"""
Secondary factor research and EventDrivenBacktester pipeline for alpha_mining.

This script turns the completed initial factor screening into a detailed,
auditable research run with cached intermediates and review-friendly outputs.
"""

from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import socket
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
import sys

sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_eval import (
    compute_factor_correlation,
    compute_ic_by_year,
    compute_ic_decay,
    compute_ic_series,
    compute_ic_summary,
    compute_marginal_ic,
    compute_quantile_returns,
    compute_quantile_summary,
    compute_long_short_returns,
    compute_rolling_ic,
    find_optimal_horizon,
    neutralize_industry,
    neutralize_size,
    neutralize_size_industry,
    test_monotonicity,
)
from src.alpha_research.walk_forward import (
    FoldSpec,
    HoldoutSpec,
    STEP_YEARS as WALK_FORWARD_STEP_YEARS,
    TEST_YEARS as WALK_FORWARD_TEST_YEARS,
    TRAIN_YEARS as WALK_FORWARD_TRAIN_YEARS,
    VALIDATION_YEARS as WALK_FORWARD_VALIDATION_YEARS,
    build_walk_forward_folds as shared_build_walk_forward_folds,
)
from src.alpha_research.factor_library.catalog import (
    get_category_map,
    get_composite_defs,
    get_factor_catalog,
)
from src.alpha_research.factor_library.operators import (
    ADJ_CLOSE,
    add_composites,
    compute_factors,
    cs_rank,
    cs_zscore,
    winsorize,
)
from src.alpha_research.mlflow_tracker import ExperimentTracker
from src.backtest_engine.event_driven import (
    BacktestContext,
    CostConfig,
    EventDrivenBacktester,
    Order,
    PctSlippage,
    Strategy,
)
from src.result_analysis.metrics import (
    calculate_cagr,
    calculate_max_drawdown,
    calculate_monthly_return_table,
    calculate_sharpe_ratio,
    calculate_total_return,
    calculate_yearly_returns,
    generate_performance_report,
)
from workspace.research.alpha_mining.event_driven_strategy_report import (
    render_factor_card,
    render_master_review,
    render_simple_backtest_html,
    write_text,
)

try:
    from src.result_analysis.report import BacktestReport
except Exception:  # pragma: no cover
    BacktestReport = None


LOGGER = logging.getLogger("alpha_mining.event_driven_strategy_research")
DEFAULT_PRELOAD_FIELDS = [
    "$open",
    "$close",
    "$high",
    "$low",
    "$vol",
    "$amount",
    "$pre_close",
    "$adj_factor",
]
SELECTION_CORR_THRESHOLD = 0.60
SELECTION_MIN_VALIDATION_ICIR = 0.15
SELECTION_MIN_MARGINAL_ICIR = 0.02
TRAIN_YEARS = WALK_FORWARD_TRAIN_YEARS
VALIDATION_YEARS = WALK_FORWARD_VALIDATION_YEARS
TEST_YEARS = WALK_FORWARD_TEST_YEARS
STEP_YEARS = WALK_FORWARD_STEP_YEARS
STRATEGY_HORIZON = 5
ROLLING_IC_WINDOW = 252
LISTED_MIN_TRADING_DAYS = 60
MIN_SELECTED_FACTORS = 6
MAX_SELECTED_FACTORS = 10


@dataclass(frozen=True)
class LiquidityScenario:
    name: str
    adv_floor: float | None
    participation_cap: float | None
    bottom_pct: float | None = None


class ScheduledLongOnlyStrategy(Strategy):
    """Trade a precomputed target-weight schedule in before_market_open."""

    def __init__(self, schedule: dict[pd.Timestamp, dict[str, float]]):
        super().__init__()
        self.schedule = schedule

    def initialize(self, context: BacktestContext) -> None:
        return None

    def before_market_open(self, context: BacktestContext) -> list[Order]:
        target_weights = self.schedule.get(pd.Timestamp(context.date))
        if not target_weights:
            return []

        prev_prices = {}
        if context.prev_day_data is not None and not context.prev_day_data.empty:
            prev_prices = (
                context.prev_day_data.set_index("ts_code")["close"].astype(float).to_dict()
            )

        portfolio_value = context.portfolio.total_value(prev_prices)
        if portfolio_value <= 0:
            portfolio_value = context.portfolio.cash

        orders: list[Order] = []
        current_positions = dict(context.portfolio.positions)
        current_codes = set(current_positions)
        target_codes = set(target_weights)

        for code in sorted(current_codes - target_codes):
            orders.append(Order(code=code, direction="sell", reason="rebalance_exit"))

        for code in sorted(current_codes & target_codes):
            pos = current_positions[code]
            ref_price = float(prev_prices.get(code, pos.avg_cost if pos.avg_cost > 0 else 0))
            if ref_price <= 0:
                continue
            current_value = pos.shares * ref_price
            target_value = portfolio_value * float(target_weights[code])
            diff_value = current_value - target_value
            lot_size = context.exchange.get_lot_size(code)
            shares_to_sell = int(max(diff_value, 0) / ref_price / lot_size) * lot_size
            if shares_to_sell > 0:
                orders.append(
                    Order(
                        code=code,
                        direction="sell",
                        target_shares=shares_to_sell,
                        reason="rebalance_trim",
                    )
                )

        for code in sorted(target_codes):
            pos = current_positions.get(code)
            ref_price = float(prev_prices.get(code, pos.avg_cost if pos else 0))
            current_value = 0.0 if pos is None or ref_price <= 0 else pos.shares * ref_price
            target_value = portfolio_value * float(target_weights[code])
            buy_value = max(target_value - current_value, 0.0)
            if buy_value > 1.0:
                orders.append(
                    Order(
                        code=code,
                        direction="buy",
                        target_value=buy_value,
                        reason="rebalance_buy",
                    )
                )
        return orders


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detailed alpha-mining factor research with EventDrivenBacktester"
    )
    parser.add_argument("--screening-run-dir", required=True, help="Completed screening run directory")
    parser.add_argument("--output-dir", default=None, help="Optional explicit output directory")
    parser.add_argument("--capital", type=float, default=2_000_000, help="Initial capital in RMB")
    parser.add_argument("--benchmark", default="000905.SH", help="Benchmark index code")
    parser.add_argument("--topk", type=int, default=50, help="Target number of holdings")
    parser.add_argument("--rebalance-days", type=int, default=5, help="Rebalance every N trading days")
    parser.add_argument("--adv-median-floor", type=float, default=5_000_000, help="20d median turnover floor in RMB")
    parser.add_argument("--participation-cap", type=float, default=0.02, help="Max target-value / 20d median turnover")
    parser.add_argument("--max-factors", type=int, default=None, help="Optional debug cap for candidate factor count")
    parser.add_argument("--max-folds", type=int, default=None, help="Optional debug cap for fold count")
    parser.add_argument("--skip-sensitivity", action="store_true", help="Skip slower sensitivity backtests")
    parser.add_argument("--skip-holdout", action="store_true", help="Skip the final partial holdout diagnostic")
    parser.add_argument("--disable-mlflow", action="store_true", help="Disable MLflow tracking for this run")
    parser.add_argument("--mode", choices=["formal", "sandbox"], default="formal",
                        help="Research mode. 'sandbox' skips the hypothesis requirement and registry publish, preserving all research primitives (for re-validation / comparison runs).")
    return parser.parse_args()


def configure_logging(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "run_console.log"
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    file_handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


def load_config() -> dict[str, Any]:
    config_path = PROJECT_ROOT / "config.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def normalize_multiindex(obj: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    if isinstance(obj.index, pd.MultiIndex) and obj.index.names[0] == "instrument":
        return obj.swaplevel().sort_index()
    if not obj.index.is_monotonic_increasing:
        return obj.sort_index()
    return obj


def slice_window(obj: pd.Series | pd.DataFrame, start: str, end: str) -> pd.Series | pd.DataFrame:
    idx = pd.IndexSlice
    return obj.loc[idx[pd.Timestamp(start):pd.Timestamp(end), :]]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def read_series_parquet(path: Path, column: str = "value") -> pd.Series:
    df = pd.read_parquet(path)
    if isinstance(df, pd.Series):
        series = df
    else:
        if column not in df.columns:
            column = df.columns[0]
        series = df[column]
    series = normalize_multiindex(series)
    series.name = path.stem
    return series.astype(np.float32)


def write_series_parquet(series: pd.Series, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalize_multiindex(series.astype(np.float32)).to_frame("value").to_parquet(path)


def qlib_to_ts_code(code: str) -> str:
    return str(code).replace("_", ".")


def ts_to_qlib_code(code: str) -> str:
    return str(code).replace(".", "_")


def resolve_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (PROJECT_ROOT / "workspace" / "research" / "alpha_mining" / f"event_driven_strategy_research_{stamp}").resolve()


def load_screening_inputs(screening_run_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    report_path = screening_run_dir / "factor_screening_report.csv"
    metadata_path = screening_run_dir / "factor_screening_run_metadata.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Missing screening report: {report_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing screening metadata: {metadata_path}")
    report_df = pd.read_csv(report_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return report_df, metadata


def parse_st_ranges(st_path: Path) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = defaultdict(list)
    if not st_path.exists():
        return {}
    for line in st_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        code, start_str, end_str = parts[0], parts[1], parts[2]
        ranges[code].append((pd.Timestamp(start_str), pd.Timestamp(end_str)))
    return dict(ranges)


def is_st_on_date(code: str, date: pd.Timestamp, st_ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]) -> bool:
    for start, end in st_ranges.get(code, []):
        if start <= date <= end:
            return True
    return False


def build_walk_forward_folds(
    start_date: str,
    end_date: str,
    train_years: int = TRAIN_YEARS,
    validation_years: int = VALIDATION_YEARS,
    test_years: int = TEST_YEARS,
    step_years: int = STEP_YEARS,
) -> tuple[list[FoldSpec], HoldoutSpec | None]:
    return shared_build_walk_forward_folds(
        start_date=start_date,
        end_date=end_date,
        train_years=train_years,
        validation_years=validation_years,
        test_years=test_years,
        step_years=step_years,
    )


def build_rebalance_dates(calendar: list[pd.Timestamp], rebalance_days: int) -> list[pd.Timestamp]:
    if rebalance_days <= 0:
        raise ValueError("rebalance_days must be positive")
    return list(calendar[::rebalance_days])


def build_liquidity_scenarios(args: argparse.Namespace) -> list[LiquidityScenario]:
    return [
        LiquidityScenario("no_filter", adv_floor=None, participation_cap=None, bottom_pct=None),
        LiquidityScenario("adv_floor_only", adv_floor=args.adv_median_floor, participation_cap=None, bottom_pct=None),
        LiquidityScenario("adv_floor_plus_participation", adv_floor=args.adv_median_floor, participation_cap=args.participation_cap, bottom_pct=None),
        LiquidityScenario("bottom_20pct_filter", adv_floor=None, participation_cap=None, bottom_pct=0.20),
    ]


def get_required_catalog(
    candidate_factors: list[str],
    include_new_data: bool,
) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, Any]]:
    from src.alpha_research.factor_library.catalog import get_industry_relative_defs
    full_catalog = get_factor_catalog(include_new_data=include_new_data)
    composite_defs = get_composite_defs()
    composite_map = {item["name"]: item for item in composite_defs}
    industry_rel_defs = get_industry_relative_defs()
    industry_rel_map = {item["name"]: item for item in industry_rel_defs}
    base_names = set()
    required_composites: list[dict[str, Any]] = []
    required_industry_rel: list[dict[str, Any]] = []
    for factor in candidate_factors:
        if factor in composite_map:
            required_composites.append(composite_map[factor])
            base_names.update(composite_map[factor]["components"])
        elif factor in industry_rel_map:
            d = industry_rel_map[factor]
            required_industry_rel.append(d)
            base_names.add(d["base"])
        elif factor in full_catalog:
            base_names.add(factor)
        else:
            raise KeyError(f"Factor {factor} not found in catalog, composites, or industry-relative defs")
    trimmed_catalog = {name: full_catalog[name] for name in full_catalog if name in base_names}
    return trimmed_catalog, required_composites, composite_map, required_industry_rel


def build_factor_meta(candidate_factors: list[str], include_new_data: bool) -> dict[str, dict[str, Any]]:
    from src.alpha_research.factor_library.catalog import get_industry_relative_defs
    category_map = get_category_map()
    full_catalog = get_factor_catalog(include_new_data=include_new_data)
    composite_map = {item["name"]: item for item in get_composite_defs()}
    industry_rel_map = {item["name"]: item for item in get_industry_relative_defs()}
    meta: dict[str, dict[str, Any]] = {}
    for factor in candidate_factors:
        if factor in composite_map:
            cdef = composite_map[factor]
            expression = "COMPOSITE(" + ", ".join(cdef["components"]) + ")"
        elif factor in industry_rel_map:
            d = industry_rel_map[factor]
            expression = f"INDUSTRY_REL[{d['kind']}]({d['base']})"
        else:
            expression = full_catalog.get(factor, "")
        meta[factor] = {
            "factor": factor,
            "category": category_map.get(factor, "Other"),
            "expression": expression,
            "family": factor.split("_")[0],
        }
    return meta


def fetch_auxiliary_fields(start_date: str, end_date: str) -> pd.DataFrame:
    import qlib  # noqa: F401
    from qlib.data import D

    instruments = D.instruments(market="all_stocks")
    fields = [
        ADJ_CLOSE,
        "Ref($total_mv, 1)",
        "Med(Ref($amount, 1), 20)",
        "Ref($amount, 1)",
    ]
    names = ["adj_close", "market_cap", "adv20_median_k", "amount_k"]
    aux_df = D.features(instruments, fields, start_time=start_date, end_time=end_date)
    aux_df.columns = names
    aux_df = aux_df.swaplevel().sort_index().astype(np.float32)
    aux_df["adv20_median_rmb"] = aux_df["adv20_median_k"] * 1000.0
    aux_df["amount_rmb"] = aux_df["amount_k"] * 1000.0
    return aux_df[["adj_close", "market_cap", "adv20_median_rmb", "amount_rmb"]]


def compute_factor_inputs(
    *,
    screening_metadata: dict[str, Any],
    candidate_factors: list[str],
    run_dir: Path,
) -> tuple[dict[str, Path], pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    include_new_data = bool(screening_metadata.get("include_new_data", True))
    trimmed_catalog, required_composites, _, required_industry_rel = get_required_catalog(
        candidate_factors, include_new_data
    )
    start_date = screening_metadata["start_date"]
    end_date = screening_metadata["end_date"]
    qlib_dir = screening_metadata["qlib_dir"]

    LOGGER.info(
        "Computing %d required base factors, %d required composites, "
        "%d industry-relative for %d A/B candidates",
        len(trimmed_catalog),
        len(required_composites),
        len(required_industry_rel),
        len(candidate_factors),
    )
    base_df, fwd_df = compute_factors(
        trimmed_catalog,
        start_date,
        end_date,
        horizons=[5, 10, 20],
        qlib_dir=qlib_dir,
        kernels=None,
        progress_interval=60,
    )
    working_df = add_composites(base_df, composite_defs=required_composites) if required_composites else base_df.copy()

    # Codex review-3 B1 fix: aux_df must be available BEFORE candidate
    # selection so industry-relative composites have market_cap to consume.
    aux_df = fetch_auxiliary_fields(start_date, end_date)

    if required_industry_rel:
        from src.alpha_research.factor_library.operators import (
            add_industry_relative_composites,
        )
        from src.data_infra.provider_metadata import build_industry_series_asof
        industry_series = build_industry_series_asof(working_df.index, "L1")
        working_df = add_industry_relative_composites(
            working_df,
            industry_series,
            market_cap=aux_df["market_cap"],
            defs=required_industry_rel,
        )

    candidate_df = working_df[candidate_factors].astype(np.float32)
    fwd_df = fwd_df.astype(np.float32)
    cache_dir = run_dir / "cache"
    raw_factor_dir = cache_dir / "raw_factors"
    raw_factor_dir.mkdir(parents=True, exist_ok=True)
    raw_factor_paths: dict[str, Path] = {}
    for factor in candidate_factors:
        path = raw_factor_dir / f"{factor}.parquet"
        write_series_parquet(candidate_df[factor], path)
        raw_factor_paths[factor] = path
    kernel_meta = {
        "requested_kernels": base_df.attrs.get("qlib_requested_kernels", ""),
        "effective_kernels": base_df.attrs.get("qlib_effective_kernels", ""),
        "required_base_factor_count": len(trimmed_catalog),
        "required_composite_count": len(required_composites),
    }
    LOGGER.info("Cached %d raw candidate factor series under %s", len(raw_factor_paths), raw_factor_dir)
    return raw_factor_paths, fwd_df, aux_df, kernel_meta


def load_stock_basic_reference(data_dir: Path) -> pd.DataFrame:
    stock_basic = pd.read_parquet(data_dir / "reference" / "stock_basic.parquet").copy()
    stock_basic["qlib_code"] = stock_basic["ts_code"].map(ts_to_qlib_code)
    stock_basic["list_date"] = pd.to_datetime(stock_basic["list_date"], format="%Y%m%d", errors="coerce")
    stock_basic["delist_date"] = pd.to_datetime(stock_basic["delist_date"], format="%Y%m%d", errors="coerce")
    return stock_basic


def build_industry_series(index: pd.MultiIndex, industry_map: pd.Series) -> pd.Series:
    """DEPRECATED — uses static stock_basic.industry (wrong taxonomy + no history).

    Replaced by `src.data_infra.provider_metadata.build_industry_series_asof`
    which loads time-varying SW2021 L1 membership. Kept as a deliberate
    error-raising shim so any out-of-tree caller fails loudly rather than
    silently producing wrong-taxonomy industry labels.
    See plan vast-exploring-rabbit v8 phase B2.
    """
    raise RuntimeError(
        "build_industry_series is deprecated; use "
        "src.data_infra.provider_metadata.build_industry_series_asof "
        "(time-varying SW2021 L1)."
    )


def preprocess_variant(series: pd.Series) -> pd.Series:
    return cs_zscore(winsorize(series.astype(np.float32))).astype(np.float32)


def summarize_variant(
    variant_name: str,
    factor_series: pd.Series,
    forward_return: pd.Series,
) -> dict[str, Any]:
    ic_series = compute_ic_series(factor_series, forward_return)
    summary = compute_ic_summary(ic_series) if not ic_series.empty else {}
    return {
        "variant": variant_name,
        "mean_rank_ic": summary.get("mean_rank_ic"),
        "rank_icir": summary.get("rank_icir"),
        "ic_hit_rate": summary.get("ic_hit_rate"),
        "n_days": summary.get("n_days"),
    }


def compute_fold_metrics_for_factor(
    factor_name: str,
    factor_series: pd.Series,
    forward_return: pd.Series,
    folds: list[FoldSpec],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for fold in folds:
        train_ic = compute_ic_series(
            slice_window(factor_series, fold.train_start, fold.train_end),
            slice_window(forward_return, fold.train_start, fold.train_end),
        )
        val_ic = compute_ic_series(
            slice_window(factor_series, fold.validation_start, fold.validation_end),
            slice_window(forward_return, fold.validation_start, fold.validation_end),
        )
        test_ic = compute_ic_series(
            slice_window(factor_series, fold.test_start, fold.test_end),
            slice_window(forward_return, fold.test_start, fold.test_end),
        )
        train_summary = compute_ic_summary(train_ic) if not train_ic.empty else {}
        val_summary = compute_ic_summary(val_ic) if not val_ic.empty else {}
        test_summary = compute_ic_summary(test_ic) if not test_ic.empty else {}

        train_direction = 1 if train_summary.get("mean_rank_ic", 0.0) >= 0 else -1
        val_direction = 1 if float(val_summary.get("mean_rank_ic", 0.0) or 0.0) >= 0 else -1
        direction_consistent = bool(train_direction == val_direction)
        validation_icir = abs(float(val_summary.get("rank_icir", 0.0) or 0.0))
        validation_pass = (
            direction_consistent
            and validation_icir >= SELECTION_MIN_VALIDATION_ICIR
            and int(val_summary.get("n_days", 0) or 0) >= 120
        )
        rows.append(
            {
                "factor": factor_name,
                "fold_id": fold.fold_id,
                "train_rank_icir": train_summary.get("rank_icir"),
                "val_rank_icir": val_summary.get("rank_icir"),
                "test_rank_icir": test_summary.get("rank_icir"),
                "train_mean_rank_ic": train_summary.get("mean_rank_ic"),
                "val_mean_rank_ic": val_summary.get("mean_rank_ic"),
                "test_mean_rank_ic": test_summary.get("mean_rank_ic"),
                "train_direction": train_direction,
                "val_direction": val_direction,
                "direction_consistent": direction_consistent,
                "validation_pass": validation_pass,
                "selected": False,
                "selection_reason": "",
            }
        )
    return pd.DataFrame(rows)


def compute_long_short_stats(long_short_returns: pd.Series) -> dict[str, Any]:
    if long_short_returns.empty:
        return {"ls_ann_return": np.nan, "ls_total_return": np.nan, "ls_sharpe": np.nan}
    return {
        "ls_ann_return": calculate_cagr(long_short_returns),
        "ls_total_return": calculate_total_return(long_short_returns),
        "ls_sharpe": calculate_sharpe_ratio(long_short_returns, risk_free_rate=0.0),
    }


def derive_factor_risks(
    screening_row: pd.Series,
    fold_metrics: pd.DataFrame,
    monotonicity: dict[str, Any],
) -> list[str]:
    risks: list[str] = []
    warning_flags = str(screening_row.get("warning_flags", "") or "").strip()
    if warning_flags and warning_flags.lower() != "nan":
        risks.append(f"Screening warning flags: {warning_flags}")
    if not bool(monotonicity.get("is_monotonic")):
        risks.append("Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.")
    if not fold_metrics.empty and fold_metrics["direction_consistent"].mean() < 0.6:
        risks.append("Signal direction flips too often between train and validation windows.")
    if not fold_metrics.empty and fold_metrics["validation_pass"].sum() == 0:
        risks.append("No fold passed the validation gate on the 5d strategy horizon.")
    coverage = screening_row.get("obs_coverage_primary")
    if pd.notna(coverage) and float(coverage) < 0.70:
        risks.append("Primary coverage is below 70%, which raises implementation risk.")
    if not risks:
        risks.append("No dominant implementation red flag, but stability still needs OOS confirmation.")
    return risks


def assign_corr_clusters(corr_matrix: pd.DataFrame, threshold: float = SELECTION_CORR_THRESHOLD) -> dict[str, str]:
    if corr_matrix.empty:
        return {}
    factors = list(corr_matrix.index)
    adjacency: dict[str, set[str]] = {factor: set() for factor in factors}
    for i, left in enumerate(factors):
        for right in factors[i + 1:]:
            corr = corr_matrix.loc[left, right]
            if pd.notna(corr) and abs(float(corr)) >= threshold:
                adjacency[left].add(right)
                adjacency[right].add(left)
    clusters: dict[str, str] = {}
    cluster_num = 1
    for factor in factors:
        if factor in clusters:
            continue
        queue = [factor]
        while queue:
            current = queue.pop()
            if current in clusters:
                continue
            clusters[current] = f"cluster_{cluster_num:02d}"
            queue.extend(adjacency[current] - set(clusters))
        cluster_num += 1
    return clusters


def apply_liquidity_rules(
    scores: pd.Series,
    adv_rmb: pd.Series,
    *,
    topk: int,
    target_value: float,
    scenario: LiquidityScenario,
) -> pd.Series:
    filtered = scores.dropna()
    aligned_adv = adv_rmb.reindex(filtered.index)
    if scenario.adv_floor is not None:
        filtered = filtered[aligned_adv >= float(scenario.adv_floor)]
        aligned_adv = aligned_adv.reindex(filtered.index)
    if scenario.bottom_pct is not None and not aligned_adv.dropna().empty:
        threshold = aligned_adv.quantile(float(scenario.bottom_pct))
        filtered = filtered[aligned_adv >= threshold]
        aligned_adv = aligned_adv.reindex(filtered.index)
    if scenario.participation_cap is not None:
        ratio = pd.Series(np.nan, index=aligned_adv.index, dtype=float)
        positive_adv = aligned_adv > 0
        ratio.loc[positive_adv] = target_value / aligned_adv.loc[positive_adv]
        filtered = filtered[ratio <= float(scenario.participation_cap)]
    return filtered.sort_values(ascending=False).head(topk)


def select_core_factors_for_fold(
    *,
    fold: FoldSpec,
    candidate_summary: pd.DataFrame,
    processed_factor_paths: dict[str, Path],
    forward_return: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fold_rows = candidate_summary[candidate_summary["fold_id"] == fold.fold_id].copy()
    qualified = fold_rows[fold_rows["validation_pass"]].copy()
    if qualified.empty:
        decision_rows = fold_rows.copy()
        decision_rows["cluster_id"] = ""
        decision_rows["marginal_mean_rank_ic"] = np.nan
        decision_rows["marginal_rank_icir"] = np.nan
        decision_rows["rejection_reason"] = "No factor passed the validation gate."
        return pd.DataFrame(), decision_rows, pd.DataFrame()

    series_map = {
        factor: slice_window(read_series_parquet(processed_factor_paths[factor]), fold.validation_start, fold.validation_end)
        for factor in qualified["factor"].tolist()
    }
    corr_matrix = compute_factor_correlation(series_map, method="spearman")
    cluster_map = assign_corr_clusters(corr_matrix, threshold=SELECTION_CORR_THRESHOLD)
    qualified["cluster_id"] = qualified["factor"].map(cluster_map).fillna("")
    qualified["abs_validation_rank_icir"] = qualified["val_rank_icir"].abs()
    qualified = qualified.sort_values(by=["abs_validation_rank_icir", "factor"], ascending=[False, True]).reset_index(drop=True)

    selected_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    marginal_rows: list[dict[str, Any]] = []
    selected_factors: list[str] = []
    selected_series: dict[str, pd.Series] = {}
    val_fwd = slice_window(forward_return, fold.validation_start, fold.validation_end)

    for _, row in qualified.iterrows():
        factor = row["factor"]
        factor_series = series_map[factor]
        max_abs_corr = 0.0
        corr_blocker = None
        for selected_factor in selected_factors:
            corr_value = corr_matrix.loc[factor, selected_factor]
            if pd.notna(corr_value) and abs(float(corr_value)) > max_abs_corr:
                max_abs_corr = abs(float(corr_value))
                corr_blocker = selected_factor

        marginal_summary: dict[str, Any] = {}
        if selected_factors:
            _, marginal_summary = compute_marginal_ic(
                {**selected_series, factor: factor_series},
                val_fwd,
                selected_factors,
                factor,
            )
        marginal_rank_icir = float(marginal_summary.get("rank_icir", np.nan))
        marginal_mean_rank_ic = float(marginal_summary.get("mean_rank_ic", np.nan))
        marginal_rows.append(
            {
                "factor": factor,
                "fold_id": fold.fold_id,
                "base_factor_count": len(selected_factors),
                "marginal_mean_rank_ic": marginal_mean_rank_ic,
                "marginal_rank_icir": marginal_rank_icir,
            }
        )

        selected = True
        selection_reason = "Validation pass; admitted as core factor."
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
                    "selection_reason": selection_reason,
                }
            )

        decision_rows.append(
            {
                **row.to_dict(),
                "selected": selected,
                "selection_reason": selection_reason if selected else "",
                "rejection_reason": rejection_reason,
                "cluster_id": row["cluster_id"],
                "max_abs_corr": max_abs_corr,
                "marginal_mean_rank_ic": marginal_mean_rank_ic,
                "marginal_rank_icir": marginal_rank_icir,
            }
        )

    return pd.DataFrame(selected_rows), pd.DataFrame(decision_rows), pd.DataFrame(marginal_rows)


def build_signal_schedule_for_window(
    *,
    start: str,
    end: str,
    selected_factors: list[str],
    factor_directions: dict[str, int],
    processed_factor_paths: dict[str, Path],
    stock_basic: pd.DataFrame,
    trade_calendar: list[pd.Timestamp],
    aux_df: pd.DataFrame,
    st_ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]],
    topk: int,
    capital: float,
    rebalance_days: int,
    scenario: LiquidityScenario,
) -> tuple[dict[pd.Timestamp, dict[str, float]], pd.DataFrame, pd.DataFrame]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    period_calendar = [date for date in trade_calendar if start_ts <= date <= end_ts]
    rebalance_dates = build_rebalance_dates(period_calendar, rebalance_days)
    target_value = capital / max(topk, 1)
    stock_basic_map = stock_basic.set_index("qlib_code")
    strategy_series: dict[str, pd.Series] = {}
    for factor in selected_factors:
        series = slice_window(read_series_parquet(processed_factor_paths[factor]), start, end)
        direction = factor_directions.get(factor, 1)
        strategy_series[factor] = cs_rank(series * float(direction)).astype(np.float32)

    schedule: dict[pd.Timestamp, dict[str, float]] = {}
    signal_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []

    for date in rebalance_dates:
        slices: list[pd.Series] = []
        for factor in selected_factors:
            factor_slice = strategy_series[factor].xs(date, level="datetime", drop_level=False)
            slices.append(factor_slice.droplevel("datetime").rename(factor))
        if not slices:
            continue
        daily_scores = pd.concat(slices, axis=1).mean(axis=1).dropna()
        if daily_scores.empty:
            continue

        eligible = pd.Series(True, index=daily_scores.index, dtype=bool)
        for code in eligible.index:
            ref = stock_basic_map.loc[code] if code in stock_basic_map.index else None
            if ref is None:
                eligible.loc[code] = False
                continue
            list_date = ref.get("list_date")
            delist_date = ref.get("delist_date")
            if pd.notna(list_date):
                traded_days = sum(1 for d in trade_calendar if list_date <= d <= date)
                if traded_days < LISTED_MIN_TRADING_DAYS:
                    eligible.loc[code] = False
                    continue
            if pd.notna(delist_date) and date > delist_date:
                eligible.loc[code] = False
                continue
            if is_st_on_date(code, date, st_ranges):
                eligible.loc[code] = False

        daily_scores = daily_scores[eligible]
        adv_slice = aux_df["adv20_median_rmb"].xs(date, level="datetime").reindex(daily_scores.index)
        selected_scores = apply_liquidity_rules(
            daily_scores,
            adv_slice,
            topk=topk,
            target_value=target_value,
            scenario=scenario,
        )
        if selected_scores.empty:
            diagnostic_rows.append(
                {
                    "date": date,
                    "n_scored": int(len(daily_scores)),
                    "n_selected": 0,
                    "scenario": scenario.name,
                    "detail": "No stock survived the liquidity screen.",
                }
            )
            continue
        weight = 1.0 / len(selected_scores)
        schedule[date] = {qlib_to_ts_code(code): float(weight) for code in selected_scores.index}
        diagnostic_rows.append(
            {
                "date": date,
                "n_scored": int(len(daily_scores)),
                "n_selected": int(len(selected_scores)),
                "scenario": scenario.name,
                "detail": "ok",
            }
        )
        for code, score in selected_scores.items():
            signal_rows.append(
                {
                    "date": date,
                    "instrument": qlib_to_ts_code(code),
                    "score": float(score),
                    "target_weight": float(weight),
                    "scenario": scenario.name,
                }
            )

    return schedule, pd.DataFrame(signal_rows), pd.DataFrame(diagnostic_rows)


def summarize_backtest_result(
    result,
    *,
    scenario: str,
    window_type: str,
    fold_id: str,
) -> dict[str, Any]:
    report = result.report.copy()
    if report.empty:
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
    order_log = result.order_log.copy()
    total_orders = int(len(order_log))
    blocked_orders = int((order_log["status"] == "BLOCKED").sum()) if not order_log.empty else 0
    filled_orders = int((order_log["status"] == "FILLED").sum()) if not order_log.empty else 0
    benchmark_total_return = calculate_total_return(report["bench"]) if "bench" in report.columns else np.nan
    strategy_total_return = calculate_total_return(report["return"])
    return {
        "scenario": scenario,
        "window_type": window_type,
        "fold_id": fold_id,
        "cumulative_return": strategy_total_return,
        "cagr": calculate_cagr(report["return"]),
        "max_drawdown": calculate_max_drawdown(report["return"]),
        "turnover_mean": float(report["turnover"].mean()) if "turnover" in report.columns else np.nan,
        "turnover_median": float(report["turnover"].median()) if "turnover" in report.columns else np.nan,
        "benchmark_total_return": benchmark_total_return,
        "excess_total_return": strategy_total_return - benchmark_total_return if pd.notna(benchmark_total_return) else np.nan,
        "trade_count": int(len(result.trades)),
        "total_orders": total_orders,
        "blocked_orders": blocked_orders,
        "filled_orders": filled_orders,
        "blocked_order_ratio": (blocked_orders / total_orders) if total_orders else np.nan,
        "filled_order_ratio": (filled_orders / total_orders) if total_orders else np.nan,
        "holding_cash_ratio": float((report["cash"] / report["total_value"]).mean()) if {"cash", "total_value"} <= set(report.columns) else np.nan,
        "window_start": str(report.index.min().date()),
        "window_end": str(report.index.max().date()),
    }


def run_event_driven_window(
    *,
    schedule: dict[pd.Timestamp, dict[str, float]],
    start: str,
    end: str,
    benchmark: str,
    capital: float,
    slippage_rate: float = 0.0005,
    exchange_config: CostConfig | None = None,
    time_split: dict | None = None,
    holdout_context: Any | None = None,
    volume_limit: float = 0.10,
    preload_strict: bool = False,
    instrumentation_path: str | None = None,
    # PR 8c Blocker 2: formal-mode kwargs forwarded to EventDrivenBacktester.
    # Validation handlers pass execution_profile + calendar_policy_id +
    # run_mode + preload_required + require_provider_manifest so the formal
    # runtime contract actually engages. Discovery callers omit them and
    # keep legacy sandbox behavior.
    execution_profile: str | None = None,
    calendar_policy_id: str | None = None,
    run_mode: str | None = None,
    preload_required: bool = False,
    require_provider_manifest: bool = False,
    override_reason: str | None = None,
) -> Any:
    """Run the ScheduledLongOnlyStrategy over a date window.

    The hypothesis_validation profile (jolly-seeking-lollipop Gate D.2) calls
    this with explicit ``time_split`` and ``holdout_context`` so the underlying
    EventDrivenBacktester enforces stage-aware window/seal checks. Existing
    discovery callers (event_driven_strategy_research.py and theme_strategy)
    omit those kwargs and get the legacy behavior.

    ``preload_strict`` (plan ``snappy-buzzing-meerkat`` v5 Phase 2.a) is
    passed through to ``EventDrivenBacktester.run``. Validation handlers
    must set ``True``; discovery callers keep the default ``False`` so a
    cache-manifest collision degrades to logged ERROR + best-effort fallback.

    PR 8c Blocker 2: formal validation handlers also pass execution_profile,
    calendar_policy_id, run_mode, preload_required, and
    require_provider_manifest so the wrapper's formal runtime contract
    (is_formal computation → strict preload + require_preloaded + provider
    manifest validation) actually engages on the validation path.
    """
    backtester = EventDrivenBacktester(data_dir=str(PROJECT_ROOT / "data"))
    strategy = ScheduledLongOnlyStrategy(schedule)
    return backtester.run(
        strategy=strategy,
        start_time=start,
        end_time=end,
        benchmark=benchmark,
        account=capital,
        exchange_config=exchange_config or CostConfig(),
        slippage=PctSlippage(slippage_rate),
        volume_limit=volume_limit,
        preload_fields=DEFAULT_PRELOAD_FIELDS,
        time_split=time_split,
        holdout_context=holdout_context,
        preload_strict=preload_strict,
        instrumentation_path=instrumentation_path,
        # PR 8c Blocker 2: pass formal kwargs through verbatim.
        execution_profile=execution_profile,
        calendar_policy_id=calendar_policy_id,
        run_mode=run_mode,
        preload_required=preload_required,
        require_provider_manifest=require_provider_manifest,
        override_reason=override_reason,
    )


def concat_with_fold(df: pd.DataFrame, fold_id: str) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    out["fold_id"] = fold_id
    return out


def aggregate_result_frames(result_frames: list[pd.DataFrame], sort_cols: list[str] | None = None) -> pd.DataFrame:
    frames = [frame for frame in result_frames if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=False)
    if sort_cols:
        result = result.sort_values(sort_cols)
    return result


def compound_fold_total_returns(perf_df: pd.DataFrame) -> float:
    if perf_df.empty or "cumulative_return" not in perf_df.columns:
        return float("nan")
    values = perf_df["cumulative_return"].dropna().astype(float)
    if values.empty:
        return float("nan")
    return float(np.prod(1 + values) - 1)


def try_start_tracker(run_name: str, disabled: bool = False) -> ExperimentTracker | None:
    if disabled:
        LOGGER.info("MLflow tracking disabled for this run.")
        return None
    mlops_config = load_config().get("mlops", {})
    tracking_uri = str(mlops_config.get("mlflow_uri", "") or "")
    parsed = urlparse(tracking_uri)
    if parsed.scheme in {"http", "https"} and parsed.hostname and parsed.port:
        try:
            with socket.create_connection((parsed.hostname, parsed.port), timeout=1.0):
                pass
        except OSError:
            LOGGER.warning("MLflow tracker unavailable for this run: %s", tracking_uri)
            return None
    try:
        tracker = ExperimentTracker(config_path=str(PROJECT_ROOT / "config.yaml"))
        tracker.start_run(run_name)
        return tracker
    except Exception as exc:
        LOGGER.warning("MLflow tracker unavailable for this run: %s", exc)
        return None


def resolve_mlflow_status(tracker: ExperimentTracker | None, disabled: bool = False) -> dict[str, str]:
    mlops_config = load_config().get("mlops", {})
    tracking_uri = str(mlops_config.get("mlflow_uri", "") or "")
    return {
        "mlflow_status": "disabled" if disabled else ("connected" if tracker is not None else "offline_skipped"),
        "mlflow_tracking_uri": tracking_uri,
    }


def tracker_log_params(tracker: ExperimentTracker | None, params: dict[str, Any]) -> None:
    if tracker is None:
        return
    try:
        tracker.log_params(params)
    except Exception as exc:
        LOGGER.warning("Failed to log MLflow params: %s", exc)


def tracker_log_metrics(tracker: ExperimentTracker | None, metrics: dict[str, Any]) -> None:
    if tracker is None:
        return
    clean = {key: float(value) for key, value in metrics.items() if value is not None and not pd.isna(value)}
    if not clean:
        return
    try:
        tracker.log_metrics(clean)
    except Exception as exc:
        LOGGER.warning("Failed to log MLflow metrics: %s", exc)


def tracker_end(tracker: ExperimentTracker | None) -> None:
    if tracker is None:
        return
    try:
        tracker.end_run()
    except Exception as exc:
        LOGGER.warning("Failed to end MLflow run cleanly: %s", exc)


def build_factor_conclusion(factor: str, factor_decisions: pd.DataFrame) -> dict[str, Any]:
    selected_count = int(factor_decisions["selected"].sum())
    validation_pass_count = int(factor_decisions["validation_pass"].sum())
    if selected_count >= max(2, math.ceil(len(factor_decisions) * 0.4)):
        decision = "keep"
        summary = "Repeatedly selected across OOS folds."
    elif validation_pass_count > 0:
        decision = "reserve"
        summary = "Shows some predictive value, but not stable enough for the core book."
    else:
        decision = "drop"
        summary = "Failed the 5d validation gate across all folds."
    return {
        "decision": decision,
        "selected_count": selected_count,
        "validation_pass_count": validation_pass_count,
        "summary": summary,
    }


def build_backtest_html(
    html_path: Path,
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series | None,
    name: str,
) -> None:
    if BacktestReport is not None:
        try:
            BacktestReport(strategy_returns, benchmark_returns, name=name).to_html(str(html_path))
            return
        except Exception as exc:
            LOGGER.warning("BacktestReport.to_html failed, using fallback HTML: %s", exc)
    perf_df = generate_performance_report(strategy_returns, benchmark_returns)
    yearly_df = calculate_yearly_returns(strategy_returns).to_frame("Strategy")
    monthly_df = calculate_monthly_return_table(strategy_returns)
    html = render_simple_backtest_html(
        title=name,
        performance_report=perf_df,
        yearly_returns=yearly_df,
        monthly_table=monthly_df,
    )
    write_text(html_path, html)


def research_context_path(run_dir: Path) -> Path:
    return run_dir / "cache" / "research_context.json"


def forward_return_cache_path(run_dir: Path) -> Path:
    return run_dir / "cache" / "forward_return.parquet"


def aux_fields_cache_path(run_dir: Path) -> Path:
    return run_dir / "cache" / "aux_fields.parquet"


def load_research_context(run_dir: Path) -> dict[str, Any]:
    return json.loads(research_context_path(run_dir).read_text(encoding="utf-8"))


def build_research_outputs(args: argparse.Namespace) -> dict[str, Any]:
    screening_run_dir = Path(args.screening_run_dir).resolve()
    run_dir = resolve_output_dir(args)
    configure_logging(run_dir)
    LOGGER.info("Starting event-driven strategy research run")
    LOGGER.info("Screening input: %s", screening_run_dir)
    _ = load_config()
    data_dir = PROJECT_ROOT / "data"

    report_df, screening_metadata = load_screening_inputs(screening_run_dir)
    screening_metadata["screening_run_dir"] = str(screening_run_dir)
    candidate_df = report_df.loc[report_df["grade"].astype(str).str.startswith(("A", "B"))].copy()
    candidate_df = candidate_df.sort_values(["grade", "abs_icir", "factor"], ascending=[True, False, True])
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

    tracker = try_start_tracker(run_dir.name, disabled=bool(args.disable_mlflow))
    tracker_log_params(
        tracker,
        {
            "screening_run_dir": str(screening_run_dir),
            "candidate_count": len(candidate_factors),
            "capital": args.capital,
            "benchmark": args.benchmark,
            "topk": args.topk,
            "rebalance_days": args.rebalance_days,
            "adv_median_floor": args.adv_median_floor,
            "participation_cap": args.participation_cap,
            "train_years": TRAIN_YEARS,
            "validation_years": VALIDATION_YEARS,
            "test_years": TEST_YEARS,
            "strategy_horizon": STRATEGY_HORIZON,
        },
    )

    factor_meta = build_factor_meta(candidate_factors, include_new_data=bool(screening_metadata.get("include_new_data", True)))
    raw_factor_paths, fwd_df, aux_df, kernel_meta = compute_factor_inputs(
        screening_metadata=screening_metadata,
        candidate_factors=candidate_factors,
        run_dir=run_dir,
    )
    forward_return = fwd_df[f"fwd_{STRATEGY_HORIZON}d"].astype(np.float32)
    adj_close = aux_df["adj_close"].astype(np.float32)
    market_cap = aux_df["market_cap"].astype(np.float32)

    stock_basic = load_stock_basic_reference(data_dir)
    # SW2021 time-varying industry replaces the prior static
    # stock_basic.industry lookup. Plan vast-exploring-rabbit v8 phase B2.
    from src.data_infra.provider_metadata import build_industry_series_asof
    st_ranges = parse_st_ranges(data_dir / "qlib_data" / "instruments" / "st_stocks.txt")
    trade_cal = pd.read_parquet(data_dir / "reference" / "trade_cal.parquet")
    trade_cal["cal_date"] = pd.to_datetime(trade_cal["cal_date"], format="%Y%m%d")
    trade_calendar = trade_cal.loc[trade_cal["is_open"] == 1, "cal_date"].sort_values().tolist()

    processed_factor_dir = run_dir / "cache" / "processed_factors"
    processed_factor_dir.mkdir(parents=True, exist_ok=True)
    processed_factor_paths: dict[str, Path] = {}
    factor_fold_metrics_frames: list[pd.DataFrame] = []
    factor_metric_rows: list[dict[str, Any]] = []
    factor_research_payloads: dict[str, dict[str, Any]] = {}

    for idx, factor in enumerate(candidate_factors, start=1):
        LOGGER.info("Researching factor %d/%d: %s", idx, len(candidate_factors), factor)
        screening_row = candidate_df[candidate_df["factor"] == factor].iloc[0]
        raw_series = read_series_parquet(raw_factor_paths[factor])
        aligned_market_cap = market_cap.reindex(raw_series.index)
        industry_series = build_industry_series_asof(raw_series.index, "L1")

        raw_variant = preprocess_variant(raw_series)
        size_variant = cs_zscore(neutralize_size(winsorize(raw_series), aligned_market_cap)).astype(np.float32)
        industry_variant = cs_zscore(neutralize_industry(winsorize(raw_series), industry_series)).astype(np.float32)
        strategy_variant = cs_zscore(
            neutralize_size_industry(winsorize(raw_series), aligned_market_cap, industry_series)
        ).astype(np.float32)
        processed_path = processed_factor_dir / f"{factor}.parquet"
        write_series_parquet(strategy_variant, processed_path)
        processed_factor_paths[factor] = processed_path

        neutralization_summary = pd.DataFrame(
            [
                summarize_variant("raw", raw_variant, forward_return),
                summarize_variant("size_neutral", size_variant, forward_return),
                summarize_variant("industry_neutral", industry_variant, forward_return),
                summarize_variant("size_industry_neutral", strategy_variant, forward_return),
            ]
        )
        fold_metrics = compute_fold_metrics_for_factor(factor, strategy_variant, forward_return, folds)
        factor_fold_metrics_frames.append(fold_metrics)

        ic_series = compute_ic_series(strategy_variant, forward_return)
        ic_summary = compute_ic_summary(ic_series) if not ic_series.empty else {}
        yearly_ic = compute_ic_by_year(ic_series) if not ic_series.empty else pd.DataFrame()
        rolling_ic = compute_rolling_ic(ic_series, window=ROLLING_IC_WINDOW) if not ic_series.empty else pd.DataFrame()
        decay_df = compute_ic_decay(strategy_variant, adj_close)
        optimal_horizon = find_optimal_horizon(decay_df)
        quantile_df = compute_quantile_returns(strategy_variant, forward_return, n_quantiles=5)
        quantile_summary = compute_quantile_summary(quantile_df) if not quantile_df.empty else pd.DataFrame()
        long_short_returns = compute_long_short_returns(quantile_df) if not quantile_df.empty else pd.Series(dtype=float)
        long_short_stats = compute_long_short_stats(long_short_returns)
        monotonicity = (
            test_monotonicity(quantile_summary)
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
            "risks": derive_factor_risks(screening_row, fold_metrics, monotonicity),
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

    selected_frames: list[pd.DataFrame] = []
    decision_frames: list[pd.DataFrame] = []
    marginal_frames: list[pd.DataFrame] = []
    fold_overview_rows: list[dict[str, Any]] = []
    factor_direction_by_fold: dict[str, dict[str, int]] = defaultdict(dict)

    for fold in folds:
        fold_selected, fold_decisions, fold_marginals = select_core_factors_for_fold(
            fold=fold,
            candidate_summary=factor_fold_metrics_df,
            processed_factor_paths=processed_factor_paths,
            forward_return=forward_return,
        )
        selected_frames.append(fold_selected)
        decision_frames.append(fold_decisions)
        marginal_frames.append(fold_marginals)
        for _, row in fold_decisions.iterrows():
            factor_direction_by_fold[fold.fold_id][row["factor"]] = int(row["train_direction"])
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
                "downgraded": bool(len(fold_selected) < MIN_SELECTED_FACTORS),
            }
        )

    selected_by_fold_df = pd.concat([frame for frame in selected_frames if not frame.empty], ignore_index=True) if selected_frames else pd.DataFrame()
    factor_selection_decisions_df = pd.concat([frame for frame in decision_frames if not frame.empty], ignore_index=True) if decision_frames else pd.DataFrame()
    marginal_df = pd.concat([frame for frame in marginal_frames if not frame.empty], ignore_index=True) if marginal_frames else pd.DataFrame()

    factor_cards_dir = run_dir / "factor_cards"
    factor_cards_dir.mkdir(parents=True, exist_ok=True)
    overall_decision_rows: list[dict[str, Any]] = []
    for factor in candidate_factors:
        factor_decisions = factor_selection_decisions_df[factor_selection_decisions_df["factor"] == factor].copy()
        factor_fold_view = factor_fold_metrics_df[factor_fold_metrics_df["factor"] == factor].copy()
        selected_fold_ids = set(
            factor_selection_decisions_df.loc[
                (factor_selection_decisions_df["factor"] == factor) & factor_selection_decisions_df["selected"],
                "fold_id",
            ]
        )
        factor_fold_view["selected"] = factor_fold_view["fold_id"].isin(selected_fold_ids)
        decision_summary = build_factor_conclusion(factor, factor_decisions if not factor_decisions.empty else factor_fold_view)
        majority_direction = 1 if factor_fold_view["train_direction"].mean() >= 0 else -1 if not factor_fold_view.empty else 1
        factor_meta[factor]["strategy_direction_label"] = "high_is_good" if majority_direction >= 0 else "low_is_good"
        correlation_rows = (
            factor_selection_decisions_df.loc[factor_selection_decisions_df["factor"] == factor, ["fold_id", "max_abs_corr"]]
            .rename(columns={"max_abs_corr": "abs_corr"})
            .assign(cluster_id="selected_cluster", peer_factor="selected_cluster_peer")
        )
        marginal_rows = marginal_df[marginal_df["factor"] == factor].copy()
        screening_snapshot = candidate_df[candidate_df["factor"] == factor].iloc[0].to_dict()
        payload = factor_research_payloads[factor]
        card_text = render_factor_card(
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
        write_text(factor_cards_dir / f"{factor}.md", card_text)
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

    overall_factor_decisions_df = pd.DataFrame(overall_decision_rows)

    default_scenario = build_liquidity_scenarios(args)[2]
    oos_performance_rows: list[dict[str, Any]] = []
    signal_frames: list[pd.DataFrame] = []
    signal_diagnostic_frames: list[pd.DataFrame] = []
    report_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    order_log_frames: list[pd.DataFrame] = []
    holding_frames: list[pd.DataFrame] = []
    corp_action_frames: list[pd.DataFrame] = []

    for fold in folds:
        fold_selected = selected_by_fold_df[selected_by_fold_df["fold_id"] == fold.fold_id]["factor"].tolist()
        if not fold_selected:
            LOGGER.warning("Skipping %s because no factor survived selection", fold.fold_id)
            continue
        schedule, signal_df, diag_df = build_signal_schedule_for_window(
            start=fold.test_start,
            end=fold.test_end,
            selected_factors=fold_selected,
            factor_directions=factor_direction_by_fold[fold.fold_id],
            processed_factor_paths=processed_factor_paths,
            stock_basic=stock_basic,
            trade_calendar=trade_calendar,
            aux_df=aux_df,
            st_ranges=st_ranges,
            topk=args.topk,
            capital=args.capital,
            rebalance_days=args.rebalance_days,
            scenario=default_scenario,
        )
        signal_frames.append(signal_df.assign(fold_id=fold.fold_id))
        signal_diagnostic_frames.append(diag_df.assign(fold_id=fold.fold_id))
        result = run_event_driven_window(
            schedule=schedule,
            start=fold.test_start,
            end=fold.test_end,
            benchmark=args.benchmark,
            capital=args.capital,
        )
        report_frames.append(concat_with_fold(result.report.reset_index(), fold.fold_id))
        trade_frames.append(concat_with_fold(result.trades, fold.fold_id))
        order_log_frames.append(concat_with_fold(result.order_log, fold.fold_id))
        holding_frames.append(concat_with_fold(result.daily_holdings, fold.fold_id))
        corp_action_frames.append(concat_with_fold(result.corporate_actions, fold.fold_id))
        oos_performance_rows.append(
            summarize_backtest_result(result, scenario=default_scenario.name, window_type="test", fold_id=fold.fold_id)
        )

    if holdout_spec is not None:
        LOGGER.info("Running holdout diagnostic window")
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
        for factor in candidate_factors:
            holdout_series = read_series_parquet(processed_factor_paths[factor])
            holdout_metrics = compute_fold_metrics_for_factor(
                factor,
                holdout_series,
                forward_return,
                [holdout_fold],
            )
            holdout_metric_frames.append(holdout_metrics)
            if not holdout_metrics.empty:
                holdout_directions[factor] = int(holdout_metrics.iloc[0]["train_direction"])
        holdout_metric_df = pd.concat(holdout_metric_frames, ignore_index=True) if holdout_metric_frames else pd.DataFrame()
        holdout_selected_df, _, _ = select_core_factors_for_fold(
            fold=holdout_fold,
            candidate_summary=holdout_metric_df,
            processed_factor_paths=processed_factor_paths,
            forward_return=forward_return,
        )
        holdout_selected = holdout_selected_df["factor"].tolist()
        if holdout_selected:
            schedule, signal_df, diag_df = build_signal_schedule_for_window(
                start=holdout_spec.start,
                end=holdout_spec.end,
                selected_factors=holdout_selected,
                factor_directions=holdout_directions,
                processed_factor_paths=processed_factor_paths,
                stock_basic=stock_basic,
                trade_calendar=trade_calendar,
                aux_df=aux_df,
                st_ranges=st_ranges,
                topk=args.topk,
                capital=args.capital,
                rebalance_days=args.rebalance_days,
                scenario=default_scenario,
            )
            result = run_event_driven_window(
                schedule=schedule,
                start=holdout_spec.start,
                end=holdout_spec.end,
                benchmark=args.benchmark,
                capital=args.capital,
            )
            signal_frames.append(signal_df.assign(fold_id="holdout"))
            signal_diagnostic_frames.append(diag_df.assign(fold_id="holdout"))
            report_frames.append(concat_with_fold(result.report.reset_index(), "holdout"))
            trade_frames.append(concat_with_fold(result.trades, "holdout"))
            order_log_frames.append(concat_with_fold(result.order_log, "holdout"))
            holding_frames.append(concat_with_fold(result.daily_holdings, "holdout"))
            corp_action_frames.append(concat_with_fold(result.corporate_actions, "holdout"))
            oos_performance_rows.append(
                summarize_backtest_result(result, scenario=default_scenario.name, window_type="holdout", fold_id="holdout")
            )

    event_driven_report_df = aggregate_result_frames(report_frames, sort_cols=["date", "fold_id"])
    event_driven_trades_df = aggregate_result_frames(trade_frames, sort_cols=["date", "fold_id"])
    event_driven_order_log_df = aggregate_result_frames(order_log_frames, sort_cols=["date", "fold_id"])
    event_driven_daily_holdings_df = aggregate_result_frames(holding_frames, sort_cols=["date", "fold_id"])
    event_driven_corporate_actions_df = aggregate_result_frames(corp_action_frames, sort_cols=["date", "fold_id"])
    strategy_signal_df = aggregate_result_frames(signal_frames, sort_cols=["date", "fold_id", "instrument"])
    signal_diagnostics_df = aggregate_result_frames(signal_diagnostic_frames, sort_cols=["date", "fold_id"])
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
                    "cumulative_return": compound_fold_total_returns(default_test_perf),
                    "cagr": default_test_perf["cagr"].mean(),
                    "max_drawdown": default_test_perf["max_drawdown"].min(),
                    "turnover_mean": default_test_perf["turnover_mean"].mean(),
                    "blocked_order_ratio": default_test_perf["blocked_order_ratio"].mean(),
                }
            )
        for scenario in [build_liquidity_scenarios(args)[0], build_liquidity_scenarios(args)[1], build_liquidity_scenarios(args)[3]]:
            scenario_perf_rows: list[dict[str, Any]] = []
            for fold in folds:
                fold_selected = selected_by_fold_df[selected_by_fold_df["fold_id"] == fold.fold_id]["factor"].tolist()
                if not fold_selected:
                    continue
                schedule, _, _ = build_signal_schedule_for_window(
                    start=fold.test_start,
                    end=fold.test_end,
                    selected_factors=fold_selected,
                    factor_directions=factor_direction_by_fold[fold.fold_id],
                    processed_factor_paths=processed_factor_paths,
                    stock_basic=stock_basic,
                    trade_calendar=trade_calendar,
                    aux_df=aux_df,
                    st_ranges=st_ranges,
                    topk=args.topk,
                    capital=args.capital,
                    rebalance_days=args.rebalance_days,
                    scenario=scenario,
                )
                result = run_event_driven_window(
                    schedule=schedule,
                    start=fold.test_start,
                    end=fold.test_end,
                    benchmark=args.benchmark,
                    capital=args.capital,
                )
                scenario_perf_rows.append(
                    summarize_backtest_result(result, scenario=scenario.name, window_type="test", fold_id=fold.fold_id)
                )
            perf_df = pd.DataFrame(scenario_perf_rows)
            if not perf_df.empty:
                liquidity_rows.append(
                    {
                        "scenario": scenario.name,
                        "cumulative_return": compound_fold_total_returns(perf_df),
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
            for fold in folds:
                fold_selected = selected_by_fold_df[selected_by_fold_df["fold_id"] == fold.fold_id]["factor"].tolist()
                if not fold_selected:
                    continue
                schedule, _, _ = build_signal_schedule_for_window(
                    start=fold.test_start,
                    end=fold.test_end,
                    selected_factors=fold_selected,
                    factor_directions=factor_direction_by_fold[fold.fold_id],
                    processed_factor_paths=processed_factor_paths,
                    stock_basic=stock_basic,
                    trade_calendar=trade_calendar,
                    aux_df=aux_df,
                    st_ranges=st_ranges,
                    topk=int(spec["topk"]),
                    capital=args.capital,
                    rebalance_days=int(spec["rebalance_days"]),
                    scenario=default_scenario,
                )
                result = run_event_driven_window(
                    schedule=schedule,
                    start=fold.test_start,
                    end=fold.test_end,
                    benchmark=args.benchmark,
                    capital=args.capital,
                    slippage_rate=float(spec["slippage_rate"]),
                )
                scenario_perf_rows.append(
                    summarize_backtest_result(result, scenario=str(spec["scenario"]), window_type="test", fold_id=fold.fold_id)
                )
            perf_df = pd.DataFrame(scenario_perf_rows)
            if not perf_df.empty:
                stress_rows.append(
                    {
                        "scenario": str(spec["scenario"]),
                        "topk": int(spec["topk"]),
                        "rebalance_days": int(spec["rebalance_days"]),
                        "slippage_rate": float(spec["slippage_rate"]),
                        "cumulative_return": compound_fold_total_returns(perf_df),
                        "cagr": perf_df["cagr"].mean(),
                        "max_drawdown": perf_df["max_drawdown"].min(),
                        "blocked_order_ratio": perf_df["blocked_order_ratio"].mean(),
                    }
                )
        sensitivity_topk_rebalance_df = pd.DataFrame(stress_rows)

    factor_research_metrics_df = pd.DataFrame(factor_metric_rows)
    fold_overview_df = pd.DataFrame(fold_overview_rows)

    run_metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "screening_run_dir": str(screening_run_dir),
        "screening_catalog_hash": screening_metadata.get("catalog_hash"),
        "screening_composite_hash": screening_metadata.get("composite_hash"),
        "candidate_count": int(len(candidate_factors)),
        "candidate_factors": candidate_factors,
        "strategy_style": "all-market long-only",
        "strategy_horizon": STRATEGY_HORIZON,
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
        "folds": [asdict(fold) for fold in folds],
        "holdout": asdict(holdout_spec) if holdout_spec is not None else None,
        "kernel_meta": kernel_meta,
        "screening_requested_kernels": screening_metadata.get("requested_kernels"),
        "screening_effective_kernels": screening_metadata.get("effective_kernels"),
        **resolve_mlflow_status(tracker, disabled=bool(args.disable_mlflow)),
    }

    factor_research_metrics_df.to_csv(run_dir / "factor_research_metrics.csv", index=False)
    factor_selection_decisions_df.to_csv(run_dir / "factor_selection_decisions.csv", index=False)
    selected_by_fold_df.to_csv(run_dir / "selected_core_factors_by_fold.csv", index=False)
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
    build_backtest_html(
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
    candidate_summary = candidate_df[["factor", "grade", "abs_icir"]].copy()
    candidate_summary["category"] = candidate_summary["factor"].map(lambda item: factor_meta[item]["category"])
    candidate_summary = candidate_summary.merge(
        overall_factor_decisions_df[["factor", "overall_decision", "selected_count", "validation_pass_count"]],
        on="factor",
        how="left",
    )
    master_review = render_master_review(
        run_metadata=run_metadata,
        screening_overview={"candidate_count": len(candidate_factors)},
        candidate_summary=candidate_summary,
        fold_overview=fold_overview_df,
        selected_by_fold=selected_by_fold_df,
        overall_factor_decisions=overall_factor_decisions_df,
        oos_performance=oos_fold_performance_df,
        liquidity_sensitivity=liquidity_sensitivity_df,
        topk_rebalance_sensitivity=sensitivity_topk_rebalance_df,
        warnings=warnings,
        artifacts=artifacts,
    )
    write_text(run_dir / "master_review.md", master_review)
    write_json(run_dir / "run_metadata.json", run_metadata)

    tracker_log_metrics(
        tracker,
        {
            "candidate_count": len(candidate_factors),
            "selected_factor_rows": len(selected_by_fold_df),
            "oos_total_return": calculate_total_return(strategy_returns) if not strategy_returns.empty else np.nan,
            "oos_cagr": calculate_cagr(strategy_returns) if not strategy_returns.empty else np.nan,
            "oos_max_drawdown": calculate_max_drawdown(strategy_returns) if not strategy_returns.empty else np.nan,
        },
    )
    tracker_end(tracker)

    LOGGER.info("Research run complete: %s", run_dir)
    return {
        "run_dir": run_dir,
        "candidate_count": len(candidate_factors),
        "selected_factor_rows": len(selected_by_fold_df),
    }


def main() -> None:
    from src.research_orchestrator.engine import _build_event_request_from_args, run_research

    args = parse_args()
    run_research(_build_event_request_from_args(args))


if __name__ == "__main__":
    main()
