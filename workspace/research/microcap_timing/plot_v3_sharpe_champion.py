# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Compare the IS-Sharpe-champion rule (v3: drawdown-state n=60/-10%/-8% + capitulation
leg) against the user's two earlier signals (v1 MA5/200, v2 +Timing(0.85,0.95)) and
the untimed index, 2009-2026, with position ribbons and a 2014-01-02 IS/OOS divider."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT = PROJECT_ROOT / "workspace" / "outputs" / "microcap_timing"
RF = 0.04
START = "2009-01-05"
IS_START = "2014-01-02"

out = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")
level, ret = out["level"], out["ret"].fillna(0)
ma5, ma200 = level.rolling(5).mean(), level.rolling(200).mean()
ratio = ma5 / ma200
rarr = ratio.to_numpy()


def cap_state(lo=0.85, hi=0.95):
    s = np.zeros(len(rarr), dtype=bool)
    for t in range(len(rarr)):
        if np.isnan(rarr[t]):
            s[t] = False
        elif rarr[t] < lo:
            s[t] = True
        elif rarr[t] > hi:
            s[t] = False
        else:
            s[t] = s[t - 1] if t > 0 else False
    return s


def dd_on(n=60, x=0.10, y=0.08):
    dd = (level / level.rolling(n, min_periods=1).max() - 1).to_numpy()
    flat = np.zeros(len(dd), dtype=bool)
    for t in range(len(dd)):
        if dd[t] < -x:
            flat[t] = True
        elif dd[t] > -y:
            flat[t] = False
        else:
            flat[t] = flat[t - 1] if t > 0 else False
    return ~flat


CAP = cap_state()
sigs = {
    "v1: MA5>MA200": (rarr > 1),
    "v2: v1 OR Timing(.85,.95)": (rarr > 1) | CAP,
    "v3: drawdown(60d,-10%/-8%) OR cap-leg": dd_on() | CAP,
}


def make_pos(sig):
    pos = pd.Series(sig.astype(float), index=level.index)
    pos[ratio.isna()] = 0.0
    return pos.shift(1).fillna(0)


def stats(pr):
    lv = (1 + pr).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    return ann * 100, dd * 100, (ann - RF) / vol


fig, (ax, axr) = plt.subplots(
    2, 1, figsize=(14.5, 8.2), sharex=True, gridspec_kw={"height_ratios": [3.2, 1]}
)

colors = {"untimed": "crimson", "v1": "steelblue", "v2": "darkgreen", "v3": "darkorange"}
pr_u = ret.loc[START:]
a_is = stats(pr_u.loc[IS_START:])
a_oos = stats(pr_u.loc[:"2013-12-31"])
ax.plot(
    (1 + pr_u).cumprod(),
    color=colors["untimed"],
    lw=1.0,
    label=f"untimed index | IS {a_is[0]:.0f}%/{a_is[1]:.0f}%/{a_is[2]:.2f} | OOS {a_oos[0]:.0f}%/{a_oos[1]:.0f}%/{a_oos[2]:.2f}",
)

positions = {}
for (lab, sig), key in zip(sigs.items(), ["v1", "v2", "v3"]):
    pos = make_pos(sig)
    positions[key] = pos
    pr = (ret * pos).loc[START:]
    s_is, s_oos = stats(pr.loc[IS_START:]), stats(pr.loc[:"2013-12-31"])
    ax.plot(
        (1 + pr).cumprod(),
        color=colors[key],
        lw=1.1,
        label=f"{lab} | IS {s_is[0]:.0f}%/{s_is[1]:.0f}%/{s_is[2]:.2f} | OOS {s_oos[0]:.0f}%/{s_oos[1]:.0f}%/{s_oos[2]:.2f}",
    )

ax.axvline(pd.Timestamp(IS_START), color="black", ls="--", lw=0.9)
ax.text(pd.Timestamp(IS_START), 0.55, "  2014-01-02 (果仁回测起点; 左=OOS 右=IS)", fontsize=8)
ax.set_yscale("log")
ax.set_yticks([0.5, 1, 2, 5, 10, 20, 60])
ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}x"))
ax.legend(fontsize=8, loc="upper left", title="curve | ann/MDD/Sharpe(rf4)", title_fontsize=8)
ax.grid(alpha=0.3)
ax.set_title("Timing rules on Guoren microcap replica, 2009-01-05 .. 2026-02-27 (no cost)")

for i, key in enumerate(["v1", "v2", "v3"]):
    p = positions[key].loc[START:]
    axr.fill_between(p.index, i + 0.08, i + 0.92, where=p.to_numpy() > 0.5,
                     color=colors[key], alpha=0.75, lw=0)
axr.axvline(pd.Timestamp(IS_START), color="black", ls="--", lw=0.9)
axr.set_ylim(0, 3)
axr.set_yticks([0.5, 1.5, 2.5])
axr.set_yticklabels(["v1", "v2", "v3"])
axr.set_ylabel("in market")
axr.grid(alpha=0.3, axis="x")

fig.tight_layout()
fig.savefig(OUT / "v3_sharpe_champion_compare.png", dpi=130)
print("saved:", OUT / "v3_sharpe_champion_compare.png")
