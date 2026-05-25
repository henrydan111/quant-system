from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from src.research_orchestrator.registries import ModelRegistryStore, SignalRegistryStore, StrategyRegistryStore
from src.research_orchestrator.registries.typed_store import TypedObjectSnapshot
from src.research_orchestrator.hypothesis import Hypothesis
from src.research_orchestrator.window_enforcement import clamp_window_to_hypothesis
from workspace.research.alpha_mining import event_driven_strategy_ml_research as ml_research


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _optional_csv(path: Path) -> pd.DataFrame:
    # Non-existent OR empty file (no columns) both mean "variant did not
    # produce this artifact" — LightGBM and rule_baseline produce no linear
    # factor weights, so the writer drops an empty file as a placeholder.
    # Treat both as empty-frame; raising EmptyDataError here aborts the whole
    # run with no useful signal.
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _optional_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _cache_dir(run_dir: Path) -> Path:
    return run_dir / "cache"


def _context_path(run_dir: Path) -> Path:
    return _cache_dir(run_dir) / "ml_bundle_context.json"


def _windows_path(run_dir: Path) -> Path:
    return _cache_dir(run_dir) / "model_windows.json"


def _training_summary_path(run_dir: Path) -> Path:
    return _cache_dir(run_dir) / "ml_training_summary.json"


def _selection_summary_path(run_dir: Path) -> Path:
    return _cache_dir(run_dir) / "ml_selection_summary.json"


def _experiment_tracking_path(run_dir: Path) -> Path:
    return _cache_dir(run_dir) / "experiment_tracking_summary.json"


def _variant_dir(run_dir: Path, variant_id: str) -> Path:
    return _cache_dir(run_dir) / "ml_variants" / variant_id


def _variant_event_report_path(run_dir: Path, variant_id: str) -> Path:
    return _variant_dir(run_dir, variant_id) / "event_driven_report.csv"


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


def _write_variant_artifact_bundle(
    *,
    run_dir: Path,
    variant_id: str,
    summary: dict[str, Any],
    oos_performance: pd.DataFrame,
    event_report: pd.DataFrame,
    signal_df: pd.DataFrame,
    signal_diagnostics: pd.DataFrame,
    prediction_df: pd.DataFrame,
    fold_metrics: pd.DataFrame,
    linear_weights: pd.DataFrame,
    feature_importance: pd.DataFrame,
) -> None:
    target = _variant_dir(run_dir, variant_id)
    target.mkdir(parents=True, exist_ok=True)
    _write_json(target / "summary.json", summary)
    oos_performance.to_csv(target / "oos_fold_performance.csv", index=False)
    event_report.to_csv(target / "event_driven_report.csv", index=False)
    signal_df.to_parquet(target / "strategy_signal.parquet", index=False)
    signal_diagnostics.to_csv(target / "signal_diagnostics.csv", index=False)
    prediction_df.to_parquet(target / "prediction_panel.parquet", index=False)
    fold_metrics.to_csv(target / "fold_metrics.csv", index=False)
    linear_weights.to_csv(target / "linear_factor_weights.csv", index=False)
    feature_importance.to_csv(target / "feature_importance.csv", index=False)


def _read_variant_summary(run_dir: Path, variant_id: str) -> dict[str, Any]:
    path = _variant_dir(run_dir, variant_id) / "summary.json"
    if not path.exists():
        return {}
    return _load_json(path)


def _read_variant_frame(run_dir: Path, variant_id: str, file_name: str) -> pd.DataFrame:
    path = _variant_dir(run_dir, variant_id) / file_name
    if path.suffix == ".parquet":
        return _optional_parquet(path)
    return _optional_csv(path)


def run_ml_dataset_build_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = ml_research.resolve_output_dir(args)
    if run_dir.resolve() != output_root.resolve():
        raise ValueError(f"ML dataset build expected run_dir {output_root}, got {run_dir}.")
    run_dir.mkdir(parents=True, exist_ok=True)
    ml_research.configure_logging(run_dir)

    model_variants = ml_research.parse_model_variants(args.model_variants)
    baseline_run_dir = Path(args.baseline_run_dir).resolve()
    screening_run_dir = Path(args.screening_run_dir).resolve()
    bundle = ml_research.load_baseline_bundle(baseline_run_dir)
    ml_research.validate_inputs(
        baseline_run_dir=baseline_run_dir,
        screening_run_dir=screening_run_dir,
        bundle=bundle,
        label_horizon=int(args.label_horizon),
    )
    bundle.run_metadata["capital"] = float(args.capital)
    start_override, end_override = _resolve_window_overrides(args, bundle.screening_metadata)
    label_forward_return = ml_research.load_forward_return_series(
        bundle,
        run_dir,
        int(args.label_horizon),
        start_override=start_override,
        end_override=end_override,
    )
    selection_forward_return = ml_research.load_forward_return_series(
        bundle,
        run_dir,
        ml_research.RULE_SELECTION_LABEL_HORIZON,
        start_override=start_override,
        end_override=end_override,
    )
    context = ml_research.load_support_context(
        bundle,
        run_dir,
        start_override=start_override,
        end_override=end_override,
    )
    effective_screening_metadata = dict(bundle.screening_metadata)
    if start_override:
        effective_screening_metadata["start_date"] = start_override
    if end_override:
        effective_screening_metadata["end_date"] = end_override

    payload = {
        "baseline_run_dir": str(baseline_run_dir),
        "screening_run_dir": str(screening_run_dir),
        "candidate_factor_count": len(bundle.candidate_factors),
        "candidate_factors": bundle.candidate_factors,
        "folds": [asdict(fold) for fold in bundle.folds],
        "holdout": asdict(bundle.holdout) if bundle.holdout is not None else None,
        "label_horizon": int(args.label_horizon),
        "selection_label_horizon": int(ml_research.RULE_SELECTION_LABEL_HORIZON),
        "model_variants": model_variants,
        "label_forward_cache": str((_cache_dir(run_dir) / f"forward_return_{int(args.label_horizon)}d.parquet").resolve()),
        "selection_forward_cache": str(
            (_cache_dir(run_dir) / f"forward_return_{int(ml_research.RULE_SELECTION_LABEL_HORIZON)}d.parquet").resolve()
        ),
        "aux_fields_cache": str((run_dir / "cache" / "aux_fields.parquet").resolve()),
        "screening_metadata": effective_screening_metadata,
        "kernel_meta": dict(bundle.run_metadata.get("kernel_meta", {})),
        "context_sizes": {
            "trade_calendar_days": len(context.trade_calendar),
            "factor_category_count": len(context.factor_category),
        },
        "series_lengths": {
            "label_forward_rows": int(len(label_forward_return)),
            "selection_forward_rows": int(len(selection_forward_return)),
        },
    }
    _write_json(_context_path(run_dir), payload)
    return {
        "run_dir": run_dir,
        "candidate_factor_count": len(bundle.candidate_factors),
        "model_variants": model_variants,
    }


def run_ml_label_builder_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = ml_research.resolve_output_dir(args)
    bundle = ml_research.load_baseline_bundle(Path(args.baseline_run_dir).resolve())
    windows = ml_research.build_model_windows(bundle.folds, bundle.holdout)
    _write_json(
        _windows_path(run_dir),
        {
            "window_count": len(windows),
            "windows": [asdict(window) for window in windows],
        },
    )
    return {
        "run_dir": run_dir,
        "window_count": len(windows),
    }


def run_ml_model_training_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = ml_research.resolve_output_dir(args)
    ml_research.configure_logging(run_dir)
    model_variants = ml_research.parse_model_variants(args.model_variants)
    baseline_run_dir = Path(args.baseline_run_dir).resolve()
    screening_run_dir = Path(args.screening_run_dir).resolve()
    bundle = ml_research.load_baseline_bundle(baseline_run_dir)
    ml_research.validate_inputs(
        baseline_run_dir=baseline_run_dir,
        screening_run_dir=screening_run_dir,
        bundle=bundle,
        label_horizon=int(args.label_horizon),
    )
    bundle.run_metadata["capital"] = float(args.capital)
    start_override, end_override = _resolve_window_overrides(args, bundle.screening_metadata)

    label_forward_return = ml_research.load_forward_return_series(
        bundle,
        run_dir,
        int(args.label_horizon),
        start_override=start_override,
        end_override=end_override,
    )
    selection_forward_return = ml_research.load_forward_return_series(
        bundle,
        run_dir,
        ml_research.RULE_SELECTION_LABEL_HORIZON,
        start_override=start_override,
        end_override=end_override,
    )
    context = ml_research.load_support_context(
        bundle,
        run_dir,
        start_override=start_override,
        end_override=end_override,
    )
    liquidity_scenarios = ml_research.build_liquidity_scenario_map(args)
    conservative_scenario = liquidity_scenarios["adv_floor_plus_participation"]
    stability_scores = ml_research.compute_stability_scores(bundle.factor_selection_decisions)
    stability_scores.to_csv(run_dir / "cache" / "stability_scores.csv", index=False)

    rule_baseline = ml_research.run_rule_baseline_same_execution(
        bundle=bundle,
        context=context,
        selection_forward_return=selection_forward_return,
        stability_scores=stability_scores,
        liquidity_scenarios=liquidity_scenarios,
        args=args,
        run_dir=run_dir,
    )
    _write_variant_artifact_bundle(
        run_dir=run_dir,
        variant_id="rule_baseline",
        summary=rule_baseline.summary,
        oos_performance=rule_baseline.oos_performance,
        event_report=rule_baseline.event_report,
        signal_df=rule_baseline.signal_df,
        signal_diagnostics=rule_baseline.signal_diagnostics,
        prediction_df=pd.DataFrame(),
        fold_metrics=pd.DataFrame(),
        linear_weights=pd.DataFrame(),
        feature_importance=pd.DataFrame(),
    )

    windows_payload = _load_json(_windows_path(run_dir))
    windows = [
        ml_research.ModelWindowSpec(**row)
        for row in list(windows_payload.get("windows", []))
    ]
    datasets = []
    for window in windows:
        datasets.append(
            ml_research.prepare_fold_dataset(
                window=window,
                candidate_factors=bundle.candidate_factors,
                processed_factor_paths=bundle.processed_factor_paths,
                forward_return=label_forward_return,
                context=context,
                rebalance_days=int(args.rebalance_days),
            )
        )

    variant_stores: dict[str, dict[str, list[Any]]] = {}
    if "linear" in model_variants:
        variant_stores["linear"] = {
            "oos_rows": [],
            "event_reports": [],
            "signal_frames": [],
            "signal_diag_frames": [],
            "prediction_frames": [],
            "metric_frames": [],
            "linear_weight_frames": [],
            "importance_frames": [],
        }
    if "lightgbm" in model_variants:
        variant_stores["lightgbm"] = {
            "oos_rows": [],
            "event_reports": [],
            "signal_frames": [],
            "signal_diag_frames": [],
            "prediction_frames": [],
            "metric_frames": [],
            "linear_weight_frames": [],
            "importance_frames": [],
        }

    for dataset in datasets:
        if "linear" in model_variants:
            linear_result = ml_research.run_elasticnet_for_window(
                dataset=dataset,
                context=context,
                scenario=conservative_scenario,
                benchmark=args.benchmark,
                topk=int(args.topk),
                capital=float(args.capital),
            )
            store = variant_stores["linear"]
            store["oos_rows"].append(linear_result["oos_row"])
            store["event_reports"].append(linear_result["event_report"])
            store["signal_frames"].append(linear_result["signal_df"])
            store["signal_diag_frames"].append(linear_result["signal_diagnostics"])
            store["prediction_frames"].append(linear_result["prediction_df"])
            store["metric_frames"].append(linear_result["fold_metrics"])
            store["linear_weight_frames"].append(linear_result["linear_weights"])
            store["importance_frames"].append(linear_result["feature_importance"])

        if "lightgbm" in model_variants:
            lightgbm_result = ml_research.run_lightgbm_for_window(
                dataset=dataset,
                context=context,
                scenario=conservative_scenario,
                benchmark=args.benchmark,
                topk=int(args.topk),
                capital=float(args.capital),
            )
            store = variant_stores["lightgbm"]
            store["oos_rows"].append(lightgbm_result["oos_row"])
            store["event_reports"].append(lightgbm_result["event_report"])
            store["signal_frames"].append(lightgbm_result["signal_df"])
            store["signal_diag_frames"].append(lightgbm_result["signal_diagnostics"])
            store["prediction_frames"].append(lightgbm_result["prediction_df"])
            store["metric_frames"].append(lightgbm_result["fold_metrics"])
            store["linear_weight_frames"].append(lightgbm_result["linear_weights"])
            store["importance_frames"].append(lightgbm_result["feature_importance"])

    variant_artifacts = []
    if "linear" in variant_stores:
        variant_artifacts.append(
            ml_research.build_model_variant_artifacts(
                spec=ml_research.MLVariantSpec("elasticnet", "linear", "ElasticNet factor-weight model"),
                **variant_stores["linear"],
            )
        )
    if "lightgbm" in variant_stores:
        variant_artifacts.append(
            ml_research.build_model_variant_artifacts(
                spec=ml_research.MLVariantSpec("lightgbm", "tree", "LightGBM direct-scoring model"),
                **variant_stores["lightgbm"],
            )
        )

    for artifacts in variant_artifacts:
        _write_variant_artifact_bundle(
            run_dir=run_dir,
            variant_id=artifacts.spec.variant_id,
            summary=artifacts.summary,
            oos_performance=artifacts.oos_performance,
            event_report=artifacts.event_report,
            signal_df=artifacts.signal_df,
            signal_diagnostics=artifacts.signal_diagnostics,
            prediction_df=artifacts.prediction_df,
            fold_metrics=artifacts.fold_metrics,
            linear_weights=artifacts.linear_weights,
            feature_importance=artifacts.feature_importance,
        )

    rule_summary = {
        **rule_baseline.summary,
        "display_name": "Rule baseline (C_stability_score, conservative 10d rerun)",
        "model_kind": "rule",
        "variant_id": "rule_baseline",
        "beats_benchmark": bool(
            pd.notna(rule_baseline.summary.get("stitched_relative_excess_return"))
            and float(rule_baseline.summary.get("stitched_relative_excess_return")) > 0
        ),
        "beats_rule_baseline": False,
        "adoption_recommendation": "reference_only",
    }
    variant_summary_rows = [rule_summary]
    for artifacts in variant_artifacts:
        summary = dict(artifacts.summary)
        summary["beats_rule_baseline"] = bool(
            pd.notna(summary.get("stitched_relative_excess_return"))
            and pd.notna(rule_summary.get("stitched_relative_excess_return"))
            and float(summary.get("stitched_relative_excess_return"))
            > float(rule_summary.get("stitched_relative_excess_return"))
        )
        summary["adoption_recommendation"] = ml_research.choose_adoption_recommendation(summary, rule_summary)
        variant_summary_rows.append(summary)

    _write_json(
        _training_summary_path(run_dir),
        {
            "baseline_run_dir": str(baseline_run_dir),
            "screening_run_dir": str(screening_run_dir),
            "model_variants": model_variants,
            "rule_summary": rule_summary,
            "variant_summary_rows": variant_summary_rows,
        },
    )
    return {
        "run_dir": run_dir,
        "variant_count": len(variant_summary_rows),
        "ml_variant_count": len(variant_artifacts),
    }


def run_ml_signal_search_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = ml_research.resolve_output_dir(args)
    training_summary = _load_json(_training_summary_path(run_dir))
    variant_summary_df = ml_research.rank_variant_summary(
        pd.DataFrame(list(training_summary.get("variant_summary_rows", [])))
    )
    ml_only_summary_df = variant_summary_df[variant_summary_df["model_kind"].isin(["linear", "tree"])].copy()
    if ml_only_summary_df.empty:
        raise ValueError("No ML variant was executed.")

    best_ml_summary = ml_only_summary_df.iloc[0].to_dict()
    adoption_recommendation = str(best_ml_summary.get("adoption_recommendation", "keep as research"))
    best_variant_id = str(best_ml_summary["variant_id"])
    rule_summary = dict(training_summary.get("rule_summary", {}))

    linear_weights = ml_research.concat_nonempty(
        [
            _read_variant_frame(run_dir, "elasticnet", "linear_factor_weights.csv"),
            _read_variant_frame(run_dir, "lightgbm", "linear_factor_weights.csv"),
        ]
    )
    feature_importance = ml_research.concat_nonempty(
        [
            _read_variant_frame(run_dir, "elasticnet", "feature_importance.csv"),
            _read_variant_frame(run_dir, "lightgbm", "feature_importance.csv"),
        ]
    )
    linear_highlights, tree_highlights = ml_research.build_factor_highlight_tables(
        linear_weights,
        feature_importance,
    )
    all_oos = ml_research.concat_nonempty(
        [
            _read_variant_frame(run_dir, "rule_baseline", "oos_fold_performance.csv").assign(variant_id="rule_baseline"),
            _read_variant_frame(run_dir, "elasticnet", "oos_fold_performance.csv").assign(variant_id="elasticnet"),
            _read_variant_frame(run_dir, "lightgbm", "oos_fold_performance.csv").assign(variant_id="lightgbm"),
        ]
    )
    weakest_folds = ml_research.build_weakest_fold_table(all_oos, best_variant_id)
    fold_model_metrics = ml_research.concat_nonempty(
        [
            _read_variant_frame(run_dir, "elasticnet", "fold_metrics.csv"),
            _read_variant_frame(run_dir, "lightgbm", "fold_metrics.csv"),
        ]
    )
    prediction_panel = ml_research.concat_nonempty(
        [
            _read_variant_frame(run_dir, "elasticnet", "prediction_panel.parquet"),
            _read_variant_frame(run_dir, "lightgbm", "prediction_panel.parquet"),
        ]
    )
    ml_master_review = ml_research.render_ml_master_review(
        variant_summary_df=variant_summary_df,
        rule_summary=rule_summary,
        best_ml_summary=best_ml_summary,
        adoption_recommendation=adoption_recommendation,
        linear_highlights=linear_highlights,
        tree_highlights=tree_highlights,
        weakest_folds=weakest_folds,
        fold_model_metrics=fold_model_metrics,
    )

    ml_research.write_text(run_dir / "ml_master_review.md", ml_master_review)
    variant_summary_df.to_csv(run_dir / "variant_comparison_summary.csv", index=False)
    fold_model_metrics.to_csv(run_dir / "fold_model_metrics.csv", index=False)
    linear_weights.to_csv(run_dir / "linear_factor_weights_by_fold.csv", index=False)
    feature_importance.to_csv(run_dir / "lightgbm_feature_importance_by_fold.csv", index=False)
    prediction_panel.to_parquet(run_dir / "prediction_panel.parquet", index=False)
    _read_variant_frame(run_dir, "rule_baseline", "event_driven_report.csv").to_csv(
        run_dir / "event_driven_report_rule_baseline.csv",
        index=False,
    )
    _read_variant_frame(run_dir, "elasticnet", "event_driven_report.csv").to_csv(
        run_dir / "event_driven_report_elasticnet.csv",
        index=False,
    )
    _read_variant_frame(run_dir, "lightgbm", "event_driven_report.csv").to_csv(
        run_dir / "event_driven_report_lightgbm.csv",
        index=False,
    )
    all_oos.to_csv(run_dir / "oos_fold_performance.csv", index=False)

    _write_json(
        _selection_summary_path(run_dir),
        {
            "best_ml_summary": best_ml_summary,
            "adoption_recommendation": adoption_recommendation,
            "rule_summary": rule_summary,
        },
    )
    return {
        "run_dir": run_dir,
        "best_variant_id": best_variant_id,
        "adoption_recommendation": adoption_recommendation,
    }


def run_ml_event_backtest_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = ml_research.resolve_output_dir(args)
    selection_summary = _load_json(_selection_summary_path(run_dir))
    best_ml_summary = dict(selection_summary.get("best_ml_summary", {}))
    best_variant_id = str(best_ml_summary.get("variant_id", "")).strip()
    best_event_report = _read_variant_frame(run_dir, best_variant_id, "event_driven_report.csv")
    if not best_event_report.empty:
        strategy_returns = pd.Series(
            best_event_report["return"].astype(float).values,
            index=pd.to_datetime(best_event_report["date"]),
            name="strategy",
        )
        benchmark_returns = (
            pd.Series(
                best_event_report["bench"].astype(float).values,
                index=pd.to_datetime(best_event_report["date"]),
                name="benchmark",
            )
            if "bench" in best_event_report.columns
            else None
        )
        ml_research.build_backtest_html(
            run_dir / "best_ml_variant_backtest_report.html",
            strategy_returns=strategy_returns,
            benchmark_returns=benchmark_returns,
            name=f"Best ML Variant: {best_ml_summary.get('display_name', best_variant_id)}",
        )

    context_payload = _load_json(_context_path(run_dir))
    model_variants = list(context_payload.get("model_variants", []))
    metadata = {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).strftime("%Y-%m-%d %H:%M:%S"),
        "baseline_run_dir": str(Path(args.baseline_run_dir).resolve()),
        "screening_run_dir": str(Path(args.screening_run_dir).resolve()),
        "benchmark": args.benchmark,
        "label_horizon": int(args.label_horizon),
        "topk": int(args.topk),
        "rebalance_days": int(args.rebalance_days),
        "capital": float(args.capital),
        "adv_median_floor": float(args.adv_median_floor),
        "participation_cap": float(args.participation_cap),
        "model_variants": model_variants,
        "candidate_factor_count": int(context_payload.get("candidate_factor_count", 0)),
        "candidate_factors": list(context_payload.get("candidate_factors", [])),
        "folds": list(context_payload.get("folds", [])),
        "holdout": context_payload.get("holdout"),
        "elasticnet_alpha_grid": list(ml_research.ELASTICNET_ALPHA_GRID),
        "elasticnet_l1_ratio_grid": list(ml_research.ELASTICNET_L1_GRID),
        "lightgbm_params": dict(ml_research.LIGHTGBM_PARAMS),
        "rule_selection_logic": "C_stability_score under the current improvement workflow",
        "rule_selection_label_horizon": int(ml_research.RULE_SELECTION_LABEL_HORIZON),
        "liquidity_policy": {
            "scenario": "adv_floor_plus_participation",
            "adv_median_floor": float(args.adv_median_floor),
            "participation_cap": float(args.participation_cap),
        },
        **ml_research.resolve_mlflow_status(None, disabled=bool(args.disable_mlflow)),
        "rule_baseline_summary": selection_summary.get("rule_summary", {}),
        "best_ml_summary": best_ml_summary,
        "adoption_recommendation": selection_summary.get("adoption_recommendation", "keep as research"),
    }
    ml_research.write_json(run_dir / "run_metadata.json", metadata)
    return {
        "run_dir": run_dir,
        "base_metadata": metadata,
        "best_variant_id": best_variant_id,
    }


def run_ml_experiment_tracking_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
) -> dict[str, Any]:
    args = SimpleNamespace(**args_payload)
    run_dir = ml_research.resolve_output_dir(args)
    selection_summary = _load_json(_selection_summary_path(run_dir))
    payload = {
        "status": "disabled" if bool(args.disable_mlflow) else "requested",
        "best_variant_id": selection_summary.get("best_ml_summary", {}).get("variant_id"),
        "adoption_recommendation": selection_summary.get("adoption_recommendation"),
    }
    _write_json(_experiment_tracking_path(run_dir), payload)
    return {
        "run_dir": run_dir,
        "tracking_status": payload["status"],
    }


def run_ml_registry_publish_step(
    *,
    output_root: Path,
    registry_dirs: dict[str, Path],
) -> dict[str, Any]:
    from src.research_orchestrator.engine import (
        _definition_hash,
        _json_dumps,
        _load_base_metadata,
        _load_optional_csv,
        _publish_typed_objects,
        _stable_object_id,
    )

    run_dir = output_root.resolve()
    metadata = _load_base_metadata(run_dir)
    generated_at = str(metadata.get("generated_at") or "")
    variant_summary_df = _load_optional_csv(run_dir / "variant_comparison_summary.csv")

    model_store = ModelRegistryStore(registry_dirs["model_registry_dir"])
    signal_store = SignalRegistryStore(registry_dirs["signal_registry_dir"])
    strategy_store = StrategyRegistryStore(registry_dirs["strategy_registry_dir"])

    model_objects: list[TypedObjectSnapshot] = []
    model_summaries: dict[str, dict[str, Any]] = {}
    produced_objects: list[dict[str, Any]] = []

    for row in variant_summary_df.to_dict(orient="records"):
        variant_id = str(row.get("variant_id", "")).strip()
        if not variant_id or variant_id == "rule_baseline":
            continue
        payload = {
            "source_profile": "ml_signal_model_research",
            "baseline_run_dir": str(metadata.get("baseline_run_dir", "")),
            "screening_run_dir": str(metadata.get("screening_run_dir", "")),
            "variant_id": variant_id,
            "model_kind": row.get("model_kind"),
            "benchmark": metadata.get("benchmark"),
            "label_horizon": metadata.get("label_horizon"),
            "topk": metadata.get("topk"),
            "rebalance_days": metadata.get("rebalance_days"),
            "model_variants": list(metadata.get("model_variants", [])),
        }
        model_hash = _definition_hash("model:ml", payload)
        model_id = _stable_object_id("model::ml", payload)
        model_name = f"ml_model_{variant_id}"
        model_objects.append(
            TypedObjectSnapshot(
                object_id=model_id,
                object_name=model_name,
                object_type="model",
                research_profile="ml_signal_model_research",
                definition_payload_json=_json_dumps(payload),
                definition_hash=model_hash,
                display_name_zh=model_name,
                recommended_status="under_review",
            )
        )
        model_summaries[model_id] = dict(row)
        produced_objects.append({"registry": "model_registry", "object_type": "model", "object_id": model_id})

    model_publish = _publish_typed_objects(
        store=model_store,
        run_type="ml_signal_model_research",
        research_profile="ml_signal_model_research",
        run_dir=run_dir,
        generated_at=generated_at,
        objects=model_objects,
        summaries_by_object_id=model_summaries,
    )

    best_ml_summary = dict(metadata.get("best_ml_summary", {}))
    best_variant_id = str(best_ml_summary.get("variant_id", "")).strip()
    signal_payload = {
        "source_profile": "ml_signal_model_research",
        "baseline_run_dir": str(metadata.get("baseline_run_dir", "")),
        "screening_run_dir": str(metadata.get("screening_run_dir", "")),
        "variant_id": best_variant_id,
        "benchmark": metadata.get("benchmark"),
        "topk": metadata.get("topk"),
        "rebalance_days": metadata.get("rebalance_days"),
        "label_horizon": metadata.get("label_horizon"),
    }
    signal_hash = _definition_hash("signal:ml", signal_payload)
    signal_id = _stable_object_id("signal::ml", signal_payload)
    signal_name = f"ml_signal_{best_variant_id or signal_hash[:8]}"
    signal_publish = _publish_typed_objects(
        store=signal_store,
        run_type="ml_signal_model_research",
        research_profile="ml_signal_model_research",
        run_dir=run_dir,
        generated_at=generated_at,
        objects=[
            TypedObjectSnapshot(
                object_id=signal_id,
                object_name=signal_name,
                object_type="signal",
                research_profile="ml_signal_model_research",
                definition_payload_json=_json_dumps(signal_payload),
                definition_hash=signal_hash,
                display_name_zh=signal_name,
                recommended_status="under_review",
            )
        ],
        summaries_by_object_id={signal_id: best_ml_summary},
    )
    produced_objects.append({"registry": "signal_registry", "object_type": "signal", "object_id": signal_id})

    strategy_payload = {
        "source_profile": "ml_signal_model_research",
        "signal_object_id": signal_id,
        "benchmark": metadata.get("benchmark"),
        "capital": metadata.get("capital"),
        "topk": metadata.get("topk"),
        "rebalance_days": metadata.get("rebalance_days"),
        "adoption_recommendation": metadata.get("adoption_recommendation"),
    }
    strategy_hash = _definition_hash("strategy:ml", strategy_payload)
    strategy_id = _stable_object_id("strategy::ml", strategy_payload)
    strategy_name = f"ml_strategy_{best_variant_id or strategy_hash[:8]}"
    strategy_publish = _publish_typed_objects(
        store=strategy_store,
        run_type="ml_signal_model_research",
        research_profile="ml_signal_model_research",
        run_dir=run_dir,
        generated_at=generated_at,
        objects=[
            TypedObjectSnapshot(
                object_id=strategy_id,
                object_name=strategy_name,
                object_type="strategy_candidate",
                research_profile="ml_signal_model_research",
                definition_payload_json=_json_dumps(strategy_payload),
                definition_hash=strategy_hash,
                display_name_zh=strategy_name,
                recommended_status="under_review",
            )
        ],
        summaries_by_object_id={strategy_id: best_ml_summary},
    )
    produced_objects.append(
        {"registry": "strategy_registry", "object_type": "strategy_candidate", "object_id": strategy_id}
    )
    return {
        "run_dir": run_dir,
        "base_metadata": metadata,
        "produced_objects": produced_objects,
        "registry_payloads": {
            "model_registry_publish": model_publish,
            "signal_registry_publish": signal_publish,
            "strategy_registry_publish": strategy_publish,
        },
    }
