import json
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import src.alpha_research.theme_strategy.cli as theme_cli
import src.research_orchestrator.steps as orch_steps
import workspace.scripts.research_orchestrator_cli as orchestrator_cli
from src.alpha_research.candidate_registry import CandidateRegistryStore
from src.alpha_research.factor_registry import FactorRegistryStore
from src.research_orchestrator import ResearchRequest, TimeSplit, compile_research_plan, profile_registry, run_research
from src.research_orchestrator.capabilities import (
    VALID_CAPABILITY_CATEGORIES,
    describe_capabilities,
    get_capability_metadata,
    validate_capabilities,
)
from src.research_orchestrator.dag import CompiledResearchDag, DagStepSpec, StepExecutionContext, StepExecutionResult
from src.research_orchestrator.engine import (
    _build_event_request_from_args,
    _build_improvement_request_from_args,
    _build_ml_request_from_args,
    _build_theme_request_from_args,
    resume_research,
)
from src.research_orchestrator.gate_report import derive_severity
from src.research_orchestrator.hypothesis import (
    ExpectedEffect,
    Hypothesis,
    HypothesisSource,
    PreRegisteredConcerns,
    SuccessCriteria,
)
from src.research_orchestrator.profiles import ResearchProfile
from src.research_orchestrator.registries import ModelRegistryStore, SignalRegistryStore, StrategyRegistryStore
from src.research_orchestrator.resolver import ResolverHub
from src.research_orchestrator.runtime import execute_dag, load_run_state
from src.research_orchestrator.schema import AssetRef
from workspace.research.alpha_mining.audit_benchmark_index import BenchmarkAuditResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"


def _build_test_hypothesis(request: ResearchRequest) -> Hypothesis:
    consumes = list(request.consumes)
    factor_refs = consumes or [AssetRef(object_type="factor", object_name="example_factor")]
    benchmark = str(request.inputs.get("benchmark", "") or "000905.SH")
    rebalance_days = int(request.inputs.get("rebalance_days", 5) or 5)
    profile_hint = request.profile_id.replace("_", "-")
    return Hypothesis(
        hypothesis_id=f"hyp_{profile_hint}_test",
        thesis_statement=f"Regression hypothesis for {request.profile_id}.",
        mechanism="A stable cross-sectional ranking effect should remain after neutralization.",
        source=HypothesisSource(
            source_type="domain",
            identifier=f"{request.profile_id}-test",
            title=f"{request.profile_id} regression fixture",
        ),
        factor_refs=factor_refs,
        factor_yaml_hashes=[],
        universe="csi_all",
        benchmark=benchmark,
        time_split=TimeSplit(
            is_start="2018-01-01",
            is_end="2022-12-31",
            oos_start="2023-01-01",
            oos_end="2024-12-31",
            walk_forward_config={"train_years": 3, "validation_years": 1, "test_years": 1, "step_years": 1},
        ),
        rebalance_frequency=f"{rebalance_days}d",
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
        success_criteria=SuccessCriteria(
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
            most_likely_failure_mode="The signal could be regime-specific and disappear when liquidity leadership rotates.",
            weakest_assumption="The ranking relationship stays directionally stable over the selected rebalance horizon.",
            what_would_falsify_this="If the formal IS metrics miss the pre-registered hard rules, reject the hypothesis.",
            priors_on_cost_sensitivity="Costs should matter once turnover rises above moderate A-share execution assumptions.",
        ),
        pre_registered_at="2026-04-12 10:00:00",
        registered_by="unit_test",
    )


def _attach_formal_hypothesis(request: ResearchRequest) -> ResearchRequest:
    if request.mode != "formal" or request.profile_id == "benchmark_audit" or request.hypothesis is not None:
        return request
    return ResearchRequest(
        profile_id=request.profile_id,
        mode=request.mode,
        consumes=request.consumes,
        produces=request.produces,
        requested_capabilities=request.requested_capabilities,
        inputs=request.inputs,
        run_context=request.run_context,
        hypothesis=_build_test_hypothesis(request),
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_auto_concern_scores(run_dir: Path, step_id: str) -> None:
    step_dir = run_dir / "steps" / step_id
    template = _load_json(step_dir / "gate_concern_scores_template.json")
    plan = _load_json(run_dir / "dag_plan.json")
    step_map = {str(item["step_id"]): item for item in plan.get("steps", [])}
    depends_on = list(step_map[step_id].get("depends_on", []))
    eval_step_id = next(
        dep for dep in depends_on if str(step_map.get(dep, {}).get("capability", "")) == "gate_evaluation"
    )
    eval_outputs = _load_json(run_dir / "steps" / eval_step_id / "step_outputs.json")
    rule_table = list(eval_outputs.get("criteria_results", []))
    measured_values = dict(eval_outputs.get("measured_values", {}))
    usable_rule = next(
        (
            row for row in rule_table
            if str(row.get("rule_id", "")).strip()
            and str(row.get("metric", "")).strip()
        ),
        rule_table[0],
    )
    metric_name = str(usable_rule.get("metric", ""))
    metric_value = measured_values.get(metric_name)
    if metric_name:
        anchor_value = metric_value if isinstance(metric_value, (int, float)) else 0.0
        anchor = {metric_name: anchor_value}
    else:
        anchor = {"fallback_metric": 0.0}
    severity = derive_severity(usable_rule, anchor)
    evidence = (
        f"Regression helper confirms this concern against rule {usable_rule.get('rule_id')} with "
        f"measured {metric_name}={metric_value}. The evidence text is intentionally long enough to "
        "satisfy the workflow schema and mirrors the exact measured value from gate_evaluation."
    )
    payload = {
        "scores": [
            {
                "concern_id": row["concern_id"],
                "concern_text": row["concern_text"],
                "keyed_to_rule_id": str(usable_rule.get("rule_id", "")),
                "measured_evidence_against_concern": evidence,
                "quantitative_anchor": anchor,
                "confirmed": True,
                "severity": severity,
            }
            for row in template["scores"]
        ]
    }
    (step_dir / "gate_concern_scores.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def _approve_gate(run_dir: Path, step_id: str) -> None:
    decision = {
        "decision": "approved",
        "decision_by": "unit_test",
        "reason": "Regression auto-approval",
        "recorded_at": "2026-04-12 10:05:00",
    }
    (run_dir / "steps" / step_id / "gate_decision.json").write_text(
        json.dumps(decision, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def _run_formal_research_with_auto_gates(request: ResearchRequest):
    request = _attach_formal_hypothesis(request)
    result = run_research(request)
    run_dir = Path(result.run_dir)
    for _ in range(6):
        state = load_run_state(run_dir)
        if state["status"] == "completed":
            return result
        if state["status"] != "paused":
            raise AssertionError(f"Unexpected run state: {state['status']}")
        step_id = str(state.get("pending_step_id", "") or "")
        if state.get("pending_input"):
            _write_auto_concern_scores(run_dir, step_id)
        elif state.get("pending_gate"):
            _approve_gate(run_dir, step_id)
        else:
            raise AssertionError(f"Paused run has no pending_input or pending_gate: {state}")
        result = resume_research(run_dir)
    raise AssertionError("Formal run did not complete after auto-resume loop")


_REAL_BUILD_THEME_REQUEST_FROM_ARGS = _build_theme_request_from_args
_REAL_BUILD_EVENT_REQUEST_FROM_ARGS = _build_event_request_from_args
_REAL_BUILD_ML_REQUEST_FROM_ARGS = _build_ml_request_from_args
_REAL_BUILD_IMPROVEMENT_REQUEST_FROM_ARGS = _build_improvement_request_from_args


def _build_theme_request_from_args(args):
    return _attach_formal_hypothesis(_REAL_BUILD_THEME_REQUEST_FROM_ARGS(args))


def _build_event_request_from_args(args):
    return _attach_formal_hypothesis(_REAL_BUILD_EVENT_REQUEST_FROM_ARGS(args))


def _build_ml_request_from_args(args):
    return _attach_formal_hypothesis(_REAL_BUILD_ML_REQUEST_FROM_ARGS(args))


def _build_improvement_request_from_args(args):
    return _attach_formal_hypothesis(_REAL_BUILD_IMPROVEMENT_REQUEST_FROM_ARGS(args))


def _write_theme_run(run_dir: Path) -> None:
    theme_dir = run_dir / "small_cap"
    theme_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "component_id": "small_cap_total_mv_small_rank",
                "theme_id": "small_cap",
                "source_fields": "('total_mv',)",
                "source_type": "field_transform",
                "transform_family": "level_rank",
                "transform_params": "{'mode': 'direct'}",
                "expected_sign": -1,
                "economic_role": "core_thesis",
                "coverage_tier": "A",
                "notes": "size core",
            },
            {
                "component_id": "small_cap_low_vol_20d",
                "theme_id": "small_cap",
                "source_fields": "('close','adj_factor')",
                "source_type": "field_transform",
                "transform_family": "stability",
                "transform_params": "{'mode': 'rolling_vol', 'window': 20}",
                "expected_sign": -1,
                "economic_role": "execution_guardrail",
                "coverage_tier": "A",
                "notes": "defensive",
            },
        ]
    ).to_csv(theme_dir / "component_registry.csv", index=False)
    pd.DataFrame(
        [
            {
                "component_id": "small_cap_total_mv_small_rank",
                "theme_id": "small_cap",
                "coverage_ratio": 0.99,
                "coverage_tier": "A",
                "mean_rank_ic": 0.03,
                "rank_icir": 1.8,
                "positive_validation_folds": 6,
                "total_validation_folds": 7,
                "direction_consistent": True,
                "max_abs_corr": 0.25,
                "marginal_rank_icir": 0.6,
                "cluster_id": "cluster_01",
                "selection_score": 2.4,
                "selected_for_recipe": True,
                "rejection_reason": "",
                "universe_id": "sc_u4",
            }
        ]
    ).to_csv(theme_dir / "component_card.csv", index=False)
    pd.DataFrame(
        [
            {
                "theme_id": "small_cap",
                "universe_id": "sc_u4",
                "recipe_id": "size_only",
                "topk": 10,
                "rebalance_days": 5,
                "stitched_relative_excess_return": 0.12,
                "positive_excess_folds": 5,
                "holdout_relative_excess_return": 0.06,
                "worst_max_drawdown": -0.18,
                "avg_turnover": 0.2,
                "component_ids": "small_cap_total_mv_small_rank",
                "weights": "1.0",
                "construction_rule": "equal_weight_seed",
                "selection_note": "seed",
            }
        ]
    ).to_csv(theme_dir / "signal_recipe_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "theme_id": "small_cap",
                "universe_id": "sc_u4",
                "recipe_id": "size_only",
                "topk": 10,
                "rebalance_days": 5,
                "relative_excess_return": 0.04,
                "max_drawdown": -0.12,
                "avg_turnover": 0.18,
                "trade_count": 9,
            }
        ]
    ).to_csv(theme_dir / "event_driven_variant_summary.csv", index=False)
    (run_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-06 14:00:00",
                "theme": "small_cap",
                "stage": "event_driven",
                "status": "completed",
                "artifact_count": 4,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_screening_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"factor": "liq_vol_cv_20d", "grade": "A (Graduated)"},
            {"factor": "comp_defensive", "grade": "B (Strong IC)"},
            {"factor": "rev_max_return_20d", "grade": "C (Monitor)"},
        ]
    ).to_csv(run_dir / "factor_screening_report.csv", index=False)
    (run_dir / "factor_screening_run_metadata.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-06 15:00:00",
                "start_date": "2012-01-01",
                "end_date": "2025-12-31",
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_event_signal_stage(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "factor": "liq_vol_cv_20d",
                "grade": "A (Graduated)",
                "rank_icir_5d": 1.5,
                "mean_rank_ic_5d": 0.03,
                "ic_hit_rate_5d": 0.58,
                "monotonic": True,
                "best_decay_horizon": 5,
                "peak_decay_icir": 1.6,
                "ls_ann_return": 0.12,
            },
            {
                "factor": "comp_defensive",
                "grade": "B (Strong IC)",
                "rank_icir_5d": 1.1,
                "mean_rank_ic_5d": 0.02,
                "ic_hit_rate_5d": 0.54,
                "monotonic": True,
                "best_decay_horizon": 5,
                "peak_decay_icir": 1.2,
                "ls_ann_return": 0.08,
            },
        ]
    ).to_csv(run_dir / "factor_research_metrics.csv", index=False)
    pd.DataFrame(
        [
            {
                "fold_id": "fold_01",
                "factor": "liq_vol_cv_20d",
                "validation_pass": True,
                "selected": True,
                "val_rank_icir": 1.35,
                "max_abs_corr": 0.15,
                "train_direction": 1,
            },
            {
                "fold_id": "fold_01",
                "factor": "comp_defensive",
                "validation_pass": True,
                "selected": False,
                "val_rank_icir": 0.92,
                "max_abs_corr": 0.72,
                "train_direction": 1,
            },
        ]
    ).to_csv(run_dir / "factor_selection_decisions.csv", index=False)
    pd.DataFrame(
        [
            {
                "fold_id": "fold_01",
                "factor": "liq_vol_cv_20d",
                "selection_rank": 1,
            }
        ]
    ).to_csv(run_dir / "selected_core_factors_by_fold.csv", index=False)
    pd.DataFrame(
        [
            {
                "fold_id": "fold_01",
                "selected_count": 1,
                "qualified_count": 2,
            }
        ]
    ).to_csv(run_dir / "fold_overview.csv", index=False)
    pd.DataFrame(
        [
            {
                "factor": "liq_vol_cv_20d",
                "overall_decision": "selected",
                "selected_count": 1,
                "validation_pass_count": 1,
            },
            {
                "factor": "comp_defensive",
                "overall_decision": "monitor",
                "selected_count": 0,
                "validation_pass_count": 1,
            },
        ]
    ).to_csv(run_dir / "overall_factor_decisions.csv", index=False)


def _write_event_backtest_stage(run_dir: Path, screening_run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2025-01-02",
                "return": 0.01,
                "bench": 0.002,
                "turnover": 0.18,
                "blocked_order_ratio": 0.0,
                "trade_count": 3,
            },
            {
                "date": "2025-01-03",
                "return": -0.004,
                "bench": -0.001,
                "turnover": 0.12,
                "blocked_order_ratio": 0.0,
                "trade_count": 2,
            },
        ]
    ).to_csv(run_dir / "event_driven_report.csv", index=False)
    (run_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-09 12:00:00",
                "screening_run_dir": str(screening_run_dir),
                "candidate_count": 2,
                "candidate_factors": ["liq_vol_cv_20d", "comp_defensive"],
                "benchmark": "000905.SH",
                "capital": 2000000.0,
                "topk": 50,
                "rebalance_days": 5,
                "adv_median_floor": 5000000.0,
                "participation_cap": 0.02,
                "strategy_horizon": 5,
                "strategy_style": "all-market long-only",
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_ml_outputs(run_dir: Path, baseline_run_dir: Path, screening_run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "variant_id": "rule_baseline",
                "model_kind": "rule",
                "display_name": "Rule baseline",
                "stitched_relative_excess_return": 0.08,
                "positive_excess_folds": 5,
                "holdout_relative_excess_return": 0.02,
                "worst_max_drawdown": -0.12,
                "avg_turnover": 0.18,
                "adoption_recommendation": "reference_only",
            },
            {
                "variant_id": "elasticnet",
                "model_kind": "linear",
                "display_name": "ElasticNet factor-weight model",
                "stitched_relative_excess_return": 0.13,
                "positive_excess_folds": 6,
                "holdout_relative_excess_return": 0.04,
                "worst_max_drawdown": -0.10,
                "avg_turnover": 0.16,
                "adoption_recommendation": "pilot_candidate",
            },
        ]
    ).to_csv(run_dir / "variant_comparison_summary.csv", index=False)
    (run_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-09 18:00:00",
                "baseline_run_dir": str(baseline_run_dir),
                "screening_run_dir": str(screening_run_dir),
                "benchmark": "000001.SH",
                "capital": 2000000.0,
                "topk": 50,
                "rebalance_days": 10,
                "label_horizon": 10,
                "model_variants": ["linear"],
                "candidate_factors": ["liq_vol_cv_20d", "comp_defensive"],
                "best_ml_summary": {
                    "variant_id": "elasticnet",
                    "model_kind": "linear",
                    "display_name": "ElasticNet factor-weight model",
                    "stitched_relative_excess_return": 0.13,
                },
                "adoption_recommendation": "pilot_candidate",
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_improvement_outputs(run_dir: Path, baseline_run_dir: Path, screening_run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "rank": 1,
                "stage": "D",
                "variant_id": "D_best",
                "selection_mode": "stability_score",
                "portfolio_weighting": "score_prop",
                "topk": 50,
                "rebalance_days": 5,
                "slow_rebalance_days": 10,
                "liquidity_scenario": "adv_floor_plus_participation",
                "slippage_rate": 0.0005,
                "stitched_relative_excess_return": 0.11,
                "positive_excess_folds": 6,
                "holdout_relative_excess_return": 0.03,
                "worst_max_drawdown": -0.15,
                "avg_turnover": 0.14,
                "avg_blocked_order_ratio": 0.01,
                "promoted": True,
                "gate_reason": "",
            }
        ]
    ).to_csv(run_dir / "variant_comparison_summary.csv", index=False)
    (run_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-09 18:30:00",
                "baseline_run_dir": str(baseline_run_dir),
                "screening_run_dir": str(screening_run_dir),
                "benchmark": "000001.SH",
                "default_topk": 50,
                "default_rebalance_days": 5,
                "slow_rebalance_days": 10,
                "best_variant": {
                    "variant_id": "D_best",
                    "stitched_relative_excess_return": 0.11,
                },
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )


class ResearchOrchestratorTests(unittest.TestCase):
    @contextmanager
    def make_temp_dir(self, name: str):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        temp_root = WORKSPACE_OUTPUTS / f"{name}_{uuid.uuid4().hex[:8]}"
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        try:
            yield str(temp_root)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_builtin_profile_registry_contains_all_formal_profiles(self):
        profiles = profile_registry().all_profiles()
        self.assertEqual(
            set(profiles),
            {
                "factor_screening",
                "theme_strategy",
                "event_driven_signal_research",
                "ml_signal_model_research",
                "strategy_improvement",
                "benchmark_audit",
                # jolly-seeking-lollipop Gate B: validation profile for
                # prescription-style hypotheses.
                "hypothesis_validation",
                # factor_lifecycle plan Phase 5: the IS-only draft->candidate factor gate.
                "factor_lifecycle",
            },
        )
        self.assertTrue(all(profile.execution_model == "dag" for profile in profiles.values()))

    def test_profile_registration_rejects_unknown_capability(self):
        profile = ResearchProfile(
            profile_id="bad_profile",
            supported_modes=("formal",),
            consumes_types=("factor",),
            produces_types=(),
            default_capabilities=("does_not_exist",),
            formal_requires_resolver=True,
            dag_builder=lambda *_: CompiledResearchDag(
                profile_id="bad_profile",
                run_dir=str(PROJECT_ROOT / "workspace" / "outputs" / "bad_profile"),
                steps=(DagStepSpec(step_id="x", capability="data_scope", handler="noop"),),
            ),
        )
        with self.assertRaises(ValueError):
            profile.validate()

    def test_research_profile_is_dag_only_and_legacy_handler_is_removed(self):
        with self.assertRaises(TypeError):
            ResearchProfile(
                profile_id="bad_profile",
                supported_modes=("formal",),
                consumes_types=(),
                produces_types=(),
                default_capabilities=("data_scope",),
                formal_requires_resolver=False,
                dag_builder=lambda *_: CompiledResearchDag(
                    profile_id="bad_profile",
                    run_dir=str(PROJECT_ROOT / "workspace" / "outputs" / "bad_profile"),
                    steps=(DagStepSpec(step_id="x", capability="data_scope", handler="noop"),),
                ),
                runner=None,
            )
        self.assertNotIn("legacy_profile_runner", orch_steps.HANDLER_REGISTRY)

    def test_capability_board_includes_new_capabilities_with_categories(self):
        self.assertEqual(VALID_CAPABILITY_CATEGORIES, ("core_research", "diagnostic", "support"))
        for name in (
            "data_readiness",
            "dataset_build",
            "factor_construction",
            "risk_overlay",
            "performance_diagnostics",
            "experiment_tracking",
            "portfolio_construction",
        ):
            meta = get_capability_metadata(name)
            self.assertEqual(meta["name"], name)
            self.assertIn(meta["category"], VALID_CAPABILITY_CATEGORIES)
            self.assertTrue(meta["description"])
        self.assertEqual(get_capability_metadata("benchmark_audit")["category"], "diagnostic")
        self.assertEqual(get_capability_metadata("object_resolver")["category"], "support")

    def test_capability_validation_normalizes_legacy_portfolio_alias(self):
        self.assertEqual(
            validate_capabilities(["data_scope", "portfolio_assembly", "portfolio_construction"]),
            ["data_scope", "portfolio_construction"],
        )
        described = describe_capabilities(["portfolio_assembly"])
        self.assertEqual(described[0]["name"], "portfolio_construction")
        self.assertEqual(described[0]["category"], "core_research")

    def test_dag_validation_rejects_cycles(self):
        dag = CompiledResearchDag(
            profile_id="cycle_profile",
            run_dir=str(PROJECT_ROOT / "workspace" / "outputs" / "cycle_profile"),
            steps=(
                DagStepSpec(step_id="a", capability="data_scope", handler="noop", depends_on=("b",)),
                DagStepSpec(step_id="b", capability="data_readiness", handler="noop", depends_on=("a",)),
            ),
        )
        with self.assertRaises(ValueError):
            dag.validate()

    def test_builtin_profiles_compile_to_valid_dag_plans(self):
        with self.make_temp_dir("orch_compile") as temp_dir:
            temp_root = Path(temp_dir)
            screening_run_dir = temp_root / "screening_run"
            _write_screening_run(screening_run_dir)
            baseline_run_dir = temp_root / "baseline_run"
            baseline_run_dir.mkdir(parents=True, exist_ok=True)
            (baseline_run_dir / "run_metadata.json").write_text(
                json.dumps(
                    {
                        "screening_run_dir": str(screening_run_dir),
                        "candidate_factors": ["liq_vol_cv_20d", "comp_defensive"],
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )

            requests = [
                _attach_formal_hypothesis(
                    ResearchRequest(
                        profile_id="factor_screening",
                        mode="formal",
                        consumes=[],
                        produces=[],
                        requested_capabilities=[],
                        inputs={
                            "argv": [],
                            "args": {},
                            "output_dir": str((temp_root / "factor_screening_run").resolve()),
                        },
                        run_context={},
                    )
                ),
                _build_theme_request_from_args(
                    SimpleNamespace(
                        theme="small_cap",
                        stage="recipe",
                        output_dir=str((temp_root / "theme_recipe_run").resolve()),
                        recipe_source_run_dir=None,
                    )
                ),
                _build_event_request_from_args(
                    SimpleNamespace(
                        screening_run_dir=str(screening_run_dir),
                        output_dir=str((temp_root / "event_run").resolve()),
                        capital=2_000_000.0,
                        benchmark="000905.SH",
                        topk=50,
                        rebalance_days=5,
                        adv_median_floor=5_000_000.0,
                        participation_cap=0.02,
                        max_factors=None,
                        max_folds=None,
                        skip_sensitivity=False,
                        skip_holdout=False,
                        disable_mlflow=True,
                    )
                ),
                _build_ml_request_from_args(
                    SimpleNamespace(
                        baseline_run_dir=str(baseline_run_dir),
                        screening_run_dir=str(screening_run_dir),
                        output_dir=str((temp_root / "ml_run").resolve()),
                        benchmark="000001.SH",
                        label_horizon=10,
                        topk=50,
                        rebalance_days=10,
                        adv_median_floor=5_000_000.0,
                        participation_cap=0.02,
                        capital=2_000_000.0,
                        model_variants="linear",
                        disable_mlflow=True,
                    )
                ),
                _build_improvement_request_from_args(
                    SimpleNamespace(
                        baseline_run_dir=str(baseline_run_dir),
                        output_dir=str((temp_root / "improvement_run").resolve()),
                        benchmark="000001.SH",
                        universe_mode="all_market",
                        selection_mode="baseline",
                        portfolio_weighting="equal",
                        topk=50,
                        rebalance_days=5,
                        slow_rebalance_days=10,
                        liquidity_scenario="adv_floor_plus_participation",
                        slippage_rate=0.0005,
                        capital=2_000_000.0,
                        adv_median_floor=5_000_000.0,
                        participation_cap=0.02,
                        max_folds=None,
                    )
                ),
                ResearchRequest(
                    profile_id="benchmark_audit",
                    mode="formal",
                    consumes=[],
                    produces=[],
                    requested_capabilities=[],
                    inputs={
                        "benchmark": "000001.SH",
                        "output_dir": str((temp_root / "benchmark_run").resolve()),
                    },
                    run_context={},
                ),
            ]
            for request in requests:
                plan = compile_research_plan(request)
                self.assertEqual(plan["execution_model"], "dag")
                self.assertTrue(plan["steps"])
                self.assertTrue(plan["run_dir"])
                self.assertNotIn("legacy_profile_runner", [item["handler"] for item in plan["steps"]])

    def test_theme_quick_event_driven_plan_skips_earlier_search_steps(self):
        request = _build_theme_request_from_args(
            SimpleNamespace(
                theme="small_cap",
                stage="event_driven",
                output_dir=str((PROJECT_ROOT / "workspace" / "outputs" / "theme_quick_plan").resolve()),
                recipe_source_run_dir=str((PROJECT_ROOT / "workspace" / "outputs" / "recipe_source").resolve()),
            )
        )
        plan = compile_research_plan(request)
        step_ids = [item["step_id"] for item in plan["steps"]]
        self.assertIn("event_driven_backtest", step_ids)
        self.assertNotIn("universe_builder", step_ids)
        self.assertNotIn("factor_discovery", step_ids)
        self.assertNotIn("signal_search", step_ids)

    def test_theme_recipe_plan_uses_granular_theme_handlers(self):
        request = _build_theme_request_from_args(
            SimpleNamespace(
                theme="small_cap",
                stage="recipe",
                output_dir=str((PROJECT_ROOT / "workspace" / "outputs" / "theme_recipe_plan_check").resolve()),
                recipe_source_run_dir=None,
            )
        )
        plan = compile_research_plan(request)
        handlers = {item["step_id"]: item["handler"] for item in plan["steps"]}
        self.assertEqual(handlers["dataset_build"], "theme_dataset_build")
        self.assertEqual(handlers["universe_builder"], "theme_universe_builder")
        self.assertEqual(handlers["factor_construction"], "theme_factor_construction")
        self.assertEqual(handlers["factor_discovery"], "theme_factor_discovery")
        self.assertEqual(handlers["signal_search"], "theme_signal_search")
        self.assertEqual(handlers["vectorized_backtest"], "theme_vectorized_backtest")
        self.assertNotIn("legacy_profile_runner", handlers.values())

    def test_event_signal_plan_uses_granular_handlers(self):
        with self.make_temp_dir("orch_event_plan_check") as temp_dir:
            screening_run_dir = Path(temp_dir) / "screening_run"
            _write_screening_run(screening_run_dir)
            request = _build_event_request_from_args(
                SimpleNamespace(
                    screening_run_dir=str(screening_run_dir),
                    output_dir=str((Path(temp_dir) / "event_run").resolve()),
                    capital=2_000_000.0,
                    benchmark="000905.SH",
                    topk=50,
                    rebalance_days=5,
                    adv_median_floor=5_000_000.0,
                    participation_cap=0.02,
                    max_factors=None,
                    max_folds=None,
                    skip_sensitivity=False,
                    skip_holdout=False,
                    disable_mlflow=True,
                )
            )
            plan = compile_research_plan(request)
        handlers = {item["step_id"]: item["handler"] for item in plan["steps"]}
        self.assertEqual(handlers["dataset_build"], "event_dataset_build")
        self.assertEqual(handlers["signal_search"], "event_signal_search")
        self.assertEqual(handlers["portfolio_construction"], "event_portfolio_construction")
        self.assertEqual(handlers["event_driven_backtest"], "event_backtest")
        self.assertEqual(handlers["execution_validation"], "event_execution_validation")
        self.assertEqual(handlers["registry_publish"], "event_registry_publish")
        self.assertNotIn("legacy_profile_runner", [handlers["signal_search"], handlers["event_driven_backtest"]])

    def test_factor_screening_plan_uses_granular_handlers(self):
        request = _attach_formal_hypothesis(
            ResearchRequest(
                profile_id="factor_screening",
                mode="formal",
                consumes=[],
                produces=[],
                requested_capabilities=[],
                inputs={
                    "argv": [],
                    "args": {},
                    "output_dir": str((PROJECT_ROOT / "workspace" / "outputs" / "factor_screening_plan_check").resolve()),
                },
                run_context={},
            )
        )
        plan = compile_research_plan(request)
        handlers = {item["step_id"]: item["handler"] for item in plan["steps"]}
        self.assertEqual(handlers["dataset_build"], "screening_dataset_build")
        self.assertEqual(handlers["factor_discovery"], "screening_factor_discovery")
        self.assertEqual(handlers["vectorized_backtest"], "screening_vectorized_backtest")
        self.assertEqual(handlers["registry_publish"], "screening_registry_publish")

    def test_ml_plan_uses_granular_handlers(self):
        with self.make_temp_dir("orch_ml_plan") as temp_dir:
            temp_root = Path(temp_dir)
            screening_run_dir = temp_root / "screening_run"
            _write_screening_run(screening_run_dir)
            baseline_run_dir = temp_root / "baseline_run"
            baseline_run_dir.mkdir(parents=True, exist_ok=True)
            (baseline_run_dir / "run_metadata.json").write_text(
                json.dumps(
                    {
                        "screening_run_dir": str(screening_run_dir),
                        "candidate_factors": ["liq_vol_cv_20d", "comp_defensive"],
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
            request = _build_ml_request_from_args(
                SimpleNamespace(
                    baseline_run_dir=str(baseline_run_dir),
                    screening_run_dir=str(screening_run_dir),
                    output_dir=str((temp_root / "ml_run").resolve()),
                    benchmark="000001.SH",
                    label_horizon=10,
                    topk=50,
                    rebalance_days=10,
                    adv_median_floor=5_000_000.0,
                    participation_cap=0.02,
                    capital=2_000_000.0,
                    model_variants="linear",
                    disable_mlflow=True,
                )
            )
        plan = compile_research_plan(request)
        handlers = {item["step_id"]: item["handler"] for item in plan["steps"]}
        self.assertEqual(handlers["dataset_build"], "ml_dataset_build")
        self.assertEqual(handlers["label_builder"], "ml_label_builder")
        self.assertEqual(handlers["model_training"], "ml_model_training")
        self.assertEqual(handlers["signal_search"], "ml_signal_search")
        self.assertEqual(handlers["portfolio_construction"], "ml_portfolio_construction")
        self.assertEqual(handlers["event_driven_backtest"], "ml_event_backtest")
        self.assertEqual(handlers["execution_validation"], "ml_execution_validation")
        self.assertEqual(handlers["experiment_tracking"], "ml_experiment_tracking")
        self.assertEqual(handlers["registry_publish"], "ml_registry_publish")

    def test_strategy_improvement_plan_uses_granular_handlers(self):
        with self.make_temp_dir("orch_improvement_plan") as temp_dir:
            temp_root = Path(temp_dir)
            screening_run_dir = temp_root / "screening_run"
            _write_screening_run(screening_run_dir)
            baseline_run_dir = temp_root / "baseline_run"
            baseline_run_dir.mkdir(parents=True, exist_ok=True)
            (baseline_run_dir / "run_metadata.json").write_text(
                json.dumps(
                    {
                        "screening_run_dir": str(screening_run_dir),
                        "candidate_factors": ["liq_vol_cv_20d", "comp_defensive"],
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
            request = _build_improvement_request_from_args(
                SimpleNamespace(
                    baseline_run_dir=str(baseline_run_dir),
                    output_dir=str((temp_root / "improvement_run").resolve()),
                    benchmark="000001.SH",
                    universe_mode="all_market",
                    selection_mode="baseline",
                    portfolio_weighting="equal",
                    topk=50,
                    rebalance_days=5,
                    slow_rebalance_days=10,
                    liquidity_scenario="adv_floor_plus_participation",
                    slippage_rate=0.0005,
                    capital=2_000_000.0,
                    adv_median_floor=5_000_000.0,
                    participation_cap=0.02,
                    max_folds=None,
                )
            )
        plan = compile_research_plan(request)
        handlers = {item["step_id"]: item["handler"] for item in plan["steps"]}
        self.assertEqual(handlers["dataset_build"], "improvement_dataset_build")
        self.assertEqual(handlers["portfolio_construction"], "improvement_portfolio_construction")
        self.assertEqual(handlers["risk_overlay"], "improvement_risk_overlay")
        self.assertEqual(handlers["stress_test"], "improvement_stress_test")
        self.assertEqual(handlers["event_driven_backtest"], "improvement_event_backtest")
        self.assertEqual(handlers["execution_validation"], "improvement_execution_validation")
        self.assertEqual(handlers["registry_publish"], "improvement_registry_publish")

    def test_benchmark_audit_plan_uses_step_handler(self):
        request = ResearchRequest(
            profile_id="benchmark_audit",
            mode="formal",
            consumes=[],
            produces=[],
            requested_capabilities=[],
            inputs={
                "benchmark": "000001.SH",
                "output_dir": str((PROJECT_ROOT / "workspace" / "outputs" / "benchmark_plan_check").resolve()),
            },
            run_context={},
        )
        plan = compile_research_plan(request)
        handlers = {item["step_id"]: item["handler"] for item in plan["steps"]}
        self.assertEqual(handlers["benchmark_audit"], "benchmark_audit_step")

    def test_cli_plan_accepts_utf8_sig_request_file(self):
        with self.make_temp_dir("orch_cli_plan") as temp_dir:
            request_path = Path(temp_dir) / "request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "profile_id": "benchmark_audit",
                        "mode": "formal",
                        "consumes": [],
                        "produces": [],
                        "requested_capabilities": [],
                        "inputs": {
                            "benchmark": "000001.SH",
                            "output_dir": str((Path(temp_dir) / "benchmark_run").resolve()),
                        },
                        "run_context": {},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8-sig",
            )
            self.assertEqual(
                orchestrator_cli.main(["plan", "--request-file", str(request_path)]),
                0,
            )

    def test_event_request_builder_only_consumes_ab_factors_and_resolves_output_dir(self):
        with self.make_temp_dir("orch_event_builder") as temp_dir:
            screening_run_dir = Path(temp_dir) / "screening_run"
            _write_screening_run(screening_run_dir)
            request = _build_event_request_from_args(
                SimpleNamespace(
                    screening_run_dir=str(screening_run_dir),
                    output_dir="",
                    capital=2_000_000.0,
                    benchmark="000905.SH",
                    topk=50,
                    rebalance_days=5,
                    adv_median_floor=5_000_000.0,
                    participation_cap=0.02,
                    max_factors=None,
                    max_folds=None,
                    skip_sensitivity=False,
                    skip_holdout=False,
                    disable_mlflow=True,
                )
            )
            self.assertEqual([item.object_name for item in request.consumes], ["liq_vol_cv_20d", "comp_defensive"])
            self.assertEqual([item.object_type for item in request.consumes], ["factor", "composite_factor"])
            self.assertTrue(str(request.inputs["output_dir"]).strip())

    def test_resolver_labels_draft_factor_registry_row(self):
        # PR P1.2 "resolve-but-label": a synced catalog factor is `draft`, so it
        # RESOLVES (status=="resolved" -> the discovery object_resolver does NOT trip
        # its unresolved hard-fail) but is labeled factor_registry_draft, NOT formal.
        with self.make_temp_dir("orch_resolver_formal") as temp_dir:
            root = Path(temp_dir)
            factor_store = FactorRegistryStore(root / "factor_registry")
            factor_store.sync_catalog(record_run=False, generated_at="2026-04-06 21:00:00")
            factor_store.save()

            resolver = ResolverHub(
                factor_registry_dir=root / "factor_registry",
                candidate_registry_dir=root / "candidate_registry",
                signal_registry_dir=root / "signal_registry",
                model_registry_dir=root / "model_registry",
                strategy_registry_dir=root / "strategy_registry",
            )
            result = resolver.resolve_assets(
                consumes=[AssetRef(object_type="factor", object_name="liq_vol_cv_20d")],
                mode="formal",
                allowed_new_object_types=set(),
                research_profile="event_driven_signal_research",
            )
            self.assertEqual(result["formal_hits"], 0)
            self.assertEqual(result["candidate_hits"], 0)
            self.assertEqual(len(result["unresolved_objects"]), 0)
            entry = result["resolved_objects"][0]
            self.assertEqual(entry["status"], "resolved")
            self.assertEqual(entry["source_layer"], "factor_registry_draft")
            self.assertEqual(entry["registry_status"], "draft")
            self.assertEqual(entry["approval_validity"], "valid")
            self.assertEqual(result["factor_registry_hits_by_layer"]["factor_registry_draft"], 1)

    def test_resolver_labels_by_registry_status(self):
        # PR P1.2: approved+valid->formal, candidate->factor_registry_candidate,
        # approved+stale->factor_registry_stale, deprecated->factor_registry_deprecated.
        with self.make_temp_dir("orch_resolver_labels") as temp_dir:
            root = Path(temp_dir)
            store = FactorRegistryStore(root / "factor_registry")
            store.sync_catalog(record_run=False, generated_at="2026-04-06 21:00:00")
            ids = store.factor_master["factor_id"].tolist()
            approved_id, candidate_id, stale_id, deprecated_id = ids[0], ids[1], ids[2], ids[3]

            def _set(fid, status, validity):
                i = store.factor_master.index[store.factor_master["factor_id"] == fid][0]
                store.factor_master.at[i, "status"] = status
                store.factor_master.at[i, "approval_validity"] = validity

            _set(approved_id, "approved", "valid")
            _set(candidate_id, "candidate", "valid")
            _set(stale_id, "approved", "requires_revalidation")
            _set(deprecated_id, "deprecated", "valid")
            store.save()

            resolver = ResolverHub(
                factor_registry_dir=root / "factor_registry",
                candidate_registry_dir=root / "candidate_registry",
                signal_registry_dir=root / "signal_registry",
                model_registry_dir=root / "model_registry",
                strategy_registry_dir=root / "strategy_registry",
            )
            result = resolver.resolve_assets(
                consumes=[
                    AssetRef(object_type="factor", object_name=f)
                    for f in (approved_id, candidate_id, stale_id, deprecated_id)
                ],
                mode="formal",
                allowed_new_object_types=set(),
                research_profile="event_driven_signal_research",
            )
            layers = {e["canonical_id"]: e["source_layer"] for e in result["resolved_objects"]}
            self.assertEqual(layers[approved_id], "formal")
            self.assertEqual(layers[candidate_id], "factor_registry_candidate")
            self.assertEqual(layers[stale_id], "factor_registry_stale")
            self.assertEqual(layers[deprecated_id], "factor_registry_deprecated")
            self.assertEqual(result["formal_hits"], 1)
            self.assertEqual(result["candidate_hits"], 1)
            self.assertEqual(result["factor_registry_hits_by_layer"]["factor_registry_stale"], 1)
            self.assertEqual(result["factor_registry_hits_by_layer"]["factor_registry_deprecated"], 1)

    def test_resolver_enforces_requested_definition_hash(self):
        # PR P1.2 (Codex round-5): a requested definition_hash that mismatches the
        # named factor-registry row must NOT resolve formally (closes the
        # same-name-shadows-different-hash path); the correct hash resolves.
        with self.make_temp_dir("orch_resolver_hash") as temp_dir:
            root = Path(temp_dir)
            store = FactorRegistryStore(root / "factor_registry")
            store.sync_catalog(record_run=False, generated_at="2026-04-06 21:00:00")
            store.save()
            real_hash = store.factor_master[
                store.factor_master["factor_id"] == "liq_vol_cv_20d"
            ].iloc[0]["definition_hash"]

            resolver = ResolverHub(
                factor_registry_dir=root / "factor_registry",
                candidate_registry_dir=root / "candidate_registry",
                signal_registry_dir=root / "signal_registry",
                model_registry_dir=root / "model_registry",
                strategy_registry_dir=root / "strategy_registry",
            )
            wrong = resolver.resolve_assets(
                consumes=[AssetRef(object_type="factor", object_name="liq_vol_cv_20d", definition_hash="0" * 64)],
                mode="formal", allowed_new_object_types=set(),
                research_profile="event_driven_signal_research",
            )
            self.assertEqual(wrong["resolved_objects"][0]["status"], "unresolved")

            right = resolver.resolve_assets(
                consumes=[AssetRef(object_type="factor", object_name="liq_vol_cv_20d", definition_hash=real_hash)],
                mode="formal", allowed_new_object_types=set(),
                research_profile="event_driven_signal_research",
            )
            self.assertEqual(right["resolved_objects"][0]["status"], "resolved")
            self.assertEqual(right["resolved_objects"][0]["source_layer"], "factor_registry_draft")

    def test_resolver_falls_back_to_candidate_registry_for_theme_component(self):
        with self.make_temp_dir("orch_resolver_candidate") as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "theme_run"
            run_dir.mkdir(parents=True, exist_ok=True)
            _write_theme_run(run_dir)

            candidate_store = CandidateRegistryStore(root / "candidate_registry")
            candidate_store.import_theme_strategy_run(run_dir)
            candidate_store.save()

            resolver = ResolverHub(
                factor_registry_dir=root / "factor_registry",
                candidate_registry_dir=root / "candidate_registry",
                signal_registry_dir=root / "signal_registry",
                model_registry_dir=root / "model_registry",
                strategy_registry_dir=root / "strategy_registry",
            )
            result = resolver.resolve_assets(
                consumes=[AssetRef(object_type="factor", object_name="small_cap_total_mv_small_rank")],
                mode="formal",
                allowed_new_object_types=set(),
                research_profile="event_driven_signal_research",
            )
            self.assertEqual(result["formal_hits"], 0)
            self.assertEqual(result["candidate_hits"], 1)
            self.assertEqual(result["resolved_objects"][0]["source_layer"], "candidate")

    def test_execute_dag_resume_restarts_from_failed_step_only(self):
        with self.make_temp_dir("orch_resume_runtime") as temp_dir:
            run_dir = Path(temp_dir) / "resume_run"
            call_log_path = run_dir / "call_log.json"
            resumed_log_path = run_dir / "resumed_log.json"

            def _append_call(name: str) -> None:
                log = json.loads(call_log_path.read_text(encoding="utf-8")) if call_log_path.exists() else []
                log.append(name)
                call_log_path.parent.mkdir(parents=True, exist_ok=True)
                call_log_path.write_text(json.dumps(log), encoding="utf-8")

            def _append_resumed(record: dict[str, object]) -> None:
                log = (
                    json.loads(resumed_log_path.read_text(encoding="utf-8"))
                    if resumed_log_path.exists()
                    else []
                )
                log.append(record)
                resumed_log_path.parent.mkdir(parents=True, exist_ok=True)
                resumed_log_path.write_text(json.dumps(log), encoding="utf-8")

            def handler_ok(context: StepExecutionContext) -> StepExecutionResult:
                _append_call(context.step.step_id)
                _append_resumed({"step_id": context.step.step_id, "resumed": bool(context.resumed)})
                return StepExecutionResult(outputs={"ok": context.step.step_id})

            def handler_flaky(context: StepExecutionContext) -> StepExecutionResult:
                _append_call(context.step.step_id)
                _append_resumed({"step_id": context.step.step_id, "resumed": bool(context.resumed)})
                marker = context.run_dir / "fail_once.marker"
                if not marker.exists():
                    marker.write_text("first_fail", encoding="utf-8")
                    raise RuntimeError("intentional failure")
                return StepExecutionResult(outputs={"ok": context.step.step_id})

            dag = CompiledResearchDag(
                profile_id="resume_profile",
                run_dir=str(run_dir),
                steps=(
                    DagStepSpec(step_id="a", capability="data_scope", handler="ok"),
                    DagStepSpec(step_id="b", capability="data_readiness", handler="flaky", depends_on=("a",)),
                    DagStepSpec(step_id="c", capability="report_render", handler="ok", depends_on=("b",)),
                ),
            )
            dag.validate()

            def build_context(step_id: str, step_dir: Path, resumed: bool, shared_state: dict[str, object]):
                step = next(item for item in dag.steps if item.step_id == step_id)
                return StepExecutionContext(
                    request=SimpleNamespace(mode="formal", produces=[], consumes=[]),
                    profile=SimpleNamespace(profile_id="resume_profile", formal_requires_resolver=False, runner=None),
                    dag=dag,
                    step=step,
                    run_dir=run_dir,
                    step_dir=step_dir,
                    registry_dirs={},
                    effective_capabilities=[],
                    effective_capability_metadata=[],
                    state=shared_state,
                    resumed=resumed,
                )

            with self.assertRaises(RuntimeError):
                execute_dag(
                    dag=dag,
                    request_hash="same_request",
                    plan_hash=dag.plan_hash(),
                    resume_policy="resume",
                    request_payload={"profile_id": "resume_profile"},
                    build_context=build_context,
                    handler_registry={"ok": handler_ok, "flaky": handler_flaky},
                )

            execute_dag(
                dag=dag,
                request_hash="same_request",
                plan_hash=dag.plan_hash(),
                resume_policy="resume",
                request_payload={"profile_id": "resume_profile"},
                build_context=build_context,
                handler_registry={"ok": handler_ok, "flaky": handler_flaky},
            )

            call_log = json.loads(call_log_path.read_text(encoding="utf-8"))
            resumed_log = json.loads(resumed_log_path.read_text(encoding="utf-8"))
            self.assertEqual(call_log, ["a", "b", "b", "c"])
            self.assertEqual(
                resumed_log,
                [
                    {"step_id": "a", "resumed": False},
                    {"step_id": "b", "resumed": False},
                    {"step_id": "b", "resumed": True},
                    {"step_id": "c", "resumed": False},
                ],
            )
            state = load_run_state(run_dir)
            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["completed_step_count"], 3)

    def test_execute_dag_rejects_resume_when_plan_hash_changes(self):
        with self.make_temp_dir("orch_resume_hash") as temp_dir:
            run_dir = Path(temp_dir) / "resume_hash_run"

            dag_v1 = CompiledResearchDag(
                profile_id="hash_profile",
                run_dir=str(run_dir),
                steps=(DagStepSpec(step_id="a", capability="data_scope", handler="ok"),),
            )
            dag_v1.validate()

            def build_context(step_id: str, step_dir: Path, resumed: bool, shared_state: dict[str, object]):
                step = next(item for item in dag_v1.steps if item.step_id == step_id)
                return StepExecutionContext(
                    request=SimpleNamespace(mode="formal", produces=[], consumes=[]),
                    profile=SimpleNamespace(profile_id="hash_profile", formal_requires_resolver=False, runner=None),
                    dag=dag_v1,
                    step=step,
                    run_dir=run_dir,
                    step_dir=step_dir,
                    registry_dirs={},
                    effective_capabilities=[],
                    effective_capability_metadata=[],
                    state=shared_state,
                    resumed=resumed,
                )

            execute_dag(
                dag=dag_v1,
                request_hash="same_request",
                plan_hash=dag_v1.plan_hash(),
                resume_policy="resume",
                request_payload={"profile_id": "hash_profile"},
                build_context=build_context,
                handler_registry={"ok": lambda context: StepExecutionResult(outputs={"ok": True})},
            )

            dag_v2 = CompiledResearchDag(
                profile_id="hash_profile",
                run_dir=str(run_dir),
                steps=(
                    DagStepSpec(step_id="a", capability="data_scope", handler="ok"),
                    DagStepSpec(step_id="b", capability="report_render", handler="ok", depends_on=("a",)),
                ),
            )
            dag_v2.validate()

            with self.assertRaises(ValueError):
                execute_dag(
                    dag=dag_v2,
                    request_hash="same_request",
                    plan_hash=dag_v2.plan_hash(),
                    resume_policy="resume",
                    request_payload={"profile_id": "hash_profile"},
                    build_context=build_context,
                    handler_registry={"ok": lambda context: StepExecutionResult(outputs={"ok": True})},
                )

    def test_resume_research_ignores_resume_policy_in_request_hash(self):
        with self.make_temp_dir("orch_resume_request") as temp_dir:
            run_dir = Path(temp_dir) / "benchmark_resume_run"
            request = ResearchRequest(
                profile_id="benchmark_audit",
                mode="formal",
                consumes=[],
                produces=[],
                requested_capabilities=[],
                inputs={
                    "benchmark": "000001.SH",
                    "output_dir": str(run_dir),
                },
                run_context={},
            )

            def _fake_benchmark_audit(benchmark_code: str, output_dir: Path):
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "benchmark_audit_report.md").write_text("# ok\n", encoding="utf-8")
                (output_dir / "benchmark_audit_metrics.json").write_text(
                    json.dumps({"benchmark_code": benchmark_code, "passed": True}, ensure_ascii=True, indent=2),
                    encoding="utf-8",
                )
                return BenchmarkAuditResult(
                    benchmark_code=benchmark_code,
                    row_count=10,
                    start_date="2020-01-01",
                    end_date="2020-01-31",
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

            with patch("workspace.research.alpha_mining.audit_benchmark_index.run_audit", side_effect=_fake_benchmark_audit):
                run_research(request)
                resumed = resume_research(run_dir)

            self.assertEqual(resumed.profile_id, "benchmark_audit")
            self.assertEqual(Path(resumed.run_dir), run_dir.resolve())

    def test_run_research_formal_rejects_unresolved_event_inputs(self):
        with self.make_temp_dir("orch_missing_root") as temp_dir:
            temp_root = Path(temp_dir)
            with self.assertRaises(ValueError):
                run_research(
                    _attach_formal_hypothesis(
                        ResearchRequest(
                            profile_id="event_driven_signal_research",
                            mode="formal",
                            consumes=[AssetRef(object_type="factor", object_name="missing_factor")],
                            produces=[],
                            requested_capabilities=[],
                            inputs={
                                "screening_run_dir": str(temp_root / "missing_screening"),
                                "output_dir": str(temp_root / "missing_out"),
                                "capital": 2_000_000.0,
                                "benchmark": "000905.SH",
                                "topk": 50,
                                "rebalance_days": 5,
                                "adv_median_floor": 5_000_000.0,
                                "participation_cap": 0.02,
                                "max_factors": None,
                                "max_folds": None,
                                "skip_sensitivity": False,
                                "skip_holdout": False,
                                "disable_mlflow": True,
                            },
                            run_context={
                                "registry_root": str(temp_root)
                            },
                        )
                    )
                )

    def test_theme_orchestrator_writes_dag_artifacts_and_publishes_objects(self):
        with self.make_temp_dir("orch_theme_run") as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = temp_root / "theme_strategy_small_cap_event_driven"
            run_dir.mkdir(parents=True, exist_ok=True)
            _write_theme_run(run_dir)
            args = SimpleNamespace(
                theme="small_cap",
                stage="event_driven",
                output_dir=str(run_dir),
                recipe_source_run_dir=None,
            )

            with patch.object(
                orch_steps,
                "run_theme_dataset_build_step",
                return_value={
                    "run_dir": run_dir,
                    "theme_ids": ["small_cap"],
                    "stage": "field_audit",
                    "ranking_rows": 1,
                    "ranking": [{"theme_id": "small_cap"}],
                },
            ), patch.object(
                orch_steps,
                "run_theme_universe_step",
                return_value={
                    "run_dir": run_dir,
                    "theme_ids": ["small_cap"],
                    "stage": "universe",
                    "ranking_rows": 1,
                    "ranking": [{"theme_id": "small_cap", "best_universe_id": "sc_u4"}],
                },
            ), patch.object(
                orch_steps,
                "run_theme_component_step",
                return_value={
                    "run_dir": run_dir,
                    "theme_ids": ["small_cap"],
                    "stage": "component",
                    "ranking_rows": 1,
                    "ranking": [{"theme_id": "small_cap", "selected_components": 1}],
                },
            ), patch.object(
                orch_steps,
                "run_theme_recipe_step",
                return_value={
                    "run_dir": run_dir,
                    "theme_ids": ["small_cap"],
                    "stage": "recipe",
                    "ranking_rows": 1,
                    "ranking": [{"theme_id": "small_cap", "best_recipe_id": "size_only"}],
                },
            ), patch.object(
                orch_steps,
                "run_theme_event_driven_step",
                return_value={
                    "run_dir": run_dir,
                    "theme_ids": ["small_cap"],
                    "stage": "event_driven",
                    "ranking_rows": 1,
                    "ranking": [{"theme_id": "small_cap", "best_recipe_id": "size_only"}],
                },
            ):
                request = _build_theme_request_from_args(args)
                request = _attach_formal_hypothesis(ResearchRequest(
                    profile_id=request.profile_id,
                    mode=request.mode,
                    consumes=request.consumes,
                    produces=request.produces,
                    requested_capabilities=["portfolio_assembly"],
                    inputs=request.inputs,
                    run_context={"registry_root": str(temp_root)},
                ))
                result = _run_formal_research_with_auto_gates(request)

            metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
            dag_plan = json.loads((run_dir / "dag_plan.json").read_text(encoding="utf-8"))
            dag_state = json.loads((run_dir / "dag_state.json").read_text(encoding="utf-8"))
            self.assertEqual(result.profile_id, "theme_strategy")
            self.assertEqual(metadata["candidate_registry_publish"]["status"], "completed")
            self.assertEqual(metadata["signal_registry_publish"]["status"], "completed")
            self.assertEqual(metadata["execution_model"], "dag")
            self.assertEqual(dag_plan["execution_model"], "dag")
            self.assertEqual(dag_state["status"], "completed")
            self.assertTrue((run_dir / "steps" / "event_driven_backtest" / "step_metadata.json").exists())
            self.assertTrue((run_dir / "steps" / "registry_publish" / "step_outputs.json").exists())
            self.assertIn("portfolio_construction", metadata["effective_capabilities"])
            self.assertNotIn("portfolio_assembly", metadata["effective_capabilities"])
            categories = {
                item["name"]: item["category"] for item in metadata["effective_capability_metadata"]
            }
            self.assertEqual(categories["portfolio_construction"], "core_research")
            self.assertEqual(categories["registry_publish"], "support")

            candidate_store = CandidateRegistryStore(temp_root / "candidate_registry")
            candidate_current = candidate_store.candidate_master[
                candidate_store.candidate_master["is_current"].fillna(False)
            ].copy()
            self.assertEqual(len(candidate_current), 2)

            signal_store = SignalRegistryStore(temp_root / "signal_registry")
            signal_current = signal_store.master[signal_store.master["is_current"].fillna(False)].copy()
            self.assertEqual(len(signal_current), 1)
            self.assertTrue((temp_root / "signal_registry" / "signal_registry_review.html").exists())

    def test_theme_quick_event_driven_run_succeeds_without_preexisting_root_run_metadata(self):
        with self.make_temp_dir("orch_theme_quick_run") as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = temp_root / "theme_strategy_small_cap_quick_event"
            recipe_source_run_dir = temp_root / "recipe_source"
            recipe_source_run_dir.mkdir(parents=True, exist_ok=True)
            request = _build_theme_request_from_args(
                SimpleNamespace(
                    theme="small_cap",
                    stage="event_driven",
                    output_dir=str(run_dir),
                    recipe_source_run_dir=str(recipe_source_run_dir),
                )
            )

            def _fake_quick_theme_event(**kwargs):
                _write_theme_run(run_dir)
                root_metadata = run_dir / "run_metadata.json"
                if root_metadata.exists():
                    root_metadata.unlink()
                return {
                    "run_dir": run_dir,
                    "theme_ids": ["small_cap"],
                    "stage": "event_driven",
                    "ranking_rows": 1,
                    "ranking": [{"theme_id": "small_cap", "best_recipe_id": "size_only"}],
                }

            with patch.object(orch_steps, "run_theme_event_driven_step", side_effect=_fake_quick_theme_event):
                result = _run_formal_research_with_auto_gates(
                    ResearchRequest(
                        profile_id=request.profile_id,
                        mode=request.mode,
                        consumes=request.consumes,
                        produces=request.produces,
                        requested_capabilities=request.requested_capabilities,
                        inputs=request.inputs,
                        run_context={"registry_root": str(temp_root)},
                        hypothesis=request.hypothesis,
                    )
                )

            metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
            dag_state = json.loads((run_dir / "dag_state.json").read_text(encoding="utf-8"))
            self.assertEqual(result.profile_id, "theme_strategy")
            self.assertEqual(dag_state["status"], "completed")
            self.assertEqual(metadata["signal_registry_publish"]["status"], "completed")
            self.assertTrue((run_dir / "steps" / "execution_validation" / "step_outputs.json").exists())

    def test_event_orchestrator_writes_step_outputs_and_publishes_typed_objects(self):
        with self.make_temp_dir("orch_event_run") as temp_dir:
            temp_root = Path(temp_dir)
            screening_run_dir = temp_root / "screening_run"
            _write_screening_run(screening_run_dir)
            run_dir = temp_root / "event_signal_run"
            registry_root = temp_root / "registry_root"
            factor_store = FactorRegistryStore(registry_root / "factor_registry")
            factor_store.sync_catalog(record_run=False, generated_at="2026-04-09 12:00:00")
            factor_store.save()
            request = _build_event_request_from_args(
                SimpleNamespace(
                    screening_run_dir=str(screening_run_dir),
                    output_dir=str(run_dir),
                    capital=2_000_000.0,
                    benchmark="000905.SH",
                    topk=50,
                    rebalance_days=5,
                    adv_median_floor=5_000_000.0,
                    participation_cap=0.02,
                    max_factors=None,
                    max_folds=None,
                    skip_sensitivity=False,
                    skip_holdout=False,
                    disable_mlflow=True,
                )
            )

            def _fake_signal_stage(args):
                _write_event_signal_stage(Path(args.output_dir))
                return {"run_dir": Path(args.output_dir), "candidate_count": 2, "selected_factor_rows": 1}

            def _fake_backtest_stage(args):
                _write_event_backtest_stage(Path(args.output_dir), screening_run_dir)
                return {"run_dir": Path(args.output_dir), "candidate_count": 2, "selected_factor_rows": 1}

            with patch.object(orch_steps, "run_signal_search_stage", side_effect=_fake_signal_stage), patch.object(
                orch_steps,
                "run_event_backtest_stage",
                side_effect=_fake_backtest_stage,
            ):
                result = _run_formal_research_with_auto_gates(
                    ResearchRequest(
                        profile_id=request.profile_id,
                        mode=request.mode,
                        consumes=request.consumes,
                        produces=request.produces,
                        requested_capabilities=request.requested_capabilities,
                        inputs=request.inputs,
                        run_context={
                            "registry_root": str(registry_root),
                        },
                        hypothesis=request.hypothesis,
                    )
                )

            metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
            dag_state = json.loads((run_dir / "dag_state.json").read_text(encoding="utf-8"))
            self.assertEqual(result.profile_id, "event_driven_signal_research")
            self.assertEqual(dag_state["status"], "completed")
            self.assertTrue((run_dir / "steps" / "signal_search" / "step_outputs.json").exists())
            self.assertTrue((run_dir / "steps" / "event_driven_backtest" / "step_outputs.json").exists())
            self.assertTrue((run_dir / "steps" / "registry_publish" / "step_outputs.json").exists())
            self.assertEqual(metadata["execution_model"], "dag")

            factor_store = FactorRegistryStore(temp_root / "registry_root" / "factor_registry")
            self.assertGreater(len(factor_store.factor_evidence), 0)
            signal_store = SignalRegistryStore(temp_root / "registry_root" / "signal_registry")
            signal_current = signal_store.master[signal_store.master["is_current"].fillna(False)].copy()
            self.assertEqual(len(signal_current), 1)

    def test_factor_screening_orchestrator_smoke_uses_split_steps(self):
        with self.make_temp_dir("orch_screening_run") as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = temp_root / "screening_run"
            registry_root = temp_root / "registry_root"
            request = _attach_formal_hypothesis(ResearchRequest(
                profile_id="factor_screening",
                mode="formal",
                consumes=[],
                produces=[],
                requested_capabilities=[],
                inputs={
                    "argv": [],
                    "args": {},
                    "output_dir": str(run_dir),
                },
                run_context={"registry_root": str(registry_root)},
            ))

            def _fake_screening_dataset_build(**kwargs):
                output_root = Path(kwargs["output_root"])
                output_root.mkdir(parents=True, exist_ok=True)
                cache_dir = output_root / "cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                (cache_dir / "screening_request.json").write_text(
                    json.dumps(
                        {
                            "output_dir": str(output_root),
                            "args": {},
                            "argv": [],
                        },
                        ensure_ascii=True,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                return {"run_dir": kwargs["output_root"], "request_path": "cache/screening_request.json", "argv_count": 0}

            def _fake_screening_backtest(**kwargs):
                _write_screening_run(Path(kwargs["output_root"]))
                return {
                    "run_dir": kwargs["output_root"],
                    "metadata": json.loads((Path(kwargs["output_root"]) / "factor_screening_run_metadata.json").read_text(encoding="utf-8")),
                    "report_path": str((Path(kwargs["output_root"]) / "factor_screening_report.csv").resolve()),
                }

            with patch.object(orch_steps, "run_screening_dataset_build_step", side_effect=_fake_screening_dataset_build), patch.object(
                orch_steps,
                "run_screening_vectorized_backtest_step",
                side_effect=_fake_screening_backtest,
            ):
                result = _run_formal_research_with_auto_gates(request)

            self.assertEqual(result.profile_id, "factor_screening")
            self.assertTrue((run_dir / "dag_plan.json").exists())
            self.assertTrue((run_dir / "dag_state.json").exists())
            self.assertTrue((run_dir / "run_metadata.json").exists())
            self.assertTrue((run_dir / "steps" / "registry_publish" / "step_outputs.json").exists())
            factor_store = FactorRegistryStore(registry_root / "factor_registry")
            self.assertGreater(len(factor_store.run_index), 0)

    def test_ml_orchestrator_smoke_publishes_model_signal_and_strategy(self):
        with self.make_temp_dir("orch_ml_run") as temp_dir:
            temp_root = Path(temp_dir)
            screening_run_dir = temp_root / "screening_run"
            _write_screening_run(screening_run_dir)
            baseline_run_dir = temp_root / "baseline_run"
            baseline_run_dir.mkdir(parents=True, exist_ok=True)
            (baseline_run_dir / "run_metadata.json").write_text(
                json.dumps(
                    {
                        "screening_run_dir": str(screening_run_dir),
                        "candidate_factors": ["liq_vol_cv_20d", "comp_defensive"],
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
            run_dir = temp_root / "ml_run"
            registry_root = temp_root / "registry_root"
            factor_store = FactorRegistryStore(registry_root / "factor_registry")
            factor_store.sync_catalog(record_run=False, generated_at="2026-04-09 18:00:00")
            factor_store.save()
            request = _build_ml_request_from_args(
                SimpleNamespace(
                    baseline_run_dir=str(baseline_run_dir),
                    screening_run_dir=str(screening_run_dir),
                    output_dir=str(run_dir),
                    benchmark="000001.SH",
                    label_horizon=10,
                    topk=50,
                    rebalance_days=10,
                    adv_median_floor=5_000_000.0,
                    participation_cap=0.02,
                    capital=2_000_000.0,
                    model_variants="linear",
                    disable_mlflow=True,
                )
            )

            with patch.object(orch_steps, "run_ml_dataset_build_step", return_value={"run_dir": run_dir, "candidate_factor_count": 2, "model_variants": ["linear"]}), patch.object(
                orch_steps,
                "run_ml_label_builder_step",
                return_value={"run_dir": run_dir, "window_count": 2},
            ), patch.object(
                orch_steps,
                "run_ml_model_training_step",
                return_value={"run_dir": run_dir, "variant_count": 2, "ml_variant_count": 1},
            ), patch.object(
                orch_steps,
                "run_ml_signal_search_step",
                side_effect=lambda **kwargs: (_write_ml_outputs(run_dir, baseline_run_dir, screening_run_dir) or {"run_dir": run_dir, "best_variant_id": "elasticnet", "adoption_recommendation": "pilot_candidate"}),
            ), patch.object(
                orch_steps,
                "run_ml_event_backtest_step",
                side_effect=lambda **kwargs: {"run_dir": run_dir, "base_metadata": json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8")), "best_variant_id": "elasticnet"},
            ), patch.object(
                orch_steps,
                "run_ml_experiment_tracking_step",
                return_value={"run_dir": run_dir, "tracking_status": "disabled"},
            ):
                result = _run_formal_research_with_auto_gates(
                    ResearchRequest(
                        profile_id=request.profile_id,
                        mode=request.mode,
                        consumes=request.consumes,
                        produces=request.produces,
                        requested_capabilities=request.requested_capabilities,
                        inputs=request.inputs,
                        run_context={"registry_root": str(registry_root)},
                        hypothesis=request.hypothesis,
                    )
                )

            self.assertEqual(result.profile_id, "ml_signal_model_research")
            self.assertTrue((run_dir / "dag_plan.json").exists())
            self.assertTrue((run_dir / "dag_state.json").exists())
            self.assertTrue((run_dir / "steps" / "registry_publish" / "step_outputs.json").exists())
            model_store = ModelRegistryStore(registry_root / "model_registry")
            signal_store = SignalRegistryStore(registry_root / "signal_registry")
            strategy_store = StrategyRegistryStore(registry_root / "strategy_registry")
            self.assertEqual(len(model_store.master[model_store.master["is_current"].fillna(False)]), 1)
            self.assertEqual(len(signal_store.master[signal_store.master["is_current"].fillna(False)]), 1)
            self.assertEqual(len(strategy_store.master[strategy_store.master["is_current"].fillna(False)]), 1)

    def test_strategy_improvement_orchestrator_smoke_publishes_strategy(self):
        with self.make_temp_dir("orch_improvement_run") as temp_dir:
            temp_root = Path(temp_dir)
            screening_run_dir = temp_root / "screening_run"
            _write_screening_run(screening_run_dir)
            baseline_run_dir = temp_root / "baseline_run"
            baseline_run_dir.mkdir(parents=True, exist_ok=True)
            (baseline_run_dir / "run_metadata.json").write_text(
                json.dumps(
                    {
                        "screening_run_dir": str(screening_run_dir),
                        "candidate_factors": ["liq_vol_cv_20d", "comp_defensive"],
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
            run_dir = temp_root / "improvement_run"
            registry_root = temp_root / "registry_root"
            factor_store = FactorRegistryStore(registry_root / "factor_registry")
            factor_store.sync_catalog(record_run=False, generated_at="2026-04-09 18:30:00")
            factor_store.save()
            request = _build_improvement_request_from_args(
                SimpleNamespace(
                    baseline_run_dir=str(baseline_run_dir),
                    output_dir=str(run_dir),
                    benchmark="000001.SH",
                    universe_mode="all_market",
                    selection_mode="baseline",
                    portfolio_weighting="equal",
                    topk=50,
                    rebalance_days=5,
                    slow_rebalance_days=10,
                    liquidity_scenario="adv_floor_plus_participation",
                    slippage_rate=0.0005,
                    capital=2_000_000.0,
                    adv_median_floor=5_000_000.0,
                    participation_cap=0.02,
                    max_folds=None,
                )
            )

            with patch.object(orch_steps, "run_improvement_dataset_build_step", return_value={"run_dir": run_dir, "candidate_factor_count": 2, "fold_count": 2}), patch.object(
                orch_steps,
                "run_improvement_portfolio_construction_step",
                return_value={"run_dir": run_dir, "stage_a_count": 3},
            ), patch.object(
                orch_steps,
                "run_improvement_risk_overlay_step",
                return_value={"run_dir": run_dir, "stability_pool_count": 5},
            ), patch.object(
                orch_steps,
                "run_improvement_stress_test_step",
                return_value={"run_dir": run_dir, "baseline_variant_id": "B0_baseline_sse_benchmark"},
            ), patch.object(
                orch_steps,
                "run_improvement_event_backtest_step",
                side_effect=lambda **kwargs: (_write_improvement_outputs(run_dir, baseline_run_dir, screening_run_dir) or {"run_dir": run_dir, "best_variant_id": "D_best"}),
            ), patch.object(
                orch_steps,
                "run_improvement_execution_validation_step",
                side_effect=lambda **kwargs: {"run_dir": run_dir, "base_metadata": json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8")), "best_variant_id": "D_best"},
            ):
                result = _run_formal_research_with_auto_gates(
                    ResearchRequest(
                        profile_id=request.profile_id,
                        mode=request.mode,
                        consumes=request.consumes,
                        produces=request.produces,
                        requested_capabilities=request.requested_capabilities,
                        inputs=request.inputs,
                        run_context={"registry_root": str(registry_root)},
                        hypothesis=request.hypothesis,
                    )
                )

            self.assertEqual(result.profile_id, "strategy_improvement")
            self.assertTrue((run_dir / "dag_plan.json").exists())
            self.assertTrue((run_dir / "dag_state.json").exists())
            self.assertTrue((run_dir / "steps" / "registry_publish" / "step_outputs.json").exists())
            strategy_store = StrategyRegistryStore(registry_root / "strategy_registry")
            self.assertEqual(len(strategy_store.master[strategy_store.master["is_current"].fillna(False)]), 1)

    def test_benchmark_audit_orchestrator_smoke_writes_dag_outputs(self):
        with self.make_temp_dir("orch_benchmark_run") as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = temp_root / "benchmark_run"
            request = ResearchRequest(
                profile_id="benchmark_audit",
                mode="formal",
                consumes=[],
                produces=[],
                requested_capabilities=[],
                inputs={
                    "benchmark": "000001.SH",
                    "output_dir": str(run_dir),
                },
                run_context={},
            )

            def _fake_benchmark_audit(benchmark_code: str, output_dir: Path):
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "benchmark_audit_report.md").write_text("# ok\n", encoding="utf-8")
                (output_dir / "benchmark_audit_metrics.json").write_text(
                    json.dumps({"benchmark_code": benchmark_code, "passed": True}, ensure_ascii=True, indent=2),
                    encoding="utf-8",
                )
                return BenchmarkAuditResult(
                    benchmark_code=benchmark_code,
                    row_count=10,
                    start_date="2020-01-01",
                    end_date="2020-01-31",
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

            with patch("workspace.research.alpha_mining.audit_benchmark_index.run_audit", side_effect=_fake_benchmark_audit):
                result = run_research(request)

            self.assertEqual(result.profile_id, "benchmark_audit")
            self.assertTrue((run_dir / "dag_plan.json").exists())
            self.assertTrue((run_dir / "dag_state.json").exists())
            self.assertTrue((run_dir / "run_metadata.json").exists())
            self.assertTrue((run_dir / "steps" / "benchmark_audit" / "step_outputs.json").exists())
            root_manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
            root_paths = {item["path"] for item in root_manifest["files"]}
            self.assertIn("run_metadata.json", root_paths)
            self.assertIn("review_summary.json", root_paths)
            self.assertIn("artifact_manifest.json", root_paths)
            step_manifest = json.loads(
                (run_dir / "steps" / "benchmark_audit" / "artifact_manifest.json").read_text(encoding="utf-8")
            )
            step_paths = {item["path"] for item in step_manifest["files"]}
            self.assertIn("step_metadata.json", step_paths)
            self.assertIn("step_outputs.json", step_paths)
            self.assertIn("artifact_manifest.json", step_paths)


if __name__ == "__main__":
    unittest.main()
