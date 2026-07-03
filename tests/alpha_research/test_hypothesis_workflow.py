from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import src.research_orchestrator.event_signal_steps as event_signal_steps
import src.research_orchestrator.ml_signal_steps as ml_steps
import src.research_orchestrator.steps as orch_steps
import src.research_orchestrator.strategy_improvement_steps as improvement_steps
import workspace.scripts.hypothesis_cli as hypothesis_cli
from src.alpha_research.testing_ledger import TestingLedgerStore
from src.alpha_research.walk_forward import TimeSplit
from src.backtest_engine.event_driven import EventDrivenBacktester
from src.research_orchestrator.dag import (
    CompiledResearchDag,
    DagStepSpec,
    PauseForInputPayload,
    StepExecutionContext,
)
from src.research_orchestrator.engine import (
    _canonical_request_payload,
    _validate_request_against_profile,
    profile_registry,
)
from src.research_orchestrator.gate_report import ConcernEnforcementError, derive_severity
from src.research_orchestrator.holdout_seal import HoldoutSealStore
from src.research_orchestrator.hypothesis import (
    FLOOR_DIRECTIONS,
    ExpectedEffect,
    Hypothesis,
    HypothesisSource,
    LaxCriteriaError,
    PreRegisteredConcerns,
    SuccessCriteria,
)
from src.research_orchestrator.qlib_windowed_features import _deterministic_cache_path
from src.research_orchestrator.runtime import reconstruct_state_from_completed_steps, write_json
from src.research_orchestrator.schema import AssetRef, ResearchRequest
from src.research_orchestrator.steps import _find_predecessor_step_id, _load_concern_scores_from_outputs
from src.research_orchestrator.window_enforcement import enforce_is_window_if_hypothesis
from src.alpha_research.hypothesis_registry import HypothesisRegistryStore
from workspace.research.alpha_mining.audit_benchmark_index import BenchmarkAuditResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"


def build_hypothesis(
    *,
    mechanism: str = "Investor attention under-reacts and lets a ranking signal persist.",
    thesis_statement: str = "A stable cross-sectional factor should predict future returns.",
    universe: str = "csi_all",
    factor_refs: list[AssetRef] | None = None,
    success_criteria: SuccessCriteria | None = None,
) -> Hypothesis:
    return Hypothesis(
        hypothesis_id="hyp_test_001",
        thesis_statement=thesis_statement,
        mechanism=mechanism,
        source=HypothesisSource(
            source_type="academic_paper",
            identifier="unit-test-paper",
            title="Unit Test Hypothesis",
        ),
        factor_refs=factor_refs or [
            AssetRef(object_type="factor", object_name="factor_a"),
            AssetRef(object_type="factor", object_name="factor_b"),
        ],
        factor_yaml_hashes=[],
        universe=universe,
        benchmark="000905.SH",
        time_split=TimeSplit(
            is_start="2018-01-01",
            is_end="2022-12-31",
            oos_start="2023-01-01",
            oos_end="2024-12-31",
            walk_forward_config={"train_years": 3, "validation_years": 1, "test_years": 1, "step_years": 1},
        ),
        rebalance_frequency="5d",
        neutralization=["size", "industry"],
        expected_sign=1,
        expected_effect=ExpectedEffect(
            statistic="rank_ic",
            point_estimate=0.04,
            ci_low=0.02,
            ci_high=0.06,
            horizon_days=5,
        ),
        expected_decay_horizon_days=5,
        success_criteria=success_criteria
        or SuccessCriteria(
            min_rank_icir=0.04,
            min_deflated_sharpe=1.1,
            min_cost_adjusted_sharpe=0.8,
            max_drawdown=0.25,
            max_annual_turnover=4.0,
            min_monotonicity_pvalue=0.05,
            max_correlation_to_approved=0.7,
            min_regime_pass_count=2,
            effect_size_must_be_in_ci=True,
            custom_rules=[],
        ),
        pre_registered_concerns=PreRegisteredConcerns(
            most_likely_failure_mode="The signal may be regime-specific.",
            weakest_assumption="Behavioral under-reaction remains stable.",
            what_would_falsify_this="Formal IS and OOS hard rules fail.",
            priors_on_cost_sensitivity="Costs matter once turnover rises materially.",
        ),
        pre_registered_at="2026-04-12 09:00:00",
        registered_by="unit_test",
    )


def build_request(hypothesis: Hypothesis | None) -> ResearchRequest:
    return ResearchRequest(
        profile_id="factor_screening",
        mode="formal",
        consumes=[],
        produces=[],
        requested_capabilities=[],
        inputs={
            "argv": [],
            "args": {},
            "output_dir": str((WORKSPACE_OUTPUTS / "hypothesis_workflow_request").resolve()),
        },
        run_context={},
        hypothesis=hypothesis,
    )


class HypothesisWorkflowTests(unittest.TestCase):
    @contextmanager
    def make_temp_dir(self, prefix: str):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        temp_root = WORKSPACE_OUTPUTS / f"{prefix}_{uuid.uuid4().hex[:8]}"
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        try:
            yield str(temp_root)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def _build_context(
        self,
        *,
        run_dir: Path,
        step: DagStepSpec,
        inputs: dict | None = None,
        hypothesis: Hypothesis | None = None,
        state: dict | None = None,
        steps: tuple[DagStepSpec, ...] | None = None,
        profile_id: str = "factor_screening",
        registry_dirs: dict[str, Path] | None = None,
        resumed: bool = False,
    ) -> StepExecutionContext:
        dag_steps = steps or (step,)
        dag = CompiledResearchDag(profile_id=profile_id, run_dir=str(run_dir), steps=dag_steps)
        return StepExecutionContext(
            request=SimpleNamespace(inputs=inputs or {}, hypothesis=hypothesis),
            profile=SimpleNamespace(profile_id=profile_id),
            dag=dag,
            step=step,
            run_dir=run_dir,
            step_dir=run_dir / "steps" / step.step_id,
            registry_dirs=registry_dirs or {},
            effective_capabilities=[],
            effective_capability_metadata=[],
            state=state or {},
            resumed=resumed,
        )

    def test_design_hash_ignores_factor_ref_order(self):
        first = build_hypothesis(
            factor_refs=[
                AssetRef(object_type="factor", object_name="factor_a"),
                AssetRef(object_type="factor", object_name="factor_b"),
            ]
        )
        second = build_hypothesis(
            factor_refs=[
                AssetRef(object_type="factor", object_name="factor_b"),
                AssetRef(object_type="factor", object_name="factor_a"),
            ]
        )
        self.assertEqual(first.design_hash(), second.design_hash())

    def test_design_hash_changes_when_universe_changes(self):
        first = build_hypothesis(universe="csi_all")
        second = build_hypothesis(universe="csi_800")
        self.assertNotEqual(first.design_hash(), second.design_hash())

    def test_economic_family_is_stable_under_mechanism_rewording(self):
        first = build_hypothesis(mechanism="Investors under-react to earnings information.")
        second = build_hypothesis(mechanism="The same economics are described with different wording only.")
        self.assertEqual(first.economic_family(), second.economic_family())
        self.assertNotEqual(first.prose_hash(), second.prose_hash())

    def test_economic_family_stays_stable_under_universe_swap(self):
        first = build_hypothesis(universe="csi_all")
        second = build_hypothesis(universe="csi_800")
        self.assertEqual(first.economic_family(), second.economic_family())

    def test_canonical_request_payload_excludes_prose(self):
        first = build_request(build_hypothesis(mechanism="Version one prose.", thesis_statement="First wording."))
        second = build_request(build_hypothesis(mechanism="Version two prose.", thesis_statement="Second wording."))
        self.assertEqual(_canonical_request_payload(first), _canonical_request_payload(second))

    def test_time_split_from_dict_drops_legacy_stage(self):
        split = TimeSplit.from_dict(
            {
                "is_start": "2018-01-01",
                "is_end": "2022-12-31",
                "oos_start": "2023-01-01",
                "oos_end": "2024-12-31",
                "stage": "oos_test",
                "walk_forward_config": {"train_years": 3},
            }
        )
        self.assertFalse(hasattr(split, "stage"))
        self.assertNotIn("stage", split.to_dict())

    def test_time_split_rejects_overlapping_is_oos(self):
        with self.assertRaises(ValueError):
            TimeSplit(
                is_start="2018-01-01",
                is_end="2022-12-31",
                oos_start="2022-12-01",
                oos_end="2024-12-31",
                walk_forward_config={},
            )

    def test_time_split_rejects_reversed_dates(self):
        with self.assertRaises(ValueError):
            TimeSplit(
                is_start="2022-01-01",
                is_end="2021-12-31",
                oos_start="2023-01-01",
                oos_end="2024-12-31",
                walk_forward_config={},
            )

    def test_formal_profile_requires_hypothesis(self):
        with self.assertRaises(ValueError):
            request = build_request(None)
            profile = profile_registry().get("factor_screening")
            _validate_request_against_profile(request, profile)

    def test_floor_rail_override_is_durable_via_registry_event(self):
        loose = build_hypothesis(
            success_criteria=SuccessCriteria(
                min_rank_icir=0.001,
                min_deflated_sharpe=0.1,
                min_cost_adjusted_sharpe=0.1,
                max_drawdown=0.9,
                max_annual_turnover=20.0,
                min_monotonicity_pvalue=0.9,
                max_correlation_to_approved=0.99,
                min_regime_pass_count=0,
                effect_size_must_be_in_ci=False,
                custom_rules=[],
            )
        )
        request = build_request(loose)
        profile = profile_registry().get("factor_screening")
        with self.make_temp_dir("hyp_registry") as temp_dir:
            registry_dir = Path(temp_dir) / "hypothesis_registry"
            request.run_context["hypothesis_registry_dir"] = str(registry_dir)
            with self.assertRaises(LaxCriteriaError):
                _validate_request_against_profile(request, profile)
            store = HypothesisRegistryStore(registry_dir)
            store.register(loose)
            store.record_manual_override(
                hypothesis_id=loose.hypothesis_id,
                design_hash=loose.design_hash(),
                override_reason="floor_rails_relaxed: unit test override",
                override_by="unit_test",
            )
            _validate_request_against_profile(request, profile)

    def test_lax_criteria_raise_explicitly(self):
        loose = build_hypothesis(
            success_criteria=SuccessCriteria(
                min_rank_icir=0.001,
                min_deflated_sharpe=0.1,
                min_cost_adjusted_sharpe=0.1,
                max_drawdown=0.9,
                max_annual_turnover=20.0,
                min_monotonicity_pvalue=0.9,
                max_correlation_to_approved=0.99,
                min_regime_pass_count=0,
                effect_size_must_be_in_ci=False,
                custom_rules=[],
            )
        )
        with self.assertRaises(LaxCriteriaError):
            _validate_request_against_profile(build_request(loose), profile_registry().get("factor_screening"))

    def test_min_monotonicity_pvalue_uses_at_most_floor_direction(self):
        self.assertEqual(FLOOR_DIRECTIONS["min_monotonicity_pvalue"], "at_most")
        strict = build_hypothesis(
            success_criteria=SuccessCriteria(
                min_rank_icir=0.04,
                min_deflated_sharpe=1.1,
                min_cost_adjusted_sharpe=0.8,
                max_drawdown=0.25,
                max_annual_turnover=4.0,
                min_monotonicity_pvalue=0.01,
                max_correlation_to_approved=0.7,
                min_regime_pass_count=2,
                effect_size_must_be_in_ci=True,
                custom_rules=[],
            )
        )
        _validate_request_against_profile(build_request(strict), profile_registry().get("factor_screening"))
        loose = build_hypothesis(
            success_criteria=SuccessCriteria(
                min_rank_icir=0.04,
                min_deflated_sharpe=1.1,
                min_cost_adjusted_sharpe=0.8,
                max_drawdown=0.25,
                max_annual_turnover=4.0,
                min_monotonicity_pvalue=0.20,
                max_correlation_to_approved=0.7,
                min_regime_pass_count=2,
                effect_size_must_be_in_ci=True,
                custom_rules=[],
            )
        )
        with self.assertRaises(LaxCriteriaError):
            _validate_request_against_profile(build_request(loose), profile_registry().get("factor_screening"))

    def test_find_predecessor_by_capability_single_stage(self):
        dag = CompiledResearchDag(
            profile_id="test",
            run_dir=str((WORKSPACE_OUTPUTS / "pred_single").resolve()),
            steps=(
                DagStepSpec(step_id="gate_evaluation", capability="gate_evaluation", handler="gate_evaluation"),
                DagStepSpec(
                    step_id="gate_concern_scoring",
                    capability="gate_concern_scoring",
                    handler="gate_concern_scoring",
                    depends_on=("gate_evaluation",),
                ),
                DagStepSpec(
                    step_id="gate_review",
                    capability="gate_review",
                    handler="gate_review",
                    depends_on=("gate_evaluation", "gate_concern_scoring"),
                ),
            ),
        )
        context = StepExecutionContext(
            request=None,
            profile=None,
            dag=dag,
            step=dag.steps[-1],
            run_dir=Path(dag.run_dir),
            step_dir=Path(dag.run_dir) / "steps" / "gate_review",
            registry_dirs={},
            effective_capabilities=[],
            effective_capability_metadata=[],
            state={},
            resumed=False,
        )
        self.assertEqual(_find_predecessor_step_id(context, "gate_evaluation"), "gate_evaluation")
        self.assertEqual(_find_predecessor_step_id(context, "gate_concern_scoring"), "gate_concern_scoring")

    def test_find_predecessor_by_capability_multi_stage(self):
        dag = CompiledResearchDag(
            profile_id="test",
            run_dir=str((WORKSPACE_OUTPUTS / "pred_multi").resolve()),
            steps=(
                DagStepSpec(step_id="gate_evaluation_is", capability="gate_evaluation", handler="gate_evaluation"),
                DagStepSpec(
                    step_id="gate_concern_scoring_is",
                    capability="gate_concern_scoring",
                    handler="gate_concern_scoring",
                    depends_on=("gate_evaluation_is",),
                ),
                DagStepSpec(step_id="oos_backtest", capability="event_driven_backtest", handler="event_backtest"),
                DagStepSpec(
                    step_id="gate_evaluation_oos",
                    capability="gate_evaluation",
                    handler="gate_evaluation",
                    depends_on=("oos_backtest",),
                ),
                DagStepSpec(
                    step_id="gate_concern_scoring_oos",
                    capability="gate_concern_scoring",
                    handler="gate_concern_scoring",
                    depends_on=("gate_evaluation_oos",),
                ),
                DagStepSpec(
                    step_id="gate_review_oos",
                    capability="gate_review",
                    handler="gate_review",
                    depends_on=("gate_evaluation_oos", "gate_concern_scoring_oos"),
                ),
            ),
        )
        context = StepExecutionContext(
            request=None,
            profile=None,
            dag=dag,
            step=dag.steps[-1],
            run_dir=Path(dag.run_dir),
            step_dir=Path(dag.run_dir) / "steps" / "gate_review_oos",
            registry_dirs={},
            effective_capabilities=[],
            effective_capability_metadata=[],
            state={},
            resumed=False,
        )
        self.assertEqual(_find_predecessor_step_id(context, "gate_evaluation"), "gate_evaluation_oos")
        self.assertEqual(_find_predecessor_step_id(context, "gate_concern_scoring"), "gate_concern_scoring_oos")

    def test_find_predecessor_raises_on_ambiguous_match(self):
        dag = CompiledResearchDag(
            profile_id="test",
            run_dir=str((WORKSPACE_OUTPUTS / "pred_ambiguous").resolve()),
            steps=(
                DagStepSpec(step_id="gate_evaluation_is", capability="gate_evaluation", handler="gate_evaluation"),
                DagStepSpec(step_id="gate_evaluation_shadow", capability="gate_evaluation", handler="gate_evaluation"),
                DagStepSpec(
                    step_id="gate_review",
                    capability="gate_review",
                    handler="gate_review",
                    depends_on=("gate_evaluation_is", "gate_evaluation_shadow"),
                ),
            ),
        )
        context = StepExecutionContext(
            request=None,
            profile=None,
            dag=dag,
            step=dag.steps[-1],
            run_dir=Path(dag.run_dir),
            step_dir=Path(dag.run_dir) / "steps" / "gate_review",
            registry_dirs={},
            effective_capabilities=[],
            effective_capability_metadata=[],
            state={},
            resumed=False,
        )
        with self.assertRaises(ValueError):
            _find_predecessor_step_id(context, "gate_evaluation")

    def test_holdout_seal_blocks_second_oos_touch_same_design_hash(self):
        with self.make_temp_dir("holdout_seal") as temp_dir:
            store = HoldoutSealStore(Path(temp_dir) / "holdout")
            store.claim_holdout_access(
                design_hash="a" * 64,
                hypothesis_id="hyp_test_001",
                structural_family="family_a",
                profile_id="event_driven_signal_research",
                run_dir=str(Path(temp_dir) / "run_a"),
                step_id="oos_backtest",
                stage="oos_test",
            )
            with self.assertRaises(ValueError):
                store.claim_holdout_access(
                    design_hash="a" * 64,
                    hypothesis_id="hyp_test_001",
                    structural_family="family_a",
                    profile_id="event_driven_signal_research",
                    run_dir=str(Path(temp_dir) / "run_b"),
                    step_id="oos_backtest",
                    stage="oos_test",
                )

    def test_window_enforcement_clamps_is_window(self):
        hypothesis = build_hypothesis()
        context = SimpleNamespace(request=SimpleNamespace(hypothesis=hypothesis))
        start_value, end_value = enforce_is_window_if_hypothesis(
            context,
            "2010-01-01",
            "2025-12-31",
            stage="is_only",
        )
        self.assertEqual(start_value, "2018-01-01")
        self.assertEqual(end_value, "2022-12-31")

    def test_window_enforcement_clamps_oos_window(self):
        hypothesis = build_hypothesis()
        context = SimpleNamespace(request=SimpleNamespace(hypothesis=hypothesis))
        start_value, end_value = enforce_is_window_if_hypothesis(
            context,
            "2010-01-01",
            "2025-12-31",
            stage="oos_test",
        )
        self.assertEqual(start_value, "2023-01-01")
        self.assertEqual(end_value, "2024-12-31")

    def test_screening_dataset_build_clamps_before_request_save(self):
        with self.make_temp_dir("screening_clamp") as temp_dir:
            run_dir = Path(temp_dir)
            step = DagStepSpec(
                step_id="dataset_build",
                capability="dataset_build",
                handler="screening_dataset_build",
                config={"stage": "is_only"},
            )
            context = self._build_context(
                run_dir=run_dir,
                step=step,
                hypothesis=build_hypothesis(),
                inputs={
                    "args": {"start": "2010-01-01", "end": "2025-12-31"},
                    "argv": ["--start", "2010-01-01", "--end", "2025-12-31"],
                },
            )
            orch_steps.handle_screening_dataset_build(context)
            payload = json.loads((run_dir / "cache" / "screening_request.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["args"]["start"], "2018-01-01")
            self.assertEqual(payload["args"]["end"], "2022-12-31")
            self.assertEqual(payload["argv"], ["--start", "2018-01-01", "--end", "2022-12-31"])

    def test_theme_dataset_build_passes_clamped_overrides(self):
        with self.make_temp_dir("theme_clamp") as temp_dir:
            run_dir = Path(temp_dir)
            step = DagStepSpec(
                step_id="dataset_build",
                capability="dataset_build",
                handler="theme_dataset_build",
                config={"stage": "is_only"},
            )
            context = self._build_context(
                run_dir=run_dir,
                step=step,
                hypothesis=build_hypothesis(),
                profile_id="theme_strategy",
                inputs={"theme": "all", "stage": "field_audit"},
            )
            with patch("src.research_orchestrator.steps.run_theme_dataset_build_step") as mock_run:
                mock_run.return_value = {"theme_ids": ["small_cap"], "ranking": []}
                orch_steps.handle_theme_dataset_build(context)
            kwargs = mock_run.call_args.kwargs
            self.assertEqual(kwargs["start_override"], "2018-01-01")
            self.assertEqual(kwargs["end_override"], "2022-12-31")

    def test_event_signal_prepare_clamps_before_factor_inputs(self):
        with self.make_temp_dir("event_clamp") as temp_dir:
            run_dir = Path(temp_dir)
            args = SimpleNamespace(
                screening_run_dir=str(run_dir),
                output_dir=str(run_dir),
                max_factors=None,
                max_folds=1,
                skip_holdout=False,
                hypothesis=build_hypothesis().to_dict(),
                stage="is_only",
            )
            report_df = pd.DataFrame(
                [
                    {"factor": "factor_a", "grade": "A (Graduated)", "abs_icir": 0.6},
                    {"factor": "factor_b", "grade": "B (Strong IC)", "abs_icir": 0.4},
                ]
            )
            screening_metadata = {
                "start_date": "2010-01-01",
                "end_date": "2025-12-31",
                "include_new_data": True,
                "qlib_dir": str(PROJECT_ROOT / "data" / "qlib_data"),
            }

            def _compute_factor_inputs(**kwargs):
                self.assertEqual(kwargs["screening_metadata"]["start_date"], "2018-01-01")
                self.assertEqual(kwargs["screening_metadata"]["end_date"], "2022-12-31")
                fwd_df = pd.DataFrame({"fwd_5d": [0.1, 0.2]})
                aux_df = pd.DataFrame({"adj_close": [1.0, 1.1], "market_cap": [1.0, 1.0]})
                return {}, fwd_df, aux_df, {}

            with patch.object(event_signal_steps.event_research, "resolve_output_dir", return_value=run_dir), \
                patch.object(event_signal_steps.event_research, "configure_logging"), \
                patch.object(event_signal_steps.event_research, "load_config", return_value={}), \
                patch.object(event_signal_steps.event_research, "load_screening_inputs", return_value=(report_df, screening_metadata)), \
                patch.object(event_signal_steps.event_research, "build_factor_meta", return_value={}), \
                patch.object(event_signal_steps.event_research, "compute_factor_inputs", side_effect=_compute_factor_inputs), \
                patch.object(event_signal_steps.event_research, "write_series_parquet"), \
                patch.object(event_signal_steps.event_research, "write_json"):
                prepared = event_signal_steps._prepare_signal_stage_inputs(args)
            self.assertEqual(prepared["screening_metadata"]["start_date"], "2018-01-01")
            self.assertEqual(prepared["screening_metadata"]["end_date"], "2022-12-31")

    def test_ml_dataset_build_passes_clamped_overrides_to_loaders(self):
        with self.make_temp_dir("ml_clamp") as temp_dir:
            run_dir = Path(temp_dir)
            bundle = SimpleNamespace(
                screening_metadata={
                    "start_date": "2010-01-01",
                    "end_date": "2025-12-31",
                    "qlib_dir": str(PROJECT_ROOT / "data" / "qlib_data"),
                },
                candidate_factors=["factor_a"],
                folds=[],
                holdout=None,
                run_metadata={},
            )
            args_payload = {
                "baseline_run_dir": str(run_dir / "baseline"),
                "screening_run_dir": str(run_dir / "screening"),
                "label_horizon": 10,
                "capital": 1000000,
                "model_variants": "linear",
                "output_dir": str(run_dir),
                "stage": "is_only",
                "hypothesis": build_hypothesis().to_dict(),
            }
            with patch.object(ml_steps.ml_research, "resolve_output_dir", return_value=run_dir), \
                patch.object(ml_steps.ml_research, "configure_logging"), \
                patch.object(ml_steps.ml_research, "parse_model_variants", return_value=["linear"]), \
                patch.object(ml_steps.ml_research, "load_baseline_bundle", return_value=bundle), \
                patch.object(ml_steps.ml_research, "validate_inputs"), \
                patch.object(ml_steps.ml_research, "load_forward_return_series", return_value=pd.Series([0.1])) as mock_forward, \
                patch.object(ml_steps.ml_research, "load_support_context", return_value=SimpleNamespace(trade_calendar=[1], factor_category={"x": "y"})):
                ml_steps.run_ml_dataset_build_step(output_root=run_dir, args_payload=args_payload)
            for call in mock_forward.call_args_list:
                self.assertEqual(call.kwargs["start_override"], "2018-01-01")
                self.assertEqual(call.kwargs["end_override"], "2022-12-31")

    def test_improvement_dataset_build_passes_clamped_overrides_to_loaders(self):
        with self.make_temp_dir("improvement_clamp") as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "cache").mkdir(parents=True, exist_ok=True)
            bundle = SimpleNamespace(
                screening_run_dir=run_dir / "screening",
                screening_metadata={
                    "start_date": "2010-01-01",
                    "end_date": "2025-12-31",
                    "qlib_dir": str(PROJECT_ROOT / "data" / "qlib_data"),
                },
                candidate_factors=["factor_a"],
                folds=[],
                holdout=None,
                factor_selection_decisions=pd.DataFrame(),
            )
            benchmark_audit = BenchmarkAuditResult(
                benchmark_code="000001.SH",
                row_count=0,
                start_date="2018-01-01",
                end_date="2022-12-31",
                duplicate_trade_dates=0,
                missing_trade_days=0,
                null_trade_date=0,
                null_open=0,
                null_high=0,
                null_low=0,
                null_close=0,
                null_pre_close=0,
                non_positive_open=0,
                non_positive_high=0,
                non_positive_low=0,
                non_positive_close=0,
                non_positive_pre_close=0,
                bad_high_low=0,
                close_outside_range=0,
                pct_chg_diff_max_abs=0.0,
                pct_chg_diff_over_1bp=0,
                passed=True,
            )
            args_payload = {
                "baseline_run_dir": str(run_dir / "baseline"),
                "benchmark": "000001.SH",
                "max_folds": None,
                "output_dir": str(run_dir),
                "stage": "is_only",
                "hypothesis": build_hypothesis().to_dict(),
            }
            with patch.object(improvement_steps.improvement, "resolve_output_dir", return_value=run_dir), \
                patch.object(improvement_steps.improvement, "configure_logging"), \
                patch.object(improvement_steps.improvement, "load_baseline_bundle", return_value=bundle), \
                patch.object(improvement_steps, "run_audit", return_value=benchmark_audit), \
                patch.object(improvement_steps.improvement, "load_forward_return_series", return_value=pd.Series([0.1])) as mock_forward, \
                patch.object(improvement_steps.improvement, "load_support_context", return_value=SimpleNamespace(trade_calendar=[1], factor_category={"x": "y"})), \
                patch.object(improvement_steps.improvement, "compute_stability_scores", return_value=pd.DataFrame()):
                improvement_steps.run_improvement_dataset_build_step(output_root=run_dir, args_payload=args_payload)
            self.assertEqual(mock_forward.call_args.kwargs["start_override"], "2018-01-01")
            self.assertEqual(mock_forward.call_args.kwargs["end_override"], "2022-12-31")

    def test_testing_ledger_verdict_is_append_only(self):
        with self.make_temp_dir("testing_ledger") as temp_dir:
            store = TestingLedgerStore(Path(temp_dir) / "ledger")
            measurement = store.record_event(
                hypothesis_id="hyp_test_001",
                design_hash="design_hash",
                prose_hash="prose_hash",
                structural_family="family_a",
                economic_family="econ_a",
                profile_id="factor_screening",
                run_id="run_a",
                run_dir=str(Path(temp_dir) / "run_a"),
                test_name="gate:gate_review",
                stage="is_only",
                statistic_name="sharpe",
                statistic_value=1.1,
                sharpe=1.1,
                event_kind="measurement",
            )
            first_verdict = store.record_verdict(
                related_event_id=measurement["event_id"],
                design_hash="design_hash",
                verdict="approved",
                decision_by="tester",
                reason="first verdict",
                run_id="run_a",
                run_dir=str(Path(temp_dir) / "run_a"),
            )
            second_verdict = store.record_verdict(
                related_event_id=measurement["event_id"],
                design_hash="design_hash",
                verdict="rejected",
                decision_by="tester",
                reason="second verdict",
                run_id="run_b",
                run_dir=str(Path(temp_dir) / "run_b"),
            )
            events = store.list_events()
            self.assertEqual(len(events), 3)
            self.assertEqual(store.get_verdict_for_measurement(measurement["event_id"])["event_id"], second_verdict["event_id"])
            self.assertEqual(second_verdict["supersedes_event_id"], first_verdict["event_id"])

    def test_dsr_variance_uses_measurement_events_only(self):
        with self.make_temp_dir("testing_variance") as temp_dir:
            store = TestingLedgerStore(Path(temp_dir) / "ledger")
            first = store.record_event(
                hypothesis_id="hyp_test_001",
                design_hash="design_hash",
                prose_hash="prose_hash",
                structural_family="family_a",
                economic_family="econ_a",
                profile_id="factor_screening",
                run_id="run_a",
                run_dir=str(Path(temp_dir) / "run_a"),
                test_name="gate:one",
                stage="is_only",
                statistic_name="sharpe",
                statistic_value=0.8,
                sharpe=0.8,
                event_kind="measurement",
            )
            store.record_event(
                hypothesis_id="hyp_test_001",
                design_hash="design_hash",
                prose_hash="prose_hash",
                structural_family="family_a",
                economic_family="econ_a",
                profile_id="factor_screening",
                run_id="run_b",
                run_dir=str(Path(temp_dir) / "run_b"),
                test_name="gate:two",
                stage="is_only",
                statistic_name="sharpe",
                statistic_value=1.2,
                sharpe=1.2,
                event_kind="measurement",
            )
            store.record_verdict(
                related_event_id=first["event_id"],
                design_hash="design_hash",
                verdict="approved",
                decision_by="tester",
                reason="verdict should not affect variance",
                run_id="run_c",
                run_dir=str(Path(temp_dir) / "run_c"),
            )
            variance = store.get_family_variance("family_a")
            self.assertAlmostEqual(float(variance), 0.08, places=6)

    def test_gate_report_refuses_missing_concern_scores(self):
        with self.make_temp_dir("gate_missing_scores") as temp_dir:
            run_dir = Path(temp_dir)
            step = DagStepSpec(
                step_id="gate_review",
                capability="gate_review",
                handler="gate_review",
                depends_on=("gate_evaluation", "gate_concern_scoring"),
            )
            steps = (
                DagStepSpec(step_id="gate_evaluation", capability="gate_evaluation", handler="gate_evaluation"),
                DagStepSpec(step_id="gate_concern_scoring", capability="gate_concern_scoring", handler="gate_concern_scoring"),
                step,
            )
            context = self._build_context(
                run_dir=run_dir,
                step=step,
                hypothesis=build_hypothesis(),
                steps=steps,
                state={"step_outputs": {"gate_evaluation": {"criteria_results": [], "measured_values": {}}}},
            )
            with self.assertRaises(ConcernEnforcementError):
                _load_concern_scores_from_outputs(context)

    def test_concern_severity_cannot_be_downgraded_below_derived_minimum(self):
        with self.make_temp_dir("concern_downgrade") as temp_dir:
            run_dir = Path(temp_dir)
            step = DagStepSpec(
                step_id="gate_concern_scoring",
                capability="gate_concern_scoring",
                handler="gate_concern_scoring",
                depends_on=("gate_evaluation",),
            )
            steps = (
                DagStepSpec(step_id="gate_evaluation", capability="gate_evaluation", handler="gate_evaluation"),
                step,
            )
            state = {
                "step_outputs": {
                    "gate_evaluation": {
                        "criteria_results": [
                            {
                                "rule_id": "min_rank_icir",
                                "metric": "rank_icir",
                                "comparator": ">=",
                                "threshold": 1.0,
                                "actual": 0.2,
                                "passed": False,
                            }
                        ],
                        "measured_values": {"rank_icir": 0.2},
                    }
                },
                "resumed_inputs": {
                    "gate_concern_scoring": {
                        "scores": [
                            {
                                "concern_id": "most_likely_failure_mode",
                                "concern_text": "Example concern",
                                "keyed_to_rule_id": "min_rank_icir",
                                "measured_evidence_against_concern": "x" * 100,
                                "quantitative_anchor": {"rank_icir": 0.2},
                                "confirmed": True,
                                "severity": "low",
                            }
                        ]
                    }
                },
            }
            context = self._build_context(
                run_dir=run_dir,
                step=step,
                hypothesis=build_hypothesis(),
                steps=steps,
                state=state,
                resumed=True,
            )
            with self.assertRaises(ConcernEnforcementError):
                orch_steps.handle_gate_concern_scoring(context)

    def test_derive_severity_uses_rule_metric_not_first_anchor_value(self):
        severity = derive_severity(
            {
                "metric": "rank_icir",
                "comparator": ">=",
                "threshold": 1.0,
                "passed": False,
            },
            {"other_metric": 1.5, "rank_icir": 0.2},
        )
        self.assertEqual(severity, "high")

    def test_engine_backstop_requires_holdout_context_for_oos(self):
        with self.assertRaises(ValueError):
            EventDrivenBacktester().run(
                strategy=object(),
                start_time="2023-01-01",
                end_time="2023-01-31",
                time_split={
                    "stage": "oos_test",
                    "is_start": "2018-01-01",
                    "is_end": "2022-12-31",
                    "oos_start": "2023-01-01",
                    "oos_end": "2024-12-31",
                },
            )

    def test_registry_publish_blocked_on_gate_rejection(self):
        with self.make_temp_dir("publish_reject") as temp_dir:
            run_dir = Path(temp_dir)
            step = DagStepSpec(
                step_id="registry_publish",
                capability="registry_publish",
                handler="registry_publish",
                depends_on=("gate_review",),
            )
            steps = (
                DagStepSpec(step_id="gate_review", capability="gate_review", handler="gate_review"),
                step,
            )
            context = self._build_context(
                run_dir=run_dir,
                step=step,
                steps=steps,
                state={"step_outputs": {"gate_review": {"decision": "rejected", "verdict": {"decision": "rejected"}}}},
            )
            with self.assertRaises(ValueError):
                orch_steps._assert_gate_allows_publication(context)

    def test_concern_scores_survive_resume_from_step_outputs(self):
        with self.make_temp_dir("resume_scores") as temp_dir:
            run_dir = Path(temp_dir)
            write_json(
                run_dir / "dag_state.json",
                {
                    "status": "paused",
                    "steps": [
                        {
                            "step_id": "gate_concern_scoring",
                            "status": "completed",
                        },
                        {
                            "step_id": "gate_review",
                            "status": "paused",
                        },
                    ],
                },
            )
            write_json(
                run_dir / "steps" / "gate_concern_scoring" / "step_outputs.json",
                {
                    "concern_scores": [
                        {
                            "concern_id": "most_likely_failure_mode",
                            "concern_text": "Persisted concern score",
                        }
                    ]
                },
            )
            write_json(run_dir / "steps" / "gate_review" / "step_outputs.json", {})
            state = reconstruct_state_from_completed_steps(run_dir)
            step = DagStepSpec(
                step_id="gate_review",
                capability="gate_review",
                handler="gate_review",
                depends_on=("gate_concern_scoring",),
            )
            steps = (
                DagStepSpec(
                    step_id="gate_concern_scoring",
                    capability="gate_concern_scoring",
                    handler="gate_concern_scoring",
                ),
                step,
            )
            context = self._build_context(
                run_dir=run_dir,
                step=step,
                hypothesis=build_hypothesis(),
                steps=steps,
                state=state,
            )
            concern_rows = _load_concern_scores_from_outputs(context)
            self.assertEqual(concern_rows[0]["concern_text"], "Persisted concern score")

    def test_registry_master_preserves_quarantined_status(self):
        with self.make_temp_dir("registry_quarantine") as temp_dir:
            store = HypothesisRegistryStore(Path(temp_dir) / "registry")
            hypothesis = build_hypothesis()
            store.register(hypothesis)
            result = store.record_gate_decision(
                hypothesis_id=hypothesis.hypothesis_id,
                design_hash=hypothesis.design_hash(),
                run_dir=str(Path(temp_dir) / "run"),
                profile_id="factor_screening",
                gate_id="gate_review",
                gate_stage="is_only",
                decision="quarantined",
                decision_by="tester",
                decision_reason="manual quarantine",
                measured_values={},
                criteria_results=[],
            )
            self.assertEqual(result["new_status"], "is_quarantined")
            self.assertEqual(store.get(hypothesis.hypothesis_id)["status"], "is_quarantined")

    def test_gate_review_accepts_quarantined_decision(self):
        with self.make_temp_dir("gate_quarantine") as temp_dir:
            run_dir = Path(temp_dir)
            hypothesis = build_hypothesis()
            registry_dirs = {
                "hypothesis_registry_dir": run_dir / "registry",
                "testing_ledger_dir": run_dir / "ledger",
            }
            step = DagStepSpec(
                step_id="gate_review",
                capability="gate_review",
                handler="gate_review",
                depends_on=("gate_evaluation", "gate_concern_scoring"),
                config={"stage": "is_only"},
            )
            steps = (
                DagStepSpec(step_id="gate_evaluation", capability="gate_evaluation", handler="gate_evaluation"),
                DagStepSpec(
                    step_id="gate_concern_scoring",
                    capability="gate_concern_scoring",
                    handler="gate_concern_scoring",
                    depends_on=("gate_evaluation",),
                ),
                step,
            )
            step_dir = run_dir / "steps" / "gate_review"
            step_dir.mkdir(parents=True, exist_ok=True)
            (step_dir / "gate_decision.json").write_text(
                json.dumps(
                    {
                        "decision": "quarantined",
                        "decision_by": "tester",
                        "reason": "needs manual follow-up",
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
            context = self._build_context(
                run_dir=run_dir,
                step=step,
                hypothesis=hypothesis,
                steps=steps,
                state={
                    "step_outputs": {
                        "gate_evaluation": {
                            "criteria_results": [{"rule_id": "min_rank_icir", "metric": "rank_icir", "threshold": 0.1, "actual": 0.1, "passed": True, "is_hard": True}],
                            "measured_values": {"rank_icir": 0.1},
                        },
                        "gate_concern_scoring": {
                            "concern_scores": [
                                {
                                    "concern_id": "most_likely_failure_mode",
                                    "concern_text": "Concern text",
                                    "keyed_to_rule_id": "min_rank_icir",
                                    "measured_evidence_against_concern": "x" * 100,
                                    "quantitative_anchor": {"rank_icir": 0.1},
                                    "confirmed": True,
                                    "severity": "low",
                                }
                            ]
                        },
                    }
                },
                registry_dirs=registry_dirs,
            )
            result = orch_steps.handle_gate_review(context)
            self.assertEqual(result.outputs["decision"], "quarantined")
            self.assertEqual(context.state.get("publish_status_override"), "under_review")

    def test_verify_seal_exit_codes(self):
        with self.make_temp_dir("verify_seal") as temp_dir:
            seal_dir = Path(temp_dir) / "seal"
            registry_dir = Path(temp_dir) / "registry"
            self.assertEqual(
                hypothesis_cli.main(
                    ["--registry-dir", str(registry_dir), "verify-seal", "not-a-hash", "--seal-dir", str(seal_dir)]
                ),
                2,
            )
            self.assertEqual(
                hypothesis_cli.main(
                    ["--registry-dir", str(registry_dir), "verify-seal", "a" * 64, "--seal-dir", str(seal_dir)]
                ),
                0,
            )
            HoldoutSealStore(seal_dir).claim_holdout_access(
                design_hash="a" * 64,
                hypothesis_id="hyp_test_001",
                structural_family="family_a",
                profile_id="event_driven_signal_research",
                run_dir=str(Path(temp_dir) / "run"),
                step_id="oos_backtest",
                stage="oos_test",
            )
            self.assertEqual(
                hypothesis_cli.main(
                    ["--registry-dir", str(registry_dir), "verify-seal", "a" * 64, "--seal-dir", str(seal_dir)]
                ),
                1,
            )

    def test_pause_for_input_payload_round_trip(self):
        payload = PauseForInputPayload(
            artifact_path="E:/tmp/gate_concern_scores.json",
            schema_id="gate_concern_scores_v1",
            description="Need scored concerns",
            template_path="E:/tmp/gate_concern_scores_template.json",
            expected_fields=("scores",),
        )
        restored = PauseForInputPayload.from_dict(payload.to_dict())
        self.assertEqual(restored, payload)

    def test_deterministic_cache_path_is_stable_across_subprocess(self):
        here_value = _deterministic_cache_path("day", ["$close", "$open"], "2020-01-01", "2020-12-31")
        command = [
            sys.executable,
            "-c",
            (
                "from src.research_orchestrator.qlib_windowed_features import _deterministic_cache_path; "
                "print(_deterministic_cache_path('day', ['$close', '$open'], '2020-01-01', '2020-12-31'))"
            ),
        ]
        result = subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True, check=True)
        self.assertEqual(here_value, result.stdout.strip())

    def test_direct_d_features_calls_are_confined_to_wrapper(self):
        # Delegate to the canonical AST lint so there is a single source of
        # truth for detection patterns, the wrapper allowlist, and the
        # `# noqa: bare-qlib-features` per-line opt-out (e.g. the privileged
        # provider-attestation sentinel read in src/data_infra/provider_manifest.py).
        lint_script = PROJECT_ROOT / "scripts" / "lint_no_bare_qlib_features.py"
        result = subprocess.run(
            [sys.executable, str(lint_script), str(PROJECT_ROOT / "src")],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self.assertEqual(
            result.returncode,
            0,
            f"bare D.features lint violations in src/:\n{result.stdout}\n{result.stderr}",
        )


class PrescriptionSchemaTests(unittest.TestCase):
    """Gate A regression (jolly-seeking-lollipop): PrescribedRecipe schema +
    Hypothesis.prescription field. Verifies (1) backward-compat invariant for
    design_hash, (2) PrescribedRecipe.validate() rejects non-v1 kinds, weight≤0,
    duplicate names, infeasible portfolio, (3) UniverseSpec dispatch + roundtrip,
    (4) UniverseCandidate to_dict/from_dict preserves special_filters tuple.
    """

    def _build_broad_universe(self):
        from src.alpha_research.theme_strategy.schema import UniverseCandidate
        return UniverseCandidate(
            candidate_id="test_broad",
            membership_source="all_market",
            board_policy="mainboard",
            st_mode="exclude",
            min_listing_days=250,
            market_cap_min=3_000_000_000,
            liquidity_floor=20_000_000,
            profitability_field="n_income_attr_p",
            profitability_positive=True,
            special_filters=("filter_a", "filter_b"),
        )

    def _build_recipe(self, **overrides):
        from src.research_orchestrator.hypothesis import (
            UniverseSpec,
            PrescribedComponent,
            PrescribedRecipe,
        )
        defaults = dict(
            universe=UniverseSpec(kind="broad", broad_filters=self._build_broad_universe()),
            components=(
                PrescribedComponent(factor_name="grow_opprofit_qoq", weight=1.0, kind="raw", direction="higher_is_better"),
                PrescribedComponent(factor_name="grow_roe_yoy", weight=1.0, kind="raw", direction="higher_is_better"),
            ),
            composite_kind="rank_weighted",
            topk=50,
            rebalance_days=10,
            neutralization=("size", "industry"),
            # R4-M2: formal steps fail closed without a prescription-pinned
            # policy id. Deliberately NOT part of normalized_dict()/design_hash
            # (execution-environment binding, not design identity) — legacy
            # fixture literal keeps the simulated flows semantically unchanged.
            calendar_policy_id="frozen_20260227_system_build",
        )
        defaults.update(overrides)
        return PrescribedRecipe(**defaults)

    # ── design_hash byte-stability (Codex round-1 critical #2) ─────────────
    def test_design_hash_stability_without_prescription(self):
        """Hypothesis without prescription must have identical design_hash to
        before this Gate A field was added — guarantees existing seals stay valid."""
        h = build_hypothesis()
        self.assertIsNone(h.prescription)
        first_hash = h.design_hash()
        # Roundtrip via to_dict/from_dict preserves the hash too.
        from src.research_orchestrator.hypothesis import Hypothesis
        roundtrip = Hypothesis.from_dict(h.to_dict())
        self.assertEqual(roundtrip.design_hash(), first_hash)

    def test_design_hash_changes_with_prescription(self):
        h_without = build_hypothesis()
        from src.research_orchestrator.hypothesis import Hypothesis
        # Build a hypothesis WITH prescription using all the same other fields.
        h_with = Hypothesis(
            **{**{
                k: getattr(h_without, k) for k in (
                    "hypothesis_id", "thesis_statement", "mechanism", "source",
                    "factor_refs", "factor_yaml_hashes", "universe", "benchmark",
                    "time_split", "rebalance_frequency", "neutralization",
                    "expected_sign", "expected_effect", "expected_decay_horizon_days",
                    "success_criteria", "pre_registered_concerns",
                    "pre_registered_at", "registered_by",
                )
            }, "prescription": self._build_recipe()}
        )
        self.assertNotEqual(h_without.design_hash(), h_with.design_hash())

    # ── UniverseSpec dispatch ─────────────────────────────────────────────
    def test_universe_spec_dispatch_theme_and_broad(self):
        from src.research_orchestrator.hypothesis import UniverseSpec
        # broad
        spec_broad = UniverseSpec(kind="broad", broad_filters=self._build_broad_universe())
        spec_broad.validate()
        roundtrip_broad = UniverseSpec.from_dict(spec_broad.to_dict())
        self.assertEqual(spec_broad.kind, roundtrip_broad.kind)
        self.assertEqual(
            spec_broad.broad_filters.candidate_id, roundtrip_broad.broad_filters.candidate_id
        )
        # theme
        spec_theme = UniverseSpec(
            kind="theme", theme_id="growth", theme_universe_candidate_id="gr_u5"
        )
        spec_theme.validate()
        roundtrip_theme = UniverseSpec.from_dict(spec_theme.to_dict())
        self.assertEqual(spec_theme.theme_id, roundtrip_theme.theme_id)
        self.assertEqual(
            spec_theme.theme_universe_candidate_id, roundtrip_theme.theme_universe_candidate_id
        )

    def test_universe_spec_rejects_invalid_kinds(self):
        from src.research_orchestrator.hypothesis import UniverseSpec
        with self.assertRaises(ValueError):
            UniverseSpec(kind="theme").validate()  # missing theme_id
        with self.assertRaises(ValueError):
            UniverseSpec(kind="broad").validate()  # missing broad_filters
        with self.assertRaises(ValueError):
            UniverseSpec(
                kind="theme",
                theme_id="growth",
                theme_universe_candidate_id="gr_u5",
                broad_filters=self._build_broad_universe(),
            ).validate()  # both set is invalid

    # ── UniverseCandidate roundtrip preserves special_filters tuple ──────
    def test_universe_candidate_roundtrip_preserves_special_filters_tuple(self):
        from src.alpha_research.theme_strategy.schema import UniverseCandidate
        original = self._build_broad_universe()
        roundtrip = UniverseCandidate.from_dict(original.to_dict())
        self.assertEqual(roundtrip.special_filters, ("filter_a", "filter_b"))
        self.assertIsInstance(roundtrip.special_filters, tuple)

    # ── PrescribedRecipe.validate() rules ─────────────────────────────────
    def test_recipe_validate_rejects_empty_components(self):
        with self.assertRaises(ValueError):
            self._build_recipe(components=()).validate()

    def test_recipe_validate_rejects_duplicate_factor_names(self):
        from src.research_orchestrator.hypothesis import PrescribedComponent
        with self.assertRaises(ValueError):
            self._build_recipe(components=(
                PrescribedComponent(factor_name="x", weight=1.0),
                PrescribedComponent(factor_name="x", weight=1.0),
            )).validate()

    def test_componentkind_validate_rejects_non_raw_in_v1(self):
        from src.research_orchestrator.hypothesis import PrescribedComponent
        with self.assertRaises(ValueError) as ctx:
            self._build_recipe(components=(
                PrescribedComponent(factor_name="x", weight=1.0, kind="industry_relative"),
            )).validate()
        self.assertIn("kind='industry_relative' not supported in v1", str(ctx.exception))

    def test_recipe_validate_rejects_non_positive_weight(self):
        from src.research_orchestrator.hypothesis import PrescribedComponent
        with self.assertRaises(ValueError):
            self._build_recipe(components=(
                PrescribedComponent(factor_name="x", weight=0.0),
            )).validate()
        with self.assertRaises(ValueError):
            self._build_recipe(components=(
                PrescribedComponent(factor_name="x", weight=-1.0),
            )).validate()

    def test_portfolio_validate_against_topk_rejects_infeasible_combo(self):
        from src.research_orchestrator.hypothesis import PortfolioConstruction
        # 0.01 * 50 = 0.5, less than target_gross_exposure 1.0
        with self.assertRaises(ValueError) as ctx:
            PortfolioConstruction(
                target_gross_exposure=1.0,
                max_position_weight=0.01,
            ).validate_against_topk(50)
        self.assertIn("infeasible", str(ctx.exception))

    def test_recipe_validate_rejects_unknown_neutralization(self):
        with self.assertRaises(ValueError) as ctx:
            self._build_recipe(neutralization=("size", "country")).validate()
        self.assertIn("country", str(ctx.exception))

    # ── Roundtrip ─────────────────────────────────────────────────────────
    def test_recipe_roundtrip_preserves_all_fields(self):
        from src.research_orchestrator.hypothesis import PrescribedRecipe
        recipe = self._build_recipe()
        roundtrip = PrescribedRecipe.from_dict(recipe.to_dict())
        self.assertEqual(roundtrip.composite_kind, recipe.composite_kind)
        self.assertEqual(roundtrip.topk, recipe.topk)
        self.assertEqual(roundtrip.rebalance_days, recipe.rebalance_days)
        self.assertEqual(len(roundtrip.components), len(recipe.components))
        self.assertEqual(roundtrip.components[0].factor_name, "grow_opprofit_qoq")
        self.assertEqual(roundtrip.allow_candidate_components, False)

    def test_floor_rails_present_for_validation_profile(self):
        from src.research_orchestrator.hypothesis import SUCCESS_CRITERIA_FLOORS
        self.assertIn("hypothesis_validation", SUCCESS_CRITERIA_FLOORS)
        floors = SUCCESS_CRITERIA_FLOORS["hypothesis_validation"]
        for key in (
            "min_rank_icir", "min_deflated_sharpe", "min_cost_adjusted_sharpe",
            "max_drawdown", "max_annual_turnover", "min_monotonicity_pvalue",
            "max_correlation_to_approved",
        ):
            self.assertIn(key, floors)


class HypothesisValidationProfileShellTests(unittest.TestCase):
    """Gate B regression (jolly-seeking-lollipop): the new profile +
    DAG builder + 11 stub handlers must plan end-to-end. Verifies:
    - profile is registered
    - DAG builder rejects requests without prescription
    - DAG builder produces a valid CompiledResearchDag (no duplicate IDs)
    - All 11 step handlers are registered
    - gate_review steps depend on BOTH eval and concerns (capability lookup)
    - Stage config is set on stage-sensitive steps
    - Engine output collection at engine.py:1002 finds renamed diagnostics
      step (handled in Gate F; for Gate B we only assert the step IDs exist)
    """

    def _build_recipe(self):
        from src.research_orchestrator.hypothesis import (
            UniverseSpec,
            PrescribedComponent,
            PrescribedRecipe,
        )
        from src.alpha_research.theme_strategy.schema import UniverseCandidate
        return PrescribedRecipe(
            universe=UniverseSpec(kind="broad", broad_filters=UniverseCandidate(
                candidate_id="test_broad",
                membership_source="all_market",
                board_policy="mainboard",
                st_mode="exclude",
                min_listing_days=250,
                market_cap_min=3_000_000_000,
                liquidity_floor=20_000_000,
                profitability_field="n_income_attr_p",
                profitability_positive=True,
            )),
            components=(
                PrescribedComponent(factor_name="grow_opprofit_qoq", weight=1.0),
                PrescribedComponent(factor_name="grow_roe_yoy", weight=1.0),
            ),
            composite_kind="rank_weighted",
            topk=50,
            rebalance_days=10,
            neutralization=("size", "industry"),
            # R4-M2: formal steps require the prescription-pinned policy id.
            calendar_policy_id="frozen_20260227_system_build",
        )

    def _build_validation_request(self, *, with_prescription: bool = True):
        from src.research_orchestrator.hypothesis import Hypothesis, SuccessCriteria
        from src.research_orchestrator.schema import ResearchRequest
        # Use the helper from this file but swap in validation-floor success criteria
        # so floor-rail validation against hypothesis_validation passes naturally.
        h = build_hypothesis(success_criteria=SuccessCriteria(
            min_rank_icir=0.04,
            min_deflated_sharpe=1.1,
            min_cost_adjusted_sharpe=0.8,
            max_drawdown=0.25,
            max_annual_turnover=4.0,
            min_monotonicity_pvalue=0.05,
            max_correlation_to_approved=0.7,
            min_regime_pass_count=2,
            effect_size_must_be_in_ci=True,
        ))
        if with_prescription:
            h = Hypothesis.from_dict({**h.to_dict(), "prescription": self._build_recipe().to_dict()})
        return ResearchRequest(
            profile_id="hypothesis_validation",
            mode="formal",
            consumes=[],
            produces=[],
            requested_capabilities=[],
            inputs={"output_dir": str((WORKSPACE_OUTPUTS / "validation_dag_test").resolve())},
            run_context={},
            hypothesis=h,
        )

    def test_profile_is_registered(self):
        from src.research_orchestrator.engine import profile_registry
        profile = profile_registry().get("hypothesis_validation")
        self.assertEqual(profile.profile_id, "hypothesis_validation")
        self.assertEqual(profile.supported_modes, ("formal",))

    def test_dag_builder_requires_prescription(self):
        from src.research_orchestrator.engine import _hypothesis_validation_dag_builder
        request = self._build_validation_request(with_prescription=False)
        with self.assertRaises(ValueError) as ctx:
            _hypothesis_validation_dag_builder(request, [])
        self.assertIn("prescription", str(ctx.exception))

    def test_dag_step_ids_unique_and_includes_oos_gates(self):
        from src.research_orchestrator.engine import _hypothesis_validation_dag_builder
        request = self._build_validation_request()
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        dag = _hypothesis_validation_dag_builder(request, [])
        step_ids = [s.step_id for s in dag.steps]
        self.assertEqual(len(step_ids), len(set(step_ids)),
                         f"Duplicate step IDs: {[x for x in step_ids if step_ids.count(x) > 1]}")
        # Must include both IS and OOS gate triplets
        for must_have in (
            "validation_object_resolver",
            "validation_gate_eval_is", "validation_gate_concerns_is", "validation_gate_review_is",
            "validation_gate_eval_oos", "validation_gate_concerns_oos", "validation_gate_review_oos",
            "validation_registry_publish",
        ):
            self.assertIn(must_have, step_ids)

    def test_gate_review_depends_on_both_eval_and_concerns(self):
        """Codex round-2 #1 regression: handle_gate_review looks up predecessors
        BY CAPABILITY, so depends_on must list both gate_eval AND gate_concerns
        (a linear chain would make capability lookup fail)."""
        from src.research_orchestrator.engine import _hypothesis_validation_dag_builder
        request = self._build_validation_request()
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        dag = _hypothesis_validation_dag_builder(request, [])
        steps_by_id = {s.step_id: s for s in dag.steps}
        for review_id, eval_id, concerns_id in (
            ("validation_gate_review_is", "validation_gate_eval_is", "validation_gate_concerns_is"),
            ("validation_gate_review_oos", "validation_gate_eval_oos", "validation_gate_concerns_oos"),
        ):
            review = steps_by_id[review_id]
            self.assertIn(eval_id, review.depends_on, f"{review_id} missing dep on {eval_id}")
            self.assertIn(concerns_id, review.depends_on, f"{review_id} missing dep on {concerns_id}")

    def test_dag_step_config_stage_is_set(self):
        """Codex round-4 must-fix #1 regression: shared gate handlers read
        stage from context.step.config['stage'] defaulting to 'is_only' at
        steps.py:116. Without explicit config the OOS gate report would be
        mislabeled as IS — a silent correctness bug."""
        from src.research_orchestrator.engine import _hypothesis_validation_dag_builder
        request = self._build_validation_request()
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        dag = _hypothesis_validation_dag_builder(request, [])
        steps_by_id = {s.step_id: s for s in dag.steps}
        for is_step in (
            "validation_vectorized_backtest_is", "validation_event_backtest_is",
            "validation_diagnostics_is", "validation_gate_eval_is",
            "validation_gate_concerns_is", "validation_gate_review_is",
        ):
            self.assertEqual(steps_by_id[is_step].config.get("stage"), "is_only",
                             f"{is_step} missing config={{'stage': 'is_only'}}")
        for oos_step in (
            "validation_event_backtest_oos", "validation_diagnostics_oos",
            "validation_gate_eval_oos", "validation_gate_concerns_oos",
            "validation_gate_review_oos",
        ):
            self.assertEqual(steps_by_id[oos_step].config.get("stage"), "oos_test",
                             f"{oos_step} missing config={{'stage': 'oos_test'}}")

    def test_handler_registry_complete_for_validation_dag(self):
        from src.research_orchestrator.engine import _hypothesis_validation_dag_builder
        from src.research_orchestrator.steps import HANDLER_REGISTRY
        request = self._build_validation_request()
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        dag = _hypothesis_validation_dag_builder(request, [])
        for step in dag.steps:
            self.assertIn(step.handler, HANDLER_REGISTRY,
                          f"Handler {step.handler!r} for step {step.step_id!r} not registered")

    def test_object_resolver_step_present_in_dag(self):
        """Codex round-2 #3 regression: formal_requires_resolver=True does NOT
        auto-add a resolver step; the DAG must include one explicitly."""
        from src.research_orchestrator.engine import _hypothesis_validation_dag_builder
        request = self._build_validation_request()
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        dag = _hypothesis_validation_dag_builder(request, [])
        step_ids = [s.step_id for s in dag.steps]
        self.assertIn("validation_object_resolver", step_ids)
        # And it must precede dataset_build (which would consume the resolved factors).
        self.assertLess(
            step_ids.index("validation_object_resolver"),
            step_ids.index("validation_dataset_build"),
        )


class PrescriptionRuntimeTests(unittest.TestCase):
    """Gate C unit tests (jolly-seeking-lollipop): pure prescription_runtime
    helpers. Tested on synthetic frames so no Qlib / ResearchSupport
    fixtures are required.
    """

    def _build_recipe(self, **overrides):
        from src.research_orchestrator.hypothesis import (
            UniverseSpec, PrescribedComponent, PrescribedRecipe,
        )
        from src.alpha_research.theme_strategy.schema import UniverseCandidate
        defaults = dict(
            universe=UniverseSpec(
                kind="broad",
                broad_filters=UniverseCandidate(
                    candidate_id="t",
                    membership_source="all_market",
                    board_policy="mainboard",
                    st_mode="exclude",
                    min_listing_days=250,
                ),
            ),
            components=(
                PrescribedComponent(factor_name="alpha_a", weight=1.0, kind="raw", direction="higher_is_better"),
                PrescribedComponent(factor_name="alpha_b", weight=2.0, kind="raw", direction="lower_is_better"),
            ),
            composite_kind="rank_weighted",
            topk=3,
            rebalance_days=5,
        )
        defaults.update(overrides)
        return PrescribedRecipe(**defaults)

    def _build_factor_frame(self):
        # 3 stocks × 2 dates, two factors
        idx = pd.MultiIndex.from_tuples(
            [
                (pd.Timestamp("2024-01-02"), "000001_SZ"),
                (pd.Timestamp("2024-01-02"), "000002_SZ"),
                (pd.Timestamp("2024-01-02"), "600519_SH"),
                (pd.Timestamp("2024-01-09"), "000001_SZ"),
                (pd.Timestamp("2024-01-09"), "000002_SZ"),
                (pd.Timestamp("2024-01-09"), "600519_SH"),
            ],
            names=["datetime", "instrument"],
        )
        return pd.DataFrame(
            {
                "alpha_a": [0.10, 0.20, 0.30, 0.50, 0.40, 0.30],
                "alpha_b": [0.50, 0.40, 0.30, 0.10, 0.20, 0.30],
            },
            index=idx,
        )

    def test_compute_factor_frame_assembles_columns(self):
        from src.research_orchestrator.prescription_runtime import compute_factor_frame
        recipe = self._build_recipe()
        frame_input = self._build_factor_frame()
        series_map = {col: frame_input[col] for col in frame_input.columns}
        out = compute_factor_frame(prescription=recipe, factor_series_map=series_map)
        self.assertEqual(list(out.columns), ["alpha_a", "alpha_b"])
        self.assertEqual(len(out), 6)

    def test_compute_factor_frame_hard_fails_on_missing_factor(self):
        from src.research_orchestrator.prescription_runtime import compute_factor_frame
        recipe = self._build_recipe()
        with self.assertRaises(KeyError) as ctx:
            compute_factor_frame(
                prescription=recipe,
                factor_series_map={"alpha_a": pd.Series(dtype=float)},  # missing alpha_b
            )
        self.assertIn("alpha_b", str(ctx.exception))

    def test_compute_composite_score_rank_weighted_with_direction(self):
        from src.research_orchestrator.prescription_runtime import compute_composite_score
        recipe = self._build_recipe()  # alpha_a higher_is_better, alpha_b lower_is_better
        frame = self._build_factor_frame()
        score = compute_composite_score(factor_frame=frame, prescription=recipe)
        # On 2024-01-02:
        #   alpha_a ranks: 1/3, 2/3, 3/3 (so 600519 highest)
        #   alpha_b ranks: 3/3, 2/3, 1/3 (so 000001 highest)
        #   With direction lower_is_better on alpha_b, sign=-1; weight=2.
        #   Composite for 600519: 1*1.0*1.0 + (-1)*1.0/3*2 = 1.0 - 0.667 = 0.333
        #   Composite for 000001: 1*1/3*1.0 + (-1)*1.0*2 = 0.333 - 2.0 = -1.667
        on_jan2 = score.xs(pd.Timestamp("2024-01-02"), level="datetime")
        # 600519 should rank higher than 000001 (direction was applied correctly)
        self.assertGreater(on_jan2.loc["600519_SH"], on_jan2.loc["000001_SZ"])

    def test_compute_composite_score_zscore_weighted(self):
        from src.research_orchestrator.prescription_runtime import compute_composite_score
        recipe = self._build_recipe(composite_kind="zscore_weighted")
        frame = self._build_factor_frame()
        score = compute_composite_score(factor_frame=frame, prescription=recipe)
        # Z-score should sum to ~0 within each date for symmetric inputs (alpha_a)
        # and direction-weighted contribution from alpha_b.
        on_jan2 = score.xs(pd.Timestamp("2024-01-02"), level="datetime")
        self.assertAlmostEqual(on_jan2.sum(), 0.0, places=6)

    def test_qlib_to_tushare_code_conversion(self):
        from src.research_orchestrator.prescription_runtime import _qlib_to_tushare_code
        self.assertEqual(_qlib_to_tushare_code("000001_SZ"), "000001.SZ")
        self.assertEqual(_qlib_to_tushare_code("000001_sz"), "000001.SZ")  # uppercase exchange
        self.assertEqual(_qlib_to_tushare_code("600519.SH"), "600519.SH")  # already Tushare-form

    def _build_feasible_topk2_recipe(self):
        """Recipe with portfolio caps that accommodate topk=2 + gross 1.0."""
        from src.research_orchestrator.hypothesis import PortfolioConstruction
        return self._build_recipe(
            topk=2,
            portfolio=PortfolioConstruction(
                weighting_rule="equal",
                side="long_only",
                target_gross_exposure=1.0,
                max_position_weight=0.6,  # 0.6 * 2 = 1.2 ≥ 1.0 ✓
                score_to_weight="topk_equal",
            ),
        )

    def test_compute_schedule_emits_topk_per_date_with_tushare_codes(self):
        from src.research_orchestrator.prescription_runtime import compute_schedule
        recipe = self._build_feasible_topk2_recipe()
        # Composite scores: 600519 > 000002 > 000001 on Jan 2; 000001 > 000002 > 600519 on Jan 9
        score = pd.Series(
            [0.1, 0.2, 0.3, 0.6, 0.5, 0.4],
            index=self._build_factor_frame().index,
            name="composite_score",
        )
        eligible_map = {
            pd.Timestamp("2024-01-02"): {"000001_SZ", "000002_SZ", "600519_SH"},
            pd.Timestamp("2024-01-09"): {"000001_SZ", "000002_SZ", "600519_SH"},
        }
        schedule = compute_schedule(
            composite_score=score,
            eligible_map=eligible_map,
            prescription=recipe,
        )
        # Per-name weight = 1.0 / 2 = 0.5; Jan 2 picks top 2: 600519, 000002.
        jan2 = schedule[schedule["datetime"] == pd.Timestamp("2024-01-02")]
        self.assertEqual(set(jan2["ts_code"]), {"600519.SH", "000002.SZ"})  # Tushare codes
        self.assertTrue((jan2["weight"] == 0.5).all())
        # Jan 9 picks top 2: 000001, 000002 (highest scores 0.6 and 0.5).
        jan9 = schedule[schedule["datetime"] == pd.Timestamp("2024-01-09")]
        self.assertEqual(set(jan9["ts_code"]), {"000001.SZ", "000002.SZ"})

    def test_compute_schedule_skips_dates_with_empty_eligibility(self):
        from src.research_orchestrator.prescription_runtime import compute_schedule
        recipe = self._build_feasible_topk2_recipe()
        score = pd.Series(
            [0.1, 0.2, 0.3],
            index=pd.MultiIndex.from_tuples(
                [(pd.Timestamp("2024-01-02"), c) for c in ["000001_SZ", "000002_SZ", "600519_SH"]],
                names=["datetime", "instrument"],
            ),
        )
        # Empty eligibility for Jan 2 → no rows emitted
        schedule = compute_schedule(
            composite_score=score,
            eligible_map={pd.Timestamp("2024-01-02"): set()},
            prescription=recipe,
        )
        self.assertEqual(len(schedule), 0)

    def test_materialize_universe_dispatches_theme_vs_broad(self):
        """Smoke test the dispatch logic routes to theme_resolver vs
        broad_filters correctly. The actual eligibility computation is
        delegated to build_universe_eligibility (already covered by
        theme_strategy tests)."""
        from src.research_orchestrator.prescription_runtime import materialize_universe
        from src.research_orchestrator.hypothesis import UniverseSpec
        from src.alpha_research.theme_strategy.schema import UniverseCandidate
        from src.alpha_research.theme_strategy import pipeline as ts_pipeline

        called_with = {}
        def fake_build(*, raw_fields, support, universe, rebal_dates, listing_days_ok):
            called_with["candidate_id"] = universe.candidate_id
            return {pd.Timestamp("2024-01-02"): set()}

        broad = UniverseCandidate(
            candidate_id="my_broad",
            membership_source="all_market",
            board_policy="mainboard",
            st_mode="exclude",
            min_listing_days=250,
        )
        original = ts_pipeline.build_universe_eligibility
        try:
            ts_pipeline.build_universe_eligibility = fake_build
            out = materialize_universe(
                universe=UniverseSpec(kind="broad", broad_filters=broad),
                raw_fields={},
                support=None,
                rebal_dates=[pd.Timestamp("2024-01-02")],
                listing_days_ok=lambda c, d: True,
            )
        finally:
            ts_pipeline.build_universe_eligibility = original

        self.assertEqual(called_with["candidate_id"], "my_broad")
        self.assertEqual(out, {pd.Timestamp("2024-01-02"): set()})

    def test_materialize_universe_kind_theme_requires_resolver(self):
        from src.research_orchestrator.prescription_runtime import materialize_universe
        from src.research_orchestrator.hypothesis import UniverseSpec
        spec = UniverseSpec(kind="theme", theme_id="growth", theme_universe_candidate_id="gr_u5")
        with self.assertRaises(ValueError) as ctx:
            materialize_universe(
                universe=spec, raw_fields={}, support=None,
                rebal_dates=[pd.Timestamp("2024-01-02")],
                listing_days_ok=lambda c, d: True,
                theme_resolver=None,
            )
        self.assertIn("theme_resolver", str(ctx.exception))


class MetricsFromEventReportCostKwargTests(unittest.TestCase):
    """Gate D.0 regression (jolly-seeking-lollipop): _metrics_from_event_report
    must accept cost_bps_per_unit_turnover and thread it through to
    cost_adjusted_sharpe. Also: handle_gate_review must read cost from
    hypothesis.prescription.cost_model.slippage_bps when present.
    """

    def _build_report(self):
        # 60 daily rows: gross 0.001/day, cost 0.0001, turnover 0.05/day.
        n = 60
        return pd.DataFrame({
            "return": [0.001] * n,
            "cost": [0.0001] * n,
            "turnover": [0.05] * n,
        })

    def test_default_cost_kwarg_matches_legacy_behavior(self):
        from src.research_orchestrator.steps import _metrics_from_event_report
        # Legacy default of 10.0 must still work.
        out = _metrics_from_event_report(self._build_report())
        self.assertEqual(out["cost_bps_per_unit_turnover"], 10.0)
        self.assertIsNotNone(out["cost_adjusted_sharpe"])

    def test_explicit_cost_kwarg_changes_cost_adjusted_sharpe(self):
        from src.research_orchestrator.steps import _metrics_from_event_report
        report = self._build_report()
        low = _metrics_from_event_report(report, cost_bps_per_unit_turnover=5.0)
        mid = _metrics_from_event_report(report, cost_bps_per_unit_turnover=10.0)
        # Same metric structure each time, but cost_bps echo + numeric differ.
        self.assertEqual(low["cost_bps_per_unit_turnover"], 5.0)
        self.assertEqual(mid["cost_bps_per_unit_turnover"], 10.0)
        # Smoking gun: the kwarg actually flowed through (different costs →
        # different cost_adjusted_sharpe values, not None and not equal).
        self.assertIsNotNone(low["cost_adjusted_sharpe"])
        self.assertIsNotNone(mid["cost_adjusted_sharpe"])
        self.assertNotEqual(low["cost_adjusted_sharpe"], mid["cost_adjusted_sharpe"])

    def test_handle_gate_review_reads_cost_from_prescription(self):
        """Source-inspection check that handle_gate_review reads from
        hypothesis.prescription.cost_model.slippage_bps. Avoids the heavy
        fixture setup needed to actually invoke the handler."""
        import inspect
        from src.research_orchestrator import steps
        src = inspect.getsource(steps.handle_gate_review)
        self.assertIn("hypothesis.prescription.cost_model.slippage_bps", src)


class ValidationObjectResolverTests(unittest.TestCase):
    """Gate D.1 regression: handle_validation_object_resolver derives consumes
    from prescription, runs ResolverHub, post-filters by source_layer, emits
    `registry_resolution` outputs (so runtime.py:407 lifts lineage), and
    hard-fails on unresolvable / candidate-only-without-opt-in components.
    """

    def _build_recipe(self, *, allow_candidate=False):
        from src.research_orchestrator.hypothesis import (
            UniverseSpec, PrescribedComponent, PrescribedRecipe, PortfolioConstruction,
        )
        from src.alpha_research.theme_strategy.schema import UniverseCandidate
        return PrescribedRecipe(
            universe=UniverseSpec(kind="broad", broad_filters=UniverseCandidate(
                candidate_id="t", membership_source="all_market",
                board_policy="mainboard", st_mode="exclude", min_listing_days=250,
            )),
            components=(
                PrescribedComponent(factor_name="alpha_a", weight=1.0),
                PrescribedComponent(factor_name="alpha_b", weight=1.0),
            ),
            composite_kind="rank_weighted",
            topk=10,
            rebalance_days=5,
            portfolio=PortfolioConstruction(
                target_gross_exposure=1.0, max_position_weight=0.20,
            ),
            allow_candidate_components=allow_candidate,
        )

    def _build_context(self, *, allow_candidate=False, mock_resolution=None):
        """Build a fake StepExecutionContext for the validation_object_resolver
        handler. Patches ResolverHub.resolve_assets to return mock_resolution."""
        from src.research_orchestrator.hypothesis import Hypothesis
        h = build_hypothesis()
        h_with = Hypothesis.from_dict({
            **h.to_dict(),
            "prescription": self._build_recipe(allow_candidate=allow_candidate).to_dict(),
        })
        from src.research_orchestrator.dag import StepExecutionContext, DagStepSpec, CompiledResearchDag
        # Reuse the registered hypothesis_validation profile for the context.
        from src.research_orchestrator.engine import profile_registry
        profile = profile_registry().get("hypothesis_validation")
        # build_request defaults to factor_screening; rebuild with the right profile.
        from src.research_orchestrator.schema import ResearchRequest
        request = ResearchRequest(
            profile_id="hypothesis_validation",
            mode="formal",
            consumes=[],
            produces=[],
            requested_capabilities=[],
            inputs={"output_dir": str((WORKSPACE_OUTPUTS / "validation_resolver_request").resolve())},
            run_context={},
            hypothesis=h_with,
        )
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        run_dir = (WORKSPACE_OUTPUTS / f"validation_resolver_test_{uuid.uuid4().hex[:8]}").resolve()
        step_dir = run_dir / "steps" / "validation_object_resolver"
        step_dir.mkdir(parents=True, exist_ok=True)
        step = DagStepSpec(
            step_id="validation_object_resolver",
            capability="object_resolver",
            handler="validation_object_resolver",
            depends_on=(),
            description="test",
            config={},
        )
        dag = CompiledResearchDag(
            profile_id="hypothesis_validation",
            run_dir=str(run_dir),
            steps=(step,),
        )
        context = StepExecutionContext(
            request=request,
            profile=profile,
            dag=dag,
            step=step,
            step_dir=step_dir,
            run_dir=run_dir,
            registry_dirs={
                "factor_registry_dir": str(run_dir / "factor_registry"),
                "candidate_registry_dir": str(run_dir / "candidate_registry"),
                "signal_registry_dir": str(run_dir / "signal_registry"),
                "model_registry_dir": str(run_dir / "model_registry"),
                "strategy_registry_dir": str(run_dir / "strategy_registry"),
                "testing_ledger_dir": str(run_dir / "testing_ledger"),
                "holdout_seal_dir": str(run_dir / "holdout_seals"),
                "hypothesis_registry_dir": str(run_dir / "hypothesis_registry"),
            },
            effective_capabilities=[],
            effective_capability_metadata=[],
            state={},
            resumed=False,
        )
        return context, run_dir

    def _patch_resolver(self, mock_resolution):
        """Context manager that patches ResolverHub.resolve_assets."""
        from src.research_orchestrator import resolver as resolver_mod
        return patch.object(resolver_mod.ResolverHub, "resolve_assets",
                            return_value=mock_resolution)

    def test_resolves_formal_factors_and_emits_registry_resolution(self):
        from src.research_orchestrator.validation_steps import handle_validation_object_resolver
        ctx, run_dir = self._build_context()
        try:
            mock_resolution = {
                "formal_hits": 2, "candidate_hits": 0, "new_objects_created": 0,
                "unresolved_objects": [],
                "resolved_objects": [
                    {"requested": {"object_type": "factor", "object_name": "alpha_a"},
                     "status": "resolved", "source_layer": "formal",
                     "object_type": "factor", "canonical_id": "alpha_a"},
                    {"requested": {"object_type": "factor", "object_name": "alpha_b"},
                     "status": "resolved", "source_layer": "formal",
                     "object_type": "factor", "canonical_id": "alpha_b"},
                ],
            }
            # alpha_a/alpha_b are synthetic resolver fixtures (not catalog factors),
            # so patch the PR9 field-dependency gate here to isolate the resolver
            # handler's emission logic. The field gate itself is covered in
            # tests/research_orchestrator/test_pr9_validation_field_gate.py.
            # The P1.3 drift gate is likewise isolated (synthetic alpha_a/alpha_b have
            # no definition_hash); it is covered by TestPR13DefinitionBindingGate.
            with self._patch_resolver(mock_resolution), patch(
                "src.research_orchestrator.validation_steps._validate_factor_field_dependencies",
                return_value={"eligible": True, "disallowed_fields": [], "unknown_fields": [], "reasons": []},
            ), patch(
                "src.research_orchestrator.validation_steps._assert_no_definition_drift",
                return_value={"checked": 0, "drifted": [], "stage": "formal_validation"},
            ):
                result = handle_validation_object_resolver(ctx)
            self.assertEqual(result.status, "completed")
            # The registry_resolution key must be emitted (runtime.py:407 reads it).
            self.assertIn("registry_resolution", result.outputs)
            self.assertEqual(result.outputs["registry_resolution"]["formal_hits"], 2)
            # consumes must be derived from prescription.components
            self.assertEqual(len(result.outputs["consumes"]), 2)
            names = {c["object_name"] for c in result.outputs["consumes"]}
            self.assertEqual(names, {"alpha_a", "alpha_b"})
            # Artifact written
            self.assertTrue((ctx.step_dir / "registry_resolution.json").exists())
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_hard_fails_on_unresolvable_factor(self):
        from src.research_orchestrator.validation_steps import handle_validation_object_resolver
        ctx, run_dir = self._build_context()
        try:
            mock_resolution = {
                "formal_hits": 1, "candidate_hits": 0, "new_objects_created": 0,
                "unresolved_objects": [
                    {"requested": {"object_type": "factor", "object_name": "alpha_b"},
                     "status": "unresolved"},
                ],
                "resolved_objects": [
                    {"requested": {"object_type": "factor", "object_name": "alpha_a"},
                     "status": "resolved", "source_layer": "formal",
                     "object_type": "factor", "canonical_id": "alpha_a"},
                    {"requested": {"object_type": "factor", "object_name": "alpha_b"},
                     "status": "unresolved"},
                ],
            }
            with self._patch_resolver(mock_resolution):
                with self.assertRaises(ValueError) as cm:
                    handle_validation_object_resolver(ctx)
            self.assertIn("alpha_b", str(cm.exception))
            self.assertIn("factor_registry", str(cm.exception))
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_rejects_candidate_only_without_opt_in(self):
        from src.research_orchestrator.validation_steps import handle_validation_object_resolver
        ctx, run_dir = self._build_context(allow_candidate=False)
        try:
            mock_resolution = {
                "formal_hits": 1, "candidate_hits": 1, "new_objects_created": 0,
                "unresolved_objects": [],
                "resolved_objects": [
                    {"requested": {"object_type": "factor", "object_name": "alpha_a"},
                     "status": "resolved", "source_layer": "formal",
                     "object_type": "factor", "canonical_id": "alpha_a"},
                    {"requested": {"object_type": "factor", "object_name": "alpha_b"},
                     "status": "resolved", "source_layer": "candidate",
                     "object_type": "factor", "canonical_id": "alpha_b_cand"},
                ],
            }
            with self._patch_resolver(mock_resolution):
                with self.assertRaises(ValueError) as cm:
                    handle_validation_object_resolver(ctx)
            self.assertIn("alpha_b", str(cm.exception))
            self.assertIn("allow_candidate_components", str(cm.exception))
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_accepts_candidate_when_opt_in_set(self):
        # PR P1.2 (Codex round-5): allow_candidate_components admits the
        # factor_registry_candidate layer (candidate-STATUS factors in the formal
        # factor registry), NOT the separate candidate-registry "candidate" layer.
        # v1.4 A7: the flag alone no longer admits — each candidate needs target-scoped
        # Stage-5 evidence (candidate_on_declared_target), so this positive test seeds
        # eligible Stage-3 records bound to the prescription's derived TUD.
        from src.research_orchestrator.validation_steps import handle_validation_object_resolver
        ctx, run_dir = self._build_context(allow_candidate=True)
        try:
            from src.alpha_research.factor_eval_skill.candidate_scope import (
                tud_from_prescription_universe,
            )
            from src.alpha_research.factor_eval_skill.stores import Stage3QualityRecordStore

            tud = tud_from_prescription_universe(ctx.request.hypothesis.prescription.universe)
            stage3 = Stage3QualityRecordStore(run_dir / "factor_eval_skill")
            for name in ("alpha_a", "alpha_b"):
                stage3.record(
                    factor_id=name, definition_hash=f"dh_{name}",
                    layer1_methodology_hash="l1_test",
                    target_universe_declaration_hash=tud.tud_hash, role="ranking",
                    quality_flags_json="{}", universe_profile_json="{}",
                    target_universe_pass="True", cross_universe_sign_divergence="False",
                    status_effect="candidate_ceiling",
                )
            mock_resolution = {
                "formal_hits": 0, "candidate_hits": 2, "new_objects_created": 0,
                "unresolved_objects": [],
                "resolved_objects": [
                    {"requested": {"object_type": "factor", "object_name": "alpha_a"},
                     "status": "resolved", "source_layer": "factor_registry_candidate",
                     "object_type": "factor", "canonical_id": "alpha_a",
                     "definition_hash": "dh_alpha_a"},
                    {"requested": {"object_type": "factor", "object_name": "alpha_b"},
                     "status": "resolved", "source_layer": "factor_registry_candidate",
                     "object_type": "factor", "canonical_id": "alpha_b",
                     "definition_hash": "dh_alpha_b"},
                ],
            }
            # Field gate patched (alpha_a/alpha_b are synthetic fixtures) — see
            # test_resolves_formal_factors_and_emits_registry_resolution.
            with self._patch_resolver(mock_resolution), patch(
                "src.research_orchestrator.validation_steps._validate_factor_field_dependencies",
                return_value={"eligible": True, "disallowed_fields": [], "unknown_fields": [], "reasons": []},
            ), patch(
                "src.research_orchestrator.validation_steps._assert_no_definition_drift",
                return_value={"checked": 0, "drifted": [], "stage": "formal_validation"},
            ):
                result = handle_validation_object_resolver(ctx)
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.outputs["registry_resolution"]["candidate_hits"], 2)
            # v1.4 A7: the target-scope admission is recorded on the artifact.
            scope_report = result.outputs["candidate_scope_report"]
            self.assertEqual(scope_report["mismatches"], [])
            self.assertEqual(len(scope_report["checked"]), 2)
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)


class ComputeExtendedMetricsTests(unittest.TestCase):
    """Gate D.3 regression: _compute_extended_metrics must populate the FULL
    SuccessCriteria-required metric set (not the 3-key subset the existing
    theme_strategy branch returns). Validates that rank_ic / rank_icir /
    monotonicity_pvalue / sharpe / cost_adjusted_sharpe / etc. all appear,
    and that correlation_to_approved is the v1 stub flagged in metrics.json.
    """

    def _build_event_report(self, n=60):
        import numpy as np
        return pd.DataFrame({
            "return": np.random.RandomState(0).normal(0.001, 0.01, n),
            "cost": [0.0001] * n,
            "turnover": [0.05] * n,
        })

    def _build_signal_and_returns(self, n_dates=20, n_stocks=10):
        import numpy as np
        rng = np.random.RandomState(0)
        dates = pd.date_range("2024-01-02", periods=n_dates, freq="B")
        stocks = [f"00000{i}_SZ" for i in range(n_stocks)]
        idx = pd.MultiIndex.from_product([dates, stocks], names=["datetime", "instrument"])
        signal = pd.Series(rng.normal(0, 1, len(idx)), index=idx)
        # Forward returns weakly correlated with signal.
        fwd = pd.Series(0.7 * signal.values + 0.3 * rng.normal(0, 1, len(idx)), index=idx)
        return signal, fwd

    def test_returns_full_metric_set(self):
        from src.research_orchestrator.validation_steps import _compute_extended_metrics
        signal, fwd = self._build_signal_and_returns()
        metrics = _compute_extended_metrics(
            event_report=self._build_event_report(),
            composite_signal=signal,
            forward_returns=fwd,
            cost_bps_per_unit_turnover=10.0,
        )
        # Must populate ALL keys SuccessCriteria reads (Codex round-1 finding).
        for key in (
            "sharpe", "deflated_sharpe", "cost_adjusted_sharpe",
            "max_drawdown", "annual_turnover", "regime_pass_count",
            "rank_ic", "rank_icir", "monotonicity_pvalue",
            "correlation_to_approved",
        ):
            self.assertIn(key, metrics)
        # correlation_to_approved is a v1 stub — must be flagged so reviewers
        # know the rule was passed by default.
        self.assertEqual(metrics["correlation_to_approved"], 0.0)
        self.assertTrue(metrics.get("correlation_to_approved_is_stub"))

    def test_cost_bps_threads_through(self):
        """The slippage_bps parameter from prescription must reach
        _metrics_from_event_report's cost_bps_per_unit_turnover (Codex round-3
        regression on testing-ledger consistency)."""
        from src.research_orchestrator.validation_steps import _compute_extended_metrics
        signal, fwd = self._build_signal_and_returns()
        report = self._build_event_report()
        m_low = _compute_extended_metrics(
            event_report=report, composite_signal=signal, forward_returns=fwd,
            cost_bps_per_unit_turnover=5.0,
        )
        m_high = _compute_extended_metrics(
            event_report=report, composite_signal=signal, forward_returns=fwd,
            cost_bps_per_unit_turnover=20.0,
        )
        self.assertEqual(m_low["cost_bps_per_unit_turnover"], 5.0)
        self.assertEqual(m_high["cost_bps_per_unit_turnover"], 20.0)


class CollectMeasuredValuesValidationBranchTests(unittest.TestCase):
    """Gate D.3 regression: _collect_measured_values must read the validation
    profile's metrics.json from the appropriate IS or OOS diagnostics step."""

    def test_validation_branch_source_inspection(self):
        """Source-level check that the new branch exists + reads from
        validation_diagnostics_{is,oos}/metrics.json based on stage."""
        import inspect
        from src.research_orchestrator import steps
        src = inspect.getsource(steps._collect_measured_values)
        self.assertIn("hypothesis_validation", src)
        self.assertIn("validation_diagnostics_is", src)
        self.assertIn("validation_diagnostics_oos", src)
        self.assertIn("metrics.json", src)


class EnginePerformanceDiagnosticsLookupTests(unittest.TestCase):
    """Gate D.3 regression: ResearchRunResult.outputs collection must look at
    BOTH the legacy 'performance_diagnostics' step name AND the renamed
    'validation_diagnostics_is/oos' step names (Codex round-2 finding)."""

    def test_engine_collects_validation_diagnostics_step_names(self):
        import inspect
        from src.research_orchestrator import engine
        src = inspect.getsource(engine.run_research)
        # Both legacy + new step names must be referenced near the
        # diagnostics_outputs assembly.
        self.assertIn("performance_diagnostics", src)
        self.assertIn("validation_diagnostics_oos", src)
        self.assertIn("validation_diagnostics_is", src)


class ValidationOOSEventBacktestSkipTests(unittest.TestCase):
    """Gate E regression: handle_validation_event_backtest_oos must read the
    upstream IS gate decision and short-circuit (NOT claim a seal, NOT call
    EventDrivenBacktester) when the IS gate decision is anything other than
    'approved'. The skip writes step_outputs.json with
    {'decision': 'skipped_due_to_is_gate', ...} — NORMAL step outputs, NOT
    a fake gate_decision.json (Codex round-3 + round-4).
    """

    def _build_context(self, *, is_decision: str, run_dir_name: str = "oos_skip_test"):
        from src.research_orchestrator.hypothesis import (
            Hypothesis, UniverseSpec, PrescribedComponent, PrescribedRecipe,
            PortfolioConstruction,
        )
        from src.alpha_research.theme_strategy.schema import UniverseCandidate
        from src.research_orchestrator.dag import (
            StepExecutionContext, DagStepSpec, CompiledResearchDag,
        )
        from src.research_orchestrator.engine import profile_registry
        from src.research_orchestrator.schema import ResearchRequest

        recipe = PrescribedRecipe(
            universe=UniverseSpec(kind="broad", broad_filters=UniverseCandidate(
                candidate_id="t", membership_source="all_market",
                board_policy="mainboard", st_mode="exclude", min_listing_days=250,
            )),
            components=(PrescribedComponent(factor_name="alpha_a", weight=1.0),),
            composite_kind="rank_weighted",
            topk=10,
            rebalance_days=5,
            portfolio=PortfolioConstruction(target_gross_exposure=1.0, max_position_weight=0.20),
            # R4-M2: the pin must survive to_dict/from_dict (exercises the
            # round-trip path formal request files take).
            calendar_policy_id="frozen_20260227_system_build",
        )
        h = build_hypothesis()
        h_with = Hypothesis.from_dict({**h.to_dict(), "prescription": recipe.to_dict()})

        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        run_dir = (WORKSPACE_OUTPUTS / f"{run_dir_name}_{uuid.uuid4().hex[:8]}").resolve()
        step_dir = run_dir / "steps" / "validation_event_backtest_oos"
        step_dir.mkdir(parents=True, exist_ok=True)

        request = ResearchRequest(
            profile_id="hypothesis_validation",
            mode="formal",
            consumes=[],
            produces=[],
            requested_capabilities=[],
            inputs={"output_dir": str(run_dir)},
            run_context={},
            hypothesis=h_with,
        )
        step = DagStepSpec(
            step_id="validation_event_backtest_oos",
            capability="event_driven_backtest",
            handler="validation_event_backtest_oos",
            depends_on=("validation_gate_review_is",),
            description="oos test",
            config={"stage": "oos_test"},
        )
        dag = CompiledResearchDag(
            profile_id="hypothesis_validation",
            run_dir=str(run_dir),
            steps=(step,),
        )
        context = StepExecutionContext(
            request=request,
            profile=profile_registry().get("hypothesis_validation"),
            dag=dag,
            step=step,
            step_dir=step_dir,
            run_dir=run_dir,
            registry_dirs={
                "factor_registry_dir": str(run_dir / "factor_registry"),
                "candidate_registry_dir": str(run_dir / "candidate_registry"),
                "signal_registry_dir": str(run_dir / "signal_registry"),
                "model_registry_dir": str(run_dir / "model_registry"),
                "strategy_registry_dir": str(run_dir / "strategy_registry"),
                "testing_ledger_dir": str(run_dir / "testing_ledger"),
                "holdout_seal_dir": str(run_dir / "holdout_seals"),
                "hypothesis_registry_dir": str(run_dir / "hypothesis_registry"),
            },
            effective_capabilities=[],
            effective_capability_metadata=[],
            state={
                "step_outputs": {
                    "validation_gate_review_is": {"decision": is_decision},
                },
            },
            resumed=False,
        )
        return context, run_dir

    def test_oos_skips_when_is_gate_rejected(self):
        from src.research_orchestrator.validation_steps import handle_validation_event_backtest_oos
        ctx, run_dir = self._build_context(is_decision="rejected")
        try:
            result = handle_validation_event_backtest_oos(ctx)
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.outputs["decision"], "skipped_due_to_is_gate")
            self.assertTrue(result.outputs["skipped"])
            self.assertEqual(result.outputs["reason"], "IS gate decision was 'rejected'")
            # NORMAL step output, not a fake gate_decision.json (Codex round-3).
            self.assertTrue((ctx.step_dir / "step_outputs.json").exists())
            self.assertFalse((ctx.step_dir / "gate_decision.json").exists())
            # No event_driven_report.csv → confirms backtester was NOT called.
            self.assertFalse((ctx.step_dir / "event_driven_report.csv").exists())
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_oos_skips_when_is_gate_quarantined(self):
        from src.research_orchestrator.validation_steps import handle_validation_event_backtest_oos
        ctx, run_dir = self._build_context(is_decision="quarantined")
        try:
            result = handle_validation_event_backtest_oos(ctx)
            self.assertEqual(result.outputs["decision"], "skipped_due_to_is_gate")
            self.assertTrue(result.outputs["skipped"])
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_oos_skips_when_is_gate_missing(self):
        from src.research_orchestrator.validation_steps import handle_validation_event_backtest_oos
        ctx, run_dir = self._build_context(is_decision="")  # no recorded decision
        try:
            result = handle_validation_event_backtest_oos(ctx)
            self.assertEqual(result.outputs["decision"], "skipped_due_to_is_gate")
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_oos_proceeds_to_backtest_when_is_gate_approved(self):
        """When IS gate is approved, the handler must NOT short-circuit and
        must invoke run_event_driven_window with the OOS time_split + the
        holdout_context built from hypothesis.design_hash. We patch
        run_event_driven_window so the test doesn't need real Qlib data."""
        from src.research_orchestrator.validation_steps import (
            handle_validation_event_backtest_oos,
        )

        ctx, run_dir = self._build_context(is_decision="approved")
        try:
            # Pre-create the schedule artifact the handler reads.
            pc_dir = run_dir / "steps" / "validation_portfolio_construction"
            pc_dir.mkdir(parents=True, exist_ok=True)
            schedule_df = pd.DataFrame({
                "datetime": [pd.Timestamp("2023-01-03")],
                "ts_code": ["000001.SZ"],
                "weight": [1.0],
            })
            schedule_df.to_parquet(pc_dir / "target_weights_schedule.parquet")

            captured = {}

            def fake_run_event_driven_window(*, schedule, start, end, benchmark, capital,
                                              slippage_rate, exchange_config, time_split,
                                              holdout_context, **_kwargs):
                captured["start"] = start
                captured["end"] = end
                captured["time_split_stage"] = (time_split or {}).get("stage")
                captured["holdout_context_design_hash"] = (
                    holdout_context.design_hash if holdout_context is not None else None
                )
                # Return a minimal result-like object.
                from types import SimpleNamespace
                return SimpleNamespace(
                    report=pd.DataFrame({"return": [0.001, 0.002], "cost": [0.0, 0.0], "turnover": [0.0, 0.0]}),
                    trades=pd.DataFrame(),
                    summary={"oos_smoke": True},
                )

            with patch(
                "workspace.research.alpha_mining.event_driven_strategy_research.run_event_driven_window",
                fake_run_event_driven_window,
            ):
                result = handle_validation_event_backtest_oos(ctx)

            self.assertEqual(result.status, "completed")
            # Verify the OOS window was used (not IS dates).
            self.assertEqual(captured["start"], ctx.request.hypothesis.time_split.oos_start)
            self.assertEqual(captured["end"], ctx.request.hypothesis.time_split.oos_end)
            # Verify time_split.stage was 'oos_test' (so SealedBacktestRunner
            # claims the seal).
            self.assertEqual(captured["time_split_stage"], "oos_test")
            # Verify the holdout_context carries the prescription's design_hash.
            self.assertEqual(
                captured["holdout_context_design_hash"],
                ctx.request.hypothesis.design_hash(),
            )
            # Confirm artifacts written.
            self.assertTrue((ctx.step_dir / "event_driven_report.csv").exists())
            self.assertTrue((ctx.step_dir / "event_driven_summary.json").exists())
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)


class ValidationOOSGateWrappersTests(unittest.TestCase):
    """Gate F regression: the three OOS gate wrappers
    (handle_validation_gate_eval_oos / _gate_concerns_oos / _gate_review_oos)
    must skip-then-delegate based on the upstream IS gate decision. On skip
    they emit NORMAL step outputs with decision='skipped_due_to_is_gate'.
    On delegation they call into the shared handle_gate_* handlers.
    """

    def _build_minimal_context(self, *, is_decision: str, step_id: str, capability: str):
        from src.research_orchestrator.hypothesis import (
            Hypothesis, UniverseSpec, PrescribedComponent, PrescribedRecipe,
            PortfolioConstruction,
        )
        from src.alpha_research.theme_strategy.schema import UniverseCandidate
        from src.research_orchestrator.dag import (
            StepExecutionContext, DagStepSpec, CompiledResearchDag,
        )
        from src.research_orchestrator.engine import profile_registry
        from src.research_orchestrator.schema import ResearchRequest

        recipe = PrescribedRecipe(
            universe=UniverseSpec(kind="broad", broad_filters=UniverseCandidate(
                candidate_id="t", membership_source="all_market",
                board_policy="mainboard", st_mode="exclude", min_listing_days=250,
            )),
            components=(PrescribedComponent(factor_name="alpha_a", weight=1.0),),
            composite_kind="rank_weighted",
            topk=10,
            rebalance_days=5,
            portfolio=PortfolioConstruction(target_gross_exposure=1.0, max_position_weight=0.20),
        )
        h_with = Hypothesis.from_dict({
            **build_hypothesis().to_dict(), "prescription": recipe.to_dict(),
        })
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        run_dir = (WORKSPACE_OUTPUTS / f"oos_wrap_{uuid.uuid4().hex[:8]}").resolve()
        step_dir = run_dir / "steps" / step_id
        step_dir.mkdir(parents=True, exist_ok=True)
        request = ResearchRequest(
            profile_id="hypothesis_validation", mode="formal",
            consumes=[], produces=[], requested_capabilities=[],
            inputs={"output_dir": str(run_dir)},
            run_context={}, hypothesis=h_with,
        )
        step = DagStepSpec(
            step_id=step_id, capability=capability, handler=step_id,
            depends_on=("validation_gate_review_is",), description="oos test",
            config={"stage": "oos_test"},
        )
        dag = CompiledResearchDag(
            profile_id="hypothesis_validation",
            run_dir=str(run_dir), steps=(step,),
        )
        ctx = StepExecutionContext(
            request=request, profile=profile_registry().get("hypothesis_validation"),
            dag=dag, step=step, step_dir=step_dir, run_dir=run_dir,
            registry_dirs={k: str(run_dir / k) for k in (
                "factor_registry_dir", "candidate_registry_dir", "signal_registry_dir",
                "model_registry_dir", "strategy_registry_dir", "testing_ledger_dir",
                "holdout_seal_dir", "hypothesis_registry_dir",
            )},
            effective_capabilities=[], effective_capability_metadata=[],
            state={"step_outputs": {"validation_gate_review_is": {"decision": is_decision}}},
            resumed=False,
        )
        return ctx, run_dir

    def test_eval_oos_wrapper_skips_when_is_rejected(self):
        from src.research_orchestrator.validation_steps import handle_validation_gate_eval_oos
        ctx, run_dir = self._build_minimal_context(
            is_decision="rejected", step_id="validation_gate_eval_oos",
            capability="gate_evaluation",
        )
        try:
            result = handle_validation_gate_eval_oos(ctx)
            self.assertEqual(result.outputs["decision"], "skipped_due_to_is_gate")
            self.assertTrue((ctx.step_dir / "step_outputs.json").exists())
            # No fake gate_decision.json (Codex round-3 + round-4 must-fix #2)
            self.assertFalse((ctx.step_dir / "gate_decision.json").exists())
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_concerns_oos_wrapper_skips_when_is_quarantined(self):
        from src.research_orchestrator.validation_steps import handle_validation_gate_concerns_oos
        ctx, run_dir = self._build_minimal_context(
            is_decision="quarantined", step_id="validation_gate_concerns_oos",
            capability="gate_concern_scoring",
        )
        try:
            result = handle_validation_gate_concerns_oos(ctx)
            self.assertEqual(result.outputs["decision"], "skipped_due_to_is_gate")
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_review_oos_wrapper_skips_when_is_missing(self):
        from src.research_orchestrator.validation_steps import handle_validation_gate_review_oos
        ctx, run_dir = self._build_minimal_context(
            is_decision="", step_id="validation_gate_review_oos",
            capability="gate_review",
        )
        try:
            result = handle_validation_gate_review_oos(ctx)
            self.assertEqual(result.outputs["decision"], "skipped_due_to_is_gate")
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_review_oos_wrapper_delegates_when_is_approved(self):
        """When IS approved, the wrapper must call handle_gate_review (NOT skip).
        We verify by patching handle_gate_review to a sentinel."""
        import src.research_orchestrator.validation_steps as vmod
        from src.research_orchestrator.dag import StepExecutionResult

        called = {"count": 0}
        def fake_review(context):
            called["count"] += 1
            return StepExecutionResult(status="completed", outputs={"decision": "approved"})

        ctx, run_dir = self._build_minimal_context(
            is_decision="approved", step_id="validation_gate_review_oos",
            capability="gate_review",
        )
        try:
            with patch("src.research_orchestrator.steps.handle_gate_review", fake_review):
                vmod.handle_validation_gate_review_oos(ctx)
            self.assertEqual(called["count"], 1)
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)


class ValidationRegistryPublishPolicyTests(unittest.TestCase):
    """Gate F regression: handle_validation_registry_publish enforces the
    direct decision matrix (Codex round-3 critical) — does NOT rely on
    _assert_gate_allows_publication, which falls through on unknown decisions.
    """

    def _build_publish_context(self, *, oos_decision: str):
        from src.research_orchestrator.hypothesis import (
            Hypothesis, UniverseSpec, PrescribedComponent, PrescribedRecipe,
            PortfolioConstruction,
        )
        from src.alpha_research.theme_strategy.schema import UniverseCandidate
        from src.research_orchestrator.dag import (
            StepExecutionContext, DagStepSpec, CompiledResearchDag,
        )
        from src.research_orchestrator.engine import profile_registry
        from src.research_orchestrator.schema import ResearchRequest

        recipe = PrescribedRecipe(
            universe=UniverseSpec(kind="broad", broad_filters=UniverseCandidate(
                candidate_id="t", membership_source="all_market",
                board_policy="mainboard", st_mode="exclude", min_listing_days=250,
            )),
            components=(PrescribedComponent(factor_name="alpha_a", weight=1.0),),
            composite_kind="rank_weighted",
            topk=10, rebalance_days=5,
            portfolio=PortfolioConstruction(target_gross_exposure=1.0, max_position_weight=0.20),
        )
        h_with = Hypothesis.from_dict({
            **build_hypothesis().to_dict(), "prescription": recipe.to_dict(),
        })
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        run_dir = (WORKSPACE_OUTPUTS / f"publish_{uuid.uuid4().hex[:8]}").resolve()
        step_dir = run_dir / "steps" / "validation_registry_publish"
        step_dir.mkdir(parents=True, exist_ok=True)
        request = ResearchRequest(
            profile_id="hypothesis_validation", mode="formal",
            consumes=[], produces=[], requested_capabilities=[],
            inputs={"output_dir": str(run_dir)},
            run_context={}, hypothesis=h_with,
        )
        step = DagStepSpec(
            step_id="validation_registry_publish", capability="registry_publish",
            handler="validation_registry_publish",
            depends_on=("validation_gate_review_oos",),
            description="publish", config={},
        )
        dag = CompiledResearchDag(
            profile_id="hypothesis_validation", run_dir=str(run_dir), steps=(step,),
        )
        ctx = StepExecutionContext(
            request=request, profile=profile_registry().get("hypothesis_validation"),
            dag=dag, step=step, step_dir=step_dir, run_dir=run_dir,
            registry_dirs={k: str(run_dir / k) for k in (
                "factor_registry_dir", "candidate_registry_dir", "signal_registry_dir",
                "model_registry_dir", "strategy_registry_dir", "testing_ledger_dir",
                "holdout_seal_dir", "hypothesis_registry_dir",
            )},
            effective_capabilities=[], effective_capability_metadata=[],
            state={"step_outputs": {"validation_gate_review_oos": {"decision": oos_decision}}},
            resumed=False,
        )
        return ctx, run_dir

    def test_approved_publishes(self):
        from src.research_orchestrator.validation_steps import handle_validation_registry_publish
        ctx, run_dir = self._build_publish_context(oos_decision="approved")
        try:
            result = handle_validation_registry_publish(ctx)
            self.assertTrue(result.outputs["published"])
            self.assertEqual(result.outputs["publish_status_override"], "")
            self.assertTrue((ctx.step_dir / "publish_record.json").exists())
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_quarantined_publishes_under_review(self):
        from src.research_orchestrator.validation_steps import handle_validation_registry_publish
        ctx, run_dir = self._build_publish_context(oos_decision="quarantined")
        try:
            result = handle_validation_registry_publish(ctx)
            self.assertTrue(result.outputs["published"])
            self.assertEqual(result.outputs["publish_status_override"], "under_review")
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_rejected_no_publish(self):
        from src.research_orchestrator.validation_steps import handle_validation_registry_publish
        ctx, run_dir = self._build_publish_context(oos_decision="rejected")
        try:
            result = handle_validation_registry_publish(ctx)
            self.assertTrue(result.outputs["skipped"])
            self.assertNotIn("published", result.outputs)
            self.assertFalse((ctx.step_dir / "publish_record.json").exists())
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_skipped_due_to_is_gate_no_publish(self):
        from src.research_orchestrator.validation_steps import handle_validation_registry_publish
        ctx, run_dir = self._build_publish_context(oos_decision="skipped_due_to_is_gate")
        try:
            result = handle_validation_registry_publish(ctx)
            self.assertTrue(result.outputs["skipped"])
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_unknown_decision_fails_closed(self):
        """Codex round-3 critical: this is the bug _assert_gate_allows_publication
        had — it would fall through and silently allow publication on unknown
        decisions. Our direct policy MUST reject unknowns."""
        from src.research_orchestrator.validation_steps import handle_validation_registry_publish
        ctx, run_dir = self._build_publish_context(oos_decision="some_unknown_state")
        try:
            result = handle_validation_registry_publish(ctx)
            self.assertTrue(result.outputs["skipped"])
            self.assertTrue(result.summary.get("fail_closed"))
            self.assertFalse((ctx.step_dir / "publish_record.json").exists())
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)


class CLIProfileAwareRegistrationTests(unittest.TestCase):
    """Gate F: hypothesis_cli.py register --profile-id flag must validate
    floors against ONLY the targeted profile, not all profiles."""

    def test_register_signature_includes_profile_id_flag(self):
        import inspect
        import workspace.scripts.hypothesis_cli as cli
        src = inspect.getsource(cli)
        self.assertIn("--profile-id", src)
        self.assertIn("profile_filter", src)
        # Smoking gun: the conditional that limits validation to just the
        # named profile when the flag is set.
        self.assertIn("profiles_to_check = [profile_filter]", src)


class CLIVerifySealExpectClaimsTests(unittest.TestCase):
    """Gate F: verify-seal --expect-claims N flag — exact-count assertion."""

    def test_verify_seal_signature_includes_expect_claims(self):
        import inspect
        import workspace.scripts.hypothesis_cli as cli
        src = inspect.getsource(cli)
        self.assertIn("--expect-claims", src)
        self.assertIn("expect_claims", src)


class CLIScoreConcernsPreValidationTests(unittest.TestCase):
    """Discovered 2026-05-19 during P1 hyp_20260519_003 run: the score-concerns CLI
    schema-validated payloads but did NOT run the semantic checks the handler later
    runs (keyed_to_rule_id known, anchor metric present + numeric + matches measured,
    declared severity >= derived). A bad payload would slip through the CLI, then the
    handler would raise on resume, flipping the step status from paused → failed AND
    clearing pending_input — leaving no clean recovery path.

    These tests pin the CLI's _validate_concern_scores_against_rules helper so any
    future drift between the CLI guard and the handler check trips immediately.
    """

    def _rule(self, *, rule_id="min_rank_icir", metric="rank_icir", comparator=">=", threshold=1.0, actual=0.2, passed=False):
        return {
            "rule_id": rule_id,
            "rule": rule_id,
            "metric": metric,
            "comparator": comparator,
            "threshold": threshold,
            "actual": actual,
            "passed": passed,
            "is_hard": True,
        }

    def _score(self, **overrides):
        base = {
            "concern_id": "most_likely_failure_mode",
            "concern_text": "Example concern.",
            "keyed_to_rule_id": "min_rank_icir",
            "measured_evidence_against_concern": "x" * 100,
            "quantitative_anchor": {"rank_icir": 0.2},
            "confirmed": True,
            "severity": "high",
        }
        base.update(overrides)
        return base

    def test_pre_validation_rejects_unknown_rule_id(self):
        rule_by_id = {"min_rank_icir": self._rule()}
        payload = {"scores": [self._score(keyed_to_rule_id="does_not_exist")]}
        with self.assertRaises(ConcernEnforcementError):
            hypothesis_cli._validate_concern_scores_against_rules(
                payload, rule_by_id, {"rank_icir": 0.2}
            )

    def test_pre_validation_rejects_missing_anchor_metric(self):
        rule_by_id = {"min_rank_icir": self._rule()}
        payload = {"scores": [self._score(quantitative_anchor={"other_metric": 0.2})]}
        with self.assertRaises(ConcernEnforcementError):
            hypothesis_cli._validate_concern_scores_against_rules(
                payload, rule_by_id, {"rank_icir": 0.2}
            )

    def test_pre_validation_rejects_anchor_value_mismatch(self):
        rule_by_id = {"min_rank_icir": self._rule()}
        # measured value is 0.2 but anchor declares 0.5 → mismatch
        payload = {"scores": [self._score(quantitative_anchor={"rank_icir": 0.5})]}
        with self.assertRaises(ConcernEnforcementError):
            hypothesis_cli._validate_concern_scores_against_rules(
                payload, rule_by_id, {"rank_icir": 0.2}
            )

    def test_pre_validation_rejects_severity_below_derived(self):
        # rank_icir = 0.2 vs threshold 1.0 → derived severity is "high" (ratio 0.8 > 0.5).
        # Declared "low" or "medium" must fail.
        rule_by_id = {"min_rank_icir": self._rule()}
        payload = {"scores": [self._score(severity="low")]}
        with self.assertRaises(ConcernEnforcementError):
            hypothesis_cli._validate_concern_scores_against_rules(
                payload, rule_by_id, {"rank_icir": 0.2}
            )

    def test_pre_validation_passes_well_formed_payload(self):
        rule_by_id = {"min_rank_icir": self._rule()}
        payload = {"scores": [self._score()]}  # severity=high, anchor matches, rule known
        hypothesis_cli._validate_concern_scores_against_rules(
            payload, rule_by_id, {"rank_icir": 0.2}
        )  # must not raise

    def test_copy_and_validate_passes_through_when_rules_omitted(self):
        # Backwards-compat: callers that don't pass rule_by_id get schema-only check.
        # The schema requires exactly 4 scores (one per pre-registered concern_id);
        # this payload satisfies the schema but would fail the semantic check
        # (severity=low against rank_icir 0.2 vs threshold 1.0 → derived=high).
        # The point: omitting rule_by_id should SKIP that semantic check.
        import tempfile
        concern_ids = [
            "most_likely_failure_mode",
            "weakest_assumption",
            "what_would_falsify_this",
            "priors_on_cost_sensitivity",
        ]
        # Severity "low" — would be rejected by semantic check if rule_by_id were passed.
        bad_semantics_payload = {
            "scores": [self._score(concern_id=cid, severity="low") for cid in concern_ids]
        }
        with tempfile.TemporaryDirectory() as td:
            out = hypothesis_cli._copy_and_validate_concern_scores(
                Path(td), bad_semantics_payload
            )
            # No rule_by_id passed → no semantic check → write succeeds
            self.assertTrue(out.exists())


class RuntimeConcernScoringRecoveryTests(unittest.TestCase):
    """Discovered 2026-05-19 during P1 hyp_20260519_003 run: if the gate_concern_scoring
    handler raises ConcernEnforcementError on resume, the runtime's per-step exception
    handler flips status from paused → failed AND clears pause_kind / pending_input from
    both dag_state.json and step_metadata.json. The next resume attempt fails because
    runtime.execute_dag's resume branch at the `status == "paused"` check is bypassed,
    so resumed_inputs is never populated and the handler raises a confusing
    'resumed without resumed_inputs payload' error.

    runtime._try_recover_concern_scoring_pause reconstructs the pending_input from the
    convention used by handle_gate_concern_scoring (artifact at step_dir/gate_concern_scores.json,
    template at step_dir/gate_concern_scores_template.json, schema_id constant). The
    recovery only fires if BOTH files exist on disk — i.e., the user actually re-ran
    score-concerns to write a corrected artifact.
    """

    def test_recovery_returns_payload_when_both_files_exist(self):
        from src.research_orchestrator.runtime import _try_recover_concern_scoring_pause
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            step_dir = Path(td) / "validation_gate_concerns_is"
            step_dir.mkdir()
            (step_dir / "gate_concern_scores_template.json").write_text("{}", encoding="utf-8")
            (step_dir / "gate_concern_scores.json").write_text('{"scores": []}', encoding="utf-8")
            payload = _try_recover_concern_scoring_pause(step_dir)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["schema_id"], "gate_concern_scores_v1")
            self.assertTrue(payload["artifact_path"].endswith("gate_concern_scores.json"))
            self.assertTrue(payload["template_path"].endswith("gate_concern_scores_template.json"))
            self.assertEqual(payload["expected_fields"], ["scores"])

    def test_recovery_returns_none_when_artifact_missing(self):
        # User hasn't re-run score-concerns yet — leave the failed state alone.
        from src.research_orchestrator.runtime import _try_recover_concern_scoring_pause
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            step_dir = Path(td) / "validation_gate_concerns_is"
            step_dir.mkdir()
            (step_dir / "gate_concern_scores_template.json").write_text("{}", encoding="utf-8")
            # NO gate_concern_scores.json
            self.assertIsNone(_try_recover_concern_scoring_pause(step_dir))

    def test_recovery_returns_none_when_template_missing(self):
        # Template missing is a sign the step never paused as gate_concern_scoring at all
        # (or the step_dir got corrupted). Don't fabricate a recovery in that case.
        from src.research_orchestrator.runtime import _try_recover_concern_scoring_pause
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            step_dir = Path(td) / "some_step"
            step_dir.mkdir()
            (step_dir / "gate_concern_scores.json").write_text('{"scores": []}', encoding="utf-8")
            # NO gate_concern_scores_template.json
            self.assertIsNone(_try_recover_concern_scoring_pause(step_dir))


if __name__ == "__main__":
    unittest.main()
