"""Full-catalog + candidate degeneracy sweep (factor audit, 2026-05-30) — LEAN.

Detects degenerate factors (constant cross-section / all-NaN / inf). A factor
that cannot rank is constant on essentially every day, so a 1-year window over
the full market is plenty.

Speed fixes vs the first attempt:
  * 1-year window (2018) instead of 3y.
  * Vectorized dispersion via per-date std (groupby on the date level once),
    NOT a per-column python groupby-nunique loop.
Read-only; writes a CSV report.
"""
import sys, csv
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from src.alpha_research.factor_library import operators as op
from src.alpha_research.factor_library.catalog import get_factor_catalog

IS_START, IS_END = "2018-01-01", "2018-12-31"
OUT = ROOT / "workspace/research/factor_expansion/factor_audit_degeneracy.csv"

cat = dict(get_factor_catalog(include_new_data=True))
mc = ROOT / "workspace/research/factor_expansion/factor_candidates_merged.csv"
for r in csv.DictReader(open(mc, encoding="utf-8")):
    cat.setdefault("CAND__" + r["name"], r["qlib_expression"])

# stk_limit fields ($up_limit/$down_limit) are empty for index instruments
# (e.g. 399001_SZ) and crash the whole-catalog D.features call. They are
# quarantine (anomaly review pending) and not formal-eligible — drop here so
# the sweep does not abort on them.
_LIMIT_FIELDS = ("$up_limit", "$down_limit")
_dropped_limit = [k for k, expr in cat.items() if any(f in expr for f in _LIMIT_FIELDS)]
for k in _dropped_limit:
    del cat[k]
if _dropped_limit:
    print(f"NOTE: dropped {len(_dropped_limit)} stk_limit-referencing factors "
          f"(quarantine; cause index-instrument crash): {_dropped_limit}", flush=True)

print(f"sweeping {len(cat)} expressions over {IS_START}..{IS_END}", flush=True)
f, _ = op.compute_factors(catalog=cat, start_date=IS_START, end_date=IS_END,
                          horizons=[5], qlib_dir=str(ROOT/"data"/"qlib_data"),
                          kernels=1, stage="is_only")
print(f"computed shape={f.shape}; analyzing dispersion (vectorized)...", flush=True)
names = f.index.names
date_level = 0 if names[0] == "datetime" else 1
dates = f.index.get_level_values(date_level)

rows = []
fvals = f.replace([np.inf, -np.inf], np.nan)
for c in f.columns:
    s = f[c]
    sv = fvals[c]
    n = len(s)
    nn = int(s.notna().sum())
    nullpct = round(100 * (1 - nn / n), 2) if n else 100.0
    n_inf = int(np.isinf(s.to_numpy(dtype="float64", na_value=np.nan)).sum())
    per_date_std = sv.groupby(dates).std()
    disp = round(float((per_date_std > 1e-12).mean()), 3) if len(per_date_std) else 0.0
    vals = sv.dropna()
    rng = (round(float(vals.min()), 4), round(float(vals.max()), 4)) if len(vals) else (None, None)
    flag = []
    if nn == 0: flag.append("ALL_NAN")
    elif disp < 0.05: flag.append("DEGENERATE_XS")
    if n_inf > 0: flag.append("HAS_INF")
    if nullpct > 90: flag.append("HIGH_NULL")
    rows.append({"factor": c, "null_pct": nullpct, "xs_dispersion": disp,
                 "n_inf": n_inf, "min": rng[0], "max": rng[1],
                 "flags": ";".join(flag) or "ok"})

df = pd.DataFrame(rows).sort_values(["flags", "xs_dispersion"])
df.to_csv(OUT, index=False)
bad = df[df["flags"] != "ok"]
print(f"\n=== {len(bad)} flagged / {len(df)} total ===", flush=True)
for _, r in bad.iterrows():
    print(f"  {r['factor']:44s} disp={r['xs_dispersion']:.3f} null%={r['null_pct']:5.1f} inf={r['n_inf']} -> {r['flags']}", flush=True)
print(f"\nfull report: {OUT}", flush=True)
