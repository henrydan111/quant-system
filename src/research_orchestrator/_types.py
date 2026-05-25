from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


VALID_OBJECT_TYPES = (
    "universe",
    "label",
    "factor",
    "composite_factor",
    "signal",
    "model",
    "portfolio_template",
    "strategy_candidate",
)


@dataclass(frozen=True)
class AssetRef:
    object_type: str
    object_name: str = ""
    object_id: str = ""
    version: int | None = None
    definition_hash: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    allow_new: bool = False

    def validate(self) -> None:
        if self.object_type not in VALID_OBJECT_TYPES:
            raise ValueError(f"Unsupported asset object_type: {self.object_type}")
        if not self.object_name and not self.object_id and not self.definition_hash and not self.payload:
            raise ValueError("AssetRef must declare object_name, object_id, definition_hash, or payload")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProducedObjectSpec:
    object_type: str
    object_name: str
    object_id: str = ""
    definition_payload: dict[str, Any] = field(default_factory=dict)
    definition_hash: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    linked_inputs: list[dict[str, Any]] = field(default_factory=list)
    preferred_status: str = "candidate"
    review_reason: str = ""

    def validate(self) -> None:
        if self.object_type not in VALID_OBJECT_TYPES:
            raise ValueError(f"Unsupported produced object_type: {self.object_type}")
        if not self.object_name:
            raise ValueError("ProducedObjectSpec.object_name is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
