"""Route-A deep-slot build for the 8-quarter unlock (RnDTTMGr%PY, AssetTurnoverDiffPY) — GPT R1/R2 task
wrapper. SCOPED + transient + NON-FORMAL: 3 fields only, publish=False, hard disk preflight + safety asserts
(the 1TB-blowup lesson, memory feedback_provider_build_disk_hazard).

slot_depth=9 (q0..q8), NOT 8: the AssetTurnoverDiffPY *begin/end* denominator candidate
  ATO(k) = TTM_revenue[k..k+3] / ((total_assets_q[k] + total_assets_q[k+4]) / 2)
needs total_assets_q8 for the YEAR-AGO leg ATO(4) = (assets_q4 + assets_q8)/2 (GPT R2 B1). RnDTTMGr%PY and the
AvgQ(4) asset-denominator candidate only need q0..q7; q8 is materialized solely for the begin/end candidate.

DOES NOT publish, DOES NOT write to the live provider, DOES NOT write field_status/registry. The live provider
data/qlib_data is the legitimate scoped-copy SOURCE; the staged OUTPUT is data/qlib_builds/<BUILD_ID>/provider
(GPT R2 M1 — the safety assert guards the OUTPUT path + publish flag, never the source). Build → read via
guorn_factor_parity.py --provider-uri data/qlib_builds/<BUILD_ID>/provider → delete the staged dir.

  python workspace/scripts/_build_deepslot_8q.py --test    # 2 symbols, confirm size/PIT before scaling
  python workspace/scripts/_build_deepslot_8q.py           # dry-run preflight (no build)
  python workspace/scripts/_build_deepslot_8q.py --go      # full main+chinext universe, build staged provider
  # optional m2 subset preflight: --export-xlsx <果仁_export.xlsx> [--export-code-col 0]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
from src.data_infra.pipeline.build_qlib_backend import build_unified_qlib, _resolve_paths  # noqa: E402
from src.data_infra.pit_backend import resolve_build_paths  # noqa: E402

BUILD_ID = "guorn_unlock_9q_scoped"               # 9 slots (q0..q8); q8 only for the begin/end asset denominator
SLOT_DEPTH = 9                                    # q0..q8 — see module docstring (GPT R2 B1)
FIELDS = ["revenue", "rd_exp", "total_assets"]    # RnDTTMGr%PY: rd_exp; AssetTurnoverDiffPY: revenue + total_assets
DATASETS = ["income", "balancesheet"]
MAX_GB = 30.0                                     # hard abort ceiling (scoped build should be ~10GB)


def _arg(flag: str, default: str | None = None) -> str | None:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def _universe():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    from guorn_universe import in_guorn_universe, EXCL_STAR  # main+chinext (排除科创/北证); ST kept (data-level)
    allc = D.list_instruments(D.instruments("all"), as_list=True)
    return sorted(c for c in allc if in_guorn_universe(c, boards=EXCL_STAR))


def _export_codes(xlsx: str, col: int) -> set[str]:
    """Zero-padded 6-digit codes from a 果仁 export column (m2 subset preflight)."""
    import pandas as pd
    df = pd.read_excel(xlsx, header=None)
    out = set()
    for v in df.iloc[:, col].astype(str):
        m = re.search(r"(\d{6})", v)
        if m:
            out.add(m.group(1))
    return out


def main():
    test = "--test" in sys.argv
    syms = ["600519.SH", "000001.SZ"] if test else [c.replace("_", ".") for c in _universe()]
    touched6 = {s[:6] for s in syms}
    data_root, qlib_dir = _resolve_paths()                 # qlib_dir = live provider = legitimate copy SOURCE
    paths = resolve_build_paths(build_id=BUILD_ID)          # provider_dir = staged OUTPUT
    live = (ROOT / "data" / "qlib_data").resolve()
    staged = Path(paths.provider_dir).resolve()

    # ---- m2: 果仁 export ⊆ touched_symbols subset preflight (GPT R1 m2 / R2 m2) ----
    export_xlsx = _arg("--export-xlsx")
    if export_xlsx:
        exp6 = _export_codes(export_xlsx, int(_arg("--export-code-col", "0")))
        missing = sorted(exp6 - touched6)
        print(f"[m2] export_code_count={len(exp6)} touched_symbol_count={len(touched6)} missing={missing}")
        assert not missing, f"REFUSE: {len(missing)} 果仁 export codes outside touched universe: {missing[:20]}"
    else:
        print("[m2] WARNING: --export-xlsx not given — export⊆touched subset NOT verified for this build")

    # ---- disk + governance preflight (GPT R1 M4 / R2 M1) ----
    est_bins = len(syms) * len(FIELDS) * (SLOT_DEPTH * 2)   # ~2 bins/slot (value+meta), generous over-estimate
    est_gb = est_bins * 60_000 / 1e9                        # ~60KB/bin heuristic (rung-6-calibrated, generous)
    print(f"[preflight] build_id={BUILD_ID} slot_depth={SLOT_DEPTH} fields={FIELDS} datasets={DATASETS}")
    print(f"[preflight] symbols={len(syms)}  est_bins≈{est_bins:,}  est_size≈{est_gb:.1f}GB")
    print(f"[preflight] source(qlib_dir)={qlib_dir}  staged_output={staged}")
    # GPT R2 M1: guard the OUTPUT path + publish, NOT the (legitimately-live) source.
    assert staged != live, "REFUSE: staged OUTPUT must not be the live provider data/qlib_data"
    assert "qlib_builds" in staged.as_posix(), "REFUSE: staged OUTPUT must live under data/qlib_builds"
    assert est_gb <= MAX_GB, f"REFUSE: est {est_gb:.1f}GB > {MAX_GB}GB ceiling — re-scope before building"
    if "--go" not in sys.argv and not test:
        print("[preflight] dry-run only. Re-run with --go to build (publish stays False regardless)."); return

    result = build_unified_qlib(
        data_root=data_root, qlib_dir=qlib_dir, field_filter=FIELDS,
        mode="update", stage="provider-only", datasets=DATASETS,
        touched_symbols=syms, build_id=BUILD_ID, slot_depth=SLOT_DEPTH,
        publish=False, include_phase3=True)                # publish=False — HARD non-formal
    built = Path(getattr(result, "provider_dir", staged)).resolve()
    assert built == staged, f"REFUSE: builder wrote {built}, expected staged output {staged}"
    print(f"[done] staged provider → {staged}  (read via --provider-uri; DELETE after validating)")


if __name__ == "__main__":
    main()
