"""Fetch direct quarterly statement data from Tushare VIP endpoints.

Supported datasets:
    - income -> data/fundamentals/income_quarterly/
    - cashflow -> data/fundamentals/cashflow_quarterly/
    - balancesheet -> data/fundamentals/balancesheet_quarterly/

Usage:
    python scripts/fetch_quarterly_statements.py --dataset income
    python scripts/fetch_quarterly_statements.py --dataset income cashflow
    python scripts/fetch_quarterly_statements.py --dataset balancesheet --start-year 2015 --end-year 2026
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

import pandas as pd
from tqdm import tqdm

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from data_infra.fetchers import TushareFetcher
from data_infra.storage import StorageManager


DATASET_CONFIG = {
    "income": {
        "storage_dir": "income_quarterly",
        "fetch_method": "fetch_income_quarterly_vip",
        "file_prefix": "income_q_",
    },
    "cashflow": {
        "storage_dir": "cashflow_quarterly",
        "fetch_method": "fetch_cashflow_quarterly_vip",
        "file_prefix": "cashflow_q_",
    },
    "balancesheet": {
        "storage_dir": "balancesheet_quarterly",
        "fetch_method": "fetch_balancesheet_quarterly_vip",
        "file_prefix": "balancesheet_q_",
    },
}


logger = logging.getLogger("fetch_quarterly_statements")
logger.setLevel(logging.INFO)
log_dir = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(log_dir, exist_ok=True)
handler = RotatingFileHandler(
    os.path.join(log_dir, "fetch_quarterly_statements.log"),
    maxBytes=5_000_000,
    backupCount=3,
)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)
stream = logging.StreamHandler()
stream.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
logger.addHandler(stream)


def generate_periods(start_year: int, end_year: int) -> list[str]:
    """Generate quarter-end periods in YYYYMMDD format."""
    periods: list[str] = []
    for year in range(start_year, end_year + 1):
        for mmdd in ("0331", "0630", "0930", "1231"):
            periods.append(f"{year}{mmdd}")
    return periods


def _write_period_file(
    storage: StorageManager,
    storage_dir: str,
    file_prefix: str,
    period: str,
    df: pd.DataFrame,
    report_types: tuple[str, ...],
) -> None:
    """Write one quarterly-period parquet and append an ingest manifest entry."""
    out_dir = os.path.join(storage.data_root, "fundamentals", storage_dir)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{file_prefix}{period}.parquet")
    df.to_parquet(out_path, index=False)
    storage._record_ingest_manifest(
        storage_dir,
        [out_path],
        len(df),
        source_params={
            "period": period,
            "report_types": list(report_types),
            "source": "tushare_vip_quarterly",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch direct quarterly Tushare statement data via VIP endpoints")
    parser.add_argument(
        "--dataset",
        nargs="+",
        choices=sorted(DATASET_CONFIG),
        default=["income"],
        help="Quarterly statement families to fetch",
    )
    parser.add_argument("--start-year", type=int, default=2008, help="First fiscal year to fetch")
    parser.add_argument("--end-year", type=int, default=datetime.now().year, help="Last fiscal year to fetch")
    parser.add_argument("--config-path", type=str, default=os.path.join(PROJECT_ROOT, "config.yaml"))
    parser.add_argument("--data-root", type=str, default=None, help="Override data root")
    parser.add_argument("--fields", type=str, default=None, help="Optional comma-separated field allowlist")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch periods even if the parquet already exists")
    args = parser.parse_args()

    fetcher = TushareFetcher(config_path=args.config_path, max_retries=5, base_sleep=1.0)
    storage = StorageManager(data_root=args.data_root)
    periods = generate_periods(args.start_year, args.end_year)
    fields = args.fields.replace(" ", "") if args.fields else None
    report_types = ("2", "3")

    for dataset_name in args.dataset:
        config = DATASET_CONFIG[dataset_name]
        fetch_func = getattr(fetcher, config["fetch_method"])
        out_dir = os.path.join(storage.data_root, "fundamentals", config["storage_dir"])
        os.makedirs(out_dir, exist_ok=True)

        fetched = 0
        skipped = 0
        logger.info("Starting %s quarterly VIP fetch (%d periods)", dataset_name, len(periods))
        for period in tqdm(periods, desc=f"{dataset_name} quarterly", unit="period", dynamic_ncols=True):
            out_path = os.path.join(out_dir, f"{config['file_prefix']}{period}.parquet")
            if not args.refresh and os.path.exists(out_path):
                try:
                    existing = pd.read_parquet(out_path)
                    if len(existing) > 0:
                        skipped += 1
                        continue
                except Exception:
                    logger.warning("Existing file unreadable, re-fetching: %s", out_path)

            df = fetch_func(period=period, fields=fields, report_types=report_types)
            if df is None:
                df = pd.DataFrame()
            df = df.dropna(how="all", axis=1) if not df.empty else df
            if df.empty:
                if os.path.exists(out_path):
                    os.remove(out_path)
                logger.info("%s %s: no rows returned, skipped file write", dataset_name, period)
                continue
            _write_period_file(storage, config["storage_dir"], config["file_prefix"], period, df, report_types)
            fetched += 1
            if not df.empty:
                logger.info("%s %s: %d rows", dataset_name, period, len(df))

        logger.info(
            "Completed %s quarterly VIP fetch. fetched=%d skipped=%d total=%d",
            dataset_name,
            fetched,
            skipped,
            len(periods),
        )


if __name__ == "__main__":
    main()
