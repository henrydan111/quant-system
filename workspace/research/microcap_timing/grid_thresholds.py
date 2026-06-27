# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Threshold-sensitivity grid for signal v2: OR(ma5>ma200, Timing(ratio, lower, upper)).

If 0.85/0.95 sits on a smooth plateau, the capitulation leg is robust; if it is a
spike, the 2024 windfall is threshold luck. Also reports each variant's 2024
calendar-year return to expose concentration.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT = PROJECT_ROOT / "workspace" / "outputs" / "microcap_timing"
EVAL_START = "2014-01-02"
RF = 0.04

out = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")
level, ret = out["level"], out["ret"].fillna(0)
ma5, ma200 = level.rolling(5).mean(), level.rolling(200).mean()
ratio = ma5 / ma200
trend = (ratio > 1).astype(int)
r = ratio.to_numpy()


def run(lower: float, upper: float) -> dict:
    state = np.zeros(len(r), dtype=int)
    for t in range(len(r)):
        if np.isnan(r[t]):
            state[t] = 0
        elif r[t] < lower:
            state[t] = 1
        elif r[t] > upper:
            state[t] = 0
        else:
            state[t] = state[t - 1] if t > 0 else 0
    sig = ((trend.to_numpy() == 1) | (state == 1)).astype(int)
    sig = pd.Series(sig, index=ratio.index).where(~ratio.isna(), 0)
    pos = sig.shift(1).fillna(0)
    pr = (ret * pos).loc[EVAL_START:]
    lv = (1 + pr).cumprod()
    n_days = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / n_days) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    y2024 = (1 + pr.loc["2024"]).prod() - 1
    return {
        "lower": lower,
        "upper": upper,
        "ann_pct": round(ann * 100, 1),
        "sharpe": round((ann - RF) / vol, 2),
        "mdd_pct": round(dd * 100, 1),
        "ret_2024_pct": round(y2024 * 100, 1),
    }


rows = []
for lower in (0.78, 0.80, 0.82, 0.84, 0.85, 0.86, 0.88, 0.90, 0.92):
    for upper in (0.88, 0.90, 0.92, 0.94, 0.95, 0.96, 0.98, 1.00):
        if upper <= lower + 0.02:
            continue
        rows.append(run(lower, upper))
g = pd.DataFrame(rows)
g.to_csv(OUT / "v2_threshold_grid.csv", index=False)

piv_ann = g.pivot(index="lower", columns="upper", values="ann_pct")
piv_2024 = g.pivot(index="lower", columns="upper", values="ret_2024_pct")
print("=== full-window ann %% (v1 baseline 31.0, untimed 36.9; user point lower=0.85 upper=0.95) ===")
print(piv_ann.to_string())
print("\n=== 2024 calendar-year return %% (index +9.7, v1 -0.9) ===")
print(piv_2024.to_string())
print("\nSharpe range:", g["sharpe"].min(), "..", g["sharpe"].max())
