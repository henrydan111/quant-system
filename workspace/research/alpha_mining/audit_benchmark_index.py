"""
Benchmark index audit utilities for event-driven strategy research.

This module provides both a reusable audit function and a lightweight CLI
entrypoint so benchmark data health can be checked before formal backtests.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from workspace.research.alpha_mining.event_driven_strategy_report import write_text


@dataclass(frozen=True)
class BenchmarkAuditResult:
    benchmark_code: str
    row_count: int
    start_date: str
    end_date: str
    duplicate_trade_dates: int
    missing_trade_days: int
    null_trade_date: int
    null_open: int
    null_high: int
    null_low: int
    null_close: int
    null_pre_close: int
    non_positive_open: int
    non_positive_high: int
    non_positive_low: int
    non_positive_close: int
    non_positive_pre_close: int
    bad_high_low: int
    close_outside_range: int
    pct_chg_diff_max_abs: float
    pct_chg_diff_over_1bp: int
    passed: bool


def load_config() -> dict[str, Any]:
    return yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))


def resolve_data_root() -> Path:
    config = load_config()
    data_root = Path(config["storage"]["data_root"])
    if not data_root.is_absolute():
        data_root = PROJECT_ROOT / data_root
    return data_root.resolve()


def resolve_index_path(benchmark_code: str) -> Path:
    data_root = resolve_data_root()
    return data_root / "market" / "index" / f"index_{benchmark_code}.parquet"


def load_trade_calendar() -> pd.DataFrame:
    data_root = resolve_data_root()
    trade_cal = pd.read_parquet(data_root / "reference" / "trade_cal.parquet").copy()
    trade_cal["cal_date"] = pd.to_datetime(trade_cal["cal_date"], format="%Y%m%d")
    return trade_cal.loc[trade_cal["is_open"] == 1, ["cal_date"]].sort_values("cal_date")


def audit_benchmark_dataframe(df: pd.DataFrame, trade_calendar: pd.DataFrame, benchmark_code: str) -> BenchmarkAuditResult:
    work = df.copy()
    work["trade_date"] = pd.to_datetime(work["trade_date"], format="%Y%m%d")
    work = work.sort_values("trade_date").reset_index(drop=True)

    row_count = int(len(work))
    start_date = work["trade_date"].min().strftime("%Y-%m-%d") if row_count else ""
    end_date = work["trade_date"].max().strftime("%Y-%m-%d") if row_count else ""
    duplicate_trade_dates = int(work["trade_date"].duplicated().sum())

    trade_slice = trade_calendar.loc[
        (trade_calendar["cal_date"] >= work["trade_date"].min()) & (trade_calendar["cal_date"] <= work["trade_date"].max())
    ]
    missing_trade_days = int((~trade_slice["cal_date"].isin(work["trade_date"])).sum()) if row_count else 0

    null_trade_date = int(work["trade_date"].isna().sum())
    null_open = int(work["open"].isna().sum())
    null_high = int(work["high"].isna().sum())
    null_low = int(work["low"].isna().sum())
    null_close = int(work["close"].isna().sum())
    null_pre_close = int(work["pre_close"].isna().sum())

    non_positive_open = int((work["open"] <= 0).sum())
    non_positive_high = int((work["high"] <= 0).sum())
    non_positive_low = int((work["low"] <= 0).sum())
    non_positive_close = int((work["close"] <= 0).sum())
    non_positive_pre_close = int((work["pre_close"] <= 0).sum())

    bad_high_low = int((work["high"] < work["low"]).sum())
    close_outside_range = int(((work["close"] > work["high"]) | (work["close"] < work["low"])).sum())

    recalculated_pct_chg = ((work["close"] / work["pre_close"]) - 1.0) * 100.0
    pct_diff = (work["pct_chg"] - recalculated_pct_chg).abs()
    pct_chg_diff_max_abs = float(pct_diff.max()) if not pct_diff.empty else 0.0
    pct_chg_diff_over_1bp = int((pct_diff > 0.01).sum())

    passed = all(
        [
            duplicate_trade_dates == 0,
            missing_trade_days == 0,
            null_trade_date == 0,
            null_open == 0,
            null_high == 0,
            null_low == 0,
            null_close == 0,
            null_pre_close == 0,
            non_positive_open == 0,
            non_positive_high == 0,
            non_positive_low == 0,
            non_positive_close == 0,
            non_positive_pre_close == 0,
            bad_high_low == 0,
            close_outside_range == 0,
            pct_chg_diff_over_1bp == 0,
        ]
    )

    return BenchmarkAuditResult(
        benchmark_code=benchmark_code,
        row_count=row_count,
        start_date=start_date,
        end_date=end_date,
        duplicate_trade_dates=duplicate_trade_dates,
        missing_trade_days=missing_trade_days,
        null_trade_date=null_trade_date,
        null_open=null_open,
        null_high=null_high,
        null_low=null_low,
        null_close=null_close,
        null_pre_close=null_pre_close,
        non_positive_open=non_positive_open,
        non_positive_high=non_positive_high,
        non_positive_low=non_positive_low,
        non_positive_close=non_positive_close,
        non_positive_pre_close=non_positive_pre_close,
        bad_high_low=bad_high_low,
        close_outside_range=close_outside_range,
        pct_chg_diff_max_abs=pct_chg_diff_max_abs,
        pct_chg_diff_over_1bp=pct_chg_diff_over_1bp,
        passed=passed,
    )


def render_benchmark_audit_report(result: BenchmarkAuditResult, index_path: Path) -> str:
    lines = [
        "# Benchmark Audit Report",
        "",
        "## Summary",
        f"- Benchmark: `{result.benchmark_code}`",
        f"- Source file: `{index_path}`",
        f"- Audit time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- Passed: `{result.passed}`",
        "",
        "## Coverage",
        f"- Row count: `{result.row_count:,}`",
        f"- Start date: `{result.start_date}`",
        f"- End date: `{result.end_date}`",
        f"- Duplicate trade_date rows: `{result.duplicate_trade_dates}`",
        f"- Missing open trade dates vs calendar: `{result.missing_trade_days}`",
        "",
        "## Null Checks",
        f"- null trade_date: `{result.null_trade_date}`",
        f"- null open/high/low/close/pre_close: `{result.null_open}` / `{result.null_high}` / `{result.null_low}` / `{result.null_close}` / `{result.null_pre_close}`",
        "",
        "## Price Validity",
        f"- non-positive open/high/low/close/pre_close: `{result.non_positive_open}` / `{result.non_positive_high}` / `{result.non_positive_low}` / `{result.non_positive_close}` / `{result.non_positive_pre_close}`",
        f"- high < low rows: `{result.bad_high_low}`",
        f"- close outside [low, high] rows: `{result.close_outside_range}`",
        "",
        "## pct_chg Consistency",
        f"- max abs diff between pct_chg and recalculated close/pre_close change: `{result.pct_chg_diff_max_abs:.6f}`",
        f"- rows with abs diff > 0.01 pct points: `{result.pct_chg_diff_over_1bp}`",
        "",
        "## Verdict",
        "- The benchmark is acceptable for formal strategy evaluation." if result.passed else "- The benchmark failed audit and should be repaired before formal strategy evaluation.",
        "",
    ]
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def run_audit(benchmark_code: str, output_dir: Path) -> BenchmarkAuditResult:
    index_path = resolve_index_path(benchmark_code)
    if not index_path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {index_path}")
    df = pd.read_parquet(index_path)
    trade_calendar = load_trade_calendar()
    result = audit_benchmark_dataframe(df, trade_calendar, benchmark_code)
    write_text(output_dir / "benchmark_audit_report.md", render_benchmark_audit_report(result, index_path))
    write_json(output_dir / "benchmark_audit_metrics.json", asdict(result))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a benchmark index parquet before formal backtests.")
    parser.add_argument("--benchmark", default="000001.SH", help="Benchmark index code, e.g. 000001.SH")
    parser.add_argument("--output-dir", required=True, help="Directory for benchmark audit artifacts")
    return parser.parse_args()


def main() -> None:
    from src.research_orchestrator.engine import _build_audit_request_from_args, run_research

    args = parse_args()
    run_research(
        _build_audit_request_from_args(
            benchmark=args.benchmark,
            output_dir=Path(args.output_dir).resolve(),
        )
    )


if __name__ == "__main__":
    main()
