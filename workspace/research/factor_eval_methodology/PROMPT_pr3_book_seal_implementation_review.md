# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 8)

R1..R6 REWORK → all folded. R7 REWORK (4B/3M/1m — crash-after-compute re-executes [A5 + book +
generic runner]; real-CLI floor-flip mints a NEW seal key and re-executes; the book gate re-judges the
persisted verdict with current code; privileged set_status accepts caller seal/artifact worlds;
REGISTRATION_BAR mutable + hash not bound to evaluator semantics; relative --run-dir breaks resume;
conftest quarantine bypassable) → **all folded**. Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-8 re-review of PR3: verify each R7 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp. Top invariants: (1) ONE canonical sealed world; (2) one seal/request executes OOS at most once — including across CRASHES; (3) the pre-declared judgment is immutable after observation — not even a code deploy or a crash-resume can re-execute or re-judge.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/alpha_research/factor_eval_skill/book_seal_stores.py  (execution_started in BOTH state machines; complete() verdict binding)
- src/research_orchestrator/promotion_evidence.py           (mark_execution_started before compute; bar snapshot)
- src/research_orchestrator/holdout_seal.py                 (OosExecutionGuardStore for the generic runner)
- src/research_orchestrator/sealed_backtest_runner.py       (guard marker after claim, before backtest)
- src/alpha_research/factor_eval_skill/identity.py          (observation_protocol_hash; required bar hash)
- src/alpha_research/factor_eval_skill/orchestration.py     (seal key from observation hash; resolved paths)
- src/alpha_research/factor_eval_skill/sealed_oos.py        (immutable REGISTRATION_BAR + evaluator_hash)
- src/research_orchestrator/registries/strategy_registry.py (persisted-verdict-final gate; canonical stores only)
- tests/conftest.py                                         (constructor write-guard + session hash sentinel + scratch cleanup)
- tests/alpha_research/test_pr3_book_seal.py, test_v14_book_level_promotion.py

YOUR R7 FINDINGS — how each was closed (verify in code; probes pinned as named tests):
B1 (crash-after-compute re-executes) → the three-state machine you prescribed, on ALL THREE legs:
   * A5: A5ReproductionStore gains `execution_started` + mark_execution_started; reproduce marks it
     INSIDE the execution lock, after open_or_resume and BEFORE any OOS read; open_or_resume on
     execution_started REFUSES (permanent quarantine, explicit human migration); complete() only from
     execution_started. A crash while still `claimed` (no OOS touched) may same-run resume.
   * Book: BookSealArtifactStore runs claimed → execution_started → verdict_persisted → complete;
     run_or_load_verdict marks execution_started before the evaluator and QUARANTINES on finding it;
     persist_verdict only from execution_started.
   * Generic runner: new OosExecutionGuardStore at the canonical root — SealedBacktestRunner._claim_if_oos
     writes the marker AFTER the claim and BEFORE the backtest; ANY later claim for that seal_key
     (including same-run allow_same_run resume) refuses: this runner persists no reloadable result, so
     re-running is the only thing a resume could do — quarantined instead.
   Pinned: test_crash_during_execution_quarantines_permanently (book, backtester called ONCE ever),
   test_crashed_execution_quarantined_at_store_level, the A5 changed-recipe test's post-crash leg
   (identical recipe now QUARANTINES), test_runner_resume_never_reexecutes_started_oos.
B2 (real-CLI floor-flip mints a new key) → the identity split you prescribed:
   EvalProtocolSpec.observation_protocol_hash (bar EXCLUDED) keys the FrozenSelectionSet → seal key;
   the FULL protocol_hash (bar included) stays in the A5 request hash + persisted records. Pinned END
   TO END: test_cmd_seal_bar_flip_hits_same_seal_key_and_refuses — a REAL cmd_seal live completion,
   then a mutated bar, then a second cmd_seal: SAME frozen_set_hash, refusal at the spent-preflight,
   metric-compute calls == 1, exactly ONE seal event ever. Plus
   test_observation_hash_excludes_bar_full_hash_includes_it.
B3 (gate re-judges with current code) → the gate now verifies the artifact's embedded verdict re-hashes
   to the EXECUTION-TIME book_verdict_hash recorded by the state machine at persist_verdict, then
   requires bar_passed — evaluate_pre_declared_bar is NEVER called on persisted data; a record without
   a book_verdict_hash (pre-R7) refuses as "must be explicitly migrated". complete() additionally
   refuses an artifact whose embedded verdict differs from the persisted one (the binding you asked
   for). Pinned: test_persisted_fail_verdict_refused_never_rejudged + the store-level
   "immutable and final" pin in test_state_machine_transitions_and_immutability.
B4 (privileged promotion accepts caller worlds) → set_status's holdout_seal_dir / book_artifact_dir /
   seal_store / artifact_store parameters are REMOVED (and publish_strategy_candidate's artifact_store
   too); all three gate stores + the publish-time artifact load derive from
   resolve_configured_global_holdout_root(). Tests monkeypatch the resolver and seed the canonical
   root. Pinned: test_privileged_stores_are_not_caller_parameters (signature) + the whole
   TestStrategyPromotionWiring class now running against one canonical root.
Major 1 (mutable bar / unbound hash) → REGISTRATION_BAR is a MappingProxyType (mutation raises) and
   carries evaluator_hash = a hash of the SOURCE of direction_aligned_pass + evaluate_sealed_oos_bar
   (editing `>` to `>=` changes the bar hash automatically); reproduce takes ONE plain-dict snapshot
   per run (hash, persisted payload, and evaluation floor all from the snapshot — the global is read
   once); run_sealed_oos verifies on load that the persisted bar re-hashes to its recorded hash.
   Pinned: test_registration_bar_is_immutable_and_evaluator_bound.
Major 2 (relative --run-dir breaks resume) → FactorEvalContext.create resolves run_dir/store_root;
   the preflight exemption compares Path(...).resolve() on both sides.
Major 3 (quarantine bypassable) → three layers in tests/conftest.py: (1) the per-test resolver patch
   (with scratch-dir cleanup on teardown); (2) a COLLECTION-TIME constructor guard wrapping
   HoldoutSealStore, OosExecutionGuardStore, and every factor_eval_skill AppendOnlyStore to refuse the
   REAL canonical root outright (covers direct construction + caller-injected paths); (3) a session
   hash sentinel over the real store file that fails the run (exitstatus 3) if its bytes changed.
   No `if pytest` in production stores, per your instruction.
Minor (blank bar hash accepted) → EvalProtocolSpec.__post_init__ fails closed on a blank
   registration_bar_hash. Pinned: test_blank_bar_hash_fails_closed.

TEST STATE: 576 passed across the full affected suite (serial). Real canonical store: 6 historical
rows, hash-sentinel clean. Subsets fitting a 124s budget:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_promotion_gate.py tests/research_orchestrator/test_promotion_evidence.py -q   (~15s)
  pytest tests/alpha_research/test_v14_book_level_promotion.py tests/alpha_research/test_factor_eval_skill_orchestration.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~15s)
Clean-checkout data-dependent failures (gitignored provider_build.json etc.) remain environment, not code.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 8.
RESIDUAL CONCERNS (honest list):
(a) The quarantine release path ("explicit human migration") is a documented posture, not yet a tool —
    releasing a crash-orphaned execution_started record today means a manual store edit with a backup.
    A gated migration CLI is future work; flagging whether you require it in PR3 or accept it as an
    operational runbook item until S6.
(b) The orchestrator OOS handler chain (steps.py claim chokepoint + SealedBacktestRunner) now has the
    guard at the RUNNER leg; the steps.py chokepoint itself claims but computes via the runner, so the
    guard covers the compute. A hypothetical future handler that computes OOS without the runner would
    need its own execution marker (the A5/book paths have theirs).
(c) The conftest constructor guard matches the REAL canonical root by resolved-path equality; a test
    that re-points config.yaml itself (not the resolver) mid-session could theoretically dodge layer 2
    — layers 1 and 3 (resolver patch + hash sentinel) still cover that.
(d) EvalProtocolSpec's protocol-hash evolution (bar now excluded from observation identity): pre-R7
    frozen-set hashes were computed from the FULL protocol hash at R6 (never spent live) and from thin
    protocol strings before that (historical drivers, already spent + bannered). Per your R6 guidance,
    no pre-emptive alias rows; the alias store bridges if a real historical equivalence ever needs
    proving.

REVIEW QUESTIONS
1. Re-run your R7 probes (A5/book/runner crash-resume double-compute; real-CLI floor-flip seal-key +
   OOS-call count; persisted-verdict re-judge via new evaluator; fork-world promotion with a registered
   verifier; bar mutation mid-run; relative run_dir resume). Any still land?
2. Residual (a): is the manual-runbook quarantine release acceptable for the machinery layer, or must
   PR3 ship a gated migration command?
3. Is the three-layer conftest guard now sufficient for the "real store unreachable from tests" claim?
4. Anything else blocking SHIP (S6 governed runner + real-data burned-window pilot remain future PRs;
   live promotion is unreachable until a verifier registers).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
