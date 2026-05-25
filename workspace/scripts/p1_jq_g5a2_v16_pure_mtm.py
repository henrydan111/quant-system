"""v16 — pure MTM test. NO engine, NO replay.

Algorithm:
  1. Load JQ's positions.csv. For each (date, security) pair, get JQ's
     held shares and price (JQ's recorded close price).
  2. For each date, compute:
       v16_value[date] = sum(jq_shares × LOCAL_close[code, date])
       jq_value[date]  = sum(jq_shares × jq_price[date])  [from positions.csv]
  3. Compare daily NAV trajectory.

If v16_value tracks jq_value exactly → our local prices match JQ's exactly.
If v16_value drifts by 11pp CAGR → that drift IS the gap from price-source
differences (adj_factor reference dates, intraday timing, MTM convention).

Cash is treated as a separate balance — we trust JQ's reported total NAV
includes both stock value and cash. v16 reconstructs the stock portion only;
the cash portion is identical between v16 and JQ (since v16 doesn't trade)."""

import pandas as pd
from pathlib import Path
import sys
import numpy as np

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))

import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

# Load JQ positions and daily NAV
jq_pos = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_positions.csv", parse_dates=["time"])
jq_pos["date"] = jq_pos["time"].dt.normalize()
jq_pos["code_qlib"] = jq_pos["security"].str.replace(".XSHE", "_SZ").str.replace(".XSHG", "_SH")
jq_pos["code_ts"] = jq_pos["security"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")

jq_daily = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_daily.csv", parse_dates=["time"])
jq_daily["date"] = jq_daily["time"].dt.normalize()

print(f"JQ positions rows: {len(jq_pos)}")
print(f"JQ daily rows: {len(jq_daily)}")
print(f"JQ date range: {jq_pos['date'].min().date()} to {jq_pos['date'].max().date()}")

# JQ-recorded stock value per day = sum(amount × price_jq)
jq_pos["jq_stock_value"] = jq_pos["amount"] * jq_pos["price"]
jq_stock_value_per_date = jq_pos.groupby("date")["jq_stock_value"].sum()

# Pull our local Qlib close for every (date, code) pair in JQ positions
all_codes = sorted(jq_pos["code_qlib"].unique())
start = jq_pos["date"].min().strftime("%Y-%m-%d")
end = jq_pos["date"].max().strftime("%Y-%m-%d")
print(f"Loading $close for {len(all_codes)} stocks from {start} to {end}…")
df_close = D.features(all_codes, ["$close", "$adj_factor"],
                      start_time=start, end_time=end, freq="day")
df_close.columns = ["close_adj", "adj_factor"]
df_close = df_close.reset_index()
df_close["date"] = pd.to_datetime(df_close["datetime"]).dt.normalize()
df_close["code_qlib"] = df_close["instrument"]
df_close["close_raw"] = df_close["close_adj"] / df_close["adj_factor"]

# Merge JQ positions with local prices
m = jq_pos.merge(
    df_close[["date", "code_qlib", "close_adj", "close_raw", "adj_factor"]],
    on=["date", "code_qlib"], how="left",
)

# v16 MTM using local adjusted close
m["v16_value_adj"] = m["amount"] * m["close_adj"]
m["v16_value_raw"] = m["amount"] * m["close_raw"]

# Per-day aggregate
v16_daily_adj = m.groupby("date")["v16_value_adj"].sum()
v16_daily_raw = m.groupby("date")["v16_value_raw"].sum()

# Compare to JQ stock value
cmp = pd.DataFrame({
    "jq_stock_value": jq_stock_value_per_date,
    "v16_value_adj": v16_daily_adj,
    "v16_value_raw": v16_daily_raw,
}).dropna()
cmp["ratio_v16adj_over_jq"] = cmp["v16_value_adj"] / cmp["jq_stock_value"]
cmp["ratio_v16raw_over_jq"] = cmp["v16_value_raw"] / cmp["jq_stock_value"]
cmp["log_ratio_adj"] = np.log(cmp["ratio_v16adj_over_jq"])
cmp["log_ratio_raw"] = np.log(cmp["ratio_v16raw_over_jq"])
cmp["year"] = cmp.index.year

print()
print("Per-year mean ratio (v16_value / jq_stock_value):")
print(f"{'year':<6} {'n_days':>8} {'med_ratio_ADJ':>15} {'med_ratio_RAW':>15} {'log_adj_eoy':>13} {'log_raw_eoy':>13}")
for yr, grp in cmp.groupby("year"):
    med_adj = grp["ratio_v16adj_over_jq"].median()
    med_raw = grp["ratio_v16raw_over_jq"].median()
    log_adj_eoy = grp["log_ratio_adj"].iloc[-1]
    log_raw_eoy = grp["log_ratio_raw"].iloc[-1]
    print(f"{yr:<6} {len(grp):>8d} {med_adj:>15.4f} {med_raw:>15.4f} {log_adj_eoy:>13.4f} {log_raw_eoy:>13.4f}")

# Cumulative-return mismatch
print()
v16_ret_adj = cmp["v16_value_adj"].pct_change()
jq_stock_ret = cmp["jq_stock_value"].pct_change()
v16_ret_raw = cmp["v16_value_raw"].pct_change()

corr_adj = v16_ret_adj.corr(jq_stock_ret)
corr_raw = v16_ret_raw.corr(jq_stock_ret)
print(f"Daily-return correlation v16(adj) vs jq_stock_value: {corr_adj:.6f}")
print(f"Daily-return correlation v16(raw) vs jq_stock_value: {corr_raw:.6f}")

# Save for inspection
out = P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v15_jq_slippage_run/v16_pure_mtm.csv"
cmp.to_csv(out)
print(f"\nWrote: {out}")
