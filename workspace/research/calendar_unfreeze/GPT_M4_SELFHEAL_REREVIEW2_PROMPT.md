# GPT §10 re-review R2 — M4 self-heal REWORK fold (B1 run-pin, M1 append-order, M2 binding guard, m1)

Copy the block below into GPT-5.5 Pro. Branch `claude/confident-jemison-48b622` is pushed with the R1 fold; all raw links resolve. R1 prompt: `GPT_M4_SELFHEAL_REVIEW_PROMPT.md` (same directory).

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is round 2: you issued REWORK on the M4 provider-rotation self-heal with Blocker B1, Majors M1/M2, Minor m1. Verify each disposition below against the live branch code and either close the finding or escalate.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: claude/confident-jemison-48b622)
Raw links (substitute the path):
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/src/research_orchestrator/qlib_windowed_features.py
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/src/research_orchestrator/cache_manifest.py
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/src/data_infra/provider_context.py
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/tests/research_orchestrator/test_cache_generation_self_heal.py
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/tests/research_orchestrator/test_research_access_context.py
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/src/research_orchestrator/sealed_backtest_runner.py
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/src/research_orchestrator/promotion_evidence.py

SELF-REVIEW PREFLIGHT — completed before this re-review: verdict = clean for GPT. Full tests/research_orchestrator 292 passed 0 failed (R1 state: 285; +7 = the new B1/M1/M2 pins); preload_hardening + pr8_runtime_enforcement + provider_manifest 51 passed. Residual concerns are listed per finding below — the most substantive is the archived-provider replay consequence under DISPOSITION B1/M2.

FINDING -> DISPOSITION MAP (verify each against the code)

B1 (Blocker — formal reads must pin the run's provider generation) = IMPLEMENTED AS SPECIFIED.
qlib_windowed_features now, after resolving live ids and BEFORE the manifest assert: when research_ctx is not None, compares (live_build_id, live_policy_id) against (str(research_ctx.provider_build_id), str(research_ctx.calendar_policy_id)); mismatch raises base-class CacheKeyMismatchError ("changed during an active ResearchAccessContext") — not the swallowable subclass. On match, the CONTEXT ids become the binding ids used for BOTH assert_cache_reusable and record_cache_write. With no context, live ids bind (sandbox self-heal preserved). Your exact requested tests exist: test_mid_run_rotation_hard_fails_before_dfeatures (D.features call count == 0, manifest row count unchanged, not-subclass assertion) and test_formal_context_under_current_generation_still_heals_stale_rows (your answer-4c semantics: a formal context built under the CURRENT generation still self-heals pre-run stale rows). The pre-existing sandbox no-context heal tests are unchanged and passing (your requested test_sandbox_no_context_still_self_heals is covered by TestRotationSelfHeal::test_rotated_row_heals_and_rebinds — no context active in that class).
Points for your attention:
(a) Blank context ids: ResearchAccessContext.provider_build_id/calendar_policy_id are required constructor fields but a caller CAN pass "". The pin compares unconditionally, so a blank-pinned context now hard-fails at the first read (message shows the '' ids). We judged this correct fail-closed behavior (a formal context without a pinned generation is itself a contract violation) rather than silently falling back to live binding. Two latent blank sources exist: sealed_backtest_runner.run_workspace_pipeline's provider_build_id/calendar_policy_id kwargs default to "" (no current in-repo callers omit... no current in-repo callers AT ALL were found outside tests), and promotion_evidence builds its context via prov.get("provider_build_id", "") from a loaded provider manifest (schema-required key, so "" only on malformed manifests). Confirm you accept unconditional-compare over blank-tolerant fallback, or require the sealed-runner defaults be made mandatory now.
(b) Deliberate consequence: a future promotion/replay reproduction running against an ARCHIVED provider (post-unfreeze, provider calendar_end == OOS_END != live) is refused at this door by B1 (context pins archived ids != live) and by M2 (process bound to archived dir != live dir). This matches provider_context's documented contract ("formal artifact replay must NEVER route through these helpers — it uses the artifact-recorded ids"); the artifact-recorded-ids replay door is separate Phase 3/4 unfreeze work. Confirm this is acceptable sequencing rather than a blocker on this fix.

M1 (Major — latest row by append order, not second-precision timestamp) = IMPLEMENTED (your lighter fix).
assert_cache_reusable now uses `latest = events.iloc[-1]` with a comment stating the invariant (record_cache_write appends under file_lock; list_events preserves parquet row order). Both tests that inspected the latest row were switched to iloc[-1]. Your requested discriminating test exists as test_latest_row_uses_append_order_not_second_precision_timestamp — ADVERSARIAL variant: the stale first row carries a LATER recorded_at than the fresh appended row (clock skew), so a timestamp sort would select the stale row and raise while append order passes. (A same-second test would NOT discriminate: pandas stable sort preserves append order on equal keys.)

M2 (Major — prove/document the live-binding claim) = IMPLEMENTED as a positive-evidence fail-closed probe.
New in provider_context.py: live_qlib_provider_dir() (resolved live dir) and qlib_bound_provider_dir() — best-effort probe of the in-process Qlib binding via qlib.config C (C.dpm.provider_uri, then C.get("provider_uri"); dict/str normalized; expanduser().resolve(); never raises; returns None when inconclusive: qlib absent/stubbed/uninitialized/config API drift). The door raises base-class CacheKeyMismatchError ("live-provider door") on a POSITIVE mismatch, BEFORE the manifest assert and D.features; an inconclusive probe proceeds (documented: not evidence). Rationale for fail-open-on-inconclusive: a hard requirement on the probe would couple every read to qlib-version internals; the probe is a belt over the documented contract, and all in-repo EventDriven/parity flows bind ROOT/data/qlib_data (audited: guorn_parity_rung1/2/6, guorn_verify_02b all init the live dir). 4 tests: positive mismatch fails closed (not-subclass), matching binding proceeds, inconclusive proceeds, dict-form dpm probe unit test. Confirm the fail-open-on-inconclusive stance or require hard-fail when the probe is inconclusive.

m1 (Minor — warning should carry run metadata) = IMPLEMENTED.
The self-heal WARNING now logs stage plus getattr(research_ctx, "run_id", "")/step_id alongside key, binding ids, and the refused stale row.

WHAT CHANGED SINCE R1 (delta diff, authoritative)
diff --git a/src/data_infra/provider_context.py b/src/data_infra/provider_context.py
index d859171..8ab6ba1 100644
--- a/src/data_infra/provider_context.py
+++ b/src/data_infra/provider_context.py
@@ -114,3 +114,45 @@ def refresh_live_provider_context() -> None:
     """Explicit invalidation hook for the safe-publish ceremony (R4-M3 option C
     belt — the stat-key mechanism already invalidates on manifest rewrite)."""
     _CACHE.clear()
+
+
+def live_qlib_provider_dir() -> Path:
+    """The live provider directory these helpers describe, resolved."""
+    return _qlib_dir().resolve()
+
+
+def qlib_bound_provider_dir() -> Optional[Path]:
+    """Best-effort probe of the IN-PROCESS Qlib provider binding.
+
+    Returns the resolved directory Qlib was ``init``-ed against, or ``None``
+    when the probe is inconclusive (qlib absent/stubbed, not yet initialized,
+    or config API drift). Never raises. Consumers treat a POSITIVE mismatch
+    against ``live_qlib_provider_dir()`` as fail-closed evidence that the
+    process is reading a staged/archived provider while stamping live ids
+    (M4 self-heal review, GPT M2); an inconclusive probe is NOT evidence.
+    """
+    try:
+        from qlib.config import C  # probe only, never at import time
+    except Exception:
+        return None
+    candidates: list[object] = []
+    try:
+        dpm = getattr(C, "dpm", None)
+        if dpm is not None:
+            candidates.append(getattr(dpm, "provider_uri", None))
+    except Exception:
+        pass
+    try:
+        candidates.append(C.get("provider_uri", None))
+    except Exception:
+        pass
+    for cand in candidates:
+        if isinstance(cand, dict):
+            cand = cand.get("__DEFAULT_FREQ") or next(iter(cand.values()), None)
+        if not cand:
+            continue
+        try:
+            return Path(str(cand)).expanduser().resolve()
+        except Exception:
+            continue
+    return None
diff --git a/src/research_orchestrator/cache_manifest.py b/src/research_orchestrator/cache_manifest.py
index 78f9171..b1a0655 100644
--- a/src/research_orchestrator/cache_manifest.py
+++ b/src/research_orchestrator/cache_manifest.py
@@ -291,7 +291,12 @@ class CacheManifestStore:
         events = self.list_events(cache_key=cache_key, cache_path=cache_path)
         if events.empty:
             return
-        latest = events.sort_values("recorded_at").iloc[-1]
+        # GPT M1 (M4 self-heal review): "latest" = APPEND order, not the
+        # second-precision recorded_at (ambiguous for same-second rows, wrong
+        # under clock skew). record_cache_write appends under file_lock and
+        # list_events preserves parquet row order, so iloc[-1] is the last
+        # write.
+        latest = events.iloc[-1]
         if cache_type != "qlib_features":
             if str(latest["design_hash"]) != str(cache_context.design_hash):
                 raise CacheKeyMismatchError(
diff --git a/src/research_orchestrator/qlib_windowed_features.py b/src/research_orchestrator/qlib_windowed_features.py
index 63f28dc..dd904cc 100644
--- a/src/research_orchestrator/qlib_windowed_features.py
+++ b/src/research_orchestrator/qlib_windowed_features.py
@@ -10,6 +10,7 @@ import pandas as pd
 
 from src.research_orchestrator.cache_manifest import (
     CacheContext,
+    CacheKeyMismatchError,
     CacheManifestStore,
     ProviderGenerationMismatchError,
     get_cache_context,
@@ -82,7 +83,12 @@ def qlib_windowed_features(
     # "sandbox/no-context calls skip this check" behavior is exactly the leak
     # the pre-publish wall exists to close. Boundary resolution failure fails
     # closed too (the resolver raises).
-    from src.data_infra.provider_context import live_provider_ids, live_spent_oos_end
+    from src.data_infra.provider_context import (
+        live_provider_ids,
+        live_qlib_provider_dir,
+        live_spent_oos_end,
+        qlib_bound_provider_dir,
+    )
 
     boundary_end = live_spent_oos_end()
     if pd.Timestamp(end_time) > boundary_end:
@@ -107,6 +113,46 @@ def qlib_windowed_features(
     # M4 provider-generation binding: a manifest row written under another
     # provider build/policy (incl. legacy ""-rows) never validates reuse.
     live_build_id, live_policy_id = live_provider_ids()
+
+    # M4 self-heal review, GPT M2: this is a LIVE-provider door — manifest
+    # rows are stamped with live ids, so a process whose in-process Qlib
+    # binding provably points elsewhere (staged/archived provider) must not
+    # read or write here. A POSITIVE probe mismatch fails closed; an
+    # inconclusive probe (qlib stubbed / not yet initialized / config API
+    # drift) is not evidence and proceeds.
+    bound_dir = qlib_bound_provider_dir()
+    if bound_dir is not None:
+        live_dir = live_qlib_provider_dir()
+        if bound_dir != live_dir:
+            raise CacheKeyMismatchError(
+                "qlib_windowed_features is a live-provider door: the in-process "
+                f"Qlib binding {bound_dir} != live provider {live_dir}. Reads "
+                "against staged/archived providers must not stamp live ids — "
+                "use a non-formal parity helper instead."
+            )
+
+    # M4 self-heal review, GPT B1: a formal run pins its provider generation
+    # in the ResearchAccessContext at run start. If the live provider rotates
+    # WHILE the context is active, every later read hard-fails (base class —
+    # the self-heal catch below cannot swallow it): one evidence artifact must
+    # never mix provider generations. With no active context (sandbox live
+    # reads), the live ids are the binding.
+    if research_ctx is not None:
+        expected_build_id = str(research_ctx.provider_build_id)
+        expected_policy_id = str(research_ctx.calendar_policy_id)
+        if (live_build_id, live_policy_id) != (expected_build_id, expected_policy_id):
+            raise CacheKeyMismatchError(
+                "Live provider generation changed during an active "
+                f"ResearchAccessContext: live=({live_build_id}, {live_policy_id}) "
+                f"!= context=({expected_build_id}, {expected_policy_id}). "
+                "Abort this formal run and restart under a single provider generation."
+            )
+        binding_build_id = expected_build_id
+        binding_policy_id = expected_policy_id
+    else:
+        binding_build_id = live_build_id
+        binding_policy_id = live_policy_id
+
     try:
         manifest.assert_cache_reusable(
             cache_key=cache_key,
@@ -116,11 +162,12 @@ def qlib_windowed_features(
             window_start=start_time,
             window_end=end_time,
             cache_type="qlib_features",
-            provider_build_id=live_build_id,
-            calendar_policy_id=live_policy_id,
+            provider_build_id=binding_build_id,
+            calendar_policy_id=binding_policy_id,
         )
     except ProviderGenerationMismatchError as exc:
-        # Provider rotated since this key's latest manifest row. This door
+        # Provider rotated since this key's latest manifest row (BEFORE this
+        # run/context started — a mid-run rotation is caught above). This door
         # holds no cached artifact — D.features below always recomputes from
         # the live provider — so a stale-generation row must not brick the key
         # permanently: proceed, and record_cache_write below appends a fresh
@@ -130,10 +177,14 @@ def qlib_windowed_features(
         # violations still propagate.
         logger.warning(
             "cache generation rotated for %s — recomputing from the live "
-            "provider and re-binding to (%s, %s); refused stale row: %s",
+            "provider and re-binding to (%s, %s); stage=%s run_id=%s "
+            "step_id=%s; refused stale row: %s",
             cache_key,
-            live_build_id,
-            live_policy_id,
+            binding_build_id,
+            binding_policy_id,
+            stage,
+            getattr(research_ctx, "run_id", ""),
+            getattr(research_ctx, "step_id", ""),
             exc,
         )
     frame = D.features(  # noqa: bare-qlib-features  (canonical chokepoint)
@@ -154,7 +205,7 @@ def qlib_windowed_features(
         stage=stage,
         window_start=start_time,
         window_end=end_time,
-        provider_build_id=live_build_id,
-        calendar_policy_id=live_policy_id,
+        provider_build_id=binding_build_id,
+        calendar_policy_id=binding_policy_id,
     )
     return frame
diff --git a/tests/research_orchestrator/test_cache_generation_self_heal.py b/tests/research_orchestrator/test_cache_generation_self_heal.py
index 2f6c324..b69f5ab 100644
--- a/tests/research_orchestrator/test_cache_generation_self_heal.py
+++ b/tests/research_orchestrator/test_cache_generation_self_heal.py
@@ -9,7 +9,8 @@ the depth9_20260630_sharecap_reanchor_20260701 publish bricked every
 pre-existing key; EventDrivenBacktester preload_features(strict=False)
 silently degraded to per-day D.features).
 
-Contract now:
+Contract now (incl. the GPT REWORK round: B1 run-generation pin, M1 append
+-order latest row, M2 live-binding guard):
   1. generation mismatch (rotated id or legacy "" row) -> WARNING +
      recompute from the live provider + append a fresh row = self-healed;
      the second read passes silently.
@@ -17,12 +18,21 @@ Contract now:
      unchanged (the subclass is raised only after those checks pass).
   3. the store itself still raises for every caller — the self-heal lives
      ONLY in the recompute-only door.
+  4. B1: an active ResearchAccessContext pins the run's provider generation;
+     a live rotation while the context is active hard-fails BEFORE D.features
+     (base class — not swallowable by the self-heal catch). Formal contexts
+     built under the CURRENT generation still self-heal pre-run stale rows.
+  5. M1: "latest row" = append order under file_lock, not the second-
+     precision recorded_at timestamp.
+  6. M2: a POSITIVE probe that the in-process Qlib binding points at a
+     non-live provider dir fails closed; an inconclusive probe proceeds.
 """
 from __future__ import annotations
 
 import logging
 import sys
 import types
+from pathlib import Path
 
 import pandas as pd
 import pytest
@@ -32,8 +42,13 @@ from src.research_orchestrator.cache_manifest import (
     CacheContext,
     CacheKeyMismatchError,
     CacheManifestStore,
+    ProviderGenerationMismatchError,
 )
 from src.research_orchestrator.qlib_windowed_features import _deterministic_cache_path
+from src.research_orchestrator.research_access_context import (
+    ResearchAccessContext,
+    research_access_context,
+)
 
 BOUNDARY = pd.Timestamp("2026-02-27")
 LIVE_BUILD = "depth9_new_build"
@@ -107,7 +122,7 @@ class TestRotationSelfHeal:
 
         rows = manifest.list_events(cache_key=_cache_key())
         assert len(rows) == 2  # stale row kept as audit trail + fresh row
-        latest = rows.sort_values("recorded_at").iloc[-1]
+        latest = rows.iloc[-1]  # append order (GPT M1), not timestamp sort
         assert latest["provider_build_id"] == LIVE_BUILD
         assert latest["calendar_policy_id"] == LIVE_POLICY
 
@@ -129,7 +144,7 @@ class TestRotationSelfHeal:
         with caplog.at_level(logging.WARNING, logger=qwf_mod.__name__):
             _call(tmp_path)
         assert sum(WARNING_MARK in r.message for r in caplog.records) == 1
-        latest = manifest.list_events(cache_key=_cache_key()).sort_values("recorded_at").iloc[-1]
+        latest = manifest.list_events(cache_key=_cache_key()).iloc[-1]
         assert latest["provider_build_id"] == LIVE_BUILD
 
     def test_no_prior_row_stays_silent(self, tmp_path, caplog):
@@ -138,6 +153,130 @@ class TestRotationSelfHeal:
         assert not any(WARNING_MARK in r.message for r in caplog.records)
 
 
+def _pin_ctx(build_id: str, policy_id: str) -> ResearchAccessContext:
+    return ResearchAccessContext(
+        run_id="r1",
+        step_id="s1",
+        stage="is_validation",
+        design_hash="d" * 8,
+        allowed_start=pd.Timestamp("2021-01-01"),
+        allowed_end=pd.Timestamp("2021-12-31"),
+        provider_build_id=build_id,
+        calendar_policy_id=policy_id,
+    )
+
+
+class TestFormalRunGenerationPin:
+    """GPT B1: an active ResearchAccessContext pins the run's provider
+    generation — a live rotation while the context is active hard-fails
+    BEFORE D.features, with the base class (not swallowable)."""
+
+    def test_mid_run_rotation_hard_fails_before_dfeatures(self, tmp_path):
+        # Run started under ctx_build; live has rotated to LIVE_BUILD.
+        manifest = _seed_row(tmp_path, build_id="ctx_build", policy_id=LIVE_POLICY)
+        calls = {"n": 0}
+
+        def counting_features(*a, **k):
+            calls["n"] += 1
+            return pd.DataFrame()
+
+        sys.modules["qlib.data"].D = types.SimpleNamespace(features=counting_features)
+        with research_access_context(_pin_ctx("ctx_build", LIVE_POLICY)):
+            with pytest.raises(CacheKeyMismatchError, match="changed during an active") as ei:
+                _call(tmp_path)
+        assert not isinstance(ei.value, ProviderGenerationMismatchError)
+        assert calls["n"] == 0  # D.features never reached
+        # Nothing appended — the manifest still holds only the seeded row.
+        assert len(manifest.list_events(cache_key=_cache_key())) == 1
+
+    def test_formal_context_under_current_generation_still_heals_stale_rows(
+        self, tmp_path, caplog
+    ):
+        # Run started AFTER the rotation: the context pins the live
+        # generation, so a PRE-run stale row self-heals (GPT answer 4c: formal
+        # runs may self-heal only when the context was built under the new
+        # provider id).
+        manifest = _seed_row(tmp_path, build_id="old_build", policy_id="old_policy")
+        with caplog.at_level(logging.WARNING, logger=qwf_mod.__name__):
+            with research_access_context(_pin_ctx(LIVE_BUILD, LIVE_POLICY)):
+                _call(tmp_path)
+        assert sum(WARNING_MARK in r.message for r in caplog.records) == 1
+        rows = manifest.list_events(cache_key=_cache_key())
+        assert len(rows) == 2
+        assert rows.iloc[-1]["provider_build_id"] == LIVE_BUILD
+
+
+class TestLatestRowAppendOrder:
+    """GPT M1: "latest" = append order under file_lock, not the second-
+    precision recorded_at (ambiguous same-second; wrong under clock skew)."""
+
+    def test_latest_row_uses_append_order_not_second_precision_timestamp(self, tmp_path):
+        manifest = _seed_row(tmp_path, build_id="old_build", policy_id="old_policy")
+        _seed_row(tmp_path, build_id=LIVE_BUILD, policy_id=LIVE_POLICY)
+        frame = pd.read_parquet(manifest.log_path)
+        # Adversarial clock skew: the STALE first row carries a LATER
+        # recorded_at than the fresh appended row. A timestamp sort would pick
+        # the stale row (raise); append order picks the fresh row (pass).
+        frame.loc[0, "recorded_at"] = "2026-07-02 00:00:01"
+        frame.loc[1, "recorded_at"] = "2026-07-02 00:00:00"
+        frame.to_parquet(manifest.log_path, index=False)
+        manifest.assert_cache_reusable(  # must NOT raise
+            cache_key=_cache_key(),
+            cache_path=_cache_key(),
+            cache_context=CacheContext(),
+            stage=STAGE,
+            window_start=START,
+            window_end=END,
+            cache_type="qlib_features",
+            provider_build_id=LIVE_BUILD,
+            calendar_policy_id=LIVE_POLICY,
+        )
+
+
+class TestLiveBindingGuard:
+    """GPT M2: a POSITIVE probe that the in-process Qlib binding points at a
+    non-live provider dir fails closed; an inconclusive probe proceeds."""
+
+    def test_positive_mismatch_fails_closed(self, tmp_path, monkeypatch):
+        import src.data_infra.provider_context as ctx_mod
+
+        monkeypatch.setattr(
+            ctx_mod, "qlib_bound_provider_dir", lambda: Path("E:/archived_provider_slot")
+        )
+        monkeypatch.setattr(
+            ctx_mod, "live_qlib_provider_dir", lambda: Path("E:/live_provider")
+        )
+        with pytest.raises(CacheKeyMismatchError, match="live-provider door") as ei:
+            _call(tmp_path)
+        assert not isinstance(ei.value, ProviderGenerationMismatchError)
+
+    def test_matching_binding_proceeds(self, tmp_path, monkeypatch):
+        import src.data_infra.provider_context as ctx_mod
+
+        same = Path("E:/live_provider")
+        monkeypatch.setattr(ctx_mod, "qlib_bound_provider_dir", lambda: same)
+        monkeypatch.setattr(ctx_mod, "live_qlib_provider_dir", lambda: same)
+        assert _call(tmp_path).empty
+
+    def test_inconclusive_probe_proceeds(self, tmp_path):
+        # The autouse qlib stub has no qlib.config submodule → probe is
+        # inconclusive → the read proceeds (not evidence of a wrong binding).
+        import src.data_infra.provider_context as ctx_mod
+
+        assert ctx_mod.qlib_bound_provider_dir() is None
+        assert _call(tmp_path).empty
+
+    def test_probe_reads_dpm_provider_uri_dict(self, tmp_path, monkeypatch):
+        import src.data_infra.provider_context as ctx_mod
+
+        cfg_mod = types.ModuleType("qlib.config")
+        cfg_mod.C = types.SimpleNamespace(
+            dpm=types.SimpleNamespace(provider_uri={"__DEFAULT_FREQ": str(tmp_path)})
+        )
+        monkeypatch.setitem(sys.modules, "qlib.config", cfg_mod)
+        assert ctx_mod.qlib_bound_provider_dir() == tmp_path.resolve()
+
+
 class TestDoorStillFailsClosed:
     def test_stage_mismatch_propagates(self, tmp_path):
         _seed_row(tmp_path, build_id=LIVE_BUILD, policy_id=LIVE_POLICY,
diff --git a/tests/research_orchestrator/test_research_access_context.py b/tests/research_orchestrator/test_research_access_context.py
index 57e97ae..80020cc 100644
--- a/tests/research_orchestrator/test_research_access_context.py
+++ b/tests/research_orchestrator/test_research_access_context.py
@@ -274,7 +274,12 @@ class TestQlibWindowedFeaturesEnforcement:
                 names=["instrument", "datetime"],
             ),
         )
-        with patch("qlib.data.D") as mock_d:
+        # B1 generation pin: the live ids must equal the context's pinned ids
+        # for the read to proceed (this context uses the test id "prod_test").
+        with patch("qlib.data.D") as mock_d, patch(
+            "src.data_infra.provider_context.live_provider_ids",
+            return_value=("prod_test", "frozen_20260227_system_build"),
+        ):
             mock_d.features.return_value = mock_frame
             with research_access_context(ctx):
                 out = qwf.qlib_windowed_features(

TEST EVIDENCE
- tests/research_orchestrator FULL: 292 passed, 0 failed (R1: 285; the +7 are TestFormalRunGenerationPin x2, TestLatestRowAppendOrder x1, TestLiveBindingGuard x4).
- tests/backtest_engine/test_preload_hardening.py + test_pr8_runtime_enforcement.py + tests/data_infra/test_provider_manifest.py: 51 passed.
- One pre-existing test updated: test_valid_read_with_context_proceeds now stubs live_provider_ids to match its context's test id "prod_test" (required by B1 — the context uses a fake id while the real manifest is live).

REVIEW QUESTIONS
1. B1 closure: is the pin airtight — any path where a context-active read can reach D.features or record_cache_write under ids != the context pin? (Note the binding ids are the CONTEXT ids on match, so even a live flip between the pin check and record_cache_write cannot stamp rotated ids.)
2. The two B1 attention points (blank-id contexts; archived-provider replay refusal) — close or escalate, with the exact change you require if escalating.
3. M2 stance: fail-open on inconclusive probe — acceptable belt, or must it hard-fail? If hard-fail, state how tests/processes that legitimately run without qlib initialized should behave.
4. Any NEW hole introduced by the delta itself (ordering of the M2 guard vs B1 pin vs assert; the getattr defaults in the warning; iloc[-1] on a filtered/reset_index frame).
5. Final: SHIP / REVISE / REWORK + the single most important residual risk.
```
