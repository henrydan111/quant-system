# GPT 5.5 Pro re-review prompt — Phase 2 wall, Round 8 (final clearing pass: M9 only)

Status: ready to send AFTER `git push` of branch `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is ROUND 8 — the final clearing pass on the Phase-2 pre-publish wall. In Round 7 you ruled m5 RESOLVED (stat-sandwich + post-resolution re-hash) and M8 PARTIALLY RESOLVED: the production-path rotation test proved the sanctioned door stamps the post-rotation provider_build_id, but kept calendar_policy_id unchanged — the Phase-3 publish rotates BOTH ids (legacy frozen_20260227_system_build -> frozen_20260630_thaw_step1), so the policy half needed its own production-path proof (M9). You also stated the final unlock condition: M9 test + m4 (direct-D.features privileged sentinel, independent session) fixed-or-waived + the full Phase-2 battery green.

Your Round-8 mandate: verify M9 is resolved by the delta below and confirm the battery evidence; scan the delta for new issues. Nothing else is in scope.

REPO (public — raw fetch may fail; the embedded delta is authoritative)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Files: tests/research_orchestrator/test_r4_wall_hardening.py · UNFREEZE_PLAN.md §7e · SELF_REVIEW.md (Round-8 preflight).

SELF-REVIEW PREFLIGHT (Round 8) — verdict "clean". Declared deviation from your snippet: no spent_oos_end parameter on _write_provider — that field lives in the policy YAML (the REAL committed frozen_20260630_thaw_step1.yaml carries spent_oos_end=2026-02-27 / fresh_holdout_start=2026-02-28), not in the manifest; the test routes through the real policy file, which is semantically equivalent and closer to production. Battery evidence (all fresh 2026-07-02 runs): wall battery 53 passed across the five wall test files (rotation, D3 clamp/seal, boundary resolver, cache permissive, cache collision); POLICY001 lint clean; run_daily_qa Overall PASS (logs/qa_phase2_battery_20260702.log).

WHAT CHANGED (authoritative — complete R7-fix delta)

--- Delta 1 · _write_provider extended (backward-compatible) ---
    def _write_provider(self, qlib_dir, build_id,
                        calendar_policy_id: str = LEGACY_POLICY,
                        calendar_end: str = "2026-02-27") -> None:
        ...live manifest copied; provider_build_id + calendar_policy_id swapped;
        day.txt written ending at calendar_end...

--- Delta 2 · new test (verbatim core) ---
    def test_rotation_formal_cache_write_stamps_new_policy_id(self, tmp_path, monkeypatch):
        """R7-M9: the Phase-3 publish rotates BOTH ids (legacy frozen ->
        thaw_step1). The sanctioned door's cache write must stamp the NEW
        calendar_policy_id, not only the new build id. (No size/mtime
        preservation needed here — content-hash invalidation is proven by the
        preceding test; this one locks the policy-stamping half.)"""
        qlib_dir = tmp_path / "qlib_data"
        self._write_provider(qlib_dir, "gen_AAAA",
                             calendar_policy_id=LEGACY_POLICY, calendar_end="2026-02-27")
        monkeypatch.setattr(ctx_mod, "_qlib_dir", lambda: qlib_dir)
        ctx_mod.refresh_live_provider_context()
        assert ctx_mod.live_provider_ids() == ("gen_AAAA", LEGACY_POLICY)

        # Phase-3-shaped rotation: new build id + thaw policy + longer calendar.
        self._write_provider(qlib_dir, "gen_BBBB",
                             calendar_policy_id=THAW_POLICY, calendar_end="2026-06-30")
        assert ctx_mod.live_provider_ids() == ("gen_BBBB", THAW_POLICY)
        # The thaw policy pins spent_oos_end=2026-02-27 (policy_fields branch).
        assert ctx_mod.live_spent_oos_end() == pd.Timestamp("2026-02-27")

        [qlib stubbed via sys.modules as in the M8 test]
        qwf_mod.qlib_windowed_features(
            instruments=["000001_SZ"], fields=["$close"],
            start_time="2026-01-05", end_time="2026-02-27",
            cache_context=CacheContext(), stage="sandbox_screening",
            cache_manifest_dir=store_dir,
        )
        row = CacheManifestStore(store_dir).list_events().sort_values("recorded_at").iloc[-1]
        assert row["provider_build_id"] == "gen_BBBB"
        assert row["calendar_policy_id"] == THAW_POLICY
        assert row["calendar_policy_id"] != LEGACY_POLICY

(THAW_POLICY = "frozen_20260630_thaw_step1", loaded from the real committed policy YAML; the boundary resolves through its policy_fields branch under the 2026-06-30 calendar and still clamps at 2026-02-27 — this test is therefore also the first end-to-end rehearsal of the Phase-3 target state: manifest -> thaw policy -> resolver -> door clamp -> cache stamping. File: 24/24 pass.)

RE-REVIEW QUESTIONS (Round 8)
1. M9: RESOLVED? Is routing spent_oos_end through the real committed policy YAML (instead of a manifest parameter) the correct reading?
2. Battery: with 53 wall tests + POLICY001 clean + run_daily_qa Overall PASS evidenced, is the Phase-3 unlock condition now exactly {m4 fixed-or-waived}?
3. New-issue scan on the delta only.

OUTPUT FORMAT
- M9: RESOLVED / PARTIALLY RESOLVED / NOT RESOLVED with the exact remaining gap.
- New issues ranked Blocker / Major / Minor with offending text quoted and exact suggested replacement.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk + the explicit Phase-3 unlock condition.
```
