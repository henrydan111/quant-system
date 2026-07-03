# GPT 5.5 Pro cross-review prompt — v1.4 pass-1 implementation, ROUND 4 (confirmation after round-3 REVISE)

> Round-3 verdict: REVISE — B1 PARTIAL: `_claim_if_oos` decided whether to claim from the
> payload's optional `stage` key, so an OOS `HoldoutContext` with a stage-less/mislabelled payload
> skipped both the claim and the A8 guard, after which `run_workspace_pipeline` installed a
> `ResearchAccessContext` asserting `holdout_seal_claimed=True` untruthfully. Fixed at `2e22b6b`
> with your exact replacement. Copy the block below into GPT 5.5 Pro verbatim.

```text
ROLE
You are a senior reviewer for an A-share quantitative research system. ROUND 4 (confirmation) of the v1.4 pass-1 implementation review. Round 3 found the runner's claim decision was payload-controlled (time_split["stage"]) rather than context-controlled (HoldoutContext.stage) — a public bypass of both the legacy seal claim and the A8 virgin-window guard, with run_workspace_pipeline then installing holdout_seal_claimed=True untruthfully. Your exact replacement was adopted. Verify the resolution and give the final verdict.

REPO (review commit 2e22b6b; diff against 87fb94a)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>
Key files:
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/sealed_backtest_runner.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/alpha_research/test_v14_book_level_promotion.py

THE RESOLUTION (verify against live code):
`_claim_if_oos` now: (1) reads payload_stage and ctx_stage (via getattr, None-safe); (2) FAILS CLOSED on a contradiction (ctx_stage and payload_stage both set but different -> ValueError "stage mismatch", your exact message, before any store construction); (3) resolves `stage = ctx_stage or payload_stage` — the HoldoutContext is the source of truth, the payload only fills a context-less gap; (4) proceeds through the unchanged ctx-None check -> shared A8 guard -> claim. run_workspace_pipeline is unchanged: its holdout_seal_claimed=True is now truthful because _claim_if_oos can no longer be skipped by a stage-less payload when the context says oos_test.

TESTS ADDED (your three names):
- test_runner_oos_context_missing_stage_still_claims_or_refuses_virgin_window — ctx.stage=oos_test + stage-less payload: virgin window -> A8 refusal with NO seal row; burned window -> the claim actually happens (seal event recorded, not silently skipped).
- test_runner_stage_mismatch_refuses_before_claim — ctx oos_test vs payload is_only -> ValueError, no seal row.
- test_workspace_pipeline_oos_context_missing_stage_cannot_install_claimed_context_without_claim — through the PUBLIC run_workspace_pipeline: virgin+stage-less refuses BEFORE pipeline_fn runs (assert_not_called, no seal); burned+stage-less runs a probe pipeline that asserts the seal event ALREADY EXISTS when the pipeline executes (the claimed-context flag is truthful).

TEST EVIDENCE: the ENTIRE tests/research_orchestrator suite + test_hypothesis_workflow + test_get_factors_boundary + test_pr8b_ordering_modes + test_pr8c_validation_wiring + test_pr8d_oos_seal_strict_boundary = 450 passed — i.e. the behavioral change (ctx-driven claim where stage-less payloads previously skipped) breaks no legitimate caller; test_v14_book_level_promotion = 22 passed.

SELF-REVIEW PREFLIGHT: verdict "clean for GPT round-4". Checked: getattr(None, "stage", "") keeps the sandbox path (runner constructed with holdout_context=None + stage-less payload -> early return, run_workspace_pipeline's explicit ctx-None sandbox branch unchanged); ctx-None + payload oos_test still raises the pre-existing "requires a HoldoutContext" ValueError; the A8 guard receives the RESOLVED stage; no other _claim_if_oos caller exists (run_vectorized / run_event_driven / run_workspace_pipeline all route through it). Residuals carried to PR3 (named, unchanged): cmd_seal A5 fresh-window override-id enforcement; the book_seal_key claim path + component-diagnostics helper + burned-window pilot.

REVIEW QUESTIONS
1. B1: RESOLVED / PARTIAL / NOT RESOLVED — one line. Confirm the stage source-of-truth ordering (mismatch check before resolution; ctx-first resolution) matches your replacement and closes the run_workspace_pipeline untruthful-flag path.
2. New-defect scan on this fix only (e.g. ctx_stage values other than oos_test/is_only; callers that legitimately relied on payload-stage-only behavior — the 450-test evidence says none, but check the source).
3. Final — SHIP / REVISE / REWORK + the single most important residual risk to carry into PR3.

OUTPUT FORMAT
- One-line B1 resolution verdict.
- Any NEW issues ranked Blocker / Major / Minor with offending line quoted + exact replacement.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
