"""D3 spent-OOS boundary resolver tests (UNFREEZE_PLAN.md item 8, GPT Round-2 M6).

The three contract-required CI tests, exercised through the REAL policy files
under config/calendar_policies/ (the "manifest-declared new policy" path —
Round-3 note: not only hand-constructed policy objects) plus temp-file
variants for the missing/invalid cases.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.research_orchestrator.calendar_policy import (
    CalendarPolicy,
    CalendarPolicyError,
    load_calendar_policy,
    resolve_spent_oos_boundary,
)

REPO_POLICY_DIR = Path(__file__).resolve().parents[2] / "config" / "calendar_policies"


def _write_policy(tmp_path: Path, policy_id: str, body: str) -> Path:
    path = tmp_path / f"{policy_id}.yaml"
    path.write_text(body, encoding="utf-8")
    return tmp_path


BASE_FIELDS = """
policy_id: {pid}
policy_schema_version: 1
calendar_start_date: 2008-01-02
calendar_end_date: {cal_end}
data_end_date: {cal_end}
frozen: {frozen}
reason: test
established_at: 2026-07-02
allowed_modes: [sandbox, formal]
default_formal_behavior: require_explicit_policy
"""


class TestRequiredCiCases:
    def test_legacy_frozen_policy_without_fields_clamps_to_its_calendar_end(self):
        # M6 required test 1 — the REAL legacy file from the repo.
        policy = load_calendar_policy("frozen_20260227_system_build", root=REPO_POLICY_DIR)
        assert policy.spent_oos_end is None
        boundary = resolve_spent_oos_boundary(policy, provider_calendar_end="2026-02-27")
        assert boundary.spent_oos_end == "2026-02-27"
        assert boundary.fresh_holdout_start is None  # no fresh window: post-spent fails closed
        assert boundary.source == "frozen_calendar_end_fallback"

    def test_legacy_fallback_still_clamps_under_longer_provider(self):
        # Invalid pairing (thawed provider + legacy policy) must CLAMP, not open.
        policy = load_calendar_policy("frozen_20260227_system_build", root=REPO_POLICY_DIR)
        boundary = resolve_spent_oos_boundary(policy, provider_calendar_end="2026-06-30")
        assert boundary.spent_oos_end == "2026-02-27"
        assert boundary.fresh_holdout_start is None

    def test_thaw_policy_clamps_default_reads_to_spent_even_with_longer_calendar(self):
        # M6 required test 2 — the REAL thaw_step1 file from the repo.
        policy = load_calendar_policy("frozen_20260630_thaw_step1", root=REPO_POLICY_DIR)
        boundary = resolve_spent_oos_boundary(policy, provider_calendar_end="2026-06-30")
        assert boundary.spent_oos_end == "2026-02-27"
        assert boundary.fresh_holdout_start == "2026-02-28"
        assert boundary.source == "policy_fields"

    def test_thaw_policy_with_only_one_boundary_field_fails_closed_via_file_path(self, tmp_path):
        # M6 required test 3 — exercised through the manifest-declared-policy
        # path (load_calendar_policy on a real file), not a hand-built object.
        body = BASE_FIELDS.format(pid="thaw_bad", cal_end="2026-06-30", frozen="true")
        body += "spent_oos_end: 2026-02-27\n"  # fresh_holdout_start missing
        root = _write_policy(tmp_path, "thaw_bad", body)
        with pytest.raises(CalendarPolicyError, match="both or neither"):
            load_calendar_policy("thaw_bad", root=root)

    def test_nonfrozen_policy_without_boundary_fields_fails_closed(self, tmp_path):
        body = BASE_FIELDS.format(pid="rolling_bad", cal_end="2026-06-30", frozen="false")
        body += "max_calendar_lag_days: 5\n"
        root = _write_policy(tmp_path, "rolling_bad", body)
        policy = load_calendar_policy("rolling_bad", root=root)
        with pytest.raises(CalendarPolicyError, match="fails closed"):
            resolve_spent_oos_boundary(policy, provider_calendar_end="2026-06-30")


class TestBoundaryValidation:
    def _policy(self, **overrides) -> CalendarPolicy:
        payload = {
            "policy_id": "t", "policy_schema_version": 1,
            "calendar_start_date": "2008-01-02", "calendar_end_date": "2026-06-30",
            "data_end_date": "2026-06-30", "frozen": True, "reason": "t",
            "established_at": "2026-07-02", "allowed_modes": ["sandbox"],
            "default_formal_behavior": "require_explicit_policy",
        }
        payload.update(overrides)
        return CalendarPolicy.from_dict(payload)

    def test_fresh_not_after_spent_raises(self):
        policy = self._policy(spent_oos_end="2026-02-27", fresh_holdout_start="2026-02-27")
        with pytest.raises(CalendarPolicyError, match="strictly after"):
            resolve_spent_oos_boundary(policy, provider_calendar_end="2026-06-30")

    def test_spent_beyond_policy_calendar_end_raises(self):
        policy = self._policy(spent_oos_end="2026-07-31", fresh_holdout_start="2026-08-01")
        with pytest.raises(CalendarPolicyError, match="exceeds the policy calendar_end_date"):
            resolve_spent_oos_boundary(policy, provider_calendar_end="2026-08-31")

    def test_spent_beyond_live_provider_calendar_raises(self):
        policy = self._policy(spent_oos_end="2026-02-27", fresh_holdout_start="2026-02-28")
        with pytest.raises(CalendarPolicyError, match="live provider calendar end"):
            resolve_spent_oos_boundary(policy, provider_calendar_end="2026-01-30")

    def test_repo_thaw_policy_parses_with_boundary_fields(self):
        policy = load_calendar_policy("frozen_20260630_thaw_step1", root=REPO_POLICY_DIR)
        assert policy.frozen is True
        assert policy.calendar_end_date == "2026-06-30"
        assert policy.spent_oos_end == "2026-02-27"
        assert policy.fresh_holdout_start == "2026-02-28"
