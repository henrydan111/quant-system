# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Test alternative crowding definitions as a microcap risk-switch.

For each metric and each sign (HIGH=risk-off vs LOW=risk-off), run the same PIT
switch: z = (m - rolling_mean)/rolling_std over 250d; risk-off when z beyond +1.5
(or below -1.5); de-risk microcap to 50% + 50% CSI300 on T+1. Report IS/OOS and,
decisively, whether it fires on the 2024 microcap crash / now (2026).

Primary question: does any definition (esp. micro_turn_share = microcap own-crowding)
actually (a) cut the tail and (b) fire before/at the 2024 crash?
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT = PROJECT_ROOT / "workspace" / "outputs" / "microcap_timing"
RF = 0.04
IS_W = slice("2014-01-02", None)
OOS_W = slice("2009-01-05", "2013-12-31")

out = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")
micro_ret = out["ret"].fillna(0)
csi = pd.read_parquet(PROJECT_ROOT / "data" / "market" / "index" / "index_000300.SH.parquet")
csi["trade_date"] = pd.to_datetime(csi["trade_date"], format="%Y%m%d")
etf_ret = (csi.set_index("trade_date")["pct_chg"] / 100).reindex(micro_ret.index).fillna(0)

cv = pd.read_parquet(OUT / "concentration_v2.parquet").reindex(micro_ret.index)
METRICS = ["top5_amount", "micro_turn_share", "micro_turn_share_q10",
           "large_turn_share", "micro_internal_hhi", "micro_count_for_half"]


def zscore(s, w=250):
    m = s.rolling(w, min_periods=120).mean()
    sd = s.rolling(w, min_periods=120).std()
    return (s - m) / sd


def stats(pr, w, pos=None, cost=0.0):
    if pos is not None and cost:
        pr = pr - pos.diff().abs().fillna(0) * cost
    pr = pr.loc[w]
    lv = (1 + pr).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax()).sub(1).min()
    return round(ann * 100, 1), round(dd * 100, 1), round((ann - RF) / vol, 2)


def run_switch(z, high_is_off, k=1.5):
    ro = (z > k) if high_is_off else (z < -k)
    ro = ro.fillna(False)
    wm = pd.Series(np.where(ro, 0.5, 1.0), index=z.index).shift(1).fillna(1.0)
    we = pd.Series(np.where(ro, 0.5, 0.0), index=z.index).shift(1).fillna(0.0)
    pr = wm * micro_ret + we * etf_ret
    return pr, ro, wm


print("baseline untimed: IS", stats(micro_ret, IS_W), "OOS", stats(micro_ret, OOS_W))
print("\n%-24s %-4s %-18s %-18s %s" % ("metric", "sign", "IS ann/mdd/shp", "OOS ann/mdd/shp", "fire2024 / fire-now / off-days"))

# crash window & now references
crash24 = slice("2024-01-15", "2024-02-07")
now = micro_ret.index[-1]
rows = []
for metric in METRICS:
    z = zscore(cv[metric])
    for high_off in (True, False):
        pr, ro, wm = run_switch(z, high_off)
        a, b = stats(pr, IS_W), stats(pr, OOS_W)
        fired_24 = int(ro.loc[crash24].sum())
        fire_now = bool(ro.loc[now])
        off_is = int(ro.loc[IS_W].sum())
        sign = "↑off" if high_off else "↓off"
        flag = "  <<<" if (b[0] >= 38.9 and a[1] > -45) else ""  # OOS>=untimed AND tail cut
        print("%-24s %-4s %-18s %-18s %d / %s / %d%s" % (
            metric, sign, f"{a[0]}/{a[1]}/{a[2]}", f"{b[0]}/{b[1]}/{b[2]}",
            fired_24, fire_now, off_is, flag))
        rows.append({"metric": metric, "sign": sign, "IS_ann": a[0], "IS_mdd": a[1], "IS_shp": a[2],
                     "OOS_ann": b[0], "OOS_mdd": b[1], "OOS_shp": b[2],
                     "fire_2024crash": fired_24, "fire_now": fire_now})
pd.DataFrame(rows).to_csv(OUT / "concentration_v2_grid.csv", index=False)

# z-path of micro_turn_share through the 2023-2024 microcap top->crash
print("\n=== micro_turn_share z-path 2023-09 .. 2024-03 (does own-crowding peak BEFORE the crash?) ===")
z_micro = zscore(cv["micro_turn_share"])
seg = z_micro.loc["2023-09-01":"2024-03-15"]
monthly = seg.groupby([seg.index.year, seg.index.month]).agg(["mean", "max"]).round(2)
print(monthly.to_string())
print("\nmicro_turn_share level: 2021 mean %.3f / 2023H2 mean %.3f / 2024-01 mean %.3f / latest %.3f" % (
    cv["micro_turn_share"].loc["2021"].mean(), cv["micro_turn_share"].loc["2023-07":"2023-12"].mean(),
    cv["micro_turn_share"].loc["2024-01"].mean(), cv["micro_turn_share"].iloc[-1]))
print("z at key dates micro_turn_share:")
for d in ["2023-12-29", "2024-01-31", "2024-02-05", "2025-04-07", "2026-02-27"]:
    if pd.Timestamp(d) in z_micro.index:
        print(f"  {d}: level={cv['micro_turn_share'].loc[d]:.3f} z={z_micro.loc[d]:+.2f}")
