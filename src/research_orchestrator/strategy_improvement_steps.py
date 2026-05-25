from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd

from src.research_orchestrator.registries import StrategyRegistryStore
from src.research_orchestrator.registries.typed_store import TypedObjectSnapshot
from src.research_orchestrator.hypothesis import Hypothesis
from src.research_orchestrator.window_enforcement import clamp_window_to_hypothesis
from workspace.research.alpha_mining.audit_benchmark_index import BenchmarkAuditResult, run_audit
from workspace.research.alpha_mining import event_driven_strategy_improvement as improvement


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _optional_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _cache_dir(run_dir: Path) -> Path:
    return run_dir / "cache"


def _context_path(run_dir: Path) -> Path:
    return _cache_dir(run_dir) / "improvement_bundle_context.json"


def _baseline_summary_path(run_dir: Path) -> Path:
    return _cache_dir(run_dir) / "baseline_summary.json"


def _benchmark_audit_path(run_dir: Path) -> Path:
    return _cache_dir(run_dir) / "benchmark_audit.json"


def _risk_overlay_path(run_dir: Path) -> Path:
    return _cache_dir(run_dir) / "risk_overlay_summary.json"


def _best_variant_cache_dir(run_dir: Path) -> Path:
    return _cache_dir(run_dir) / "best_variant_raw"


def _variant_specs_columns() -> list[str]:
    return list(improvement.VariantSpec.__annotations__.keys())


def _variant_cache_dir(run_dir: Path, variant_id: str) -> Path:
    return _cache_dir(run_dir) / "variants" / variant_id


def _resolve_window_overrides(args: SimpleNamespace, screening_metadata: dict[str, Any]) -> tuple[str | None, str | None]:
    hypothesis_payload = getattr(args, "hypothesis", None)
    if not hypothesis_payload:
        return None, None
    hypothesis = Hypothesis.from_dict(dict(hypothesis_payload))
    start_value, end_value = clamp_window_to_hypothesis(
        hypothesis,
        screening_metadata.get("start_date"),
        screening_metadata.get("end_date"),
        stage=str(getattr(args, "stage", "is_only") or "is_only"),
    )
    return start_value or None, end_value or None


def _save_variant_artifacts(run_dir: Path, artifacts: improvement.VariantArtifacts) -> None:
    target = _variant_cache_dir(run_dir, artifacts.spec.variant_id)
    target.mkdir(parents=True, exist_ok=True)
    _write_json(target / "spec.json", asdict(artifacts.spec))
    _write_json(target / "summary.json", artifacts.summary)
    artifacts.oos_performance.to_csv(target / "oos_fold_performance.csv", index=False)
    artifacts.event_report.to_csv(target / "event_report.csv", index=False)
    artifacts.trades.to_csv(target / "trades.csv", index=False)
    artifacts.order_log.to_csv(target / "order_log.csv", index=False)
    artifacts.signal_df.to_parquet(target / "signal_df.parquet", index=False)
    artifacts.signal_diagnostics.to_csv(target / "signal_diagnostics.csv", index=False)
    artifacts.selected_by_fold.to_csv(target / "selected_by_fold.csv", index=False)


def _save_best_variant_cache(run_dir: Path, artifacts: improvement.VariantArtifacts) -> None:
    target = _best_variant_cache_dir(run_dir)
    target.mkdir(parents=True, exist_ok=True)
    _write_json(target / "spec.json", asdict(artifacts.spec))
    _write_json(target / "summary.json", artifacts.summary)
    artifacts.oos_performance.to_csv(target / "oos_fold_performance.csv", index=False)
    artifacts.event_report.to_csv(target / "event_report.csv", index=False)
    artifacts.trades.to_csv(target / "trades.csv", index=False)
    artifacts.order_log.to_csv(target / "order_log.csv", index=False)
    artifacts.signal_df.to_parquet(target / "signal_df.parquet", index=False)
    artifacts.signal_diagnostics.to_csv(target / "signal_diagnostics.csv", index=False)
    artifacts.selected_by_fold.to_csv(target / "selected_by_fold.csv", index=False)


def _load_best_variant_cache(run_dir: Path) -> improvement.VariantArtifacts:
    target = _best_variant_cache_dir(run_dir)
    spec = improvement.VariantSpec(**_load_json(target / "spec.json"))
    summary = _load_json(target / "summary.json")
    return improvement.VariantArtifacts(
        spec=spec,
        summary=summary,
        oos_performance=_optional_csv(target / "oos_fold_performance.csv"),
        event_report=_optional_csv(target / "event_report.csv"),
        trades=_optional_csv(target / "trades.csv"),
        order_log=_optional_csv(target / "order_log.csv"),
        signal_df=_optional_parquet(target / "signal_df.parquet"),
        signal_diagnostics=_optional_csv(target / "signal_diagnostics.csv"),
        selected_by_fold=_optional_csv(target / "selected_by_fold.csv"),
    )


def run_improvement_dataset_build_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = improvement.resolve_output_dir(args)
    if run_dir.resolve() != output_root.resolve():
        raise ValueError(f"Improvement dataset build expected run_dir {output_root}, got {run_dir}.")
    run_dir.mkdir(parents=True, exist_ok=True)
    improvement.configure_logging(run_dir)

    baseline_run_dir = Path(args.baseline_run_dir).resolve()
    bundle = improvement.load_baseline_bundle(baseline_run_dir, max_folds=args.max_folds)
    benchmark_audit = run_audit(args.benchmark, run_dir)
    start_override, end_override = _resolve_window_overrides(args, bundle.screening_metadata)
    forward_return = improvement.load_forward_return_series(
        bundle,
        run_dir,
        start_override=start_override,
        end_override=end_override,
    )
    context = improvement.load_support_context(
        bundle,
        run_dir,
        start_override=start_override,
        end_override=end_override,
    )
    stability_scores = improvement.compute_stability_scores(bundle.factor_selection_decisions)
    stability_scores.to_csv(run_dir / "cache" / "stability_scores.csv", index=False)

    payload = {
        "baseline_run_dir": str(baseline_run_dir),
        "screening_run_dir": str(bundle.screening_run_dir),
        "benchmark": str(args.benchmark),
        "candidate_factor_count": len(bundle.candidate_factors),
        "fold_count": len(bundle.folds),
        "holdout_enabled": bundle.holdout is not None,
        "folds": [asdict(fold) for fold in bundle.folds],
        "holdout": asdict(bundle.holdout) if bundle.holdout is not None else None,
        "benchmark_audit": asdict(benchmark_audit),
        "forward_return_cache": str((run_dir / "cache" / "forward_return_5d.parquet").resolve()),
        "aux_fields_cache": str((run_dir / "cache" / "aux_fields.parquet").resolve()),
        "context_sizes": {
            "trade_calendar_days": len(context.trade_calendar),
            "factor_category_count": len(context.factor_category),
        },
        "series_lengths": {
            "forward_return_rows": int(len(forward_return)),
            "stability_rows": int(len(stability_scores)),
        },
    }
    _write_json(_context_path(run_dir), payload)
    _write_json(_benchmark_audit_path(run_dir), asdict(benchmark_audit))
    return {
        "run_dir": run_dir,
        "candidate_factor_count": len(bundle.candidate_factors),
        "fold_count": len(bundle.folds),
    }


def run_improvement_portfolio_construction_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = improvement.resolve_output_dir(args)
    stage_a_specs = improvement.build_stage_a_specs(args)
    pd.DataFrame([asdict(spec) for spec in stage_a_specs]).to_csv(run_dir / "stage_a_specs.csv", index=False)
    pd.DataFrame(columns=_variant_specs_columns()).to_csv(run_dir / "stage_b_specs.csv", index=False)
    pd.DataFrame(columns=_variant_specs_columns()).to_csv(run_dir / "stage_c_specs.csv", index=False)
    return {
        "run_dir": run_dir,
        "stage_a_count": len(stage_a_specs),
    }


def run_improvement_risk_overlay_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = improvement.resolve_output_dir(args)
    bundle = improvement.load_baseline_bundle(Path(args.baseline_run_dir).resolve(), max_folds=args.max_folds)
    stability_scores = _optional_csv(run_dir / "cache" / "stability_scores.csv")
    factor_mix = improvement.build_factor_mix_table(bundle)
    stability_pool = (
        stability_scores.sort_values(
            ["selected_frequency", "avg_abs_validation_rank_icir", "factor"],
            ascending=[False, False, True],
        ).head(improvement.STABILITY_TOP_N)
        if not stability_scores.empty
        else pd.DataFrame()
    )
    factor_mix.to_csv(run_dir / "factor_mix_table.csv", index=False)
    stability_pool.to_csv(run_dir / "stability_pool.csv", index=False)
    summary = {
        "family_caps": dict(improvement.FAMILY_CAPS),
        "stability_top_n": int(improvement.STABILITY_TOP_N),
        "stability_pool_count": int(len(stability_pool)),
        "factor_mix_count": int(len(factor_mix)),
    }
    _write_json(_risk_overlay_path(run_dir), summary)
    return {
        "run_dir": run_dir,
        "stability_pool_count": int(len(stability_pool)),
    }


def run_improvement_stress_test_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = improvement.resolve_output_dir(args)
    bundle = improvement.load_baseline_bundle(Path(args.baseline_run_dir).resolve(), max_folds=args.max_folds)
    start_override, end_override = _resolve_window_overrides(args, bundle.screening_metadata)
    forward_return = improvement.load_forward_return_series(
        bundle,
        run_dir,
        start_override=start_override,
        end_override=end_override,
    )
    context = improvement.load_support_context(
        bundle,
        run_dir,
        start_override=start_override,
        end_override=end_override,
    )
    stability_scores = _optional_csv(run_dir / "cache" / "stability_scores.csv")
    liquidity_scenarios = improvement.build_liquidity_scenario_map(args)

    b0_spec = improvement.VariantSpec(
        stage="B0",
        variant_id="B0_baseline_sse_benchmark",
        description="Frozen formal baseline, rerun against the SSE Composite benchmark.",
        benchmark=args.benchmark,
        universe_mode=args.universe_mode,
        selection_mode="baseline",
        portfolio_weighting="equal",
        topk=args.topk,
        rebalance_days=args.rebalance_days,
        slow_rebalance_days=args.slow_rebalance_days,
        liquidity_scenario="adv_floor_plus_participation",
        slippage_rate=args.slippage_rate,
    )
    baseline_artifacts = improvement.evaluate_variant(
        spec=b0_spec,
        bundle=bundle,
        context=context,
        forward_return=forward_return,
        stability_scores=stability_scores,
        liquidity_scenarios=liquidity_scenarios,
        run_dir=run_dir,
        keep_detail=True,
    )
    _write_json(_baseline_summary_path(run_dir), baseline_artifacts.summary)

    year_diag = improvement.build_year_regime_diagnostics(baseline_artifacts.oos_performance, args.benchmark)
    expression_diag = improvement.build_portfolio_expression_diagnostics(baseline_artifacts.signal_df)
    exposure_diag = improvement.build_benchmark_relative_exposure(baseline_artifacts.signal_df, context, args.benchmark)
    factor_mix = improvement.build_factor_mix_table(bundle)
    slow_factor_diag = improvement.build_slow_factor_diag(bundle)
    benchmark_note = (
        "Local monthly index_weights snapshots currently cover CSI families but do not provide a direct "
        "000001.SH constituent-weight history, so this exposure file is a broad style / exchange diagnostic "
        "instead of an exact constituent-level attribution."
    )
    benchmark_audit = BenchmarkAuditResult(**_load_json(_benchmark_audit_path(run_dir)))
    improvement.write_text(
        run_dir / "strategy_gap_attribution.md",
        improvement.build_gap_attribution_markdown(
            benchmark_audit=benchmark_audit,
            benchmark_note=benchmark_note,
            baseline_summary=baseline_artifacts.summary,
            year_diag=year_diag,
            expression_diag=expression_diag,
            exposure_diag=exposure_diag,
            factor_mix=factor_mix,
            slow_factor_diag=slow_factor_diag,
        ),
    )
    year_diag.to_csv(run_dir / "year_regime_diagnostics.csv", index=False)
    expression_diag.to_csv(run_dir / "portfolio_expression_diagnostics.csv", index=False)
    exposure_diag.to_csv(run_dir / "benchmark_relative_exposure.csv", index=False)
    return {
        "run_dir": run_dir,
        "baseline_variant_id": baseline_artifacts.spec.variant_id,
    }


def run_improvement_event_backtest_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = improvement.resolve_output_dir(args)
    bundle = improvement.load_baseline_bundle(Path(args.baseline_run_dir).resolve(), max_folds=args.max_folds)
    start_override, end_override = _resolve_window_overrides(args, bundle.screening_metadata)
    forward_return = improvement.load_forward_return_series(
        bundle,
        run_dir,
        start_override=start_override,
        end_override=end_override,
    )
    context = improvement.load_support_context(
        bundle,
        run_dir,
        start_override=start_override,
        end_override=end_override,
    )
    stability_scores = _optional_csv(run_dir / "cache" / "stability_scores.csv")
    liquidity_scenarios = improvement.build_liquidity_scenario_map(args)

    stage_a_specs = improvement.build_stage_a_specs(args)
    stage_a_artifacts: list[improvement.VariantArtifacts] = []
    for spec in stage_a_specs:
        artifacts = improvement.evaluate_variant(
            spec=spec,
            bundle=bundle,
            context=context,
            forward_return=forward_return,
            stability_scores=stability_scores,
            liquidity_scenarios=liquidity_scenarios,
            run_dir=run_dir,
            keep_detail=False,
        )
        stage_a_artifacts.append(artifacts)
        _save_variant_artifacts(run_dir, artifacts)
    pd.DataFrame([asdict(spec) for spec in stage_a_specs]).to_csv(run_dir / "stage_a_specs.csv", index=False)
    stage_summary_df = improvement.sort_variant_summary(pd.DataFrame([art.summary for art in stage_a_artifacts]))

    best_a = improvement.choose_stage_winner(stage_summary_df, "A")
    stage_b_specs = improvement.build_stage_b_specs(best_a, args)
    stage_b_artifacts: list[improvement.VariantArtifacts] = []
    for spec in stage_b_specs:
        artifacts = improvement.evaluate_variant(
            spec=spec,
            bundle=bundle,
            context=context,
            forward_return=forward_return,
            stability_scores=stability_scores,
            liquidity_scenarios=liquidity_scenarios,
            run_dir=run_dir,
            keep_detail=False,
        )
        stage_b_artifacts.append(artifacts)
        _save_variant_artifacts(run_dir, artifacts)
    pd.DataFrame([asdict(spec) for spec in stage_b_specs]).to_csv(run_dir / "stage_b_specs.csv", index=False)
    stage_summary_df = improvement.sort_variant_summary(
        pd.concat([stage_summary_df, pd.DataFrame([art.summary for art in stage_b_artifacts])], ignore_index=True)
    )

    best_b = improvement.choose_stage_winner(stage_summary_df, "B")
    stage_c_specs = improvement.build_stage_c_specs(best_b, args)
    stage_c_artifacts: list[improvement.VariantArtifacts] = []
    for spec in stage_c_specs:
        artifacts = improvement.evaluate_variant(
            spec=spec,
            bundle=bundle,
            context=context,
            forward_return=forward_return,
            stability_scores=stability_scores,
            liquidity_scenarios=liquidity_scenarios,
            run_dir=run_dir,
            keep_detail=False,
        )
        stage_c_artifacts.append(artifacts)
        _save_variant_artifacts(run_dir, artifacts)
    pd.DataFrame([asdict(spec) for spec in stage_c_specs]).to_csv(run_dir / "stage_c_specs.csv", index=False)
    stage_summary_df = improvement.sort_variant_summary(
        pd.concat([stage_summary_df, pd.DataFrame([art.summary for art in stage_c_artifacts])], ignore_index=True)
    )

    best_c = improvement.choose_stage_winner(stage_summary_df, "C")
    best_variant = improvement.evaluate_variant(
        spec=improvement.VariantSpec(stage="D", **{k: v for k, v in asdict(best_c).items() if k != "stage"}),
        bundle=bundle,
        context=context,
        forward_return=forward_return,
        stability_scores=stability_scores,
        liquidity_scenarios=liquidity_scenarios,
        run_dir=run_dir,
        keep_detail=True,
    )
    _save_best_variant_cache(run_dir, best_variant)

    experiment_grid = stage_summary_df.copy()
    experiment_grid.to_csv(run_dir / "improvement_experiment_grid.csv", index=False)
    variant_summary = improvement.sort_variant_summary(
        pd.concat([stage_summary_df, pd.DataFrame([best_variant.summary])], ignore_index=True)
        .drop_duplicates(subset=["variant_id"], keep="last")
    )
    variant_summary.to_csv(run_dir / "variant_comparison_summary.csv", index=False)
    _write_json(
        _cache_dir(run_dir) / "improvement_stage_winners.json",
        {
            "best_stage_a": asdict(best_a),
            "best_stage_b": asdict(best_b),
            "best_stage_c": asdict(best_c),
            "best_variant": best_variant.summary,
        },
    )
    return {
        "run_dir": run_dir,
        "best_variant_id": best_variant.spec.variant_id,
    }


def run_improvement_execution_validation_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = improvement.resolve_output_dir(args)
    best_variant = _load_best_variant_cache(run_dir)
    improvement.persist_best_variant(best_variant, run_dir)

    benchmark_audit = BenchmarkAuditResult(**_load_json(_benchmark_audit_path(run_dir)))
    baseline_summary = _load_json(_baseline_summary_path(run_dir))
    variant_summary = _optional_csv(run_dir / "variant_comparison_summary.csv")
    master_review = improvement.build_improvement_master_review(
        benchmark_audit=benchmark_audit,
        baseline_summary=baseline_summary,
        variant_summary=variant_summary,
        best_variant=best_variant,
    )
    improvement.write_text(run_dir / "improvement_master_review.md", master_review)

    stage_winners = _load_json(_cache_dir(run_dir) / "improvement_stage_winners.json")
    bundle = improvement.load_baseline_bundle(Path(args.baseline_run_dir).resolve(), max_folds=args.max_folds)
    run_metadata = {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).strftime("%Y-%m-%d %H:%M:%S"),
        "baseline_run_dir": str(Path(args.baseline_run_dir).resolve()),
        "screening_run_dir": str(bundle.screening_run_dir),
        "benchmark": args.benchmark,
        "capital": args.capital,
        "default_topk": args.topk,
        "default_rebalance_days": args.rebalance_days,
        "slow_rebalance_days": args.slow_rebalance_days,
        "adv_median_floor": args.adv_median_floor,
        "participation_cap": args.participation_cap,
        "benchmark_audit": asdict(benchmark_audit),
        "baseline_summary": baseline_summary,
        "best_stage_a": stage_winners.get("best_stage_a", {}),
        "best_stage_b": stage_winners.get("best_stage_b", {}),
        "best_stage_c": stage_winners.get("best_stage_c", {}),
        "best_variant": best_variant.summary,
        "candidate_factor_count": len(bundle.candidate_factors),
        "fold_count": len(bundle.folds),
        "holdout_enabled": bundle.holdout is not None,
        "promotion_gates": {
            "stitched_relative_excess_return_min": 0.10,
            "positive_excess_folds_min": 5,
            "holdout_relative_excess_return_min": 0.0,
            "worst_max_drawdown_min": -0.30,
            "turnover_and_blocked_ratio_are_hard_gates": False,
        },
    }
    improvement.write_json(run_dir / "run_metadata.json", run_metadata)
    return {
        "run_dir": run_dir,
        "base_metadata": run_metadata,
        "best_variant_id": best_variant.spec.variant_id,
    }


def run_improvement_registry_publish_step(
    *,
    output_root: Path,
    strategy_registry_dir: Path,
) -> dict[str, Any]:
    from src.research_orchestrator.engine import (
        _definition_hash,
        _json_dumps,
        _load_base_metadata,
        _publish_typed_objects,
        _stable_object_id,
    )

    run_dir = output_root.resolve()
    metadata = _load_base_metadata(run_dir)
    generated_at = str(metadata.get("generated_at") or "")
    best_variant = dict(metadata.get("best_variant", {}))
    strategy_payload = {
        "source_profile": "strategy_improvement",
        "baseline_run_dir": str(metadata.get("baseline_run_dir", "")),
        "screening_run_dir": str(metadata.get("screening_run_dir", "")),
        "benchmark": metadata.get("benchmark"),
        "best_variant": best_variant,
        "default_topk": metadata.get("default_topk"),
        "default_rebalance_days": metadata.get("default_rebalance_days"),
        "slow_rebalance_days": metadata.get("slow_rebalance_days"),
    }
    strategy_hash = _definition_hash("strategy:improvement", strategy_payload)
    strategy_id = _stable_object_id("strategy::improvement", strategy_payload)
    strategy_name = f"improved_strategy_{str(best_variant.get('variant_id', strategy_hash[:8]))}"

    strategy_store = StrategyRegistryStore(strategy_registry_dir)
    strategy_publish = _publish_typed_objects(
        store=strategy_store,
        run_type="strategy_improvement",
        research_profile="strategy_improvement",
        run_dir=run_dir,
        generated_at=generated_at,
        objects=[
            TypedObjectSnapshot(
                object_id=strategy_id,
                object_name=strategy_name,
                object_type="strategy_candidate",
                research_profile="strategy_improvement",
                definition_payload_json=_json_dumps(strategy_payload),
                definition_hash=strategy_hash,
                display_name_zh=strategy_name,
                recommended_status="under_review",
            )
        ],
        summaries_by_object_id={strategy_id: best_variant},
    )
    return {
        "run_dir": run_dir,
        "base_metadata": metadata,
        "produced_objects": [
            {
                "registry": "strategy_registry",
                "object_type": "strategy_candidate",
                "object_id": strategy_id,
            }
        ],
        "registry_payloads": {"strategy_registry_publish": strategy_publish},
    }
