"""
Data Storage Interface
Lightweight and locally cached data storage using Parquet files.
Creates raw data cache and manages transition into Qlib's binary format.
"""
import pandas as pd
import os
import glob
import logging
import sys
import subprocess
import json
from datetime import datetime

class StorageManager:
    def __init__(self, data_root=None):
        if data_root is not None:
            self.data_root = data_root
        else:
            # Resolve from config.yaml relative to project root
            import yaml
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            config_path = os.path.join(project_root, 'config.yaml')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            self.data_root = os.path.normpath(
                os.path.join(project_root, config['storage']['data_root'])
            )
        os.makedirs(self.data_root, exist_ok=True)
        self.raw_manifest_dir = os.path.join(self.data_root, 'raw_cache', 'manifests')
        os.makedirs(self.raw_manifest_dir, exist_ok=True)
        self.ingest_build_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        logging.info(f"Initialized local storage cache at {self.data_root}")

    def _record_ingest_manifest(self, dataset: str, file_paths: list[str], row_count: int, source_params=None):
        """Append a raw-ingest manifest entry for the current storage session."""
        manifest_path = os.path.join(self.raw_manifest_dir, f'{self.ingest_build_id}.jsonl')
        payload = {
            'build_id': self.ingest_build_id,
            'dataset': dataset,
            'fetched_at': datetime.now().isoformat(timespec='seconds'),
            'row_count': int(row_count),
            'files': [os.path.normpath(path) for path in file_paths],
            'source_params': source_params or {},
        }
        with open(manifest_path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + '\n')

    def create_daily_table(self):
        """Create storage location (No DB used anymore)."""
        pass

    def insert_daily_data(self, df: pd.DataFrame):
        """
        Store daily OHLCV and valuation dataframe as a local parquet file.
        
        The storage is structurally partitioned by the exact `trade_date` 
        to ensure high read/write velocity without relying on a SQL/NoSQL DB.
        
        Args:
            df (pd.DataFrame): DataFrame containing daily stock market data.
        """
        if df.empty: return
        
        # Determine the trade date from the dataframe to name the file
        dates = df['trade_date'].unique()
        written_files = []
        for date_val in dates:
            date_str = pd.to_datetime(date_val).strftime("%Y%m%d")
            year_str = date_str[:4]
            year_dir = os.path.join(self._get_data_root(), 'market', 'daily', year_str)
            os.makedirs(year_dir, exist_ok=True)
            file_path = os.path.join(year_dir, f"daily_{date_str}.parquet")
            
            # Filter data for this date
            day_df = df[df['trade_date'] == date_val]
            
            # Overwrite if exists
            day_df.to_parquet(file_path, index=False)
            logging.info(f"Saved {len(day_df)} records to {file_path}")
            written_files.append(file_path)
        self._record_ingest_manifest('daily', written_files, len(df))

    def _get_data_root(self):
        return self.data_root

    def insert_fundamental_data(self, df: pd.DataFrame, category: str):
        """
        Store quarterly/annual fundamental data in Parquet format.
        
        Files are dynamically partitioned by the exact `end_date` (reporting period),
        and data is implicitly deduplicated before saving.
        
        Args:
            df (pd.DataFrame): DataFrame containing the corporate financials.
            category (str): Financial category ('income', 'balancesheet', 'indicators').
        """
        if df.empty: return
        target_dir = os.path.join(self._get_data_root(), 'fundamentals', category)
        os.makedirs(target_dir, exist_ok=True)
        written_files = []
        if 'end_date' in df.columns:
            dates = df['end_date'].unique()
            for d in dates:
                if pd.isna(d): continue
                period_df = df[df['end_date'] == d]
                file_path = os.path.join(target_dir, f"{category}_{d}.parquet")
                if os.path.exists(file_path):
                    existing = pd.read_parquet(file_path)
                    combined = pd.concat([existing, period_df]).drop_duplicates()
                    combined.to_parquet(file_path, index=False)
                else:
                    period_df.to_parquet(file_path, index=False)
                logging.info(f"Saved {len(period_df)} {category} records to {file_path}")
                written_files.append(file_path)
        else:
            file_path = os.path.join(target_dir, f"{category}.parquet")
            df.to_parquet(file_path, index=False)
            written_files.append(file_path)
        self._record_ingest_manifest(category, written_files, len(df))

    def insert_corporate_data(self, df: pd.DataFrame, category: str):
        """
        Store corporate actions (e.g., dividends, splits) in Parquet format.
        
        Files are partitioned by exact year of the announcement date (`ann_date`) 
        or reporting period (`end_date`), automatically deduplicated if the file exists.
        
        Args:
            df (pd.DataFrame): DataFrame containing the corporate action records.
            category (str): The specific category (e.g., 'dividends').
        """
        if df.empty: return
        target_dir = os.path.join(self._get_data_root(), 'corporate', category)
        os.makedirs(target_dir, exist_ok=True)
        written_files = []
        # Dividends usually have end_date (period) or ann_date
        date_col = 'end_date' if 'end_date' in df.columns else ('ann_date' if 'ann_date' in df.columns else None)
        if date_col:
            df['year'] = pd.to_datetime(df[date_col]).dt.year
            for y in df['year'].dropna().unique():
                y_df = df[df['year'] == y].drop(columns=['year'])
                file_path = os.path.join(target_dir, f"{category}_{int(y)}.parquet")
                
                # Deduplicate if file exists
                if os.path.exists(file_path):
                    existing = pd.read_parquet(file_path)
                    combined = pd.concat([existing, y_df]).drop_duplicates()
                    combined.to_parquet(file_path, index=False)
                else:
                    y_df.to_parquet(file_path, index=False)
                logging.info(f"Saved {len(y_df)} {category} records to {file_path}")
                written_files.append(file_path)
        else:
            file_path = os.path.join(target_dir, f"{category}.parquet")
            df.to_parquet(file_path, index=False)
            written_files.append(file_path)
        self._record_ingest_manifest(category, written_files, len(df))

    def insert_market_data(self, df: pd.DataFrame, category: str):
        """Store daily market-related data (moneyflow, margin, northbound, stk_limit).

        Files are partitioned by trade_date (YYYY/category_YYYYMMDD.parquet),
        following the same pattern as daily OHLCV data. Deduplicates if file exists.

        Args:
            df: DataFrame containing daily market data with 'trade_date' column.
            category: Data category (e.g., 'moneyflow', 'margin', 'northbound', 'stk_limit').
        """
        if df.empty:
            return
        dates = df['trade_date'].unique()
        written_files = []
        for date_val in dates:
            date_str = pd.to_datetime(date_val).strftime("%Y%m%d")
            year_str = date_str[:4]
            year_dir = os.path.join(self._get_data_root(), 'market', category, year_str)
            os.makedirs(year_dir, exist_ok=True)
            file_path = os.path.join(year_dir, f"{category}_{date_str}.parquet")

            day_df = df[df['trade_date'] == date_val]

            if os.path.exists(file_path):
                existing = pd.read_parquet(file_path)
                combined = pd.concat([existing, day_df]).drop_duplicates()
                combined.to_parquet(file_path, index=False)
            else:
                day_df.to_parquet(file_path, index=False)
            logging.info(f"Saved {len(day_df)} {category} records to {file_path}")
            written_files.append(file_path)
        self._record_ingest_manifest(category, written_files, len(df))

    def insert_universe_data(self, df: pd.DataFrame, category: str):

        """
        Store universe mapping like index_weights or industry mappings.
        """
        if df.empty: return
        target_dir = os.path.join(self._get_data_root(), 'universe', category)
        os.makedirs(target_dir, exist_ok=True)
        written_files = []
        
        if category == 'index_weights' and 'trade_date' in df.columns:
            df['month'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y%m')
            for m in df['month'].unique():
                m_df = df[df['month'] == m].drop(columns=['month'])
                file_path = os.path.join(target_dir, f"{category}_{m}.parquet")
                if os.path.exists(file_path):
                    existing = pd.read_parquet(file_path)
                    combined = pd.concat([existing, m_df]).drop_duplicates()
                    combined.to_parquet(file_path, index=False)
                else:
                    m_df.to_parquet(file_path, index=False)
                logging.info(f"Saved {category} records for month {m} to {file_path}")
                written_files.append(file_path)
        else:
            file_path = os.path.join(target_dir, f"{category}.parquet")
            df.to_parquet(file_path, index=False)
            written_files.append(file_path)
        self._record_ingest_manifest(category, written_files, len(df))

    def export_to_qlib(self, dest_dir: str, mode="all", *, calendar_policy_id: str):
        """
        Export local parquet raw data into Qlib-compatible binary format.

        Reads all daily parquet files, converts them to intermediate CSVs,
        and invokes the Qlib `dump_bin.py` script to generate `.bin` files.

        Args:
            dest_dir (str): Target directory where Qlib binary data will be stored.
            mode (str, optional): Dump mode. 'all' for initialization, 'update' for daily appends. Defaults to 'all'.
            calendar_policy_id (str): Calendar policy stamped into the published
                manifest — REQUIRED, no default (UNFREEZE_PLAN.md D1).
        """
        from data_infra.pit_backend import build_qlib_backend

        build_qlib_backend(
            data_root=self._get_data_root(),
            qlib_dir=dest_dir,
            mode=mode,
            include_phase3=True,
            publish=True,
            allow_exceptions=True,
            calendar_policy_id=calendar_policy_id,
        )
