# GPT 5.5 Pro re-review prompt — Phase 2 wall, Round 7 (clearing pass after R6 M8+m5)

Status: ready to send AFTER `git push` of branch `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is ROUND 7 — the narrowest clearing pass yet on the Phase-2 pre-publish wall. History: plan R1-R3 (SHIP); implementation R4 REVISE (M1-M6+m1-m2, all folded) → R5 REVISE (single blocker M7 provider-context content identity, folded) → R6 REVISE with M7 RESOLVED and exactly two remaining items: M8 (Major — the rotation test proved only READ-side refusal of old-generation cache rows; the SANCTIONED WRITE path stamping the new generation after rotation was unproven) and m5 (Minor — TOCTOU between manifest hashing and the miss-path reload). In R6 you also stated the explicit Phase-3 unlock condition: M7 merged (done) + M8 test + m4 (direct-D.features privileged sentinel, independent session) fixed-or-waived + the full Phase-2 battery green.

Your Round-7 mandate: verify M8 and m5 are adequately resolved by the delta below; scan the delta for new issues. Nothing else is in scope.

REPO (public — raw fetch may fail; the embedded delta is authoritative)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Files: src/data_infra/provider_context.py · tests/research_orchestrator/test_r4_wall_hardening.py · UNFREEZE_PLAN.md §7d · SELF_REVIEW.md (Round-7 preflight).

SELF-REVIEW PREFLIGHT (Round 7) — verdict "clean". M8 follows your replacement text in both actions (relabel + production-path test through qlib_windowed_features with stubbed qlib, asserting the WRITTEN manifest row carries the post-rotation generation resolved by the door's own live_provider_ids() — no caller-supplied ids). m5 declared deviation: instead of a new load_provider_manifest_from_bytes API, the implementation uses your allowed alternative — stat-before/read/stat-after around the hash (mismatch fails closed "changed during read") plus a POST-resolution re-hash compared to the key digest (mismatch fails closed "rotated during resolution"). Regression: 601 passed / 9 skipped full sweep; wall battery 28/28.

WHAT CHANGED (authoritative — complete R6-fix delta)

--- Delta 1 · test_r4_wall_hardening.py (M8) ---
(a) Existing rotation test's cache section relabeled:
    # Old-generation cache ROWS are invalidated under the new generation
    # (read-side refusal; the write-side production-path proof is the
    # separate R6-M8 test below).
(b) New test (verbatim core):

    def test_same_size_same_mtime_rotation_formal_cache_write_stamps_new_generation(self, tmp_path, monkeypatch):
        qlib_dir = tmp_path / "qlib_data"
        self._write_provider(qlib_dir, "gen_AAAA")
        manifest = qlib_dir / "metadata" / "provider_build.json"
        monkeypatch.setattr(ctx_mod, "_qlib_dir", lambda: qlib_dir)
        ctx_mod.refresh_live_provider_context()
        assert ctx_mod.live_provider_ids()[0] == "gen_AAAA"
        before = manifest.stat()
        self._write_provider(qlib_dir, "gen_BBBB")
        os.utime(manifest, ns=(before.st_atime_ns, before.st_mtime_ns))
        # qlib stubbed via sys.modules (D.features -> empty frame)
        store_dir = tmp_path / "cache_manifest"
        qwf_mod.qlib_windowed_features(
            instruments=["000001_SZ"], fields=["$close"],
            start_time="2026-01-05", end_time="2026-02-27",
            cache_context=CacheContext(), stage="sandbox_screening",
            cache_manifest_dir=store_dir,
        )
        events = CacheManifestStore(store_dir).list_events()
        assert not events.empty
        row = events.sort_values("recorded_at").iloc[-1]
        assert row["provider_build_id"] == "gen_BBBB"
        assert row["calendar_policy_id"] == LEGACY_POLICY
        assert row["provider_build_id"] != "gen_AAAA"

(qlib_windowed_features internally calls provider_context.live_provider_ids() for the ids it stamps — the door's own path, no caller-supplied ids. The D3 clamp passes because end_time == the legacy boundary 2026-02-27.)

--- Delta 2 · provider_context.py (m5) ---
Key construction hardened:
    stat_before = manifest_file.stat()
    digest = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
    stat = manifest_file.stat()
    ...
    if (stat_before.st_mtime_ns, stat_before.st_size) != (stat.st_mtime_ns, stat.st_size):
        raise ProviderContextError("... changed during read — fail closed (mid-publish; retry).")
    key = (str(manifest_file), stat.st_mtime_ns, stat.st_size, digest)
Miss path, AFTER load_provider_manifest + day.txt + policy + boundary resolution:
    post_digest = hashlib.sha256(manifest_file.read_bytes()).hexdigest()   # failure -> fail closed
    if post_digest != digest:
        raise ProviderContextError("... rotated during resolution — fail closed (retry).")
    (only then cache {key: result}; _CACHE.clear() keeps exactly one generation)

RE-REVIEW QUESTIONS (Round 7)
1. M8: does the production-path test prove the sanctioned writer stamps the post-rotation generation? Is the sandbox_screening/no-context invocation acceptable as "the formal door's write path" (same code path stamps ids for all stages), or do you require an additional context-active variant?
2. m5: does the stat-sandwich + post-resolution re-hash close the TOCTOU to your satisfaction without a from-bytes loader API?
3. New-issue scan on the delta only.
4. Restate the Phase-3 unlock condition with M8 now landed — is it exactly {m4 fixed-or-waived + Phase-2 battery green}?

OUTPUT FORMAT
- Per item (M8, m5): RESOLVED / PARTIALLY RESOLVED / NOT RESOLVED with the exact remaining gap.
- New issues ranked Blocker / Major / Minor with offending text quoted and exact suggested replacement.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk + the explicit Phase-3 unlock condition.
```
