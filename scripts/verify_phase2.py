"""Compatibility wrapper for Phase 2-focused raw integrity verification."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from data_infra.pit_backend import StagedQlibBackendBuilder


DEFAULT_PHASE2_DATASETS = [
    "trade_cal",
    "stock_basic",
    "namechange",
    "stock_st_daily",
    "index_weights",
    "industry_sw2021",
    "income",
    "income_quarterly",
    "balancesheet",
    "indicators",
    "dividends",
]


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile the Phase 2 raw store through the staged PIT integrity gates")
    parser.add_argument("--datasets", type=str, default=None, help="Comma-separated dataset subset")
    parser.add_argument("--allow-exceptions", action="store_true", help="Report issues without failing the process")
    args = parser.parse_args()

    logger.warning(
        "verify_phase2.py is a compatibility wrapper. "
        "The primary verifier is src/data_infra/pipeline/verify_database.py."
    )

    datasets = args.datasets.split(",") if args.datasets else DEFAULT_PHASE2_DATASETS
    builder = StagedQlibBackendBuilder(include_phase3=False, allow_exceptions=args.allow_exceptions)
    profiles = builder.profile_datasets(datasets=datasets)

    errors: list[str] = []
    warnings: list[str] = []
    for name, profile in profiles.items():
        errors.extend([f"{name}: {message}" for message in profile.errors])
        warnings.extend([f"{name}: {message}" for message in profile.warnings])
        if profile.unexpected_missing_dates:
            message = f"{name}: missing {len(profile.unexpected_missing_dates)} expected dates"
            if args.allow_exceptions:
                warnings.append(message)
            else:
                errors.append(message)

    summary = {
        "build_id": builder.build_id,
        "datasets": list(profiles),
        "errors": errors,
        "warnings": warnings,
    }
    logger.info("Profiled %d Phase 2 datasets", len(profiles))
    if warnings:
        logger.warning("Warnings (%d): %s", len(warnings), warnings[:10])
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors and not args.allow_exceptions:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
