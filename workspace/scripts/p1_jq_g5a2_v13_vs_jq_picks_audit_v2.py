"""v2 of v13-vs-JQ picks audit: compare END-OF-DAY HELD positions, not just
new trades that day. JQ retains positions across weeks, so the trades file
only shows NEW additions/removals; the actual holding set is in positions.csv."""

import pandas as pd
from pathlib import Path

P = Path(r"E:/量化系统")
v13_trades = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v13_jq_universe_run/event_driven_trades.csv",
                         parse_dates=["date"])
jq_positions = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_positions.csv",
                           parse_dates=["time"])
jq_positions["date"] = jq_positions["time"].dt.normalize()

# Reconstruct v13's per-day position set from buy/sell events
v13_trades["code_norm"] = v13_trades["code"].str.replace(".SZ", ".XSHE").str.replace(".SH", ".XSHG")
v13_trades_sorted = v13_trades.sort_values(["date"]).copy()
held: set = set()
v13_eod_positions = {}
for d, grp in v13_trades_sorted.groupby("date"):
    for _, t in grp.iterrows():
        if t["direction"] == "buy":
            held.add(t["code_norm"])
        elif t["direction"] == "sell":
            # Cannot be 100% sure of partial vs full sell; assume full close
            # (this works for v13's strategy where partial sells are rare).
            held.discard(t["code_norm"])
    v13_eod_positions[d] = set(held)

# Sample 8 Tuesdays spanning the window
sample_dates = []
for year in [2014, 2015, 2017, 2019, 2021, 2022, 2024, 2025]:
    yr_d = [d for d in v13_eod_positions.keys() if d.year == year and d.weekday() == 1]
    if yr_d:
        sample_dates.append(yr_d[len(yr_d)//2])

print(f"{'date':<12} {'v13_held':>9} {'jq_held':>8} {'intersect':>10} {'only_v13':>10} {'only_jq':>10}")
print("-" * 70)
totals = {"v13": 0, "jq": 0, "intersect": 0}
for d in sample_dates:
    v13_h = v13_eod_positions.get(d, set())
    jq_h = set(jq_positions[jq_positions["date"] == d]["security"])
    inter = v13_h & jq_h
    print(f"{d.date()!s:<12} {len(v13_h):>9} {len(jq_h):>8} {len(inter):>10} "
          f"{len(v13_h - jq_h):>10} {len(jq_h - v13_h):>10}")
    totals["v13"] += len(v13_h)
    totals["jq"] += len(jq_h)
    totals["intersect"] += len(inter)

print("-" * 70)
if totals["v13"] and totals["jq"]:
    print(f"Total intersection: {totals['intersect']}/{totals['v13']} v13 = {totals['intersect']/totals['v13']*100:.1f}%")
    print(f"Total intersection: {totals['intersect']}/{totals['jq']} JQ  = {totals['intersect']/totals['jq']*100:.1f}%")

# Detail: 2 sample dates
for d in sample_dates[:3]:
    print()
    print("=" * 80)
    print(f"Detail: {d.date()}")
    print("=" * 80)
    v13_h = sorted(v13_eod_positions.get(d, set()))
    jq_h = sorted(jq_positions[jq_positions["date"] == d]["security"])
    print(f"v13 held ({len(v13_h)}): {v13_h}")
    print(f"JQ held  ({len(jq_h)}): {jq_h}")
    print(f"Only v13: {sorted(set(v13_h) - set(jq_h))}")
    print(f"Only JQ:  {sorted(set(jq_h) - set(v13_h))}")
