# GPT 5.5 Pro cross-review prompt — Phase 2 pre-publish wall IMPLEMENTATION diff (Round 4)

发送前：分支已推送（HEAD ≥ 0425100）。发送时把 `workspace/research/calendar_unfreeze/phase2_wall.diff` **全文**粘贴到 ===DIFF=== 标记之间（1,342 行、23 文件——GPT 沙盒 raw fetch 不可靠，内嵌文本为权威）。

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is ROUND 4 of the calendar-unfreeze review series. Rounds 1-3 reviewed and SHIPPED the DESIGN (UNFREEZE_PLAN.md v3: D3 born-sealed mechanical clamps, no-global-policy invariant, pre-publish wall ordering). THIS round reviews the Phase-2 IMPLEMENTATION diff against that shipped design. Your mandate: (1) is the implementation FAITHFUL to the shipped contract? (2) does the implementation introduce NEW holes the design review could not see? Do not re-litigate design decisions you already shipped.

REPO (public — raw fetch may fail; the embedded diff below is authoritative)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>
Key context files:
- CLAUDE.md (§3 invariants, §3.2 PIT, §3.4 formal-run governance)
- workspace/research/calendar_unfreeze/UNFREEZE_PLAN.md (the SHIPPED design, incl. D3 items 1-8 and the §6/§7/§8 disposition tables)
- workspace/research/calendar_unfreeze/SELF_REVIEW.md (Round-4 preflight at the bottom)

SYSTEM FACTS the diff operates against:
- Live provider: FROZEN at 2026-02-27, manifest policy id frozen_20260227_system_build, build id depth9_20260630_sharecap_reanchor_20260701. The thawed provider does NOT exist yet — this wall must be green BEFORE Phase-3 rebuild/publish.
- Raw layer: already caught up to 2026-06-30 (82 trading days incl. the FY2025 annual + 2026Q1 report season), so post-boundary data physically exists in data/pit_ledger inputs — the sandbox-door clamp is ALREADY load-bearing today.
- The two sanctioned data doors: src/data_infra/pit_research_loader.py (sandbox, reads pit_ledger) and src/research_orchestrator/qlib_windowed_features.py (formal, wraps D.features under ResearchAccessContext + cache manifest).
- Existing layered defenses that the diff builds on: ResearchAccessContext.validate_read (window/seal/fields at oos_test stage), PIT002 + bare-D.features lints, HoldoutSealStore spend-on-attempt.

SELF-REVIEW PREFLIGHT (Round 4) — verdict "clean for GPT". Checked §3 invariants (all changes NARROW access; the one semantic widening — the promotion_evidence calendar_end guard — accepts a longer calendar ONLY when oos_end equals the policy-recorded spent boundary, with the IsEndLeakageError belt retained; the shorter-calendar case still refuses). Known trade-offs deliberately left for your judgment:
(a) lru_cache process-lifetime caching of the boundary/live-ids (rotation mid-process reads stale values; assumption: per-run processes, rotations happen in the publish ceremony);
(b) cache generation-binding enforced only when the caller passes non-empty ids (today's only caller is the formal door, which always does);
(c) the QA audit-window anchor uses an hour>=16 heuristic for "last closed session";
(d) _formal_calendar_policy_id prefers a prescription field that does not exist yet on PrescribedRecipe (getattr → None → manifest-recorded id).
Also disclosed: an earlier "post-Phase-1 QA all green" report was WRONG (audit window anchored on the now-future calendar tail; the || echo chain swallowed the exit code) — fixed in this diff (last-closed-session anchor) and re-verified via exit code + Overall line.

WHAT CHANGED (23 files, +798/−33; commits 81680fb / 3f1cec8 / cb2c8d0)
1. calendar_policy.py: optional spent_oos_end/fresh_holdout_start (both-or-neither) + resolve_spent_oos_boundary (3 branches per the shipped M6 contract) + SpentOosBoundary.
2. config/calendar_policies/frozen_20260630_thaw_step1.yaml: NEW policy (legacy YAML untouched).
3. pit_backend.py: publish(calendar_policy_id) REQUIRED (default deleted); run() gate publish-without-id → BuildGateError; threading through build_qlib_backend/build_unified_qlib/CLI --calendar-policy; update_daily_data + storage.export_to_qlib pass the manifest-RECORDED id.
4. pit_research_loader.py: _spent_oos_end_timestamp (live-manifest policy → resolver, fail-closed) + hard clamp of sim_dates in _load (NO seal escape in sandbox BY DESIGN — the only fresh-window door is the formal sealed path) + live_provider_ids().
5. qlib_windowed_features.py: D3 clamp — no-context read past boundary → HoldoutWindowViolation; context without claimed seal → HoldoutSealViolation; sealed context passes. Plus M4 cache generation binding (passes live build/policy ids to assert_cache_reusable + record_cache_write).
6. cache_manifest.py: provider_build_id/calendar_policy_id columns recorded + validated (legacy ""-rows mismatch real ids = one-time safe invalidation after rotation).
7. validation_steps.py: the two hardcoded calendar_policy_id="frozen_20260227_system_build" (IS/OOS handlers) → _formal_calendar_policy_id(context) (prescription pin else manifest-recorded).
8. promotion_evidence.py: OOS_END module constant → lazy _default_oos_end() (policy-driven); the calendar_end==oos_end guard relaxed ONLY for oos_end == policy-recorded spent boundary (never defaults to the live end; Phase-4 belt retained).
9. revalidation.py: END constant → lazy _spent_end() (params default None).
10. scripts/lint_no_global_calendar_policy.py (NEW, POLICY001a/b) + wired into run_daily_qa; caught 3 real violations on first run (2 resolved as ""-sentinel semantics, 1 noqa-exempted: the retroactive-manifest tool whose purpose IS stamping the legacy id).
11. run_daily_qa.py: audit expected-data window capped at the last CLOSED session (trade_cal now extends into the future for next_open_trade_day headroom).
12. Tests: +14 new (9 resolver incl. the manifest-declared-path cases; 5 formal-door behavior), fixture updates (pr8c source-text assertions moved to the new contract; cache-collision fixtures record generation ids; one test moved off the persistent data/_test_cache dir). Suites: orchestrator 253 green, data_infra green, pr8 green, run_daily_qa Overall PASS exit=0.

===DIFF===
<粘贴 workspace/research/calendar_unfreeze/phase2_wall.diff 全文>
===END DIFF===

REVIEW QUESTIONS
1. FAITHFULNESS: check the implementation against the shipped D3 items 1-8 one by one (policy fields, resolver branches + the 3 required CI tests incl. the manifest-declared-path flavor, both door clamps, seal record reuse, promotion/revalidation binding semantics, lint, pre-publish ordering). Anything the design required that the diff does NOT deliver?
2. FAIL-CLOSED COMPLETENESS: enumerate the failure branches — resolver on missing manifest/policy/calendar; promotion guard with calendar_end shorter/longer/equal; clamp when boundary resolution itself raises. Any branch that fails OPEN?
3. NEW-HOLE SCAN, especially: (a) the lru_cache staleness trade-off — is a long-lived process (dashboard hourly task, orchestrator daemon) that spans a provider rotation a REAL leak vector, and if so what invalidation would you require? (b) the ""-sentinel semantics in POLICY001b — can an empty-string policy id reach a publish or an artifact record silently? (c) the sandbox clamp reads the LIVE manifest — with tmp/test data roots (monkeypatched _data_root) the resolver fails closed; is any legitimate production path broken by that? (d) the formal door now imports pit_research_loader (data_infra ← research_orchestrator cross-import) — layering concern or acceptable?
4. TEST SUFFICIENCY: are the 14 new tests + updated fixtures enough to lock the wall, or name the exact missing test (e.g., a test that a PUBLISH without --calendar-policy fails at the CLI level; a test that update_daily_data's incremental republish preserves the manifest id).
5. The QA audit-window heuristic (hour>=16): acceptable, or require anchoring on an explicit last-complete-session source?
6. VERDICT: is the wall GREEN enough to unlock Phase 3 (mode=all rebuild → frozen-prefix byte + sidecar membership audits → dry-run → safe publish under frozen_20260630_thaw_step1)?

OUTPUT FORMAT
- Per D3 item 1-8 + M2/M4/M7: FAITHFUL / DEVIATES (with the offending diff hunk quoted and exact suggested replacement).
- New issues ranked Blocker / Major / Minor.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
