# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 10)

R1..R8 REWORK → all folded. R9 REWORK (2B/1m — the UNBOUND base-class `AppendOnlyStore.record(store,…)`
rolls both state machines back past the subclass overrides + `_transition` accepts caller-declared
states; a self-consistent NON-canonical bar (forged rule + forged evaluator_hash + matching self-hash)
is accepted and persisted as the "declared" judgment, and bare `eval_protocol_hash` strings are
unverifiable; module docstring missing execution_started) → **all folded**. R9 confirmed: the formal
handler execution guard, the mid-call bar-swap threading, the sides-covering evaluator hash, the
full-dir sentinel, blank-hash quarantine, terminal wording, and ARTIFACT_STATES all hold.
Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-10 re-review of PR3: verify each R9 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp. Top invariants: (1) ONE canonical sealed world; (2) one seal/request executes OOS at most once — across concurrency, crashes, the formal orchestrator path, AND raw store-level forgeries; (3) the declared judgment IS the executable canonical judgment, immutable after observation.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/alpha_research/factor_eval_skill/_store.py            (PUBLIC_RECORD_ENABLED gate in the BASE record())
- src/alpha_research/factor_eval_skill/book_seal_stores.py  (_TRANSITIONS action table; PUBLIC_RECORD_ENABLED=False ×2; docstring)
- src/alpha_research/factor_eval_skill/sealed_oos.py        (canonical_registration_bar_snapshot; REGISTRATION_BAR built from it)
- src/research_orchestrator/promotion_evidence.py           (canonical-bar gate before claim; EvalProtocolSpec chain checks)
- src/alpha_research/factor_eval_skill/orchestration.py     (cmd_seal passes eval_protocol=spec)
- tests/alpha_research/test_pr3_book_seal.py                (R1..R9 probes pinned)

YOUR R9 FINDINGS — how each was closed (verify in code; probes pinned as named tests):
B1 (unbound base record() + caller-declared transitions) → your exact replacement:
   * AppendOnlyStore.record now checks `type(self).PUBLIC_RECORD_ENABLED is not True` IN THE BASE
     METHOD (against the actual instance's class) and raises the typed PublicRecordDisabledError —
     `AppendOnlyStore.record(state_store, state="claimed", ...)` refuses; both state machines declare
     PUBLIC_RECORD_ENABLED = False (their R8 overrides remain as the belt).
   * BookSealArtifactStore._transition takes an ACTION name resolved against the fixed _TRANSITIONS
     table (mark_execution_started / persist_verdict / mark_diagnostics_failed / complete) — the
     allowed_from/new_state caller parameters are GONE; no table entry targets "claimed", so
     execution_started → claimed is unrepresentable; unknown actions refuse. (The A5 machine's
     transitions were already hard-coded per method.)
   Pinned with your two named regressions: test_unbound_append_only_record_cannot_reset_book_or_a5
   (both machines: crash → unbound record refuses → state stays execution_started → evaluator calls
   stay 1) and test_transition_api_cannot_move_execution_started_to_claimed (no "claimed" target in
   the table; old kwargs are a TypeError; invented action refuses).
B2 (self-signed non-canonical bar accepted; bare protocol hash) → your exact replacement:
   * sealed_oos.canonical_registration_bar_snapshot(): LITERALS + a LIVE _evaluator_source_hash()
     recomputation, reading NO replaceable module global; REGISTRATION_BAR is now BUILT FROM it
     (single source, immutable) and registration_bar_snapshot()/registration_bar_hash() delegate to it.
   * reproduce_sealed_oos, BEFORE any claim (claim_seal): the declared bar must EQUAL the canonical
     bar and its hash the canonical hash — your forged probe (rank rule "> 100", evaluator_hash
     "DECLARED_DIFFERENT_EVALUATOR", matching self-hash) now refuses "declared registration bar is not
     the executable canonical bar" with ZERO seal events. Old/unknown bars fail closed (versioned-
     evaluator recovery = future work; never "accept the old dict, run the current evaluator").
   * bare eval_protocol_hash strings are GONE from reproduce_sealed_oos and run_sealed_oos — the FULL
     EvalProtocolSpec travels, and the chain is verified: eval_protocol.registration_bar_hash == the
     declared bar hash ("protocol/bar mismatch"), eval_protocol.observation_protocol_hash ==
     frozen_set.eval_protocol_hash ("frozen-set observation protocol mismatch"); the recorded
     eval_protocol_hash is derived from the spec, never accepted as a string.
   Pinned with your three named regressions: test_self_hashed_noncanonical_bar_fails_before_claim,
   test_declared_rank_rule_is_the_rule_actually_executed (the same probe: the ONLY acceptable
   declaration is the canonical executable bar, so a declared rule can never diverge from the executed
   rule — divergent declarations refuse pre-claim), test_arbitrary_eval_protocol_hash_is_rejected
   (signature pins + None/chain-mismatch refusals, zero seal events).
   Consequence pinned in test_completed_a5_reproduction_is_never_recomputed: after a bar-constant code
   change, the OLD declared bar refuses at the canonical gate (fail-closed, persisted verdict stands) —
   the exact "deploy new code" path can neither re-judge nor re-execute.
Minor (module docstring) → the header now reads claimed → execution_started → verdict_persisted →
   complete | diagnostics_failed.

TEST STATE: 587 passed across the full affected suite (serial); the full-dir sentinel remained clean.
Subsets fitting a 124s budget:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_promotion_evidence.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~10s)
  pytest tests/alpha_research/test_v14_book_level_promotion.py tests/research_orchestrator/test_pr9_validation_field_gate.py tests/alpha_research/test_factor_eval_skill_orchestration.py -q   (~10s)
Clean-checkout data-dependent failures (gitignored provider_build.json / calendars) remain environment.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 10.
RESIDUAL CONCERNS (honest list):
(a) The canonical-bar gate binds cmd_seal-declared bars to the CURRENT code's bar. A mid-flight code
    deploy between declaration and execution (same process: impossible — one snapshot; across a
    crash-resume: the resumed call re-declares from the same code or refuses at the canonical gate)
    is fail-closed; a completed record under an old bar stays retrievable only through the future
    versioned-migration path.
(b) PUBLIC_RECORD_ENABLED protects the record() door; object.__setattr__/direct parquet writes remain
    the in-process Python trust boundary (the conftest sentinel + canonical-root guard cover the test
    surface; a hostile in-process actor is out of scope per your earlier rulings).
(c) The A5 store's transitions are per-method hard-coded rather than table-driven — same guarantees
    (no method writes "claimed" after open), different shape; flagging in case you want the table form
    there too.
(d) Runner-routing unification + the AST lint banning direct run_event_driven_window in formal OOS
    handlers remain the pre-S6 follow-up you scoped in R9.

REVIEW QUESTIONS
1. Re-run your R9 probes (unbound base record on both machines; _transition rollback; self-hashed
   forged bar; arbitrary protocol hash). Any still land?
2. Residual (c): is the A5 per-method form acceptable, or do you want the _TRANSITIONS table there?
3. Anything else blocking SHIP for the machinery layer (S6 governed runner + real-data burned-window
   pilot + versioned bar-migration tooling remain future PRs; live promotion is unreachable until a
   verifier registers).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
