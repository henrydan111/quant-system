"""PR 5 negative-test suite — field-status registry.

Covers the gates the plan committed to:
  1. extract_qlib_fields handles $field, Ref($field, n), nested operators
  2. Approved field passes at every stage
  3. Quarantine field blocked at formal_validation / oos_test / publish
  4. Pending_review field blocked at formal but allowed at sandbox
  5. Unknown field blocked at formal (conservative-fail)
  6. Unknown field warned (allowed) at sandbox
  7. Deprecated field blocked at every stage
  8. validate_expression collects ALL violations, not just the first
  9. Malformed YAML raises FieldRegistryError
  10. Unknown stage raises FieldRegistryError
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.data_infra.field_registry import (
    DEFAULT_REGISTRY_PATH,
    DatasetEntry,
    FieldApprovalError,
    FieldRegistryError,
    FieldStatusRegistry,
    extract_qlib_fields,
    load_field_registry,
)


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────


def _minimal_payload(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "statuses": {
            "approved": {
                "allowed": {
                    "sandbox_screening": True,
                    "vectorized_screening": True,
                    "formal_validation": True,
                    "oos_test": True,
                    "registry_publish": True,
                },
            },
            "pending_review": {
                "allowed": {
                    "sandbox_screening": True,
                    "vectorized_screening": True,
                    "formal_validation": False,
                    "oos_test": False,
                    "registry_publish": False,
                },
            },
            "quarantine": {
                "allowed": {
                    "sandbox_screening": False,
                    "vectorized_screening": False,
                    "formal_validation": False,
                    "oos_test": False,
                    "registry_publish": False,
                },
            },
            "deprecated": {
                "allowed": {
                    "sandbox_screening": False,
                    "vectorized_screening": False,
                    "formal_validation": False,
                    "oos_test": False,
                    "registry_publish": False,
                },
            },
        },
        "datasets": {
            "ohlcv": {
                "status": "approved",
                "fields": ["$close", "$open"],
            },
            "event": {
                "status": "pending_review",
                "field_prefixes": ["$event__"],
            },
            "blocked": {
                "status": "quarantine",
                "field_prefixes": ["$moneyflow_"],
            },
            "stale": {
                "status": "deprecated",
                "fields": ["$old_field"],
            },
        },
        "unknown_field_policy": {
            "sandbox_screening": "warn",
            "vectorized_screening": "warn",
            "formal_validation": "fail",
            "oos_test": "fail",
            "registry_publish": "fail",
        },
    }
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────────────────
# Expression parser
# ─────────────────────────────────────────────────────────────────────────


class TestExtractQlibFields:
    def test_bare_field(self) -> None:
        assert extract_qlib_fields("$close") == ("$close",)

    def test_ref_wrapped(self) -> None:
        assert extract_qlib_fields("Ref($close, 1)") == ("$close",)

    def test_nested_operators(self) -> None:
        assert extract_qlib_fields("Mean(Ref($close, 1), 20)") == ("$close",)

    def test_multiple_fields(self) -> None:
        result = extract_qlib_fields("Ref($close, 1) / Ref($total_mv, 1)")
        assert set(result) == {"$close", "$total_mv"}

    def test_dunder_namespacing(self) -> None:
        # Event-like daily endpoint fields use $dataset__column form.
        assert extract_qlib_fields("Std($top_list__amount, 10)") == ("$top_list__amount",)

    def test_empty_expression(self) -> None:
        assert extract_qlib_fields("") == ()
        assert extract_qlib_fields(None) == ()

    def test_no_fields(self) -> None:
        # Pure constant expression.
        assert extract_qlib_fields("1.0 + 2.0") == ()


# ─────────────────────────────────────────────────────────────────────────
# Registry loading
# ─────────────────────────────────────────────────────────────────────────


class TestRegistryLoading:
    def test_minimal_payload_loads(self) -> None:
        reg = FieldStatusRegistry.from_dict(_minimal_payload())
        assert reg.schema_version == 1
        assert "approved" in reg.statuses
        assert "ohlcv" in reg.datasets

    def test_wrong_schema_version_raises(self) -> None:
        payload = _minimal_payload(schema_version=999)
        with pytest.raises(FieldRegistryError, match="schema_version"):
            FieldStatusRegistry.from_dict(payload)

    def test_missing_required_section_raises(self) -> None:
        payload = _minimal_payload()
        del payload["statuses"]
        with pytest.raises(FieldRegistryError, match="statuses"):
            FieldStatusRegistry.from_dict(payload)

    def test_dataset_references_unknown_status_raises(self) -> None:
        payload = _minimal_payload()
        payload["datasets"]["bogus"] = {"status": "not_a_real_status"}
        with pytest.raises(FieldRegistryError, match="not in registered statuses"):
            FieldStatusRegistry.from_dict(payload)

    def test_status_missing_stage_raises(self) -> None:
        payload = _minimal_payload()
        del payload["statuses"]["approved"]["allowed"]["oos_test"]
        with pytest.raises(FieldRegistryError, match="oos_test"):
            FieldStatusRegistry.from_dict(payload)

    def test_unknown_field_policy_missing_stage_raises(self) -> None:
        payload = _minimal_payload()
        del payload["unknown_field_policy"]["formal_validation"]
        with pytest.raises(FieldRegistryError, match="formal_validation"):
            FieldStatusRegistry.from_dict(payload)

    def test_unknown_field_policy_invalid_value_raises(self) -> None:
        payload = _minimal_payload()
        payload["unknown_field_policy"]["formal_validation"] = "explode"
        with pytest.raises(FieldRegistryError, match="warn.*fail"):
            FieldStatusRegistry.from_dict(payload)

    def test_load_from_disk_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FieldRegistryError, match="not found"):
            load_field_registry(tmp_path / "no.yaml")

    def test_load_from_disk_malformed_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("not: valid: yaml: at all", encoding="utf-8")
        with pytest.raises(FieldRegistryError, match="Failed to read"):
            load_field_registry(bad)


# ─────────────────────────────────────────────────────────────────────────
# Resolution at each stage
# ─────────────────────────────────────────────────────────────────────────


class TestResolution:
    @pytest.fixture
    def reg(self) -> FieldStatusRegistry:
        return FieldStatusRegistry.from_dict(_minimal_payload())

    def test_approved_field_at_every_stage(self, reg) -> None:
        for stage in (
            "sandbox_screening", "vectorized_screening",
            "formal_validation", "oos_test", "registry_publish",
        ):
            r = reg.resolve_field("$close", stage)
            assert r.allowed is True
            assert r.dataset_id == "ohlcv"
            assert r.status_id == "approved"

    def test_quarantine_field_blocked_everywhere(self, reg) -> None:
        for stage in (
            "sandbox_screening", "vectorized_screening",
            "formal_validation", "oos_test", "registry_publish",
        ):
            r = reg.resolve_field("$moneyflow_buy_sm_vol", stage)
            assert r.allowed is False
            assert r.dataset_id == "blocked"
            assert r.status_id == "quarantine"

    def test_pending_review_blocked_at_formal(self, reg) -> None:
        r = reg.resolve_field("$event__price", "formal_validation")
        assert r.allowed is False
        assert r.status_id == "pending_review"

    def test_pending_review_allowed_at_sandbox(self, reg) -> None:
        r = reg.resolve_field("$event__price", "sandbox_screening")
        assert r.allowed is True
        assert r.status_id == "pending_review"

    def test_deprecated_blocked_everywhere(self, reg) -> None:
        for stage in (
            "sandbox_screening", "formal_validation", "oos_test", "registry_publish",
        ):
            r = reg.resolve_field("$old_field", stage)
            assert r.allowed is False
            assert r.status_id == "deprecated"

    def test_unknown_field_at_formal_blocked(self, reg) -> None:
        r = reg.resolve_field("$some_new_field", "formal_validation")
        assert r.is_unknown is True
        assert r.allowed is False
        assert "unknown_field_policy[formal_validation]=fail" in r.reason

    def test_unknown_field_at_sandbox_warns(self, reg) -> None:
        r = reg.resolve_field("$some_new_field", "sandbox_screening")
        assert r.is_unknown is True
        assert r.allowed is True
        assert "warn" in r.reason

    def test_unknown_stage_raises(self, reg) -> None:
        with pytest.raises(FieldRegistryError, match="Unknown stage"):
            reg.resolve_field("$close", "live_paper")


# ─────────────────────────────────────────────────────────────────────────
# validate_expression
# ─────────────────────────────────────────────────────────────────────────


class TestValidateExpression:
    @pytest.fixture
    def reg(self) -> FieldStatusRegistry:
        return FieldStatusRegistry.from_dict(_minimal_payload())

    def test_approved_expression_passes(self, reg) -> None:
        resolutions = reg.validate_expression(
            "Mean(Ref($close, 1), 20)", "formal_validation"
        )
        assert len(resolutions) == 1
        assert resolutions[0].allowed is True

    def test_quarantine_field_raises(self, reg) -> None:
        with pytest.raises(FieldApprovalError, match="moneyflow"):
            reg.validate_expression(
                "Ref($moneyflow_buy_sm_vol, 1)", "formal_validation"
            )

    def test_pending_review_field_raises_at_formal(self, reg) -> None:
        with pytest.raises(FieldApprovalError, match="event__"):
            reg.validate_expression("$event__price", "oos_test")

    def test_pending_review_field_allowed_at_sandbox(self, reg) -> None:
        # No raise — sandbox stage allows pending_review.
        result = reg.validate_expression("$event__price", "sandbox_screening")
        assert len(result) == 1
        assert result[0].allowed is True

    def test_unknown_field_raises_at_formal(self, reg) -> None:
        with pytest.raises(FieldApprovalError, match="unknown_field"):
            reg.validate_expression("$brand_new_thing", "formal_validation")

    def test_unknown_field_allowed_at_sandbox(self, reg) -> None:
        # No raise — sandbox stage warns on unknown.
        result = reg.validate_expression("$brand_new_thing", "sandbox_screening")
        assert result[0].is_unknown is True

    def test_raise_on_unknown_override_forces_fail(self, reg) -> None:
        with pytest.raises(FieldApprovalError, match="unknown_field"):
            reg.validate_expression(
                "$brand_new_thing", "sandbox_screening", raise_on_unknown=True
            )

    def test_multiple_violations_all_reported(self, reg) -> None:
        with pytest.raises(FieldApprovalError) as exc_info:
            reg.validate_expression(
                "Ref($moneyflow_buy_sm_vol, 1) / Ref($event__price, 1)",
                "formal_validation",
            )
        msg = str(exc_info.value)
        assert "$moneyflow_buy_sm_vol" in msg
        assert "$event__price" in msg


# ─────────────────────────────────────────────────────────────────────────
# Live registry smoke
# ─────────────────────────────────────────────────────────────────────────


class TestLiveRegistry:
    """Sanity check against the committed config/field_registry/field_status.yaml."""

    @pytest.fixture
    def reg(self) -> FieldStatusRegistry:
        return load_field_registry()

    def test_close_is_approved(self, reg) -> None:
        r = reg.resolve_field("$close", "formal_validation")
        assert r.allowed is True
        assert r.dataset_id == "market_daily"

    def test_moneyflow_is_quarantined_for_formal(self, reg) -> None:
        r = reg.resolve_field("$moneyflow_buy_sm_vol", "formal_validation")
        assert r.allowed is False
        assert r.status_id == "quarantine"

    def test_top_list_is_pending_for_formal(self, reg) -> None:
        r = reg.resolve_field("$top_list__close", "formal_validation")
        assert r.allowed is False
        assert r.status_id == "pending_review"

    def test_top_list_allowed_for_sandbox(self, reg) -> None:
        r = reg.resolve_field("$top_list__close", "sandbox_screening")
        assert r.allowed is True

    def test_pit_field_is_approved(self, reg) -> None:
        # $pit_or_yoy and friends should be approved (explicit field).
        r = reg.resolve_field("$pit_or_yoy", "formal_validation")
        assert r.allowed is True

    def test_pit_prefix_match_for_unknown_pit_field(self, reg) -> None:
        # An unlisted PIT field still resolves via the $pit_ prefix.
        r = reg.resolve_field("$pit_some_future_field", "formal_validation")
        assert r.allowed is True
        assert r.dataset_id == "pit_fundamentals"

    def test_completely_unknown_field_blocks_formal(self, reg) -> None:
        r = reg.resolve_field("$completely_unknown_xyz", "formal_validation")
        assert r.is_unknown is True
        assert r.allowed is False
