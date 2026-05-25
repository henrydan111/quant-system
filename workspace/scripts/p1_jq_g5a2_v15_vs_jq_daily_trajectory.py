"""Trace where the v15-vs-JQ 11.08pp residual accumulates day by day.

Compute the daily ratio v15_NAV / JQ_NAV. If the ratio decays LINEARLY → gradual
data drift. If it crashes on specific dates → discrete event mis-handling.

Also identify TOP 30 worst-divergence days for further investigation."""

import pandas as pd
import numpy as np
from pathlib import Path

P = Path(r"E:/量化系统")

v15 = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v15_jq_slippage_run/event_driven_report.csv")
cal = pd.read_parquet(P / "data/reference/trade_cal.parquet")
cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
cal = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= "2014-01-01") & (cal["cal_date"] <= "2026-02-27")]
cal = cal.sort_values("cal_date").reset_index(drop=True)
v15["date"] = cal["cal_date"].iloc[:len(v15)].values

jq = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_daily.csv", parse_dates=["time"])
jq["date"] = jq["time"].dt.normalize()
jq = jq[["date", "daily_strategy_return", "nav"]].rename(columns={"daily_strategy_return": "ret_jq", "nav": "nav_jq"})

df = v15[["date", "return"]].rename(columns={"return": "ret_v15"}).merge(jq, on="date", how="inner")
df["nav_v15"] = (1 + df["ret_v15"]).cumprod()

# Normalize to common starting point at first real trade date
first_trade = pd.Timestamp("2014-02-07")
df = df[df["date"] >= first_trade].reset_index(drop=True)
df["nav_v15"] = (1 + df["ret_v15"]).cumprod()
df["nav_jq_recompound"] = (1 + df["ret_jq"]).cumprod()
df["ratio_v15_over_jq"] = df["nav_v15"] / df["nav_jq_recompound"]
df["log_ratio"] = np.log(df["ratio_v15_over_jq"])

# Find days where the daily return DIFFERENCE is largest
df["daily_diff_pp"] = (df["ret_v15"] - df["ret_jq"]) * 100
df["year"] = df["date"].dt.year

print(f"Total trading days: {len(df)}")
print(f"Final v15 NAV (CNY1 start): {df['nav_v15'].iloc[-1]:.2f}")
print(f"Final JQ NAV (CNY1 start): {df['nav_jq_recompound'].iloc[-1]:.2f}")
print(f"Final ratio v15/JQ: {df['ratio_v15_over_jq'].iloc[-1]:.4f}")
print(f"Final log_ratio: {df['log_ratio'].iloc[-1]:.4f}")
print()

# Per-year compounded ret_v15 - ret_jq
print("Per-year cumulative (1 + ret).prod() comparison:")
print(f"{'year':<6} {'v15_yearly':>12} {'jq_yearly':>12} {'diff_pp':>10} {'log_ratio_eoy':>14}")
for yr, grp in df.groupby("year"):
    v15_y = (1 + grp["ret_v15"]).prod() - 1
    jq_y = (1 + grp["ret_jq"]).prod() - 1
    log_eoy = grp["log_ratio"].iloc[-1]
    print(f"{yr:<6} {v15_y*100:>+10.2f}% {jq_y*100:>+10.2f}% {(v15_y-jq_y)*100:>+9.2f}pp {log_eoy:>14.4f}")

# Worst 30 days for v15 vs JQ
print()
print("Top 30 days where v15's daily return MOST UNDERPERFORMED JQ:")
worst = df.nsmallest(30, "daily_diff_pp")
print(worst[["date", "ret_v15", "ret_jq", "daily_diff_pp"]].to_string(index=False))

# Best 30 days
print()
print("Top 30 days where v15 OUTPERFORMED JQ:")
best = df.nlargest(30, "daily_diff_pp")
print(best[["date", "ret_v15", "ret_jq", "daily_diff_pp"]].to_string(index=False))

# Save full trajectory for follow-up
out = P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v15_jq_slippage_run/v15_vs_jq_daily.csv"
df.to_csv(out, index=False)
print(f"\nWrote: {out}")
