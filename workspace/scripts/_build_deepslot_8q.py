"""Route-A deep-slot build for the 8-quarter unlock (RnDTTMGr%PY, AssetTurnoverDiffPY) — GPT-M4 task-specific
wrapper. SCOPED + transient + NON-FORMAL: slot_depth=8 (q0..q7), 3 fields only, publish=False, hard disk
preflight + safety asserts (the 1TB-blowup lesson, memory feedback_provider_build_disk_hazard).

DOES NOT publish, DOES NOT touch the live provider, DOES NOT write field_status/registry. Build → read via
guorn_factor_parity.py --provider-uri data/qlib_builds/<BUILD_ID>/provider → delete the staged dir.

  python workspace/scripts/_build_deepslot_8q.py --test    # 2 symbols, confirm size/PIT before scaling
  python workspace/scripts/_build_deepslot_8q.py           # full main+chinext universe
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
from src.data_infra.pipeline.build_qlib_backend import build_unified_qlib, _resolve_paths  # noqa: E402

BUILD_ID = "guorn_unlock_8q_scoped"
SLOT_DEPTH = 8                                    # q0..q7 — exactly the year-ago TTM leg, no deeper
FIELDS = ["revenue", "rd_exp", "total_assets"]    # RnDTTMGr%PY: rd_exp; AssetTurnoverDiffPY: revenue + total_assets
DATASETS = ["income", "balancesheet"]
MAX_GB = 30.0                                     # hard abort ceiling (scoped build should be ~5GB)


def _universe():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    from guorn_universe import in_guorn_universe, EXCL_STAR  # main+chinext (排除科创/北证); ST kept (data-level)
    allc = D.list_instruments(D.instruments("all"), as_list=True)
    return sorted(c for c in allc if in_guorn_universe(c, boards=EXCL_STAR))


def main():
    test = "--test" in sys.argv
    syms = ["600519.SH", "000001.SZ"] if test else [c.replace("_", ".") for c in _universe()]
    data_root, qlib_dir = _resolve_paths()
    staged = ROOT / "data" / "qlib_builds" / BUILD_ID / "provider"

    # ---- disk + governance preflight (GPT-M4) ----
    est_bins = len(syms) * len(FIELDS) * (SLOT_DEPTH * 2)          # ~2 bins/slot (value+meta), generous
    est_gb = est_bins * 60_000 / 1e9                              # ~60KB/bin heuristic (rung-6-calibrated)
    print(f"[preflight] build_id={BUILD_ID} slot_depth={SLOT_DEPTH} fields={FIELDS} datasets={DATASETS}")
    print(f"[preflight] symbols={len(syms)}  est_bins≈{est_bins:,}  est_size≈{est_gb:.1f}GB  staged→{staged}")
    assert str(qlib_dir).replace("\\", "/").rstrip("/") != str(ROOT / "data" / "qlib_data").replace("\\", "/"), \
        "REFUSE: staged build must NOT target the live provider data/qlib_data"
    assert est_gb <= MAX_GB, f"REFUSE: est {est_gb:.1f}GB > {MAX_GB}GB ceiling — re-scope before building"
    if "--go" not in sys.argv and not test:
        print("[preflight] dry-run only. Re-run with --go to build (publish stays False regardless)."); return

    build_unified_qlib(
        data_root=data_root, qlib_dir=qlib_dir, field_filter=FIELDS,
        mode="update", stage="provider-only", datasets=DATASETS,
        touched_symbols=syms, build_id=BUILD_ID, slot_depth=SLOT_DEPTH,
        publish=False, include_phase3=True)                       # publish=False — HARD non-formal
    print(f"[done] staged provider → {staged}  (read via --provider-uri; DELETE after validating)")


if __name__ == "__main__":
    main()
