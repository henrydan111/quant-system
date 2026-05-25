"""Compare year-by-year unique stocks bought by v9 vs JoinQuant.
Tests whether JQ's selection universe includes delisted names that v9 excludes
via the survivor filter (RESTRICT_TO_SURVIVORS_ONLY=True, cutoff=2024-01-01)."""

import pandas as pd
from pathlib import Path

P = Path(r"E:/量化系统")
v9_trades = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v9_jq_stoploss_parity_run/event_driven_trades.csv",
                       parse_dates=["date"])
jq_trades = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv",
                       parse_dates=["time"])
jq_trades["date"] = jq_trades["time"].dt.normalize()

# Normalize codes: v9 uses .SZ, JQ uses .XSHE
v9_trades["code_norm"] = v9_trades["code"].str.replace(".SZ", ".XSHE").str.replace(".SH", ".XSHG")

# Buy trades only
v9_buys = v9_trades[v9_trades["direction"] == "buy"]
jq_buys = jq_trades[jq_trades["action"] == "open"]

# Year-by-year unique picks
print(f"{'Year':<6} {'v9_uniq':>8} {'JQ_uniq':>8} {'v9∩JQ':>8} {'only_v9':>9} {'only_JQ':>9}")
print("-" * 60)
for year in range(2014, 2027):
    v9_y = set(v9_buys[v9_buys["date"].dt.year == year]["code_norm"])
    jq_y = set(jq_buys[jq_buys["date"].dt.year == year]["security"])
    inter = v9_y & jq_y
    only_v9 = v9_y - jq_y
    only_jq = jq_y - v9_y
    print(f"{year:<6d} {len(v9_y):>8d} {len(jq_y):>8d} {len(inter):>8d} {len(only_v9):>9d} {len(only_jq):>9d}")

# Detail: 2014 only-JQ picks (could be survivor-filtered names)
print()
print("=" * 80)
print("2014 only-JQ picks (= stocks JQ bought that v9 did NOT):")
print("=" * 80)
v9_2014 = set(v9_buys[v9_buys["date"].dt.year == 2014]["code_norm"])
jq_2014 = set(jq_buys[jq_buys["date"].dt.year == 2014]["security"])
only_jq_2014 = sorted(jq_2014 - v9_2014)
print(f"{len(only_jq_2014)} stocks: {only_jq_2014}")

# For each only-JQ pick, what's its delisting status?
sb = pd.read_parquet(P / "data/reference/stock_basic.parquet")
sb["delist_date"] = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")
print()
print(f"{'JQ_only':<14} {'delist_date':<14} {'delisted_before_2024?'}")
for c in only_jq_2014:
    ts_c = c.replace(".XSHE", ".SZ").replace(".XSHG", ".SH")
    row = sb[sb["ts_code"] == ts_c]
    if not row.empty:
        d = row.iloc[0]["delist_date"]
        flag = (pd.notna(d) and d < pd.Timestamp("2024-01-01"))
        print(f"{c:<14} {str(d.date()) if pd.notna(d) else 'None':<14} {flag}")
    else:
        print(f"{c:<14} NOT IN stock_basic")

# 2024 only-JQ picks (the year with the biggest gap)
print()
print("=" * 80)
print("2024 only-JQ picks (the -65pp gap year):")
print("=" * 80)
v9_2024 = set(v9_buys[v9_buys["date"].dt.year == 2024]["code_norm"])
jq_2024 = set(jq_buys[jq_buys["date"].dt.year == 2024]["security"])
only_jq_2024 = sorted(jq_2024 - v9_2024)
only_v9_2024 = sorted(v9_2024 - jq_2024)
print(f"Only-JQ ({len(only_jq_2024)}): {only_jq_2024[:30]}...")
print(f"Only-v9 ({len(only_v9_2024)}): {only_v9_2024[:30]}...")
print(f"Intersection: {len(v9_2024 & jq_2024)} / v9={len(v9_2024)} / jq={len(jq_2024)}")

# Sample only-JQ 2024 picks: delist status
print()
delisted_pre24 = 0
delisted_post24 = 0
active = 0
for c in only_jq_2024:
    ts_c = c.replace(".XSHE", ".SZ").replace(".XSHG", ".SH")
    row = sb[sb["ts_code"] == ts_c]
    if row.empty:
        continue
    d = row.iloc[0]["delist_date"]
    if pd.isna(d):
        active += 1
    elif d < pd.Timestamp("2024-01-01"):
        delisted_pre24 += 1
    else:
        delisted_post24 += 1
print(f"Only-JQ 2024 picks status: active={active} delisted_pre2024={delisted_pre24} delisted_post2024={delisted_post24}")
