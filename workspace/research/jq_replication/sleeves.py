"""Low-correlated multi-sleeve research — build long-only-VIABLE sleeves, measure their
return-series cross-correlations, find the low-correlated set. (Goal: a strategy composed
of low-correlated factors, striving for 50%+ CAGR.)

Key refinement of the low-correlation insight: cross-sectional ICIR-optimal factors include
microcap/lottery names that DON'T convert to long-only top-K. So we require each sleeve to be
independently long-only-viable AND seek LOW correlation among them. Simulator (validated within
0.6-0.8% CAGR of event-driven). All sleeves: main-board, ex-ST, monthly, realistic costs, 10% cap.
"""
from __future__ import annotations
import json, itertools
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru

F = JR.factor_panel()
COST = 0.00185
IS = ("2014-01-01", "2020-12-31")
FULL = ("2014-01-01", "2026-02-27")

def _mb(day):
    return day[day.index.map(JR.is_mainboard)]

def _exst(day, d):
    st = ru.st_codes_on(d)
    return day[~day.index.map(lambda c: c.upper() in st)] if st else day

def pctrank(s):  # higher = better after orientation by caller
    return s.rank(pct=True)

def sleeve(start, end, selector, topk):
    """selector(day_df) -> Series score (higher=better) on the eligible names that day."""
    rebal = ru.monthly_rebalance_dates(start, end)
    hold = {}
    for d in rebal:
        try:
            day = F.xs(d, level=0)
        except KeyError:
            hold[d] = []; continue
        day = _exst(_mb(day), d)
        sc = selector(day)
        if sc is None or sc.dropna().empty:
            hold[d] = []; continue
        hold[d] = list(sc.dropna().sort_values(ascending=False).head(topk).index)
    return JR.simulate_eqw_monthly(hold, start, end, cost_oneway=COST, max_weight=0.10)

# ---- selectors (each economically distinct) ----
def sel_value_quality(day):   # 大市值价值 gate + ROA rank (the proven winner)
    g = (day["val_bp"] > 1.0) & (day["val_cftp"] > 0) & (day["qual_roa"] > 0.15) & (day["grow_netprofit_yoy"] > 0)
    p = day[g.fillna(False)]
    return p["qual_roa"] if not p.empty else None

def sel_value_cp(day):        # broad C/P value (no quality gate)
    return day["val_cftp"]

def sel_growth(day):          # growth among profitable names
    p = day[(day["qual_roa"] > 0).fillna(False)]
    if p.empty: return None
    return (pctrank(p["grow_netprofit_yoy"]) + pctrank(p["grow_revenue_yoy"]) + pctrank(p["grow_opprofit_qoq"]))

def sel_quality(day):         # pure quality (ROA+ROE), no value gate
    return pctrank(day["qual_roa"]) + pctrank(day["qual_roe"])

def sel_lowvol(day):          # low volatility (defensive)
    return -day["risk_vol_60d"]

def sel_rev_liquid(day):      # reversal among LIQUID large-caps (not microcap)
    liq = day[day["liq_log_dollar_vol"].rank(pct=True) >= 0.5]
    if liq.empty: return None
    return -liq["mom_return_20d"]   # low past return = reversal long

SLEEVES = {
    "value_quality": (sel_value_quality, 10),
    "value_cp":      (sel_value_cp, 20),
    "growth":        (sel_growth, 20),
    "quality":       (sel_quality, 20),
    "lowvol":        (sel_lowvol, 20),
    "rev_liquid":    (sel_rev_liquid, 20),
}

def met(net):
    m = ru.goal_metrics(net)
    m["calmar"] = m["cagr"]/abs(m["mdd"]) if m["mdd"] < 0 else float("nan")
    return m

for win, (s, e) in {"IS": IS, "FULL": FULL}.items():
    print(f"\n===== sleeves [{win}] =====", flush=True)
    nets = {}
    for name, (selr, k) in SLEEVES.items():
        net = sleeve(s, e, selr, k)
        nets[name] = net
        m = met(net)
        print(f"  {name:16s} CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} Calmar={m['calmar']:4.2f}", flush=True)
    R = pd.DataFrame(nets).dropna()
    print(f"  --- sleeve daily-return correlation [{win}] ---", flush=True)
    print(R.corr().round(2).to_string(), flush=True)
    if win == "FULL":
        R.to_parquet(JR.OUT / "sleeve_returns_full.parquet")
    else:
        R.to_parquet(JR.OUT / "sleeve_returns_is.parquet")
print(f"\nSaved sleeve returns -> {JR.OUT}", flush=True)
