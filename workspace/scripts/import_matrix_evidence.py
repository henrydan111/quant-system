# SCRIPT_STATUS: ACTIVE — F2: import the universe-matrix evidence into the factor registry
"""Import the 7-universe matrix evidence (workspace/outputs/unified_eval_matrix/results.jsonl)
into the factor registry evidence table. Dry-run by default; --live to write.

One import call PER UNIVERSE (each domain has its own methodology hash; run_id =
matrix_<hash8>); the store's universe-aware replace key keeps per-domain imports
additive and idempotent. Rows carry universe_id + the effective-window governance
fields (inside unified_metrics_json via full-record packing). Evidence-only —
never touches status (formal_evidence_eligible=False on every row).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_registry.store import FactorRegistryStore  # noqa: E402

MATRIX_DIR = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_matrix"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="write the REAL registry (default: dry-run copy)")
    args = ap.parse_args()

    methods = json.loads((MATRIX_DIR / "methodologies.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (MATRIX_DIR / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    by_universe: dict[str, list] = {}
    for r in rows:
        if "error" in r:
            continue
        by_universe.setdefault(r.get("universe_id", "univ_all"), []).append(r)
    print(f"matrix rows: {len(rows)} | universes: { {u: len(v) for u, v in by_universe.items()} }")

    if args.live:
        registry_dir = PROJECT_ROOT / "data" / "factor_registry"
    else:
        tmp = Path(tempfile.mkdtemp(prefix="matrix_import_dryrun_"))
        shutil.copytree(PROJECT_ROOT / "data" / "factor_registry", tmp / "factor_registry")
        registry_dir = tmp / "factor_registry"
        print(f"dry-run registry copy: {registry_dir}")

    store = FactorRegistryStore(registry_dir)
    total_attached = 0
    for uid, recs in sorted(by_universe.items()):
        mhash = methods[uid]["hash"]
        out = store.record_formal_auto_evidence(
            run_id=f"matrix_{mhash}", records=recs, methodology_hash=mhash,
            source_path=str(MATRIX_DIR / "results.jsonl"),
        )
        attached = len(out.get("attached", out.get("factors", []))) if isinstance(out, dict) else out
        print(f"{uid}: methodology {mhash} -> {out if not isinstance(out, dict) else {k: (len(v) if isinstance(v, list) else v) for k, v in out.items()}}")
        total_attached += (len(out.get('attached', [])) if isinstance(out, dict) else 0)

    if args.live:
        store.save()   # PERSIST — record_formal_auto_evidence only mutates in-memory
        print("store.save() committed to disk")

    ev = store.factor_evidence
    n_univ = ev["universe_id"].notna().sum() if "universe_id" in ev.columns else 0
    print(f"evidence table now {len(ev)} rows; rows with universe_id: {n_univ}")
    if not args.live:
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
