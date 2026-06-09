"""Fresh ML, objective = HIGHEST RETURN (unlevered). A-share return is concentrated in
small/mid caps where naive ML failed by picking junk. Fresh idea: GBM on the high-return
small/mid universe with QUALITY/VALUE/GROWTH/LOWVOL features ONLY (forbid the momentum/
reversal/turnover lottery cluster that caused prior crashes), walk-forward, top-K.
Search universes {defensive, smallmid-quality, broad} to find the max-CAGR config.
Unlevered (CLAUDE.md §7.11). PIT-safe cached factors. Sim = validated total-return proxy.
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru
from src.alpha_research.model_zoo import LightGBMModel

CACHE = JR.CACHE
FEATURES = ["val_bp","val_ep_ttm","val_sp_ttm","val_cftp","val_div_yield",
    "qual_roe","qual_roa","qual_gross_margin","qual_net_margin","qual_accruals",
    "grow_netprofit_yoy","grow_revenue_yoy","grow_opprofit_qoq","lev_debt_to_assets",
    "risk_vol_60d","risk_downvol_60d"]
LGB = dict(objective="regression", metric="mse", num_leaves=31, max_depth=5, learning_rate=0.02,
           min_child_samples=200, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
           reg_lambda=5.0, reg_alpha=1.0, verbose=-1, n_jobs=4)
BT_START, BT_END = "2017-01-01", "2026-02-27"

print("loading panels...", flush=True)
F = JR.factor_panel()
fwd = pd.concat([pd.read_parquet(CACHE/"fwd_is.parquet")["fwd_20d"], pd.read_parquet(CACHE/"fwd_oos.parquet")["fwd_20d"]])
fwd = fwd[~fwd.index.duplicated(keep="first")]
DATE = F.index.get_level_values(0); INST = F.index.get_level_values(1)
mb = pd.Series(INST.map(JR.is_mainboard), index=F.index)
liqr = F["liq_log_dollar_vol"].groupby(DATE).rank(pct=True)
szr = F["size_ln_mcap"].groupby(DATE).rank(pct=True)

UNIVERSES = {
    "defensive":  (mb & (liqr>=0.40) & (F["qual_roa"]>0)),
    "smallmid_q": ((szr>=0.05) & (szr<=0.70) & (liqr>=0.30) & (F["qual_roa"]>0)),
    "broad":      ((liqr>=0.40) & (F["qual_roa"]>0)),
}
cal = ru.trading_calendar(); WK = set(cal[::5])
rebal = ru.monthly_rebalance_dates(BT_START, BT_END); RB = set(rebal)

def run_universe(uname, umask):
    umask = umask.fillna(False)
    Fu = F.loc[umask, FEATURES]; fwdu = fwd.reindex(Fu.index); du = Fu.index.get_level_values(0)
    Xr = Fu.groupby(du).rank(pct=True); y = fwdu.groupby(du).rank(pct=True)
    ok = Xr.notna().all(axis=1) & y.notna(); Xr, y = Xr[ok], y[ok]
    dr = Xr.index.get_level_values(0); yr = pd.Series(dr.year, index=Xr.index)
    is_wk = pd.Series(dr.isin(WK), index=Xr.index); is_rb = pd.Series(dr.isin(RB), index=Xr.index)
    preds=[]
    for Y in range(2017,2027):
        tr=is_wk&(yr<=Y-2); va=is_wk&(yr==Y-1); te=is_rb&(yr==Y)
        if tr.sum()<5000 or te.sum()==0: continue
        m=LightGBMModel(**LGB); m.fit(Xr[tr],y[tr],Xr[va],y[va],num_boost_round=600,early_stopping_rounds=40)
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
        print(f"  ML[{uname}] k{K}: CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} Calmar={m['calmar']:4.2f}", flush=True)
        print("     yearly: "+"  ".join(f"{y}:{v:+.0%}" for y,v in yrr.items()), flush=True)
        res[K]={"cagr":m["cagr"],"mdd":m["mdd"],"sharpe":m["sharpe"],"calmar":m["calmar"]}
    return res

results={}
for uname,umask in UNIVERSES.items():
    print(f"\n=== ML max-return: universe={uname} ===", flush=True)
    results[uname]=run_universe(uname,umask)

# reference: pure smallmid (no ML, size-only) + 大市值价值
print("\n=== references ===", flush=True)
def simple_book(umask, rankcol, sign, K):
    um=umask.fillna(False); hold={}
    for d in rebal:
        try: day=F.xs(d,level=0)
        except KeyError: hold[d]=[]; continue
        idx=um.xs(d,level=0); idx=idx[idx].index
        day=day.loc[day.index.intersection(idx)]
        st=ru.st_codes_on(d)
        if st: day=day[~day.index.map(lambda c:c.upper() in st)]
        s=(day[rankcol]*sign).dropna()
        hold[d]=list(s.sort_values(ascending=False).head(K).index)
    net=JR.simulate_eqw_monthly(hold,BT_START,BT_END,cost_oneway=0.00185,max_weight=0.10)
    m=ru.goal_metrics(net); m["calmar"]=m["cagr"]/abs(m["mdd"]) if m["mdd"]<0 else float("nan"); return m
m=simple_book(UNIVERSES["smallmid_q"],"val_cftp",1,20)
print(f"  ref smallmid_q by C/P k20: CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:.2f}", flush=True)
print(f"  (baseline 大市值价值 top10 2017-26 = +14.75% / -34.3% / Sharpe 0.73)", flush=True)
json.dump(results, open(JR.OUT/"ml_max_return_results.json","w"), indent=2, default=float)
print(f"\nSaved -> {JR.OUT/'ml_max_return_results.json'}", flush=True)
