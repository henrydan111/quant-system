"""M3 — regime/style rotation (the high-CAGR lever) on IS (2014-2020).

Economic thesis: A-share returns are concentrated in small-cap bull phases
(2014-15, 2019-20). Plain momentum fails long-only (falling knives into crashes,
prior finding). A PIT-safe index-momentum regime filter that holds an aggressive
small-cap book ONLY in uptrends and rotates to large-value / cash otherwise
should neutralize the falling-knife property and capture the bull phases.

Builds base books once (VectorizedBacktester), caches their net series, then
sweeps PIT-safe (shift-1) index regime signals cheaply via combine_regime.
NOT a new execution model -- it selects among already-validated book returns.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

import jq_utils as J
import research_utils as ru
import backtest_harness as bh
import overlay as ov

IS_START, IS_END = "2014-01-01", "2020-12-31"
BENCH = "000905_SH"

VAL_W = {"val_bp": 1.0, "val_ep_ttm": 1.0, "val_sp_ttm": 1.0, "val_cftp": 1.0}
VAL_NEG = {k: False for k in VAL_W}
LOWVOL_W = {"risk_vol_60d": 1.0, "risk_downvol_60d": 1.0}
LOWVOL_NEG = {k: True for k in LOWVOL_W}

print("Loading factors...")
F = pd.read_parquet(J.CACHE / "factors_is.parquet")
mom_path = J.OUT / "mom_slope_r2_is.parquet"
if mom_path.exists():
    F = F.join(pd.read_parquet(mom_path), how="left")
    HAS_MOM = "mom_slope_r2_60" in F.columns
else:
    HAS_MOM = False
print(f"  has slope_r2 momentum: {HAS_MOM}")

BOOK_CACHE = J.OUT / "m3_base_books.parquet"


def build_base_books():
    books = {}
    # large-cap value+low-vol (prior deployable)
    m = bh.run_composite_backtest(F, {**VAL_W, **LOWVOL_W}, {**VAL_NEG, **LOWVOL_NEG},
                                  IS_START, IS_END, universe_kwargs={"liq_pct_floor": 0.40},
                                  topk=40, benchmark=BENCH, label="largeVL")
    books["largeVL"] = m["_net"]; print(J.summary_line("largeVL", m["_net"], m["_bench"]))
    # small/mid quality+value (size band 10-60 pct, quality+value), k40
    sm_uk = {"liq_pct_floor": 0.40, "size_low_pct": 0.10, "size_high_pct": 0.60}
    qv_w = {"val_cftp": 1.0, "val_bp": 1.0, "qual_roa": 1.0, "grow_netprofit_yoy": 1.0}
    qv_neg = {k: False for k in qv_w}
    m = bh.run_composite_backtest(F, qv_w, qv_neg, IS_START, IS_END,
                                  universe_kwargs=sm_uk, topk=40, benchmark=BENCH, label="smallQV")
    books["smallQV"] = m["_net"]; print(J.summary_line("smallQV", m["_net"], m["_bench"]))
    # small/mid low-vol -- cleanest small-cap beta-capture leg (low falling-knife)
    m = bh.run_composite_backtest(F, {"risk_vol_60d": 1.0, "risk_downvol_60d": 1.0},
                                  {"risk_vol_60d": True, "risk_downvol_60d": True},
                                  IS_START, IS_END, universe_kwargs=sm_uk, topk=40,
                                  benchmark=BENCH, label="smallLV")
    books["smallLV"] = m["_net"]; print(J.summary_line("smallLV", m["_net"], m["_bench"]))
    # small/mid momentum (slope_r2) -- aggressive bull-capture (falling-knife risk)
    if HAS_MOM:
        m = bh.run_composite_backtest(F, {"mom_slope_r2_60": 1.0}, {"mom_slope_r2_60": False},
                                      IS_START, IS_END, universe_kwargs=sm_uk, topk=40,
                                      benchmark=BENCH, label="smallMom")
        books["smallMom"] = m["_net"]; print(J.summary_line("smallMom", m["_net"], m["_bench"]))
    bdf = pd.DataFrame(books)
    bdf.to_parquet(BOOK_CACHE)
    return bdf


if BOOK_CACHE.exists():
    print("Loading cached base books...")
    bdf = pd.read_parquet(BOOK_CACHE)
else:
    print("Building base books (each a VectorizedBacktester run)...")
    bdf = build_base_books()

books = {c: bdf[c].dropna() for c in bdf.columns}
bench_net = None

# ---- regime signals (PIT-safe, shift-1) ----
results = []
def rec(label, net):
    results.append(J.metrics_dict(label, net))
    print(J.summary_line(label, net))

print("\n=== base books (standalone) ===")
for name, net in books.items():
    rec(f"base:{name}", net)

print("\n=== M3 regime rotation sweeps ===")
# small-on signal: 中证1000 above its MA  (small-cap uptrend)
# large-on signal: 沪深300 above its MA   (broad uptrend)
for ma in (120, 200):
    small_on = ov.trend_exposure("000852.SH", ma, IS_START, IS_END)   # 1.0 when 1000>MA
    large_on = ov.trend_exposure("000300.SH", ma, IS_START, IS_END)   # 1.0 when 300>MA
    rs = ov.load_index_close  # noqa
    # 3-state choice: smallMom if small_on; elif large_on -> largeVL; else cash
    idx = small_on.index.union(large_on.index)
    so = small_on.reindex(idx).ffill().fillna(0.0)
    lo = large_on.reindex(idx).ffill().fillna(0.0)

    AGGS = (["smallMom"] if HAS_MOM else []) + ["smallQV", "smallLV"]
    for agg in AGGS:
        choice = pd.Series("cash", index=idx)
        choice[lo > 0] = "largeVL"
        choice[so > 0] = agg
        net = J.combine_regime({agg: books[agg], "largeVL": books["largeVL"]},
                               choice, switch_cost=0.0030)
        rec(f"M3 rot[{agg}|largeVL|cash] MA{ma}", net)

    # 2-state: aggressive when small_on else cash (pure bull-capture)
    AGGS = (["smallMom"] if HAS_MOM else []) + ["smallQV", "smallLV"]
    for agg in AGGS:
        choice = pd.Series("cash", index=idx)
        choice[so > 0] = agg
        net = J.combine_regime({agg: books[agg]}, choice, switch_cost=0.0030)
        rec(f"M3 rot[{agg}|cash] MA{ma}", net)
        # cost sensitivity: re-price the best-style switch at a punitive 60bps
        net_hi = J.combine_regime({agg: books[agg]}, choice, switch_cost=0.0060)
        rec(f"M3 rot[{agg}|cash] MA{ma} cost60bp", net_hi)

print("\n=== yearly breakdown ===")
for r in results:
    ys = "  ".join(f"{y}:{v:+.1%}" for y, v in sorted(r["yearly"].items()))
    print(f"{r['label']:34s} {ys}")

with open(J.OUT / "m3_results.json", "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in results],
              f, indent=2, default=float)
print(f"\nSaved -> {J.OUT/'m3_results.json'}")
