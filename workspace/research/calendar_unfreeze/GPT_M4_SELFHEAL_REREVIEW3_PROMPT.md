# GPT §10 re-review R3 — M4 self-heal R2 REVISE fold (TOCTOU re-check, formal inconclusive fail-closed, blank-id fail-fast)

Copy the block below into GPT-5.5 Pro. Prior rounds: R1 = REWORK (B1/M1/M2/m1, folded), R2 = REVISE (canary passed; B1/M1/m1 CLOSED, new R2-M1/R2-M2/R2-m1, folded here).

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is round 3: your R2 verdict was REVISE with two Majors (R2-M1 TOCTOU post-read race; R2-M2 inconclusive-probe under formal context) and one Minor (R2-m1 blank-id fail-fast). Verify each disposition below against the pinned commit and either close or escalate.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: claude/confident-jemison-48b622)
Review THIS immutable commit: c543504f0a54e95cf559bb0d7cbeed2944934544 — all raw links are SHA-pinned.
- https://raw.githubusercontent.com/henrydan111/quant-system/c543504f0a54e95cf559bb0d7cbeed2944934544/src/research_orchestrator/qlib_windowed_features.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c543504f0a54e95cf559bb0d7cbeed2944934544/src/research_orchestrator/sealed_backtest_runner.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c543504f0a54e95cf559bb0d7cbeed2944934544/src/data_infra/provider_context.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c543504f0a54e95cf559bb0d7cbeed2944934544/src/research_orchestrator/cache_manifest.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c543504f0a54e95cf559bb0d7cbeed2944934544/tests/research_orchestrator/test_cache_generation_self_heal.py

FRESHNESS CANARY — do this FIRST. Fetch qlib_windowed_features.py and sealed_backtest_runner.py via the SHA links and confirm ALL THREE markers before any judgment; state in your response that the canary passed:
1. qlib_windowed_features.py contains "changed during qlib_windowed_features" (the R2-M1 post-read re-check);
2. qlib_windowed_features.py contains "could not be proven" (the R2-M2 formal inconclusive fail-closed branch);
3. sealed_backtest_runner.py contains "requires non-blank" BEFORE the self._claim_if_oos(time_split) call (the R2-m1 pre-claim guard).

FINDING -> DISPOSITION MAP

R2-M1 (Major — TOCTOU: rotation after pre-read pin, before/during D.features) = IMPLEMENTED AS SPECIFIED.
After D.features and the frame trim, BEFORE record_cache_write: live_provider_ids() is re-resolved and compared to (binding_build_id, binding_policy_id); mismatch raises base CacheKeyMismatchError ("Discarding this read") — the frame is discarded and NO manifest row is written. Per your requirement this applies to the no-context sandbox path too (never write a row under possibly-stale ids; the next call re-pins under the new generation, or hard-fails at the pre-read pin when a context is active). Your required regression exists: test_live_rotation_after_dfeatures_before_record_hard_fails_without_append (first live_provider_ids call returns A, second returns B; D.features called exactly once; CacheKeyMismatchError not-subclass; manifest row count unchanged/empty), plus test_stable_generation_across_read_records_normally pinning the happy path.
Residual (unchanged, for your awareness): the re-check observes rotation via the provider manifest file's (mtime_ns,size) stat key. A publish that swaps provider BYTES without rewriting provider_build.json would be invisible to any id-based check — but such a publish already violates the attestation contract (§3.4: every publish emits a new manifest), and no id-based guard at any layer could see it.

R2-M2 (Major — inconclusive probe must fail closed under an active formal context) = IMPLEMENTED AS SPECIFIED.
The guard is now two-branch: probe None + research_ctx active -> raise base CacheKeyMismatchError ("could not be proven"), BEFORE the manifest assert and BEFORE D.features; probe None + no context -> proceed (sandbox liveness, your accepted stance); probe conclusive-mismatch -> raise for everyone (unchanged). Your required tests exist: test_active_context_inconclusive_qlib_binding_fails_before_dfeatures (D.features count == 0, manifest unchanged, not-subclass) and the no-context proceed case (test_inconclusive_probe_proceeds — your test_no_context_inconclusive_qlib_binding_still_proceeds under its R1 name). Three pre-existing context-active tests gained conclusive-and-matching probe stubs (test_d3_formal_door_clamp fixture, test_valid_read_with_context_proceeds, TestFormalRunGenerationPin) — required by the new semantics: a stubbed-qlib process genuinely cannot prove its binding, so those tests now stub the probe explicitly, exactly as your R2 "Tests that stub qlib under active context" note prescribed.
Production impact check: formal runs initialize real qlib before any D.features, so the probe is conclusive there (C.dpm.provider_uri present post-init); the fail-closed branch bites only processes that install a formal context without a provable qlib binding — which is the population you wanted refused.

R2-m1 (Minor — blank ids impossible at construction) = IMPLEMENTED, compatibility variant, STRENGTHENED ordering.
Kept the signature (defaults remain for the self._ctx-is-None sandbox path, which needs no ids) and added your fail-before-context guard with one deliberate strengthening: the ValueError fires BEFORE self._claim_if_oos(time_split), not merely before context creation. Rationale: _claim_if_oos is spend-on-attempt (§3.4) — with your placement a blank-id formal call would burn a holdout seal slot before dying on a caller typo. The guard reads only caller-supplied arguments, so no data/seal information is leaked by checking first. Test: test_blank_ids_raise_before_seal_claim (an instance whose _claim_if_oos raises AssertionError if reached; ValueError "non-blank" fires first).

WHAT CHANGED SINCE R2 (delta diff cf5414e..c543504, src+tests, authoritative)
diff --git a/src/research_orchestrator/qlib_windowed_features.py b/src/research_orchestrator/qlib_windowed_features.py
index dd904cc..37ac00c 100644
--- a/src/research_orchestrator/qlib_windowed_features.py
+++ b/src/research_orchestrator/qlib_windowed_features.py
@@ -114,14 +114,24 @@ def qlib_windowed_features(
     # provider build/policy (incl. legacy ""-rows) never validates reuse.
     live_build_id, live_policy_id = live_provider_ids()
 
-    # M4 self-heal review, GPT M2: this is a LIVE-provider door — manifest
-    # rows are stamped with live ids, so a process whose in-process Qlib
-    # binding provably points elsewhere (staged/archived provider) must not
-    # read or write here. A POSITIVE probe mismatch fails closed; an
-    # inconclusive probe (qlib stubbed / not yet initialized / config API
-    # drift) is not evidence and proceeds.
+    # M4 self-heal review, GPT M2 (+ R2 escalation): this is a LIVE-provider
+    # door — manifest rows are stamped with live ids, so a process whose
+    # in-process Qlib binding provably points elsewhere (staged/archived
+    # provider) must not read or write here. A POSITIVE probe mismatch fails
+    # closed for everyone. An INCONCLUSIVE probe (qlib stubbed / not yet
+    # initialized / config API drift) is tolerated only for no-context
+    # sandbox liveness; under an active ResearchAccessContext the binding
+    # must be PROVEN before a formal read is stamped (R2-M2).
     bound_dir = qlib_bound_provider_dir()
-    if bound_dir is not None:
+    if bound_dir is None:
+        if research_ctx is not None:
+            raise CacheKeyMismatchError(
+                "qlib_windowed_features is a live-provider door under an active "
+                "ResearchAccessContext, but the in-process Qlib provider binding "
+                "could not be proven. Refusing to stamp formal reads with live "
+                "provider ids on an inconclusive probe."
+            )
+    else:
         live_dir = live_qlib_provider_dir()
         if bound_dir != live_dir:
             raise CacheKeyMismatchError(
@@ -197,6 +207,21 @@ def qlib_windowed_features(
         date_values = pd.to_datetime(frame.index.get_level_values("datetime"))
         mask = (date_values >= pd.Timestamp(start_time)) & (date_values <= pd.Timestamp(end_time))
         frame = frame[mask].copy()
+    # R2-M1 (TOCTOU): the live provider may rotate AFTER the pre-read pin and
+    # BEFORE/DURING D.features — the frame could then hold rotated-provider
+    # bytes while the manifest row would stamp the pre-rotation binding ids.
+    # Re-check and DISCARD the read instead of recording it (applies to the
+    # no-context sandbox path too — never write a row under possibly-stale
+    # ids). The next call re-pins under the new generation (no context) or
+    # hard-fails at the pre-read pin (active context).
+    current_build_id, current_policy_id = live_provider_ids()
+    if (current_build_id, current_policy_id) != (binding_build_id, binding_policy_id):
+        raise CacheKeyMismatchError(
+            "Live provider generation changed during qlib_windowed_features "
+            f"read: live=({current_build_id}, {current_policy_id}) "
+            f"!= bound=({binding_build_id}, {binding_policy_id}). "
+            "Discarding this read; restart under a single provider generation."
+        )
     manifest.record_cache_write(
         cache_type="qlib_features",
         cache_key=cache_key,
diff --git a/src/research_orchestrator/sealed_backtest_runner.py b/src/research_orchestrator/sealed_backtest_runner.py
index 2915637..6a067f1 100644
--- a/src/research_orchestrator/sealed_backtest_runner.py
+++ b/src/research_orchestrator/sealed_backtest_runner.py
@@ -95,6 +95,18 @@ class SealedBacktestRunner:
         ``pipeline_args`` is a dict, or
         ``pipeline_fn(time_split, self._ctx, pipeline_args)`` otherwise.
         """
+        # R2-m1 (M4 self-heal review): a formal context without provider
+        # provenance would only fail at the FIRST read (B1 pin) with a
+        # confusing "generation changed" message — fail at construction
+        # instead, and BEFORE _claim_if_oos so a malformed call cannot burn
+        # a spend-on-attempt seal slot.
+        if self._ctx is not None and (
+            not str(provider_build_id).strip() or not str(calendar_policy_id).strip()
+        ):
+            raise ValueError(
+                "run_workspace_pipeline formal context requires non-blank "
+                "provider_build_id and calendar_policy_id."
+            )
         self._claim_if_oos(time_split)
 
         if self._ctx is None:
diff --git a/tests/research_orchestrator/test_cache_generation_self_heal.py b/tests/research_orchestrator/test_cache_generation_self_heal.py
index b69f5ab..1f303b9 100644
--- a/tests/research_orchestrator/test_cache_generation_self_heal.py
+++ b/tests/research_orchestrator/test_cache_generation_self_heal.py
@@ -49,6 +49,9 @@ from src.research_orchestrator.research_access_context import (
     ResearchAccessContext,
     research_access_context,
 )
+# Module-level: pulls real qlib transitively (data_feeder), so it must import
+# BEFORE the autouse fixture swaps sys.modules["qlib"] for the stub.
+from src.research_orchestrator.sealed_backtest_runner import SealedBacktestRunner
 
 BOUNDARY = pd.Timestamp("2026-02-27")
 LIVE_BUILD = "depth9_new_build"
@@ -166,12 +169,24 @@ def _pin_ctx(build_id: str, policy_id: str) -> ResearchAccessContext:
     )
 
 
+def _stub_conclusive_live_binding(monkeypatch) -> None:
+    """R2-M2: an active-context read requires a PROVEN live Qlib binding —
+    stub the probe conclusive-and-matching for tests that exercise layers
+    behind it."""
+    import src.data_infra.provider_context as ctx_mod
+
+    same = Path("E:/live_provider")
+    monkeypatch.setattr(ctx_mod, "qlib_bound_provider_dir", lambda: same)
+    monkeypatch.setattr(ctx_mod, "live_qlib_provider_dir", lambda: same)
+
+
 class TestFormalRunGenerationPin:
     """GPT B1: an active ResearchAccessContext pins the run's provider
     generation — a live rotation while the context is active hard-fails
     BEFORE D.features, with the base class (not swallowable)."""
 
-    def test_mid_run_rotation_hard_fails_before_dfeatures(self, tmp_path):
+    def test_mid_run_rotation_hard_fails_before_dfeatures(self, tmp_path, monkeypatch):
+        _stub_conclusive_live_binding(monkeypatch)
         # Run started under ctx_build; live has rotated to LIVE_BUILD.
         manifest = _seed_row(tmp_path, build_id="ctx_build", policy_id=LIVE_POLICY)
         calls = {"n": 0}
@@ -190,8 +205,9 @@ class TestFormalRunGenerationPin:
         assert len(manifest.list_events(cache_key=_cache_key())) == 1
 
     def test_formal_context_under_current_generation_still_heals_stale_rows(
-        self, tmp_path, caplog
+        self, tmp_path, caplog, monkeypatch
     ):
+        _stub_conclusive_live_binding(monkeypatch)
         # Run started AFTER the rotation: the context pins the live
         # generation, so a PRE-run stale row self-heals (GPT answer 4c: formal
         # runs may self-heal only when the context was built under the new
@@ -206,6 +222,68 @@ class TestFormalRunGenerationPin:
         assert rows.iloc[-1]["provider_build_id"] == LIVE_BUILD
 
 
+class TestToctouPostReadPin:
+    """GPT R2-M1: the live provider may rotate AFTER the pre-read pin and
+    BEFORE/DURING D.features — the read must be DISCARDED (no manifest row
+    under possibly-stale ids), sandbox path included."""
+
+    def test_live_rotation_after_dfeatures_before_record_hard_fails_without_append(
+        self, tmp_path, monkeypatch
+    ):
+        import src.data_infra.provider_context as ctx_mod
+
+        calls = {"ids": 0, "d": 0}
+
+        def flipping_ids():
+            calls["ids"] += 1
+            if calls["ids"] == 1:  # pre-read pin
+                return (LIVE_BUILD, LIVE_POLICY)
+            return ("rotated_mid_read", LIVE_POLICY)  # post-read re-check
+
+        monkeypatch.setattr(ctx_mod, "live_provider_ids", flipping_ids)
+
+        def counting_features(*a, **k):
+            calls["d"] += 1
+            return pd.DataFrame()
+
+        sys.modules["qlib.data"].D = types.SimpleNamespace(features=counting_features)
+        with pytest.raises(
+            CacheKeyMismatchError, match="changed during qlib_windowed_features"
+        ) as ei:
+            _call(tmp_path)
+        assert not isinstance(ei.value, ProviderGenerationMismatchError)
+        assert calls["d"] == 1  # the read happened, then was discarded
+        # No row recorded under the stale binding ids.
+        assert CacheManifestStore(tmp_path).list_events(cache_key=_cache_key()).empty
+
+    def test_stable_generation_across_read_records_normally(self, tmp_path):
+        _call(tmp_path)
+        rows = CacheManifestStore(tmp_path).list_events(cache_key=_cache_key())
+        assert len(rows) == 1
+        assert rows.iloc[-1]["provider_build_id"] == LIVE_BUILD
+
+
+class TestRunWorkspacePipelineBlankIds:
+    """GPT R2-m1: a formal (ctx-bearing) run_workspace_pipeline call with
+    blank provider ids fails at construction — BEFORE the spend-on-attempt
+    seal claim, and with a message naming the real defect."""
+
+    def test_blank_ids_raise_before_seal_claim(self):
+        runner = SealedBacktestRunner.__new__(SealedBacktestRunner)
+        runner._ctx = object()  # non-None sentinel: the guard fires before any use
+
+        def _boom(*a, **k):
+            raise AssertionError("seal must NOT be claimed on a malformed call")
+
+        runner._claim_if_oos = _boom
+        with pytest.raises(ValueError, match="non-blank"):
+            runner.run_workspace_pipeline(
+                pipeline_fn=lambda **k: None,
+                time_split={},
+                pipeline_args={},
+            )
+
+
 class TestLatestRowAppendOrder:
     """GPT M1: "latest" = append order under file_lock, not the second-
     precision recorded_at (ambiguous same-second; wrong under clock skew)."""
@@ -259,13 +337,38 @@ class TestLiveBindingGuard:
         assert _call(tmp_path).empty
 
     def test_inconclusive_probe_proceeds(self, tmp_path):
+        # (= GPT's test_no_context_inconclusive_qlib_binding_still_proceeds.)
         # The autouse qlib stub has no qlib.config submodule → probe is
-        # inconclusive → the read proceeds (not evidence of a wrong binding).
+        # inconclusive → a NO-CONTEXT sandbox read proceeds (not evidence of
+        # a wrong binding; R2-M2 keeps fail-open only here).
         import src.data_infra.provider_context as ctx_mod
 
         assert ctx_mod.qlib_bound_provider_dir() is None
         assert _call(tmp_path).empty
 
+    def test_active_context_inconclusive_qlib_binding_fails_before_dfeatures(
+        self, tmp_path
+    ):
+        # R2-M2 escalation: under an active ResearchAccessContext the binding
+        # must be PROVEN — an inconclusive probe hard-fails before D.features
+        # and before any manifest write.
+        import src.data_infra.provider_context as ctx_mod
+
+        assert ctx_mod.qlib_bound_provider_dir() is None  # stub qlib: no config
+        calls = {"d": 0}
+
+        def counting_features(*a, **k):
+            calls["d"] += 1
+            return pd.DataFrame()
+
+        sys.modules["qlib.data"].D = types.SimpleNamespace(features=counting_features)
+        with research_access_context(_pin_ctx(LIVE_BUILD, LIVE_POLICY)):
+            with pytest.raises(CacheKeyMismatchError, match="could not be proven") as ei:
+                _call(tmp_path)
+        assert not isinstance(ei.value, ProviderGenerationMismatchError)
+        assert calls["d"] == 0
+        assert CacheManifestStore(tmp_path).list_events(cache_key=_cache_key()).empty
+
     def test_probe_reads_dpm_provider_uri_dict(self, tmp_path, monkeypatch):
         import src.data_infra.provider_context as ctx_mod
 
diff --git a/tests/research_orchestrator/test_d3_formal_door_clamp.py b/tests/research_orchestrator/test_d3_formal_door_clamp.py
index b19a034..93bcca2 100644
--- a/tests/research_orchestrator/test_d3_formal_door_clamp.py
+++ b/tests/research_orchestrator/test_d3_formal_door_clamp.py
@@ -37,6 +37,14 @@ def _stub_boundary_and_qlib(monkeypatch, tmp_path):
     monkeypatch.setattr(
         ctx_mod, "live_provider_ids", lambda: ("test_build", "frozen_20260630_thaw_step1")
     )
+    # R2-M2: active-context reads require a PROVEN live Qlib binding — stub
+    # the probe conclusive-and-matching so the clamp layers under test are
+    # reachable with the stubbed qlib below.
+    from pathlib import Path as _Path
+
+    _same = _Path("E:/live_provider")
+    monkeypatch.setattr(ctx_mod, "qlib_bound_provider_dir", lambda: _same)
+    monkeypatch.setattr(ctx_mod, "live_qlib_provider_dir", lambda: _same)
 
     # Stub qlib.data.D.features so no provider is touched.
     fake_frame = pd.DataFrame()
diff --git a/tests/research_orchestrator/test_research_access_context.py b/tests/research_orchestrator/test_research_access_context.py
index 80020cc..eaf463e 100644
--- a/tests/research_orchestrator/test_research_access_context.py
+++ b/tests/research_orchestrator/test_research_access_context.py
@@ -276,9 +276,20 @@ class TestQlibWindowedFeaturesEnforcement:
         )
         # B1 generation pin: the live ids must equal the context's pinned ids
         # for the read to proceed (this context uses the test id "prod_test").
+        # R2-M2: an active-context read also requires a PROVEN live Qlib
+        # binding — stub the probe conclusive-and-matching.
+        from pathlib import Path as _Path
+
+        _same = _Path("E:/live_provider")
         with patch("qlib.data.D") as mock_d, patch(
             "src.data_infra.provider_context.live_provider_ids",
             return_value=("prod_test", "frozen_20260227_system_build"),
+        ), patch(
+            "src.data_infra.provider_context.qlib_bound_provider_dir",
+            return_value=_same,
+        ), patch(
+            "src.data_infra.provider_context.live_qlib_provider_dir",
+            return_value=_same,
         ):
             mock_d.features.return_value = mock_frame
             with research_access_context(ctx):

TEST EVIDENCE
- tests/research_orchestrator FULL: 296 passed, 0 failed (R2 state: 292; +4 = TOCTOU discard + stable-generation happy path + formal-inconclusive + blank-id-pre-claim).
- tests/backtest_engine/test_preload_hardening.py + test_pr8_runtime_enforcement.py + tests/data_infra/test_provider_manifest.py: 51 passed.

REVIEW QUESTIONS
1. R2-M1 closure: is the post-read re-check airtight given the binding-id semantics (context ids on match, live ids otherwise)? Note the window between the re-check and the record_cache_write append is a pure metadata write — no further provider reads occur.
2. R2-M2 closure: any hole in the two-branch guard ordering (probe branch runs before the B1 pin, both before the manifest assert)? Is the production-impact claim sound?
3. R2-m1: accept the pre-claim strengthening, or do you see a reason the guard must sit after _claim_if_oos?
4. Any NEW hole introduced by this delta only.
5. Final: SHIP / REVISE / REWORK + the single most important residual risk.
```
