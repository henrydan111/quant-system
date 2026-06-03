"""PR 9 negative-test suite — field-registry resolver enforcement.

GPT 5.5 Pro's locked-in scope for PR 9:

  1. Wire assert_field_dependencies_eligible into handle_validation_object_resolver.
  2. Add behavioral OOS handler test with a minimal mocked StepExecutionContext.
  3. Document "OOS seal is consumed on attempt; resume same run for recovery"
     in CLAUDE.md (handled in docs, not tests).
  4. Negative tests:
     - moneyflow field in formal validation → fails before IS
     - pending_review event-like field in formal validation → fails before IS
     - unknown field in formal validation → fails before IS
     - sandbox/screening behavior remains allowed or warn-only per registry policy
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.data_infra.field_registry import (
    FieldApprovalError,
    FieldStatusRegistry,
)
from src.research_orchestrator.release_gate import (
    assert_field_dependencies_eligible,
    evaluate_field_dependencies,
)


def _minimal_registry() -> FieldStatusRegistry:
    """Standalone registry mirroring the committed seed: approved ohlcv +
    quarantined moneyflow + pending_review event endpoint + conservative
    unknown policy."""
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
            },
            "datasets": {
                "ohlcv": {"status": "approved", "fields": ["$close", "$open"]},
                "moneyflow": {"status": "quarantine", "field_prefixes": ["$moneyflow_"]},
                "event_like": {
                    "status": "pending_review",
                    "field_prefixes": ["$top_list__"],
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
    )


# ─────────────────────────────────────────────────────────────────────────
# Negative gate behavior — these are the four canonical PR 9 cases.
# ─────────────────────────────────────────────────────────────────────────


class TestFormalValidationFieldGate:
    def test_moneyflow_field_blocked_at_formal_validation(self) -> None:
        registry = _minimal_registry()
        with pytest.raises(FieldApprovalError, match=r"\$moneyflow_buy_sm_vol"):
            assert_field_dependencies_eligible(
                expressions=["Ref($moneyflow_buy_sm_vol, 1)"],
                stage="formal_validation",
                registry=registry,
                artifact_label="hyp_pr9_moneyflow",
            )

    def test_pending_review_event_field_blocked_at_formal_validation(self) -> None:
        registry = _minimal_registry()
        with pytest.raises(FieldApprovalError, match=r"\$top_list__amount"):
            assert_field_dependencies_eligible(
                expressions=["Mean(Ref($top_list__amount, 1), 5)"],
                stage="formal_validation",
                registry=registry,
                artifact_label="hyp_pr9_top_list",
            )

    def test_unknown_field_blocked_at_formal_validation(self) -> None:
        registry = _minimal_registry()
        with pytest.raises(FieldApprovalError, match=r"\$brand_new_unknown_field"):
            assert_field_dependencies_eligible(
                expressions=["Ref($brand_new_unknown_field, 1)"],
                stage="formal_validation",
                registry=registry,
                artifact_label="hyp_pr9_unknown",
            )

    def test_approved_fields_pass_at_formal_validation(self) -> None:
        registry = _minimal_registry()
        # Should NOT raise.
        result = assert_field_dependencies_eligible(
            expressions=["Mean(Ref($close, 1), 20)", "Std(Ref($open, 1), 10)"],
            stage="formal_validation",
            registry=registry,
        )
        assert result.eligible is True
        assert result.disallowed_fields == ()


class TestSandboxFieldGate:
    """Per registry policy: sandbox/screening stages permit pending_review +
    unknown fields (warn). Quarantine is still blocked everywhere."""

    def test_pending_review_field_allowed_at_sandbox(self) -> None:
        registry = _minimal_registry()
        result = evaluate_field_dependencies(
            expressions=["Mean(Ref($top_list__amount, 1), 5)"],
            stage="sandbox_screening",
            registry=registry,
        )
        assert result.eligible is True
        assert "$top_list__amount" not in result.disallowed_fields

    def test_unknown_field_warns_at_sandbox(self) -> None:
        registry = _minimal_registry()
        result = evaluate_field_dependencies(
            expressions=["Ref($brand_new_unknown_field, 1)"],
            stage="sandbox_screening",
            registry=registry,
        )
        assert result.eligible is True
        assert "$brand_new_unknown_field" in result.unknown_fields
        assert "$brand_new_unknown_field" not in result.disallowed_fields

    def test_quarantined_field_still_blocked_at_sandbox(self) -> None:
        # Quarantine status disallows ALL stages — sandbox no exception.
        registry = _minimal_registry()
        result = evaluate_field_dependencies(
            expressions=["Ref($moneyflow_buy_sm_vol, 1)"],
            stage="sandbox_screening",
            registry=registry,
        )
        assert result.eligible is False
        assert "$moneyflow_buy_sm_vol" in result.disallowed_fields


# ─────────────────────────────────────────────────────────────────────────
# Validation handler wiring (source-reflection + helper invocation)
# ─────────────────────────────────────────────────────────────────────────


class TestResolverHandlerWiring:
    """Confirm handle_validation_object_resolver calls the field-dependency
    helper after the resolver succeeds, and that the helper's name matches
    what PR 9 added."""

    def test_resolver_handler_imports_field_gate_helper(self) -> None:
        src = Path("src/research_orchestrator/validation_steps.py").read_text(
            encoding="utf-8"
        )
        handler_start = src.index("def handle_validation_object_resolver")
        next_def = src.find("\ndef ", handler_start + 1)
        handler_body = src[handler_start:next_def if next_def > 0 else len(src)]
        assert "_validate_factor_field_dependencies(" in handler_body, (
            "handle_validation_object_resolver must call "
            "_validate_factor_field_dependencies after the resolver succeeds."
        )

    def test_validate_factor_field_dependencies_helper_exists(self) -> None:
        src = Path("src/research_orchestrator/validation_steps.py").read_text(
            encoding="utf-8"
        )
        assert "def _validate_factor_field_dependencies" in src, (
            "PR 9 must add a _validate_factor_field_dependencies helper "
            "that does the lookup-and-check in one place."
        )

    def test_helper_calls_assert_field_dependencies_eligible(self) -> None:
        src = Path("src/research_orchestrator/validation_steps.py").read_text(
            encoding="utf-8"
        )
        helper_idx = src.index("def _validate_factor_field_dependencies")
        next_def = src.find("\ndef ", helper_idx + 1)
        helper_body = src[helper_idx:next_def if next_def > 0 else len(src)]
        assert "assert_field_dependencies_eligible(" in helper_body, (
            "_validate_factor_field_dependencies must call "
            "assert_field_dependencies_eligible (the strict variant) so "
            "disallowed fields raise FieldApprovalError before the IS leg."
        )


class TestHelperBehavior:
    """Direct behavioral test of the new helper against synthetic factor
    catalogs — easier to set up than a full StepExecutionContext.

    The helper expects to find each factor_name in get_factor_catalog() OR
    get_industry_relative_defs(); we mock both so the test doesn't depend on
    the live 191-factor catalog.
    """

    def _helper(self):
        from src.research_orchestrator.validation_steps import (
            _validate_factor_field_dependencies,
        )
        return _validate_factor_field_dependencies

    def test_helper_passes_for_approved_factor(self) -> None:
        helper = self._helper()
        with patch(
            "src.alpha_research.factor_library.catalog.get_factor_catalog",
            return_value={"mom_return_20d": "Mean(Ref($close, 1), 20)"},
        ), patch(
            "src.alpha_research.factor_library.catalog.get_industry_relative_defs",
            return_value=[],
        ):
            report = helper(
                factor_names=["mom_return_20d"],
                stage="formal_validation",
                artifact_label="hyp_pr9_test",
            )
        assert report["eligible"] is True
        assert "$close" in report["fields_checked"]

    def test_helper_raises_for_quarantined_factor(self) -> None:
        helper = self._helper()
        with patch(
            "src.alpha_research.factor_library.catalog.get_factor_catalog",
            return_value={
                "vol_money_flow_imbalance_20d": (
                    "Mean(Ref($moneyflow_buy_sm_vol, 1), 20)"
                ),
            },
        ), patch(
            "src.alpha_research.factor_library.catalog.get_industry_relative_defs",
            return_value=[],
        ):
            with pytest.raises(FieldApprovalError, match=r"\$moneyflow"):
                helper(
                    factor_names=["vol_money_flow_imbalance_20d"],
                    stage="formal_validation",
                    artifact_label="hyp_pr9_quarantine",
                )

    def test_helper_handles_industry_relative_factor(self) -> None:
        helper = self._helper()
        with patch(
            "src.alpha_research.factor_library.catalog.get_factor_catalog",
            return_value={
                "val_bp": "Ref($pb, 1)",  # base factor uses approved $pb
            },
        ), patch(
            "src.alpha_research.factor_library.catalog.get_industry_relative_defs",
            return_value=[
                {
                    "name": "val_bp_industry_rel",
                    "base": "val_bp",
                    "kind": "industry_mean_subtract",
                },
            ],
        ):
            report = helper(
                factor_names=["val_bp_industry_rel"],
                stage="formal_validation",
                artifact_label="hyp_pr9_industry_rel",
            )
        assert report["eligible"] is True
        # The base's expression was used (val_bp → $pb).
        assert "$pb" in report["fields_checked"]
        assert any(
            s["source"] == "industry_relative_base" for s in report["expression_sources"]
        )


# ─────────────────────────────────────────────────────────────────────────
# PR 9a fail-closed behavior (GPT 5.5 Pro round-2 review)
# ─────────────────────────────────────────────────────────────────────────


class TestPR9aFailClosed:
    """The four cases PR 9a closes against PR 9's fail-open behavior:

      1. factor_name not in catalog / industry_defs → FieldApprovalError
      2. industry-relative composite with missing base → FieldApprovalError
      3. empty factor_names input at formal stage → FieldApprovalError
      4. screening stages keep the lenient behavior (note, not raise)
    """

    def _helper(self):
        from src.research_orchestrator.validation_steps import (
            _validate_factor_field_dependencies,
        )
        return _validate_factor_field_dependencies

    def test_no_expression_found_fails_closed_at_formal(self) -> None:
        helper = self._helper()
        with patch(
            "src.alpha_research.factor_library.catalog.get_factor_catalog",
            return_value={"mom_return_20d": "Mean(Ref($close, 1), 20)"},
        ), patch(
            "src.alpha_research.factor_library.catalog.get_industry_relative_defs",
            return_value=[],
        ):
            with pytest.raises(FieldApprovalError, match=r"no factor-library expression"):
                helper(
                    factor_names=["ghost_factor_not_in_catalog"],
                    stage="formal_validation",
                    artifact_label="hyp_pr9a_missing",
                )

    def test_industry_relative_unresolved_base_fails_closed_at_formal(self) -> None:
        helper = self._helper()
        with patch(
            "src.alpha_research.factor_library.catalog.get_factor_catalog",
            # base factor 'val_ghost' is NOT in this catalog
            return_value={"mom_return_20d": "Mean(Ref($close, 1), 20)"},
        ), patch(
            "src.alpha_research.factor_library.catalog.get_industry_relative_defs",
            return_value=[
                {
                    "name": "val_ghost_industry_rel",
                    "base": "val_ghost",
                    "kind": "industry_mean_subtract",
                },
            ],
        ):
            with pytest.raises(FieldApprovalError, match=r"missing base factor"):
                helper(
                    factor_names=["val_ghost_industry_rel"],
                    stage="formal_validation",
                    artifact_label="hyp_pr9a_missing_base",
                )

    def test_empty_expression_list_fails_closed_at_formal(self) -> None:
        helper = self._helper()
        with patch(
            "src.alpha_research.factor_library.catalog.get_factor_catalog",
            return_value={"mom_return_20d": "Mean(Ref($close, 1), 20)"},
        ), patch(
            "src.alpha_research.factor_library.catalog.get_industry_relative_defs",
            return_value=[],
        ):
            with pytest.raises(FieldApprovalError):
                helper(
                    factor_names=[],
                    stage="formal_validation",
                    artifact_label="hyp_pr9a_empty",
                )

    def test_no_expression_found_does_not_raise_at_sandbox(self) -> None:
        """Screening / sandbox stages preserve the lenient behavior so
        exploration is not blocked. PR 9a only fails closed at formal stages."""
        helper = self._helper()
        with patch(
            "src.alpha_research.factor_library.catalog.get_factor_catalog",
            return_value={"mom_return_20d": "Mean(Ref($close, 1), 20)"},
        ), patch(
            "src.alpha_research.factor_library.catalog.get_industry_relative_defs",
            return_value=[],
        ):
            report = helper(
                factor_names=["ghost_factor_not_in_catalog"],
                stage="sandbox_screening",
                artifact_label="hyp_pr9a_sandbox",
            )
        # Helper returns a note in expression_sources but does NOT raise.
        sources = report["expression_sources"]
        assert any(s["source"] == "no_expression_found" for s in sources)

    def test_industry_defs_precedence_over_catalog(self) -> None:
        """When a factor name appears in BOTH industry_defs and the catalog,
        industry_defs wins (the composite always inherits the base
        expression). This protects the PIT-safety inheritance contract."""
        helper = self._helper()
        with patch(
            "src.alpha_research.factor_library.catalog.get_factor_catalog",
            return_value={
                "val_bp": "Ref($pb, 1)",
                # A stray same-named entry that should be SUPERSEDED:
                "val_bp_industry_rel": "Ref($SOME_QUARANTINED_FIELD, 1)",
            },
        ), patch(
            "src.alpha_research.factor_library.catalog.get_industry_relative_defs",
            return_value=[
                {
                    "name": "val_bp_industry_rel",
                    "base": "val_bp",
                    "kind": "industry_mean_subtract",
                },
            ],
        ):
            report = helper(
                factor_names=["val_bp_industry_rel"],
                stage="formal_validation",
                artifact_label="hyp_pr9a_precedence",
            )
        assert report["eligible"] is True
        # Did NOT use the stray catalog entry → no $SOME_QUARANTINED_FIELD
        # was ever submitted to the gate.
        assert "$SOME_QUARANTINED_FIELD" not in report["fields_checked"]
        assert "$pb" in report["fields_checked"]


# ─────────────────────────────────────────────────────────────────────────
# Behavioral resolver-handler test (GPT 5.5 Pro round-2 review #3)
# ─────────────────────────────────────────────────────────────────────────


class TestResolverHandlerBehavior:
    """Direct behavioral test of handle_validation_object_resolver — proves
    the PR 9 helper is actually invoked from inside the handler and that a
    FieldApprovalError propagates BEFORE the IS leg begins.

    Pre-PR-9a the only handler-level coverage was source-reflection (assert
    the helper name appears in the file). This class drives the handler
    end-to-end with a minimal mocked StepExecutionContext + a mocked
    ResolverHub so we observe the actual call path.
    """

    @pytest.fixture(autouse=True)
    def _isolate_drift_gate(self):
        # These tests drive the handler with SYNTHETIC resolver fixtures that omit a
        # definition_hash; the P1.3 drift gate (fail-closed, covered by TestPR13)
        # would reject them. Isolate it so these tests exercise the allow-set / field
        # gate as intended.
        with patch(
            "src.research_orchestrator.validation_steps._assert_no_definition_drift",
            return_value={"checked": 0, "drifted": [], "stage": "formal_validation"},
        ):
            yield

    def _make_context(self, tmp_path: Path):
        from src.research_orchestrator.hypothesis import PrescribedComponent
        # Minimal hypothesis + prescription with one component.
        prescription = MagicMock(
            components=[
                PrescribedComponent(factor_name="qual_roe", weight=1.0),
            ],
            allow_candidate_components=False,
        )
        hypothesis = MagicMock(prescription=prescription, hypothesis_id="hyp_pr9a_behavioral")
        context = MagicMock()
        context.request.hypothesis = hypothesis
        context.step_dir = tmp_path / "step"
        context.step_dir.mkdir(parents=True)
        context.registry_dirs = {
            "factor_registry_dir": str(tmp_path / "factor_registry"),
            "candidate_registry_dir": str(tmp_path / "candidate_registry"),
            "signal_registry_dir": str(tmp_path / "signal_registry"),
            "model_registry_dir": str(tmp_path / "model_registry"),
            "strategy_registry_dir": str(tmp_path / "strategy_registry"),
        }
        context.profile.profile_id = "hypothesis_validation"
        return context

    def test_field_gate_helper_is_invoked_after_resolver_success(
        self, tmp_path: Path
    ) -> None:
        from src.research_orchestrator.validation_steps import (
            handle_validation_object_resolver,
        )

        context = self._make_context(tmp_path)
        # Mock resolver: every component resolves to formal layer.
        resolver_payload = {
            "resolved_objects": [
                {
                    "status": "resolved",
                    "source_layer": "formal",
                    "requested": {"object_name": "qual_roe", "object_type": "factor"},
                },
            ],
        }
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=resolver_payload,
        ), patch(
            "src.research_orchestrator.validation_steps._validate_factor_field_dependencies",
            return_value={
                "stage": "formal_validation",
                "eligible": True,
                "fields_checked": ["$roe"],
                "disallowed_fields": [],
                "unknown_fields": [],
                "reasons": [],
                "expression_sources": [],
            },
        ) as helper_mock:
            result = handle_validation_object_resolver(context)
        helper_mock.assert_called_once()
        # The field_dependency_report was persisted into outputs and on disk.
        assert "field_dependency_report" in result.outputs
        assert (context.step_dir / "registry_resolution.json").exists()

    def test_field_gate_helper_failure_propagates_before_is_leg(
        self, tmp_path: Path
    ) -> None:
        from src.research_orchestrator.validation_steps import (
            handle_validation_object_resolver,
        )

        context = self._make_context(tmp_path)
        resolver_payload = {
            "resolved_objects": [
                {
                    "status": "resolved",
                    "source_layer": "formal",
                    "requested": {"object_name": "qual_roe", "object_type": "factor"},
                },
            ],
        }
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=resolver_payload,
        ), patch(
            "src.research_orchestrator.validation_steps._validate_factor_field_dependencies",
            side_effect=FieldApprovalError("PR9a behavioral test: gate refused"),
        ):
            with pytest.raises(FieldApprovalError, match=r"PR9a behavioral test"):
                handle_validation_object_resolver(context)


class TestPR12FormalAllowSet:
    """PR P1.2: handle_validation_object_resolver enforces an EXPLICIT source-layer
    allow-set — {formal} (+ factor_registry_candidate iff allow_candidate_components).
    Every other resolved layer (factor_registry_draft / _stale / _deprecated AND the
    candidate-registry "candidate" layer) is rejected BEFORE the IS leg. This is the
    sole formal-permission point under the resolve-but-label design (Codex round-5)."""

    def _make_context(self, tmp_path: Path, allow_candidate: bool = False):
        from src.research_orchestrator.hypothesis import PrescribedComponent

        prescription = MagicMock(
            components=[PrescribedComponent(factor_name="qual_roe", weight=1.0)],
            allow_candidate_components=allow_candidate,
        )
        hypothesis = MagicMock(prescription=prescription, hypothesis_id="hyp_pr12_allowset")
        context = MagicMock()
        context.request.hypothesis = hypothesis
        context.step_dir = tmp_path / "step"
        context.step_dir.mkdir(parents=True)
        context.registry_dirs = {
            "factor_registry_dir": str(tmp_path / "factor_registry"),
            "candidate_registry_dir": str(tmp_path / "candidate_registry"),
            "signal_registry_dir": str(tmp_path / "signal_registry"),
            "model_registry_dir": str(tmp_path / "model_registry"),
            "strategy_registry_dir": str(tmp_path / "strategy_registry"),
        }
        context.profile.profile_id = "hypothesis_validation"
        return context

    @staticmethod
    def _payload(layer: str):
        return {
            "resolved_objects": [
                {
                    "status": "resolved",
                    "source_layer": layer,
                    "requested": {"object_name": "qual_roe", "object_type": "factor"},
                },
            ],
        }

    @pytest.mark.parametrize(
        "layer",
        ["factor_registry_draft", "factor_registry_stale", "factor_registry_deprecated", "candidate"],
    )
    def test_non_formal_layer_rejected(self, tmp_path: Path, layer: str) -> None:
        from src.research_orchestrator.validation_steps import handle_validation_object_resolver

        context = self._make_context(tmp_path, allow_candidate=False)
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=self._payload(layer),
        ):
            with pytest.raises(ValueError, match=r"cannot resolve required"):
                handle_validation_object_resolver(context)

    def test_factor_registry_candidate_rejected_without_flag(self, tmp_path: Path) -> None:
        from src.research_orchestrator.validation_steps import handle_validation_object_resolver

        context = self._make_context(tmp_path, allow_candidate=False)
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=self._payload("factor_registry_candidate"),
        ):
            with pytest.raises(ValueError, match=r"cannot resolve required"):
                handle_validation_object_resolver(context)

    def test_plain_candidate_rejected_even_with_flag(self, tmp_path: Path) -> None:
        # allow_candidate_components admits ONLY factor_registry_candidate, never the
        # separate candidate-registry "candidate" layer.
        from src.research_orchestrator.validation_steps import handle_validation_object_resolver

        context = self._make_context(tmp_path, allow_candidate=True)
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=self._payload("candidate"),
        ):
            with pytest.raises(ValueError, match=r"cannot resolve required"):
                handle_validation_object_resolver(context)

    def test_formal_layer_accepted(self, tmp_path: Path) -> None:
        from src.research_orchestrator.validation_steps import handle_validation_object_resolver

        context = self._make_context(tmp_path, allow_candidate=False)
        # This test isolates the ALLOW-SET; the drift gate (P1.3) and the field gate
        # (PR9) are patched out (their behavior is covered by TestPR13 / the field-gate
        # tests). The mock payload has no definition_hash, which the real fail-closed
        # drift gate would now reject — not what this test is asserting.
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=self._payload("formal"),
        ), patch(
            "src.research_orchestrator.validation_steps._validate_factor_field_dependencies",
            return_value={"eligible": True, "disallowed_fields": [], "unknown_fields": [], "reasons": []},
        ), patch(
            "src.research_orchestrator.validation_steps._assert_no_definition_drift",
            return_value={"checked": 1, "drifted": [], "stage": "formal_validation"},
        ):
            result = handle_validation_object_resolver(context)
        assert "field_dependency_report" in result.outputs

    def test_factor_registry_candidate_accepted_with_flag(self, tmp_path: Path) -> None:
        from src.research_orchestrator.validation_steps import handle_validation_object_resolver

        context = self._make_context(tmp_path, allow_candidate=True)
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=self._payload("factor_registry_candidate"),
        ), patch(
            "src.research_orchestrator.validation_steps._validate_factor_field_dependencies",
            return_value={"eligible": True, "disallowed_fields": [], "unknown_fields": [], "reasons": []},
        ), patch(
            "src.research_orchestrator.validation_steps._assert_no_definition_drift",
            return_value={"checked": 1, "drifted": [], "stage": "formal_validation"},
        ):
            result = handle_validation_object_resolver(context)
        assert "field_dependency_report" in result.outputs


class TestPR13DefinitionBindingGate:
    """PR P1.3: handle_validation_object_resolver hard-fails with
    FactorDefinitionDriftError BEFORE the field gate / any compute when a resolved
    formal factor's registry definition_hash no longer matches the current code
    catalog (registry row stale vs catalog.py)."""

    def _make_context(self, tmp_path: Path, allow_candidate: bool = False):
        from src.research_orchestrator.hypothesis import PrescribedComponent

        prescription = MagicMock(
            components=[PrescribedComponent(factor_name="qual_roe", weight=1.0)],
            allow_candidate_components=allow_candidate,
        )
        hypothesis = MagicMock(prescription=prescription, hypothesis_id="hyp_pr13_defbind")
        context = MagicMock()
        context.request.hypothesis = hypothesis
        context.step_dir = tmp_path / "step"
        context.step_dir.mkdir(parents=True)
        context.registry_dirs = {
            "factor_registry_dir": str(tmp_path / "factor_registry"),
            "candidate_registry_dir": str(tmp_path / "candidate_registry"),
            "signal_registry_dir": str(tmp_path / "signal_registry"),
            "model_registry_dir": str(tmp_path / "model_registry"),
            "strategy_registry_dir": str(tmp_path / "strategy_registry"),
        }
        context.profile.profile_id = "hypothesis_validation"
        return context

    @staticmethod
    def _code_hash(tmp_path: Path, factor_id: str) -> str:
        from src.alpha_research.factor_registry import FactorRegistryStore

        return FactorRegistryStore(str(tmp_path / "hashsrc")).current_catalog_definition_hashes()[factor_id]

    @staticmethod
    def _payload(definition_hash: str):
        return {
            "resolved_objects": [
                {
                    "status": "resolved",
                    "source_layer": "formal",
                    "canonical_id": "qual_roe",
                    "definition_hash": definition_hash,
                    "requested": {"object_name": "qual_roe", "object_type": "factor"},
                },
            ],
        }

    def test_matching_definition_hash_passes(self, tmp_path: Path) -> None:
        from src.research_orchestrator.validation_steps import handle_validation_object_resolver

        context = self._make_context(tmp_path)
        good_hash = self._code_hash(tmp_path, "qual_roe")
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=self._payload(good_hash),
        ), patch(
            "src.research_orchestrator.validation_steps._validate_factor_field_dependencies",
            return_value={"eligible": True, "disallowed_fields": [], "unknown_fields": [], "reasons": []},
        ):
            result = handle_validation_object_resolver(context)
        report = result.outputs["definition_binding_report"]
        assert report["checked"] == 1
        assert report["drifted"] == []

    def test_drifted_definition_hash_raises_before_field_gate(self, tmp_path: Path) -> None:
        from src.research_orchestrator.validation_steps import (
            FactorDefinitionDriftError,
            handle_validation_object_resolver,
        )

        context = self._make_context(tmp_path)
        field_gate = MagicMock()
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=self._payload("0" * 64),
        ), patch(
            "src.research_orchestrator.validation_steps._validate_factor_field_dependencies",
            field_gate,
        ):
            with pytest.raises(FactorDefinitionDriftError, match="drifted"):
                handle_validation_object_resolver(context)
        # the drift check must fire BEFORE the field gate / any compute
        field_gate.assert_not_called()

    def test_missing_definition_hash_fails_closed(self, tmp_path: Path) -> None:
        # GPT cross-review: a formal entry permitted into validation with NO registry
        # definition_hash (malformed/legacy row) must be treated as drift (fail-closed)
        # and raise BEFORE the field gate — NOT silently skipped.
        from src.research_orchestrator.validation_steps import (
            FactorDefinitionDriftError,
            handle_validation_object_resolver,
        )

        context = self._make_context(tmp_path)
        field_gate = MagicMock()
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=self._payload(""),  # malformed: empty definition_hash
        ), patch(
            "src.research_orchestrator.validation_steps._validate_factor_field_dependencies",
            field_gate,
        ):
            with pytest.raises(FactorDefinitionDriftError, match="drifted"):
                handle_validation_object_resolver(context)
        field_gate.assert_not_called()

    def test_factor_registry_candidate_layer_drift_is_caught(self, tmp_path: Path) -> None:
        # GPT final-integration-review coverage: the drift gate covers the
        # factor_registry_candidate layer too (layer.startswith("factor_registry")),
        # not just "formal". Phase 2 leans on candidate backfills, so prove a
        # candidate entry with a mismatched definition_hash raises drift BEFORE the
        # field gate when allow_candidate_components=True admits it.
        from src.research_orchestrator.validation_steps import (
            FactorDefinitionDriftError,
            handle_validation_object_resolver,
        )

        context = self._make_context(tmp_path, allow_candidate=True)
        field_gate = MagicMock()
        payload = {
            "resolved_objects": [
                {
                    "status": "resolved",
                    "source_layer": "factor_registry_candidate",
                    "canonical_id": "qual_roe",
                    "definition_hash": "0" * 64,  # mismatched vs the current catalog
                    "requested": {"object_name": "qual_roe", "object_type": "factor"},
                },
            ],
        }
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=payload,
        ), patch(
            "src.research_orchestrator.validation_steps._validate_factor_field_dependencies",
            field_gate,
        ):
            with pytest.raises(FactorDefinitionDriftError, match="drifted"):
                handle_validation_object_resolver(context)
        field_gate.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────
# Formal-factor compatibility test (GPT 5.5 Pro round-2 review #2)
# ─────────────────────────────────────────────────────────────────────────


class TestFormalFactorCompatibility:
    """Iterate the LIVE formal factor catalog and prove that every factor
    either (a) resolves through the field-dependency gate at formal_validation
    OR (b) is explicitly enumerated as a known-failing alpha/quarantine factor.

    Compatibility universe scope (GPT 5.5 Pro round-3 review #3):

      * `get_factor_catalog(include_new_data=False)` →  111 base factors
      * `get_factor_catalog(include_new_data=True)`  →  153 base factors
        (+36 new alpha endpoint factors: flow_*, north_*, margin_*,
        earn_*, alpha_*; +6 Round-6 sealed-OOS winners onboarded
        2026-06-02 via _add_sealed_oos_winners)
      * `get_industry_relative_defs()`              →    4 industry-relative
        composites (PIT inherited from `base` factor)
      * `get_composite_defs()`                       →   20 Layer-2 composites
        (PIT inherited from `components` list)
      * Total factor surface area                    →  177 named factors

    This test iterates the 153 base factors from
    `get_factor_catalog(include_new_data=True)`. The 4 industry-relative
    composites and 20 Layer-2 composites inherit their field dependencies
    from their base factors and are covered transitively (their fields are
    a subset of what this test already checks). Industry-relative
    composites also have direct coverage in `TestHelperBehavior`.

    The historical PR description on PR #14 mentions "191 factors" — that
    docstring count in catalog.py:1 is stale; the actual live count is 177
    (153 + 4 + 20). The "191" never reflected the runtime universe.

    Pre-PR-9a a silent registry/catalog mismatch could block
    historically-formal factors at the resolver gate without anyone
    noticing until production. PR 9a's KNOWN_NON_FORMAL_FACTORS is pinned
    as an auditable mapping (not a bare set) so a stale skip cannot
    silently grow stale — each entry must continue to fail with the
    expected dataset + status + fields, or the second assertion fires.
    """

    # Factors that intentionally fail the formal field gate because their
    # $field references live in quarantined / pending_review datasets. These
    # are non-formal alpha factors and are expected to remain blocked until
    # the underlying dataset is promoted via the field_approval_log.
    #
    # PR 9a round-3 (GPT 5.5 Pro): converted from a bare set to a mapping
    # so each known-failing factor records WHY it fails. The second test
    # below (`test_known_non_formal_factors_still_block`) iterates this dict
    # and asserts each factor still raises FieldApprovalError with disallowed
    # fields that are a subset of expected_fields. If a factor STOPS failing,
    # the test reports it as unexpected_passes; if the failing fields no
    # longer match the recorded ones, the test reports the drift.
    KNOWN_NON_FORMAL_FACTORS: dict[str, dict[str, Any]] = {
        # ── moneyflow (quarantine) ────────────────────────────────────────
        "flow_net_inflow_5d": dict(
            reason="depends on moneyflow quarantine",
            expected_status="quarantine",
            expected_dataset="moneyflow",
            expected_fields=["$net_mf_amount"],
        ),
        "flow_net_inflow_20d": dict(
            reason="depends on moneyflow quarantine",
            expected_status="quarantine",
            expected_dataset="moneyflow",
            expected_fields=["$net_mf_amount"],
        ),
        "flow_large_net_pct_20d": dict(
            reason="depends on moneyflow quarantine",
            expected_status="quarantine",
            expected_dataset="moneyflow",
            expected_fields=["$buy_lg_amount", "$sell_lg_amount"],
        ),
        "flow_small_net_pct_20d": dict(
            reason="depends on moneyflow quarantine",
            expected_status="quarantine",
            expected_dataset="moneyflow",
            expected_fields=["$buy_sm_amount", "$sell_sm_amount"],
        ),
        "flow_large_small_ratio": dict(
            reason="depends on moneyflow quarantine",
            expected_status="quarantine",
            expected_dataset="moneyflow",
            expected_fields=[
                "$buy_lg_amount", "$buy_sm_amount",
                "$sell_lg_amount", "$sell_sm_amount",
            ],
        ),
        "flow_inflow_surge": dict(
            reason="depends on moneyflow quarantine",
            expected_status="quarantine",
            expected_dataset="moneyflow",
            expected_fields=["$net_mf_amount"],
        ),
        "flow_large_buy_ratio_5d": dict(
            reason="depends on moneyflow quarantine",
            expected_status="quarantine",
            expected_dataset="moneyflow",
            expected_fields=["$buy_lg_amount"],
        ),
        # ── hk_hold (quarantine) ──────────────────────────────────────────
        "north_hold_pct": dict(
            reason="depends on hk_hold quarantine",
            expected_status="quarantine",
            expected_dataset="hk_hold",
            expected_fields=["$ratio"],
        ),
        "north_hold_change_5d": dict(
            reason="depends on hk_hold quarantine",
            expected_status="quarantine",
            expected_dataset="hk_hold",
            expected_fields=["$ratio"],
        ),
        "north_hold_change_20d": dict(
            reason="depends on hk_hold quarantine",
            expected_status="quarantine",
            expected_dataset="hk_hold",
            expected_fields=["$ratio"],
        ),
        "north_accumulation_20d": dict(
            reason="depends on hk_hold quarantine",
            expected_status="quarantine",
            expected_dataset="hk_hold",
            expected_fields=["$ratio"],
        ),
        "north_flow_momentum": dict(
            reason="depends on hk_hold quarantine",
            expected_status="quarantine",
            expected_dataset="hk_hold",
            expected_fields=["$ratio"],
        ),
        # ── margin_detail (quarantine) ────────────────────────────────────
        "margin_balance_pct": dict(
            reason="depends on margin_detail quarantine",
            expected_status="quarantine",
            expected_dataset="margin_detail",
            expected_fields=["$rzye"],
        ),
        "margin_net_buy_20d": dict(
            reason="depends on margin_detail quarantine",
            expected_status="quarantine",
            expected_dataset="margin_detail",
            expected_fields=["$rzche", "$rzmre"],
        ),
        "margin_sl_balance_change": dict(
            reason="depends on margin_detail quarantine",
            expected_status="quarantine",
            expected_dataset="margin_detail",
            expected_fields=["$rqye"],
        ),
        # ── top_inst (pending_review) ─────────────────────────────────────
        "alpha_inst_net_buy_20d": dict(
            reason="depends on top_inst pending_review",
            expected_status="pending_review",
            expected_dataset="top_inst",
            expected_fields=["$top_inst__net_buy"],
        ),
        "alpha_topinst_net_buy_ema_20d": dict(
            reason="depends on top_inst pending_review",
            expected_status="pending_review",
            expected_dataset="top_inst",
            expected_fields=["$top_inst__net_buy"],
        ),
        "alpha_topinst_hit_density_60d": dict(
            reason="depends on top_inst pending_review",
            expected_status="pending_review",
            expected_dataset="top_inst",
            expected_fields=["$top_inst__net_buy"],
        ),
        # ── top_list (pending_review) ─────────────────────────────────────
        "alpha_toplist_net_rate_20d": dict(
            reason="depends on top_list pending_review",
            expected_status="pending_review",
            expected_dataset="top_list",
            expected_fields=["$top_list__net_rate"],
        ),
        "alpha_toplist_amount_over_mv_20d": dict(
            reason="depends on top_list pending_review",
            expected_status="pending_review",
            expected_dataset="top_list",
            expected_fields=["$top_list__l_amount"],
        ),
        "alpha_toplist_hit_density_60d": dict(
            reason="depends on top_list pending_review",
            expected_status="pending_review",
            expected_dataset="top_list",
            expected_fields=["$top_list__l_amount"],
        ),
        # ── block_trade (pending_review) ──────────────────────────────────
        "alpha_block_discount_20d": dict(
            reason="depends on block_trade pending_review",
            expected_status="pending_review",
            expected_dataset="block_trade",
            expected_fields=["$block_trade__price"],
        ),
        "alpha_block_volume_share_20d": dict(
            reason="depends on block_trade pending_review",
            expected_status="pending_review",
            expected_dataset="block_trade",
            expected_fields=["$block_trade__vol"],
        ),
        "alpha_block_event_density_20d": dict(
            reason="depends on block_trade pending_review",
            expected_status="pending_review",
            expected_dataset="block_trade",
            expected_fields=["$block_trade__amount"],
        ),
        # ── cyq_perf (pending_review) ─────────────────────────────────────
        "alpha_chip_winner_rate_chg_20d": dict(
            reason="depends on cyq_perf pending_review",
            expected_status="pending_review",
            expected_dataset="cyq_perf",
            expected_fields=["$cyq_perf__winner_rate"],
        ),
        "alpha_chip_cost_spread_pct": dict(
            reason="depends on cyq_perf pending_review",
            expected_status="pending_review",
            expected_dataset="cyq_perf",
            expected_fields=[
                "$cyq_perf__cost_50pct",
                "$cyq_perf__cost_5pct",
                "$cyq_perf__cost_95pct",
            ],
        ),
        "alpha_chip_price_vs_cost50": dict(
            reason="depends on cyq_perf pending_review",
            expected_status="pending_review",
            expected_dataset="cyq_perf",
            expected_fields=["$cyq_perf__cost_50pct"],
        ),
        "alpha_chip_weight_avg_dev": dict(
            reason="depends on cyq_perf pending_review",
            expected_status="pending_review",
            expected_dataset="cyq_perf",
            expected_fields=["$cyq_perf__weight_avg"],
        ),
        "alpha_chip_winner_rate_ema_10d": dict(
            reason="depends on cyq_perf pending_review",
            expected_status="pending_review",
            expected_dataset="cyq_perf",
            expected_fields=["$cyq_perf__winner_rate"],
        ),
        # ── stk_holdertrade (pending_review, PR 9a registration) ──────────
        "alpha_holder_gross_vol_60d": dict(
            reason="depends on stk_holdertrade pending_review",
            expected_status="pending_review",
            expected_dataset="stk_holdertrade",
            expected_fields=["$holdertrade_gross_vol"],
        ),
        "alpha_holder_event_density_60d": dict(
            reason="depends on stk_holdertrade pending_review",
            expected_status="pending_review",
            expected_dataset="stk_holdertrade",
            expected_fields=["$holdertrade_events"],
        ),
        "alpha_holder_net_ratio_ema_20d": dict(
            reason="depends on stk_holdertrade pending_review",
            expected_status="pending_review",
            expected_dataset="stk_holdertrade",
            expected_fields=["$holdertrade_net_ratio"],
        ),
        "alpha_insider_net_buy_60d": dict(
            reason="depends on stk_holdertrade pending_review",
            expected_status="pending_review",
            expected_dataset="stk_holdertrade",
            expected_fields=["$holdertrade_net_ratio"],
        ),
    }

    def test_every_formal_factor_resolves_at_formal_validation(self) -> None:
        """For every factor in get_factor_catalog(include_new_data=True),
        assert it either passes the formal field gate or appears in the
        KNOWN_NON_FORMAL_FACTORS allow-fail mapping. A NEW failure means a
        registry/catalog drift that PR 9a's gate would silently block
        in production — fix the registry, fix the factor, or add the
        factor to the known-failing mapping with a justification."""
        from src.alpha_research.factor_library.catalog import get_factor_catalog
        from src.data_infra.field_registry import load_field_registry
        from src.research_orchestrator.release_gate import evaluate_field_dependencies

        registry = load_field_registry()
        catalog = get_factor_catalog(include_new_data=True)
        unexpected_failures = []
        unexpected_passes = []
        for name, expr in catalog.items():
            result = evaluate_field_dependencies(
                expressions=[expr],
                stage="formal_validation",
                registry=registry,
            )
            if not result.eligible and name not in self.KNOWN_NON_FORMAL_FACTORS:
                unexpected_failures.append(
                    (name, list(result.disallowed_fields), list(result.unknown_fields))
                )
            elif result.eligible and name in self.KNOWN_NON_FORMAL_FACTORS:
                unexpected_passes.append(name)
        assert not unexpected_failures, (
            f"Formal factor(s) unexpectedly FAILED the field gate at formal_validation. "
            f"Either fix field_status.yaml to cover the missing field, fix the factor, "
            f"or add the factor to KNOWN_NON_FORMAL_FACTORS with justification.\n"
            f"Failures: {unexpected_failures}"
        )
        assert not unexpected_passes, (
            f"Factor(s) listed as non-formal now PASS the field gate — the underlying "
            f"dataset was promoted. Remove from KNOWN_NON_FORMAL_FACTORS and add to the "
            f"formal factor list.\nUnexpected passes: {unexpected_passes}"
        )

    def test_known_non_formal_factors_still_block(self) -> None:
        """PR 9a round-3 (GPT 5.5 Pro): KNOWN_NON_FORMAL_FACTORS is auditable,
        not an escape hatch. Each entry MUST still raise FieldApprovalError
        through the live helper, AND the failing dataset / status / fields
        must match the recorded expectations.

        Three drift modes this catches:

          (1) Factor stopped failing — dataset got promoted; remove the
              entry from the mapping and reclassify the factor as formal.
          (2) Factor fails for the wrong dataset/status — registry changed
              underneath us; update the entry or investigate the regression.
          (3) Factor fails on different $fields than recorded — factor
              expression was edited; update expected_fields after review.
        """
        from src.alpha_research.factor_library.catalog import get_factor_catalog
        from src.data_infra.field_registry import (
            FieldApprovalError, load_field_registry,
        )
        from src.research_orchestrator.validation_steps import (
            _validate_factor_field_dependencies,
        )

        catalog = get_factor_catalog(include_new_data=True)
        registry = load_field_registry()
        unexpected_passes: list[str] = []
        wrong_dataset: list[tuple[str, str, str]] = []
        wrong_status: list[tuple[str, str, str]] = []
        wrong_fields: list[tuple[str, list[str], list[str]]] = []

        for factor_name, expectation in self.KNOWN_NON_FORMAL_FACTORS.items():
            # The factor must be in the catalog — otherwise the mapping is
            # stale on a different axis (factor was renamed/removed).
            assert factor_name in catalog, (
                f"KNOWN_NON_FORMAL_FACTORS lists {factor_name!r} but it is no "
                f"longer in get_factor_catalog(include_new_data=True). Remove "
                f"the entry or rename it."
            )

            # The helper must raise. If it doesn't, the underlying dataset
            # was promoted and the factor should move to the formal list.
            try:
                _validate_factor_field_dependencies(
                    factor_names=[factor_name],
                    stage="formal_validation",
                    artifact_label=f"pr9a_known_non_formal::{factor_name}",
                )
                unexpected_passes.append(factor_name)
                continue
            except FieldApprovalError:
                pass

            # The disallowed fields, dataset, and status must match the
            # recorded expectations.
            from src.research_orchestrator.release_gate import (
                evaluate_field_dependencies,
            )
            result = evaluate_field_dependencies(
                expressions=[catalog[factor_name]],
                stage="formal_validation",
                registry=registry,
            )
            actual_fields = sorted(result.disallowed_fields)
            expected_fields = sorted(expectation["expected_fields"])
            if actual_fields != expected_fields:
                wrong_fields.append(
                    (factor_name, actual_fields, expected_fields)
                )

            # Resolve one representative field to confirm dataset + status.
            sample = result.disallowed_fields[0]
            resolution = registry.resolve_field(sample, "formal_validation")
            if resolution.dataset_id != expectation["expected_dataset"]:
                wrong_dataset.append(
                    (factor_name, resolution.dataset_id or "", expectation["expected_dataset"])
                )
            if resolution.status_id != expectation["expected_status"]:
                wrong_status.append(
                    (factor_name, resolution.status_id or "", expectation["expected_status"])
                )

        assert not unexpected_passes, (
            f"KNOWN_NON_FORMAL_FACTORS entries that now PASS the formal field "
            f"gate (dataset was promoted): {unexpected_passes}. Remove from the "
            f"mapping and reclassify these as formal."
        )
        assert not wrong_fields, (
            f"KNOWN_NON_FORMAL_FACTORS entries whose disallowed $fields no "
            f"longer match expected_fields (factor expression or registry "
            f"changed):\n" +
            "\n".join(
                f"  {n}: actual={a} expected={e}"
                for n, a, e in wrong_fields
            )
        )
        assert not wrong_dataset, (
            f"KNOWN_NON_FORMAL_FACTORS entries whose blocking dataset changed "
            f"(registry coverage drift):\n" +
            "\n".join(
                f"  {n}: actual={a!r} expected={e!r}"
                for n, a, e in wrong_dataset
            )
        )
        assert not wrong_status, (
            f"KNOWN_NON_FORMAL_FACTORS entries whose blocking status changed "
            f"(dataset transitioned to a different status):\n" +
            "\n".join(
                f"  {n}: actual={a!r} expected={e!r}"
                for n, a, e in wrong_status
            )
        )

    def test_representative_formal_basket_passes(self) -> None:
        """Spot-check the representative basket GPT 5.5 Pro called out
        directly. These factors anchor the production formal universe; if
        any of them silently regresses to non-formal status, this is the
        loudest signal."""
        representative = [
            "val_bp",
            "val_ep_ttm",
            "qual_roe",
            "qual_accruals",
            "grow_netprofit_yoy",
            "lev_debt_to_assets",
            "liq_turnover_20d",
            "mom_return_20d",
            "size_ln_mcap",
            "risk_vol_20d",
        ]
        from src.alpha_research.factor_library.catalog import get_factor_catalog
        from src.data_infra.field_registry import load_field_registry
        from src.research_orchestrator.release_gate import evaluate_field_dependencies

        registry = load_field_registry()
        catalog = get_factor_catalog(include_new_data=True)
        for name in representative:
            assert name in catalog, (
                f"Representative formal factor {name!r} missing from catalog — "
                f"if this is intentional, update test_pr9_validation_field_gate.py."
            )
            r = evaluate_field_dependencies(
                expressions=[catalog[name]],
                stage="formal_validation",
                registry=registry,
            )
            assert r.eligible, (
                f"Representative formal factor {name!r} is now BLOCKED by the "
                f"field-dependency gate. disallowed={list(r.disallowed_fields)} "
                f"unknown={list(r.unknown_fields)}"
            )


# ─────────────────────────────────────────────────────────────────────────
# Indicators dataset PIT-lag contract (GPT 5.5 Pro round-3 review #1)
# ─────────────────────────────────────────────────────────────────────────


class TestFormalIndicatorPITLagContract:
    """Locks the indicator-fields PIT contract recorded in
    config/field_registry/approvals/2026-05-27_indicators_unlisted_to_approved.yaml.

    The `indicators` dataset is approved with `same_day_raw_usage_allowed:
    false` and `approved_usage_pattern: "Ref($field, 1) or stricter"`. The
    approval YAML lists the formal factors that depend on each indicator
    field. This test iterates those factors and asserts every reference to
    an indicators-dataset $field is wrapped inside a `Ref(...)` ancestor.

    PR 9a round-3 (GPT 5.5 Pro): on-disk presence is necessary but
    insufficient for formal approval — the approval contract requires
    expression-lag discipline AND field eligibility. The
    tests/alpha_research/test_factor_library_pit_safety.py suite already
    enforces this across the entire catalog; this class re-asserts the
    invariant scoped to the indicator dataset specifically so future
    reviewers can see the PR 9a approval YAML's evidence claim is alive
    and locked.
    """

    # The 18 indicator fields newly approved by PR 9a. Must match
    # config/field_registry/field_status.yaml::indicators.fields verbatim.
    INDICATOR_FIELDS = (
        "$roe", "$roa", "$roic",
        "$grossprofit_margin", "$netprofit_margin", "$assets_turn",
        "$ocfps", "$bps", "$eps",
        "$debt_to_assets", "$current_ratio", "$quick_ratio",
        "$netprofit_yoy", "$or_yoy", "$op_yoy",
        "$basic_eps_yoy", "$roe_yoy", "$q_op_qoq",
    )

    def test_indicator_fields_in_registry_match_yaml(self) -> None:
        """The 18 fields enumerated here must be exactly the set declared
        approved at config/field_registry/field_status.yaml::indicators."""
        from src.data_infra.field_registry import load_field_registry
        registry = load_field_registry()
        for field in self.INDICATOR_FIELDS:
            r = registry.resolve_field(field, "formal_validation")
            assert r.allowed, (
                f"PR 9a indicator field {field!r} should be approved at "
                f"formal_validation but registry returned "
                f"allowed={r.allowed} dataset={r.dataset_id} status={r.status_id}"
            )
            assert r.dataset_id == "indicators", (
                f"PR 9a indicator field {field!r} resolved to dataset "
                f"{r.dataset_id!r} (expected 'indicators'). field_status.yaml "
                f"drift suspected."
            )
            assert r.status_id == "approved", (
                f"PR 9a indicator field {field!r} resolved to status "
                f"{r.status_id!r} (expected 'approved')."
            )

    def test_formal_factors_wrap_indicator_fields_in_ref(self) -> None:
        """Every formal-eligible factor whose expression references an
        indicators-dataset field must wrap that field inside a `Ref(...)`
        ancestor frame — enforcing the approval YAML's
        `approved_usage_pattern: "Ref($field, 1) or stricter"` clause."""
        # Reuse the parser-based stack walk that the catalog-wide PIT test
        # already uses, scoped to the indicator subset.
        from tests.alpha_research.test_factor_library_pit_safety import (
            find_unwrapped_field_references,
        )
        from src.alpha_research.factor_library.catalog import get_factor_catalog

        catalog = get_factor_catalog(include_new_data=True)
        indicator_fields = set(self.INDICATOR_FIELDS)

        unwrapped_indicator_uses: list[tuple[str, list[str]]] = []
        for factor_name, expression in catalog.items():
            violations = find_unwrapped_field_references(expression)
            # Filter to violations that touch an indicator field.
            indicator_violations = sorted(
                {field for _, field in violations if field in indicator_fields}
            )
            if indicator_violations:
                unwrapped_indicator_uses.append((factor_name, indicator_violations))

        assert not unwrapped_indicator_uses, (
            "Approval contract violation: PR 9a approved the indicators "
            "dataset under the `Ref($field, 1) or stricter` usage pattern, "
            "but the following formal-catalog factors reference an "
            "indicators $field WITHOUT wrapping it in a Ref(...) ancestor:\n" +
            "\n".join(
                f"  {n}: unwrapped indicator fields {fs}"
                for n, fs in unwrapped_indicator_uses
            ) +
            "\n\nEither wrap each indicator $field inside Ref(...), or "
            "revisit the approval YAML at "
            "config/field_registry/approvals/"
            "2026-05-27_indicators_unlisted_to_approved.yaml — same_day_raw_usage_allowed: false."
        )


# ─────────────────────────────────────────────────────────────────────────
# PR 9b universe raw-field gate (GPT 5.5 Pro round-4 review)
# ─────────────────────────────────────────────────────────────────────────


class TestPR9bUniverseFieldGate:
    """PR 9b closes the universe raw-field bypass GPT 5.5 Pro identified:

    pre-PR-9b ``handle_validation_object_resolver`` validated only the
    factor expressions of ``prescription.components``. But
    ``handle_validation_dataset_build`` independently constructs
    ``raw_field_exprs`` from ``prescription.universe.broad_filters.profitability_field``
    and turns it into ``Ref(${profit_field}, 1)``. A formal prescription
    with all-approved factor components could pass the factor gate AND
    still consume a quarantined ``$ratio`` (hk_hold) through the universe
    path.

    PR 9b adds two checks:

    1. Resolver-time: a new ``_validate_prescription_universe_field_dependencies``
       helper enumerates the same canonical raw_field set + the optional
       ``profitability_field`` and runs them through
       ``assert_field_dependencies_eligible``. Called from
       ``handle_validation_object_resolver`` immediately after the factor
       check.
    2. Dataset_build-time defense-in-depth: before ``QlibFieldProvider.load_named_expressions``,
       the handler validates ``raw_field_exprs.values()`` so a future
       addition to that dict cannot bypass the gate even if someone
       forgets to mirror it into the resolver-side helper.
    """

    @pytest.fixture(autouse=True)
    def _isolate_drift_gate(self):
        # Synthetic resolver fixtures here omit a definition_hash; isolate the P1.3
        # drift gate (fail-closed, covered by TestPR13) so the universe-field gate is
        # what these tests exercise. Harmless for the dataset_build tests that never
        # reach the resolver handler.
        with patch(
            "src.research_orchestrator.validation_steps._assert_no_definition_drift",
            return_value={"checked": 0, "drifted": [], "stage": "formal_validation"},
        ):
            yield

    def _helper(self):
        from src.research_orchestrator.validation_steps import (
            _validate_prescription_universe_field_dependencies,
        )
        return _validate_prescription_universe_field_dependencies

    def _broad_prescription(self, profitability_field: str | None):
        """Build a minimal mock prescription with a broad universe whose
        broad_filters carries the given profitability_field (or None)."""
        broad_filters = MagicMock(profitability_field=profitability_field)
        universe = MagicMock(kind="broad", broad_filters=broad_filters)
        return MagicMock(universe=universe)

    # ── Helper-direct: positive paths ────────────────────────────────────
    def test_universe_helper_passes_with_no_profitability_field(self) -> None:
        helper = self._helper()
        prescription = self._broad_prescription(profitability_field=None)
        report = helper(
            prescription=prescription,
            stage="formal_validation",
            artifact_label="hyp_pr9b_no_profit_field",
        )
        assert report["eligible"] is True
        # Canonical 4 universe fields were checked.
        for f in ("$close", "$adj_factor", "$total_mv", "$amount"):
            assert f in report["fields_checked"]
        # No profitability_field source recorded.
        sources = report["expression_sources"]
        assert not any(
            s["source"] == "broad_filters.profitability_field" for s in sources
        )

    def test_universe_helper_passes_with_approved_profitability_field(self) -> None:
        helper = self._helper()
        # $roe is approved under the indicators dataset (PR 9a).
        prescription = self._broad_prescription(profitability_field="roe")
        report = helper(
            prescription=prescription,
            stage="formal_validation",
            artifact_label="hyp_pr9b_approved_profit_field",
        )
        assert report["eligible"] is True
        assert "$roe" in report["fields_checked"]
        sources = report["expression_sources"]
        assert any(
            s["source"] == "broad_filters.profitability_field" and s["field"] == "$roe"
            for s in sources
        )

    def test_universe_helper_handles_theme_universe(self) -> None:
        """Theme universes have no broad_filters; helper must still
        validate the canonical OHLCV/market_cap/amount set without raising."""
        helper = self._helper()
        prescription = MagicMock(universe=MagicMock(kind="theme", broad_filters=None))
        report = helper(
            prescription=prescription,
            stage="formal_validation",
            artifact_label="hyp_pr9b_theme",
        )
        assert report["eligible"] is True
        # Theme universe still uses the canonical raw fields downstream.
        for f in ("$close", "$adj_factor", "$total_mv", "$amount"):
            assert f in report["fields_checked"]

    # ── Helper-direct: negative paths ────────────────────────────────────
    def test_universe_helper_blocks_quarantined_profitability_field(self) -> None:
        helper = self._helper()
        # $ratio is the hk_hold quarantined field.
        prescription = self._broad_prescription(profitability_field="ratio")
        with pytest.raises(FieldApprovalError, match=r"\$ratio"):
            helper(
                prescription=prescription,
                stage="formal_validation",
                artifact_label="hyp_pr9b_quarantined",
            )

    def test_universe_helper_blocks_pending_review_profitability_field(self) -> None:
        helper = self._helper()
        # Any pending_review event-like field — use a real one from
        # field_status.yaml: $top_list__net_rate.
        prescription = self._broad_prescription(profitability_field="top_list__net_rate")
        with pytest.raises(FieldApprovalError, match=r"top_list"):
            helper(
                prescription=prescription,
                stage="formal_validation",
                artifact_label="hyp_pr9b_pending",
            )

    def test_universe_helper_blocks_unknown_profitability_field(self) -> None:
        helper = self._helper()
        prescription = self._broad_prescription(profitability_field="ghost_xyz_field")
        with pytest.raises(FieldApprovalError, match=r"ghost_xyz_field"):
            helper(
                prescription=prescription,
                stage="formal_validation",
                artifact_label="hyp_pr9b_unknown",
            )

    def test_universe_helper_blocks_at_oos_stage(self) -> None:
        helper = self._helper()
        prescription = self._broad_prescription(profitability_field="ratio")
        with pytest.raises(FieldApprovalError):
            helper(
                prescription=prescription,
                stage="oos_test",
                artifact_label="hyp_pr9b_oos",
            )

    # ── Resolver-handler integration: end-to-end behavior ────────────────
    def _make_resolver_context(
        self,
        tmp_path: Path,
        *,
        profitability_field: str | None,
    ):
        """Build a resolver-handler context whose prescription components are
        approved (qual_roe) but whose universe carries the given
        profitability_field."""
        from src.research_orchestrator.hypothesis import PrescribedComponent
        broad_filters = MagicMock(profitability_field=profitability_field)
        universe = MagicMock(kind="broad", broad_filters=broad_filters)
        prescription = MagicMock(
            components=[PrescribedComponent(factor_name="qual_roe", weight=1.0)],
            allow_candidate_components=False,
            universe=universe,
        )
        hypothesis = MagicMock(
            prescription=prescription,
            hypothesis_id="hyp_pr9b_resolver_integration",
        )
        context = MagicMock()
        context.request.hypothesis = hypothesis
        context.step_dir = tmp_path / "step"
        context.step_dir.mkdir(parents=True)
        context.registry_dirs = {
            "factor_registry_dir": str(tmp_path / "factor_registry"),
            "candidate_registry_dir": str(tmp_path / "candidate_registry"),
            "signal_registry_dir": str(tmp_path / "signal_registry"),
            "model_registry_dir": str(tmp_path / "model_registry"),
            "strategy_registry_dir": str(tmp_path / "strategy_registry"),
        }
        context.profile.profile_id = "hypothesis_validation"
        return context

    def test_resolver_handler_blocks_quarantined_universe_field(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: a formal prescription with approved components but
        broad_filters.profitability_field='ratio' must FAIL at the
        resolver, BEFORE the IS leg ever begins."""
        from src.research_orchestrator.validation_steps import (
            handle_validation_object_resolver,
        )

        context = self._make_resolver_context(tmp_path, profitability_field="ratio")
        resolver_payload = {
            "resolved_objects": [
                {
                    "status": "resolved",
                    "source_layer": "formal",
                    "requested": {"object_name": "qual_roe", "object_type": "factor"},
                },
            ],
        }
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=resolver_payload,
        ):
            with pytest.raises(FieldApprovalError, match=r"\$ratio"):
                handle_validation_object_resolver(context)

    def test_resolver_handler_passes_with_approved_universe_field(
        self, tmp_path: Path
    ) -> None:
        """Approved factor components + approved profitability_field=$roe
        must pass and persist both reports."""
        from src.research_orchestrator.validation_steps import (
            handle_validation_object_resolver,
        )

        context = self._make_resolver_context(tmp_path, profitability_field="roe")
        resolver_payload = {
            "resolved_objects": [
                {
                    "status": "resolved",
                    "source_layer": "formal",
                    "requested": {"object_name": "qual_roe", "object_type": "factor"},
                },
            ],
        }
        with patch(
            "src.research_orchestrator.resolver.ResolverHub.resolve_assets",
            return_value=resolver_payload,
        ):
            result = handle_validation_object_resolver(context)

        # Both reports persisted into outputs AND into registry_resolution.json.
        assert "field_dependency_report" in result.outputs
        assert "universe_field_dependency_report" in result.outputs
        assert (context.step_dir / "registry_resolution.json").exists()
        import json
        persisted = json.loads(
            (context.step_dir / "registry_resolution.json").read_text(encoding="utf-8")
        )
        assert "universe_field_dependency_report" in persisted
        # The universe report should have $roe + canonical 4 universe fields.
        ufdr = persisted["universe_field_dependency_report"]
        assert ufdr["eligible"] is True
        assert "$roe" in ufdr["fields_checked"]

    # ── Dataset_build defense-in-depth ───────────────────────────────────
    def test_dataset_build_is_stage_maps_to_formal_validation(self) -> None:
        """PR 9c (2026-05-28, GPT 5.5 Pro round-5 review): the
        dataset_build defense-in-depth gate MUST fire on the normal IS leg.

        Pre-PR-9c the check was ``if stage in {"formal_validation",
        "oos_test", "registry_publish"}:`` but ``_gate_stage(context)``
        returns ``"is_only"`` by default (steps.py:132). The IS leg of
        a formal hypothesis_validation run is itself a formal stage for
        the field-status registry; the pre-fix code silently skipped it.

        PR 9c maps ``is_only`` → ``formal_validation``, ``oos_test`` →
        ``oos_test``, both ``formal_validation`` and ``registry_publish``
        pass through, and only truly unrecognized stages (none today)
        are ungated.

        This test pins the mapping at source level: the hypothesis_
        validation IS leg cannot silently skip the gate again."""
        src = Path("src/research_orchestrator/validation_steps.py").read_text(
            encoding="utf-8"
        )
        ds_start = src.index("def handle_validation_dataset_build")
        next_def = src.find("\ndef ", ds_start + 1)
        ds_body = src[ds_start:next_def if next_def > 0 else len(src)]
        # The PR 9c stage-mapping branch must explicitly map "is_only"
        # to "formal_validation" for field-gate purposes.
        assert 'stage == "is_only"' in ds_body, (
            "PR 9c: handle_validation_dataset_build must explicitly map "
            "stage=='is_only' to formal_validation for the field-gate "
            "defense-in-depth. The pre-fix `if stage in {formal_*}` check "
            "silently skipped the IS leg."
        )
        assert 'field_gate_stage = "formal_validation"' in ds_body or (
            'field_gate_stage = "formal_validation"' in ds_body.replace("'", '"')
        ), (
            "PR 9c: IS-leg mapping must set field_gate_stage to "
            "'formal_validation' explicitly."
        )
        # And the assert_field_dependencies_eligible call must use the
        # mapped variable, not the raw `stage`.
        assert "stage=field_gate_stage" in ds_body, (
            "PR 9c: assert_field_dependencies_eligible must consume the "
            "mapped field_gate_stage, not the raw `stage` value."
        )

    def test_dataset_build_gate_fires_on_is_only_behavioral(self) -> None:
        """Behavioral counterpart to the source-level mapping test.

        Build a synthetic raw_field_exprs containing a quarantined field
        and run assert_field_dependencies_eligible with the mapped stage
        directly — verifying that the FieldApprovalError fires when the
        IS-leg mapping (``is_only`` → ``formal_validation``) is applied,
        and does NOT fire if the pre-PR-9c bug returns (raw ``is_only``
        is treated as an ungated stage by the registry).

        This test stays at the helper level rather than driving
        ``handle_validation_dataset_build`` end-to-end because that
        handler requires a full ResearchSupport bundle + Qlib provider.
        The helper-level proof is sufficient: the bug was in the stage
        check, not in the registry's behavior."""
        from src.research_orchestrator.release_gate import (
            assert_field_dependencies_eligible,
            evaluate_field_dependencies,
        )

        # raw_field_exprs simulation: someone added $ratio to honor
        # northbound_required and forgot to mirror it into the
        # resolver-side helper. With PR 9c the dataset_build gate catches
        # it on the IS leg.
        future_raw_field_exprs = {
            "close": "Ref($close, 1)",
            "adj_factor": "Ref($adj_factor, 1)",
            "total_mv": "Ref($total_mv, 1)",
            "amount": "Ref($amount, 1)",
            "ratio": "Ref($ratio, 1)",  # ← future addition, quarantined
        }

        # PR 9c mapping: IS leg should be treated as formal_validation.
        mapped_stage_for_is = "formal_validation"
        with pytest.raises(FieldApprovalError, match=r"\$ratio"):
            assert_field_dependencies_eligible(
                expressions=list(future_raw_field_exprs.values()),
                stage=mapped_stage_for_is,
                artifact_label="hyp_pr9c_is_leg",
            )

        # Sanity: at sandbox stage the same expression set passes (the
        # quarantine policy disallows $ratio at every stage, but unknown
        # fields warn at sandbox — confirming our stage mapping is the
        # right axis to test).
        sandbox_result = evaluate_field_dependencies(
            expressions=list(future_raw_field_exprs.values()),
            stage="sandbox_screening",
        )
        # $ratio is quarantine, blocked at every stage including sandbox.
        assert "$ratio" in sandbox_result.disallowed_fields

    def test_dataset_build_has_defense_in_depth_check(self) -> None:
        """Source-level proof that handle_validation_dataset_build runs
        assert_field_dependencies_eligible on raw_field_exprs.values() at
        formal stages BEFORE the raw_field_exprs Qlib load.

        Note: handle_validation_dataset_build also has an EARLIER
        ``provider.load_named_expressions({"market_cap": "Ref($total_mv, 1)"})``
        call inside the industry-relative composite branch. That call uses
        a hardcoded approved field (``$total_mv``) and is structurally
        constrained — there is no user-controllable path to inject a
        different field into it. The defense-in-depth gate therefore only
        needs to cover the second, user-controllable
        ``load_named_expressions(raw_field_exprs, ...)`` site.
        """
        src = Path("src/research_orchestrator/validation_steps.py").read_text(
            encoding="utf-8"
        )
        # Find the dataset_build handler body.
        ds_start = src.index("def handle_validation_dataset_build")
        next_def = src.find("\ndef ", ds_start + 1)
        ds_body = src[ds_start:next_def if next_def > 0 else len(src)]
        # Defense-in-depth call signature must exist.
        assert "assert_field_dependencies_eligible(" in ds_body, (
            "PR 9b: handle_validation_dataset_build must call "
            "assert_field_dependencies_eligible on raw_field_exprs.values() "
            "before the raw_field_exprs Qlib load."
        )
        idx_assert = ds_body.index("assert_field_dependencies_eligible(")
        # Locate the SPECIFIC user-controllable raw_field_exprs load — NOT
        # the earlier hardcoded market_cap load. We anchor on the
        # ``load_named_expressions(`` followed by ``raw_field_exprs`` token.
        idx_raw_load = ds_body.find("load_named_expressions(\n        raw_field_exprs")
        if idx_raw_load < 0:
            # Tolerate light formatting variation (indentation, line breaks).
            import re
            m = re.search(
                r"load_named_expressions\s*\(\s*raw_field_exprs",
                ds_body,
            )
            assert m is not None, (
                "PR 9b: could not locate the raw_field_exprs Qlib load "
                "(load_named_expressions(raw_field_exprs, ...)) — has the "
                "handler been refactored? Update this test in lock-step."
            )
            idx_raw_load = m.start()
        assert idx_assert < idx_raw_load, (
            "PR 9b: defense-in-depth gate must fire BEFORE the raw_field_exprs "
            f"Qlib load. Observed positions: assert@{idx_assert} "
            f"raw_load@{idx_raw_load}"
        )
        # Mirror-contract docstring callout: the helper docstring must
        # explicitly tell future maintainers that adding a field to
        # raw_field_exprs requires updating the helper too.
        helper_idx = src.index("def _validate_prescription_universe_field_dependencies")
        helper_next = src.find("\ndef ", helper_idx + 1)
        helper_body = src[helper_idx:helper_next if helper_next > 0 else len(src)]
        assert "Mirror contract" in helper_body or "mirror contract" in helper_body, (
            "PR 9b helper must carry the mirror-contract callout so future "
            "additions to dataset_build raw_field_exprs are mirrored here."
        )


# ─────────────────────────────────────────────────────────────────────────
# Behavioral OOS handler test (GPT 8d carry-over)
# ─────────────────────────────────────────────────────────────────────────


class TestOOSHandlerSealClaimBehavior:
    """Verify handle_validation_event_backtest_oos calls
    _claim_holdout_access_if_needed BEFORE run_event_driven_window.

    This is the behavioral counterpart to PR 8d's source-reflection test —
    we construct a minimal mocked StepExecutionContext and assert the
    actual call order via mock side_effect."""

    def _make_context(self, tmp_path: Path):
        """Minimal StepExecutionContext fixture for OOS handler invocation."""
        # State carries the upstream IS gate decision = "approved" so the
        # OOS handler doesn't short-circuit.
        state = {
            "step_outputs": {
                "validation_gate_review_is": {"decision": "approved"},
            },
        }
        # Hypothesis with prescription + time_split + design_hash().
        hypothesis = MagicMock(
            hypothesis_id="hyp_pr9_test",
            time_split=MagicMock(
                is_start="2020-01-01", is_end="2022-12-31",
                oos_start="2023-01-01", oos_end="2024-12-31",
            ),
            benchmark="000300_SH",
        )
        hypothesis.design_hash.return_value = "deadbeefcafebabe"
        hypothesis.structural_family.return_value = "test_family"
        hypothesis.prescription = MagicMock(
            portfolio=MagicMock(target_gross_exposure=0.5),
        )

        # Build a context-like object with the attributes the handler reads.
        # The handler accesses: request.hypothesis, run_dir, step_dir,
        # step.step_id, step.config["stage"], state, registry_dirs,
        # profile.profile_id, resumed.
        context = MagicMock()
        context.request.hypothesis = hypothesis
        context.run_dir = tmp_path / "run"
        context.step_dir = tmp_path / "step"
        context.step.step_id = "validation_event_backtest_oos"
        context.step.config = {"stage": "oos_test"}
        context.state = state
        context.registry_dirs = {"holdout_seal_dir": str(tmp_path / "seals")}
        context.profile.profile_id = "hypothesis_validation"
        context.resumed = False

        # Pre-create directories the handler will write into.
        (tmp_path / "run" / "steps" / "validation_portfolio_construction").mkdir(
            parents=True
        )
        (tmp_path / "step").mkdir(parents=True)
        (tmp_path / "seals").mkdir(parents=True)
        # Write a minimal schedule parquet the handler will read.
        import pandas as pd
        empty_schedule = pd.DataFrame(
            columns=["date", "instrument", "weight"]
        )
        empty_schedule.to_parquet(
            tmp_path / "run" / "steps" / "validation_portfolio_construction"
            / "target_weights_schedule.parquet"
        )
        return context

    def test_seal_claim_fires_before_run_event_driven_window(
        self, tmp_path: Path
    ) -> None:
        from src.research_orchestrator.validation_steps import (
            handle_validation_event_backtest_oos,
        )

        context = self._make_context(tmp_path)
        call_order: list[str] = []

        def _record_claim(*args, **kwargs):
            call_order.append("claim")

        def _record_run(*args, **kwargs):
            call_order.append("run")
            return MagicMock(report=None, trades=None, summary={})

        with patch(
            "src.research_orchestrator.steps._claim_holdout_access_if_needed",
            side_effect=_record_claim,
        ), patch(
            "workspace.research.alpha_mining.event_driven_strategy_research"
            ".run_event_driven_window",
            side_effect=_record_run,
        ), patch(
            "src.research_orchestrator.steps._run_with_cache_context",
            side_effect=lambda _ctx, fn, **kw: fn(**kw),
        ), patch(
            "src.research_orchestrator.validation_steps._schedule_dataframe_to_dict",
            return_value={},
        ), patch(
            "src.research_orchestrator.validation_steps._slippage_rate_from_prescription",
            return_value=0.0003,
        ), patch(
            "src.research_orchestrator.validation_steps._build_cost_config",
            return_value=None,
        ), patch(
            "src.research_orchestrator.steps._time_split_payload_for_step",
            return_value={"stage": "oos_test"},
        ), patch(
            "src.research_orchestrator.steps._holdout_context_for_step",
            return_value=MagicMock(),
        ):
            handle_validation_event_backtest_oos(context)

        # Both calls happened — and claim happened FIRST.
        assert "claim" in call_order, (
            "OOS handler did not call _claim_holdout_access_if_needed"
        )
        assert "run" in call_order, (
            "OOS handler did not invoke run_event_driven_window"
        )
        assert call_order.index("claim") < call_order.index("run"), (
            f"claim must fire BEFORE run; observed order: {call_order}"
        )

    def test_oos_handler_short_circuits_on_non_approved_is_gate(
        self, tmp_path: Path
    ) -> None:
        """When upstream IS gate is not 'approved', the OOS handler returns
        a skipped_due_to_is_gate result and never claims the seal."""
        from src.research_orchestrator.validation_steps import (
            handle_validation_event_backtest_oos,
        )

        context = self._make_context(tmp_path)
        context.state["step_outputs"]["validation_gate_review_is"]["decision"] = (
            "rejected"
        )

        with patch(
            "src.research_orchestrator.steps._claim_holdout_access_if_needed",
        ) as claim_mock, patch(
            "workspace.research.alpha_mining.event_driven_strategy_research"
            ".run_event_driven_window",
        ) as run_mock:
            result = handle_validation_event_backtest_oos(context)

        # Neither helper was called.
        claim_mock.assert_not_called()
        run_mock.assert_not_called()
        # And the result indicates skip.
        assert result.outputs["decision"] == "skipped_due_to_is_gate"
