# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Zero-vs-NaN structural-zero audit (GPT Round-6 condition #1). Read-only
#   diagnostic: quantifies how Tushare encodes a true-zero balance-sheet line
#   vs a not-reported one for goodwill/lt_borr/st_borr across raw parquet, PIT
#   ledger, and provider D.features. No mutation.
# ──────────────────────────────────────────────────────────────────────
"""Zero-vs-NaN structural-zero audit (GPT Round-6 condition #1).

For goodwill / lt_borr / st_borr: determine how Tushare encodes a true-zero
balance-sheet line vs a not-reported one, across:
  (a) raw Tushare balancesheet parquet (aggregated over many periods),
  (b) the PIT ledger,
  (c) the provider D.features _q0 output.
If true-zero is encoded as NaN (indistinguishable from not-reported), factors
like acc_goodwill_ratio are biased toward firms that report the item.

FINDING (2026-05-31, pooled 2018-2023 annual periods): true-zero is NOT encoded
as 0.0 — it is NaN. zero% is <1.3% at every layer while nan% is 24-55%
(goodwill 54% nan / 0.85% zero; lt_borr 48% / 1.1%; st_borr 24% / 0.7%;
total_assets control 0% nan). CONCLUSION: true-zero is INDISTINGUISHABLE from
not-reported for these fields. acc_goodwill_ratio + acc_noa_scaled are biased
toward reporting firms — marked structural_zero_pending; kept out of the OOS
top set until resolved.
Read-only.
"""
import sys, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd

FIELDS = ["goodwill", "lt_borr", "st_borr", "total_assets", "inventories"]

def dist(s: pd.Series) -> dict:
    n = len(s)
    return {
        "n": n,
        "nan%": round(100 * s.isna().mean(), 1),
        "zero%": round(100 * (s == 0).sum() / n, 2) if n else 0.0,
        "pos%": round(100 * (s > 0).sum() / n, 1) if n else 0.0,
        "neg%": round(100 * (s < 0).sum() / n, 1) if n else 0.0,
    }

print("=== (a) RAW Tushare balancesheet — pooled across recent annual periods ===", flush=True)
# pool several year-end partitions with real volume (2018-2023 Q4)
files = []
for yr in ["20181231", "20191231", "20201231", "20211231", "20221231", "20231231"]:
    p = ROOT / "data" / "fundamentals" / "balancesheet" / f"balancesheet_{yr}.parquet"
    if p.exists():
        files.append(p)
raw = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
print(f"pooled raw rows: {len(raw)} from {len(files)} annual partitions", flush=True)
for c in FIELDS:
    if c in raw.columns:
        print(f"  raw {c:14s} {dist(raw[c])}", flush=True)
    else:
        print(f"  raw {c:14s} COLUMN ABSENT", flush=True)

print("\n=== (b) PIT ledger (balancesheet.parquet) ===", flush=True)
led = pd.read_parquet(ROOT / "data" / "pit_ledger" / "balancesheet" / "balancesheet.parquet",
                      columns=[c for c in FIELDS if True])
for c in FIELDS:
    if c in led.columns:
        print(f"  ledger {c:14s} {dist(led[c])}", flush=True)

print("\n=== (c) PROVIDER D.features _q0 (2018 full market sample) ===", flush=True)
qlib_dir = ROOT / "data" / "qlib_data"
if (qlib_dir / "calendars" / "day.txt").exists():
    from src.alpha_research.factor_library import operators as op
    cat = {f"{c}_q0": f"Ref(${c}_q0, 1)" for c in ["goodwill", "lt_borr", "st_borr", "total_assets"]}
    f, _ = op.compute_factors(catalog=cat, start_date="2018-06-01", end_date="2018-06-30",
                              horizons=[5], qlib_dir=str(qlib_dir), kernels=1, stage="is_only")
    for col in f.columns:
        s = f[col]
        print(f"  provider {col:18s} {dist(s)}", flush=True)
else:
    print("  provider absent — skip", flush=True)

print("\nINTERPRETATION:", flush=True)
print("  If zero%≈0 and nan% is high for goodwill/lt_borr/st_borr at ALL three layers,", flush=True)
print("  then Tushare encodes 'no goodwill' as NaN (NOT 0) and true-zero is", flush=True)
print("  INDISTINGUISHABLE from not-reported -> acc_goodwill_ratio etc. are biased", flush=True)
print("  toward reporting firms. total_assets (always present) is the control.", flush=True)
print("DONE", flush=True)
