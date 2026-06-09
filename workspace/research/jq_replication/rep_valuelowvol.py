"""FAITHFUL replication of 价值低波策略 (JoinQuant post/54680, author 阿鹤基本面研究).

Exact params from source .txt:
  universe : full market, ex-ST, ex-paused, ex-new(<180d)
  low-vol  : ATR(20) lowest 10%
  value    : C/P = 1/pcf_ratio, highest 20%
  select   : INTERSECTION (low_vol ∩ value), equal-weight ALL names (not top-K)
  rebal    : monthly, previous-day data
  costs    : close_tax 0.1% + commission 万3 + slippage (their FixedSlippage(0.0046))

Local mapping (PIT-safe cached factors): C/P -> val_cftp ; ATR(20) low -> risk_vol_20d
low (close-to-close vol proxy for ATR). ST excluded per rebalance via st_stocks ranges.
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru

F = JR.factor_panel()
R = JR.return_panel()
print(f"[rep] panels ready F={F.shape} R={R.shape}", flush=True)


def build_holdings(start, end, *, vol_low=0.10, value_top=0.20):
    rebal = ru.monthly_rebalance_dates(start, end)
    hold, sizes = {}, []
    for d in rebal:
        try:
            day = F.xs(d, level=0)
        except KeyError:
            hold[d] = []; sizes.append(0); continue
        day = day[day["val_cftp"].notna() & day["risk_vol_20d"].notna()]
        st = ru.st_codes_on(d)
        if st:
            day = day[~day.index.map(lambda c: c.upper() in st)]
        if day.empty:
            hold[d] = []; sizes.append(0); continue
        vol_rank = day["risk_vol_20d"].rank(pct=True)          # low = good
        cp_rank = day["val_cftp"].rank(pct=True)               # high = cheap
        sel = day[(vol_rank <= vol_low) & (cp_rank >= 1 - value_top)]
        names = list(sel.index)
        hold[d] = names; sizes.append(len(names))
    return hold, pd.Series(sizes, index=rebal)


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
    hold, sz = build_holdings(s, e)
    print(f"\n[{win}] intersection size: median={sz.median():.0f} min={sz.min()} max={sz.max()}", flush=True)
    # single-name cap 10% (their rule when >=10 names); ~median 100-200 names so non-binding
    net_faithful = JR.simulate_eqw_monthly(hold, s, e, cost_oneway=0.00080, max_weight=0.10)
    results.append(metrics(f"价值低波 FAITHFUL {win}", net_faithful,
                           {"window": win, "variant": "faithful", "median_names": float(sz.median())}))
    net_real = JR.simulate_eqw_monthly(hold, s, e, cost_oneway=0.00185, max_weight=0.10)
    results.append(metrics(f"价值低波 REALISTIC(10bps) {win}", net_real,
                           {"window": win, "variant": "realistic"}))

print("\n=== yearly (faithful, full) ===")
for r in results:
    if r["variant"] == "faithful" and r["window"] == "FULL_2014_2026":
        print("  " + "  ".join(f"{y}:{v:+.0%}" for y, v in sorted(r["yearly"].items())))

with open(JR.OUT / "rep_valuelowvol_results.json", "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in results], f, indent=2, default=float)
print(f"\nSaved -> {JR.OUT/'rep_valuelowvol_results.json'}")
