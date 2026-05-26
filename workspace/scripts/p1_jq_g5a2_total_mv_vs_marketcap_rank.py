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
"""Decisive LOCAL test of the selection-difference hypothesis (no new JQ data needed).

JoinQuant ranks the 中小综 universe by valuation.market_cap.asc() and holds the
smallest ~12. If JQ's valuation.market_cap == our Tushare total_mv, then JQ's
actual holdings should rank 1-15 by OUR total_mv on calm days (no limit-locks
to perturb selection).

For several CALM Tuesdays (avoid 股灾 limit-down distortion), take JQ's actual
holdings (positions.csv) and compute each holding's rank by our Ref($total_mv,1)
within the same eligible universe. Scattered ranks (e.g. 1-50) ⟹ the two cap
metrics differ ⟹ selection is a real data-vendor difference."""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))
import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

# JQ original positions (reflect JQ market_cap selection)
jq_pos = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_positions.csv", parse_dates=["time"])
jq_pos["date"] = jq_pos["time"].dt.normalize()
jq_pos["ts_code"] = jq_pos["security"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")

# JQ PIT universe
jq_pit = pd.read_csv(P / "Knowledge/zxz_399101_pit_membership_tuesdays.csv")
jq_pit["date"] = pd.to_datetime(jq_pit["date"]).dt.normalize()
jq_pit["ts_code"] = jq_pit["ts_code"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")

# stock_basic for filters
sb = pd.read_parquet(P / "data/reference/stock_basic.parquet")
sb["list_date"] = pd.to_datetime(sb["list_date"], format="%Y%m%d", errors="coerce")
sb["delist_date"] = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")

# Calm Tuesdays (avoid crash periods)
calm_dates = ["2017-03-07", "2017-09-12", "2019-05-14", "2019-11-12",
              "2021-03-09", "2021-10-12", "2023-05-09", "2025-03-11"]

def nearest_tue(d):
    tu = sorted(jq_pit["date"].unique())
    valid = [t for t in tu if t <= d]
    return valid[-1] if valid else tu[0]

print("Selection-metric test: JQ's actual holdings ranked by OUR Tushare total_mv")
print("(if ranks cluster 1-15 → total_mv≈market_cap; if scattered 1-50+ → metrics differ)")
print()
all_ranks = []
for ds in calm_dates:
    d = pd.Timestamp(ds)
    jq_holdings = set(jq_pos[jq_pos["date"] == d]["ts_code"])
    if not jq_holdings:
        continue
    # Build our eligible universe on d
    uni = set(jq_pit[jq_pit["date"] == nearest_tue(d)]["ts_code"])
    list_cutoff = d - pd.Timedelta(days=375)
    elig = sb[(sb["ts_code"].isin(uni)) & (sb["list_date"] <= list_cutoff)
              & ((sb["delist_date"].isna()) | (sb["delist_date"] > d))]
    elig_codes = sorted(elig["ts_code"].str.replace(".", "_"))
    # total_mv ranking
    df = D.features(elig_codes, ["Ref($total_mv, 1)"], start_time=ds, end_time=ds, freq="day")
    df.columns = ["total_mv_lag1"]
    df = df.reset_index().dropna(subset=["total_mv_lag1"])
    df["ts_code"] = df["instrument"].str.replace("_", ".")
    df = df.sort_values("total_mv_lag1").reset_index(drop=True)
    df["our_rank"] = range(1, len(df) + 1)
    rank_map = dict(zip(df["ts_code"], df["our_rank"]))
    holding_ranks = sorted([rank_map.get(c, -1) for c in jq_holdings if rank_map.get(c, -1) > 0])
    n_in_top15 = sum(1 for r in holding_ranks if r <= 15)
    print(f"{ds}: JQ held {len(jq_holdings)}, our-total_mv ranks = {holding_ranks}")
    print(f"          {n_in_top15}/{len(holding_ranks)} in our top-15;  "
          f"max rank = {max(holding_ranks) if holding_ranks else 'NA'};  "
          f"median rank = {int(np.median(holding_ranks)) if holding_ranks else 'NA'}")
    all_ranks.extend(holding_ranks)

print()
print("=" * 70)
if all_ranks:
    arr = np.array(all_ranks)
    print(f"Aggregate over calm days: {len(arr)} holdings")
    print(f"  median rank by our total_mv: {int(np.median(arr))}")
    print(f"  in top-12: {(arr<=12).sum()} ({(arr<=12).mean()*100:.0f}%)")
    print(f"  in top-15: {(arr<=15).sum()} ({(arr<=15).mean()*100:.0f}%)")
    print(f"  in top-24: {(arr<=24).sum()} ({(arr<=24).mean()*100:.0f}%)")
    print(f"  beyond rank 24: {(arr>24).sum()} ({(arr>24).mean()*100:.0f}%)")
    print()
    print("INTERPRETATION:")
    if (arr <= 15).mean() > 0.85:
        print("  ≥85% of JQ holdings are in our total_mv top-15 → metrics AGREE.")
        print("  The selection gap is NOT from total_mv vs market_cap.")
    else:
        print("  JQ holdings are SCATTERED across our total_mv ranks → metrics DIFFER.")
        print("  Tushare total_mv ≠ JoinQuant valuation.market_cap → confirms selection gap.")
