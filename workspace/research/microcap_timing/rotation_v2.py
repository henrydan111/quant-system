# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Core experiment: microcap <-> DIVIDEND rotation (long-only, no leverage, no short).

The 'out' leg is the dividend basket (12.9% ann, holds up in the 2024-type idiosyncratic
microcap crash), NOT cash. Hypothesis: this fixes the two failures of every prior timing
rule — (a) V-recovery whipsaw is cheaper (div drifts +10%/yr, not 0), (b) the 2024-style
microcap-specific crash is genuinely dodged (div diverges).

Signals (PIT, decide at T close on index levels, position T+1):
  S1 abs-trend   : micro if MA5(micro)>MA200(micro) else div          (v1, out=div)
  S2 abs+capit   : S1 OR capitulation(micro ratio<0.85..0.95)         (v2, out=div)
  S3 rel-mom     : micro if micro_Nd_return > div_Nd_return else div   (relative strength)
  S4 rel-mom-MA  : micro if MA(micro/div, s) > MA(micro/div, l) else div
  S5 dd-guard    : micro if (trend AND dd60<10%) else div             (v4, out=div)
Benchmarks: 100% micro, 100% div, static 50/50 (no timing).
IS 2014+, OOS 2009-2013. Success = higher Sharpe AND lower MDD than 100% micro on BOTH,
ideally beating the static blend (timing adds value beyond diversification).
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
lowvol = pd.read_parquet(OUT / "basket_lowvol.parquet")["ret"].reindex(micro.index).fillna(0)
dates = micro.index

micro_lvl = (1 + micro).cumprod()
div_lvl = (1 + div).cumprod()


def stats(pr, w, pos=None, cost=0.0):
    if pos is not None and cost:
        pr = pr - pos.diff().abs().fillna(0) * cost
    pr = pr.loc[w]
    lv = (1 + pr).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    return round(ann * 100, 1), round(dd * 100, 1), round((ann - RF) / vol, 2)


def rotate(in_micro, out_leg=div):
    pos = in_micro.shift(1).fillna(True).astype(float)
    return pos * micro + (1 - pos) * out_leg, pos


# signals
ma5, ma200 = micro_lvl.rolling(5).mean(), micro_lvl.rolling(200).mean()
ratio = ma5 / ma200
rarr = ratio.to_numpy()
trend = pd.Series(rarr > 1, index=dates)


def capit():
    s = np.zeros(len(rarr), dtype=bool)
    for t in range(len(rarr)):
        if np.isnan(rarr[t]):
            s[t] = False
        elif rarr[t] < 0.85:
            s[t] = True
        elif rarr[t] > 0.95:
            s[t] = False
        else:
            s[t] = s[t - 1] if t > 0 else False
    return pd.Series(s, index=dates)


CAP = capit()
dd60_ok = pd.Series((1 - micro_lvl / micro_lvl.rolling(60, min_periods=1).max()) < 0.10, index=dates)

signals = {
    "100% micro (bench)": pd.Series(True, index=dates),
    "S1 trend->div": trend,
    "S2 trend+capit->div": (trend | CAP),
    "S5 dd-guard->div": ((trend & dd60_ok) | CAP),
}
# relative-momentum signals
for N in (60, 120, 250):
    rm = ((1 + micro).rolling(N).apply(np.prod, raw=True) > (1 + div).rolling(N).apply(np.prod, raw=True))
    signals[f"S3 rel-mom {N}d->div"] = rm.fillna(True)
for s_, l_ in ((20, 120), (20, 200)):
    rr = (micro_lvl / div_lvl)
    rm = rr.rolling(s_).mean() > rr.rolling(l_).mean()
    signals[f"S4 rel-mom-MA {s_}/{l_}->div"] = rm.fillna(True)

print("=== microcap <-> dividend rotation (out=div100). ann/mdd/sharpe ===")
print("%-30s %-20s %-20s %s" % ("signal", "IS", "OOS", "%micro IS/OOS | 2024"))
results = {}
for lab, sig in signals.items():
    pr, pos = rotate(sig)
    a, b = stats(pr, IS_W), stats(pr, OOS_W)
    pm_is, pm_oos = round(pos.loc[IS_W].mean() * 100), round(pos.loc[OOS_W].mean() * 100)
    r2024 = (1 + pr.loc["2024"]).prod() - 1
    results[lab] = (a, b)
    win = "  <<<" if (a[2] > 1.09 and a[1] > -47.8 and b[2] > 1.22 and b[1] > -35.2) else ""
    print("%-30s %-20s %-20s %d/%d | %+.0f%%%s" % (lab, str(a), str(b), pm_is, pm_oos, r2024 * 100, win))

# benchmarks: 100% div, static 50/50
for lab, pr in (("100% div", div), ("static 50/50 micro+div", 0.5 * micro + 0.5 * div)):
    print("%-30s %-20s %-20s %s" % (lab, str(stats(pr, IS_W)), str(stats(pr, OOS_W)), "(no timing)"))

print("\nout-leg sensitivity (best signal S2) with out=lowvol vs div vs cash:")
for lab, out_leg in (("div", div), ("lowvol", lowvol), ("cash", pd.Series(0.0, index=dates))):
    pr, pos = rotate(trend | CAP, out_leg=out_leg)
    print("  out=%-7s IS %s  OOS %s" % (lab, stats(pr, IS_W), stats(pr, OOS_W)))
