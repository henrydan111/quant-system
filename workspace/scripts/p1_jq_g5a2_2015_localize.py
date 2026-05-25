"""Localize the 2015 gap (JQ-verify +305% vs v18 +169%, ~136pp).
Is it stoploss firing differently, or stock selection?

Compare:
  - JQ-verify daily returns + trade activity (from result CSV: 当日开仓/当日平仓)
  - v18 daily returns + market_stoploss firings (from v18 trades)
in 2015, to see if v18 went to cash (stoploss) on days JQ-verify stayed invested."""

import pandas as pd
import numpy as np
from pathlib import Path

P = Path(r"E:/量化系统")

# JQ-verify CSV
jqv = pd.read_csv(P / "Knowledge/聚宽回测数据/result_1 (1).csv", encoding="gbk")
jqv.columns = ["time", "bench_cum", "strat_cum", "daily_pnl", "daily_open_val", "daily_close_val", "col6", "drawdown"]
jqv["date"] = pd.to_datetime(jqv["time"]).dt.normalize()
jqv["strat_cum"] = jqv["strat_cum"].astype(float)
jqv["nav"] = 1.0 + jqv["strat_cum"] / 100.0
jqv["daily_ret"] = jqv["nav"].pct_change()
jqv2015 = jqv[(jqv["date"] >= "2015-06-01") & (jqv["date"] <= "2015-09-30")].copy()

# v18 daily report
v18 = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v18_no_trim_run/event_driven_report.csv")
cal = pd.read_parquet(P / "data/reference/trade_cal.parquet")
cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
cal = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= "2014-01-01") & (cal["cal_date"] <= "2026-02-27")]
cal = cal.sort_values("cal_date").reset_index(drop=True)
v18["date"] = cal["cal_date"].iloc[:len(v18)].values
v18["date"] = pd.to_datetime(v18["date"])

# v18 trades — find market_stoploss / pass_month firings
v18_tr = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v18_no_trim_run/event_driven_trades.csv", parse_dates=["date"])
stoploss_dates = set(v18_tr[v18_tr["reason"] == "market_stoploss"]["date"].dt.normalize())

# Merge for 2015 summer
v18_2015 = v18[(v18["date"] >= "2015-06-01") & (v18["date"] <= "2015-09-30")].copy()
m = jqv2015[["date", "daily_ret", "daily_open_val", "daily_close_val", "drawdown"]].merge(
    v18_2015[["date", "return", "n_positions", "cash", "total_value"]], on="date", how="inner")
m["v18_stoploss"] = m["date"].isin(stoploss_dates)
m["diff_pp"] = (m["return"] - m["daily_ret"]) * 100

print("2015 summer day-by-day: JQ-verify vs v18")
print(f"{'date':<12} {'jqv_ret':>9} {'v18_ret':>9} {'diff_pp':>9} {'v18_npos':>9} {'v18_cash%':>10} {'v18_SL':>7}")
for _, r in m.iterrows():
    cash_pct = r["cash"] / r["total_value"] * 100 if r["total_value"] else 0
    sl = "FIRE" if r["v18_stoploss"] else ""
    print(f"{r['date'].date()!s:<12} {r['daily_ret']*100:>+8.2f}% {r['return']*100:>+8.2f}% "
          f"{r['diff_pp']:>+8.2f} {int(r['n_positions']):>9} {cash_pct:>9.0f}% {sl:>7}")

# Count days v18 was mostly cash in 2015 full year
v18_2015_full = v18[(v18["date"] >= "2015-01-01") & (v18["date"] <= "2015-12-31")].copy()
v18_2015_full["cash_pct"] = v18_2015_full["cash"] / v18_2015_full["total_value"]
mostly_cash = (v18_2015_full["cash_pct"] > 0.8).sum()
print()
print(f"v18 2015: days >80% cash = {mostly_cash} / {len(v18_2015_full)}")
print(f"v18 2015 market_stoploss firings: {len([d for d in stoploss_dates if d.year==2015])}")
print(f"   dates: {sorted([str(d.date()) for d in stoploss_dates if d.year==2015])}")
