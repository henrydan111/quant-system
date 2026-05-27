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
"""CRITICAL engine-integrity check: is our Qlib $total_mv RAW or accidentally
adjusted by adj_factor?

If $total_mv is adjusted (= raw_total_mv scaled per-stock by adj_factor), the
cross-sectional smallest-market-cap RANKING is DISTORTED, causing v11 to pick
different stocks than JoinQuant (which ranks by raw valuation.market_cap).

Compare for sample stocks on 2015-07-27:
  - Qlib $total_mv (what v11 ranks by)
  - Tushare daily_basic.total_mv (raw, the ground truth)
  - ratio = Qlib / Tushare. If ratio == 1.0 → raw (correct). If ratio == adj_factor → BUG."""

import pandas as pd
from pathlib import Path
import sys

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))

import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

TEST_DATE = pd.Timestamp("2015-07-27")

# Sample 002 stocks
sample = ["002058", "002125", "002193", "002213", "002607", "002634", "002136", "002435"]
codes_qlib = [c + "_SZ" for c in sample]

# Qlib values
df = D.features(codes_qlib, ["$total_mv", "$close", "$adj_factor"],
                start_time=TEST_DATE.strftime("%Y-%m-%d"), end_time=TEST_DATE.strftime("%Y-%m-%d"), freq="day")
df.columns = ["qlib_total_mv", "qlib_close_adj", "adj_factor"]
df = df.reset_index()
df["ts_code"] = df["instrument"].str.replace("_", ".")

# Tushare raw daily_basic
db_path = P / "data/market/daily_basic"
print(f"daily_basic dir exists: {db_path.exists()}")
# Try to find the parquet
tushare_rows = []
import glob
db_files = list(db_path.glob("*.parquet")) if db_path.exists() else []
print(f"daily_basic parquet files: {len(db_files)}")

# Load daily_basic for 2015 — try a yearly or monthly partition
candidates = [
    P / "data/market/daily_basic.parquet",
    P / "data/market/daily_basic/2015.parquet",
]
db = None
for c in candidates:
    if c.exists():
        db = pd.read_parquet(c)
        print(f"Loaded daily_basic from {c}: {db.shape}")
        break
if db is None and db_files:
    # Load all and filter
    parts = []
    for f in db_files[:50]:
        try:
            d = pd.read_parquet(f, columns=["ts_code", "trade_date", "total_mv", "close"])
            parts.append(d)
        except Exception:
            d = pd.read_parquet(f)
            parts.append(d)
    db = pd.concat(parts, ignore_index=True) if parts else None
    if db is not None:
        print(f"Loaded daily_basic from {len(db_files)} partition files: {db.shape}")

print()
print(f"{'code':<12} {'qlib_total_mv':>15} {'qlib_close_adj':>15} {'adj_factor':>11}")
for _, r in df.iterrows():
    print(f"{r['ts_code']:<12} {r['qlib_total_mv']:>15,.1f} {r['qlib_close_adj']:>15.3f} {r['adj_factor']:>11.4f}")

if db is not None:
    db["trade_date"] = db["trade_date"].astype(str)
    db_d = db[db["trade_date"] == "20150727"]
    print()
    print("Tushare daily_basic (RAW) on 20150727:")
    print(f"{'code':<12} {'tushare_total_mv':>17} {'tushare_close':>14}")
    merge_rows = []
    for c in sample:
        ts_c = c + ".SZ"
        row = db_d[db_d["ts_code"] == ts_c]
        if not row.empty:
            tmv = row.iloc[0]["total_mv"]
            tcl = row.iloc[0].get("close", float("nan"))
            print(f"{ts_c:<12} {tmv:>17,.1f} {tcl:>14.3f}")
            qrow = df[df["ts_code"] == ts_c]
            if not qrow.empty:
                merge_rows.append({
                    "code": ts_c,
                    "qlib_total_mv": qrow.iloc[0]["qlib_total_mv"],
                    "tushare_total_mv": tmv,
                    "ratio_qlib_over_tushare": qrow.iloc[0]["qlib_total_mv"] / tmv if tmv else float("nan"),
                    "adj_factor": qrow.iloc[0]["adj_factor"],
                })
    print()
    print("=" * 80)
    print("RATIO check: qlib_total_mv / tushare_total_mv vs adj_factor")
    print("(ratio == 1.0 → RAW, correct. ratio == adj_factor → BUG: total_mv is adjusted)")
    print("=" * 80)
    cmp = pd.DataFrame(merge_rows)
    print(cmp.to_string(index=False))
