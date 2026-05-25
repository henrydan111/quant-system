"""Compatibility wrapper for staged PIT-aware Qlib backend builds.

The old direct ``StorageManager.export_to_qlib()`` path is no longer the
supported production workflow. Keep this script as a familiar entrypoint, but
route all work through the staged PIT backend builder.
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


log_dir = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, "manual_qlib_dump.log"),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compatibility wrapper over the staged PIT-aware Qlib builder"
    )
    parser.add_argument("--data-root", type=str, default=None, help="Override data root")
    parser.add_argument("--qlib-dir", type=str, default=None, help="Override Qlib provider dir")
    parser.add_argument("--mode", choices=["all", "update"], default="all", help="Build mode")
    parser.add_argument(
        "--stage",
        choices=["full", "upstream-only", "provider-only"],
        default="full",
        help="Build stage selection",
    )
    parser.add_argument("--build-id", type=str, default=None, help="Explicit staged build id")
    parser.add_argument("--datasets", type=str, default=None, help="Comma-separated dataset subset")
    parser.add_argument("--fields", type=str, default=None, help="Comma-separated field subset")
    parser.add_argument("--touched-symbols", type=str, default=None, help="Comma-separated ts_codes")
    parser.add_argument("--slot-depth", type=int, default=5, help="Quarter slot depth")
    parser.add_argument("--publish", action="store_true", help="Promote the staged build into data/qlib_data")
    parser.add_argument("--exclude-phase3", action="store_true", help="Skip Phase 3 datasets")
    parser.add_argument("--skip-compat-aliases", action="store_true", help="Skip legacy alias writes")
    parser.add_argument("--allow-exceptions", action="store_true", help="Keep build even if exceptions remain")
    args = parser.parse_args()

    logger.warning(
        "manual_qlib_dump.py is now a compatibility wrapper. "
        "The supported workflow is src/data_infra/pipeline/build_qlib_backend.py."
    )

    data_root, qlib_dir = _resolve_paths(args.data_root, args.qlib_dir)
    datasets = args.datasets.split(",") if args.datasets else None
    fields = args.fields.split(",") if args.fields else None
    touched_symbols = args.touched_symbols.split(",") if args.touched_symbols else None

    result = build_unified_qlib(
        data_root=data_root,
        qlib_dir=qlib_dir,
        field_filter=fields,
        mode=args.mode,
        publish=args.publish,
        include_phase3=not args.exclude_phase3,
        datasets=datasets,
        touched_symbols=touched_symbols,
        build_id=args.build_id,
        slot_depth=args.slot_depth,
        allow_exceptions=args.allow_exceptions,
        write_compat_aliases=not args.skip_compat_aliases,
        stage=args.stage,
    )
    logger.info("Build complete. Manifest: %s", result.manifest_path)


if __name__ == "__main__":
    main()
