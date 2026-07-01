# Matrix reference-decoupling — IMPLEMENTATION cross-review brief (for GPT 5.5 Pro)

**Gate:** APPROVE the landed PR-0/1a/1b/1c implementation + the migration plan → I then run the
evidence migration + the E1a matrix. / CHANGES REQUIRED. This is the impl-review you asked for
"before it touches the evidence tables" — nothing has touched production evidence yet.

**Repo:** https://github.com/henrydan111/quant-system  **Reviewed commit:** `f9cee72` on `report-rc-registration`
**Design (authoritative, R1–R6 + C1–C4 folded):**
https://github.com/henrydan111/quant-system/blob/f9cee72/workspace/research/cicc_replication/MATRIX_REFERENCE_DECOUPLING_DESIGN.md

## What landed (all verified; NO production-evidence mutation)

- **PR-0** ([test_matrix_reference_invariance.py](https://github.com/henrydan111/quant-system/blob/f9cee72/tests/alpha_research/test_matrix_reference_invariance.py)) —
  R4 gate: runs `_evaluate_batch` twice on identical synthetic panels changing ONLY the approved book;
  asserts every Layer-1 column byte-identical except `resid_ic_vs_approved_*` + the two reference
  hashes. **GREEN (1 passed, 120s).** The empirical lock for Layer-1 reference-invariance.
- **PR-1a** ([unified_eval.py](https://github.com/henrydan111/quant-system/blob/f9cee72/src/alpha_research/factor_eval/unified_eval.py) `EvalMethodology`) —
  added `layer1_methodology_hash` (reference-EXCLUDED, the live identity), `reference_set_stable_hash`
  + `reference_set_current_hash` (R1: two hashes), `methodology_schema_version` (recorded, never
  hashed). `methodology_hash` retained BIT-IDENTICAL as legacy. 35 unit tests pass incl.
  `test_layer1_methodology_hash_is_reference_book_invariant`.
- **PR-1b** ([unified_eval_full_run.py:_evaluate_batch](https://github.com/henrydan111/quant-system/blob/f9cee72/workspace/scripts/unified_eval_full_run.py)) —
  every eval record now carries the new hashes (reference hashes from the ACTUAL ctx book). Additive;
  R4 re-green.
- **PR-1c** —
  * Drift switch ([unified_eval_universe_matrix.py](https://github.com/henrydan111/quant-system/blob/f9cee72/workspace/scripts/unified_eval_universe_matrix.py)):
    resume identity = `layer1_methodology_hash`; `methodologies.json` stores hash + layer1_hash +
    schema_version + both reference hashes; a legacy file (no layer1_hash) re-stamps transparently
    (NOT drift). This stops the approval churn.
  * [Layer2ResidualStore](https://github.com/henrydan111/quant-system/blob/f9cee72/src/alpha_research/factor_eval/layer2_residual_store.py) (R2):
    append-only, keyed `(factor, universe, layer1_hash, reference_book_type, reference_set_hash,
    computed_at)`; `latest_descriptive` read view; `assert_single_reference` (C3 cross-book guard);
    `extract_layer2_residuals` populates from results.jsonl. 3 unit tests pass.
  * R5: `panel_index` sourced from ADJ + STYLE_CONTROLS_V1 (not the union seed); approved factors are
    residual controls only. Value-preserving (index invariance proven by the premise-check, locked by R4).

## The remaining migration + wire-ups (NOT yet written — the part this review gates)

1. **`factor_evidence` schema** ([store.py](https://github.com/henrydan111/quant-system/blob/f9cee72/src/alpha_research/factor_registry/store.py) FACTOR_EVIDENCE_COLUMNS) —
   add `methodology_schema_version, layer1_methodology_hash, reference_set_stable_hash,
   reference_set_current_hash, row_role, legacy_methodology_hash, migration_id, layer1_value_digest`.
2. **`record_formal_auto_evidence` import key** — include schema_version + layer1 hash; Layer-2
   residuals go to the Layer2Residual table, never mutating Layer-1 evidence identity.
3. **`import_matrix_evidence`** — carry the new fields; call `extract_layer2_residuals` so the
   approved-book residuals land in the Layer-2 table (Option B: inline kept as cache).
4. **Migration script** (append-only; legacy immutable) — for the existing ~1568 matrix evidence
   rows, append derived `row_role=migrated_layer1` rows: recompute `layer1_methodology_hash`, copy
   `legacy_methodology_hash` = the row's old `methodology_hash`, stamp `migration_assertion
   {layer1_values_unchanged:true, approved_book_residuals_moved_to_layer2:true}` + `layer1_value_digest`
   + both reference hashes (the 9-approved book those rows used). Extract their resid → Layer2Residual
   (tagged with the legacy book's reference_set_hash). `--dry-run` default. Migration dedupe: default
   views select migrated XOR legacy.
5. **Dashboard** — show Layer-1 methodology separately from Layer-2 reference snapshots; comparison
   queries refuse mixed reference hashes.

## Verification points — challenge each

**V1 — Drift switch correctness.** Read the matrix `methodologies.json` block: resume now compares
`layer1_methodology_hash`; a legacy file (only `"hash"`) re-stamps without firing; a protocol/style
change still raises. Is the legacy-file transparent-re-stamp safe, or should it require an explicit
`--migrate` flag rather than auto-re-stamping on a normal run?

**V2 — Layer-2 store keys + append-only.** Are the key columns sufficient to never collide two
distinct computations, and is `assert_single_reference` the right C3 enforcement point (it's a
query-time guard; the producer doesn't call it)? Should the producer also refuse to *write* mixed
books in one batch?

**V3 — Option B cache risk.** PR-1b/c keep `resid_ic_vs_approved_*` INLINE in results.jsonl (cache)
AND will write them to the Layer2Residual table (canonical via `extract_layer2_residuals`). Is the
dual-write acceptable as the documented Option-B shim, or must the inline columns be dropped from new
rows in this PR (Option A) to avoid two sources of truth?

**V4 — Migration value-safety.** The migration appends derived rows asserting `layer1_values_unchanged`.
R4 + the premise-check prove the approved book doesn't change Layer-1 values, so the existing rows'
Layer-1 columns ARE valid under the new layer1 hash without recompute. Is appending a derived row
(carrying `layer1_value_digest` to prove equivalence) the right mechanism, or do you want the migration
to RECOMPUTE a sample of rows and assert byte-equality before trusting the digest?

**V5 — import_matrix_evidence run_id.** Existing rows imported under `run_id=matrix_<legacy9hash>`; new
E1a rows would import under `matrix_<legacy7hash>` (the legacy hash still churns — only layer1 is
stable). Should the import run_id switch to `matrix_<layer1hash>` (stable) so E1a + future factors
share one run_id, with the reference book recorded separately? (I lean yes — otherwise every approval
still spawns a new run_id namespace even though the Layer-1 evidence is identical.)

**V6 — Anything that breaks by NOT migrating first.** If I run the E1a matrix BEFORE migrating the
existing rows: new rows carry the new schema fields; old rows don't. The dashboard / import read both.
Is running E1a-first (new rows new-schema, old rows legacy until migrated) safe, or must the migration
run first so the evidence table is single-schema before any new rows land?

## Requested verdict
Per V1–V6: OK / CHANGES REQUIRED (+ fix). Overall: APPROVE (run migration then E1a matrix, in which
order) / CHANGES REQUIRED before any production run.
