"""
Re-fetch Index Weights at Monthly Granularity
==============================================
The original init_phase2_data.py fetched index_weight by year. However,
Tushare's index_weight API sometimes returns incomplete data when queried
over a full year — especially for CSI1000 (000852.SH) which only returns
Jul-Dec data in yearly queries.

This script re-fetches month by month for all tracked indices, compares
with existing data, and fills in any gaps.

Rate limit: 2000 points = 200 calls/min. We use 0.4s sleep between calls.
Total calls: ~7 indices × 18 years × 12 months = ~1512 (well within daily limit).

Usage:
    python data/refetch_index_weights.py [--dry-run] [--start-year 2008] [--end-year 2026]
"""

import argparse
import glob
import logging
import os
import sys
import time
from calendar import monthrange
from datetime import datetime

import pandas as pd
from tqdm import tqdm

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

# NOTE: TushareFetcher and StorageManager are imported lazily inside
# refetch_missing_months() to allow --dry-run without tushare installed.

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

INDEX_WEIGHTS_DIR = os.path.join(project_root, "data", "universe", "index_weights")

INDICES_TO_TRACK = [
    '000001.SH',  # 上证综指
    '000300.SH',  # 沪深300
    '000905.SH',  # 中证500
    '000852.SH',  # 中证1000
    '399001.SZ',  # 深证成指
    '399006.SZ',  # 创业板指
    '000688.SH',  # 科创50
]

# For each index, the approximate date from which data should exist
# (before this, the index didn't exist or wasn't tracked)
INDEX_START_DATES = {
    '000001.SH': '200801',
    '000300.SH': '200501',
    '000905.SH': '200801',
    '000852.SH': '201410',
    '399001.SZ': '200901',
    '399006.SZ': '201006',
    '000688.SH': '201912',
}


def load_existing_data() -> dict:
    """
    Load existing index_weights parquet files and build an index of
    which (index_code, YYYYMM) combinations already have data.
    Returns: dict of {(index_code, YYYYMM): count_of_records}
    """
    existing = {}
    parquet_files = sorted(glob.glob(os.path.join(INDEX_WEIGHTS_DIR, "*.parquet")))
    
    for pf in parquet_files:
        try:
            df = pd.read_parquet(pf)
            if 'index_code' not in df.columns or 'trade_date' not in df.columns:
                continue
            
            # Extract YYYYMM from trade_date
            df['_ym'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.strftime('%Y%m')
            
            for (idx, ym), group in df.groupby(['index_code', '_ym']):
                existing[(idx, ym)] = len(group)
        except Exception as e:
            logging.warning(f"Failed to read {pf}: {e}")
    
    return existing


def generate_month_list(start_year: int, end_year: int) -> list:
    """Generate list of YYYYMM strings from start_year to end_year."""
    months = []
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            ym = f"{y}{m:02d}"
            # Don't go beyond current month
            if ym > datetime.now().strftime('%Y%m'):
                break
            months.append(ym)
    return months


def refetch_missing_months(start_year: int, end_year: int, dry_run: bool = False):
    """
    Compare existing data with expected coverage and re-fetch missing months.
    """
    logging.info("Loading existing index_weights data...")
    existing = load_existing_data()
    
    logging.info(f"Found {len(existing)} existing (index, month) combinations")
    
    # Build the list of (index_code, YYYYMM) that SHOULD have data
    all_months = generate_month_list(start_year, end_year)
    
    missing = []
    for idx_code in INDICES_TO_TRACK:
        idx_start = INDEX_START_DATES.get(idx_code, '200801')
        for ym in all_months:
            if ym < idx_start:
                continue
            key = (idx_code, ym)
            if key not in existing:
                missing.append(key)
    
    logging.info(f"Found {len(missing)} missing (index, month) combinations to re-fetch")
    
    if dry_run:
        logging.info("=== DRY RUN - showing first 50 missing combinations ===")
        for idx_code, ym in missing[:50]:
            print(f"  MISSING: {idx_code} {ym}")
        if len(missing) > 50:
            print(f"  ... and {len(missing) - 50} more")
        
        # Also show summary per index
        print("\n=== Summary per index ===")
        for idx_code in INDICES_TO_TRACK:
            idx_missing = [m for i, m in missing if i == idx_code]
            idx_existing = sum(1 for (i, m) in existing if i == idx_code)
            idx_start = INDEX_START_DATES.get(idx_code, '200801')
            expected = sum(1 for ym in all_months if ym >= idx_start)
            print(f"  {idx_code}: {idx_existing} existing, {len(idx_missing)} missing, {expected} expected total")
        return
    
    # Initialize Tushare and Storage (lazy imports)
    from data_infra.fetchers import TushareFetcher
    from data_infra.storage import StorageManager
    
    config_path = os.path.join(project_root, 'config.yaml')

    fetcher = TushareFetcher(config_path=config_path)
    storage = StorageManager(data_root=os.path.join(project_root, 'data'))
    
    # Fetch missing months
    total = len(missing)
    fetched_count = 0
    empty_count = 0
    error_count = 0
    
    for i, (idx_code, ym) in enumerate(
        tqdm(missing, desc="Index weight refetch", unit="month", dynamic_ncols=True),
        start=1,
    ):
        year = int(ym[:4])
        month = int(ym[4:6])
        _, last_day = monthrange(year, month)
        
        start_date = f"{ym}01"
        end_date = f"{ym}{last_day:02d}"
        
        logging.info(f"[{i}/{total}] Fetching {idx_code} for {ym} ({start_date} - {end_date})...")
        
        try:
            w_df = fetcher.fetch_index_weight(
                index_code=idx_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if w_df is not None and not w_df.empty:
                storage.insert_universe_data(w_df, "index_weights")
                fetched_count += 1
                logging.info(f"  -> Got {len(w_df)} records")
            else:
                empty_count += 1
                logging.info(f"  -> Empty (Tushare returned no data for this month)")
                
        except Exception as e:
            error_count += 1
            logging.error(f"  -> Error: {e}")
        
        # Rate limiting: 200 calls/min = 0.3s between calls, use 0.4s for safety
        time.sleep(0.4)
        
        # Progress report every 100 calls
        if i % 100 == 0:
            logging.info(f"Progress: {i}/{total} done. Fetched: {fetched_count}, Empty: {empty_count}, Errors: {error_count}")
    
    logging.info("=" * 60)
    logging.info(f"Re-fetch complete!")
    logging.info(f"  Total attempted: {total}")
    logging.info(f"  Successfully fetched: {fetched_count}")
    logging.info(f"  Empty responses (no data available): {empty_count}")
    logging.info(f"  Errors: {error_count}")
    logging.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-fetch missing index_weight data month by month")
    parser.add_argument("--start-year", type=int, default=2008, help="Start year (default: 2008)")
    parser.add_argument("--end-year", type=int, default=datetime.now().year, help="End year")
    parser.add_argument("--dry-run", action="store_true", help="Only show missing months, don't fetch")
    
    args = parser.parse_args()
    refetch_missing_months(args.start_year, args.end_year, args.dry_run)
