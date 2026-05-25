"""P1-2: Reproducible refresh of ``data/reference/namechange.parquet``.

Context
=======

The namechange parquet is consumed by
``provider_metadata.build_st_universe`` (and through it, the ST universe
sidecar) but has no automated fetch path. It was historically placed once
and may drift over time as Tushare adds new rows for recent rename events.

This script re-fetches the full namechange history from Tushare and
atomically swaps the on-disk parquet when the new data is a strict
superset of the existing file. If any pre-existing row would be MUTATED
(rather than just having new rows appended), the script HARD FAILS —
namechange is an append-only ledger and silent mutations should never
happen.

Usage
=====

    E:/量化系统/venv/Scripts/python.exe scripts/refresh_namechange.py
    E:/量化系统/venv/Scripts/python.exe scripts/refresh_namechange.py --dry-run

This script is NOT wired into any daily or automated pipeline. Run it
manually when you want to bring the local cache up to date.

See CLAUDE.md §6 "Data Operations" and ``project_state.md`` remediation
milestone for the audit context.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_infra.fetchers import TushareFetcher  # noqa: E402
from data_infra.storage import StorageManager  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

NAMECHANGE_PATH = PROJECT_ROOT / "data" / "reference" / "namechange.parquet"
CORE_COLUMNS = ["ts_code", "name", "start_date", "end_date", "ann_date", "change_reason"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Sort and coerce a namechange DataFrame for deterministic comparison."""
    work = df.copy()
    for col in CORE_COLUMNS:
        if col not in work.columns:
            work[col] = None
    work = work[CORE_COLUMNS]
    return work.sort_values(["ts_code", "ann_date", "start_date", "name"]).reset_index(drop=True)


def _row_key(row: pd.Series) -> tuple:
    return (
        row.get("ts_code"),
        row.get("ann_date"),
        row.get("start_date"),
        row.get("name"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproducible namechange refresh (P1-2)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and validate but do not replace the on-disk file",
    )
    parser.add_argument(
        "--config-path",
        default=str(PROJECT_ROOT / "config.yaml"),
        help="Path to config.yaml",
    )
    args = parser.parse_args()

    # Load existing file if present
    existing: pd.DataFrame | None = None
    if NAMECHANGE_PATH.exists():
        existing = pd.read_parquet(NAMECHANGE_PATH)
        logger.info("Existing namechange has %d rows", len(existing))
    else:
        logger.info("No existing namechange at %s — this will be a first-time write", NAMECHANGE_PATH)

    # Fetch fresh data
    fetcher = TushareFetcher(config_path=args.config_path, base_sleep=1.5, max_retries=5)
    logger.info("Fetching full namechange history from Tushare...")
    fresh = fetcher.fetch_namechange()
    logger.info("Fetched %d rows", len(fresh))

    if fresh.empty:
        logger.error("Tushare returned an empty namechange frame. Aborting to protect the existing file.")
        return 2

    fresh_norm = _normalize(fresh)

    # Validate: fresh must be a strict superset of existing (no mutations)
    if existing is not None and not existing.empty:
        existing_norm = _normalize(existing)

        # Build a key-indexed lookup for the existing file
        existing_indexed = {
            _row_key(row): row for _, row in existing_norm.iterrows()
        }
        fresh_indexed = {
            _row_key(row): row for _, row in fresh_norm.iterrows()
        }

        missing_in_fresh = set(existing_indexed.keys()) - set(fresh_indexed.keys())
        if missing_in_fresh:
            logger.error(
                "SAFETY VIOLATION: %d rows that exist in the current file are MISSING "
                "from the fresh fetch. Possible causes: Tushare schema change, "
                "API downtime, or legitimate Tushare row deletions. "
                "Refusing to overwrite. First 5 missing: %s",
                len(missing_in_fresh),
                list(missing_in_fresh)[:5],
            )
            return 3

        mutated: list[tuple] = []
        for key, old_row in existing_indexed.items():
            if key not in fresh_indexed:
                continue
            new_row = fresh_indexed[key]
            for col in CORE_COLUMNS:
                old_val = old_row.get(col)
                new_val = new_row.get(col)
                if pd.isna(old_val) and pd.isna(new_val):
                    continue
                if old_val != new_val:
                    mutated.append((key, col, old_val, new_val))
                    break
        if mutated:
            logger.error(
                "SAFETY VIOLATION: %d pre-existing rows would be MUTATED by the fresh "
                "fetch. namechange is append-only — mutations should never happen. "
                "First 5: %s",
                len(mutated),
                mutated[:5],
            )
            return 4

        new_rows = set(fresh_indexed.keys()) - set(existing_indexed.keys())
        logger.info("Validation passed: %d new rows, 0 mutations", len(new_rows))

    if args.dry_run:
        logger.info("Dry-run mode: NOT writing %s", NAMECHANGE_PATH)
        return 0

    # Atomic write via tmp + rename
    tmp_path = NAMECHANGE_PATH.with_suffix(".parquet.tmp")
    NAMECHANGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fresh_norm.to_parquet(tmp_path, index=False)
    os.replace(tmp_path, NAMECHANGE_PATH)
    logger.info("Wrote %d rows to %s", len(fresh_norm), NAMECHANGE_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
