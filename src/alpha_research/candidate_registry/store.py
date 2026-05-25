"""File-backed candidate registry for research-discovered candidate objects."""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.alpha_research.factor_registry.store import (
    _apply_schema,
    _atomic_write_dataframe,
    _atomic_write_json,
    _build_empty_table,
    _coerce_bool,
    _coerce_float,
    _coerce_int,
    _coerce_string,
    _compute_run_id,
    _hash_object,
    _json_dumps,
    _json_list,
    _latest_non_null,
    _make_temp_path,
    _now_str,
    _sort_with_version,
)


LOGGER = logging.getLogger(__name__)

SCHEMA_VERSION = 1
VALID_STATUSES = (
    "observed",
    "candidate",
    "under_review",
    "promoted",
    "rejected",
    "archived",
    "already_formal",
)

CANDIDATE_MASTER_COLUMNS = [
    "candidate_id",
    "object_name",
    "version",
    "is_current",
    "status",
    "recommended_status",
    "object_type",
    "research_type",
    "theme_id",
    "source_type",
    "source_fields_json",
    "component_ids_json",
    "weights_json",
    "construction_rule",
    "transform_family",
    "transform_params_json",
    "expected_sign",
    "economic_role",
    "coverage_tier",
    "definition_payload_json",
    "definition_hash",
    "linked_formal_factor_id",
    "linked_formal_factor_version",
    "formal_equivalent_factor_id",
    "formal_equivalent_factor_version",
    "first_seen_run_id",
    "last_seen_run_id",
    "latest_run_stage",
    "latest_universe_id",
    "latest_coverage_ratio",
    "latest_rank_icir",
    "latest_positive_validation_folds",
    "latest_total_validation_folds",
    "latest_selection_score",
    "latest_selected_for_recipe",
    "latest_rejection_reason",
    "latest_stitched_relative_excess_return",
    "latest_holdout_relative_excess_return",
    "latest_event_relative_excess_return",
    "latest_avg_turnover",
    "latest_topk",
    "latest_rebalance_days",
    "display_name_zh",
    "notes",
    "review_reason",
    "created_at",
    "updated_at",
]

CANDIDATE_EVIDENCE_COLUMNS = [
    "run_id",
    "run_type",
    "research_type",
    "candidate_id",
    "object_name",
    "version",
    "is_current_at_import",
    "object_type",
    "theme_id",
    "stage",
    "universe_id",
    "coverage_ratio",
    "coverage_tier",
    "mean_rank_ic",
    "rank_icir",
    "positive_validation_folds",
    "total_validation_folds",
    "direction_consistent",
    "max_abs_corr",
    "marginal_rank_icir",
    "selection_score",
    "selected_for_recipe",
    "rejection_reason",
    "stitched_relative_excess_return",
    "positive_excess_folds",
    "holdout_relative_excess_return",
    "worst_max_drawdown",
    "avg_turnover",
    "topk",
    "rebalance_days",
    "event_relative_excess_return",
    "event_max_drawdown",
    "event_avg_turnover",
    "event_trade_count",
    "linked_formal_factor_id",
    "formal_equivalent_factor_id",
    "source_run_dir",
    "evidence_time",
]

RUN_INDEX_COLUMNS = [
    "run_id",
    "run_type",
    "research_type",
    "run_dir",
    "generated_at",
    "theme",
    "stage",
    "artifact_count",
    "status",
    "imported_at",
]

STATUS_HISTORY_COLUMNS = [
    "candidate_id",
    "version",
    "old_status",
    "new_status",
    "reason",
    "source_run_id",
    "changed_at",
]

CANDIDATE_MASTER_SCHEMA = {
    "candidate_id": "string",
    "object_name": "string",
    "version": "Int64",
    "is_current": "boolean",
    "status": "string",
    "recommended_status": "string",
    "object_type": "string",
    "research_type": "string",
    "theme_id": "string",
    "source_type": "string",
    "source_fields_json": "string",
    "component_ids_json": "string",
    "weights_json": "string",
    "construction_rule": "string",
    "transform_family": "string",
    "transform_params_json": "string",
    "expected_sign": "Int64",
    "economic_role": "string",
    "coverage_tier": "string",
    "definition_payload_json": "string",
    "definition_hash": "string",
    "linked_formal_factor_id": "string",
    "linked_formal_factor_version": "Int64",
    "formal_equivalent_factor_id": "string",
    "formal_equivalent_factor_version": "Int64",
    "first_seen_run_id": "string",
    "last_seen_run_id": "string",
    "latest_run_stage": "string",
    "latest_universe_id": "string",
    "latest_coverage_ratio": "Float64",
    "latest_rank_icir": "Float64",
    "latest_positive_validation_folds": "Int64",
    "latest_total_validation_folds": "Int64",
    "latest_selection_score": "Float64",
    "latest_selected_for_recipe": "boolean",
    "latest_rejection_reason": "string",
    "latest_stitched_relative_excess_return": "Float64",
    "latest_holdout_relative_excess_return": "Float64",
    "latest_event_relative_excess_return": "Float64",
    "latest_avg_turnover": "Float64",
    "latest_topk": "Int64",
    "latest_rebalance_days": "Int64",
    "display_name_zh": "string",
    "notes": "string",
    "review_reason": "string",
    "created_at": "string",
    "updated_at": "string",
}

CANDIDATE_EVIDENCE_SCHEMA = {
    "run_id": "string",
    "run_type": "string",
    "research_type": "string",
    "candidate_id": "string",
    "object_name": "string",
    "version": "Int64",
    "is_current_at_import": "boolean",
    "object_type": "string",
    "theme_id": "string",
    "stage": "string",
    "universe_id": "string",
    "coverage_ratio": "Float64",
    "coverage_tier": "string",
    "mean_rank_ic": "Float64",
    "rank_icir": "Float64",
    "positive_validation_folds": "Int64",
    "total_validation_folds": "Int64",
    "direction_consistent": "boolean",
    "max_abs_corr": "Float64",
    "marginal_rank_icir": "Float64",
    "selection_score": "Float64",
    "selected_for_recipe": "boolean",
    "rejection_reason": "string",
    "stitched_relative_excess_return": "Float64",
    "positive_excess_folds": "Int64",
    "holdout_relative_excess_return": "Float64",
    "worst_max_drawdown": "Float64",
    "avg_turnover": "Float64",
    "topk": "Int64",
    "rebalance_days": "Int64",
    "event_relative_excess_return": "Float64",
    "event_max_drawdown": "Float64",
    "event_avg_turnover": "Float64",
    "event_trade_count": "Int64",
    "linked_formal_factor_id": "string",
    "formal_equivalent_factor_id": "string",
    "source_run_dir": "string",
    "evidence_time": "string",
}

RUN_INDEX_SCHEMA = {
    "run_id": "string",
    "run_type": "string",
    "research_type": "string",
    "run_dir": "string",
    "generated_at": "string",
    "theme": "string",
    "stage": "string",
    "artifact_count": "Int64",
    "status": "string",
    "imported_at": "string",
}

STATUS_HISTORY_SCHEMA = {
    "candidate_id": "string",
    "version": "Int64",
    "old_status": "string",
    "new_status": "string",
    "reason": "string",
    "source_run_id": "string",
    "changed_at": "string",
}


def _parse_timestamp(value: Any) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.Timestamp.min
    return pd.Timestamp(parsed)


def _normalize_python_literal(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (list, tuple, dict)):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def _normalize_string_list(value: Any) -> list[str]:
    payload = _normalize_python_literal(value)
    if isinstance(payload, (list, tuple, set)):
        return [_coerce_string(item).strip() for item in payload if _coerce_string(item).strip()]
    text = _coerce_string(payload).strip()
    return [text] if text else []


def _normalize_dict(value: Any) -> dict[str, Any]:
    payload = _normalize_python_literal(value)
    if isinstance(payload, dict):
        return {str(key): payload[key] for key in sorted(payload)}
    return {}


def _theme_component_candidate_id(component_id: str) -> str:
    return f"theme_component::{component_id}"


def _theme_recipe_candidate_id(theme_id: str, recipe_id: str) -> str:
    return f"theme_recipe::{theme_id}::{recipe_id}"


@dataclass(frozen=True)
class CandidateDefinitionSnapshot:
    candidate_id: str
    object_name: str
    object_type: str
    research_type: str
    theme_id: str
    source_type: str
    source_fields_json: str
    component_ids_json: str
    weights_json: str
    construction_rule: str
    transform_family: str
    transform_params_json: str
    expected_sign: int | None
    economic_role: str
    coverage_tier: str
    definition_payload_json: str
    definition_hash: str
    linked_formal_factor_id: str
    linked_formal_factor_version: int | None
    formal_equivalent_factor_id: str
    formal_equivalent_factor_version: int | None
    display_name_zh: str


@dataclass(frozen=True)
class CandidateMasterRecord:
    candidate_id: str
    object_name: str
    version: int
    is_current: bool
    status: str
    recommended_status: str
    object_type: str
    research_type: str
    theme_id: str
    source_type: str
    source_fields_json: str
    component_ids_json: str
    weights_json: str
    construction_rule: str
    transform_family: str
    transform_params_json: str
    expected_sign: int | None
    economic_role: str
    coverage_tier: str
    definition_payload_json: str
    definition_hash: str
    linked_formal_factor_id: str
    linked_formal_factor_version: int | None
    formal_equivalent_factor_id: str
    formal_equivalent_factor_version: int | None
    first_seen_run_id: str
    last_seen_run_id: str
    latest_run_stage: str
    latest_universe_id: str
    latest_coverage_ratio: float | None
    latest_rank_icir: float | None
    latest_positive_validation_folds: int | None
    latest_total_validation_folds: int | None
    latest_selection_score: float | None
    latest_selected_for_recipe: bool | None
    latest_rejection_reason: str
    latest_stitched_relative_excess_return: float | None
    latest_holdout_relative_excess_return: float | None
    latest_event_relative_excess_return: float | None
    latest_avg_turnover: float | None
    latest_topk: int | None
    latest_rebalance_days: int | None
    display_name_zh: str
    notes: str
    review_reason: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CandidateEvidenceRecord:
    run_id: str
    run_type: str
    research_type: str
    candidate_id: str
    object_name: str
    version: int
    is_current_at_import: bool
    object_type: str
    theme_id: str
    stage: str
    universe_id: str
    coverage_ratio: float | None
    coverage_tier: str
    mean_rank_ic: float | None
    rank_icir: float | None
    positive_validation_folds: int | None
    total_validation_folds: int | None
    direction_consistent: bool | None
    max_abs_corr: float | None
    marginal_rank_icir: float | None
    selection_score: float | None
    selected_for_recipe: bool | None
    rejection_reason: str
    stitched_relative_excess_return: float | None
    positive_excess_folds: int | None
    holdout_relative_excess_return: float | None
    worst_max_drawdown: float | None
    avg_turnover: float | None
    topk: int | None
    rebalance_days: int | None
    event_relative_excess_return: float | None
    event_max_drawdown: float | None
    event_avg_turnover: float | None
    event_trade_count: int | None
    linked_formal_factor_id: str
    formal_equivalent_factor_id: str
    source_run_dir: str
    evidence_time: str


@dataclass(frozen=True)
class CandidateRunIndexRecord:
    run_id: str
    run_type: str
    research_type: str
    run_dir: str
    generated_at: str
    theme: str
    stage: str
    artifact_count: int | None
    status: str
    imported_at: str


@dataclass(frozen=True)
class CandidateStatusHistoryRecord:
    candidate_id: str
    version: int
    old_status: str
    new_status: str
    reason: str
    source_run_id: str
    changed_at: str


class CandidateRegistryStore:
    """Manage the candidate registry stored under data/candidate_registry."""

    def __init__(self, root: str | Path, formal_registry_dir: str | Path | None = None):
        self.root = Path(root).resolve()
        project_root = Path(__file__).resolve().parents[3]
        self.formal_registry_dir = (
            Path(formal_registry_dir).resolve()
            if formal_registry_dir is not None
            else (project_root / "data" / "factor_registry").resolve()
        )
        self.metadata_path = self.root / "registry_metadata.json"
        self.candidate_master_path = self.root / "candidate_master.parquet"
        self.candidate_master_csv_path = self.root / "candidate_master.csv"
        self.candidate_evidence_path = self.root / "candidate_evidence.parquet"
        self.candidate_evidence_csv_path = self.root / "candidate_evidence.csv"
        self.run_index_path = self.root / "run_index.parquet"
        self.run_index_csv_path = self.root / "run_index.csv"
        self.status_history_path = self.root / "status_history.parquet"
        self.status_history_csv_path = self.root / "status_history.csv"
        self.review_html_path = self.root / "candidate_registry_review.html"
        self.readme_path = self.root / "README.md"
        self.registry_metadata = {
            "schema_version": SCHEMA_VERSION,
            "last_theme_sync_at": "",
            "theme_run_count": 0,
            "current_candidate_count": 0,
        }
        self.candidate_master = _build_empty_table(CANDIDATE_MASTER_COLUMNS, CANDIDATE_MASTER_SCHEMA)
        self.candidate_evidence = _build_empty_table(CANDIDATE_EVIDENCE_COLUMNS, CANDIDATE_EVIDENCE_SCHEMA)
        self.run_index = _build_empty_table(RUN_INDEX_COLUMNS, RUN_INDEX_SCHEMA)
        self.status_history = _build_empty_table(STATUS_HISTORY_COLUMNS, STATUS_HISTORY_SCHEMA)
        self.load()

    def load(self) -> None:
        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.registry_metadata.update(payload)

        self.candidate_master = self._load_table(
            self.candidate_master_path,
            self.candidate_master_csv_path,
            CANDIDATE_MASTER_COLUMNS,
            CANDIDATE_MASTER_SCHEMA,
        )
        self.candidate_evidence = self._load_table(
            self.candidate_evidence_path,
            self.candidate_evidence_csv_path,
            CANDIDATE_EVIDENCE_COLUMNS,
            CANDIDATE_EVIDENCE_SCHEMA,
        )
        self.run_index = self._load_table(
            self.run_index_path,
            self.run_index_csv_path,
            RUN_INDEX_COLUMNS,
            RUN_INDEX_SCHEMA,
        )
        self.status_history = self._load_table(
            self.status_history_path,
            self.status_history_csv_path,
            STATUS_HISTORY_COLUMNS,
            STATUS_HISTORY_SCHEMA,
        )

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry_metadata["current_candidate_count"] = int(
            self.candidate_master["is_current"].fillna(False).sum()
        )
        self.registry_metadata["theme_run_count"] = int(
            (self.run_index["research_type"] == "theme_strategy").sum()
        )
        _atomic_write_json(self.metadata_path, self.registry_metadata)
        _atomic_write_dataframe(
            _sort_with_version(self.candidate_master, ["candidate_id", "version"]),
            self.candidate_master_path,
            self.candidate_master_csv_path,
        )
        _atomic_write_dataframe(
            _sort_with_version(
                self.candidate_evidence,
                ["evidence_time", "object_type", "candidate_id", "version"],
            ),
            self.candidate_evidence_path,
            self.candidate_evidence_csv_path,
        )
        _atomic_write_dataframe(
            _sort_with_version(self.run_index, ["generated_at", "run_type", "run_id"]),
            self.run_index_path,
            self.run_index_csv_path,
        )
        _atomic_write_dataframe(
            _sort_with_version(self.status_history, ["changed_at", "candidate_id", "version"]),
            self.status_history_path,
            self.status_history_csv_path,
        )
        self.render_html_review()
        temp_path = _make_temp_path(self.readme_path)
        temp_path.write_text(self._build_readme_text(), encoding="utf-8")
        os.replace(temp_path, self.readme_path)

    def import_theme_strategy_run(
        self,
        run_dir: str | Path,
        *,
        include_recipe_objects: bool = False,
    ) -> dict[str, Any]:
        run_dir = Path(run_dir).resolve()
        metadata = self._load_theme_run_metadata(run_dir)
        generated_at = _coerce_string(metadata.get("generated_at")) or self._infer_generated_at(run_dir)
        stage = _coerce_string(metadata.get("stage"))
        status = _coerce_string(metadata.get("status")) or "completed"
        theme_dirs = self._discover_theme_dirs(run_dir)
        if not theme_dirs:
            raise FileNotFoundError(f"No theme artifact directories found under {run_dir}")

        formal_map = self._load_formal_factor_map()
        run_id = _compute_run_id("theme_strategy", run_dir, generated_at)

        evidence_rows: list[CandidateEvidenceRecord] = []
        imported_candidate_ids: set[str] = set()
        component_count = 0
        recipe_count = 0

        for theme_dir in theme_dirs:
            theme_stage = stage or self._normalize_stage_from_theme_dir(theme_dir)
            component_registry = self._read_optional_csv(theme_dir / "component_registry.csv")
            component_card = self._read_optional_csv(theme_dir / "component_card.csv")
            recipe_summary = self._sort_recipe_summary_frame(
                self._read_optional_csv(theme_dir / "signal_recipe_summary.csv")
            )
            event_summary = self._read_optional_csv(theme_dir / "event_driven_variant_summary.csv")
            component_metrics = self._index_rows(component_card, "component_id")

            for row in self._normalize_component_rows(component_registry):
                snapshot = self._build_theme_component_snapshot(row, formal_map)
                version, is_current = self._upsert_snapshot(snapshot, generated_at)
                imported_candidate_ids.add(snapshot.candidate_id)
                component_count += 1
                evidence_rows.append(
                    self._build_theme_component_evidence(
                        run_id=run_id,
                        run_dir=run_dir,
                        generated_at=generated_at,
                        stage=theme_stage,
                        snapshot=snapshot,
                        version=version,
                        is_current=is_current,
                        metric_row=component_metrics.get(snapshot.object_name, {}),
                    )
                )

            event_rows = self._best_event_rows(event_summary)
            if include_recipe_objects:
                for row in self._best_recipe_rows(recipe_summary):
                    snapshot = self._build_theme_recipe_snapshot(row)
                    version, is_current = self._upsert_snapshot(snapshot, generated_at)
                    imported_candidate_ids.add(snapshot.candidate_id)
                    recipe_count += 1
                    evidence_rows.append(
                        self._build_theme_recipe_evidence(
                            run_id=run_id,
                            run_dir=run_dir,
                            generated_at=generated_at,
                            stage=theme_stage,
                            snapshot=snapshot,
                            version=version,
                            is_current=is_current,
                            recipe_row=row,
                            event_row=event_rows.get(snapshot.object_name, {}),
                        )
                    )

        self._replace_run_evidence(run_id, evidence_rows)
        self._upsert_run_index(
            CandidateRunIndexRecord(
                run_id=run_id,
                run_type="theme_strategy",
                research_type="theme_strategy",
                run_dir=str(run_dir),
                generated_at=generated_at,
                theme="|".join(sorted(theme_dir.name for theme_dir in theme_dirs)),
                stage=stage or "|".join(
                    sorted({self._normalize_stage_from_theme_dir(theme_dir) for theme_dir in theme_dirs})
                ),
                artifact_count=_coerce_int(metadata.get("artifact_count")) or self._count_artifacts(run_dir),
                status=status,
                imported_at=_now_str(),
            )
        )
        self.refresh_master_derived_fields()
        self.registry_metadata.update(
            {
                "schema_version": SCHEMA_VERSION,
                "last_theme_sync_at": generated_at,
                "theme_run_count": int((self.run_index["research_type"] == "theme_strategy").sum()),
                "current_candidate_count": int(
                    self.candidate_master["is_current"].fillna(False).sum()
                ),
            }
        )
        return {
            "run_id": run_id,
            "run_type": "theme_strategy",
            "candidate_count": len(imported_candidate_ids),
            "candidate_ids": sorted(imported_candidate_ids),
            "component_count": component_count,
            "recipe_count": recipe_count,
            "theme_count": len(theme_dirs),
        }

    def set_status(
        self,
        *,
        candidate_id: str,
        status: str,
        reason: str,
        version: int | None = None,
        source_run_id: str | None = None,
    ) -> dict[str, Any]:
        normalized = status.strip().lower()
        if normalized not in VALID_STATUSES:
            raise ValueError(f"Unsupported status: {status}")

        index = self._resolve_master_index(candidate_id=candidate_id, version=version)
        changed_at = _now_str()
        old_status = _coerce_string(self.candidate_master.at[index, "status"]) or "observed"
        self.candidate_master.at[index, "status"] = normalized
        self.candidate_master.at[index, "updated_at"] = changed_at
        self.candidate_master.at[index, "review_reason"] = reason
        self.status_history = pd.concat(
            [
                self.status_history,
                _apply_schema(
                    pd.DataFrame(
                        [
                            asdict(
                                CandidateStatusHistoryRecord(
                                    candidate_id=candidate_id,
                                    version=int(self.candidate_master.at[index, "version"]),
                                    old_status=old_status,
                                    new_status=normalized,
                                    reason=reason,
                                    source_run_id=_coerce_string(source_run_id),
                                    changed_at=changed_at,
                                )
                            )
                        ]
                    ),
                    STATUS_HISTORY_COLUMNS,
                    STATUS_HISTORY_SCHEMA,
                ),
            ],
            ignore_index=True,
        )
        return {
            "candidate_id": candidate_id,
            "version": int(self.candidate_master.at[index, "version"]),
            "old_status": old_status,
            "new_status": normalized,
        }

    def export_current(self, output_path: str | Path, *, status: str | None = None) -> int:
        current_df = self.candidate_master[self.candidate_master["is_current"].fillna(False)].copy()
        if status:
            normalized = status.strip().lower()
            if normalized not in VALID_STATUSES:
                raise ValueError(f"Unsupported status: {status}")
            current_df = current_df[current_df["status"] == normalized].copy()
        current_df = _sort_with_version(
            current_df,
            ["object_type", "theme_id", "object_name", "version"],
        )
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() == ".parquet":
            current_df.to_parquet(output_path, index=False)
        else:
            current_df.to_csv(output_path, index=False, encoding="utf-8")
        return len(current_df)

    def render_html_review(self, output_path: str | Path | None = None) -> Path:
        from src.alpha_research.candidate_registry.report import build_candidate_registry_review_html

        target_path = Path(output_path).resolve() if output_path is not None else self.review_html_path
        html_text = build_candidate_registry_review_html(
            registry_metadata=self.registry_metadata,
            candidate_master=self.candidate_master.copy(),
            candidate_evidence=self.candidate_evidence.copy(),
            run_index=self.run_index.copy(),
            status_history=self.status_history.copy(),
        )
        temp_path = _make_temp_path(target_path)
        temp_path.write_text(html_text, encoding="utf-8")
        os.replace(temp_path, target_path)
        return target_path

    def summary_text(self) -> str:
        current_df = self.candidate_master[self.candidate_master["is_current"].fillna(False)].copy()
        status_counts = current_df["status"].fillna("observed").value_counts().sort_index()
        object_counts = current_df["object_type"].fillna("").value_counts().sort_index()
        theme_counts = current_df["theme_id"].fillna("").value_counts().sort_index()
        lines = [f"Current candidates: {len(current_df)}", "", "Status counts:"]
        for status in VALID_STATUSES:
            lines.append(f"  {status}: {int(status_counts.get(status, 0))}")
        lines.append("")
        lines.append("Object type counts:")
        for object_type, count in object_counts.items():
            lines.append(f"  {object_type}: {int(count)}")
        lines.append("")
        lines.append("Theme counts:")
        for theme_id, count in theme_counts.items():
            lines.append(f"  {theme_id}: {int(count)}")
        return "\n".join(lines)

    def refresh_master_derived_fields(self) -> None:
        if self.candidate_master.empty:
            return

        master = self.candidate_master.copy()
        evidence = self.candidate_evidence.copy()
        if not evidence.empty:
            evidence["__evidence_sort"] = pd.to_datetime(evidence["evidence_time"], errors="coerce")
            evidence = evidence.sort_values(["__evidence_sort", "run_id"], kind="stable")

        for index, row in master.iterrows():
            candidate_id = _coerce_string(row["candidate_id"])
            version = _coerce_int(row["version"])
            if version is None:
                continue
            subset = evidence[
                (evidence["candidate_id"] == candidate_id)
                & (evidence["version"] == version)
            ].copy()

            first_seen_run_id = ""
            last_seen_run_id = ""
            latest_run_stage = ""
            latest_universe_id = ""
            latest_coverage_ratio = None
            latest_rank_icir = None
            latest_positive_validation_folds = None
            latest_total_validation_folds = None
            latest_selection_score = None
            latest_selected_for_recipe = None
            latest_rejection_reason = ""
            latest_stitched_relative_excess_return = None
            latest_holdout_relative_excess_return = None
            latest_event_relative_excess_return = None
            latest_avg_turnover = None
            latest_topk = None
            latest_rebalance_days = None

            if not subset.empty:
                first_seen_run_id = _coerce_string(subset.iloc[0]["run_id"])
                last_seen_run_id = _coerce_string(subset.iloc[-1]["run_id"])
                latest_run_stage = _latest_non_null(subset["stage"], _coerce_string) or ""
                latest_universe_id = _latest_non_null(subset["universe_id"], _coerce_string) or ""
                latest_coverage_ratio = _latest_non_null(subset["coverage_ratio"], _coerce_float)
                latest_rank_icir = _latest_non_null(subset["rank_icir"], _coerce_float)
                latest_positive_validation_folds = _latest_non_null(
                    subset["positive_validation_folds"],
                    _coerce_int,
                )
                latest_total_validation_folds = _latest_non_null(
                    subset["total_validation_folds"],
                    _coerce_int,
                )
                latest_selection_score = _latest_non_null(subset["selection_score"], _coerce_float)
                latest_selected_for_recipe = _latest_non_null(
                    subset["selected_for_recipe"],
                    _coerce_bool,
                )
                latest_rejection_reason = _latest_non_null(
                    subset["rejection_reason"],
                    _coerce_string,
                ) or ""
                latest_stitched_relative_excess_return = _latest_non_null(
                    subset["stitched_relative_excess_return"],
                    _coerce_float,
                )
                latest_holdout_relative_excess_return = _latest_non_null(
                    subset["holdout_relative_excess_return"],
                    _coerce_float,
                )
                latest_event_relative_excess_return = _latest_non_null(
                    subset["event_relative_excess_return"],
                    _coerce_float,
                )
                latest_avg_turnover = _latest_non_null(subset["avg_turnover"], _coerce_float)
                latest_topk = _latest_non_null(subset["topk"], _coerce_int)
                latest_rebalance_days = _latest_non_null(subset["rebalance_days"], _coerce_int)

            master.at[index, "first_seen_run_id"] = first_seen_run_id
            master.at[index, "last_seen_run_id"] = last_seen_run_id
            master.at[index, "latest_run_stage"] = latest_run_stage
            master.at[index, "latest_universe_id"] = latest_universe_id
            master.at[index, "latest_coverage_ratio"] = latest_coverage_ratio
            master.at[index, "latest_rank_icir"] = latest_rank_icir
            master.at[index, "latest_positive_validation_folds"] = latest_positive_validation_folds
            master.at[index, "latest_total_validation_folds"] = latest_total_validation_folds
            master.at[index, "latest_selection_score"] = latest_selection_score
            master.at[index, "latest_selected_for_recipe"] = latest_selected_for_recipe
            master.at[index, "latest_rejection_reason"] = latest_rejection_reason
            master.at[index, "latest_stitched_relative_excess_return"] = latest_stitched_relative_excess_return
            master.at[index, "latest_holdout_relative_excess_return"] = latest_holdout_relative_excess_return
            master.at[index, "latest_event_relative_excess_return"] = latest_event_relative_excess_return
            master.at[index, "latest_avg_turnover"] = latest_avg_turnover
            master.at[index, "latest_topk"] = latest_topk
            master.at[index, "latest_rebalance_days"] = latest_rebalance_days
            master.at[index, "recommended_status"] = self._derive_recommended_status(
                object_type=_coerce_string(row["object_type"]),
                formal_equivalent_factor_id=_coerce_string(row["formal_equivalent_factor_id"]),
                selected_for_recipe=latest_selected_for_recipe,
                holdout_relative_excess_return=latest_holdout_relative_excess_return,
                event_relative_excess_return=latest_event_relative_excess_return,
                rejection_reason=latest_rejection_reason,
            )

        self.candidate_master = _apply_schema(master, CANDIDATE_MASTER_COLUMNS, CANDIDATE_MASTER_SCHEMA)

    def _load_table(
        self,
        parquet_path: Path,
        csv_path: Path,
        columns: list[str],
        schema: dict[str, str],
    ) -> pd.DataFrame:
        if parquet_path.exists():
            df = pd.read_parquet(parquet_path)
        elif csv_path.exists():
            df = pd.read_csv(csv_path)
        else:
            return _build_empty_table(columns, schema)
        return _apply_schema(df, columns, schema)

    def _load_theme_run_metadata(self, run_dir: Path) -> dict[str, Any]:
        metadata_path = run_dir / "run_metadata.json"
        if metadata_path.exists():
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        return {}

    def _infer_generated_at(self, run_dir: Path) -> str:
        latest_mtime = max(
            (item.stat().st_mtime for item in run_dir.rglob("*") if item.is_file()),
            default=run_dir.stat().st_mtime if run_dir.exists() else datetime.now().timestamp(),
        )
        return datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M:%S")

    def _count_artifacts(self, run_dir: Path) -> int:
        return sum(1 for item in run_dir.rglob("*") if item.is_file()) if run_dir.exists() else 0

    def _discover_theme_dirs(self, run_dir: Path) -> list[Path]:
        if (run_dir / "component_registry.csv").exists():
            return [run_dir]
        theme_dirs = []
        for child in sorted(run_dir.iterdir()) if run_dir.exists() else []:
            if child.is_dir() and (child / "component_registry.csv").exists():
                theme_dirs.append(child)
        return theme_dirs

    def _normalize_stage_from_theme_dir(self, theme_dir: Path) -> str:
        if (theme_dir / "event_driven_variant_summary.csv").exists():
            return "event_driven"
        if (theme_dir / "signal_recipe_summary.csv").exists():
            return "recipe"
        if (theme_dir / "component_card.csv").exists():
            return "component"
        if (theme_dir / "universe_search_summary.csv").exists():
            return "universe"
        if (theme_dir / "component_registry.csv").exists():
            return "field_audit"
        return "unknown"

    def _read_optional_csv(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def _index_rows(self, df: pd.DataFrame, key_column: str) -> dict[str, dict[str, Any]]:
        if df.empty or key_column not in df.columns:
            return {}
        mapping: dict[str, dict[str, Any]] = {}
        for row in df.to_dict(orient="records"):
            key = _coerce_string(row.get(key_column)).strip()
            if key:
                mapping[key] = row
        return mapping

    def _normalize_component_rows(self, component_registry: pd.DataFrame) -> list[dict[str, Any]]:
        if component_registry.empty:
            return []
        rows = []
        for row in component_registry.to_dict(orient="records"):
            if _coerce_string(row.get("component_id")).strip():
                rows.append(row)
        return rows

    def _sort_recipe_summary_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        working = frame.copy()
        numeric_columns = [
            "stitched_relative_excess_return",
            "positive_excess_folds",
            "holdout_relative_excess_return",
            "worst_max_drawdown",
            "avg_turnover",
        ]
        for column in numeric_columns:
            if column in working.columns:
                working[column] = working[column].map(_coerce_float)
        sort_columns = [column for column in numeric_columns if column in working.columns]
        ascending = [False, False, False, False, True][: len(sort_columns)]
        if sort_columns:
            working = working.sort_values(sort_columns, ascending=ascending, na_position="last", kind="stable")
        return working.reset_index(drop=True)

    def _best_recipe_rows(self, recipe_summary: pd.DataFrame) -> list[dict[str, Any]]:
        if recipe_summary.empty or "recipe_id" not in recipe_summary.columns:
            return []
        rows = []
        for recipe_id, group in recipe_summary.groupby("recipe_id", sort=False):
            best = group.iloc[0].to_dict()
            best["recipe_id"] = recipe_id
            rows.append(best)
        return rows

    def _best_event_rows(self, event_summary: pd.DataFrame) -> dict[str, dict[str, Any]]:
        if event_summary.empty or "recipe_id" not in event_summary.columns:
            return {}
        working = event_summary.copy()
        numeric_columns = ["relative_excess_return", "max_drawdown", "avg_turnover"]
        for column in numeric_columns:
            if column in working.columns:
                working[column] = working[column].map(_coerce_float)
        sort_columns = [column for column in numeric_columns if column in working.columns]
        ascending = [False, False, True][: len(sort_columns)]
        if sort_columns:
            working = working.sort_values(sort_columns, ascending=ascending, na_position="last", kind="stable")
        mapping: dict[str, dict[str, Any]] = {}
        for recipe_id, group in working.groupby("recipe_id", sort=False):
            mapping[_coerce_string(recipe_id)] = group.iloc[0].to_dict()
        return mapping

    def _load_formal_factor_map(self) -> dict[str, dict[str, Any]]:
        parquet_path = self.formal_registry_dir / "factor_master.parquet"
        csv_path = self.formal_registry_dir / "factor_master.csv"
        if parquet_path.exists():
            df = pd.read_parquet(parquet_path)
        elif csv_path.exists():
            df = pd.read_csv(csv_path)
        else:
            return {}
        if "factor_id" not in df.columns:
            return {}
        if "is_current" in df.columns:
            current_mask = df["is_current"].map(_coerce_bool).fillna(False)
            df = df[current_mask].copy()
        mapping = {}
        for row in df.to_dict(orient="records"):
            factor_id = _coerce_string(row.get("factor_id")).strip()
            if factor_id:
                mapping[factor_id] = row
        return mapping

    def _build_theme_component_snapshot(
        self,
        row: dict[str, Any],
        formal_map: dict[str, dict[str, Any]],
    ) -> CandidateDefinitionSnapshot:
        component_id = _coerce_string(row.get("component_id")).strip()
        theme_id = _coerce_string(row.get("theme_id")).strip()
        source_type = _coerce_string(row.get("source_type")).strip()
        source_fields = _normalize_string_list(row.get("source_fields"))
        transform_params = _normalize_dict(row.get("transform_params"))
        factor_name = _coerce_string(transform_params.get("factor_name")).strip()
        linked_formal = formal_map.get(factor_name, {}) if source_type == "factor_alias" and factor_name else {}
        payload = {
            "component_id": component_id,
            "theme_id": theme_id,
            "source_type": source_type,
            "source_fields": source_fields,
            "transform_family": _coerce_string(row.get("transform_family")).strip(),
            "transform_params": transform_params,
            "expected_sign": _coerce_int(row.get("expected_sign")),
            "economic_role": _coerce_string(row.get("economic_role")).strip(),
            "coverage_tier": _coerce_string(row.get("coverage_tier")).strip(),
        }
        payload_json = _json_dumps(payload)
        return CandidateDefinitionSnapshot(
            candidate_id=_theme_component_candidate_id(component_id),
            object_name=component_id,
            object_type="theme_component",
            research_type="theme_strategy",
            theme_id=theme_id,
            source_type=source_type,
            source_fields_json=_json_list(source_fields),
            component_ids_json="[]",
            weights_json="[]",
            construction_rule="",
            transform_family=_coerce_string(row.get("transform_family")).strip(),
            transform_params_json=_json_dumps(transform_params),
            expected_sign=_coerce_int(row.get("expected_sign")),
            economic_role=_coerce_string(row.get("economic_role")).strip(),
            coverage_tier=_coerce_string(row.get("coverage_tier")).strip(),
            definition_payload_json=payload_json,
            definition_hash=hashlib.sha256(f"theme_component|{payload_json}".encode("utf-8")).hexdigest(),
            linked_formal_factor_id=_coerce_string(linked_formal.get("factor_id")).strip(),
            linked_formal_factor_version=_coerce_int(linked_formal.get("version")),
            formal_equivalent_factor_id="",
            formal_equivalent_factor_version=None,
            display_name_zh=component_id,
        )

    def _build_theme_recipe_snapshot(self, row: dict[str, Any]) -> CandidateDefinitionSnapshot:
        recipe_id = _coerce_string(row.get("recipe_id")).strip()
        theme_id = _coerce_string(row.get("theme_id")).strip()
        component_ids = [item for item in _coerce_string(row.get("component_ids")).split("|") if item]
        weights = [
            float(item)
            for item in _coerce_string(row.get("weights")).split("|")
            if item
        ]
        payload = {
            "recipe_id": recipe_id,
            "theme_id": theme_id,
            "component_ids": component_ids,
            "weights": weights,
            "construction_rule": _coerce_string(row.get("construction_rule")).strip(),
        }
        payload_json = _json_dumps(payload)
        return CandidateDefinitionSnapshot(
            candidate_id=_theme_recipe_candidate_id(theme_id, recipe_id),
            object_name=recipe_id,
            object_type="theme_recipe",
            research_type="theme_strategy",
            theme_id=theme_id,
            source_type="recipe",
            source_fields_json="[]",
            component_ids_json=_json_list(component_ids),
            weights_json=_json_list(weights),
            construction_rule=_coerce_string(row.get("construction_rule")).strip(),
            transform_family="",
            transform_params_json="{}",
            expected_sign=None,
            economic_role="",
            coverage_tier="",
            definition_payload_json=payload_json,
            definition_hash=hashlib.sha256(f"theme_recipe|{payload_json}".encode("utf-8")).hexdigest(),
            linked_formal_factor_id="",
            linked_formal_factor_version=None,
            formal_equivalent_factor_id="",
            formal_equivalent_factor_version=None,
            display_name_zh=f"{theme_id}:{recipe_id}",
        )

    def _build_theme_component_evidence(
        self,
        *,
        run_id: str,
        run_dir: Path,
        generated_at: str,
        stage: str,
        snapshot: CandidateDefinitionSnapshot,
        version: int,
        is_current: bool,
        metric_row: dict[str, Any],
    ) -> CandidateEvidenceRecord:
        return CandidateEvidenceRecord(
            run_id=run_id,
            run_type="theme_strategy",
            research_type="theme_strategy",
            candidate_id=snapshot.candidate_id,
            object_name=snapshot.object_name,
            version=version,
            is_current_at_import=is_current,
            object_type=snapshot.object_type,
            theme_id=snapshot.theme_id,
            stage=stage,
            universe_id=_coerce_string(metric_row.get("universe_id")).strip(),
            coverage_ratio=_coerce_float(metric_row.get("coverage_ratio")),
            coverage_tier=_coerce_string(metric_row.get("coverage_tier")).strip() or snapshot.coverage_tier,
            mean_rank_ic=_coerce_float(metric_row.get("mean_rank_ic")),
            rank_icir=_coerce_float(metric_row.get("rank_icir")),
            positive_validation_folds=_coerce_int(metric_row.get("positive_validation_folds")),
            total_validation_folds=_coerce_int(metric_row.get("total_validation_folds")),
            direction_consistent=_coerce_bool(metric_row.get("direction_consistent")),
            max_abs_corr=_coerce_float(metric_row.get("max_abs_corr")),
            marginal_rank_icir=_coerce_float(metric_row.get("marginal_rank_icir")),
            selection_score=_coerce_float(metric_row.get("selection_score")),
            selected_for_recipe=_coerce_bool(metric_row.get("selected_for_recipe")),
            rejection_reason=_coerce_string(metric_row.get("rejection_reason")).strip(),
            stitched_relative_excess_return=None,
            positive_excess_folds=None,
            holdout_relative_excess_return=None,
            worst_max_drawdown=None,
            avg_turnover=None,
            topk=None,
            rebalance_days=None,
            event_relative_excess_return=None,
            event_max_drawdown=None,
            event_avg_turnover=None,
            event_trade_count=None,
            linked_formal_factor_id=snapshot.linked_formal_factor_id,
            formal_equivalent_factor_id=snapshot.formal_equivalent_factor_id,
            source_run_dir=str(run_dir),
            evidence_time=generated_at,
        )

    def _build_theme_recipe_evidence(
        self,
        *,
        run_id: str,
        run_dir: Path,
        generated_at: str,
        stage: str,
        snapshot: CandidateDefinitionSnapshot,
        version: int,
        is_current: bool,
        recipe_row: dict[str, Any],
        event_row: dict[str, Any],
    ) -> CandidateEvidenceRecord:
        return CandidateEvidenceRecord(
            run_id=run_id,
            run_type="theme_strategy",
            research_type="theme_strategy",
            candidate_id=snapshot.candidate_id,
            object_name=snapshot.object_name,
            version=version,
            is_current_at_import=is_current,
            object_type=snapshot.object_type,
            theme_id=snapshot.theme_id,
            stage=stage,
            universe_id=_coerce_string(recipe_row.get("universe_id")).strip(),
            coverage_ratio=None,
            coverage_tier="",
            mean_rank_ic=None,
            rank_icir=None,
            positive_validation_folds=None,
            total_validation_folds=None,
            direction_consistent=None,
            max_abs_corr=None,
            marginal_rank_icir=None,
            selection_score=None,
            selected_for_recipe=None,
            rejection_reason="",
            stitched_relative_excess_return=_coerce_float(recipe_row.get("stitched_relative_excess_return")),
            positive_excess_folds=_coerce_int(recipe_row.get("positive_excess_folds")),
            holdout_relative_excess_return=_coerce_float(recipe_row.get("holdout_relative_excess_return")),
            worst_max_drawdown=_coerce_float(recipe_row.get("worst_max_drawdown")),
            avg_turnover=_coerce_float(recipe_row.get("avg_turnover")),
            topk=_coerce_int(recipe_row.get("topk")),
            rebalance_days=_coerce_int(recipe_row.get("rebalance_days")),
            event_relative_excess_return=_coerce_float(event_row.get("relative_excess_return")),
            event_max_drawdown=_coerce_float(event_row.get("max_drawdown")),
            event_avg_turnover=_coerce_float(event_row.get("avg_turnover")),
            event_trade_count=_coerce_int(event_row.get("trade_count")),
            linked_formal_factor_id="",
            formal_equivalent_factor_id="",
            source_run_dir=str(run_dir),
            evidence_time=generated_at,
        )

    def _upsert_snapshot(
        self,
        snapshot: CandidateDefinitionSnapshot,
        generated_at: str,
    ) -> tuple[int, bool]:
        candidate_view = self.candidate_master[self.candidate_master["candidate_id"] == snapshot.candidate_id]
        current_view = candidate_view[candidate_view["is_current"].fillna(False)]
        matching_view = candidate_view[candidate_view["definition_hash"] == snapshot.definition_hash]
        generated_ts = _parse_timestamp(generated_at)
        current_ts = _parse_timestamp(current_view.iloc[-1]["updated_at"]) if not current_view.empty else pd.Timestamp.min

        if not matching_view.empty:
            target_index = int(matching_view.sort_values("version").index[-1])
            target_is_current = bool(self.candidate_master.at[target_index, "is_current"])
            should_be_current = current_view.empty or generated_ts >= current_ts
            if should_be_current:
                other_current = [idx for idx in current_view.index.tolist() if idx != target_index]
                if other_current:
                    self.candidate_master.loc[other_current, "is_current"] = False
                target_is_current = True
            self._apply_snapshot_to_row(target_index, snapshot, generated_at, is_current=target_is_current)
            return int(self.candidate_master.at[target_index, "version"]), target_is_current

        version = 1 if candidate_view.empty else int(candidate_view["version"].max()) + 1
        should_be_current = current_view.empty or generated_ts >= current_ts
        if should_be_current and not current_view.empty:
            self.candidate_master.loc[current_view.index, "is_current"] = False

        record = CandidateMasterRecord(
            candidate_id=snapshot.candidate_id,
            object_name=snapshot.object_name,
            version=version,
            is_current=should_be_current,
            status="observed" if not snapshot.formal_equivalent_factor_id else "already_formal",
            recommended_status="observed",
            object_type=snapshot.object_type,
            research_type=snapshot.research_type,
            theme_id=snapshot.theme_id,
            source_type=snapshot.source_type,
            source_fields_json=snapshot.source_fields_json,
            component_ids_json=snapshot.component_ids_json,
            weights_json=snapshot.weights_json,
            construction_rule=snapshot.construction_rule,
            transform_family=snapshot.transform_family,
            transform_params_json=snapshot.transform_params_json,
            expected_sign=snapshot.expected_sign,
            economic_role=snapshot.economic_role,
            coverage_tier=snapshot.coverage_tier,
            definition_payload_json=snapshot.definition_payload_json,
            definition_hash=snapshot.definition_hash,
            linked_formal_factor_id=snapshot.linked_formal_factor_id,
            linked_formal_factor_version=snapshot.linked_formal_factor_version,
            formal_equivalent_factor_id=snapshot.formal_equivalent_factor_id,
            formal_equivalent_factor_version=snapshot.formal_equivalent_factor_version,
            first_seen_run_id="",
            last_seen_run_id="",
            latest_run_stage="",
            latest_universe_id="",
            latest_coverage_ratio=None,
            latest_rank_icir=None,
            latest_positive_validation_folds=None,
            latest_total_validation_folds=None,
            latest_selection_score=None,
            latest_selected_for_recipe=None,
            latest_rejection_reason="",
            latest_stitched_relative_excess_return=None,
            latest_holdout_relative_excess_return=None,
            latest_event_relative_excess_return=None,
            latest_avg_turnover=None,
            latest_topk=None,
            latest_rebalance_days=None,
            display_name_zh=snapshot.display_name_zh,
            notes="",
            review_reason="",
            created_at=generated_at,
            updated_at=generated_at,
        )
        self.candidate_master = pd.concat(
            [
                self.candidate_master,
                _apply_schema(
                    pd.DataFrame([asdict(record)]),
                    CANDIDATE_MASTER_COLUMNS,
                    CANDIDATE_MASTER_SCHEMA,
                ),
            ],
            ignore_index=True,
        )
        return version, should_be_current

    def _apply_snapshot_to_row(
        self,
        index: int,
        snapshot: CandidateDefinitionSnapshot,
        generated_at: str,
        *,
        is_current: bool,
    ) -> None:
        existing_display_name = _coerce_string(self.candidate_master.at[index, "display_name_zh"])
        old_updated_at = _coerce_string(self.candidate_master.at[index, "updated_at"])
        effective_updated_at = generated_at if _parse_timestamp(generated_at) >= _parse_timestamp(old_updated_at) else old_updated_at
        self.candidate_master.at[index, "object_name"] = snapshot.object_name
        self.candidate_master.at[index, "is_current"] = is_current
        self.candidate_master.at[index, "object_type"] = snapshot.object_type
        self.candidate_master.at[index, "research_type"] = snapshot.research_type
        self.candidate_master.at[index, "theme_id"] = snapshot.theme_id
        self.candidate_master.at[index, "source_type"] = snapshot.source_type
        self.candidate_master.at[index, "source_fields_json"] = snapshot.source_fields_json
        self.candidate_master.at[index, "component_ids_json"] = snapshot.component_ids_json
        self.candidate_master.at[index, "weights_json"] = snapshot.weights_json
        self.candidate_master.at[index, "construction_rule"] = snapshot.construction_rule
        self.candidate_master.at[index, "transform_family"] = snapshot.transform_family
        self.candidate_master.at[index, "transform_params_json"] = snapshot.transform_params_json
        self.candidate_master.at[index, "expected_sign"] = snapshot.expected_sign
        self.candidate_master.at[index, "economic_role"] = snapshot.economic_role
        self.candidate_master.at[index, "coverage_tier"] = snapshot.coverage_tier
        self.candidate_master.at[index, "definition_payload_json"] = snapshot.definition_payload_json
        self.candidate_master.at[index, "definition_hash"] = snapshot.definition_hash
        self.candidate_master.at[index, "linked_formal_factor_id"] = snapshot.linked_formal_factor_id
        self.candidate_master.at[index, "linked_formal_factor_version"] = snapshot.linked_formal_factor_version
        self.candidate_master.at[index, "formal_equivalent_factor_id"] = snapshot.formal_equivalent_factor_id
        self.candidate_master.at[index, "formal_equivalent_factor_version"] = snapshot.formal_equivalent_factor_version
        self.candidate_master.at[index, "display_name_zh"] = existing_display_name or snapshot.display_name_zh
        self.candidate_master.at[index, "updated_at"] = effective_updated_at

    def _replace_run_evidence(self, run_id: str, evidence_rows: list[CandidateEvidenceRecord]) -> None:
        existing = self.candidate_evidence[self.candidate_evidence["run_id"] != run_id].copy()
        new_df = (
            _apply_schema(
                pd.DataFrame([asdict(record) for record in evidence_rows]),
                CANDIDATE_EVIDENCE_COLUMNS,
                CANDIDATE_EVIDENCE_SCHEMA,
            )
            if evidence_rows
            else _build_empty_table(CANDIDATE_EVIDENCE_COLUMNS, CANDIDATE_EVIDENCE_SCHEMA)
        )
        self.candidate_evidence = pd.concat([existing, new_df], ignore_index=True)
        self.candidate_evidence = _apply_schema(
            self.candidate_evidence,
            CANDIDATE_EVIDENCE_COLUMNS,
            CANDIDATE_EVIDENCE_SCHEMA,
        )

    def _upsert_run_index(self, record: CandidateRunIndexRecord) -> None:
        existing = self.run_index[self.run_index["run_id"] != record.run_id].copy()
        record_df = _apply_schema(pd.DataFrame([asdict(record)]), RUN_INDEX_COLUMNS, RUN_INDEX_SCHEMA)
        self.run_index = pd.concat([existing, record_df], ignore_index=True)
        self.run_index = _apply_schema(self.run_index, RUN_INDEX_COLUMNS, RUN_INDEX_SCHEMA)

    def _resolve_master_index(self, *, candidate_id: str, version: int | None) -> int:
        subset = self.candidate_master[self.candidate_master["candidate_id"] == candidate_id]
        if subset.empty:
            raise KeyError(f"Unknown candidate: {candidate_id}")
        if version is None:
            current = subset[subset["is_current"].fillna(False)]
            if current.empty:
                raise KeyError(f"Candidate {candidate_id} has no current version")
            return int(current.index[-1])
        exact = subset[subset["version"] == int(version)]
        if exact.empty:
            raise KeyError(f"Candidate {candidate_id} v{version} not found")
        return int(exact.index[-1])

    def _derive_recommended_status(
        self,
        *,
        object_type: str,
        formal_equivalent_factor_id: str,
        selected_for_recipe: bool | None,
        holdout_relative_excess_return: float | None,
        event_relative_excess_return: float | None,
        rejection_reason: str,
    ) -> str:
        if formal_equivalent_factor_id:
            return "already_formal"
        if rejection_reason:
            return "observed"
        if object_type == "theme_component":
            return "candidate" if selected_for_recipe else "observed"
        if object_type == "theme_recipe":
            if event_relative_excess_return is not None and event_relative_excess_return > 0:
                return "under_review"
            if holdout_relative_excess_return is not None and holdout_relative_excess_return > 0:
                return "candidate"
            return "observed"
        return "observed"

    def _build_readme_text(self) -> str:
        return "\n".join(
            [
                "# Candidate Registry",
                "",
                "This directory is the unified candidate pool for research outputs.",
                "",
                "- `candidate_master.csv` / `.parquet`: current candidate definitions plus latest evidence summary.",
                "- `candidate_evidence.csv` / `.parquet`: per-run evidence for each candidate.",
                "- `run_index.csv` / `.parquet`: imported research runs.",
                "- `status_history.csv` / `.parquet`: manual status changes.",
                "- `candidate_registry_review.html`: human-readable review page.",
            ]
        )
