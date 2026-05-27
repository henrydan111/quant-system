"""PR 2 negative-test suite — preload hardening.

Covers the gates the plan committed to:
  1. feeder.preload(start, end) raises NotImplementedError
  2. assert_preloaded raises on preload_status != "success"
  3. assert_preloaded raises on missing required fields
  4. assert_preloaded raises on cache window too short on either side
  5. assert_preloaded raises on direct_fallback_count > 0 with require_zero_fallback=True
  6. EventDrivenBacktester.run() unions ENGINE_REQUIRED_FIELDS into the preload payload
  7. should_preload auto-True for formal run_mode even when preload_fields is None
  8. strict + require_preloaded auto-True for formal run_mode

The tests mock ``QlibDataFeeder`` so they do not require a live Qlib provider.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.backtest_engine.event_driven import EventDrivenBacktester
from src.backtest_engine.event_driven.constants import (
    ENGINE_REQUIRED_FIELDS,
    ENGINE_REQUIRED_FIELDS_SET,
    FORMAL_RUN_MODES,
)
from src.backtest_engine.event_driven.data_feeder import QlibDataFeeder


class TestEngineRequiredFieldsContract:
    """Sanity contract: ENGINE_REQUIRED_FIELDS matches what the engine fetches."""

    def test_required_fields_includes_canonical_ohlcv(self) -> None:
        for f in ("$open", "$close", "$high", "$low", "$vol", "$amount"):
            assert f in ENGINE_REQUIRED_FIELDS_SET

    def test_required_fields_includes_adj_factor(self) -> None:
        assert "$adj_factor" in ENGINE_REQUIRED_FIELDS_SET

    def test_required_fields_includes_pre_close(self) -> None:
        assert "$pre_close" in ENGINE_REQUIRED_FIELDS_SET

    def test_formal_modes_present(self) -> None:
        assert "formal" in FORMAL_RUN_MODES
        assert "oos_test" in FORMAL_RUN_MODES
        assert "joinquant_replication" in FORMAL_RUN_MODES


class _FakeFeeder:
    """Minimal QlibDataFeeder stand-in for assert_preloaded tests.

    Real QlibDataFeeder.__init__ touches qlib.init(), so we bypass it and
    populate just the attributes assert_preloaded reads.
    """

    def __init__(self, cache_df: pd.DataFrame | None, status: str = "success",
                 fallback_count: int = 0):
        self._cache_df = cache_df
        self._preload_status = status
        self._direct_fallback_count = fallback_count

    # Bind the real method onto the fake so we exercise the actual logic.
    assert_preloaded = QlibDataFeeder.assert_preloaded


def _make_cache_df(fields: list[str], start: str, end: str) -> pd.DataFrame:
    """Build a small MultiIndex(instrument, datetime) DataFrame for tests."""
    dates = pd.date_range(start, end, freq="D")
    idx = pd.MultiIndex.from_product([["000001_SZ"], dates], names=["instrument", "datetime"])
    return pd.DataFrame({f: [1.0] * len(dates) for f in fields}, index=idx)


class TestPreloadRaises:
    def test_deprecated_preload_raises(self) -> None:
        # Instantiate the real class without touching qlib.init by using __new__.
        feeder = QlibDataFeeder.__new__(QlibDataFeeder)
        with pytest.raises(NotImplementedError, match="preload_features"):
            feeder.preload(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31"))


class TestAssertPreloadedNegatives:
    def test_not_attempted_raises(self) -> None:
        feeder = _FakeFeeder(None, status="not_attempted")
        with pytest.raises(RuntimeError, match="preload_status='not_attempted'"):
            feeder.assert_preloaded(
                required_fields=ENGINE_REQUIRED_FIELDS,
                start=pd.Timestamp("2024-01-02"),
                end=pd.Timestamp("2024-01-31"),
            )

    def test_swallowed_exception_raises(self) -> None:
        feeder = _FakeFeeder(None, status="swallowed_exception")
        with pytest.raises(RuntimeError, match="preload_status='swallowed_exception'"):
            feeder.assert_preloaded(
                required_fields=ENGINE_REQUIRED_FIELDS,
                start=pd.Timestamp("2024-01-02"),
                end=pd.Timestamp("2024-01-31"),
            )

    def test_empty_cache_raises(self) -> None:
        feeder = _FakeFeeder(pd.DataFrame())
        with pytest.raises(RuntimeError, match="cache is empty"):
            feeder.assert_preloaded(
                required_fields=ENGINE_REQUIRED_FIELDS,
                start=pd.Timestamp("2024-01-02"),
                end=pd.Timestamp("2024-01-31"),
            )

    def test_missing_field_raises(self) -> None:
        # Cache has only 6 fields (missing $pre_close and $adj_factor)
        partial = ["$open", "$close", "$high", "$low", "$vol", "$amount"]
        df = _make_cache_df(partial, "2024-01-01", "2024-02-01")
        feeder = _FakeFeeder(df)
        with pytest.raises(RuntimeError, match=r"missing required fields"):
            feeder.assert_preloaded(
                required_fields=ENGINE_REQUIRED_FIELDS,
                start=pd.Timestamp("2024-01-02"),
                end=pd.Timestamp("2024-01-31"),
            )

    def test_cache_min_after_start_raises(self) -> None:
        df = _make_cache_df(list(ENGINE_REQUIRED_FIELDS), "2024-01-15", "2024-02-01")
        feeder = _FakeFeeder(df)
        with pytest.raises(RuntimeError, match="cache_min"):
            feeder.assert_preloaded(
                required_fields=ENGINE_REQUIRED_FIELDS,
                start=pd.Timestamp("2024-01-02"),  # before cache_min
                end=pd.Timestamp("2024-01-31"),
            )

    def test_cache_max_before_end_raises(self) -> None:
        df = _make_cache_df(list(ENGINE_REQUIRED_FIELDS), "2024-01-01", "2024-01-15")
        feeder = _FakeFeeder(df)
        with pytest.raises(RuntimeError, match="cache_max"):
            feeder.assert_preloaded(
                required_fields=ENGINE_REQUIRED_FIELDS,
                start=pd.Timestamp("2024-01-02"),
                end=pd.Timestamp("2024-01-31"),  # after cache_max
            )

    def test_nonzero_fallback_raises(self) -> None:
        df = _make_cache_df(list(ENGINE_REQUIRED_FIELDS), "2024-01-01", "2024-02-01")
        feeder = _FakeFeeder(df, fallback_count=3)
        with pytest.raises(RuntimeError, match="direct_fallback_count=3"):
            feeder.assert_preloaded(
                required_fields=ENGINE_REQUIRED_FIELDS,
                start=pd.Timestamp("2024-01-02"),
                end=pd.Timestamp("2024-01-31"),
                require_zero_fallback=True,
            )

    def test_nonzero_fallback_allowed_when_flag_false(self) -> None:
        df = _make_cache_df(list(ENGINE_REQUIRED_FIELDS), "2024-01-01", "2024-02-01")
        feeder = _FakeFeeder(df, fallback_count=3)
        # Should not raise when require_zero_fallback=False
        feeder.assert_preloaded(
            required_fields=ENGINE_REQUIRED_FIELDS,
            start=pd.Timestamp("2024-01-02"),
            end=pd.Timestamp("2024-01-31"),
            require_zero_fallback=False,
        )

    def test_happy_path_passes(self) -> None:
        df = _make_cache_df(list(ENGINE_REQUIRED_FIELDS), "2024-01-01", "2024-02-01")
        feeder = _FakeFeeder(df)
        feeder.assert_preloaded(
            required_fields=ENGINE_REQUIRED_FIELDS,
            start=pd.Timestamp("2024-01-02"),
            end=pd.Timestamp("2024-01-31"),
        )


class TestWrapperPreloadCondition:
    """EventDrivenBacktester.run() — should_preload + field union + strict promotion."""

    def _run_with_mocked_components(self, tmp_path: Path, **run_kwargs):
        strategy = MagicMock()
        with patch("src.backtest_engine.event_driven.QlibDataFeeder") as feeder_cls, patch(
            "src.backtest_engine.event_driven.Exchange"
        ), patch("src.backtest_engine.event_driven.BacktestEngine") as engine_cls:
            feeder = feeder_cls.return_value
            engine = engine_cls.return_value
            engine.run.return_value = MagicMock(config={})
            EventDrivenBacktester(data_dir=str(tmp_path)).run(
                strategy=strategy,
                start_time="2024-01-02",
                end_time="2024-01-31",
                **run_kwargs,
            )
        return feeder_cls, feeder, engine_cls

    def test_no_preload_when_sandbox_and_no_fields(self, tmp_path: Path) -> None:
        _, feeder, engine_cls = self._run_with_mocked_components(tmp_path)
        feeder.preload_features.assert_not_called()
        # require_preloaded should be False by default
        assert engine_cls.call_args.kwargs["require_preloaded"] is False

    def test_preload_fields_triggers_preload_and_unions_engine_fields(self, tmp_path: Path) -> None:
        _, feeder, _ = self._run_with_mocked_components(
            tmp_path, preload_fields=["$turnover_rate", "$pe_ttm"]
        )
        feeder.preload_features.assert_called_once()
        _args, kwargs = feeder.preload_features.call_args
        # positional: 'all', fields, start, end
        called_args = feeder.preload_features.call_args.args
        called_fields = called_args[1]
        for required in ENGINE_REQUIRED_FIELDS:
            assert required in called_fields, f"engine field {required} missing"
        assert "$turnover_rate" in called_fields
        assert "$pe_ttm" in called_fields

    def test_formal_run_mode_auto_enables_preload(self, tmp_path: Path) -> None:
        _, feeder, engine_cls = self._run_with_mocked_components(
            tmp_path, run_mode="formal"
        )
        feeder.preload_features.assert_called_once()
        called_args = feeder.preload_features.call_args.args
        called_fields = called_args[1]
        for required in ENGINE_REQUIRED_FIELDS:
            assert required in called_fields
        # strict should be True for formal mode
        assert feeder.preload_features.call_args.kwargs["strict"] is True
        # require_preloaded should be True for formal mode
        assert engine_cls.call_args.kwargs["require_preloaded"] is True

    def test_oos_test_run_mode_auto_enables_preload(self, tmp_path: Path) -> None:
        _, feeder, engine_cls = self._run_with_mocked_components(
            tmp_path, run_mode="oos_test"
        )
        feeder.preload_features.assert_called_once()
        assert feeder.preload_features.call_args.kwargs["strict"] is True
        assert engine_cls.call_args.kwargs["require_preloaded"] is True

    def test_joinquant_replication_auto_enables_preload(self, tmp_path: Path) -> None:
        _, feeder, engine_cls = self._run_with_mocked_components(
            tmp_path, run_mode="joinquant_replication"
        )
        feeder.preload_features.assert_called_once()
        assert engine_cls.call_args.kwargs["require_preloaded"] is True

    def test_sandbox_mode_does_not_auto_enable(self, tmp_path: Path) -> None:
        _, feeder, engine_cls = self._run_with_mocked_components(
            tmp_path, run_mode="sandbox"
        )
        feeder.preload_features.assert_not_called()
        assert engine_cls.call_args.kwargs["require_preloaded"] is False

    def test_preload_required_kwarg_overrides_sandbox(self, tmp_path: Path) -> None:
        _, feeder, engine_cls = self._run_with_mocked_components(
            tmp_path, preload_required=True
        )
        feeder.preload_features.assert_called_once()
        called_args = feeder.preload_features.call_args.args
        called_fields = called_args[1]
        for required in ENGINE_REQUIRED_FIELDS:
            assert required in called_fields
        assert engine_cls.call_args.kwargs["require_preloaded"] is True

    def test_preload_strict_kwarg_preserved_outside_formal_modes(self, tmp_path: Path) -> None:
        _, feeder, _ = self._run_with_mocked_components(
            tmp_path, preload_fields=["$turnover_rate"], preload_strict=True
        )
        assert feeder.preload_features.call_args.kwargs["strict"] is True
