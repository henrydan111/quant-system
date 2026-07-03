import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.stdout.reconfigure(encoding="utf-8")
from src.alpha_research.factor_library.catalog import get_factor_catalog
from src.alpha_research.factor_library import operators

full = get_factor_catalog(include_new_data=True)
FACTORS = [k for k in full if k.startswith("grn_")]
crash = 0
for f in FACTORS:
    try:
        df, _ = operators.compute_factors(
            catalog={f: full[f]}, start_date="2011-01-01", end_date="2011-06-30",
            horizons=None, qlib_dir=str(ROOT / "data" / "qlib_data"), kernels=1, stage="is_only")
        print(f"{f:24} OK  nonnull={df.iloc[:,0].notna().mean():.3f}", flush=True)
    except Exception as e:
        crash += 1
        print(f"{f:24} CRASH  {type(e).__name__}: {str(e)[:90]}", flush=True)
print(f"\n=== {len(FACTORS)-crash}/{len(FACTORS)} OK, {crash} CRASH ===")
