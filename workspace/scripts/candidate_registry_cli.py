"""CLI for the candidate registry."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.candidate_registry import CandidateRegistryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Candidate registry CLI")
    parser.add_argument(
        "--registry-dir",
        default=str(PROJECT_ROOT / "data" / "candidate_registry"),
        help="Registry root directory (default: data/candidate_registry)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    theme_parser = subparsers.add_parser(
        "import-theme-run",
        help="Import a completed theme_strategy run into the candidate registry",
    )
    theme_parser.add_argument("--run-dir", required=True, help="theme_strategy run directory")

    status_parser = subparsers.add_parser("set-status", help="Manually change candidate status")
    status_parser.add_argument("--candidate", required=True, help="Candidate id")
    status_parser.add_argument(
        "--status",
        required=True,
        choices=[
            "observed",
            "candidate",
            "under_review",
            "promoted",
            "rejected",
            "archived",
            "already_formal",
        ],
        help="Manual status to set",
    )
    status_parser.add_argument("--reason", required=True, help="Reason for the status change")
    status_parser.add_argument("--version", type=int, default=None, help="Optional specific candidate version")
    status_parser.add_argument("--source-run-id", default=None, help="Optional related run id")

    export_parser = subparsers.add_parser("export", help="Export the current candidate list")
    export_parser.add_argument("--status", default=None, help="Optional status filter")
    export_parser.add_argument("--output", required=True, help="Output CSV or parquet path")

    render_parser = subparsers.add_parser("render-html", help="Render the human-readable HTML review page")
    render_parser.add_argument(
        "--output",
        default=None,
        help="Optional output HTML path (default: <registry-dir>/candidate_registry_review.html)",
    )

    subparsers.add_parser("summary", help="Print a registry summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("candidate_registry_cli")
    store = CandidateRegistryStore(args.registry_dir)

    if args.command == "import-theme-run":
        result = store.import_theme_strategy_run(args.run_dir)
        store.save()
        logger.info(
            "Imported theme run %s with %s candidates (%s components, %s recipes)",
            result["run_id"],
            result["candidate_count"],
            result["component_count"],
            result["recipe_count"],
        )
        return 0

    if args.command == "set-status":
        result = store.set_status(
            candidate_id=args.candidate,
            status=args.status,
            reason=args.reason,
            version=args.version,
            source_run_id=args.source_run_id,
        )
        store.save()
        logger.info(
            "Status updated: %s v%s %s -> %s",
            result["candidate_id"],
            result["version"],
            result["old_status"],
            result["new_status"],
        )
        return 0

    if args.command == "export":
        count = store.export_current(args.output, status=args.status)
        logger.info("Exported %s current candidates to %s", count, Path(args.output).resolve())
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
