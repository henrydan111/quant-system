# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (round 1)

Reviews the PR3 implementation of the already-SHIPPED v1.4 amendment design (4-round GPT design arc +
4-round pass-1 implementation arc, 2026-07-03). PR3 lands the amendment's named residuals. Branch:
`calendar-unfreeze`; the commit adds/edits the 9 files linked below.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is the IMPLEMENTATION review of PR3 — the book-level promotion machinery an already-approved design (the v1.4 amendment, 4 GPT design rounds + 4 pass-1 implementation rounds, all findings folded) says must land before ANY virgin (post-2026-02-27) OOS may be spent. A defect here can silently break the one-seal-per-book guarantee, the spend-on-attempt semantics, or the promotion door — be adversarial; do not rubber-stamp.

REPO (public — fetch any file to verify against live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

CONTEXT (fetch):
- CLAUDE.md (§3.4 formal-run governance, §3.5 factor lifecycle & book-level promotion — the LIVE contract this implements)
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/CLAUDE.md
- THE NORMATIVE DESIGN (v1.4 amendment; §2 A2/A5/A6/A8 + round-2 N2/N3 are the PR3 spec; header names the PR3 residuals)
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/factor_eval_methodology/FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md

THE 9 CHANGED/NEW FILES (authoritative — fetch each):
1. NEW src/alpha_research/factor_eval_skill/book_seal.py — run_book_sealed_evaluation (the book_seal_key claim path), run_component_diagnostics_in_book_context (A2(b)/N3), evaluate_pre_declared_bar (fail-closed bar)
   https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_eval_skill/book_seal.py
2. src/research_orchestrator/promotion_evidence.py — extracted _compute_oos_per_factor_metrics (context-AGNOSTIC metric body; reproduce_sealed_oos now wraps it in its own context — behavior-preserving, 17/17 legacy tests green)
   https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/promotion_evidence.py
3. src/alpha_research/factor_eval_skill/sealed_oos.py — run_sealed_oos: A5 guard (virgin window + claim_seal=True requires fresh_window_override_id; fires BEFORE any work; closes the direct-script-call bypass)
   https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_eval_skill/sealed_oos.py
4. src/alpha_research/factor_eval_skill/orchestration.py — cmd_seal: A5 enforcement (virgin live requires the override id; virgin budget via virgin_window_multiplicity enforced IN ADDITION to the legacy report; virgin spends recorded as record_study_spend A5 rows with the override id; burned windows unchanged)
   https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_eval_skill/orchestration.py
5. src/research_orchestrator/registries/strategy_registry.py — A8 wiring: assert_book_seal_promotion_evidence (book_seal section required; key RECOMPUTED from the 8-field identity payload; seal event must EXIST in the holdout store; mode must be 'live'; bar_passed and component_diagnostics_ok must be literal True); set_status('approved') now REQUIRES holdout_seal_dir/seal_store; publish_strategy_candidate (StrategyCandidate v0 through the sanctioned publish door, definition_hash = book_seal_key)
   https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/registries/strategy_registry.py
6. src/research_orchestrator/window_enforcement.py — A8 guard token renamed v1.4_A8_virgin_window_blocked_until_pr3 -> v1.4_A8_virgin_window_legacy_path_blocked (legacy design_hash/frozen_set paths stay PERMANENTLY virgin-blocked; message points at the book door + A5 override)
   https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/window_enforcement.py
7. NEW tests/alpha_research/test_pr3_book_seal.py — 31 tests: the amendment's 3 named tests (component_diagnostics_no_second_seal / preserves_active_book_research_access_context / refuses_bare_claim_false_without_book_context), the bar matrix, the book-runner spend semantics (one-shot / same-run resume / spend-on-attempt / virgin refusals / hard budget), the A5 matrix (incl. a full cmd_seal pipeline test), the promotion-gate matrix (tamper/dryrun/failed-bar/broken-diagnostics/missing-store all refused; full valid path passes end-to-end)
   https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/alpha_research/test_pr3_book_seal.py
8. tests/alpha_research/test_v14_book_level_promotion.py — token pins updated (6 sites)
   https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/alpha_research/test_v14_book_level_promotion.py
9. tests/research_orchestrator/test_promotion_gate.py — the old "P1.1 artifact alone approves a strategy" test REWRITTEN to the new two-layer contract (P1.1 necessary, book-seal wiring additionally required)
   https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/research_orchestrator/test_promotion_gate.py

TEST STATE: 31/31 new + all driving files green (test_v14_book_level_promotion, test_factor_registry, test_factor_eval_skill_orchestration+d7, test_promotion_gate, test_promotion_evidence, test_pr9_validation_field_gate = 178 tests; + 343 green across the wider affected set). KNOWN PRE-EXISTING failures (verified by stashing this diff): 6 smoke tests in test_research_orchestrator.py fail on "run_workspace_pipeline formal context requires non-blank provider_build_id" — broken by the M4 hardening (2026-07-02) before this PR; queued as a separate fix; NOT touched here.

SELF-REVIEW PREFLIGHT — completed before this request. VERDICT: clean for GPT.
§3 invariants + the 9 principles checked: PIT (no data-path change; the extraction is verbatim; legacy context placement preserved; book path installs a CLAIMED context; diagnostics REUSE it so reads are seal-validated at the data layer) — PASS. OOS sacred (claim BEFORE any data work = spend-on-attempt; one-shot per book_seal_key with NO design_hash/frozen_set fallback; same-run resume provider-id-bound; virgin budget enforced PRE-claim; dryrun refuses virgin outright; A5 override enforced at BOTH cmd_seal and run_sealed_oos; legacy claim sites stay virgin-blocked) — PASS. Survivorship/four-layer — untouched. Multiplicity (A6 budget pre-claim; A5 spends recorded as study rows in the same budget) — PASS. No-leverage/execution-realism — the book verdict is CONTRACTUALLY the event-driven total-return 1× number (see residual (a)).
RESIDUAL CONCERNS for the reviewer (honest list):
(a) book_backtest_fn is an UNENFORCED seam: run_book_sealed_evaluation cannot verify the callable is actually the event-driven total-return 1× engine on the declared universe — execution_envelope_hash is key material but nothing validates the callable against it. The S6 harness (a later PR) binds it. Is a structural guard needed NOW, or is the documented contract + envelope-hash-in-key acceptable for this layer?
(b) dryrun-mode isolation is documented, not enforced: the caller must pass run-local stores; the enforced guarantee is only that dryrun REFUSES virgin windows. A mis-pointed dryrun could write a burned-window seal row in the global store (auditable nuisance, not a leak). Acceptable?
(c) The A2(b) "writes evidence rows" lands as: rows embedded in the A2 artifact + published into strategy_registry evidence via publish_strategy_candidate summaries. They are NOT appended to the factor registry's evidence.parquet (deliberate: no factor-registry master writes outside the orchestrator publish path). Does this satisfy the amendment's m3 schema intent?
(d) evaluate_pre_declared_bar semantics: keys must end _min/_max; drawdown metrics (mdd/max_drawdown) under _max are a MAGNITUDE cap with an explicit both-negative sign assertion (repo convention: goal_metrics mdd=-0.40). Unknown key/missing metric/NaN all raise. Check for any remaining silent-pass path.
(e) The §5 burned-window pilot: PR3 ships the dryrun MODE + end-to-end mocked integration tests; the REAL-DATA pilot (full A2 artifact on a real book) still gates the FIRST LIVE seal and requires an actual book (none exists yet — the first book build is the next roadmap item). The A8 "no virgin spend before promotion path exists" condition is now satisfied by this PR pending YOUR review.
(f) cmd_seal virgin path enforces BOTH the legacy oos_window_multiplicity report AND virgin_window_multiplicity (stricter wins; double enforcement intentional).
(g) window_enforcement token rename (blocked_until_pr3 -> legacy_path_blocked): semantics unchanged (legacy identity paths NEVER spend virgin windows); only the pointer text changed. 6 test pins updated.

QUANTITATIVE-RESEARCH PRINCIPLES — check the change against EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD. Esp.: does the extraction change WHAT runs inside the ResearchAccessContext for the legacy path (it now wraps panel+screening too — pure pandas, no provider reads — verify)? Can the diagnostics helper be tricked into running under a WRONG context (key/window/stage checks at book_seal.py)?
2. OOS SACRED & SEALED. Esp.: (i) can any path claim a book seal keyed by anything other than book_seal_key? (ii) can the same book_seal_key spend twice (crash/resume matrix — allow_same_run + provider-id binding)? (iii) can run_component_diagnostics_in_book_context cause a SECOND observation of the window outside the claimed seal? (iv) is there any remaining virgin-window path that bypasses BOTH the A5 override requirement and the book door (grep for claim_holdout_access / HoldoutSealStore callers)?
3. SURVIVORSHIP — untouched; confirm.
4. FACTOR-EVAL STANDARD — candidate stays terminal; diagnostics mint no status (rows carry spent_in_book_context=True / fresh_oos_eligible=False / promotion_eligible=False); confirm no status write anywhere in the new code.
5. EXECUTION & COST REALISM — the promotion-driving number is contractually the event-driven total-return 1× figure (residual (a)); the bar evaluator's mdd sign handling.
6. NO LEVERAGE — 1× contractual; nothing in the new code scales exposure.
7. NO HEDGE WORDS — docstrings/messages state contracts precisely; flag any over-claim (e.g. does any docstring claim MORE isolation than the code enforces?).
8. FOUR-LAYER — untouched; confirm.
9. MULTIPLE TESTING — A6 budget enforced BEFORE the claim in both the book runner and cmd_seal-virgin; A5 spends counted in the same budget; ledger rows carry spend_unit_type. Confirm no ordering hole (e.g. a claim that succeeds when the budget check would have refused).

REVIEW QUESTIONS
1. Correctness — the claim/record/context ordering in run_book_sealed_evaluation (budget -> claim -> ledger -> context -> backtest -> bar -> diagnostics -> final report): any hole where a failure leaves the stores inconsistent in a way same-run resume cannot recover? The diagnostics-failure branch (recorded, blocks promotion, keeps verdict): sound, or should it hard-fail?
2. The promotion door — is assert_book_seal_promotion_evidence sufficient to make StrategyRegistryStore.set_status('approved') the A8-complete "sole promotion door wired to the book seal artifact"? What tamper/spoof survives it (e.g. a book_seal section from a DIFFERENT object's artifact — should the gate bind object_id/definition_hash to the registry row's book_seal_key)?
3. The A5 enforcement — cmd_seal + run_sealed_oos: any remaining door for a factor-level virgin spend without a pre-recorded override id? Is enforcing at the wrapper (not inside reproduce_sealed_oos) sufficient given reproduce_sealed_oos is importable?
4. Evidence — the exact additional test you would demand before the FIRST LIVE book seal (beyond the required real-data burned-window pilot).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
