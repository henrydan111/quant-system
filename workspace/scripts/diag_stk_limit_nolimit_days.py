# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: none
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: D
"""What does Tushare's stk_limit field look like on legitimately-no-limit days?

Regimes inspected on the FIRST trading days after listing:
  - Main board (60xxxx/00xxxx): TWO regimes —
      * post-2023 全面注册制 (registration system): first 5 days NO limit (sentinel)
      * pre-2023: listing day had a +44% / -36% (ASYMMETRIC) special limit
  - ChiNext (300/301) post-2020-08-24: first 5 days genuinely NO limit
  - STAR (688/689): first 5 days genuinely NO limit
  - BSE (8xxxxx): listing day no limit

For each sampled IPO we print the first ~7 trading days: pre_close, close,
implied move, and Tushare up_limit/down_limit (NaN = endpoint published no row).

Run: venv/Scripts/python.exe workspace/scripts/diag_stk_limit_nolimit_days.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest_engine.event_driven.data_feeder import QlibDataFeeder

DATA_DIR = str(PROJECT_ROOT / "data")


def first_days(feeder, code: str, n: int = 7) -> pd.DataFrame:
    sb = feeder._stock_basic
    row = sb[sb["ts_code"] == code]
    if row.empty or pd.isna(row.iloc[0]["list_date"]):
        return pd.DataFrame()
    ld = pd.Timestamp(row.iloc[0]["list_date"])
    end = ld + pd.Timedelta(days=40)
    df = feeder.get_features(
        [code], ["$up_limit", "$down_limit", "$close", "$pre_close", "$vol"],
        ld, end,
    )
    if df.empty:
        return pd.DataFrame()
    df = df.rename(columns={
        "$up_limit": "up_limit", "$down_limit": "down_limit",
        "$close": "close", "$pre_close": "pre_close", "$vol": "vol",
    }).reset_index()
    df = df[df["vol"].fillna(0) > 0].head(n)
    return df


def show(feeder, label: str, code: str) -> None:
    df = first_days(feeder, code)
    print(f"\n── {label}: {code} ──")
    if df.empty:
        print("   (no data)")
        return
    print(f"   {'date':<12}{'pre_close':>10}{'close':>9}{'move%':>8}"
          f"{'up_limit':>10}{'down_limit':>11}")
    for _, r in df.iterrows():
        d = str(r["datetime"])[:10]
        pc = r["pre_close"]; cl = r["close"]
        mv = (cl / pc - 1) * 100 if pd.notna(pc) and pc else float("nan")
        ul = "NaN" if pd.isna(r["up_limit"]) else f"{r['up_limit']:.2f}"
        dl = "NaN" if pd.isna(r["down_limit"]) else f"{r['down_limit']:.2f}"
        print(f"   {d:<12}{pc:>10.2f}{cl:>9.2f}{mv:>7.1f}%{ul:>10}{dl:>11}")
    # Implied band on present rows
    present = df[df["up_limit"].notna() & (df["pre_close"] > 0)]
    if len(present):
        bands = (present["up_limit"] / present["pre_close"] - 1).round(3).tolist()
        print(f"   implied up-bands (present rows): {bands}")


def find_ipos(feeder, prefixes, list_year: str, k: int = 2) -> list[str]:
    sb = feeder._stock_basic.copy()
    sb = sb[sb["list_date"].notna()]
    sb = sb[sb["list_date"].dt.year == int(list_year)]
    out = []
    for p in prefixes:
        cand = sb[sb["ts_code"].astype(str).str[:len(p)] == p].sort_values("list_date")
        out += cand["ts_code"].astype(str).head(k).tolist()
    return out


def main() -> None:
    feeder = QlibDataFeeder(DATA_DIR, stage="is_only")
    # Use 2024 listings (provider coverage perfect that year).
    print("Sampling 2024 IPOs across boards (coverage perfect in 2024).")
    main_board = find_ipos(feeder, ["60", "00"], "2024", k=1)
    chinext = find_ipos(feeder, ["300", "301"], "2024", k=2)
    star = find_ipos(feeder, ["688"], "2024", k=2)
    bse = find_ipos(feeder, ["83", "92", "87"], "2024", k=2)

    for c in main_board:
        show(feeder, "MAIN BOARD (post-2023: first 5 days NO limit; pre-2023 was +44%/-36%)", c)
    for c in chinext:
        show(feeder, "CHINEXT (first 5 days NO limit)", c)
    for c in star:
        show(feeder, "STAR (first 5 days NO limit)", c)
    for c in bse:
        show(feeder, "BSE (listing day no limit)", c)

    # Index (true no-limit instrument) for contrast.
    print("\n── INDEX (true no-limit instrument) ──")
    df = feeder.get_features(["000300.SH"], ["$up_limit", "$down_limit", "$close"],
                             pd.Timestamp("2024-03-01"), pd.Timestamp("2024-03-05"))
    if not df.empty:
        df = df.rename(columns={"$up_limit": "up_limit", "$down_limit": "down_limit",
                                "$close": "close"}).reset_index()
        for _, r in df.iterrows():
            ul = "NaN" if pd.isna(r["up_limit"]) else f"{r['up_limit']:.2f}"
            print(f"   {str(r['datetime'])[:10]}  close={r['close']:.2f}  up_limit={ul}")


if __name__ == "__main__":
    main()
