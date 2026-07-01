"""Post-publish verification: the LIVE provider's $roe_core_stab_12q / $sales_gr_stab_12q must equal the
rung-6 deepslot f9/f10 (the +14.3pp parity truth) over the FULL rung-6 universe — proving the in-place
publish served the validated fields. If median rel-err ~0 full-universe, the #59 overlap reproduces 35.9%
BY CONSTRUCTION (the composite reads these fields). NON-formal verification.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
CACHE = ROOT / "workspace/outputs/guorn_parity/rung6_cache"


def main():
    uni = (ROOT / "workspace/outputs/guorn_parity/rung6_universe.txt").read_text().strip().split(",")
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)
    meta = json.loads((CACHE / "meta.json").read_text(encoding="utf-8"))
    pdays = pd.DatetimeIndex(pd.to_datetime(meta["pdays"]))
    f9 = pd.read_parquet(CACHE / "f9.parquet")
    f10 = pd.read_parquet(CACHE / "f10.parquet")
    qinsts = [c.replace(".SH", "_SH").replace(".SZ", "_SZ") for c in uni]
    print(f"[verify] LIVE provider; universe={len(qinsts)} pdays={len(pdays)} "
          f"({pdays.min().date()}..{pdays.max().date()})", flush=True)
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
            print(f"  {name}: NO overlap"); return False
        rel = np.abs(m[ok] - t[ok]) / np.clip(np.abs(t[ok]), 1e-6, None)
        med = float(np.median(rel)); w1 = float(np.mean(rel <= 0.01)); w5 = float(np.mean(rel <= 0.05))
        print(f"  {name}: n={ok.sum()} median_relerr={med:.2e} within1%={w1:.3f} within5%={w5:.3f} | "
              f"live cov={np.isfinite(m).mean():.3f} truth cov={np.isfinite(t).mean():.3f}", flush=True)
        return med < 1e-3 and w1 >= 0.95

    print("=== LIVE $roe_core_stab_12q/$sales_gr_stab_12q vs rung-6 deepslot f9/f10 (FULL universe) ===")
    ok_roe = cmp(mat_roe, f9, "roe_core_stab_12q vs f9")
    ok_sal = cmp(mat_sal, f10, "sales_gr_stab_12q vs f10")
    print(f"[verify] VERDICT: {'PASS' if (ok_roe and ok_sal) else 'FAIL'} "
          f"(roe={ok_roe} sales={ok_sal})", flush=True)
    return 0 if (ok_roe and ok_sal) else 1


if __name__ == "__main__":
    raise SystemExit(main())
