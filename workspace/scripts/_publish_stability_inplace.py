"""SURGICAL in-place publish of the 2 果仁 #59 quality-stability fields into the LIVE provider.

Writes $roe_core_stab_12q / $sales_gr_stab_12q directly into the 5,755 live feature dirs by driving
ONLY `_materialize_quality_stability` against the live ledgers + live calendar. PURELY ADDITIVE — no
existing bin is read-for-mutation or overwritten (the 2 fields are new), so there is no half-built
state any reader (incl. the other session) can observe; the existing provider_build.json stays valid
(calendar/namespacing unchanged). Idempotent: re-running overwrites the 2 bins cleanly.

Bit-equivalent to the validated scoped path (`_validate_stability_materializer.py`, median rel-err 0.0
vs the rung-6 deepslot f9/f10) because it uses the SAME close.day.bin reference + the SAME
provider_calendar(day.txt) the scoped copies used. NON-formal data op; field-status approval YAML +
log are added separately (registration step). See GUORN_HARNESS_59_PLAN.md / GPT R2 SHIP.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from src.data_infra.pipeline.build_qlib_backend import _resolve_paths  # noqa: E402
from src.data_infra.pit_backend import StagedQlibBackendBuilder, provider_calendar  # noqa: E402

FIELDS = ["roe_core_stab_12q", "sales_gr_stab_12q"]


def _count_bins(features_root, names, field):
    return sum(os.path.exists(os.path.join(features_root, n, f"{field}.day.bin")) for n in names)


def main():
    dr, qd = _resolve_paths()
    print(f"[inplace] data_root={dr}\n[inplace] qlib_dir ={qd}", flush=True)
    builder = StagedQlibBackendBuilder(
        data_root=dr, qlib_dir=qd, field_filter=FIELDS,
        build_id="quality_stab_inplace", include_phase3=True,
    )
    # Pre-flight: the 3 live ledgers the materializer reads MUST exist.
    for ds in ("income", "balancesheet", "income_quarterly"):
        p = builder.ledger_path(ds)
        if not os.path.exists(p):
            raise SystemExit(f"FATAL missing live ledger: {p}")
        print(f"[inplace] ledger ok: {ds}", flush=True)

    calendar = provider_calendar(qd)  # LIVE calendars/day.txt — exact positional bin alignment
    features_root = os.path.join(qd, "features")
    names = sorted(n for n in os.listdir(features_root) if os.path.isdir(os.path.join(features_root, n)))
    target_dirs = {n: os.path.join(features_root, n) for n in names}
    print(f"[inplace] live feature dirs={len(target_dirs)}  calendar days={len(calendar)}  "
          f"end={calendar.max().date()}", flush=True)

    # ADDITIVE proof: count pre-existing bins for the 2 fields (expect 0 on a clean first publish).
    pre = {f: _count_bins(features_root, names, f) for f in FIELDS}
    print(f"[inplace] PRE  bin counts: {pre}", flush=True)

    t0 = time.time()
    written = builder._materialize_quality_stability(calendar, target_dirs)
    dt = time.time() - t0
    print(f"[inplace] materializer returned written-field set: {written}  ({dt:.0f}s)", flush=True)

    post = {f: _count_bins(features_root, names, f) for f in FIELDS}
    print(f"[inplace] POST bin counts: {post}", flush=True)
    print(f"[inplace] coverage: roe={post['roe_core_stab_12q']/len(names):.3f}  "
          f"sales={post['sales_gr_stab_12q']/len(names):.3f}", flush=True)

    # Clean up the empty staged build workspace the constructor created (we never ran
    # materialize_provider, so build_root holds only empty dirs — no copytree happened).
    bp = builder.paths.build_root
    prov = os.path.join(bp, "provider")
    if os.path.basename(bp) == "quality_stab_inplace" and not (os.path.isdir(prov) and os.listdir(prov)):
        import shutil
        shutil.rmtree(bp, ignore_errors=True)
        print(f"[inplace] cleaned empty build workspace: {bp}", flush=True)

    print("[inplace] DONE", flush=True)


if __name__ == "__main__":
    main()
