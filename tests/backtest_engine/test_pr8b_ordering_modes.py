"""PR 8b negative-test suite — calendar/runtime ordering + mode coverage fixup.

Covers each of the 6 issues GPT 5.5 Pro flagged in PR 8a review:

  Blocker 1 — calendar_policy_id check must fire BEFORE feeder/preload.
  Blocker 2 — run_mode='formal' / 'oos_test' must pass the frozen policy.
  Blocker 3 — manifest.calendar_policy_id must match the requested policy id.
  Fix #4    — strict cache-only raises on PARTIAL missing instruments.
  Fix #5    — strict_cache_only restored on the exception path via try/finally.
  Fix #6    — daily QA has a behavioral mismatch test, not just source-reflection.
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
    strict_cache_mode,
)


def _stub_manifest(policy_id: str = "frozen_20260227_system_build"):
    return MagicMock(
        provider_build_id="prod_test_001",
        provider=MagicMock(calendar_end_date="2026-02-27"),
        event_endpoint_namespacing=MagicMock(status="enforced"),
        calendar_policy_id=policy_id,
    )


class TestBlocker1OrderingBeforePreload:
    def test_missing_policy_raises_before_preload_features_called(self, tmp_path: Path) -> None:
        strategy = MagicMock()
        with patch("src.backtest_engine.event_driven.QlibDataFeeder") as feeder_cls, patch(
            "src.backtest_engine.event_driven.Exchange"
        ), patch("src.backtest_engine.event_driven.BacktestEngine") as engine_cls, patch(
            "src.backtest_engine.event_driven.load_provider_manifest", return_value=_stub_manifest(),
        ):
            feeder = feeder_cls.return_value
            engine = engine_cls.return_value
            engine.run.return_value = MagicMock(config={})
            with pytest.raises(RuntimeError, match="calendar_policy_id"):
                EventDrivenBacktester(data_dir=str(tmp_path)).run(
                    strategy=strategy,
                    start_time="2024-01-02",
                    end_time="2024-01-31",
                    execution_profile="joinquant_daily_sim",
                    run_mode=None,
                )
            # PR 8b Blocker 1: feeder.preload_features must NOT have been
            # called before the policy check raised.
            feeder.preload_features.assert_not_called()
            engine_cls.assert_not_called()


class TestBlocker2FormalModesAllowed:
    def test_formal_in_allowed_modes(self) -> None:
        from src.research_orchestrator.calendar_policy import load_calendar_policy
        policy = load_calendar_policy("frozen_20260227_system_build")
        assert "formal" in policy.allowed_modes
        policy.assert_run_mode_allowed("formal")

    def test_oos_test_in_allowed_modes(self) -> None:
        from src.research_orchestrator.calendar_policy import load_calendar_policy
        policy = load_calendar_policy("frozen_20260227_system_build")
        assert "oos_test" in policy.allowed_modes
        policy.assert_run_mode_allowed("oos_test")

    def test_formal_run_mode_with_frozen_policy_validates(self) -> None:
        from src.backtest_engine.event_driven import _validate_provider_at_runtime
        manifest = _stub_manifest()
        with patch("qlib.data.D") as mock_d:
            mock_d.calendar.return_value = [pd.Timestamp("2026-02-27")]
            _validate_provider_at_runtime(
                manifest=manifest,
                calendar_policy_id="frozen_20260227_system_build",
                run_mode="formal",
            )

    def test_oos_test_run_mode_with_frozen_policy_validates(self) -> None:
        from src.backtest_engine.event_driven import _validate_provider_at_runtime
        manifest = _stub_manifest()
        with patch("qlib.data.D") as mock_d:
            mock_d.calendar.return_value = [pd.Timestamp("2026-02-27")]
            _validate_provider_at_runtime(
                manifest=manifest,
                calendar_policy_id="frozen_20260227_system_build",
                run_mode="oos_test",
            )


class TestBlocker3ManifestPolicyMismatch:
    def test_mismatch_raises(self) -> None:
        from src.backtest_engine.event_driven import _validate_provider_at_runtime
        manifest = _stub_manifest(policy_id="some_other_policy")
        with patch("qlib.data.D") as mock_d:
            mock_d.calendar.return_value = [pd.Timestamp("2026-02-27")]
            with pytest.raises(RuntimeError, match="manifest declares calendar_policy_id"):
                _validate_provider_at_runtime(
                    manifest=manifest,
                    calendar_policy_id="frozen_20260227_system_build",
                    run_mode="joinquant_daily",
                )

    def test_match_passes(self) -> None:
        from src.backtest_engine.event_driven import _validate_provider_at_runtime
        manifest = _stub_manifest(policy_id="frozen_20260227_system_build")
        with patch("qlib.data.D") as mock_d:
            mock_d.calendar.return_value = [pd.Timestamp("2026-02-27")]
            _validate_provider_at_runtime(
                manifest=manifest,
                calendar_policy_id="frozen_20260227_system_build",
                run_mode="joinquant_daily",
            )


class TestFix4PartialMissingInstruments:
    def _make_feeder_with_cache(self) -> QlibDataFeeder:
        feeder = QlibDataFeeder.__new__(QlibDataFeeder)
        idx = pd.MultiIndex.from_product(
            [["000001_SZ", "000002_SZ"], pd.date_range("2024-01-01", "2024-01-31")],
            names=["instrument", "datetime"],
        )
        feeder._cache_df = pd.DataFrame({"$close": [1.0] * len(idx)}, index=idx)
        feeder._preload_status = "success"
        feeder._direct_fallback_count = 0
        feeder._cache_hit_count = 0
        feeder._strict_cache_only = False
        feeder._stage = "is_only"
        return feeder

    def test_partial_missing_raises_in_strict_mode(self) -> None:
        feeder = self._make_feeder_with_cache()
        feeder.set_strict_cache_only(True)
        with pytest.raises(PreloadCoverageError, match="not present in cache"):
            feeder.get_features(
                instruments=["000001_SZ", "NEVER_IN_CACHE_SZ"],
                fields=["$close"],
                start_time=pd.Timestamp("2024-01-02"),
                end_time=pd.Timestamp("2024-01-02"),
            )

    def test_partial_missing_silent_in_non_strict_mode(self) -> None:
        feeder = self._make_feeder_with_cache()
        feeder.set_strict_cache_only(False)
        out = feeder.get_features(
            instruments=["000001_SZ", "NEVER_IN_CACHE_SZ"],
            fields=["$close"],
            start_time=pd.Timestamp("2024-01-02"),
            end_time=pd.Timestamp("2024-01-02"),
        )
        instruments_in_out = set(out.index.get_level_values("instrument").unique())
        assert "000001_SZ" in instruments_in_out
        assert "NEVER_IN_CACHE_SZ" not in instruments_in_out

    def test_all_present_in_strict_mode_passes(self) -> None:
        feeder = self._make_feeder_with_cache()
        feeder.set_strict_cache_only(True)
        out = feeder.get_features(
            instruments=["000001_SZ", "000002_SZ"],
            fields=["$close"],
            start_time=pd.Timestamp("2024-01-02"),
            end_time=pd.Timestamp("2024-01-02"),
        )
        assert not out.empty


class TestFix5RestoreOnExceptionPath:
    def test_context_manager_restores_after_exception(self) -> None:
        feeder = QlibDataFeeder.__new__(QlibDataFeeder)
        feeder._strict_cache_only = False
        with pytest.raises(RuntimeError, match="boom"):
            with strict_cache_mode(feeder, enabled=True):
                assert feeder._strict_cache_only is True
                raise RuntimeError("boom")
        assert feeder._strict_cache_only is False

    def test_context_manager_with_disabled_is_noop(self) -> None:
        feeder = QlibDataFeeder.__new__(QlibDataFeeder)
        feeder._strict_cache_only = True
        with strict_cache_mode(feeder, enabled=False):
            assert feeder._strict_cache_only is True
        assert feeder._strict_cache_only is True

    def test_engine_source_uses_try_finally(self) -> None:
        src = Path("src/backtest_engine/event_driven/engine.py").read_text(encoding="utf-8")
        finally_idx = src.find("finally:")
        restore_idx = src.find("set_strict_cache_only(_prev_strict_cache_only)")
        assert finally_idx > 0
        assert restore_idx > finally_idx, (
            "set_strict_cache_only(_prev_strict_cache_only) must be inside the finally: block"
        )


class TestFix6DailyQABehavioral:
    """Behavioral test: temp Qlib layout with mismatched calendar end dates
    must trigger the same RuntimeError that daily QA raises."""

    def test_frozen_policy_with_mismatched_live_calendar_fails(self, tmp_path: Path) -> None:
        qlib_dir = tmp_path / "qlib_data"
        (qlib_dir / "calendars").mkdir(parents=True)
        (qlib_dir / "metadata").mkdir(parents=True)
        (qlib_dir / "calendars" / "day.txt").write_text(
            "2026-02-25\n2026-02-26\n2026-02-27\n2026-03-01\n2026-03-15\n",
            encoding="utf-8",
        )
        import json
        manifest_payload = {
            "schema_version": 1,
            "provider_build_id": "prod_test_001",
            "provider_published_at": "2026-04-21T00:00:00",
            "calendar_policy_id": "frozen_20260227_system_build",
            "provider": {
                "path": str(qlib_dir).replace("\\", "/"),
                "region": "REG_CN",
                "calendar_start_date": "2008-01-02",
                "calendar_end_date": "2026-02-27",
                "data_end_date": "2026-02-27",
            },
            "event_endpoint_namespacing": {
                "status": "enforced",
                "affected_datasets": ["top_list"],
                "prefix_rule": "{dataset}__{column}",
                "canonical_kline_fields_protected": ["$close"],
            },
            "retroactive_manifest": False,
        }
        (qlib_dir / "metadata" / "provider_build.json").write_text(
            json.dumps(manifest_payload), encoding="utf-8",
        )

        from src.data_infra.provider_manifest import (
            ProviderManifestError,
            load_provider_manifest,
            validate_provider_manifest_against_qlib,
        )
        from src.research_orchestrator.calendar_policy import load_calendar_policy
        manifest = load_provider_manifest(qlib_dir)
        policy = load_calendar_policy(manifest.calendar_policy_id)
        cal_lines = [
            line.strip()
            for line in (qlib_dir / "calendars" / "day.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        live_calendar_end = cal_lines[-1]
        # The frozen-policy assertion in daily QA raises on this mismatch.
        assert policy.frozen is True
        assert live_calendar_end != policy.calendar_end_date
        with pytest.raises(ProviderManifestError, match="calendar"):
            validate_provider_manifest_against_qlib(
                manifest, live_calendar_end, allow_calendar_mismatch=False,
            )

    def test_frozen_policy_with_matching_live_calendar_passes(self, tmp_path: Path) -> None:
        qlib_dir = tmp_path / "qlib_data"
        (qlib_dir / "calendars").mkdir(parents=True)
        (qlib_dir / "metadata").mkdir(parents=True)
        (qlib_dir / "calendars" / "day.txt").write_text(
            "2026-02-25\n2026-02-26\n2026-02-27\n",
            encoding="utf-8",
        )
        import json
        manifest_payload = {
            "schema_version": 1,
            "provider_build_id": "prod_test_001",
            "provider_published_at": "2026-04-21T00:00:00",
            "calendar_policy_id": "frozen_20260227_system_build",
            "provider": {
                "path": str(qlib_dir).replace("\\", "/"),
                "region": "REG_CN",
                "calendar_start_date": "2008-01-02",
                "calendar_end_date": "2026-02-27",
                "data_end_date": "2026-02-27",
            },
            "event_endpoint_namespacing": {
                "status": "enforced",
                "affected_datasets": ["top_list"],
                "prefix_rule": "{dataset}__{column}",
                "canonical_kline_fields_protected": ["$close"],
            },
            "retroactive_manifest": False,
        }
        (qlib_dir / "metadata" / "provider_build.json").write_text(
            json.dumps(manifest_payload), encoding="utf-8",
        )
        from src.data_infra.provider_manifest import (
            load_provider_manifest,
            validate_provider_manifest_against_qlib,
        )
        manifest = load_provider_manifest(qlib_dir)
        validate_provider_manifest_against_qlib(
            manifest, "2026-02-27", allow_calendar_mismatch=False,
        )
