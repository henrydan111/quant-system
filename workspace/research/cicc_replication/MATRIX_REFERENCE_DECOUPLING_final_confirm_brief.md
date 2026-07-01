# Matrix reference-decoupling — FINAL CONFIRM brief for GPT 5.5 Pro (migration/import chunk)

**You previously returned CHANGES REQUIRED (impl-review V1–V6, A1–A3).** V1/V2/A1/A2 landed in the prior
commit (verified). This brief covers the **migration/import chunk** — the production-touching code you
asked to see before it runs. Nothing here has touched production evidence yet: the `--apply` (registry
write) and the native E1a re-run are still GATED on your confirm. The read-only **V4 byte-equality
proof has been executed** (results below).

Please confirm (or change) so I can run, in this order (V6): **migrate → then E1a**.

---

## What this chunk does (recap of the design you approved in R2)

Two-layer reference-decoupling. **Layer-1** = the matrix's reference-INVARIANT metrics (walk-forward
IC/ICIR, quantile/decay/turnover/coverage, neutralized IC, the frozen-STYLE_CONTROLS_V1 residual,
long-leg), keyed by `layer1_methodology_hash` (reference-EXCLUDED). **Layer-2** = the
reference-DEPENDENT `resid_ic_vs_approved_*` marginal-vs-book metric, moved to an append-only store
keyed by `reference_set_hash` + book type. An approval/revoke now appends Layer-2 rows and never
recomputes Layer-1.

---

## How each of your impl-review points is addressed in CODE

| Pt | Your ask | Disposition (code) |
|---|---|---|
| **V3** | inline `resid_ic_vs_approved_*` must NOT become a 2nd source of truth | The matrix import (`import_matrix_evidence.py`) now calls `extract_layer2_residuals(...)` → the canonical **Layer2ResidualStore** (`data/factor_registry/layer2/`). The inline columns remain a CACHE only; they are never in `run_id`/identity/P-GATE. |
| **V4** | migration value-safety: dry-run → sample-recompute → assert byte-equal Layer-1 → only then append | `migrate_evidence_reference_decoupling.py` has 3 modes: `--dry-run` (plan, no eval/writes), `--sample-recompute` (recompute a stratified ≥20-pair sample with the CURRENT producer code and assert byte-equality vs the STORED legacy values; writes a PASS token), `--apply` (gated; appends derived rows + stamps `layer1_value_digest`). |
| **V5** | import run_id keyed on the STABLE layer1 hash; UPSERT, never whole-run replace | Both imports now use `run_id = <prefix>_<schema>_<layer1_hash>`. The store's upsert key is now `(run_id, factor, version, universe, row_role)` — additive per-domain, idempotent per layer1 hash, and lets a `migrated_layer1` sibling sit next to the immutable `legacy` row. |
| **V6** | order: migrate first, then E1a | The migration is written/run first; the native E1a matrix run supersedes the matrix subset afterward (a native row outranks a migrated row in `canonical_layer1_evidence`). |
| **A3** | R4 test must not be skippable before `--apply` | `--apply` runs the R4 invariance test inline (subprocess pytest) AND requires a FRESH sample-recompute token (same git SHA + matching layer1 hashes). Any gate failure → `SystemExit` (fail-closed). |
| **item 1** | dedupe / default-view (migrated XOR legacy) | New `canonical_layer1_evidence(df)` (module fn + store method) collapses the auto/matrix family to ONE row per (factor, version, universe) by row_role precedence `native > migrated > legacy`, then recency. Unit-tested. |

**Migration mechanism (no recompute).** For each legacy row, the migration round-trips its
`unified_metrics_json` (the original full eval rec), OVERRIDES only the identity fields
(`layer1_methodology_hash`, reference hashes, schema, `row_role="migrated_layer1"`,
`legacy_methodology_hash`, `migration_id`, `layer1_value_digest`), and re-imports it under the SAME
legacy `run_id`. The Layer-1 metric VALUES are carried verbatim; `layer1_value_digest` is a sha256 over
exactly the reference-invariant payload (same exclusion set the byte-equality proof uses). The store's
definition-binding stays fail-closed — a drifted/deprecated factor is SKIPPED (not migrated), so its
stale evidence is never stamped with the new hash.

**Why the byte-equality proof is meaningful (not circular).** It recomputes with the CURRENT producer
code and compares to the STORED legacy values. A match proves the legacy rows are protocol-consistent
(the current `layer1_methodology_hash` legitimately applies). A mismatch == protocol / window /
STYLE_CONTROLS drift → the proof FAILS and the migration is BLOCKED (those rows must be re-run
natively, not migrated). A behavior-changing bug in my `build_base_ctx` extraction surfaces here as a
proof failure, never as silent corruption.

---

## Scope (live registry, measured)

- **1,711 legacy auto/refresh rows**: 1,526 matrix (7 universes × 218 factors) + 185 unified-refresh
  (univ_all). All pre-decoupling (`row_role=""`, no `layer1_methodology_hash`).
- Per-universe `layer1_methodology_hash` (schema `unified_eval_layer1_ref_invariant_v1`): univ_all
  `c4a3340f…`, csi1000 `6c710037…`, csi300 `073ed53b…`, csi500 `82336d5c…`, growth `5f06a610…`,
  liquid_top300 `912fae9a…`, microcap `69d3a0a9…`. (univ_all folds BOTH the matrix and the
  unified_refresh legacy run_ids under one methodology.)

## V4 byte-equality proof — RESULT

<!-- PROOF_RESULT_PLACEHOLDER -->

---

## Code (GitHub permalinks)

<!-- PERMALINKS_PLACEHOLDER -->

## Tests

`tests/alpha_research/test_factor_registry.py` (32) + `test_unified_eval.py` (35) +
`test_matrix_reference_invariance.py` (5, incl. the R4 gate + the new canonical-view dedupe) — all green.

---

## The decision I need from you

1. **Is the migration mechanism sound** (round-trip `unified_metrics_json` + override identity + append
   `migrated_layer1` sibling under the legacy run_id, legacy row immutable)?
2. **Is the V4 proof sufficient** as the value-safety gate (stratified ≥20-pair byte-equality vs stored
   legacy, fail-closed on any mismatch), or do you want a different sample / a 100% recompute?
3. **Is the `--apply` gate set right** (R4-green inline + fresh sample-recompute token), or stricter?
4. Any objection to the V6 run order (migrate → E1a) once you confirm?

If APPROVE: I run `--apply` (writes the migrated siblings + Layer-2 store), then re-run E1a natively.
