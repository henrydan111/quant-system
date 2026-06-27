# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Concentration risk-switch timing (小红书 idea): de-risk microcap when turnover
concentration spikes above its trailing mean + k*std.

Rule (PIT): conc[T] = top-5% turnover share, known at T close. threshold[T] =
rolling_mean(conc, W)[T] + k*rolling_std(conc, W)[T] (trailing, through T). If
conc[T] > threshold[T] -> risk-OFF from T+1: hold 50% microcap + 50% ETF(CSI300)
or cash. Else full microcap. Gross <= 1 (no leverage).

Windows: IS 2014-01-02..end, OOS 2009-01-05..2013-12-31. Also: orthogonality to the
price rules (combine with v4), and 2021/2024 firing diagnostics.
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
level = out["level"]

csi = pd.read_parquet(PROJECT_ROOT / "data" / "market" / "index" / "index_000300.SH.parquet")
csi["trade_date"] = pd.to_datetime(csi["trade_date"], format="%Y%m%d")
etf_ret = (csi.set_index("trade_date")["pct_chg"] / 100.0).reindex(micro_ret.index).fillna(0)

conc = pd.read_parquet(OUT / "concentration.parquet")["conc_top5"].reindex(micro_ret.index)

# price-rule v4 position for orthogonality test
ma5, ma200 = level.rolling(5).mean(), level.rolling(200).mean()
ratio = ma5 / ma200
rarr = ratio.to_numpy()


def cap_state(lo=0.85, hi=0.95):
    s = np.zeros(len(rarr), dtype=bool)
    for t in range(len(rarr)):
        if np.isnan(rarr[t]):
            s[t] = False
        elif rarr[t] < lo:
            s[t] = True
        elif rarr[t] > hi:
            s[t] = False
        else:
            s[t] = s[t - 1] if t > 0 else False
    return s


dd_ok = ((1 - level / level.rolling(60, min_periods=1).max()) < 0.10).to_numpy()
v4_in = pd.Series(((rarr > 1) & dd_ok) | cap_state(), index=level.index)


def risk_off(window, k):
    """Boolean risk-off at T close (PIT trailing threshold)."""
    if window == "expanding":
        m = conc.expanding(min_periods=60).mean()
        s = conc.expanding(min_periods=60).std()
    else:
        m = conc.rolling(window, min_periods=max(60, window // 2)).mean()
        s = conc.rolling(window, min_periods=max(60, window // 2)).std()
    return (conc > (m + k * s)).fillna(False)


def stats(pr, w, cost=0.0, pos=None):
    if pos is not None:
        pr = pr - pos.diff().abs().fillna(0) * cost
    pr = pr.loc[w]
    lv = (1 + pr).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax()).sub(1).min()
    return round(ann * 100, 1), round(dd * 100, 1), round((ann - RF) / vol, 2)


def build(window, k, derisk_to=0.5, etf="csi300"):
    ro = risk_off(window, k)
    w_micro = pd.Series(np.where(ro, derisk_to, 1.0), index=conc.index).shift(1).fillna(1.0)
    w_etf = pd.Series(np.where(ro, 1.0 - derisk_to, 0.0), index=conc.index).shift(1).fillna(0.0)
    if etf == "cash":
        w_etf *= 0
    pr = w_micro * micro_ret + w_etf * etf_ret
    return pr, w_micro, ro


print("baselines: untimed IS", stats(micro_ret, IS_W), "OOS", stats(micro_ret, OOS_W))
print("v4 price-rule: IS", stats(micro_ret * v4_in.shift(1).fillna(0), IS_W),
      "OOS", stats(micro_ret * v4_in.shift(1).fillna(0), OOS_W))

print("\n=== concentration risk-switch grid (derisk to 50%, ETF=CSI300) ===")
print("%-22s %-20s %-20s %s" % ("config", "IS ann/mdd/shp", "OOS ann/mdd/shp", "risk-off days IS/OOS"))
rows = []
for window in (250, 500, "expanding"):
    for k in (1.0, 1.5, 2.0):
        pr, wm, ro = build(window, k)
        a, b = stats(pr, IS_W), stats(pr, OOS_W)
        nis = int(ro.loc[IS_W].sum())
        noos = int(ro.loc[OOS_W].sum())
        lab = f"W={window} k={k}"
        print("%-22s %-20s %-20s %d/%d" % (lab, f"{a[0]}/{a[1]}/{a[2]}", f"{b[0]}/{b[1]}/{b[2]}", nis, noos))
        rows.append({"config": lab, "IS_ann": a[0], "IS_mdd": a[1], "IS_shp": a[2],
                     "OOS_ann": b[0], "OOS_mdd": b[1], "OOS_shp": b[2], "off_IS": nis, "off_OOS": noos})
pd.DataFrame(rows).to_csv(OUT / "concentration_grid.csv", index=False)

# ETF vs cash leg, representative W=250 k=1.5
print("\n=== ETF(CSI300) vs cash leg, W=250 k=1.5 ===")
for etf in ("csi300", "cash"):
    pr, wm, ro = build(250, 1.5, etf=etf)
    print(f"  rest->{etf:7s}: IS {stats(pr, IS_W)}  OOS {stats(pr, OOS_W)}")

# full exit (0%) vs 50%
print("\n=== derisk depth, W=250 k=1.5, ETF=CSI300 ===")
for d in (0.5, 0.25, 0.0):
    pr, wm, ro = build(250, 1.5, derisk_to=d)
    print(f"  micro->{int(d*100)}%: IS {stats(pr, IS_W)}  OOS {stats(pr, OOS_W)}")

# orthogonality: combine concentration switch with v4 price rule (multiply microcap weight by v4_in)
print("\n=== combine: v4 price-rule AND concentration switch (W=250 k=1.5, ETF=CSI300) ===")
ro = risk_off(250, 1.5)
w_micro = pd.Series(np.where(ro, 0.5, 1.0), index=conc.index) * v4_in.astype(float)
w_etf = pd.Series(np.where(ro, 0.5, 0.0), index=conc.index)
pr_comb = (w_micro * micro_ret + w_etf * etf_ret).reindex(micro_ret.index)
pr_comb = (w_micro.shift(1).fillna(0) * micro_ret + w_etf.shift(1).fillna(0) * etf_ret)
print("  combined: IS", stats(pr_comb, IS_W), " OOS", stats(pr_comb, OOS_W))

# yearly + firing diagnostics
ro = risk_off(250, 1.5)
yearly_off = ro.groupby(ro.index.year).sum()
pr, wm, _ = build(250, 1.5)
yr = pd.DataFrame({
    "index": (1 + micro_ret).groupby(micro_ret.index.year).prod() - 1,
    "conc_switch": (1 + pr).groupby(pr.index.year).prod() - 1,
    "risk_off_days": yearly_off,
}).loc[2009:]
yr["edge_pp"] = (yr["conc_switch"] - yr["index"]) * 100
print("\n=== yearly (W=250 k=1.5, ETF=CSI300) ===")
print((yr[["index", "conc_switch"]] * 100).round(1).join(yr[["risk_off_days", "edge_pp"]].round(1)).to_string())

# 2021 crowding peak / 2024 microcap crash / 2026 current
print("\n=== conc level & z-score at key dates (W=250) ===")
m = conc.rolling(250, min_periods=120).mean()
sd = conc.rolling(250, min_periods=120).std()
z = (conc - m) / sd
for d in ["2021-01-08", "2021-02-10", "2024-01-31", "2024-02-05", "2025-04-07", "2026-02-27"]:
    if pd.Timestamp(d) in conc.index:
        print(f"  {d}: conc={conc.loc[d]:.3f} z={z.loc[d]:+.2f} risk_off={bool(z.loc[d] > 1.5)}")
print(f"\nconc range full sample: {conc.min():.3f}..{conc.max():.3f}, latest(2026-02-27)={conc.iloc[-1]:.3f}")
