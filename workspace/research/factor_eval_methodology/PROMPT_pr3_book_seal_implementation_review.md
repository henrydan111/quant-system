# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 9)

R1..R7 REWORK → all folded. R8 REWORK (3B/4M/1m — the formal hypothesis_validation OOS handler
executes twice under one claim; inherited public record() lets callers roll state machines back;
the bar snapshot is not threaded through the chain [mid-call global swap executes an undeclared
judgment]; evaluator_hash misses the sides derivation; the conftest sentinel covers one file and
fails silent; complete() skips blank historical hashes; unsafe "migration releases seal" wording;
stale ARTIFACT_STATES) → **all folded**. Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-9 re-review of PR3: verify each R8 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp. Top invariants: (1) ONE canonical sealed world; (2) one seal/request executes OOS at most once — across concurrency, crashes, AND the formal orchestrator path; (3) the declared judgment is the executed judgment, immutable after observation.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/research_orchestrator/validation_steps.py            (OOS handler: guard marker after claim, before schedule)
- src/alpha_research/factor_eval_skill/book_seal_stores.py (record() disabled; complete() fail-closed; terminal-spend wording; ARTIFACT_STATES)
- src/alpha_research/factor_eval_skill/sealed_oos.py       (evaluator hash covers sides; run_sealed_oos requires the declared bar)
- src/research_orchestrator/promotion_evidence.py          (reproduce requires + verifies the declared bar; never re-reads the global)
- src/alpha_research/factor_eval_skill/orchestration.py    (cmd_seal: THE single bar read, threaded down)
- tests/conftest.py                                        (full-dir sentinel + config hash; UsageError on guard failure)
- tests/alpha_research/test_pr3_book_seal.py               (R1..R8 probes pinned)
- tests/research_orchestrator/test_pr9_validation_field_gate.py (the handler crash-resume regression)

YOUR R8 FINDINGS — how each was closed (verify in code; probes pinned as named tests):
B1 (formal OOS handler executes twice) → handle_validation_event_backtest_oos now, immediately after
   _claim_holdout_access_if_needed and BEFORE reading the schedule or any OOS data, resolves the
   HoldoutContext (None → hard refuse) and calls OosExecutionGuardStore(resolve_configured_global_
   holdout_root()).assert_and_mark_execution(seal_key/run_dir/step_id) — your exact minimal fix. Your
   probe is pinned FUNCTIONALLY: test_oos_handler_resume_never_reexecutes_after_execution_started
   (crash mid-backtest → resume refuses "already STARTED" → direct_oos_compute_calls stays 1).
   The stronger run_workspace_pipeline routing + lint remains open as a disclosed follow-up (residual b).
B2 (public record() rolls state back) → record() is OVERRIDDEN TO RAISE on BOTH state machines
   (BookSealArtifactStore + A5ReproductionStore) — state changes go only through the sanctioned
   transitions; neither class uses record() internally (BookSealArtifactStore appends via its locked
   private helper, A5 via its own transitions). Pinned: test_state_machine_public_record_disabled +
   test_quarantine_survives_forged_reset_attempt (your end-to-end probe: crash → forged
   state="claimed" append refuses → evaluator calls stay 1).
B3 (bar not threaded) → your exact replacement pattern: cmd_seal reads the global ONCE
   (registration_bar_snapshot()), hashes it, binds the hash into EvalProtocolSpec, and passes the SAME
   snapshot + hash + spec.protocol_hash into run_sealed_oos → reproduce_sealed_oos; both bar params are
   REQUIRED there; reproduce NEVER re-reads the module global and VERIFIES
   payload_hash(registration_bar) == the declared registration_bar_hash ("registration bar/protocol
   mismatch" refusal); eval_protocol_hash (full identity) enters the a5_request_hash AND the completion
   record. Pinned with your exact probe shape: test_mid_call_bar_swap_cannot_change_executed_judgment
   (the global is swapped INSIDE the compute leg of a single call — the persisted bar is the DECLARED
   floor-1.0 snapshot, hash matches the declaration, and ls 0.5 FAILS) +
   test_reproduce_refuses_mismatched_declared_bar.
M1 (evaluator_hash misses sides) → _evaluator_source_hash now covers direction_aligned_pass,
   evaluate_sealed_oos_bar, sides_from_frozen_set, AND sorted(VALID_SIDES). Pinned:
   test_evaluator_hash_covers_sides_derivation.
M2 (sentinel partial + silent) → the sentinel is a {relative_path: sha256} snapshot over EVERY regular
   file under the real canonical root (lock/tmp excluded by explicit suffix list) PLUS config.yaml;
   sessionfinish prints the changed entries and sets exitstatus 3; BOTH guard-establishment except
   blocks now raise pytest.UsageError (a session that cannot prove the guard does not run).
M3 (complete() skips blank hashes) → your exact replacement: cur None → refuse; blank persisted hash →
   "must be explicitly migrated before complete"; embedded mismatch → refuse. Pinned:
   test_complete_refuses_blank_historical_verdict_hash.
M4 (unsafe release wording) → all three quarantine messages (A5, book, runner guard) now read
   "TERMINALLY SPENT … re-execution is forbidden. Recovery may only APPEND a result_recovered or
   abandoned_after_execution_started verdict with forensic evidence — never delete or reset prior
   rows"; class docstrings updated to match.
Minor (stale states) → ARTIFACT_STATES now lists all five states incl. execution_started; the module
   docstrings carry the R7 sequence.

TEST STATE: 583 passed across the full affected suite (serial), with the R8 probe pins + the full-dir
sentinel active (a clean exit itself proves the real store's byte-identity). Subsets fitting a 124s
budget:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_pr9_validation_field_gate.py -q   (~15s)
  pytest tests/alpha_research/test_v14_book_level_promotion.py tests/research_orchestrator/test_promotion_evidence.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~10s)
Clean-checkout data-dependent failures (gitignored provider_build.json etc.) remain environment, not code.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 9.
RESIDUAL CONCERNS (honest list):
(a) The B1 fix is your "precise minimal" variant (guard marker in the handler). The stronger final
    shape — routing the handler through SealedBacktestRunner.run_workspace_pipeline + an AST lint
    banning direct run_event_driven_window calls from formal OOS handlers — is NOT in this fold;
    flagging whether you require it in PR3 or accept the marker + functional regression until S6.
(b) record() remains public on NON-state-machine stores (ledger, authorizations, diagnostics,
    envelopes) whose semantics are append-only logs with their own sanctioned writers; the base-class
    _record_unchecked refactor you sketched as "long term" is deferred with them.
(c) The A5 "same-run resume while still claimed" path (crash BEFORE execution_started, i.e. before any
    OOS read) remains resumable by design — the window is the instants between open_or_resume and
    mark_execution_started.
(d) reproduce_sealed_oos verifies the DECLARED bar hash but cannot verify the declared hash is the
    CURRENT code's bar (a caller could thread an old, once-valid snapshot). The request hash binds it
    (old bar = its own request identity), the persisted record shows exactly what was declared and
    executed, and cmd_seal (the only sanctioned entry) always declares the current snapshot — flagging
    the layering for your call.

REVIEW QUESTIONS
1. Re-run your R8 probes (formal-handler double-execute; forged record() rollback on both machines;
   mid-call bar swap; sides-derivation edit under constant bar hash; direct a5_reproductions.parquet
   write escaping the sentinel; blank-hash complete()). Any still land?
2. Residual (a): marker + functional regression now, runner-routing + lint later — acceptable for the
   machinery layer, or a PR3 blocker?
3. Residual (d): is request-hash binding + sanctioned-entry declaration sufficient, or must reproduce
   also compare the declared hash against the live registration_bar_hash() when claim_seal=True?
4. Anything else blocking SHIP (S6 governed runner + real-data burned-window pilot remain future PRs;
   live promotion is unreachable until a verifier registers).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
