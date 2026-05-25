"""Validation profile cache-context propagation regression for plan
``snappy-buzzing-meerkat`` v5 Part D.

Pre-fix: ``handle_validation_event_backtest_is`` invoked
``run_event_driven_window`` outside ``_run_with_cache_context``, so
``QlibDataFeeder.preload_features`` used an empty ``CacheContext`` and
manifest rows were written with empty ``design_hash``. The audit trail was
permanently wrong.

Post-fix: the validation handlers wrap the call in
``_run_with_cache_context(context, ...)``. The thread-local CacheContext
inheritance in ``qlib_windowed_features.get_cache_context()`` then carries
the real design_hash into manifest rows.

This test exercises the propagation directly without a full DAG run by
constructing a minimal ``StepExecutionContext`` and routing the wrapper
through a stub ``run_event_driven_window`` that calls
``qlib_windowed_features`` against an isolated manifest dir.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd

from src.research_orchestrator.cache_manifest import (
    CacheContext,
    CacheManifestStore,
)
from src.research_orchestrator.qlib_windowed_features import qlib_windowed_features


OHLCV_FIELDS = [
    "$open", "$close", "$high", "$low",
    "$vol", "$amount", "$pre_close", "$adj_factor",
]


# ─────────────────────────────────────────────────────────────────────────────
# Minimal StepExecutionContext stand-in
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _Step:
    step_id: str
    capability: str = "event_driven_backtest"
    config: dict | None = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}


@dataclass
class _Profile:
    profile_id: str = "hypothesis_validation"


@dataclass
class _Hypothesis:
    hypothesis_id: str = "hyp_test"
    _design_hash: str = "deadbeef" * 4

    def design_hash(self) -> str:
        return self._design_hash

    def structural_family(self) -> str:
        return "test_family"


@dataclass
class _Request:
    hypothesis: _Hypothesis | None = None


@dataclass
class _MinimalContext:
    request: _Request
    profile: _Profile
    step: _Step
    run_dir: Path
    state: dict
    resumed: bool = False
    registry_dirs: dict | None = None
    step_dir: Path | None = None


def _make_context(*, design_hash: str, run_dir: Path) -> _MinimalContext:
    hypothesis = _Hypothesis(_design_hash=design_hash)
    step = _Step(step_id="validation_event_backtest_is")
    step_dir = run_dir / "steps" / step.step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    return _MinimalContext(
        request=_Request(hypothesis=hypothesis),
        profile=_Profile(),
        step=step,
        run_dir=run_dir,
        state={},
        registry_dirs={"holdout_seal_dir": str(run_dir / "_seal")},
        step_dir=step_dir,
    )


def _stub_d_features(*_args, **_kwargs):
    idx = pd.MultiIndex.from_product(
        [["000001_SZ"], pd.date_range("2021-01-04", periods=3, freq="D")],
        names=("instrument", "datetime"),
    )
    return pd.DataFrame({f: 1.0 for f in OHLCV_FIELDS}, index=idx)


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_run_with_cache_context_propagates_design_hash_to_manifest(tmp_path: Path):
    """Calling ``qlib_windowed_features`` from inside ``_run_with_cache_context``
    with our minimal context must result in a manifest row whose
    ``design_hash`` matches the hypothesis design_hash.
    """
    from src.research_orchestrator.steps import _run_with_cache_context

    manifest_dir = tmp_path / "manifest"
    target_design_hash = "abc123" * 4

    ctx = _make_context(design_hash=target_design_hash, run_dir=tmp_path / "run")

    def _inner(**kwargs):
        # The simulated leaf call: invoke qlib_windowed_features with an
        # EMPTY CacheContext (mirroring data_feeder.preload_features at line
        # 115 — the context is inherited via thread-local rather than
        # explicit kwarg).
        mock_D = MagicMock()
        mock_D.features.side_effect = _stub_d_features
        with patch("qlib.data.D", mock_D):
            return qlib_windowed_features(
                instruments=["000001_SZ"],
                fields=OHLCV_FIELDS,
                start_time="2021-01-04",
                end_time="2021-01-08",
                cache_context=CacheContext(),  # empty: relies on inheritance
                stage="is_only",
                cache_manifest_dir=manifest_dir,
            )

    _run_with_cache_context(ctx, _inner)

    # Verify the manifest row carries the real design_hash, not empty.
    manifest = CacheManifestStore(manifest_dir)
    rows = manifest.list_events()
    assert len(rows) == 1
    assert rows.iloc[0]["design_hash"] == target_design_hash
    assert rows.iloc[0]["design_hash"] != ""


def test_without_run_with_cache_context_design_hash_is_empty(tmp_path: Path):
    """Pre-fix regression: without the ``_run_with_cache_context`` wrap, a
    call that passes ``CacheContext()`` writes an empty design_hash. This
    test pins the bad behavior so we know Part D is the only fix path.
    """
    manifest_dir = tmp_path / "manifest"

    mock_D = MagicMock()
    mock_D.features.side_effect = _stub_d_features
    with patch("qlib.data.D", mock_D):
        qlib_windowed_features(
            instruments=["000001_SZ"],
            fields=OHLCV_FIELDS,
            start_time="2021-01-04",
            end_time="2021-01-08",
            cache_context=CacheContext(),
            stage="is_only",
            cache_manifest_dir=manifest_dir,
        )

    manifest = CacheManifestStore(manifest_dir)
    rows = manifest.list_events()
    assert len(rows) == 1
    assert rows.iloc[0]["design_hash"] == ""


def test_part_e_stage_propagates_through_data_feeder(tmp_path: Path):
    """Part E: ``QlibDataFeeder`` constructed with stage='oos_test' writes
    manifest rows with stage='oos_test', not the legacy hardcoded
    'is_only'. This previously produced wrong audit trails on OOS runs.
    """
    from src.backtest_engine.event_driven.data_feeder import QlibDataFeeder

    class _FakeFeeder(QlibDataFeeder):
        def __init__(self, *, stage: str):
            self._cache_df = None
            self._latest_adj = {}
            self._stage = stage
            # Match instrumentation attrs added by the v5 instrumentation.
            self._preload_status = "not_attempted"
            self._preload_wall_seconds = 0.0
            self._cache_hit_count = 0
            self._direct_fallback_count = 0

    manifest_dir = tmp_path / "manifest"
    feeder = _FakeFeeder(stage="oos_test")

    def _routed(**kwargs):
        kwargs["cache_manifest_dir"] = manifest_dir
        mock_D = MagicMock()
        mock_D.features.side_effect = _stub_d_features
        with patch("qlib.data.D", mock_D):
            return qlib_windowed_features(**kwargs)

    with patch(
        "src.backtest_engine.event_driven.data_feeder.qlib_windowed_features",
        side_effect=_routed,
    ), patch(
        "src.backtest_engine.event_driven.data_feeder.D"
    ) as mock_d:
        mock_d.instruments.return_value = ["000001_SZ"]
        feeder.preload_features("all", OHLCV_FIELDS, "2021-01-04", "2021-01-08")

    manifest = CacheManifestStore(manifest_dir)
    rows = manifest.list_events()
    assert len(rows) == 1
    # Without Part E, this row would have stage="is_only" (the old hardcode).
    assert rows.iloc[0]["stage"] == "oos_test"
