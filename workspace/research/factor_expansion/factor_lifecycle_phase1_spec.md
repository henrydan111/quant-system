# Factor Lifecycle — Phase 1 Implementation Spec

**Date:** 2026-05-31. **Status:** spec reviewed — Codex round-4 (pre-build) + round-5 (P1.2 redesign)
integrated; GO to draft on Option A. No code written yet. Derived from
`factor_lifecycle_formalization_plan.md` (v3 + Codex round-1/2/3, all GO). Phase 1 = the
**safety-first enforcement layer**: close the reader+writer formal gates, bind definitions, seal OOS
by frozen-set identity, and file-lock the trial ledger — all on/with the minimal schema additions
Codex flagged. **No factor is registered/promoted by Phase 1 itself.**

**Codex round-5 redesign of P1.2 (verified, GO):** the round-2/round-4 `draft→_unresolved` reader
design is a PROVEN regression — the shared `_resolve_formal_factor` feeds 3 discovery DAGs whose
`object_resolver` step hard-raises on unresolved (`steps.py:444`), and all 171 registry rows are
`draft`, so draft→`None` would hard-fail discovery + break a unit test. P1.2 is redesigned to
**"resolve-but-label"**: the resolver resolves every row and labels `source_layer` by status; the
formal gate lives ONLY in the validation consumer's allow-set. Safety trace confirmed — discovery
publish writes `candidate`/`observed` (`typed_store.py:452`), never `approved`, so labeling draft as
resolved cannot make it formal-usable. Details in P1.2 below.

**Codex round-4 corrections (all verified against code, all integrated below):**
- P1.1: `factor_registry_cli.py set-status --status approved` is a writer-gate bypass — added to
  touch list; `export_current(status="approved")` must fail-closed to `approval_validity=="valid"`.
- P1.2: ship P1.1+P1.2 in ONE PR (resolver + `validation_steps` in the same commit); add
  `factor_registry_candidate` to the resolver summary accounting (else candidate hits vanish from
  run summaries); the `formal_only` toggle becomes a 3-state allow-set (it currently accepts ANY
  non-formal layer when `allow_candidate_components=True` — P1.2 TIGHTENS that).
- P1.3: definition_hash comparison uses the registry snapshot's hash algorithm, incl. composites
  + industry-relative defs resolved through the same catalog-snapshot rules that wrote it.
- P1.4: touch list was incomplete — add `research_access_context.py` (carry `seal_key`) and
  `hypothesis_cli.py verify-seal` (queries `design_hash` only ⇒ false-negative OOS diagnostic).
- P1.5: do NOT lock both public methods (`record_verdict` calls `record_event` ⇒ self-deadlock on
  the non-reentrant `file_lock`); use one lock scope + an unlocked internal append helper.

## Scope (5 work-items, dependency-ordered)
| # | Item | Files (primary) | Gate it closes |
|---|---|---|---|
| **P1.1** | Writer gate on `set_status("approved")` + minimal `approval_validity` column | `src/alpha_research/factor_registry/store.py`, `workspace/scripts/factor_registry_cli.py` | R1 (ungated writer + CLI bypass) + §2.3 fail-closed-on-missing-validity |
| **P1.2** | Reader gate "resolve-but-label" (status/validity-labeled `source_layer`) + validation allow-set + accounting + `definition_hash` enforcement | `src/research_orchestrator/resolver.py`, `validation_steps.py`, `steps.py` | H1 (formal-resolver status bypass) |
| **P1.3** | Definition-binding hard-fail | `src/research_orchestrator/validation_steps.py` | H2 (definition drift) |
| **P1.4** | `FrozenSelectionSet` + `seal_key` migration (5-step order) | `holdout_seal.py`, `steps.py`, `sealed_backtest_runner.py`, `event_driven/__init__.py`, `vectorized/__init__.py`, `research_access_context.py`, `workspace/scripts/hypothesis_cli.py`, new `frozen_selection_set.py` | H3 (mutable design_hash re-opens OOS) |
| **P1.5** | File-lock `TestingLedgerStore` (one lock scope + unlocked append helper) | `src/alpha_research/testing_ledger.py` | H5 (unlocked OOS-budget ledger) |

Build order (Codex round-4): **P1.1 + P1.2 in ONE PR** (writer + reader formal gate land together —
`approval_validity` column and the reader that consumes it are one logical unit; resolver +
`validation_steps` tightening in the same commit) **→ P1.3 → P1.5 → P1.4** (seal migration last, its
own PR, in the 5-step internal order). P1.4 is safe as its own PR ONLY because the back-compat
`_load()` fill makes the old rule `seal_key = design_hash` hold until step 5; no caller passes a
non-`design_hash` `seal_key` until every reader/backstop/CLI/context site is merged.

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
- **`export_current` fail-closed (Codex round-4):** `export_current(status="approved")` currently
  filters on exact `status` only (`store.py:798`), so a stale-`approved` row would export as
  deployable. Default behavior: when `status=="approved"`, also require `approval_validity=="valid"`.
  Add an explicit `include_invalid: bool = False` arg for audit/review exports that need stale rows;
  the default deployable export is valid-only.
- **CLI writer-gate parity (Codex round-4) — `factor_registry_cli.py`:** the `set-status` subcommand
  (`factor_registry_cli.py:102-109`) calls `store.set_status(... status=args.status ...)` with
  `--status approved` allowed and NO evidence/git_sha — a direct bypass of the new writer gate.
  Fix: `set-status --status approved` requires `--promotion-evidence-json <path>` (parsed into the
  `promotion_evidence` dict) and the CLI auto-resolves `current_git_sha` via `git rev-parse HEAD`
  (refusing on a dirty tree, mirroring the gate's clean-tree requirement); absent the evidence file
  it exits 2 with a message pointing to the promotion path. `draft`/`candidate`/`deprecated` remain
  unrestricted. The CLI must NOT become an unaudited approval door.
- **Tests:** `set_status("approved")` without evidence raises; with passing evidence + git_sha succeeds;
  enum still validated; missing `approval_validity` on an approved row ⇒ treated non-valid;
  `export_current(status="approved")` excludes a stale-approved row by default and includes it under
  `include_invalid=True`; CLI `set-status --status approved` without `--promotion-evidence-json`
  exits 2 and cannot bypass the gate.

## P1.2 — Reader gate, Option A "resolve-but-label" (`resolver.py`, `validation_steps.py`) — SAME PR as P1.1

**Codex round-5 redesign — SUPERSEDES the round-2 `draft→_unresolved` call (proven regression).** The
shared `_resolve_formal_factor` is consumed by 3 discovery DAGs that include the `object_resolver` step
(`event_driven_signal_research`, `ml_signal_model_research`, `strategy_improvement`; `factor_screening`
+ `theme_strategy` set `formal_requires_resolver=True` but their DAG builders do NOT add the step today)
via `handle_object_resolver`, which HARD-RAISES on any unresolved consume (`steps.py:438-446`). Returning
`None` for draft would hard-fail those 3 discovery runs (all 171 registry rows are `draft`) AND break
`tests/alpha_research/test_research_orchestrator.py:1093`. So the resolver RESOLVES every current row and
labels privilege separately; the formal gate moves entirely to the validation consumer.

- `resolver._resolve_formal_factor` (`resolver.py:124`): keep top-level `status="resolved"` for every
  current row; stamp `source_layer` by registry status + validity:

  | registry status | approval_validity | source_layer |
  |---|---|---|
  | approved | valid | `formal` |
  | candidate | valid | `factor_registry_candidate` |
  | draft | (any) | `factor_registry_draft` |
  | approved | non-valid | `factor_registry_stale` |
  | deprecated | (any) | `factor_registry_deprecated` |

  Resolve-and-label deprecated/stale (NOT `None`) — returning `None` recreates the discovery hard-fail
  for intentional audits of old factors; the validation allow-set rejects them anyway.
- **Explicit metadata (round-5):** add `registry_status` + `approval_validity` to `ResolutionEntry`
  and its `to_dict()`, so reviewers read privilege from explicit fields, not by parsing `source_layer`.
- **Enforce requested `definition_hash` (round-5):** today `resolver.py:137` uses `definition_hash`
  only as a fallback when name/id matching is empty, so a same-name factor-registry row can shadow a
  different-hash request. When `asset.definition_hash` is supplied it MUST be an AND filter on the
  match (name match + mismatched hash → no match), closing the shadowing path. Add P1.2 tests.
- **Summary accounting (round-4 + round-5):** `formal_hits` counts ONLY `source_layer=="formal"`;
  `candidate_hits` includes `factor_registry_candidate` + the existing `{candidate, signal, model,
  strategy}`; ADD a `factor_registry_hits_by_layer` dict counting `{formal, factor_registry_candidate,
  factor_registry_draft, factor_registry_stale, factor_registry_deprecated}` so no non-formal resolved
  row vanishes from summaries. Surface the new counts in `handle_object_resolver`'s summary
  (`steps.py:449`).
- `validation_steps` formal-gate (`validation_steps.py:100-117`) — explicit allow-set, the SOLE formal
  permission point (verified: discovery publish writes `candidate`/`observed` via `typed_store.py:452`,
  NEVER `approved`; `prescription_runtime.py:103` proves permission before factor-frame compute).
  `allowed = {"formal"}`; add `"factor_registry_candidate"` IFF `prescription.allow_candidate_components`.
  Reject `unresolved` and EVERY other layer — `factor_registry_draft`, `factor_registry_stale`,
  `factor_registry_deprecated`, AND plain `candidate` (candidate-registry path). Net tightening; no
  current prescription sets `allow_candidate_components=True`. Resolver + this land in ONE commit.
- **Candidate-registry fallback:** keep factor-registry priority (Option A preserves current ordering;
  no new shadowing once `definition_hash` is enforced). No automatic "draft yields to candidate
  registry" rule — if explicit registry preference is ever needed, add it to `AssetRef`, don't infer it
  from status.
- **Tests:** approved+valid → `formal`; approved+non-valid → `factor_registry_stale`, validation
  rejects; candidate → `factor_registry_candidate`, accepted only under `allow_candidate_components`;
  draft → `factor_registry_draft`, validation rejects, AND a discovery test proves draft does NOT trip
  the `object_resolver` unresolved hard-fail; deprecated → `factor_registry_deprecated`, resolves +
  validation rejects; a supplied mismatched `definition_hash` does NOT match a same-name row; plain
  candidate-registry `candidate` is NOT accepted as a formal component even under
  `allow_candidate_components`; UPDATE `test_research_orchestrator.py:1093` to expect `formal_hits==0`,
  `source_layer=="factor_registry_draft"`, `factor_registry_hits_by_layer["factor_registry_draft"]==1`.

## P1.3 — Definition-binding hard-fail (`validation_steps.py`)
- Where components are resolved to expressions via `get_factor_catalog()`/`get_industry_relative_defs()`
  (~lines 218-227, 463-469): after resolving, compute the current code definition_hash for each name and
  compare to the registry row's `definition_hash`. On mismatch raise `FactorDefinitionDriftError` BEFORE
  any IS/OOS compute. (Compute-from-registry-expression deferred — composites/industry-rel resolve
  through code and need graph serialization.)
- **Hash-algorithm parity (Codex round-4):** the "current code definition_hash" MUST be computed with
  the SAME algorithm/snapshot rules the registry used when it wrote the row's `definition_hash` (the
  `sync_catalog`/`import_*` path in `store.py`). This includes composites and industry-relative defs:
  resolve each through the same catalog-snapshot the registry hashes, not an ad-hoc re-serialization,
  or a base/composite will mismatch spuriously. Compare-before-compute is the invariant; the hash
  must be apples-to-apples or the gate either false-fires or false-passes.
- **Tests:** registry hash == code hash → passes; injected mismatch → raises before dataset build;
  a composite and an industry-relative factor each round-trip (registry hash == recomputed hash)
  under the shared algorithm.

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
3. Add `seal_key` to `HoldoutContext` (fallback `design_hash`) AND to `ResearchAccessContext`
   (`research_access_context.py:90` — carry `seal_key`, fallback `design_hash`; thread through
   `from_split`). **(Codex round-4)** Without this, the OOS access context reports `design_hash`
   while the seal is claimed under `frozen_set_hash` — an inconsistent identity at the read path.
4. Update the check/diagnostic sites to pass/read `seal_key`:
   - 4 backstop check sites: `steps.py`, `sealed_backtest_runner.py`, `event_driven/__init__.py`,
     `vectorized/__init__.py`.
   - `hypothesis_cli.py verify-seal` (`hypothesis_cli.py:357-379`) **(Codex round-4)**: today it
     queries `store.list_events(design_hash=...)` only. Once seals are keyed by `frozen_set_hash`,
     a `verify-seal --design-hash <h>` finds zero OOS events and reports "untouched" (exit 0) even
     when the OOS WAS consumed — a dangerous false-negative on the OOS-budget diagnostic. Add a
     `--seal-key` argument (query by `seal_key`); keep `--design-hash` for back-compat (resolves
     via the `_load()` backfill where `seal_key == design_hash`). Preserve the exit-code contract
     (`0=untouched`, `1=touched`, `2=malformed hash`).
5. ONLY then have lifecycle code pass `FrozenSelectionSet.frozen_set_hash` as `seal_key`.
- **Tests (reuse `test_lock_concurrency` pattern):** two `frozen_set_hash`-keyed claims of the same set →
  1 pass/1 raise; editing `success_criteria`/`expected_effect` does NOT change `frozen_set_hash` (so a
  consumed OOS stays sealed); changing `expected_direction`/`selection_rule_hash`/`candidate_pool_hash`/
  `eval_protocol_hash`/`portfolio_side`/`universe`/`time_split_window` DOES change it; old
  `design_hash`-only seal rows still resolve via the `_load()` backfill (`seal_key == design_hash`);
  `verify-seal` works for both an old `design_hash` and a new `seal_key`.

## P1.5 — File-lock `TestingLedgerStore` (`testing_ledger.py`)
- **Non-reentrant-lock hazard (Codex round-4, verified):** `file_lock` (`file_lock.py`) is NOT
  reentrant — it opens a fresh handle + `LOCK_EX|LOCK_NB` per call. `record_verdict` (`:216`) calls
  `get_event` → `get_verdict_for_measurement` → **`self.record_event` (`:231`)**. Naively wrapping
  BOTH public methods in `with file_lock(...)` makes `record_verdict` hold the lock and then
  `record_event` block on the same lock file → `LockTimeoutError`. Correct pattern:
  - Extract `_append_event_unlocked(row, shard_path)` = the load-shard → `_append_row` → atomic-write
    body (currently `record_event:211-213`). NO lock.
  - `record_event`: `with file_lock(<ledger>.lock): _append_event_unlocked(...)` (lock the full
    load→append→write).
  - `record_verdict`: ONE `with file_lock(<ledger>.lock):` scope covering `get_event` +
    `get_verdict_for_measurement` (the prior-verdict/supersedes lookup) + `_append_event_unlocked`
    as a SINGLE critical section — it must NOT call the public `record_event`. The read helpers
    (`list_events`) inside the scope do not re-lock (plain reads). This both prevents the deadlock
    AND closes the read-check-write race so a concurrent verdict can't slip between the
    supersedes-lookup and the append. Lock file `<ledger_root>/testing_ledger.lock`.
- **Tests (mirror `test_lock_concurrency`):** N concurrent `record_event` of distinct rows → N persisted
  (no lost update); concurrent `record_verdict` calls do NOT deadlock and do NOT lose rows; a
  `record_verdict` completes (proves no self-deadlock against its inner append).

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
- **No feature flag / staged rollout (Codex round-4):** the only behavior changes on existing runs are
  intentional fail-closed effects on FORMAL paths (a draft factor stops resolving as formal; a
  definition-drift raises; an ungated `approved` write is refused). No discovery/sandbox path and no
  currently-passing formal run regresses (no prescription sets `allow_candidate_components=True`; all
  171 factors are `draft` today so none was relying on an `approved`-reader path). Ship the fail-closed
  behavior directly.
- Risk: P1.4 touches 6 sites (4 backstops + `research_access_context` + `verify-seal`) + a schema; ship
  as its own PR behind the 5-step order with the back-compat `_load()` fill so no in-flight seal/cache is
  orphaned and `seal_key == design_hash` holds until step 5.
- Risk: P1.2 source-layer change could affect the candidate-*registry* path — the distinct
  `factor_registry_candidate` name + a regression test on `_resolve_candidate_factor` + the resolver
  summary-accounting fix mitigate.

## Acceptance
All five gates testable + fail-closed; full offline test set green; CLAUDE.md/AGENTS.md updated;
no `approved` row creatable without the promotion gate (incl. via `factor_registry_cli.py`); a stale
`approved` row not exported as deployable; a consumed sealed-OOS cannot be re-opened by editing
thresholds/prose and `verify-seal` reports its true OOS state under both key forms; `record_verdict`
does not self-deadlock. Then Phase 2 (schema/evidence) begins.

## Codex round-4 verdict (recorded)
GO to draft implementation after the P1.4 + P1.5 spec corrections above (all integrated). Per-item:
P1.1 Go (with CLI + export_current amendments) · P1.2 Go (atomic with P1.1 + accounting fix) ·
P1.3 Go (hash-parity clarification) · P1.5 Go (after the one-lock-scope clarification) ·
P1.4 Go (after the touch-list expansion to `research_access_context` + `verify-seal`).
