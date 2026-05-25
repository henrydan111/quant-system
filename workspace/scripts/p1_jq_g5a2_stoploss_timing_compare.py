"""Test the stoploss-timing hypothesis for the v19-vs-JQ-verify gap.

JQ-verify CSV has 当日平仓 (daily closed-position value). On a market_stoploss
day the strategy sells ~everything, so 当日平仓 ≈ full portfolio value and the
position count collapses. Detect JQ-verify's mass-sell (stoploss) days and
compare to v19's market_stoploss firing days. If they fire on DIFFERENT days,
that explains the bidirectional per-year exposure differences."""

import pandas as pd
import numpy as np
from pathlib import Path

P = Path(r"E:/量化系统")

# JQ-verify CSV
jqv = pd.read_csv(P / "Knowledge/聚宽回测数据/result_1 (1).csv", encoding="gbk")
jqv.columns = ["time", "bench", "strat", "daily_pnl", "daily_open_val", "daily_close_val", "col6", "drawdown"]
jqv["date"] = pd.to_datetime(jqv["time"]).dt.normalize()
jqv["nav"] = 1.0 + jqv["strat"].astype(float) / 100.0
# Portfolio value proxy = nav (×100k). daily_close_val is in yuan.
jqv["pv"] = jqv["nav"] * 100000.0
# mass-sell ratio = daily_close_val / portfolio value
jqv["close_ratio"] = jqv["daily_close_val"].abs() / jqv["pv"].replace(0, np.nan)
# A stoploss/pass-month clearout: close_ratio > 0.7 (sold most of the book)
jqv["mass_sell"] = jqv["close_ratio"] > 0.7

# v19 market_stoploss days (from trades)
v19_tr = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v19_nan_fix_run/event_driven_trades.csv", parse_dates=["date"])
v19_sl = set(v19_tr[v19_tr["reason"] == "market_stoploss"]["date"].dt.normalize())

print(f"v19 market_stoploss firing days: {len(v19_sl)}")
print(f"  per year: {pd.Series(sorted(v19_sl)).groupby(pd.Series(sorted(v19_sl)).dt.year).count().to_dict()}")
print()

# JQ-verify mass-sell days (excluding Jan/Apr pass-months)
jqv_ms = jqv[(jqv["mass_sell"]) & (~jqv["date"].dt.month.isin([1, 4]))]
jqv_ms_dates = set(jqv_ms["date"])
print(f"JQ-verify mass-sell days (close_ratio>0.7, excl. pass-months): {len(jqv_ms_dates)}")
print(f"  per year: {jqv_ms.groupby(jqv_ms['date'].dt.year).size().to_dict()}")
print()

# Compare: which v19 stoploss days does JQ-verify NOT mass-sell? and vice versa
v19_only = sorted(v19_sl - jqv_ms_dates)
jqv_only = sorted(jqv_ms_dates - v19_sl)
both = sorted(v19_sl & jqv_ms_dates)
print(f"Both fired: {len(both)} → {[str(d.date()) for d in both]}")
print(f"v19 fired but JQ-verify did NOT mass-sell: {len(v19_only)} → {[str(d.date()) for d in v19_only][:20]}")
print(f"JQ-verify mass-sold but v19 did NOT stoploss: {len(jqv_only)} → {[str(d.date()) for d in jqv_only][:20]}")

# For the big-gap years, show JQ-verify's mass-sell timing
print()
print("Mass-sell / stoploss days by year (v19 SL vs JQ-verify mass-sell):")
years = range(2014, 2027)
for yr in years:
    v19_y = sorted([d for d in v19_sl if d.year == yr])
    jqv_y = sorted([d for d in jqv_ms_dates if d.year == yr])
    if v19_y or jqv_y:
        print(f"  {yr}: v19_SL={[str(d.date()) for d in v19_y]}  JQv_mass={[str(d.date()) for d in jqv_y]}")
