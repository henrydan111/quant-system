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
