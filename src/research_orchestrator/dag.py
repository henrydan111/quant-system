from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.research_orchestrator.capabilities import validate_capabilities


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DagStepSpec:
    step_id: str
    capability: str
    handler: str
    depends_on: tuple[str, ...] = ()
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.step_id:
            raise ValueError("DagStepSpec.step_id is required")
        validate_capabilities([self.capability])
        if not self.handler:
            raise ValueError(f"DagStepSpec.handler is required for step {self.step_id}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CompiledResearchDag:
    profile_id: str
    run_dir: str
    steps: tuple[DagStepSpec, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.profile_id:
            raise ValueError("CompiledResearchDag.profile_id is required")
        if not self.run_dir:
            raise ValueError("CompiledResearchDag.run_dir is required")
        if not self.steps:
            raise ValueError("CompiledResearchDag.steps cannot be empty")

        seen: set[str] = set()
        step_ids = {step.step_id for step in self.steps}
        for step in self.steps:
            step.validate()
            if step.step_id in seen:
                raise ValueError(f"Duplicate DAG step_id: {step.step_id}")
            seen.add(step.step_id)
            missing = sorted(set(step.depends_on) - step_ids)
            if missing:
                raise ValueError(f"DAG step {step.step_id} depends on missing steps: {missing}")

        self.topological_order()

    def topological_order(self) -> list[DagStepSpec]:
        step_map = {step.step_id: step for step in self.steps}
        remaining = {step.step_id: set(step.depends_on) for step in self.steps}
        ready = [step.step_id for step in self.steps if not remaining[step.step_id]]
        ordered: list[DagStepSpec] = []

        while ready:
            step_id = ready.pop(0)
            ordered.append(step_map[step_id])
            for other_step in self.steps:
                if step_id in remaining[other_step.step_id]:
                    remaining[other_step.step_id].remove(step_id)
                    if not remaining[other_step.step_id]:
                        if other_step.step_id not in [item.step_id for item in ordered] and other_step.step_id not in ready:
                            ready.append(other_step.step_id)

        if len(ordered) != len(self.steps):
            unresolved = sorted(step_id for step_id, deps in remaining.items() if deps)
            raise ValueError(f"DAG contains a cycle or unresolved dependencies: {unresolved}")
        return ordered

    def plan_hash(self) -> str:
        payload = {
            "profile_id": self.profile_id,
            "run_dir": self.run_dir,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": self.metadata,
        }
        return _sha256_text(_json_dumps(payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "run_dir": self.run_dir,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": dict(self.metadata),
        }


@dataclass
class StepExecutionContext:
    request: Any
    profile: Any
    dag: CompiledResearchDag
    step: DagStepSpec
    run_dir: Path
    step_dir: Path
    registry_dirs: dict[str, Path]
    effective_capabilities: list[str]
    effective_capability_metadata: list[dict[str, Any]]
    state: dict[str, Any]
    resumed: bool = False


@dataclass(frozen=True)
class PauseForInputPayload:
    artifact_path: str
    schema_id: str
    description: str
    template_path: str = ""
    expected_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.artifact_path).strip():
            raise ValueError("PauseForInputPayload.artifact_path is required")
        if not str(self.schema_id).strip():
            raise ValueError("PauseForInputPayload.schema_id is required")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["expected_fields"] = list(self.expected_fields)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PauseForInputPayload":
        return cls(
            artifact_path=str(payload.get("artifact_path", "") or ""),
            schema_id=str(payload.get("schema_id", "") or ""),
            description=str(payload.get("description", "") or ""),
            template_path=str(payload.get("template_path", "") or ""),
            expected_fields=tuple(str(item) for item in payload.get("expected_fields", []) or []),
        )


@dataclass(frozen=True)
class StepExecutionResult:
    outputs: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    status: str = "completed"
    gate: dict[str, Any] = field(default_factory=dict)
    pending_input: PauseForInputPayload | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pending_input"] = self.pending_input.to_dict() if self.pending_input is not None else {}
        return payload


@dataclass(frozen=True)
class DagRunState:
    profile_id: str
    run_dir: str
    request_hash: str
    plan_hash: str
    resume_policy: str
    status: str
    failed_step_id: str = ""
    pending_step_id: str = ""
    pending_gate: dict[str, Any] = field(default_factory=dict)
    pending_input: PauseForInputPayload | None = None
    completed_step_count: int = 0
    steps: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pending_input"] = self.pending_input.to_dict() if self.pending_input is not None else {}
        return payload
