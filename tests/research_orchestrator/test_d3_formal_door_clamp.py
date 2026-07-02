"""D3 born-sealed clamp at the FORMAL door (UNFREEZE_PLAN.md Phase 2, GPT R1-B1).

Three contract paths through qlib_windowed_features when the read window
crosses the live spent-OOS boundary:
  1. no active ResearchAccessContext        -> HoldoutWindowViolation
  2. active context, seal NOT claimed       -> HoldoutSealViolation
  3. active context, seal claimed, in-window-> clamp passes (read proceeds)
Plus: reads ending at/before the boundary are untouched (status quo).
"""
from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

from src.research_orchestrator import qlib_windowed_features as qwf_mod
from src.research_orchestrator.cache_manifest import CacheContext
from src.research_orchestrator.research_access_context import (
    HoldoutSealViolation,
    HoldoutWindowViolation,
    ResearchAccessContext,
    research_access_context,
)

BOUNDARY = pd.Timestamp("2026-02-27")


@pytest.fixture(autouse=True)
def _stub_boundary_and_qlib(monkeypatch, tmp_path):
    # Pin the boundary + generation ids (unit isolation; the resolver itself is
    # covered by test_spent_oos_boundary.py against the real policy files).
    import src.data_infra.provider_context as ctx_mod

    monkeypatch.setattr(ctx_mod, "live_spent_oos_end", lambda: BOUNDARY)
    monkeypatch.setattr(
        ctx_mod, "live_provider_ids", lambda: ("test_build", "frozen_20260630_thaw_step1")
    )

    # Stub qlib.data.D.features so no provider is touched.
    fake_frame = pd.DataFrame()
    d_stub = types.SimpleNamespace(features=lambda *a, **k: fake_frame)
    qlib_data_mod = types.ModuleType("qlib.data")
    qlib_data_mod.D = d_stub
    qlib_mod = types.ModuleType("qlib")
    qlib_mod.data = qlib_data_mod
    monkeypatch.setitem(sys.modules, "qlib", qlib_mod)
    monkeypatch.setitem(sys.modules, "qlib.data", qlib_data_mod)
    yield


def _call(end_time: str, tmp_path, start_time: str = "2026-01-05"):
    return qwf_mod.qlib_windowed_features(
        instruments=["000001_SZ"],
        fields=["$close"],
        start_time=start_time,
        end_time=end_time,
        cache_context=CacheContext(),
        stage="sandbox_screening",
        cache_manifest_dir=tmp_path / "manifest",
    )


def _ctx(seal_claimed: bool) -> ResearchAccessContext:
    return ResearchAccessContext(
        run_id="r1",
        step_id="s1",
        stage="oos_test",
        design_hash="d" * 8,
        allowed_start=pd.Timestamp("2026-02-28"),
        allowed_end=pd.Timestamp("2026-06-30"),
        provider_build_id="test_build",
        calendar_policy_id="frozen_20260630_thaw_step1",
        holdout_context_id="run_dir",
        holdout_seal_claimed=seal_claimed,
    )


class TestFormalDoorClamp:
    def test_no_context_read_past_boundary_fails_closed(self, tmp_path):
        with pytest.raises(HoldoutWindowViolation, match="born-sealed"):
            _call("2026-03-02", tmp_path)

    def test_context_without_seal_past_boundary_fails_closed(self, tmp_path):
        # Either layer may fire first: the pre-existing validate_read seal check
        # (oos_test stage) or the new D3 boundary clamp — both are
        # HoldoutSealViolation and both name the missing claim.
        with research_access_context(_ctx(seal_claimed=False)):
            with pytest.raises(HoldoutSealViolation, match="holdout_seal_claimed"):
                _call("2026-06-30", tmp_path, start_time="2026-02-28")

    def test_non_oos_context_without_seal_past_boundary_hits_the_d3_clamp(self, tmp_path):
        # A NON-oos stage context (validate_read's seal check does not fire)
        # crossing the boundary without a seal is exactly the D3 clamp's job.
        ctx = ResearchAccessContext(
            run_id="r1", step_id="s1", stage="is_validation", design_hash="d" * 8,
            allowed_start=pd.Timestamp("2026-01-05"), allowed_end=pd.Timestamp("2026-06-30"),
            provider_build_id="test_build", calendar_policy_id="frozen_20260630_thaw_step1",
        )
        with research_access_context(ctx):
            with pytest.raises(HoldoutSealViolation, match="born-sealed fresh window"):
                _call("2026-06-30", tmp_path)

    def test_context_with_claimed_seal_passes_the_clamp(self, tmp_path):
        with research_access_context(_ctx(seal_claimed=True)):
            frame = _call("2026-06-30", tmp_path, start_time="2026-02-28")
        assert frame.empty  # stubbed read proceeded — clamp did not block

    def test_read_at_or_before_boundary_is_untouched(self, tmp_path):
        frame = _call("2026-02-27", tmp_path)
        assert frame.empty
