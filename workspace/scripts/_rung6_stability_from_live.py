"""Re-source the 2 #59 stability factors (f9/f10) from the LIVE materialized provider fields
$roe_core_stab_12q / $sales_gr_stab_12q (replacing the deleted deep-slot build's values) so the
rung-6 backtest runs end-to-end FROM LIVE. Sanity-compares vs the existing deepslot cache (expect
median rel-err ~0 — the live fields were verified bit-faithful). The 9 level/flow factors (f0..f8)
are already live-sourced (q0..q4 slots, unchanged) → reused. NON-formal parity step.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
CACHE = ROOT / "workspace" / "outputs" / "guorn_parity" / "rung6_cache"


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    f0 = pd.read_parquet(CACHE / "f0.parquet")
    insts, idx = list(f0.columns), f0.index
    fetch_start = (idx.min() - pd.Timedelta(days=40)).strftime("%Y-%m-%d")
    fetch_end = idx.max().strftime("%Y-%m-%d")
    print(f"[from-live] {len(insts)} insts; pdays {idx.min().date()}..{idx.max().date()}", flush=True)
    df = D.features(insts, ["$roe_core_stab_12q", "$sales_gr_stab_12q"],
                    start_time=fetch_start, end_time=fetch_end, freq="day")
    roe = df["$roe_core_stab_12q"].unstack(level=0).sort_index().ffill().reindex(idx).reindex(columns=insts)
    sal = df["$sales_gr_stab_12q"].unstack(level=0).sort_index().ffill().reindex(idx).reindex(columns=insts)

    # sanity vs the deepslot cache currently on disk (f9=RoeCoreQ-stab, f10=SalesGr-stab)
    f9_old = pd.read_parquet(CACHE / "f9.parquet").reindex(idx).reindex(columns=insts)
    f10_old = pd.read_parquet(CACHE / "f10.parquet").reindex(idx).reindex(columns=insts)

    def cmp(new, old, name):
        a, b = new.values.ravel(), old.values.ravel()
        ok = np.isfinite(a) & np.isfinite(b)
        rel = np.abs(a[ok] - b[ok]) / np.clip(np.abs(b[ok]), 1e-9, None)
        print(f"  {name}: live cov={np.isfinite(a).mean():.3f} deepslot cov={np.isfinite(b).mean():.3f} "
              f"median_relerr={np.median(rel):.2e} within1%={np.mean(rel <= 0.01):.3f} n={ok.sum()}", flush=True)

    print("[from-live] sanity vs deepslot cache (expect median ~0):")
    cmp(roe, f9_old, "f9 RoeCoreQ-stab")
    cmp(sal, f10_old, "f10 SalesGr-stab")

    roe.astype("float32").to_parquet(CACHE / "f9.parquet")
    sal.astype("float32").to_parquet(CACHE / "f10.parquet")
    print(f"[from-live] f9/f10 OVERWRITTEN from LIVE materialized fields; "
          f"cov roe={roe.notna().mean().mean():.3f} sales={sal.notna().mean().mean():.3f}", flush=True)


if __name__ == "__main__":
    main()
