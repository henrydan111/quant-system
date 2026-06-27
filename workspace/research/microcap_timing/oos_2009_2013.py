# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Out-of-sample test of v1 and v2 timing on 2009-2013 (signal defined from 2008-10-31).

The capitulation leg's thresholds (0.85/0.95) were chosen by the user on the
2014-2026 backtest; 2009-2013 is untouched by that choice. Window includes the
2009 V-recovery, the 2011 slow bear, the 2012 double-bottom and the 2013 bull.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT = PROJECT_ROOT / "workspace" / "outputs" / "microcap_timing"
RF = 0.04
OOS_START, OOS_END = "2009-01-05", "2013-12-31"

out = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")
level, ret = out["level"], out["ret"].fillna(0)
ma5, ma200 = level.rolling(5).mean(), level.rolling(200).mean()
ratio = ma5 / ma200
trend = (ratio > 1).astype(int)
print("index starts:", level.index[0].date(), "| signal defined from:", ma200.dropna().index[0].date())

r = ratio.to_numpy()
state = np.zeros(len(r), dtype=int)
for t in range(len(r)):
    if np.isnan(r[t]):
        state[t] = 0
    elif r[t] < 0.85:
        state[t] = 1
    elif r[t] > 0.95:
        state[t] = 0
    else:
        state[t] = state[t - 1] if t > 0 else 0
state = pd.Series(state, index=ratio.index)

sig_v1 = trend.where(~ratio.isna(), 0)
sig_v2 = ((trend == 1) | (state == 1)).astype(int).where(~ratio.isna(), 0)
pos_v1, pos_v2 = sig_v1.shift(1).fillna(0), sig_v2.shift(1).fillna(0)

w = slice(OOS_START, OOS_END)
rets = {
    "untimed": ret.loc[w],
    "v1": (ret * pos_v1).loc[w],
    "v2": (ret * pos_v2).loc[w],
}

rows = []
for lab, pr in rets.items():
    lv = (1 + pr).cumprod()
    n_days = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / n_days) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    rows.append(
        {
            "series": lab,
            "total_pct": round((lv.iloc[-1] - 1) * 100, 1),
            "ann_pct": round(ann * 100, 2),
            "vol_pct": round(vol * 100, 2),
            "mdd_pct": round(dd * 100, 1),
            "sharpe_rf4": round((ann - RF) / vol, 2),
        }
    )
print("\n=== OOS 2009-01-05..2013-12-31 ===")
print(pd.DataFrame(rows).to_string(index=False))

idx_y = (1 + rets["untimed"]).groupby(rets["untimed"].index.year).prod() - 1
v1_y = (1 + rets["v1"]).groupby(rets["v1"].index.year).prod() - 1
v2_y = (1 + rets["v2"]).groupby(rets["v2"].index.year).prod() - 1
yearly = pd.DataFrame({"index": idx_y, "v1": v1_y, "v2": v2_y}) * 100
print("\n=== yearly (%) ===")
print(yearly.round(1).to_string())

active = ((state == 1) & (trend == 0)).loc[w]
grp = (active != active.shift()).cumsum()
print("\n=== capitulation-leg activations in OOS ===")
any_act = False
for g, seg in active.groupby(grp):
    if not seg.iloc[0]:
        continue
    any_act = True
    d0, d1 = seg.index[0], seg.index[-1]
    mv = float((1 + ret.loc[d0:d1]).prod() - 1)
    print(f"  {d0.date()} .. {d1.date()}  ({len(seg)}d)  index move while re-entered: {mv*100:+.1f}%  ratio at entry {ratio.loc[d0]:.3f}")
if not any_act:
    print("  (none)")

# 2008-10-31..2008-12-31 state check (pre-OOS warm segment)
pre = pd.DataFrame({"ratio": ratio, "trend": trend, "state": state}).loc["2008-10-31":"2009-01-31"]
print("\nratio at 2008-10-31: %.3f | state on first defined day: %d" % (pre["ratio"].iloc[0], pre["state"].iloc[0]))
