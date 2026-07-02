"""券商月度金股 (broker_recommend, doc_id=267) historical bootstrap.

One-time idempotent fetch of the broker monthly golden-stock lists into the
local Parquet cache, per-month. Skips months that already have a file unless
``--force``. Strictly sequential, ``base_sleep>=1.5`` per CLAUDE.md §6.1.

Storage:
    data/analyst/broker_recommend/broker_recommend_{YYYYMM}.parquet
    raw columns: [month, broker, ts_code, name]

PIT / coverage notes (see data_dictionary.md and the fetcher docstring):
    - `month` is the RECOMMENDATION month, NOT a visible-at timestamp. Tushare
      populates month M within its first 1-3 days, so downstream visibility must
      be anchored on the first trading day on/after ~day 4 of month M.
    - History effectively starts 2020-07; earlier months return empty.
    - Broker coverage is unstable (~10-44 brokers/month) → conviction is
      comparable only cross-sectionally within a month.

Usage:
    # Dry run — list months that would be fetched, no API calls, no writes
    venv/Scripts/python.exe scripts/fetch_broker_recommend_historical.py --dry-run

    # Full backfill (2020-07 .. current month)
    venv/Scripts/python.exe scripts/fetch_broker_recommend_historical.py

    # Explicit window / refetch
    venv/Scripts/python.exe scripts/fetch_broker_recommend_historical.py --start-month 202007 --end-month 202606 --force
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_infra.fetchers import TushareFetcher  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fetch_broker_recommend")

OUT_DIR = PROJECT_ROOT / "data" / "analyst" / "broker_recommend"
DEFAULT_START = "202007"  # earliest non-empty month (verified by coverage probe)
RAW_COLUMNS = ["month", "broker", "ts_code", "name"]


def _enumerate_months(start_month: str, end_month: str) -> list[str]:
    """Inclusive YYYYMM range."""
    start = datetime.strptime(start_month, "%Y%m")
    end = datetime.strptime(end_month, "%Y%m")
    months: list[str] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _month_file(month: str) -> Path:
    return OUT_DIR / f"broker_recommend_{month}.parquet"


def main() -> int:
    parser = argparse.ArgumentParser(description="broker_recommend historical bootstrap")
    parser.add_argument("--start-month", default=DEFAULT_START, help="YYYYMM (default 202007)")
    parser.add_argument("--end-month", default=None, help="YYYYMM (default: current month)")
    parser.add_argument("--force", action="store_true", help="Refetch months that already exist")
    parser.add_argument("--dry-run", action="store_true", help="List months to fetch; no API calls, no writes")
    parser.add_argument("--config-path", default=str(PROJECT_ROOT / "config.yaml"))
    args = parser.parse_args()

    end_month = args.end_month or datetime.now().strftime("%Y%m")
    months = _enumerate_months(args.start_month, end_month)

    existing = {f.stem.split("_")[-1] for f in OUT_DIR.glob("*.parquet")} if OUT_DIR.exists() else set()
    todo = [m for m in months if args.force or m not in existing]
    skip = [m for m in months if m in existing and not args.force]

    logger.info("Window: %s .. %s (%d months)", args.start_month, end_month, len(months))
    logger.info("Output dir: %s", OUT_DIR)
    logger.info("Already present: %d | To fetch: %d", len(skip), len(todo))

    if args.dry_run:
        print("\n===== DRY RUN — broker_recommend backfill =====")
        print(f"output dir : {OUT_DIR}")
        print(f"window     : {args.start_month} .. {end_month}  ({len(months)} months)")
        print(f"would skip : {len(skip)} existing")
        print(f"would fetch: {len(todo)} months -> {len(todo)} parquet files")
        if todo:
            print(f"  first: broker_recommend_{todo[0]}.parquet")
            print(f"  last : broker_recommend_{todo[-1]}.parquet")
        print("\nNo API calls made, no files written.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fetcher = TushareFetcher(config_path=args.config_path, base_sleep=1.5, max_retries=5)

    fetched, empty, failed = 0, 0, 0
    for i, month in enumerate(todo):
        if i % 12 == 0:
            logger.info("  progress: %d/%d (%d fetched, %d empty, %d failed)",
                        i, len(todo), fetched, empty, failed)
        try:
            df = fetcher.fetch_broker_recommend(month=month)
        except Exception as e:
            logger.warning("  %s: FAILED %s", month, e)
            failed += 1
            continue

        if df is None or df.empty:
            logger.info("  %s: empty", month)
            empty += 1
            continue

        # Keep raw faithful to source schema; guard against column drift.
        missing = [c for c in RAW_COLUMNS if c not in df.columns]
        if missing:
            logger.warning("  %s: missing expected columns %s (got %s)", month, missing, list(df.columns))
        df.to_parquet(_month_file(month), index=False)
        fetched += 1

    logger.info("Done. fetched=%d empty=%d failed=%d (window %s..%s)",
                fetched, empty, failed, args.start_month, end_month)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
