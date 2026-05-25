"""Cache-manifest collision regression for plan ``snappy-buzzing-meerkat`` v5.

Pre-fix behavior: a hypothesis preloading raw OHLCV through
``QlibDataFeeder.preload_features`` could collide with a prior hypothesis's
manifest row on the same OHLCV cache_key, raising ``CacheKeyMismatchError``
that the feeder silently swallowed (data_feeder.py:129) — leaving
``_cache_df=None`` and degrading to per-day ``D.features`` queries.

Post-fix behavior:
* ``preload_features(strict=True)`` re-raises on a real failure (e.g. stage
  mismatch, which Part B does NOT relax).
* ``preload_features(strict=False)`` continues to log ERROR and leave
  ``_cache_df=None`` for backward compatibility.

These tests do NOT spin up the real Qlib provider; they exercise the
manifest plumbing by monkeypatching the leaf ``qlib_windowed_features`` so
the failure mode is reproducible without any external data.
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.backtest_engine.event_driven.data_feeder import QlibDataFeeder
from src.research_orchestrator.cache_manifest import (
    CacheContext,
    CacheKeyMismatchError,
    CacheManifestStore,
)
from src.research_orchestrator.qlib_windowed_features import (
    _deterministic_cache_path,
    qlib_windowed_features,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

OHLCV_FIELDS = [
    "$open", "$close", "$high", "$low",
    "$vol", "$amount", "$pre_close", "$adj_factor",
]
START = "2021-01-04"
END = "2021-01-08"
FREQ = "day"


def _seed_collision(manifest_dir: Path, *, design_hash: str, stage: str) -> dict:
    """Write a manifest row that will collide with a fresh preload call.

    Mirrors what ``qlib_windowed_features`` would have written under a prior
    run with a different design_hash. Returns the recorded row.
    """
    cache_key = _deterministic_cache_path(FREQ, OHLCV_FIELDS, START, END)
    manifest = CacheManifestStore(manifest_dir)
    row = manifest.record_cache_write(
        cache_type="qlib_features",
        cache_key=cache_key,
        cache_path=cache_key,
        cache_context=CacheContext(design_hash=design_hash),
        stage=stage,
        window_start=START,
        window_end=END,
    )
    return row


def _stub_d_features(*_args, **_kwargs):
    """A tiny non-empty MultiIndex frame so tests can run without Qlib.

    The structure (instrument, datetime) MultiIndex matters for
    ``QlibDataFeeder.preload_features`` post-processing.
    """
    idx = pd.MultiIndex.from_product(
        [["000001_SZ", "000002_SZ"], pd.date_range("2021-01-04", periods=3, freq="D")],
        names=("instrument", "datetime"),
    )
    return pd.DataFrame(
        {f: 1.0 for f in OHLCV_FIELDS},
        index=idx,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Part B: design_hash mismatch on cache_type='qlib_features' is now permitted
# ─────────────────────────────────────────────────────────────────────────────

def test_design_hash_collision_on_qlib_features_does_not_raise(tmp_path: Path):
    """Two hypotheses with different design_hashes loading the SAME OHLCV
    window must both succeed under cache_type='qlib_features' (Part B).
    """
    manifest_dir = tmp_path / "manifest"
    _seed_collision(manifest_dir, design_hash="hyp_A_hash", stage="is_only")

    # Now call qlib_windowed_features under hyp_B's design_hash.
    mock_D = MagicMock()
    mock_D.features.side_effect = _stub_d_features
    with patch("qlib.data.D", mock_D):
        df = qlib_windowed_features(
            instruments=["000001_SZ"],
            fields=OHLCV_FIELDS,
            start_time=START,
            end_time=END,
            cache_context=CacheContext(design_hash="hyp_B_hash"),
            stage="is_only",
            cache_manifest_dir=manifest_dir,
        )

    assert not df.empty
    # Both rows recorded.
    manifest = CacheManifestStore(manifest_dir)
    rows = manifest.list_events()
    assert len(rows) == 2
    assert set(rows["design_hash"].tolist()) == {"hyp_A_hash", "hyp_B_hash"}


def test_stage_mismatch_still_raises_under_qlib_features(tmp_path: Path):
    """Part B relaxes design_hash but NOT stage — stage mismatch must still
    raise so an OOS row never silently aliases an IS row.
    """
    manifest_dir = tmp_path / "manifest"
    _seed_collision(manifest_dir, design_hash="hyp_A_hash", stage="is_only")

    mock_D = MagicMock()
    mock_D.features.side_effect = _stub_d_features
    with patch("qlib.data.D", mock_D):
        with pytest.raises(CacheKeyMismatchError, match="stage"):
            qlib_windowed_features(
                instruments=["000001_SZ"],
                fields=OHLCV_FIELDS,
                start_time=START,
                end_time=END,
                cache_context=CacheContext(design_hash="hyp_B_hash"),
                stage="oos_test",
                cache_manifest_dir=manifest_dir,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2.a: strict-mode plumbing in QlibDataFeeder.preload_features
# ─────────────────────────────────────────────────────────────────────────────

class _FakeFeeder(QlibDataFeeder):
    """QlibDataFeeder with __init__ stubbed so we don't need a Qlib provider.

    Only ``_cache_df``, ``_latest_adj``, and ``_stage`` are needed for
    ``preload_features`` plumbing tests.
    """

    def __init__(self, *, stage: str = "is_only"):  # noqa: D401
        self._cache_df = None
        self._latest_adj = {}
        self._stage = stage
        # Match instrumentation attrs added by the v5 instrumentation.
        self._preload_status = "not_attempted"
        self._preload_wall_seconds = 0.0
        self._cache_hit_count = 0
        self._direct_fallback_count = 0


def test_preload_features_strict_true_reraises_on_collision(tmp_path: Path, caplog):
    """Strict mode must propagate ``CacheKeyMismatchError`` so a formal run
    fails LOUD instead of silently degrading to per-day fallback.
    """
    manifest_dir = tmp_path / "manifest"
    # Seed a stage-mismatching row so Part B does NOT relax the failure
    # (we keep the OHLCV cache_key but force stage to "oos_test"; a fresh
    # IS preload will then trip the stage guard).
    _seed_collision(manifest_dir, design_hash="hyp_A_hash", stage="oos_test")

    feeder = _FakeFeeder(stage="is_only")

    def _raising_qlib_windowed_features(**kwargs):
        # Force the manifest dir to the temp one; then call the real wrapper.
        kwargs["cache_manifest_dir"] = manifest_dir
        mock_D = MagicMock()
        mock_D.features.side_effect = _stub_d_features
        with patch("qlib.data.D", mock_D):
            return qlib_windowed_features(**kwargs)

    with patch(
        "src.backtest_engine.event_driven.data_feeder.qlib_windowed_features",
        side_effect=_raising_qlib_windowed_features,
    ), patch(
        "src.backtest_engine.event_driven.data_feeder.D"
    ) as mock_d:
        mock_d.instruments.return_value = ["000001_SZ"]

        caplog.set_level(logging.ERROR)
        with pytest.raises(CacheKeyMismatchError, match="stage"):
            feeder.preload_features(
                "all", OHLCV_FIELDS, START, END, strict=True,
            )

    # ERROR log fires on first failure regardless of strict.
    assert any(
        "Failed to preload Qlib features" in rec.getMessage()
        for rec in caplog.records
    )
    assert feeder._cache_df is None


def test_preload_features_strict_false_logs_and_keeps_legacy_behavior(
    tmp_path: Path, caplog,
):
    """Default ``strict=False`` keeps the legacy best-effort path (logs
    ERROR, leaves ``_cache_df=None``). Discovery profiles rely on this.
    """
    manifest_dir = tmp_path / "manifest"
    _seed_collision(manifest_dir, design_hash="hyp_A_hash", stage="oos_test")

    feeder = _FakeFeeder(stage="is_only")

    def _raising_qlib_windowed_features(**kwargs):
        kwargs["cache_manifest_dir"] = manifest_dir
        mock_D = MagicMock()
        mock_D.features.side_effect = _stub_d_features
        with patch("qlib.data.D", mock_D):
            return qlib_windowed_features(**kwargs)

    with patch(
        "src.backtest_engine.event_driven.data_feeder.qlib_windowed_features",
        side_effect=_raising_qlib_windowed_features,
    ), patch(
        "src.backtest_engine.event_driven.data_feeder.D"
    ) as mock_d:
        mock_d.instruments.return_value = ["000001_SZ"]

        caplog.set_level(logging.ERROR)
        # Should NOT raise.
        feeder.preload_features(
            "all", OHLCV_FIELDS, START, END, strict=False,
        )

    assert feeder._cache_df is None  # legacy fallthrough
    assert any(
        "Failed to preload Qlib features" in rec.getMessage()
        for rec in caplog.records
    )


def test_preload_features_succeeds_when_design_hash_collides_under_qlib_features(
    tmp_path: Path,
):
    """End-to-end: feeder.preload_features under hyp_B succeeds even though
    hyp_A already wrote a manifest row for the same OHLCV window. Proves
    Part B's relaxation reaches the feeder layer; ``_cache_df`` is populated.
    """
    manifest_dir = tmp_path / "manifest"
    _seed_collision(manifest_dir, design_hash="hyp_A_hash", stage="is_only")

    feeder = _FakeFeeder(stage="is_only")

    def _routed_qlib_windowed_features(**kwargs):
        kwargs["cache_manifest_dir"] = manifest_dir
        mock_D = MagicMock()
        mock_D.features.side_effect = _stub_d_features
        with patch("qlib.data.D", mock_D):
            return qlib_windowed_features(**kwargs)

    with patch(
        "src.backtest_engine.event_driven.data_feeder.qlib_windowed_features",
        side_effect=_routed_qlib_windowed_features,
    ), patch(
        "src.backtest_engine.event_driven.data_feeder.D"
    ) as mock_d:
        mock_d.instruments.return_value = ["000001_SZ"]

        feeder.preload_features("all", OHLCV_FIELDS, START, END, strict=True)

    assert feeder._cache_df is not None
    assert not feeder._cache_df.empty
