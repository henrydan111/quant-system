# Factor Lifecycle — Phase 2 Design Spec (registry schema / evidence)

**Date:** 2026-05-31. **Status:** DRAFT v2 — **GPT cross-review integrated** (conditional GO; GPT ran
the repo: `test_factor_registry.py` 16 passed, verified the CSV/code grounding). No code written yet.
Phase 2 = the **registry evidence/metadata schema** (plan §4 Phase 2; §2.1 master shape; §3 taxonomy).

**Hard boundary (unchanged):** Phase 2 is **schema + evidence population ONLY**. It NEVER writes
`status`, `approval_validity`, or `definition_hash`; it does NOT promote; it does NOT wire `get_factors()`
(Phase 3) or any seal/`FrozenSelectionSet` behavior (Phase 3/5, GPT-confirmed). It adds columns + a
read-only populator so the Phase-6 backfill acts on structured data, not CSVs/markdown. `approval_validity`
already landed in P1.1. **Boundary integrity (GPT §4):** because Phase 2 touches none of `status` /
`approval_validity` / `definition_hash`, the Phase-1 reader (`resolver.py:147` labels only `approved`+valid
as `formal`) and writer (`store.py` `set_status` gate) are unaffected — new evidence columns cannot leak
into resolution or promotion.

## GPT cross-review — what changed in v2
1. **LO metric is GROSS, not cost-adjusted.** `long_only_topbucket` deducts no turnover/cost. v2 stores
   it as `lo_*_gross` and makes the Phase-2 `long_only_viable` **PROVISIONAL** (gross-based); the
   **formal cost-adjusted** viability (plan §3) is **deferred** to a `formal_candidate`-class recompute
   path (Phase 4 modules). Gross evidence must not be treated as formal long-only proof.
2. **Importer must definition-bind, never attach by name.** The revalidation CSV/JSON carry no
   `definition_hash`/`catalog_hash`. P2.3 recomputes the current code `definition_hash` per factor and
   matches the registry row's hash BEFORE writing evidence — **fail-closed** on mismatch/missing (else a
   changed definition inherits stale evidence by name).
3. **Multi-source, structured-first importer.** `is/oos_rank_icir`, `sign_consistency`, `lo_*` come from
   `catalog_revalidation/*.csv`; `oos_ls_sharpe` / `retain_pct` come from
   `screening_oos/screening_oos_report.csv` (+ `.parquet`). Prefer CSV/parquet/JSON; do NOT parse markdown.
4. **Missing columns added:** `signal_role_suggested` (was prose-only) + `field_eligibility_snapshot_json`
   (plan §2.1) are now explicit in P2.1.
5. **Historical-evidence labeling.** Imported revalidation numbers carry `evidence_class=
   historical_investigation` + `formal_evidence_eligible=false` + `source_path`+`source_hash`. They are
   NON-approval evidence and can NOT satisfy the promotion gate without a formal recompute.

## Scope (re-sequenced per GPT: schema foundation first)
| # | Item | Adds |
|---|---|---|
| **P2.1** | **Full schema foundation** (all columns, fail-closed load defaults) | *evidence:* `is_rank_icir, oos_rank_icir, sign_consistency, oos_ls_sharpe, retain_pct, lo_excess_ann_gross, lo_sharpe_gross, lo_hit, evidence_class, formal_evidence_eligible, source_path, source_hash, provider_build_id, calendar_policy_id`; *master latest-mirrors + metadata:* `latest_oos_rank_icir, latest_lo_sharpe_gross, long_only_viable_provisional, expected_direction, signal_role, signal_role_suggested, requires_inverse_for_long_only, approved_uses, validation_scope, field_eligibility_snapshot_json, last_revalidated_at, latest_provider_build_id, latest_calendar_policy_id` |
| **P2.2** | `long_only_viable_provisional` **derivation** (deterministic, in `refresh_master_derived_fields`) | — |
| **P2.3** | `import_revalidation(...)` populator (definition-bound, multi-source, evidence-labeled, NO status writes) | — |
| **P2.4** | HTML review + CLI surfacing + schema-migration / viability-boundary / definition-bind / boundary-integrity tests | — |

Build order: **P2.1 → P2.2 → P2.3 → P2.4**. Every new column normalizes on load (fail-closed defaults,
mirroring P1.1's `_normalize_approval_validity`) so pre-Phase-2 registries read back unchanged.

## P2.1 — column home (GPT open-Q1)
Per-run metrics live on **`factor_evidence`** (append-only, matches the existing IC-evidence + provenance
rows); `factor_master` carries **`latest_*` mirrors** populated by `refresh_master_derived_fields()` (the
existing pattern at `store.py:590/667/981`). Provenance (`provider_build_id`/`calendar_policy_id`) is an
**evidence-row** field with a latest-mirror on master — master-only is insufficient since evidence spans
multiple runs.

## P2.2 — provisional long-only viability (GPT open-Q2/Q3 + refined order)
`long_only_viable_provisional` is **stored on master but DERIVED deterministically** from the latest
gross LO evidence during refresh/load (NOT manually editable). Decision order (fail-closed, GPT):
```
missing/NaN                                   -> non_viable
sharpe_gross >= 1.0 and excess > 0 and hit >= 0.60 -> viable
sharpe_gross < 0.5 or excess <= 0             -> non_viable
sharpe_gross >= 0.5 and excess > 0            -> review_only   (else non_viable)
```
`review_only` is **fail-closed for automated/formal long-only use** (treated as non-viable by any
formal long-only path) but remains advisory for human review / `risk_sleeve` / `short_side` /
`neutralizer` classification. NOTE: this is the GROSS proxy; the **formal** cost-adjusted
`long_only_viable` (plan §3) is a later-phase recompute. Spot-check (GPT, live data): of 16 derived
IC-candidates → 2 `viable`, 2 `review_only`, 12 `non_viable`.

## P2.1 — signal-role: auto-SUGGESTED vs human-ASSIGNED (plan §3)
`signal_role_suggested` (auto, from the metric: `long_only_viable_provisional==viable` → suggest
`long_only_alpha`; high-|IC| + weak long-only → suggest nothing) is SEPARATE from the authoritative
`signal_role` (default `unassigned`; human-assigned via a gated CLI, never auto). Weak long-only does
NOT auto-imply `risk_sleeve`.

## P2.3 — importer (definition-bound, structured, NO status writes)
`FactorRegistryStore.import_revalidation(catalog_csv, derived_csv, oos_report_csv, provider_manifest)`:
for each factor, (a) recompute the current code `definition_hash` and require it to match the registry
row's hash — else **skip + log fail-closed** (never attach by name alone, GPT §3); (b) append a
`factor_evidence` row with the metrics + `evidence_class=historical_investigation` +
`formal_evidence_eligible=false` + `source_path`/`source_hash` + provenance; (c) `refresh_master_derived_fields()`
recomputes the latest-mirrors + `long_only_viable_provisional`. It MUST NOT touch `status` (every row
stays `draft`; Phase 6 does the gated status backfill). Idempotent; logs matched/missed/hash-skipped.

## Open questions — RESOLVED (GPT)
1. Column home → evidence + `latest_*` mirror; provenance on evidence + latest-mirror. ✓ (P2.1)
2. `long_only_viable` → stored on master, derived in refresh (not editable). ✓ (P2.2)
3. `review_only` → fail-closed for formal long-only; advisory otherwise. ✓ (P2.2)
4. Historical CSV trust → evidence only, labeled `historical_investigation` + `formal_evidence_eligible=false`
   + source path/hash + definition-bound; cannot satisfy promotion. ✓ (v2 §5, P2.3)
5. Seal/frozen-set → Phase 2 touches none of it; single-seal-key rule stays Phase 3/5. ✓ (boundary)

## Boundary / non-goals
No status change, no promotion, no `get_factors()` (Phase 3), no orchestrator profile (Phase 5), no
seal/frozen-set wiring (Phase 3/5), no 171/6 backfill (Phase 6), no cost-adjusted/formal LO recompute
(later phase). Pure additive schema + a definition-bound read-only populator + tests + HTML.

## Acceptance
All new columns added with fail-closed load defaults; `long_only_viable_provisional` derivation matches
the §3 thresholds (unit-tested at 0.5 / 1.0 / hit 0.60 / excess≤0); `import_revalidation` writes evidence
ONLY (never `status`) and SKIPS factors whose current `definition_hash` ≠ the registry row (tested);
imported rows carry `evidence_class=historical_investigation` + `formal_evidence_eligible=false`; a
boundary-integrity test proves the resolver/writer behavior is unchanged after an import; HTML surfaces
the gross LO metric + signal-role; CLAUDE.md/AGENTS.md updated; full offline suite green. Then Phase 3
(`get_factors` + staged catalog→registry cutover) begins.

## Post-implementation GPT cross-review (PR #31) — integrated fixes
GPT reviewed the IMPLEMENTED P2.1–P2.4 (ran the suite + real-data import) and returned a NO-GO with 5
findings; all were verified against the code/real data and fixed on `factor-lifecycle-p2` (boundary
re-confirmed: import attaches 171, all stay `draft`; status/approval_validity/definition_hash untouched;
promotion gate never reads `factor_evidence`). The fixes harden `refresh_master_derived_fields`:
1. **Provenance + role mirrors (finding 1).** Refresh now mirrors `latest_provider_build_id` /
   `latest_calendar_policy_id` / `last_revalidated_at` from the latest bound `run_type=='revalidation'`
   evidence ONLY (re-review fix: a plain `sync_catalog`, which writes a `catalog_sync` evidence row with
   a blank `source_hash`, must NOT stamp `last_revalidated_at`), and sets
   `signal_role_suggested='long_only_alpha'` for a `viable` factor (spec §P2.1) — NEVER touching the
   authoritative `signal_role`.
2. **No cross-row metric mixing (finding 2).** Viability is derived from the SINGLE latest evidence row
   that carries an LO Sharpe, using THAT row's full `(sharpe, excess, hit)` tuple. A partial latest tuple
   → `non_viable` (no resurrection of an older row's excess/hit). Replaces the per-metric
   `_latest_non_null` that could combine a new Sharpe with stale excess/hit.
3. **Definition-bound mirrors (finding 3).** Only evidence whose `source_hash` is blank
   (legacy/non-LO) OR equals the row's CURRENT `definition_hash` drives the P2 mirrors. Stale-definition
   evidence (nonblank `source_hash` ≠ current hash, e.g. a skip-drifted re-import) is ignored even though
   it physically remains in `factor_evidence`.
4. **`field_eligibility_snapshot_json` populated (finding 4).** Refresh snapshots each factor's
   referenced `$fields` against the LIVE field-status registry at the strict `formal_validation` stage:
   BASE factors → `{"resolved":true,"all_allowed":…,"fields":{…}}`; COMPOSITE / INDUSTRY_RELATIVE master
   expressions are pseudo-expressions with no `$field` tokens → `{"resolved":false,
   "reason":"transitive_deferred_…"}` (their transitive deps are resolved in Phase 3). **Fail-closed
   contract:** `resolved=false` AND the empty string ('not computed') MUST be treated by any consumer as
   NOT eligible — never `all_allowed`. Registry-load failure also yields `resolved=false` (never a false
   `all_allowed=true`).
5. **`retain_pct` deferred (finding 5).** Absent from every revalidation CSV and from
   `screening_oos_report.csv`, and the OOS-screened factors are not yet registry rows. The column stays
   schema-reserved/null and MUST NOT be read as populated until structured walk-forward retention inputs
   are wired (later phase). Documented in `_read_revalidation_csv` + here.

Regression tests (findings 1–4) added to `tests/alpha_research/test_factor_registry.py`; the finding-2 /
finding-3 tests were proven to FAIL on the pre-fix logic (independent-latest / no-bind both derive
`viable` where the fixed code derives `non_viable`). Full suite: 27 passed.

**GPT re-review (commit `75c2e45`) — 1 residual must-fix, then GO.** GPT confirmed findings 1–5 closed but
found that `last_revalidated_at` was set from ANY bound row, so a plain `sync_catalog(record_run=True)`
(which writes a `catalog_sync` evidence row, blank `source_hash` → passes the carve-out) stamped all 171
factors "revalidated" at the sync time. Fixed by scoping the P2 evidence-mirrors to `run_type=='revalidation'`
rows only; added `test_sync_catalog_alone_leaves_revalidation_mirrors_blank` (proven to fail pre-fix: 171
non-blank). Full suite after the re-review fix: **28 passed**; real-data probe: sync→0 non-blank,
import_revalidation→171 (provider mirror = pbX).
