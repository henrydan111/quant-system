"""ML max-return with the FULL ~135-feature catalog (the last lever). Same walk-forward GBM,
rank target, defensive + smallmid universes, top-K, unlevered. Vs 31-feature ML + the rule.
"""
from __future__ import annotations
import json, gc
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru
from src.alpha_research.model_zoo import LightGBMModel

OUT = JR.OUT
LGB = dict(objective="regression", metric="mse", num_leaves=63, max_depth=6, learning_rate=0.02,
           min_child_samples=200, subsample=0.8, subsample_freq=1, colsample_bytree=0.7,
           reg_lambda=5.0, reg_alpha=1.0, verbose=-1, n_jobs=4)
BT_START, BT_END = "2017-01-01", "2026-02-27"

print("loading rich features...", flush=True)
F = pd.read_parquet(OUT/"full_features.parquet")
fwd = pd.read_parquet(OUT/"full_fwd.parquet")["fwd_20d"]
print(f"  features {F.shape}", flush=True)
FEATS = [c for c in F.columns if F[c].notna().mean() > 0.3]   # drop near-empty cols
print(f"  usable feature cols: {len(FEATS)}", flush=True)
DATE = F.index.get_level_values(0)
liqr = F["liq_log_dollar_vol"].groupby(DATE).rank(pct=True)
szr = F["size_ln_mcap"].groupby(DATE).rank(pct=True)
UNIS = {
    "defensive":  (liqr>=0.40) & (F["qual_roa"]>0),
    "smallmid_q": (szr>=0.05) & (szr<=0.70) & (liqr>=0.30) & (F["qual_roa"]>0),
}
cal = ru.trading_calendar(); WK=set(cal[::5])
rebal = ru.monthly_rebalance_dates(BT_START,BT_END); RB=set(rebal)

def run(uname, umask):
    umask = umask.fillna(False)
    Fu = F.loc[umask, FEATS]; fwdu = fwd.reindex(Fu.index); du = Fu.index.get_level_values(0)
    Xr = Fu.groupby(du).rank(pct=True); y = fwdu.groupby(du).rank(pct=True)
    ok = (Xr.notna().mean(axis=1) > 0.5) & y.notna(); Xr, y = Xr[ok].fillna(0.5), y[ok]
    dr = Xr.index.get_level_values(0); yr = pd.Series(dr.year, index=Xr.index)
    is_wk = pd.Series(dr.isin(WK), index=Xr.index); is_rb = pd.Series(dr.isin(RB), index=Xr.index)
    preds=[]
    for Y in range(2017,2027):
        tr=is_wk&(yr<=Y-2); va=is_wk&(yr==Y-1); te=is_rb&(yr==Y)
        if tr.sum()<5000 or te.sum()==0: continue
        m=LightGBMModel(**LGB); m.fit(Xr[tr],y[tr],Xr[va],y[va],num_boost_round=700,early_stopping_rounds=40)
        preds.append(m.predict(Xr[te]))
    P=pd.concat(preds).sort_index()
    res={}
    for K in (10,20):
        hold={}
        for d,g in P.groupby(level=0):
            names=list(g.droplevel(0).sort_values(ascending=False).index)
            st=ru.st_codes_on(d); hold[pd.Timestamp(d)]=[n for n in names if n.upper() not in st][:K]
        net=JR.simulate_eqw_monthly(hold,BT_START,BT_END,cost_oneway=0.00185,max_weight=0.10)
        m=ru.goal_metrics(net); m["calmar"]=m["cagr"]/abs(m["mdd"]) if m["mdd"]<0 else float("nan")
        yrr=net.groupby(net.index.year).apply(lambda r:(1+r).prod()-1)
        print(f"  RICH-ML[{uname}] k{K}: CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} Calmar={m['calmar']:4.2f}", flush=True)
        print("     yearly: "+"  ".join(f"{y}:{v:+.0%}" for y,v in yrr.items()), flush=True)
        res[K]={"cagr":m["cagr"],"mdd":m["mdd"],"sharpe":m["sharpe"],"calmar":m["calmar"]}
    del Xr,y; gc.collect()
    return res

results={}
for uname,umask in UNIS.items():
    print(f"\n=== RICH-ML universe={uname} ({len(FEATS)} features) ===", flush=True)
    results[uname]=run(uname,umask)
print("\n(reference: 31-feat ML smallmid k20 +8.75%/-50%; 大市值价值 rule +14.75%/-34%/Sh0.73)", flush=True)
json.dump(results, open(OUT/"ml_rich_results.json","w"), indent=2, default=float)
print(f"Saved -> {OUT/'ml_rich_results.json'}", flush=True)
