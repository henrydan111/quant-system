# ──────────────────────────────────────────────────────────────────────
# script_status: research_tooling
# formal_research_allowed: false
# deployment_target: unified_eval_evidence_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   2026-06-10 unified merge — import the full-catalog unified-eval sweep into the factor
#   registry EVIDENCE table via FactorRegistryStore.record_formal_refresh_evidence
#   (run_type='factor_lifecycle_refresh', evidence_class='unified_refresh',
#   formal_evidence_eligible=False — formal METHODOLOGY, ungated run; can never support a
#   status change). Definition-bound fail-closed; idempotent per run_id. DEFAULT IS
#   --dry-run (imports into a TEMP COPY of data/factor_registry and reports); pass --live
#   to write the real registry (user-authorized 2026-06-10: "将lifecycle和unified_eval合并").
# ──────────────────────────────────────────────────────────────────────
"""Import unified-eval refresh evidence into the factor registry (dry-run by default)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_registry import FactorRegistryStore

EVAL_DIR = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval"
REGISTRY = PROJECT_ROOT / "data" / "factor_registry"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="write the REAL registry (default: dry-run copy)")
    args = ap.parse_args()

    full = pd.read_parquet(EVAL_DIR / "unified_eval_full.parquet")
    meta = json.loads((EVAL_DIR / "methodology.json").read_text(encoding="utf-8"))
    mhash = meta["hash"]               # legacy reference-INCLUDED hash (kept as the legacy column)
    # V5: run_id is keyed on the reference-INVARIANT layer1 hash, so an approval/revoke does not
    # fork the run_id. Native rows (row_role="native_layer1") thus live under a fresh run_id and
    # never collide with the pre-decoupling legacy ("") rows under unified_refresh_<legacy_hash>.
    l1 = meta.get("layer1_hash")
    if not l1:
        raise SystemExit("methodology.json is LEGACY (no layer1_hash) — re-run the unified sweep to "
                         "re-stamp under the new schema before importing (GPT impl-review V5).")
    schema = meta.get("methodology_schema_version") or "v0"
    run_id = f"unified_refresh_{schema}_{l1}"
    records = [r for r in full.to_dict("records") if not r.get("error")]
    n_err = len(full) - len(records)
    print(f"sweep rows: {len(full)} | importable: {len(records)} | error rows skipped: {n_err}")
    print(f"run_id: {run_id} | legacy methodology_hash: {mhash} (commit {meta.get('code_commit')})")

    if args.live:
        root = REGISTRY
        print("MODE: LIVE — writing data/factor_registry/")
    else:
        tmp = Path(tempfile.mkdtemp(prefix="unified_refresh_dryrun_"))
        shutil.copytree(REGISTRY, tmp / "factor_registry")
        root = tmp / "factor_registry"
        print(f"MODE: DRY-RUN — temp copy at {root}")

    store = FactorRegistryStore(root)
    out = store.record_formal_refresh_evidence(
        run_id=f"unified_refresh_{mhash}", records=records, methodology_hash=mhash,
        source_path=str(EVAL_DIR.relative_to(PROJECT_ROOT)),
    )
    store.save()
    print(f"attached: {len(out['attached'])} | skipped_drift: {len(out['skipped_drift'])} "
          f"| skipped_unknown: {len(out['skipped_unknown'])}")
    if out["skipped_drift"]:
        print("  drift:", out["skipped_drift"][:10], "..." if len(out["skipped_drift"]) > 10 else "")
    if out["skipped_unknown"]:
        print("  unknown:", out["skipped_unknown"][:10], "..." if len(out["skipped_unknown"]) > 10 else "")
    ev = store.factor_evidence
    ref = ev[ev["run_type"] == "factor_lifecycle_refresh"]
    print(f"refresh rows in evidence table: {len(ref)} | eligible=False all: "
          f"{bool((~ref['formal_evidence_eligible'].astype(bool)).all())}")
    if not args.live:
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
