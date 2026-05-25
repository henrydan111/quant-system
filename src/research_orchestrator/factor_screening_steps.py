from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.alpha_research.factor_registry import FactorRegistryStore
from workspace.scripts.batch_factor_screening import run_factor_screening_pipeline


def screening_request_path(run_dir: Path) -> Path:
    return run_dir / "cache" / "screening_request.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _screening_metadata_path(run_dir: Path) -> Path:
    return run_dir / "factor_screening_run_metadata.json"


def load_screening_request(run_dir: Path) -> dict[str, Any]:
    return _load_json(screening_request_path(run_dir))


def load_screening_metadata(run_dir: Path) -> dict[str, Any]:
    metadata_path = _screening_metadata_path(run_dir)
    if metadata_path.exists():
        return _load_json(metadata_path)
    return {}


def run_screening_dataset_build_step(
    *,
    output_root: Path,
    args_payload: dict[str, Any],
    argv: list[str],
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "output_dir": str(output_root),
        "args": dict(args_payload),
        "argv": list(argv),
    }
    _write_json(screening_request_path(output_root), payload)
    return {
        "run_dir": output_root,
        "request_path": str(screening_request_path(output_root)),
        "argv_count": len(argv),
    }


def run_screening_vectorized_backtest_step(
    *,
    output_root: Path,
) -> dict[str, Any]:
    request_payload = load_screening_request(output_root)
    pipeline_result = run_factor_screening_pipeline(list(request_payload.get("argv", [])))
    pipeline_run_dir = Path(str(pipeline_result.get("output_dir", output_root))).resolve()
    if pipeline_run_dir != output_root.resolve():
        raise ValueError(
            f"Factor screening pipeline wrote to {pipeline_run_dir}, expected {output_root.resolve()}."
        )
    metadata = load_screening_metadata(output_root)
    return {
        "run_dir": output_root,
        "pipeline_result": pipeline_result,
        "metadata": metadata,
        "report_path": str((output_root / "factor_screening_report.csv").resolve()),
    }


def run_screening_registry_publish_step(
    *,
    output_root: Path,
    factor_registry_dir: Path,
) -> dict[str, Any]:
    factor_store = FactorRegistryStore(factor_registry_dir)
    factor_import = factor_store.import_screening(output_root)
    factor_store.save()

    metadata = load_screening_metadata(output_root)
    metadata.update(
        {
            "output_dir": str(output_root),
            "factor_registry_import": factor_import,
        }
    )
    return {
        "run_dir": output_root,
        "base_metadata": metadata,
        "registry_payloads": {"factor_registry_import": factor_import},
        "produced_objects": [],
    }
