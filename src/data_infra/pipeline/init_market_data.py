"""
Market Data Initializer
Downloads reference data (stock_basic, trade_cal), major index series,
and daily OHLCV + valuation + adjustment factor data from Tushare Pro.

This is a one-time bootstrap script. For daily incremental updates,
use update_daily_data.py instead. For Qlib binary compilation,
use build_qlib_backend.py after this script completes.

Usage:
    python src/data_infra/pipeline/init_market_data.py --start_date 20100101 --end_date 20260227
    python src/data_infra/pipeline/init_market_data.py --dry-run
"""
import sys
import os
import argparse
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import pandas as pd
from tqdm import tqdm

# Add src to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
sys.path.append(os.path.join(project_root, 'src'))

from data_infra.fetchers import TushareFetcher

# Set up logging with RotatingFileHandler
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, 'init_market_data.log'),
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=3
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Major indices tracked by the system
TARGET_INDICES = {
    '000001.SH': '上证指数',
    '000300.SH': '沪深300',
    '000905.SH': '中证500',
    '000852.SH': '中证1000',
    '399001.SZ': '深证成指',
    '399006.SZ': '创业板指',
    '000688.SH': '科创50'
}


class MarketDataInitializer:
    """
    Bootstrap initializer for Phase 1 market data.

    Downloads reference data (stock_basic, trade_cal), major index daily series,
    and per-date composite daily data (OHLCV + valuation + adj_factor) from Tushare Pro.
    All data is stored as hierarchical Parquet files under the configured data root.

    Args:
        config_path: Path to config.yaml.
        start_date: Start date in YYYYMMDD format.
        end_date: End date in YYYYMMDD format.
        data_root: Root directory for data storage. Defaults to config value.
        dry_run: If True, log what would be done without making API calls.
    """

    def __init__(self, config_path: str, start_date: str, end_date: str,
                 data_root: str = None, dry_run: bool = False):
        self.start_date = start_date
        self.end_date = end_date
        self.dry_run = dry_run

        # Resolve data root from config if not provided
        if data_root is None:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            self.data_dir = os.path.normpath(
                os.path.join(project_root, config['storage']['data_root'])
            )
        else:
            self.data_dir = data_root

        # Initialize fetcher (skipped in dry-run mode)
        if not self.dry_run:
            self.fetcher = TushareFetcher(config_path=config_path, max_retries=5, base_sleep=1.5)
        else:
            self.fetcher = None

        # Setup directory structure
        self.ref_dir = os.path.join(self.data_dir, 'reference')
        self.market_daily_dir = os.path.join(self.data_dir, 'market', 'daily')
        self.index_dir = os.path.join(self.data_dir, 'market', 'index')

        for d in [self.ref_dir, self.market_daily_dir, self.index_dir]:
            os.makedirs(d, exist_ok=True)

    def download_reference_data(self):
        """
        Download stock basic info and trade calendar.

        Returns:
            list: List of trading date strings (YYYYMMDD) for the requested range.
        """
        logger.info("--- Downloading Reference Data ---")

        if self.dry_run:
            logger.info("[DRY-RUN] Would fetch stock_basic and trade_cal")
            return []

        # Stock basic
        logger.info("Fetching stock_basic...")
        df_basic = self.fetcher.fetch_stock_basic()
        if not df_basic.empty:
            file_path = os.path.join(self.ref_dir, "stock_basic.parquet")
            df_basic.to_parquet(file_path, index=False)
            logger.info(f"Saved stock_basic ({len(df_basic)} records) to {file_path}")
        else:
            logger.error("Failed to fetch stock_basic")

        # Trade calendar
        logger.info(f"Fetching trade_cal from {self.start_date} to {self.end_date}...")
        df_cal = self.fetcher.fetch_trade_cal(start_date=self.start_date, end_date=self.end_date)
        if not df_cal.empty:
            file_path = os.path.join(self.ref_dir, "trade_cal.parquet")
            df_cal.to_parquet(file_path, index=False)
            logger.info(f"Saved trade_cal ({len(df_cal)} records) to {file_path}")
        else:
            logger.error("Failed to fetch trade_cal")

        return df_cal['cal_date'].tolist() if not df_cal.empty else []

    def download_index_data(self):
        """Download major index daily data for all tracked indices."""
        logger.info("--- Downloading Index Data ---")

        if self.dry_run:
            logger.info(f"[DRY-RUN] Would fetch index_daily for {len(TARGET_INDICES)} indices")
            return

        for ts_code, name in TARGET_INDICES.items():
            logger.info(f"Fetching index_daily for {name} ({ts_code})...")
            try:
                df_index = self.fetcher.fetch_index_daily(
                    ts_code=ts_code, start_date=self.start_date, end_date=self.end_date
                )
                if not df_index.empty:
                    file_path = os.path.join(self.index_dir, f"index_{ts_code}.parquet")
                    df_index.to_parquet(file_path, index=False)
                    logger.info(f"Saved {name} ({len(df_index)} records) to {file_path}")
            except Exception as e:
                logger.error(f"Error fetching index {name}: {e}")

    def download_daily_market_data(self, trade_dates: list):
        """
        Iterate through trade dates and download composite daily data.

        For each trading day, fetches OHLCV, daily valuation metrics, and
        adjustment factors, merges them into a single DataFrame, and saves
        as a partitioned Parquet file.

        Args:
            trade_dates: List of trading date strings (YYYYMMDD).
        """
        logger.info("--- Downloading Daily Market Data ---")

        if self.dry_run:
            logger.info(f"[DRY-RUN] Would download {len(trade_dates)} trading days")
            return

        for trade_date in tqdm(trade_dates, desc="Daily Data"):
            year = trade_date[:4]
            year_dir = os.path.join(self.market_daily_dir, year)
            os.makedirs(year_dir, exist_ok=True)

            file_path = os.path.join(year_dir, f"daily_{trade_date}.parquet")

            # Skip if already downloaded (resume-safe)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 10240:
                logger.debug(f"Skipping {trade_date}, already exists.")
                continue

            try:
                # 1. Fetch OHLCV Price
                df_daily = self.fetcher.fetch_daily_data(trade_date=trade_date)
                if df_daily.empty:
                    logger.warning(f"No daily data returned for {trade_date}")
                    continue

                # 2. Fetch Daily Basic (valuation: PE, PB, turnover, etc.)
                df_basic = self.fetcher.fetch_fundamentals(trade_date=trade_date)

                # 3. Fetch Adjustment Factors
                df_adj = self.fetcher.fetch_adj_factor(trade_date=trade_date)

                # Merge datasets
                df_merged = df_daily
                if not df_basic.empty:
                    df_basic = df_basic.drop(columns=['close'], errors='ignore')
                    df_merged = pd.merge(df_merged, df_basic, on=['ts_code', 'trade_date'], how='left')
                if not df_adj.empty:
                    df_merged = pd.merge(df_merged, df_adj, on=['ts_code', 'trade_date'], how='left')

                # Save to Parquet
                df_merged.to_parquet(file_path, index=False)
                logger.info(f"Saved merged daily data ({len(df_merged)} stocks) for {trade_date}")

            except Exception as e:
                logger.error(f"Error processing {trade_date}: {e}")


def main():
    # Raw-store quiescence (HARD pre-promotion integration gate): refuse to run while a
    # recovered family is being swapped into the live store — the tree may be half-replaced.
    from data_infra.recovery_quiescence import assert_no_active_recovery
    assert_no_active_recovery()
    parser = argparse.ArgumentParser(
        description="Initialize Market Data Database from Tushare Pro"
    )
    parser.add_argument('--start_date', type=str, default='20100101',
                        help='Start date in YYYYMMDD (default: 20100101)')
    parser.add_argument('--end_date', type=str, default=datetime.now().strftime('%Y%m%d'),
                        help='End date in YYYYMMDD (default: today)')
    parser.add_argument('--data-root', type=str, default=None,
                        help='Override data root directory (default: from config.yaml)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Log what would be done without making API calls')

    args = parser.parse_args()

    config_path = os.path.join(project_root, 'config.yaml')
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        return

    initializer = MarketDataInitializer(
        config_path=config_path,
        start_date=args.start_date,
        end_date=args.end_date,
        data_root=args.data_root,
        dry_run=args.dry_run
    )

    # 1. Download Reference Data (returns trading days list)
    trade_dates = initializer.download_reference_data()

    if not trade_dates and not args.dry_run:
        logger.error("Failed to get trading calendar. Aborting.")
        return

    # 2. Download Index Data
    initializer.download_index_data()

    # 3. Loop through days to build daily core data
    initializer.download_daily_market_data(trade_dates)

    logger.info("Market data initialization complete.")
    logger.info("Next step: run init_fundamentals_data.py, then build_qlib_backend.py")


if __name__ == "__main__":
    main()
