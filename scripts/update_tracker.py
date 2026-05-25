"""Deprecated data-tracker append helper.

The tracker now serves as durable project state and should be updated
deliberately instead of appending canned stale text blocks.
"""

from __future__ import annotations

import logging


logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.warning("update_tracker.py is deprecated and intentionally does not modify data/data_tracker.md.")
    logger.info("Update data/data_tracker.md directly when data coverage or partition schemes change.")


if __name__ == "__main__":
    main()
