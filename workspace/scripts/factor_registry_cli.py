"""CLI for the formal factor registry."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_registry import FactorRegistryStore


def _git_head_sha(project_root: Path) -> tuple[str, bool]:
    """Return ``(HEAD_sha, is_dirty)``. ``is_dirty`` is True when the working tree
    has uncommitted changes. A privileged approval binds to a clean, committed HEAD;
    the store-level gate does the authoritative validation against ``current_git_sha``."""
    sha = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    porcelain = subprocess.run(
        ["git", "-C", str(project_root), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return sha, bool(porcelain)


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
    status_parser.add_argument(
        "--promotion-evidence-json",
        default=None,
        help="Path to a promotion-evidence JSON (REQUIRED for --status approved; passes the promotion gate)",
    )

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
        gate_kwargs: dict = {}
        if args.status == "approved":
            # Writer gate (PR P1.1): the CLI must NOT be an unaudited approval door.
            # Require an explicit promotion-evidence artifact and bind it to a clean,
            # committed HEAD; the store-level gate does the authoritative validation
            # (raises PromotionGateError -> non-zero exit if the evidence is short).
            if not args.promotion_evidence_json:
                logger.error(
                    "set-status --status approved requires --promotion-evidence-json "
                    "<path> (the promotion gate). Refusing — supply an independent "
                    "PIT-correct reproduction artifact via the promotion path."
                )
                return 2
            evidence_path = Path(args.promotion_evidence_json).resolve()
            if not evidence_path.exists():
                logger.error("Promotion-evidence file not found: %s", evidence_path)
                return 2
            promotion_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            head_sha, dirty = _git_head_sha(PROJECT_ROOT)
            if dirty:
                logger.error(
                    "Refusing approved promotion: git working tree is dirty. Commit or "
                    "stash before binding a privileged approval to HEAD."
                )
                return 2
            gate_kwargs = {"promotion_evidence": promotion_evidence, "current_git_sha": head_sha}
        result = store.set_status(
            factor_id=args.factor,
            status=args.status,
            reason=args.reason,
            version=args.version,
            source_run_id=args.source_run_id,
            **gate_kwargs,
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
