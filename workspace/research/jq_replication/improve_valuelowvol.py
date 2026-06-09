"""IMPROVE 价值低波 — remove the audited flaw (full-universe intersection drags in
创业板/科创/microcap -> -54% MDD). Fix: restrict the universe (main-board / liquidity
floor / size floor) to realize the low-vol promise. Simulator = validated total-return
proxy. Realistic costs. Tune on IS; FULL is the held-out check.
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru

F = JR.factor_panel()
COST = 0.00185

def build(start, end, *, vol_low=0.10, value_top=0.20, board=None, liq_floor=None, size_floor=None):
    rebal = ru.monthly_rebalance_dates(start, end)
    hold, sizes = {}, []
    for d in rebal:
        try:
            day = F.xs(d, level=0)
        except KeyError:
            hold[d] = []; sizes.append(0); continue
        day = day[day["val_cftp"].notna() & day["risk_vol_20d"].notna()]
        if board == "main":
            day = day[day.index.map(JR.is_mainboard)]
        st = ru.st_codes_on(d)
        if st:
            day = day[~day.index.map(lambda c: c.upper() in st)]
        if liq_floor is not None and "liq_log_dollar_vol" in day:
            day = day[day["liq_log_dollar_vol"].rank(pct=True) >= liq_floor]
        if size_floor is not None and "size_ln_mcap" in day:
            day = day[day["size_ln_mcap"].rank(pct=True) >= size_floor]
        if day.empty:
            hold[d] = []; sizes.append(0); continue
        sel = day[(day["risk_vol_20d"].rank(pct=True) <= vol_low) &
                  (day["val_cftp"].rank(pct=True) >= 1 - value_top)]
        hold[d] = list(sel.index); sizes.append(len(sel))
    return hold, pd.Series(sizes, index=rebal)

def met(label, net, extra=None):
    m = ru.goal_metrics(net)
    m["calmar"] = m["cagr"] / abs(m["mdd"]) if m["mdd"] < 0 else float("nan")
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    m["worst_year"] = float(yr.min()) if len(yr) else float("nan")
    m["label"] = label
    if extra: m.update(extra)
    print(f"{label:46s} CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} "
          f"Calmar={m['calmar']:4.2f} worstY={m['worst_year']:+6.1%}", flush=True)
    return m

VARIANTS = {
    "A faithful (full universe)":        dict(),
    "B main-board only":                 dict(board="main"),
    "C main-board + liq>40%":            dict(board="main", liq_floor=0.40),
    "D main-board + size>30%":           dict(board="main", size_floor=0.30),
    "E liq>40% (any board)":             dict(liq_floor=0.40),
}
results = []
for win, (s, e) in {"IS_2014_2020": ("2014-01-01", "2020-12-31"),
                    "FULL_2014_2026": ("2014-01-01", "2026-02-27")}.items():
    print(f"\n===== {win} =====")
    for name, kw in VARIANTS.items():
        hold, sz = build(s, e, **kw)
        net = JR.simulate_eqw_monthly(hold, s, e, cost_oneway=COST, max_weight=0.10)
        results.append(met(f"[{win}] {name}", net, {"window": win, "variant": name,
                                                    "median_names": float(sz.median())}))

with open(JR.OUT / "improve_valuelowvol_results.json", "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in results], f, indent=2, default=float)
print(f"\nSaved -> {JR.OUT/'improve_valuelowvol_results.json'}")
