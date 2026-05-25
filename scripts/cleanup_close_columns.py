"""Deprecated raw-mutation helper.

Historical one-off Parquet rewrites are no longer part of the supported data
workflow. Raw partitions should stay immutable; approved row-level corrections
belong in ``data/reference/daily_price_repair_overrides.csv`` and are applied
inside the staged PIT backend.
"""

from __future__ import annotations

import logging


logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.warning("cleanup_close_columns.py is deprecated and intentionally performs no raw-data edits.")
    logger.info("Use the staged PIT backend plus data/reference/daily_price_repair_overrides.csv for approved repairs.")


if __name__ == "__main__":
    main()
