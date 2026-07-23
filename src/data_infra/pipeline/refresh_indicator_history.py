"""Refresh the historical indicators raw store from ``fina_indicator_vip``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
sys.path.insert(0, os.path.join(project_root, "src"))

from data_infra.pipeline.indicator_history_refresh import IndicatorVipHistoryRefresher


log_dir = os.path.join(project_root, "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, "refresh_indicator_history.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    # Raw-store quiescence (HARD pre-promotion integration gate): refuse to run while a
    # recovered family is being swapped into the live store — the tree may be half-replaced.
    from data_infra.recovery_quiescence import assert_no_active_recovery
    assert_no_active_recovery()
    parser = argparse.ArgumentParser(description="Refresh historical indicators from fina_indicator_vip")
    parser.add_argument("--config-path", type=str, default=os.path.join(project_root, "config.yaml"))
    parser.add_argument("--data-root", type=str, default=None, help="Override data root")
    parser.add_argument("--build-id", type=str, default=None, help="Explicit refresh build id")
    parser.add_argument("--start-period", type=str, default=None, help="Inclusive start period YYYYMMDD")
    parser.add_argument("--end-period", type=str, default=None, help="Inclusive end period YYYYMMDD")
    parser.add_argument("--dry-run", action="store_true", help="List the selected periods without mutating raw data")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate an existing staged/live indicator directory without fetching new data",
    )
    args = parser.parse_args()

    refresher = IndicatorVipHistoryRefresher(
        config_path=args.config_path,
        data_root=args.data_root,
        build_id=args.build_id,
        logger=logger,
    )
    summaries = refresher.run(
        start_period=args.start_period,
        end_period=args.end_period,
        dry_run=args.dry_run,
        validate_only=args.validate_only,
    )
    if summaries:
        total_rows = sum(summary.row_count for summary in summaries)
        logger.info("Indicator VIP refresh complete: %d periods, %d total rows", len(summaries), total_rows)
    else:
        logger.info("Indicator VIP refresh finished without fetching data.")


if __name__ == "__main__":
    main()
