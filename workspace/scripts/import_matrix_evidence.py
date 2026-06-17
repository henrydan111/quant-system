# SCRIPT_STATUS: ACTIVE — F2: import the universe-matrix evidence into the factor registry
"""Import the 7-universe matrix evidence (workspace/outputs/unified_eval_matrix/results.jsonl)
into the factor registry evidence table. Dry-run by default; --live to write.

Reference-decoupling (GPT impl-review V3/V5 + pre-import review):
  * run_id = ``matrix_<schema>_<universe>_<layer1_hash>`` — keyed PER UNIVERSE on the reference-INVARIANT
    Layer-1 hash. Import is an UPSERT by (run_id, factor, version, universe, row_role).
  * The inline ``resid_ic_vs_approved_*`` columns are a CACHE only. The CANONICAL marginal-vs-book metric
    is pushed to the append-only Layer2ResidualStore (keyed by reference_set_hash + book type).
  * IMPORT-SIDE VALIDATOR (GPT pre-flight defense-in-depth): every row is validated against its universe
    methodology BEFORE grouping — wrong schema / layer1-hash / reference-hash rows are REJECTED (not
    merely error rows). Low-coverage rows with NaN metric VALUES are kept (only malformed IDENTITY is
    rejected). + a scope assertion (residual_preprocess_scope == ESTU_STYLE_V1) and a reference-book
    consistency assertion across all 7 universes (so the single member-list passed to Layer-2 is valid).

Evidence-only — never touches status (formal_evidence_eligible=False on every row).
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
from workspace.scripts.unified_eval_common import build_frozen_methodology  # noqa: E402
from workspace.scripts import unified_eval_full_run as fr  # noqa: E402

MATRIX_DIR = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_matrix"
EXPECTED_SCOPE = "ESTU_STYLE_V1"
# identity keys a row MUST carry correctly; metric KEYS that must be PRESENT (value may be None = low-cov)
REQUIRED_METRIC_KEYS = ("heldout_rank_icir", "mean_rank_ic", "coverage", "effective_ic_days")


def _run_id(method: dict, universe_id: str) -> str:
    l1 = method.get("layer1_hash")
    if not l1:
        raise SystemExit("methodologies.json is LEGACY (no layer1_hash) — re-run the base matrix "
                         "to re-stamp under the new schema before importing (GPT impl-review V5).")
    schema = method.get("methodology_schema_version") or "v0"
    return f"matrix_{schema}_{universe_id}_{l1}"


def _validate_row(rec: dict, method: dict) -> str:
    """Return "" if the row is import-valid for its universe methodology, else a rejection reason
    (GPT pre-import condition 1). Rejects malformed IDENTITY only — NOT low-coverage NaN metric VALUES."""
    if rec.get("error"):
        return "error_row"
    if rec.get("methodology_schema_version") != method.get("methodology_schema_version"):
        return "schema_mismatch"
    if rec.get("layer1_methodology_hash") != method.get("layer1_hash"):
        return "layer1_hash_mismatch"
    if rec.get("reference_set_stable_hash") != method.get("reference_set_stable_hash"):
        return "stable_ref_hash_mismatch"
    if rec.get("reference_set_current_hash") != method.get("reference_set_current_hash"):
        return "current_ref_hash_mismatch"
    missing = [k for k in REQUIRED_METRIC_KEYS if k not in rec]   # KEY presence, value may be None
    if missing:
        return f"missing_metric_keys:{missing}"
    return ""


def _assert_scope_and_reference_consistency(methods: dict) -> None:
    """GPT pre-import conditions: (4) reference-book membership identical across all 7 universe
    methodologies (so the single member-list passed to Layer-2 extraction is valid), and a scope
    assertion — rebuild each universe methodology and confirm residual_preprocess_scope==ESTU_STYLE_V1
    AND its layer1 hash matches methodologies.json (proves the rows were produced under the scope-fixed
    methodology; the scope is baked into the layer1 hash that the per-row validator checks)."""
    stable_hashes = {m.get("reference_set_stable_hash") for m in methods.values()}
    current_hashes = {m.get("reference_set_current_hash") for m in methods.values()}
    stable_sets = {tuple(sorted(m.get("reference_set_stable", []))) for m in methods.values()}
    current_sets = {tuple(sorted(m.get("reference_set_current", []))) for m in methods.values()}
    if len(stable_hashes) != 1 or len(current_hashes) != 1 or len(stable_sets) != 1 or len(current_sets) != 1:
        raise SystemExit("reference-book membership/hashes DIFFER across universes — cannot pass a single "
                         "member list to Layer-2 extraction (GPT pre-import condition 4). Universe-specific "
                         "member metadata would be required.")
    for uid, m in methods.items():
        rebuilt = build_frozen_methodology(is_start=fr.TIME_SPLIT.is_start, is_end=fr.TIME_SPLIT.is_end,
                                           universe_id=uid)
        if rebuilt.residual_preprocess_scope != EXPECTED_SCOPE:
            raise SystemExit(f"{uid}: current methodology residual_preprocess_scope="
                             f"{rebuilt.residual_preprocess_scope!r} != {EXPECTED_SCOPE!r} — refuse import.")
        if rebuilt.layer1_methodology_hash != m.get("layer1_hash"):
            raise SystemExit(f"{uid}: rebuilt layer1 hash {rebuilt.layer1_methodology_hash} != "
                             f"methodologies.json {m.get('layer1_hash')} — methodology drift; refuse import.")
    print(f"scope+reference assertions PASSED: residual_preprocess_scope={EXPECTED_SCOPE}, "
          f"reference book identical across {len(methods)} universes "
          f"(stable_hash={next(iter(stable_hashes))}, current_hash={next(iter(current_hashes))})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="write the REAL registry (default: dry-run copy)")
    args = ap.parse_args()

    methods = json.loads((MATRIX_DIR / "methodologies.json").read_text(encoding="utf-8"))
    _assert_scope_and_reference_consistency(methods)
    rows = [json.loads(l) for l in (MATRIX_DIR / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    # GPT condition 1: methodology-aware validation BEFORE grouping. Reject malformed-identity rows.
    by_universe: dict[str, list] = {}
    rejected: dict[str, int] = {}
    rows_read: dict[str, int] = {}
    for r in rows:
        uid = r.get("universe_id", "univ_all")
        rows_read[uid] = rows_read.get(uid, 0) + 1
        method = methods.get(uid)
        if method is None:
            rejected["unknown_universe"] = rejected.get("unknown_universe", 0) + 1
            continue
        reason = _validate_row(r, method)
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        by_universe.setdefault(uid, []).append(r)
    print(f"rows read: {len(rows)} | rows_by_universe: {rows_read}")
    print(f"validator rejected: {rejected if rejected else '{}  (0 — all rows valid identity)'}")

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
        rid = _run_id(method, uid)
        out = store.record_formal_auto_evidence(
            run_id=rid, records=recs, methodology_hash=method["hash"],
            source_path=str(MATRIX_DIR / "results.jsonl"))
        att = len(out.get("attached", []))
        sd = len(out.get("skipped_drift", []))
        su = len(out.get("skipped_unknown", []))
        print(f"{uid:18s} run_id={rid}  read={len(recs)} attached={att} skipped_drift={sd} skipped_unknown={su}"
              + (f"  DRIFT={out['skipped_drift'][:6]}" if sd else "")
              + (f"  UNKNOWN={out['skipped_unknown'][:6]}" if su else ""))
        total_attached += att

    # Layer-2: push the reference-DEPENDENT residuals to the append-only store (member list is valid —
    # reference-book consistency asserted above).
    any_method = next(iter(methods.values()))
    members_by_book = {"stable": any_method.get("reference_set_stable"),
                       "current": any_method.get("reference_set_current")}
    l2_store = Layer2ResidualStore(registry_dir / "layer2")
    n_l2 = extract_layer2_residuals(MATRIX_DIR / "results.jsonl", l2_store, members_by_book=members_by_book)
    print(f"Layer-2 residuals appended: {n_l2} (store: {l2_store.path})")

    if args.live:
        store.save()
        print("store.save() committed to disk")

    # canonical-view check: quarantined-legacy excluded + no dup canonical rows per (factor,ver,universe)
    canon = store.canonical_layer1_evidence()
    from src.alpha_research.factor_registry.store import LEGACY_CONTAMINATED_RESIDUAL_SCOPE
    n_contam = int((canon["row_role"] == LEGACY_CONTAMINATED_RESIDUAL_SCOPE).sum()) if "row_role" in canon else -1
    auto = canon[canon["run_type"].isin(["factor_lifecycle_auto", "factor_lifecycle_refresh"])]
    dups = int(auto.duplicated(subset=["factor_id", "version", "universe_id"]).sum())
    print(f"total attached: {total_attached} | canonical rows: {len(canon)} | "
          f"contaminated in canonical: {n_contam} (want 0) | canonical auto dups: {dups} (want 0)")
    if not args.live:
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
