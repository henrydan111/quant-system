from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.alpha_research.walk_forward import (
    FoldSpec,
    HoldoutSpec,
    STEP_YEARS,
    TEST_YEARS,
    TRAIN_YEARS,
    VALIDATION_YEARS,
    build_walk_forward_folds,
)
from src.research_orchestrator.window_enforcement import clamp_window_to_hypothesis
from workspace.research.alpha_mining import event_driven_strategy_research as event_research


def research_context_path(run_dir: Path) -> Path:
    return run_dir / "cache" / "research_context.json"


def forward_return_cache_path(run_dir: Path) -> Path:
    return run_dir / "cache" / "forward_return.parquet"


def aux_fields_cache_path(run_dir: Path) -> Path:
    return run_dir / "cache" / "aux_fields.parquet"


def load_research_context(run_dir: Path) -> dict[str, Any]:
    return json.loads(research_context_path(run_dir).read_text(encoding="utf-8"))


def _prepare_signal_stage_inputs(args) -> dict[str, Any]:
    screening_run_dir = Path(args.screening_run_dir).resolve()
    run_dir = event_research.resolve_output_dir(args)
    event_research.configure_logging(run_dir)
    event_research.LOGGER.info("Starting event-driven strategy signal-research stage")
    event_research.LOGGER.info("Screening input: %s", screening_run_dir)
    _ = event_research.load_config()

    report_df, screening_metadata = event_research.load_screening_inputs(screening_run_dir)
    screening_metadata["screening_run_dir"] = str(screening_run_dir)
    hypothesis_payload = getattr(args, "hypothesis", None)
    if hypothesis_payload:
        from src.research_orchestrator.hypothesis import Hypothesis

        hypothesis = Hypothesis.from_dict(dict(hypothesis_payload))
        step_stage = str(getattr(args, "stage", "is_only") or "is_only")
        start_value, end_value = clamp_window_to_hypothesis(
            hypothesis,
            screening_metadata.get("start_date"),
            screening_metadata.get("end_date"),
            stage=step_stage,
        )
        if start_value:
            screening_metadata["start_date"] = start_value
        if end_value:
            screening_metadata["end_date"] = end_value
        if step_stage != "oos_test":
            setattr(args, "skip_holdout", True)
    candidate_df = report_df.loc[
        report_df["grade"].astype(str).str.startswith(("A", "B"))
    ].copy()
    candidate_df = candidate_df.sort_values(
        ["grade", "abs_icir", "factor"],
        ascending=[True, False, True],
    )
    if args.max_factors is not None:
        candidate_df = candidate_df.head(args.max_factors).copy()
    candidate_factors = candidate_df["factor"].tolist()
    if not candidate_factors:
        raise ValueError("No A/B factors were found in the screening report.")

    folds, holdout_spec = build_walk_forward_folds(
        screening_metadata["start_date"],
        screening_metadata["end_date"],
    )
    if args.max_folds is not None:
        folds = folds[: args.max_folds]
    if args.skip_holdout:
        holdout_spec = None

    factor_meta = event_research.build_factor_meta(
        candidate_factors,
        include_new_data=bool(screening_metadata.get("include_new_data", True)),
    )
    raw_factor_paths, fwd_df, aux_df, kernel_meta = event_research.compute_factor_inputs(
        screening_metadata=screening_metadata,
        candidate_factors=candidate_factors,
        run_dir=run_dir,
    )
    forward_return = fwd_df[f"fwd_{event_research.STRATEGY_HORIZON}d"].astype(np.float32)
    event_research.write_series_parquet(forward_return, forward_return_cache_path(run_dir))
    aux_fields_cache_path(run_dir).parent.mkdir(parents=True, exist_ok=True)
    aux_df.to_parquet(aux_fields_cache_path(run_dir))
    candidate_df.to_csv(run_dir / "candidate_snapshot.csv", index=False)
    event_research.write_json(
        research_context_path(run_dir),
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "screening_run_dir": str(screening_run_dir),
            "screening_metadata": screening_metadata,
            "candidate_factors": candidate_factors,
            "factor_meta": factor_meta,
            "kernel_meta": kernel_meta,
            "folds": [asdict(fold) for fold in folds],
            "holdout": asdict(holdout_spec) if holdout_spec is not None else None,
            "raw_factor_paths": {name: str(path) for name, path in raw_factor_paths.items()},
        },
    )
    return {
        "run_dir": run_dir,
        "screening_run_dir": screening_run_dir,
        "screening_metadata": screening_metadata,
        "candidate_df": candidate_df,
        "candidate_factors": candidate_factors,
        "factor_meta": factor_meta,
        "kernel_meta": kernel_meta,
        "folds": folds,
        "holdout_spec": holdout_spec,
        "raw_factor_paths": raw_factor_paths,
        "aux_df": aux_df,
        "forward_return": forward_return,
    }


def _run_factor_research_and_selection(prepared: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(prepared["run_dir"])
    data_dir = event_research.PROJECT_ROOT / "data"
    candidate_df = prepared["candidate_df"]
    candidate_factors = prepared["candidate_factors"]
    factor_meta = prepared["factor_meta"]
    raw_factor_paths = prepared["raw_factor_paths"]
    aux_df = prepared["aux_df"]
    forward_return = prepared["forward_return"]
    folds = prepared["folds"]

    # SW2021 time-varying industry replaces the prior static
    # stock_basic.industry lookup (110-value Tushare proprietary taxonomy
    # → wrong taxonomy + no history). See plan vast-exploring-rabbit v8.
    from src.data_infra.provider_metadata import build_industry_series_asof
    adj_close = aux_df["adj_close"].astype(np.float32)
    market_cap = aux_df["market_cap"].astype(np.float32)

    processed_factor_dir = run_dir / "cache" / "processed_factors"
    processed_factor_dir.mkdir(parents=True, exist_ok=True)
    processed_factor_paths: dict[str, Path] = {}
    factor_fold_metrics_frames: list[pd.DataFrame] = []
    factor_metric_rows: list[dict[str, Any]] = []
    factor_research_payloads: dict[str, dict[str, Any]] = {}

    for idx, factor in enumerate(candidate_factors, start=1):
        event_research.LOGGER.info(
            "Researching factor %d/%d: %s",
            idx,
            len(candidate_factors),
            factor,
        )
        screening_row = candidate_df[candidate_df["factor"] == factor].iloc[0]
        raw_series = event_research.read_series_parquet(raw_factor_paths[factor])
        aligned_market_cap = market_cap.reindex(raw_series.index)
        industry_series = build_industry_series_asof(raw_series.index, "L1")

        raw_variant = event_research.preprocess_variant(raw_series)
        size_variant = event_research.cs_zscore(
            event_research.neutralize_size(
                event_research.winsorize(raw_series),
                aligned_market_cap,
            )
        ).astype(np.float32)
        industry_variant = event_research.cs_zscore(
            event_research.neutralize_industry(
                event_research.winsorize(raw_series),
                industry_series,
            )
        ).astype(np.float32)
        strategy_variant = event_research.cs_zscore(
            event_research.neutralize_size_industry(
                event_research.winsorize(raw_series),
                aligned_market_cap,
                industry_series,
            )
        ).astype(np.float32)
        processed_path = processed_factor_dir / f"{factor}.parquet"
        event_research.write_series_parquet(strategy_variant, processed_path)
        processed_factor_paths[factor] = processed_path

        neutralization_summary = pd.DataFrame(
            [
                event_research.summarize_variant("raw", raw_variant, forward_return),
                event_research.summarize_variant("size_neutral", size_variant, forward_return),
                event_research.summarize_variant("industry_neutral", industry_variant, forward_return),
                event_research.summarize_variant("size_industry_neutral", strategy_variant, forward_return),
            ]
        )
        fold_metrics = event_research.compute_fold_metrics_for_factor(
            factor,
            strategy_variant,
            forward_return,
            folds,
        )
        factor_fold_metrics_frames.append(fold_metrics)

        ic_series = event_research.compute_ic_series(strategy_variant, forward_return)
        ic_summary = event_research.compute_ic_summary(ic_series) if not ic_series.empty else {}
        yearly_ic = event_research.compute_ic_by_year(ic_series) if not ic_series.empty else pd.DataFrame()
        rolling_ic = (
            event_research.compute_rolling_ic(ic_series, window=event_research.ROLLING_IC_WINDOW)
            if not ic_series.empty
            else pd.DataFrame()
        )
        decay_df = event_research.compute_ic_decay(strategy_variant, adj_close)
        optimal_horizon = event_research.find_optimal_horizon(decay_df)
        quantile_df = event_research.compute_quantile_returns(strategy_variant, forward_return, n_quantiles=5)
        quantile_summary = event_research.compute_quantile_summary(quantile_df) if not quantile_df.empty else pd.DataFrame()
        long_short_returns = event_research.compute_long_short_returns(quantile_df) if not quantile_df.empty else pd.Series(dtype=float)
        long_short_stats = event_research.compute_long_short_stats(long_short_returns)
        monotonicity = (
            event_research.test_monotonicity(quantile_summary)
            if not quantile_summary.empty
            else {"is_monotonic": False, "spearman_corr": np.nan, "p_value": np.nan, "direction": "unknown"}
        )
        factor_research_payloads[factor] = {
            "neutralization_summary": neutralization_summary,
            "yearly_ic": yearly_ic,
            "rolling_ic_tail": rolling_ic.tail(24),
            "decay_df": decay_df,
            "optimal_horizon": optimal_horizon,
            "quantile_summary": quantile_summary,
            "long_short_stats": long_short_stats,
            "monotonicity": monotonicity,
            "risks": event_research.derive_factor_risks(screening_row, fold_metrics, monotonicity),
        }
        factor_metric_rows.append(
            {
                "factor": factor,
                "grade": screening_row["grade"],
                "category": factor_meta[factor]["category"],
                "mean_rank_ic_5d": ic_summary.get("mean_rank_ic"),
                "rank_icir_5d": ic_summary.get("rank_icir"),
                "ic_hit_rate_5d": ic_summary.get("ic_hit_rate"),
                "best_decay_horizon": optimal_horizon.get("best_horizon_icir"),
                "peak_decay_icir": optimal_horizon.get("peak_icir"),
                "ls_ann_return": long_short_stats.get("ls_ann_return"),
                "monotonic": monotonicity.get("is_monotonic"),
            }
        )

    factor_fold_metrics_df = pd.concat(factor_fold_metrics_frames, ignore_index=True) if factor_fold_metrics_frames else pd.DataFrame()
    return {
        "run_dir": run_dir,
        "candidate_df": candidate_df,
        "candidate_factors": candidate_factors,
        "factor_meta": factor_meta,
        "folds": folds,
        "forward_return": forward_return,
        "processed_factor_paths": processed_factor_paths,
        "factor_fold_metrics_df": factor_fold_metrics_df,
        "factor_metric_rows": factor_metric_rows,
        "factor_research_payloads": factor_research_payloads,
    }


def run_signal_search_stage(args) -> dict[str, Any]:
    prepared = _prepare_signal_stage_inputs(args)
    research = _run_factor_research_and_selection(prepared)
    run_dir = Path(research["run_dir"])
    candidate_df = research["candidate_df"]
    candidate_factors = research["candidate_factors"]
    factor_meta = research["factor_meta"]
    folds = research["folds"]
    forward_return = research["forward_return"]
    processed_factor_paths = research["processed_factor_paths"]
    factor_fold_metrics_df = research["factor_fold_metrics_df"]
    factor_metric_rows = research["factor_metric_rows"]
    factor_research_payloads = research["factor_research_payloads"]

    selected_frames: list[pd.DataFrame] = []
    decision_frames: list[pd.DataFrame] = []
    marginal_frames: list[pd.DataFrame] = []
    fold_overview_rows: list[dict[str, Any]] = []

    for fold in folds:
        fold_selected, fold_decisions, fold_marginals = event_research.select_core_factors_for_fold(
            fold=fold,
            candidate_summary=factor_fold_metrics_df,
            processed_factor_paths=processed_factor_paths,
            forward_return=forward_return,
        )
        selected_frames.append(fold_selected)
        decision_frames.append(fold_decisions)
        marginal_frames.append(fold_marginals)
        fold_overview_rows.append(
            {
                "fold_id": fold.fold_id,
                "train_start": fold.train_start,
                "train_end": fold.train_end,
                "validation_start": fold.validation_start,
                "validation_end": fold.validation_end,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
                "qualified_count": int(fold_decisions["validation_pass"].sum()) if not fold_decisions.empty else 0,
                "selected_count": int(len(fold_selected)),
                "downgraded": bool(len(fold_selected) < event_research.MIN_SELECTED_FACTORS),
            }
        )

    selected_by_fold_df = (
        pd.concat([frame for frame in selected_frames if not frame.empty], ignore_index=True)
        if selected_frames
        else pd.DataFrame()
    )
    factor_selection_decisions_df = (
        pd.concat([frame for frame in decision_frames if not frame.empty], ignore_index=True)
        if decision_frames
        else pd.DataFrame()
    )
    marginal_df = (
        pd.concat([frame for frame in marginal_frames if not frame.empty], ignore_index=True)
        if marginal_frames
        else pd.DataFrame()
    )

    factor_cards_dir = run_dir / "factor_cards"
    factor_cards_dir.mkdir(parents=True, exist_ok=True)
    overall_decision_rows: list[dict[str, Any]] = []
    for factor in candidate_factors:
        factor_decisions = factor_selection_decisions_df[factor_selection_decisions_df["factor"] == factor].copy()
        factor_fold_view = factor_fold_metrics_df[factor_fold_metrics_df["factor"] == factor].copy()
        selected_fold_ids = set(
            factor_selection_decisions_df.loc[
                (factor_selection_decisions_df["factor"] == factor)
                & factor_selection_decisions_df["selected"],
                "fold_id",
            ]
        )
        factor_fold_view["selected"] = factor_fold_view["fold_id"].isin(selected_fold_ids)
        decision_summary = event_research.build_factor_conclusion(
            factor,
            factor_decisions if not factor_decisions.empty else factor_fold_view,
        )
        majority_direction = 1 if factor_fold_view["train_direction"].mean() >= 0 else -1 if not factor_fold_view.empty else 1
        factor_meta[factor]["strategy_direction_label"] = "high_is_good" if majority_direction >= 0 else "low_is_good"
        correlation_rows = (
            factor_selection_decisions_df.loc[
                factor_selection_decisions_df["factor"] == factor,
                ["fold_id", "max_abs_corr"],
            ]
            .rename(columns={"max_abs_corr": "abs_corr"})
            .assign(cluster_id="selected_cluster", peer_factor="selected_cluster_peer")
        )
        marginal_rows = marginal_df[marginal_df["factor"] == factor].copy()
        screening_snapshot = candidate_df[candidate_df["factor"] == factor].iloc[0].to_dict()
        payload = factor_research_payloads[factor]
        card_text = event_research.render_factor_card(
            factor_name=factor,
            factor_meta=factor_meta[factor],
            screening_snapshot=screening_snapshot,
            fold_metrics=factor_fold_view,
            neutralization_summary=payload["neutralization_summary"],
            yearly_ic=payload["yearly_ic"],
            rolling_ic_tail=payload["rolling_ic_tail"],
            decay_df=payload["decay_df"],
            optimal_horizon=payload["optimal_horizon"],
            quantile_summary=payload["quantile_summary"],
            long_short_stats=payload["long_short_stats"],
            monotonicity=payload["monotonicity"],
            correlation_rows=correlation_rows,
            marginal_rows=marginal_rows,
            risks=payload["risks"],
            conclusion=decision_summary,
        )
        event_research.write_text(factor_cards_dir / f"{factor}.md", card_text)
        overall_decision_rows.append(
            {
                "factor": factor,
                "grade": screening_snapshot["grade"],
                "category": factor_meta[factor]["category"],
                "overall_decision": decision_summary["decision"],
                "selected_count": decision_summary["selected_count"],
                "validation_pass_count": decision_summary["validation_pass_count"],
                "avg_validation_rank_icir": factor_fold_view["val_rank_icir"].mean() if not factor_fold_view.empty else np.nan,
                "max_abs_corr": factor_decisions["max_abs_corr"].max() if not factor_decisions.empty else np.nan,
            }
        )

    factor_research_metrics_df = pd.DataFrame(factor_metric_rows)
    fold_overview_df = pd.DataFrame(fold_overview_rows)
    overall_factor_decisions_df = pd.DataFrame(overall_decision_rows)
    factor_research_metrics_df.to_csv(run_dir / "factor_research_metrics.csv", index=False)
    factor_selection_decisions_df.to_csv(run_dir / "factor_selection_decisions.csv", index=False)
    selected_by_fold_df.to_csv(run_dir / "selected_core_factors_by_fold.csv", index=False)
    fold_overview_df.to_csv(run_dir / "fold_overview.csv", index=False)
    overall_factor_decisions_df.to_csv(run_dir / "overall_factor_decisions.csv", index=False)
    event_research.write_json(
        run_dir / "signal_stage_metadata.json",
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "candidate_count": len(candidate_factors),
            "selected_factor_rows": int(len(selected_by_fold_df)),
            "factor_card_count": len(candidate_factors),
            "fold_count": len(folds),
            "has_holdout": prepared["holdout_spec"] is not None,
        },
    )
    event_research.LOGGER.info("Signal-research stage complete: %s", run_dir)
    return {
        "run_dir": run_dir,
        "candidate_count": len(candidate_factors),
        "selected_factor_rows": len(selected_by_fold_df),
    }


def _load_backtest_inputs(args) -> dict[str, Any]:
    run_dir = event_research.resolve_output_dir(args)
    event_research.configure_logging(run_dir)
    context = load_research_context(run_dir)
    candidate_factors = [str(item) for item in context.get("candidate_factors", [])]
    folds = [FoldSpec(**item) for item in context.get("folds", [])]
    holdout_spec = HoldoutSpec(**context["holdout"]) if context.get("holdout") else None
    factor_meta = {str(key): dict(value) for key, value in context.get("factor_meta", {}).items()}
    screening_metadata = dict(context["screening_metadata"])
    candidate_df = pd.read_csv(run_dir / "candidate_snapshot.csv")
    factor_selection_decisions_df = pd.read_csv(run_dir / "factor_selection_decisions.csv")
    selected_by_fold_df = pd.read_csv(run_dir / "selected_core_factors_by_fold.csv")
    fold_overview_df = pd.read_csv(run_dir / "fold_overview.csv")
    overall_factor_decisions_df = pd.read_csv(run_dir / "overall_factor_decisions.csv")
    factor_research_metrics_df = pd.read_csv(run_dir / "factor_research_metrics.csv")
    forward_return = event_research.read_series_parquet(forward_return_cache_path(run_dir))
    aux_df = pd.read_parquet(aux_fields_cache_path(run_dir))
    data_dir = event_research.PROJECT_ROOT / "data"
    stock_basic = event_research.load_stock_basic_reference(data_dir)
    st_ranges = event_research.parse_st_ranges(data_dir / "qlib_data" / "instruments" / "st_stocks.txt")
    trade_cal = pd.read_parquet(data_dir / "reference" / "trade_cal.parquet")
    trade_cal["cal_date"] = pd.to_datetime(trade_cal["cal_date"], format="%Y%m%d")
    trade_calendar = trade_cal.loc[trade_cal["is_open"] == 1, "cal_date"].sort_values().tolist()
    processed_factor_dir = run_dir / "cache" / "processed_factors"
    processed_factor_paths = {
        factor: processed_factor_dir / f"{factor}.parquet"
        for factor in candidate_factors
        if (processed_factor_dir / f"{factor}.parquet").exists()
    }
    if len(processed_factor_paths) != len(candidate_factors):
        missing = sorted(set(candidate_factors) - set(processed_factor_paths))
        raise FileNotFoundError(f"Missing processed factor files: {missing}")
    factor_direction_by_fold: dict[str, dict[str, int]] = defaultdict(dict)
    for _, row in factor_selection_decisions_df.iterrows():
        factor_direction_by_fold[str(row["fold_id"])][str(row["factor"])] = int(row["train_direction"])
    return {
        "run_dir": run_dir,
        "screening_run_dir": Path(str(context["screening_run_dir"])).resolve(),
        "screening_metadata": screening_metadata,
        "candidate_factors": candidate_factors,
        "folds": folds,
        "holdout_spec": holdout_spec,
        "factor_meta": factor_meta,
        "candidate_df": candidate_df,
        "factor_selection_decisions_df": factor_selection_decisions_df,
        "selected_by_fold_df": selected_by_fold_df,
        "fold_overview_df": fold_overview_df,
        "overall_factor_decisions_df": overall_factor_decisions_df,
        "factor_research_metrics_df": factor_research_metrics_df,
        "forward_return": forward_return,
        "aux_df": aux_df,
        "stock_basic": stock_basic,
        "st_ranges": st_ranges,
        "trade_calendar": trade_calendar,
        "processed_factor_paths": processed_factor_paths,
        "factor_direction_by_fold": factor_direction_by_fold,
        "kernel_meta": dict(context.get("kernel_meta", {})),
    }


def run_event_backtest_stage(args) -> dict[str, Any]:
    inputs = _load_backtest_inputs(args)
    run_dir = Path(inputs["run_dir"])
    event_research.LOGGER.info("Starting event-driven strategy backtest stage")
    tracker = event_research.try_start_tracker(run_dir.name, disabled=bool(args.disable_mlflow))
    event_research.tracker_log_params(
        tracker,
        {
            "screening_run_dir": str(inputs["screening_run_dir"]),
            "candidate_count": len(inputs["candidate_factors"]),
            "capital": args.capital,
            "benchmark": args.benchmark,
            "topk": args.topk,
            "rebalance_days": args.rebalance_days,
            "adv_median_floor": args.adv_median_floor,
            "participation_cap": args.participation_cap,
            "train_years": TRAIN_YEARS,
            "validation_years": VALIDATION_YEARS,
            "test_years": TEST_YEARS,
            "strategy_horizon": event_research.STRATEGY_HORIZON,
        },
    )

    default_scenario = event_research.build_liquidity_scenarios(args)[2]
    oos_performance_rows: list[dict[str, Any]] = []
    signal_frames: list[pd.DataFrame] = []
    signal_diagnostic_frames: list[pd.DataFrame] = []
    report_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    order_log_frames: list[pd.DataFrame] = []
    holding_frames: list[pd.DataFrame] = []
    corp_action_frames: list[pd.DataFrame] = []

    for fold in inputs["folds"]:
        fold_selected = inputs["selected_by_fold_df"][
            inputs["selected_by_fold_df"]["fold_id"] == fold.fold_id
        ]["factor"].tolist()
        if not fold_selected:
            event_research.LOGGER.warning("Skipping %s because no factor survived selection", fold.fold_id)
            continue
        schedule, signal_df, diag_df = event_research.build_signal_schedule_for_window(
            start=fold.test_start,
            end=fold.test_end,
            selected_factors=fold_selected,
            factor_directions=inputs["factor_direction_by_fold"][fold.fold_id],
            processed_factor_paths=inputs["processed_factor_paths"],
            stock_basic=inputs["stock_basic"],
            trade_calendar=inputs["trade_calendar"],
            aux_df=inputs["aux_df"],
            st_ranges=inputs["st_ranges"],
            topk=args.topk,
            capital=args.capital,
            rebalance_days=args.rebalance_days,
            scenario=default_scenario,
        )
        signal_frames.append(signal_df.assign(fold_id=fold.fold_id))
        signal_diagnostic_frames.append(diag_df.assign(fold_id=fold.fold_id))
        result = event_research.run_event_driven_window(
            schedule=schedule,
            start=fold.test_start,
            end=fold.test_end,
            benchmark=args.benchmark,
            capital=args.capital,
        )
        report_frames.append(event_research.concat_with_fold(result.report.reset_index(), fold.fold_id))
        trade_frames.append(event_research.concat_with_fold(result.trades, fold.fold_id))
        order_log_frames.append(event_research.concat_with_fold(result.order_log, fold.fold_id))
        holding_frames.append(event_research.concat_with_fold(result.daily_holdings, fold.fold_id))
        corp_action_frames.append(event_research.concat_with_fold(result.corporate_actions, fold.fold_id))
        oos_performance_rows.append(
            event_research.summarize_backtest_result(
                result,
                scenario=default_scenario.name,
                window_type="test",
                fold_id=fold.fold_id,
            )
        )

    holdout_spec = inputs["holdout_spec"]
    if holdout_spec is not None:
        event_research.LOGGER.info("Running holdout diagnostic window")
        holdout_fold = FoldSpec(
            fold_id="holdout",
            train_start=holdout_spec.train_start,
            train_end=holdout_spec.train_end,
            validation_start=holdout_spec.validation_start,
            validation_end=holdout_spec.validation_end,
            test_start=holdout_spec.start,
            test_end=holdout_spec.end,
        )
        holdout_metric_frames: list[pd.DataFrame] = []
        holdout_directions: dict[str, int] = {}
        for factor in inputs["candidate_factors"]:
            holdout_series = event_research.read_series_parquet(inputs["processed_factor_paths"][factor])
            holdout_metrics = event_research.compute_fold_metrics_for_factor(
                factor,
                holdout_series,
                inputs["forward_return"],
                [holdout_fold],
            )
            holdout_metric_frames.append(holdout_metrics)
            if not holdout_metrics.empty:
                holdout_directions[factor] = int(holdout_metrics.iloc[0]["train_direction"])
        holdout_metric_df = pd.concat(holdout_metric_frames, ignore_index=True) if holdout_metric_frames else pd.DataFrame()
        holdout_selected_df, _, _ = event_research.select_core_factors_for_fold(
            fold=holdout_fold,
            candidate_summary=holdout_metric_df,
            processed_factor_paths=inputs["processed_factor_paths"],
            forward_return=inputs["forward_return"],
        )
        holdout_selected = holdout_selected_df["factor"].tolist()
        if holdout_selected:
            schedule, signal_df, diag_df = event_research.build_signal_schedule_for_window(
                start=holdout_spec.start,
                end=holdout_spec.end,
                selected_factors=holdout_selected,
                factor_directions=holdout_directions,
                processed_factor_paths=inputs["processed_factor_paths"],
                stock_basic=inputs["stock_basic"],
                trade_calendar=inputs["trade_calendar"],
                aux_df=inputs["aux_df"],
                st_ranges=inputs["st_ranges"],
                topk=args.topk,
                capital=args.capital,
                rebalance_days=args.rebalance_days,
                scenario=default_scenario,
            )
            result = event_research.run_event_driven_window(
                schedule=schedule,
                start=holdout_spec.start,
                end=holdout_spec.end,
                benchmark=args.benchmark,
                capital=args.capital,
            )
            signal_frames.append(signal_df.assign(fold_id="holdout"))
            signal_diagnostic_frames.append(diag_df.assign(fold_id="holdout"))
            report_frames.append(event_research.concat_with_fold(result.report.reset_index(), "holdout"))
            trade_frames.append(event_research.concat_with_fold(result.trades, "holdout"))
            order_log_frames.append(event_research.concat_with_fold(result.order_log, "holdout"))
            holding_frames.append(event_research.concat_with_fold(result.daily_holdings, "holdout"))
            corp_action_frames.append(event_research.concat_with_fold(result.corporate_actions, "holdout"))
            oos_performance_rows.append(
                event_research.summarize_backtest_result(
                    result,
                    scenario=default_scenario.name,
                    window_type="holdout",
                    fold_id="holdout",
                )
            )

    event_driven_report_df = event_research.aggregate_result_frames(report_frames, sort_cols=["date", "fold_id"])
    event_driven_trades_df = event_research.aggregate_result_frames(trade_frames, sort_cols=["date", "fold_id"])
    event_driven_order_log_df = event_research.aggregate_result_frames(order_log_frames, sort_cols=["date", "fold_id"])
    event_driven_daily_holdings_df = event_research.aggregate_result_frames(holding_frames, sort_cols=["date", "fold_id"])
    event_driven_corporate_actions_df = event_research.aggregate_result_frames(corp_action_frames, sort_cols=["date", "fold_id"])
    strategy_signal_df = event_research.aggregate_result_frames(signal_frames, sort_cols=["date", "fold_id", "instrument"])
    signal_diagnostics_df = event_research.aggregate_result_frames(signal_diagnostic_frames, sort_cols=["date", "fold_id"])
    oos_fold_performance_df = pd.DataFrame(oos_performance_rows)

    liquidity_sensitivity_df = pd.DataFrame()
    sensitivity_topk_rebalance_df = pd.DataFrame()
    if not args.skip_sensitivity:
        liquidity_rows = []
        if not oos_fold_performance_df.empty:
            default_test_perf = oos_fold_performance_df[oos_fold_performance_df["window_type"] == "test"].copy()
            liquidity_rows.append(
                {
                    "scenario": default_scenario.name,
                    "cumulative_return": event_research.compound_fold_total_returns(default_test_perf),
                    "cagr": default_test_perf["cagr"].mean(),
                    "max_drawdown": default_test_perf["max_drawdown"].min(),
                    "turnover_mean": default_test_perf["turnover_mean"].mean(),
                    "blocked_order_ratio": default_test_perf["blocked_order_ratio"].mean(),
                }
            )
        for scenario in [
            event_research.build_liquidity_scenarios(args)[0],
            event_research.build_liquidity_scenarios(args)[1],
            event_research.build_liquidity_scenarios(args)[3],
        ]:
            scenario_perf_rows: list[dict[str, Any]] = []
            for fold in inputs["folds"]:
                fold_selected = inputs["selected_by_fold_df"][inputs["selected_by_fold_df"]["fold_id"] == fold.fold_id]["factor"].tolist()
                if not fold_selected:
                    continue
                schedule, _, _ = event_research.build_signal_schedule_for_window(
                    start=fold.test_start,
                    end=fold.test_end,
                    selected_factors=fold_selected,
                    factor_directions=inputs["factor_direction_by_fold"][fold.fold_id],
                    processed_factor_paths=inputs["processed_factor_paths"],
                    stock_basic=inputs["stock_basic"],
                    trade_calendar=inputs["trade_calendar"],
                    aux_df=inputs["aux_df"],
                    st_ranges=inputs["st_ranges"],
                    topk=args.topk,
                    capital=args.capital,
                    rebalance_days=args.rebalance_days,
                    scenario=scenario,
                )
                result = event_research.run_event_driven_window(
                    schedule=schedule,
                    start=fold.test_start,
                    end=fold.test_end,
                    benchmark=args.benchmark,
                    capital=args.capital,
                )
                scenario_perf_rows.append(
                    event_research.summarize_backtest_result(
                        result,
                        scenario=scenario.name,
                        window_type="test",
                        fold_id=fold.fold_id,
                    )
                )
            perf_df = pd.DataFrame(scenario_perf_rows)
            if not perf_df.empty:
                liquidity_rows.append(
                    {
                        "scenario": scenario.name,
                        "cumulative_return": event_research.compound_fold_total_returns(perf_df),
                        "cagr": perf_df["cagr"].mean(),
                        "max_drawdown": perf_df["max_drawdown"].min(),
                        "turnover_mean": perf_df["turnover_mean"].mean(),
                        "blocked_order_ratio": perf_df["blocked_order_ratio"].mean(),
                    }
                )
        liquidity_sensitivity_df = pd.DataFrame(liquidity_rows)
        stress_rows: list[dict[str, Any]] = []
        stress_specs = [
            {"scenario": "topk_30", "topk": 30, "rebalance_days": args.rebalance_days, "slippage_rate": 0.0005},
            {"scenario": "topk_50", "topk": 50, "rebalance_days": args.rebalance_days, "slippage_rate": 0.0005},
            {"scenario": "topk_100", "topk": 100, "rebalance_days": args.rebalance_days, "slippage_rate": 0.0005},
            {"scenario": "rebalance_10d", "topk": args.topk, "rebalance_days": 10, "slippage_rate": 0.0005},
            {"scenario": "slippage_stress", "topk": args.topk, "rebalance_days": args.rebalance_days, "slippage_rate": 0.0010},
        ]
        for spec in stress_specs:
            scenario_perf_rows: list[dict[str, Any]] = []
            for fold in inputs["folds"]:
                fold_selected = inputs["selected_by_fold_df"][
                    inputs["selected_by_fold_df"]["fold_id"] == fold.fold_id
                ]["factor"].tolist()
                if not fold_selected:
                    continue
                schedule, _, _ = event_research.build_signal_schedule_for_window(
                    start=fold.test_start,
                    end=fold.test_end,
                    selected_factors=fold_selected,
                    factor_directions=inputs["factor_direction_by_fold"][fold.fold_id],
                    processed_factor_paths=inputs["processed_factor_paths"],
                    stock_basic=inputs["stock_basic"],
                    trade_calendar=inputs["trade_calendar"],
                    aux_df=inputs["aux_df"],
                    st_ranges=inputs["st_ranges"],
                    topk=int(spec["topk"]),
                    capital=args.capital,
                    rebalance_days=int(spec["rebalance_days"]),
                    scenario=default_scenario,
                )
                result = event_research.run_event_driven_window(
                    schedule=schedule,
                    start=fold.test_start,
                    end=fold.test_end,
                    benchmark=args.benchmark,
                    capital=args.capital,
                    slippage_rate=float(spec["slippage_rate"]),
                )
                scenario_perf_rows.append(
                    event_research.summarize_backtest_result(
                        result,
                        scenario=str(spec["scenario"]),
                        window_type="test",
                        fold_id=fold.fold_id,
                    )
                )
            perf_df = pd.DataFrame(scenario_perf_rows)
            if not perf_df.empty:
                stress_rows.append(
                    {
                        "scenario": str(spec["scenario"]),
                        "topk": int(spec["topk"]),
                        "rebalance_days": int(spec["rebalance_days"]),
                        "slippage_rate": float(spec["slippage_rate"]),
                        "cumulative_return": event_research.compound_fold_total_returns(perf_df),
                        "cagr": perf_df["cagr"].mean(),
                        "max_drawdown": perf_df["max_drawdown"].min(),
                        "blocked_order_ratio": perf_df["blocked_order_ratio"].mean(),
                    }
                )
        sensitivity_topk_rebalance_df = pd.DataFrame(stress_rows)

    run_metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "screening_run_dir": str(inputs["screening_run_dir"]),
        "screening_catalog_hash": inputs["screening_metadata"].get("catalog_hash"),
        "screening_composite_hash": inputs["screening_metadata"].get("composite_hash"),
        "candidate_count": int(len(inputs["candidate_factors"])),
        "candidate_factors": inputs["candidate_factors"],
        "strategy_style": "all-market long-only",
        "strategy_horizon": event_research.STRATEGY_HORIZON,
        "benchmark": args.benchmark,
        "capital": args.capital,
        "topk": args.topk,
        "rebalance_days": args.rebalance_days,
        "adv_median_floor": args.adv_median_floor,
        "participation_cap": args.participation_cap,
        "train_years": TRAIN_YEARS,
        "validation_years": VALIDATION_YEARS,
        "test_years": TEST_YEARS,
        "step_years": STEP_YEARS,
        "folds": [asdict(fold) for fold in inputs["folds"]],
        "holdout": asdict(holdout_spec) if holdout_spec is not None else None,
        "kernel_meta": inputs["kernel_meta"],
        "screening_requested_kernels": inputs["screening_metadata"].get("requested_kernels"),
        "screening_effective_kernels": inputs["screening_metadata"].get("effective_kernels"),
        **event_research.resolve_mlflow_status(tracker, disabled=bool(args.disable_mlflow)),
    }

    signal_diagnostics_df.to_csv(run_dir / "signal_diagnostics.csv", index=False)
    if not strategy_signal_df.empty:
        strategy_signal_df.to_parquet(run_dir / "strategy_signal.parquet", index=False)
    else:
        pd.DataFrame(columns=["date", "instrument", "score", "target_weight", "scenario", "fold_id"]).to_parquet(run_dir / "strategy_signal.parquet", index=False)
    event_driven_report_df.to_csv(run_dir / "event_driven_report.csv", index=False)
    event_driven_trades_df.to_csv(run_dir / "event_driven_trades.csv", index=False)
    event_driven_order_log_df.to_csv(run_dir / "event_driven_order_log.csv", index=False)
    event_driven_daily_holdings_df.to_csv(run_dir / "event_driven_daily_holdings.csv", index=False)
    event_driven_corporate_actions_df.to_csv(run_dir / "event_driven_corporate_actions.csv", index=False)
    oos_fold_performance_df.to_csv(run_dir / "oos_fold_performance.csv", index=False)
    liquidity_sensitivity_df.to_csv(run_dir / "sensitivity_liquidity.csv", index=False)
    sensitivity_topk_rebalance_df.to_csv(run_dir / "sensitivity_topk_rebalance.csv", index=False)

    if not event_driven_report_df.empty:
        report_indexed = event_driven_report_df.set_index("date").sort_index()
        strategy_returns = report_indexed["return"]
        benchmark_returns = report_indexed["bench"] if "bench" in report_indexed.columns else None
    else:
        strategy_returns = pd.Series(dtype=float)
        benchmark_returns = None
    event_research.build_backtest_html(
        run_dir / "strategy_backtest_report.html",
        strategy_returns=strategy_returns,
        benchmark_returns=benchmark_returns if benchmark_returns is not None and not benchmark_returns.empty else None,
        name="Event-Driven Alpha-Mining OOS Strategy",
    )

    warnings = [
        "Signal admission is locked to the 5d horizon because the formal strategy rebalances every 5 trading days.",
        "Long-short quantile returns in factor cards are diagnostics only, not tradable strategy returns.",
        "Industry neutralization uses time-varying SW2021 L1 membership from data/universe/industry_sw2021_members/industry_sw2021_members.parquet via provider_metadata.build_industry_series_asof. Pre-2014 coverage is 94-97% of the daily trading universe due to Shenwan backfill thinness (NOT survivorship bias — see workspace/outputs/sw_industry_coverage_audit_20260427.md). Unclassified rows are skipped from neutralization via notna() mask.",
        f"Default liquidity control for the 2,000,000 RMB account uses adv20 median >= {args.adv_median_floor:,.0f} RMB and participation <= {args.participation_cap:.2%}.",
    ]
    artifacts = [
        "master_review.md",
        "factor_cards/",
        "factor_research_metrics.csv",
        "factor_selection_decisions.csv",
        "selected_core_factors_by_fold.csv",
        "signal_diagnostics.csv",
        "strategy_signal.parquet",
        "event_driven_report.csv",
        "event_driven_trades.csv",
        "event_driven_order_log.csv",
        "event_driven_daily_holdings.csv",
        "event_driven_corporate_actions.csv",
        "oos_fold_performance.csv",
        "sensitivity_liquidity.csv",
        "sensitivity_topk_rebalance.csv",
        "strategy_backtest_report.html",
        "run_metadata.json",
        "run_console.log",
    ]
    candidate_summary = inputs["candidate_df"][["factor", "grade", "abs_icir"]].copy()
    candidate_summary["category"] = candidate_summary["factor"].map(lambda item: inputs["factor_meta"][item]["category"])
    candidate_summary = candidate_summary.merge(
        inputs["overall_factor_decisions_df"][["factor", "overall_decision", "selected_count", "validation_pass_count"]],
        on="factor",
        how="left",
    )
    master_review = event_research.render_master_review(
        run_metadata=run_metadata,
        screening_overview={"candidate_count": len(inputs["candidate_factors"])},
        candidate_summary=candidate_summary,
        fold_overview=inputs["fold_overview_df"],
        selected_by_fold=inputs["selected_by_fold_df"],
        overall_factor_decisions=inputs["overall_factor_decisions_df"],
        oos_performance=oos_fold_performance_df,
        liquidity_sensitivity=liquidity_sensitivity_df,
        topk_rebalance_sensitivity=sensitivity_topk_rebalance_df,
        warnings=warnings,
        artifacts=artifacts,
    )
    event_research.write_text(run_dir / "master_review.md", master_review)
    event_research.write_json(run_dir / "run_metadata.json", run_metadata)

    event_research.tracker_log_metrics(
        tracker,
        {
            "candidate_count": len(inputs["candidate_factors"]),
            "selected_factor_rows": len(inputs["selected_by_fold_df"]),
            "oos_total_return": event_research.calculate_total_return(strategy_returns) if not strategy_returns.empty else np.nan,
            "oos_cagr": event_research.calculate_cagr(strategy_returns) if not strategy_returns.empty else np.nan,
            "oos_max_drawdown": event_research.calculate_max_drawdown(strategy_returns) if not strategy_returns.empty else np.nan,
        },
    )
    event_research.tracker_end(tracker)
    event_research.LOGGER.info("Backtest stage complete: %s", run_dir)
    return {
        "run_dir": run_dir,
        "candidate_count": len(inputs["candidate_factors"]),
        "selected_factor_rows": len(inputs["selected_by_fold_df"]),
    }
