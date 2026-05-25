"""Compatibility wrapper for income-quarter PIT provider rebuilds.

This script is kept for operators who are used to the historical entrypoint,
but it now delegates to the shared staged PIT backend and rebuilds only the
income family plus the base datasets it depends on.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from data_infra.pipeline.build_qlib_backend import _resolve_paths, build_unified_qlib


DEFAULT_DATASETS = [
    "trade_cal",
    "stock_basic",
    "daily",
    "index_daily",
    "income",
    "income_quarterly",
]


log_dir = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, "build_quarterly_qlib.log"),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild income quarterly PIT features via the staged backend")
    parser.add_argument("--data-root", type=str, default=None, help="Override data root")
    parser.add_argument("--qlib-dir", type=str, default=None, help="Override Qlib provider dir")
    parser.add_argument("--mode", choices=["all", "update"], default="update", help="Build mode")
    parser.add_argument(
        "--stage",
        choices=["full", "upstream-only", "provider-only"],
        default="provider-only",
        help="Build stage selection",
    )
    parser.add_argument("--build-id", type=str, default=None, help="Explicit staged build id")
    parser.add_argument("--fields", type=str, default=None, help="Comma-separated income field subset")
    parser.add_argument("--touched-symbols", type=str, default=None, help="Comma-separated ts_codes")
    parser.add_argument("--publish", action="store_true", help="Promote the staged build into data/qlib_data")
    parser.add_argument("--allow-exceptions", action="store_true", help="Keep build even if exceptions remain")
    parser.add_argument("--skip-compat-aliases", action="store_true", help="Skip legacy alias writes")
    args = parser.parse_args()

    logger.warning(
        "build_quarterly_qlib.py is a compatibility wrapper. "
        "Prefer src/data_infra/pipeline/build_qlib_backend.py for new workflows."
    )

    data_root, qlib_dir = _resolve_paths(args.data_root, args.qlib_dir)
    fields = args.fields.split(",") if args.fields else None
    touched_symbols = args.touched_symbols.split(",") if args.touched_symbols else None

    result = build_unified_qlib(
        data_root=data_root,
        qlib_dir=qlib_dir,
        field_filter=fields,
        mode=args.mode,
        publish=args.publish,
        include_phase3=False,
        datasets=DEFAULT_DATASETS,
        touched_symbols=touched_symbols,
        build_id=args.build_id,
        allow_exceptions=args.allow_exceptions,
        write_compat_aliases=not args.skip_compat_aliases,
        stage=args.stage,
    )
    logger.info("Build complete. Manifest: %s", result.manifest_path)


if __name__ == "__main__":
    main()
