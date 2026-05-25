"""Audit a published or staged Qlib provider for compile health and PIT serving.

This script is the production-facing acceptance check for the local provider.
It combines:

1. Provider filesystem checks
2. Targeted `D.features()` retrieval on core market / statement / alt-data fields
3. Compatibility alias parity checks for PIT field families

It is intentionally lightweight enough to run after a staged build, while still
covering the main serving invariants we rely on in research and backtests.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import qlib
import yaml
from qlib.data import D


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if os.path.join(PROJECT_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))


DEFAULT_MARKET_FIELDS = ["close", "vol", "amount"]
DEFAULT_STATEMENT_FIELDS = [
    "roe",
    "roe_q0",
    "revenue",
    "revenue_q",
    "revenue_cum_q0",
    "revenue_sq_q0",
    "n_cashflow_act",
    "n_cashflow_act_q",
    "n_cashflow_act_cum_q0",
    "n_cashflow_act_sq_q0",
]
DEFAULT_INDICATOR_FIELDS = [
    "q_roe",
    "q_op_qoq",
    "q_ocf_to_sales",
    "or_yoy",
    "op_yoy",
    "pit_or_yoy",
    "pit_op_yoy",
    "pit_q_op_qoq",
    "pit_ocf_yoy",
]
DEFAULT_ALT_FIELDS = ["net_mf_amount", "rzye", "up_limit", "down_limit"]
DEFAULT_EVENT_FIELDS = [
    "top_list__net_amount",
    "top_list__l_buy",
    "top_inst__net_buy",
    "block_trade__amount",
    "cyq_perf__winner_rate",
    "holdertrade_net_ratio",
]

DEFAULT_FIELDS = (
    DEFAULT_MARKET_FIELDS
    + DEFAULT_STATEMENT_FIELDS
    + DEFAULT_INDICATOR_FIELDS
    + DEFAULT_ALT_FIELDS
    + DEFAULT_EVENT_FIELDS
)

DEFAULT_ALIAS_CHECKS = [
    ("roe", "roe_q0"),
    ("revenue", "revenue_cum_q0"),
    ("revenue_q", "revenue_sq_q0"),
    ("n_cashflow_act", "n_cashflow_act_cum_q0"),
    ("n_cashflow_act_q", "n_cashflow_act_sq_q0"),
    ("pit_or_yoy", "pit_or_yoy_q0"),
    ("pit_op_yoy", "pit_op_yoy_q0"),
    ("pit_q_op_qoq", "pit_q_op_qoq_q0"),
    ("pit_ocf_yoy", "pit_ocf_yoy_q0"),
]

REQUIRED_INSTRUMENT_FILES = [
    "all.txt",
    "all_stocks.txt",
    "st_stocks.txt",
    "csi300.txt",
    "csi500.txt",
    "csi1000.txt",
]


@dataclass
class AuditSummary:
    provider_uri: str
    sample_symbol_count: int
    start_date: str
    end_date: str
    checked_fields: list[str]
    filesystem_errors: list[str]
    filesystem_warnings: list[str]
    retrieval_errors: list[str]
    field_coverage: dict[str, dict[str, float | int]]
    alias_checks: list[dict[str, float | int | str | bool]]
    passed: bool


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve_provider_uri(args: argparse.Namespace) -> str:
    if args.provider_uri:
        return os.path.abspath(args.provider_uri)
    if args.build_id:
        return os.path.join(PROJECT_ROOT, "data", "qlib_builds", args.build_id, "provider")

    config = load_config(args.config_path)
    configured = config["storage"]["qlib_data_dir"]
    if os.path.isabs(configured):
        return configured
    return os.path.abspath(os.path.join(PROJECT_ROOT, configured))


def filesystem_audit(provider_uri: str, field_names: list[str], sample_symbols: list[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not os.path.isdir(provider_uri):
        return [f"Provider directory not found: {provider_uri}"], warnings

    calendars_dir = os.path.join(provider_uri, "calendars")
    instruments_dir = os.path.join(provider_uri, "instruments")
    features_dir = os.path.join(provider_uri, "features")
    if not os.path.isdir(calendars_dir):
        errors.append("Missing calendars directory")
    if not os.path.isdir(instruments_dir):
        errors.append("Missing instruments directory")
    if not os.path.isdir(features_dir):
        errors.append("Missing features directory")
        return errors, warnings

    for file_name in REQUIRED_INSTRUMENT_FILES:
        if not os.path.exists(os.path.join(instruments_dir, file_name)):
            errors.append(f"Missing instruments file: {file_name}")

    for symbol in sample_symbols:
        qlib_code = symbol.lower()
        feature_dir = os.path.join(features_dir, qlib_code)
        if not os.path.isdir(feature_dir):
            errors.append(f"Missing feature directory for sampled symbol: {qlib_code}")
            continue
        if not os.path.exists(os.path.join(feature_dir, "close.day.bin")):
            errors.append(f"{qlib_code}: missing close.day.bin")
        for field_name in field_names:
            feature_path = os.path.join(feature_dir, f"{field_name}.day.bin")
            if not os.path.exists(feature_path):
                warnings.append(f"{qlib_code}: missing sampled field file {field_name}.day.bin")

    return errors, warnings


def normalize_symbol_list(symbols: list[str]) -> list[str]:
    return [symbol.replace(".", "_").upper() for symbol in symbols]


def list_sample_symbols(sample_size: int, start_date: str, end_date: str) -> list[str]:
    instruments = D.instruments(market="all")
    all_symbols = D.list_instruments(
        instruments=instruments,
        start_time=start_date,
        end_time=end_date,
        as_list=True,
    )
    random.seed(42)
    if len(all_symbols) <= sample_size:
        return sorted(all_symbols)
    return sorted(random.sample(all_symbols, sample_size))


def fetch_fields(sample_symbols: list[str], field_names: list[str], start_date: str, end_date: str) -> tuple[pd.DataFrame, list[str]]:
    retrieval_errors: list[str] = []
    qlib_fields = [f"${field_name}" for field_name in field_names]
    try:
        df = D.features(sample_symbols, qlib_fields, start_time=start_date, end_time=end_date)
        df.columns = field_names
        return df, retrieval_errors
    except Exception as exc:  # pragma: no cover - defensive runtime path
        retrieval_errors.append(f"D.features failed for combined field request: {exc}")
        frames = []
        for field_name in field_names:
            try:
                field_df = D.features(sample_symbols, [f"${field_name}"], start_time=start_date, end_time=end_date)
                field_df.columns = [field_name]
                frames.append(field_df)
            except Exception as field_exc:
                retrieval_errors.append(f"{field_name}: {field_exc}")
        if not frames:
            return pd.DataFrame(), retrieval_errors
        merged = pd.concat(frames, axis=1)
        return merged, retrieval_errors


def coverage_stats(df: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    stats: dict[str, dict[str, float | int]] = {}
    total_rows = int(len(df))
    for field_name in df.columns:
        non_null = int(df[field_name].notna().sum())
        coverage = float(non_null / total_rows) if total_rows else 0.0
        stats[field_name] = {
            "rows": total_rows,
            "non_null": non_null,
            "coverage": coverage,
        }
    return stats


def alias_parity(
    df: pd.DataFrame,
    alias_checks: list[tuple[str, str]],
    requested_fields: set[str],
) -> list[dict[str, float | int | str | bool]]:
    results: list[dict[str, float | int | str | bool]] = []
    for lhs, rhs in alias_checks:
        if lhs not in requested_fields or rhs not in requested_fields:
            continue
        if lhs not in df.columns or rhs not in df.columns:
            results.append(
                {
                    "lhs": lhs,
                    "rhs": rhs,
                    "checked_rows": 0,
                    "equal_rows": 0,
                    "equal_ratio": 0.0,
                    "passed": False,
                    "reason": "missing_field",
                }
            )
            continue
        pair = df[[lhs, rhs]].dropna()
        checked_rows = int(len(pair))
        if checked_rows == 0:
            results.append(
                {
                    "lhs": lhs,
                    "rhs": rhs,
                    "checked_rows": 0,
                    "equal_rows": 0,
                    "equal_ratio": 0.0,
                    "passed": True,
                    "reason": "no_overlap",
                }
            )
            continue
        equal_mask = np.isclose(pair[lhs].to_numpy(), pair[rhs].to_numpy(), rtol=1e-6, atol=1e-6, equal_nan=True)
        equal_rows = int(equal_mask.sum())
        equal_ratio = float(equal_rows / checked_rows)
        results.append(
            {
                "lhs": lhs,
                "rhs": rhs,
                "checked_rows": checked_rows,
                "equal_rows": equal_rows,
                "equal_ratio": equal_ratio,
                "passed": bool(equal_rows == checked_rows),
                "reason": "ok" if equal_rows == checked_rows else "mismatch",
            }
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the published or staged Qlib provider")
    parser.add_argument("--config-path", default=os.path.join(PROJECT_ROOT, "config.yaml"))
    parser.add_argument("--provider-uri", default=None, help="Override provider directory")
    parser.add_argument("--build-id", default=None, help="Audit staged provider data/qlib_builds/<build_id>/provider")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--symbols", default=None, help="Comma-separated symbol allowlist in Qlib format, e.g. 000001_SZ")
    parser.add_argument("--fields", default=None, help="Comma-separated field allowlist without $ prefix")
    parser.add_argument("--summary-json", default=None, help="Optional output path for JSON summary")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    args = parse_args()
    provider_uri = resolve_provider_uri(args)

    if args.fields:
        field_names = [field.strip() for field in args.fields.split(",") if field.strip()]
    else:
        field_names = list(DEFAULT_FIELDS)

    logging.info("Connecting to provider: %s", provider_uri)
    qlib.init(provider_uri=provider_uri, region="cn", kernels=1)

    if args.symbols:
        sample_symbols = normalize_symbol_list([symbol.strip() for symbol in args.symbols.split(",") if symbol.strip()])
    else:
        sample_symbols = normalize_symbol_list(list_sample_symbols(args.sample_size, args.start_date, args.end_date))
    logging.info("Auditing %d sampled symbols", len(sample_symbols))

    filesystem_errors, filesystem_warnings = filesystem_audit(provider_uri, field_names, sample_symbols)
    df, retrieval_errors = fetch_fields(sample_symbols, field_names, args.start_date, args.end_date)
    field_coverage = coverage_stats(df) if not df.empty else {}
    alias_results = alias_parity(df, DEFAULT_ALIAS_CHECKS, set(field_names)) if not df.empty else []

    passed = not filesystem_errors and not retrieval_errors and all(result["passed"] for result in alias_results)
    summary = AuditSummary(
        provider_uri=provider_uri,
        sample_symbol_count=len(sample_symbols),
        start_date=args.start_date,
        end_date=args.end_date,
        checked_fields=field_names,
        filesystem_errors=filesystem_errors,
        filesystem_warnings=filesystem_warnings,
        retrieval_errors=retrieval_errors,
        field_coverage=field_coverage,
        alias_checks=alias_results,
        passed=passed,
    )

    summary_json = json.dumps(asdict(summary), ensure_ascii=False, indent=2)
    print(summary_json)
    if args.summary_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.summary_json)), exist_ok=True)
        with open(args.summary_json, "w", encoding="utf-8") as handle:
            handle.write(summary_json)

    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
