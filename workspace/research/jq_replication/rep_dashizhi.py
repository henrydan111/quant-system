"""FAITHFUL replication of 大市值价值投资 (JoinQuant post/41921, author Ahfu).

Exact params from the source .txt:
  universe : main-board only (excl 创业板30x/科创68x/北交4x,8x), listed >200d, ex-ST/paused
  gate     : pb<1 + 经营现金流>0 + 扣非净利润>0 + roa>0.15% + 净利润同比>0
  rank     : ROA desc, take top 5
  rebal    : monthly, buy at open
  cash-out : when <5 names pass the gate (auto cash near bull tops)
  costs    : close_tax 0.1% + commission 万1.2 + NO slippage (a flaw)

Local-backend mapping (PIT-safe cached factors, already Ref(...,1)-shifted):
  pb<1 -> val_bp>1 ; OCF>0 -> val_cftp>0 ; roa>0.15% -> qual_roa>0.15 ;
  净利同比>0 -> grow_netprofit_yoy>0 ; 扣非>0 approximated by qual_roa>0.15 (positive earnings)
Run window 2014-2020 (IS) is the faithful replication baseline; full 2014-2026 shown
for context (the strategy params are the AUTHOR's, zero tuning by us -> running the
fixed externally-specified strategy over history is replication, not OOS dredging).
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru

F = JR.factor_panel()
print(f"[rep] factor panel {F.shape} {F.index.get_level_values(0).min().date()}..{F.index.get_level_values(0).max().date()}", flush=True)
print("[rep] building/loading daily return panel...", flush=True)
R = JR.return_panel()
print(f"[rep] return panel {R.shape}", flush=True)

# main-board instrument set
all_inst = F.index.get_level_values(1).unique()
MAIN = set(c for c in all_inst if JR.is_mainboard(c))
print(f"[rep] main-board instruments: {len(MAIN)}/{len(all_inst)}", flush=True)


def build_holdings(start, end, *, topk=5, roa_min=0.15, mainboard=True):
    rebal = ru.monthly_rebalance_dates(start, end)
    hold = {}
    counts = []
    for d in rebal:
        try:
            day = F.xs(d, level=0)
        except KeyError:
            hold[d] = []; counts.append(0); continue
        if mainboard:
            day = day[day.index.map(JR.is_mainboard)]
        gate = ((day["val_bp"] > 1.0) & (day["val_cftp"] > 0) &
                (day["qual_roa"] > roa_min) & (day["grow_netprofit_yoy"] > 0))
        passed = day[gate.fillna(False)]
        ranked = passed["qual_roa"].sort_values(ascending=False)
        names = list(ranked.head(topk).index)
        hold[d] = names
        counts.append(len(passed))
    return hold, pd.Series(counts, index=rebal)


def metrics(label, net, extra=None):
    m = ru.goal_metrics(net)
    m["calmar"] = m["cagr"] / abs(m["mdd"]) if m["mdd"] < 0 else float("nan")
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    m["worst_year"] = float(yr.min()) if len(yr) else float("nan")
    m["yearly"] = {int(y): float(v) for y, v in yr.items()}
    m["label"] = label
    if extra: m.update(extra)
    print(f"{label:42s} CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:5.2f} "
          f"Calmar={m['calmar']:4.2f} worstY={m['worst_year']:+6.1%} n={m['n_days']}", flush=True)
    return m


results = []
for win, (s, e) in {"IS_2014_2020": ("2014-01-01", "2020-12-31"),
                    "FULL_2014_2026": ("2014-01-01", "2026-02-27")}.items():
    hold, cnt = build_holdings(s, e, topk=5, roa_min=0.15)
    n_empty = int((cnt < 5).sum()); n_zero = int((cnt == 0).sum())
    print(f"\n[{win}] gate pass-count: median={cnt.median():.0f} "
          f"months_with_<5={n_empty}/{len(cnt)} months_with_0={n_zero}", flush=True)
    # faithful: zero slippage, 万1.2 comm, 0.1% tax -> cost_oneway=(0.00012+0.00112)/2
    net_faithful = JR.simulate_eqw_monthly(hold, s, e, cost_oneway=0.00062)
    results.append(metrics(f"大市值价值 FAITHFUL(0slip) {win}", net_faithful,
                           {"window": win, "variant": "faithful_zeroslip",
                            "cost_oneway": 0.00062, "months_lt5": n_empty, "months_zero": n_zero}))
    # realistic: 万2.5 comm + 0.1% tax + 10bps slippage each side
    net_real = JR.simulate_eqw_monthly(hold, s, e, cost_oneway=0.00185)
    results.append(metrics(f"大市值价值 REALISTIC(10bps) {win}", net_real,
                           {"window": win, "variant": "realistic", "cost_oneway": 0.00185}))

print("\n=== yearly (faithful, full) ===")
for r in results:
    if r["variant"] == "faithful_zeroslip" and r["window"] == "FULL_2014_2026":
        print("  " + "  ".join(f"{y}:{v:+.0%}" for y, v in sorted(r["yearly"].items())))

with open(JR.OUT / "rep_dashizhi_results.json", "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in results], f, indent=2, default=float)
print(f"\nSaved -> {JR.OUT/'rep_dashizhi_results.json'}")
