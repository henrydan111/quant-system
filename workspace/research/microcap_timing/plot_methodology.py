# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Deliverable chart for the microcap<->dividend rotation methodology (S5, 0.2% cost)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "workspace" / "outputs" / "microcap_timing"

micro = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")["ret"].fillna(0)
div = pd.read_parquet(OUT / "basket_div.parquet")["ret"].reindex(micro.index).fillna(0)
dates = micro.index
micro_lvl = (1 + micro).cumprod()

ma5 = micro_lvl.rolling(5).mean()
ma200 = micro_lvl.rolling(200).mean()
ratio = (ma5 / ma200).to_numpy()
dd60 = (1 - micro_lvl / micro_lvl.rolling(60, min_periods=1).max()).to_numpy()
cap = np.zeros(len(ratio), dtype=bool)
for t in range(len(ratio)):
    if np.isnan(ratio[t]):
        cap[t] = False
    elif ratio[t] < 0.85:
        cap[t] = True
    elif ratio[t] > 0.95:
        cap[t] = False
    else:
        cap[t] = cap[t - 1] if t > 0 else False
in_micro = pd.Series((((ratio > 1) & (dd60 < 0.10)) | cap).astype(float), index=dates)
w = in_micro.shift(1).fillna(1.0)
pr = w * micro + (1 - w) * div - w.diff().abs().fillna(0) * 0.002

W = slice("2014-01-02", None)


def stats(s):
    s = s.loc[W]
    lv = (1 + s).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = s.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    return ann * 100, dd * 100, (ann - 0.04) / vol


sm, su = stats(pr), stats(micro)
fig, (ax, axr) = plt.subplots(2, 1, figsize=(14.5, 8), sharex=True, gridspec_kw={"height_ratios": [3.4, 0.6]})
lv_u = (1 + micro.loc[W]).cumprod()
lv_s = (1 + pr.loc[W]).cumprod()
ax.plot(lv_u, color="crimson", lw=1.0, label=f"微盘满仓  {su[0]:.0f}% / MDD {su[1]:.0f}% / Sharpe {su[2]:.2f}")
ax.plot(lv_s, color="teal", lw=1.2, label=f"微盘⇄红利轮动(含0.2%成本)  {sm[0]:.0f}% / MDD {sm[1]:.0f}% / Sharpe {sm[2]:.2f}")
in_div = (w.loc[W] < 0.5)
d = in_div.astype(int).diff().fillna(in_div.iloc[0])
for s, e in zip(in_div.index[d == 1], list(in_div.index[d == -1]) + [in_div.index[-1]]):
    ax.axvspan(s, e, color="goldenrod", alpha=0.18, lw=0)
ax.set_yscale("log")
ax.set_yticks([1, 2, 5, 10, 20, 50])
ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}x"))
ax.legend(fontsize=10, loc="upper left")
ax.grid(alpha=0.3)
ax.set_title("小市值择时方法论:微盘核心 ⇄ 红利防御(出场腿=红利ETF,非现金) — 金色=持红利期")
axr.fill_between(w.loc[W].index, 0, 1, where=(w.loc[W] > 0.5).to_numpy(), color="teal", alpha=0.6, lw=0, label="持微盘")
axr.fill_between(w.loc[W].index, 0, 1, where=(w.loc[W] < 0.5).to_numpy(), color="goldenrod", alpha=0.7, lw=0, label="持红利")
axr.set_yticks([])
axr.set_ylabel("仓位")
axr.legend(fontsize=8, ncol=2, loc="upper left")
fig.tight_layout()
fig.savefig(OUT / "methodology_microcap_dividend.png", dpi=130)
print("saved:", OUT / "methodology_microcap_dividend.png")
print(f"S5+cost IS: {sm[0]:.1f}/{sm[1]:.1f}/{sm[2]:.2f}  micro: {su[0]:.1f}/{su[1]:.1f}/{su[2]:.2f}")
