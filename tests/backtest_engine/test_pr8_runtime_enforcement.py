"""PR 8 negative-test suite — formal-runtime enforcement fixes.

Covers each fix the PR 8 plan committed to:
  1. Execution profile with allowed_for_formal=True implies is_formal even
     when run_mode=None → strict preload + require_preloaded auto-enabled.
  2. strict_cache_only raises PreloadCoverageError on first cache miss
     during the day loop.
  3. Formal run with calendar-policy mismatch raises at the runtime
     provider validator (not just at daily QA).
  5. release_gate flags execution_profile_hash mismatch as a distinct reason.
  6. override_diff records object overrides as {class, params} so the
     override is replayable.
  8. require_research_access_context raises in formal stages without
     an active context; sandbox stages return None tolerantly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.backtest_engine.event_driven import EventDrivenBacktester
from src.backtest_engine.event_driven.data_feeder import (
    PreloadCoverageError,
    QlibDataFeeder,
)


def _stub_manifest():
    return MagicMock(
        provider_build_id="prod_test_001",
        provider=MagicMock(calendar_end_date="2026-02-27"),
        event_endpoint_namespacing=MagicMock(status="enforced"),
    )


def _run_with_mocks(tmp_path: Path, **run_kwargs):
    strategy = MagicMock()
    with patch("src.backtest_engine.event_driven.QlibDataFeeder") as feeder_cls, patch(
        "src.backtest_engine.event_driven.Exchange"
    ), patch("src.backtest_engine.event_driven.BacktestEngine") as engine_cls, patch(
        "src.backtest_engine.event_driven.load_provider_manifest", return_value=_stub_manifest(),
    ), patch(
        "src.backtest_engine.event_driven._validate_provider_at_runtime"
    ):
        feeder = feeder_cls.return_value
        engine = engine_cls.return_value
        engine.run.return_value = MagicMock(config={})
        # PR 8a fix #1: formal runs require calendar_policy_id.
        run_kwargs.setdefault("calendar_policy_id", "frozen_20260227_system_build")
        EventDrivenBacktester(data_dir=str(tmp_path)).run(
            strategy=strategy,
            start_time="2024-01-02",
            end_time="2024-01-31",
            **run_kwargs,
        )
    return feeder_cls, feeder, engine_cls


class TestFix1ProfileImpliesFormal:
    """A formal execution_profile with run_mode=None should still be formal."""

    def test_joinquant_daily_sim_alone_auto_enables_preload(self, tmp_path: Path) -> None:
        _, feeder, engine_cls = _run_with_mocks(
            tmp_path, execution_profile="joinquant_daily_sim", run_mode=None,
        )
        feeder.preload_features.assert_called_once()
        kwargs = feeder.preload_features.call_args.kwargs
        assert kwargs.get("strict") is True
        assert engine_cls.call_args.kwargs["require_preloaded"] is True

    def test_realistic_china_stress_not_formal_does_not_auto_preload(self, tmp_path: Path) -> None:
        _, feeder, engine_cls = _run_with_mocks(
            tmp_path, execution_profile="realistic_china_stress", run_mode=None,
        )
        feeder.preload_features.assert_not_called()
        assert engine_cls.call_args.kwargs["require_preloaded"] is False

    def test_explicit_formal_run_mode_still_overrides_non_formal_profile(self, tmp_path: Path) -> None:
        _, feeder, engine_cls = _run_with_mocks(
            tmp_path,
            execution_profile="realistic_china_stress",
            run_mode="formal",
        )
        feeder.preload_features.assert_called_once()
        assert engine_cls.call_args.kwargs["require_preloaded"] is True


class TestFix2StrictCacheOnly:
    def _make_feeder_with_cache(self) -> QlibDataFeeder:
        feeder = QlibDataFeeder.__new__(QlibDataFeeder)
        idx = pd.MultiIndex.from_product(
            [["000001_SZ"], pd.date_range("2024-01-01", "2024-01-31")],
            names=["instrument", "datetime"],
        )
        feeder._cache_df = pd.DataFrame({"$close": [1.0] * len(idx)}, index=idx)
        feeder._preload_status = "success"
        feeder._direct_fallback_count = 0
        feeder._cache_hit_count = 0
        feeder._strict_cache_only = False
        feeder._stage = "is_only"
        return feeder

    def test_strict_mode_blocks_cache_miss(self) -> None:
        feeder = self._make_feeder_with_cache()
        feeder.set_strict_cache_only(True)
        with pytest.raises(PreloadCoverageError, match="cache miss"):
            feeder.get_features(
                instruments=["000001_SZ"],
                fields=["$pe_ttm"],
                start_time=pd.Timestamp("2024-01-02"),
                end_time=pd.Timestamp("2024-01-02"),
            )
        assert feeder._direct_fallback_count == 0

    def test_strict_mode_off_falls_back_silently(self) -> None:
        feeder = self._make_feeder_with_cache()
        feeder.set_strict_cache_only(False)
        with patch(
            "src.backtest_engine.event_driven.data_feeder.qlib_windowed_features"
        ) as mock_qwf:
            mock_qwf.return_value = pd.DataFrame()
            feeder.get_features(
                instruments=["000001_SZ"],
                fields=["$pe_ttm"],
                start_time=pd.Timestamp("2024-01-02"),
                end_time=pd.Timestamp("2024-01-02"),
            )
        assert feeder._direct_fallback_count == 1

    def test_strict_mode_allows_cached_fields(self) -> None:
        feeder = self._make_feeder_with_cache()
        feeder.set_strict_cache_only(True)
        out = feeder.get_features(
            instruments=["000001_SZ"],
            fields=["$close"],
            start_time=pd.Timestamp("2024-01-02"),
            end_time=pd.Timestamp("2024-01-02"),
        )
        assert not out.empty


class TestFix3ProviderRuntimeValidation:
    def test_frozen_policy_with_matching_calendar_passes(self) -> None:
        from src.backtest_engine.event_driven import _validate_provider_at_runtime
        manifest = MagicMock(
            provider=MagicMock(calendar_end_date="2026-02-27"),
            event_endpoint_namespacing=MagicMock(status="enforced"),
        )
        with patch("qlib.data.D") as mock_d:
            mock_d.calendar.return_value = [pd.Timestamp("2026-02-27")]
            _validate_provider_at_runtime(
                manifest=manifest,
                calendar_policy_id="frozen_20260227_system_build",
                run_mode="joinquant_replication",
            )

    def test_frozen_policy_with_stale_calendar_raises(self) -> None:
        from src.backtest_engine.event_driven import _validate_provider_at_runtime
        manifest = MagicMock(
            provider=MagicMock(calendar_end_date="2026-02-27"),
            event_endpoint_namespacing=MagicMock(status="enforced"),
        )
        with patch("qlib.data.D") as mock_d:
            mock_d.calendar.return_value = [pd.Timestamp("2026-01-15")]
            with pytest.raises(RuntimeError, match="Frozen calendar policy"):
                _validate_provider_at_runtime(
                    manifest=manifest,
                    calendar_policy_id="frozen_20260227_system_build",
                    run_mode="joinquant_replication",
                )

    def test_disallowed_run_mode_raises(self) -> None:
        from src.backtest_engine.event_driven import _validate_provider_at_runtime
        from src.research_orchestrator.calendar_policy import CalendarPolicyError
        manifest = MagicMock(
            provider=MagicMock(calendar_end_date="2026-02-27"),
            event_endpoint_namespacing=MagicMock(status="enforced"),
        )
        with patch("qlib.data.D") as mock_d:
            mock_d.calendar.return_value = [pd.Timestamp("2026-02-27")]
            with pytest.raises(CalendarPolicyError, match="not in this policy"):
                _validate_provider_at_runtime(
                    manifest=manifest,
                    calendar_policy_id="frozen_20260227_system_build",
                    run_mode="live_paper",
                )


class TestFix5ProfileHashMismatch:
    def test_artifact_with_stale_hash_blocked(self) -> None:
        from src.research_orchestrator.artifact_provenance import (
            ArtifactProvenance,
            attach_provenance,
        )
        from src.research_orchestrator.release_gate import evaluate_artifact_provenance
        config: dict = {}
        attach_provenance(
            config,
            ArtifactProvenance(
                provider_build_id="prod_test",
                calendar_policy_id="frozen_20260227_system_build",
                execution_profile_id="joinquant_daily_sim",
                execution_profile_version="2026-05-26.v1",
                execution_profile_hash="stale" + "0" * 59,
            ),
        )
        result = evaluate_artifact_provenance(config)
        assert result.eligible is False
        assert "execution_profile_hash_mismatch" in result.reasons
        assert result.profile_hash_matches_current is False

    def test_artifact_with_current_hash_passes(self) -> None:
        from src.research_orchestrator.artifact_provenance import (
            ArtifactProvenance,
            attach_provenance,
        )
        from src.research_orchestrator.release_gate import evaluate_artifact_provenance
        from src.backtest_engine.execution_profiles import get_profile
        profile = get_profile("joinquant_daily_sim")
        config: dict = {}
        attach_provenance(
            config,
            ArtifactProvenance(
                provider_build_id="prod_test",
                calendar_policy_id="frozen_20260227_system_build",
                execution_profile_id=profile.profile_id,
                execution_profile_version=profile.profile_version,
                execution_profile_hash=profile.profile_hash,
            ),
        )
        result = evaluate_artifact_provenance(config)
        assert result.eligible is True, f"reasons={result.reasons}"
        assert result.profile_hash_matches_current is True


class TestFix6ReplayableOverrideDiff:
    def test_cost_config_serialized(self) -> None:
        from src.backtest_engine.event_driven.exchange import CostConfig
        from src.backtest_engine.event_driven import _serialize_cost_config
        custom = CostConfig.realistic_china()
        serialized = _serialize_cost_config(custom)
        assert serialized["class"] == "CostConfig"
        assert "params" in serialized
        assert "stamp_tax" in serialized["params"]
        assert serialized["params"]["stamp_tax"] == 0.0005

    def test_slippage_serialized(self) -> None:
        from src.backtest_engine.event_driven.exchange import FixedSlippage
        from src.backtest_engine.event_driven import _serialize_slippage
        custom = FixedSlippage(0.0005)
        serialized = _serialize_slippage(custom)
        assert serialized["class"] == "FixedSlippage"
        assert "params" in serialized


class TestFix8RequireResearchAccessContext:
    def test_formal_stage_without_context_raises(self) -> None:
        from src.research_orchestrator.research_access_context import (
            MissingResearchAccessContextError,
            require_research_access_context,
            set_research_access_context,
            reset_research_access_context,
        )
        token = set_research_access_context(None)
        try:
            with pytest.raises(MissingResearchAccessContextError, match="formal_validation"):
                require_research_access_context("formal_validation")
        finally:
            reset_research_access_context(token)

    def test_oos_test_stage_without_context_raises(self) -> None:
        from src.research_orchestrator.research_access_context import (
            MissingResearchAccessContextError,
            require_research_access_context,
            set_research_access_context,
            reset_research_access_context,
        )
        token = set_research_access_context(None)
        try:
            with pytest.raises(MissingResearchAccessContextError, match="oos_test"):
                require_research_access_context("oos_test")
        finally:
            reset_research_access_context(token)

    def test_sandbox_stage_without_context_returns_none(self) -> None:
        from src.research_orchestrator.research_access_context import (
            require_research_access_context,
            set_research_access_context,
            reset_research_access_context,
        )
        token = set_research_access_context(None)
        try:
            result = require_research_access_context("sandbox_screening")
            assert result is None
        finally:
            reset_research_access_context(token)

    def test_formal_stage_with_context_returns_context(self) -> None:
        from src.research_orchestrator.research_access_context import (
            ResearchAccessContext,
            require_research_access_context,
            research_access_context,
        )
        ctx = ResearchAccessContext(
            run_id="r", step_id="s", stage="formal_validation",
            design_hash="h",
            allowed_start=pd.Timestamp("2024-01-01"),
            allowed_end=pd.Timestamp("2024-12-31"),
            provider_build_id="p", calendar_policy_id="policy",
        )
        with research_access_context(ctx):
            returned = require_research_access_context("formal_validation")
            assert returned is ctx
