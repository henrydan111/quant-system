# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Signal v2: If(OR(ma5>ma200, Timing(ma5/ma200, 0.85, 0.95)), 1, 0).

Guoren Timing(x, lower, upper) semantics (official help, 大盘择时函数 section):
returns 1 when x < lower, 0 when x > upper, otherwise holds yesterday's value.
So v2 = trend leg OR capitulation-rebound leg (state ON after ratio < 0.85,
released when ratio > 0.95). State initialized to 0 at first defined bar.

Outputs: stats vs untimed & v1, yearly table, v2 flat episodes, behavior in the
key crash windows, cost sensitivity, equity plot.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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

state = np.zeros(len(ratio), dtype=int)
r = ratio.to_numpy()
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

pos_v1 = sig_v1.shift(1).fillna(0)
pos_v2 = sig_v2.shift(1).fillna(0)

ev = out.loc[EVAL_START:].index
ret_ev = ret.loc[ev]


def stats(r: pd.Series, label: str) -> dict:
    lv = (1 + r).cumprod()
    n_days = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / n_days) - 1
    vol = r.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    return {
        "series": label,
        "ann_pct": round(ann * 100, 2),
        "vol_pct": round(vol * 100, 2),
        "mdd_pct": round(dd * 100, 2),
        "sharpe_rf4": round((ann - RF) / vol, 2),
    }


rows = [
    stats(ret_ev, "untimed index"),
    stats((ret * pos_v1).loc[ev], "v1: MA5>MA200"),
    stats((ret * pos_v2).loc[ev], "v2: OR(trend, Timing(.85,.95))"),
]
for cost in (0.002,):
    for pos, lab in ((pos_v1, "v1"), (pos_v2, "v2")):
        chg = pos.diff().abs().fillna(0).loc[ev]
        rows.append(stats((ret * pos).loc[ev] - chg * cost, f"{lab} w/ {cost:.1%} one-way cost"))
res = pd.DataFrame(rows)
print("=== stats 2014-01-02..2026-02-27 ===")
print(res.to_string(index=False))

flips_v1 = int(pos_v1.loc[ev].diff().abs().sum())
flips_v2 = int(pos_v2.loc[ev].diff().abs().sum())
print(f"\nposition changes: v1={flips_v1}  v2={flips_v2}")

yearly = pd.DataFrame(
    {
        "index": (1 + ret_ev).groupby(ev.year).prod() - 1,
        "v1": (1 + (ret * pos_v1).loc[ev]).groupby(ev.year).prod() - 1,
        "v2": (1 + (ret * pos_v2).loc[ev]).groupby(ev.year).prod() - 1,
    }
)
yearly["v2_minus_v1_pp"] = (yearly["v2"] - yearly["v1"]) * 100
yearly["v2_minus_idx_pp"] = (yearly["v2"] - yearly["index"]) * 100
print("\n=== yearly (%) ===")
print((yearly[["index", "v1", "v2"]] * 100).round(1).join(yearly[["v2_minus_v1_pp", "v2_minus_idx_pp"]].round(1)).to_string())

# v2 flat episodes
pos_ev2 = pos_v2.loc[ev]
rows = []
arr = pos_ev2.to_numpy()
dates = pos_ev2.index
i = 0
while i < len(arr):
    if arr[i] == 0:
        j = i
        while j + 1 < len(arr) and arr[j + 1] == 0:
            j += 1
        flat_days = dates[i : j + 1]
        avoided = float((1 + ret.loc[flat_days]).prod() - 1)
        rows.append(
            {
                "flat_start": str(dates[i].date()),
                "flat_end": str(dates[j].date()),
                "n_days": j - i + 1,
                "idx_move_pct": round(avoided * 100, 1),
                "rel_edge_pct": round((1 / (1 + avoided) - 1) * 100, 1),
            }
        )
        i = j + 1
    else:
        i += 1
ep = pd.DataFrame(rows)
print("\n=== v2 flat episodes ===")
print(ep.to_string(index=False))
print("episodes:", len(ep), "| winners:", (ep.rel_edge_pct > 0).sum(), "| sum edge pp:", round(ep.rel_edge_pct.sum(), 1))

# capitulation-leg activations (state ON while trend OFF -> the leg actually changing behavior)
active = ((state == 1) & (trend == 0)).loc[ev]
grp = (active != active.shift()).cumsum()
print("\n=== capitulation-leg activations (state=1, trend=0) ===")
for g, seg in active.groupby(grp):
    if not seg.iloc[0]:
        continue
    d0, d1 = seg.index[0], seg.index[-1]
    mv = float((1 + ret.loc[d0:d1]).prod() - 1)
    print(f"  {d0.date()} .. {d1.date()}  ({len(seg)}d)  index move while re-entered: {mv*100:+.1f}%  ratio at entry {ratio.loc[d0]:.3f}")

# plot
lv_u = (1 + ret_ev).cumprod()
lv1 = (1 + (ret * pos_v1).loc[ev]).cumprod()
lv2 = (1 + (ret * pos_v2).loc[ev]).cumprod()
fig, ax = plt.subplots(figsize=(14, 6))
ax.plot(lv_u, color="crimson", lw=1.0, label="untimed index")
ax.plot(lv1, color="steelblue", lw=1.0, label="v1 MA5/200")
ax.plot(lv2, color="darkgreen", lw=1.1, label="v2 +Timing(0.85,0.95)")
flat = (pos_ev2 == 0).astype(int)
d = flat.diff().fillna(flat.iloc[0])
starts, ends = flat.index[d == 1], flat.index[d == -1]
if len(ends) < len(starts):
    ends = ends.append(pd.DatetimeIndex([flat.index[-1]]))
for s, e in zip(starts, ends):
    ax.axvspan(s, e, color="grey", alpha=0.25, lw=0)
ax.set_yscale("log")
ax.set_yticks([1, 2, 5, 10, 20, 45])
ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda v, _: f"+{(v-1)*100:.0f}%" if v > 1 else "0%"))
ax.set_title("v2 timing (grey = v2 flat) vs v1 vs untimed, 2014-01-02..2026-02-27")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "signal_v2_curve.png", dpi=130)
print("\nplot ->", str(OUT / "signal_v2_curve.png"))
