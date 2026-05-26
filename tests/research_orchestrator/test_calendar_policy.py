"""Negative-test suite for the calendar policy loader (PR 1)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.research_orchestrator.calendar_policy import (
    CALENDAR_POLICY_SCHEMA_VERSION,
    CalendarPolicy,
    CalendarPolicyError,
    load_calendar_policy,
)


def _write_policy(root: Path, policy_id: str, payload: dict) -> Path:
    path = root / f"{policy_id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def _valid_policy(**overrides) -> dict:
    base = {
        "policy_id": "test_policy",
        "policy_schema_version": CALENDAR_POLICY_SCHEMA_VERSION,
        "calendar_start_date": "2008-01-02",
        "calendar_end_date": "2026-02-27",
        "data_end_date": "2026-02-27",
        "frozen": True,
        "reason": "test",
        "established_at": "2026-05-26",
        "allowed_modes": ["sandbox", "joinquant_replication"],
        "default_formal_behavior": "require_explicit_policy",
    }
    base.update(overrides)
    return base


class TestCalendarPolicyLoadErrors:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(CalendarPolicyError, match="not found"):
            load_calendar_policy("does_not_exist", root=tmp_path)

    def test_wrong_schema_version_raises(self, tmp_path: Path) -> None:
        _write_policy(
            tmp_path, "test_policy", _valid_policy(policy_schema_version=999)
        )
        with pytest.raises(CalendarPolicyError, match="schema_version"):
            load_calendar_policy("test_policy", root=tmp_path)

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        payload = _valid_policy()
        del payload["reason"]
        _write_policy(tmp_path, "test_policy", payload)
        with pytest.raises(CalendarPolicyError, match="reason"):
            load_calendar_policy("test_policy", root=tmp_path)

    def test_non_frozen_requires_max_lag_days(self, tmp_path: Path) -> None:
        _write_policy(tmp_path, "test_policy", _valid_policy(frozen=False))
        with pytest.raises(CalendarPolicyError, match="max_calendar_lag_days"):
            load_calendar_policy("test_policy", root=tmp_path)


class TestCalendarPolicyBehavior:
    def test_frozen_permits_allowed_mode(self, tmp_path: Path) -> None:
        _write_policy(tmp_path, "test_policy", _valid_policy())
        policy = load_calendar_policy("test_policy", root=tmp_path)
        assert policy.permits_calendar_mismatch("sandbox") is True
        assert policy.permits_calendar_mismatch("joinquant_replication") is True

    def test_frozen_blocks_unauthorized_mode(self, tmp_path: Path) -> None:
        _write_policy(tmp_path, "test_policy", _valid_policy())
        policy = load_calendar_policy("test_policy", root=tmp_path)
        assert policy.permits_calendar_mismatch("live_paper") is False

    def test_assert_run_mode_allowed_raises(self, tmp_path: Path) -> None:
        _write_policy(tmp_path, "test_policy", _valid_policy())
        policy = load_calendar_policy("test_policy", root=tmp_path)
        with pytest.raises(CalendarPolicyError, match="live_paper"):
            policy.assert_run_mode_allowed("live_paper")

    def test_non_frozen_with_lag_loads(self, tmp_path: Path) -> None:
        _write_policy(
            tmp_path,
            "test_policy",
            _valid_policy(frozen=False, max_calendar_lag_days=7),
        )
        policy = load_calendar_policy("test_policy", root=tmp_path)
        assert policy.frozen is False
        assert policy.max_calendar_lag_days == 7
        # Non-frozen policies never permit mismatch via this method;
        # callers check the lag separately.
        assert policy.permits_calendar_mismatch("sandbox") is False


class TestLiveCalendarPolicy:
    """The committed frozen policy under config/calendar_policies/."""

    def test_live_policy_loads(self) -> None:
        policy = load_calendar_policy("frozen_20260227_system_build")
        assert policy.frozen is True
        assert policy.calendar_end_date == "2026-02-27"
        assert "joinquant_replication" in policy.allowed_modes
