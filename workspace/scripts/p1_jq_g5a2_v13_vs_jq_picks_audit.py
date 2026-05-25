"""v13 used JQ's ACTUAL PIT universe. So if v13 still picks different stocks
than JQ on the same Tuesday, the difference MUST come from the market_cap data
used for ranking (Tushare $total_mv vs JQ valuation.market_cap).

For 4 sample Tuesdays spanning the window, compute:
  1. v13's top-12 picks (from event_driven_trades.csv)
  2. JQ's top-12 picks (from g5_G5_A2_stocknum12_trades.csv)
  3. Intersection count

If intersection is HIGH on all dates → market_cap data matches → gap is elsewhere
If intersection is LOW → market_cap data differs → Mech E confirmed."""

import pandas as pd
from pathlib import Path

P = Path(r"E:/量化系统")
v13_trades = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v13_jq_universe_run/event_driven_trades.csv",
                         parse_dates=["date"])
jq_trades = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv",
                        parse_dates=["time"])
jq_trades["date"] = jq_trades["time"].dt.normalize()
v13_trades["code_norm"] = v13_trades["code"].str.replace(".SZ", ".XSHE").str.replace(".SH", ".XSHG")

# Find Tuesdays where v13 made 12 buys (full rebalance day, no stoploss interaction)
v13_buys_full = (v13_trades[v13_trades["direction"] == "buy"]
                 .groupby("date").size())
clean_dates = v13_buys_full[v13_buys_full >= 8].index   # Tuesdays with ≥8 buys

# Sample 8 dates spanning the window
sample_dates = []
for year in [2014, 2015, 2017, 2019, 2021, 2022, 2024, 2025]:
    yr_dates = [d for d in clean_dates if d.year == year and d.weekday() == 1]
    if yr_dates:
        sample_dates.append(yr_dates[len(yr_dates)//2])  # middle of year

print(f"{'date':<12} {'v13_n':>6} {'jq_n':>6} {'intersect':>10} {'only_v13':>10} {'only_jq':>10}")
print("-" * 70)
totals = {"v13": 0, "jq": 0, "intersect": 0}
for d in sample_dates:
    v13_picks = set(v13_trades[(v13_trades["date"] == d) & (v13_trades["direction"] == "buy")]["code_norm"])
    jq_picks = set(jq_trades[(jq_trades["date"] == d) & (jq_trades["action"] == "open")]["security"])
    inter = v13_picks & jq_picks
    print(f"{d.date()!s:<12} {len(v13_picks):>6} {len(jq_picks):>6} {len(inter):>10} {len(v13_picks - jq_picks):>10} {len(jq_picks - v13_picks):>10}")
    totals["v13"] += len(v13_picks)
    totals["jq"] += len(jq_picks)
    totals["intersect"] += len(inter)

print("-" * 70)
print(f"Total intersection ratio: {totals['intersect']}/{totals['v13']} v13 = {totals['intersect']/max(totals['v13'],1)*100:.1f}%")
print(f"Total intersection ratio: {totals['intersect']}/{totals['jq']} JQ  = {totals['intersect']/max(totals['jq'],1)*100:.1f}%")

# Detailed dump of one date — the disputed picks
print()
print("=" * 80)
test_date = sample_dates[3] if len(sample_dates) > 3 else sample_dates[0]
print(f"Detail: {test_date.date()}")
print("=" * 80)
v13_picks = sorted(v13_trades[(v13_trades["date"] == test_date) & (v13_trades["direction"] == "buy")]["code_norm"])
jq_picks = sorted(jq_trades[(jq_trades["date"] == test_date) & (jq_trades["action"] == "open")]["security"])
print(f"v13 picks ({len(v13_picks)}): {v13_picks}")
print(f"JQ picks  ({len(jq_picks)}): {jq_picks}")
print(f"Only v13: {sorted(set(v13_picks) - set(jq_picks))}")
print(f"Only JQ:  {sorted(set(jq_picks) - set(v13_picks))}")
