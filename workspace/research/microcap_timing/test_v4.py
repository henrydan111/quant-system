# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""v4 (user-proposed): If(OR(AND(ma5>ma200, dd60<10%), Timing(ma5/ma200,0.85,0.95)),1,0).

Trend leg now requires BOTH golden cross AND drawdown-from-60d-high < 10% (simple
threshold, no hysteresis). Capitulation leg unchanged. Compared against untimed /
v1 / v2 / v3 on IS (2014+) and OOS (2009-2013); plus dd-threshold & window
perturbation, yearly decomposition, crash behavior, and the 4-curve plot."""
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
IS_W = slice("2014-01-02", None)
OOS_W = slice("2009-01-05", "2013-12-31")

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


def dd_on_state(n=60, x=0.10, y=0.08):
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
TREND = rarr > 1


def dd_ok(n, x):
    return ((1 - level / level.rolling(n, min_periods=1).max()) < x).to_numpy()


def make_pos(sig):
    pos = pd.Series(sig.astype(float), index=level.index)
    pos[ratio.isna()] = 0.0
    return pos.shift(1).fillna(0)


def stats_row(pos, label, w, cost=0.0):
    pr = (ret * pos) - pos.diff().abs().fillna(0) * cost
    pr = pr.loc[w]
    lv = (1 + pr).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    return {
        "config": label,
        "ann_pct": round(ann * 100, 1),
        "mdd_pct": round(dd * 100, 1),
        "sharpe": round((ann - RF) / vol, 2),
        "flips": int(pos.loc[w].diff().abs().sum()),
    }


pos_all = {
    "untimed": pd.Series(1.0, index=level.index),
    "v1": make_pos(TREND),
    "v2": make_pos(TREND | CAP),
    "v3 (dd-state 10/8 OR cap)": make_pos(dd_on_state() | CAP),
    "v4 (trend AND dd60<10% OR cap)": make_pos((TREND & dd_ok(60, 0.10)) | CAP),
}
rows = []
for w, wl in ((IS_W, "IS"), (OOS_W, "OOS")):
    for lab, pos in pos_all.items():
        rows.append({**stats_row(pos, lab, w), "window": wl})
print("=== v4 vs all (no cost) ===")
print(pd.DataFrame(rows).to_string(index=False))

print("\n=== v4 with 0.2% one-way cost ===")
v4 = pos_all["v4 (trend AND dd60<10% OR cap)"]
print(pd.DataFrame([
    {**stats_row(v4, "v4", IS_W, 0.002), "window": "IS"},
    {**stats_row(v4, "v4", OOS_W, 0.002), "window": "OOS"},
]).to_string(index=False))

# yearly
pr4 = ret * v4
yearly = pd.DataFrame({
    "index": (1 + ret).groupby(ret.index.year).prod() - 1,
    "v2": (1 + ret * pos_all["v2"]).groupby(ret.index.year).prod() - 1,
    "v4": (1 + pr4).groupby(pr4.index.year).prod() - 1,
}).loc[2009:] * 100
yearly["v4_minus_idx"] = yearly["v4"] - yearly["index"]
print("\n=== yearly (%) ===")
print(yearly.round(1).to_string())

# crash behavior
for pk, tr in (("2015-06-12", "2015-07-08"), ("2024-01-02", "2024-02-07"),
               ("2015-12-30", "2016-01-28"), ("2025-03-18", "2025-04-07")):
    seg = slice(pk, tr)
    print("crash %s->%s: index %.1f%% | v4 %.1f%% | days in mkt %.0f%%" % (
        pk, tr, ((1 + ret.loc[seg]).prod() - 1) * 100,
        ((1 + (ret * v4).loc[seg]).prod() - 1) * 100, v4.loc[seg].mean() * 100))

# perturbation: dd threshold x and window n
print("\n=== v4 perturbation (ann IS / ann OOS / mdd IS / mdd OOS / sharpe IS / sharpe OOS) ===")
for n in (40, 60, 120):
    for x in (0.08, 0.10, 0.12, 0.15):
        p = make_pos((TREND & dd_ok(n, x)) | CAP)
        a = stats_row(p, "", IS_W)
        b = stats_row(p, "", OOS_W)
        print(f"  n={n:3d} x={int(x*100):2d}%: {a['ann_pct']:5.1f}/{b['ann_pct']:5.1f} | {a['mdd_pct']:6.1f}/{b['mdd_pct']:6.1f} | {a['sharpe']:.2f}/{b['sharpe']:.2f} | flips {a['flips']}")

# state at data end
dd_now = 1 - level.iloc[-1] / level.rolling(60, min_periods=1).max().iloc[-1]
print(f"\nat 2026-02-27: dd from 60d high = {dd_now*100:.1f}%, trend gap = {(rarr[-1]-1)*100:.1f}%, v4 position = {int(v4.iloc[-1])}")

# plot
fig, (ax, axr) = plt.subplots(2, 1, figsize=(14.5, 8.2), sharex=True,
                              gridspec_kw={"height_ratios": [3.2, 1]})
colors = {"untimed": "crimson", "v1": "steelblue", "v2": "darkgreen",
          "v3 (dd-state 10/8 OR cap)": "darkorange", "v4 (trend AND dd60<10% OR cap)": "purple"}
for lab, pos in pos_all.items():
    pr = (ret * pos).loc["2009-01-05":]
    s_is, s_oos = stats_row(pos, lab, IS_W), stats_row(pos, lab, OOS_W)
    ax.plot((1 + pr).cumprod(), color=colors[lab], lw=1.05,
            label=f"{lab} | IS {s_is['ann_pct']:.0f}%/{s_is['mdd_pct']:.0f}%/{s_is['sharpe']:.2f} | OOS {s_oos['ann_pct']:.0f}%/{s_oos['mdd_pct']:.0f}%/{s_oos['sharpe']:.2f}")
ax.axvline(pd.Timestamp("2014-01-02"), color="black", ls="--", lw=0.9)
ax.set_yscale("log")
ax.set_yticks([0.5, 1, 2, 5, 10, 20, 60])
ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}x"))
ax.legend(fontsize=8, loc="upper left", title="curve | ann/MDD/Sharpe", title_fontsize=8)
ax.grid(alpha=0.3)
ax.set_title("v4 vs v1/v2/v3 vs untimed — Guoren microcap replica 2009-2026 (no cost; dashed = 2014-01-02)")
for i, key in enumerate(["v1", "v2", "v4 (trend AND dd60<10% OR cap)"]):
    p = pos_all[key].loc["2009-01-05":]
    axr.fill_between(p.index, i + 0.08, i + 0.92, where=p.to_numpy() > 0.5,
                     color=colors[key], alpha=0.75, lw=0)
axr.axvline(pd.Timestamp("2014-01-02"), color="black", ls="--", lw=0.9)
axr.set_ylim(0, 3)
axr.set_yticks([0.5, 1.5, 2.5])
axr.set_yticklabels(["v1", "v2", "v4"])
axr.set_ylabel("in market")
axr.grid(alpha=0.3, axis="x")
fig.tight_layout()
fig.savefig(OUT / "v4_compare.png", dpi=130)
print("plot ->", OUT / "v4_compare.png")
