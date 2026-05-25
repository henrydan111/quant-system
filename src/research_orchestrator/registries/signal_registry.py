from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.alpha_research.candidate_registry import CandidateRegistryStore
from src.alpha_research.factor_registry.store import _coerce_float, _coerce_int, _coerce_string, _json_dumps
from src.research_orchestrator.registries.typed_store import TypedObjectSnapshot, TypedRegistryStore


def _signal_object_id(theme_id: str, recipe_id: str) -> str:
    return f"signal::theme_recipe::{theme_id}::{recipe_id}"


def _load_theme_run_metadata(run_dir: Path) -> dict[str, Any]:
    metadata_path = run_dir / "run_metadata.json"
    if metadata_path.exists():
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    theme_dirs = [item for item in run_dir.iterdir() if item.is_dir()] if run_dir.exists() else []
    stage = ""
    if any((theme_dir / "event_driven_variant_summary.csv").exists() for theme_dir in theme_dirs):
        stage = "event_driven"
    elif any((theme_dir / "signal_recipe_summary.csv").exists() for theme_dir in theme_dirs):
        stage = "recipe"
    elif any((theme_dir / "component_card.csv").exists() for theme_dir in theme_dirs):
        stage = "component"
    elif any((theme_dir / "universe_search_summary.csv").exists() for theme_dir in theme_dirs):
        stage = "universe"
    elif any((theme_dir / "field_inventory.csv").exists() for theme_dir in theme_dirs):
        stage = "field_audit"
    latest_mtime = max(
        (item.stat().st_mtime for item in run_dir.rglob("*") if item.is_file()),
        default=run_dir.stat().st_mtime if run_dir.exists() else datetime.now().timestamp(),
    )
    return {
        "generated_at": datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "stage": stage,
        "status": "completed",
        "artifact_count": sum(1 for item in run_dir.rglob("*") if item.is_file()) if run_dir.exists() else 0,
    }


class SignalRegistryStore(TypedRegistryStore):
    def __init__(self, registry_dir: str | Path) -> None:
        super().__init__(
            registry_dir,
            registry_slug="signal_registry",
            allowed_object_types=("signal",),
            review_title="Signal Registry Review",
        )

    def import_theme_strategy_run(self, run_dir: str | Path) -> dict[str, Any]:
        run_dir = Path(run_dir).resolve()
        metadata = _load_theme_run_metadata(run_dir)
        generated_at = _coerce_string(metadata.get("generated_at"))
        stage = _coerce_string(metadata.get("stage"))
        theme_dirs = [item for item in run_dir.iterdir() if item.is_dir()]
        objects: list[TypedObjectSnapshot] = []
        summaries: dict[str, dict[str, Any]] = {}
        for theme_dir in theme_dirs:
            recipe_path = theme_dir / "signal_recipe_summary.csv"
            if not recipe_path.exists():
                continue
            event_path = theme_dir / "event_driven_variant_summary.csv"
            recipe_df = pd.read_csv(recipe_path)
            event_df = pd.read_csv(event_path) if event_path.exists() else pd.DataFrame()
            event_map = {
                f"{_coerce_string(row.get('theme_id'))}|{_coerce_string(row.get('recipe_id'))}": row
                for row in event_df.to_dict(orient="records")
            }
            for row in recipe_df.to_dict(orient="records"):
                theme_id = _coerce_string(row.get("theme_id")).strip()
                recipe_id = _coerce_string(row.get("recipe_id")).strip()
                component_ids = [item for item in _coerce_string(row.get("component_ids")).split("|") if item]
                weights = [float(item) for item in _coerce_string(row.get("weights")).split("|") if item]
                payload = {
                    "theme_id": theme_id,
                    "recipe_id": recipe_id,
                    "component_ids": component_ids,
                    "weights": weights,
                    "construction_rule": _coerce_string(row.get("construction_rule")).strip(),
                    "topk": _coerce_int(row.get("topk")),
                    "rebalance_days": _coerce_int(row.get("rebalance_days")),
                }
                payload_json = _json_dumps(payload)
                object_id = _signal_object_id(theme_id, recipe_id)
                definition_hash = hashlib.sha256(
                    f"theme_recipe|{payload_json}".encode("utf-8")
                ).hexdigest()
                objects.append(
                    TypedObjectSnapshot(
                        object_id=object_id,
                        object_name=recipe_id,
                        object_type="signal",
                        research_profile="theme_strategy",
                        definition_payload_json=payload_json,
                        definition_hash=definition_hash,
                        display_name_zh=f"{theme_id}:{recipe_id}",
                        recommended_status="under_review",
                    )
                )
                event_row = event_map.get(f"{theme_id}|{recipe_id}", {})
                summaries[object_id] = {
                    "stage": stage,
                    "theme_id": theme_id,
                    "universe_id": _coerce_string(row.get("universe_id")).strip(),
                    "stitched_relative_excess_return": _coerce_float(row.get("stitched_relative_excess_return")),
                    "positive_excess_folds": _coerce_int(row.get("positive_excess_folds")),
                    "holdout_relative_excess_return": _coerce_float(row.get("holdout_relative_excess_return")),
                    "worst_max_drawdown": _coerce_float(row.get("worst_max_drawdown")),
                    "avg_turnover": _coerce_float(row.get("avg_turnover")),
                    "event_relative_excess_return": _coerce_float(event_row.get("relative_excess_return")),
                    "event_max_drawdown": _coerce_float(event_row.get("max_drawdown")),
                    "event_trade_count": _coerce_int(event_row.get("trade_count")),
                }
        result = self.publish_objects(
            run_type="theme_strategy",
            research_profile="theme_strategy",
            run_dir=run_dir,
            generated_at=generated_at,
            objects=objects,
            summaries_by_object_id=summaries,
            artifact_count=_coerce_int(metadata.get("artifact_count")),
        )
        result["signal_count"] = result["object_count"]
        return result

    def migrate_theme_recipes_from_candidate_registry(self, candidate_registry_dir: str | Path) -> dict[str, Any]:
        candidate_store = CandidateRegistryStore(candidate_registry_dir)
        recipe_master = candidate_store.candidate_master[
            candidate_store.candidate_master["object_type"] == "theme_recipe"
        ].copy()
        if recipe_master.empty:
            return {"migrated_count": 0}

        published = 0
        for _, row in recipe_master.sort_values(["object_name", "version"]).iterrows():
            theme_id = _coerce_string(row.get("theme_id")).strip()
            object_name = _coerce_string(row.get("object_name")).strip()
            object_id = _signal_object_id(theme_id, object_name)
            payload_json = _coerce_string(row.get("definition_payload_json")) or "{}"
            snapshot = TypedObjectSnapshot(
                object_id=object_id,
                object_name=object_name,
                object_type="signal",
                research_profile="theme_strategy",
                definition_payload_json=payload_json,
                definition_hash=_coerce_string(row.get("definition_hash"))
                or hashlib.sha256(f"theme_recipe|{payload_json}".encode("utf-8")).hexdigest(),
                display_name_zh=_coerce_string(row.get("display_name_zh")) or f"{theme_id}:{object_name}",
                recommended_status="under_review",
            )
            evidence_rows = candidate_store.candidate_evidence[
                candidate_store.candidate_evidence["candidate_id"] == row["candidate_id"]
            ].copy()
            summaries = {
                object_id: {
                    "theme_id": theme_id,
                    "stitched_relative_excess_return": _coerce_float(evidence_rows["stitched_relative_excess_return"].dropna().iloc[-1])
                    if not evidence_rows["stitched_relative_excess_return"].dropna().empty
                    else None,
                    "holdout_relative_excess_return": _coerce_float(evidence_rows["holdout_relative_excess_return"].dropna().iloc[-1])
                    if not evidence_rows["holdout_relative_excess_return"].dropna().empty
                    else None,
                    "event_relative_excess_return": _coerce_float(evidence_rows["event_relative_excess_return"].dropna().iloc[-1])
                    if not evidence_rows["event_relative_excess_return"].dropna().empty
                    else None,
                }
            }
            generated_at = _coerce_string(row.get("updated_at")) or _coerce_string(row.get("created_at"))
            run_id = _coerce_string(row.get("last_seen_run_id")) or None
            self.publish_objects(
                run_type="theme_recipe_migration",
                research_profile="theme_strategy",
                run_dir="",
                generated_at=generated_at,
                objects=[snapshot],
                summaries_by_object_id=summaries,
                artifact_count=None,
                status="migrated",
                run_id=run_id,
            )
            published += 1
        return {"migrated_count": published}
