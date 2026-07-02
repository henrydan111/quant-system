"""Provider-rotation self-heal at the formal door (M4 sharp-corner fix).

The M4 generation binding refuses a manifest row written under another
provider build/policy. Before this fix the refusal propagated out of
``qlib_windowed_features`` BEFORE ``record_cache_write`` could append a
fresh row, so any cache_key with a pre-rotation row was permanently
unreadable through the formal door after a rotation (observed 2026-07-02:
the depth9_20260630_sharecap_reanchor_20260701 publish bricked every
pre-existing key; EventDrivenBacktester preload_features(strict=False)
silently degraded to per-day D.features).

Contract now (incl. the GPT REWORK round: B1 run-generation pin, M1 append
-order latest row, M2 live-binding guard):
  1. generation mismatch (rotated id or legacy "" row) -> WARNING +
     recompute from the live provider + append a fresh row = self-healed;
     the second read passes silently.
  2. design_hash/stage/window mismatches still propagate out of the door
     unchanged (the subclass is raised only after those checks pass).
  3. the store itself still raises for every caller — the self-heal lives
     ONLY in the recompute-only door.
  4. B1: an active ResearchAccessContext pins the run's provider generation;
     a live rotation while the context is active hard-fails BEFORE D.features
     (base class — not swallowable by the self-heal catch). Formal contexts
     built under the CURRENT generation still self-heal pre-run stale rows.
  5. M1: "latest row" = append order under file_lock, not the second-
     precision recorded_at timestamp.
  6. M2: a POSITIVE probe that the in-process Qlib binding points at a
     non-live provider dir fails closed; an inconclusive probe proceeds.
"""
from __future__ import annotations

import logging
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from src.research_orchestrator import qlib_windowed_features as qwf_mod
from src.research_orchestrator.cache_manifest import (
    CacheContext,
    CacheKeyMismatchError,
    CacheManifestStore,
    ProviderGenerationMismatchError,
)
from src.research_orchestrator.qlib_windowed_features import _deterministic_cache_path
from src.research_orchestrator.research_access_context import (
    ResearchAccessContext,
    research_access_context,
)

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
        latest = rows.iloc[-1]  # append order (GPT M1), not timestamp sort
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
        latest = manifest.list_events(cache_key=_cache_key()).iloc[-1]
        assert latest["provider_build_id"] == LIVE_BUILD

    def test_no_prior_row_stays_silent(self, tmp_path, caplog):
        with caplog.at_level(logging.WARNING, logger=qwf_mod.__name__):
            _call(tmp_path)
        assert not any(WARNING_MARK in r.message for r in caplog.records)


def _pin_ctx(build_id: str, policy_id: str) -> ResearchAccessContext:
    return ResearchAccessContext(
        run_id="r1",
        step_id="s1",
        stage="is_validation",
        design_hash="d" * 8,
        allowed_start=pd.Timestamp("2021-01-01"),
        allowed_end=pd.Timestamp("2021-12-31"),
        provider_build_id=build_id,
        calendar_policy_id=policy_id,
    )


class TestFormalRunGenerationPin:
    """GPT B1: an active ResearchAccessContext pins the run's provider
    generation — a live rotation while the context is active hard-fails
    BEFORE D.features, with the base class (not swallowable)."""

    def test_mid_run_rotation_hard_fails_before_dfeatures(self, tmp_path):
        # Run started under ctx_build; live has rotated to LIVE_BUILD.
        manifest = _seed_row(tmp_path, build_id="ctx_build", policy_id=LIVE_POLICY)
        calls = {"n": 0}

        def counting_features(*a, **k):
            calls["n"] += 1
            return pd.DataFrame()

        sys.modules["qlib.data"].D = types.SimpleNamespace(features=counting_features)
        with research_access_context(_pin_ctx("ctx_build", LIVE_POLICY)):
            with pytest.raises(CacheKeyMismatchError, match="changed during an active") as ei:
                _call(tmp_path)
        assert not isinstance(ei.value, ProviderGenerationMismatchError)
        assert calls["n"] == 0  # D.features never reached
        # Nothing appended — the manifest still holds only the seeded row.
        assert len(manifest.list_events(cache_key=_cache_key())) == 1

    def test_formal_context_under_current_generation_still_heals_stale_rows(
        self, tmp_path, caplog
    ):
        # Run started AFTER the rotation: the context pins the live
        # generation, so a PRE-run stale row self-heals (GPT answer 4c: formal
        # runs may self-heal only when the context was built under the new
        # provider id).
        manifest = _seed_row(tmp_path, build_id="old_build", policy_id="old_policy")
        with caplog.at_level(logging.WARNING, logger=qwf_mod.__name__):
            with research_access_context(_pin_ctx(LIVE_BUILD, LIVE_POLICY)):
                _call(tmp_path)
        assert sum(WARNING_MARK in r.message for r in caplog.records) == 1
        rows = manifest.list_events(cache_key=_cache_key())
        assert len(rows) == 2
        assert rows.iloc[-1]["provider_build_id"] == LIVE_BUILD


class TestLatestRowAppendOrder:
    """GPT M1: "latest" = append order under file_lock, not the second-
    precision recorded_at (ambiguous same-second; wrong under clock skew)."""

    def test_latest_row_uses_append_order_not_second_precision_timestamp(self, tmp_path):
        manifest = _seed_row(tmp_path, build_id="old_build", policy_id="old_policy")
        _seed_row(tmp_path, build_id=LIVE_BUILD, policy_id=LIVE_POLICY)
        frame = pd.read_parquet(manifest.log_path)
        # Adversarial clock skew: the STALE first row carries a LATER
        # recorded_at than the fresh appended row. A timestamp sort would pick
        # the stale row (raise); append order picks the fresh row (pass).
        frame.loc[0, "recorded_at"] = "2026-07-02 00:00:01"
        frame.loc[1, "recorded_at"] = "2026-07-02 00:00:00"
        frame.to_parquet(manifest.log_path, index=False)
        manifest.assert_cache_reusable(  # must NOT raise
            cache_key=_cache_key(),
            cache_path=_cache_key(),
            cache_context=CacheContext(),
            stage=STAGE,
            window_start=START,
            window_end=END,
            cache_type="qlib_features",
            provider_build_id=LIVE_BUILD,
            calendar_policy_id=LIVE_POLICY,
        )


class TestLiveBindingGuard:
    """GPT M2: a POSITIVE probe that the in-process Qlib binding points at a
    non-live provider dir fails closed; an inconclusive probe proceeds."""

    def test_positive_mismatch_fails_closed(self, tmp_path, monkeypatch):
        import src.data_infra.provider_context as ctx_mod

        monkeypatch.setattr(
            ctx_mod, "qlib_bound_provider_dir", lambda: Path("E:/archived_provider_slot")
        )
        monkeypatch.setattr(
            ctx_mod, "live_qlib_provider_dir", lambda: Path("E:/live_provider")
        )
        with pytest.raises(CacheKeyMismatchError, match="live-provider door") as ei:
            _call(tmp_path)
        assert not isinstance(ei.value, ProviderGenerationMismatchError)

    def test_matching_binding_proceeds(self, tmp_path, monkeypatch):
        import src.data_infra.provider_context as ctx_mod

        same = Path("E:/live_provider")
        monkeypatch.setattr(ctx_mod, "qlib_bound_provider_dir", lambda: same)
        monkeypatch.setattr(ctx_mod, "live_qlib_provider_dir", lambda: same)
        assert _call(tmp_path).empty

    def test_inconclusive_probe_proceeds(self, tmp_path):
        # The autouse qlib stub has no qlib.config submodule → probe is
        # inconclusive → the read proceeds (not evidence of a wrong binding).
        import src.data_infra.provider_context as ctx_mod

        assert ctx_mod.qlib_bound_provider_dir() is None
        assert _call(tmp_path).empty

    def test_probe_reads_dpm_provider_uri_dict(self, tmp_path, monkeypatch):
        import src.data_infra.provider_context as ctx_mod

        cfg_mod = types.ModuleType("qlib.config")
        cfg_mod.C = types.SimpleNamespace(
            dpm=types.SimpleNamespace(provider_uri={"__DEFAULT_FREQ": str(tmp_path)})
        )
        monkeypatch.setitem(sys.modules, "qlib.config", cfg_mod)
        assert ctx_mod.qlib_bound_provider_dir() == tmp_path.resolve()


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
