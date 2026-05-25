"""CLI for the formal factor registry."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_registry import FactorRegistryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Formal factor registry CLI")
    parser.add_argument(
        "--registry-dir",
        default=str(PROJECT_ROOT / "data" / "factor_registry"),
        help="Registry root directory (default: data/factor_registry)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sync-catalog", help="Sync the official factor catalog into the registry")

    screening_parser = subparsers.add_parser("import-screening", help="Import a completed screening run")
    screening_parser.add_argument("--run-dir", required=True, help="Screening run directory")

    research_parser = subparsers.add_parser("import-research", help="Import a completed research run")
    research_parser.add_argument("--run-dir", required=True, help="Research run directory")

    status_parser = subparsers.add_parser("set-status", help="Manually change the status of a factor")
    status_parser.add_argument("--factor", required=True, help="Factor id")
    status_parser.add_argument(
        "--status",
        required=True,
        choices=["draft", "candidate", "approved", "deprecated"],
        help="Manual status to set",
    )
    status_parser.add_argument("--reason", required=True, help="Reason for the status change")
    status_parser.add_argument("--version", type=int, default=None, help="Optional specific factor version")
    status_parser.add_argument("--source-run-id", default=None, help="Optional related run id")

    export_parser = subparsers.add_parser("export", help="Export the current factor list")
    export_parser.add_argument("--status", default=None, help="Optional status filter")
    export_parser.add_argument("--output", required=True, help="Output CSV or parquet path")

    render_parser = subparsers.add_parser("render-html", help="Render the human-readable HTML review page")
    render_parser.add_argument(
        "--output",
        default=None,
        help="Optional output HTML path (default: <registry-dir>/factor_registry_review.html)",
    )

    subparsers.add_parser("summary", help="Print a registry summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("factor_registry_cli")

    store = FactorRegistryStore(args.registry_dir)

    if args.command == "sync-catalog":
        result = store.sync_catalog(record_run=True)
        store.save()
        logger.info(
            "Catalog synced: %s current records (%s base, %s composite)",
            result["current_factor_count"],
            result["catalog_factor_count"],
            result["catalog_composite_count"],
        )
        return 0

    if args.command == "import-screening":
        result = store.import_screening(args.run_dir)
        store.save()
        logger.info(
            "Imported screening run %s with %s evidence rows (%s)",
            result["run_id"],
            result["factor_count"],
            result["definition_binding"],
        )
        return 0

    if args.command == "import-research":
        result = store.import_research(args.run_dir)
        store.save()
        logger.info(
            "Imported research run %s with %s evidence rows (%s)",
            result["run_id"],
            result["factor_count"],
            result["definition_binding"],
        )
        return 0

    if args.command == "set-status":
        result = store.set_status(
            factor_id=args.factor,
            status=args.status,
            reason=args.reason,
            version=args.version,
            source_run_id=args.source_run_id,
        )
        store.save()
        logger.info(
            "Status updated: %s v%s %s -> %s",
            result["factor_id"],
            result["version"],
            result["old_status"],
            result["new_status"],
        )
        return 0

    if args.command == "export":
        count = store.export_current(args.output, status=args.status)
        logger.info("Exported %s current factor records to %s", count, Path(args.output).resolve())
        return 0

    if args.command == "render-html":
        output_path = store.render_html_review(args.output)
        logger.info("Rendered HTML review to %s", output_path)
        return 0

    if args.command == "summary":
        logger.info(store.summary_text())
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
