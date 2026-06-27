# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Iteration 3: robustness + costs for S5 = (trend AND dd60<x) OR capitulation, out=div.

(1) Parameter grid around the defaults — is the modern-era win a plateau or a spike?
(2) Realistic transaction cost on the rotation OVERLAY (micro<->div switches), since
    the microcap index's own internal turnover is shared with buy-and-hold and not part
    of the timing comparison.
(3) Out-leg = div basket vs CSI300 (deployable as 红利ETF / 沪深300ETF).
Report IS 2014-26, the two modern sub-periods, and 2009-13. Defaults: dd 10%, MAlong 200,
capit 0.85/0.95.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "workspace" / "outputs" / "microcap_timing"
RF = 0.04
WINS = {"IS14-26": slice("2014-01-02", None), "14-19": slice("2014-01-02", "2019-12-31"),
        "20-26": slice("2020-01-01", None), "OOS09-13": slice("2009-01-05", "2013-12-31")}

micro = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")["ret"].fillna(0)
div = pd.read_parquet(OUT / "basket_div.parquet")["ret"].reindex(micro.index).fillna(0)
csi = pd.read_parquet(ROOT / "data" / "market" / "index" / "index_000300.SH.parquet")
csi["trade_date"] = pd.to_datetime(csi["trade_date"], format="%Y%m%d")
etf = (csi.set_index("trade_date")["pct_chg"] / 100).reindex(micro.index).fillna(0)
dates = micro.index
micro_lvl = (1 + micro).cumprod()


def stats(pr, w):
    pr = pr.loc[w]
    lv = (1 + pr).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    return round(ann * 100, 1), round(dd * 100, 1), round((ann - RF) / vol, 2)


def capit(lo, hi, ratio):
    s = np.zeros(len(ratio), dtype=bool)
    for t in range(len(ratio)):
        if np.isnan(ratio[t]):
            s[t] = False
        elif ratio[t] < lo:
            s[t] = True
        elif ratio[t] > hi:
            s[t] = False
        else:
            s[t] = s[t - 1] if t > 0 else False
    return s


def signal_S5(dd_x=0.10, ma_long=200, cap_lo=0.85, cap_hi=0.95):
    ma5 = micro_lvl.rolling(5).mean()
    mal = micro_lvl.rolling(ma_long).mean()
    ratio = (ma5 / mal).to_numpy()
    dd60 = (1 - micro_lvl / micro_lvl.rolling(60, min_periods=1).max()).to_numpy()
    cap = capit(cap_lo, cap_hi, ratio)
    in_micro = ((ratio > 1) & (dd60 < dd_x)) | cap
    return pd.Series(in_micro.astype(float), index=dates)


def run(wser, out_leg=div, cost=0.0):
    w = wser.shift(1).fillna(1.0)
    pr = w * micro + (1 - w) * out_leg
    if cost:
        pr = pr - w.diff().abs().fillna(0) * cost  # overlay switch turnover
    return pr, w


print("=== (1) S5 parameter robustness (out=div, no cost). cells = sub2020-26 ann/mdd/sharpe ===")
print("default dd=10 maL=200 cap=.85/.95")
for dd_x in (0.08, 0.10, 0.12, 0.15):
    line = []
    for ma_long in (150, 200, 250):
        pr, w = run(signal_S5(dd_x=dd_x, ma_long=ma_long))
        a = stats(pr, WINS["20-26"])
        line.append(f"maL{ma_long}:{a[0]}/{a[1]}/{a[2]}")
    print(f"  dd={int(dd_x*100):2d}%  " + "   ".join(line))

print("\n=== capitulation-band robustness (dd=10,maL=200), sub2020-26 ===")
for lo, hi in ((0.82, 0.92), (0.85, 0.95), (0.88, 0.96), (0.80, 0.90)):
    pr, w = run(signal_S5(cap_lo=lo, cap_hi=hi))
    print(f"  cap {lo}/{hi}: {stats(pr, WINS['20-26'])}")

print("\n=== (2) default S5 across all windows, with transaction cost on overlay ===")
hdr = "%-22s " + " ".join(["%-20s"] * len(WINS))
print(hdr % ("config", *WINS.keys()))
print(hdr % ("100% micro", *[str(stats(micro, v)) for v in WINS.values()]))
for cost in (0.0, 0.002, 0.005):
    pr, w = run(signal_S5(), cost=cost)
    flips = int(w.diff().abs().loc[WINS["IS14-26"]].sum())
    print(hdr % (f"S5 div cost={cost:.1%}", *[str(stats(pr, v)) for v in WINS.values()]) + f"  (IS flips~{flips})")

print("\n=== (3) out-leg = div vs CSI300 (deployable ETFs), default S5, cost 0.2% ===")
for lab, leg in (("div basket", div), ("CSI300", etf)):
    pr, w = run(signal_S5(), out_leg=leg, cost=0.002)
    print(hdr % (f"out={lab}", *[str(stats(pr, v)) for v in WINS.values()]))
