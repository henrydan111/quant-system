"""New Alpha Endpoints Historical Bootstrap.

One-time fetch of 5 high-alpha-potential Tushare endpoints into the local
Parquet cache. Idempotent per-year: skips years that already have files
unless ``--force`` is passed. Respects ``base_sleep=1.5`` per CLAUDE.md.

Endpoints wired:
  1. top_list      (per-date)  -> data/market/top_list/YYYY/top_list_YYYYMMDD.parquet
  2. top_inst      (per-date)  -> data/market/top_inst/YYYY/top_inst_YYYYMMDD.parquet
  3. block_trade   (per-date)  -> data/market/block_trade/YYYY/block_trade_YYYYMMDD.parquet
  4. stk_holdertrade (per-stock) -> data/corporate/stk_holdertrade/stk_holdertrade_YYYY.parquet
  5. cyq_perf      (per-stock) -> data/market/cyq_perf/YYYY/cyq_perf_YYYYMMDD.parquet

Usage:
    # Full bootstrap (all 5, all years — takes many hours)
    venv/Scripts/python.exe scripts/fetch_new_alpha_endpoints.py

    # Single endpoint, single year
    venv/Scripts/python.exe scripts/fetch_new_alpha_endpoints.py --endpoints top_list --years 2024

    # Smoke test on 50 stocks for cyq_perf
    venv/Scripts/python.exe scripts/fetch_new_alpha_endpoints.py --endpoints cyq_perf --sample-stocks 50

    # Force refetch existing years
    venv/Scripts/python.exe scripts/fetch_new_alpha_endpoints.py --force

See CLAUDE.md section 6.2 for the pipeline entry points list.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_infra.fetchers import TushareFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

TRADE_CAL_PATH = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
STOCK_BASIC_PATH = PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet"
DATA_ROOT = PROJECT_ROOT / "data"

PER_DATE_ENDPOINTS = ["top_list", "top_inst", "block_trade"]
PER_STOCK_ENDPOINTS = ["stk_holdertrade", "cyq_perf"]
ALL_ENDPOINTS = PER_DATE_ENDPOINTS + PER_STOCK_ENDPOINTS


def _load_open_dates() -> list[str]:
    cal = pd.read_parquet(TRADE_CAL_PATH)
    cal = cal[cal["is_open"] == 1]
    return sorted(pd.to_datetime(cal["cal_date"], format="%Y%m%d").dt.strftime("%Y%m%d").tolist())


def _load_stock_codes() -> list[str]:
    sb = pd.read_parquet(STOCK_BASIC_PATH)
    return sorted(sb["ts_code"].dropna().astype(str).tolist())


def _year_dates(open_dates: list[str], year: int) -> list[str]:
    return [d for d in open_dates if d.startswith(str(year))]


def _per_date_year_dir(endpoint: str, year: int) -> Path:
    return DATA_ROOT / "market" / endpoint / str(year)


def _per_date_file(endpoint: str, date_str: str) -> Path:
    year = date_str[:4]
    return DATA_ROOT / "market" / endpoint / year / f"{endpoint}_{date_str}.parquet"


def _fetch_per_date_endpoint(
    fetcher: TushareFetcher,
    endpoint: str,
    years: list[int],
    open_dates: list[str],
    force: bool,
) -> None:
    fetch_func = getattr(fetcher, f"fetch_{endpoint}")
    for year in years:
        year_dir = _per_date_year_dir(endpoint, year)
        dates = _year_dates(open_dates, year)
        if not dates:
            logger.info("  %s/%d: no trading days", endpoint, year)
            continue

        existing = set()
        if year_dir.exists():
            existing = {f.stem.split("_")[-1] for f in year_dir.glob("*.parquet")}

        if not force and len(existing) >= len(dates):
            logger.info("  %s/%d: already complete (%d files)", endpoint, year, len(existing))
            continue

        year_dir.mkdir(parents=True, exist_ok=True)
        fetched = 0
        for i, date_str in enumerate(dates):
            if not force and date_str in existing:
                continue
            if i % 50 == 0:
                logger.info("  %s/%d: %d/%d (%d fetched)", endpoint, year, i, len(dates), fetched)
            try:
                df = fetch_func(trade_date=date_str)
                if df is not None and not df.empty:
                    out_path = _per_date_file(endpoint, date_str)
                    df.to_parquet(out_path, index=False)
                    fetched += 1
            except Exception as e:
                logger.warning("  %s/%s: %s", endpoint, date_str, e)
        logger.info("  %s/%d: done (%d files written)", endpoint, year, fetched)


def _fetch_stk_holdertrade(
    fetcher: TushareFetcher,
    years: list[int],
    stock_codes: list[str],
    force: bool,
) -> None:
    out_dir = DATA_ROOT / "corporate" / "stk_holdertrade"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_frames: list[pd.DataFrame] = []
    for i, ts_code in enumerate(stock_codes):
        if i % 200 == 0:
            logger.info("  stk_holdertrade: stock %d/%d (%s)", i, len(stock_codes), ts_code)
        try:
            df = fetcher.fetch_stk_holdertrade(ts_code=ts_code)
            if df is not None and not df.empty:
                all_frames.append(df)
        except Exception as e:
            logger.warning("  stk_holdertrade/%s: %s", ts_code, e)

    if not all_frames:
        logger.info("  stk_holdertrade: no data returned")
        return

    combined = pd.concat(all_frames, ignore_index=True)
    combined["ann_date"] = pd.to_datetime(combined["ann_date"], format="%Y%m%d", errors="coerce")

    for year in years:
        mask = combined["ann_date"].dt.year == year
        year_df = combined[mask]
        if year_df.empty:
            continue
        out_path = out_dir / f"stk_holdertrade_{year}.parquet"
        if out_path.exists() and not force:
            logger.info("  stk_holdertrade/%d: already exists, skipping", year)
            continue
        year_df.to_parquet(out_path, index=False)
        logger.info("  stk_holdertrade/%d: %d rows", year, len(year_df))


def _fetch_cyq_perf(
    fetcher: TushareFetcher,
    years: list[int],
    stock_codes: list[str],
    force: bool,
) -> None:
    # cyq_perf requires per-stock iteration but produces per-date data.
    # Strategy: fetch per stock, accumulate all rows, then partition into
    # per-date files under data/market/cyq_perf/YYYY/.
    all_frames: list[pd.DataFrame] = []
    for i, ts_code in enumerate(stock_codes):
        if i % 100 == 0:
            logger.info("  cyq_perf: stock %d/%d (%s)", i, len(stock_codes), ts_code)
        try:
            df = fetcher.fetch_cyq_perf(ts_code=ts_code)
            if df is not None and not df.empty:
                all_frames.append(df)
        except Exception as e:
            logger.warning("  cyq_perf/%s: %s", ts_code, e)

    if not all_frames:
        logger.info("  cyq_perf: no data returned")
        return

    combined = pd.concat(all_frames, ignore_index=True)
    combined["trade_date_str"] = pd.to_datetime(
        combined["trade_date"], format="%Y%m%d", errors="coerce"
    ).dt.strftime("%Y%m%d")

    for year in years:
        year_mask = combined["trade_date_str"].str.startswith(str(year))
        year_df = combined[year_mask]
        if year_df.empty:
            continue

        year_dir = DATA_ROOT / "market" / "cyq_perf" / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)

        for date_str, day_df in year_df.groupby("trade_date_str"):
            out_path = year_dir / f"cyq_perf_{date_str}.parquet"
            if out_path.exists() and not force:
                continue
            day_df.drop(columns=["trade_date_str"], errors="ignore").to_parquet(
                out_path, index=False
            )
        logger.info("  cyq_perf/%d: %d dates, %d rows", year, year_df["trade_date_str"].nunique(), len(year_df))


def main() -> int:
    parser = argparse.ArgumentParser(description="New alpha endpoints historical bootstrap")
    parser.add_argument("--endpoints", type=str, default=",".join(ALL_ENDPOINTS),
                        help=f"Comma-separated endpoints (default: all)")
    parser.add_argument("--years", type=str, default=None,
                        help="Comma-separated years (default: 2008-2026)")
    parser.add_argument("--force", action="store_true",
                        help="Refetch years that already exist")
    parser.add_argument("--sample-stocks", type=int, default=None,
                        help="Limit stock iteration to N stocks (for smoke testing)")
    parser.add_argument("--config-path", default=str(PROJECT_ROOT / "config.yaml"))
    args = parser.parse_args()

    endpoints = [e.strip() for e in args.endpoints.split(",") if e.strip()]
    open_dates = _load_open_dates()
    stock_codes = _load_stock_codes()
    if args.sample_stocks:
        stock_codes = stock_codes[:args.sample_stocks]
        logger.info("Sampling %d stocks (--sample-stocks)", args.sample_stocks)

    first_year = int(open_dates[0][:4])
    last_year = int(open_dates[-1][:4])
    if args.years:
        years = [int(y.strip()) for y in args.years.split(",")]
    else:
        years = list(range(first_year, last_year + 1))

    fetcher = TushareFetcher(config_path=args.config_path, base_sleep=1.5, max_retries=5)
    logger.info("Endpoints: %s, Years: %s, Stocks: %d", endpoints, years, len(stock_codes))

    for endpoint in endpoints:
        logger.info("=== %s ===", endpoint)
        if endpoint in PER_DATE_ENDPOINTS:
            _fetch_per_date_endpoint(fetcher, endpoint, years, open_dates, args.force)
        elif endpoint == "stk_holdertrade":
            _fetch_stk_holdertrade(fetcher, years, stock_codes, args.force)
        elif endpoint == "cyq_perf":
            _fetch_cyq_perf(fetcher, years, stock_codes, args.force)
        else:
            logger.warning("Unknown endpoint: %s", endpoint)

    logger.info("Bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
