"""A3 — Coverage verification for SW2021 historical membership.

Plan ref: C:\\Users\\henry\\.claude\\plans\\vast-exploring-rabbit.md (v8)

For each audit date, computes the fraction of stocks (with daily price data
on that date) that have a non-null SW2021 L1 classification.

Pre-committed gate decision rules:
  * 2014+ dates: coverage >= 98% required
  * 2008 + 2010: coverage >= 95% required
  * Anything below 95% on a pre-2014 date triggers stop-and-discuss

Audit dates: 2008-01-02, 2010-06-30, 2014-12-31, 2020-06-30, 2024-06-28, 2026-02-27
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

MEMBERS_PATH = (
    PROJECT_ROOT
    / "data"
    / "universe"
    / "industry_sw2021_members"
    / "industry_sw2021_members.parquet"
)
DAILY_DIR = PROJECT_ROOT / "data" / "market" / "daily"

AUDIT_DATES = [
    "2008-01-02",
    "2010-06-30",
    "2014-12-31",
    "2020-06-30",
    "2024-06-28",
    "2026-02-27",
]

GATE_FLOORS = {
    "2008-01-02": 0.95,
    "2010-06-30": 0.95,
    "2014-12-31": 0.98,
    "2020-06-30": 0.98,
    "2024-06-28": 0.98,
    "2026-02-27": 0.98,
}


def _industry_as_of_inline(
    members: pd.DataFrame, ts_code: str, as_of: pd.Timestamp
) -> str | None:
    """Inline lookup for verification — B1 will provide the canonical helper."""
    rows = members[members["ts_code"] == ts_code]
    if rows.empty:
        return None
    # Find the interval covering as_of
    hit = rows[(rows["in_date"] <= as_of) & (rows["out_date"] >= as_of)]
    if hit.empty:
        return None
    # If multiple matches (overlapping windows — shouldn't happen but defensive),
    # take the row with latest in_date
    return str(hit.sort_values("in_date").iloc[-1]["l1_code"])


def _stocks_with_data_on(date: pd.Timestamp) -> set[str]:
    """Load the day's daily parquet and return the set of ts_codes with data."""
    yyyy = date.strftime("%Y")
    yyyymmdd = date.strftime("%Y%m%d")
    path = DAILY_DIR / yyyy / f"daily_{yyyymmdd}.parquet"
    if not path.exists():
        return set()
    df = pd.read_parquet(path, columns=["ts_code"])
    return set(df["ts_code"].unique())


def _classify_basket(
    members: pd.DataFrame, basket: set[str], date: pd.Timestamp
) -> tuple[int, int, list[str]]:
    """Return (classified_count, total_count, top10_unclassified_by_mcap)."""
    if not basket:
        return 0, 0, []

    # Vectorized per-stock interval check (faster than loop)
    sub = members[members["ts_code"].isin(basket)]
    sub_active = sub[(sub["in_date"] <= date) & (sub["out_date"] >= date)]
    classified = set(sub_active["ts_code"].unique())
    unclassified = basket - classified

    # Get top-10 unclassified by total_mv on that day
    yyyy = date.strftime("%Y")
    yyyymmdd = date.strftime("%Y%m%d")
    path = DAILY_DIR / yyyy / f"daily_{yyyymmdd}.parquet"
    daily = pd.read_parquet(path, columns=["ts_code", "total_mv"])
    daily_unc = daily[daily["ts_code"].isin(unclassified)]
    if not daily_unc.empty:
        top10 = (
            daily_unc.dropna(subset=["total_mv"])
            .sort_values("total_mv", ascending=False)
            .head(10)["ts_code"]
            .tolist()
        )
    else:
        top10 = list(unclassified)[:10]

    return len(classified), len(basket), top10


def main() -> int:
    if not MEMBERS_PATH.exists():
        logger.error("Members file missing: %s — run fetch_sw_industry_members.py first", MEMBERS_PATH)
        return 1

    members = pd.read_parquet(MEMBERS_PATH)
    logger.info("Loaded %d membership rows for %d stocks", len(members), members["ts_code"].nunique())

    print()
    print("=" * 80)
    print("SW2021 COVERAGE AUDIT")
    print("=" * 80)
    print(f'{"Date":<14} {"Total":<8} {"Classified":<12} {"Coverage":<10} {"Floor":<8} {"Pass"}')
    print("-" * 80)

    all_pass = True
    for d_str in AUDIT_DATES:
        d = pd.Timestamp(d_str)
        basket = _stocks_with_data_on(d)
        if not basket:
            print(f"{d_str:<14} {'no daily file':<48}")
            all_pass = False
            continue

        classified_n, total_n, top10 = _classify_basket(members, basket, d)
        coverage = classified_n / total_n if total_n else 0
        floor = GATE_FLOORS[d_str]
        passed = coverage >= floor
        all_pass = all_pass and passed
        mark = "PASS" if passed else "FAIL"
        print(
            f"{d_str:<14} {total_n:<8} {classified_n:<12} "
            f"{coverage*100:>6.2f}%   {floor*100:>5.1f}%   {mark}"
        )
        if not passed and top10:
            print(f"  top-10 unclassified by total_mv: {', '.join(top10[:10])}")

    print("=" * 80)
    print(f"OVERALL GATE: {'PASS' if all_pass else 'FAIL'}")
    print("=" * 80)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
