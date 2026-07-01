# SCRIPT_STATUS: ACTIVE — pre-import quarantine of residual-scope-contaminated matrix evidence
"""Positively mark the pre-fix matrix/refresh evidence rows as `legacy_contaminated_residual_scope`
so default reads (FactorRegistryStore.canonical_layer1_evidence) fail-closed exclude them
(GPT pre-flight blocker 4). Target = auto/refresh rows with an EMPTY layer1_methodology_hash —
produced before the residual-control-scope fix; their resid_* columns used the batch-order-dependent
control scope and must NOT back any read/decision. Rows are KEPT in the table for audit.

Run BEFORE importing the freshly-rebuilt matrix. Dry-run by default; --live mutates + saves.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_registry.store import FactorRegistryStore  # noqa: E402

REGISTRY = PROJECT_ROOT / "data" / "factor_registry"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="mutate + save (default: dry-run report)")
    args = ap.parse_args()
    store = FactorRegistryStore(REGISTRY)
    out = store.quarantine_legacy_residual_scope(dry_run=not args.live)
    print(f"contaminated rows matched: {out['matched']} (marker={out.get('marker')})")
    for rid, n in sorted(out.get("by_run_id", {}).items()):
        print(f"  {rid}: {n}")
    if args.live and out["matched"]:
        store.save()
        print("store.save() committed — contaminated rows now excluded from canonical reads")
    elif not args.live:
        print("dry-run — re-run with --live to mark + persist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
