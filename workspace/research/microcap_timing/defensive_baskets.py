# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Build long-only defensive baskets and test the PRECONDITION for microcap<->defensive
rotation: does any positive-drift long asset actually hold up during microcap's worst
stretches? If none does, long-only rotation cannot beat buy-and-hold; if one does,
it's the 'out' leg that sidesteps the cash-whipsaw trap.

Baskets (monthly rebalance, equal weight, from existing panels — no shorting/leverage):
  - lowvol100 : lowest trailing-60d-vol 100 names among the larger-70% by mcap
  - div100    : highest dv_ttm 100 names among the larger-70% by mcap (needs dvttm panel)
  - csi300    : index return (from index file)
Microcap = the Guoren replica.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "workspace" / "outputs" / "microcap_timing"

ret = pd.read_parquet(OUT / "panel_ret.parquet").astype("float64")
mv = pd.read_parquet(OUT / "panel_total_mv.parquet").reindex_like(ret)
traded = pd.read_parquet(OUT / "panel_traded.parquet").reindex_like(ret).fillna(0)
dates = ret.index


def monthly_rebalance_dates(idx):
    s = pd.Series(idx, index=idx)
    return s.groupby([idx.year, idx.month]).first().to_numpy()


def build_basket(score, n=100, mcap_floor_pct=0.30, top=True):
    """Monthly-rebalanced equal-weight basket. score: dates x codes (higher=preferred if top)."""
    rb = monthly_rebalance_dates(dates)
    members = pd.DataFrame(False, index=dates, columns=ret.columns)
    cur = None
    rb_set = set(pd.Timestamp(d) for d in rb)
    for t in dates:
        if t in rb_set:
            mv_row = mv.loc[t]
            sc_row = score.loc[t]
            ok = mv_row.notna() & sc_row.notna() & (traded.loc[t] > 0)
            if ok.sum() > n:
                floor = mv_row[ok].quantile(mcap_floor_pct)
                elig = ok & (mv_row >= floor)
                sel = sc_row[elig].sort_values(ascending=not top).head(n).index
                cur = sel
        if cur is not None:
            members.loc[t, cur] = True
    # daily equal-weight return of held members (drop suspended/nan)
    out = []
    mvals = members.to_numpy()
    rvals = ret.to_numpy()
    for i in range(len(dates)):
        sel = mvals[i]
        r = rvals[i, sel]
        r = r[np.isfinite(r)]
        out.append(r.mean() if r.size else np.nan)
    return pd.Series(out, index=dates)


vol60 = ret.rolling(60, min_periods=40).std()
lowvol = build_basket(-vol60, n=100)  # highest -vol = lowest vol
lowvol.to_frame("ret").to_parquet(OUT / "basket_lowvol.parquet")

dv_path = OUT / "panel_dvttm.parquet"
if dv_path.exists():
    dv = pd.read_parquet(dv_path).reindex_like(ret)
    div = build_basket(dv, n=100)
    div.to_frame("ret").to_parquet(OUT / "basket_div.parquet")
else:
    div = pd.Series(np.nan, index=dates)
    print("(dvttm panel not ready yet; div basket skipped this run)")

csi = pd.read_parquet(ROOT / "data" / "market" / "index" / "index_000300.SH.parquet")
csi["trade_date"] = pd.to_datetime(csi["trade_date"], format="%Y%m%d")
etf = (csi.set_index("trade_date")["pct_chg"] / 100).reindex(dates).fillna(0)

micro = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")["ret"].fillna(0)

assets = {"microcap": micro, "lowvol100": lowvol.fillna(0), "div100": div.fillna(0), "csi300": etf}


def cum(s, w):
    return (1 + s.loc[w]).prod() - 1


# ---- PRECONDITION: behavior in microcap's worst windows ----
windows = {
    "2015-06 crash": ("2015-06-12", "2015-07-08"),
    "2016-01 circuit": ("2015-12-30", "2016-01-28"),
    "2018 bear": ("2018-01-24", "2018-10-18"),
    "2024-01/02 quant crash": ("2024-01-02", "2024-02-07"),
    "2025-04 tariff": ("2025-03-18", "2025-04-07"),
    "2011-12 slow bear": ("2011-04-18", "2012-01-06"),
}
print("=== PRECONDITION: asset return during microcap's worst windows (%) ===")
print("%-26s %9s %9s %9s %9s" % ("window", "microcap", "lowvol", "div", "csi300"))
for lab, (a, b) in windows.items():
    w = slice(a, b)
    print("%-26s %9.1f %9.1f %9.1f %9.1f" % (
        lab, cum(micro, w) * 100, cum(lowvol.fillna(0), w) * 100,
        cum(div.fillna(0), w) * 100 if div.notna().any() else float("nan"), cum(etf, w) * 100))

# ---- full-sample stats + correlation ----
def stats(s, w=slice("2014-01-02", None)):
    s = s.loc[w]
    lv = (1 + s).cumprod()
    nd = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / nd) - 1
    vol = s.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    return round(ann * 100, 1), round(dd * 100, 1), round((ann - 0.04) / vol, 2)


print("\n=== standalone stats (IS 2014+) and corr with microcap ===")
for k, v in assets.items():
    c_all = v.loc["2014-01-02":].corr(micro.loc["2014-01-02":])
    # downside corr: only on microcap-down days
    dn = micro.loc["2014-01-02":] < 0
    c_dn = v.loc["2014-01-02":][dn].corr(micro.loc["2014-01-02":][dn])
    print("%-12s ann/mdd/shp %-20s corr=%.2f  down-day corr=%.2f" % (k, str(stats(v)), c_all, c_dn))
print("\nNote: low corr + positive drift + holds-up-in-crash-windows = viable 'out' leg.")
