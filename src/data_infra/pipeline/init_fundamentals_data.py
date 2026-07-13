"""
Fundamentals Data Initializer
Downloads quarterly financial statements, VIP indicator history, dividend histories,
industry classifications, and monthly index constituent weights from Tushare Pro.

This is a one-time bootstrap script. For daily incremental updates (including
new quarterly announcements), use update_daily_data.py instead. For Qlib binary
compilation, use build_qlib_backend.py after this script completes.

Usage:
    python src/data_infra/pipeline/init_fundamentals_data.py
    python src/data_infra/pipeline/init_fundamentals_data.py --start_year 2008 --end_year 2026
    python src/data_infra/pipeline/init_fundamentals_data.py --dry-run
"""
import sys
import os
import argparse
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import pandas as pd
from tqdm import tqdm
import gc
import glob

# Add src to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
sys.path.append(os.path.join(project_root, 'src'))

from data_infra.fetchers import TushareFetcher
from data_infra.pipeline.indicator_history_refresh import (
    IndicatorVipHistoryRefresher,
    discover_indicator_periods,
    quarter_end_periods,
)
from data_infra.storage import StorageManager

# Set up logging with RotatingFileHandler
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, 'init_fundamentals_data.log'),
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=3
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Indices whose constituent weights we track
TRACKED_INDICES = [
    '000001.SH', '000300.SH', '000905.SH', '000852.SH',
    '399001.SZ', '399006.SZ', '000688.SH'
]


class FundamentalsDataInitializer:
    """
    Bootstrap initializer for fundamentals, corporate actions, and universe data.

    Downloads per-stock quarterly financials (income, balance sheet), VIP
    historical indicator periods, dividend history, Shenwan industry
    classifications, and monthly index
    constituent weights. Data is stored via StorageManager in partitioned Parquet.

    Args:
        config_path: Path to config.yaml.
        start_year: Earliest year to fetch (e.g. 2008).
        end_year: Latest year to fetch (e.g. 2026).
        data_root: Override data root directory. Defaults to config value.
        dry_run: If True, log what would be done without making API calls.
    """

    CHUNK_SIZE = 500  # Flush to disk every N stocks to limit memory usage

    def __init__(self, config_path: str, start_year: int, end_year: int,
                 data_root: str = None, dry_run: bool = False):
        self.start_year = start_year
        self.end_year = end_year
        self.dry_run = dry_run
        self.config_path = config_path

        # Initialize fetcher and storage
        if not self.dry_run:
            self.fetcher = TushareFetcher(config_path=config_path, max_retries=5, base_sleep=1.5)
            self.storage = StorageManager(data_root=data_root)
        else:
            self.fetcher = None
            self.storage = None

        # Resolve data root for reference file lookups
        if data_root is not None:
            self.data_root = data_root
        else:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            self.data_root = os.path.normpath(
                os.path.join(project_root, config['storage']['data_root'])
            )

    def _load_stock_list(self) -> list:
        """
        Load the list of all stock codes from Phase 1 reference data.

        Returns:
            List of ts_code strings.
        """
        stock_basic_path = os.path.join(self.data_root, 'reference', 'stock_basic.parquet')
        if not os.path.exists(stock_basic_path):
            logger.error(f"Cannot find stock_basic at {stock_basic_path}. Run init_market_data.py first.")
            return []

        stock_basic = pd.read_parquet(stock_basic_path)
        ts_codes = stock_basic['ts_code'].tolist()
        logger.info(f"Loaded {len(ts_codes)} stocks from reference data.")
        return ts_codes

    def _get_processed_stocks(self) -> set:
        """
        Scan existing income data to find stocks that have already been processed.
        Used for resume-safe operation when the script is interrupted.

        Returns:
            Set of ts_code strings that already have data on disk.
        """
        processed = set()
        income_dir = os.path.join(self.data_root, 'fundamentals', 'income')
        if not os.path.exists(income_dir):
            return processed

        logger.info("Scanning existing income data for previously processed stocks...")
        for pqt_file in glob.glob(os.path.join(income_dir, "*.parquet")):
            try:
                df_existing = pd.read_parquet(pqt_file, columns=['ts_code'])
                processed.update(df_existing['ts_code'].unique())
            except Exception:
                pass

        logger.info(f"Found {len(processed)} stocks already processed. Will skip them.")
        return processed

    def download_industry_classification(self):
        """Download Shenwan 2021 industry classification (static dataset)."""
        logger.info("--- Downloading Industry Classification ---")

        if self.dry_run:
            logger.info("[DRY-RUN] Would fetch Shenwan 2021 industry classification")
            return

        try:
            sw_df = self.fetcher.fetch_index_classify(src='SW2021')
            self.storage.insert_universe_data(sw_df, 'industry_sw2021')
            logger.info(f"Saved Shenwan 2021 classification ({len(sw_df)} records)")
        except Exception as e:
            logger.error(f"Error fetching industry classifications: {e}")

    def download_fundamentals(self, ts_codes: list):
        """
        Download per-stock quarterly financials and dividends for all stocks.

        Iterates through the stock list, fetching income statements,
        balance sheets, and dividends per stock.
        Flushes to disk in chunks to prevent memory exhaustion.

        Args:
            ts_codes: List of Tushare stock codes to process.
        """
        logger.info("--- Downloading Fundamentals & Corporate Data ---")

        if self.dry_run:
            logger.info(f"[DRY-RUN] Would fetch fundamentals for {len(ts_codes)} stocks")
            return

        # Resume support: skip already-processed stocks
        processed = self._get_processed_stocks()

        income_records, balance_records, div_records = [], [], []
        start_filter = f"{self.start_year}0101"

        logger.info(f"Starting loop: ~3 API calls per stock, {len(ts_codes)} total.")

        for i, ts_code in enumerate(tqdm(ts_codes, desc="Fundamentals & Corporate Data")):
            if ts_code not in processed:
                try:
                    # Income Statement
                    inc_df = self.fetcher.fetch_income(ts_code=ts_code)
                    if not inc_df.empty:
                        inc_df = inc_df[inc_df['end_date'] >= start_filter]
                        if not inc_df.empty:
                            income_records.append(inc_df)

                    # Balance Sheet
                    bal_df = self.fetcher.fetch_balancesheet(ts_code=ts_code)
                    if not bal_df.empty:
                        bal_df = bal_df[bal_df['end_date'] >= start_filter]
                        if not bal_df.empty:
                            balance_records.append(bal_df)

                    # Dividends
                    div_df = self.fetcher.fetch_dividend(ts_code=ts_code)
                    if not div_df.empty:
                        date_col = 'ann_date' if 'ann_date' in div_df.columns else (
                            'end_date' if 'end_date' in div_df.columns else None
                        )
                        if date_col:
                            div_df = div_df[div_df[date_col] >= start_filter]
                        if not div_df.empty:
                            div_records.append(div_df)

                except Exception as e:
                    logger.error(f"Error fetching data for {ts_code}: {e}")

            # Periodically flush to disk to free memory
            if (i > 0 and i % self.CHUNK_SIZE == 0) or i == len(ts_codes) - 1:
                self._flush_records(income_records, balance_records, div_records, i, len(ts_codes))
                income_records, balance_records, div_records = [], [], []
                gc.collect()

    def _flush_records(self, income_records, balance_records, div_records,
                       current_idx, total):
        """
        Flush accumulated records to disk via StorageManager.

        Args:
            income_records: List of income DataFrames to save.
            balance_records: List of balance sheet DataFrames to save.
            div_records: List of dividend DataFrames to save.
            current_idx: Current position in the iteration (for logging).
            total: Total number of stocks (for logging).
        """
        logger.info(f"Flushing chunk to storage at {current_idx + 1}/{total}...")

        if income_records:
            clean = [df.dropna(how='all', axis=1) for df in income_records]
            self.storage.insert_fundamental_data(pd.concat(clean, ignore_index=True), "income")
        if balance_records:
            clean = [df.dropna(how='all', axis=1) for df in balance_records]
            self.storage.insert_fundamental_data(pd.concat(clean, ignore_index=True), "balancesheet")
        if div_records:
            clean = [df.dropna(how='all', axis=1) for df in div_records]
            self.storage.insert_corporate_data(pd.concat(clean, ignore_index=True), "dividends")

    def download_indicator_history(self):
        """Refresh historical indicator periods via the VIP all-stock endpoint."""
        logger.info("--- Refreshing Historical Indicators via VIP ---")

        existing_periods = discover_indicator_periods(os.path.join(self.data_root, "fundamentals", "indicators"))
        if existing_periods:
            periods = [
                period
                for period in existing_periods
                if period >= f"{self.start_year}0101" and period <= f"{self.end_year}1231"
            ]
        else:
            today = datetime.now().strftime("%Y%m%d")
            periods = [period for period in quarter_end_periods(self.start_year, self.end_year) if period < today]
        if not periods:
            logger.warning("No indicator periods selected for VIP refresh.")
            return
        if self.dry_run:
            logger.info("[DRY-RUN] Would refresh %d indicator periods via VIP", len(periods))
            return

        refresher = IndicatorVipHistoryRefresher(
            config_path=self.config_path,
            data_root=self.data_root,
            logger=logger,
        )
        summaries = refresher.run(explicit_periods=periods)
        logger.info(
            "Historical indicator refresh complete: %d periods, %d total rows",
            len(summaries),
            sum(summary.row_count for summary in summaries),
        )

    def download_index_weights(self):
        """
        Download monthly index constituent weights for all tracked indices.

        Iterates year-by-year for each index, fetching monthly weight snapshots.
        """
        logger.info("--- Downloading Index Weights ---")

        if self.dry_run:
            years = list(range(self.start_year, self.end_year + 1))
            logger.info(f"[DRY-RUN] Would fetch weights for {len(TRACKED_INDICES)} indices, "
                        f"{len(years)} years each")
            return

        years = range(self.start_year, self.end_year + 1)

        for idx_code in TRACKED_INDICES:
            records = []
            for y in tqdm(years, desc=f"Weights for {idx_code}"):
                start_d = f"{y}0101"
                end_d = f"{y}1231"
                try:
                    w_df = self.fetcher.fetch_index_weight(
                        index_code=idx_code, start_date=start_d, end_date=end_d
                    )
                    if not w_df.empty:
                        records.append(w_df)
                except Exception as e:
                    logger.error(f"Error fetching weights for {idx_code} in {y}: {e}")

            if records:
                self.storage.insert_universe_data(
                    pd.concat(records, ignore_index=True), "index_weights"
                )

    def run(self):
        """Execute the full fundamentals initialization pipeline."""
        logger.info("=" * 60)
        logger.info("  Fundamentals Data Initialization")
        logger.info(f"  Year range: {self.start_year} - {self.end_year}")
        logger.info(f"  Dry run: {self.dry_run}")
        logger.info("=" * 60)

        # 1. Load stock list from Phase 1
        ts_codes = self._load_stock_list()
        if not ts_codes and not self.dry_run:
            return

        # 2. Industry Classification (static)
        self.download_industry_classification()

        # 3. Per-stock Fundamentals & Dividends
        self.download_fundamentals(ts_codes)

        # 4. Historical Indicators (VIP period refresh)
        self.download_indicator_history()

        # 5. Index Weights (monthly)
        self.download_index_weights()

        logger.info("Fundamentals data initialization complete.")
        logger.info("Next step: run build_qlib_backend.py to compile Qlib binary backend.")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize Fundamentals Database (Financials, Dividends, Index Weights)"
    )
    parser.add_argument('--start_year', type=int, default=2008,
                        help='Start year for data range (default: 2008)')
    parser.add_argument('--end_year', type=int, default=datetime.now().year,
                        help='End year for data range (default: current year)')
    parser.add_argument('--data-root', type=str, default=None,
                        help='Override data root directory (default: from config.yaml)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Log what would be done without making API calls')

    args = parser.parse_args()

    config_path = os.path.join(project_root, 'config.yaml')
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        return

    initializer = FundamentalsDataInitializer(
        config_path=config_path,
        start_year=args.start_year,
        end_year=args.end_year,
        data_root=args.data_root,
        dry_run=args.dry_run
    )

    initializer.run()


if __name__ == "__main__":
    main()
