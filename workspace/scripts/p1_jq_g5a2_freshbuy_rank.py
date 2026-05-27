# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Sandbox / one-shot diagnostic script. NOT a formal research
#   surface. Bare D.features calls inside this file are tolerated
#   per scripts/lint_no_bare_qlib_features.py allowlist semantics
#   (PR 6) but the script's output is not eligible for the formal
#   release gate.
# ──────────────────────────────────────────────────────────────────────
"""Cleaner selection-metric test: rank JQ's FRESH BUYS (action=open) against the
AVAILABLE pool (eligible universe minus already-held) by our Tushare total_mv.

This controls for the held-winner-drift confound. JoinQuant only buys empty slots
with the smallest market_cap among NOT-already-held names. If our total_mv ranks
those same fresh buys at the top of the available pool, the metrics agree; if the
fresh buys rank deep in the available pool, the metrics differ.

Uses calm Tuesdays to avoid limit-down distortion of the candidate set."""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))
import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

jq_tr = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv", parse_dates=["time"])
jq_tr["date"] = jq_tr["time"].dt.normalize()
jq_tr["ts_code"] = jq_tr["security"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")
jq_pos = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_positions.csv", parse_dates=["time"])
jq_pos["date"] = jq_pos["time"].dt.normalize()
jq_pos["ts_code"] = jq_pos["security"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")

jq_pit = pd.read_csv(P / "Knowledge/zxz_399101_pit_membership_tuesdays.csv")
jq_pit["date"] = pd.to_datetime(jq_pit["date"]).dt.normalize()
jq_pit["ts_code"] = jq_pit["ts_code"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")

sb = pd.read_parquet(P / "data/reference/stock_basic.parquet")
sb["list_date"] = pd.to_datetime(sb["list_date"], format="%Y%m%d", errors="coerce")
sb["delist_date"] = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")

def nearest_tue(d):
    tu = sorted(jq_pit["date"].unique()); valid = [t for t in tu if t <= d]
    return valid[-1] if valid else tu[0]
def prev_trade(d):
    return jq_pos[jq_pos["date"] < d]["date"].max()

calm_dates = ["2017-03-07", "2017-09-12", "2019-05-14", "2021-03-09", "2021-10-12", "2023-05-09", "2025-03-11"]

print("Fresh-buy rank test: JQ's new buys ranked within the AVAILABLE pool (excl. held) by our total_mv")
print("(fresh buys clustering at top of available pool → metrics agree)")
print()
all_pct = []
for ds in calm_dates:
    d = pd.Timestamp(ds)
    fresh = set(jq_tr[(jq_tr["date"] == d) & (jq_tr["action"] == "open")]["ts_code"])
    if not fresh:
        continue
    pd_ = prev_trade(d)
    held_prev = set(jq_pos[jq_pos["date"] == pd_]["ts_code"]) if pd_ is not None else set()
    uni = set(jq_pit[jq_pit["date"] == nearest_tue(d)]["ts_code"])
    list_cutoff = d - pd.Timedelta(days=375)
    elig = sb[(sb["ts_code"].isin(uni)) & (sb["list_date"] <= list_cutoff)
              & ((sb["delist_date"].isna()) | (sb["delist_date"] > d))]
    avail = set(elig["ts_code"]) - held_prev   # available pool (not already held)
    avail_codes = sorted(c.replace(".", "_") for c in avail)
    df = D.features(avail_codes, ["Ref($total_mv, 1)"], start_time=ds, end_time=ds, freq="day")
    df.columns = ["mv"]; df = df.reset_index().dropna(subset=["mv"])
    df["ts_code"] = df["instrument"].str.replace("_", ".")
    df = df.sort_values("mv").reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    n_avail = len(df)
    rmap = dict(zip(df["ts_code"], df["rank"]))
    fresh_ranks = sorted([rmap.get(c, -1) for c in fresh if rmap.get(c, -1) > 0])
    pct = [r / n_avail * 100 for r in fresh_ranks]   # percentile within available pool
    print(f"{ds}: {len(fresh)} fresh buys; avail pool={n_avail}; ranks={fresh_ranks}")
    print(f"          percentiles within available pool: {[f'{p:.0f}%' for p in pct]}")
    all_pct.extend(pct)

print()
print("=" * 70)
if all_pct:
    arr = np.array(all_pct)
    print(f"Aggregate fresh-buy percentile within available pool: median={np.median(arr):.1f}%")
    print(f"  in top-2% of pool: {(arr<=2).mean()*100:.0f}%")
    print(f"  in top-5% of pool: {(arr<=5).mean()*100:.0f}%")
    print(f"  in top-10% of pool: {(arr<=10).mean()*100:.0f}%")
    print()
    print("INTERPRETATION (available pool ~600-900 stocks; top-12 ≈ top 1.5-2%):")
    if (arr <= 3).mean() > 0.7:
        print("  Fresh buys cluster in the smallest ~2-3% by our total_mv → metrics AGREE.")
    else:
        print("  Fresh buys are NOT consistently the smallest by our total_mv → metrics DIFFER")
        print("  (Tushare total_mv ranks differently from JoinQuant valuation.market_cap).")
