"""Combine low-correlated VIABLE sleeves into ONE multi-factor long-only book (union of
each sleeve's top-N, equal weight), and test whether diversification + concentration beats
the single value_quality book. Sleeves are correlated ~0.6 (shared beta) so the diversification
benefit is limited — but spend any freed MDD budget on concentration to push CAGR. Tune on IS,
FULL = held-out check. Simulator = validated total-return proxy.
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru

F = JR.factor_panel()
COST = 0.00185
IS = ("2014-01-01", "2020-12-31"); FULL = ("2014-01-01", "2026-02-27")

def _elig(d):
    day = F.xs(d, level=0)
    day = day[day.index.map(JR.is_mainboard)]
    st = ru.st_codes_on(d)
    return day[~day.index.map(lambda c: c.upper() in st)] if st else day

def pr(s): return s.rank(pct=True)

def sel(day, which):
    if which == "VQ":
        g = (day["val_bp"]>1)&(day["val_cftp"]>0)&(day["qual_roa"]>0.15)&(day["grow_netprofit_yoy"]>0)
        p = day[g.fillna(False)];  return p["qual_roa"] if not p.empty else None
    if which == "LV":  return -day["risk_vol_60d"]
    if which == "VCP": return day["val_cftp"]
    if which == "GRW":
        p = day[(day["qual_roa"]>0).fillna(False)]
        return (pr(p["grow_netprofit_yoy"])+pr(p["grow_revenue_yoy"])+pr(p["grow_opprofit_qoq"])) if not p.empty else None
    raise ValueError(which)

def union_holdings(start, end, spec):   # spec: {sleeve: topN}
    rebal = ru.monthly_rebalance_dates(start, end)
    hold = {}
    for d in rebal:
        try:
            day = _elig(d)
        except KeyError:
            hold[d] = []; continue
        names = []
        for w, k in spec.items():
            sc = sel(day, w)
            if sc is None: continue
            names += list(sc.dropna().sort_values(ascending=False).head(k).index)
        hold[d] = list(dict.fromkeys(names))   # dedupe, preserve order
    return JR.simulate_eqw_monthly(hold, start, end, cost_oneway=COST, max_weight=0.10)

def met(label, net, extra=None):
    m = ru.goal_metrics(net); m["calmar"]=m["cagr"]/abs(m["mdd"]) if m["mdd"]<0 else float("nan")
    yr = net.groupby(net.index.year).apply(lambda r:(1+r).prod()-1); m["worst_year"]=float(yr.min())
    m["yearly"]={int(y):float(v) for y,v in yr.items()}; m["label"]=label
    if extra: m.update(extra)
    print(f"{label:30s} CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} Calmar={m['calmar']:4.2f} worstY={m['worst_year']:+6.1%}", flush=True)
    return m

CONFIGS = {
    "VQ10 (baseline)":      {"VQ":10},
    "VQ5+LV5":              {"VQ":5,"LV":5},
    "VQ5+LV5+VCP5":         {"VQ":5,"LV":5,"VCP":5},
    "VQ7+LV7":              {"VQ":7,"LV":7},
    "VQ10+LV10":            {"VQ":10,"LV":10},
    "VQ5+LV5+GRW5":         {"VQ":5,"LV":5,"GRW":5},
    "VQ3+LV3 (concentr.)":  {"VQ":3,"LV":3},
    "VQ8+VCP8":             {"VQ":8,"VCP":8},
}
results=[]
for win,(s,e) in {"IS":IS,"FULL":FULL}.items():
    print(f"\n===== combos [{win}] =====", flush=True)
    for name,spec in CONFIGS.items():
        results.append(met(f"[{win}] {name}", union_holdings(s,e,spec), {"window":win,"spec":spec}))
json.dump([{k:v for k,v in r.items() if not k.startswith('_')} for r in results],
          open(JR.OUT/"combine_sleeves_results.json","w"), indent=2, default=float)
print(f"\nSaved -> {JR.OUT/'combine_sleeves_results.json'}", flush=True)
