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
"""v17 — complete NAV reconstruction. Pure data calculation, no engine.

Algorithm:
  1. Start with cash = ¥100,000, positions = {}.
  2. For each JQ trade (sorted by date, then sells before buys within day):
       - For BUY: cash -= jq_shares × LOCAL_open[date, code] × (1 + slippage + commission)
                  positions[code] += jq_shares
       - For SELL: cash += jq_shares × LOCAL_open[date, code] × (1 - slippage - commission - stamp_tax)
                   positions[code] -= jq_shares
     Use LOCAL adjusted-open price (since we proved JQ uses adjusted prices too).
  3. At each EOD, compute portfolio NAV = cash + sum(positions[code] × LOCAL_close[date, code]).
  4. Compare NAV trajectory to JQ's daily NAV.

If v17 matches JQ NAV → the 11pp gap was entirely v15 implementation bug; data alignment is fine.
If v17 differs → quantify exactly how much."""

import pandas as pd
from pathlib import Path
import sys
import numpy as np
from collections import defaultdict

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))

import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

INITIAL_CASH = 100_000.0
COMMISSION = 0.00025
STAMP_TAX = 0.001
SLIPPAGE_PER_SHARE = 0.0003  # JQ FixedSlippage convention

# Load JQ trades
jq = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv", parse_dates=["time"])
jq["date"] = jq["time"].dt.normalize()
jq["code_qlib"] = jq["security"].str.replace(".XSHE", "_SZ").str.replace(".XSHG", "_SH")
jq["direction"] = jq["action"].map({"open": "buy", "close": "sell"})
jq_sorted = jq.sort_values(["date", "direction"]).copy()   # sells (close < open) first

jq_daily = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_daily.csv", parse_dates=["time"])
jq_daily["date"] = jq_daily["time"].dt.normalize()
jq_daily_idx = jq_daily.set_index("date")[["nav"]]

# Trade calendar
cal = pd.read_parquet(P / "data/reference/trade_cal.parquet")
cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
cal = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= jq["date"].min()) & (cal["cal_date"] <= jq["date"].max())]
trading_days = sorted(cal["cal_date"].unique())
print(f"Trading days: {len(trading_days)}")

# Bulk-load local open/close for all (date, code) pairs we'll need
all_codes = sorted(jq["code_qlib"].unique())
print(f"Loading $open/$close for {len(all_codes)} stocks…")
df = D.features(all_codes, ["$open", "$close"],
                start_time=jq["date"].min().strftime("%Y-%m-%d"),
                end_time=jq["date"].max().strftime("%Y-%m-%d"), freq="day")
df.columns = ["open", "close"]
df = df.reset_index()
df["date"] = pd.to_datetime(df["datetime"]).dt.normalize()
print(f"Loaded {len(df)} (date, code) rows of OHLC")

# Pivot to date×code lookups
open_lookup = df.set_index(["date", "instrument"])["open"]
close_lookup = df.set_index(["date", "instrument"])["close"]

# Reconstruct daily NAV
cash = INITIAL_CASH
positions = defaultdict(float)
results = []
trades_by_date = jq_sorted.groupby("date")
n_skipped = 0

for tdate in trading_days:
    tdate_ts = pd.Timestamp(tdate)
    if tdate_ts in trades_by_date.groups:
        day_trades = trades_by_date.get_group(tdate_ts)
        for _, t in day_trades.iterrows():
            code = t["code_qlib"]
            shares = float(t["amount"])
            # Use local open price (since JQ's price ≈ our adjusted open)
            try:
                px = float(open_lookup.loc[(tdate_ts, code)])
            except KeyError:
                px = float("nan")
            if not np.isfinite(px) or px <= 0:
                n_skipped += 1
                continue
            if t["direction"] == "buy":
                # Apply slippage: buy at (open + slippage)
                fill_px = px + SLIPPAGE_PER_SHARE
                gross = fill_px * shares
                commission_cost = max(gross * COMMISSION, 5.0)
                cash -= gross + commission_cost
                positions[code] += shares
            else:  # sell
                fill_px = max(px - SLIPPAGE_PER_SHARE, 0.01)
                gross = fill_px * shares
                commission_cost = max(gross * COMMISSION, 5.0)
                # Stamp tax depends on date (post-2023-08-28 = 0.0005, pre = 0.001)
                tax_rate = 0.0005 if tdate_ts >= pd.Timestamp("2023-08-28") else STAMP_TAX
                tax_cost = gross * tax_rate
                cash += gross - commission_cost - tax_cost
                positions[code] -= shares
                if positions[code] < 1e-6:
                    positions[code] = 0.0
    # EOD NAV = cash + sum(positions × local close)
    nav = cash
    for code, shares in positions.items():
        if shares <= 0:
            continue
        try:
            close_px = float(close_lookup.loc[(tdate_ts, code)])
            if np.isfinite(close_px):
                nav += shares * close_px
            else:
                # Suspended day — use last known close from JQ positions (price recorded for that day)
                # Fall back to keeping position at last MTM
                pass
        except KeyError:
            pass
    results.append({"date": tdate_ts, "v17_nav": nav, "v17_cash": cash, "n_pos": len([c for c, s in positions.items() if s > 0])})

print(f"Trades skipped (no local price): {n_skipped} / {len(jq)}")
res = pd.DataFrame(results)
# Merge JQ nav
res = res.merge(jq_daily_idx.reset_index(), on="date", how="left")
res["jq_nav_scaled"] = res["nav"] * INITIAL_CASH   # jq nav starts at 1.0; scale to 100k
res["v17_minus_jq_pct"] = (res["v17_nav"] - res["jq_nav_scaled"]) / res["jq_nav_scaled"] * 100

print()
print(f"v17 final NAV: {res['v17_nav'].iloc[-1]:,.0f}")
print(f"JQ final NAV: {res['jq_nav_scaled'].iloc[-1]:,.0f}")
print(f"Ratio v17/JQ: {res['v17_nav'].iloc[-1] / res['jq_nav_scaled'].iloc[-1]:.4f}")
print()

# Yearly summary
res["year"] = res["date"].dt.year
print("Per-year EOY ratios:")
print(f"{'year':<6} {'eoy_v17':>15} {'eoy_jq':>15} {'eoy_ratio':>10}")
for yr, grp in res.groupby("year"):
    eoy = grp.iloc[-1]
    print(f"{yr:<6} {eoy['v17_nav']:>15,.0f} {eoy['jq_nav_scaled']:>15,.0f} "
          f"{eoy['v17_nav']/eoy['jq_nav_scaled']:>10.4f}")

# Save
out = P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v15_jq_slippage_run/v17_nav_reconstruction.csv"
res.to_csv(out, index=False)
print(f"\nWrote: {out}")
