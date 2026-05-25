from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Any
import sys

from .pipeline import ThemeStrategyPipeline


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUNS_ROOT = PROJECT_ROOT / "workspace" / "outputs" / "theme_strategy"
DEFAULT_RESEARCH_ROOT = PROJECT_ROOT / "workspace" / "research" / "theme_strategy"
DEFAULT_CANDIDATE_REGISTRY_DIR = PROJECT_ROOT / "data" / "candidate_registry"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Theme-driven strategy research with field-first components."
    )
    parser.add_argument(
        "--theme",
        default="all",
        choices=["small_cap", "st", "flow_northbound", "all"],
        help="Theme to run.",
    )
    parser.add_argument(
        "--stage",
        default="all",
        choices=["universe", "field_audit", "component", "recipe", "event_driven", "all"],
        help="Pipeline stage to run.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional explicit output directory.",
    )
    parser.add_argument(
        "--recipe-source-run-dir",
        default=None,
        help="Optional existing recipe-stage run directory. With --stage event_driven, reuse that recipe result and skip recomputing universe/component/recipe.",
    )
    parser.add_argument(
        "--mode",
        choices=["formal", "sandbox"],
        default="formal",
        help="Research mode. 'sandbox' skips hypothesis requirement + registry publish for re-validation / comparison runs.",
    )
    return parser.parse_args(argv)


def build_run_name(theme: str, stage: str, stamp: str | None = None) -> str:
    run_stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    theme_label = str(theme or "all").strip().lower()
    stage_label = str(stage or "all").strip().lower()
    return f"theme_strategy_{theme_label}_{stage_label}_{run_stamp}"


def resolve_output_dir(output_dir: str | None, theme: str, stage: str) -> Path:
    if output_dir:
        return Path(output_dir).resolve()
    return (DEFAULT_RUNS_ROOT / build_run_name(theme, stage)).resolve()


def configure_logging(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run_console.log"
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def collect_artifact_manifest(run_dir: Path) -> list[dict[str, Any]]:
    if not run_dir.exists():
        return []
    artifacts: list[dict[str, Any]] = []
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        stat = path.stat()
        artifacts.append(
            {
                "path": path.relative_to(run_dir).as_posix(),
                "size_bytes": int(stat.st_size),
            }
        )
    return artifacts


def update_latest_runs_index(run_dir: Path, theme: str, stage: str) -> None:
    DEFAULT_RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    index_path = DEFAULT_RUNS_ROOT / "latest_runs.json"
    if index_path.exists():
        try:
            index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index_payload = {}
    else:
        index_payload = {}

    by_theme = index_payload.setdefault("by_theme", {})
    theme_payload = by_theme.setdefault(theme, {"stages": {}})
    theme_payload["latest_run_dir"] = str(run_dir)
    theme_payload["latest_stage"] = stage
    theme_payload.setdefault("stages", {})[stage] = str(run_dir)

    index_payload["latest_run_dir"] = str(run_dir)
    index_payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_json(index_path, index_payload)


def build_run_metadata(
    *,
    theme: str,
    stage: str,
    output_dir: Path,
    status: str,
    started_at: str,
    finished_at: str | None = None,
    artifact_count: int | None = None,
    error: str | None = None,
    candidate_registry_publish: dict[str, Any] | None = None,
    recipe_source_run_dir: str | None = None,
    execution_mode: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "generated_at": finished_at or started_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "status": status,
        "theme": theme,
        "stage": stage,
        "output_dir": str(output_dir),
        "research_entrypoint": str((DEFAULT_RESEARCH_ROOT / "theme_strategy_research.py").resolve()),
        "runs_root": str(DEFAULT_RUNS_ROOT.resolve()),
    }
    if recipe_source_run_dir:
        payload["recipe_source_run_dir"] = str(Path(recipe_source_run_dir).resolve())
    if execution_mode:
        payload["execution_mode"] = execution_mode
    if artifact_count is not None:
        payload["artifact_count"] = int(artifact_count)
    if error:
        payload["error"] = error
    if candidate_registry_publish is not None:
        payload["candidate_registry_publish"] = candidate_registry_publish
    return payload


def run_theme_strategy_pipeline(args: argparse.Namespace) -> Path:
    if args.recipe_source_run_dir and args.stage != "event_driven":
        raise ValueError("--recipe-source-run-dir only supports --stage event_driven.")
    output_dir = resolve_output_dir(args.output_dir, args.theme, args.stage)
    configure_logging(output_dir)
    execution_mode = "recipe_reuse_event_driven" if args.recipe_source_run_dir else "full_pipeline"

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_json(
        output_dir / "run_metadata.json",
        build_run_metadata(
            theme=args.theme,
            stage=args.stage,
            output_dir=output_dir,
            status="running",
            started_at=started_at,
            recipe_source_run_dir=args.recipe_source_run_dir,
            execution_mode=execution_mode,
        ),
    )

    try:
        pipeline = ThemeStrategyPipeline(output_root=output_dir)
        final_dir = pipeline.run(
            theme=args.theme,
            stage=args.stage,
            recipe_source_run_dir=args.recipe_source_run_dir,
        )
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        artifacts = collect_artifact_manifest(final_dir)
        write_json(
            final_dir / "run_metadata.json",
            build_run_metadata(
                theme=args.theme,
                stage=args.stage,
                output_dir=final_dir,
                status="completed",
                started_at=started_at,
                finished_at=finished_at,
                artifact_count=len(artifacts),
                recipe_source_run_dir=args.recipe_source_run_dir,
                execution_mode=execution_mode,
            ),
        )
        write_json(
            final_dir / "artifact_manifest.json",
            {
                "generated_at": finished_at,
                "theme": args.theme,
                "stage": args.stage,
                "run_dir": str(final_dir),
                "recipe_source_run_dir": str(Path(args.recipe_source_run_dir).resolve()) if args.recipe_source_run_dir else "",
                "execution_mode": execution_mode,
                "files": artifacts,
            },
        )
        update_latest_runs_index(final_dir, args.theme, args.stage)
        logging.info("Theme strategy research finished. Artifacts written to %s", final_dir)
        return final_dir
    except Exception as exc:
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_json(
            output_dir / "run_metadata.json",
            build_run_metadata(
                theme=args.theme,
                stage=args.stage,
                output_dir=output_dir,
                status="failed",
                started_at=started_at,
                finished_at=finished_at,
                error=str(exc),
                recipe_source_run_dir=args.recipe_source_run_dir,
                execution_mode=execution_mode,
            ),
        )
        raise
    finally:
        logging.shutdown()
        root_logger = logging.getLogger()
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> Path:
    from src.research_orchestrator.engine import _build_theme_request_from_args, run_research

    args = parse_args(argv)
    request = _build_theme_request_from_args(args)
    result = run_research(request)
    return Path(result.run_dir)
