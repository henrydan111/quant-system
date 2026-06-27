# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Decompose microcap-index return into WATER-LEVEL drift (beta) + ROTATION alpha.

Guoren formula under analysis:
  rotation_alpha_20d = 20d_return(index 111001) - 20d_change(water_level)
  water_level = total_mv of the rank-100 (100th-smallest) stock, cross-section.

User claim: mean 20d alpha ~2% -> ~1.02^12 = 26%/yr rotation excess over water level,
non-decaying. Verify, then characterize: decay, regime, cost-survival, timing usability.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "workspace" / "outputs" / "microcap_timing"

micro = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")["ret"].fillna(0)
mv = pd.read_parquet(OUT / "panel_total_mv.parquet").reindex(micro.index)
traded = pd.read_parquet(OUT / "panel_traded.parquet").reindex(micro.index).fillna(0)
dates = micro.index
micro_lvl = (1 + micro).cumprod()

# water level = rank-100 ascending total_mv among valid traded names (raw, as Guoren Hrank)
RANK = 100
mv_np = mv.to_numpy()
tr_np = traded.to_numpy()
water = np.full(len(dates), np.nan)
water_elig = np.full(len(dates), np.nan)  # eligible-only variant (rough: exclude tiny suspended)
for i in range(len(dates)):
    row = mv_np[i].copy()
    row[(tr_np[i] == 0)] = np.nan  # only traded
    valid = row[np.isfinite(row) & (row > 0)]
    if valid.size >= RANK:
        s = np.sort(valid)
        water[i] = s[RANK - 1]
water = pd.Series(water, index=dates).ffill()

wl_lvl = water  # this is a level (market cap); its 20d pct change = water-level move
idx_ret20 = micro_lvl / micro_lvl.shift(20) - 1
wl_ret20 = wl_lvl / wl_lvl.shift(20) - 1
alpha20 = (idx_ret20 - wl_ret20).dropna()

print("=== verify the decomposition (full sample) ===")
print(f"mean 20d index return   : {idx_ret20.mean()*100:+.2f}%")
print(f"mean 20d water-level chg : {wl_ret20.mean()*100:+.2f}%")
print(f"mean 20d rotation alpha  : {alpha20.mean()*100:+.2f}%   (user claim ~2%)")
ann = (1 + alpha20.mean()) ** 12 - 1
print(f"implied annual rotation alpha (1+mean)^12-1 : {ann*100:.1f}%   (user claim ~26%)")
print(f"alpha20 > 0 share        : {(alpha20>0).mean()*100:.0f}%")

# non-overlapping 20d blocks (honest, no overlap autocorrelation)
blocks = []
i = 20
while i < len(micro_lvl):
    r_idx = micro_lvl.iloc[i] / micro_lvl.iloc[i - 20] - 1
    r_wl = wl_lvl.iloc[i] / wl_lvl.iloc[i - 20] - 1
    blocks.append((micro_lvl.index[i], r_idx - r_wl, r_idx, r_wl))
    i += 20
bl = pd.DataFrame(blocks, columns=["date", "alpha", "idx", "wl"]).set_index("date")
print(f"\nNON-overlapping 20d blocks: mean alpha {bl['alpha'].mean()*100:+.2f}%  "
      f"-> annual {((1+bl['alpha'].mean())**12-1)*100:.1f}%  (n={len(bl)})")

# decay: alpha by year (annualized from non-overlapping blocks)
bl["year"] = bl.index.year
yr = bl.groupby("year")["alpha"].agg(["mean", "count"])
yr["ann_%"] = ((1 + yr["mean"]) ** 12 - 1) * 100
print("\n=== rotation alpha by year (annualized, non-overlapping 20d) — decay check ===")
print(yr[["ann_%", "count"]].round(1).to_string())

# decomposition share: how much of microcap total return is water vs rotation?
tot_idx = micro_lvl.iloc[-1] / micro_lvl.iloc[20] - 1
tot_wl = wl_lvl.iloc[-1] / wl_lvl.iloc[20] - 1
print(f"\nfull-sample cumulative: index {tot_idx*100:.0f}%  water-level {tot_wl*100:.0f}%")
print(f"water-level CAGR {((1+tot_wl)**(245/ (len(micro_lvl)-20))-1)*100:.1f}%  vs index CAGR ~37%")

alpha20.to_frame("alpha20").join(idx_ret20.rename("idx20")).join(wl_ret20.rename("wl20")).to_parquet(OUT / "waterlevel_alpha.parquet")
print("\nsaved -> waterlevel_alpha.parquet")
