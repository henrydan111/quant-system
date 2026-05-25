from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.research_orchestrator._types import AssetRef, ProducedObjectSpec
from src.research_orchestrator.hypothesis import Hypothesis

VALID_RESEARCH_MODES = ("sandbox", "formal")


@dataclass(frozen=True)
class ResearchRequest:
    profile_id: str
    mode: str
    consumes: list[AssetRef] = field(default_factory=list)
    produces: list[ProducedObjectSpec] = field(default_factory=list)
    requested_capabilities: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    run_context: dict[str, Any] = field(default_factory=dict)
    hypothesis: Hypothesis | None = None

    def validate(self) -> None:
        if not self.profile_id:
            raise ValueError("ResearchRequest.profile_id is required")
        if self.mode not in VALID_RESEARCH_MODES:
            raise ValueError(f"Unsupported research mode: {self.mode}")
        for item in self.consumes:
            item.validate()
        for item in self.produces:
            item.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "mode": self.mode,
            "consumes": [item.to_dict() for item in self.consumes],
            "produces": [item.to_dict() for item in self.produces],
            "requested_capabilities": list(self.requested_capabilities),
            "inputs": dict(self.inputs),
            "run_context": dict(self.run_context),
            "hypothesis": self.hypothesis.to_dict() if self.hypothesis is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResearchRequest":
        hypothesis_payload = payload.get("hypothesis")
        return cls(
            profile_id=str(payload.get("profile_id", "") or ""),
            mode=str(payload.get("mode", "") or ""),
            consumes=[AssetRef(**item) for item in payload.get("consumes", [])],
            produces=[ProducedObjectSpec(**item) for item in payload.get("produces", [])],
            requested_capabilities=[str(item) for item in payload.get("requested_capabilities", [])],
            inputs=dict(payload.get("inputs", {})),
            run_context=dict(payload.get("run_context", {})),
            hypothesis=Hypothesis.from_dict(dict(hypothesis_payload)) if hypothesis_payload else None,
        )


@dataclass(frozen=True)
class ResearchRunResult:
    profile_id: str
    mode: str
    run_dir: str
    metadata: dict[str, Any]
    registry_resolution: dict[str, Any]
    produced_objects: list[dict[str, Any]]
    lineage_links: list[dict[str, Any]]
    outputs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
