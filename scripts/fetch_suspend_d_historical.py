"""P1-1: One-time historical bootstrap of Tushare ``suspend_d`` (停复牌).

Context
=======

The backtester's ``exchange.is_suspended()`` currently uses the proxy
``vol == 0`` to detect suspensions. This misses:
  * Half-day suspensions where the stock resumes trading partway through
  * Name-change / ticker-change halts where volume is non-zero on
    adjacent days but the stock is authoritatively suspended
  * Pre-listing quiet periods where raw data is absent rather than zero

Tushare's ``suspend_d`` endpoint is the authoritative source. This
script does a one-time historical fetch of every trading day in the
local trade calendar and stores the result as year-partitioned parquet
files under ``data/market/suspension/``. A consolidated
``suspension_ranges.parquet`` keyed by ``ts_code`` with (start, end) is
then built for fast range-lookup by ``provider_metadata.is_suspended``.

This script is idempotent: it skips any year that already has a populated
parquet file unless ``--force`` is passed. Respects ``base_sleep=1.5``
per CLAUDE.md §6.1.

Usage
=====

    # One-time full backfill (takes several hours; progress is logged)
    E:/量化系统/venv/Scripts/python.exe scripts/fetch_suspend_d_historical.py

    # Force refetch a specific year (used to recover a corrupt year)
    E:/量化系统/venv/Scripts/python.exe scripts/fetch_suspend_d_historical.py --force --years 2024

    # Rebuild the consolidated range file from existing per-day partitions
    E:/量化系统/venv/Scripts/python.exe scripts/fetch_suspend_d_historical.py --ranges-only

See CLAUDE.md §6 "Data Operations" and ``project_state.md`` remediation
milestone for the audit context.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_infra.fetchers import TushareFetcher  # noqa: E402
from data_infra.storage import StorageManager  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SUSPENSION_DIR = PROJECT_ROOT / "data" / "market" / "suspension"
RANGES_FILE = SUSPENSION_DIR / "suspension_ranges.parquet"
TRADE_CAL_PATH = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"


def _load_trade_calendar() -> list[str]:
    """Return sorted list of open-day strings YYYYMMDD from the trade calendar."""
    cal = pd.read_parquet(TRADE_CAL_PATH)
    cal = cal[cal["is_open"] == 1]
    dates = pd.to_datetime(cal["cal_date"], format="%Y%m%d").sort_values()
    return dates.dt.strftime("%Y%m%d").tolist()


def _year_path(year: int) -> Path:
    return SUSPENSION_DIR / f"suspension_{year}.parquet"


def _fetch_year(
    fetcher: TushareFetcher,
    year: int,
    open_days: list[str],
) -> pd.DataFrame:
    """Fetch suspend_d for every open day in ``year`` and concat."""
    year_days = [d for d in open_days if d.startswith(str(year))]
    if not year_days:
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for i, day in enumerate(year_days):
        if i % 10 == 0:
            logger.info("  Year %d: fetching %s (%d/%d)", year, day, i + 1, len(year_days))
        df = fetcher.fetch_suspend_d(trade_date=day)
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _build_ranges(suspension_dir: Path) -> pd.DataFrame:
    """Consolidate year partitions into a per-symbol (start, end, reason) table."""
    files = sorted(suspension_dir.glob("suspension_*.parquet"))
    frames: list[pd.DataFrame] = []
    for f in files:
        df = pd.read_parquet(f)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["ts_code", "suspend_start", "suspend_end", "suspend_reason"])

    all_rows = pd.concat(frames, ignore_index=True)
    all_rows = all_rows.dropna(subset=["ts_code", "suspend_timing"])
    all_rows["trade_date"] = pd.to_datetime(all_rows["trade_date"], format="%Y%m%d", errors="coerce")
    all_rows = all_rows.dropna(subset=["trade_date"]).sort_values(["ts_code", "trade_date"])

    # Contract contiguous dates per ts_code into (start, end) ranges
    ranges: list[dict] = []
    for ts_code, group in all_rows.groupby("ts_code"):
        group = group.sort_values("trade_date").reset_index(drop=True)
        current_start: pd.Timestamp | None = None
        current_end: pd.Timestamp | None = None
        current_reason: str | None = None
        prior_date: pd.Timestamp | None = None
        for _, row in group.iterrows():
            d = row["trade_date"]
            reason = row.get("suspend_timing", "")
            if current_start is None:
                current_start = d
                current_end = d
                current_reason = reason
            elif prior_date is not None and (d - prior_date).days <= 7:
                current_end = d
            else:
                ranges.append(
                    {
                        "ts_code": ts_code,
                        "suspend_start": current_start,
                        "suspend_end": current_end,
                        "suspend_reason": current_reason,
                    }
                )
                current_start = d
                current_end = d
                current_reason = reason
            prior_date = d
        if current_start is not None:
            ranges.append(
                {
                    "ts_code": ts_code,
                    "suspend_start": current_start,
                    "suspend_end": current_end,
                    "suspend_reason": current_reason,
                }
            )
    return pd.DataFrame(ranges)


def main() -> int:
    parser = argparse.ArgumentParser(description="Historical suspend_d bootstrap (P1-1)")
    parser.add_argument("--years", type=str, default=None, help="Comma-separated years to fetch (default: all)")
    parser.add_argument("--force", action="store_true", help="Refetch years that already exist")
    parser.add_argument("--ranges-only", action="store_true", help="Skip fetch; just rebuild suspension_ranges.parquet")
    parser.add_argument("--config-path", default=str(PROJECT_ROOT / "config.yaml"))
    args = parser.parse_args()

    SUSPENSION_DIR.mkdir(parents=True, exist_ok=True)

    if args.ranges_only:
        logger.info("Rebuilding suspension_ranges.parquet from existing partitions...")
        ranges = _build_ranges(SUSPENSION_DIR)
        ranges.to_parquet(RANGES_FILE, index=False)
        logger.info("Wrote %d range rows to %s", len(ranges), RANGES_FILE)
        return 0

    open_days = _load_trade_calendar()
    if not open_days:
        logger.error("Trade calendar has no open days — aborting")
        return 2

    first_year = int(open_days[0][:4])
    last_year = int(open_days[-1][:4])
    all_years = list(range(first_year, last_year + 1))

    if args.years:
        requested = [int(y.strip()) for y in args.years.split(",") if y.strip()]
        years_to_fetch = [y for y in all_years if y in requested]
    else:
        years_to_fetch = all_years

    logger.info(
        "Will process years %s (calendar range %d..%d)",
        years_to_fetch,
        first_year,
        last_year,
    )

    fetcher = TushareFetcher(config_path=args.config_path, base_sleep=1.5, max_retries=5)

    for year in years_to_fetch:
        target = _year_path(year)
        if target.exists() and not args.force:
            logger.info("Skipping %d: already exists at %s (use --force to refetch)", year, target)
            continue
        logger.info("Fetching suspend_d for %d...", year)
        df = _fetch_year(fetcher, year, open_days)
        if df.empty:
            logger.info("  %d: no suspensions found", year)
            # Still write an empty sentinel so we don't re-query
            pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing"]).to_parquet(
                target, index=False
            )
        else:
            df.to_parquet(target, index=False)
            logger.info("  %d: wrote %d rows to %s", year, len(df), target)

    # Rebuild consolidated range file after any fetches
    logger.info("Rebuilding suspension_ranges.parquet...")
    ranges = _build_ranges(SUSPENSION_DIR)
    ranges.to_parquet(RANGES_FILE, index=False)
    logger.info("Wrote %d range rows to %s", len(ranges), RANGES_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
