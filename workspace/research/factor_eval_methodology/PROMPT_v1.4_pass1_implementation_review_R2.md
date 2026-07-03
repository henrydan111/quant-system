# GPT 5.5 Pro cross-review prompt — v1.4 pass-1 implementation, ROUND 2 (re-review after REVISE)

> Round-1 implementation verdict: REVISE — Blockers 1-3, Major 1, Minor 1; A3/A7/A2 core designs
> CONFIRMED. All five findings ACCEPTED and folded. Branch `calendar-unfreeze` is pushed.
> Copy the block below into GPT 5.5 Pro verbatim.

```text
ROLE
You are a senior reviewer for an A-share quantitative research system. ROUND 2 of the v1.4 pass-1 IMPLEMENTATION review. In round 1 you found: B1 (the legacy design_hash OOS handler could spend a virgin window), B2 (A5 study spends silently under-counted when a book row exists for the same frozen set), B3 (TUD alias REQUIRED_FIELDS omitted factor_version + data-policy ids), Major 1 (override lacked bounded expiration), Minor 1 (stale §3.5 heading) — and confirmed A3/A7/A2 as substantively right. All five were accepted and folded. Verify each resolution is faithful, scan the fixes for new defects, and give the final verdict.

REPO (the fix commit is the latest on the branch; diff it against 0c3badd)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

THE FIVE RESOLUTIONS (verify against live code):
1. B1 → the virgin-window guard was placed at the UNIVERSAL seal-claim chokepoint `src/research_orchestrator/steps.py::_claim_holdout_access_if_needed` (immediately after the CICC quarantine check, before `HoldoutSealStore` construction) rather than only in `handle_validation_event_backtest_oos` — DELIBERATE ADAPTATION: the chokepoint covers the event-driven AND vectorized OOS handlers in one place (the handler you flagged routes through it; the comment at validation_steps.py ~L1129 documents the chokepoint pattern). `is_virgin_window(str(hypothesis.time_split.oos_end))` → RuntimeError "v1.4_A8_virgin_window_blocked_until_pr3..." with your exact message content. Tests: `TestA8VirginWindowChokepoint::test_a8_legacy_design_hash_oos_handler_refuses_virgin_window` + `::test_burned_window_still_reaches_the_legacy_claim` (a burned-window claim proceeds and records a seal event — the dry-run pilot path stays alive) in tests/alpha_research/test_v14_book_level_promotion.py. NOTE the residual you should confirm acceptable: the skill's own cmd_seal (frozen_set_hash-keyed, D6-enforced, user-driven confirm-first per §13) is NOT guarded by this chokepoint — the A5 fresh-window override-id enforcement there is PR3-scope wiring.
2. B2 → `OosWindowLedgerStore._latest_window_frozen_unit(spend_unit_types=...)` per your exact replacement; record_spend idempotences on {"", "frozen_set"}, record_study_spend on {"a5_signal_replication_study"}; record_book_spend unchanged (already keyed on (window, book_seal_key)). Tests: `test_book_first_then_a5_study_same_frozen_set_counts_two_spends` (both orders + idempotency) + `test_legacy_record_spend_not_masked_by_book_row`.
3. B3 → REQUIRED_FIELDS extended per your exact list (incl. recorded_before_stage7_freeze, factor_version, data_policy_ids_json); record_alias validates data_policy_ids_json as JSON carrying non-empty provider_build_id + calendar_policy_id (your exact error wording); the freeze-flag check moved BEFORE the missing-fields check so the stringified "True" satisfies presence. `candidate_scope._alias_matches_tud` inherits the extended REQUIRED_FIELDS automatically. Tests: `TestTudAliasFullPayload` (full-payload accepted; factor_version refusal; empty/placeholder/malformed data-policy refusals); the pr9 alias-positive fixture now carries real ids (no more "{}").
4. Major 1 → "expiration" added to _OVERRIDE_REQUIRED_FIELDS + the {"", "none", "never", "permanent"} refusal per your exact replacement; docstring + CLAUDE.md + AGENTS.md writer-gate bullets updated; `_override_payload()` fixture carries expiration="2027-01-01"; three unbounded values pinned refused in test_legacy_override_is_the_sole_gated_mint.
5. Minor 1 → CLAUDE.md §3.5 heading and the AGENTS.md §2a.5 mirror both read "factors: draft → candidate; approved = legacy-only; books promote via strategy_registry".
Plus your B3-adjacent guidance folded: the rederive script's output note now labels the result a CURRENT-POOL re-derivation, not a bit-for-bit reconstruction.
Also migrated: tests/alpha_research/test_hypothesis_workflow.py::test_accepts_candidate_when_opt_in_set (the last test pinning flag-alone admission) now seeds target-scoped Stage-3 fixtures and asserts the candidate_scope_report.

TEST EVIDENCE: chokepoint-driving files (test_v14 + test_pr9 + test_pr8c_validation_wiring + test_pr8d_oos_seal_strict_boundary + test_factor_lifecycle_profile + test_hypothesis_workflow) 196 passed; test_factor_registry + test_promotion_gate + skill stores/D6/D7 84 passed.

SELF-REVIEW PREFLIGHT: verdict "clean for GPT round-2". Checked: the chokepoint guard fires only at stage=='oos_test' (IS-only paths unaffected); the guard is BEFORE the store construction so no seal row is written on refusal; `_latest_window_frozen_unit` treats legacy blank spend_unit_type as frozen_set (pre-v1.4 parquet rows keep their idempotency); the extended REQUIRED_FIELDS cannot invalidate existing aliases (the store is new — no rows exist); the expiration check is string-normalized (case/whitespace). Residual concerns: the cmd_seal note in resolution 1.

REVIEW QUESTIONS
1. Per-finding table (B1, B2, B3, Major 1, Minor 1): RESOLVED / PARTIAL / NOT RESOLVED, one line each.
2. B1 placement — confirm the chokepoint adaptation is equal-or-stronger than your per-handler replacement, and that leaving cmd_seal's A5 override-id enforcement to PR3 (given D6 enforcement + §13 confirm-first already gate it) is an acceptable, explicitly-named residual.
3. New-defect scan on the fixes themselves (e.g. the guard's placement relative to the CICC quarantine; the spend-unit sets {"", "frozen_set"} vs future unit types; the alias JSON validation's failure modes).
4. Final — SHIP / REVISE / REWORK + the single most important residual risk to carry into PR3.

OUTPUT FORMAT
- Per-finding resolution table.
- Any NEW issues ranked Blocker / Major / Minor with offending line quoted + exact replacement.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
