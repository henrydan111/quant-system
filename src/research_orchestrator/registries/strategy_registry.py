from __future__ import annotations

from pathlib import Path

from src.research_orchestrator.registries.typed_store import TypedRegistryStore


class StrategyRegistryStore(TypedRegistryStore):
    def __init__(self, registry_dir: str | Path) -> None:
        super().__init__(
            registry_dir,
            registry_slug="strategy_registry",
            allowed_object_types=("strategy_candidate",),
            review_title="Strategy Registry Review",
        )
