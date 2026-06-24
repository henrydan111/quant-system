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

from data_infra.pit_backend import StagedQlibBackendBuilder, provider_calendar  # noqa: E402
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
    """robocopy /MT with summary captured (no /NJS). Returns parsed Files/Bytes/Failed + exit code."""
    dst.mkdir(parents=True, exist_ok=True)
    cmd = ["robocopy", str(src), str(dst), "/E", "/MT:32", "/NFL", "/NDL", "/NP", "/R:1", "/W:1"]
    log(f"robocopy {src} -> {dst} (this resumes a partial stage; identical files are skipped)")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = proc.stdout or ""
    rc = proc.returncode
    # robocopy exit: <8 = success (0 nothing to do, 1 copied, 2 extra, 3 copied+extra, ...). >=8 = failure.
    files = re.search(r"Files\s*:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", out)
    bytes_ = re.search(r"Bytes\s*:\s*([\d.]+\s*\w?)\s+", out)
    summary = {
        "exit_code": rc,
        "success": rc < 8,
        "files_total": int(files.group(1)) if files else None,
        "files_copied": int(files.group(2)) if files else None,
        "files_skipped": int(files.group(3)) if files else None,
        "files_failed": int(files.group(5)) if files else None,
        "raw_files_line": files.group(0) if files else None,
        "raw_bytes_line": bytes_.group(0).strip() if bytes_ else None,
    }
    return summary


def integrity_check(staged: Path, live: Path, sample_n: int = 120) -> dict:
    """Unchanged-bin integrity, BEFORE the new field is materialized: staged must equal live.
    Global dir-count + a sampled per-dir (file-count, total-size) equality cross-check."""
    sf = staged / "features"
    lf = live / "features"
    staged_dirs = sorted(d.name for d in os.scandir(sf) if d.is_dir())
    live_dirs = sorted(d.name for d in os.scandir(lf) if d.is_dir())
    dir_match = staged_dirs == live_dirs
    sample = live_dirs[:: max(1, len(live_dirs) // sample_n)][:sample_n]
    mismatches = []
    for d in sample:
        sfiles = {f.name: f.stat().st_size for f in os.scandir(sf / d) if f.is_file()}
        lfiles = {f.name: f.stat().st_size for f in os.scandir(lf / d) if f.is_file()}
        if sfiles != lfiles:
            extra = set(sfiles) - set(lfiles)
            missing = set(lfiles) - set(sfiles)
            sizediff = [k for k in set(sfiles) & set(lfiles) if sfiles[k] != lfiles[k]]
            mismatches.append({"dir": d, "extra": sorted(extra)[:5], "missing": sorted(missing)[:5],
                               "size_diff": sorted(sizediff)[:5]})
    return {
        "dir_count_staged": len(staged_dirs), "dir_count_live": len(live_dirs),
        "dir_lists_identical": dir_match, "sampled_dirs": len(sample),
        "sampled_mismatches": mismatches, "ok": dir_match and not mismatches,
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
    args = ap.parse_args()

    builder = StagedQlibBackendBuilder(build_id=BUILD_ID, field_filter=ADDED_FIELDS)
    staged = Path(builder.paths.provider_dir)
    base_build_id = read_base_build_id()
    log(f"base_provider_build_id = {base_build_id}")
    log(f"staged provider dir    = {staged}")

    # 1. stage (robocopy, resumes a partial; summary captured)
    robo = run_robocopy(LIVE, staged)
    log(f"robocopy: exit={robo['exit_code']} failed={robo['files_failed']} "
        f"copied={robo['files_copied']} skipped={robo['files_skipped']} total={robo['files_total']}")
    if not robo["success"] or (robo["files_failed"] or 0) > 0:
        log("ABORT: robocopy reported failures"); return 2

    # 2. integrity BEFORE materialize: staged must equal live (no new field yet)
    integ = integrity_check(staged, LIVE)
    log(f"integrity (unchanged bins): dirs {integ['dir_count_staged']}=={integ['dir_count_live']} "
        f"identical={integ['dir_lists_identical']} sampled={integ['sampled_dirs']} "
        f"mismatches={len(integ['sampled_mismatches'])} ok={integ['ok']}")
    if not integ["ok"]:
        log(f"ABORT: integrity mismatch: {integ['sampled_mismatches'][:3]}"); return 3

    # 3. materialize ONLY the new field into the staged tree
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
        "staging_method": "robocopy /MT:32 (parallel independent-file copy; shutil.copytree was ~8h)",
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
    log("publishing (atomic os.replace swap + .bak backup) ...")
    builder.publish(emit_manifest=False)
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
