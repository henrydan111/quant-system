"""ML v2 — apply the factor-selection insight TO the ML: feed it only long-only-VIABLE
fundamentals (value/quality/growth/low-vol), FORBID the high-ICIR lottery cluster
(turnover/reversal/momentum) that ML v1 loaded on and crashed with. Same walk-forward,
defensive universe, rank target, GBM+Ridge. Benchmark vs 大市值价值 top10 (2017-2026).
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru
from src.alpha_research.model_zoo import LightGBMModel
from sklearn.linear_model import Ridge

CACHE = JR.CACHE
# VIABLE fundamentals + low-vol ONLY (no turnover/reversal/momentum/rsi/amihud/size)
FEATURES = [
    "val_bp","val_ep_ttm","val_sp_ttm","val_cftp","val_div_yield",
    "qual_roe","qual_roa","qual_gross_margin","qual_net_margin","qual_accruals",
    "grow_netprofit_yoy","grow_revenue_yoy","grow_opprofit_qoq","lev_debt_to_assets",
    "risk_vol_60d","risk_downvol_60d",
]
LGB = dict(objective="regression", metric="mse", num_leaves=31, max_depth=5, learning_rate=0.02,
           min_child_samples=200, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
           reg_lambda=5.0, reg_alpha=1.0, verbose=-1, n_jobs=4)
BT_START, BT_END = "2017-01-01", "2026-02-27"

print("loading panels...", flush=True)
F = JR.factor_panel()
fwd = pd.concat([pd.read_parquet(CACHE/"fwd_is.parquet")["fwd_20d"],
                 pd.read_parquet(CACHE/"fwd_oos.parquet")["fwd_20d"]])
fwd = fwd[~fwd.index.duplicated(keep="first")]
DATE = F.index.get_level_values(0); INST = F.index.get_level_values(1)
mb = pd.Series(INST.map(JR.is_mainboard), index=F.index)
liqrank = F["liq_log_dollar_vol"].groupby(DATE).rank(pct=True)
uni = (mb & (liqrank >= 0.40) & (F["qual_roa"] > 0)).fillna(False)
Fu = F.loc[uni, FEATURES]; fwdu = fwd.reindex(Fu.index); du = Fu.index.get_level_values(0)
Xr = Fu.groupby(du).rank(pct=True); y = fwdu.groupby(du).rank(pct=True)
ok = Xr.notna().all(axis=1) & y.notna(); Xr, y = Xr[ok], y[ok]
dr = Xr.index.get_level_values(0); yr = pd.Series(dr.year, index=Xr.index)
print(f"  in-universe rows: {len(Xr)}", flush=True)
cal = ru.trading_calendar(); wk = set(cal[::5])
is_wk = pd.Series(dr.isin(wk), index=Xr.index)
rebal = ru.monthly_rebalance_dates(BT_START, BT_END)
is_rebal = pd.Series(dr.isin(set(rebal)), index=Xr.index)

def walk(kind):
    preds, fi_acc = [], None
    for Y in range(2017, 2027):
        tr = is_wk & (yr <= Y-2); va = is_wk & (yr == Y-1); te = is_rebal & (yr == Y)
        if tr.sum() < 5000 or te.sum() == 0: continue
        if kind == "gbm":
            m = LightGBMModel(**LGB); m.fit(Xr[tr], y[tr], Xr[va], y[va], num_boost_round=600, early_stopping_rounds=40)
            p = m.predict(Xr[te]); fi = m.feature_importance(); fi_acc = fi if fi_acc is None else fi_acc.add(fi, fill_value=0)
        else:
            m = Ridge(alpha=20.0); m.fit(Xr[tr].values, y[tr].values); p = pd.Series(m.predict(Xr[te].values), index=Xr[te].index)
        preds.append(p)
    return pd.concat(preds).sort_index(), fi_acc

def backtest(score, label):
    out = {}
    for K in (20, 30):
        hold = {}
        for d, g in score.groupby(level=0):
            names = list(g.droplevel(0).sort_values(ascending=False).index)
            st = ru.st_codes_on(d); hold[pd.Timestamp(d)] = [n for n in names if n.upper() not in st][:K]
        net = JR.simulate_eqw_monthly(hold, BT_START, BT_END, cost_oneway=0.00185, max_weight=0.10)
        m = ru.goal_metrics(net); m["calmar"]=m["cagr"]/abs(m["mdd"]) if m["mdd"]<0 else float("nan")
        yrr = net.groupby(net.index.year).apply(lambda r:(1+r).prod()-1)
        print(f"  {label} k{K}: CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} Calmar={m['calmar']:4.2f}", flush=True)
        print("     yearly: "+"  ".join(f"{y}:{v:+.0%}" for y,v in yrr.items()), flush=True)
        out[K]={"cagr":m["cagr"],"mdd":m["mdd"],"sharpe":m["sharpe"],"calmar":m["calmar"]}
    return out

results={}
print("\n=== ML v2 Ridge (viable fundamentals+lowvol) ===", flush=True)
Pr,_=walk("ridge"); results["ridge_viable"]=backtest(Pr,"ML2-Ridge")
print("\n=== ML v2 GBM (viable fundamentals+lowvol) ===", flush=True)
Pg,fi=walk("gbm"); results["gbm_viable"]=backtest(Pg,"ML2-GBM")
if fi is not None: print("  GBM top features: "+", ".join(f"{k}={v:.0f}" for k,v in fi.sort_values(ascending=False).head(8).items()), flush=True)
json.dump(results, open(JR.OUT/"ml_strategy2_results.json","w"), indent=2, default=float)
print(f"\n(baseline 大市值价值 top10 2017-2026 = +14.75% / -34.3% / Sharpe 0.73 / Calmar 0.43)", flush=True)
print(f"Saved -> {JR.OUT/'ml_strategy2_results.json'}", flush=True)
