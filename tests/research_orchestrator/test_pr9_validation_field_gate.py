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
