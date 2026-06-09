"""M0/M1 — JoinQuant value-book modules on IS (2014-2020), clean PIT.

M0: C/P (val_cftp) + financial-authenticity gate concentrated value book
    (the 大市值价值 / 价值低波 idea). Tests gated vs ungated, k5/k10/k20,
    ROA-ranked vs C/P-ranked. Diagnoses how often the absolute gate empties
    (the "选不出票即空仓" natural-timing mechanism).
M1: C/P ∩ low-vol intersection (价值低波 orthogonal construction).

Sanity: first reproduces the prior effort's value@core k20 and VL@core k40
baselines, to confirm the harness reproduces the documented IS numbers.

Reuses: cached factors_is.parquet (PIT-safe), backtest_harness (VectorizedBacktester).
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

import jq_utils as J
import research_utils as ru
import backtest_harness as bh

IS_START, IS_END = "2014-01-01", "2020-12-31"
BENCH = "000905_SH"

print("Loading cached IS factors...")
F = pd.read_parquet(J.CACHE / "factors_is.parquet")
print(f"  {F.shape}, {F.index.get_level_values(0).min().date()} -> {F.index.get_level_values(0).max().date()}")

results = []


def record(m):
    results.append(J.metrics_dict(m["label"], m["_net"], m.get("_bench")))
    print(J.summary_line(m["label"], m["_net"], m.get("_bench")))


# ---------- sanity: reproduce prior baselines ----------
print("\n=== SANITY: reproduce prior baselines ===")
VAL_W = {"val_bp": 1.0, "val_ep_ttm": 1.0, "val_sp_ttm": 1.0, "val_cftp": 1.0}
VAL_NEG = {k: False for k in VAL_W}  # value yields: high = cheap = good
LOWVOL_W = {"risk_vol_60d": 1.0, "risk_downvol_60d": 1.0}
LOWVOL_NEG = {k: True for k in LOWVOL_W}  # low vol = good -> negate

m = bh.run_composite_backtest(F, VAL_W, VAL_NEG, IS_START, IS_END,
                              universe_kwargs={"liq_pct_floor": 0.40},
                              topk=20, benchmark=BENCH, label="prior:value@core k20")
record(m)
VL_W = {**VAL_W, **LOWVOL_W}
VL_NEG = {**VAL_NEG, **LOWVOL_NEG}
m = bh.run_composite_backtest(F, VL_W, VL_NEG, IS_START, IS_END,
                              universe_kwargs={"liq_pct_floor": 0.40},
                              topk=40, benchmark=BENCH, label="prior:VL@core k40")
record(m)


# ---------- gated-book helper (natural cash-out capable) ----------
def gate_mask(sub: pd.DataFrame, *, pb_lt1: bool, roa_min: float) -> pd.Series:
    """Financial-authenticity gate on factor rows. pb<1 == val_bp>1."""
    m = (sub["val_cftp"] > 0) & (sub["grow_netprofit_yoy"] > 0) & (sub["qual_roa"] > roa_min)
    if pb_lt1:
        m = m & (sub["val_bp"] > 1.0)
    return m.fillna(False)


def run_gated(label, weights, neg, *, topk, pb_lt1, roa_min,
              size_band=None, liq=0.40):
    rebal = ru.monthly_rebalance_dates(IS_START, IS_END)
    uk = {"liq_pct_floor": liq}
    if size_band:
        uk["size_low_pct"], uk["size_high_pct"] = size_band
    uni = ru.build_universe_mask(F, rebal, **uk)
    uni_idx = pd.MultiIndex.from_frame(uni)
    sub = F.loc[F.index.isin(uni_idx)]
    keep = gate_mask(sub, pb_lt1=pb_lt1, roa_min=roa_min)
    gated_idx = sub.index[keep]
    gated_uni = gated_idx.to_frame(index=False)[["datetime", "instrument"]]
    # diagnostic: qualifying names per rebalance
    cnt = gated_uni.groupby("datetime").size()
    n_empty = int((cnt.reindex(rebal).fillna(0) == 0).sum())
    rebal_score = bh.build_composite_signal(F, weights, neg, rebal, gated_uni)
    daily = bh.expand_monthly_signal(rebal_score, rebal, IS_START, IS_END)
    if daily.empty:
        print(f"{label:34s} EMPTY signal")
        return None
    m = bh.run_composite_backtest(F, weights, neg, IS_START, IS_END,
                                  daily_signal_override=daily, topk=topk,
                                  benchmark=BENCH, label=label)
    m["_gate_cnt_median"] = float(cnt.median())
    m["_gate_n_empty_rebal"] = n_empty
    m["_gate_n_rebal"] = len(rebal)
    return m


# ---------- M0: C/P-anchored concentrated value books ----------
print("\n=== M0: C/P concentrated value books (gated vs ungated) ===")
CP_W = {"val_cftp": 1.0}
CP_NEG = {"val_cftp": False}
ROA_W = {"qual_roa": 1.0}
ROA_NEG = {"qual_roa": False}

# ungated C/P rank, varying concentration
for k in (5, 10, 20):
    m = bh.run_composite_backtest(F, CP_W, CP_NEG, IS_START, IS_END,
                                  universe_kwargs={"liq_pct_floor": 0.40},
                                  topk=k, benchmark=BENCH, label=f"M0 C/P ungated k{k}")
    record(m)

# gated (pb<1 + OCF>0 + npy>0 + ROA>0), ranked by ROA (JQ) and by C/P
for pb in (True, False):
    for rank_name, (w, neg) in (("ROA", (ROA_W, ROA_NEG)), ("C/P", (CP_W, CP_NEG))):
        for k in (5, 10):
            tag = f"M0 gate(pb<1={pb},ROA>0) rank={rank_name} k{k}"
            m = run_gated(tag, w, neg, topk=k, pb_lt1=pb, roa_min=0.0)
            if m is None:
                continue
            record(m)
            print(f"      gate: median_names={m['_gate_cnt_median']:.0f} "
                  f"empty_rebal={m['_gate_n_empty_rebal']}/{m['_gate_n_rebal']}")

# stricter ROA gate to probe natural cash-out
for roa_min in (5.0, 10.0):
    tag = f"M0 gate(pb<1,ROA>{roa_min:.0f}) rank=ROA k5"
    m = run_gated(tag, ROA_W, ROA_NEG, topk=5, pb_lt1=True, roa_min=roa_min)
    if m is not None:
        record(m)
        print(f"      gate: median_names={m['_gate_cnt_median']:.0f} "
              f"empty_rebal={m['_gate_n_empty_rebal']}/{m['_gate_n_rebal']}")


# ---------- M1: C/P ∩ low-vol intersection ----------
print("\n=== M1: C/P ∩ low-vol intersection ===")
def run_intersection(label, topk, cp_top_pct=0.30, vol_low_pct=0.30):
    rebal = ru.monthly_rebalance_dates(IS_START, IS_END)
    uni = ru.build_universe_mask(F, rebal, liq_pct_floor=0.40)
    uni_idx = pd.MultiIndex.from_frame(uni)
    sub = F.loc[F.index.isin(uni_idx)]
    g = sub.groupby(level=0)
    cp_rank = g["val_cftp"].rank(pct=True)             # high C/P = cheap
    vol_rank = g["risk_vol_60d"].rank(pct=True)        # low vol = good
    inter = (cp_rank >= 1 - cp_top_pct) & (vol_rank <= vol_low_pct)
    inter_idx = sub.index[inter.fillna(False)]
    inter_uni = inter_idx.to_frame(index=False)[["datetime", "instrument"]]
    cnt = inter_uni.groupby("datetime").size()
    # equal-weight within intersection (score = constant -> topk picks by C/P tiebreak)
    rebal_score = bh.build_composite_signal(F, CP_W, CP_NEG, rebal, inter_uni)
    daily = bh.expand_monthly_signal(rebal_score, rebal, IS_START, IS_END)
    m = bh.run_composite_backtest(F, CP_W, CP_NEG, IS_START, IS_END,
                                  daily_signal_override=daily, topk=topk,
                                  benchmark=BENCH, label=label)
    m["_inter_median"] = float(cnt.median())
    return m

for k in (20, 40):
    m = run_intersection(f"M1 C/P∩lowvol k{k}", k)
    record(m)
    print(f"      intersection: median_names={m['_inter_median']:.0f}")

# yearly breakdown for the top candidates
print("\n=== yearly breakdown (all books) ===")
for r in results:
    ys = "  ".join(f"{y}:{v:+.1%}" for y, v in sorted(r["yearly"].items()))
    print(f"{r['label']:34s} {ys}")

# save
with open(J.OUT / "m0_m1_results.json", "w", encoding="utf-8") as f:
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    json.dump(clean, f, indent=2, default=float)
print(f"\nSaved -> {J.OUT / 'm0_m1_results.json'}")
