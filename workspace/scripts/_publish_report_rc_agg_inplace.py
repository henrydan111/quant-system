"""SURGICAL in-place publish of the 5 report_rc CONSENSUS + RATING aggregate fields into the LIVE provider.

Writes $report_rc__{np_fy1,op_rt_fy1,n_active_orgs,rating_up,rating_dn} directly into the live feature dirs
by driving ONLY `_materialize_report_rc_aggregates` against the live report_rc + income ledgers + the live
calendar. PURELY ADDITIVE — the 5 fields are new, no existing bin is read-for-mutation or overwritten, so
there is no half-built state any reader can observe; the existing provider_build.json stays valid
(calendar/namespacing unchanged). Idempotent. Mirrors the validated quality_stability in-place publish.

The 5 fields are QUARANTINE in field_status.yaml (per-field entries) — publishing makes them readable for
NON-FORMAL parity; formal eligibility waits on the standing output canary (P4b) + per-field promotion.
Writes a provenance JSON (R3-m2). NON-formal data op. GPT §10 design R1->R4 SHIP + post-impl R1->R2 SHIP.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from src.data_infra.pipeline.build_qlib_backend import _resolve_paths            # noqa: E402
from src.data_infra.pit_backend import StagedQlibBackendBuilder, provider_calendar  # noqa: E402

FIELDS = ["report_rc__np_fy1", "report_rc__op_rt_fy1", "report_rc__n_active_orgs",
          "report_rc__rating_up", "report_rc__rating_dn"]
OUT = ROOT / "workspace" / "outputs" / "guorn_parity" / "report_rc_agg_inplace_provenance.json"


def _count(features_root, names, field):
    return sum(os.path.exists(os.path.join(features_root, n, f"{field}.day.bin")) for n in names)


def main():
    dr, qd = _resolve_paths()
    print(f"[inplace] data_root={dr}\n[inplace] qlib_dir ={qd}", flush=True)
    builder = StagedQlibBackendBuilder(
        data_root=dr, qlib_dir=qd, field_filter=FIELDS,
        build_id="report_rc_agg_inplace", include_phase3=True,
    )
    for ds in ("report_rc", "income"):
        p = builder.ledger_path(ds)
        if not os.path.exists(p):
            raise SystemExit(f"FATAL missing live ledger: {p}")
        print(f"[inplace] ledger ok: {ds}", flush=True)

    calendar = provider_calendar(qd)   # LIVE calendars/day.txt — exact positional bin alignment
    features_root = os.path.join(qd, "features")
    names = sorted(n for n in os.listdir(features_root) if os.path.isdir(os.path.join(features_root, n)))
    target_dirs = {n: os.path.join(features_root, n) for n in names}
    print(f"[inplace] live feature dirs={len(target_dirs)}  calendar days={len(calendar)}  "
          f"end={calendar.max().date()}", flush=True)

    pre = {f: _count(features_root, names, f) for f in FIELDS}
    print(f"[inplace] PRE  bin counts: {pre}", flush=True)

    t0 = time.time()
    written = builder._materialize_report_rc_aggregates(calendar, target_dirs)
    dt = time.time() - t0
    print(f"[inplace] materializer wrote: {sorted(written)}  ({dt:.0f}s)", flush=True)

    post = {f: _count(features_root, names, f) for f in FIELDS}
    print(f"[inplace] POST bin counts: {post}", flush=True)
    cov = {f: round(post[f] / len(names), 4) for f in FIELDS}
    print(f"[inplace] coverage (frac of {len(names)} dirs): {cov}", flush=True)

    # provider build binding (R3-m2 provenance)
    pbid = None
    pbjson = os.path.join(qd, "metadata", "provider_build.json")
    if os.path.exists(pbjson):
        try:
            pbid = json.loads(Path(pbjson).read_text()).get("provider_build_id")
        except Exception:
            pbid = None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "fields": FIELDS, "pre_bin_counts": pre, "post_bin_counts": post, "coverage": cov,
        "n_feature_dirs": len(names), "calendar_end": str(calendar.max().date()),
        "provider_build_id": pbid, "elapsed_s": round(dt, 1),
        "additive": True, "base_build_rotated": False,
        "status": "quarantine (field_status report_rc_*; pending standing output canary)",
        "note": "in-place additive publish of the 5 report_rc consensus/rating aggregates; mirrors quality_stability",
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[inplace] provenance -> {OUT}", flush=True)

    bp = builder.paths.build_root
    prov = os.path.join(bp, "provider")
    if os.path.basename(bp) == "report_rc_agg_inplace" and not (os.path.isdir(prov) and os.listdir(prov)):
        import shutil
        shutil.rmtree(bp, ignore_errors=True)
        print(f"[inplace] cleaned empty build workspace: {bp}", flush=True)
    print("[inplace] DONE", flush=True)


if __name__ == "__main__":
    main()
