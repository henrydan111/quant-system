"""
Factor Research Data Initializer (Phase 3)
Downloads additional data sources required for the 177-factor research catalog:
  1. cashflow      - Cash flow statements (per stock, quarterly)
  2. forecast      - Earnings pre-announcements (per stock)
  3. moneyflow     - Daily capital flow (per trading day)
  4. hk_hold       - Northbound HKSC daily holdings (per trading day)
  5. margin_detail - Margin trading details (per trading day)
  6. stk_holdernumber - Shareholder count (per stock, quarterly)
  7. stk_limit     - Daily limit prices (per trading day)

Storage follows existing conventions:
  - Fundamentals (cashflow, forecast, stk_holdernumber): partitioned by end_date/ann_date
  - Market data (moneyflow, hk_hold, margin, stk_limit): partitioned by trade_date/year

Usage:
    python src/data_infra/pipeline/init_factor_data.py
    python src/data_infra/pipeline/init_factor_data.py --category moneyflow
    python src/data_infra/pipeline/init_factor_data.py --dry-run
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
from data_infra.storage import StorageManager

# Set up logging with RotatingFileHandler
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, 'init_factor_data.log'),
            maxBytes=10*1024*1024,
            backupCount=3
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# All categories available for download
ALL_CATEGORIES = [
    'cashflow', 'forecast', 'moneyflow', 'hk_hold',
    'margin_detail', 'stk_holdernumber', 'stk_limit'
]


class FactorDataInitializer:
    """Downloads factor research data from Tushare Pro API.

    Handles 7 new data endpoints needed for the 177-factor catalog.
    Supports per-category download, resume-safe operation, and dry-run mode.

    Args:
        config_path: Path to config.yaml.
        start_date: Earliest date (YYYYMMDD) for market data.
        end_date: Latest date (YYYYMMDD) for market data.
        start_year: Earliest year for fundamental data.
        end_year: Latest year for fundamental data.
        categories: List of categories to download, or None for all.
        data_root: Override data root directory.
        dry_run: If True, log without making API calls.
    """

    CHUNK_SIZE = 500  # Flush per-stock data every N stocks

    def __init__(self, config_path, start_date, end_date,
                 start_year, end_year, categories=None,
                 data_root=None, dry_run=False):
        self.start_date = start_date
        self.end_date = end_date
        self.start_year = start_year
        self.end_year = end_year
        self.categories = categories or ALL_CATEGORIES
        self.dry_run = dry_run
        self.config_path = config_path

        if not self.dry_run:
            self.fetcher = TushareFetcher(config_path=config_path, max_retries=5, base_sleep=1.0)
            self.storage = StorageManager(data_root=data_root)
        else:
            self.fetcher = None
            self.storage = None

        # Resolve data root
        if data_root is not None:
            self.data_root = data_root
        else:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            self.data_root = os.path.normpath(
                os.path.join(project_root, config['storage']['data_root'])
            )

    def _load_stock_list(self):
        """Load all stock codes from Phase 1 reference data.

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

    def _load_trading_dates(self):
        """Load trading calendar dates within the configured date range.

        Returns:
            List of date strings (YYYYMMDD).
        """
        cal_path = os.path.join(self.data_root, 'reference', 'trade_cal.parquet')
        if not os.path.exists(cal_path):
            logger.error(f"Cannot find trade_cal at {cal_path}. Run init_market_data.py first.")
            return []
        cal = pd.read_parquet(cal_path)
        cal = cal[(cal['cal_date'] >= self.start_date) & (cal['cal_date'] <= self.end_date)]
        if 'is_open' in cal.columns:
            cal = cal[cal['is_open'] == 1]
        dates = sorted(cal['cal_date'].unique().tolist())
        logger.info(f"Loaded {len(dates)} trading dates ({dates[0]} to {dates[-1]}).")
        return dates

    def _get_existing_dates(self, category):
        """Scan existing data to find dates already downloaded (for resume).

        Args:
            category: Data category name.

        Returns:
            Set of date strings (YYYYMMDD) already on disk.
        """
        existing = set()
        market_dir = os.path.join(self.data_root, 'market', category)
        if not os.path.exists(market_dir):
            return existing
        for f in glob.glob(os.path.join(market_dir, '**', '*.parquet'), recursive=True):
            # Extract date from filename like moneyflow_20230101.parquet
            basename = os.path.basename(f).replace('.parquet', '')
            parts = basename.split('_')
            if len(parts) >= 2:
                date_part = parts[-1]
                if len(date_part) == 8 and date_part.isdigit():
                    existing.add(date_part)
        if existing:
            logger.info(f"Found {len(existing)} existing {category} dates. Will skip them.")
        return existing

    def _get_processed_stocks(self, category):
        """Find stocks already processed for per-stock categories (cashflow, forecast, holdernumber).

        Args:
            category: Data category name.

        Returns:
            Set of ts_code strings already on disk.
        """
        processed = set()
        funda_dir = os.path.join(self.data_root, 'fundamentals', category)
        corp_dir = os.path.join(self.data_root, 'corporate', category)

        for search_dir in [funda_dir, corp_dir]:
            if not os.path.exists(search_dir):
                continue
            for pqt_file in glob.glob(os.path.join(search_dir, '*.parquet')):
                try:
                    df_existing = pd.read_parquet(pqt_file, columns=['ts_code'])
                    processed.update(df_existing['ts_code'].unique())
                except Exception:
                    pass

        if processed:
            logger.info(f"Found {len(processed)} stocks already processed for {category}.")
        return processed

    # ------------------------------------------------------------------ #
    #  Per-Stock Downloads (cashflow, forecast, stk_holdernumber)          #
    # ------------------------------------------------------------------ #

    def download_cashflow(self, ts_codes):
        """Download cash flow statements for all stocks.

        Stored as: data/fundamentals/cashflow/cashflow_{end_date}.parquet
        """
        logger.info("--- Downloading Cash Flow Statements ---")
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would fetch cashflow for {len(ts_codes)} stocks")
            return

        processed = self._get_processed_stocks('cashflow')
        records = []
        start_filter = f"{self.start_year}0101"

        for i, ts_code in enumerate(tqdm(ts_codes, desc="Cash Flow")):
            if ts_code in processed:
                continue
            try:
                df = self.fetcher.fetch_cashflow(ts_code=ts_code)
                if not df.empty:
                    df = df[df['end_date'] >= start_filter]
                    if not df.empty:
                        records.append(df)
            except Exception as e:
                logger.error(f"Error fetching cashflow for {ts_code}: {e}")

            if (i > 0 and i % self.CHUNK_SIZE == 0) or i == len(ts_codes) - 1:
                if records:
                    clean = [d.dropna(how='all', axis=1) for d in records]
                    self.storage.insert_fundamental_data(
                        pd.concat(clean, ignore_index=True), "cashflow"
                    )
                    logger.info(f"Flushed cashflow chunk at {i+1}/{len(ts_codes)}")
                records = []
                gc.collect()

    def download_forecast(self, ts_codes):
        """Download earnings forecasts for all stocks.

        Stored as: data/fundamentals/forecast/forecast_{end_date}.parquet
        """
        logger.info("--- Downloading Earnings Forecasts ---")
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would fetch forecast for {len(ts_codes)} stocks")
            return

        processed = self._get_processed_stocks('forecast')
        records = []
        start_filter = f"{self.start_year}0101"

        for i, ts_code in enumerate(tqdm(ts_codes, desc="Forecast")):
            if ts_code in processed:
                continue
            try:
                df = self.fetcher.fetch_forecast(ts_code=ts_code)
                if not df.empty:
                    if 'end_date' in df.columns:
                        df = df[df['end_date'] >= start_filter]
                    if not df.empty:
                        records.append(df)
            except Exception as e:
                logger.error(f"Error fetching forecast for {ts_code}: {e}")

            if (i > 0 and i % self.CHUNK_SIZE == 0) or i == len(ts_codes) - 1:
                if records:
                    clean = [d.dropna(how='all', axis=1) for d in records]
                    self.storage.insert_fundamental_data(
                        pd.concat(clean, ignore_index=True), "forecast"
                    )
                    logger.info(f"Flushed forecast chunk at {i+1}/{len(ts_codes)}")
                records = []
                gc.collect()

    def download_stk_holdernumber(self, ts_codes):
        """Download shareholder count data for all stocks.

        Stored as: data/corporate/holder_number/holder_number_{year}.parquet
        """
        logger.info("--- Downloading Shareholder Count ---")
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would fetch stk_holdernumber for {len(ts_codes)} stocks")
            return

        processed = self._get_processed_stocks('holder_number')
        records = []

        for i, ts_code in enumerate(tqdm(ts_codes, desc="Holder Number")):
            if ts_code in processed:
                continue
            try:
                df = self.fetcher.fetch_stk_holdernumber(ts_code=ts_code)
                if not df.empty:
                    records.append(df)
            except Exception as e:
                logger.error(f"Error fetching holdernumber for {ts_code}: {e}")

            if (i > 0 and i % self.CHUNK_SIZE == 0) or i == len(ts_codes) - 1:
                if records:
                    clean = [d.dropna(how='all', axis=1) for d in records]
                    self.storage.insert_corporate_data(
                        pd.concat(clean, ignore_index=True), "holder_number"
                    )
                    logger.info(f"Flushed holder_number chunk at {i+1}/{len(ts_codes)}")
                records = []
                gc.collect()

    # ------------------------------------------------------------------ #
    #  Per-Date Downloads (moneyflow, hk_hold, margin_detail, stk_limit)  #
    # ------------------------------------------------------------------ #

    def _download_daily_category(self, trading_dates, category, fetch_func):
        """Generic daily data downloader for market-level endpoints.

        Iterates over trading dates, fetches all stocks for each date,
        and stores using StorageManager.insert_market_data().

        Args:
            trading_dates: List of trading date strings (YYYYMMDD).
            category: Storage category name.
            fetch_func: Fetcher method to call with trade_date=.
        """
        logger.info(f"--- Downloading {category} ---")
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would fetch {category} for {len(trading_dates)} dates")
            return

        existing_dates = self._get_existing_dates(category)
        pending = [d for d in trading_dates if d not in existing_dates]
        logger.info(f"{category}: {len(pending)} dates to download "
                     f"({len(existing_dates)} already exist)")

        batch_records = []
        batch_size = 20  # Flush every 20 dates to balance I/O vs memory

        for i, trade_date in enumerate(tqdm(pending, desc=category)):
            try:
                df = fetch_func(trade_date=trade_date)
                if not df.empty:
                    batch_records.append(df)
            except Exception as e:
                logger.error(f"Error fetching {category} for {trade_date}: {e}")

            if (i > 0 and i % batch_size == 0) or i == len(pending) - 1:
                if batch_records:
                    combined = pd.concat(batch_records, ignore_index=True)
                    self.storage.insert_market_data(combined, category)
                    logger.info(f"Flushed {category} batch at {i+1}/{len(pending)} "
                                 f"({len(combined)} records)")
                batch_records = []
                gc.collect()

    def download_moneyflow(self, trading_dates):
        """Download daily capital flow data."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would fetch moneyflow for {len(trading_dates)} dates")
            return
        self._download_daily_category(
            trading_dates, 'moneyflow', self.fetcher.fetch_moneyflow
        )

    def download_hk_hold(self, trading_dates):
        """Download northbound holding data.

        Note: hk_hold data is available from ~2017 onwards.
        """
        if self.dry_run:
            filtered = [d for d in trading_dates if d >= '20170101']
            logger.info(f"[DRY-RUN] Would fetch northbound for {len(filtered)} dates")
            return
        filtered = [d for d in trading_dates if d >= '20170101']
        self._download_daily_category(
            filtered, 'northbound', self.fetcher.fetch_hk_hold
        )

    def download_margin_detail(self, trading_dates):
        """Download margin trading detail data.

        Note: margin_detail data is available from ~2010 onwards.
        """
        if self.dry_run:
            filtered = [d for d in trading_dates if d >= '20100101']
            logger.info(f"[DRY-RUN] Would fetch margin for {len(filtered)} dates")
            return
        filtered = [d for d in trading_dates if d >= '20100101']
        self._download_daily_category(
            filtered, 'margin', self.fetcher.fetch_margin_detail
        )

    def download_stk_limit(self, trading_dates):
        """Download daily limit-up/limit-down prices."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would fetch stk_limit for {len(trading_dates)} dates")
            return
        self._download_daily_category(
            trading_dates, 'stk_limit', self.fetcher.fetch_stk_limit
        )


    # ------------------------------------------------------------------ #
    #  Main Entry Point                                                    #
    # ------------------------------------------------------------------ #

    def run(self):
        """Execute the factor data download pipeline."""
        logger.info("=" * 60)
        logger.info("  Factor Research Data Initialization (Phase 3)")
        logger.info(f"  Date range: {self.start_date} - {self.end_date}")
        logger.info(f"  Year range: {self.start_year} - {self.end_year}")
        logger.info(f"  Categories: {', '.join(self.categories)}")
        logger.info(f"  Dry run: {self.dry_run}")
        logger.info("=" * 60)

        # Load required reference data
        ts_codes = self._load_stock_list()
        trading_dates = self._load_trading_dates()

        if not ts_codes and not self.dry_run:
            return
        if not trading_dates and not self.dry_run:
            return

        # Per-stock categories
        if 'cashflow' in self.categories:
            self.download_cashflow(ts_codes)

        if 'forecast' in self.categories:
            self.download_forecast(ts_codes)

        if 'stk_holdernumber' in self.categories:
            self.download_stk_holdernumber(ts_codes)

        # Per-date categories
        if 'moneyflow' in self.categories:
            self.download_moneyflow(trading_dates)

        if 'hk_hold' in self.categories:
            self.download_hk_hold(trading_dates)

        if 'margin_detail' in self.categories:
            self.download_margin_detail(trading_dates)

        if 'stk_limit' in self.categories:
            self.download_stk_limit(trading_dates)

        logger.info("=" * 60)
        logger.info("Factor research data initialization complete.")
        logger.info("Next: rebuild Qlib backend with build_qlib_backend.py if needed.")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Download factor research data sources from Tushare Pro"
    )
    parser.add_argument('--start-date', type=str, default='20080101',
                        help='Start date for market data (YYYYMMDD, default: 20080101)')
    parser.add_argument('--end-date', type=str, default=datetime.now().strftime('%Y%m%d'),
                        help='End date for market data (YYYYMMDD, default: today)')
    parser.add_argument('--start-year', type=int, default=2008,
                        help='Start year for fundamental data (default: 2008)')
    parser.add_argument('--end-year', type=int, default=datetime.now().year,
                        help='End year for fundamental data (default: current year)')
    parser.add_argument('--category', type=str, nargs='+', default=None,
                        choices=ALL_CATEGORIES,
                        help='Specific categories to download (default: all)')
    parser.add_argument('--data-root', type=str, default=None,
                        help='Override data root directory')
    parser.add_argument('--dry-run', action='store_true',
                        help='Log what would be done without API calls')
    args = parser.parse_args()

    config_path = os.path.join(project_root, 'config.yaml')
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        return

    initializer = FactorDataInitializer(
        config_path=config_path,
        start_date=args.start_date,
        end_date=args.end_date,
        start_year=args.start_year,
        end_year=args.end_year,
        categories=args.category,
        data_root=args.data_root,
        dry_run=args.dry_run
    )

    initializer.run()


if __name__ == "__main__":
    main()
