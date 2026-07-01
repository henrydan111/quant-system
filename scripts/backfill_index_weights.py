"""Backfill monthly index_weight snapshots for one index over a month range.

Why this exists: the original yearly-window ingest (init_fundamentals_data.download_index_weights)
logged-and-skipped per-year fetch errors, which left 000300.SH with a silent 2008-01..2015-12 hole
in data/normalized/universe/index_weights/ (000905.SH is complete over the same span). The
index_weight doc (Tushare数据接口/content/96_指数成分和权重.md) recommends month-granularity
requests (start=month first day, end=month last day), which this script follows.

Vendor quirk (verified 2026-06-11): the SSE code ``000300.SH`` returns EMPTY for all
months before ~2016; the SZSE mirror code ``399300.SZ`` serves the same index back to
2008-01 (member sets and weights verified identical on 2024-01-31) with DAILY snapshots
pre-2016. Use ``--index 399300.SZ --relabel-as 000300.SH`` so storage keys stay on the
canonical code used by INDEX_UNIVERSE_MAP and the universe loaders.

Usage:
    venv/Scripts/python.exe scripts/backfill_index_weights.py --index 399300.SZ \
        --relabel-as 000300.SH --start 200801 --end 201512 [--dry-run]

Sequential single fetcher (never parallel against Tushare Pro), all calls through
TushareFetcher._safe_api_call via fetch_index_weight. insert_universe_data merges
per-month with drop_duplicates, so re-runs are idempotent.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_infra.fetchers import TushareFetcher  # noqa: E402
from data_infra.storage import StorageManager  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_index_weights")


def month_range(start: str, end: str) -> list[pd.Period]:
    return list(pd.period_range(pd.Period(start, freq="M"), pd.Period(end, freq="M"), freq="M"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, help="index code to FETCH, e.g. 399300.SZ")
    ap.add_argument("--relabel-as", default=None,
                    help="canonical index_code to STORE under (mirror-code fetches)")
    ap.add_argument("--start", required=True, help="first month YYYYMM")
    ap.add_argument("--end", required=True, help="last month YYYYMM")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    months = month_range(args.start, args.end)
    out_dir = PROJECT_ROOT / "data" / "normalized" / "universe" / "index_weights"
    targets = [out_dir / f"index_weights_{m.strftime('%Y%m')}.parquet" for m in months]
    logger.info("Will touch %d monthly files under %s (merge+dedup, idempotent)", len(targets), out_dir)
    logger.info("First/last targets: %s .. %s", targets[0].name, targets[-1].name)

    if args.dry_run:
        logger.info("[DRY-RUN] %d monthly fetches for %s, no writes.", len(months), args.index)
        return 0

    fetcher = TushareFetcher()
    storage = StorageManager()
    fetched_rows = 0
    empty_months: list[str] = []
    for i, m in enumerate(months, 1):
        start_d = m.start_time.strftime("%Y%m%d")
        end_d = m.end_time.strftime("%Y%m%d")
        df = fetcher.fetch_index_weight(index_code=args.index, start_date=start_d, end_date=end_d)
        if df is None or df.empty:
            empty_months.append(m.strftime("%Y%m"))
            logger.warning("%s %s: EMPTY response", args.index, m.strftime("%Y%m"))
            continue
        if args.relabel_as:
            df = df.assign(index_code=args.relabel_as)
        storage.insert_universe_data(df, "index_weights")
        fetched_rows += len(df)
        logger.info("[%d/%d] %s %s: %d rows", i, len(months), args.index, m.strftime("%Y%m"), len(df))

    logger.info("Done: %d rows across %d months; %d empty months: %s",
                fetched_rows, len(months), len(empty_months), empty_months or "none")
    return 1 if len(empty_months) == len(months) else 0


if __name__ == "__main__":
    raise SystemExit(main())
