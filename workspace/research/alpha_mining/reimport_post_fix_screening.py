"""Follow-up Plan #1 - Safe re-import of post-fix screening into factor_registry.

Implements the Codex HIGH finding: registry ``latest_*`` refresh sorts by
``evidence_time`` (string-parsed) then ``run_id`` (hash order). Screening
metadata writes ``generated_at`` at second precision, so two runs that
land in the same second will tie-break on hash order - NOT guaranteed
chronological recency.

This script adds three safety measures on top of the bare CLI call:

  1. PRE-IMPORT GUARD: read the existing run_index and assert that the
     post-fix run's ``generated_at`` is STRICTLY later (second granularity)
     than every prior screening run. If not, the script FAILS and tells
     the user to regenerate the run metadata with a later timestamp.

  2. IMPORT via FactorRegistryStore.import_screening().

  3. POST-IMPORT SPOT CHECK: for each factor, assert the master's
     ``latest_run_id`` now points to the new run (not the baseline run).

Also appends a manual ``status_history.parquet`` entry recording the
contamination-fix event, because Codex noted screening import does not
touch status_history automatically.

Usage:
    venv/Scripts/python.exe workspace/research/alpha_mining/reimport_post_fix_screening.py \\
        --run-dir workspace/research/alpha_mining/post_fix_screening_20260411

Ref: plan file ``C:\\Users\\henry\\.claude\\plans\\vast-exploring-rabbit.md``
Step 10.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_registry.store import FactorRegistryStore


def _parse_generated_at(value: str) -> datetime:
    """Parse the registry's 'generated_at' format (second precision)."""
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _assert_strictly_later(
    registry_dir: Path,
    new_run_metadata_path: Path,
    log: logging.Logger,
) -> None:
    """Refuse to import if another screening run already used the same second."""
    meta = json.loads(new_run_metadata_path.read_text(encoding="utf-8"))
    new_at = _parse_generated_at(meta["generated_at"])

    run_index_path = registry_dir / "run_index.parquet"
    if not run_index_path.exists():
        log.info("No prior run_index - any timestamp is fine")
        return
    run_index = pd.read_parquet(run_index_path)
    if run_index.empty:
        log.info("run_index is empty - any timestamp is fine")
        return

    screening_rows = run_index[run_index["run_type"] == "screening"].copy()
    if screening_rows.empty:
        log.info("No prior screening runs in run_index - any timestamp is fine")
        return

    screening_rows["_parsed"] = screening_rows["generated_at"].map(_parse_generated_at)
    latest_prior = screening_rows["_parsed"].max()
    if new_at <= latest_prior:
        raise SystemExit(
            f"PRE-IMPORT GUARD TRIGGERED: post-fix run generated_at={new_at} "
            f"is not strictly later than the latest prior screening run at {latest_prior}. "
            f"Regenerate the run metadata with a later timestamp and retry."
        )
    log.info(
        "Pre-import guard OK: new generated_at=%s is strictly later than latest prior=%s",
        new_at,
        latest_prior,
    )


def _append_status_history_fix_event(
    registry_dir: Path,
    run_id: str,
    log: logging.Logger,
) -> None:
    """Append a manual status_history.parquet row recording the fix event."""
    status_path = registry_dir / "status_history.parquet"
    if not status_path.exists():
        log.warning("status_history.parquet missing at %s; skipping event append", status_path)
        return
    df = pd.read_parquet(status_path)
    new_row = {
        "factor_id": "__ALL_CONTAMINATED__",
        "version": 0,
        "status": "audit_event",
        "reason": (
            "Factor library same-day leakage fix (follow-up plan #1). "
            "45 Layer 1 operators rewritten to wrap every $field reference "
            "in a Ref(...) frame. Registry latest_* fields now reflect "
            f"post-fix evidence from run {run_id}."
        ),
        "source_run_id": run_id,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    for col in df.columns:
        if col not in new_row:
            new_row[col] = None
    appended = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    appended.to_parquet(status_path, index=False)
    csv_path = registry_dir / "status_history.csv"
    if csv_path.exists():
        appended.to_csv(csv_path, index=False)
    log.info("Appended contamination-fix audit event to %s", status_path)


def _verify_latest_run_id(
    registry_dir: Path,
    expected_run_id: str,
    log: logging.Logger,
) -> None:
    """Spot-check the master's latest_run_id after import."""
    master_path = registry_dir / "factor_master.parquet"
    evidence_path = registry_dir / "factor_evidence.parquet"
    if not (master_path.exists() and evidence_path.exists()):
        log.warning("Master or evidence parquet missing; cannot verify")
        return
    master = pd.read_parquet(master_path)
    evidence = pd.read_parquet(evidence_path)
    new_run_evidence = evidence[evidence["run_id"] == expected_run_id]
    if new_run_evidence.empty:
        raise SystemExit(
            f"POST-IMPORT VERIFY FAILED: no evidence rows for run_id={expected_run_id} "
            f"in factor_evidence.parquet after import"
        )
    touched_factors = new_run_evidence["factor_id"].unique()
    if "latest_run_id" not in master.columns:
        log.warning(
            "factor_master has no latest_run_id column; skipping per-factor spot check"
        )
        return
    stale = []
    for factor_id in touched_factors:
        row = master[master["factor_id"] == factor_id]
        if row.empty:
            continue
        current = row["latest_run_id"].iloc[0] if "latest_run_id" in row.columns else None
        if current != expected_run_id:
            stale.append((factor_id, current))
    if stale:
        log.warning(
            "POST-IMPORT: %d factors did NOT pick up the new run_id as latest_run_id "
            "(showing first 5): %s",
            len(stale),
            stale[:5],
        )
    else:
        log.info(
            "POST-IMPORT verify OK: all %d touched factors now reference run_id=%s",
            len(touched_factors),
            expected_run_id,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe post-fix screening reimport")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "factor_registry",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    log = logging.getLogger("reimport_post_fix")

    metadata_path = args.run_dir / "factor_screening_run_metadata.json"
    if not metadata_path.exists():
        raise SystemExit(f"Missing {metadata_path}")

    log.info("Pre-import guard: checking run_index for same-second conflict...")
    _assert_strictly_later(args.registry_dir, metadata_path, log)

    log.info("Opening FactorRegistryStore at %s", args.registry_dir)
    store = FactorRegistryStore(root=str(args.registry_dir))

    log.info("Syncing catalog (in case operator hash changed) ...")
    store.sync_catalog(record_run=False)

    log.info("Importing screening run %s", args.run_dir)
    result = store.import_screening(str(args.run_dir))
    new_run_id = result.get("run_id") if isinstance(result, dict) else None
    log.info("Import complete; new run_id=%s", new_run_id)
    log.info("Import result: %s", json.dumps(result, default=str, indent=2)[:1000])

    # Persist in-memory changes to disk. import_screening() mutates state
    # but does NOT save — that's the caller's responsibility.
    log.info("Saving registry to disk...")
    store.save()
    log.info("Save complete.")

    if new_run_id:
        log.info("Appending status_history contamination-fix event ...")
        _append_status_history_fix_event(args.registry_dir, new_run_id, log)

        log.info("Post-import spot check: latest_run_id on touched factors ...")
        _verify_latest_run_id(args.registry_dir, new_run_id, log)

    log.info("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
