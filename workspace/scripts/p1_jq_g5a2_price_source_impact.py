# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Sandbox / one-shot diagnostic script. NOT a formal research
#   surface. Bare D.features calls inside this file are tolerated
#   per scripts/lint_no_bare_qlib_features.py allowlist semantics
#   (PR 6) but the script's output is not eligible for the formal
#   release gate.
# ──────────────────────────────────────────────────────────────────────
"""Direct quantification: how much CASH P&L difference does the adjusted-vs-real
price gap produce across all 3,510 JQ trades?

For each (date, code, direction, jq_shares, jq_price) JQ trade:
  - v15 fill price = our_open_adjusted (loaded from local Qlib)
  - v15 actual shares bought = (jq_price * jq_shares) / our_open_adjusted   [BUY case]
  - v15 actual cash for sell = jq_shares * our_open_adjusted                [SELL case]

The DIRECT cash impact at the moment of trade:
  - BUY: v15 spends same target_value but gets more/fewer shares
  - SELL: v15 gets different cash than JQ for the same shares

This bounds the magnitude of the adjusted-price effect on cumulative wealth."""

import pandas as pd
from pathlib import Path
import sys
import numpy as np

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))

import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

# Load JQ trades
jq = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv", parse_dates=["time"])
jq["date"] = jq["time"].dt.normalize()
jq["code_ts"] = jq["security"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")
jq["code_qlib"] = jq["code_ts"].str.replace(".", "_")
jq["direction"] = jq["action"].map({"open": "buy", "close": "sell"})

# Load all Qlib data needed for the trades — $open, $adj_factor
all_codes = sorted(jq["code_qlib"].unique())
start = jq["date"].min().strftime("%Y-%m-%d")
end = (jq["date"].max() + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
print(f"Loading Qlib data for {len(all_codes)} codes from {start} to {end}…")
df = D.features(all_codes, ["$open", "$close", "$adj_factor"], start_time=start, end_time=end, freq="day")
df.columns = ["open_adj", "close_adj", "adj_factor"]
df = df.reset_index()
df["date"] = pd.to_datetime(df["datetime"]).dt.normalize()
df["code_qlib"] = df["instrument"]

# Compute RAW open and close prices
df["open_raw"] = df["open_adj"] / df["adj_factor"]
df["close_raw"] = df["close_adj"] / df["adj_factor"]

# Merge JQ trades with Qlib data
m = jq.merge(df[["date", "code_qlib", "open_adj", "open_raw", "close_adj", "close_raw", "adj_factor"]],
             on=["date", "code_qlib"], how="left")

# Restrict to trades with valid data
m = m.dropna(subset=["open_adj", "adj_factor"])
print(f"Trades with valid Qlib data: {len(m)} / {len(jq)}")

# Compute price discrepancies
m["adj_vs_raw_diff_pct"] = (m["open_adj"] - m["open_raw"]) / m["open_raw"] * 100
m["jq_vs_local_diff_pct"] = (m["price"] - m["open_adj"]) / m["price"] * 100
m["jq_vs_raw_diff_pct"] = (m["price"] - m["open_raw"]) / m["price"] * 100

# Cash P&L impact per trade
# v15 BUY: target_value = jq_price * jq_shares; engine fills at open_adj → buys (target_value/open_adj) shares
#       Net cash spent = target_value (same as JQ)
#       BUT shares acquired differ: v15_shares - jq_shares = (jq_price * jq_shares / open_adj) - jq_shares
# v15 SELL: shares sold = jq_shares (we passed target_shares = jq_shares for sells)
#       Cash received = jq_shares * open_adj
#       JQ cash received = jq_shares * jq_price
#       v15_cash - jq_cash = jq_shares * (open_adj - jq_price)
m["jq_shares"] = m["amount"]
m["jq_value"] = m["jq_shares"] * m["price"]

# Yearly summary
m["year"] = m["date"].dt.year
print()
print("=== Yearly summary: open_adj vs open_raw vs JQ_price ===")
print(f"(positive = local adjusted/raw > JQ price)")
print(f"{'year':<6} {'n':>5} {'med_jq_vs_raw':>16} {'med_jq_vs_adj':>16} {'med_adj_vs_raw':>16}")
for yr, sub in m.groupby("year"):
    print(f"{yr:<6} {len(sub):>5} "
          f"{sub['jq_vs_raw_diff_pct'].median():>+16.3f}% "
          f"{sub['jq_vs_local_diff_pct'].median():>+16.3f}% "
          f"{sub['adj_vs_raw_diff_pct'].median():>+16.3f}%")

# Sample: 2014 first trade
first = m[m["date"] == pd.Timestamp("2014-02-07")].head(5)
print()
print("=== 2014-02-07 sample trades ===")
print(first[["code_qlib", "direction", "price", "open_adj", "open_raw", "adj_factor", "jq_vs_raw_diff_pct"]].to_string(index=False))

# Sample: 2025 trades (where v14 wildly outperformed JQ)
recent = m[m["date"] >= "2025-09-01"].head(15)
print()
print("=== 2025 recent trades sample ===")
print(recent[["code_qlib", "date", "direction", "price", "open_adj", "open_raw", "adj_factor", "jq_vs_raw_diff_pct"]].to_string(index=False))
