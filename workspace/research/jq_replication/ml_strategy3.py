"""ML v3 — does ML add value as a REFINER of the proven value rule (rank within the
大市值价值 gate) vs as the primary selector? Walk-forward GBM on viable features (as v2),
then three top-10 books over 2017-2026:
  (1) ROA-rank within the 大市值价值 gate         [the proven baseline]
  (2) ML-rank within the 大市值价值 gate          [ML refines the value picks]
  (3) ML-rank within broad defensive universe     [ML as primary selector]
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

F = JR.factor_panel()
fwd = pd.concat([pd.read_parquet(CACHE/"fwd_is.parquet")["fwd_20d"], pd.read_parquet(CACHE/"fwd_oos.parquet")["fwd_20d"]])
fwd = fwd[~fwd.index.duplicated(keep="first")]
DATE=F.index.get_level_values(0); INST=F.index.get_level_values(1)
mb=pd.Series(INST.map(JR.is_mainboard),index=F.index)
liqrank=F["liq_log_dollar_vol"].groupby(DATE).rank(pct=True)
uni=(mb&(liqrank>=0.40)&(F["qual_roa"]>0)).fillna(False)
Fu=F.loc[uni,FEATURES]; fwdu=fwd.reindex(Fu.index); du=Fu.index.get_level_values(0)
Xr=Fu.groupby(du).rank(pct=True); y=fwdu.groupby(du).rank(pct=True)
ok=Xr.notna().all(axis=1)&y.notna(); Xr,y=Xr[ok],y[ok]
dr=Xr.index.get_level_values(0); yr=pd.Series(dr.year,index=Xr.index)
cal=ru.trading_calendar(); is_wk=pd.Series(dr.isin(set(cal[::5])),index=Xr.index)
rebal=ru.monthly_rebalance_dates(BT_START,BT_END); is_rebal=pd.Series(dr.isin(set(rebal)),index=Xr.index)

print("walk-forward GBM (viable features)...", flush=True)
preds=[]
for Y in range(2017,2027):
    tr=is_wk&(yr<=Y-2); va=is_wk&(yr==Y-1); te=is_rebal&(yr==Y)
    if tr.sum()<5000 or te.sum()==0: continue
    m=LightGBMModel(**LGB); m.fit(Xr[tr],y[tr],Xr[va],y[va],num_boost_round=600,early_stopping_rounds=40)
    preds.append(m.predict(Xr[te]))
P=pd.concat(preds).sort_index()                       # ML score on in-universe rebalance rows

def vq_gate_mask(day):
    return ((day["val_bp"]>1)&(day["val_cftp"]>0)&(day["qual_roa"]>0.15)&(day["grow_netprofit_yoy"]>0)).fillna(False)

def build(kind, K=10):
    hold={}
    for d in rebal:
        try: day=F.xs(d,level=0)
        except KeyError: hold[d]=[]; continue
        day=day[day.index.map(JR.is_mainboard)]
        st=ru.st_codes_on(d)
        if st: day=day[~day.index.map(lambda c:c.upper() in st)]
        if kind in ("roa_gate","ml_gate"):
            p=day[vq_gate_mask(day)]
            if p.empty: hold[d]=[]; continue
            if kind=="roa_gate":
                order=p["qual_roa"].sort_values(ascending=False)
            else:
                try: sc=P.xs(d,level=0)
                except KeyError: hold[d]=[]; continue
                order=sc.reindex(p.index).dropna().sort_values(ascending=False)
        else:  # ml_broad
            try: sc=P.xs(d,level=0)
            except KeyError: hold[d]=[]; continue
            order=sc.dropna().sort_values(ascending=False)
        hold[d]=list(order.head(K).index)
    net=JR.simulate_eqw_monthly(hold,BT_START,BT_END,cost_oneway=0.00185,max_weight=0.10)
    m=ru.goal_metrics(net); m["calmar"]=m["cagr"]/abs(m["mdd"]) if m["mdd"]<0 else float("nan")
    return m

res={}
for kind,lab in [("roa_gate","(1) ROA-rank in value gate [baseline]"),
                 ("ml_gate","(2) ML-rank in value gate [refiner]"),
                 ("ml_broad","(3) ML-rank broad universe [selector]")]:
    m=build(kind); res[kind]=m
    print(f"  {lab:42s} CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} Calmar={m['calmar']:4.2f}", flush=True)
json.dump(res, open(JR.OUT/"ml_strategy3_results.json","w"), indent=2, default=float)
print(f"Saved -> {JR.OUT/'ml_strategy3_results.json'}", flush=True)
