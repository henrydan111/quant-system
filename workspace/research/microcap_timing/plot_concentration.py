# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Visualize the concentration risk-switch: top-5% turnover share with its trailing
1.5-sigma band, risk-off shading, against the microcap index; plus equity of the
switch (rest->CSI300) vs untimed, 2009-2026."""
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

out = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")
micro = out["ret"].fillna(0)
conc = pd.read_parquet(OUT / "concentration.parquet")["conc_top5"].reindex(micro.index)
csi = pd.read_parquet(PROJECT_ROOT / "data" / "market" / "index" / "index_000300.SH.parquet")
csi["trade_date"] = pd.to_datetime(csi["trade_date"], format="%Y%m%d")
etf = (csi.set_index("trade_date")["pct_chg"] / 100).reindex(micro.index).fillna(0)

m = conc.rolling(250, min_periods=120).mean()
sd = conc.rolling(250, min_periods=120).std()
thr = m + 1.5 * sd
ro = (conc > thr).fillna(False)

wm = pd.Series(np.where(ro, 0.5, 1.0), index=conc.index).shift(1).fillna(1.0)
we = pd.Series(np.where(ro, 0.5, 0.0), index=conc.index).shift(1).fillna(0.0)
pr = wm * micro + we * etf

w = slice("2014-01-02", None)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14.5, 8.5), sharex=True,
                               gridspec_kw={"height_ratios": [1, 1.4]})

c = conc.loc[w]
ax1.plot(c.index, c, color="black", lw=0.8, label="top-5% 成交额集中度")
ax1.plot(thr.loc[w].index, thr.loc[w], color="red", lw=0.9, ls="--", label="trailing 均值+1.5σ (250d)")
ax1.fill_between(c.index, 0.2, 0.6, where=ro.loc[w].to_numpy(), color="red", alpha=0.18, lw=0, label="risk-off")
ax1.set_ylim(0.25, 0.6)
ax1.set_ylabel("集中度")
ax1.legend(fontsize=8, loc="upper right")
ax1.grid(alpha=0.3)
ax1.set_title("成交额集中度风控开关 (top-5%份额 > 250日均值+1.5σ → 小市值减仓50%+50%转沪深300)")
for d, t in [("2021-01-15", "2021抱团顶\n(正确触发)"), ("2024-02-05", "2024微盘崩盘\n(集中度低→未触发)"),
             ("2026-02-15", "2026当前\n(未触发)")]:
    ax1.annotate(t, xy=(pd.Timestamp(d), 0.52), fontsize=7.5, ha="center", color="darkblue")

lv_u = (1 + micro.loc[w]).cumprod()
lv_s = (1 + pr.loc[w]).cumprod()
ax2.plot(lv_u, color="crimson", lw=1.0, label="不择时 微盘指数")
ax2.plot(lv_s, color="teal", lw=1.1, label="集中度风控开关 (rest→沪深300)")
ax2.fill_between(lv_u.index, 0, 60, where=ro.loc[w].to_numpy(), color="red", alpha=0.12, lw=0)
ax2.set_yscale("log")
ax2.set_yticks([1, 2, 5, 10, 20, 50])
ax2.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}x"))
ax2.set_ylim(0.9, 60)
ax2.legend(fontsize=9, loc="upper left")
ax2.grid(alpha=0.3)
ax2.set_title("净值: IS 39.7%/-48.3%/1.20 vs 不择时 36.9%/-47.8%/1.09 (红带=减仓期)")

fig.tight_layout()
fig.savefig(OUT / "concentration_switch.png", dpi=130)
print("saved:", OUT / "concentration_switch.png")
