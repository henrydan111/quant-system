# SCRIPT_STATUS: ACTIVE — combined quarantine+import DRY-RUN (zero live writes) for the GPT packet
"""Produce GPT's full pre-import dry-run packet WITHOUT touching the real registry: copy
data/factor_registry to a temp dir, apply the legacy quarantine + the matrix import there, and report
quarantine matches, per-universe import attach/skip, Layer-2 keys, and the canonical-view checks
(contaminated excluded, no duplicate canonical rows). The real registry stays untouched, so there is
no empty-canonical window during the GPT review pause; the live sequence (backup -> quarantine --live
-> import --live) runs back-to-back only after the final GO.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_registry.store import (  # noqa: E402
    FactorRegistryStore, LEGACY_CONTAMINATED_RESIDUAL_SCOPE,
)
from src.alpha_research.factor_eval.layer2_residual_store import (  # noqa: E402
    Layer2ResidualStore, extract_layer2_residuals,
)
from workspace.scripts.import_matrix_evidence import (  # noqa: E402
    MATRIX_DIR, _run_id, _validate_row, _assert_scope_and_reference_consistency,
)


def main() -> int:
    methods = json.loads((MATRIX_DIR / "methodologies.json").read_text(encoding="utf-8"))
    _assert_scope_and_reference_consistency(methods)
    rows = [json.loads(l) for l in (MATRIX_DIR / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    tmp = Path(tempfile.mkdtemp(prefix="combined_dryrun_"))
    shutil.copytree(PROJECT_ROOT / "data" / "factor_registry", tmp / "factor_registry")
    reg = tmp / "factor_registry"
    print(f"=== combined dry-run on temp copy {reg} (real registry UNTOUCHED) ===")
    store = FactorRegistryStore(reg)

    # 1) quarantine the legacy contaminated rows (on the temp store)
    q = store.quarantine_legacy_residual_scope(dry_run=False)
    print(f"\n[quarantine] matched={q['matched']} by_run_id={q['by_run_id']}")

    # 2) validate + import the fresh matrix rows per universe
    by_u, rejected, rows_read = {}, {}, {}
    for r in rows:
        uid = r.get("universe_id", "univ_all"); rows_read[uid] = rows_read.get(uid, 0) + 1
        reason = _validate_row(r, methods.get(uid, {})) if uid in methods else "unknown_universe"
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1; continue
        by_u.setdefault(uid, []).append(r)
    print(f"\n[import] rows_read={rows_read}\n[import] validator_rejected={rejected if rejected else 0}")
    total_att = 0
    for uid, recs in sorted(by_u.items()):
        out = store.record_formal_auto_evidence(run_id=_run_id(methods[uid], uid), records=recs,
                                                methodology_hash=methods[uid]["hash"],
                                                source_path=str(MATRIX_DIR / "results.jsonl"))
        att, sd, su = len(out["attached"]), len(out["skipped_drift"]), len(out["skipped_unknown"])
        total_att += att
        print(f"  {uid:18s} read={len(recs)} attached={att} skipped_drift={sd} skipped_unknown={su}"
              + (f"  DRIFT={out['skipped_drift'][:8]}" if sd else "")
              + (f"  UNKNOWN={out['skipped_unknown'][:8]}" if su else ""))

    # 3) Layer-2 extraction (member list valid — reference-book consistency asserted)
    am = next(iter(methods.values()))
    l2 = Layer2ResidualStore(reg / "layer2")
    n_l2 = extract_layer2_residuals(MATRIX_DIR / "results.jsonl", l2,
                                    members_by_book={"stable": am.get("reference_set_stable"),
                                                     "current": am.get("reference_set_current")})
    l2df = l2.records()
    keys_ok = bool(len(l2df)) and l2df[["factor_id", "universe_id", "layer1_methodology_hash",
                                       "reference_book_type", "reference_set_hash", "computed_at"]].notna().all().all()
    print(f"\n[layer2] appended={n_l2} required_keys_present={keys_ok} "
          f"book_types={sorted(set(l2df['reference_book_type']))} ref_hashes={sorted(set(l2df['reference_set_hash']))}")

    # 4) canonical-view checks
    canon = store.canonical_layer1_evidence()
    n_contam = int((canon["row_role"] == LEGACY_CONTAMINATED_RESIDUAL_SCOPE).sum())
    auto = canon[canon["run_type"].isin(["factor_lifecycle_auto", "factor_lifecycle_refresh"])]
    n_native = int((auto["row_role"] == "native_layer1").sum())
    dups = int(auto.duplicated(subset=["factor_id", "version", "universe_id"]).sum())
    print(f"\n[canonical] total={len(canon)} native_layer1_auto={n_native} "
          f"contaminated_in_canonical={n_contam} (want 0) | auto_dups_per(factor,ver,universe)={dups} (want 0)")
    print(f"\n[summary] total_attached={total_att} | quarantined={q['matched']} | "
          f"layer2_appended={n_l2} | PACKET_GREEN={n_contam == 0 and dups == 0 and keys_ok and not rejected}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
