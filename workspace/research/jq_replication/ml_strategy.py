"""ML strategy — walk-forward factor combination, applying the validated lessons.

Prior ML FAILED (phase3: −19..−21% CAGR) because it ranked the SMALLMID universe by
cross-sectionally-demeaned RAW forward return → top-K = high-beta lottery falling-knives.
FIXES applied here:
  1. Rank WITHIN a defensive/tradeable universe (main-board, liquid, profitable) — the
     validated 大市值价值 insight that removes the falling-knife failure mode.
  2. RANK target (pct-rank of fwd_20d within universe), not raw demeaned return → the model
     learns relative ordering among good names, not extreme lottery payoffs.
  3. WALK-FORWARD (expanding train ≤Y-2, valid Y-1, predict Y) → every prediction is genuinely
     out-of-sample. Evaluated 2017-2026.
  4. Two models: Ridge (optimal LINEAR combo of low-correlated factors) + LightGBM (non-linear
     interactions). Benchmarked vs the simple 大市值价值 ROA rule over the same span.
PIT-safe (cached Ref(...,1) factors). Simulator = total-return proxy validated within 0.6-0.8% CAGR.
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru
from src.alpha_research.model_zoo import LightGBMModel
from sklearn.linear_model import Ridge

CACHE = JR.CACHE
FEATURES = [
    "mom_return_20d","mom_return_60d","mom_return_120d","mom_return_250d",
    "rev_return_5d","rev_return_10d","rev_max_return_20d",
    "risk_vol_20d","risk_vol_60d","risk_downvol_60d","liq_turnover_20d",
    "val_bp","val_ep_ttm","val_sp_ttm","val_cftp","val_div_yield",
    "qual_roe","qual_roa","qual_gross_margin","qual_net_margin","qual_accruals",
    "grow_netprofit_yoy","grow_revenue_yoy","grow_opprofit_qoq","lev_debt_to_assets","tech_rsi_14",
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
DATE = F.index.get_level_values(0)
INST = F.index.get_level_values(1)

# defensive daily universe: main-board, liquid (dollar-vol rank>=0.4), profitable (roa>0)
print("building defensive universe + ranked features...", flush=True)
mb = pd.Series(INST.map(JR.is_mainboard), index=F.index)
liqrank = F["liq_log_dollar_vol"].groupby(DATE).rank(pct=True)
uni = mb & (liqrank >= 0.40) & (F["qual_roa"] > 0)
uni = uni.fillna(False)
Fu = F.loc[uni, FEATURES]
fwdu = fwd.reindex(Fu.index)
du = Fu.index.get_level_values(0)
Xr = Fu.groupby(du).rank(pct=True)                       # features ranked within universe/day
y = fwdu.groupby(du).rank(pct=True)                      # TARGET = rank of fwd_20d within universe/day
ok = Xr.notna().all(axis=1) & y.notna()
Xr, y = Xr[ok], y[ok]
dr = Xr.index.get_level_values(0)
yr = pd.Series(dr.year, index=Xr.index)
print(f"  in-universe rows: {len(Xr)} ; years {dr.year.min()}-{dr.year.max()}", flush=True)

# weekly sampling for training speed (every 5th trading day)
cal = ru.trading_calendar()
wk = set(cal[::5])
is_wk = pd.Series(dr.isin(wk), index=Xr.index)

rebal = ru.monthly_rebalance_dates(BT_START, BT_END)
rebal_set = set(rebal)
is_rebal = pd.Series(dr.isin(rebal_set), index=Xr.index)

def walk_forward(model_kind):
    preds = []
    fi_acc = None
    for Y in range(2017, 2027):
        tr = is_wk & (yr <= Y-2)
        va = is_wk & (yr == Y-1)
        te = is_rebal & (yr == Y)
        if tr.sum() < 5000 or te.sum() == 0:
            continue
        if model_kind == "gbm":
            m = LightGBMModel(**LGB)
            m.fit(Xr[tr], y[tr], Xr[va], y[va], num_boost_round=600, early_stopping_rounds=40)
            p = m.predict(Xr[te])
            fi = m.feature_importance()
            fi_acc = fi if fi_acc is None else fi_acc.add(fi, fill_value=0)
        else:  # ridge
            m = Ridge(alpha=20.0)
            m.fit(Xr[tr].values, y[tr].values)
            p = pd.Series(m.predict(Xr[te].values), index=Xr[te].index)
        preds.append(p)
    P = pd.concat(preds).sort_index()
    return P, fi_acc

def backtest(score, label):
    # holdings = top-K by score within universe at each rebalance, ex-ST, for K in {20,30}
    out = {}
    for K in (20, 30):
        hold = {}
        for d, g in score.groupby(level=0):
            names = list(g.droplevel(0).sort_values(ascending=False).index)
            st = ru.st_codes_on(d)
            names = [n for n in names if n.upper() not in st][:K]
            hold[pd.Timestamp(d)] = names
        net = JR.simulate_eqw_monthly(hold, BT_START, BT_END, cost_oneway=0.00185, max_weight=0.10)
        m = ru.goal_metrics(net); m["calmar"]=m["cagr"]/abs(m["mdd"]) if m["mdd"]<0 else float("nan")
        yrr = net.groupby(net.index.year).apply(lambda r:(1+r).prod()-1)
        print(f"  {label} k{K}: CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} Calmar={m['calmar']:4.2f}", flush=True)
        print("     yearly: "+"  ".join(f"{y}:{v:+.0%}" for y,v in yrr.items()), flush=True)
        out[K] = {"cagr":m["cagr"],"mdd":m["mdd"],"sharpe":m["sharpe"],"calmar":m["calmar"],
                  "yearly":{int(y):float(v) for y,v in yrr.items()}}
    return out

results = {}
print("\n=== Ridge (linear factor combo) walk-forward ===", flush=True)
Pr,_ = walk_forward("ridge"); results["ridge"] = backtest(Pr, "ML-Ridge")
print("\n=== LightGBM walk-forward ===", flush=True)
Pg, fi = walk_forward("gbm");  results["gbm"] = backtest(Pg, "ML-GBM")
if fi is not None:
    print("  GBM top features: " + ", ".join(f"{k}={v:.0f}" for k,v in fi.sort_values(ascending=False).head(10).items()), flush=True)

# baseline: 大市值价值 ROA rule over the SAME span
print("\n=== baseline 大市值价值 top10 (same 2017-2026 span) ===", flush=True)
def vq_holdings():
    hold = {}
    for d in rebal:
        try: day = F.xs(d, level=0)
        except KeyError: hold[d]=[]; continue
        day = day[day.index.map(JR.is_mainboard)]
        st = ru.st_codes_on(d)
        if st: day = day[~day.index.map(lambda c: c.upper() in st)]
        g=(day["val_bp"]>1)&(day["val_cftp"]>0)&(day["qual_roa"]>0.15)&(day["grow_netprofit_yoy"]>0)
        p=day[g.fillna(False)]
        hold[d]=list(p["qual_roa"].sort_values(ascending=False).head(10).index) if not p.empty else []
    return hold
netb = JR.simulate_eqw_monthly(vq_holdings(), BT_START, BT_END, cost_oneway=0.00185, max_weight=0.10)
mb_=ru.goal_metrics(netb); mb_["calmar"]=mb_["cagr"]/abs(mb_["mdd"])
print(f"  大市值价值 top10: CAGR={mb_['cagr']:+7.2%} MDD={mb_['mdd']:+7.2%} Sharpe={mb_['sharpe']:5.2f} Calmar={mb_['calmar']:4.2f}", flush=True)
results["baseline_vq10"] = {"cagr":mb_["cagr"],"mdd":mb_["mdd"],"sharpe":mb_["sharpe"],"calmar":mb_["calmar"]}

json.dump(results, open(JR.OUT/"ml_strategy_results.json","w"), indent=2, default=float)
Pg.to_frame("gbm").to_parquet(JR.OUT/"ml_gbm_preds.parquet")
print(f"\nSaved -> {JR.OUT/'ml_strategy_results.json'}", flush=True)
