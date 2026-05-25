"""
Machine-learning factor-combination research for alpha_mining.

This entrypoint keeps the existing rule-based research workflow intact and
adds a separate, auditable ML comparison layer:

- rule baseline rerun under the same conservative 10-day execution settings
- ElasticNet for explicit factor weights
- LightGBM for direct stock scoring
"""

from __future__ import annotations

import argparse
import math
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
import sys

sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_eval import compute_ic_series, compute_ic_summary
from src.alpha_research.factor_library.operators import compute_factors
from src.alpha_research.model_zoo import ElasticNetModel, LightGBMModel
from workspace.research.alpha_mining.event_driven_strategy_improvement import (
    VariantSpec,
    apply_eligibility_filter,
    build_liquidity_scenario_map,
    compound_column,
    compute_stability_scores,
    evaluate_variant,
    load_baseline_bundle,
    load_support_context,
    relative_excess_return,
)
from workspace.research.alpha_mining.event_driven_strategy_research import (
    FoldSpec,
    HoldoutSpec,
    LiquidityScenario,
    apply_liquidity_rules,
    build_backtest_html,
    build_rebalance_dates,
    configure_logging,
    qlib_to_ts_code,
    read_series_parquet,
    resolve_mlflow_status,
    run_event_driven_window,
    slice_window,
    summarize_backtest_result,
    write_json,
    write_series_parquet,
)
from workspace.research.alpha_mining.event_driven_strategy_report import (
    bullet_list,
    dataframe_to_markdown,
    write_text,
)


LOGGER = logging.getLogger("alpha_mining.event_driven_strategy_ml_research")
DEFAULT_MODEL_VARIANTS = ("linear", "lightgbm")
ELASTICNET_ALPHA_GRID = (0.0005, 0.0020, 0.0100)
ELASTICNET_L1_GRID = (0.20, 0.50, 0.80)
LIGHTGBM_NUM_BOOST_ROUND = 400
LIGHTGBM_EARLY_STOPPING_ROUNDS = 50
LIGHTGBM_PARAMS = {
    "num_leaves": 64,
    "max_depth": 6,
    "learning_rate": 0.05,
    "feature_fraction": 0.80,
    "bagging_fraction": 0.80,
    "bagging_freq": 5,
    "lambda_l1": 0.10,
    "lambda_l2": 1.00,
    "min_data_in_leaf": 200,
}
MIN_FEATURE_COVERAGE_RATIO = 0.70
SLIPPAGE_RATE = 0.0005
RULE_SELECTION_LABEL_HORIZON = 5


@dataclass(frozen=True)
class ModelWindowSpec:
    fold_id: str
    window_type: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    test_start: str
    test_end: str


@dataclass(frozen=True)
class FoldDataset:
    fold_id: str
    window_type: str
    factor_directions: dict[str, int]
    train_dates: list[pd.Timestamp]
    validation_dates: list[pd.Timestamp]
    test_dates: list[pd.Timestamp]
    X_train: pd.DataFrame
    y_train: pd.Series
    X_validation: pd.DataFrame
    y_validation: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series


@dataclass(frozen=True)
class MLVariantSpec:
    variant_id: str
    model_kind: str
    display_name: str


@dataclass
class MLVariantArtifacts:
    spec: MLVariantSpec
    summary: dict[str, Any]
    oos_performance: pd.DataFrame
    event_report: pd.DataFrame
    signal_df: pd.DataFrame
    signal_diagnostics: pd.DataFrame
    prediction_df: pd.DataFrame
    fold_metrics: pd.DataFrame
    linear_weights: pd.DataFrame
    feature_importance: pd.DataFrame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ML factor-combination research on top of the formal alpha-mining event-driven baseline."
    )
    parser.add_argument("--baseline-run-dir", required=True, help="Completed formal event-driven research run directory")
    parser.add_argument("--screening-run-dir", required=True, help="Completed latest screening run directory")
    parser.add_argument("--output-dir", default=None, help="Optional explicit output directory")
    parser.add_argument("--benchmark", default="000001.SH", help="Benchmark index code")
    parser.add_argument("--label-horizon", type=int, default=10, help="Forward-return horizon in trading days")
    parser.add_argument("--topk", type=int, default=50, help="Target number of holdings")
    parser.add_argument("--rebalance-days", type=int, default=10, help="Rebalance interval in trading days")
    parser.add_argument("--adv-median-floor", type=float, default=5_000_000.0, help="20d median turnover floor in RMB")
    parser.add_argument("--participation-cap", type=float, default=0.02, help="Max target-value / ADV20")
    parser.add_argument("--capital", type=float, default=2_000_000.0, help="Initial capital in RMB")
    parser.add_argument("--model-variants", default="linear,lightgbm", help="Comma-separated subset of: linear,lightgbm")
    parser.add_argument(
        "--disable-mlflow",
        action="store_true",
        default=True,
        help="Disable MLflow tracking (default: disabled for this research entrypoint).",
    )
    parser.add_argument("--enable-mlflow", action="store_false", dest="disable_mlflow", help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=["formal", "sandbox"], default="formal",
                        help="Research mode. 'sandbox' skips the hypothesis requirement and registry publish for re-validation / comparison runs.")
    return parser.parse_args()


def resolve_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (
        PROJECT_ROOT
        / "workspace"
        / "research"
        / "alpha_mining"
        / f"event_driven_strategy_ml_research_{stamp}"
    ).resolve()


def parse_model_variants(spec: str) -> list[str]:
    raw = [item.strip().lower() for item in str(spec).split(",")]
    variants = [item for item in raw if item]
    if not variants:
        return list(DEFAULT_MODEL_VARIANTS)
    allowed = set(DEFAULT_MODEL_VARIANTS)
    unknown = [item for item in variants if item not in allowed]
    if unknown:
        raise ValueError(f"Unsupported model variants: {unknown}")
    ordered: list[str] = []
    for item in variants:
        if item not in ordered:
            ordered.append(item)
    return ordered


def concat_nonempty(
    frames: list[pd.DataFrame | None],
    *,
    ignore_index: bool = True,
) -> pd.DataFrame:
    valid_frames = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid_frames:
        return pd.DataFrame()
    return pd.concat(valid_frames, ignore_index=ignore_index)


def build_model_windows(folds: list[FoldSpec], holdout: HoldoutSpec | None) -> list[ModelWindowSpec]:
    windows = [
        ModelWindowSpec(
            fold_id=fold.fold_id,
            window_type="test",
            train_start=fold.train_start,
            train_end=fold.train_end,
            validation_start=fold.validation_start,
            validation_end=fold.validation_end,
            test_start=fold.test_start,
            test_end=fold.test_end,
        )
        for fold in folds
    ]
    if holdout is not None:
        windows.append(
            ModelWindowSpec(
                fold_id="holdout",
                window_type="holdout",
                train_start=holdout.train_start,
                train_end=holdout.train_end,
                validation_start=holdout.validation_start,
                validation_end=holdout.validation_end,
                test_start=holdout.start,
                test_end=holdout.end,
            )
        )
    return windows


def validate_inputs(
    *,
    baseline_run_dir: Path,
    screening_run_dir: Path,
    bundle,
    label_horizon: int,
) -> None:
    if not baseline_run_dir.exists():
        raise FileNotFoundError(f"Missing baseline run dir: {baseline_run_dir}")
    if not screening_run_dir.exists():
        raise FileNotFoundError(f"Missing screening run dir: {screening_run_dir}")
    if bundle.screening_run_dir.resolve() != screening_run_dir.resolve():
        raise ValueError(
            "The provided screening run dir does not match the screening run recorded in the formal baseline metadata."
        )
    if int(label_horizon) != 10:
        LOGGER.warning("This first-version ML entrypoint was designed around 10-day labels; received %s", label_horizon)


def load_forward_return_series(
    bundle,
    run_dir: Path,
    horizon: int,
    *,
    start_override: str | None = None,
    end_override: str | None = None,
) -> pd.Series:
    cache_path = run_dir / "cache" / f"forward_return_{int(horizon)}d.parquet"
    if cache_path.exists():
        return read_series_parquet(cache_path)

    LOGGER.info("Computing cached %dd forward return series for ML research", int(horizon))
    start_date = str(start_override or bundle.screening_metadata["start_date"])
    end_date = str(end_override or bundle.screening_metadata["end_date"])
    _, fwd_df = compute_factors(
        {},
        start_date,
        end_date,
        horizons=[int(horizon)],
        qlib_dir=bundle.screening_metadata["qlib_dir"],
        kernels=None,
        progress_interval=60,
    )
    forward_return = fwd_df[f"fwd_{int(horizon)}d"].astype(np.float32)
    write_series_parquet(forward_return, cache_path)
    return forward_return


def get_rebalance_dates_for_window(
    start: str,
    end: str,
    trade_calendar: list[pd.Timestamp],
    rebalance_days: int,
) -> list[pd.Timestamp]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    period_calendar = [date for date in trade_calendar if start_ts <= date <= end_ts]
    return build_rebalance_dates(period_calendar, rebalance_days)


def filter_to_dates(obj: pd.Series | pd.DataFrame, dates: list[pd.Timestamp]) -> pd.Series | pd.DataFrame:
    if not dates:
        return obj.iloc[0:0]
    allowed = pd.DatetimeIndex(pd.to_datetime(dates))
    mask = obj.index.get_level_values("datetime").isin(allowed)
    return obj.loc[mask]


def rank_icir_for_predictions(predictions: pd.Series, labels: pd.Series) -> float:
    if predictions.empty or labels.empty:
        return float("nan")
    label_slice = labels.reindex(predictions.index).dropna()
    pred_slice = predictions.reindex(label_slice.index).dropna()
    if pred_slice.empty or label_slice.empty:
        return float("nan")
    ic_series = compute_ic_series(pred_slice.astype(np.float32), label_slice.astype(np.float32))
    if ic_series.empty:
        return float("nan")
    summary = compute_ic_summary(ic_series)
    return float(summary.get("rank_icir", np.nan))


def compute_train_factor_directions(
    candidate_factors: list[str],
    processed_factor_paths: dict[str, Path],
    forward_return: pd.Series,
    train_start: str,
    train_end: str,
) -> dict[str, int]:
    label_slice = slice_window(forward_return, train_start, train_end)
    directions: dict[str, int] = {}
    for factor in candidate_factors:
        factor_slice = slice_window(read_series_parquet(processed_factor_paths[factor]), train_start, train_end)
        ic_series = compute_ic_series(factor_slice, label_slice)
        summary = compute_ic_summary(ic_series) if not ic_series.empty else {}
        mean_rank_ic = float(summary.get("mean_rank_ic", 0.0) or 0.0)
        directions[factor] = 1 if mean_rank_ic >= 0 else -1
    return directions


def build_window_feature_panel(
    *,
    candidate_factors: list[str],
    processed_factor_paths: dict[str, Path],
    factor_directions: dict[str, int],
    forward_return: pd.Series,
    start: str,
    end: str,
    sample_dates: list[pd.Timestamp],
    context,
    min_coverage_ratio: float = MIN_FEATURE_COVERAGE_RATIO,
) -> tuple[pd.DataFrame, pd.Series]:
    feature_series: list[pd.Series] = []
    for factor in candidate_factors:
        series = slice_window(read_series_parquet(processed_factor_paths[factor]), start, end)
        series = filter_to_dates(series, sample_dates)
        direction = int(factor_directions.get(factor, 1))
        feature_series.append((series * float(direction)).rename(factor).astype(np.float32))

    if not feature_series:
        return pd.DataFrame(), pd.Series(dtype=np.float32)

    feature_df = pd.concat(feature_series, axis=1, join="outer").sort_index()
    label_series = slice_window(forward_return, start, end)
    label_series = filter_to_dates(label_series, sample_dates)
    frame = feature_df.join(label_series.rename("label"), how="inner")
    if frame.empty:
        return pd.DataFrame(), pd.Series(dtype=np.float32)

    min_non_null = max(1, math.ceil(len(candidate_factors) * float(min_coverage_ratio)))
    kept_frames: list[pd.DataFrame] = []
    for date, group in frame.groupby(level="datetime"):
        daily = group.droplevel("datetime")
        placeholder = pd.Series(1.0, index=daily.index, dtype=float)
        eligible_codes = apply_eligibility_filter(placeholder, pd.Timestamp(date), context).index
        if len(eligible_codes) == 0:
            continue
        daily = daily.reindex(eligible_codes)
        daily = daily[daily["label"].notna()].copy()
        if daily.empty:
            continue
        daily["non_null_feature_count"] = daily[candidate_factors].notna().sum(axis=1)
        daily = daily[daily["non_null_feature_count"] >= min_non_null].drop(columns=["non_null_feature_count"])
        if daily.empty:
            continue
        daily.index = pd.MultiIndex.from_product(
            [[pd.Timestamp(date)], daily.index],
            names=["datetime", "instrument"],
        )
        kept_frames.append(daily)

    if not kept_frames:
        return pd.DataFrame(), pd.Series(dtype=np.float32)

    filtered = pd.concat(kept_frames).sort_index()
    X = filtered[candidate_factors].fillna(0.0).astype(np.float32)
    y = filtered["label"].astype(np.float32)
    return X, y


def prepare_fold_dataset(
    *,
    window: ModelWindowSpec,
    candidate_factors: list[str],
    processed_factor_paths: dict[str, Path],
    forward_return: pd.Series,
    context,
    rebalance_days: int,
) -> FoldDataset:
    factor_directions = compute_train_factor_directions(
        candidate_factors,
        processed_factor_paths,
        forward_return,
        window.train_start,
        window.train_end,
    )
    train_dates = get_rebalance_dates_for_window(window.train_start, window.train_end, context.trade_calendar, rebalance_days)
    validation_dates = get_rebalance_dates_for_window(
        window.validation_start,
        window.validation_end,
        context.trade_calendar,
        rebalance_days,
    )
    test_dates = get_rebalance_dates_for_window(window.test_start, window.test_end, context.trade_calendar, rebalance_days)

    X_train, y_train = build_window_feature_panel(
        candidate_factors=candidate_factors,
        processed_factor_paths=processed_factor_paths,
        factor_directions=factor_directions,
        forward_return=forward_return,
        start=window.train_start,
        end=window.train_end,
        sample_dates=train_dates,
        context=context,
    )
    X_validation, y_validation = build_window_feature_panel(
        candidate_factors=candidate_factors,
        processed_factor_paths=processed_factor_paths,
        factor_directions=factor_directions,
        forward_return=forward_return,
        start=window.validation_start,
        end=window.validation_end,
        sample_dates=validation_dates,
        context=context,
    )
    X_test, y_test = build_window_feature_panel(
        candidate_factors=candidate_factors,
        processed_factor_paths=processed_factor_paths,
        factor_directions=factor_directions,
        forward_return=forward_return,
        start=window.test_start,
        end=window.test_end,
        sample_dates=test_dates,
        context=context,
    )
    if X_train.empty or X_validation.empty or X_test.empty:
        raise ValueError(
            f"{window.fold_id} produced an empty ML dataset "
            f"(train={len(X_train)}, validation={len(X_validation)}, test={len(X_test)})."
        )
    return FoldDataset(
        fold_id=window.fold_id,
        window_type=window.window_type,
        factor_directions=factor_directions,
        train_dates=train_dates,
        validation_dates=validation_dates,
        test_dates=test_dates,
        X_train=X_train,
        y_train=y_train,
        X_validation=X_validation,
        y_validation=y_validation,
        X_test=X_test,
        y_test=y_test,
    )


def empty_backtest_summary(*, scenario: str, window_type: str, fold_id: str) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "window_type": window_type,
        "fold_id": fold_id,
        "cumulative_return": np.nan,
        "cagr": np.nan,
        "max_drawdown": np.nan,
        "turnover_mean": np.nan,
        "turnover_median": np.nan,
        "benchmark_total_return": np.nan,
        "excess_total_return": np.nan,
        "trade_count": 0,
        "total_orders": 0,
        "blocked_orders": 0,
        "filled_orders": 0,
        "blocked_order_ratio": np.nan,
        "filled_order_ratio": np.nan,
        "holding_cash_ratio": np.nan,
        "window_start": "",
        "window_end": "",
    }


def build_prediction_schedule(
    *,
    predictions: pd.Series,
    context,
    scenario: LiquidityScenario,
    topk: int,
    capital: float,
    variant_id: str,
    fold_id: str,
    window_type: str,
) -> tuple[dict[pd.Timestamp, dict[str, float]], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    schedule: dict[pd.Timestamp, dict[str, float]] = {}
    prediction_rows: list[dict[str, Any]] = []
    signal_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    target_value = float(capital) / max(int(topk), 1)
    if predictions.empty:
        return schedule, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    for date in sorted(predictions.index.get_level_values("datetime").unique()):
        daily_scores = predictions.xs(date, level="datetime").astype(float)
        eligible_scores = apply_eligibility_filter(daily_scores, pd.Timestamp(date), context)
        for code, score in eligible_scores.items():
            prediction_rows.append(
                {
                    "date": pd.Timestamp(date),
                    "instrument": qlib_to_ts_code(code),
                    "score": float(score),
                    "variant_id": variant_id,
                    "fold_id": fold_id,
                    "window_type": window_type,
                }
            )
        if eligible_scores.empty:
            diagnostic_rows.append(
                {
                    "date": pd.Timestamp(date),
                    "variant_id": variant_id,
                    "fold_id": fold_id,
                    "window_type": window_type,
                    "n_scored": 0,
                    "n_selected": 0,
                    "detail": "No stock survived the eligibility filter.",
                    "scenario": scenario.name,
                }
            )
            continue
        adv_slice = context.aux_df["adv20_median_rmb"].xs(date, level="datetime").reindex(eligible_scores.index)
        selected_scores = apply_liquidity_rules(
            eligible_scores.astype(float),
            adv_slice,
            topk=topk,
            target_value=target_value,
            scenario=scenario,
        )
        if selected_scores.empty:
            diagnostic_rows.append(
                {
                    "date": pd.Timestamp(date),
                    "variant_id": variant_id,
                    "fold_id": fold_id,
                    "window_type": window_type,
                    "n_scored": int(len(eligible_scores)),
                    "n_selected": 0,
                    "detail": "No stock survived the liquidity screen.",
                    "scenario": scenario.name,
                }
            )
            continue
        weight = 1.0 / float(len(selected_scores))
        schedule[pd.Timestamp(date)] = {
            qlib_to_ts_code(code): float(weight)
            for code in selected_scores.index
        }
        diagnostic_rows.append(
            {
                "date": pd.Timestamp(date),
                "variant_id": variant_id,
                "fold_id": fold_id,
                "window_type": window_type,
                "n_scored": int(len(eligible_scores)),
                "n_selected": int(len(selected_scores)),
                "detail": "ok",
                "scenario": scenario.name,
            }
        )
        for code, score in selected_scores.items():
            signal_rows.append(
                {
                    "date": pd.Timestamp(date),
                    "instrument": qlib_to_ts_code(code),
                    "score": float(score),
                    "target_weight": float(weight),
                    "variant_id": variant_id,
                    "fold_id": fold_id,
                    "window_type": window_type,
                    "scenario": scenario.name,
                }
            )

    return (
        schedule,
        pd.DataFrame(prediction_rows),
        pd.DataFrame(signal_rows),
        pd.DataFrame(diagnostic_rows),
    )


def evaluate_prediction_window(
    *,
    predictions: pd.Series,
    labels: pd.Series,
    context,
    scenario: LiquidityScenario,
    benchmark: str,
    topk: int,
    capital: float,
    variant_id: str,
    fold_id: str,
    window_type: str,
    start: str,
    end: str,
    slippage_rate: float = SLIPPAGE_RATE,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    schedule, prediction_df, signal_df, diagnostic_df = build_prediction_schedule(
        predictions=predictions,
        context=context,
        scenario=scenario,
        topk=topk,
        capital=capital,
        variant_id=variant_id,
        fold_id=fold_id,
        window_type=window_type,
    )
    rank_icir = rank_icir_for_predictions(predictions, labels)
    if not schedule:
        summary = empty_backtest_summary(
            scenario=variant_id,
            window_type=window_type,
            fold_id=fold_id,
        )
        summary["prediction_rank_icir"] = rank_icir
        summary["relative_excess_return"] = np.nan
        return summary, pd.DataFrame(), signal_df, diagnostic_df, prediction_df

    result = run_event_driven_window(
        schedule=schedule,
        start=start,
        end=end,
        benchmark=benchmark,
        capital=capital,
        slippage_rate=slippage_rate,
    )
    perf_row = summarize_backtest_result(
        result,
        scenario=variant_id,
        window_type=window_type,
        fold_id=fold_id,
    )
    perf_row["prediction_rank_icir"] = rank_icir
    perf_row["relative_excess_return"] = relative_excess_return(
        float(perf_row.get("cumulative_return", np.nan)),
        float(perf_row.get("benchmark_total_return", np.nan)),
    )
    return perf_row, result.report.reset_index(), signal_df, diagnostic_df, prediction_df


def choose_best_elasticnet_candidate(candidate_df: pd.DataFrame) -> pd.Series:
    if candidate_df.empty:
        raise ValueError("ElasticNet validation candidate table is empty.")
    ranked = candidate_df.sort_values(
        [
            "validation_relative_excess_return",
            "validation_max_drawdown",
            "validation_prediction_rank_icir",
            "alpha",
            "l1_ratio",
        ],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)
    return ranked.iloc[0]


def build_linear_weight_table(fold_id: str, coefficients: pd.Series) -> pd.DataFrame:
    coef = coefficients.astype(float).sort_values(key=lambda s: s.abs(), ascending=False)
    abs_sum = float(coef.abs().sum())
    abs_share = coef.abs() / abs_sum if abs_sum > 0 else pd.Series(0.0, index=coef.index)
    table = pd.DataFrame(
        {
            "fold_id": fold_id,
            "factor": coef.index,
            "coefficient": coef.values,
            "abs_coefficient": coef.abs().values,
            "abs_weight_share": abs_share.reindex(coef.index).values,
        }
    )
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    return table


def build_lightgbm_importance_table(
    fold_id: str,
    gain_importance: pd.Series,
    split_importance: pd.Series,
) -> pd.DataFrame:
    factors = sorted(set(gain_importance.index) | set(split_importance.index))
    gain = gain_importance.reindex(factors).fillna(0.0).astype(float)
    split = split_importance.reindex(factors).fillna(0.0).astype(float)
    gain_sum = float(gain.sum())
    split_sum = float(split.sum())
    table = pd.DataFrame(
        {
            "fold_id": fold_id,
            "factor": factors,
            "gain_importance": gain.values,
            "gain_share": (gain / gain_sum).values if gain_sum > 0 else np.zeros(len(factors)),
            "split_importance": split.values,
            "split_share": (split / split_sum).values if split_sum > 0 else np.zeros(len(factors)),
        }
    )
    table = table.sort_values(["gain_importance", "split_importance", "factor"], ascending=[False, False, True]).reset_index(drop=True)
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    return table


def run_elasticnet_for_window(
    *,
    dataset: FoldDataset,
    context,
    scenario: LiquidityScenario,
    benchmark: str,
    topk: int,
    capital: float,
) -> dict[str, Any]:
    LOGGER.info("Running ElasticNet on %s (%s)", dataset.fold_id, dataset.window_type)
    validation_rows: list[dict[str, Any]] = []

    for alpha in ELASTICNET_ALPHA_GRID:
        for l1_ratio in ELASTICNET_L1_GRID:
            model = ElasticNetModel(alpha=alpha, l1_ratio=l1_ratio)
            model.fit(dataset.X_train, dataset.y_train)
            validation_pred = model.predict(dataset.X_validation)
            validation_perf, _, _, _, _ = evaluate_prediction_window(
                predictions=validation_pred,
                labels=dataset.y_validation,
                context=context,
                scenario=scenario,
                benchmark=benchmark,
                topk=topk,
                capital=capital,
                variant_id="elasticnet",
                fold_id=dataset.fold_id,
                window_type="validation",
                start=dataset.validation_dates[0].strftime("%Y-%m-%d"),
                end=dataset.validation_dates[-1].strftime("%Y-%m-%d"),
            )
            validation_rows.append(
                {
                    "variant_id": "elasticnet",
                    "model_kind": "linear",
                    "fold_id": dataset.fold_id,
                    "window_type": dataset.window_type,
                    "split": "validation_candidate",
                    "alpha": float(alpha),
                    "l1_ratio": float(l1_ratio),
                    "train_rows": int(len(dataset.X_train)),
                    "validation_rows": int(len(dataset.X_validation)),
                    "test_rows": int(len(dataset.X_test)),
                    "validation_relative_excess_return": validation_perf.get("relative_excess_return"),
                    "validation_max_drawdown": validation_perf.get("max_drawdown"),
                    "validation_prediction_rank_icir": validation_perf.get("prediction_rank_icir"),
                    "selected_hyperparams": False,
                }
            )

    validation_df = pd.DataFrame(validation_rows)
    best = choose_best_elasticnet_candidate(validation_df)
    validation_df["selected_hyperparams"] = (
        (validation_df["alpha"] == float(best["alpha"]))
        & (validation_df["l1_ratio"] == float(best["l1_ratio"]))
    )

    best_validation_model = ElasticNetModel(alpha=float(best["alpha"]), l1_ratio=float(best["l1_ratio"]))
    best_validation_model.fit(dataset.X_train, dataset.y_train)
    best_validation_predictions = best_validation_model.predict(dataset.X_validation)

    X_train_full = pd.concat([dataset.X_train, dataset.X_validation]).sort_index()
    y_train_full = pd.concat([dataset.y_train, dataset.y_validation]).sort_index()
    final_model = ElasticNetModel(alpha=float(best["alpha"]), l1_ratio=float(best["l1_ratio"]))
    final_model.fit(X_train_full, y_train_full)
    test_predictions = final_model.predict(dataset.X_test)
    test_perf, event_report, signal_df, signal_diag_df, test_prediction_df = evaluate_prediction_window(
        predictions=test_predictions,
        labels=dataset.y_test,
        context=context,
        scenario=scenario,
        benchmark=benchmark,
        topk=topk,
        capital=capital,
        variant_id="elasticnet",
        fold_id=dataset.fold_id,
        window_type=dataset.window_type,
        start=dataset.test_dates[0].strftime("%Y-%m-%d"),
        end=dataset.test_dates[-1].strftime("%Y-%m-%d"),
    )
    oos_row = {
        **test_perf,
        "variant_id": "elasticnet",
        "model_kind": "linear",
        "label_horizon": 10,
        "rebalance_days": 10,
    }

    fold_metrics = pd.concat(
        [
            validation_df,
            pd.DataFrame(
                [
                    {
                        "variant_id": "elasticnet",
                        "model_kind": "linear",
                        "fold_id": dataset.fold_id,
                        "window_type": dataset.window_type,
                        "split": dataset.window_type,
                        "alpha": float(best["alpha"]),
                        "l1_ratio": float(best["l1_ratio"]),
                        "train_rows": int(len(dataset.X_train)),
                        "validation_rows": int(len(dataset.X_validation)),
                        "test_rows": int(len(dataset.X_test)),
                        "validation_relative_excess_return": float(best["validation_relative_excess_return"]),
                        "validation_max_drawdown": float(best["validation_max_drawdown"]),
                        "validation_prediction_rank_icir": float(best["validation_prediction_rank_icir"]),
                        "test_relative_excess_return": oos_row.get("relative_excess_return"),
                        "test_max_drawdown": oos_row.get("max_drawdown"),
                        "test_prediction_rank_icir": oos_row.get("prediction_rank_icir"),
                        "selected_hyperparams": True,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    validation_prediction_panel = pd.DataFrame(
        {
            "date": dataset.X_validation.index.get_level_values("datetime"),
            "instrument": dataset.X_validation.index.get_level_values("instrument").map(qlib_to_ts_code),
            "score": best_validation_predictions.values,
            "variant_id": "elasticnet",
            "fold_id": dataset.fold_id,
            "window_type": "validation",
        }
    )
    prediction_df = pd.concat([validation_prediction_panel, test_prediction_df], ignore_index=True)
    linear_weights = build_linear_weight_table(dataset.fold_id, final_model.coefficients())
    return {
        "oos_row": oos_row,
        "event_report": event_report.assign(fold_id=dataset.fold_id, variant_id="elasticnet") if not event_report.empty else event_report,
        "signal_df": signal_df,
        "signal_diagnostics": signal_diag_df,
        "prediction_df": prediction_df,
        "fold_metrics": fold_metrics,
        "linear_weights": linear_weights,
        "feature_importance": pd.DataFrame(),
    }


def run_lightgbm_for_window(
    *,
    dataset: FoldDataset,
    context,
    scenario: LiquidityScenario,
    benchmark: str,
    topk: int,
    capital: float,
) -> dict[str, Any]:
    LOGGER.info("Running LightGBM on %s (%s)", dataset.fold_id, dataset.window_type)
    validation_model = LightGBMModel(**LIGHTGBM_PARAMS)
    validation_model.fit(
        dataset.X_train,
        dataset.y_train,
        dataset.X_validation,
        dataset.y_validation,
        num_boost_round=LIGHTGBM_NUM_BOOST_ROUND,
        early_stopping_rounds=LIGHTGBM_EARLY_STOPPING_ROUNDS,
    )
    validation_predictions = validation_model.predict(dataset.X_validation)
    validation_perf, _, _, _, _ = evaluate_prediction_window(
        predictions=validation_predictions,
        labels=dataset.y_validation,
        context=context,
        scenario=scenario,
        benchmark=benchmark,
        topk=topk,
        capital=capital,
        variant_id="lightgbm",
        fold_id=dataset.fold_id,
        window_type="validation",
        start=dataset.validation_dates[0].strftime("%Y-%m-%d"),
        end=dataset.validation_dates[-1].strftime("%Y-%m-%d"),
    )
    best_iteration = int(
        validation_model.model.best_iteration
        if validation_model.model is not None and validation_model.model.best_iteration > 0
        else LIGHTGBM_NUM_BOOST_ROUND
    )

    X_train_full = pd.concat([dataset.X_train, dataset.X_validation]).sort_index()
    y_train_full = pd.concat([dataset.y_train, dataset.y_validation]).sort_index()
    final_model = LightGBMModel(**LIGHTGBM_PARAMS)
    final_model.fit(
        X_train_full,
        y_train_full,
        num_boost_round=best_iteration,
    )
    test_predictions = final_model.predict(dataset.X_test)
    test_perf, event_report, signal_df, signal_diag_df, test_prediction_df = evaluate_prediction_window(
        predictions=test_predictions,
        labels=dataset.y_test,
        context=context,
        scenario=scenario,
        benchmark=benchmark,
        topk=topk,
        capital=capital,
        variant_id="lightgbm",
        fold_id=dataset.fold_id,
        window_type=dataset.window_type,
        start=dataset.test_dates[0].strftime("%Y-%m-%d"),
        end=dataset.test_dates[-1].strftime("%Y-%m-%d"),
    )
    oos_row = {
        **test_perf,
        "variant_id": "lightgbm",
        "model_kind": "tree",
        "label_horizon": 10,
        "rebalance_days": 10,
    }
    validation_prediction_panel = pd.DataFrame(
        {
            "date": dataset.X_validation.index.get_level_values("datetime"),
            "instrument": dataset.X_validation.index.get_level_values("instrument").map(qlib_to_ts_code),
            "score": validation_predictions.values,
            "variant_id": "lightgbm",
            "fold_id": dataset.fold_id,
            "window_type": "validation",
        }
    )
    prediction_df = pd.concat([validation_prediction_panel, test_prediction_df], ignore_index=True)
    fold_metrics = pd.DataFrame(
        [
            {
                "variant_id": "lightgbm",
                "model_kind": "tree",
                "fold_id": dataset.fold_id,
                "window_type": dataset.window_type,
                "split": "validation",
                "train_rows": int(len(dataset.X_train)),
                "validation_rows": int(len(dataset.X_validation)),
                "test_rows": int(len(dataset.X_test)),
                "best_iteration": best_iteration,
                "validation_relative_excess_return": validation_perf.get("relative_excess_return"),
                "validation_max_drawdown": validation_perf.get("max_drawdown"),
                "validation_prediction_rank_icir": validation_perf.get("prediction_rank_icir"),
                "selected_hyperparams": True,
            },
            {
                "variant_id": "lightgbm",
                "model_kind": "tree",
                "fold_id": dataset.fold_id,
                "window_type": dataset.window_type,
                "split": dataset.window_type,
                "train_rows": int(len(dataset.X_train)),
                "validation_rows": int(len(dataset.X_validation)),
                "test_rows": int(len(dataset.X_test)),
                "best_iteration": best_iteration,
                "test_relative_excess_return": oos_row.get("relative_excess_return"),
                "test_max_drawdown": oos_row.get("max_drawdown"),
                "test_prediction_rank_icir": oos_row.get("prediction_rank_icir"),
                "selected_hyperparams": True,
            },
        ]
    )
    feature_importance = build_lightgbm_importance_table(
        dataset.fold_id,
        final_model.feature_importance("gain"),
        final_model.feature_importance("split"),
    )
    return {
        "oos_row": oos_row,
        "event_report": event_report.assign(fold_id=dataset.fold_id, variant_id="lightgbm") if not event_report.empty else event_report,
        "signal_df": signal_df,
        "signal_diagnostics": signal_diag_df,
        "prediction_df": prediction_df,
        "fold_metrics": fold_metrics,
        "linear_weights": pd.DataFrame(),
        "feature_importance": feature_importance,
    }


def summarize_ml_variant(
    *,
    spec: MLVariantSpec,
    oos_df: pd.DataFrame,
) -> dict[str, Any]:
    test_df = oos_df[oos_df["window_type"] == "test"].copy()
    holdout_df = oos_df[oos_df["window_type"] == "holdout"].copy()
    stitched_total_return = compound_column(test_df, "cumulative_return")
    stitched_benchmark_total_return = compound_column(test_df, "benchmark_total_return")
    stitched_relative_excess_return = relative_excess_return(stitched_total_return, stitched_benchmark_total_return)
    test_df["relative_excess_return"] = test_df.apply(
        lambda row: relative_excess_return(row["cumulative_return"], row["benchmark_total_return"]),
        axis=1,
    )
    holdout_relative_excess_return = (
        relative_excess_return(
            float(holdout_df.iloc[0]["cumulative_return"]),
            float(holdout_df.iloc[0]["benchmark_total_return"]),
        )
        if not holdout_df.empty
        else float("nan")
    )
    return {
        "variant_id": spec.variant_id,
        "model_kind": spec.model_kind,
        "display_name": spec.display_name,
        "stitched_total_return": stitched_total_return,
        "stitched_benchmark_total_return": stitched_benchmark_total_return,
        "stitched_relative_excess_return": stitched_relative_excess_return,
        "positive_excess_folds": int((test_df["relative_excess_return"] > 0).sum()),
        "test_fold_count": int(len(test_df)),
        "holdout_relative_excess_return": holdout_relative_excess_return,
        "worst_max_drawdown": float(test_df["max_drawdown"].min()) if not test_df.empty else np.nan,
        "avg_turnover": float(test_df["turnover_mean"].mean()) if not test_df.empty else np.nan,
        "avg_blocked_order_ratio": float(test_df["blocked_order_ratio"].mean()) if not test_df.empty else np.nan,
        "avg_holding_cash_ratio": float(test_df["holding_cash_ratio"].mean()) if not test_df.empty else np.nan,
        "beats_benchmark": bool(pd.notna(stitched_relative_excess_return) and stitched_relative_excess_return > 0),
    }


def rank_variant_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return summary_df
    ranked = summary_df.sort_values(
        [
            "stitched_relative_excess_return",
            "holdout_relative_excess_return",
            "positive_excess_folds",
            "worst_max_drawdown",
            "variant_id",
        ],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)
    ranked.insert(0, "rank", np.arange(1, len(ranked) + 1))
    return ranked


def choose_adoption_recommendation(ml_summary: dict[str, Any], rule_summary: dict[str, Any]) -> str:
    ml_excess = float(ml_summary.get("stitched_relative_excess_return", np.nan))
    ml_holdout = float(ml_summary.get("holdout_relative_excess_return", np.nan))
    rule_excess = float(rule_summary.get("stitched_relative_excess_return", np.nan))
    rule_holdout = float(rule_summary.get("holdout_relative_excess_return", np.nan))
    if pd.notna(ml_excess) and ml_excess > 0 and ml_excess > rule_excess and pd.notna(ml_holdout) and ml_holdout >= max(0.0, rule_holdout):
        return "adopt"
    if pd.notna(ml_excess) and pd.notna(ml_holdout) and (
        (ml_excess > rule_excess and ml_holdout >= rule_holdout)
        or (ml_excess > 0 and ml_holdout >= 0)
    ):
        return "keep as research"
    return "reject"


def build_factor_highlight_tables(
    linear_weights: pd.DataFrame,
    feature_importance: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if linear_weights.empty:
        linear_table = pd.DataFrame()
    else:
        linear_table = (
            linear_weights.groupby("factor", as_index=False)
            .agg(
                avg_abs_weight_share=("abs_weight_share", "mean"),
                avg_coefficient=("coefficient", "mean"),
                fold_count=("fold_id", "nunique"),
            )
            .sort_values(["avg_abs_weight_share", "avg_coefficient", "factor"], ascending=[False, False, True])
            .head(10)
            .reset_index(drop=True)
        )
    if feature_importance.empty:
        tree_table = pd.DataFrame()
    else:
        tree_table = (
            feature_importance.groupby("factor", as_index=False)
            .agg(
                avg_gain_share=("gain_share", "mean"),
                avg_split_share=("split_share", "mean"),
                fold_count=("fold_id", "nunique"),
            )
            .sort_values(["avg_gain_share", "avg_split_share", "factor"], ascending=[False, False, True])
            .head(10)
            .reset_index(drop=True)
        )
    return linear_table, tree_table


def build_weakest_fold_table(oos_df: pd.DataFrame, variant_id: str) -> pd.DataFrame:
    variant_df = oos_df[(oos_df["variant_id"] == variant_id) & (oos_df["window_type"] == "test")].copy()
    if variant_df.empty:
        return pd.DataFrame()
    variant_df["relative_excess_return"] = variant_df.apply(
        lambda row: relative_excess_return(row["cumulative_return"], row["benchmark_total_return"]),
        axis=1,
    )
    return variant_df.sort_values(
        ["relative_excess_return", "max_drawdown", "fold_id"],
        ascending=[True, True, True],
    )[
        [
            "fold_id",
            "cumulative_return",
            "benchmark_total_return",
            "relative_excess_return",
            "max_drawdown",
            "turnover_mean",
            "blocked_order_ratio",
            "window_start",
            "window_end",
        ]
    ].head(5)


def render_ml_master_review(
    *,
    variant_summary_df: pd.DataFrame,
    rule_summary: dict[str, Any],
    best_ml_summary: dict[str, Any],
    adoption_recommendation: str,
    linear_highlights: pd.DataFrame,
    tree_highlights: pd.DataFrame,
    weakest_folds: pd.DataFrame,
    fold_model_metrics: pd.DataFrame,
) -> str:
    summary_columns = [
        "rank",
        "display_name",
        "stitched_relative_excess_return",
        "stitched_total_return",
        "stitched_benchmark_total_return",
        "positive_excess_folds",
        "holdout_relative_excess_return",
        "worst_max_drawdown",
        "avg_turnover",
        "avg_blocked_order_ratio",
        "beats_benchmark",
        "beats_rule_baseline",
        "adoption_recommendation",
    ]
    lines = [
        "# ML Factor Combination Review",
        "",
        "## Executive Summary",
        f"- Best ML variant: `{best_ml_summary.get('display_name', '')}`",
        f"- Best ML stitched relative excess vs `000001.SH`: `{best_ml_summary.get('stitched_relative_excess_return', np.nan):.2%}`",
        f"- Best ML vs same-execution rule baseline: `{best_ml_summary.get('beats_rule_baseline', False)}`",
        f"- Adoption recommendation: `{adoption_recommendation}`",
        "",
        "## Variant Comparison",
        dataframe_to_markdown(variant_summary_df, columns=[column for column in summary_columns if column in variant_summary_df.columns]),
        "",
        "## Same-Execution Rule Baseline",
        dataframe_to_markdown(pd.DataFrame([rule_summary])),
        "",
        "## ElasticNet Factor Highlights",
        dataframe_to_markdown(
            linear_highlights,
            columns=["factor", "avg_abs_weight_share", "avg_coefficient", "fold_count"],
        ),
        "",
        "## LightGBM Factor Highlights",
        dataframe_to_markdown(
            tree_highlights,
            columns=["factor", "avg_gain_share", "avg_split_share", "fold_count"],
        ),
        "",
        "## Weakest Folds For Best ML Variant",
        dataframe_to_markdown(
            weakest_folds,
            columns=[
                "fold_id",
                "cumulative_return",
                "benchmark_total_return",
                "relative_excess_return",
                "max_drawdown",
                "turnover_mean",
                "blocked_order_ratio",
                "window_start",
                "window_end",
            ],
        ),
        "",
        "## Fold-Level Model Notes",
        dataframe_to_markdown(
            fold_model_metrics[
                fold_model_metrics["split"].isin(["validation", "test", "holdout"])
            ].copy(),
            columns=[
                "variant_id",
                "fold_id",
                "window_type",
                "split",
                "alpha",
                "l1_ratio",
                "best_iteration",
                "validation_relative_excess_return",
                "validation_prediction_rank_icir",
                "test_relative_excess_return",
                "test_prediction_rank_icir",
            ],
        ),
        "",
        "## Interpretation",
        bullet_list(
            [
                "Rule baseline is the current best non-ML selection logic (`C_stability_score`) rerun under the same conservative 10-day execution settings.",
                "ElasticNet exposes direct factor weights, so it is easier to explain when we want to see which factors the model is leaning on.",
                "LightGBM does not give a single clean weight vector, so we review it through feature importance instead.",
                "Turnover and blocked-order ratio are kept as execution diagnostics, not as hard promotion gates.",
            ]
        ),
    ]
    return "\n".join(lines) + "\n"


def run_rule_baseline_same_execution(
    *,
    bundle,
    context,
    selection_forward_return: pd.Series,
    stability_scores: pd.DataFrame,
    liquidity_scenarios: dict[str, LiquidityScenario],
    args: argparse.Namespace,
    run_dir: Path,
) -> Any:
    LOGGER.info("Running same-execution rule baseline (C_stability_score logic)")
    spec = VariantSpec(
        stage="RULE",
        variant_id="rule_baseline_conservative_10d",
        description="Current best rule logic (C_stability_score) rerun with the same conservative 10-day execution settings as ML.",
        benchmark=args.benchmark,
        universe_mode="all_market",
        selection_mode="stability_score",
        portfolio_weighting="equal",
        topk=int(args.topk),
        rebalance_days=int(args.rebalance_days),
        slow_rebalance_days=int(args.rebalance_days),
        liquidity_scenario="adv_floor_plus_participation",
        slippage_rate=SLIPPAGE_RATE,
    )
    return evaluate_variant(
        spec=spec,
        bundle=bundle,
        context=context,
        forward_return=selection_forward_return,
        stability_scores=stability_scores,
        liquidity_scenarios=liquidity_scenarios,
        run_dir=run_dir,
        keep_detail=True,
    )


def build_model_variant_artifacts(
    *,
    spec: MLVariantSpec,
    oos_rows: list[dict[str, Any]],
    event_reports: list[pd.DataFrame],
    signal_frames: list[pd.DataFrame],
    signal_diag_frames: list[pd.DataFrame],
    prediction_frames: list[pd.DataFrame],
    metric_frames: list[pd.DataFrame],
    linear_weight_frames: list[pd.DataFrame],
    importance_frames: list[pd.DataFrame],
) -> MLVariantArtifacts:
    oos_df = pd.DataFrame(oos_rows)
    event_report = concat_nonempty(event_reports)
    signal_df = concat_nonempty(signal_frames)
    signal_diagnostics = concat_nonempty(signal_diag_frames)
    prediction_df = concat_nonempty(prediction_frames)
    fold_metrics = concat_nonempty(metric_frames)
    linear_weights = concat_nonempty(linear_weight_frames)
    feature_importance = concat_nonempty(importance_frames)
    summary = summarize_ml_variant(spec=spec, oos_df=oos_df)
    return MLVariantArtifacts(
        spec=spec,
        summary=summary,
        oos_performance=oos_df,
        event_report=event_report,
        signal_df=signal_df,
        signal_diagnostics=signal_diagnostics,
        prediction_df=prediction_df,
        fold_metrics=fold_metrics,
        linear_weights=linear_weights,
        feature_importance=feature_importance,
    )


def run_ml_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_output_dir(args)
    configure_logging(run_dir)
    LOGGER.info("Starting ML factor-combination research")
    LOGGER.info("Baseline run: %s", args.baseline_run_dir)
    LOGGER.info("Screening run: %s", args.screening_run_dir)

    model_variants = parse_model_variants(args.model_variants)
    baseline_run_dir = Path(args.baseline_run_dir).resolve()
    screening_run_dir = Path(args.screening_run_dir).resolve()
    bundle = load_baseline_bundle(baseline_run_dir)
    validate_inputs(
        baseline_run_dir=baseline_run_dir,
        screening_run_dir=screening_run_dir,
        bundle=bundle,
        label_horizon=int(args.label_horizon),
    )
    bundle.run_metadata["capital"] = float(args.capital)

    label_forward_return = load_forward_return_series(bundle, run_dir, int(args.label_horizon))
    selection_forward_return = load_forward_return_series(bundle, run_dir, RULE_SELECTION_LABEL_HORIZON)
    context = load_support_context(bundle, run_dir)
    liquidity_scenarios = build_liquidity_scenario_map(args)
    conservative_scenario = liquidity_scenarios["adv_floor_plus_participation"]
    stability_scores = compute_stability_scores(bundle.factor_selection_decisions)
    rule_baseline = run_rule_baseline_same_execution(
        bundle=bundle,
        context=context,
        selection_forward_return=selection_forward_return,
        stability_scores=stability_scores,
        liquidity_scenarios=liquidity_scenarios,
        args=args,
        run_dir=run_dir,
    )

    windows = build_model_windows(bundle.folds, bundle.holdout)
    datasets = []
    for idx, window in enumerate(windows, start=1):
        LOGGER.info("Preparing ML dataset %d/%d for %s", idx, len(windows), window.fold_id)
        datasets.append(
            prepare_fold_dataset(
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

    for idx, dataset in enumerate(datasets, start=1):
        LOGGER.info("Running ML models for fold %d/%d: %s", idx, len(datasets), dataset.fold_id)
        if "linear" in model_variants:
            linear_result = run_elasticnet_for_window(
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
            lightgbm_result = run_lightgbm_for_window(
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

    variant_artifacts: list[MLVariantArtifacts] = []
    if "linear" in variant_stores:
        variant_artifacts.append(
            build_model_variant_artifacts(
                spec=MLVariantSpec("elasticnet", "linear", "ElasticNet factor-weight model"),
                **variant_stores["linear"],
            )
        )
    if "lightgbm" in variant_stores:
        variant_artifacts.append(
            build_model_variant_artifacts(
                spec=MLVariantSpec("lightgbm", "tree", "LightGBM direct-scoring model"),
                **variant_stores["lightgbm"],
            )
        )

    variant_summary_rows = []
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
    variant_summary_rows.append(rule_summary)

    for artifacts in variant_artifacts:
        summary = artifacts.summary.copy()
        summary["beats_rule_baseline"] = bool(
            pd.notna(summary.get("stitched_relative_excess_return"))
            and pd.notna(rule_summary.get("stitched_relative_excess_return"))
            and float(summary.get("stitched_relative_excess_return")) > float(rule_summary.get("stitched_relative_excess_return"))
        )
        summary["adoption_recommendation"] = choose_adoption_recommendation(summary, rule_summary)
        variant_summary_rows.append(summary)

    variant_summary_df = rank_variant_summary(pd.DataFrame(variant_summary_rows))
    ml_only_summary_df = variant_summary_df[variant_summary_df["model_kind"].isin(["linear", "tree"])].copy()
    if ml_only_summary_df.empty:
        raise ValueError("No ML variant was executed.")
    best_ml_summary = ml_only_summary_df.iloc[0].to_dict()
    adoption_recommendation = str(best_ml_summary.get("adoption_recommendation", "keep as research"))

    best_ml_artifacts = next(
        artifacts for artifacts in variant_artifacts if artifacts.spec.variant_id == best_ml_summary["variant_id"]
    )
    linear_weights = concat_nonempty([artifacts.linear_weights for artifacts in variant_artifacts])
    feature_importance = concat_nonempty([artifacts.feature_importance for artifacts in variant_artifacts])
    linear_highlights, tree_highlights = build_factor_highlight_tables(linear_weights, feature_importance)
    all_oos = concat_nonempty(
        [rule_baseline.oos_performance.assign(variant_id="rule_baseline")]
        + [artifacts.oos_performance for artifacts in variant_artifacts]
    )
    weakest_folds = build_weakest_fold_table(all_oos, str(best_ml_summary["variant_id"]))
    fold_model_metrics = concat_nonempty([artifacts.fold_metrics for artifacts in variant_artifacts])
    prediction_panel = concat_nonempty([artifacts.prediction_df for artifacts in variant_artifacts])
    ml_master_review = render_ml_master_review(
        variant_summary_df=variant_summary_df,
        rule_summary=rule_summary,
        best_ml_summary=best_ml_summary,
        adoption_recommendation=adoption_recommendation,
        linear_highlights=linear_highlights,
        tree_highlights=tree_highlights,
        weakest_folds=weakest_folds,
        fold_model_metrics=fold_model_metrics,
    )

    write_text(run_dir / "ml_master_review.md", ml_master_review)
    variant_summary_df.to_csv(run_dir / "variant_comparison_summary.csv", index=False)
    fold_model_metrics.to_csv(run_dir / "fold_model_metrics.csv", index=False)
    linear_weights.to_csv(run_dir / "linear_factor_weights_by_fold.csv", index=False)
    feature_importance.to_csv(run_dir / "lightgbm_feature_importance_by_fold.csv", index=False)
    prediction_panel.to_parquet(run_dir / "prediction_panel.parquet", index=False)
    rule_baseline.event_report.to_csv(run_dir / "event_driven_report_rule_baseline.csv", index=False)
    next((art.event_report for art in variant_artifacts if art.spec.variant_id == "elasticnet"), pd.DataFrame()).to_csv(
        run_dir / "event_driven_report_elasticnet.csv",
        index=False,
    )
    next((art.event_report for art in variant_artifacts if art.spec.variant_id == "lightgbm"), pd.DataFrame()).to_csv(
        run_dir / "event_driven_report_lightgbm.csv",
        index=False,
    )
    all_oos.to_csv(run_dir / "oos_fold_performance.csv", index=False)

    best_event_report = best_ml_artifacts.event_report.copy()
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
        build_backtest_html(
            run_dir / "best_ml_variant_backtest_report.html",
            strategy_returns=strategy_returns,
            benchmark_returns=benchmark_returns,
            name=f"Best ML Variant: {best_ml_summary['display_name']}",
        )

    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline_run_dir": str(baseline_run_dir),
        "screening_run_dir": str(screening_run_dir),
        "benchmark": args.benchmark,
        "label_horizon": int(args.label_horizon),
        "topk": int(args.topk),
        "rebalance_days": int(args.rebalance_days),
        "capital": float(args.capital),
        "adv_median_floor": float(args.adv_median_floor),
        "participation_cap": float(args.participation_cap),
        "model_variants": model_variants,
        "candidate_factor_count": len(bundle.candidate_factors),
        "candidate_factors": bundle.candidate_factors,
        "folds": [asdict(fold) for fold in bundle.folds],
        "holdout": asdict(bundle.holdout) if bundle.holdout is not None else None,
        "elasticnet_alpha_grid": list(ELASTICNET_ALPHA_GRID),
        "elasticnet_l1_ratio_grid": list(ELASTICNET_L1_GRID),
        "lightgbm_params": LIGHTGBM_PARAMS,
        "rule_selection_logic": "C_stability_score under the current improvement workflow",
        "rule_selection_label_horizon": RULE_SELECTION_LABEL_HORIZON,
        "liquidity_policy": {
            "scenario": "adv_floor_plus_participation",
            "adv_median_floor": float(args.adv_median_floor),
            "participation_cap": float(args.participation_cap),
        },
        **resolve_mlflow_status(None, disabled=bool(args.disable_mlflow)),
        "rule_baseline_summary": rule_summary,
        "best_ml_summary": best_ml_summary,
        "adoption_recommendation": adoption_recommendation,
    }
    write_json(run_dir / "run_metadata.json", metadata)
    LOGGER.info("ML factor-combination research finished: %s", run_dir)
    return {
        "run_dir": run_dir,
        "metadata": metadata,
    }


def main() -> None:
    from src.research_orchestrator.engine import _build_ml_request_from_args, run_research

    args = parse_args()
    run_research(_build_ml_request_from_args(args))


if __name__ == "__main__":
    main()
