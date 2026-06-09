"""Event-driven validation of 大市值价值: faithful baseline (top5) + improved (top10 ROA).

The simulator is a validated total-return proxy (within 0.6% CAGR of event-driven on
the VL book), but the EventDrivenBacktester is the deployable truth: T+1, limit-up
unbuyability with ranked substitution, suspension, JoinQuant costs + slippage, 10% ADV
cap, and dividends credited on the ex-date. Run over FULL 2014-2026.

Gate (PIT-safe cached factors): main-board, pb<1 (val_bp>1), OCF>0, ROA>0.15%, npy>0;
rank ROA desc; HEADROOM=3x candidates for limit substitution; cash-out when gate empties.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru
from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
from src.backtest_engine.event_driven.strategies import RankedFallbackStrategy

START, END = "2014-01-01", "2026-02-26"
BENCH = "000300.SH"
CAPITAL = 10_000_000.0
VOL_LIMIT = 0.10
PRELOAD = ["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor"]
F = JR.factor_panel()


def ranked_schedule(topk, roa_min=0.15):
    rebal = ru.monthly_rebalance_dates(START, END)
    headroom = topk * 3
    sched = {}
    for d in rebal:
        try:
            day = F.xs(d, level=0)
        except KeyError:
            sched[pd.Timestamp(d)] = []; continue
        day = day[day.index.map(JR.is_mainboard)]
        st = ru.st_codes_on(d)
        if st:
            day = day[~day.index.map(lambda c: c.upper() in st)]
        gate = ((day["val_bp"] > 1.0) & (day["val_cftp"] > 0) &
                (day["qual_roa"] > roa_min) & (day["grow_netprofit_yoy"] > 0))
        ranked = day[gate.fillna(False)]["qual_roa"].sort_values(ascending=False).head(headroom)
        sched[pd.Timestamp(d)] = [str(i).upper().replace("_", ".") for i in ranked.index]
    return sched


def run(topk, label):
    sched = ranked_schedule(topk)
    ne = sum(1 for v in sched.values() if len(v) < topk)
    strat = RankedFallbackStrategy(sched, topk=topk)
    bt = EventDrivenBacktester(data_dir=str(JR.PROJECT_ROOT / "data"))
    res = bt.run(strategy=strat, start_time=START, end_time=END, benchmark=BENCH,
                 account=CAPITAL, exchange_config=CostConfig(), slippage=None,
                 volume_limit=VOL_LIMIT, preload_fields=PRELOAD)
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    m = ru.goal_metrics(net)
    m["calmar"] = m["cagr"] / abs(m["mdd"]) if m["mdd"] < 0 else float("nan")
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    m["yearly"] = {int(y): float(v) for y, v in yr.items()}
    m["label"] = label; m["months_lt_topk"] = ne
    print(f"{label:34s} CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} "
          f"Calmar={m['calmar']:4.2f} n={m['n_days']}", flush=True)
    print("  yearly: " + "  ".join(f"{y}:{v:+.0%}" for y, v in sorted(m['yearly'].items())), flush=True)
    return m

results = [run(5, "EVENTDRIVEN 大市值价值 top5 (faithful)"),
           run(10, "EVENTDRIVEN 大市值价值 top10 (improved)")]
with open(JR.OUT / "rep_eventdriven_results.json", "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in results], f, indent=2, default=str)
print(f"\nSaved -> {JR.OUT/'rep_eventdriven_results.json'}")
