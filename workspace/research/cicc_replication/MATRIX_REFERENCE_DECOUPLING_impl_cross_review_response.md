# Matrix reference-decoupling — response to GPT 5.5 Pro impl-review (CHANGES REQUIRED)

**Verdict:** CHANGES REQUIRED before any production evidence run. Landed core directionally approved;
fixes required in the evidence-provenance wire-up. Split: V1/V2/A1/A2 are **landed-code** fixes (done
+ tested in this commit); V3/V4/V5/A3 + the V6 order govern the **migration/import** chunk (not yet
written — the production-touching step, which gets a final confirm before it runs).

| Pt | Verdict | Status | Where |
|---|---|---|---|
| **V1** drift legacy re-stamp too automatic | CHANGES REQ | **FIXED** | matrix now REFUSES to re-stamp a legacy methodologies.json without `--migrate-legacy-methodology-json`; backs up `methodologies.legacy.<ts>.json` first; does not infer the old book from the current registry. |
| **V2** Layer-2 under-keyed appends | CHANGES REQ | **FIXED** | `append()` enforces `REQUIRED_KEYS` (factor/universe/layer1_hash/book_type/reference_hash/computed_at) at write; `extract_layer2_residuals` skips rows lacking `layer1_methodology_hash`. Unit test added. |
| **A2** member JSON not populated | finding | **FIXED** | `extract_layer2_residuals(members_by_book=…)` populates `reference_set_members_json` (sorted); tested. |
| **A1** full_run still on legacy resume | finding | **FIXED** | `unified_eval_full_run` + `unified_eval_matrix_layer2` resume now compare `layer1_methodology_hash`; a legacy file (no layer1_hash) raises with a migrate/clear instruction (no silent rewrite). |
| **V3** Option-B inline cache → 2nd source of truth | CHANGES REQ | **ACCEPTED → migration/import** | import will NOT import `resid_ic_vs_approved_*` as canonical Layer-1; they go to Layer2ResidualStore only (inline kept as `*_cache`, never in run_id/identity/P-GATE). + a test. |
| **V4** migration value-safety | CHANGES REQ | **ACCEPTED → migration** | migration runs dry-run → **sample recompute** (≥20 factor×universe across style/approved/candidate/PV/fundamental + univ_all + a thin domain) → assert byte-equal Layer-1 → only then append derived rows (with `layer1_value_digest`). |
| **V5** import run_id should key on stable layer1 hash | CHANGES REQ | **ACCEPTED → import (Option A)** | `run_id = matrix_<schema>_<layer1_hash>`, import = **UPSERT by (run_id, factor, universe, row_role)**, never whole-run replacement (verify vs `_replace_run_evidence`). |
| **V6** ordering | CHANGES REQ | **ACCEPTED: migrate-first** | production order: schema+import-key → dedupe/default-views → migration dry-run → sample recompute → append migrated + extract legacy Layer-2 → THEN run/import E1a. E1a-first only as a scratch (non-imported) filesystem run. |
| **A3** R4 test skippable | finding | **ACCEPTED → migration** | the migration `--apply` will require a recorded GREEN R4 artifact (or run R4 in a calendar-present env) before applying. |

## Verified now (landed-code fixes)
`py_compile` OK on all four edited drivers/stores; `test_unified_eval` (35) + the 3 Layer-2 unit tests
= **38 passed**. R4 gate unchanged path (last green at PR-1b, 120s).

## Remaining (the migration/import chunk — production-touching, gets a final confirm before running)
1. `factor_evidence` schema fields (`methodology_schema_version`, `layer1_methodology_hash`,
   `reference_set_stable/current_hash`, `row_role`, `legacy_methodology_hash`, `migration_id`,
   `layer1_value_digest`) + dedupe/default-view (migrated XOR legacy).
2. `record_formal_auto_evidence` / `import_matrix_evidence` — V3 (Layer-2 not canonical Layer-1) + V5
   (stable run_id, upsert) + call `extract_layer2_residuals` with the methodology member lists (A2).
3. Migration script: V4 dry-run + sample-recompute + append-derived (legacy immutable) + legacy
   Layer-2 extraction (carrying the OLD book from the backed-up methodologies.legacy.json, V1).
4. A3 R4-green gate on `--apply`. Then V6 order: migrate → E1a.

I'll implement that chunk next and send it for a final confirm before it touches production evidence.
