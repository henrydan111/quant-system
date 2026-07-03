# SCRIPT_STATUS: Class-B one-off compute-safety probe (kept). Isolates the length-safe onmom fix — tests 3
# limit-exclusion variants (bare If / +$close*0 anchor / no-exclusion) over 2011-H1 to pick the faithful
# length-safe form. Read-only (no registry / provider write).
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.stdout.reconfigure(encoding="utf-8")
from src.alpha_research.factor_library import operators

QDIR = str(ROOT / "data" / "qlib_data")
# candidate onmom exprs — anchor limit_status to price length so an empty limit_status bin
# (sparse in 2010-2011) degrades to "no exclusion" instead of a broadcast crash.
onret_v1 = ("If(Eq(Ref($limit_status, 1), 1), 0, "
            "Log(Ref(($open * $adj_factor), 1) / Ref(($close * $adj_factor), 2)))")  # current (crashes)
# anchor: add price*0 (length N, NaN where limit absent) so cond is length N; NaN != 1 -> take Log branch
onret_v2 = ("If(Eq(Ref($limit_status, 1) + Ref($close, 1) * 0, 1), 0, "
            "Log(Ref(($open * $adj_factor), 1) / Ref(($close * $adj_factor), 2)))")
onret_v3 = ("Log(Ref(($open * $adj_factor), 1) / Ref(($close * $adj_factor), 2))")  # no-exclusion fallback

for tag, onret in (("v1_current", onret_v1), ("v2_anchor", onret_v2), ("v3_noexcl", onret_v3)):
    expr = f"Sum({onret}, 250) - Sum({onret}, 20)"
    try:
        df, _ = operators.compute_factors(
            catalog={f"onmom_{tag}": expr}, start_date="2011-01-01", end_date="2011-06-30",
            horizons=None, qlib_dir=QDIR, kernels=1, stage="is_only")
        print(f"{tag:14} OK  nonnull={df.iloc[:,0].notna().mean():.3f}", flush=True)
    except Exception as e:
        print(f"{tag:14} CRASH  {str(e)[:80]}", flush=True)
