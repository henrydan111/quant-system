# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Chart: microcap index vs water level (flat) + yearly rotation alpha bars."""
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
mv = pd.read_parquet(OUT / "panel_total_mv.parquet").reindex(micro.index)
traded = pd.read_parquet(OUT / "panel_traded.parquet").reindex(micro.index).fillna(0)
dates = micro.index
micro_lvl = (1 + micro).cumprod()

mv_np, tr_np = mv.to_numpy(), traded.to_numpy()
water = np.full(len(dates), np.nan)
for i in range(len(dates)):
    row = mv_np[i].copy()
    row[tr_np[i] == 0] = np.nan
    valid = row[np.isfinite(row) & (row > 0)]
    if valid.size >= 100:
        water[i] = np.sort(valid)[99]
water = pd.Series(water, index=dates).ffill()
water_norm = water / water.iloc[20]
idx_norm = micro_lvl / micro_lvl.iloc[20]

idx20 = micro_lvl / micro_lvl.shift(20) - 1
wl20 = water / water.shift(20) - 1
alpha = (idx20 - wl20)
blocks = []
i = 20
while i < len(micro_lvl):
    blocks.append((micro_lvl.index[i], micro_lvl.iloc[i] / micro_lvl.iloc[i - 20] - 1 - (water.iloc[i] / water.iloc[i - 20] - 1)))
    i += 20
bl = pd.DataFrame(blocks, columns=["date", "alpha"]).set_index("date")
yr = bl.groupby(bl.index.year)["alpha"].mean()
yr_ann = ((1 + yr) ** 12 - 1) * 100

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8.5), gridspec_kw={"height_ratios": [1.5, 1]})
ax1.plot(idx_norm.loc["2009":], color="crimson", lw=1.1, label="微盘指数(累计,起点=1)")
ax1.plot(water_norm.loc["2009":], color="navy", lw=1.3, label="微盘水位 第100小市值(累计,起点=1)")
ax1.set_yscale("log")
ax1.set_yticks([1, 3, 10, 30, 100, 300])
ax1.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}x"))
ax1.legend(fontsize=10, loc="upper left")
ax1.grid(alpha=0.3)
ax1.set_title("微盘收益 ≈ 100% 轮动:指数18年 +131倍,而水位几乎不动(+13%/0.7%年化)")

colors = ["seagreen" if v > 0 else "firebrick" for v in yr_ann.values]
ax2.bar(yr_ann.index, yr_ann.values, color=colors, alpha=0.8)
ax2.axhline(27, color="grey", ls="--", lw=1, label="全期均值 27%/年")
ax2.set_ylabel("年化轮动alpha %")
ax2.set_title("逐年轮动alpha:持续为正、无明显衰减,但2023-24显著回落(拥挤期),2025回升")
ax2.legend(fontsize=9)
ax2.grid(alpha=0.3, axis="y")
for x, v in zip(yr_ann.index, yr_ann.values):
    ax2.text(x, v + 1, f"{v:.0f}", ha="center", fontsize=7)

fig.tight_layout()
fig.savefig(OUT / "waterlevel_rotation_alpha.png", dpi=130)
print("saved:", OUT / "waterlevel_rotation_alpha.png")
