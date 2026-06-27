# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Concentration as a SIZE-ROTATION timing signal (microcap <-> CSI300), not a
risk-off switch.

Lead from test_concentration_v2: large_turn_share level has the only monotone,
material link to microcap forward returns (corr +0.13), and it is CONTRARIAN —
high large-cap turnover crowding precedes microcap STRENGTH. The correct use is
therefore a rotation: hold microcap when large-cap is crowded, rotate to CSI300
when turnover broadens.

Tests, all PIT (metric at T close, trailing z, rotate T+1), IS 2014+ / OOS 2009-13:
 1. Does large_turn_share predict the microcap-MINUS-CSI300 spread? (the rotation premise)
 2. Binary size rotation on several metrics & signs & thresholds.
 3. Alternative constructions: 20d change, detrend (level - 250d MA), to beat the
    slow-buildup problem that defeats trailing-z on a 2y crowding ramp.
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
micro = out["ret"].fillna(0)
csi = pd.read_parquet(PROJECT_ROOT / "data" / "market" / "index" / "index_000300.SH.parquet")
csi["trade_date"] = pd.to_datetime(csi["trade_date"], format="%Y%m%d")
etf = (csi.set_index("trade_date")["pct_chg"] / 100).reindex(micro.index).fillna(0)
cv = pd.read_parquet(OUT / "concentration_v2.parquet").reindex(micro.index)


def stats(pr, w):
    pr = pr.loc[w]
    lv = (1 + pr).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax()).sub(1).min()
    return round(ann * 100, 1), round(dd * 100, 1), round((ann - RF) / vol, 2)


# ---------- 1. does large_turn_share predict micro - csi300 spread? ----------
spread = micro - etf
fwd20 = (1 + spread).rolling(20).apply(np.prod, raw=True).shift(-20) - 1  # approx rel spread
print("=== microcap-minus-CSI300 fwd-20d spread by large_turn_share PIT percentile (IS2014+) ===")
pct = cv["large_turn_share"].expanding(min_periods=250).rank(pct=True)
df = pd.DataFrame({"pct": pct, "sp": fwd20}).dropna().loc["2014-01-02":]
df["b"] = pd.cut(df["pct"], [0, 0.2, 0.4, 0.6, 0.8, 1.0], labels=["p0-20", "20-40", "40-60", "60-80", "p80-100"])
print((df.groupby("b", observed=True)["sp"].agg(["mean", "count"]) * [100, 1]).round(2).to_string())


def zser(s, w=250):
    return (s - s.rolling(w, min_periods=120).mean()) / s.rolling(w, min_periods=120).std()


def rotation(signal_in_micro):
    """signal_in_micro: bool series, True=hold microcap else CSI300. Position T+1."""
    pos = signal_in_micro.shift(1).fillna(True)
    return pos * micro + (~pos) * etf, pos


print("\nbaselines: untimed-micro IS", stats(micro, IS_W), "OOS", stats(micro, OOS_W),
      "| CSI300 IS", stats(etf, IS_W), "OOS", stats(etf, OOS_W))

# ---------- 2. binary size rotation ----------
print("\n=== size rotation: in MICROCAP when z(metric) > k (else CSI300) ===")
print("%-22s %-6s %-18s %-18s %s" % ("metric", "k", "IS ann/mdd/shp", "OOS ann/mdd/shp", "%micro IS/OOS"))
rows = []
for metric in ["large_turn_share", "top5_amount", "micro_turn_share"]:
    z = zser(cv[metric])
    for k in (-0.5, 0.0, 0.5, 1.0):
        in_micro = (z > k).fillna(True)
        pr, pos = rotation(in_micro)
        a, b = stats(pr, IS_W), stats(pr, OOS_W)
        pm_is = round(pos.loc[IS_W].mean() * 100)
        pm_oos = round(pos.loc[OOS_W].mean() * 100)
        flag = "  <<<" if (a[0] > 36.9 and b[0] > 38.9) else ""
        print("%-22s %-6s %-18s %-18s %d/%d%s" % (metric, f">{k}", f"{a[0]}/{a[1]}/{a[2]}",
              f"{b[0]}/{b[1]}/{b[2]}", pm_is, pm_oos, flag))
        rows.append({"metric": metric, "k": k, "IS_ann": a[0], "IS_mdd": a[1], "IS_shp": a[2],
                     "OOS_ann": b[0], "OOS_mdd": b[1], "OOS_shp": b[2]})
pd.DataFrame(rows).to_csv(OUT / "size_rotation_grid.csv", index=False)

# ---------- 3. alternative constructions on large_turn_share ----------
print("\n=== large_turn_share alternative constructions (rotation in-micro when signal high) ===")
lt = cv["large_turn_share"]
constructions = {
    "level z>0.5": (zser(lt) > 0.5),
    "level z>1.0": (zser(lt) > 1.0),
    "20d change>0": (lt.diff(20) > 0),
    "detrend>0 (lvl-250MA)": ((lt - lt.rolling(250, min_periods=120).mean()) > 0),
    "detrend z>0.5": (zser(lt - lt.rolling(250, min_periods=120).mean(), 250) > 0.5),
    "above 60d MA": (lt > lt.rolling(60, min_periods=20).mean()),
}
for lab, sig in constructions.items():
    pr, pos = rotation(sig.fillna(True))
    print("  %-24s IS %s  OOS %s  %%micro %d/%d" % (
        lab, stats(pr, IS_W), stats(pr, OOS_W),
        round(pos.loc[IS_W].mean() * 100), round(pos.loc[OOS_W].mean() * 100)))

# ---------- 4. the winner's behavior in 2024/2026 + yearly ----------
best = (zser(cv["large_turn_share"]) > 0.0).fillna(True)
pr, pos = rotation(best)
yr = pd.DataFrame({
    "micro": (1 + micro).groupby(micro.index.year).prod() - 1,
    "rotation": (1 + pr).groupby(pr.index.year).prod() - 1,
    "pct_micro": pos.groupby(pos.index.year).mean(),
}).loc[2009:]
yr["edge_pp"] = (yr["rotation"] - yr["micro"]) * 100
print("\n=== yearly: rotation (in-micro when large_turn z>0, else CSI300) ===")
print((yr[["micro", "rotation"]] * 100).round(1).join((yr["pct_micro"] * 100).round(0)).join(yr["edge_pp"].round(1)).to_string())
print("\nin microcap now (2026-02-27)?:", bool(pos.iloc[-1]), "| large_turn_share z latest %.2f" % zser(cv['large_turn_share']).iloc[-1])
