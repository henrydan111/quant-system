"""Compare market_cap rankings on a specific 2024 Tuesday between v9 and JoinQuant.

If JQ picked stocks v9 didn't (and both filter the same way), one of:
  (A) The total_mv values differ between data sources (Tushare vs JQ valuation)
  (B) The eligibility filter differs (375d, ST, KCBJ, paused)
  (C) Some 003-prefix names are excluded by v9 but not JQ

Approach: pick a Tuesday from 2024 where JQ picked names v9 didn't.
Reconstruct what v9 would have ranked and pick the top 12 — compare to JQ's actual picks."""

import pandas as pd
import sys
from pathlib import Path

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))

# Step 1: find a Tuesday in 2024 where v9 and JQ disagreed
v9_trades = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v9_jq_stoploss_parity_run/event_driven_trades.csv",
                       parse_dates=["date"])
jq_trades = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv",
                       parse_dates=["time"])
jq_trades["date"] = jq_trades["time"].dt.normalize()
v9_trades["code_norm"] = v9_trades["code"].str.replace(".SZ", ".XSHE").str.replace(".SH", ".XSHG")

# Find a Tuesday in 2024 with ≥4 disagreements
disagreement_dates = []
for d in jq_trades[jq_trades["date"].dt.year == 2024]["date"].unique():
    d_ts = pd.Timestamp(d)
    if d_ts.weekday() != 1:  # Tuesday
        continue
    v9_picks = set(v9_trades[(v9_trades["date"] == d_ts) & (v9_trades["direction"] == "buy")]["code_norm"])
    jq_picks = set(jq_trades[(jq_trades["date"] == d_ts) & (jq_trades["action"] == "open")]["security"])
    if len(jq_picks - v9_picks) >= 3:
        disagreement_dates.append((d_ts, len(jq_picks - v9_picks)))

disagreement_dates.sort(key=lambda x: x[0])
print("2024 Tuesdays with ≥3 JQ-not-v9 picks:")
for d, n in disagreement_dates[:10]:
    print(f"  {d.date()}  n_diff={n}")

if not disagreement_dates:
    print("No suitable Tuesday found.")
    sys.exit(0)

# Use the first such Tuesday
test_date = disagreement_dates[0][0]
print(f"\n=== Testing date: {test_date.date()} ===\n")

# Step 2: compute v9 ranking on this date using qlib
import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

# Build the 002/003 universe + survivor filter (matching v9)
sb = pd.read_parquet(P / "data/reference/stock_basic.parquet")
sb["list_date"] = pd.to_datetime(sb["list_date"], format="%Y%m%d", errors="coerce")
sb["delist_date"] = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")
sb = sb[sb["ts_code"].str.startswith("002") | sb["ts_code"].str.startswith("003")]
# Survivor cut
sb = sb[sb["delist_date"].isna() | (sb["delist_date"] >= pd.Timestamp("2024-01-01"))]
# 375d listing age
list_cutoff = test_date - pd.Timedelta(days=375)
sb = sb[(sb["list_date"] <= list_cutoff) & ((sb["delist_date"].isna()) | (sb["delist_date"] > test_date))]
# ST exclusion
st_rows = []
for line in (P / "data/qlib_data/instruments/st_stocks.txt").read_text(encoding="utf-8").splitlines():
    parts = line.strip().split("\t")
    if len(parts) < 3:
        continue
    st_rows.append({
        "ts_code": parts[0].replace("_", ".").upper(),
        "start": pd.to_datetime(parts[1], format="%Y-%m-%d", errors="coerce"),
        "end": pd.to_datetime(parts[2], format="%Y-%m-%d", errors="coerce"),
    })
st_df = pd.DataFrame(st_rows)
st_today = st_df[
    (st_df["start"].notna())
    & (st_df["start"] <= test_date)
    & ((st_df["end"].isna()) | (st_df["end"] > test_date))
]
sb = sb[~sb["ts_code"].isin(set(st_today["ts_code"]))]

uni_codes = sorted(sb["ts_code"].str.replace(".", "_").unique())
print(f"v9 universe on {test_date.date()}: {len(uni_codes)} stocks (002/003, alive 2024-01-01, 375d listed, non-ST)")

# Get Ref($total_mv, 1) for these stocks on test_date
df = D.features(uni_codes, ["Ref($total_mv, 1)", "$close", "$open"],
                start_time=(test_date - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
                end_time=(test_date + pd.Timedelta(days=2)).strftime("%Y-%m-%d"), freq="day")
df.columns = ["total_mv_lag1", "close", "open"]
df = df.reset_index()
df["date"] = pd.to_datetime(df["datetime"]).dt.normalize()
df["ts_code"] = df["instrument"].str.upper().str.replace("_", ".")
slice_ = df[df["date"] == test_date].dropna(subset=["total_mv_lag1"])

# Rank smallest first
ranked = slice_.nsmallest(30, "total_mv_lag1")
ranked["ts_code_jq"] = ranked["ts_code"].str.replace(".SZ", ".XSHE").str.replace(".SH", ".XSHG")
print("\nv9 top 30 by total_mv_lag1 (ascending):")
for i, row in enumerate(ranked.itertuples(), 1):
    print(f"  {i:2d}. {row.ts_code_jq:>12}  total_mv_lag1={row.total_mv_lag1:>10.2f}  close={row.close:.2f}")

# What did v9 actually pick on test_date?
v9_picks_actual = sorted(v9_trades[(v9_trades["date"] == test_date) & (v9_trades["direction"] == "buy")]["code_norm"])
jq_picks_actual = sorted(jq_trades[(jq_trades["date"] == test_date) & (jq_trades["action"] == "open")]["security"])

print(f"\nv9 actual picks ({test_date.date()}): {v9_picks_actual}")
print(f"JQ actual picks ({test_date.date()}): {jq_picks_actual}")
only_jq = sorted(set(jq_picks_actual) - set(v9_picks_actual))
only_v9 = sorted(set(v9_picks_actual) - set(jq_picks_actual))
print(f"\nOnly JQ ({len(only_jq)}): {only_jq}")
print(f"Only v9 ({len(only_v9)}): {only_v9}")

# Where do only-JQ picks rank in v9's universe?
print("\nWhere do JQ-only picks rank in v9's market_cap-ranked universe?")
ranked_full = slice_.sort_values("total_mv_lag1")
ranked_full["rank"] = range(1, len(ranked_full) + 1)
ranked_full["ts_code_jq"] = ranked_full["ts_code"].str.replace(".SZ", ".XSHE").str.replace(".SH", ".XSHG")
for c in only_jq:
    row = ranked_full[ranked_full["ts_code_jq"] == c]
    if row.empty:
        print(f"  {c}: NOT in v9 universe at all (filtered out!)")
    else:
        r = row.iloc[0]
        print(f"  {c}: v9 rank #{int(r['rank']):>4d}/{len(ranked_full)}  total_mv_lag1={r['total_mv_lag1']:.2f}")
