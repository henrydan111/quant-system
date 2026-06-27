# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Per-year timing contribution + equity plot for the Guoren microcap replication."""
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

out = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")
full = out["level"]
ma5, ma200 = full.rolling(5).mean(), full.rolling(200).mean()
sig = (ma5 > ma200).astype(int)
pos = sig.shift(1).fillna(0)

ev = out.loc[EVAL_START:]
pos_ev = pos.loc[EVAL_START:]
ret_u = ev["ret"].fillna(0)
ret_t = (ev["ret"] * pos_ev).fillna(0)

yearly = pd.DataFrame(
    {
        "index": (1 + ret_u).groupby(ev.index.year).prod() - 1,
        "timed": (1 + ret_t).groupby(ev.index.year).prod() - 1,
        "days_flat": (pos_ev == 0).groupby(ev.index.year).sum(),
    }
)
yearly["timing_edge"] = yearly["timed"] - yearly["index"]
print("=== yearly: index vs timed (%) ===")
print(
    (yearly[["index", "timed", "timing_edge"]] * 100)
    .round(1)
    .join(yearly["days_flat"])
    .to_string()
)

# 2024 flat window: what the index did while we were out
flat_w = out.loc["2024-02-01":"2024-09-27", "ret"].fillna(0)
print("\nindex move during 2024 flat window (02-01..09-27): %.1f%%" % ((1 + flat_w).prod() * 100 - 100))
dodge = out.loc["2024-02-01":"2024-02-07", "ret"].fillna(0)
print("of which dodged crash leg (02-01..02-07): %.1f%%" % ((1 + dodge).prod() * 100 - 100))

# cost sensitivity: full-book turnover on each position change
lv_u = (1 + ret_u).cumprod()
rows = []
for cost in (0.0, 0.001, 0.002, 0.003):
    chg = pos_ev.diff().abs().fillna(0)
    ret_c = ret_t - chg * cost
    lv = (1 + ret_c).cumprod()
    n_days = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / n_days) - 1
    dd = (lv / lv.cummax() - 1).min()
    vol = ret_c.std() * np.sqrt(245)
    rows.append(
        {
            "one_way_cost": cost,
            "ann_pct": round(ann * 100, 2),
            "mdd_pct": round(dd * 100, 2),
            "sharpe_rf4": round((ann - 0.04) / vol, 2),
        }
    )
print("\n=== timed variant cost sensitivity ===")
print(pd.DataFrame(rows).to_string(index=False))

# ---- plot ----
lv_t = (1 + ret_t).cumprod()
fig, ax = plt.subplots(figsize=(14, 6))
ax.plot(lv_u.index, lv_u, color="crimson", lw=1.0, label="replica microcap index (untimed)")
ax.plot(lv_t.index, lv_t, color="steelblue", lw=1.0, label="replica + MA5/200 timing")
flat = (pos_ev == 0).astype(int)
d = flat.diff().fillna(flat.iloc[0])
starts = flat.index[d == 1]
ends = flat.index[d == -1]
if len(ends) < len(starts):
    ends = ends.append(pd.DatetimeIndex([flat.index[-1]]))
for s, e in zip(starts, ends):
    ax.axvspan(s, e, color="grey", alpha=0.25, lw=0)
ax.set_yscale("log")
ticks = [1, 2, 5, 10, 20, 45]
ax.set_yticks(ticks)
ax.get_yaxis().set_major_formatter(
    plt.FuncFormatter(lambda v, _: f"+{(v - 1) * 100:.0f}%" if v > 1 else "0%")
)
ax.set_title("Guoren microcap index replica (2014-01-02 .. 2026-02-27), grey = timing flat")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "replica_curve.png", dpi=130)
print("\nplot ->", OUT / "replica_curve.png")
