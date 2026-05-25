"""Find the FIRST date where v15's executed trades diverged from JQ's intended trades.
Once divergence happens, subsequent sells of non-held stocks fail, and the
positions cascade-diverge.

For each JQ trade (date, code, action, amount), check:
  - Did v15 execute it?
  - If not, why? (need to check v15's order audit log or infer from trades csv)

If v15 didn't execute many JQ trades, that's the bug — likely because:
  (a) v15's engine blocked sell of code not held (due to earlier-day cascade)
  (b) v15's engine blocked buy due to insufficient cash
  (c) Data missing for that code/date in our Qlib"""

import pandas as pd
from pathlib import Path

P = Path(r"E:/量化系统")

jq_trades = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv", parse_dates=["time"])
jq_trades["date"] = jq_trades["time"].dt.normalize()
jq_trades["code_ts"] = jq_trades["security"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")
jq_trades["direction"] = jq_trades["action"].map({"open": "buy", "close": "sell"})

v15_trades = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v15_jq_slippage_run/event_driven_trades.csv", parse_dates=["date"])

# For each JQ trade, check if v15 has a matching trade
jq_key = jq_trades[["date", "code_ts", "direction", "amount"]].copy()
jq_key["jq_trade_id"] = range(len(jq_key))
v15_key = v15_trades[["date", "code", "direction", "shares"]].rename(columns={"code": "code_ts"}).copy()
v15_key["v15_trade_id"] = range(len(v15_key))

# Outer merge on (date, code_ts, direction)
merged = jq_key.merge(v15_key, on=["date", "code_ts", "direction"], how="outer", suffixes=("_jq", "_v15"))

# How many JQ trades have NO v15 match?
not_replayed = merged[merged["v15_trade_id"].isna()].copy()
print(f"Total JQ trades: {len(jq_trades)}")
print(f"Total v15 trades: {len(v15_trades)}")
print(f"JQ trades with NO v15 match: {len(not_replayed)}")
print()
print("Not-replayed JQ trades by year and direction:")
not_replayed["year"] = not_replayed["date"].dt.year
print(not_replayed.groupby(["year", "direction"]).size().to_string())

# v15 trades not in JQ (engine generated extras?)
extra = merged[merged["jq_trade_id"].isna()]
print()
print(f"v15 trades NOT IN JQ list: {len(extra)} (should be 0; if not, v15 engine has phantom trades)")

# When did the first divergence happen?
print()
print("First 30 JQ trades where v15 didn't execute (chronological):")
nr_sorted = not_replayed.sort_values(["date", "code_ts"])[["date", "code_ts", "direction", "amount"]]
print(nr_sorted.head(30).to_string(index=False))

# Did v15 execute partially (different amount)?
both = merged.dropna(subset=["jq_trade_id", "v15_trade_id"]).copy()
both["share_ratio"] = both["shares"] / both["amount"]
print()
print(f"Both-present trades: {len(both)}")
print("Share-ratio distribution (v15_shares / jq_amount):")
print(f"  median: {both['share_ratio'].median():.4f}")
print(f"  mean: {both['share_ratio'].mean():.4f}")
print(f"  min: {both['share_ratio'].min():.4f}")
print(f"  max: {both['share_ratio'].max():.4f}")
print(f"  std: {both['share_ratio'].std():.4f}")
print(f"  pct of trades where share_ratio < 0.5: {(both['share_ratio'] < 0.5).mean() * 100:.1f}%")
print(f"  pct of trades where share_ratio > 0.5 and < 0.95: {((both['share_ratio'] >= 0.5) & (both['share_ratio'] < 0.95)).mean() * 100:.1f}%")
print(f"  pct of trades where share_ratio between 0.95 and 1.05: {((both['share_ratio'] >= 0.95) & (both['share_ratio'] < 1.05)).mean() * 100:.1f}%")
