"""Audit: what was v9's first trade date and which stocks were bought?
Compare with JoinQuant's first trade (2014-02-07) on the same date.
Both should be Tuesdays/Fridays in early Feb 2014 since strategy is weekly Tue 10:30."""

import pandas as pd
from pathlib import Path

P = Path(r"E:/量化系统")
v9_trades = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v9_jq_stoploss_parity_run/event_driven_trades.csv",
                       parse_dates=["date"])
v8_trades = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v8_100k_capital_run/event_driven_trades.csv",
                       parse_dates=["date"])
jq_trades = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv",
                       parse_dates=["time"])
jq_trades["date"] = jq_trades["time"].dt.normalize()

# First trades
print("=" * 80)
print("First trade dates")
print("=" * 80)
print(f"v9 first trade: {v9_trades['date'].min().date()}")
print(f"v8 first trade: {v8_trades['date'].min().date()}")
print(f"JQ first trade: {jq_trades['date'].min().date()}")

# v9 first day trades
first_d_v9 = v9_trades["date"].min()
print(f"\nv9 first-day trades ({first_d_v9.date()}):")
print(v9_trades[v9_trades["date"] == first_d_v9][["code", "direction", "shares", "price"]].to_string(index=False))

# JQ first day
first_d_jq = jq_trades["date"].min()
print(f"\nJQ first-day trades ({first_d_jq.date()}):")
print(jq_trades[jq_trades["date"] == first_d_jq][["security", "action", "amount", "price"]].to_string(index=False))

# Common stocks?
v9_codes = set(v9_trades[v9_trades["date"] == first_d_v9]["code"].str.replace(".SZ", ".XSHE").str.replace(".SH", ".XSHG"))
jq_codes = set(jq_trades[jq_trades["date"] == first_d_jq]["security"])
print(f"\nIntersection first-day picks: {len(v9_codes & jq_codes)} of {len(v9_codes)} v9 picks and {len(jq_codes)} jq picks")
print(f"Only v9: {sorted(v9_codes - jq_codes)}")
print(f"Only JQ: {sorted(jq_codes - v9_codes)}")

# 2014 trades summary
print("\n" + "=" * 80)
print("2014 buy-trade count by month")
print("=" * 80)
v9_2014 = v9_trades[(v9_trades["date"].dt.year == 2014) & (v9_trades["direction"] == "buy")]
jq_2014 = jq_trades[(jq_trades["date"].dt.year == 2014) & (jq_trades["action"] == "open")]
print(f"v9: {len(v9_2014)} buy trades; JQ: {len(jq_2014)} buy trades")
print(f"v9 unique buy dates: {v9_2014['date'].nunique()}; JQ unique buy dates: {jq_2014['date'].nunique()}")

# Compare typical Tuesday picks early 2014
for d in ["2014-02-07", "2014-02-11", "2014-02-18", "2014-02-25"]:
    d_ts = pd.Timestamp(d)
    v9_picks = v9_trades[(v9_trades["date"] == d_ts) & (v9_trades["direction"] == "buy")]["code"].tolist()
    jq_picks = jq_trades[(jq_trades["date"] == d_ts) & (jq_trades["action"] == "open")]["security"].tolist()
    v9_picks_norm = [c.replace(".SZ", ".XSHE").replace(".SH", ".XSHG") for c in v9_picks]
    common = set(v9_picks_norm) & set(jq_picks)
    print(f"\n{d}: v9_picks={len(v9_picks)} jq_picks={len(jq_picks)} common={len(common)}")
    if v9_picks_norm or jq_picks:
        print(f"  v9: {sorted(v9_picks_norm)}")
        print(f"  jq: {sorted(jq_picks)}")
