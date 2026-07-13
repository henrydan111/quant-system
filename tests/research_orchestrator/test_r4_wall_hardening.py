"""GPT Round-4 wall-hardening battery (UNFREEZE_PLAN.md Phase 2, R4-M1..M6).

Locks the fail-closed edges the Round-4 review demanded beyond the original
14 wall tests: publish id validation, incremental-republish policy
preservation, formal policy provenance (no manifest fallback), in-process
provider-rotation invalidation, the promotion-guard binding branches, and
seal-recovery generation binding.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
# pit_backend / update_daily_data use the src-on-path bare `data_infra.` import
# convention (same as tests/data_infra/test_pit_backend.py).
sys.path.insert(0, str(REPO_ROOT / "src"))
LEGACY_POLICY = "frozen_20260227_system_build"
THAW_POLICY = "frozen_20260701_thaw_step1"


# ── M6.1 publish id validation ───────────────────────────────────────────────

class TestPublishPolicyIdValidation:
    def _builder(self, tmp_path):
        from src.data_infra.pit_backend import StagedQlibBackendBuilder

        return StagedQlibBackendBuilder(
            data_root=str(tmp_path / "data"),
            qlib_dir=str(tmp_path / "qlib"),
            build_id="unit_r4_publish_gate",
            allow_exceptions=True,
        )

    @pytest.mark.parametrize("bad_id", [None, "", "   "])
    def test_publish_with_missing_or_blank_id_fails(self, tmp_path, bad_id):
        from src.data_infra.pit_backend import BuildGateError

        builder = self._builder(tmp_path)
        with pytest.raises(BuildGateError, match="non-blank calendar_policy_id"):
            builder.run(publish=True, calendar_policy_id=bad_id)

    def test_publish_with_unknown_policy_id_fails(self, tmp_path):
        from src.data_infra.pit_backend import BuildGateError

        builder = self._builder(tmp_path)
        with pytest.raises(BuildGateError, match="does not resolve to a committed policy"):
            builder.run(publish=True, calendar_policy_id="no_such_policy_v99")


# ── M6.2 incremental republish preserves the manifest-recorded policy ────────

class TestIncrementalRepublishPolicy:
    def test_trigger_incremental_passes_manifest_recorded_id(self, monkeypatch):
        import data_infra.pipeline.update_daily_data as udd

        captured: dict = {}

        def fake_build(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(udd, "build_unified_qlib", fake_build)
        monkeypatch.setattr(udd, "_resolve_paths", lambda: ("data", "data/qlib_data"))
        monkeypatch.setattr(udd, "_live_calendar_policy_id", lambda qlib_dir: "recorded_policy_x")

        udd.trigger_qlib_incremental(touched_symbols=["000001.SZ"], affected_datasets=["daily"])
        assert captured["calendar_policy_id"] == "recorded_policy_x"
        assert captured["publish"] is True

    def test_live_calendar_policy_id_reads_the_manifest_record(self):
        import data_infra.pipeline.update_daily_data as udd

        live = udd._live_calendar_policy_id(str(REPO_ROOT / "data" / "qlib_data"))
        assert live and live.strip()  # the real manifest's recorded id, never blank


# ── M6.3 formal policy provenance: prescription pin or fail closed ───────────

class TestFormalPolicyProvenance:
    class _Ctx:
        def __init__(self, prescription):
            hypothesis = type("H", (), {"prescription": prescription})()
            self.request = type("R", (), {"hypothesis": hypothesis})()

    def test_prescription_pin_flows(self):
        from src.research_orchestrator.validation_steps import _formal_calendar_policy_id

        pin = type("P", (), {"calendar_policy_id": THAW_POLICY})()
        assert _formal_calendar_policy_id(self._Ctx(pin)) == THAW_POLICY

    @pytest.mark.parametrize("unset", [None, "", "   "])
    def test_unset_or_blank_pin_fails_closed_never_manifest(self, unset):
        from src.research_orchestrator.validation_steps import _formal_calendar_policy_id

        pin = type("P", (), {"calendar_policy_id": unset})()
        with pytest.raises(ValueError, match="failing closed"):
            _formal_calendar_policy_id(self._Ctx(pin))

    def test_missing_prescription_fails_closed(self):
        from src.research_orchestrator.validation_steps import _formal_calendar_policy_id

        with pytest.raises(ValueError, match="failing closed"):
            _formal_calendar_policy_id(self._Ctx(None))


# ── M6.5 in-process provider rotation invalidates the context cache ──────────

class TestProviderRotationInvalidation:
    def _write_provider(
        self,
        qlib_dir: Path,
        build_id: str,
        calendar_policy_id: str = LEGACY_POLICY,
        calendar_end: str = "2026-02-27",
    ) -> None:
        live = json.loads(
            (REPO_ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json")
            .read_text(encoding="utf-8")
        )
        live["provider_build_id"] = build_id
        live["calendar_policy_id"] = calendar_policy_id
        (qlib_dir / "metadata").mkdir(parents=True, exist_ok=True)
        (qlib_dir / "metadata" / "provider_build.json").write_text(
            json.dumps(live), encoding="utf-8"
        )
        (qlib_dir / "calendars").mkdir(parents=True, exist_ok=True)
        (qlib_dir / "calendars" / "day.txt").write_text(f"{calendar_end}\n", encoding="utf-8")

    def test_rotation_reresolves_ids_and_boundary(self, tmp_path, monkeypatch):
        import src.data_infra.provider_context as ctx_mod

        qlib_dir = tmp_path / "qlib_data"
        self._write_provider(qlib_dir, "gen_A")
        monkeypatch.setattr(ctx_mod, "_qlib_dir", lambda: qlib_dir)
        ctx_mod.refresh_live_provider_context()

        assert ctx_mod.live_provider_ids() == ("gen_A", LEGACY_POLICY)
        assert ctx_mod.live_spent_oos_end() == pd.Timestamp("2026-02-27")

        # Rotate: rewrite the manifest (mtime/size change) — NO explicit refresh.
        self._write_provider(qlib_dir, "gen_B_rotated")
        assert ctx_mod.live_provider_ids() == ("gen_B_rotated", LEGACY_POLICY)

    def test_missing_manifest_fails_closed(self, tmp_path, monkeypatch):
        import src.data_infra.provider_context as ctx_mod

        monkeypatch.setattr(ctx_mod, "_qlib_dir", lambda: tmp_path / "absent")
        ctx_mod.refresh_live_provider_context()
        with pytest.raises(ctx_mod.ProviderContextError, match="fail closed"):
            ctx_mod.live_provider_ids()

    def test_same_size_same_mtime_rotation_still_reresolves(self, tmp_path, monkeypatch):
        """R5-M7: a manifest rewrite that preserves BOTH byte length and
        st_mtime_ns (Windows coarse timestamps / copied / atomic-publish
        filesystems) must STILL invalidate the context cache — content
        identity (sha256), not stat identity. Then: cache rows recorded under
        the pre-rotation generation are refused against the new ids."""
        import os

        import src.data_infra.provider_context as ctx_mod

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

        # Old-generation cache ROWS are invalidated under the new generation
        # (read-side refusal; the write-side production-path proof is the
        # separate R6-M8 test below).
        from src.research_orchestrator.cache_manifest import (
            CacheContext,
            CacheKeyMismatchError,
            CacheManifestStore,
        )

        store = CacheManifestStore(tmp_path / "cache_manifest")
        store.record_cache_write(
            cache_type="qlib_features", cache_key="k", cache_path="k",
            cache_context=CacheContext(), stage="s",
            window_start="2026-01-05", window_end="2026-02-27",
            provider_build_id="gen_AAAA", calendar_policy_id=LEGACY_POLICY,
        )
        new_build, new_policy = ctx_mod.live_provider_ids()
        with pytest.raises(CacheKeyMismatchError, match="provider_build_id"):
            store.assert_cache_reusable(
                cache_key="k", cache_path="k", cache_context=CacheContext(),
                stage="s", window_start="2026-01-05", window_end="2026-02-27",
                cache_type="qlib_features",
                provider_build_id=new_build, calendar_policy_id=new_policy,
            )

    def test_same_size_same_mtime_rotation_formal_cache_write_stamps_new_generation(
        self, tmp_path, monkeypatch
    ):
        """R6-M8: after a same-size/same-mtime rotation, the SANCTIONED formal
        door (qlib_windowed_features) must stamp its cache write with the
        CURRENT live generation — proven through the production write path,
        not a direct CacheManifestStore call with caller-supplied ids."""
        import os
        import sys
        import types

        import src.data_infra.provider_context as ctx_mod
        from src.research_orchestrator import qlib_windowed_features as qwf_mod
        from src.research_orchestrator.cache_manifest import CacheContext, CacheManifestStore

        qlib_dir = tmp_path / "qlib_data"
        self._write_provider(qlib_dir, "gen_AAAA")
        manifest = qlib_dir / "metadata" / "provider_build.json"
        monkeypatch.setattr(ctx_mod, "_qlib_dir", lambda: qlib_dir)
        ctx_mod.refresh_live_provider_context()
        assert ctx_mod.live_provider_ids()[0] == "gen_AAAA"
        before = manifest.stat()

        self._write_provider(qlib_dir, "gen_BBBB")
        os.utime(manifest, ns=(before.st_atime_ns, before.st_mtime_ns))

        # Stub qlib so the formal-door read needs no provider tree.
        fake_frame = pd.DataFrame()
        d_stub = types.SimpleNamespace(features=lambda *a, **k: fake_frame)
        qlib_data_mod = types.ModuleType("qlib.data")
        qlib_data_mod.D = d_stub
        qlib_mod = types.ModuleType("qlib")
        qlib_mod.data = qlib_data_mod
        monkeypatch.setitem(sys.modules, "qlib", qlib_mod)
        monkeypatch.setitem(sys.modules, "qlib.data", qlib_data_mod)

        store_dir = tmp_path / "cache_manifest"
        qwf_mod.qlib_windowed_features(
            instruments=["000001_SZ"],
            fields=["$close"],
            start_time="2026-01-05",
            end_time="2026-02-27",
            cache_context=CacheContext(),
            stage="sandbox_screening",
            cache_manifest_dir=store_dir,
        )

        events = CacheManifestStore(store_dir).list_events()
        assert not events.empty
        row = events.sort_values("recorded_at").iloc[-1]
        assert row["provider_build_id"] == "gen_BBBB"
        assert row["calendar_policy_id"] == LEGACY_POLICY
        assert row["provider_build_id"] != "gen_AAAA"

    def test_rotation_formal_cache_write_stamps_new_policy_id(self, tmp_path, monkeypatch):
        """R7-M9: the Phase-3 publish rotates BOTH ids (legacy frozen ->
        thaw_step1). The sanctioned door's cache write must stamp the NEW
        calendar_policy_id, not only the new build id. (No size/mtime
        preservation needed here — content-hash invalidation is proven by the
        preceding test; this one locks the policy-stamping half.)"""
        import sys
        import types

        import src.data_infra.provider_context as ctx_mod
        from src.research_orchestrator import qlib_windowed_features as qwf_mod
        from src.research_orchestrator.cache_manifest import CacheContext, CacheManifestStore

        qlib_dir = tmp_path / "qlib_data"
        self._write_provider(
            qlib_dir, "gen_AAAA",
            calendar_policy_id=LEGACY_POLICY, calendar_end="2026-02-27",
        )
        monkeypatch.setattr(ctx_mod, "_qlib_dir", lambda: qlib_dir)
        ctx_mod.refresh_live_provider_context()
        assert ctx_mod.live_provider_ids() == ("gen_AAAA", LEGACY_POLICY)

        # Phase-3-shaped rotation: new build id + thaw policy + longer calendar.
        self._write_provider(
            qlib_dir, "gen_BBBB",
            calendar_policy_id=THAW_POLICY, calendar_end="2026-06-30",
        )
        assert ctx_mod.live_provider_ids() == ("gen_BBBB", THAW_POLICY)
        # The thaw policy pins spent_oos_end=2026-02-27 (policy_fields branch).
        assert ctx_mod.live_spent_oos_end() == pd.Timestamp("2026-02-27")

        fake_frame = pd.DataFrame()
        d_stub = types.SimpleNamespace(features=lambda *a, **k: fake_frame)
        qlib_data_mod = types.ModuleType("qlib.data")
        qlib_data_mod.D = d_stub
        qlib_mod = types.ModuleType("qlib")
        qlib_mod.data = qlib_data_mod
        monkeypatch.setitem(sys.modules, "qlib", qlib_mod)
        monkeypatch.setitem(sys.modules, "qlib.data", qlib_data_mod)

        store_dir = tmp_path / "cache_manifest"
        qwf_mod.qlib_windowed_features(
            instruments=["000001_SZ"],
            fields=["$close"],
            start_time="2026-01-05",
            end_time="2026-02-27",
            cache_context=CacheContext(),
            stage="sandbox_screening",
            cache_manifest_dir=store_dir,
        )

        row = CacheManifestStore(store_dir).list_events().sort_values("recorded_at").iloc[-1]
        assert row["provider_build_id"] == "gen_BBBB"
        assert row["calendar_policy_id"] == THAW_POLICY
        assert row["calendar_policy_id"] != LEGACY_POLICY


# ── M6.6 promotion guard binding branches (R4-M1) ────────────────────────────

class TestPromotionGuardBindings:
    """Exercise reproduce_sealed_oos's calendar_end guard via injected
    provider_provenance; the accept paths are proven by the guard letting the
    call reach the (deliberately failing) seal-store stub."""

    class _StubSealStoreBoom:
        def claim_holdout_access(self, **kwargs):
            raise RuntimeError("GUARD_PASSED_reached_seal_store")

    def _call(self, *, oos_end, calendar_end, seal_ctx=None, monkeypatch=None,
              spent_boundary="2026-02-27", fresh_window_override_id=""):
        import src.research_orchestrator.promotion_evidence as pe

        if monkeypatch is not None:
            import src.data_infra.provider_context as ctx_mod

            monkeypatch.setattr(
                ctx_mod, "live_spent_oos_end", lambda: pd.Timestamp(spent_boundary)
            )
            if seal_ctx is not None:
                from src.research_orchestrator import research_access_context as rac

                monkeypatch.setattr(rac, "get_research_access_context", lambda: seal_ctx)
                monkeypatch.setattr(pe, "PromotionEvidenceError", pe.PromotionEvidenceError)

        class _FS:
            frozen_set_hash = "f" * 16

        return pe.reproduce_sealed_oos(
            frozen_set=_FS(),
            factor_exprs={"f1": "Ref($close,1)"},
            oos_start="2021-01-01",
            oos_end=oos_end,
            qlib_dir="data/qlib_data",
            seal_root="data/_r4_test_seal",
            run_dir="r4_run",
            design_hash="d" * 8,
            provider_provenance={
                "provider_build_id": "prov_X",
                "calendar_policy_id": THAW_POLICY,
                "calendar_end": calendar_end,
            },
            seal_store=self._StubSealStoreBoom(),
            fresh_window_override_id=fresh_window_override_id,
            # PR3 R2 B4: a virgin claim must reserve its A5 spend in the A6 ledger first
            ledger_root="data/_r4_test_seal",
        )

    @staticmethod
    def _a5_authorization(oos_end: str) -> str:
        """PR3 R1 B3: a virgin-window factor-level claim now needs a PRE-RECORDED
        consume-once A5 authorization — record a unique one per test run (ids are
        single-use, so a fixed id would fail the second run)."""
        import uuid

        from src.alpha_research.factor_eval_skill.book_seal_stores import (
            OverrideAuthorizationStore,
        )

        override_id = f"r4_test_{uuid.uuid4().hex[:12]}"
        OverrideAuthorizationStore("data/_r4_test_seal").record_authorization(
            kind="a5_fresh_window", override_id=override_id,
            oos_window_id=f"2021-01-01..{oos_end}", scope_key="f" * 16,
            user_signoff="r4-test", reason="D3.5 sealed fresh-window guard test",
        )
        return override_id

    def test_shorter_calendar_refused(self, monkeypatch):
        import src.research_orchestrator.promotion_evidence as pe

        with pytest.raises(pe.PromotionEvidenceError, match="SHORTER"):
            self._call(oos_end="2026-02-27", calendar_end="2026-01-30", monkeypatch=monkeypatch)

    def test_longer_calendar_with_spent_boundary_passes_guard(self, monkeypatch):
        with pytest.raises(RuntimeError, match="GUARD_PASSED"):
            self._call(oos_end="2026-02-27", calendar_end="2026-06-30", monkeypatch=monkeypatch)

    def test_longer_calendar_fresh_end_without_seal_refused(self, monkeypatch):
        import src.research_orchestrator.promotion_evidence as pe

        with pytest.raises(pe.PromotionEvidenceError, match="neither the policy-recorded"):
            self._call(oos_end="2026-05-29", calendar_end="2026-06-30", monkeypatch=monkeypatch)

    def test_longer_calendar_with_matching_seal_passes_guard(self, monkeypatch):
        seal_ctx = type("Ctx", (), {
            "holdout_seal_claimed": True,
            "allowed_start": pd.Timestamp("2021-01-01"),
            "allowed_end": pd.Timestamp("2026-05-29"),
            "provider_build_id": "prov_X",
            "calendar_policy_id": THAW_POLICY,
        })()
        with pytest.raises(RuntimeError, match="GUARD_PASSED"):
            self._call(oos_end="2026-05-29", calendar_end="2026-06-30",
                       seal_ctx=seal_ctx, monkeypatch=monkeypatch,
                       fresh_window_override_id=self._a5_authorization("2026-05-29"))

    def test_longer_calendar_with_mismatched_seal_provider_refused(self, monkeypatch):
        import src.research_orchestrator.promotion_evidence as pe

        seal_ctx = type("Ctx", (), {
            "holdout_seal_claimed": True,
            "allowed_start": pd.Timestamp("2021-01-01"),
            "allowed_end": pd.Timestamp("2026-05-29"),
            "provider_build_id": "prov_OTHER",
            "calendar_policy_id": THAW_POLICY,
        })()
        with pytest.raises(pe.PromotionEvidenceError, match="neither the policy-recorded"):
            self._call(oos_end="2026-05-29", calendar_end="2026-06-30",
                       seal_ctx=seal_ctx, monkeypatch=monkeypatch)


# ── M6.7 seal-recovery generation binding ────────────────────────────────────

class TestSealRecoveryGenerationBinding:
    def _claim(self, store, **overrides):
        base = dict(
            design_hash="d" * 8, hypothesis_id="h", structural_family="s",
            profile_id="p", run_dir="run_x", step_id="step_1",
            provider_build_id="gen_A", calendar_policy_id=LEGACY_POLICY,
        )
        base.update(overrides)
        return store.claim_holdout_access(**base)

    def test_resume_under_same_generation_allowed(self, tmp_path):
        from src.research_orchestrator.holdout_seal import HoldoutSealStore

        store = HoldoutSealStore(tmp_path)
        first = self._claim(store)
        again = self._claim(store, allow_same_run=True)
        assert again["event_id"] == first["event_id"]

    def test_resume_under_rotated_provider_refused(self, tmp_path):
        from src.research_orchestrator.holdout_seal import HoldoutSealStore

        store = HoldoutSealStore(tmp_path)
        self._claim(store)
        with pytest.raises(ValueError, match="provider generation changed"):
            self._claim(store, allow_same_run=True, provider_build_id="gen_B")

    def test_fresh_claim_records_generation(self, tmp_path):
        from src.research_orchestrator.holdout_seal import HoldoutSealStore

        store = HoldoutSealStore(tmp_path)
        row = self._claim(store)
        assert row["provider_build_id"] == "gen_A"
        assert row["calendar_policy_id"] == LEGACY_POLICY
