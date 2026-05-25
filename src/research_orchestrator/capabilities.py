from __future__ import annotations

from typing import Any

import pandas as pd

from workspace.research.alpha_mining.event_driven_strategy_research import run_event_driven_window


CAPABILITY_SPECS: dict[str, dict[str, str]] = {
    "data_scope": {
        "category": "core_research",
        "description": "Planned capability placeholder for explicit scope declaration. Not yet a standalone executable step.",
    },
    "data_readiness": {
        "category": "core_research",
        "description": "Planned capability placeholder for data freshness and PIT coverage checks. Not yet a standalone executable step.",
    },
    "dataset_build": {
        "category": "core_research",
        "description": "Assemble prices, fundamentals, events, masks, labels, and benchmark data into a research-ready dataset.",
    },
    "universe_builder": {
        "category": "core_research",
        "description": "Define candidate stock pools and compare them through research validation.",
    },
    "label_builder": {
        "category": "core_research",
        "description": "Build forward-return, classification, risk, or other supervised labels.",
    },
    "factor_construction": {
        "category": "core_research",
        "description": "Construct new factors or components from existing fields and transformations.",
    },
    "factor_discovery": {
        "category": "core_research",
        "description": "Screen, evaluate, deduplicate, and rank factor candidates.",
    },
    "signal_search": {
        "category": "core_research",
        "description": "Combine factors into signals and search signal recipes or parameters.",
    },
    "model_training": {
        "category": "core_research",
        "description": "Train, tune, and compare predictive models.",
    },
    "portfolio_construction": {
        "category": "core_research",
        "description": "Turn signals into target holdings or weights with rebalance logic.",
    },
    "risk_overlay": {
        "category": "core_research",
        "description": "Apply exposure, turnover, capacity, or other portfolio-level risk constraints.",
    },
    "vectorized_backtest": {
        "category": "core_research",
        "description": "Run fast vectorized backtests for broad research screening.",
    },
    "event_driven_backtest": {
        "category": "core_research",
        "description": "Run realistic event-driven backtests with execution rules.",
    },
    "execution_validation": {
        "category": "core_research",
        "description": "Validate execution realism such as slippage, limits, blocked orders, and turnover drift.",
    },
    "stress_test": {
        "category": "core_research",
        "description": "Probe robustness under alternate assumptions, shocks, or parameter stress.",
    },
    "performance_diagnostics": {
        "category": "core_research",
        "description": "Planned capability placeholder for standardized diagnostics rollups. Not yet a standalone executable step.",
    },
    "gate_review": {
        "category": "support",
        "description": "Render a structured gate report, wait for a human decision, and resume only after approval or rejection.",
    },
    "gate_evaluation": {
        "category": "support",
        "description": "Compute measured values and pre-committed rule evaluation before concern scoring and human review.",
    },
    "gate_concern_scoring": {
        "category": "support",
        "description": "Pause for scored pre-registered concerns, validate the filled artifact, and persist concern evidence.",
    },
    "benchmark_audit": {
        "category": "diagnostic",
        "description": "Audit benchmark integrity and detect benchmark data issues.",
    },
    "object_resolver": {
        "category": "support",
        "description": "Resolve reusable research objects from formal registries or candidate pools.",
    },
    "registry_publish": {
        "category": "support",
        "description": "Publish research outputs back into the appropriate registry layer.",
    },
    "experiment_tracking": {
        "category": "support",
        "description": "Track run parameters, versions, comparisons, and experiment metadata.",
    },
    "report_render": {
        "category": "support",
        "description": "Planned capability placeholder for a standalone report-render step. Most profiles still render within other handlers.",
    },
}

CAPABILITY_ALIASES = {
    "portfolio_assembly": "portfolio_construction",
}

VALID_CAPABILITIES = tuple(CAPABILITY_SPECS.keys())
VALID_CAPABILITY_CATEGORIES = ("core_research", "diagnostic", "support")


def normalize_capability_name(value: str) -> str:
    item = str(value).strip()
    if not item:
        return ""
    return CAPABILITY_ALIASES.get(item, item)


def get_capability_metadata(value: str) -> dict[str, str]:
    item = normalize_capability_name(value)
    if item not in CAPABILITY_SPECS:
        raise ValueError(f"Unknown capability: {item}")
    payload = dict(CAPABILITY_SPECS[item])
    payload["name"] = item
    return payload


def list_capability_metadata() -> list[dict[str, str]]:
    return [get_capability_metadata(name) for name in VALID_CAPABILITIES]


def describe_capabilities(values: list[str] | tuple[str, ...]) -> list[dict[str, str]]:
    return [get_capability_metadata(name) for name in validate_capabilities(list(values))]


def validate_capabilities(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        item = normalize_capability_name(value)
        if not item:
            continue
        if item not in CAPABILITY_SPECS:
            raise ValueError(f"Unknown capability: {item}")
        if item not in ordered:
            ordered.append(item)
    return ordered


def build_equal_weight_schedule(
    scores_by_date: dict[pd.Timestamp, pd.Series],
    *,
    topk: int,
) -> dict[pd.Timestamp, dict[str, float]]:
    schedule: dict[pd.Timestamp, dict[str, float]] = {}
    for date, scores in sorted(scores_by_date.items(), key=lambda item: item[0]):
        if scores is None or scores.empty:
            continue
        selected = scores.sort_values(ascending=False).head(max(int(topk), 1))
        if selected.empty:
            continue
        weight = 1.0 / float(len(selected))
        schedule[pd.Timestamp(date)] = {str(code): float(weight) for code in selected.index}
    return schedule


def summarize_vectorized_screening_results(results: pd.DataFrame) -> dict[str, Any]:
    working = results.copy()
    grade_counts = (
        working["grade"].astype(str).value_counts().sort_index().to_dict()
        if "grade" in working.columns
        else {}
    )
    return {
        "row_count": int(len(working)),
        "grade_counts": grade_counts,
        "columns": working.columns.tolist(),
    }


def run_event_driven_backtest(
    *,
    schedule: dict[pd.Timestamp, dict[str, float]],
    start: str,
    end: str,
    benchmark: str,
    capital: float,
    slippage_rate: float = 0.0005,
):
    return run_event_driven_window(
        schedule=schedule,
        start=start,
        end=end,
        benchmark=benchmark,
        capital=capital,
        slippage_rate=slippage_rate,
    )


def summarize_event_driven_validation(result) -> dict[str, Any]:
    report = result.report.copy()
    if report.empty:
        return {
            "return": None,
            "max_drawdown": None,
            "turnover": None,
            "blocked_order_ratio": None,
            "trade_count": 0,
        }
    cumulative_return = float(report["return"].astype(float).add(1.0).prod() - 1.0)
    running = report["return"].astype(float).add(1.0).cumprod()
    peak = running.cummax()
    max_drawdown = float((running / peak - 1.0).min()) if not running.empty else None
    turnover = float(report["turnover"].astype(float).mean()) if "turnover" in report.columns else None
    blocked_ratio = (
        float(report["blocked_order_ratio"].astype(float).mean())
        if "blocked_order_ratio" in report.columns
        else None
    )
    return {
        "return": cumulative_return,
        "max_drawdown": max_drawdown,
        "turnover": turnover,
        "blocked_order_ratio": blocked_ratio,
        "trade_count": int(len(result.trades)),
    }
