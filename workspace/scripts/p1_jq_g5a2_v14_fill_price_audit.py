"""v14 vs JQ fill-price audit.

For each JQ trade, compare:
  - JQ's recorded fill price (10:30 minute price)
  - v14's actual fill price (local Qlib open price × slippage)

If v14's BUY fills are systematically LOWER than JQ in 2025 and HIGHER in 2023,
that explains the year-by-year direction of the execution-edge gap.

Approach: cross-join JQ trades with v14 trades on (date, code, direction).
Compute price_diff_pct = (jq_price - v14_price) / jq_price.

Aggregate by year, direction. If buys have positive diff_pct in 2025 (jq>v14)
and negative in 2023 (jq<v14), our local opens drift below/above JQ's 10:30
fills systematically in those years.
"""

import pandas as pd
from pathlib import Path
import numpy as np

P = Path(r"E:/量化系统")
v14 = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v14_jq_replay_run/event_driven_trades.csv",
                  parse_dates=["date"])
jq = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv",
                 parse_dates=["time"])
jq["date"] = jq["time"].dt.normalize()
jq["code_ts"] = jq["security"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")
jq["direction"] = jq["action"].map({"open": "buy", "close": "sell"})
jq_clean = jq[["date", "code_ts", "direction", "price", "amount"]].rename(columns={"code_ts": "code", "price": "jq_price", "amount": "jq_shares"})

# Outer-merge on (date, code, direction)
merged = v14.merge(
    jq_clean,
    left_on=["date", "code", "direction"],
    right_on=["date", "code", "direction"],
    how="outer",
    suffixes=("_v14", "_jq"),
)
print(f"Total v14 trades: {len(v14)}")
print(f"Total JQ trades: {len(jq)}")
print(f"Merged rows (date+code+direction): {len(merged)}")

# Both-present rows
both = merged.dropna(subset=["price", "jq_price"])
print(f"Both-present rows: {len(both)}")
print()

# Price diff
both = both.assign(
    diff_pct=(both["jq_price"] - both["price"]) / both["jq_price"] * 100,
    year=both["date"].dt.year,
)

# Aggregate
print("Median JQ_price - v14_price diff (pp) by year and direction:")
print("(positive: JQ price > v14 price; i.e., v14 got better fill)")
pivot = both.groupby(["year", "direction"])["diff_pct"].agg(["median", "mean", "count"]).round(3)
print(pivot.to_string())

print()
print("Big-impact years (where execution edge was extreme in attribution):")
for yr in [2015, 2017, 2022, 2023, 2024, 2025]:
    sub = both[both["year"] == yr]
    if sub.empty:
        continue
    buy = sub[sub["direction"] == "buy"]
    sell = sub[sub["direction"] == "sell"]
    print(f"  {yr}: n_buy={len(buy):>4d}  mean_buy_diff_pct={buy['diff_pct'].mean():>+7.3f}%"
          f"   n_sell={len(sell):>4d}  mean_sell_diff_pct={sell['diff_pct'].mean():>+7.3f}%")
