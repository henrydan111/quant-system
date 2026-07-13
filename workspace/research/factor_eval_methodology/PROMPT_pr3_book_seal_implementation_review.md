# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 3)

R1 = REWORK (5B/3M/1m, all folded). R2 = REWORK (5B/3M — concurrent double-execution, plan↔frozen-set
unbinding, claim-unbound diagnostics, unledgered direct A5, forgeable a6 dict + CLI boolean; governed-
runner gap, blank-request resume, dangling diagnostic ids). **Every R2 finding is folded**; this round
asks you to verify closure and re-probe. Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-3 re-review of PR3: you returned REWORK twice with adversarial probes; verify each R2 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/alpha_research/factor_eval_skill/book_seal.py
- src/alpha_research/factor_eval_skill/book_seal_stores.py
- src/alpha_research/factor_eval_skill/stores.py
- src/alpha_research/factor_eval_skill/sealed_oos.py
- src/alpha_research/factor_eval_skill/orchestration.py
- src/research_orchestrator/promotion_evidence.py
- src/research_orchestrator/registries/strategy_registry.py
- src/research_orchestrator/research_access_context.py   (additive request_hash field)
- workspace/scripts/factor_eval_cli.py                    (boolean switch removed)
- tests/alpha_research/test_pr3_book_seal.py              (43 tests — your R1+R2 probes pinned)
- tests/research_orchestrator/test_r4_wall_hardening.py   (D3.5 test: A5 authorization + ledger_root)

YOUR R2 BLOCKERS — how each was closed (verify in code; your probes are pinned as named tests):
B1 (concurrent resume double-executes) → BookSealArtifactStore.run_or_load_verdict: the read-state →
   evaluate → persist sequence runs under a PER-KEY file lock (book_seal_stores.py _key_lock_path); a
   concurrent same-key resume blocks, then takes the persisted branch — the evaluator can never run
   twice for one request; the lock is NOT released before the backtest (your exact replacement). The
   runner's inline state-read/backtest/persist block is REPLACED by this one call. Per-key locking means
   a long backtest never blocks other books; persist_verdict's store-wide lock nests inside with
   consistent ordering. Pinned: TestRunOrLoadVerdictAtomicity::test_one_execution_guarantee (+ the
   existing never-rerun/diagnostics-only-resume matrix).
B2 (identity not bound to the observed set) → run_book_sealed_evaluation now REQUIRES a real
   FrozenSelectionSet, frozen_set.frozen_set_hash == plan.frozen_set_hash, and factor_exprs covering the
   selected members EXACTLY (your probe: plan="PLAN_FROZEN_SET" + foreign set → refused before identity).
   The canonical component manifest {factor_id: version/definition_hash/side/expr} is SEALED INTO the
   claimed state row (open_claim component_manifest_json + book_plan_hash columns). Pinned:
   test_plan_frozen_set_binding_enforced.
B3 (diagnostics borrowable by foreign contexts) → run_component_diagnostics_in_book_context no longer
   accepts frozen_set/factor_exprs AT ALL — it loads the SEALED manifest from the canonical claim
   (load_component_manifest, request-bound) and verifies: active context seal_key + request_hash + stage
   + window; canonical claim run_dir/step_id/provider/calendar/oos_window == context; the REAL seal
   event's event_id == the claim's recorded seal_event_id AND event request_hash/run/step match.
   ResearchAccessContext gained an additive request_hash field the runner sets. Pinned:
   test_borrowed_seal_with_wrong_step_or_request_refused / test_diagnostics_observe_only_the_sealed_manifest
   / test_fabricated_context_without_real_seal_event_refused / test_pre_r2_claim_without_manifest_refused.
B4 (direct A5 consumes+claims but never ledgers) → reproduce_sealed_oos now takes ledger_root and, on a
   virgin claim, calls the ATOMIC OosWindowLedgerStore.reserve_a5_study_spend BEFORE the holdout claim;
   ledger_root missing → PromotionEvidenceError BEFORE any claim (an unledgered virgin observation is
   impossible). cmd_seal passes its store_root down and its after-the-fact record_study_spend is REMOVED
   (burned windows keep the legacy post-claim record). Pinned:
   test_reproduce_sealed_oos_virgin_authorizes_ledgers_then_claims (your probe extended: authorization
   consumed AND holdout event AND ledger.distinct_spend_keys(window) non-empty) +
   test_cmd_seal_live_virgin_requires_override_and_ledgers_via_reproduce (the mock performs the REAL
   reservation with the ledger_root cmd_seal passes — wiring pinned).
B5 (forgeable a6 dict + CLI boolean) → reserve_book_spend's override_authorization parameter is REMOVED;
   it takes override_store + multiplicity_override_id and calls OverrideAuthorizationStore.require_consumed
   INSIDE the ledger lock — the consumed record is RE-READ FROM THE STORE, matched on kind/id/window/
   scope AND consumed_by_request_hash == the reserving request. cmd_seal's multiplicity_override:bool is
   REMOVED (multiplicity_override_id, consumed at the global holdout root before enforcement); the CLI
   flag --multiplicity-override is replaced by --multiplicity-override-id / --fresh-window-override-id.
   Pinned: test_hard_threshold_verified_from_the_store_never_caller_input (invented id refused;
   wrong-request consumption refused; correctly-bound consumption admits) +
   test_cmd_seal_multiplicity_override_must_be_prerecorded (signature pin).
M1 (gate accepts seeded live artifacts) → the gate's FINAL check (after every binding, so tamper tests
   still exercise their layers) requires a governed_execution attestation whose runner_id is in
   REGISTERED_GOVERNED_RUNNERS — a frozenset that is EMPTY until the S6 runner PR registers its id. ALL
   live artifacts fail closed today, exactly as you prescribed; the attestation contract (profile id/hash,
   allowed_for_formal, return_type=total_return, max_gross_exposure<=1.0, result_hash recomputed from the
   persisted metrics) is already validated so the S6 PR only registers. Pinned:
   test_fully_consistent_live_artifact_fails_closed_at_governed_runner (every binding passes; the final
   check refuses) — the promotion pass-path is now UNREACHABLE by construction until S6.
M2 (blank-request legacy reservation resumes anything) → strict equality in reserve_book_spend; a blank
   recorded hash is quarantined (both your probe requests refuse). Pinned:
   test_blank_request_legacy_reservation_is_quarantined.
M3 (dangling diagnostic ids promote) → the gate loads the durable StrategyComponentDiagnosticStore
   (same root as the artifact store), verifies EVERY diagnostic_record_id exists, belongs to this
   book_seal_key + request_hash, and that the durable component set equals the artifact's. Pinned:
   test_dangling_diagnostic_record_ids_refused.

TEST STATE: 539 passed across the full affected suite. NOTE on your R2 tool-timeout: the full suite takes
~4 minutes; to verify within a 124s budget run the three subsets separately:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_promotion_gate.py -q          (~30s)
  pytest tests/alpha_research/test_factor_eval_skill_orchestration.py tests/alpha_research/test_v14_book_level_promotion.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~60s)
  pytest tests/alpha_research/test_factor_registry.py tests/research_orchestrator/test_pr9_validation_field_gate.py -q   (~110s)
Known pre-existing (unchanged, chipped separately): 6 test_research_orchestrator.py smoke failures from
the earlier M4 hardening.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 3.
RESIDUAL CONCERNS (honest list):
(a) run_or_load_verdict's per-key lock serializes same-key contenders across PROCESSES via the OS file
    lock; within one process, python file locks may be re-entrant on some platforms — the state re-check
    inside persist_verdict's transition is the second belt.
(b) cmd_seal consumes an a6 authorization BEFORE the enforcement bands run; if enforcement then refuses
    (e.g. missing ack), the authorization is wasted (conservative direction, must re-record).
(c) The A5 reservation does not itself enforce the warn/hard bands (each A5 study is individually
    human-authorized consume-once; the bands for the factor-level path are enforced at cmd_seal via
    virgin_window_multiplicity, which reads the same ledger). A direct reproduce caller with N distinct
    pre-recorded authorizations could exceed the hard band without a cmd_seal-level refusal — flag if you
    want the hard band enforced inside reserve_a5_study_spend as well.
(d) A5 ledger rows no longer carry evidence_tier (the reservation happens below cmd_seal where the tier
    is unknown; the authorization record carries the reason).
(e) Diagnostic-row append idempotence on resume-after-append crash remains a known Minor (R2 residual e),
    to be closed before real live use.

REVIEW QUESTIONS
1. Re-run your R2 probe matrix (barrier double-execute / foreign frozen_set / borrowed seal with forged
   step / direct-A5 ledger / shaped a6 dict / blank-request resume / seeded live artifact / dangling
   diagnostic ids). Any probe still lands?
2. Interleaving audit of the new atomic pieces: consume(a6) → reserve → claim → open_claim →
   run_or_load_verdict → diagnostics → append_rows → complete. Any crash point that loses
   one-request-one-result, deadlocks a seal unrecoverably, or lets the budget under-count?
3. Is residual (c) acceptable for PR3, or must reserve_a5_study_spend enforce the hard band internally?
4. Anything else blocking SHIP for the machinery layer (the S6 governed runner + real-data burned-window
   pilot remain explicitly future PRs; live promotion is unreachable until then by M1's registry).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
