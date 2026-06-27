# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Use the rotation-alpha / water-level GAP as a forward timing signal.

Baseline already known: contemporaneous 20d alpha has ~0 forward corr (-0.04) and is
not autocorrelated. Here we test DERIVED signals the user proposed — using accumulated
past alpha to judge how stretched the index is vs its water-level floor, to predict
mean reversion:

  S_A engine-speed : trailing alpha rate (is the rotation engine stalling, e.g. 2023-24)
  S_B stretch      : (index/water) detrended by own MA, z -> microcap over-extended vs floor
  S_C alpha-DD     : cumulative-alpha curve in drawdown -> engine impaired

For each: (1) forward 20d/60d predictive correlation; (2) timing overlay = rotate
microcap->dividend when the signal says risk-off, IS 2014+ / OOS 2009-13.
Discipline: few well-motivated forms, report honestly (the -0.04 baseline says expect little).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "workspace" / "outputs" / "microcap_timing"
RF = 0.04
IS_W = slice("2014-01-02", None)
OOS_W = slice("2009-01-05", "2013-12-31")

micro = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")["ret"].fillna(0)
div = pd.read_parquet(OUT / "basket_div.parquet")["ret"].reindex(micro.index).fillna(0)
mv = pd.read_parquet(OUT / "panel_total_mv.parquet").reindex(micro.index)
traded = pd.read_parquet(OUT / "panel_traded.parquet").reindex(micro.index).fillna(0)
dates = micro.index
micro_lvl = (1 + micro).cumprod()

# water level (rank-100) daily
mv_np, tr_np = mv.to_numpy(), traded.to_numpy()
water = np.full(len(dates), np.nan)
for i in range(len(dates)):
    row = mv_np[i].copy()
    row[tr_np[i] == 0] = np.nan
    v = row[np.isfinite(row) & (row > 0)]
    if v.size >= 100:
        water[i] = np.sort(v)[99]
water = pd.Series(water, index=dates).ffill()

# daily rotation alpha (index daily ret - water daily ret), cumulative alpha curve
water_ret = water / water.shift(1) - 1
alpha_daily = (micro - water_ret).fillna(0)
alpha_curve = (1 + alpha_daily).cumprod()
gap = micro_lvl / water  # index vs floor (always-up trend)


def z(s, w=250):
    return (s - s.rolling(w, min_periods=120).mean()) / s.rolling(w, min_periods=120).std()


# signals (all PIT, value at T)
S = {}
for n in (60, 120, 250):
    S[f"A engine-speed {n}d"] = z(alpha_curve / alpha_curve.shift(n) - 1)        # high=fast engine
S["B stretch gap/MA250"] = z(gap / gap.rolling(250, min_periods=120).mean())     # high=over-extended
S["B stretch gap/MA500"] = z(gap / gap.rolling(500, min_periods=200).mean())
S["C alpha-drawdown"] = (alpha_curve / alpha_curve.cummax() - 1)                 # 0=peak, <0 in DD

# forward predictive correlation
fwd20 = micro_lvl.shift(-20) / micro_lvl - 1
fwd60 = micro_lvl.shift(-60) / micro_lvl - 1
print("=== (1) forward predictive power of each signal (IS 2014+) ===")
print("%-24s %10s %10s" % ("signal", "corr fwd20", "corr fwd60"))
for lab, s in S.items():
    df = pd.DataFrame({"s": s, "f20": fwd20, "f60": fwd60}).dropna().loc[IS_W]
    print("%-24s %+10.3f %+10.3f" % (lab, df["s"].corr(df["f20"]), df["s"].corr(df["f60"])))


def stats(pr, w):
    pr = pr.loc[w]
    lv = (1 + pr).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    return round(ann * 100, 1), round(dd * 100, 1), round((ann - RF) / vol, 2)


def overlay(risk_off):
    """risk_off bool at T -> hold dividend T+1, else microcap."""
    w = (~risk_off).shift(1).fillna(True).astype(float)
    return w * micro + (1 - w) * div, w


print("\n=== (2) timing overlay (risk-off -> dividend). micro bench: IS %s OOS %s ===" % (
    stats(micro, IS_W), stats(micro, OOS_W)))
print("%-26s %-6s %-20s %-20s %s" % ("signal", "thr", "IS", "OOS", "%offIS"))
# engine-speed: off when speed LOW (stalling). stretch: off when HIGH. alpha-DD: off when deep DD.
specs = [
    ("A engine-speed 120d", S["A engine-speed 120d"], "low", (-0.5, -1.0)),
    ("A engine-speed 250d", S["A engine-speed 250d"], "low", (-0.5, -1.0)),
    ("B stretch gap/MA250", S["B stretch gap/MA250"], "high", (0.5, 1.0)),
    ("B stretch gap/MA500", S["B stretch gap/MA500"], "high", (0.5, 1.0)),
    ("C alpha-drawdown", S["C alpha-drawdown"], "ddown", (-0.10, -0.20)),
]
for lab, s, direction, thrs in specs:
    for thr in thrs:
        if direction == "low":
            ro = (s < thr).fillna(False)
        elif direction == "high":
            ro = (s > thr).fillna(False)
        else:  # alpha drawdown deeper than thr
            ro = (s < thr).fillna(False)
        pr, w = overlay(ro)
        a, b = stats(pr, IS_W), stats(pr, OOS_W)
        off = round(ro.loc[IS_W].mean() * 100)
        flag = "  <<<" if (a[2] > 1.28 and b[2] > 1.12) else ""  # beat the S5 methodology both windows
        print("%-26s %-6s %-20s %-20s %d%%%s" % (lab, thr, str(a), str(b), off, flag))

# reference: the S5 dividend methodology (price-based) for comparison
ma5, ma200 = micro_lvl.rolling(5).mean(), micro_lvl.rolling(200).mean()
ratio = (ma5 / ma200).to_numpy()
dd60 = (1 - micro_lvl / micro_lvl.rolling(60, min_periods=1).max()).to_numpy()
cap = np.zeros(len(ratio), dtype=bool)
for t in range(len(ratio)):
    cap[t] = False if np.isnan(ratio[t]) else (True if ratio[t] < 0.85 else (False if ratio[t] > 0.95 else (cap[t-1] if t else False)))
in_m = pd.Series((((ratio > 1) & (dd60 < 0.10)) | cap), index=dates)
pr5, _ = overlay(~in_m)
print("\nref S5 price-methodology -> div: IS %s OOS %s" % (stats(pr5, IS_W), stats(pr5, OOS_W)))
