# GPT 5.5 Pro cross-review prompt — v1.4 pass-1 implementation, ROUND 3 (confirmation after round-2 REVISE)

> Round-2 verdict: REVISE — B2/B3/Major-1/Minor-1 RESOLVED; B1 PARTIAL (the
> `SealedBacktestRunner._claim_if_oos` direct claim path with the `design_hash` fallback was not
> guarded) + a new Minor (stale lifecycle overview seams). Both folded at commit `df7d96c`.
> Copy the block below into GPT 5.5 Pro verbatim.

```text
ROLE
You are a senior reviewer for an A-share quantitative research system. ROUND 3 (confirmation) of the v1.4 pass-1 implementation review. In round 2 you found B1 PARTIAL: the A8 virgin-window guard sat only at the orchestrator chokepoint while SealedBacktestRunner._claim_if_oos still claimed directly with the design_hash fallback — a second legacy claim path. You also flagged stale lifecycle-overview seams (Minor). Both are folded. Verify the two resolutions and give the final verdict.

REPO (review commit df7d96c; diff against b756181)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>
Key files:
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/window_enforcement.py   (the shared guard)
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/sealed_backtest_runner.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/steps.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/alpha_research/test_v14_book_level_promotion.py

THE TWO RESOLUTIONS:
1. B1 → your exact factoring adopted: `assert_v14_a8_no_legacy_virgin_oos_claim(stage, time_split, caller)` lives in `window_enforcement.py` (the repo's window-policy module) with your message content, the oos_end fallback chain (oos_end / end_date / end), AND the fail-closed refusal when the OOS end is undeterminable ("v1.4_A8_virgin_window_guard_unable_to_determine_oos_end"). Called from BOTH legacy claim sites: `SealedBacktestRunner._claim_if_oos` (immediately after the ctx-None check, BEFORE HoldoutSealStore construction — a refusal writes no seal row) and the orchestrator chokepoint `_claim_holdout_access_if_needed` (which now passes hypothesis.time_split.to_dict()). Tests (none call the chokepoint helper for the runner path): `test_a8_sealed_backtest_runner_refuses_virgin_window_before_claim`, `test_a8_event_backtest_handler_refuses_virgin_window_through_runner_and_writes_no_seal` (via the public run_event_driven; the injected backtester is never invoked; seal store asserted empty), `test_a8_vectorized_oos_handler_refuses_virgin_window_through_runner_and_writes_no_seal` (via run_vectorized), plus `test_runner_burned_window_still_claims` (pilot path: a 2026-02-27-ending window claims and records) and `test_runner_missing_oos_end_fails_closed`.
2. Minor → the CLAUDE.md §9 overview line, the AGENTS.md overview line, and the factor_lifecycle/README.md title now read "draft → candidate (terminal; approved = legacy-only; book promotion via strategy_registry)" per your replacement wording.

TEST EVIDENCE: all runner/chokepoint-driving suites green — test_v14_book_level_promotion + test_hypothesis_workflow + test_get_factors_boundary + test_cache_generation_self_heal + test_pr8c_validation_wiring + test_pr8d_oos_seal_strict_boundary + test_pr9_validation_field_gate + test_factor_lifecycle_profile = 228 passed.

SELF-REVIEW PREFLIGHT: verdict "clean for GPT round-3". Checked: the guard runs only at stage=='oos_test' (IS paths untouched — pr8c/pr8d/lifecycle-profile suites green unchanged); run_workspace_pipeline routes through the same _claim_if_oos so the pipeline entry is covered too; the chokepoint passes a REAL dict (time_split.to_dict()) so the fail-closed branch cannot fire spuriously on well-formed hypotheses (TimeSplit.oos_end is constructor-required); burned-window claims verified writing seal events in both sites' tests. Residual named for PR3 (unchanged from round 2): cmd_seal's A5 fresh-window override-id enforcement (D6-enforced + §13 confirm-first today).

REVIEW QUESTIONS
1. B1 and the Minor: RESOLVED / PARTIAL / NOT RESOLVED, one line each. Specifically confirm no OTHER HoldoutSealStore.claim_holdout_access caller remains unguarded for legacy identities (you have the repo — grep it; reproduce_sealed_oos/cmd_seal is the named A5/PR3 residual).
2. New-defect scan on the round-2 fixes (guard placement in _claim_if_oos relative to the ctx-None check; the fail-closed oos_end branch's interaction with any caller passing a stage-only dict legitimately).
3. Final — SHIP / REVISE / REWORK + the single most important residual risk to carry into PR3.

OUTPUT FORMAT
- Two-line resolution table.
- Any NEW issues ranked Blocker / Major / Minor with offending line quoted + exact replacement.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
