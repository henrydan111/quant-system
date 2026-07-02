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
THAW_POLICY = "frozen_20260630_thaw_step1"


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
    def _write_provider(self, qlib_dir: Path, build_id: str) -> None:
        live = json.loads(
            (REPO_ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json")
            .read_text(encoding="utf-8")
        )
        live["provider_build_id"] = build_id
        live["calendar_policy_id"] = LEGACY_POLICY
        (qlib_dir / "metadata").mkdir(parents=True, exist_ok=True)
        (qlib_dir / "metadata" / "provider_build.json").write_text(
            json.dumps(live), encoding="utf-8"
        )
        (qlib_dir / "calendars").mkdir(parents=True, exist_ok=True)
        (qlib_dir / "calendars" / "day.txt").write_text("2026-02-27\n", encoding="utf-8")

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


# ── M6.6 promotion guard binding branches (R4-M1) ────────────────────────────

class TestPromotionGuardBindings:
    """Exercise reproduce_sealed_oos's calendar_end guard via injected
    provider_provenance; the accept paths are proven by the guard letting the
    call reach the (deliberately failing) seal-store stub."""

    class _StubSealStoreBoom:
        def claim_holdout_access(self, **kwargs):
            raise RuntimeError("GUARD_PASSED_reached_seal_store")

    def _call(self, *, oos_end, calendar_end, seal_ctx=None, monkeypatch=None,
              spent_boundary="2026-02-27"):
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
        )

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
                       seal_ctx=seal_ctx, monkeypatch=monkeypatch)

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
