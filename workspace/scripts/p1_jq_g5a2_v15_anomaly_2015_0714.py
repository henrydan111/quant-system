"""Trace 2015-07-14 anomaly: v15 -14.47% vs JQ +4.61% on same day, identical
trade list. Either v15 holds different stocks, has different position sizes,
or has wrong MTM prices.

Steps:
1. Show JQ trades on 2015-07-14 (the day of divergence)
2. Show v15 trades on the same day
3. Show v15's positions at end of 2015-07-13 (the day BEFORE)
4. Show v15's positions at end of 2015-07-14
5. Compare to JQ's positions on the same dates
6. For each held position, compute MTM change v15 vs JQ"""

import pandas as pd
from pathlib import Path
import sys

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))

# Load JQ trades, positions, daily
jq_trades = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv", parse_dates=["time"])
jq_pos = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_positions.csv", parse_dates=["time"])
jq_daily = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_daily.csv", parse_dates=["time"])
jq_trades["date"] = jq_trades["time"].dt.normalize()
jq_pos["date"] = jq_pos["time"].dt.normalize()
jq_daily["date"] = jq_daily["time"].dt.normalize()

# Load v15 trades
v15_trades = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v15_jq_slippage_run/event_driven_trades.csv", parse_dates=["date"])

ANOM_DATE = pd.Timestamp("2015-07-14")
PRIOR_DATE = pd.Timestamp("2015-07-13")
NEXT_DATE = pd.Timestamp("2015-07-15")

print(f"=== JQ position list on {PRIOR_DATE.date()} (EOD) ===")
jp = jq_pos[jq_pos["date"] == PRIOR_DATE][["security", "amount", "avg_cost", "price"]]
print(jp.to_string(index=False))
print(f"n_positions: {len(jp)}, total_value: {(jp['amount']*jp['price']).sum():,.0f}")

print()
print(f"=== JQ trades on {ANOM_DATE.date()} ===")
jt = jq_trades[jq_trades["date"] == ANOM_DATE][["security", "action", "amount", "price"]]
print(jt.to_string(index=False))

print()
print(f"=== JQ position list on {ANOM_DATE.date()} (EOD) ===")
jp2 = jq_pos[jq_pos["date"] == ANOM_DATE][["security", "amount", "avg_cost", "price"]]
print(jp2.to_string(index=False))
print(f"n_positions: {len(jp2)}, total_value: {(jp2['amount']*jp2['price']).sum():,.0f}")

print()
print(f"=== JQ daily metric on {ANOM_DATE.date()} ===")
jd = jq_daily[jq_daily["date"] == ANOM_DATE]
print(jd[["date", "daily_strategy_return", "nav", "drawdown"]].to_string(index=False))

print()
print("=" * 80)
print(f"=== v15 trades on {ANOM_DATE.date()} ===")
print("=" * 80)
vt = v15_trades[v15_trades["date"] == ANOM_DATE]
print(vt[["code", "direction", "shares", "price", "value", "reason"]].to_string(index=False))

print()
print(f"=== v15 trades on {PRIOR_DATE.date()} ===")
vt2 = v15_trades[v15_trades["date"] == PRIOR_DATE]
print(vt2[["code", "direction", "shares", "price", "value", "reason"]].to_string(index=False))

# Reconstruct v15 positions on PRIOR and ANOM
print()
print("=" * 80)
print(f"=== Reconstruct v15 EOD positions on {PRIOR_DATE.date()} from trades log ===")
print("=" * 80)
v15_sorted = v15_trades.sort_values("date").copy()
held = {}  # code -> shares
for _, t in v15_sorted[v15_sorted["date"] <= PRIOR_DATE].iterrows():
    if t["direction"] == "buy":
        held[t["code"]] = held.get(t["code"], 0) + t["shares"]
    elif t["direction"] == "sell":
        held[t["code"]] = held.get(t["code"], 0) - t["shares"]
        if held[t["code"]] <= 0:
            del held[t["code"]]

print(f"v15 held EOD {PRIOR_DATE.date()}: {len(held)} positions")
for c, s in sorted(held.items()):
    print(f"  {c}: {s} shares")

# Same for ANOM_DATE
held_eod = dict(held)
for _, t in v15_sorted[v15_sorted["date"] == ANOM_DATE].iterrows():
    if t["direction"] == "buy":
        held_eod[t["code"]] = held_eod.get(t["code"], 0) + t["shares"]
    elif t["direction"] == "sell":
        held_eod[t["code"]] = held_eod.get(t["code"], 0) - t["shares"]
        if held_eod[t["code"]] <= 0:
            del held_eod[t["code"]]
print()
print(f"v15 held EOD {ANOM_DATE.date()}: {len(held_eod)} positions")
for c, s in sorted(held_eod.items()):
    print(f"  {c}: {s} shares")
