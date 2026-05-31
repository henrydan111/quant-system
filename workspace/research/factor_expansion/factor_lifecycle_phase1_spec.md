# Factor Lifecycle — Phase 1 Implementation Spec

**Date:** 2026-05-31. **Status:** spec for review — no code written yet. Derived from
`factor_lifecycle_formalization_plan.md` (v3 + Codex round-1/2/3, all GO). Phase 1 = the
**safety-first enforcement layer**: close the reader+writer formal gates, bind definitions,
seal OOS by frozen-set identity, and file-lock the trial ledger — all on/with the minimal schema
additions Codex flagged. **No factor is registered/promoted by Phase 1 itself.**

## Scope (5 work-items, dependency-ordered)
| # | Item | Files (primary) | Gate it closes |
|---|---|---|---|
| **P1.1** | Writer gate on `set_status("approved")` + minimal `approval_validity` column | `src/alpha_research/factor_registry/store.py` | R1 (ungated writer) + §2.3 fail-closed-on-missing-validity |
| **P1.2** | Reader gate in formal resolver (status + validity aware) | `src/research_orchestrator/resolver.py`, `validation_steps.py` | H1 (formal-resolver status bypass) |
| **P1.3** | Definition-binding hard-fail | `src/research_orchestrator/validation_steps.py` | H2 (definition drift) |
| **P1.4** | `FrozenSelectionSet` + `seal_key` migration (5-step order) | `holdout_seal.py`, `steps.py`, `sealed_backtest_runner.py`, `event_driven/__init__.py`, `vectorized/__init__.py`, new `frozen_selection_set.py` | H3 (mutable design_hash re-opens OOS) |
| **P1.5** | File-lock `TestingLedgerStore` | `src/alpha_research/testing_ledger.py` | H5 (unlocked OOS-budget ledger) |

Build order: **P1.1 → P1.2** (writer before/with reader so reader can't trust ungated rows) → P1.3 →
P1.5 → P1.4 (seal migration last, in its own 5-step internal order). P1.4 may ship as a follow-on PR.

---

## P1.1 — Writer gate + `approval_validity` (`factor_registry/store.py`)
- Add column `approval_validity` to `MASTER_COLUMNS`/schema, default `"valid"`; schema-normalize old
  rows on `_load()` to `"valid"` ONLY for non-approved rows, and to `"requires_revalidation"` for any
  pre-existing `approved` row (there are none today — all 171 are `draft` — but fail-closed regardless).
- In `set_status`: when `status=="approved"`, require kwargs `promotion_evidence: dict` +
  `current_git_sha: str`; call `assert_promotion_artifact_eligible(promotion_evidence, current_git_sha=...)`
  (from `release_gate.py:632`) and raise `PromotionGateError` on failure — mirroring
  `StrategyRegistryStore.set_status` (`registries/strategy_registry.py`). Non-approved transitions
  unchanged. Setting `approved` also requires `approval_validity=="valid"`.
- Add `set_approval_validity(factor_id, validity, reason)` (writes `status_history`) for the
  drift→`stale` path (used later by provider-rebuild detection; not wired in Phase 1).
- **Tests:** `set_status("approved")` without evidence raises; with passing evidence + git_sha succeeds;
  enum still validated; missing `approval_validity` on an approved row ⇒ treated non-valid.

## P1.2 — Reader gate (`resolver.py`, `validation_steps.py`)
- `resolver._resolve_formal_factor`: stamp `source_layer="formal"` ONLY when
  `status=="approved" AND approval_validity=="valid"`. For `candidate` (+ `approval_validity=="valid"`)
  return a NEW `source_layer="factor_registry_candidate"` (NOT plain `"candidate"` — that denotes the
  candidate-*registry* path in `_resolve_candidate_factor`). `draft`/`deprecated`/`stale` → `_unresolved`.
- `validation_steps` (`formal_only` block, ~line 100): accept `source_layer=="formal"` always; accept
  `"factor_registry_candidate"` ONLY when `prescription.allow_candidate_components`; reject any other
  non-formal layer. Never accept arbitrary layers.
- **Tests:** draft factor → unresolved → formal validation rejects; approved+valid → resolves formal;
  approved+stale → rejected; candidate resolves only under `allow_candidate_components`; the candidate
  *registry* path is unaffected (no source-layer-name collision).

## P1.3 — Definition-binding hard-fail (`validation_steps.py`)
- Where components are resolved to expressions via `get_factor_catalog()`/`get_industry_relative_defs()`
  (~lines 218-227, 463-469): after resolving, compute the current code definition_hash for each name and
  compare to the registry row's `definition_hash`. On mismatch raise `FactorDefinitionDriftError` BEFORE
  any IS/OOS compute. (Compute-from-registry-expression deferred — composites/industry-rel resolve
  through code and need graph serialization.)
- **Tests:** registry hash == code hash → passes; injected mismatch → raises before dataset build.

## P1.4 — `FrozenSelectionSet` + `seal_key` migration (new module + 5-step seal change)
New `src/research_orchestrator/frozen_selection_set.py`: a frozen dataclass with
`frozen_set_hash` = sha256 over the strict-serialized payload:
`{schema_version, selected:[(factor_id, version, definition_hash, expected_direction)…sorted],
candidate_pool_hash, selection_rule_hash, eval_protocol_hash, metric, portfolio_side, universe,
time_split_window, rebalance, neutralization}` — **excluding** all pass/fail wording; **excluding**
provider/calendar/build IDs (carried beside as provenance). Serialization: `sort_keys=True`, compact
separators, `allow_nan=False`, ISO dates, normalized enum strings, no raw floats (ints/enums/hashes/
decimal strings), no timestamps/run paths.
- `candidate_pool_hash` = hash over every factor visible to the selection rule (not just selected).
- `eval_protocol_hash` = hash over preprocessing/winsor/rank/horizon/label/quantile/cost-slippage/
  missing-data/tie-break/universe-filter rules.

**Seal migration (exact order — avoids orphaning live seals, no mixed read/write paths):**
1. Add `seal_key` to `HoldoutSealStore` schema; in `_load()` lazily fill missing `seal_key` from
   `design_hash`. Keep `design_hash` column for provenance.
2. `claim_holdout_access()` + `list_events()` accept `seal_key` (default `design_hash`).
3. Add `seal_key` to `HoldoutContext` (fallback `design_hash`).
4. Update the 4 check sites to pass/read `seal_key`: `steps.py`, `sealed_backtest_runner.py`,
   `event_driven/__init__.py`, `vectorized/__init__.py`.
5. ONLY then have lifecycle code pass `FrozenSelectionSet.frozen_set_hash` as `seal_key`.
- **Tests (reuse `test_lock_concurrency` pattern):** two `frozen_set_hash`-keyed claims of the same set →
  1 pass/1 raise; editing `success_criteria`/`expected_effect` does NOT change `frozen_set_hash` (so a
  consumed OOS stays sealed); changing `expected_direction`/`selection_rule_hash`/`candidate_pool_hash`
  DOES change it; old `design_hash`-only rows still resolve via the `_load()` backfill.

## P1.5 — File-lock `TestingLedgerStore` (`testing_ledger.py`)
- Wrap the read-append-write in `record_event`/`record_verdict` in `with file_lock(<ledger>.lock):`,
  mirroring `CacheManifestStore.record_cache_write` / `HoldoutSealStore.claim_holdout_access` (which
  the repo already file-locks per CLAUDE.md §3). Lock file `<ledger_root>/testing_ledger.lock`.
- **Tests (mirror `test_lock_concurrency`):** N concurrent `record_event` of distinct rows → N persisted
  (no lost update).

## Cross-cutting
- **CLAUDE.md/AGENTS.md §3:** add hard-invariant entries for the reader+writer formal gates, the
  `frozen_set_hash` seal, and the definition-binding — in the same PR (per the §11.2 alignment contract).
- **New errors:** `FactorDefinitionDriftError`; reuse `PromotionGateError`.
- **No registration in Phase 1.** Backfilling the 171 statuses / the 6 expansion candidates is Phase 6,
  and the 6 enter as `candidate` (never `approved` without a pre-unblinding independent PIT reproduction).
- **CI:** add the new tests to the offline `factor_lifecycle` set in `.github/workflows/ci.yml`.

## Risks / non-goals
- Non-goal: `get_factors()` API, schema beyond `approval_validity`, the orchestrator profile, backfill —
  all later phases.
- Risk: P1.4 touches 4 backstop sites + a schema; ship behind the 5-step order with the back-compat
  `_load()` fill so no in-flight seal/cache is orphaned. If risk is high, P1.4 is its own PR after P1.1-3,5.
- Risk: P1.2 source-layer change could affect the candidate-*registry* path — the distinct
  `factor_registry_candidate` name + a regression test on `_resolve_candidate_factor` mitigate.

## Acceptance
All five gates testable + fail-closed; full offline test set green; CLAUDE.md/AGENTS.md updated;
no `approved` row creatable without the promotion gate; a consumed sealed-OOS cannot be re-opened by
editing thresholds/prose. Then Phase 2 (schema/evidence) begins.
