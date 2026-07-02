# GPT 5.5 Pro re-review prompt — Phase 2 wall, Round 6 (clearing pass after R5-M7)

Status: ready to send AFTER `git push` of branch `calendar-unfreeze` (pushed: commit `dcc367c`).

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is ROUND 6 — a NARROW clearing pass on the Phase-2 pre-publish wall implementation. History: the design plan shipped after 3 rounds (R1 REVISE → R2 REVISE → R3 SHIP). The implementation diff was then reviewed: R4 REVISE (M1-M6 + m1-m2, all accepted) → R5 REVISE, converged to a single Phase-3 blocker: M7 (provider_context cache keyed only by (st_mtime_ns, st_size) — a same-size / preserved-mtime manifest rewrite could let a long-lived process stamp cache/seal/promotion provenance with stale provider_build_id/calendar_policy_id). In R5 you also RULED: M2/M4/M5/m1/m2 + the three self-found items RESOLVED/APPROVED; calendar_policy_id correctly EXCLUDED from design_hash; M1 seal-record-level binding + M6-test-2 + m3 (context snapshot) = Phase-6 gates, NOT Phase-3 blockers; m4 (the pre-existing direct-D.features test vs the privileged provider_manifest sentinel call) must be fixed/waived before Phase 3 is declared fully green — it is being handled in an independent session.

Your Round-6 mandate: (1) verify M7 + M6-test-1 are adequately resolved by the delta below; (2) confirm the Phase-6 gate framing and the m4 pending status keep Phase 3 unlockable once m4 lands; (3) scan the delta for new issues. Do not re-litigate items you already ruled RESOLVED.

REPO (public — raw fetch may fail; the embedded delta below is authoritative)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze, commit dcc367c)
Key files: src/data_infra/provider_context.py · tests/research_orchestrator/test_r4_wall_hardening.py · workspace/research/calendar_unfreeze/UNFREEZE_PLAN.md (§7c = R5 dispositions) · SELF_REVIEW.md (Round-6 preflight).

SELF-REVIEW PREFLIGHT (Round 6) — verdict "clean for GPT clearing re-review". Faithfulness note, declared up front: your M7 replacement text specified a two-step check (stat match → then compare cached sha256 vs current sha256); the implementation instead computes sha256(provider_build.json) on EVERY call and puts it IN the cache key — strictly stronger and simpler, with identical cost (your spec also requires hashing the current file on every stat-match call). Fail-closed semantics unchanged; refresh_live_provider_context() retained as the publish-ceremony belt, not the only protection. Regression: 600 passed / 9 skipped across research_orchestrator + data_infra.

WHAT CHANGED (authoritative — the complete R5-fix delta)

--- Delta 1 · src/data_infra/provider_context.py (M7) ---
Cache dict re-keyed:
  # (path, st_mtime_ns, st_size, manifest_sha256)
  #   -> (build_id, policy_id, spent_oos_end_ts, fresh_holdout_start)
  _CACHE: dict[tuple[str, int, int, str], tuple[str, str, pd.Timestamp, Optional[str]]] = {}

_resolve() key construction:
  manifest_file = Path(manifest_path_for(qlib_dir))
  stat = manifest_file.stat()
  # R5-M7: content identity, not only (mtime, size) — hash the manifest
  # bytes on every call so a same-size / preserved-mtime rewrite still
  # invalidates the cache.
  digest = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
  key = (str(manifest_file), stat.st_mtime_ns, stat.st_size, digest)
  ...on any stat/read failure: raise ProviderContextError("... fail closed.")
Cache hit returns cached tuple; miss → full reload (manifest + day.txt + policy + resolve_spent_oos_boundary), then _CACHE.clear(); _CACHE[key] = result (exactly one generation kept). Module docstring updated to document content-identity semantics (Windows coarse timestamps / copied / atomic-publish filesystems).

--- Delta 2 · tests/research_orchestrator/test_r4_wall_hardening.py (M6-test-1) ---
New test in TestProviderRotationInvalidation:

    def test_same_size_same_mtime_rotation_still_reresolves(self, tmp_path, monkeypatch):
        qlib_dir = tmp_path / "qlib_data"
        self._write_provider(qlib_dir, "gen_AAAA")
        manifest = qlib_dir / "metadata" / "provider_build.json"
        monkeypatch.setattr(ctx_mod, "_qlib_dir", lambda: qlib_dir)
        ctx_mod.refresh_live_provider_context()
        assert ctx_mod.live_provider_ids()[0] == "gen_AAAA"
        before = manifest.stat()
        # Rotate with an id of IDENTICAL length, then restore mtime exactly.
        self._write_provider(qlib_dir, "gen_BBBB")
        os.utime(manifest, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = manifest.stat()
        assert after.st_size == before.st_size
        assert after.st_mtime_ns == before.st_mtime_ns
        assert ctx_mod.live_provider_ids()[0] == "gen_BBBB"
        assert ctx_mod.live_spent_oos_end() == pd.Timestamp("2026-02-27")
        # Old-generation cache writes are refused after the rotation.
        store = CacheManifestStore(tmp_path / "cache_manifest")
        store.record_cache_write(..., provider_build_id="gen_AAAA", calendar_policy_id=LEGACY_POLICY)
        new_build, new_policy = ctx_mod.live_provider_ids()
        with pytest.raises(CacheKeyMismatchError, match="provider_build_id"):
            store.assert_cache_reusable(..., provider_build_id=new_build, calendar_policy_id=new_policy)

(_write_provider copies the REAL repo provider_build.json, swaps provider_build_id, pins calendar_policy_id to the legacy frozen policy, writes day.txt ending 2026-02-27. File: 22/22 pass.)

--- Delta 3 · UNFREEZE_PLAN.md §7c (dispositions, no executable change) ---
R5 rulings recorded verbatim: M7 + M6-test-1 accepted & implemented; M1-residual (seal-record-level binding: candidate/factor id, purpose, code_hash, config_hash, data_snapshot_hash, record-level one-shot) + M6-test-2 + m3 (immutable ResearchAccessContextSnapshot passed explicitly to reads/cache/guards) = the Phase-6 gate list blocking ANY fresh-window evidence; m4 handled by the independent session (task "调和 D.features 限制测试与特权哨兵调用"); design ruling calendar_policy_id ∉ design_hash APPROVED.

RE-REVIEW QUESTIONS (Round 6, narrow)
1. M7: does content-identity keying (sha256 in the key, computed every call) fully close the stale-provenance rotation risk? Is the every-call-hash variant an acceptable (stronger) reading of your two-step spec? Any residual gap (e.g. manifest read/hash TOCTOU between the key computation and load_provider_manifest re-reading the file inside the miss path)?
2. M6-test-1: does the test prove both halves you required (same-size/same-mtime re-resolution AND old-generation cache refusal)? Anything you would add to make it non-gameable?
3. Phase-3 unlock condition: with M7 landed, is the remaining gate exactly {m4 fixed-or-waived} + the already-green Phase-2 battery — while {M1-residual, M6-test-2, m3} correctly sit on the Phase-6 gate? State the unlock condition explicitly.
4. New-issue scan on the delta only.

OUTPUT FORMAT
- Per item (M7, M6-test-1): RESOLVED / PARTIALLY RESOLVED / NOT RESOLVED with the exact remaining gap.
- New issues ranked Blocker / Major / Minor with offending text quoted and exact suggested replacement.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk, plus the explicit Phase-3 unlock condition.
```
