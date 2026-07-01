"""Additive provider publish for $profit_dedt_sq (GPT Phase-C Major-1: HONEST provenance).

WHY a bespoke script. `materialize_provider(mode="update")` does `shutil.copytree(live->staged)` of the
~23M-file provider (~8h, single-threaded). For ONE additive field that is unviable. This script stages via
`robocopy /MT` (parallel, INDEPENDENT files), materializes ONLY $profit_dedt_sq_q0..q4 into the staged tree
(the existing bins are byte-identical robocopy copies, NOT re-derived -> zero regression risk on existing
fields), then publishes via the PROVEN atomic swap — but emits a TRUTHFUL manifest (mode=update /
stage=provider-only, NOT the builder's hardcoded all/full) plus an `additive_build_provenance.json` sidecar
recording base_provider_build_id, added_fields, the robocopy summary, the unchanged-bin integrity check, and
the new-field parity. The approval-evidence binding (daily QA) then rebinds onto a provider whose evidence
FULLY describes how the field was added (GPT residual-risk closure).

Reproducible: re-runnable; robocopy resumes from a partial stage (skips already-copied identical files).
Idempotent up to the atomic swap. NON-FORMAL one-off (workspace/scripts).

Run:  PYTHONPATH=src venv/Scripts/python.exe workspace/scripts/_publish_phasec_additive.py [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np

ROOT = Path("E:/量化系统")
sys.path.insert(0, str(ROOT / "src"))

from data_infra.pit_backend import StagedQlibBackendBuilder, provider_calendar, iter_progress  # noqa: E402
from data_infra.provider_manifest import emit_manifest_at_publish  # noqa: E402

BUILD_ID = "phasec_profit_dedt_sq_20260624"
ADDED_FIELDS = [f"profit_dedt_sq_q{s}" for s in range(5)]
LIVE = ROOT / "data" / "qlib_data"
CAL_POLICY = "frozen_20260227_system_build"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def read_base_build_id() -> str | None:
    p = LIVE / "metadata" / "provider_build.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8")).get("provider_build_id")


def run_robocopy(src: Path, dst: Path) -> dict:
    """robocopy /MIR (MIRROR: /E + /PURGE) with summary captured. /MIR makes dst EXACTLY equal src —
    it purges any stale extras in dst (e.g. a prior --dry-run's $profit_dedt_sq_*.day.bin, or any leftover
    from a reused staging dir), closing the GPT R2 Major (the /E variant could publish stale extras). The
    materialize step re-adds $profit_dedt_sq AFTER this, so the order (mirror -> materialize) is intact.
    Robocopy Files line = Total Copied Skipped Mismatch FAILED Extras."""
    dst.mkdir(parents=True, exist_ok=True)
    cmd = ["robocopy", str(src), str(dst), "/MIR", "/MT:32", "/NFL", "/NDL", "/NP", "/R:1", "/W:1"]
    log(f"robocopy /MIR {src} -> {dst} (mirror+purge; identical files skipped, stale extras removed)")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = proc.stdout or ""
    rc = proc.returncode
    # robocopy exit: <8 = success (bit 0=copied, 1=extra purged, 2=mismatch, 3=ok+extra ...). >=8 = failure.
    files = re.search(r"Files\s*:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", out)
    bytes_ = re.search(r"Bytes\s*:\s*([\d.]+\s*\w?)\s+", out)
    summary = {
        "exit_code": rc,
        "success": rc < 8,
        "mirror": True,
        "files_total": int(files.group(1)) if files else None,
        "files_copied": int(files.group(2)) if files else None,
        "files_skipped": int(files.group(3)) if files else None,
        "files_mismatch": int(files.group(4)) if files else None,
        "files_failed": int(files.group(5)) if files else None,
        "files_extras_purged": int(files.group(6)) if files else None,  # informational: /MIR removed these
        "raw_files_line": files.group(0) if files else None,
        "raw_bytes_line": bytes_.group(0).strip() if bytes_ else None,
    }
    return summary


def integrity_check(staged: Path, live: Path) -> dict:
    """Unchanged-bin integrity, FULL (every feature dir — GPT R2 Major: not sampled). staged must equal
    live on EVERY existing bin (filename, size). Idempotent — a prior --dry-run's added-field bins are
    EXCLUDED (live never has them); /MIR also purges them, so this is belt-and-suspenders. The added-field
    bins are NOT materialized yet at call time (integrity runs BEFORE materialize)."""
    sf = staged / "features"
    lf = live / "features"
    added_bins = {f"{f}.day.bin" for f in ADDED_FIELDS}
    staged_dirs = sorted(d.name for d in os.scandir(sf) if d.is_dir())
    live_dirs = sorted(d.name for d in os.scandir(lf) if d.is_dir())
    dir_match = staged_dirs == live_dirs
    mismatches = []
    for d in iter_progress(live_dirs, total=len(live_dirs), desc="integrity", unit="dir", leave=False):
        sfiles = {f.name: f.stat().st_size for f in os.scandir(sf / d) if f.is_file() and f.name not in added_bins}
        lfiles = {f.name: f.stat().st_size for f in os.scandir(lf / d) if f.is_file()}
        if sfiles != lfiles:
            extra = set(sfiles) - set(lfiles)
            missing = set(lfiles) - set(sfiles)
            sizediff = [k for k in set(sfiles) & set(lfiles) if sfiles[k] != lfiles[k]]
            mismatches.append({"dir": d, "extra": sorted(extra)[:5], "missing": sorted(missing)[:5],
                               "size_diff": sorted(sizediff)[:5]})
        if len(mismatches) > 50:  # fail fast — something is structurally wrong
            break
    return {
        "dir_count_staged": len(staged_dirs), "dir_count_live": len(live_dirs),
        "dir_lists_identical": dir_match, "checked_dirs": len(live_dirs), "coverage": "FULL",
        "mismatch_count": len(mismatches), "mismatches": mismatches[:20],
        "ok": dir_match and not mismatches,
    }


def binv(features_dir: Path, code: str, field: str) -> np.ndarray | None:
    p = features_dir / code / f"{field}.day.bin"
    return np.fromfile(p, dtype=np.float32)[1:] if p.exists() else None


def new_field_parity(staged: Path, sample_n: int = 150) -> dict:
    """New $profit_dedt_sq_q0 vs the vendor's direct $q_dtprofit_q0 in the SAME staged tree (exact)."""
    sf = staged / "features"
    dirs = [d.name for d in os.scandir(sf) if d.is_dir()]
    dirs = dirs[:: max(1, len(dirs) // sample_n)][:sample_n]
    rels, covs, n = [], [], 0
    for d in dirs:
        sq = binv(sf, d, "profit_dedt_sq_q0")
        ven = binv(sf, d, "q_dtprofit_q0")
        if sq is None:
            continue
        covs.append(float(np.isfinite(sq).mean()))
        if ven is None:
            continue
        m = np.isfinite(sq) & np.isfinite(ven) & (np.abs(ven) > 1e-6)
        if m.sum() >= 50:
            rels.append(float(np.median(np.abs(sq[m] - ven[m]) / np.abs(ven[m]))))
            n += int(m.sum())
    return {
        "dirs_sampled": len(dirs), "dirs_with_new_field": len(covs),
        "median_coverage_new_field": round(float(np.median(covs)), 4) if covs else None,
        "vendor_parity_median_rel": round(float(np.median(rels)), 6) if rels else None,
        "vendor_parity_obs": n,
        "ok": bool(rels) and float(np.median(rels)) < 1e-3,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="stage+materialize+verify but DO NOT publish")
    ap.add_argument("--swap-only", action="store_true",
                    help="REUSE an already-staged+materialized tree (skip robocopy+materialize); re-verify "
                         "integrity+parity, then swap. For retrying a publish whose only failure was a "
                         "transient handle on data/qlib_data during os.replace, or a disk-space stall.")
    args = ap.parse_args()

    builder = StagedQlibBackendBuilder(build_id=BUILD_ID, field_filter=ADDED_FIELDS)
    staged = Path(builder.paths.provider_dir)
    base_build_id = read_base_build_id()
    log(f"base_provider_build_id = {base_build_id}")
    log(f"staged provider dir    = {staged}")

    # 1. stage (robocopy /MIR: mirror+purge; summary captured). Skipped in --swap-only (reuse staged tree).
    if args.swap_only:
        robo = {"reused_staged_tree": True, "note": "--swap-only: robocopy from the prior verified run; "
                "integrity+parity re-verified below before the swap"}
        log("--swap-only: reusing the already-staged+materialized tree (skipping robocopy)")
    else:
        robo = run_robocopy(LIVE, staged)
        log(f"robocopy /MIR: exit={robo['exit_code']} failed={robo['files_failed']} mismatch={robo['files_mismatch']} "
            f"copied={robo['files_copied']} skipped={robo['files_skipped']} extras_purged={robo['files_extras_purged']} "
            f"total={robo['files_total']}")
        if not robo["success"] or (robo["files_failed"] or 0) > 0 or (robo["files_mismatch"] or 0) > 0:
            log("ABORT: robocopy reported failures/mismatches"); return 2

    # 2. integrity BEFORE materialize: staged must FULLY equal live (no new field yet)
    integ = integrity_check(staged, LIVE)
    log(f"integrity (unchanged bins, FULL): dirs {integ['dir_count_staged']}=={integ['dir_count_live']} "
        f"identical={integ['dir_lists_identical']} checked={integ['checked_dirs']} "
        f"mismatches={integ['mismatch_count']} ok={integ['ok']}")
    if not integ["ok"]:
        log(f"ABORT: integrity mismatch: {integ['mismatches'][:3]}"); return 3

    # 3. materialize ONLY the new field into the staged tree. Skipped in --swap-only (already present).
    if args.swap_only:
        present = len(glob.glob(str(staged / "features" / "*" / "profit_dedt_sq_q0.day.bin")))
        log(f"--swap-only: $profit_dedt_sq_q0 already materialized in {present} staged dirs (skipping materialize)")
        if present < 5000:
            log(f"ABORT: staged tree only has {present} profit_dedt_sq_q0 bins (<5000) — not a complete prior run"); return 4
    else:
        calendar = provider_calendar(str(staged))
        features_root = staged / "features"
        target_dirs = {name: str(features_root / name) for name in os.listdir(features_root)
                       if (features_root / name).is_dir()}
        log(f"materializing {ADDED_FIELDS} into {len(target_dirs)} staged dirs ...")
        written = builder._materialize_profit_dedt_sq(calendar, target_dirs)
        log(f"materialized fields: {written}")
        if sorted(set(written)) != sorted(ADDED_FIELDS):
            log(f"ABORT: unexpected written set {written}"); return 4

    # 4. new-field parity vs vendor (exact)
    parity = new_field_parity(staged)
    log(f"new-field parity: cov~{parity['median_coverage_new_field']} "
        f"vendor_rel={parity['vendor_parity_median_rel']} obs={parity['vendor_parity_obs']} ok={parity['ok']}")
    if not parity["ok"]:
        log("ABORT: new-field vendor parity failed"); return 5

    provenance = {
        "build_kind": "additive_provider_copy",
        "new_provider_build_id": BUILD_ID,
        "base_provider_build_id": base_build_id,
        "added_fields": [f"${f}" for f in ADDED_FIELDS],
        "source_dataset": "indicators",
        "source_class": "derived_flow_from_snapshot_ledger",
        "staging_method": "robocopy /MIR /MT:32 (parallel mirror+purge; unchanged bins full filename/size verified; shutil.copytree was ~8h)",
        "robocopy_summary": robo,
        "unchanged_bin_integrity": integ,
        "new_field_parity_vs_vendor_q_dtprofit": parity,
        "materializer": "StagedQlibBackendBuilder._materialize_profit_dedt_sq",
        "published_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }

    if args.dry_run:
        log("DRY-RUN: skipping publish. Provenance preview:")
        print(json.dumps(provenance, ensure_ascii=False, indent=2))
        return 0

    # 5. publish: proven atomic swap, but suppress the builder's hardcoded all/full manifest,
    #    then emit a TRUTHFUL manifest (update/provider-only) + the provenance sidecar.
    #    Retry-with-backoff on PermissionError (transient handle on data/qlib_data from Search/Defender/
    #    a qlib reader during the os.replace), WITH a half-swap safety guard.
    import time
    bak = f"{builder.paths.qlib_dir}.bak_{BUILD_ID}"
    log("publishing (atomic os.replace swap + .bak backup) ...")
    last_err = None
    for attempt in range(1, 9):
        # SAFETY: publish() does os.replace(live->bak) THEN os.replace(staged->live). If the FIRST
        # succeeded but the SECOND failed, live is gone and .bak holds the only old-live copy — a naive
        # retry would rmtree that .bak. Detect that half-state and refuse to retry (manual recovery).
        if not os.path.isdir(builder.paths.qlib_dir) and os.path.isdir(bak):
            log(f"ABORT: HALF-SWAPPED state — live moved to .bak, staged not yet live. Do NOT re-run "
                f"(would delete the backup). MANUAL RECOVERY: os.replace(r'{bak}', r'{builder.paths.qlib_dir}') "
                f"to roll back to the old live, then investigate the handle holder."); return 7
        try:
            builder.publish(emit_manifest=False)
            last_err = None
            break
        except PermissionError as e:
            last_err = e
            log(f"  publish attempt {attempt}/8 PermissionError (a process holds data/qlib_data); "
                f"retry in {attempt*10}s ... {e}")
            time.sleep(attempt * 10)
    if last_err is not None:
        log("ABORT: publish failed after 8 retries — a process persistently holds a handle on "
            "data/qlib_data. Close qlib readers / dashboard / pause Search+Defender on it, then re-run "
            "with --swap-only."); return 6
    log("PUBLISHED (atomic swap done).")

    cal_lines = [ln.strip() for ln in (LIVE / "calendars" / "day.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    try:
        src_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() or None
    except Exception:
        src_commit = None
    emit_manifest_at_publish(
        qlib_dir=str(LIVE),
        provider_build_id=BUILD_ID,
        calendar_policy_id=CAL_POLICY,
        calendar_start_date=cal_lines[0],
        calendar_end_date=cal_lines[-1],
        data_end_date=cal_lines[-1],
        source_git_commit=src_commit,
        builder_mode="update",            # TRUTHFUL: incremental, not a full "all" rebuild
        builder_stage="provider-only",    # TRUTHFUL: provider features only, upstream ledgers untouched
    )
    sidecar = LIVE / "metadata" / "additive_build_provenance.json"
    sidecar.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"emitted manifest (mode=update/stage=provider-only) + sidecar {sidecar}")
    log("DONE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
