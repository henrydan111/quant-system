"""Sandbox sanity-run for _materialize_report_rc_aggregates on REAL ledgers (no bins written).

Constructs a builder over the real data_root, captures _write_feature_series, runs the materializer for
a few well-covered stocks, and eyeballs the 5 fields (coverage + recent values + sanity). NOT a test.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from data_infra.pit_backend import StagedQlibBackendBuilder   # noqa: E402

b = StagedQlibBackendBuilder(data_root=str(ROOT / "data"), qlib_dir=str(ROOT / "workspace" / "outputs" / "_sandbox_qlib"),
                             build_id="sandbox_rrc_agg", allow_exceptions=True)
cal = b.open_calendar()
print(f"calendar: {len(cal)} days {cal[0].date()}..{cal[-1].date()}", flush=True)

captured: dict = {}
b._write_feature_series = lambda fd, fn, arr: captured.setdefault(fd, {}).__setitem__(fn, np.asarray(arr, dtype=float))

codes = ["600519_sh", "000001_sz", "300750_sz", "000333_sz", "601318_sh"]
written = b._materialize_report_rc_aggregates(cal, {c: c for c in codes})
print("written fields:", written, flush=True)

for c in codes:
    arr = captured.get(c, {})
    if not arr:
        print(f"\n=== {c} === (no covered data)")
        continue
    print(f"\n=== {c} ===")
    for fn in ["report_rc__np_fy1", "report_rc__op_rt_fy1", "report_rc__n_active_orgs",
               "report_rc__rating_up", "report_rc__rating_dn"]:
        a = arr.get(fn)
        if a is None:
            print(f"  {fn:28} (not written)"); continue
        fin = np.isfinite(a)
        cov = fin.mean()
        tail = a[-1] if fin[-1] else "NaN"
        rng = (np.nanmin(a), np.nanmax(a)) if fin.any() else ("-", "-")
        print(f"  {fn:28} cov={cov:.3f}  last={tail}  range=({rng[0]:.4g}..{rng[1]:.4g})" if fin.any()
              else f"  {fn:28} cov=0.000 (all NaN)")
