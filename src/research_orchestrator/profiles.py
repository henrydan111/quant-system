from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.research_orchestrator.capabilities import validate_capabilities
from src.research_orchestrator._types import VALID_OBJECT_TYPES
from src.research_orchestrator.dag import CompiledResearchDag

DagBuilderFn = Callable[..., CompiledResearchDag]


@dataclass(frozen=True)
class ResearchProfile:
    profile_id: str
    supported_modes: tuple[str, ...]
    consumes_types: tuple[str, ...]
    produces_types: tuple[str, ...]
    default_capabilities: tuple[str, ...]
    formal_requires_resolver: bool
    dag_builder: DagBuilderFn
    execution_model: str = "dag"

    def validate(self) -> None:
        if not self.profile_id:
            raise ValueError("ResearchProfile.profile_id is required")
        unknown_modes = sorted(set(self.supported_modes) - {"sandbox", "formal"})
        if unknown_modes:
            raise ValueError(f"Unsupported profile modes: {unknown_modes}")
        unknown_consumes = sorted(set(self.consumes_types) - set(VALID_OBJECT_TYPES))
        if unknown_consumes:
            raise ValueError(f"Unsupported consume types: {unknown_consumes}")
        unknown_produces = sorted(set(self.produces_types) - set(VALID_OBJECT_TYPES))
        if unknown_produces:
            raise ValueError(f"Unsupported produce types: {unknown_produces}")
        validate_capabilities(list(self.default_capabilities))
        if self.execution_model != "dag":
            raise ValueError(f"Unsupported execution_model: {self.execution_model}")
        if self.dag_builder is None:
            raise ValueError(f"ResearchProfile.dag_builder is required for {self.profile_id}")


class ProfileRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, ResearchProfile] = {}

    def register(self, profile: ResearchProfile) -> None:
        profile.validate()
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> ResearchProfile:
        if profile_id not in self._profiles:
            raise KeyError(f"Unknown research profile: {profile_id}")
        return self._profiles[profile_id]

    def all_profiles(self) -> dict[str, ResearchProfile]:
        return dict(self._profiles)
