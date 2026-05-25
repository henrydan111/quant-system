from __future__ import annotations

from pathlib import Path

from src.research_orchestrator.registries.typed_store import TypedRegistryStore


class ModelRegistryStore(TypedRegistryStore):
    def __init__(self, registry_dir: str | Path) -> None:
        super().__init__(
            registry_dir,
            registry_slug="model_registry",
            allowed_object_types=("model",),
            review_title="Model Registry Review",
        )
