# Factor-lifecycle Phase 5 — orchestrator `factor_lifecycle` profile (DESIGN, pre-build)

Status: **DESIGN v2 — conditional-GO review integrated; ready for confirm before build.** Round-1 design
review (deep orchestrator code-read) returned a conditional GO with 4 must-fixes — all integrated: (1) neither
existing resolver is reusable — a NEW `factor_lifecycle_object_resolver` with a draft-ACCEPTING allow-set that
still runs P1.3 + the field gate; (2) publish uses a DIRECT decision matrix (`approved`→candidate only), not
`_assert_gate_allows_publication` (whose `quarantined`→`under_review` has no factor-registry status); (3) add a
`factor_lifecycle` branch to the gate metrics + a floor table (else the gate is empty); (4) field-ineligible
factors are EXCLUDED from compute (never reach `load_is_windowed_panel`). The 6 open questions are resolved
below. Phases 1-4 are MERGED to `wave1-field-promotion`. Plan: §2.4/2.5 of
[factor_lifecycle_formalization_plan.md](factor_lifecycle_formalization_plan.md).

## Goal
Add a NEW orchestrator profile `factor_lifecycle` that runs the merged IS-only walk-forward validator
([run_is_walk_forward](src/alpha_research/factor_lifecycle/walk_forward_validation.py)) as the formal
**`draft → candidate`** factor gate: resolve prescribed factors → build the IS-only windowed panel →
`run_is_walk_forward` → human gate (the existing triplet) → publish the passing factors at registry status
**`candidate`** (never `approved`). It reuses the orchestrator's gate/ledger/registry machinery; it adds only
two handlers + one profile + a dag_builder.

## The single most important rule — this profile is **IS-ONLY** (the leakage boundary at the orchestrator level)
`hypothesis_validation` has IS **and** OOS legs because it spends the sealed OOS for a publish decision. The
`factor_lifecycle` `draft→candidate` gate is **IS-ONLY** (Phase 4: candidate evidence is an IS-internal
walk-forward bounded to `is_end`, *never* spends sealed OOS). Therefore the `factor_lifecycle` DAG MUST have
**no OOS backtest leg, no `oos_test` stage, and no holdout-seal claim**. The `candidate → approved` OOS spend
is a SEPARATE path (frozen-set sealed OOS + promotion gate — Phase 6 / `hypothesis_validation`), not this
profile. A profile that touched OOS here would re-open exactly the leak Phase 4 closed.

## Current state (grounded — Explore map, 2026-06-01)
- `ResearchProfile` ([profiles.py:14](src/research_orchestrator/profiles.py)) = `{profile_id, supported_modes,
  consumes_types, produces_types, default_capabilities, formal_requires_resolver, dag_builder}`; the 7
  built-ins register in `engine._register_builtin_profiles()`.
- A DAG is a list of `DagStepSpec{step_id, capability, handler, depends_on, config}` ([dag.py:20](src/research_orchestrator/dag.py));
  handlers are keyed in `HANDLER_REGISTRY` (steps.py) and receive a `StepExecutionContext`
  (`request, profile, step, run_dir, step_dir, registry_dirs, state, resumed`) → return a
  `StepExecutionResult(status, outputs, artifacts, summary, gate)`.
- **`hypothesis_validation`** ([engine.py:809](src/research_orchestrator/engine.py)) is the IS→gate→OOS→publish
  analog: `object_resolver` (P1.2 allow-set + P1.3 definition-binding) → `validation_dataset_build`
  (`stage=is_only`) → IS backtests → `gate_evaluation`/`gate_concern_scoring`/`gate_review` (the triplet;
  `gate_review` → `pause_for_gate` for the human decision) → OOS leg → `validation_registry_publish`.
- **`factor_screening`** ([engine.py:595](src/research_orchestrator/engine.py)) shows the discovery pattern +
  `_inject_gate_sequence()` (auto-inserts the gate triplet before publish) + `screening_registry_publish`
  (writes `candidate`/`observed` via `TypedRegistryStore.publish_objects`, never `approved`).
- `TestingLedgerStore.record_event` ([testing_ledger.py](src/alpha_research/testing_ledger.py)) is file-locked
  (P1.5) — the orchestrator already records gate measurements through it.
- The writer-side guard `_assert_gate_allows_publication()` ([steps.py](src/research_orchestrator/steps.py))
  blocks publish on `rejected` and forces `under_review` on `quarantined`. `approved` on the FACTOR registry
  is guarded by the P1.1 promotion gate (`set_status("approved")`); **`candidate` is non-privileged**.

## Proposed profile + DAG
```python
ResearchProfile(
    profile_id="factor_lifecycle",
    supported_modes=("formal",),            # the draft->candidate gate is a formal decision
    consumes_types=("factor", "composite_factor"),
    produces_types=("factor",),             # same factors, now at status candidate (or left draft)
    default_capabilities=(... dataset_build, walk_forward_validation, gate_*, registry_publish ...),
    formal_requires_resolver=True,          # auto-injects object_resolver (P1.2 + P1.3)
    dag_builder=_factor_lifecycle_dag_builder,
)
```
DAG (IS-only — note the ABSENCE of any `oos_test` step):
```
data_scope (noop) → data_readiness (noop)
  → factor_lifecycle_object_resolver [NEW] draft-accepting allow-set + P1.3 + field gate (see below)
  → factor_lifecycle_dataset_build   [NEW] IS-only windowed panel; EXCLUDES field-ineligible factors
  → factor_lifecycle_walk_forward    [NEW] run_is_walk_forward -> per-factor candidate/draft verdicts + ledger
  → gate_evaluation → gate_concern_scoring → gate_review   [reuse triplet + a factor_lifecycle metrics/floor branch]
  → factor_lifecycle_registry_publish [NEW] direct decision matrix: only `approved` -> set status=candidate
  → report_render              [reuse]
```

### `factor_lifecycle_object_resolver` (NEW — review must-fix #1)
**Neither existing resolver is reusable as-is:** the generic `object_resolver` ([steps.py:414](src/research_orchestrator/steps.py)) raises on unresolved but runs NO P1.3 definition-binding / field gate; `validation_object_resolver`'s allow-set is `{formal}` (+candidate) and **rejects `draft`** ([validation_steps.py:116](src/research_orchestrator/validation_steps.py)) — fatal for a draft→candidate gate. The NEW handler:
- accepts `source_layer ∈ {factor_registry_draft, factor_registry_candidate, formal}` (the input to a
  draft→candidate gate IS draft); REJECTS `factor_registry_stale`, `factor_registry_deprecated`, plain
  candidate-registry `candidate`, and `new_candidate`;
- REUSES the P1.3 `_assert_no_definition_drift` helper (definition_hash == current code hash, fail-closed) and
  the field gate at `formal_validation` (per-factor `$field` eligibility) — these HELPERS are reused, only the
  allow-set differs;
- records `field_eligible` per factor for the dataset_build to consume.

### `factor_lifecycle_dataset_build` (NEW)
Builds the **IS-only** windowed panel via Phase-4 `build_is_windowed_panel` / `load_is_windowed_panel`
(factors `horizons=None` over `[is_start, is_end]`; label at the exact trading-calendar `r(t)`; both inputs
asserted `≤ is_end`). It must NEVER request data past `is_end` (no `oos_test` schedule — unlike
`validation_dataset_build`).
**Field-ineligible factors are NOT computed (review must-fix #4):** the resolver's per-factor `field_eligible`
flags partition the batch — only field-eligible factor expressions are passed to `load_is_windowed_panel`. A
field-ineligible factor is marked `draft` (no compute, recorded with a reason) and the batch continues with
the eligible subset; a configurable `strict` flag instead hard-fails the whole batch. A disallowed `$field`
must never reach the compute path.

### `factor_lifecycle_walk_forward` (NEW)
Calls `run_is_walk_forward(panel=<IsWindowedPanel>, time_split=<is_split>, factor_origin=<from prescription>,
field_eligible=<from object_resolver's field report>)`. The result's per-factor rows carry
`status ∈ {candidate, draft}` (from `assign_candidate_status`, IS-only — no `oos_*`). Records to the ledger:
one `record_event(test_name=f"factor_lifecycle:{factor}", statistic_name="heldout_rank_icir", stage="is_only",
n_obs=n_heldout_blocks, ...)` per factor + a `factor_lifecycle:batch_effective_trials` row (the batch the
selection rule saw — direction flips, clustering, count). Output: the `WalkForwardResult` + per-factor verdicts.

### `factor_lifecycle_registry_publish` (NEW — review must-fix #2: direct decision matrix)
Do NOT reuse `_assert_gate_allows_publication` unchanged: it lets `quarantined` proceed with
`publish_status_override="under_review"` ([steps.py:323](src/research_orchestrator/steps.py)), but the factor
registry has NO `under_review` status (only `draft/candidate/approved/deprecated`,
[store.py:33](src/alpha_research/factor_registry/store.py)). This handler uses a DIRECT matrix:
- human decision `approved` → for each factor with verdict `candidate`: (a) write a FORMAL lifecycle EVIDENCE
  row FIRST via a dedicated factor-registry evidence path (NOT `import_revalidation`, which is historical):
  `run_type="factor_lifecycle"`, `formal_evidence_eligible=True`, `evidence_class` from Phase 4
  (`generated_heldout` / `a_priori`), `source_hash` bound to the CURRENT `definition_hash`, IS-only metrics
  (heldout ICIR, sign-consistency, n_heldout_blocks) populated, NO `oos_*`. **Idempotent by
  `(run_id, factor_id, version)` (GPT slice-1 risk)** so a retry after a status-write failure does not
  duplicate evidence rows. (b) then `FactorRegistryStore.set_status(factor, "candidate", reason=…,
  source_run_id=…)` — the **non-privileged** candidate transition (NO `current_git_sha` required; that is only
  the privileged `approved` gate, [store.py:1088](src/alpha_research/factor_registry/store.py)). Produced
  objects are recorded with lifecycle status `candidate` (NOT typed-registry `approved` artifacts — GPT
  lineage confirmation for `produces=("factor",)`);
- `rejected` / `quarantined` / missing / unknown decision → write NO candidate statuses (no-op + recorded).
- factors with verdict `draft` are left unchanged.
**NEVER writes `approved`** — that stays behind the P1.1 promotion gate (independent PIT-correct reproduction +
clean tree + git sha), reached only via the separate sealed-OOS/promotion path. `approved` is impossible from
this handler by construction.

### Gate metrics + floor (NEW — review must-fix #3; GPT slice-1 risk)
The shared `gate_evaluation`/`gate_concern_scoring` read `_collect_measured_values`, which returns `{}` for an
unknown profile ([steps.py:264](src/research_orchestrator/steps.py)) — so the gate would have an empty rule
table. Add a `factor_lifecycle` branch that surfaces, from the walk-forward step: `candidate_count`,
`tested_count`, `field_ineligible_count`, `skipped_count`, `max/median heldout_rank_icir`, a sign-consistency
summary, and `effective_trials`. **GPT slice-1 risk — `_collect_measured_values` alone is NOT enough:** the
gate evaluator only auto-evaluates the standard `SuccessCriteria` metrics, so the produced `criteria_results`
must be NON-EMPTY and auto-evaluable for lifecycle runs. Either (a) map the lifecycle heldout ICIR cleanly
into the existing `rank_icir` criterion so the standard rule fires, OR (b) extend the criteria-evaluation path
with explicit `factor_lifecycle` floor rails. Verify the eval step emits a non-empty `criteria_results` (else
concern scoring has nothing to score).

## What is REUSED unchanged vs NEW (the formal gates stay intact)
**Reused unchanged (do NOT modify):** the P1.3 `_assert_no_definition_drift` HELPER, the field gate at
`formal_validation`, the gate-triplet *mechanics* + `pause_for_gate`, the **P1.1 promotion gate** on
`set_status("approved")`, and the `TestingLedgerStore` lock semantics. **NEW (must NOT subvert the above):**
`factor_lifecycle_object_resolver` (a draft-ACCEPTING allow-set wrapping the SAME P1.3 + field helpers — it
does not weaken P1.3 or the field gate, only widens the lifecycle-status allow-set to include `draft`); the
direct publish decision matrix (replaces `_assert_gate_allows_publication` because `under_review` has no
factor-registry status); and the `factor_lifecycle` gate-metrics/floor branch. The privileged `approved`
writer gate is untouched and unreachable from this profile.

## Risks + tests
- **OOS leak via the profile (the orchestrator-level mirror of the Phase-4 guard)** → (structural, slice 1)
  `test_factor_lifecycle_profile_has_no_oos_stage`: the compiled DAG has NO step with `config["stage"]==
  "oos_test"`, NO `event_driven_backtest`/`vectorized_backtest` handler, NO `oos`-named step. **PLUS (runtime,
  once handlers exist — GPT slice-1 risk):** `test_factor_lifecycle_run_never_claims_seal` monkeypatches
  `HoldoutSealStore.claim_holdout_access` and proves a lifecycle run never calls it — catching a handler-level
  mistake the DAG-only test cannot see (`_claim_holdout_access_if_needed` only fires on `oos_test`,
  [steps.py:337](src/research_orchestrator/steps.py)).
- **Resolver allow-set (must-fix #1)** → `test_lifecycle_resolver_accepts_draft_rejects_stale`: accepts
  `factor_registry_draft`/`candidate`/`formal`; rejects `stale`/`deprecated`/candidate-registry/`new_candidate`;
  still runs `_assert_no_definition_drift` (drift → raise) + the field gate.
- **Field-ineligible not computed (must-fix #4)** → `test_field_ineligible_factor_excluded_from_compute`: a
  disallowed-`$field` factor never reaches `load_is_windowed_panel`; it is marked `draft`; the eligible subset
  still runs (or `strict` hard-fails the batch).
- **Publish decision matrix (must-fix #2)** → `test_publish_only_on_approved`: `approved` → passing factors set
  to `candidate`; `rejected`/`quarantined`/missing → NO status writes; `approved` is impossible from this
  handler; non-privileged `candidate` needs no `current_git_sha`.
- **Gate metrics (must-fix #3)** → `test_factor_lifecycle_gate_metrics_nonempty`: `_collect_measured_values`
  returns the candidate/tested/heldout-ICIR/effective-trials metrics for this profile (not `{}`), and the
  floor/criteria table is non-empty for concern scoring.
- **Ledger** → `test_walk_forward_records_per_factor_and_batch_trials` (one `record_event` per tested factor +
  one `batch_effective_trials` row).
- **Profile registration** → the profile validates + registers; `profiles` CLI lists it; floor-validation
  accepts `factor_lifecycle`.
- **`approved` writer gate intact** → reuse the P1.1 promotion-gate tests unchanged (this profile cannot reach
  `approved`).

## Open questions — RESOLVED (design review, conditional GO)
1. **IS-only boundary** → YES: no OOS leg, no `oos_test`, no event/vectorized OOS backtest, no holdout claim.
   Add the no-`oos_test` / no-OOS-handler / no-`claim_holdout_access` tests. ✓
2. **Publish mechanism** → `FactorRegistryStore.set_status(…, "candidate")`, NOT `publish_objects`. The
   lifecycle status lives in the factor registry. `current_git_sha` NOT required for `candidate` (only
   privileged `approved`). Write formal lifecycle evidence rows BEFORE the status change. ✓
3. **Input shape** → prescription-driven, but do NOT shoehorn into the strategy `PrescribedRecipe`
   (weights/topk/portfolio are irrelevant). Use an explicit factor-batch spec OR `request.consumes` + lifecycle
   metadata. ✓
4. **`factor_origin`** → explicit PER FACTOR, enum-validated `{generated, a_priori}`; missing → FAIL CLOSED;
   a batch default is acceptable only if explicitly supplied + recorded. ✓
5. **Gate granularity** → ONE human gate for the batch; per-factor ledger rows for every tested factor + one
   `batch_effective_trials` row capturing the whole pool the rule saw. ✓
6. **Scope** → profile + the lifecycle RESOLVER + dataset_build + walk_forward + publish handlers + the
   gate-metric plumbing + dag_builder + tests; NO actual run (Phase 6 runs it). The earlier "two handlers" was
   wrong — the safe implementation is ≥4 handlers + the gate-metrics branch. ✓

## Implementation cautions (review GO) + build order
- **`formal_requires_resolver=True` does NOT auto-inject a resolver** in the current engine — the explicit
  `factor_lifecycle_object_resolver` DAG step is the SOURCE OF TRUTH and must be in the dag_builder's step list.
- **The `validation_steps.py` field-gate helper is batch/raise-oriented.** For the "exclude ineligible +
  continue" mode, call it PER FACTOR (or per-factor partitions) and pass only eligible factors to compute;
  `strict` mode can still hard-fail the whole batch.
- **Build order (review-confirmed):** (1) profile + `_factor_lifecycle_dag_builder` + the no-OOS structural
  test; (2) lifecycle resolver + allow-set/drift/field tests; (3) dataset_build + field-ineligible test;
  (4) walk-forward + ledger test; (5) gate-metrics/floor branch + test; (6) registry publish + decision-matrix
  test.

## Acceptance
The `factor_lifecycle` profile + `_factor_lifecycle_dag_builder` + the FOUR new handlers
(`factor_lifecycle_object_resolver` draft-accepting + P1.3 + field gate; `factor_lifecycle_dataset_build`
IS-only + field-ineligible exclusion; `factor_lifecycle_walk_forward` + ledger; `factor_lifecycle_registry_publish`
direct-decision-matrix candidate-only) + the `factor_lifecycle` gate-metrics/floor branch registered; the
no-OOS-stage (incl. no `claim_holdout_access`) + resolver-allow-set + field-ineligible + decision-matrix +
gate-metrics + ledger tests green; the P1.1/P1.3 formal gates untouched; CLAUDE.md §3 + AGENTS.md §2a + §9
(profile list: 7→8) updated (same pass, §11.2); full offline suite green. Then Phase 6 (gated 171-status +
6-OOS-candidate backfill) runs the profile.
