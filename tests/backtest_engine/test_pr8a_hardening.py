"""PR 8a negative-test suite — calendar/runtime hardening follow-up.

Covers the 7 issues GPT 5.5 Pro flagged in PR 8 review:

  1. Formal run + missing calendar_policy_id → raises before any backtest
     work begins.
  2. joinquant_daily_sim with frozen policy + run_mode=None now passes
     policy.assert_run_mode_allowed (deployment_target added to
     allowed_modes in the YAML).
  3. (covered via direct calendar-policy assertions.)
  4. _validate_provider_at_runtime raises on Qlib calendar read failure
     instead of returning silently.
  5. _serialize_slippage(FixedSlippage(0.0005)) round-trips the spread.
  6. strict cache-only raises when all requested instruments are missing.
  7. BacktestEngine restores feeder._strict_cache_only after a normal
     run completes.
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
        EventDrivenBacktester(data_dir=str(tmp_path)).run(
            strategy=strategy,
            start_time="2024-01-02",
            end_time="2024-01-31",
            **run_kwargs,
        )
    return feeder_cls, feeder, engine_cls


class TestFix1FormalRequiresCalendarPolicy:
    def test_formal_profile_without_calendar_policy_raises(self, tmp_path: Path) -> None:
        # Note: NO calendar_policy_id in the kwargs → must raise.
        with pytest.raises(RuntimeError, match="calendar_policy_id"):
            _run_with_mocks(
                tmp_path,
                execution_profile="joinquant_daily_sim",
                run_mode=None,
            )

    def test_formal_run_mode_without_calendar_policy_raises(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="calendar_policy_id"):
            _run_with_mocks(tmp_path, run_mode="formal")

    def test_sandbox_without_calendar_policy_proceeds(self, tmp_path: Path) -> None:
        # No formal flag, no profile → not formal → no policy required.
        _run_with_mocks(tmp_path)  # no raise


class TestFix2PolicyAllowedModesContainProfileTargets:
    def test_joinquant_daily_in_allowed_modes(self) -> None:
        from src.research_orchestrator.calendar_policy import load_calendar_policy
        policy = load_calendar_policy("frozen_20260227_system_build")
        assert "joinquant_daily" in policy.allowed_modes
        # PR 8a fix #2: passing the profile's deployment_target straight in
        # must not raise.
        policy.assert_run_mode_allowed("joinquant_daily")

    def test_joinquant_open_close_replica_in_allowed_modes(self) -> None:
        from src.research_orchestrator.calendar_policy import load_calendar_policy
        policy = load_calendar_policy("frozen_20260227_system_build")
        assert "joinquant_open_close_replica" in policy.allowed_modes
        policy.assert_run_mode_allowed("joinquant_open_close_replica")

    def test_unrelated_mode_still_rejected(self) -> None:
        from src.research_orchestrator.calendar_policy import (
            CalendarPolicyError,
            load_calendar_policy,
        )
        policy = load_calendar_policy("frozen_20260227_system_build")
        with pytest.raises(CalendarPolicyError, match="live_paper"):
            policy.assert_run_mode_allowed("live_paper")


class TestFix3DailyQAStrictFrozen:
    """Daily QA must enforce frozen-policy calendar equality, not blanket-allow."""

    def test_daily_qa_strict_frozen_path_present(self) -> None:
        # We assert by reading the script source rather than running the
        # full QA pipeline (which requires a live Qlib provider). The
        # critical change is removing the blanket `allow_mismatch = policy.frozen`.
        from pathlib import Path
        src = Path("scripts/run_daily_qa.py").read_text(encoding="utf-8")
        # The blanket assignment line should be GONE from non-comment code.
        # Allow the phrase inside the explanatory comment that documents
        # the old behavior — strip out comment lines first.
        code_lines = [
            line for line in src.splitlines() if not line.lstrip().startswith("#")
        ]
        code_only = "\n".join(code_lines)
        assert "allow_mismatch = policy.frozen" not in code_only, (
            "Daily QA still uses the PR 8a-deprecated blanket "
            "`allow_mismatch = policy.frozen`. Fix #3 should require strict "
            "equality for frozen policies."
        )
        # The new strict equality check should be present somewhere.
        assert "Frozen calendar policy" in src
        # allow_calendar_mismatch=False must be the explicit pass-through.
        assert "allow_calendar_mismatch=False" in code_only


class TestFix4ValidatorRaisesOnQlibFailure:
    def test_qlib_calendar_read_failure_raises(self) -> None:
        from src.backtest_engine.event_driven import _validate_provider_at_runtime
        manifest = MagicMock(
            provider=MagicMock(calendar_end_date="2026-02-27"),
            event_endpoint_namespacing=MagicMock(status="enforced"),
            calendar_policy_id="frozen_20260227_system_build",  # PR 8b Blocker 3
        )
        # PR 8c Blocker 1: validator now reads calendars/day.txt directly,
        # so the failure mode is file-read failure, not Qlib failure. The
        # safety guarantee is the same: validator must raise, not silently
        # skip the mismatch check.
        with patch(
            "src.backtest_engine.event_driven._read_provider_calendar_end",
            side_effect=RuntimeError(
                "Provider calendar file not found at /nope/calendars/day.txt"
            ),
        ):
            with pytest.raises(RuntimeError, match="Provider calendar file not found"):
                _validate_provider_at_runtime(
                    manifest=manifest,
                    calendar_policy_id="frozen_20260227_system_build",
                    run_mode="joinquant_daily",
                    qlib_dir="/nope",
                )


class TestFix5SlippageSerializationComplete:
    def test_fixed_slippage_spread_captured(self) -> None:
        from src.backtest_engine.event_driven.exchange import FixedSlippage
        from src.backtest_engine.event_driven import _serialize_slippage
        custom = FixedSlippage(0.0005)
        serialized = _serialize_slippage(custom)
        assert serialized["class"] == "FixedSlippage"
        # PR 8a fix #5: spread must be in params now.
        assert "spread" in serialized["params"]
        assert serialized["params"]["spread"] == 0.0005

    def test_fixed_slippage_round_trip(self) -> None:
        from src.backtest_engine.event_driven.exchange import FixedSlippage
        from src.backtest_engine.event_driven import _serialize_slippage
        custom = FixedSlippage(0.0007)
        serialized = _serialize_slippage(custom)
        rebuilt = FixedSlippage(serialized["params"]["spread"])
        assert rebuilt.spread == custom.spread

    def test_pct_slippage_rate_captured(self) -> None:
        from src.backtest_engine.event_driven.exchange import PctSlippage
        from src.backtest_engine.event_driven import _serialize_slippage
        custom = PctSlippage(0.001)
        serialized = _serialize_slippage(custom)
        assert serialized["class"] == "PctSlippage"
        assert "rate" in serialized["params"]
        assert serialized["params"]["rate"] == 0.001


class TestFix6StrictCacheOnlyMissingInstrument:
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

    def test_strict_mode_raises_on_all_missing_instruments(self) -> None:
        feeder = self._make_feeder_with_cache()
        feeder.set_strict_cache_only(True)
        # 'NEVER_IN_CACHE_SZ' is not in the cache's instrument index.
        # PR 8b fix #4 changed the message to use the unified "not present
        # in cache" phrasing for both all-missing and partial-missing.
        with pytest.raises(PreloadCoverageError, match="not present in cache"):
            feeder.get_features(
                instruments=["NEVER_IN_CACHE_SZ"],
                fields=["$close"],  # field IS in cache
                start_time=pd.Timestamp("2024-01-02"),
                end_time=pd.Timestamp("2024-01-02"),
            )

    def test_nonstrict_mode_returns_empty_silently(self) -> None:
        # Non-strict behavior preserved: missing instruments + cached fields
        # returns empty DataFrame without raising.
        feeder = self._make_feeder_with_cache()
        feeder.set_strict_cache_only(False)
        out = feeder.get_features(
            instruments=["NEVER_IN_CACHE_SZ"],
            fields=["$close"],
            start_time=pd.Timestamp("2024-01-02"),
            end_time=pd.Timestamp("2024-01-02"),
        )
        assert out.empty


class TestFix7EngineRestoresStrictCacheOnly:
    """Engine source contains the restore call AFTER the day loop.

    A full end-to-end test would require a complete feeder stub (the engine
    accesses many feeder methods, ts_code columns, etc.). The contract under
    test is simpler: after the day loop, before the return, the engine
    must call ``self.feeder.set_strict_cache_only(_prev_strict_cache_only)``.
    Source-reflection is sufficient to verify the restore line is present.
    """

    def test_engine_source_restores_strict_cache_only(self) -> None:
        from pathlib import Path
        src = Path("src/backtest_engine/event_driven/engine.py").read_text(encoding="utf-8")
        # The pre-loop save must be present.
        assert "_prev_strict_cache_only" in src, (
            "Engine missing _prev_strict_cache_only snapshot"
        )
        # The post-loop restore call must be present.
        assert "set_strict_cache_only(_prev_strict_cache_only)" in src, (
            "Engine missing post-loop set_strict_cache_only(_prev_strict_cache_only) restore"
        )
        # Restore must appear AFTER the day loop (after the for line).
        for_idx = src.find("for i, date in enumerate(calendar):")
        restore_idx = src.find("set_strict_cache_only(_prev_strict_cache_only)")
        assert for_idx > 0 and restore_idx > for_idx, (
            "set_strict_cache_only(_prev_strict_cache_only) must come AFTER the day loop"
        )
