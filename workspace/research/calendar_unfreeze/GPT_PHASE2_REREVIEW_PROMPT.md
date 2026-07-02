# GPT 5.5 Pro re-review prompt — Phase 2 wall implementation, Round 5 (after Round-4 REVISE)

发送前提：分支已推送（HEAD ≥ ea61d17）。发送时把 `workspace/research/calendar_unfreeze/phase2_wall_v2.diff`（2,113 行 / 30 文件，累计墙 diff 含 R4 修复）**全文**粘贴进 ===DIFF=== 标记之间。

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is ROUND 5 of the calendar-unfreeze series. Round 1-3 SHIPPED the design; Round 4 reviewed the Phase-2 implementation and returned REVISE with 0 Blockers, 6 Majors (M1 promotion guard missing the explicit-seal branch; M2 _formal_calendar_policy_id falling back to the live manifest — the most important residual; M3 lru_cache staleness across provider rotation; M4 cache generation binding only-when-supplied; M5 empty-string policy ids; M6 insufficient tests) and 2 minors (m1 hour>=16 heuristic is temporary-only; m2 cross-import belongs in a neutral module). ALL were accepted, none declined. Your Round-5 mandate is NARROW: (1) verify each R4 finding is adequately resolved in the updated diff; (2) judge the two self-found items fixed along the way; (3) rule on one deliberate semantic decision flagged for you; (4) scan the R4-fix delta for NEW holes. Do not re-litigate what you marked FAITHFUL in Round 4.

REPO (public — raw fetch may fail; the embedded diff is authoritative)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Context files: CLAUDE.md (§3 invariants), workspace/research/calendar_unfreeze/UNFREEZE_PLAN.md (§7b = the R4 disposition table), SELF_REVIEW.md (Round-5 preflight).

SELF-REVIEW PREFLIGHT (Round 5) — verdict "clean for GPT re-review". Honest disclosures:
(a) M1's sealed branch validates at the CONTEXT level (active ResearchAccessContext with holdout_seal_claimed + window coverage + provider/policy binding matched against the injected provenance); the seal RECORD-level full field binding you specified (candidate_id/purpose/code_hash/config_hash/data_snapshot_hash) is NOT implemented this round — recorded as follow-up. Judge whether context-level binding suffices for the wall or blocks Phase 3.
(b) While applying M2 we found the pin was being DROPPED on the normal formal path: PrescribedRecipe.to_dict()/from_dict() enumerate fields explicitly and did not carry calendar_policy_id, so any prescription round-tripping through a request file lost it and every formal run would have failed closed. Fixed (both directions) + the fixture exercises the round trip.
(c) DELIBERATE DECISION FOR YOUR RULING: calendar_policy_id is EXCLUDED from PrescribedRecipe.normalized_dict() and therefore from design_hash — rationale: the policy pin is an execution-environment binding, not design identity (the same design evaluated under two policies is the same design; policy/build binding lives in artifact provenance + seal records); consequence: zero design_hash drift for every existing registered hypothesis and seal key. The alternative (include it) would silently re-key every existing seal. Rule on this.
(d) Self-found beyond your list: HoldoutSealStore.claim_holdout_access(allow_same_run=True) crash-resume would silently resume under a ROTATED provider against different data — claim rows now record provider_build_id/calendar_policy_id and the recovery path refuses on generation mismatch (legacy ""-rows refuse against real ids too). 3 tests.
(e) Two PRE-EXISTING failures surfaced but NOT addressed here (separate task chips, not this wall's scope): tests/data_infra/test_share_capital_daily.py bare-import collection error; test_direct_d_features_calls_are_confined_to_wrapper vs the 2026-05-26 privileged sentinel D.features call in provider_manifest.py (noqa'd for the AST lint but not for that test's own scan).

WHAT CHANGED SINCE ROUND 4 (the R4-fix delta inside the cumulative 30-file diff)
1. src/data_infra/provider_context.py (NEW, m2+M3): side-effect-free neutral module; live_provider_ids()/live_spent_oos_end() cached keyed by provider_build.json (st_mtime_ns, st_size) — a rotation rewrites the manifest so any long-lived process re-resolves on the next call, no restart needed; refresh_live_provider_context() belt for the publish ceremony; resolution failure raises ProviderContextError (fail closed). Both doors now depend on it (pit_research_loader keeps thin back-compat delegates; qlib_windowed_features imports it directly).
2. M5: the publish gate in pit_backend.run() now rejects None/blank AND ids that do not load as a committed policy YAML (load_calendar_policy IS the existence+schema check).
3. M4: cache_manifest record_cache_write/assert_cache_reusable — provider_build_id/calendar_policy_id are REQUIRED parameters, validated non-blank at entry (blank raises CacheKeyMismatchError); legacy ""-rows refuse against real ids = the deliberate invalidation path (no silent migration mode reachable from research doors; the monthly ceremony archives the manifest).
4. M2: PrescribedRecipe.calendar_policy_id field (None sentinel) + to_dict/from_dict round-trip carry + _formal_calendar_policy_id = prescription pin (via context.request.hypothesis.prescription) or ValueError fail-closed; the live-manifest fallback is DELETED.
5. M1: the promotion guard is now 3-way: calendar_end < oos_end → refuse; == → pass; > → pass ONLY via (spent-replay: oos_end == policy-recorded boundary) OR (sealed: active context, holdout_seal_claimed, allowed window covers [oos_start, oos_end], ctx provider/policy == injected provenance). Never inferred from the live end.
6. Seal generation binding (self-found): SEAL_COLUMNS + claim rows carry provider_build_id/calendar_policy_id; allow_same_run recovery refuses on mismatch.
7. M6 battery test_r4_wall_hardening.py (21 tests): publish gate None/""/whitespace/unknown-id; trigger_qlib_incremental passes the manifest-RECORDED id + the real-manifest read; formal provenance pin-flows/unset-fails/missing-prescription-fails; in-process rotation re-resolution + missing-manifest fail-closed; promotion guard 5 branches (shorter/spent/fresh-no-seal/matching-seal/mismatched-seal); seal recovery same-gen-ok/rotated-refused/records-generation. Plus 4 generation-binding fail-closed tests in the permissive cache file.
8. m1: run_daily_qa comment marks hour>=16 as TEMPORARY CONSERVATIVE CAP with the steady-state anchor named.
Suites: 756 passed / 1 pre-existing unrelated failure; run_daily_qa Overall PASS exit=0 (incl. POLICY001 lint).

===DIFF===
<粘贴 workspace/research/calendar_unfreeze/phase2_wall_v2.diff 全文>
===END DIFF===

RE-REVIEW QUESTIONS (Round 5, narrow)
1. Per R4 finding M1-M6, m1, m2: RESOLVED / PARTIALLY / NOT RESOLVED, with the exact remaining gap. For M1 specifically: does context-level seal binding suffice for the pre-publish wall, or must the seal-record-level field binding (code_hash/config_hash/data_snapshot_hash...) land BEFORE Phase 3?
2. Ruling on disclosure (c): calendar_policy_id excluded from design_hash — correct (env binding, zero seal-key drift) or a provenance hole (same design under two policies shares a hash)?
3. The round-trip fix (b): any OTHER prescription/hypothesis serialization path (registry rows, run_metadata, normalized_dict consumers) where the pin could still be dropped or ignored?
4. M3 mechanism: is (st_mtime_ns, st_size) keying sufficient rotation detection on Windows (mtime granularity, same-size rewrites), or do you require a content hash? Note _CACHE.clear() keeps exactly one generation.
5. New-hole scan on the R4 delta only — e.g. the required-kwarg ordering in assert_cache_reusable (keyword-only after a defaulted param), the ProviderContextError path when qlib_dir exists but day.txt is missing, the promotion sealed-branch reading get_research_access_context() at guard time vs at compute time.
6. VERDICT: is the wall green enough to unlock Phase 3 (mode=all rebuild → frozen-prefix byte + sidecar membership audits → dry-run → safe publish under frozen_20260630_thaw_step1)?

OUTPUT FORMAT
- Per R4 finding: RESOLVED / PARTIALLY RESOLVED / NOT RESOLVED.
- New issues ranked Blocker / Major / Minor with offending hunk quoted + exact replacement.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
