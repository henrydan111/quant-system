"""Validate _materialize_quality_stability (pit_backend) vs the rung-6 deepslot f9/f10 (the +14.3pp truth).

Runs the REAL materializer via a tiny scoped staged build (test basket, field_filter=[2 output fields] so
ONLY the 2 stability fields materialize — it reads the income/balancesheet LEDGER directly, not the _sq
slots), then reads $roe_core_stab_12q/$sales_gr_stab_12q at the cache pdays and compares to f9 (RoeCoreQ-stab)
/ f10 (SalesGr-stab). NON-FORMAL validation (mirrors _validate_forecast_factor_vs_guorn.py). No publish.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from src.data_infra.pipeline.build_qlib_backend import build_unified_qlib, _resolve_paths  # noqa

CACHE = ROOT / "workspace/outputs/guorn_parity/rung6_cache"
BID = "stab_validate"


def main():
    uni = (ROOT / "workspace/outputs/guorn_parity/rung6_universe.txt").read_text().strip().split(",")
    basket = uni[::90][:60]                      # ~60-stock spread across the universe
    dr, qd = _resolve_paths()
    print(f"[validate] scoped build for {len(basket)} symbols (2 stability fields only, no publish)", flush=True)
    build_unified_qlib(data_root=dr, qlib_dir=qd, field_filter=["roe_core_stab_12q", "sales_gr_stab_12q"],
                       mode="update", stage="provider-only", datasets=["income", "balancesheet"],
                       touched_symbols=basket, build_id=BID, slot_depth=5, publish=False, include_phase3=True)

    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / f"data/qlib_builds/{BID}/provider"), region=REG_CN, kernels=1)
    meta = __import__("json").loads((CACHE / "meta.json").read_text(encoding="utf-8"))
    pdays = pd.DatetimeIndex(pd.to_datetime(meta["pdays"]))
    f9 = pd.read_parquet(CACHE / "f9.parquet")    # RoeCoreQ-stab (truth)
    f10 = pd.read_parquet(CACHE / "f10.parquet")  # SalesGr-stab (truth)
    insts = [c for c in basket if c.replace(".SH", "_SH").replace(".SZ", "_SZ") in f9.columns]
    qinsts = [c.replace(".SH", "_SH").replace(".SZ", "_SZ") for c in insts]
    df = D.features(qinsts, ["$roe_core_stab_12q", "$sales_gr_stab_12q"],
                    start_time=str(pdays.min().date()), end_time=str(pdays.max().date()), freq="day")
    mat_roe = df["$roe_core_stab_12q"].unstack(level=0).reindex(pdays)
    mat_sal = df["$sales_gr_stab_12q"].unstack(level=0).reindex(pdays)

    def cmp(mat, truth, name):
        cols = [c for c in qinsts if c in mat.columns and c in truth.columns]
        m = mat[cols].values.ravel()
        t = truth[cols].reindex(pdays).values.ravel()
        ok = np.isfinite(m) & np.isfinite(t)
        if ok.sum() == 0:
            print(f"  {name}: NO overlap"); return
        rel = np.abs(m[ok] - t[ok]) / np.clip(np.abs(t[ok]), 1e-6, None)
        print(f"  {name}: n={ok.sum()} median_relerr={np.median(rel):.2e} within1%={np.mean(rel<=0.01):.3f} "
              f"within5%={np.mean(rel<=0.05):.3f} | materialized cov={np.isfinite(m).mean():.3f} truth cov={np.isfinite(t).mean():.3f}")

    print("=== materializer vs rung-6 f9/f10 (truth) ===")
    cmp(mat_roe, f9, "roe_core_stab_12q vs f9")
    cmp(mat_sal, f10, "sales_gr_stab_12q vs f10")


if __name__ == "__main__":
    main()
