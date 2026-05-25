from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from jsonschema import validate as jsonschema_validate

from src.research_orchestrator.dag import (
    CompiledResearchDag,
    DagRunState,
    PauseForInputPayload,
    StepExecutionContext,
    StepExecutionResult,
)
from src.research_orchestrator.input_schemas import get_schema


StepHandlerFn = Callable[[StepExecutionContext], StepExecutionResult]


def _make_temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")


def timestamp_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(target)
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temp_path, target)


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _pending_input_to_dict(payload: PauseForInputPayload | dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, PauseForInputPayload):
        return payload.to_dict()
    return dict(payload)


def collect_artifact_manifest(run_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(run_dir).resolve()
    if not root.exists():
        return []
    files: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        stat = path.stat()
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": int(stat.st_size),
            }
        )
    return files


def write_root_artifacts(
    *,
    run_dir: str | Path,
    run_metadata: dict[str, Any],
    produced_objects: list[dict[str, Any]],
    review_summary: dict[str, Any],
    registry_resolution: dict[str, Any] | None = None,
    lineage_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "run_metadata.json", run_metadata)
    write_json(root / "produced_objects.json", {"produced_objects": produced_objects})
    write_json(root / "review_summary.json", review_summary)
    if registry_resolution is not None:
        write_json(root / "registry_resolution.json", registry_resolution)
    if lineage_links is not None:
        write_json(root / "lineage_links.json", {"lineage_links": lineage_links})
    artifact_manifest = {
        "run_dir": str(root),
        "files": collect_artifact_manifest(root),
    }
    write_json(root / "artifact_manifest.json", artifact_manifest)
    artifact_manifest["files"] = collect_artifact_manifest(root)
    write_json(root / "artifact_manifest.json", artifact_manifest)
    return run_metadata


def _step_state_payload(dag: CompiledResearchDag) -> list[dict[str, Any]]:
    return [
        {
            "step_id": step.step_id,
            "capability": step.capability,
            "handler": step.handler,
            "status": "pending",
            "started_at": None,
            "finished_at": None,
            "error": "",
            "pause_kind": "",
            "gate": {},
            "pending_input": {},
        }
        for step in dag.topological_order()
    ]


def initialize_run_state(
    *,
    dag: CompiledResearchDag,
    request_payload: dict[str, Any],
    request_hash: str,
    plan_hash: str,
    resume_policy: str,
) -> None:
    root = Path(dag.run_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    plan_payload = {
        "execution_model": "dag",
        "profile_id": dag.profile_id,
        "run_dir": str(root),
        "request": request_payload,
        "request_hash": request_hash,
        "plan_hash": plan_hash,
        "compiled_at": timestamp_now(),
        "steps": [step.to_dict() for step in dag.topological_order()],
        "metadata": dict(dag.metadata),
    }
    write_json(root / "dag_plan.json", plan_payload)
    state = DagRunState(
        profile_id=dag.profile_id,
        run_dir=str(root),
        request_hash=request_hash,
        plan_hash=plan_hash,
        resume_policy=resume_policy,
        status="running",
        completed_step_count=0,
        steps=tuple(_step_state_payload(dag)),
    )
    write_json(root / "dag_state.json", state.to_dict())


def load_run_state(run_dir: str | Path) -> dict[str, Any]:
    return read_json(Path(run_dir).resolve() / "dag_state.json")


def load_run_plan(run_dir: str | Path) -> dict[str, Any]:
    return read_json(Path(run_dir).resolve() / "dag_plan.json")


def update_run_state(
    *,
    run_dir: str | Path,
    status: str | None = None,
    failed_step_id: str | None = None,
    steps: list[dict[str, Any]] | None = None,
    pending_step_id: str | None = None,
    pending_gate: dict[str, Any] | None = None,
    pending_input: PauseForInputPayload | dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    state = load_run_state(root)
    if status is not None:
        state["status"] = status
    if failed_step_id is not None:
        state["failed_step_id"] = failed_step_id
    if steps is not None:
        state["steps"] = steps
        state["completed_step_count"] = sum(1 for item in steps if item.get("status") == "completed")
    if pending_step_id is not None:
        state["pending_step_id"] = pending_step_id
    if pending_gate is not None:
        state["pending_gate"] = dict(pending_gate)
    if pending_input is not None:
        state["pending_input"] = _pending_input_to_dict(pending_input)
    write_json(root / "dag_state.json", state)
    return state


def write_step_metadata(
    *,
    step_dir: Path,
    step_id: str,
    capability: str,
    status: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    error: str = "",
    resumed: bool = False,
    summary: dict[str, Any] | None = None,
    gate: dict[str, Any] | None = None,
    pause_kind: str = "",
    pending_input: PauseForInputPayload | dict[str, Any] | None = None,
) -> None:
    write_json(
        step_dir / "step_metadata.json",
        {
            "step_id": step_id,
            "capability": capability,
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "error": error,
            "resumed": resumed,
            "summary": dict(summary or {}),
            "gate": dict(gate or {}),
            "pause_kind": str(pause_kind or ""),
            "pending_input": _pending_input_to_dict(pending_input),
        },
    )


def write_step_outputs(step_dir: Path, payload: dict[str, Any]) -> None:
    write_json(step_dir / "step_outputs.json", payload)


def write_step_artifact_manifest(
    *,
    step_dir: Path,
    extra_artifacts: list[str] | None = None,
) -> None:
    payload = {
        "step_dir": str(step_dir),
        "files": collect_artifact_manifest(step_dir),
        "external_artifacts": list(extra_artifacts or []),
    }
    write_json(step_dir / "artifact_manifest.json", payload)
    payload["files"] = collect_artifact_manifest(step_dir)
    write_json(step_dir / "artifact_manifest.json", payload)


def load_step_outputs(run_dir: str | Path, step_id: str) -> dict[str, Any]:
    return read_json(Path(run_dir).resolve() / "steps" / step_id / "step_outputs.json")


def reconstruct_state_from_completed_steps(run_dir: str | Path) -> dict[str, Any]:
    state = load_run_state(run_dir)
    reconstructed = {
        "step_outputs": {},
        "resumed_inputs": {},
        "registry_resolution": {
            "formal_hits": 0,
            "candidate_hits": 0,
            "new_objects_created": 0,
            "unresolved_objects": [],
            "resolved_objects": [],
        },
        "base_metadata": {},
        "produced_objects": [],
        "registry_payloads": {},
    }
    for step in state.get("steps", []):
        if step.get("status") not in {"completed", "paused"}:
            continue
        outputs = load_step_outputs(run_dir, str(step["step_id"]))
        reconstructed["step_outputs"][str(step["step_id"])] = outputs
        if outputs.get("registry_resolution"):
            reconstructed["registry_resolution"] = outputs["registry_resolution"]
        if outputs.get("base_metadata"):
            reconstructed["base_metadata"] = outputs["base_metadata"]
        if outputs.get("produced_objects"):
            reconstructed["produced_objects"] = outputs["produced_objects"]
        if outputs.get("registry_payloads"):
            reconstructed["registry_payloads"] = outputs["registry_payloads"]
    return reconstructed


def _try_recover_concern_scoring_pause(
    step_dir: Path,
) -> dict[str, Any] | None:
    """Reconstruct a pause_for_input payload for a previously-paused gate_concern_scoring step.

    When the gate_concern_scoring handler raises ConcernEnforcementError on resume
    (e.g. user submitted a concern artifact with severity below the derived minimum),
    the per-step exception handler in execute_dag flips status from ``paused`` →
    ``failed`` AND clears ``pause_kind`` / ``pending_input`` in both dag_state.json
    and step_metadata.json. Without recovery, the only way forward is to manually
    edit run state (which the auto-mode classifier correctly blocks) or restart the
    DAG from scratch (re-running the upstream event_backtest, ~10+ min).

    This helper reconstructs the pending_input from convention:
      - artifact_path = step_dir / "gate_concern_scores.json"
      - template_path = step_dir / "gate_concern_scores_template.json"
      - schema_id     = "gate_concern_scores_v1"
    Recovery only fires when BOTH files exist on disk (i.e. the user re-ran
    ``hypothesis_cli.py score-concerns`` to write a corrected artifact). Returns
    None to leave the failed state untouched if either file is missing.

    The artifact_path/template_path/schema_id values mirror what
    src/research_orchestrator/steps.py::handle_gate_concern_scoring writes when it
    first creates the pause (steps.py:1417-1433). If that handler changes its
    conventions, this helper must move in lock-step.
    """
    artifact_path = step_dir / "gate_concern_scores.json"
    template_path = step_dir / "gate_concern_scores_template.json"
    if not artifact_path.exists() or not template_path.exists():
        return None
    return {
        "artifact_path": str(artifact_path.resolve()),
        "schema_id": "gate_concern_scores_v1",
        "description": (
            "Recovery: gate_concern_scoring previously failed on resume; "
            "re-reading user-resubmitted artifact"
        ),
        "template_path": str(template_path.resolve()),
        "expected_fields": ["scores"],
    }


def execute_dag(
    *,
    dag: CompiledResearchDag,
    request_hash: str,
    plan_hash: str,
    resume_policy: str,
    request_payload: dict[str, Any],
    build_context: Callable[[str, Path, bool, dict[str, Any]], StepExecutionContext],
    handler_registry: dict[str, StepHandlerFn],
) -> dict[str, Any]:
    root = Path(dag.run_dir).resolve()
    lock_path = root / ".dag_run.lock"
    root.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        raise ValueError(f"Run directory is already locked by an active process: {lock_path}")
    lock_payload = {
        "created_at": timestamp_now(),
        "pid": os.getpid(),
        "profile_id": dag.profile_id,
    }
    write_json(lock_path, lock_payload)
    try:
        if resume_policy == "restart" or not (root / "dag_plan.json").exists():
            initialize_run_state(
                dag=dag,
                request_payload=request_payload,
                request_hash=request_hash,
                plan_hash=plan_hash,
                resume_policy=resume_policy,
            )
            shared_state = reconstruct_state_from_completed_steps(root)
        else:
            plan_payload = load_run_plan(root)
            existing_request_hash = str(plan_payload.get("request_hash", ""))
            existing_plan_hash = str(plan_payload.get("plan_hash", ""))
            if existing_request_hash != request_hash or existing_plan_hash != plan_hash:
                raise ValueError("Resume blocked because request_hash or plan_hash changed for this run_dir.")
            shared_state = reconstruct_state_from_completed_steps(root)
            update_run_state(run_dir=root, status="running")

        run_state = load_run_state(root)
        steps_state = list(run_state.get("steps", []))
        steps_by_id = {item["step_id"]: item for item in steps_state}

        for step in dag.topological_order():
            step_dir = root / "steps" / step.step_id
            step_dir.mkdir(parents=True, exist_ok=True)
            current_state = steps_by_id[step.step_id]
            if resume_policy == "resume" and current_state.get("status") == "completed":
                continue

            # Recovery: if a gate_concern_scoring step previously paused, then failed on
            # resume (typically because the submitted concern artifact violated the
            # handler's severity/anchor checks), and the user has since rewritten the
            # artifact via hypothesis_cli.py score-concerns, restore the in-memory
            # paused state so the standard pause_for_input resume branch below picks up
            # the corrected artifact instead of re-invoking the handler with empty
            # resumed_inputs. See _try_recover_concern_scoring_pause for the convention
            # this relies on.
            if (
                current_state.get("status") == "failed"
                and step.capability == "gate_concern_scoring"
            ):
                recovered_payload = _try_recover_concern_scoring_pause(step_dir)
                if recovered_payload is not None:
                    current_state["status"] = "paused"
                    current_state["error"] = ""
                    current_state["pause_kind"] = "pause_for_input"
                    current_state["pending_input"] = recovered_payload
                    current_state["finished_at"] = None
                    write_step_metadata(
                        step_dir=step_dir,
                        step_id=step.step_id,
                        capability=step.capability,
                        status="paused",
                        started_at=current_state.get("started_at"),
                        resumed=True,
                        pause_kind="pause_for_input",
                        pending_input=recovered_payload,
                    )

            if current_state.get("status") == "paused":
                pause_kind = str(current_state.get("pause_kind", "") or "pause_for_gate")
                if pause_kind == "pause_for_input":
                    pending_input_payload = dict(current_state.get("pending_input", {}))
                    artifact_path = str(pending_input_payload.get("artifact_path", "") or "").strip()
                    if not artifact_path:
                        raise ValueError(
                            f"pause_for_input resume blocked: no artifact path recorded for {step.step_id}"
                        )
                    artifact_file = Path(artifact_path)
                    if not artifact_file.exists():
                        raise ValueError(f"pause_for_input resume blocked: artifact not found at {artifact_file}")
                    try:
                        artifact_payload = json.loads(artifact_file.read_text(encoding="utf-8"))
                    except Exception as exc:
                        raise ValueError(f"pause_for_input artifact is not valid JSON: {exc}") from exc
                    schema_id = str(pending_input_payload.get("schema_id", "") or "")
                    try:
                        schema = get_schema(schema_id)
                    except KeyError as exc:
                        raise ValueError(f"Unknown pause_for_input schema_id: {schema_id}") from exc
                    jsonschema_validate(instance=artifact_payload, schema=schema)
                    shared_state.setdefault("resumed_inputs", {})[step.step_id] = artifact_payload
                else:
                    paused_outputs = load_step_outputs(root, step.step_id)
                    gate_payload = dict(paused_outputs.get("gate", {}))
                    decision_path = str(gate_payload.get("decision_path", "") or "").strip()
                    if not decision_path:
                        raise ValueError(
                            f"Resume blocked because paused gate {step.step_id} has no decision path recorded."
                        )
                    decision_file = Path(decision_path)
                    if not decision_file.exists():
                        raise ValueError(
                            f"Resume blocked because paused gate {step.step_id} is still waiting for a decision: {decision_file}"
                        )
                    decision_payload = read_json(decision_file)
                    decision_value = str(decision_payload.get("decision", "") or "").strip().lower()
                    if decision_value not in {
                        "approve",
                        "approved",
                        "pass",
                        "passed",
                        "reject",
                        "rejected",
                        "fail",
                        "failed",
                        "quarantine",
                        "quarantined",
                    }:
                        raise ValueError(
                            f"Resume blocked because paused gate {step.step_id} does not have an explicit decision yet."
                        )

            resumed_attempt = bool(current_state.get("started_at") or current_state.get("finished_at"))
            handler = handler_registry.get(step.handler)
            if handler is None:
                raise KeyError(f"No step handler registered for: {step.handler}")

            started_at = timestamp_now()
            current_state["status"] = "running"
            current_state["started_at"] = started_at
            current_state["error"] = ""
            write_step_metadata(
                step_dir=step_dir,
                step_id=step.step_id,
                capability=step.capability,
                status="running",
                started_at=started_at,
                resumed=resumed_attempt,
            )
            update_run_state(run_dir=root, steps=steps_state)

            try:
                context = build_context(step.step_id, step_dir, resumed_attempt, shared_state)
                result = handler(context)
                finished_at = timestamp_now()
                outputs = dict(result.outputs)
                if result.gate:
                    outputs.setdefault("gate", dict(result.gate))
                shared_state["step_outputs"][step.step_id] = outputs
                if result.outputs.get("registry_resolution"):
                    shared_state["registry_resolution"] = result.outputs["registry_resolution"]
                if result.outputs.get("base_metadata"):
                    shared_state["base_metadata"] = result.outputs["base_metadata"]
                if result.outputs.get("produced_objects"):
                    shared_state["produced_objects"] = result.outputs["produced_objects"]
                if result.outputs.get("registry_payloads"):
                    shared_state["registry_payloads"] = result.outputs["registry_payloads"]
                write_step_outputs(step_dir, outputs)
                write_step_artifact_manifest(step_dir=step_dir, extra_artifacts=result.artifacts)

                if result.status == "pause_for_input":
                    write_step_metadata(
                        step_dir=step_dir,
                        step_id=step.step_id,
                        capability=step.capability,
                        status="paused",
                        started_at=started_at,
                        finished_at=finished_at,
                        resumed=resumed_attempt,
                        summary=result.summary,
                        gate=result.gate,
                        pause_kind="pause_for_input",
                        pending_input=result.pending_input,
                    )
                    current_state["status"] = "paused"
                    current_state["finished_at"] = finished_at
                    current_state["error"] = ""
                    current_state["pause_kind"] = "pause_for_input"
                    current_state["gate"] = dict(result.gate)
                    current_state["pending_input"] = _pending_input_to_dict(result.pending_input)
                    update_run_state(
                        run_dir=root,
                        status="paused",
                        failed_step_id="",
                        steps=steps_state,
                        pending_step_id=step.step_id,
                        pending_gate={},
                        pending_input=result.pending_input,
                    )
                    return shared_state

                if result.status == "pause_for_gate":
                    write_step_metadata(
                        step_dir=step_dir,
                        step_id=step.step_id,
                        capability=step.capability,
                        status="paused",
                        started_at=started_at,
                        finished_at=finished_at,
                        resumed=resumed_attempt,
                        summary=result.summary,
                        gate=result.gate,
                        pause_kind="pause_for_gate",
                    )
                    current_state["status"] = "paused"
                    current_state["finished_at"] = finished_at
                    current_state["error"] = ""
                    current_state["pause_kind"] = "pause_for_gate"
                    current_state["gate"] = dict(result.gate)
                    current_state["pending_input"] = {}
                    update_run_state(
                        run_dir=root,
                        status="paused",
                        failed_step_id="",
                        steps=steps_state,
                        pending_step_id=step.step_id,
                        pending_gate=result.gate,
                        pending_input={},
                    )
                    return shared_state

                write_step_metadata(
                    step_dir=step_dir,
                    step_id=step.step_id,
                    capability=step.capability,
                    status="completed",
                    started_at=started_at,
                    finished_at=finished_at,
                    resumed=resumed_attempt,
                    summary=result.summary,
                    gate=result.gate,
                )
                current_state["status"] = "completed"
                current_state["finished_at"] = finished_at
                current_state["error"] = ""
                current_state["pause_kind"] = ""
                current_state["gate"] = dict(result.gate)
                current_state["pending_input"] = {}
                update_run_state(
                    run_dir=root,
                    steps=steps_state,
                    pending_step_id="",
                    pending_gate={},
                    pending_input={},
                )
            except Exception as exc:
                finished_at = timestamp_now()
                write_step_metadata(
                    step_dir=step_dir,
                    step_id=step.step_id,
                    capability=step.capability,
                    status="failed",
                    started_at=started_at,
                    finished_at=finished_at,
                    error=str(exc),
                    resumed=resumed_attempt,
                    gate=current_state.get("gate", {}),
                    pause_kind=str(current_state.get("pause_kind", "") or ""),
                    pending_input=dict(current_state.get("pending_input", {})),
                )
                current_state["status"] = "failed"
                current_state["finished_at"] = finished_at
                current_state["error"] = str(exc)
                current_state["pause_kind"] = ""
                current_state["pending_input"] = {}
                update_run_state(
                    run_dir=root,
                    status="failed",
                    failed_step_id=step.step_id,
                    steps=steps_state,
                    pending_step_id="",
                    pending_gate={},
                    pending_input={},
                )
                raise

        update_run_state(
            run_dir=root,
            status="completed",
            failed_step_id="",
            steps=steps_state,
            pending_step_id="",
            pending_gate={},
            pending_input={},
        )
        return shared_state
    finally:
        if lock_path.exists():
            lock_path.unlink()
