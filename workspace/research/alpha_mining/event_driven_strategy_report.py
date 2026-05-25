"""
Report builders for the event-driven alpha-mining research pipeline.

The functions here only format already-computed results into reviewable
artifacts: markdown factor cards, a markdown master review, and a simple
HTML backtest report fallback that does not depend on Plotly.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd


def _fmt_pct(value: Any, digits: int = 2) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.{digits}%}"


def _fmt_num(value: Any, digits: int = 3) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.{digits}f}"


def _fmt_int(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{int(value):,}"


def _format_cell(column: str, value: Any) -> str:
    if pd.isna(value):
        return ""
    text_columns = {
        "factor",
        "category",
        "expression",
        "grade",
        "decision",
        "selection_reason",
        "rejection_reason",
        "warning_flags",
        "window_type",
        "fold_id",
        "variant",
        "split",
        "cluster_id",
        "family",
        "detail",
        "scenario",
    }
    pct_columns = {
        "ls_ann_return",
        "ls_total_return",
        "avg_cs_coverage",
        "date_coverage",
        "obs_coverage_primary",
        "rankic_coverage_primary",
        "ic_hit_rate",
        "target_weight",
        "blocked_order_ratio",
        "filled_order_ratio",
        "turnover_mean",
        "turnover_median",
        "holding_cash_ratio",
        "cumulative_return",
        "cagr",
        "max_drawdown",
        "benchmark_total_return",
        "excess_total_return",
    }
    if column in text_columns:
        return str(value)
    if column in pct_columns or column.endswith("_pct") or column.endswith("_rate"):
        return _fmt_pct(value)
    if column.endswith("_days") or column.startswith("n_") or column in {
        "selected_count",
        "validation_pass_count",
        "rebalance_count",
        "total_orders",
        "blocked_orders",
        "filled_orders",
        "trade_count",
    }:
        return _fmt_int(value)
    if "ic" in column or "sharpe" in column or "corr" in column or "beta" in column:
        return _fmt_num(value, digits=3)
    if isinstance(value, float):
        return _fmt_num(value, digits=3)
    return str(value)


def dataframe_to_markdown(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    rename: dict[str, str] | None = None,
) -> str:
    if df is None or df.empty:
        return "_No rows._"

    rename = rename or {}
    if columns is None:
        columns = list(df.columns)
    available = [column for column in columns if column in df.columns]
    if not available:
        return "_No matching columns._"

    header = [rename.get(column, column) for column in available]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for _, row in df[available].iterrows():
        cells = [_format_cell(column, row[column]) for column in available]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def bullet_list(items: Iterable[str]) -> str:
    items = [item for item in items if item]
    if not items:
        return "- None."
    return "\n".join(f"- {item}" for item in items)


def render_factor_card(
    *,
    factor_name: str,
    factor_meta: dict[str, Any],
    screening_snapshot: dict[str, Any],
    fold_metrics: pd.DataFrame,
    neutralization_summary: pd.DataFrame,
    yearly_ic: pd.DataFrame,
    rolling_ic_tail: pd.DataFrame,
    decay_df: pd.DataFrame,
    optimal_horizon: dict[str, Any],
    quantile_summary: pd.DataFrame,
    long_short_stats: dict[str, Any],
    monotonicity: dict[str, Any],
    correlation_rows: pd.DataFrame,
    marginal_rows: pd.DataFrame,
    risks: list[str],
    conclusion: dict[str, Any],
) -> str:
    lines: list[str] = [f"# Factor Card: {factor_name}", ""]
    lines.extend(
        [
            "## Basic Info",
            f"- Category: `{factor_meta.get('category', 'Unknown')}`",
            f"- Signal direction in strategy: `{factor_meta.get('strategy_direction_label', 'unknown')}`",
            f"- Raw expression: `{factor_meta.get('expression', '')}`",
            "",
            "## Screening Snapshot",
            f"- Grade: `{screening_snapshot.get('grade', '')}`",
            f"- 5d Rank ICIR: `{_fmt_num(screening_snapshot.get('rank_icir_5d'))}`",
            f"- 10d Rank ICIR: `{_fmt_num(screening_snapshot.get('rank_icir_10d'))}`",
            f"- 20d Rank ICIR: `{_fmt_num(screening_snapshot.get('rank_icir_20d'))}`",
            f"- Monotonic: `{screening_snapshot.get('monotonic', '')}`",
            f"- Warning flags: `{screening_snapshot.get('warning_flags', '')}`",
            f"- Primary coverage: `{_fmt_pct(screening_snapshot.get('obs_coverage_primary'))}`",
            "",
            "## Fold Metrics",
            dataframe_to_markdown(
                fold_metrics,
                columns=[
                    "fold_id",
                    "train_rank_icir",
                    "val_rank_icir",
                    "test_rank_icir",
                    "train_direction",
                    "val_direction",
                    "direction_consistent",
                    "validation_pass",
                    "selected",
                    "selection_reason",
                ],
                rename={
                    "train_rank_icir": "train_icir",
                    "val_rank_icir": "val_icir",
                    "test_rank_icir": "test_icir",
                },
            ),
            "",
            "## Neutralization Comparison",
            dataframe_to_markdown(
                neutralization_summary,
                columns=[
                    "variant",
                    "mean_rank_ic",
                    "rank_icir",
                    "ic_hit_rate",
                    "n_days",
                ],
            ),
            "",
            "## Yearly IC",
            dataframe_to_markdown(
                yearly_ic.reset_index(),
                columns=["year", "mean_rank_ic", "rank_icir", "ic_hit_rate", "n_days"],
            ),
            "",
            "## Rolling IC Tail",
            dataframe_to_markdown(
                rolling_ic_tail.reset_index(),
                columns=[
                    "date",
                    "rolling_mean_rank_ic",
                    "rolling_rank_icir",
                ],
                rename={"rolling_mean_rank_ic": "roll_mean_rank_ic"},
            ),
            "",
            "## IC Decay",
            f"- Best horizon by |ICIR|: `{optimal_horizon.get('best_horizon_icir')}`",
            f"- Peak ICIR: `{_fmt_num(optimal_horizon.get('peak_icir'))}`",
            f"- Half-life estimate: `{optimal_horizon.get('half_life')}`",
            dataframe_to_markdown(
                decay_df.reset_index(),
                columns=["horizon", "mean_rank_ic", "rank_icir", "n_days"],
            ),
            "",
            "## Quantile Diagnostic",
            f"- Long-short annualized diagnostic return: `{_fmt_pct(long_short_stats.get('ls_ann_return'))}`",
            f"- Long-short total diagnostic return: `{_fmt_pct(long_short_stats.get('ls_total_return'))}`",
            f"- Long-short Sharpe: `{_fmt_num(long_short_stats.get('ls_sharpe'))}`",
            f"- Monotonic: `{monotonicity.get('is_monotonic')}`",
            f"- Monotonic Spearman: `{_fmt_num(monotonicity.get('spearman_corr'))}`",
            dataframe_to_markdown(
                quantile_summary.reset_index(),
                columns=[
                    "quantile",
                    "mean_daily_return",
                    "annualized_return",
                    "volatility",
                    "sharpe",
                    "n_days",
                ],
            ),
            "",
            "## Correlation And Redundancy",
            dataframe_to_markdown(
                correlation_rows,
                columns=[
                    "fold_id",
                    "peer_factor",
                    "abs_corr",
                    "cluster_id",
                ],
            ),
            "",
            "## Marginal IC",
            dataframe_to_markdown(
                marginal_rows,
                columns=[
                    "fold_id",
                    "base_factor_count",
                    "marginal_mean_rank_ic",
                    "marginal_rank_icir",
                ],
            ),
            "",
            "## Risks",
            bullet_list(risks),
            "",
            "## Conclusion",
            f"- Final decision: `{conclusion.get('decision', 'reserve')}`",
            f"- Selected folds: `{conclusion.get('selected_count', 0)}`",
            f"- Validation-pass folds: `{conclusion.get('validation_pass_count', 0)}`",
            f"- Summary: {conclusion.get('summary', '')}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_master_review(
    *,
    run_metadata: dict[str, Any],
    screening_overview: dict[str, Any],
    candidate_summary: pd.DataFrame,
    fold_overview: pd.DataFrame,
    selected_by_fold: pd.DataFrame,
    overall_factor_decisions: pd.DataFrame,
    oos_performance: pd.DataFrame,
    liquidity_sensitivity: pd.DataFrame,
    topk_rebalance_sensitivity: pd.DataFrame,
    warnings: list[str],
    artifacts: list[str],
) -> str:
    lines: list[str] = ["# Event-Driven Strategy Research Review", ""]
    lines.extend(
        [
            "## Research Design",
            f"- Screening input: `{run_metadata.get('screening_run_dir', '')}`",
            f"- Candidate scope: `{screening_overview.get('candidate_count', 0)}` A/B factors",
            f"- Rolling split: `{run_metadata.get('train_years', 5)}y train / {run_metadata.get('validation_years', 2)}y validation / {run_metadata.get('test_years', 1)}y test`, step `{run_metadata.get('step_years', 1)}y`",
            f"- Strategy style: `{run_metadata.get('strategy_style', 'all-market long-only')}`",
            f"- Benchmark: `{run_metadata.get('benchmark', '')}`",
            f"- Capital: `{_fmt_int(run_metadata.get('capital', 0))}` RMB",
            "",
            "## Anti-Lookahead Controls",
            "- Factor directions are locked from the train window only.",
            "- Factor admission and redundancy removal use train/validation only.",
            "- Each fold's event-driven backtest runs only on its own test window.",
            "- The 2026 partial window is held out as a diagnostic and does not feed factor admission.",
            "",
            "## Candidate Pool Overview",
            dataframe_to_markdown(
                candidate_summary,
                columns=[
                    "factor",
                    "category",
                    "grade",
                    "abs_icir",
                    "overall_decision",
                    "selected_count",
                    "validation_pass_count",
                ],
            ),
            "",
            "## Fold Selection Logic",
            dataframe_to_markdown(
                fold_overview,
                columns=[
                    "fold_id",
                    "train_start",
                    "train_end",
                    "validation_start",
                    "validation_end",
                    "test_start",
                    "test_end",
                    "qualified_count",
                    "selected_count",
                    "downgraded",
                ],
            ),
            "",
            "## Selected Core Factors By Fold",
            dataframe_to_markdown(
                selected_by_fold,
                columns=[
                    "fold_id",
                    "selection_rank",
                    "factor",
                    "validation_rank_icir",
                    "marginal_rank_icir",
                    "cluster_id",
                ],
            ),
            "",
            "## Final Factor Conclusions",
            dataframe_to_markdown(
                overall_factor_decisions,
                columns=[
                    "factor",
                    "overall_decision",
                    "selected_count",
                    "validation_pass_count",
                    "avg_validation_rank_icir",
                    "max_abs_corr",
                ],
            ),
            "",
            "## OOS Event-Driven Performance",
            dataframe_to_markdown(
                oos_performance,
                columns=[
                    "scenario",
                    "window_type",
                    "cumulative_return",
                    "cagr",
                    "max_drawdown",
                    "turnover_mean",
                    "blocked_order_ratio",
                    "trade_count",
                ],
            ),
            "",
            "## Liquidity Sensitivity",
            dataframe_to_markdown(
                liquidity_sensitivity,
                columns=[
                    "scenario",
                    "cumulative_return",
                    "cagr",
                    "max_drawdown",
                    "turnover_mean",
                    "blocked_order_ratio",
                ],
            ),
            "",
            "## Topk / Rebalance / Slippage Sensitivity",
            dataframe_to_markdown(
                topk_rebalance_sensitivity,
                columns=[
                    "scenario",
                    "topk",
                    "rebalance_days",
                    "slippage_rate",
                    "cumulative_return",
                    "cagr",
                    "max_drawdown",
                    "blocked_order_ratio",
                ],
            ),
            "",
            "## Warnings And Caveats",
            bullet_list(warnings),
            "",
            "## Artifacts",
            bullet_list(artifacts),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_simple_backtest_html(
    *,
    title: str,
    performance_report: pd.DataFrame,
    yearly_returns: pd.DataFrame,
    monthly_table: pd.DataFrame,
    extra_sections: list[tuple[str, pd.DataFrame]] | None = None,
    notes: list[str] | None = None,
) -> str:
    extra_sections = extra_sections or []
    notes = notes or []

    parts = [
        "<!DOCTYPE html>",
        "<html><head>",
        "<meta charset='utf-8'>",
        f"<title>{title}</title>",
        "<style>",
        "body{font-family:Segoe UI,Arial,sans-serif;margin:32px;background:#fafafa;color:#1f2937;}",
        "h1,h2{color:#111827;}",
        "table{border-collapse:collapse;margin:16px 0;width:100%;background:#fff;}",
        "th,td{border:1px solid #d1d5db;padding:8px 10px;text-align:right;}",
        "th{text-align:center;background:#f3f4f6;}",
        "td:first-child,th:first-child{text-align:left;}",
        "ul{padding-left:20px;}",
        ".note{background:#fff7ed;border:1px solid #fdba74;padding:12px 14px;margin:16px 0;}",
        "</style>",
        "</head><body>",
        f"<h1>{title}</h1>",
    ]

    if notes:
        parts.append("<div class='note'><strong>Notes</strong><ul>")
        parts.extend(f"<li>{note}</li>" for note in notes)
        parts.append("</ul></div>")

    parts.extend(
        [
            "<h2>Performance Summary</h2>",
            performance_report.to_html(border=0, float_format=lambda x: f"{x:,.4f}"),
            "<h2>Yearly Returns</h2>",
            yearly_returns.to_html(border=0, float_format=lambda x: f"{x:,.4f}"),
            "<h2>Monthly Return Table</h2>",
            monthly_table.to_html(border=0, float_format=lambda x: f"{x:,.4f}"),
        ]
    )

    for section_name, section_df in extra_sections:
        parts.append(f"<h2>{section_name}</h2>")
        parts.append(section_df.to_html(border=0, float_format=lambda x: f"{x:,.4f}"))

    parts.extend(["</body></html>"])
    return "\n".join(parts)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
