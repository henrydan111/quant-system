"""M2 — slope×R² trend-smoothness momentum (T-1, PIT-safe) on IS (2014-2020).

The JoinQuant "加权对数回归动量×R²": trend speed (regression slope of price)
gated by trend smoothness (R² of the fit). The ×R² is the claimed improvement
over naive N-day momentum (which the prior effort found = reversal/falling knives
long-only). Tests whether ×R² rescues momentum long-only.

PIT-safe: every $field wrapped in Ref(...,1) via ADJ_CLOSE_T1. Computed through
the sanctioned compute_factors door. Forward returns from the same call.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

import jq_utils as J
import research_utils as ru
import backtest_harness as bh

from src.alpha_research.factor_library import compute_factors
from src.alpha_research.factor_library.operators import ADJ_CLOSE_T1
from src.alpha_research import factor_eval as fe

IS_START, IS_END = "2014-01-01", "2020-12-31"
BENCH = "000905_SH"

# slope-of-price normalized by price (scale-free trend speed) × R² (smoothness)
def slope_r2(n):
    speed = f"(Slope({ADJ_CLOSE_T1}, {n}) / {ADJ_CLOSE_T1})"
    smooth = f"Rsquare({ADJ_CLOSE_T1}, {n})"
    return f"{speed} * {smooth}"

def slope_only(n):
    return f"(Slope({ADJ_CLOSE_T1}, {n}) / {ADJ_CLOSE_T1})"

CAT = {
    "mom_slope_r2_25":  slope_r2(25),
    "mom_slope_r2_60":  slope_r2(60),
    "mom_slope_r2_120": slope_r2(120),
    "mom_slope_60":     slope_only(60),   # control: speed without R² gate
}

print("Computing slope×R² momentum factors over IS (this hits the qlib provider)...")
fac, fwd = compute_factors(CAT, IS_START, IS_END, horizons=[20], stage="is_only")
print(f"  factors {fac.shape}, fwd {fwd.shape}, cols={list(fwd.columns)}")
fwd_col = [c for c in fwd.columns if "20" in c][0]
fwd20 = fwd[fwd_col]

print("\n=== M2 IC (vs fwd_20d) ===")
ic_rows = []
for name in CAT:
    ics = fe.compute_ic_series(fac[name], fwd20)
    s = fe.compute_ic_summary(ics)
    row = {"factor": name,
           "mean_ic": s.get("mean_ic"), "mean_rank_ic": s.get("mean_rank_ic"),
           "icir": s.get("icir"), "rank_icir": s.get("rank_icir"),
           "ic_t": s.get("ic_tstat", s.get("t_stat"))}
    ic_rows.append(row)
    print(f"  {name:20s} meanRankIC={row['mean_rank_ic']:+.4f} rankICIR={row['rank_icir']:+.3f} "
          f"meanIC={row['mean_ic']:+.4f}")

# quantile monotonicity for the headline factor
print("\n=== M2 quantile spread (mom_slope_r2_60) ===")
q = fe.compute_quantile_returns(fac["mom_slope_r2_60"], fwd20, n_quantiles=5)
qs = fe.compute_quantile_summary(q)
print(qs.to_string())
mono = fe.test_monotonicity(qs)
print("monotonic:", mono)

# ---- long-only top-K: does ×R² rescue momentum? ----
print("\n=== M2 long-only top-K (merged with cached universe factors) ===")
F = pd.read_parquet(J.CACHE / "factors_is.parquet")
Fm = F.join(fac, how="left")  # add the new momentum factors onto the universe panel

results = []
def record(m):
    results.append(J.metrics_dict(m["label"], m["_net"], m.get("_bench")))
    print(J.summary_line(m["label"], m["_net"], m.get("_bench")))

# plain momentum (reversal control) — high momentum = good (no negate)
for name in ["mom_return_20d", "mom_slope_r2_25", "mom_slope_r2_60", "mom_slope_r2_120", "mom_slope_60"]:
    for k in (20, 40):
        w = {name: 1.0}; neg = {name: False}
        m = bh.run_composite_backtest(Fm, w, neg, IS_START, IS_END,
                                      universe_kwargs={"liq_pct_floor": 0.40},
                                      topk=k, benchmark=BENCH, label=f"M2 {name} k{k} (long high)")
        record(m)

print("\n=== yearly breakdown ===")
for r in results:
    ys = "  ".join(f"{y}:{v:+.1%}" for y, v in sorted(r["yearly"].items()))
    print(f"{r['label']:34s} {ys}")

with open(J.OUT / "m2_results.json", "w", encoding="utf-8") as f:
    json.dump({"ic": ic_rows,
               "books": [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]},
              f, indent=2, default=float)
# cache the new momentum factors for reuse in M3
fac.to_parquet(J.OUT / "mom_slope_r2_is.parquet")
print(f"\nSaved -> {J.OUT/'m2_results.json'} and mom_slope_r2_is.parquet")
