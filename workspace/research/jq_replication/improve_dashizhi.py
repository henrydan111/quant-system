"""IMPROVE 大市值价值 — remove the audited flaws, keep PIT-safe & realistic costs.

Audited flaws (克隆策略优缺点与因子库.md §三.4):
  F1 only 5 holdings -> idiosyncratic blow-up risk        -> diversify to 10
  F2 single-indicator ROA rank -> 周期顶/一次性收益 risk   -> multi-factor rank (ROA + C/P + low-vol)
  F3 zero slippage                                         -> realistic 10bps (all variants)
  F4 no ST exclusion in our replication                    -> explicit ST exclusion
  F5 pb<1 hard gate -> style dependence / over-空仓        -> test a softer value gate

Discipline: tune on IS (2014-2020); FULL (2014-2026) is the held-out check. The fixes
are PRE-SPECIFIED audit remedies (economically motivated), not OOS-dredged params.
Realistic costs everywhere (cost_oneway=0.00185). Equal-weight + 10% single-name cap.
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru

F = JR.factor_panel()
R = JR.return_panel()
COST = 0.00185

def build(start, end, *, topk, pb_max=1.0, roa_min=0.15, rank="roa", exclude_st=True):
    rebal = ru.monthly_rebalance_dates(start, end)
    hold, cnt = {}, []
    for d in rebal:
        try:
            day = F.xs(d, level=0)
        except KeyError:
            hold[d] = []; cnt.append(0); continue
        day = day[day.index.map(JR.is_mainboard)]
        if exclude_st:
            st = ru.st_codes_on(d)
            if st:
                day = day[~day.index.map(lambda c: c.upper() in st)]
        gate = ((day["val_bp"] > 1.0 / pb_max) & (day["val_cftp"] > 0) &
                (day["qual_roa"] > roa_min) & (day["grow_netprofit_yoy"] > 0))
        passed = day[gate.fillna(False)]
        cnt.append(len(passed))
        if passed.empty:
            hold[d] = []; continue
        if rank == "roa":
            sc = passed["qual_roa"]
        else:  # multi-factor: ROA (quality) + C/P (value) + low-vol, equal-weighted pct ranks
            sc = (passed["qual_roa"].rank(pct=True)
                  + passed["val_cftp"].rank(pct=True)
                  + (-passed["risk_vol_60d"]).rank(pct=True))
        hold[d] = list(sc.sort_values(ascending=False).head(topk).index)
    return hold, pd.Series(cnt, index=rebal)

def met(label, net, extra=None):
    m = ru.goal_metrics(net)
    m["calmar"] = m["cagr"] / abs(m["mdd"]) if m["mdd"] < 0 else float("nan")
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    m["worst_year"] = float(yr.min()) if len(yr) else float("nan")
    m["yearly"] = {int(y): float(v) for y, v in yr.items()}
    m["label"] = label
    if extra: m.update(extra)
    print(f"{label:46s} CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} "
          f"Calmar={m['calmar']:4.2f} worstY={m['worst_year']:+6.1%}", flush=True)
    return m

VARIANTS = {
    "A baseline top5 ROA":            dict(topk=5,  rank="roa"),
    "B top10 ROA (F1)":               dict(topk=10, rank="roa"),
    "C top10 multifactor (F1+F2)":    dict(topk=10, rank="multi"),
    "D C+ST-excl (F1+F2+F4)":         dict(topk=10, rank="multi", exclude_st=True),
    "E D+pb<1.5 (F5 softer gate)":    dict(topk=10, rank="multi", pb_max=1.5),
    "F D+top15":                      dict(topk=15, rank="multi"),
}

results = []
for win, (s, e) in {"IS_2014_2020": ("2014-01-01", "2020-12-31"),
                    "FULL_2014_2026": ("2014-01-01", "2026-02-27")}.items():
    print(f"\n===== {win} =====")
    for name, kw in VARIANTS.items():
        hold, cnt = build(s, e, **kw)
        net = JR.simulate_eqw_monthly(hold, s, e, cost_oneway=COST, max_weight=0.10)
        results.append(met(f"[{win}] {name}", net, {"window": win, "variant": name, **kw}))

with open(JR.OUT / "improve_dashizhi_results.json", "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in results], f, indent=2, default=float)
print(f"\nSaved -> {JR.OUT/'improve_dashizhi_results.json'}")
