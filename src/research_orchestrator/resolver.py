from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.alpha_research.candidate_registry import CandidateRegistryStore
from src.alpha_research.factor_registry import FactorRegistryStore
from src.alpha_research.factor_registry.store import _coerce_int, _coerce_string, _json_dumps
from src.research_orchestrator.registries import ModelRegistryStore, SignalRegistryStore, StrategyRegistryStore
from src.research_orchestrator.schema import AssetRef


@dataclass(frozen=True)
class ResolutionEntry:
    requested: dict[str, Any]
    status: str
    source_layer: str
    object_type: str
    canonical_id: str
    version: int | None
    definition_hash: str
    can_publish: bool
    # PR P1.2 (Codex round-5): explicit registry privilege metadata, so reviewers
    # read status/validity directly instead of parsing the source_layer string.
    # Empty for non-factor-registry layers (candidate/signal/model/strategy/new).
    registry_status: str = ""
    approval_validity: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested": dict(self.requested),
            "status": self.status,
            "source_layer": self.source_layer,
            "object_type": self.object_type,
            "canonical_id": self.canonical_id,
            "version": self.version,
            "definition_hash": self.definition_hash,
            "can_publish": self.can_publish,
            "registry_status": self.registry_status,
            "approval_validity": self.approval_validity,
        }


class ResolverHub:
    def __init__(
        self,
        *,
        factor_registry_dir: str | Path,
        candidate_registry_dir: str | Path,
        signal_registry_dir: str | Path,
        model_registry_dir: str | Path,
        strategy_registry_dir: str | Path,
    ) -> None:
        self.factor_store = FactorRegistryStore(factor_registry_dir)
        self.candidate_store = CandidateRegistryStore(candidate_registry_dir)
        self.signal_store = SignalRegistryStore(signal_registry_dir)
        self.model_store = ModelRegistryStore(model_registry_dir)
        self.strategy_store = StrategyRegistryStore(strategy_registry_dir)

    def resolve_assets(
        self,
        *,
        consumes: list[AssetRef],
        mode: str,
        allowed_new_object_types: set[str] | None = None,
        research_profile: str = "",
    ) -> dict[str, Any]:
        allowed_new_object_types = allowed_new_object_types or set()
        entries: list[ResolutionEntry] = []
        for asset in consumes:
            asset.validate()
            entries.append(
                self._resolve_single(
                    asset=asset,
                    mode=mode,
                    allowed_new_object_types=allowed_new_object_types,
                    research_profile=research_profile,
                )
            )
        # PR P1.2 (Codex round-4/5): with draft factors now RESOLVED-but-labeled
        # (not unresolved), keep every non-formal registry layer visible in the
        # summary so nothing silently vanishes. formal_hits stays formal-only.
        factor_registry_layers = (
            "formal",
            "factor_registry_candidate",
            "factor_registry_draft",
            "factor_registry_stale",
            "factor_registry_deprecated",
        )
        return {
            "formal_hits": sum(1 for item in entries if item.source_layer == "formal"),
            "candidate_hits": sum(
                1 for item in entries
                if item.source_layer in {"candidate", "factor_registry_candidate", "signal", "model", "strategy"}
            ),
            "new_objects_created": sum(1 for item in entries if item.source_layer == "new_candidate"),
            "factor_registry_hits_by_layer": {
                layer: sum(1 for item in entries if item.source_layer == layer)
                for layer in factor_registry_layers
            },
            "unresolved_objects": [item.to_dict() for item in entries if item.status == "unresolved"],
            "resolved_objects": [item.to_dict() for item in entries],
        }

    def _resolve_single(
        self,
        *,
        asset: AssetRef,
        mode: str,
        allowed_new_object_types: set[str],
        research_profile: str,
    ) -> ResolutionEntry:
        if asset.object_type in {"factor", "composite_factor"}:
            formal = self._resolve_formal_factor(asset)
            if formal is not None:
                return formal
            candidate = self._resolve_candidate_factor(asset)
            if candidate is not None:
                return candidate
            if mode == "formal" and asset.object_type in allowed_new_object_types and (asset.allow_new or asset.payload):
                return self._create_new_factor_candidate(asset, research_profile)
            return self._unresolved(asset, mode, asset.object_type in allowed_new_object_types)

        if asset.object_type == "signal":
            typed = self._resolve_typed(asset, self.signal_store, "signal")
            if typed is not None:
                return typed
            return self._unresolved(asset, mode, asset.object_type in allowed_new_object_types)

        if asset.object_type == "model":
            typed = self._resolve_typed(asset, self.model_store, "model")
            if typed is not None:
                return typed
            return self._unresolved(asset, mode, asset.object_type in allowed_new_object_types)

        if asset.object_type == "strategy_candidate":
            typed = self._resolve_typed(asset, self.strategy_store, "strategy")
            if typed is not None:
                return typed
            return self._unresolved(asset, mode, asset.object_type in allowed_new_object_types)

        return self._unresolved(asset, mode, asset.object_type in allowed_new_object_types)

    @staticmethod
    def _formal_source_layer(registry_status: str, approval_validity: str) -> str:
        """Map a factor-registry row's (status, approval_validity) to a source_layer.

        PR P1.2 "resolve-but-label" (Codex round-5): the row is ALWAYS resolved
        (so discovery's object_resolver never trips its unresolved hard-fail); only
        the privilege LABEL changes. The formal gate lives in the validation
        consumer's allow-set, which accepts ``formal`` (+ ``factor_registry_candidate``
        under ``allow_candidate_components``) and rejects the rest. Fail-closed: a
        candidate without a valid approval, or any unknown status, is labeled draft.
        """
        valid = approval_validity == "valid"
        if registry_status == "approved":
            return "formal" if valid else "factor_registry_stale"
        if registry_status == "candidate" and valid:
            return "factor_registry_candidate"
        if registry_status == "deprecated":
            return "factor_registry_deprecated"
        return "factor_registry_draft"

    def _resolve_formal_factor(self, asset: AssetRef) -> ResolutionEntry | None:
        current = self.factor_store.factor_master[
            self.factor_store.factor_master["is_current"].fillna(False)
        ].copy()
        if current.empty:
            return None
        matches = current.copy()
        if asset.object_id:
            matches = matches[matches["factor_id"] == asset.object_id].copy()
        elif asset.object_name:
            matches = matches[matches["factor_id"] == asset.object_name].copy()
        if asset.version is not None:
            matches = matches[matches["version"] == int(asset.version)].copy()
        if asset.definition_hash:
            # PR P1.2 (Codex round-5): enforce a requested definition_hash as a REAL
            # filter, not a fallback — a name match with a mismatched hash must NOT
            # resolve here (it returns None and falls through to the candidate
            # registry), closing the same-name-shadows-different-hash path. A pure
            # hash request (no id/name) still resolves registry-wide by hash.
            matches = matches[matches["definition_hash"] == asset.definition_hash].copy()
            if matches.empty and not asset.object_id and not asset.object_name:
                matches = current[current["definition_hash"] == asset.definition_hash].copy()
        if matches.empty:
            return None
        row = matches.sort_values("version").iloc[-1]
        registry_status = (_coerce_string(row.get("status")) or "draft").strip().lower()
        approval_validity = (_coerce_string(row.get("approval_validity")) or "valid").strip().lower()
        return ResolutionEntry(
            requested=asset.to_dict(),
            status="resolved",
            source_layer=self._formal_source_layer(registry_status, approval_validity),
            object_type="composite_factor" if _coerce_string(row.get("factor_kind")) == "composite" else "factor",
            canonical_id=_coerce_string(row.get("factor_id")),
            version=_coerce_int(row.get("version")),
            definition_hash=_coerce_string(row.get("definition_hash")),
            can_publish=False,
            registry_status=registry_status,
            approval_validity=approval_validity,
        )

    def _resolve_candidate_factor(self, asset: AssetRef) -> ResolutionEntry | None:
        current = self.candidate_store.candidate_master[
            self.candidate_store.candidate_master["is_current"].fillna(False)
        ].copy()
        current = current[current["object_type"].isin(["factor", "composite_factor", "theme_component"])].copy()
        if current.empty:
            return None
        matches = current.copy()
        if asset.object_id:
            matches = matches[matches["candidate_id"] == asset.object_id].copy()
        elif asset.object_name:
            matches = matches[matches["object_name"] == asset.object_name].copy()
        if asset.version is not None:
            matches = matches[matches["version"] == int(asset.version)].copy()
        if matches.empty and asset.definition_hash:
            matches = current[current["definition_hash"] == asset.definition_hash].copy()
        if matches.empty:
            return None
        row = matches.sort_values("version").iloc[-1]
        return ResolutionEntry(
            requested=asset.to_dict(),
            status="resolved",
            source_layer="candidate",
            object_type=_coerce_string(row.get("object_type")),
            canonical_id=_coerce_string(row.get("candidate_id")),
            version=_coerce_int(row.get("version")),
            definition_hash=_coerce_string(row.get("definition_hash")),
            can_publish=False,
        )

    def _resolve_typed(self, asset: AssetRef, store, source_layer: str) -> ResolutionEntry | None:
        matches = store.find_current(
            object_type=asset.object_type,
            object_name=asset.object_name,
            object_id=asset.object_id,
            definition_hash=asset.definition_hash,
            version=asset.version,
        )
        if matches.empty:
            return None
        row = matches.sort_values("version").iloc[-1]
        return ResolutionEntry(
            requested=asset.to_dict(),
            status="resolved",
            source_layer=source_layer,
            object_type=asset.object_type,
            canonical_id=_coerce_string(row.get("object_id")),
            version=_coerce_int(row.get("version")),
            definition_hash=_coerce_string(row.get("definition_hash")),
            can_publish=False,
        )

    def _create_new_factor_candidate(self, asset: AssetRef, research_profile: str) -> ResolutionEntry:
        from src.alpha_research.candidate_registry.store import CandidateDefinitionSnapshot

        payload = dict(asset.payload)
        payload_json = _json_dumps(payload)
        definition_hash = asset.definition_hash or hashlib.sha256(
            payload_json.encode("utf-8")
        ).hexdigest()
        candidate_id = asset.object_id or f"{asset.object_type}::{asset.object_name or hashlib.sha256(payload_json.encode('utf-8')).hexdigest()[:12]}"
        snapshot = CandidateDefinitionSnapshot(
            candidate_id=candidate_id,
            object_name=asset.object_name or candidate_id,
            object_type=asset.object_type,
            research_type=research_profile or "research_orchestrator",
            theme_id="",
            source_type="resolver_created",
            source_fields_json="[]",
            component_ids_json="[]",
            weights_json="[]",
            construction_rule="",
            transform_family="",
            transform_params_json="{}",
            expected_sign=None,
            economic_role="",
            coverage_tier="",
            definition_payload_json=payload_json,
            definition_hash=definition_hash,
            linked_formal_factor_id="",
            linked_formal_factor_version=None,
            formal_equivalent_factor_id="",
            formal_equivalent_factor_version=None,
            display_name_zh=asset.object_name or candidate_id,
        )
        version, _ = self.candidate_store._upsert_snapshot(snapshot, generated_at="1970-01-01 00:00:00")
        self.candidate_store.refresh_master_derived_fields()
        return ResolutionEntry(
            requested=asset.to_dict(),
            status="resolved",
            source_layer="new_candidate",
            object_type=asset.object_type,
            canonical_id=candidate_id,
            version=version,
            definition_hash=definition_hash,
            can_publish=True,
        )

    def _unresolved(self, asset: AssetRef, mode: str, can_publish: bool) -> ResolutionEntry:
        return ResolutionEntry(
            requested=asset.to_dict(),
            status="unresolved" if mode == "formal" else "sandbox_unresolved",
            source_layer="",
            object_type=asset.object_type,
            canonical_id="",
            version=None,
            definition_hash=asset.definition_hash,
            can_publish=can_publish,
        )
