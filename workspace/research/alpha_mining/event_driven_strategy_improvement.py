"""
Systematic improvement experiments for the event-driven alpha-mining strategy.

This entrypoint keeps the existing formal research run as the frozen baseline,
audits the new SSE Composite benchmark, diagnoses why strong ICIR did not turn
into strong long-only returns, and then evaluates structured upgrade variants.
"""

from __future__ import annotations

import argparse
import json
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

from src.alpha_research.factor_eval import compute_factor_correlation, compute_marginal_ic
from src.alpha_research.factor_library.operators import compute_factors, cs_rank
from workspace.research.alpha_mining.audit_benchmark_index import BenchmarkAuditResult, run_audit
from workspace.research.alpha_mining.event_driven_strategy_research import (
    LISTED_MIN_TRADING_DAYS,
    MAX_SELECTED_FACTORS,
    SELECTION_CORR_THRESHOLD,
    SELECTION_MIN_MARGINAL_ICIR,
    FoldSpec,
    HoldoutSpec,
    LiquidityScenario,
    aggregate_result_frames,
    apply_liquidity_rules,
    assign_corr_clusters,
    build_backtest_html,
    build_rebalance_dates,
    compute_fold_metrics_for_factor,
    compound_fold_total_returns,
    concat_with_fold,
    configure_logging,
    fetch_auxiliary_fields,
    is_st_on_date,
    load_screening_inputs,
    load_stock_basic_reference,
    parse_st_ranges,
    qlib_to_ts_code,
    read_series_parquet,
    resolve_mlflow_status,
    run_event_driven_window,
    select_core_factors_for_fold,
    slice_window,
    ts_to_qlib_code,
    write_json,
    write_series_parquet,
)
from workspace.research.alpha_mining.event_driven_strategy_report import (
    dataframe_to_markdown,
    write_text,
)


LOGGER = logging.getLogger("alpha_mining.event_driven_strategy_improvement")
FAST_BLEND_WEIGHT = 0.60
SLOW_BLEND_WEIGHT = 0.40
SCORE_PROP_SINGLE_STOCK_CAP = 0.03
STABILITY_TOP_N = 12

FAMILY_CAPS = {
    "Liquidity": 0.30,
    "MomentumReversal": 0.30,
    "Volatility": 0.25,
    "Technical": 0.15,
    "OtherCompositeDefensive": 0.20,
    "CapitalFlow": 0.15,
    "Northbound": 0.15,
    "Growth": 0.15,
    "Value": 0.15,
}


@dataclass(frozen=True)
class VariantSpec:
    stage: str
    variant_id: str
    description: str
    benchmark: str
    universe_mode: str
    selection_mode: str
    portfolio_weighting: str
    topk: int
    rebalance_days: int
    slow_rebalance_days: int | None
    liquidity_scenario: str
    slippage_rate: float


@dataclass(frozen=True)
class BaselineBundle:
    baseline_run_dir: Path
    screening_run_dir: Path
    run_metadata: dict[str, Any]
    screening_metadata: dict[str, Any]
    screening_report: pd.DataFrame
    factor_selection_decisions: pd.DataFrame
    selected_by_fold: pd.DataFrame
    factor_research_metrics: pd.DataFrame
    baseline_signal: pd.DataFrame
    candidate_factors: list[str]
    folds: list[FoldSpec]
    holdout: HoldoutSpec | None
    processed_factor_paths: dict[str, Path]


@dataclass(frozen=True)
class SupportContext:
    aux_df: pd.DataFrame
    stock_basic: pd.DataFrame
    stock_basic_map: pd.DataFrame
    trade_calendar: list[pd.Timestamp]
    trade_calendar_index: pd.DatetimeIndex
    trade_pos_by_date: dict[pd.Timestamp, int]
    st_ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]
    factor_category: dict[str, str]
    factor_best_decay: dict[str, float]


@dataclass
class VariantArtifacts:
    spec: VariantSpec
    summary: dict[str, Any]
    oos_performance: pd.DataFrame
    event_report: pd.DataFrame
    trades: pd.DataFrame
    order_log: pd.DataFrame
    signal_df: pd.DataFrame
    signal_diagnostics: pd.DataFrame
    selected_by_fold: pd.DataFrame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the SSE benchmark and run systematic event-driven strategy improvement experiments."
    )
    parser.add_argument("--baseline-run-dir", required=True, help="Completed formal baseline research run directory")
    parser.add_argument("--output-dir", default=None, help="Optional explicit output directory")
    parser.add_argument("--benchmark", default="000001.SH", help="Benchmark index code")
    parser.add_argument("--universe-mode", default="all_market", help="Universe mode label for reporting")
    parser.add_argument("--selection-mode", default="baseline", help="Default selection mode label")
    parser.add_argument("--portfolio-weighting", default="equal", help="Default portfolio weighting label")
    parser.add_argument("--topk", type=int, default=50, help="Baseline portfolio size")
    parser.add_argument("--rebalance-days", type=int, default=5, help="Fast/base rebalance interval")
    parser.add_argument("--slow-rebalance-days", type=int, default=10, help="Slow sleeve rebalance interval")
    parser.add_argument("--liquidity-scenario", default="adv_floor_plus_participation", help="Default liquidity scenario label")
    parser.add_argument("--slippage-rate", type=float, default=0.0005, help="Default slippage rate")
    parser.add_argument("--capital", type=float, default=2_000_000, help="Initial capital")
    parser.add_argument("--adv-median-floor", type=float, default=5_000_000, help="ADV20 median floor in RMB")
    parser.add_argument("--participation-cap", type=float, default=0.02, help="Single rebalance target-value / ADV20 cap")
    parser.add_argument("--max-folds", type=int, default=None, help="Optional debug cap for the number of folds")
    return parser.parse_args()


def resolve_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (PROJECT_ROOT / "workspace" / "research" / "alpha_mining" / f"event_driven_strategy_improvement_{stamp}").resolve()


def load_baseline_bundle(baseline_run_dir: Path, max_folds: int | None = None) -> BaselineBundle:
    metadata = json.loads((baseline_run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    screening_run_dir = Path(metadata["screening_run_dir"]).resolve()
    screening_report, screening_metadata = load_screening_inputs(screening_run_dir)
    factor_selection_decisions = pd.read_csv(baseline_run_dir / "factor_selection_decisions.csv")
    selected_by_fold = pd.read_csv(baseline_run_dir / "selected_core_factors_by_fold.csv")
    factor_research_metrics = pd.read_csv(baseline_run_dir / "factor_research_metrics.csv")
    baseline_signal = pd.read_parquet(baseline_run_dir / "strategy_signal.parquet")

    candidate_factors = list(metadata.get("candidate_factors") or factor_research_metrics["factor"].tolist())
    folds = [FoldSpec(**row) for row in metadata.get("folds", [])]
    if max_folds is not None:
        folds = folds[:max_folds]
        keep_ids = {fold.fold_id for fold in folds}
        factor_selection_decisions = factor_selection_decisions[factor_selection_decisions["fold_id"].isin(keep_ids)].copy()
        selected_by_fold = selected_by_fold[selected_by_fold["fold_id"].isin(keep_ids)].copy()
        baseline_signal = baseline_signal[baseline_signal["fold_id"].isin(keep_ids | {"holdout"})].copy()
    holdout_meta = metadata.get("holdout")
    holdout = HoldoutSpec(**holdout_meta) if holdout_meta else None

    processed_factor_paths = {
        factor: baseline_run_dir / "cache" / "processed_factors" / f"{factor}.parquet"
        for factor in candidate_factors
    }
    missing = [factor for factor, path in processed_factor_paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing processed factor cache for: {missing[:5]}")

    return BaselineBundle(
        baseline_run_dir=baseline_run_dir,
        screening_run_dir=screening_run_dir,
        run_metadata=metadata,
        screening_metadata=screening_metadata,
        screening_report=screening_report,
        factor_selection_decisions=factor_selection_decisions,
        selected_by_fold=selected_by_fold,
        factor_research_metrics=factor_research_metrics,
        baseline_signal=baseline_signal,
        candidate_factors=candidate_factors,
        folds=folds,
        holdout=holdout,
        processed_factor_paths=processed_factor_paths,
    )


def build_liquidity_scenario_map(args: argparse.Namespace) -> dict[str, LiquidityScenario]:
    return {
        "no_filter": LiquidityScenario("no_filter", adv_floor=None, participation_cap=None, bottom_pct=None),
        "adv_floor_only": LiquidityScenario(
            "adv_floor_only",
            adv_floor=float(args.adv_median_floor),
            participation_cap=None,
            bottom_pct=None,
        ),
        "adv_floor_plus_participation": LiquidityScenario(
            "adv_floor_plus_participation",
            adv_floor=float(args.adv_median_floor),
            participation_cap=float(args.participation_cap),
            bottom_pct=None,
        ),
        "bottom_20pct_filter": LiquidityScenario(
            "bottom_20pct_filter",
            adv_floor=None,
            participation_cap=None,
            bottom_pct=0.20,
        ),
    }

def _resolve_effective_window(
    bundle: BaselineBundle,
    *,
    start_override: str | None = None,
    end_override: str | None = None,
) -> tuple[str, str]:
    start_date = str(start_override or bundle.screening_metadata["start_date"])
    end_date = str(end_override or bundle.screening_metadata["end_date"])
    return start_date, end_date


def _load_forward_return_series_with_window(
    bundle: BaselineBundle,
    run_dir: Path,
    *,
    start_override: str | None = None,
    end_override: str | None = None,
) -> pd.Series:
    cache_path = run_dir / "cache" / "forward_return_5d.parquet"
    if cache_path.exists():
        return read_series_parquet(cache_path)

    LOGGER.info("Computing cached 5d forward return series for improvement experiments")
    start_date, end_date = _resolve_effective_window(
        bundle,
        start_override=start_override,
        end_override=end_override,
    )
    _, fwd_df = compute_factors(
        {},
        start_date,
        end_date,
        horizons=[5],
        qlib_dir=bundle.screening_metadata["qlib_dir"],
        kernels=None,
        progress_interval=60,
    )
    forward_return = fwd_df["fwd_5d"].astype(np.float32)
    write_series_parquet(forward_return, cache_path)
    return forward_return


def load_forward_return_series(
    bundle: BaselineBundle,
    run_dir: Path,
    *,
    start_override: str | None = None,
    end_override: str | None = None,
) -> pd.Series:
    return _load_forward_return_series_with_window(
        bundle,
        run_dir,
        start_override=start_override,
        end_override=end_override,
    )


def load_support_context(
    bundle: BaselineBundle,
    run_dir: Path,
    *,
    start_override: str | None = None,
    end_override: str | None = None,
) -> SupportContext:
    aux_path = run_dir / "cache" / "aux_fields.parquet"
    if aux_path.exists():
        aux_df = pd.read_parquet(aux_path)
    else:
        LOGGER.info("Fetching auxiliary fields for liquidity and exposure diagnostics")
        start_date, end_date = _resolve_effective_window(
            bundle,
            start_override=start_override,
            end_override=end_override,
        )
        aux_df = fetch_auxiliary_fields(
            start_date,
            end_date,
        )
        aux_df.to_parquet(aux_path)

    data_dir = PROJECT_ROOT / "data"
    stock_basic = load_stock_basic_reference(data_dir)
    trade_cal = pd.read_parquet(data_dir / "reference" / "trade_cal.parquet").copy()
    trade_cal["cal_date"] = pd.to_datetime(trade_cal["cal_date"], format="%Y%m%d")
    trade_calendar = trade_cal.loc[trade_cal["is_open"] == 1, "cal_date"].sort_values().tolist()
    trade_index = pd.DatetimeIndex(trade_calendar)
    trade_pos_by_date = {pd.Timestamp(date): idx for idx, date in enumerate(trade_index)}

    stock_basic["exchange_bucket"] = stock_basic["ts_code"].astype(str).str.split(".").str[-1]
    stock_basic["list_idx"] = stock_basic["list_date"].apply(
        lambda value: int(trade_index.searchsorted(value, side="left")) if pd.notna(value) else 0
    )
    stock_basic_map = stock_basic.set_index("qlib_code")

    st_ranges = parse_st_ranges(data_dir / "qlib_data" / "instruments" / "st_stocks.txt")
    factor_category = (
        bundle.factor_research_metrics.drop_duplicates("factor").set_index("factor")["category"].to_dict()
    )
    factor_best_decay = (
        bundle.factor_research_metrics.drop_duplicates("factor").set_index("factor")["best_decay_horizon"].to_dict()
    )

    return SupportContext(
        aux_df=aux_df,
        stock_basic=stock_basic,
        stock_basic_map=stock_basic_map,
        trade_calendar=trade_calendar,
        trade_calendar_index=trade_index,
        trade_pos_by_date=trade_pos_by_date,
        st_ranges=st_ranges,
        factor_category=factor_category,
        factor_best_decay=factor_best_decay,
    )


def compound_column(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return float("nan")
    values = df[column].dropna().astype(float)
    if values.empty:
        return float("nan")
    return float(np.prod(1.0 + values) - 1.0)


def relative_excess_return(strategy_total_return: float, benchmark_total_return: float) -> float:
    if pd.isna(strategy_total_return) or pd.isna(benchmark_total_return):
        return float("nan")
    if benchmark_total_return <= -1.0:
        return float("nan")
    return float((1.0 + float(strategy_total_return)) / (1.0 + float(benchmark_total_return)) - 1.0)


def compute_stability_scores(factor_selection_decisions: pd.DataFrame) -> pd.DataFrame:
    work = factor_selection_decisions.copy()
    work["abs_validation_rank_icir"] = work["val_rank_icir"].abs()
    work["abs_marginal_rank_icir"] = work["marginal_rank_icir"].abs().fillna(0.0)
    agg = (
        work.groupby("factor")
        .agg(
            selected_frequency=("selected", "mean"),
            avg_abs_validation_rank_icir=("abs_validation_rank_icir", "mean"),
            avg_abs_marginal_rank_icir=("abs_marginal_rank_icir", "mean"),
            validation_pass_rate=("validation_pass", "mean"),
            max_abs_corr=("max_abs_corr", "max"),
        )
        .reset_index()
    )
    agg["max_abs_corr"] = agg["max_abs_corr"].fillna(0.0).clip(lower=0.0, upper=1.0)
    agg["low_corr_reward"] = 1.0 - agg["max_abs_corr"]

    metric_weights = {
        "selected_frequency": 0.35,
        "avg_abs_validation_rank_icir": 0.25,
        "avg_abs_marginal_rank_icir": 0.20,
        "validation_pass_rate": 0.10,
        "low_corr_reward": 0.10,
    }
    for column in metric_weights:
        agg[f"norm_{column}"] = agg[column].rank(method="average", pct=True).fillna(0.0)
    agg["stability_score"] = 0.0
    for column, weight in metric_weights.items():
        agg["stability_score"] += weight * agg[f"norm_{column}"]

    return agg.sort_values(
        ["stability_score", "selected_frequency", "avg_abs_validation_rank_icir", "factor"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def factor_family_bucket(factor: str, category: str | None) -> str:
    if factor.startswith("liq_"):
        return "Liquidity"
    if factor.startswith(("mom_", "rev_")):
        return "MomentumReversal"
    if factor.startswith("risk_"):
        return "Volatility"
    if factor.startswith("tech_"):
        return "Technical"
    if factor.startswith("flow_"):
        return "CapitalFlow"
    if factor.startswith("north_"):
        return "Northbound"
    if factor.startswith("grow_") or category == "Growth":
        return "Growth"
    if factor.startswith("val_") or category == "Value":
        return "Value"
    return "OtherCompositeDefensive"


def normalize_weight_series(weights: pd.Series) -> pd.Series:
    clean = weights.astype(float).clip(lower=0.0)
    total = float(clean.sum())
    if total <= 0:
        raise ValueError("Weight series cannot sum to zero.")
    return clean / total


def apply_factor_family_caps(weights: pd.Series, family_map: dict[str, str]) -> pd.Series:
    capped = normalize_weight_series(weights)
    for _ in range(12):
        family_series = pd.Series({factor: family_map.get(factor, "OtherCompositeDefensive") for factor in capped.index})
        family_sums = capped.groupby(family_series).sum()
        over_families = {
            family: FAMILY_CAPS[family]
            for family, value in family_sums.items()
            if family in FAMILY_CAPS and float(value) > FAMILY_CAPS[family] + 1e-12
        }
        if not over_families:
            return normalize_weight_series(capped)

        excess = 0.0
        locked_factors: set[str] = set()
        for family, cap in over_families.items():
            members = [factor for factor in capped.index if family_series[factor] == family]
            current = float(capped.loc[members].sum())
            if current <= 0:
                continue
            scale = float(cap) / current
            capped.loc[members] = capped.loc[members] * scale
            excess += current - float(capped.loc[members].sum())
            locked_factors.update(members)

        free_factors = [factor for factor in capped.index if factor not in locked_factors]
        if not free_factors or excess <= 0:
            return normalize_weight_series(capped)
        free_weights = capped.loc[free_factors]
        free_total = float(free_weights.sum())
        if free_total <= 0:
            capped.loc[free_factors] = excess / len(free_factors)
        else:
            capped.loc[free_factors] = free_weights + excess * free_weights / free_total
        capped = normalize_weight_series(capped)
    return normalize_weight_series(capped)


def build_factor_weight_map(
    selected_factors: list[str],
    factor_category: dict[str, str],
    *,
    use_family_caps: bool,
) -> pd.Series:
    if not selected_factors:
        return pd.Series(dtype=float)
    base = pd.Series(1.0, index=selected_factors, dtype=float)
    if not use_family_caps:
        return normalize_weight_series(base)
    family_map = {
        factor: factor_family_bucket(factor, factor_category.get(factor))
        for factor in selected_factors
    }
    return apply_factor_family_caps(base, family_map)


def apply_single_stock_cap(weights: pd.Series, cap: float) -> pd.Series:
    capped = normalize_weight_series(weights)
    if len(capped) * cap < 1.0 - 1e-12:
        raise ValueError("Single-stock cap is infeasible for the requested number of names.")
    fixed = pd.Series(False, index=capped.index)
    for _ in range(24):
        over = capped > cap + 1e-12
        if not over.any():
            return normalize_weight_series(capped)
        fixed = fixed | over
        excess = float((capped[over] - cap).sum())
        capped.loc[over] = cap
        free = ~fixed
        if not free.any() or excess <= 0:
            return normalize_weight_series(capped)
        free_weights = capped.loc[free]
        free_total = float(free_weights.sum())
        if free_total <= 0:
            capped.loc[free] = excess / int(free.sum())
        else:
            capped.loc[free] = free_weights + excess * free_weights / free_total
        capped = normalize_weight_series(capped)
    return normalize_weight_series(capped)


def build_stock_weights(selected_scores: pd.Series, weighting_mode: str) -> pd.Series:
    ordered = selected_scores.sort_values(ascending=False)
    if ordered.empty:
        return ordered.astype(float)
    if weighting_mode == "equal":
        return normalize_weight_series(pd.Series(1.0, index=ordered.index, dtype=float))
    if weighting_mode == "tiered":
        weights = pd.Series(0.75, index=ordered.index, dtype=float)
        head_20 = min(len(weights), 20)
        next_30_end = min(len(weights), 50)
        weights.iloc[:head_20] = 2.0
        if next_30_end > head_20:
            weights.iloc[head_20:next_30_end] = 1.25
        return normalize_weight_series(weights)
    if weighting_mode == "score_proportional":
        raw = ordered - float(ordered.min()) + 1e-6
        if float(raw.sum()) <= 0:
            raw = pd.Series(1.0, index=ordered.index, dtype=float)
        return apply_single_stock_cap(raw, SCORE_PROP_SINGLE_STOCK_CAP)
    raise ValueError(f"Unknown portfolio weighting mode: {weighting_mode}")


def build_weight_preview_row(scores: pd.Series) -> dict[str, float]:
    def hhi(weights: pd.Series) -> float:
        return float((weights**2).sum()) if not weights.empty else float("nan")

    def top10_share(weights: pd.Series) -> float:
        return float(weights.sort_values(ascending=False).head(10).sum()) if not weights.empty else float("nan")

    equal = build_stock_weights(scores, "equal")
    tiered = build_stock_weights(scores, "tiered")
    score_prop = build_stock_weights(scores, "score_proportional")
    return {
        "equal_hhi": hhi(equal),
        "tiered_hhi": hhi(tiered),
        "score_prop_hhi": hhi(score_prop),
        "equal_top10_share": top10_share(equal),
        "tiered_top10_share": top10_share(tiered),
        "score_prop_top10_share": top10_share(score_prop),
    }


def filter_stability_pool_for_fold(
    fold_rows: pd.DataFrame,
    stability_scores: pd.DataFrame,
    *,
    top_n: int = STABILITY_TOP_N,
) -> pd.DataFrame:
    score_map = stability_scores.set_index("factor")["stability_score"]
    ranked = fold_rows.copy()
    ranked["stability_score"] = ranked["factor"].map(score_map)
    ranked = ranked[
        ranked["validation_pass"].fillna(False)
        & ranked["stability_score"].notna()
    ].copy()
    ranked["abs_validation_rank_icir"] = ranked["val_rank_icir"].abs()
    return ranked.sort_values(
        ["stability_score", "abs_validation_rank_icir", "factor"],
        ascending=[False, False, True],
    ).head(top_n).reset_index(drop=True)


def select_ranked_factor_pool_for_fold(
    *,
    fold: FoldSpec,
    ranked_pool: pd.DataFrame,
    processed_factor_paths: dict[str, Path],
    forward_return: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if ranked_pool.empty:
        return pd.DataFrame(), pd.DataFrame()

    series_map = {
        factor: slice_window(read_series_parquet(processed_factor_paths[factor]), fold.validation_start, fold.validation_end)
        for factor in ranked_pool["factor"].tolist()
    }
    corr_matrix = compute_factor_correlation(series_map, method="spearman")
    cluster_map = assign_corr_clusters(corr_matrix, threshold=SELECTION_CORR_THRESHOLD)

    work = ranked_pool.copy()
    work["cluster_id"] = work["factor"].map(cluster_map).fillna("")
    work["abs_validation_rank_icir"] = work["val_rank_icir"].abs()
    if "stability_score" not in work.columns:
        work["stability_score"] = work["abs_validation_rank_icir"]
    work = work.sort_values(
        ["stability_score", "abs_validation_rank_icir", "factor"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    val_fwd = slice_window(forward_return, fold.validation_start, fold.validation_end)
    selected_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    selected_factors: list[str] = []
    selected_series: dict[str, pd.Series] = {}

    for _, row in work.iterrows():
        factor = row["factor"]
        factor_series = series_map[factor]
        max_abs_corr = 0.0
        corr_blocker = None
        for peer in selected_factors:
            corr_value = corr_matrix.loc[factor, peer]
            if pd.notna(corr_value) and abs(float(corr_value)) > max_abs_corr:
                max_abs_corr = abs(float(corr_value))
                corr_blocker = peer

        marginal_rank_icir = np.nan
        marginal_mean_rank_ic = np.nan
        if selected_factors:
            _, marginal_summary = compute_marginal_ic(
                {**selected_series, factor: factor_series},
                val_fwd,
                selected_factors,
                factor,
            )
            marginal_rank_icir = float(marginal_summary.get("rank_icir", np.nan))
            marginal_mean_rank_ic = float(marginal_summary.get("mean_rank_ic", np.nan))

        selected = True
        rejection_reason = ""
        if len(selected_factors) >= MAX_SELECTED_FACTORS:
            selected = False
            rejection_reason = "Core factor quota already reached."
        elif corr_blocker is not None and max_abs_corr >= SELECTION_CORR_THRESHOLD:
            selected = False
            rejection_reason = f"High redundancy with {corr_blocker} (|corr|={max_abs_corr:.3f})."
        elif selected_factors and (pd.isna(marginal_rank_icir) or abs(marginal_rank_icir) < SELECTION_MIN_MARGINAL_ICIR):
            selected = False
            rejection_reason = "Marginal ICIR is too weak after controlling for already-selected factors."

        if selected:
            selected_factors.append(factor)
            selected_series[factor] = factor_series
            selected_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "selection_rank": len(selected_rows) + 1,
                    "factor": factor,
                    "validation_rank_icir": row["val_rank_icir"],
                    "marginal_rank_icir": marginal_rank_icir,
                    "cluster_id": row["cluster_id"],
                    "selection_reason": "Admitted from the stability-ranked top-12 pool.",
                }
            )

        decision_rows.append(
            {
                **row.to_dict(),
                "selected": selected,
                "rejection_reason": rejection_reason,
                "max_abs_corr": max_abs_corr,
                "marginal_mean_rank_ic": marginal_mean_rank_ic,
                "marginal_rank_icir": marginal_rank_icir,
            }
        )

    return pd.DataFrame(selected_rows), pd.DataFrame(decision_rows)


def build_direction_map(decisions_df: pd.DataFrame) -> dict[str, dict[str, int]]:
    mapping: dict[str, dict[str, int]] = {}
    for fold_id, fold_df in decisions_df.groupby("fold_id"):
        mapping[str(fold_id)] = {
            str(row["factor"]): int(row["train_direction"])
            for _, row in fold_df.iterrows()
        }
    return mapping


def build_holdout_metric_df(
    bundle: BaselineBundle,
    forward_return: pd.Series,
    run_dir: Path,
) -> pd.DataFrame:
    if bundle.holdout is None:
        return pd.DataFrame()
    cache_path = run_dir / "cache" / "holdout_factor_metrics.csv"
    if cache_path.exists():
        return pd.read_csv(cache_path)

    LOGGER.info("Building holdout factor metrics for improvement selection")
    holdout_fold = FoldSpec(
        fold_id="holdout",
        train_start=bundle.holdout.train_start,
        train_end=bundle.holdout.train_end,
        validation_start=bundle.holdout.validation_start,
        validation_end=bundle.holdout.validation_end,
        test_start=bundle.holdout.start,
        test_end=bundle.holdout.end,
    )
    frames: list[pd.DataFrame] = []
    for factor in bundle.candidate_factors:
        series = read_series_parquet(bundle.processed_factor_paths[factor])
        frames.append(compute_fold_metrics_for_factor(factor, series, forward_return, [holdout_fold]))
    holdout_metric_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    holdout_metric_df.to_csv(cache_path, index=False)
    return holdout_metric_df


def resolve_selection_plan(
    selection_mode: str,
    bundle: BaselineBundle,
    forward_return: pd.Series,
    stability_scores: pd.DataFrame,
    run_dir: Path,
) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    base_mode = selection_mode.replace("_fastslow", "")
    direction_map = build_direction_map(bundle.factor_selection_decisions)

    if base_mode == "baseline":
        selected = bundle.selected_by_fold.copy()
        if bundle.holdout is not None:
            holdout_metric_df = build_holdout_metric_df(bundle, forward_return, run_dir)
            if not holdout_metric_df.empty:
                holdout_fold = FoldSpec(
                    fold_id="holdout",
                    train_start=bundle.holdout.train_start,
                    train_end=bundle.holdout.train_end,
                    validation_start=bundle.holdout.validation_start,
                    validation_end=bundle.holdout.validation_end,
                    test_start=bundle.holdout.start,
                    test_end=bundle.holdout.end,
                )
                holdout_selected, _, _ = select_core_factors_for_fold(
                    fold=holdout_fold,
                    candidate_summary=holdout_metric_df,
                    processed_factor_paths=bundle.processed_factor_paths,
                    forward_return=forward_return,
                )
                if not holdout_selected.empty:
                    selected = pd.concat([selected, holdout_selected], ignore_index=True)
                    direction_map["holdout"] = {
                        str(row["factor"]): int(row["train_direction"])
                        for _, row in holdout_metric_df.iterrows()
                    }
        return selected, direction_map

    if base_mode == "stability_score":
        selected_frames: list[pd.DataFrame] = []
        for fold in bundle.folds:
            fold_rows = bundle.factor_selection_decisions[
                bundle.factor_selection_decisions["fold_id"] == fold.fold_id
            ].copy()
            ranked_pool = filter_stability_pool_for_fold(fold_rows, stability_scores, top_n=STABILITY_TOP_N)
            fold_selected, _ = select_ranked_factor_pool_for_fold(
                fold=fold,
                ranked_pool=ranked_pool,
                processed_factor_paths=bundle.processed_factor_paths,
                forward_return=forward_return,
            )
            if not fold_selected.empty:
                selected_frames.append(fold_selected)
        if bundle.holdout is not None:
            holdout_metric_df = build_holdout_metric_df(bundle, forward_return, run_dir)
            if not holdout_metric_df.empty:
                holdout_fold = FoldSpec(
                    fold_id="holdout",
                    train_start=bundle.holdout.train_start,
                    train_end=bundle.holdout.train_end,
                    validation_start=bundle.holdout.validation_start,
                    validation_end=bundle.holdout.validation_end,
                    test_start=bundle.holdout.start,
                    test_end=bundle.holdout.end,
                )
                ranked_pool = filter_stability_pool_for_fold(holdout_metric_df, stability_scores, top_n=STABILITY_TOP_N)
                holdout_selected, _ = select_ranked_factor_pool_for_fold(
                    fold=holdout_fold,
                    ranked_pool=ranked_pool,
                    processed_factor_paths=bundle.processed_factor_paths,
                    forward_return=forward_return,
                )
                if not holdout_selected.empty:
                    selected_frames.append(holdout_selected)
                    direction_map["holdout"] = {
                        str(row["factor"]): int(row["train_direction"])
                        for _, row in holdout_metric_df.iterrows()
                    }
        selected = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
        return selected, direction_map

    raise ValueError(f"Unsupported selection mode: {selection_mode}")


def build_daily_composite_scores(
    date: pd.Timestamp,
    factor_series_map: dict[str, pd.Series],
    factor_weights: pd.Series,
) -> pd.Series:
    slices: list[pd.Series] = []
    for factor, weight in factor_weights.items():
        try:
            factor_slice = factor_series_map[factor].xs(date, level="datetime", drop_level=False)
        except KeyError:
            continue
        slices.append(factor_slice.droplevel("datetime").rename(factor) * float(weight))
    if not slices:
        return pd.Series(dtype=float)
    return pd.concat(slices, axis=1).sum(axis=1).dropna().astype(float)


def apply_eligibility_filter(
    scores: pd.Series,
    date: pd.Timestamp,
    context: SupportContext,
) -> pd.Series:
    if scores.empty:
        return scores
    current_pos = context.trade_pos_by_date.get(pd.Timestamp(date))
    if current_pos is None:
        return pd.Series(dtype=float)
    eligible_codes: list[str] = []
    for code in scores.index:
        if code not in context.stock_basic_map.index:
            continue
        ref = context.stock_basic_map.loc[code]
        list_idx = int(ref.get("list_idx", 0))
        if current_pos - list_idx + 1 < LISTED_MIN_TRADING_DAYS:
            continue
        delist_date = ref.get("delist_date")
        if pd.notna(delist_date) and pd.Timestamp(date) > delist_date:
            continue
        if is_st_on_date(code, pd.Timestamp(date), context.st_ranges):
            continue
        eligible_codes.append(code)
    return scores.reindex(eligible_codes).dropna()


def build_one_sleeve_snapshot(
    *,
    date: pd.Timestamp,
    factors: list[str],
    factor_series_map: dict[str, pd.Series],
    factor_weights: pd.Series,
    context: SupportContext,
    scenario: LiquidityScenario,
    topk: int,
    capital: float,
    weighting_mode: str,
) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    if not factors:
        return pd.Series(dtype=float), pd.Series(dtype=float), {
            "date": date,
            "n_scored": 0,
            "n_selected": 0,
            "detail": "No factors in this sleeve.",
        }

    daily_scores = build_daily_composite_scores(date, factor_series_map, factor_weights.reindex(factors).dropna())
    daily_scores = apply_eligibility_filter(daily_scores, date, context)
    if daily_scores.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float), {
            "date": date,
            "n_scored": 0,
            "n_selected": 0,
            "detail": "No stock survived eligibility filters.",
        }

    adv_slice = context.aux_df["adv20_median_rmb"].xs(date, level="datetime").reindex(daily_scores.index)
    selected_scores = apply_liquidity_rules(
        daily_scores,
        adv_slice,
        topk=topk,
        target_value=float(capital) / max(int(topk), 1),
        scenario=scenario,
    )
    if selected_scores.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float), {
            "date": date,
            "n_scored": int(len(daily_scores)),
            "n_selected": 0,
            "detail": "No stock survived the liquidity screen.",
        }

    weights = build_stock_weights(selected_scores, weighting_mode)
    return weights, selected_scores, {
        "date": date,
        "n_scored": int(len(daily_scores)),
        "n_selected": int(len(selected_scores)),
        "detail": "ok",
    }


def blend_weight_maps(
    fast_weights: pd.Series,
    slow_weights: pd.Series,
    *,
    fast_scale: float = FAST_BLEND_WEIGHT,
    slow_scale: float = SLOW_BLEND_WEIGHT,
) -> pd.Series:
    if fast_weights.empty and slow_weights.empty:
        return pd.Series(dtype=float)
    if fast_weights.empty:
        return normalize_weight_series(slow_weights)
    if slow_weights.empty:
        return normalize_weight_series(fast_weights)
    combined = fast_weights.mul(fast_scale, fill_value=0.0).add(
        slow_weights.mul(slow_scale, fill_value=0.0),
        fill_value=0.0,
    )
    return normalize_weight_series(combined)


def build_signal_schedule_variant(
    *,
    start: str,
    end: str,
    selected_factors: list[str],
    factor_directions: dict[str, int],
    processed_factor_paths: dict[str, Path],
    context: SupportContext,
    spec: VariantSpec,
    scenario: LiquidityScenario,
    capital: float,
) -> tuple[dict[pd.Timestamp, dict[str, float]], pd.DataFrame, pd.DataFrame]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    period_calendar = [date for date in context.trade_calendar if start_ts <= date <= end_ts]
    if not period_calendar or not selected_factors:
        return {}, pd.DataFrame(), pd.DataFrame()

    factor_series_map: dict[str, pd.Series] = {}
    for factor in selected_factors:
        series = slice_window(read_series_parquet(processed_factor_paths[factor]), start, end)
        direction = factor_directions.get(factor, 1)
        factor_series_map[factor] = cs_rank(series * float(direction)).astype(np.float32)

    use_family_caps = spec.stage in {"C", "D"}
    if spec.selection_mode.endswith("fastslow"):
        fast_factors = [
            factor
            for factor in selected_factors
            if float(context.factor_best_decay.get(factor, np.nan) or np.nan) <= 20.0
        ]
        slow_factors = [factor for factor in selected_factors if factor not in fast_factors]
        if not fast_factors:
            fast_factors = list(selected_factors)
            slow_factors = []
    else:
        fast_factors = list(selected_factors)
        slow_factors = []

    fast_weights = build_factor_weight_map(fast_factors, context.factor_category, use_family_caps=use_family_caps)
    slow_weights = build_factor_weight_map(slow_factors, context.factor_category, use_family_caps=use_family_caps)

    fast_rebalance_dates = set(build_rebalance_dates(period_calendar, spec.rebalance_days))
    slow_days = int(spec.slow_rebalance_days or spec.rebalance_days)
    slow_rebalance_dates = set(build_rebalance_dates(period_calendar, slow_days)) if slow_factors else set()
    combined_rebalance_dates = sorted(fast_rebalance_dates | slow_rebalance_dates)

    schedule: dict[pd.Timestamp, dict[str, float]] = {}
    signal_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    current_fast_weights = pd.Series(dtype=float)
    current_fast_scores = pd.Series(dtype=float)
    current_slow_weights = pd.Series(dtype=float)
    current_slow_scores = pd.Series(dtype=float)

    for date in combined_rebalance_dates:
        fast_detail = "skipped"
        slow_detail = "skipped"
        fast_capital = capital if not slow_factors else capital * FAST_BLEND_WEIGHT
        slow_capital = capital * SLOW_BLEND_WEIGHT
        if date in fast_rebalance_dates:
            current_fast_weights, current_fast_scores, fast_diag = build_one_sleeve_snapshot(
                date=date,
                factors=fast_factors,
                factor_series_map=factor_series_map,
                factor_weights=fast_weights,
                context=context,
                scenario=scenario,
                topk=spec.topk,
                capital=fast_capital,
                weighting_mode=spec.portfolio_weighting,
            )
            fast_detail = str(fast_diag["detail"])
        if slow_factors and date in slow_rebalance_dates:
            current_slow_weights, current_slow_scores, slow_diag = build_one_sleeve_snapshot(
                date=date,
                factors=slow_factors,
                factor_series_map=factor_series_map,
                factor_weights=slow_weights,
                context=context,
                scenario=scenario,
                topk=spec.topk,
                capital=slow_capital,
                weighting_mode=spec.portfolio_weighting,
            )
            slow_detail = str(slow_diag["detail"])

        combined_weights = blend_weight_maps(current_fast_weights, current_slow_weights)
        if combined_weights.empty:
            diagnostic_rows.append(
                {
                    "date": date,
                    "n_scored": int(current_fast_scores.size + current_slow_scores.size),
                    "n_selected": 0,
                    "scenario": scenario.name,
                    "detail": f"fast={fast_detail}; slow={slow_detail}",
                    "weighting_mode": spec.portfolio_weighting,
                    "selection_mode": spec.selection_mode,
                }
            )
            continue

        combined_scores = (
            current_fast_scores.mul(FAST_BLEND_WEIGHT, fill_value=0.0).add(
                current_slow_scores.mul(SLOW_BLEND_WEIGHT, fill_value=0.0),
                fill_value=0.0,
            )
            if slow_factors
            else current_fast_scores.copy()
        )
        combined_scores = combined_scores.reindex(combined_weights.index).fillna(0.0)
        schedule[date] = {qlib_to_ts_code(code): float(weight) for code, weight in combined_weights.items()}
        diagnostic_rows.append(
            {
                "date": date,
                "n_scored": int(current_fast_scores.size + current_slow_scores.size),
                "n_selected": int(combined_weights.size),
                "scenario": scenario.name,
                "detail": f"fast={fast_detail}; slow={slow_detail}",
                "weighting_mode": spec.portfolio_weighting,
                "selection_mode": spec.selection_mode,
            }
        )
        for code, weight in combined_weights.items():
            signal_rows.append(
                {
                    "date": date,
                    "instrument": qlib_to_ts_code(code),
                    "score": float(combined_scores.get(code, np.nan)),
                    "target_weight": float(weight),
                    "scenario": scenario.name,
                    "selection_mode": spec.selection_mode,
                    "weighting_mode": spec.portfolio_weighting,
                }
            )

    return schedule, pd.DataFrame(signal_rows), pd.DataFrame(diagnostic_rows)


def build_stage_a_specs(args: argparse.Namespace) -> list[VariantSpec]:
    specs: list[VariantSpec] = []
    for topk in [50, 80, 100]:
        for rebalance_days in [5, 10]:
            for liquidity_scenario in [
                "no_filter",
                "adv_floor_only",
                "adv_floor_plus_participation",
                "bottom_20pct_filter",
            ]:
                for slippage_rate in [0.0005, 0.0010]:
                    variant_id = (
                        f"A_topk{topk}_reb{rebalance_days}_{liquidity_scenario}_slip{slippage_rate:.4f}"
                    )
                    specs.append(
                        VariantSpec(
                            stage="A",
                            variant_id=variant_id,
                            description="Baseline factor set with parameter sensitivity only.",
                            benchmark=args.benchmark,
                            universe_mode=args.universe_mode,
                            selection_mode="baseline",
                            portfolio_weighting="equal",
                            topk=topk,
                            rebalance_days=rebalance_days,
                            slow_rebalance_days=args.slow_rebalance_days,
                            liquidity_scenario=liquidity_scenario,
                            slippage_rate=slippage_rate,
                        )
                    )
    return specs


def build_stage_b_specs(best_a: VariantSpec, args: argparse.Namespace) -> list[VariantSpec]:
    return [
        VariantSpec(
            stage="B",
            variant_id="B_P1_equal_top50",
            description="Equal-weight top50 portfolio.",
            benchmark=args.benchmark,
            universe_mode=args.universe_mode,
            selection_mode="baseline",
            portfolio_weighting="equal",
            topk=50,
            rebalance_days=best_a.rebalance_days,
            slow_rebalance_days=args.slow_rebalance_days,
            liquidity_scenario=best_a.liquidity_scenario,
            slippage_rate=best_a.slippage_rate,
        ),
        VariantSpec(
            stage="B",
            variant_id="B_P2_tiered_top80",
            description="Tiered top80 portfolio weights.",
            benchmark=args.benchmark,
            universe_mode=args.universe_mode,
            selection_mode="baseline",
            portfolio_weighting="tiered",
            topk=80,
            rebalance_days=best_a.rebalance_days,
            slow_rebalance_days=args.slow_rebalance_days,
            liquidity_scenario=best_a.liquidity_scenario,
            slippage_rate=best_a.slippage_rate,
        ),
        VariantSpec(
            stage="B",
            variant_id="B_P3_scoreprop_top80",
            description="Score-proportional top80 portfolio weights.",
            benchmark=args.benchmark,
            universe_mode=args.universe_mode,
            selection_mode="baseline",
            portfolio_weighting="score_proportional",
            topk=80,
            rebalance_days=best_a.rebalance_days,
            slow_rebalance_days=args.slow_rebalance_days,
            liquidity_scenario=best_a.liquidity_scenario,
            slippage_rate=best_a.slippage_rate,
        ),
    ]


def build_stage_c_specs(best_b: VariantSpec, args: argparse.Namespace) -> list[VariantSpec]:
    return [
        VariantSpec(
            stage="C",
            variant_id="C_stability_score",
            description="Stability-score factor selection with family caps.",
            benchmark=args.benchmark,
            universe_mode=args.universe_mode,
            selection_mode="stability_score",
            portfolio_weighting=best_b.portfolio_weighting,
            topk=best_b.topk,
            rebalance_days=best_b.rebalance_days,
            slow_rebalance_days=args.slow_rebalance_days,
            liquidity_scenario=best_b.liquidity_scenario,
            slippage_rate=best_b.slippage_rate,
        ),
        VariantSpec(
            stage="C",
            variant_id="C_stability_fastslow",
            description="Stability-score selection plus fast/slow sleeves.",
            benchmark=args.benchmark,
            universe_mode=args.universe_mode,
            selection_mode="stability_score_fastslow",
            portfolio_weighting=best_b.portfolio_weighting,
            topk=best_b.topk,
            rebalance_days=best_b.rebalance_days,
            slow_rebalance_days=args.slow_rebalance_days,
            liquidity_scenario=best_b.liquidity_scenario,
            slippage_rate=best_b.slippage_rate,
        ),
    ]


def passes_variant_gate(summary_row: dict[str, Any]) -> tuple[bool, str]:
    failures: list[str] = []
    if float(summary_row.get("stitched_relative_excess_return", np.nan) or np.nan) < 0.10:
        failures.append("stitched relative excess return < +10%")
    if int(summary_row.get("positive_excess_folds", 0) or 0) < 5:
        failures.append("positive-excess test folds < 5")
    if float(summary_row.get("holdout_relative_excess_return", np.nan) or np.nan) < 0.0:
        failures.append("holdout relative excess return < 0")
    if float(summary_row.get("worst_max_drawdown", np.nan) or np.nan) < -0.30:
        failures.append("worst-fold max drawdown < -30%")
    return (len(failures) == 0, "ok" if not failures else "; ".join(failures))


def summarize_variant_suite(spec: VariantSpec, oos_df: pd.DataFrame) -> dict[str, Any]:
    test_df = oos_df[oos_df["window_type"] == "test"].copy()
    holdout_df = oos_df[oos_df["window_type"] == "holdout"].copy()
    stitched_return = compound_column(test_df, "cumulative_return")
    stitched_benchmark = compound_column(test_df, "benchmark_total_return")
    stitched_relative_excess = relative_excess_return(stitched_return, stitched_benchmark)
    test_df["relative_excess_return"] = test_df.apply(
        lambda row: relative_excess_return(row["cumulative_return"], row["benchmark_total_return"]),
        axis=1,
    )
    holdout_relative_excess = (
        relative_excess_return(
            float(holdout_df.iloc[0]["cumulative_return"]),
            float(holdout_df.iloc[0]["benchmark_total_return"]),
        )
        if not holdout_df.empty
        else float("nan")
    )
    summary = {
        "stage": spec.stage,
        "variant_id": spec.variant_id,
        "description": spec.description,
        "benchmark": spec.benchmark,
        "selection_mode": spec.selection_mode,
        "portfolio_weighting": spec.portfolio_weighting,
        "universe_mode": spec.universe_mode,
        "topk": spec.topk,
        "rebalance_days": spec.rebalance_days,
        "slow_rebalance_days": spec.slow_rebalance_days,
        "liquidity_scenario": spec.liquidity_scenario,
        "slippage_rate": spec.slippage_rate,
        "stitched_total_return": stitched_return,
        "stitched_benchmark_total_return": stitched_benchmark,
        "stitched_relative_excess_return": stitched_relative_excess,
        "positive_excess_folds": int((test_df["relative_excess_return"] > 0).sum()),
        "test_fold_count": int(len(test_df)),
        "holdout_relative_excess_return": holdout_relative_excess,
        "worst_max_drawdown": float(test_df["max_drawdown"].min()) if not test_df.empty else np.nan,
        "avg_turnover": float(test_df["turnover_mean"].mean()) if not test_df.empty else np.nan,
        "avg_blocked_order_ratio": float(test_df["blocked_order_ratio"].mean()) if not test_df.empty else np.nan,
        "avg_holding_cash_ratio": float(test_df["holding_cash_ratio"].mean()) if not test_df.empty else np.nan,
    }
    promoted, reason = passes_variant_gate(summary)
    summary["promoted"] = promoted
    summary["gate_reason"] = reason
    return summary


def sort_variant_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return summary_df
    base = summary_df.drop(columns=["rank"], errors="ignore")
    ranked = base.sort_values(
        [
            "stage",
            "promoted",
            "stitched_relative_excess_return",
            "positive_excess_folds",
            "holdout_relative_excess_return",
            "worst_max_drawdown",
            "avg_turnover",
            "avg_blocked_order_ratio",
            "avg_holding_cash_ratio",
            "variant_id",
        ],
        ascending=[True, False, False, False, False, False, True, True, True, True],
    ).reset_index(drop=True)
    ranked.insert(0, "rank", np.arange(1, len(ranked) + 1))
    return ranked


def choose_stage_winner(summary_df: pd.DataFrame, stage: str) -> VariantSpec:
    stage_rows = sort_variant_summary(summary_df[summary_df["stage"] == stage].copy())
    if stage_rows.empty:
        raise ValueError(f"No variants were evaluated for stage {stage}.")
    row = stage_rows.iloc[0].to_dict()
    return VariantSpec(
        stage=str(row["stage"]),
        variant_id=str(row["variant_id"]),
        description=str(row["description"]),
        benchmark=str(row["benchmark"]),
        universe_mode=str(row["universe_mode"]),
        selection_mode=str(row["selection_mode"]),
        portfolio_weighting=str(row["portfolio_weighting"]),
        topk=int(row["topk"]),
        rebalance_days=int(row["rebalance_days"]),
        slow_rebalance_days=int(row["slow_rebalance_days"]) if pd.notna(row["slow_rebalance_days"]) else None,
        liquidity_scenario=str(row["liquidity_scenario"]),
        slippage_rate=float(row["slippage_rate"]),
    )


def evaluate_variant(
    *,
    spec: VariantSpec,
    bundle: BaselineBundle,
    context: SupportContext,
    forward_return: pd.Series,
    stability_scores: pd.DataFrame,
    liquidity_scenarios: dict[str, LiquidityScenario],
    run_dir: Path,
    keep_detail: bool = False,
) -> VariantArtifacts:
    LOGGER.info(
        "Evaluating %s [%s] - selection=%s, weighting=%s, topk=%d, rebalance=%d, liquidity=%s, slippage=%.4f",
        spec.variant_id,
        spec.stage,
        spec.selection_mode,
        spec.portfolio_weighting,
        spec.topk,
        spec.rebalance_days,
        spec.liquidity_scenario,
        spec.slippage_rate,
    )
    scenario = liquidity_scenarios[spec.liquidity_scenario]
    selected_by_fold, direction_map = resolve_selection_plan(
        spec.selection_mode,
        bundle,
        forward_return,
        stability_scores,
        run_dir,
    )

    oos_rows: list[dict[str, Any]] = []
    signal_frames: list[pd.DataFrame] = []
    signal_diag_frames: list[pd.DataFrame] = []
    report_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    order_log_frames: list[pd.DataFrame] = []

    test_specs: list[tuple[str, str, str]] = [
        (fold.fold_id, fold.test_start, fold.test_end)
        for fold in bundle.folds
    ]
    if bundle.holdout is not None:
        test_specs.append(("holdout", bundle.holdout.start, bundle.holdout.end))

    from workspace.research.alpha_mining.event_driven_strategy_research import summarize_backtest_result

    for fold_id, start, end in test_specs:
        fold_factors = selected_by_fold.loc[selected_by_fold["fold_id"] == fold_id, "factor"].tolist()
        if not fold_factors:
            LOGGER.warning("%s produced no factors for %s", spec.variant_id, fold_id)
            continue
        schedule, signal_df, diag_df = build_signal_schedule_variant(
            start=start,
            end=end,
            selected_factors=fold_factors,
            factor_directions=direction_map.get(fold_id, {}),
            processed_factor_paths=bundle.processed_factor_paths,
            context=context,
            spec=spec,
            scenario=scenario,
            capital=float(bundle.run_metadata.get("capital", 2_000_000.0)),
        )
        if not schedule:
            LOGGER.warning("%s produced no tradable schedule for %s", spec.variant_id, fold_id)
            continue

        signal_frames.append(signal_df.assign(fold_id=fold_id, variant_id=spec.variant_id))
        signal_diag_frames.append(diag_df.assign(fold_id=fold_id, variant_id=spec.variant_id))
        result = run_event_driven_window(
            schedule=schedule,
            start=start,
            end=end,
            benchmark=spec.benchmark,
            capital=float(bundle.run_metadata.get("capital", 2_000_000.0)),
            slippage_rate=float(spec.slippage_rate),
        )
        window_type = "holdout" if fold_id == "holdout" else "test"
        perf_row = summarize_backtest_result(
            result,
            scenario=spec.variant_id,
            window_type=window_type,
            fold_id=fold_id,
        )
        perf_row["stage"] = spec.stage
        perf_row["benchmark"] = spec.benchmark
        perf_row["selection_mode"] = spec.selection_mode
        perf_row["portfolio_weighting"] = spec.portfolio_weighting
        perf_row["liquidity_scenario"] = spec.liquidity_scenario
        perf_row["slippage_rate"] = spec.slippage_rate
        oos_rows.append(perf_row)

        if keep_detail:
            report_frames.append(concat_with_fold(result.report.reset_index(), fold_id))
            trade_frames.append(concat_with_fold(result.trades, fold_id))
            order_log_frames.append(concat_with_fold(result.order_log, fold_id))

    oos_df = pd.DataFrame(oos_rows)
    summary = summarize_variant_suite(spec, oos_df)
    return VariantArtifacts(
        spec=spec,
        summary=summary,
        oos_performance=oos_df,
        event_report=aggregate_result_frames(report_frames, sort_cols=["date", "fold_id"]),
        trades=aggregate_result_frames(trade_frames, sort_cols=["date", "fold_id"]),
        order_log=aggregate_result_frames(order_log_frames, sort_cols=["date", "fold_id"]),
        signal_df=aggregate_result_frames(signal_frames, sort_cols=["date", "fold_id", "instrument"]),
        signal_diagnostics=aggregate_result_frames(signal_diag_frames, sort_cols=["date", "fold_id"]),
        selected_by_fold=selected_by_fold.copy(),
    )


def build_year_regime_diagnostics(oos_df: pd.DataFrame, benchmark: str) -> pd.DataFrame:
    if oos_df.empty:
        return pd.DataFrame()
    work = oos_df.copy()
    work["relative_excess_return"] = work.apply(
        lambda row: relative_excess_return(row["cumulative_return"], row["benchmark_total_return"]),
        axis=1,
    )
    work["benchmark"] = benchmark
    return work[
        [
            "fold_id",
            "window_type",
            "benchmark",
            "cumulative_return",
            "benchmark_total_return",
            "relative_excess_return",
            "max_drawdown",
            "turnover_mean",
            "blocked_order_ratio",
            "holding_cash_ratio",
            "window_start",
            "window_end",
        ]
    ].sort_values(["window_type", "window_start", "fold_id"])


def build_portfolio_expression_diagnostics(signal_df: pd.DataFrame) -> pd.DataFrame:
    if signal_df.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for (fold_id, date), group in signal_df.groupby(["fold_id", "date"]):
        scores = group.set_index("instrument")["score"].astype(float)
        preview = build_weight_preview_row(scores)
        rows.append(
            {
                "fold_id": fold_id,
                "date": date,
                "n_selected": int(group["instrument"].nunique()),
                "score_range": float(scores.max() - scores.min()) if not scores.empty else np.nan,
                "score_std": float(scores.std()) if len(scores) > 1 else 0.0,
                **preview,
            }
        )
    diag = pd.DataFrame(rows)
    if diag.empty:
        return diag
    return (
        diag.groupby("fold_id")
        .agg(
            avg_selected=("n_selected", "mean"),
            avg_score_range=("score_range", "mean"),
            avg_score_std=("score_std", "mean"),
            equal_hhi=("equal_hhi", "mean"),
            tiered_hhi=("tiered_hhi", "mean"),
            score_prop_hhi=("score_prop_hhi", "mean"),
            equal_top10_share=("equal_top10_share", "mean"),
            tiered_top10_share=("tiered_top10_share", "mean"),
            score_prop_top10_share=("score_prop_top10_share", "mean"),
        )
        .reset_index()
        .sort_values("fold_id")
    )


def build_benchmark_relative_exposure(signal_df: pd.DataFrame, context: SupportContext, benchmark: str) -> pd.DataFrame:
    if signal_df.empty:
        return pd.DataFrame()
    work = signal_df.copy()
    work["qlib_code"] = work["instrument"].map(ts_to_qlib_code)
    work["date"] = pd.to_datetime(work["date"])

    aux_reset = context.aux_df.reset_index().rename(columns={"datetime": "date", "instrument": "qlib_code"})
    stock_meta = context.stock_basic[["qlib_code", "exchange_bucket"]].drop_duplicates()
    work = work.merge(aux_reset, on=["date", "qlib_code"], how="left")
    work = work.merge(stock_meta, on="qlib_code", how="left")

    rows: list[dict[str, Any]] = []
    for date, group in work.groupby("date"):
        weights = group["target_weight"].astype(float)
        market_cap = group["market_cap"].astype(float)
        adv20 = group["adv20_median_rmb"].astype(float)
        sh_weight = float(weights[group["exchange_bucket"] == "SH"].sum())
        sz_weight = float(weights[group["exchange_bucket"] == "SZ"].sum())

        market_slice = (
            context.aux_df.xs(pd.Timestamp(date), level="datetime", drop_level=False)
            .reset_index()
            .rename(columns={"instrument": "qlib_code"})
        )
        market_slice = market_slice.merge(stock_meta, on="qlib_code", how="left")
        rows.append(
            {
                "date": date,
                "benchmark": benchmark,
                "portfolio_sh_weight": sh_weight,
                "portfolio_sz_weight": sz_weight,
                "portfolio_avg_market_cap": float((weights * market_cap).sum()) if not group.empty else np.nan,
                "market_avg_market_cap": float(market_slice["market_cap"].mean()) if not market_slice.empty else np.nan,
                "portfolio_avg_adv20": float((weights * adv20).sum()) if not group.empty else np.nan,
                "market_avg_adv20": float(market_slice["adv20_median_rmb"].mean()) if not market_slice.empty else np.nan,
                "market_sh_share_by_count": float((market_slice["exchange_bucket"] == "SH").mean()) if not market_slice.empty else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("date")


def build_gap_attribution_markdown(
    *,
    benchmark_audit: BenchmarkAuditResult,
    benchmark_note: str,
    baseline_summary: dict[str, Any],
    year_diag: pd.DataFrame,
    expression_diag: pd.DataFrame,
    exposure_diag: pd.DataFrame,
    factor_mix: pd.DataFrame,
    slow_factor_diag: pd.DataFrame,
) -> str:
    exposure_summary = pd.DataFrame()
    if not exposure_diag.empty:
        exposure_summary = pd.DataFrame(
            [
                {
                    "avg_portfolio_sh_weight": exposure_diag["portfolio_sh_weight"].mean(),
                    "avg_portfolio_sz_weight": exposure_diag["portfolio_sz_weight"].mean(),
                    "avg_portfolio_market_cap": exposure_diag["portfolio_avg_market_cap"].mean(),
                    "avg_market_market_cap": exposure_diag["market_avg_market_cap"].mean(),
                    "avg_portfolio_adv20": exposure_diag["portfolio_avg_adv20"].mean(),
                    "avg_market_adv20": exposure_diag["market_avg_adv20"].mean(),
                    "avg_market_sh_share_by_count": exposure_diag["market_sh_share_by_count"].mean(),
                }
            ]
        )

    lines = [
        "# Strategy Gap Attribution",
        "",
        "## Benchmark Audit",
        f"- Benchmark: `{benchmark_audit.benchmark_code}`",
        f"- Audit passed: `{benchmark_audit.passed}`",
        f"- Covered dates: `{benchmark_audit.start_date}` to `{benchmark_audit.end_date}`",
        f"- Missing trade days vs calendar: `{benchmark_audit.missing_trade_days}`",
        f"- Duplicate trade_date rows: `{benchmark_audit.duplicate_trade_dates}`",
        "",
        "## Baseline B0 Summary",
        f"- Stitched total return: `{baseline_summary.get('stitched_total_return', np.nan):.2%}`",
        f"- Stitched benchmark total return: `{baseline_summary.get('stitched_benchmark_total_return', np.nan):.2%}`",
        f"- Stitched relative excess return: `{baseline_summary.get('stitched_relative_excess_return', np.nan):.2%}`",
        f"- Positive-excess test folds: `{int(baseline_summary.get('positive_excess_folds', 0))}` / `7`",
        f"- Holdout relative excess return: `{baseline_summary.get('holdout_relative_excess_return', np.nan):.2%}`",
        f"- Worst-fold max drawdown: `{baseline_summary.get('worst_max_drawdown', np.nan):.2%}`",
        f"- Turnover and blocked-order ratio are kept as diagnostics, not promotion gates.",
        "",
        "## Year / Regime Diagnostics",
        dataframe_to_markdown(
            year_diag,
            columns=[
                "fold_id",
                "window_type",
                "cumulative_return",
                "benchmark_total_return",
                "relative_excess_return",
                "max_drawdown",
                "turnover_mean",
                "blocked_order_ratio",
            ],
        ),
        "",
        "## Portfolio Expression Diagnostics",
        dataframe_to_markdown(
            expression_diag,
            columns=[
                "fold_id",
                "avg_selected",
                "avg_score_range",
                "equal_hhi",
                "tiered_hhi",
                "score_prop_hhi",
                "equal_top10_share",
                "tiered_top10_share",
                "score_prop_top10_share",
            ],
        ),
        "",
        "## Repeated Factor Mix",
        dataframe_to_markdown(
            factor_mix,
            columns=["factor", "category", "selected_folds", "mean_abs_val_icir"],
        ),
        "",
        "## Slow-Signal Mismatch Diagnostic",
        dataframe_to_markdown(
            slow_factor_diag,
            columns=["factor", "category", "best_decay_horizon", "selected_folds", "is_slow_signal"],
        ),
        "",
        "## Benchmark-Relative Exposure",
        dataframe_to_markdown(exposure_summary),
        f"\n- {benchmark_note}",
        "",
        "## Key Findings",
        "- Equal-weight `top50` holdings visibly flatten score differences. The expression diagnostics compare the same selected names under equal, tiered, and score-proportional weights so this effect is easy to review.",
        "- The core book is concentrated in a small set of liquidity / short-horizon reversal / volatility ideas, so many high-ICIR factors are overlapping instead of additive.",
        "- A visible share of repeatedly selected factors have `best_decay_horizon > 20`, which suggests a mismatch between slow signals and the current 5-day rebalance rhythm.",
        "- Execution friction is meaningful, but it is treated here as implementation context rather than a hard factor-quality gate.",
        "- Relative to the SSE Composite benchmark, the current all-market portfolio still carries a large SZ allocation and only a rough broad-style exposure match because local 000001.SH constituent weights are not available.",
        "",
    ]
    return "\n".join(lines)


def build_improvement_master_review(
    *,
    benchmark_audit: BenchmarkAuditResult,
    baseline_summary: dict[str, Any],
    variant_summary: pd.DataFrame,
    best_variant: VariantArtifacts,
) -> str:
    stage_a = variant_summary[variant_summary["stage"] == "A"].head(8)
    stage_b = variant_summary[variant_summary["stage"] == "B"].head(8)
    stage_c = variant_summary[variant_summary["stage"] == "C"].head(8)
    best_row = pd.DataFrame([best_variant.summary])

    lines = [
        "# Strategy Improvement Master Review",
        "",
        "## Benchmark Setup",
        f"- Formal benchmark is now `{benchmark_audit.benchmark_code}`.",
        f"- Benchmark audit passed: `{benchmark_audit.passed}`",
        "",
        "## Baseline B0 vs New Benchmark",
        dataframe_to_markdown(pd.DataFrame([baseline_summary])),
        "",
        "## Stage A: Parameter Sensitivity",
        dataframe_to_markdown(
            stage_a,
            columns=[
                "rank",
                "variant_id",
                "stitched_relative_excess_return",
                "positive_excess_folds",
                "holdout_relative_excess_return",
                "worst_max_drawdown",
                "avg_turnover",
                "avg_blocked_order_ratio",
                "promoted",
            ],
        ),
        "",
        "## Stage B: Portfolio Expression",
        dataframe_to_markdown(
            stage_b,
            columns=[
                "rank",
                "variant_id",
                "portfolio_weighting",
                "topk",
                "stitched_relative_excess_return",
                "holdout_relative_excess_return",
                "worst_max_drawdown",
                "promoted",
            ],
        ),
        "",
        "## Stage C: Selection / Tempo Upgrade",
        dataframe_to_markdown(
            stage_c,
            columns=[
                "rank",
                "variant_id",
                "selection_mode",
                "stitched_relative_excess_return",
                "positive_excess_folds",
                "holdout_relative_excess_return",
                "worst_max_drawdown",
                "avg_turnover",
                "avg_blocked_order_ratio",
                "promoted",
                "gate_reason",
            ],
        ),
        "",
        "## Best Variant",
        dataframe_to_markdown(
            best_row,
            columns=[
                "variant_id",
                "stage",
                "selection_mode",
                "portfolio_weighting",
                "topk",
                "rebalance_days",
                "slow_rebalance_days",
                "liquidity_scenario",
                "slippage_rate",
                "stitched_relative_excess_return",
                "positive_excess_folds",
                "holdout_relative_excess_return",
                "worst_max_drawdown",
                "avg_turnover",
                "avg_blocked_order_ratio",
                "promoted",
                "gate_reason",
            ],
        ),
        "",
        "## Interpretation",
        "- Turnover and blocked-order ratio remain in the report because they matter for implementation style, but they are not promotion gates anymore.",
        "- A candidate still needs to beat the SSE Composite on stitched OOS relative return, breadth across folds, holdout behavior, and worst-fold drawdown to count as a true upgrade.",
        "",
    ]
    return "\n".join(lines)


def build_factor_mix_table(bundle: BaselineBundle) -> pd.DataFrame:
    if bundle.selected_by_fold.empty:
        return pd.DataFrame()
    category_map = bundle.factor_research_metrics.set_index("factor")["category"].to_dict()
    val_icir_map = bundle.factor_selection_decisions.groupby("factor")["val_rank_icir"].apply(lambda x: x.abs().mean()).to_dict()
    mix = (
        bundle.selected_by_fold.groupby("factor")
        .agg(selected_folds=("fold_id", "nunique"))
        .reset_index()
    )
    mix["category"] = mix["factor"].map(category_map)
    mix["mean_abs_val_icir"] = mix["factor"].map(val_icir_map)
    return mix.sort_values(["selected_folds", "mean_abs_val_icir", "factor"], ascending=[False, False, True]).head(12)


def build_slow_factor_diag(bundle: BaselineBundle) -> pd.DataFrame:
    selected_freq = (
        bundle.selected_by_fold.groupby("factor")
        .agg(selected_folds=("fold_id", "nunique"))
        .reset_index()
    )
    diag = bundle.factor_research_metrics[["factor", "category", "best_decay_horizon"]].merge(
        selected_freq,
        on="factor",
        how="left",
    )
    diag["selected_folds"] = diag["selected_folds"].fillna(0).astype(int)
    diag["is_slow_signal"] = diag["best_decay_horizon"].fillna(0).astype(float) > 20.0
    return diag.sort_values(["selected_folds", "best_decay_horizon", "factor"], ascending=[False, False, True]).head(12)


def persist_best_variant(best_variant: VariantArtifacts, run_dir: Path) -> None:
    best_variant.oos_performance.to_csv(run_dir / "best_variant_oos_fold_performance.csv", index=False)
    best_variant.signal_df.to_parquet(run_dir / "best_variant_signal.parquet", index=False)
    best_variant.signal_diagnostics.to_csv(run_dir / "best_variant_signal_diagnostics.csv", index=False)
    if not best_variant.event_report.empty:
        best_variant.event_report.to_csv(run_dir / "best_variant_event_driven_report.csv", index=False)
    if not best_variant.trades.empty:
        best_variant.trades.to_csv(run_dir / "best_variant_event_driven_trades.csv", index=False)
    if not best_variant.order_log.empty:
        best_variant.order_log.to_csv(run_dir / "best_variant_event_driven_order_log.csv", index=False)

    if not best_variant.event_report.empty:
        report_indexed = best_variant.event_report.set_index("date").sort_index()
        strategy_returns = report_indexed["return"].astype(float)
        benchmark_returns = report_indexed["bench"].astype(float) if "bench" in report_indexed.columns else None
        build_backtest_html(
            run_dir / "best_variant_backtest_report.html",
            strategy_returns=strategy_returns,
            benchmark_returns=benchmark_returns,
            name=f"Best Variant {best_variant.spec.variant_id}",
        )
    else:
        write_text(
            run_dir / "best_variant_backtest_report.html",
            "<html><body><p>No detailed report was generated.</p></body></html>",
        )


def run_improvement_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    baseline_run_dir = Path(args.baseline_run_dir).resolve()
    run_dir = resolve_output_dir(args)
    configure_logging(run_dir)
    LOGGER.info("Starting strategy improvement pipeline")
    LOGGER.info("Baseline run dir: %s", baseline_run_dir)

    bundle = load_baseline_bundle(baseline_run_dir, max_folds=args.max_folds)
    benchmark_audit = run_audit(args.benchmark, run_dir)
    forward_return = load_forward_return_series(bundle, run_dir)
    context = load_support_context(bundle, run_dir)
    stability_scores = compute_stability_scores(bundle.factor_selection_decisions)
    liquidity_scenarios = build_liquidity_scenario_map(args)

    b0_spec = VariantSpec(
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
    baseline_artifacts = evaluate_variant(
        spec=b0_spec,
        bundle=bundle,
        context=context,
        forward_return=forward_return,
        stability_scores=stability_scores,
        liquidity_scenarios=liquidity_scenarios,
        run_dir=run_dir,
        keep_detail=True,
    )

    year_diag = build_year_regime_diagnostics(baseline_artifacts.oos_performance, args.benchmark)
    expression_diag = build_portfolio_expression_diagnostics(baseline_artifacts.signal_df)
    exposure_diag = build_benchmark_relative_exposure(baseline_artifacts.signal_df, context, args.benchmark)
    factor_mix = build_factor_mix_table(bundle)
    slow_factor_diag = build_slow_factor_diag(bundle)
    benchmark_note = (
        "Local monthly index_weights snapshots currently cover CSI families but do not provide a direct "
        "000001.SH constituent-weight history, so this exposure file is a broad style / exchange diagnostic "
        "instead of an exact constituent-level attribution."
    )
    write_text(
        run_dir / "strategy_gap_attribution.md",
        build_gap_attribution_markdown(
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

    stage_a_specs = build_stage_a_specs(args)
    stage_rows: list[dict[str, Any]] = []
    for spec in stage_a_specs:
        artifacts = evaluate_variant(
            spec=spec,
            bundle=bundle,
            context=context,
            forward_return=forward_return,
            stability_scores=stability_scores,
            liquidity_scenarios=liquidity_scenarios,
            run_dir=run_dir,
            keep_detail=False,
        )
        stage_rows.append(artifacts.summary)
    stage_summary_df = sort_variant_summary(pd.DataFrame(stage_rows))

    best_a = choose_stage_winner(stage_summary_df, "A")
    stage_b_rows: list[dict[str, Any]] = []
    for spec in build_stage_b_specs(best_a, args):
        artifacts = evaluate_variant(
            spec=spec,
            bundle=bundle,
            context=context,
            forward_return=forward_return,
            stability_scores=stability_scores,
            liquidity_scenarios=liquidity_scenarios,
            run_dir=run_dir,
            keep_detail=False,
        )
        stage_b_rows.append(artifacts.summary)
    stage_summary_df = sort_variant_summary(pd.concat([stage_summary_df, pd.DataFrame(stage_b_rows)], ignore_index=True))

    best_b = choose_stage_winner(stage_summary_df, "B")
    stage_c_rows: list[dict[str, Any]] = []
    for spec in build_stage_c_specs(best_b, args):
        artifacts = evaluate_variant(
            spec=spec,
            bundle=bundle,
            context=context,
            forward_return=forward_return,
            stability_scores=stability_scores,
            liquidity_scenarios=liquidity_scenarios,
            run_dir=run_dir,
            keep_detail=False,
        )
        stage_c_rows.append(artifacts.summary)
    stage_summary_df = sort_variant_summary(pd.concat([stage_summary_df, pd.DataFrame(stage_c_rows)], ignore_index=True))

    best_c = choose_stage_winner(stage_summary_df, "C")
    best_variant = evaluate_variant(
        spec=VariantSpec(stage="D", **{k: v for k, v in asdict(best_c).items() if k != "stage"}),
        bundle=bundle,
        context=context,
        forward_return=forward_return,
        stability_scores=stability_scores,
        liquidity_scenarios=liquidity_scenarios,
        run_dir=run_dir,
        keep_detail=True,
    )

    persist_best_variant(best_variant, run_dir)

    experiment_grid = stage_summary_df.copy()
    experiment_grid.to_csv(run_dir / "improvement_experiment_grid.csv", index=False)
    variant_summary = sort_variant_summary(
        pd.concat([stage_summary_df, pd.DataFrame([best_variant.summary])], ignore_index=True)
        .drop_duplicates(subset=["variant_id"], keep="last")
    )
    variant_summary.to_csv(run_dir / "variant_comparison_summary.csv", index=False)

    master_review = build_improvement_master_review(
        benchmark_audit=benchmark_audit,
        baseline_summary=baseline_artifacts.summary,
        variant_summary=variant_summary,
        best_variant=best_variant,
    )
    write_text(run_dir / "improvement_master_review.md", master_review)

    run_metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline_run_dir": str(baseline_run_dir),
        "screening_run_dir": str(bundle.screening_run_dir),
        "benchmark": args.benchmark,
        "capital": args.capital,
        "default_topk": args.topk,
        "default_rebalance_days": args.rebalance_days,
        "slow_rebalance_days": args.slow_rebalance_days,
        "adv_median_floor": args.adv_median_floor,
        "participation_cap": args.participation_cap,
        "benchmark_audit": asdict(benchmark_audit),
        "baseline_summary": baseline_artifacts.summary,
        "best_stage_a": asdict(best_a),
        "best_stage_b": asdict(best_b),
        "best_stage_c": asdict(best_c),
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
    write_json(run_dir / "run_metadata.json", run_metadata)

    LOGGER.info("Strategy improvement pipeline complete: %s", run_dir)
    return {
        "run_dir": str(run_dir),
        "best_variant_id": best_variant.spec.variant_id,
        "best_variant_excess": best_variant.summary.get("stitched_relative_excess_return"),
    }


def main() -> None:
    from src.research_orchestrator.engine import _build_improvement_request_from_args, run_research

    args = parse_args()
    run_research(_build_improvement_request_from_args(args))


if __name__ == "__main__":
    main()
