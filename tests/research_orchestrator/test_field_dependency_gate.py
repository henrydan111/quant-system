"""PR 5 negative-test suite — release_gate.evaluate_field_dependencies."""

from __future__ import annotations

import pytest

from src.data_infra.field_registry import (
    FieldApprovalError,
    FieldStatusRegistry,
)
from src.research_orchestrator.release_gate import (
    FieldDependencyGateResult,
    assert_field_dependencies_eligible,
    evaluate_field_dependencies,
)


def _minimal_registry() -> FieldStatusRegistry:
    return FieldStatusRegistry.from_dict(
        {
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
                "quarantine": {
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
                "ohlcv": {"status": "approved", "fields": ["$close"]},
                "blocked": {"status": "quarantine", "field_prefixes": ["$mf_"]},
            },
            "unknown_field_policy": {
                "sandbox_screening": "warn",
                "vectorized_screening": "warn",
                "formal_validation": "fail",
                "oos_test": "fail",
                "registry_publish": "fail",
            },
        }
    )


class TestEvaluateFieldDependencies:
    def test_approved_only_passes(self) -> None:
        reg = _minimal_registry()
        result = evaluate_field_dependencies(
            fields=["$close"], stage="formal_validation", registry=reg,
        )
        assert result.eligible is True
        assert result.disallowed_fields == ()
        assert result.unknown_fields == ()
        assert "$close" in result.fields_checked

    def test_quarantine_field_blocks_gate(self) -> None:
        reg = _minimal_registry()
        result = evaluate_field_dependencies(
            fields=["$mf_buy"], stage="formal_validation", registry=reg,
        )
        assert result.eligible is False
        assert "$mf_buy" in result.disallowed_fields
        assert any("quarantine" in r for r in result.reasons)

    def test_unknown_field_blocks_formal(self) -> None:
        reg = _minimal_registry()
        result = evaluate_field_dependencies(
            fields=["$xyz_unknown"], stage="formal_validation", registry=reg,
        )
        assert result.eligible is False
        assert "$xyz_unknown" in result.disallowed_fields
        assert "$xyz_unknown" in result.unknown_fields

    def test_unknown_field_warns_at_sandbox(self) -> None:
        reg = _minimal_registry()
        result = evaluate_field_dependencies(
            fields=["$xyz_unknown"], stage="sandbox_screening", registry=reg,
        )
        assert result.eligible is True
        assert "$xyz_unknown" in result.unknown_fields
        assert result.disallowed_fields == ()

    def test_expressions_input(self) -> None:
        reg = _minimal_registry()
        result = evaluate_field_dependencies(
            expressions=["Mean(Ref($close, 1), 20)", "Ref($mf_buy, 1)"],
            stage="formal_validation",
            registry=reg,
        )
        assert result.eligible is False
        assert "$mf_buy" in result.disallowed_fields
        # Approved $close still resolved and listed
        assert "$close" in result.fields_checked

    def test_fields_and_expressions_combined(self) -> None:
        reg = _minimal_registry()
        result = evaluate_field_dependencies(
            fields=["$close"],
            expressions=["Ref($mf_extra, 1)"],
            stage="formal_validation",
            registry=reg,
        )
        assert set(result.fields_checked) == {"$close", "$mf_extra"}
        assert "$mf_extra" in result.disallowed_fields


class TestAssertFieldDependenciesEligible:
    def test_strict_passes_silently(self) -> None:
        reg = _minimal_registry()
        result = assert_field_dependencies_eligible(
            fields=["$close"], stage="formal_validation", registry=reg,
        )
        assert result.eligible is True

    def test_strict_raises_on_block(self) -> None:
        reg = _minimal_registry()
        with pytest.raises(FieldApprovalError, match="\\$mf_buy"):
            assert_field_dependencies_eligible(
                fields=["$mf_buy"], stage="formal_validation", registry=reg,
                artifact_label="test_factor",
            )

    def test_strict_raises_on_unknown_at_formal(self) -> None:
        reg = _minimal_registry()
        with pytest.raises(FieldApprovalError, match="\\$xyz_unknown"):
            assert_field_dependencies_eligible(
                fields=["$xyz_unknown"], stage="formal_validation", registry=reg,
            )


class TestLiveGateWithCommittedRegistry:
    """Integration smoke against the committed config/field_registry/field_status.yaml."""

    def test_approved_close_passes_formal(self) -> None:
        # No registry kwarg — loads the committed YAML
        result = evaluate_field_dependencies(
            fields=["$close"], stage="formal_validation",
        )
        assert result.eligible is True

    def test_live_moneyflow_blocks_formal(self) -> None:
        result = evaluate_field_dependencies(
            fields=["$moneyflow_buy_sm_vol"], stage="formal_validation",
        )
        assert result.eligible is False
        assert "$moneyflow_buy_sm_vol" in result.disallowed_fields

    def test_live_top_list_blocks_formal(self) -> None:
        result = evaluate_field_dependencies(
            fields=["$top_list__amount"], stage="formal_validation",
        )
        assert result.eligible is False
        assert "$top_list__amount" in result.disallowed_fields

    def test_live_top_list_allowed_at_sandbox(self) -> None:
        result = evaluate_field_dependencies(
            fields=["$top_list__amount"], stage="sandbox_screening",
        )
        assert result.eligible is True
