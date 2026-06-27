# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Iteration 2: REGIME-AWARE microcap<->dividend rotation.

Lead from rotation_v2: out=div beats out=cash, and dd-guard cuts IS MDD to -38.5 /
Sharpe 1.36, but every rotation loses on 2009-2013 because div was NOT a safe-haven
then (small & value both pure beta pre-2017). Fix: rotate to div ONLY when div is the
relative winner (idiosyncratic microcap stress), not in broad bears where div falls too.

S6 regime-aware: in micro UNLESS (micro own-weak) AND (div outperforming micro lately).
S7 continuous : w_micro = smooth f(div relative strength), gross=1 (rest in div).
Diagnostics: per-year, and 2014-2019 vs 2020-2026 sub-periods (modern robustness),
since 2009-2013 is a structurally different (pre-decoupling) era.
Defaults fixed a-priori; NOT searched on OOS (overfit guard).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "workspace" / "outputs" / "microcap_timing"
RF = 0.04
W = {"IS 2014-26": slice("2014-01-02", None), "OOS 2009-13": slice("2009-01-05", "2013-12-31"),
     "sub 2014-19": slice("2014-01-02", "2019-12-31"), "sub 2020-26": slice("2020-01-01", None)}

micro = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")["ret"].fillna(0)
div = pd.read_parquet(OUT / "basket_div.parquet")["ret"].reindex(micro.index).fillna(0)
dates = micro.index
micro_lvl, div_lvl = (1 + micro).cumprod(), (1 + div).cumprod()


def stats(pr, w):
    pr = pr.loc[w]
    lv = (1 + pr).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    return round(ann * 100, 1), round(dd * 100, 1), round((ann - RF) / vol, 2)


def rotate(w_micro):
    w = w_micro.shift(1).fillna(1.0)
    return w * micro + (1 - w) * div, w


ma5, ma200 = micro_lvl.rolling(5).mean(), micro_lvl.rolling(200).mean()
ratio = (ma5 / ma200).to_numpy()
dd60 = (1 - micro_lvl / micro_lvl.rolling(60, min_periods=1).max())
micro_weak = pd.Series((dd60.to_numpy() > 0.10) | (ratio < 1), index=dates)
rel40 = (1 + div).rolling(40).apply(np.prod, raw=True) - (1 + micro).rolling(40).apply(np.prod, raw=True)
div_winning = (rel40 > 0).fillna(False)


def capit():
    s = np.zeros(len(ratio), dtype=bool)
    for t in range(len(ratio)):
        if np.isnan(ratio[t]):
            s[t] = False
        elif ratio[t] < 0.85:
            s[t] = True
        elif ratio[t] > 0.95:
            s[t] = False
        else:
            s[t] = s[t - 1] if t > 0 else False
    return pd.Series(s, index=dates)


CAP = capit()

to_div = micro_weak & div_winning & (~CAP)
w_S6 = pd.Series(np.where(to_div, 0.0, 1.0), index=dates)

z_rel = (rel40 - rel40.rolling(250, min_periods=120).mean()) / rel40.rolling(250, min_periods=120).std()
tilt = (1 - (0.5 + 0.5 * np.tanh(z_rel)).clip(0, 1)).where(micro_weak, 1.0)
w_S7 = tilt.fillna(1.0).clip(0, 1)
w_S7 = w_S7.where(~CAP, 1.0)

bench = {
    "100% micro": pd.Series(1.0, index=dates),
    "S2 trend+capit->div": pd.Series(np.where((pd.Series(ratio > 1, index=dates) | CAP), 1.0, 0.0), index=dates),
    "S5 dd-guard->div": pd.Series(np.where(((pd.Series(ratio > 1, index=dates) & (dd60 < 0.10)) | CAP), 1.0, 0.0), index=dates),
}
print("=== regime-aware microcap<->dividend rotation. ann/mdd/sharpe per window ===")
cols = list(W.keys())
hdr = "%-26s " + " ".join(["%-21s"] * len(cols))
print(hdr % ("signal", *cols))
rows = {}
for lab, wser in {**bench, "S6 regime-aware->div": w_S6, "S7 continuous tilt->div": w_S7}.items():
    ws = wser if isinstance(wser, pd.Series) else pd.Series(wser, index=dates)
    pr, w = rotate(ws)
    rows[lab] = {k: stats(pr, v) for k, v in W.items()}
    print(hdr % (lab, *[str(rows[lab][k]) for k in cols]))

print("\n=== per-year return (%) and %micro ===")
for lab, wser in (("S5 dd-guard", bench["S5 dd-guard->div"]), ("S6 regime-aware", w_S6), ("S7 continuous", w_S7)):
    pr, w = rotate(wser)
    yr = ((1 + pr).groupby(pr.index.year).prod() - 1) * 100
    mc = ((1 + micro).groupby(micro.index.year).prod() - 1) * 100
    pm = w.groupby(w.index.year).mean() * 100
    tab = pd.DataFrame({"micro": mc.round(0), lab: yr.round(0), "%micro": pm.round(0)}).loc[2009:]
    print(f"\n[{lab}]")
    print(tab.to_string())
