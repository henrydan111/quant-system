# GPT §10 cross-review — M4 provider-rotation self-heal at the formal door

Copy the block below into GPT-5.5 Pro. Branch `claude/confident-jemison-48b622` is pushed; all raw links resolve.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, and do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: claude/confident-jemison-48b622)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/<path>  (copy-pattern: substitute <path> with each path below)

CONTEXT — read these to judge the change against the contract:
- CLAUDE.md  (hard invariants §3, PIT §3.2, sealed-OOS §3.4, research integrity §7)
  https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/CLAUDE.md
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/src/research_orchestrator/cache_manifest.py
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/src/research_orchestrator/qlib_windowed_features.py
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/src/data_infra/provider_context.py
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/tests/research_orchestrator/test_cache_generation_self_heal.py
- https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/tests/research_orchestrator/test_assert_cache_reusable_permissive.py
- Prior review context: this amends the M4 finding of the calendar-unfreeze Phase-2 wall, which YOU (GPT) reviewed through 4 rounds to SHIP. The R4-M4 resolution was: generation ids required non-blank; legacy ""-rows refuse on reuse = deliberate invalidation; "the monthly bump ceremony archives the cache manifest; no silent migration mode is reachable from research doors."
  https://raw.githubusercontent.com/henrydan111/quant-system/claude/confident-jemison-48b622/workspace/research/calendar_unfreeze/UNFREEZE_PLAN.md

SELF-REVIEW PREFLIGHT — completed before this GPT request: verdict = clean for GPT. Checked §3 invariants + each quantitative-research principle in the canonical template. Fixes made: none post-design (check ordering in assert_cache_reusable was already design_hash→stage→window→generation, so the typed-subclass approach needed no reordering). Residual concerns handed to reviewer: (a) mid-run provider rotation is now non-fatal at this layer (WARNING + rebind instead of hard kill) — see Q3; (b) pre-existing, unchanged: record_cache_write stamps LIVE manifest ids even if the process qlib.init'ed a different provider URI (staged/archived provider), so manifest rows can misattribute generation for non-live readers — out of scope here but flag if you disagree; (c) data_feeder.preload_features(strict=False) still swallows ANY exception into the slow per-day fallback — separate hardening, not touched.

PROBLEM BEING FIXED (observed in production, 2026-07-02)
The M4 generation binding as shipped has a liveness bug: `assert_cache_reusable` raises on a stale-generation manifest row BEFORE `qlib_windowed_features` ever reaches `record_cache_write`. The manifest is append-only and the assert reads only the LATEST row per cache_key — so after the 2026-07-01 provider rotation (depth9_20260630_sharecap_reanchor_20260701), every cache_key with a pre-rotation row (all legacy rows carry backfilled "") became PERMANENTLY unreadable through the formal door: the raise prevents the recompute path from ever appending the fresh row that would heal the key. The designed escape hatch ("monthly ceremony archives the manifest") did not run on this rotation and nothing enforces it. Observed blast radius: EventDrivenBacktester preload_features(strict=False) logged "Failed to preload Qlib features: Cache manifest mismatch for qlib::day::25e4407a376f56d5: provider_build_id '' != 'depth9_20260630_sharecap_reanchor_20260701'" and silently degraded to per-day D.features (~10-60x slower; verify07 Model-I run log 2026-07-02 06:27). Formal runs (strict=True) would instead hard-fail on every key.

THE FIX (design intent)
Key observation: `qlib_windowed_features` holds NO cached artifact. It ALWAYS recomputes via `D.features` from the live provider; the manifest assert is a pure governance guard on a virtual ledger. Refusing a stale-generation row therefore prevents nothing stale from being served through this door — it only kills the read. So:
1. cache_manifest.py: the generation-binding branch (which runs strictly AFTER design_hash/stage/window checks) now raises a typed subclass `ProviderGenerationMismatchError(CacheKeyMismatchError)`. The blank-id caller-contract guards keep raising the BASE class (so they cannot be swallowed by the rotation catch). Store-level behavior for every caller: unchanged raise (fail-closed default).
2. qlib_windowed_features.py: catches ONLY the subclass → logs a WARNING (key, live ids, refused row) → proceeds to `D.features` (recompute from live provider) → the existing `record_cache_write` appends a fresh row under the live generation. Next read: latest row matches → silent. The stale row stays in the manifest = rotation audit trail. All other CacheKeyMismatchError (design_hash/stage/window) still propagate out of the door.
3. Governance stance preserved: there is still NO path that ACCEPTS a stale-generation row as valid reuse-evidence; what changed is that a stale row no longer blocks a fresh recompute-and-rebind. The seal/D3 checks (validate_read, born-sealed boundary clamp) run BEFORE the manifest assert and are outside the try — they cannot be swallowed.

WHAT CHANGED (authoritative — treat the embedded text as the source of truth; the links cross-check the surrounding code)

--- src diff (cache_manifest.py + qlib_windowed_features.py) ---
diff --git a/src/research_orchestrator/cache_manifest.py b/src/research_orchestrator/cache_manifest.py
index 53f9b98..78f9171 100644
--- a/src/research_orchestrator/cache_manifest.py
+++ b/src/research_orchestrator/cache_manifest.py
@@ -34,7 +34,9 @@ CACHE_MANIFEST_COLUMNS = (
     # UNFREEZE_PLAN.md Phase 2 (GPT R2-M4): provider-generation binding — a
     # cache written under one provider build/policy must not be reused under
     # another. Legacy rows backfill "" and therefore fail the reuse check
-    # against a real id (one-time safe invalidation after a rotation).
+    # against a real id. The refusal is typed (ProviderGenerationMismatchError)
+    # so the recompute-only door can self-heal by appending a fresh row under
+    # the live generation — the check reads only the latest row per key.
     "provider_build_id",
     "calendar_policy_id",
 )
@@ -98,6 +100,19 @@ class CacheKeyMismatchError(ValueError):
     """Raised when a cached artifact is reused across the wrong hypothesis window or stage."""
 
 
+class ProviderGenerationMismatchError(CacheKeyMismatchError):
+    """The manifest's latest row for this key was written under another provider
+    generation (build/policy rotation, incl. legacy ``""`` rows).
+
+    Raised ONLY by the generation-binding branch of ``assert_cache_reusable``,
+    which runs strictly AFTER the design_hash/stage/window checks — so a caller
+    that catches this subclass can never mask one of those violations. A door
+    that holds NO cached artifact and always recomputes from the live provider
+    (today: ``qlib_windowed_features``) may catch it, recompute, and re-record
+    under the live generation; every other caller must let it propagate
+    (fail-closed default unchanged)."""
+
+
 @dataclass(frozen=True)
 class CacheContext:
     design_hash: str = ""
@@ -241,9 +256,15 @@ class CacheManifestStore:
 
         R4-M4: the provider-generation ids are REQUIRED non-blank; a legacy
         manifest row (recorded "" before the generation-binding rule) then
-        mismatches the real ids and is REFUSED — refusal is the deliberate
-        legacy-invalidation path (the monthly bump ceremony archives the cache
-        manifest; no silent migration mode is reachable from research doors).
+        mismatches the real ids and is REFUSED (``ProviderGenerationMismatchError``)
+        — stale-generation rows never validate reuse. The refusal is NOT
+        permanent for the one recompute-only door: ``qlib_windowed_features``
+        catches the typed subclass, recomputes from the live provider, and
+        appends a fresh row under the live generation (the manifest is
+        append-only and this check reads only the latest row, so the append
+        self-heals the key; the stale row stays behind as the rotation audit
+        trail). Every other caller lets it propagate — there is still no
+        silent path that ACCEPTS a stale row as valid.
 
         ``cache_type`` controls the design_hash check (Part B, plan
         ``snappy-buzzing-meerkat`` v5):
@@ -288,13 +309,17 @@ class CacheManifestStore:
         # UNFREEZE_PLAN.md Phase 2 (GPT R2-M4): provider-generation binding.
         # Enforced only when the caller supplies the current ids; a legacy row
         # (backfilled "") then mismatches a real id and the cache is refused —
-        # a one-time safe invalidation after any provider rotation.
+        # a one-time safe invalidation after any provider rotation. Raised as
+        # the typed subclass so the recompute-only door can self-heal (append a
+        # fresh row under the live generation) WITHOUT weakening the checks
+        # above: this branch is reached only after design_hash/stage/window all
+        # matched, so catching the subclass can never mask those violations.
         for column, current in (
             ("provider_build_id", provider_build_id),
             ("calendar_policy_id", calendar_policy_id),
         ):
             if current and str(latest.get(column, "")) != str(current):
-                raise CacheKeyMismatchError(
+                raise ProviderGenerationMismatchError(
                     f"Cache manifest mismatch for {cache_path}: {column} "
                     f"{latest.get(column, '')!r} != {current!r} — caches do not "
                     "survive a provider rotation (UNFREEZE_PLAN.md M4 binding)."
diff --git a/src/research_orchestrator/qlib_windowed_features.py b/src/research_orchestrator/qlib_windowed_features.py
index b0d6e34..63f28dc 100644
--- a/src/research_orchestrator/qlib_windowed_features.py
+++ b/src/research_orchestrator/qlib_windowed_features.py
@@ -2,6 +2,7 @@ from __future__ import annotations
 
 import hashlib
 import json
+import logging
 from pathlib import Path
 from typing import Any
 
@@ -10,6 +11,7 @@ import pandas as pd
 from src.research_orchestrator.cache_manifest import (
     CacheContext,
     CacheManifestStore,
+    ProviderGenerationMismatchError,
     get_cache_context,
 )
 from src.research_orchestrator.research_access_context import (
@@ -18,6 +20,8 @@ from src.research_orchestrator.research_access_context import (
     get_research_access_context,
 )
 
+logger = logging.getLogger(__name__)
+
 
 def _deterministic_cache_path(freq: str, fields: list[str], start: str, end: str) -> str:
     payload = {
@@ -100,20 +104,38 @@ def qlib_windowed_features(
     manifest = CacheManifestStore(cache_manifest_dir)
     cache_key = _deterministic_cache_path(freq, fields, start_time, end_time)
     cache_path = cache_key
-    # M4 provider-generation binding: cache rows written under another provider
-    # build/policy are refused (legacy ""-rows mismatch -> safe invalidation).
+    # M4 provider-generation binding: a manifest row written under another
+    # provider build/policy (incl. legacy ""-rows) never validates reuse.
     live_build_id, live_policy_id = live_provider_ids()
-    manifest.assert_cache_reusable(
-        cache_key=cache_key,
-        cache_path=cache_path,
-        cache_context=effective_context,
-        stage=stage,
-        window_start=start_time,
-        window_end=end_time,
-        cache_type="qlib_features",
-        provider_build_id=live_build_id,
-        calendar_policy_id=live_policy_id,
-    )
+    try:
+        manifest.assert_cache_reusable(
+            cache_key=cache_key,
+            cache_path=cache_path,
+            cache_context=effective_context,
+            stage=stage,
+            window_start=start_time,
+            window_end=end_time,
+            cache_type="qlib_features",
+            provider_build_id=live_build_id,
+            calendar_policy_id=live_policy_id,
+        )
+    except ProviderGenerationMismatchError as exc:
+        # Provider rotated since this key's latest manifest row. This door
+        # holds no cached artifact — D.features below always recomputes from
+        # the live provider — so a stale-generation row must not brick the key
+        # permanently: proceed, and record_cache_write below appends a fresh
+        # row under the live generation (the next read then passes; the stale
+        # row stays behind as the rotation audit trail). The subclass is
+        # raised only after design_hash/stage/window all matched — those
+        # violations still propagate.
+        logger.warning(
+            "cache generation rotated for %s — recomputing from the live "
+            "provider and re-binding to (%s, %s); refused stale row: %s",
+            cache_key,
+            live_build_id,
+            live_policy_id,
+            exc,
+        )
     frame = D.features(  # noqa: bare-qlib-features  (canonical chokepoint)
         instruments,
         list(fields),

--- test diff (test_assert_cache_reusable_permissive.py) + new file test_cache_generation_self_heal.py ---
diff --git a/tests/research_orchestrator/test_assert_cache_reusable_permissive.py b/tests/research_orchestrator/test_assert_cache_reusable_permissive.py
index cb06931..4c1bbab 100644
--- a/tests/research_orchestrator/test_assert_cache_reusable_permissive.py
+++ b/tests/research_orchestrator/test_assert_cache_reusable_permissive.py
@@ -20,6 +20,7 @@ from src.research_orchestrator.cache_manifest import (
     CacheContext,
     CacheKeyMismatchError,
     CacheManifestStore,
+    ProviderGenerationMismatchError,
 )
 
 
@@ -182,17 +183,20 @@ class TestGenerationBindingFailClosed:
     def test_record_with_blank_ids_fails(self, tmp_path: Path):
         manifest = CacheManifestStore(tmp_path)
         for bad in ("", "   "):
-            with pytest.raises(CacheKeyMismatchError, match="non-blank provider_build_id"):
+            with pytest.raises(CacheKeyMismatchError, match="non-blank provider_build_id") as ei:
                 manifest.record_cache_write(
                     cache_type="qlib_features", cache_key=CACHE_KEY, cache_path=CACHE_KEY,
                     cache_context=CacheContext(design_hash="h"), stage="is_only",
                     window_start=WINDOW_START, window_end=WINDOW_END,
                     provider_build_id=bad, calendar_policy_id=POLICY_ID,
                 )
+            # Caller-contract violation, NOT a rotation: must not be the
+            # subclass, or the recompute door's self-heal could swallow it.
+            assert not isinstance(ei.value, ProviderGenerationMismatchError)
 
     def test_assert_with_blank_ids_fails(self, tmp_path: Path):
         manifest = _seed_row(tmp_path, cache_type="qlib_features", design_hash="h")
-        with pytest.raises(CacheKeyMismatchError, match="non-blank calendar_policy_id"):
+        with pytest.raises(CacheKeyMismatchError, match="non-blank calendar_policy_id") as ei:
             manifest.assert_cache_reusable(
                 cache_key=CACHE_KEY, cache_path=CACHE_KEY,
                 cache_context=CacheContext(design_hash="h"), stage="is_only",
@@ -200,10 +204,11 @@ class TestGenerationBindingFailClosed:
                 cache_type="qlib_features",
                 provider_build_id=BUILD_ID, calendar_policy_id="",
             )
+        assert not isinstance(ei.value, ProviderGenerationMismatchError)
 
     def test_cross_generation_reuse_refused(self, tmp_path: Path):
         manifest = _seed_row(tmp_path, cache_type="qlib_features", design_hash="h")
-        with pytest.raises(CacheKeyMismatchError, match="provider rotation"):
+        with pytest.raises(ProviderGenerationMismatchError, match="provider rotation"):
             manifest.assert_cache_reusable(
                 cache_key=CACHE_KEY, cache_path=CACHE_KEY,
                 cache_context=CacheContext(design_hash="h"), stage="is_only",
@@ -221,10 +226,26 @@ class TestGenerationBindingFailClosed:
         frame["provider_build_id"] = ""
         frame["calendar_policy_id"] = ""
         frame.to_parquet(manifest.log_path, index=False)
-        with pytest.raises(CacheKeyMismatchError, match="provider rotation"):
+        with pytest.raises(ProviderGenerationMismatchError, match="provider rotation"):
             manifest.assert_cache_reusable(
                 cache_key=CACHE_KEY, cache_path=CACHE_KEY,
                 cache_context=CacheContext(design_hash="h"), stage="is_only",
                 window_start=WINDOW_START, window_end=WINDOW_END,
                 cache_type="qlib_features", **GEN,
             )
+
+    def test_stage_mismatch_beats_generation_mismatch(self, tmp_path: Path):
+        """Ordering pin: when BOTH stage and generation mismatch, the stage
+        check fires first with the BASE class — the subclass can only ever
+        mean 'everything else matched, only the generation rotated'."""
+        manifest = _seed_row(tmp_path, cache_type="qlib_features", design_hash="h",
+                             stage="is_only")
+        with pytest.raises(CacheKeyMismatchError, match="stage") as ei:
+            manifest.assert_cache_reusable(
+                cache_key=CACHE_KEY, cache_path=CACHE_KEY,
+                cache_context=CacheContext(design_hash="h"), stage="oos_test",
+                window_start=WINDOW_START, window_end=WINDOW_END,
+                cache_type="qlib_features",
+                provider_build_id="rotated_build", calendar_policy_id=POLICY_ID,
+            )
+        assert not isinstance(ei.value, ProviderGenerationMismatchError)

--- NEW FILE: tests/research_orchestrator/test_cache_generation_self_heal.py ---
"""Provider-rotation self-heal at the formal door (M4 sharp-corner fix).

The M4 generation binding refuses a manifest row written under another
provider build/policy. Before this fix the refusal propagated out of
``qlib_windowed_features`` BEFORE ``record_cache_write`` could append a
fresh row, so any cache_key with a pre-rotation row was permanently
unreadable through the formal door after a rotation (observed 2026-07-02:
the depth9_20260630_sharecap_reanchor_20260701 publish bricked every
pre-existing key; EventDrivenBacktester preload_features(strict=False)
silently degraded to per-day D.features).

Contract now:
  1. generation mismatch (rotated id or legacy "" row) -> WARNING +
     recompute from the live provider + append a fresh row = self-healed;
     the second read passes silently.
  2. design_hash/stage/window mismatches still propagate out of the door
     unchanged (the subclass is raised only after those checks pass).
  3. the store itself still raises for every caller — the self-heal lives
     ONLY in the recompute-only door.
"""
from __future__ import annotations

import logging
import sys
import types

import pandas as pd
import pytest

from src.research_orchestrator import qlib_windowed_features as qwf_mod
from src.research_orchestrator.cache_manifest import (
    CacheContext,
    CacheKeyMismatchError,
    CacheManifestStore,
)
from src.research_orchestrator.qlib_windowed_features import _deterministic_cache_path

BOUNDARY = pd.Timestamp("2026-02-27")
LIVE_BUILD = "depth9_new_build"
LIVE_POLICY = "frozen_20260630_thaw_step1"
FIELDS = ["$close"]
START = "2021-01-04"
END = "2021-01-08"
STAGE = "sandbox_screening"
WARNING_MARK = "cache generation rotated"


@pytest.fixture(autouse=True)
def _stub_boundary_and_qlib(monkeypatch):
    import src.data_infra.provider_context as ctx_mod

    monkeypatch.setattr(ctx_mod, "live_spent_oos_end", lambda: BOUNDARY)
    monkeypatch.setattr(ctx_mod, "live_provider_ids", lambda: (LIVE_BUILD, LIVE_POLICY))

    fake_frame = pd.DataFrame()
    d_stub = types.SimpleNamespace(features=lambda *a, **k: fake_frame)
    qlib_data_mod = types.ModuleType("qlib.data")
    qlib_data_mod.D = d_stub
    qlib_mod = types.ModuleType("qlib")
    qlib_mod.data = qlib_data_mod
    monkeypatch.setitem(sys.modules, "qlib", qlib_mod)
    monkeypatch.setitem(sys.modules, "qlib.data", qlib_data_mod)
    yield


def _call(manifest_dir, stage: str = STAGE):
    return qwf_mod.qlib_windowed_features(
        instruments=["000001_SZ"],
        fields=FIELDS,
        start_time=START,
        end_time=END,
        cache_context=CacheContext(),
        stage=stage,
        cache_manifest_dir=manifest_dir,
    )


def _cache_key() -> str:
    return _deterministic_cache_path("day", FIELDS, START, END)


def _seed_row(manifest_dir, *, build_id: str, policy_id: str,
              stage: str = STAGE, window_start: str = START,
              window_end: str = END) -> CacheManifestStore:
    manifest = CacheManifestStore(manifest_dir)
    manifest.record_cache_write(
        cache_type="qlib_features",
        cache_key=_cache_key(),
        cache_path=_cache_key(),
        cache_context=CacheContext(),
        stage=stage,
        window_start=window_start,
        window_end=window_end,
        provider_build_id=build_id,
        calendar_policy_id=policy_id,
    )
    return manifest


class TestRotationSelfHeal:
    def test_rotated_row_heals_and_rebinds(self, tmp_path, caplog):
        manifest = _seed_row(tmp_path, build_id="old_build", policy_id=LIVE_POLICY)
        with caplog.at_level(logging.WARNING, logger=qwf_mod.__name__):
            frame = _call(tmp_path)
        assert frame.empty  # stubbed recompute proceeded
        assert sum(WARNING_MARK in r.message for r in caplog.records) == 1

        rows = manifest.list_events(cache_key=_cache_key())
        assert len(rows) == 2  # stale row kept as audit trail + fresh row
        latest = rows.sort_values("recorded_at").iloc[-1]
        assert latest["provider_build_id"] == LIVE_BUILD
        assert latest["calendar_policy_id"] == LIVE_POLICY

        # Second read: latest row now matches the live generation — silent.
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=qwf_mod.__name__):
            _call(tmp_path)
        assert not any(WARNING_MARK in r.message for r in caplog.records)

    def test_legacy_blank_row_heals(self, tmp_path, caplog):
        # Pre-M4 legacy rows carry "" ids (record_cache_write refuses blanks,
        # so rewrite the parquet directly — same shape as production legacy).
        manifest = _seed_row(tmp_path, build_id=LIVE_BUILD, policy_id=LIVE_POLICY)
        frame = pd.read_parquet(manifest.log_path)
        frame["provider_build_id"] = ""
        frame["calendar_policy_id"] = ""
        frame.to_parquet(manifest.log_path, index=False)

        with caplog.at_level(logging.WARNING, logger=qwf_mod.__name__):
            _call(tmp_path)
        assert sum(WARNING_MARK in r.message for r in caplog.records) == 1
        latest = manifest.list_events(cache_key=_cache_key()).sort_values("recorded_at").iloc[-1]
        assert latest["provider_build_id"] == LIVE_BUILD

    def test_no_prior_row_stays_silent(self, tmp_path, caplog):
        with caplog.at_level(logging.WARNING, logger=qwf_mod.__name__):
            _call(tmp_path)
        assert not any(WARNING_MARK in r.message for r in caplog.records)


class TestDoorStillFailsClosed:
    def test_stage_mismatch_propagates(self, tmp_path):
        _seed_row(tmp_path, build_id=LIVE_BUILD, policy_id=LIVE_POLICY,
                  stage="is_only")
        with pytest.raises(CacheKeyMismatchError, match="stage"):
            _call(tmp_path, stage="oos_test")

    def test_stage_mismatch_propagates_even_when_generation_also_rotated(self, tmp_path):
        # BOTH stale: stage wins (checked first, base class) — the self-heal
        # branch must not swallow it.
        _seed_row(tmp_path, build_id="old_build", policy_id="old_policy",
                  stage="is_only")
        with pytest.raises(CacheKeyMismatchError, match="stage"):
            _call(tmp_path, stage="oos_test")

    def test_window_mismatch_propagates(self, tmp_path):
        # Same cache_key, different recorded window (only reachable by manual
        # seeding — the key encodes the window — but the guard must hold).
        _seed_row(tmp_path, build_id=LIVE_BUILD, policy_id=LIVE_POLICY,
                  window_start="2020-01-01", window_end="2020-01-10")
        with pytest.raises(CacheKeyMismatchError, match="window"):
            _call(tmp_path)

TEST EVIDENCE
- Full tests/research_orchestrator: 285 passed, 0 failed (baseline before change: 278 passed; +7 = 6 new self-heal tests + 1 new ordering pin).
- tests/backtest_engine/test_preload_hardening.py + test_pr8_runtime_enforcement.py: 39 passed.
- New pins: rotated-row heal + rebind + second-read silence; legacy ""-row heal; no-prior-row silence; stage mismatch propagates (alone AND when generation also rotated — ordering pin: base class wins); window mismatch propagates; blank-id guards raise base class NOT the subclass.

QUANTITATIVE-RESEARCH PRINCIPLES — check the change against EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (the cardinal rule). Does the self-heal ever let a read see data not knowable at t? (The recompute reads the live provider — same as a first-ever read of that key.)
2. OUT-OF-SAMPLE IS SACRED & SEALED. Can catching ProviderGenerationMismatchError ever mask a stage/window/seal violation? Trace the order: validate_read → D3 born-sealed clamp → assert (design_hash→stage→window→generation). The try wraps ONLY the assert.
3. SURVIVORSHIP — n/a unless you see otherwise.
4-6. Factor-eval / execution realism / leverage — n/a unless you see otherwise.
7. NO HEDGE WORDS — the claims above (blast radius, root cause, test counts) are backed by the named log/tests; flag any that are not.
8-9. Pipeline / multiple testing — n/a unless you see otherwise.

REVIEW QUESTIONS
1. Correctness of the exception taxonomy: is raising the subclass ONLY from the generation branch (post design_hash/stage/window) airtight, including the cache_type="qlib_features" path where the design_hash check is intentionally skipped? Is there any input where a design_hash/stage/window violation could surface AS the subclass and be swallowed?
2. Governance: does the self-heal violate the SPIRIT of your R4-M4 ruling ("no silent migration mode reachable from research doors")? Our position: the ruling targeted silently ACCEPTING stale rows as reuse-evidence; the self-heal never accepts the stale row — it recomputes from the live provider and re-records, with a WARNING and an append-only audit trail. The ceremony-archive escape hatch proved operationally unreliable (it didn't run on the first real rotation) and archiving DESTROYS audit history that the append path preserves. Do you concur, or do you require an additional guard (e.g., a per-run generation pin in ResearchAccessContext so a MID-RUN rotation still hard-fails formal runs — see Q3)?
3. Mid-run rotation tradeoff: under the old code, a provider rotation DURING a run hard-killed the next windowed read (accidentally — only for keys with pre-rotation rows). Under the fix it warns + rebinds, so a formal run could span a rotation and mix two provider generations, detectable only via WARNING logs and mixed manifest rows. provider_context caches ids keyed by manifest (mtime_ns,size) so live ids DO flip mid-process. Is a follow-up per-run pin (capture ids at run start / seal claim; hard-fail on change) REQUIRED for SHIP, or acceptable as a separately-reviewed follow-up? Note the pre-fix protection was incidental and incomplete (keys without prior rows never tripped it; run-start validation is the designed layer for this).
4. Design alternatives you should explicitly rule in/out: (a) explicit supersede API on CacheManifestStore instead of catch-at-door (we judged it equivalent plumbing with more API surface reachable from anywhere — the typed-exception catch is localized to the one door that provably recomputes); (b) auto-archive of the cache manifest inside the publish ceremony (rejected as the LOAD-BEARING fix: it proved skippable, destroys audit rows, and leaves the door bricked whenever ops forget; fine as belt-and-suspenders hygiene later); (c) making the door hard-fail formal stages but self-heal sandbox (rejected: post-rotation stale rows brick FORMAL runs identically — the fix must apply to formal reads too). Do you agree with these dispositions?
5. Evidence — what proof is missing; the exact test/command you'd run to confirm it.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
