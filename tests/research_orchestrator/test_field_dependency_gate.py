"""PR 5 negative-test suite — release_gate.evaluate_field_dependencies."""

from __future__ import annotations

import pytest

from src.data_infra.field_registry import (
    FieldApprovalError,
    FieldStatusRegistry,
    load_field_registry,
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
    """Integration smoke against the committed config/field_registry/field_status.yaml.

    Expectations are DERIVED from the live registry at runtime — never pin a
    specific dataset's governance status here. The original pinned tests
    (moneyflow quarantined, top_list pending_review) broke when those datasets
    were later legitimately approved (moneyflow/top_list 2026-06-05, hk_hold
    2026-06-04); a legal approval must never fail the suite.
    """

    def test_approved_close_passes_formal(self) -> None:
        # No registry kwarg — loads the committed YAML. $close is an
        # ENGINE_REQUIRED_FIELDS member; it staying approved IS an invariant.
        result = evaluate_field_dependencies(
            fields=["$close"], stage="formal_validation",
        )
        assert result.eligible is True

    @staticmethod
    def _live_quarantined_fields() -> list[str]:
        registry = load_field_registry()
        fields: list[str] = []
        for dataset_id in registry.list_datasets_by_status("quarantine"):
            entry = registry.datasets[dataset_id]
            fields.extend(entry.fields)
            fields.extend(f"{prefix}smoke_probe" for prefix in entry.field_prefixes)
        return sorted(fields)

    def test_live_quarantined_field_blocks_formal(self) -> None:
        quarantined = self._live_quarantined_fields()
        if not quarantined:
            pytest.skip(
                "live field_status.yaml currently has no quarantined datasets "
                "— nothing to smoke-test; the synthetic-registry tests above "
                "still cover the refusal mechanism"
            )
        field = quarantined[0]
        result = evaluate_field_dependencies(
            fields=[field], stage="formal_validation",
        )
        assert result.eligible is False
        assert field in result.disallowed_fields

    def test_live_quarantined_field_blocks_sandbox_too(self) -> None:
        # Committed policy: quarantine disallows EVERY stage, sandbox included.
        quarantined = self._live_quarantined_fields()
        if not quarantined:
            pytest.skip(
                "live field_status.yaml currently has no quarantined datasets "
                "— nothing to smoke-test"
            )
        field = quarantined[0]
        result = evaluate_field_dependencies(
            fields=[field], stage="sandbox_screening",
        )
        assert result.eligible is False
        assert field in result.disallowed_fields
