# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 2, post-REWORK)

Round 1 = **REWORK** (5 Blockers + 3 Majors + 1 Minor; adversarial probes: completed-OOS re-run,
forged/foreign promotion evidence, string-typed A5 auth, forgeable context, non-atomic accounting,
boolean override, infinite-metric bar pass). **Every finding is folded**; this round asks you to verify
each is genuinely closed and to re-probe. Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is your ROUND-2 re-review of PR3 (book-level promotion machinery) — you returned REWORK with adversarial probes; confirm each Blocker is genuinely closed (re-run your probes), and surface anything new. Do not rubber-stamp.

REPO (public — fetch to verify against live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- Design: workspace/research/factor_eval_methodology/FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md
- NEW src/alpha_research/factor_eval_skill/book_seal_stores.py  (BookSealArtifactStore state machine / OverrideAuthorizationStore / StrategyComponentDiagnosticStore)
- src/alpha_research/factor_eval_skill/book_seal.py             (reworked runner + diagnostics)
- src/alpha_research/factor_eval_skill/stores.py                (OosWindowLedgerStore.reserve_book_spend + disclosure columns)
- src/research_orchestrator/registries/strategy_registry.py    (canonical-artifact promotion gate + immutable publish)
- src/research_orchestrator/promotion_evidence.py              (A5 enforcement at the lowest shared claim point + provider-bound claim)
- src/alpha_research/factor_eval_skill/sealed_oos.py            (wrapper fail-fast)
- src/alpha_research/factor_eval_skill/orchestration.py         (cmd_seal virgin governing report)
- src/research_orchestrator/holdout_seal.py                     (request_hash column + resume binding)
- tests/alpha_research/test_pr3_book_seal.py                    (44 tests — your probes pinned)
- tests/research_orchestrator/test_promotion_gate.py, tests/research_orchestrator/test_r4_wall_hardening.py

YOUR ROUND-1 BLOCKERS — how each was closed (verify in code; your probes are now tests):
B1 (resume re-runs completed OOS) → BookSealArtifactStore state machine (claimed → verdict_persisted →
   complete | diagnostics_failed), append-only, file-locked. Every evaluation has a request_hash
   (identity over book_seal_key/mode/provider ids/hypothesis/profile/factor_exprs/horizon/n_quantiles/
   component_weights); the seal event records it (holdout_seal.py request_hash column) and resume
   verification includes it. Resume is AUTOMATIC (no allow_same_run in the public API): state==complete
   REFUSES ("never re-run"); changed request REFUSES; state==claimed re-runs the backtest ONLY because no
   verdict was ever persisted (first completion); verdict_persisted/diagnostics_failed reuse the PERSISTED
   verdict and finish ONLY diagnostics — book_backtest_fn is never called once a verdict exists (pinned:
   test_completed_evaluation_can_never_be_rerun / test_failed_bar_is_persisted_and_immutable /
   test_diagnostics_failure_persists_state_and_resume_never_reruns_backtest /
   test_changed_request_resume_refused / test_crash_before_verdict_resume_completes_once).
   Diagnostics failure persists diagnostics_failed and raises typed BookSealDiagnosticsError.
B2 (forged/foreign promotion evidence; in-place republish) → the gate signature is now
   assert_book_seal_promotion_evidence(object_id, registry_store, artifact_store, seal_store, version):
   it LOADS the canonical artifact by the hash the REGISTRY ROW references (BookSealArtifactStore.
   load_artifact re-hashes at read), binds row.definition_hash == artifact.book_seal_key, recomputes
   book_seal_key from the identity payload, verifies the seal event (event_id + request_hash + run/step/
   provider/calendar/stage), RECOMPUTES the bar from persisted metrics vs the plan's bar (an edited
   bar_passed is worthless), validates diagnostics rows (finite mandatory metrics, count consistency,
   no promotion claim), and checks the multiplicity action. set_status('approved') requires BOTH
   holdout_seal_dir and book_artifact_dir (fail-closed). publish_strategy_candidate loads the canonical
   artifact (never a caller dict) and REFUSES a same-object republish with a changed payload (immutable
   rows). Pinned: test_gate_ignores_caller_supplied_book_seal_dict / test_tampered_persisted_bar_boolean_
   refused_by_recompute / test_foreign_artifact_binding_refused / test_same_key_republish_with_changed_
   payload_refused / test_missing_seal_event_refused / test_dryrun_artifact_never_promotable.
B3 (string-typed A5 auth; reproduce_sealed_oos bypass) → OverrideAuthorizationStore: authorizations are
   PRE-RECORDED (explicit user_signoff + reason/burn statement + window + scope), consume-ONCE, scope-
   bound; an invented id refuses ("never pre-recorded"). Enforcement moved INTO reproduce_sealed_oos
   (the lowest shared claim point of the factor-level path) — a direct import cannot bypass it; the
   claim there is now also provider/calendar-bound. The wrapper check remains as fail-fast. Pinned:
   test_reproduce_sealed_oos_virgin_enforced_at_lowest_claim_point (your exact probe: direct call,
   invented id → refused BEFORE any claim; real authorization → consumed once, second use refused) +
   test_authorizations_are_prerecorded_scoped_and_consume_once.
B4 (caller-forgeable execution/diagnostics) → YOUR INTERIM ADOPTED: mode="live" now RAISES ("refused
   until the governed S6 book runner exists") — the callable seam is dryrun-only, and dryrun is never
   promotable. Docstrings no longer claim enforcement the code doesn't do. Diagnostics: the context flag
   alone is no longer trusted — the helper requires the seal_store and verifies a REAL claim event for
   the key whose run_dir matches the active context (fabricated context → "no holdout seal event";
   foreign run → refused); completeness enforced (exact frozen-set coverage, finite mandatory metrics,
   n_components consistency). Pinned: test_live_mode_refused_until_governed_runner /
   test_fabricated_context_without_real_seal_event_refused / test_foreign_run_seal_event_refused /
   test_nan_or_missing_component_metrics_refused. NOTE the gate-side testing pattern: since live mode is
   refused in the public runner, promotion-gate tests SEED the canonical store directly
   (_seed_live_artifact — simulating the future governed runner's output); the gate's job is binding
   verification, not artifact production.
B5 (non-atomic claim/ledger; boolean override) → OosWindowLedgerStore.reserve_book_spend: ONE lock does
   recognize-resume (an existing identical key returns resumed=True — never a pending extra spend, and a
   changed request_hash on the same key refuses) → count → enforce (warn band needs multiplicity_ack;
   hard threshold needs a CONSUMED a6_multiplicity authorization row — a fabricated dict or boolean
   refuses) → append the spend-on-attempt row. Reservation runs BEFORE the claim: a crash between leaves
   a recorded spend + unclaimed seal (budget over-counts, conservative). multiplicity_override:bool is
   REMOVED from the public API (multiplicity_override_id, consumed via the store; a6 records must commit
   to adjusted statistics). Pinned: test_reserve_recognizes_resume_not_pending_extra /
   test_hard_threshold_needs_consumed_authorization_not_boolean / test_reserve_changed_request_refused /
   test_a6_authorization_requires_adjusted_stats_commitment.
M1 → math.isfinite on BOTH metric and bound (inf refused; pinned).
M2 → StrategyComponentDiagnosticStore: durable append-only rows keyed book_seal_key+request_hash+
   component_factor_id; record ids stored in the artifact (artifact_hash covers them transitively);
   registry evidence summary carries diagnostic_record_ids.
M3 → ledger columns +book_plan_hash/+structural_family/+request_hash (backfilled); the runner passes
   plan hash + factor ids; cmd_seal's GOVERNING final report on virgin windows is now
   virgin_window_multiplicity (legacy report retained alongside as legacy_multiplicity).
Minor 1 → dryrun seal/ledger stores MUST be run_dir-local (Path.is_relative_to guard; pinned:
   test_dryrun_refuses_non_run_local_stores).

TEST STATE: 540 passed across the full affected suite (the 44-test PR3 file + all driving files:
test_v14_book_level_promotion, test_factor_registry, test_factor_eval_skill_* , test_promotion_gate,
test_promotion_evidence, test_pr9_validation_field_gate, test_lock_concurrency, test_frozen_selection_set,
test_d3_formal_door_clamp, test_factor_lifecycle_*, test_r4_wall_hardening (updated: the D3.5
sealed-fresh-window guard test now records a unique-per-run A5 authorization — the new required step),
test_research_access_context, test_validation_cache_context_propagation). Known pre-existing (unchanged,
chipped separately): 6 test_research_orchestrator.py smoke failures from the earlier M4 hardening.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 2.
RESIDUAL CONCERNS (honest list):
(a) Live mode refusal means the FIRST live book seal requires the governed S6 runner PR
    (GovernedBookBacktestResult attested against the execution-profile registry) — the promotion gate is
    ready and tested against seeded canonical artifacts; the producer is future work, as your interim
    prescribed. Your requested test_live_book_seal_crash_tamper_matrix_real_engine (real
    EventDrivenBacktester) lands with that PR + the burned-window pilot.
(b) Python-level trust boundary: the stores enforce convention+verification, not OS capabilities — a
    process with write access to the store files can still corrupt them (load_artifact re-hashes, so
    silent artifact tamper is detectable; a full coordinated rewrite of seal+artifact+ledger is not).
    Same trust level as every other gate in the repo.
(c) Crash between a6-authorization consumption and reservation wastes the authorization (conservative:
    must re-record). Crash between reservation and claim over-counts the budget (conservative).
(d) request_hash covers the evaluation inputs listed above but NOT qlib_dir/trade_cal (paths, not
    identity — provider ids ARE bound). Flag if you consider any omitted field spend-differentiating.
(e) The diagnostics-store rows are append-only and idempotence is NOT enforced on resume-after-
    diagnostics-append crash (a crash between append_rows and complete() could duplicate rows on
    resume; the artifact's diagnostic_record_ids pins the canonical set).

REVIEW QUESTIONS
1. Re-run your R1 probe matrix against the new code (completed re-run / verdict flip / changed request /
   foreign artifact / edited booleans / invented overrides / fabricated context / boolean override /
   inf metric). Any probe still lands?
2. Is the state machine sound — any interleaving (crash points between: consume → reserve → claim →
   open_claim → backtest → persist_verdict → diagnostics → append_rows → complete) that loses the
   one-request-one-result guarantee or deadlocks a seal unrecoverably?
3. Is the promotion gate now A8-complete (sole, book-bound, canonical-artifact door)? What forgery
   remains within the Python trust boundary that SHOULD be closed at this layer?
4. Residuals (a)-(e): acceptable for PR3, or does any block SHIP?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
