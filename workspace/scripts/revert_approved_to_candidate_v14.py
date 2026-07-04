# SCRIPT_STATUS: ACTIVE — one-off v1.4 registry migration: revert the legacy factor-level
# `approved` rows to the terminal `candidate` status. Under v1.4 (book-level promotion) the
# factor-level `approved` mint is RETIRED and `candidate` is terminal; the design initially
# preserved the 7 legacy rows, but the user directed (2026-07-04) that the live registry be
# made fully consistent (0 approved). This is a NON-PRIVILEGED downgrade (the eps_diffusion
# revocation path) — set_status('candidate') on an approved row is allowed; the sealed-OOS
# evidence rows (evidence.parquet) and the status_history transition are BOTH preserved, so
# the historical fact "this factor once passed the legacy per-factor sealed-OOS gate" is not
# lost — only the current status label changes.
"""Revert all current `approved` factor-registry rows to `candidate` (v1.4).

Usage:
  venv/Scripts/python.exe workspace/scripts/revert_approved_to_candidate_v14.py            # dry-run
  venv/Scripts/python.exe workspace/scripts/revert_approved_to_candidate_v14.py --apply     # write
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("revert_approved_v14")

REGISTRY_DIR = ROOT / "data" / "factor_registry"
REASON = (
    "v1.4 book-level-promotion: factor-level `approved` mint retired, `candidate` is the "
    "terminal factor-level status. Reverting legacy approved row -> candidate to make the "
    "live registry consistent (user directive 2026-07-04). Sealed-OOS evidence + this "
    "status_history transition are preserved; only the current status label changes."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry-run)")
    args = ap.parse_args()

    from src.alpha_research.factor_registry import FactorRegistryStore

    log.info("registry master table WILL be touched: %s", REGISTRY_DIR / "factor_master.parquet")
    store = FactorRegistryStore(REGISTRY_DIR)
    master = store.factor_master
    current = master[master["is_current"].fillna(False)]
    approved = current[current["status"] == "approved"]

    if approved.empty:
        log.info("no current approved rows — nothing to do.")
        return 0

    log.info("%d current approved rows to revert -> candidate:", len(approved))
    targets = []
    for _, row in approved.iterrows():
        fid, ver = str(row["factor_id"]), int(row["version"])
        log.info("  %s v%d (validity=%s)", fid, ver, row.get("approval_validity"))
        targets.append((fid, ver))

    if not args.apply:
        log.info("DRY-RUN — re-run with --apply to write. No changes made.")
        return 0

    for fid, ver in targets:
        result = store.set_status(
            factor_id=fid, status="candidate", reason=REASON, version=ver,
            source_run_id="revert_approved_to_candidate_v14",
        )
        log.info("reverted %s: %s -> %s", fid, result["old_status"], result["new_status"])
    store.save()

    reloaded = FactorRegistryStore(REGISTRY_DIR)
    rc = reloaded.factor_master
    still = rc[rc["is_current"].fillna(False) & (rc["status"] == "approved")]
    log.info("post-revert current status counts: %s",
             rc[rc["is_current"].fillna(False)]["status"].value_counts().to_dict())
    if not still.empty:
        log.error("FAILED: %d approved rows remain: %s", len(still), still["factor_id"].tolist())
        return 1
    log.info("SUCCESS: 0 approved rows remain; all reverted to candidate (evidence preserved).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
