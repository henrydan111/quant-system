# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: none
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: D
"""One-off diagnostic: how complete are Tushare's stk_limit up_limit/down_limit
day bins on stock-days where the stock actually traded?

For each sampled year we load the whole-market $up_limit/$down_limit/$vol via the
engine's own QlibDataFeeder (same execution path the backtester uses), then count
rows where vol > 0 (the stock traded that day) but up_limit or down_limit is NaN.
Those are the genuine coverage gaps that would force a fallback.

Run: venv/Scripts/python.exe workspace/scripts/diag_stk_limit_coverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest_engine.event_driven.data_feeder import QlibDataFeeder

DATA_DIR = str(PROJECT_ROOT / "data")
# Representative years spanning the full provider window (raw cov 2008-2026).
SAMPLE_WINDOWS = [
    ("2014-01-01", "2014-12-31"),
    ("2018-01-01", "2018-12-31"),
    ("2021-01-01", "2021-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2026-01-01", "2026-02-27"),
]
FIELDS = ["$up_limit", "$down_limit", "$vol", "$close", "$pre_close"]


def analyze_window(feeder: QlibDataFeeder, start: str, end: str, stock_codes: set) -> dict:
    feeder._cache_df = None  # reset between windows
    feeder.preload_features("all", FIELDS, start, end, strict=True)
    df = feeder._cache_df
    if df is None or df.empty:
        return {"window": f"{start}..{end}", "rows": 0, "note": "empty"}

    df = df.rename(columns={
        "$up_limit": "up_limit", "$down_limit": "down_limit",
        "$vol": "vol", "$close": "close", "$pre_close": "pre_close",
    })
    # Restrict to ACTUAL tradable stocks (drop index/benchmark instruments,
    # which legitimately carry no price limit).
    inst = df.index.get_level_values("instrument")
    df = df[inst.isin(stock_codes)]
    traded = df[(df["vol"].fillna(0) > 0)]
    n_traded = len(traded)
    up_nan = traded["up_limit"].isna()
    dn_nan = traded["down_limit"].isna()
    either_nan = up_nan | dn_nan
    n_gap = int(either_nan.sum())

    # Classify each gap row by trading-days-since-listing so IPO no-limit
    # windows (main/BSE 1d, ChiNext/STAR 5d) can be separated from genuine
    # mid-life coverage holes.
    ipo_gap = 0
    sample_gaps = []
    nonipo_samples = []
    if n_gap:
        g = traded[either_nan].reset_index()
        for _, r in g.iterrows():
            code = r.get("instrument")
            date = pd.Timestamp(r.get("datetime"))
            ld = feeder._stock_basic.loc[
                feeder._stock_basic["ts_code"] == code, "list_date"
            ]
            days_since = None
            if not ld.empty and pd.notna(ld.iloc[0]):
                try:
                    days_since = feeder.count_trading_days(ld.iloc[0], date)
                except Exception:
                    days_since = None
            is_ipo = days_since is not None and days_since <= 5
            if is_ipo:
                ipo_gap += 1
            rec = {
                "code": code, "date": str(date)[:10],
                "days_since_list": days_since,
                "close": round(float(r["close"]), 2) if pd.notna(r["close"]) else None,
                "pre_close": round(float(r["pre_close"]), 2) if pd.notna(r["pre_close"]) else None,
            }
            if len(sample_gaps) < 5:
                sample_gaps.append(rec)
            if not is_ipo and len(nonipo_samples) < 10:
                nonipo_samples.append(rec)

    return {
        "window": f"{start}..{end}",
        "traded_rows": n_traded,
        "gap_rows": n_gap,
        "gap_pct": round(100.0 * n_gap / n_traded, 4) if n_traded else 0.0,
        "ipo_gap_rows": ipo_gap,
        "nonipo_gap_rows": n_gap - ipo_gap,
        "sample_gaps": sample_gaps,
        "nonipo_samples": nonipo_samples,
    }


def value_sanity(feeder: QlibDataFeeder, start: str, end: str, stock_codes: set) -> dict:
    """Where up_limit/down_limit ARE present, verify the implied band lands on a
    known regulatory tier (±5/10/20/30%) vs raw pre_close. This is the value
    correctness evidence for promoting stk_limit quarantine->approved."""
    feeder._cache_df = None
    feeder.preload_features("all", FIELDS, start, end, strict=True)
    df = feeder._cache_df.rename(columns={
        "$up_limit": "up_limit", "$down_limit": "down_limit",
        "$vol": "vol", "$close": "close", "$pre_close": "pre_close",
    })
    inst = df.index.get_level_values("instrument")
    df = df[inst.isin(stock_codes)]
    ok = df[df["up_limit"].notna() & df["down_limit"].notna()
            & df["pre_close"].notna() & (df["pre_close"] > 0)].copy()
    ok["up_band"] = (ok["up_limit"] / ok["pre_close"] - 1.0).round(2)
    ok["dn_band"] = (1.0 - ok["down_limit"] / ok["pre_close"]).round(2)
    known = [0.05, 0.10, 0.20, 0.30]
    # float32 storage -> compare with tolerance, not exact membership.
    def _near_tier(s):
        import numpy as np
        arr = s.to_numpy(dtype="float64")
        return pd.Series(
            np.any([np.isclose(arr, k, atol=0.005) for k in known], axis=0),
            index=s.index,
        )
    up_known = _near_tier(ok["up_band"])
    dn_known = _near_tier(ok["dn_band"])
    off = ok[~(up_known & dn_known)]
    return {
        "window": f"{start}..{end}",
        "checked": len(ok),
        "up_band_dist": ok["up_band"].value_counts().head(6).to_dict(),
        "off_tier_rows": len(off),
        "off_tier_pct": round(100.0 * len(off) / len(ok), 4) if len(ok) else 0.0,
        "off_samples": [
            {"code": r.instrument, "date": str(r.datetime)[:10],
             "pre_close": round(r.pre_close, 2), "up_limit": round(r.up_limit, 2),
             "up_band": r.up_band, "dn_band": r.dn_band}
            for r in off.reset_index().head(6).itertuples()
        ],
    }


def main() -> None:
    feeder = QlibDataFeeder(DATA_DIR, stage="is_only")
    stock_codes = set(feeder._stock_basic["ts_code"].astype(str))
    print(f"Tradable-stock universe (stock_basic): {len(stock_codes)} codes\n")
    print(f"{'window':<24} {'traded':>11} {'gaps':>8} {'gap%':>9} {'ipo':>7} {'non-ipo':>8}")
    print("-" * 76)
    results = []
    for start, end in SAMPLE_WINDOWS:
        res = analyze_window(feeder, start, end, stock_codes)
        results.append(res)
        print(f"{res['window']:<24} {res.get('traded_rows',0):>11} "
              f"{res.get('gap_rows',0):>8} {res.get('gap_pct',0):>8}% "
              f"{res.get('ipo_gap_rows',0):>7} {res.get('nonipo_gap_rows',0):>8}")

    print("\n=== sample NON-IPO gap rows (real coverage holes; stock traded, "
          "limit NaN, >5 days since listing) ===")
    any_gap = False
    for res in results:
        for g in res.get("nonipo_samples", []):
            any_gap = True
            print(f"  {g}")
    if not any_gap:
        print("  NONE — every non-IPO traded stock-day in the sampled windows "
              "has up_limit/down_limit populated.")

    print("\n=== VALUE SANITY: implied band vs known regulatory tiers "
          "(±5/10/20/30%) ===")
    for start, end in SAMPLE_WINDOWS:
        v = value_sanity(feeder, start, end, stock_codes)
        print(f"  {v['window']}: checked={v['checked']} off_tier={v['off_tier_rows']} "
              f"({v['off_tier_pct']}%)  up_band_dist={v['up_band_dist']}")
        for s in v["off_samples"]:
            print(f"      OFF: {s}")


if __name__ == "__main__":
    main()
