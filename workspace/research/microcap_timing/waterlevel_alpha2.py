# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Part 2: what the rotation alpha IS, whether it survives cost, and whether it can time.

(A) Mechanism: the smallest-400 equal-weight DAILY-rebalanced index harvests a
    reconstitution/reversal premium. Measure the basket's one-way daily turnover
    (membership churn + equal-weight reset) and the cost drag on the 27%/yr gross alpha.
(B) Robustness of the water-level choice: rank-100 vs the average cap of the actual
    smallest-400 basket (rank-100 is a moving percentile as the universe grows 1500->5400).
(C) Timing: does the 20d rotation-alpha predict FORWARD microcap returns (mean-revert?
    momentum?), or is it pure attribution?
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "workspace" / "outputs" / "microcap_timing"

micro = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")["ret"].fillna(0)
ret = pd.read_parquet(OUT / "panel_ret.parquet").astype("float64").reindex(micro.index)
mv = pd.read_parquet(OUT / "panel_total_mv.parquet").reindex(micro.index)
traded = pd.read_parquet(OUT / "panel_traded.parquet").reindex(micro.index).fillna(0)
dates = micro.index
N = 400

# rebuild smallest-400 membership (traded, valid mv) to measure turnover + avg cap
mv_np = mv.ffill().to_numpy()
tr_np = traded.to_numpy()
members = np.zeros((len(dates), mv.shape[1]), dtype=bool)
avg400 = np.full(len(dates), np.nan)
for i in range(len(dates)):
    row = mv_np[i].copy()
    row[(tr_np[i] == 0)] = np.inf  # untraded can't be selected
    row[~np.isfinite(row)] = np.inf
    row[row <= 0] = np.inf
    k = min(N, int(np.isfinite(row).sum()))
    if k == 0:
        continue
    idx = np.argpartition(row, k - 1)[:k]
    members[i, idx] = True
    sel = mv_np[i][idx]
    avg400[i] = np.nanmean(sel[np.isfinite(sel)])

# (A) turnover: membership churn per day
churn = np.zeros(len(dates))
for i in range(1, len(dates)):
    a, b = members[i - 1], members[i]
    churn[i] = np.logical_xor(a, b).sum() / (2 * N)  # one-way fraction replaced
churn = pd.Series(churn, index=dates)
ann_member_turnover = churn.loc["2014-01-02":].mean() * 245
print("=== (A) turnover & cost drag on the rotation alpha ===")
print(f"mean daily MEMBERSHIP churn (one-way): {churn.loc['2014-01-02':].mean()*100:.2f}%  "
      f"-> annual ~{ann_member_turnover*100:.0f}%")

# equal-weight reset turnover for HELD names: weights drift by daily return, reset to 1/k
# approx one-way EW-reset turnover = 0.5 * mean(|r_i - rbar|) over held names each day
ew_turn = []
rnp = ret.to_numpy()
for i in range(1, len(dates)):
    sel = members[i - 1]  # held into day i
    r = rnp[i, sel]
    r = r[np.isfinite(r)]
    if r.size:
        ew_turn.append(0.5 * np.mean(np.abs(r - r.mean())))
ew_turn = pd.Series(ew_turn, index=dates[1:])
ann_ew = ew_turn.loc["2014-01-02":].mean() * 245
print(f"mean daily EW-RESET turnover (one-way): {ew_turn.loc['2014-01-02':].mean()*100:.2f}%  "
      f"-> annual ~{ann_ew*100:.0f}%")
tot_ann_turn = ann_member_turnover + ann_ew
print(f"TOTAL one-way annual turnover ~{tot_ann_turn*100:.0f}%")
for c in (0.001, 0.002, 0.003, 0.005):
    print(f"  cost {c*100:.1f}%/side -> drag ~{tot_ann_turn*c*100:.1f}%/yr  => net rotation alpha ~{27.0 - tot_ann_turn*c*100:.0f}%/yr")

# (B) water-level choice robustness: rank-100 vs avg of smallest-400
micro_lvl = (1 + micro).cumprod()
wl_rank100 = pd.read_parquet(OUT / "waterlevel_alpha.parquet")["wl20"]  # already 20d change
avg400s = pd.Series(avg400, index=dates).ffill()
wl_avg400_20 = avg400s / avg400s.shift(20) - 1
idx20 = micro_lvl / micro_lvl.shift(20) - 1
alpha_rank100 = (idx20 - wl_rank100).dropna()
alpha_avg400 = (idx20 - wl_avg400_20).dropna()
print("\n=== (B) water-level definition robustness ===")
print(f"alpha vs rank-100 water : mean20 {alpha_rank100.mean()*100:+.2f}%  ann {((1+alpha_rank100.mean())**12-1)*100:.0f}%")
print(f"alpha vs avg-of-400     : mean20 {alpha_avg400.mean()*100:+.2f}%  ann {((1+alpha_avg400.mean())**12-1)*100:.0f}%")
print(f"avg-400 cap 20d drift mean: {wl_avg400_20.mean()*100:+.2f}%  (vs rank-100 {wl_rank100.mean()*100:+.2f}%)")

# (C) timing: does 20d rotation alpha predict forward 20d microcap return?
alpha20 = (idx20 - wl_rank100)
fwd20 = micro_lvl.shift(-20) / micro_lvl - 1
df = pd.DataFrame({"a": alpha20, "fwd": fwd20}).dropna().loc["2014-01-02":]
print("\n=== (C) timing usability ===")
print(f"corr(rotation_alpha_20d, FORWARD 20d microcap return) = {df['a'].corr(df['fwd']):+.3f}")
print(f"corr(rotation_alpha_20d, FORWARD 20d rotation alpha)  = "
      f"{pd.DataFrame({'a':alpha20,'fa':alpha20.shift(-20)}).dropna().loc['2014-01-02':].corr().iloc[0,1]:+.3f}")
q = pd.qcut(df["a"], 5, labels=["Q1低","Q2","Q3","Q4","Q5高"])
print("forward 20d microcap return by current rotation-alpha quintile (%):")
print((df.groupby(q, observed=True)["fwd"].mean() * 100).round(2).to_string())
