# SCRIPT_STATUS: ACTIVE — F2: import the universe-matrix evidence into the factor registry
"""Import the 7-universe matrix evidence (workspace/outputs/unified_eval_matrix/results.jsonl)
into the factor registry evidence table. Dry-run by default; --live to write.

Reference-decoupling (GPT impl-review V3/V5):
  * run_id = ``matrix_<schema>_<layer1_hash>`` — keyed on the reference-INVARIANT Layer-1 hash, so
    an approval/revoke (which changes the legacy methodology_hash) does NOT fork the run_id. Import
    is an UPSERT by (run_id, factor, version, universe, row_role) — never whole-run replacement —
    so per-domain imports stay additive and a re-import of the same Layer-1 cleanly replaces.
  * The inline ``resid_ic_vs_approved_*`` columns are a CACHE only (Option B). The CANONICAL
    marginal-vs-book metric is pushed to the append-only Layer2ResidualStore via
    ``extract_layer2_residuals`` (keyed by reference_set_hash + book type) — never imported as a
    canonical Layer-1 metric and never part of run_id / identity / P-GATE.

Rows carry universe_id + the effective-window governance fields (inside unified_metrics_json via
full-record packing) + the reference-decoupling provenance (layer1_methodology_hash, reference
hashes, row_role="native_layer1"). Evidence-only — never touches status
(formal_evidence_eligible=False on every row).
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
from src.alpha_research.factor_eval.layer2_residual_store import (  # noqa: E402
    Layer2ResidualStore, extract_layer2_residuals,
)

MATRIX_DIR = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_matrix"


def _run_id(method: dict) -> str:
    """V5: reference-INVARIANT import run_id. Fail-closed if the methodologies.json is LEGACY
    (no layer1_hash) — the matrix producer refuses to emit such a file without an explicit
    --migrate-legacy-methodology-json, so reaching here without it is a real error."""
    l1 = method.get("layer1_hash")
    if not l1:
        raise SystemExit("methodologies.json is LEGACY (no layer1_hash) — re-run the base matrix "
                         "to re-stamp under the new schema before importing (GPT impl-review V5).")
    schema = method.get("methodology_schema_version") or "v0"
    return f"matrix_{schema}_{l1}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="write the REAL registry (default: dry-run copy)")
    args = ap.parse_args()

    methods = json.loads((MATRIX_DIR / "methodologies.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (MATRIX_DIR / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
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
        method = methods[uid]
        rid = _run_id(method)
        out = store.record_formal_auto_evidence(
            run_id=rid, records=recs, methodology_hash=method["hash"],
            source_path=str(MATRIX_DIR / "results.jsonl"),
        )
        attached = out.get("attached", []) if isinstance(out, dict) else out
        print(f"{uid}: run_id={rid} legacy_hash={method['hash']} -> "
              f"{ {k: (len(v) if isinstance(v, list) else v) for k, v in out.items()} if isinstance(out, dict) else out}")
        total_attached += len(attached) if isinstance(attached, list) else 0

    # V3: push the reference-DEPENDENT residuals to the canonical append-only Layer-2 store
    # (NOT the registry's Layer-1 columns). The book is universe-independent (the approved set is
    # masked per universe, not redefined), so member lists come from any universe entry.
    any_method = next(iter(methods.values()))
    members_by_book = {
        "stable": any_method.get("reference_set_stable"),
        "current": any_method.get("reference_set_current"),
    }
    l2_store = Layer2ResidualStore(registry_dir / "layer2")
    n_l2 = extract_layer2_residuals(MATRIX_DIR / "results.jsonl", l2_store,
                                    members_by_book=members_by_book)
    print(f"Layer-2 residuals appended: {n_l2} (store: {l2_store.path})")

    if args.live:
        store.save()   # PERSIST — record_formal_auto_evidence only mutates in-memory
        print("store.save() committed to disk")

    ev = store.factor_evidence
    n_univ = ev["universe_id"].notna().sum() if "universe_id" in ev.columns else 0
    n_native = (ev["row_role"] == "native_layer1").sum() if "row_role" in ev.columns else 0
    print(f"evidence table now {len(ev)} rows; with universe_id: {n_univ}; native_layer1: {n_native}")
    if not args.live:
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
