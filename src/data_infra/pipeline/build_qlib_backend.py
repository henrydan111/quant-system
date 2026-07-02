"""Staged PIT-aware Qlib backend builder entrypoint.

This script now routes all backend work through the shared observed-data PIT
builder in :mod:`data_infra.pit_backend`. The old flat merge path has been
retired, but the legacy ``build_unified_qlib`` function name is preserved as a
compatibility wrapper for existing callers.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
sys.path.insert(0, os.path.join(project_root, "src"))

from data_infra.pit_backend import BuildGateError, SLOT_DEPTH_DEFAULT, build_qlib_backend, resolve_build_paths

log_dir = os.path.join(project_root, "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, "build_qlib_backend.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def _resolve_paths(data_root: str | None = None, qlib_dir: str | None = None) -> tuple[str, str]:
    """Compatibility wrapper returning ``(data_root, qlib_dir)``."""
    paths = resolve_build_paths(data_root=data_root, qlib_dir=qlib_dir)
    return paths.data_root, paths.qlib_dir


def build_unified_qlib(
    data_root: str,
    qlib_dir: str,
    field_filter: list[str] | None = None,
    mode: str = "all",
    publish: bool = False,
    include_phase3: bool = True,
    datasets: list[str] | None = None,
    touched_symbols: list[str] | None = None,
    build_id: str | None = None,
    slot_depth: int = SLOT_DEPTH_DEFAULT,
    allow_exceptions: bool = False,
    write_compat_aliases: bool = True,
    stage: str = "full",
    calendar_policy_id: str | None = None,
):
    """Backward-compatible wrapper over the staged PIT builder."""
    return build_qlib_backend(
        data_root=data_root,
        qlib_dir=qlib_dir,
        mode=mode,
        datasets=datasets,
        include_phase3=include_phase3,
        publish=publish,
        build_id=build_id,
        slot_depth=slot_depth,
        field_filter=field_filter,
        touched_symbols=touched_symbols,
        allow_exceptions=allow_exceptions,
        write_compat_aliases=write_compat_aliases,
        stage=stage,
        calendar_policy_id=calendar_policy_id,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the staged PIT-aware local Qlib provider")
    parser.add_argument("--data-root", type=str, default=None, help="Override data root (default: config.yaml)")
    parser.add_argument("--qlib-dir", type=str, default=None, help="Override provider output dir (default: config.yaml)")
    parser.add_argument("--fields", type=str, default=None, help="Comma-separated extra-field allowlist")
    parser.add_argument("--datasets", type=str, default=None, help="Comma-separated dataset subset to process")
    parser.add_argument("--mode", choices=["all", "update"], default="all", help="Build mode")
    parser.add_argument(
        "--stage",
        choices=["full", "upstream-only", "provider-only"],
        default="full",
        help="Build stage selection",
    )
    parser.add_argument("--build-id", type=str, default=None, help="Explicit staged build id")
    parser.add_argument("--slot-depth", type=int, default=SLOT_DEPTH_DEFAULT,
                        help=f"Quarter slot depth (default: {SLOT_DEPTH_DEFAULT})")
    parser.add_argument("--publish", action="store_true", help="Promote the staged build into data/qlib_data")
    parser.add_argument(
        "--calendar-policy",
        type=str,
        default=None,
        help="Calendar policy id stamped into the published manifest "
             "(config/calendar_policies/<id>.yaml). REQUIRED with --publish — no default.",
    )
    parser.add_argument("--exclude-phase3", action="store_true", help="Skip Phase 3 datasets")
    parser.add_argument(
        "--touched-symbols",
        type=str,
        default=None,
        help="Comma-separated ts_codes for scoped provider materialization",
    )
    parser.add_argument(
        "--skip-compat-aliases",
        action="store_true",
        help="Skip legacy scalar compatibility alias writes during provider materialization",
    )
    parser.add_argument(
        "--allow-exceptions",
        action="store_true",
        help="Keep the staged build even when profile/validation exceptions remain",
    )
    args = parser.parse_args()

    data_root, qlib_dir = _resolve_paths(args.data_root, args.qlib_dir)
    field_filter = args.fields.split(",") if args.fields else None
    datasets = args.datasets.split(",") if args.datasets else None
    touched_symbols = args.touched_symbols.split(",") if args.touched_symbols else None

    logger.info("Data root: %s", data_root)
    logger.info("Qlib dir: %s", qlib_dir)
    logger.info("Mode: %s", args.mode)
    logger.info("Stage: %s", args.stage)

    try:
        result = build_unified_qlib(
            data_root=data_root,
            qlib_dir=qlib_dir,
            field_filter=field_filter,
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
            calendar_policy_id=args.calendar_policy,
        )
    except BuildGateError as exc:
        logger.error("PIT backend build blocked by integrity gates:\n%s", exc)
        raise SystemExit(2) from exc

    logger.info("Build complete. Manifest: %s", result.manifest_path)
    if result.validation_warnings:
        logger.warning("Validation warnings (%d): %s", len(result.validation_warnings), result.validation_warnings[:10])


if __name__ == "__main__":
    main()
