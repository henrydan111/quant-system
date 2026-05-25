from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.alpha_research.factor_registry.store import (
    _apply_schema,
    _atomic_write_dataframe,
    _atomic_write_json,
    _build_empty_table,
    _coerce_int,
    _coerce_string,
    _compute_run_id,
    _make_temp_path,
    _now_str,
    _sort_with_version,
)


VALID_TYPED_STATUSES = ("observed", "candidate", "under_review", "approved", "rejected", "archived")

MASTER_COLUMNS = [
    "object_id",
    "object_name",
    "version",
    "is_current",
    "status",
    "recommended_status",
    "object_type",
    "research_profile",
    "definition_payload_json",
    "definition_hash",
    "formal_equivalent_object_id",
    "formal_equivalent_object_version",
    "first_seen_run_id",
    "last_seen_run_id",
    "latest_source_profile",
    "latest_summary_json",
    "display_name_zh",
    "notes",
    "review_reason",
    "created_at",
    "updated_at",
]

EVIDENCE_COLUMNS = [
    "run_id",
    "run_type",
    "research_profile",
    "object_id",
    "object_name",
    "version",
    "is_current_at_import",
    "object_type",
    "summary_json",
    "source_run_dir",
    "evidence_time",
]

RUN_INDEX_COLUMNS = [
    "run_id",
    "run_type",
    "research_profile",
    "run_dir",
    "generated_at",
    "artifact_count",
    "status",
    "imported_at",
]

STATUS_HISTORY_COLUMNS = [
    "object_id",
    "version",
    "old_status",
    "new_status",
    "reason",
    "source_run_id",
    "changed_at",
]

MASTER_SCHEMA = {
    "object_id": "string",
    "object_name": "string",
    "version": "Int64",
    "is_current": "boolean",
    "status": "string",
    "recommended_status": "string",
    "object_type": "string",
    "research_profile": "string",
    "definition_payload_json": "string",
    "definition_hash": "string",
    "formal_equivalent_object_id": "string",
    "formal_equivalent_object_version": "Int64",
    "first_seen_run_id": "string",
    "last_seen_run_id": "string",
    "latest_source_profile": "string",
    "latest_summary_json": "string",
    "display_name_zh": "string",
    "notes": "string",
    "review_reason": "string",
    "created_at": "string",
    "updated_at": "string",
}

EVIDENCE_SCHEMA = {
    "run_id": "string",
    "run_type": "string",
    "research_profile": "string",
    "object_id": "string",
    "object_name": "string",
    "version": "Int64",
    "is_current_at_import": "boolean",
    "object_type": "string",
    "summary_json": "string",
    "source_run_dir": "string",
    "evidence_time": "string",
}

RUN_INDEX_SCHEMA = {
    "run_id": "string",
    "run_type": "string",
    "research_profile": "string",
    "run_dir": "string",
    "generated_at": "string",
    "artifact_count": "Int64",
    "status": "string",
    "imported_at": "string",
}

STATUS_HISTORY_SCHEMA = {
    "object_id": "string",
    "version": "Int64",
    "old_status": "string",
    "new_status": "string",
    "reason": "string",
    "source_run_id": "string",
    "changed_at": "string",
}


@dataclass(frozen=True)
class TypedObjectSnapshot:
    object_id: str
    object_name: str
    object_type: str
    research_profile: str
    definition_payload_json: str
    definition_hash: str
    display_name_zh: str
    notes: str = ""
    formal_equivalent_object_id: str = ""
    formal_equivalent_object_version: int | None = None
    recommended_status: str = "candidate"


@dataclass(frozen=True)
class TypedObjectEvidence:
    run_id: str
    run_type: str
    research_profile: str
    object_id: str
    object_name: str
    version: int
    is_current_at_import: bool
    object_type: str
    summary_json: str
    source_run_dir: str
    evidence_time: str


@dataclass(frozen=True)
class TypedRunIndex:
    run_id: str
    run_type: str
    research_profile: str
    run_dir: str
    generated_at: str
    artifact_count: int | None
    status: str
    imported_at: str


def _default_summary_json(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, ensure_ascii=True, separators=(",", ":"), sort_keys=True, default=str)


def _render_generic_review_html(
    *,
    title: str,
    registry_metadata: dict[str, Any],
    master: pd.DataFrame,
    run_index: pd.DataFrame,
    status_history: pd.DataFrame,
) -> str:
    current_df = master[master["is_current"].fillna(False)].copy().sort_values(
        ["object_type", "recommended_status", "object_name", "version"],
        ascending=[True, True, True, True],
        na_position="last",
    )
    rows = []
    for _, row in current_df.iterrows():
        rows.append(
            "<tr>"
            f"<td><code>{row['object_name']}</code></td>"
            f"<td>{row['object_type']}</td>"
            f"<td>{row['version']}</td>"
            f"<td>{row['recommended_status']}</td>"
            f"<td>{row['status']}</td>"
            f"<td><code>{row['object_id']}</code></td>"
            "</tr>"
        )
    run_rows = []
    for _, row in run_index.sort_values("generated_at", ascending=False).head(12).iterrows():
        run_rows.append(
            "<tr>"
            f"<td>{row['generated_at']}</td>"
            f"<td>{row['research_profile']}</td>"
            f"<td><code>{row['run_id']}</code></td>"
            f"<td>{row['status']}</td>"
            f"<td>{row['artifact_count']}</td>"
            "</tr>"
        )
    status_rows = []
    for _, row in status_history.sort_values("changed_at", ascending=False).head(20).iterrows():
        status_rows.append(
            "<tr>"
            f"<td>{row['changed_at']}</td>"
            f"<td><code>{row['object_id']}</code></td>"
            f"<td>{row['old_status']}</td>"
            f"<td>{row['new_status']}</td>"
            f"<td>{row['reason']}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #1a1a1a; }}
    h1, h2 {{ margin-bottom: 8px; }}
    .meta {{ color: #666; margin-bottom: 18px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #d9d9d9; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    code {{ background: #f7f7f7; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">Schema v{registry_metadata.get("schema_version", "")} | Current objects: {len(current_df)}</div>
  <h2>Current Objects</h2>
  <table>
    <thead><tr><th>Name</th><th>Type</th><th>Version</th><th>Recommended</th><th>Status</th><th>ID</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <h2>Recent Runs</h2>
  <table>
    <thead><tr><th>Generated</th><th>Profile</th><th>Run ID</th><th>Status</th><th>Artifacts</th></tr></thead>
    <tbody>{''.join(run_rows)}</tbody>
  </table>
  <h2>Status History</h2>
  <table>
    <thead><tr><th>Changed</th><th>ID</th><th>Old</th><th>New</th><th>Reason</th></tr></thead>
    <tbody>{''.join(status_rows)}</tbody>
  </table>
</body>
</html>"""


class TypedRegistryStore:
    def __init__(
        self,
        registry_dir: str | Path,
        *,
        registry_slug: str,
        allowed_object_types: tuple[str, ...],
        review_title: str,
    ) -> None:
        self.registry_dir = Path(registry_dir).resolve()
        self.registry_slug = registry_slug
        self.allowed_object_types = tuple(allowed_object_types)
        self.review_title = review_title
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_path = self.registry_dir / "registry_metadata.json"
        self.master_path = self.registry_dir / f"{registry_slug}_master.parquet"
        self.master_csv_path = self.registry_dir / f"{registry_slug}_master.csv"
        self.evidence_path = self.registry_dir / f"{registry_slug}_evidence.parquet"
        self.evidence_csv_path = self.registry_dir / f"{registry_slug}_evidence.csv"
        self.run_index_path = self.registry_dir / "run_index.parquet"
        self.run_index_csv_path = self.registry_dir / "run_index.csv"
        self.status_history_path = self.registry_dir / "status_history.parquet"
        self.status_history_csv_path = self.registry_dir / "status_history.csv"
        self.readme_path = self.registry_dir / "README.md"
        self.review_html_path = self.registry_dir / f"{registry_slug}_review.html"

        self.registry_metadata = self._load_json(self.metadata_path, {"schema_version": 1})
        self.master = self._load_table(self.master_path, self.master_csv_path, MASTER_COLUMNS, MASTER_SCHEMA)
        self.evidence = self._load_table(self.evidence_path, self.evidence_csv_path, EVIDENCE_COLUMNS, EVIDENCE_SCHEMA)
        self.run_index = self._load_table(self.run_index_path, self.run_index_csv_path, RUN_INDEX_COLUMNS, RUN_INDEX_SCHEMA)
        self.status_history = self._load_table(
            self.status_history_path,
            self.status_history_csv_path,
            STATUS_HISTORY_COLUMNS,
            STATUS_HISTORY_SCHEMA,
        )

    def _load_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(default)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return dict(default)

    def _load_table(
        self,
        parquet_path: Path,
        csv_path: Path,
        columns: list[str],
        schema: dict[str, str],
    ) -> pd.DataFrame:
        if parquet_path.exists():
            return _apply_schema(pd.read_parquet(parquet_path), columns, schema)
        if csv_path.exists():
            return _apply_schema(pd.read_csv(csv_path), columns, schema)
        return _build_empty_table(columns, schema)

    def current_records(self) -> pd.DataFrame:
        return self.master[self.master["is_current"].fillna(False)].copy()

    def find_current(
        self,
        *,
        object_type: str,
        object_name: str = "",
        object_id: str = "",
        definition_hash: str = "",
        version: int | None = None,
    ) -> pd.DataFrame:
        current = self.current_records()
        current = current[current["object_type"] == object_type].copy()
        if object_id:
            current = current[current["object_id"] == object_id].copy()
        if object_name:
            current = current[current["object_name"] == object_name].copy()
        if definition_hash:
            current = current[current["definition_hash"] == definition_hash].copy()
        if version is not None:
            current = current[current["version"] == int(version)].copy()
        return current

    def publish_objects(
        self,
        *,
        run_type: str,
        research_profile: str,
        run_dir: str | Path | None,
        generated_at: str,
        objects: list[TypedObjectSnapshot],
        summaries_by_object_id: dict[str, dict[str, Any]] | None = None,
        artifact_count: int | None = None,
        status: str = "completed",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        summaries_by_object_id = summaries_by_object_id or {}
        resolved_run_id = run_id or _compute_run_id(run_type, run_dir, generated_at)
        evidence_rows: list[TypedObjectEvidence] = []
        published_ids: list[str] = []

        for snapshot in objects:
            if snapshot.object_type not in self.allowed_object_types:
                raise ValueError(
                    f"{self.registry_slug} does not accept object type {snapshot.object_type}"
                )
            version, is_current = self._upsert_snapshot(snapshot, generated_at)
            published_ids.append(snapshot.object_id)
            evidence_rows.append(
                TypedObjectEvidence(
                    run_id=resolved_run_id,
                    run_type=run_type,
                    research_profile=research_profile,
                    object_id=snapshot.object_id,
                    object_name=snapshot.object_name,
                    version=version,
                    is_current_at_import=is_current,
                    object_type=snapshot.object_type,
                    summary_json=_default_summary_json(summaries_by_object_id.get(snapshot.object_id)),
                    source_run_dir=str(Path(run_dir).resolve()) if run_dir else "",
                    evidence_time=generated_at,
                )
            )

        self._replace_run_evidence(resolved_run_id, evidence_rows)
        self._upsert_run_index(
            TypedRunIndex(
                run_id=resolved_run_id,
                run_type=run_type,
                research_profile=research_profile,
                run_dir=str(Path(run_dir).resolve()) if run_dir else "",
                generated_at=generated_at,
                artifact_count=artifact_count,
                status=status,
                imported_at=_now_str(),
            )
        )
        self.refresh_master_derived_fields()
        self.registry_metadata.update(
            {
                "schema_version": 1,
                "last_sync_at": generated_at,
                "current_object_count": int(self.current_records().shape[0]),
            }
        )
        return {
            "run_id": resolved_run_id,
            "object_count": len(published_ids),
            "object_ids": published_ids,
        }

    def _upsert_snapshot(self, snapshot: TypedObjectSnapshot, generated_at: str) -> tuple[int, bool]:
        object_view = self.master[self.master["object_id"] == snapshot.object_id]
        current_view = object_view[object_view["is_current"].fillna(False)]
        matching_view = object_view[object_view["definition_hash"] == snapshot.definition_hash]

        if not matching_view.empty:
            index = int(matching_view.sort_values("version").index[-1])
            version = int(self.master.at[index, "version"])
            self._update_master_row(index=index, snapshot=snapshot, generated_at=generated_at)
            self.master.at[index, "is_current"] = True
            if not current_view.empty:
                for current_index in current_view.index:
                    if int(current_index) != index:
                        self.master.at[current_index, "is_current"] = False
            return version, True

        next_version = int(object_view["version"].max()) + 1 if not object_view.empty else 1
        if not current_view.empty:
            self.master.loc[current_view.index, "is_current"] = False

        record = {
            "object_id": snapshot.object_id,
            "object_name": snapshot.object_name,
            "version": next_version,
            "is_current": True,
            "status": "observed" if snapshot.recommended_status == "observed" else "candidate",
            "recommended_status": snapshot.recommended_status,
            "object_type": snapshot.object_type,
            "research_profile": snapshot.research_profile,
            "definition_payload_json": snapshot.definition_payload_json,
            "definition_hash": snapshot.definition_hash,
            "formal_equivalent_object_id": snapshot.formal_equivalent_object_id,
            "formal_equivalent_object_version": snapshot.formal_equivalent_object_version,
            "first_seen_run_id": "",
            "last_seen_run_id": "",
            "latest_source_profile": snapshot.research_profile,
            "latest_summary_json": "{}",
            "display_name_zh": snapshot.display_name_zh or snapshot.object_name,
            "notes": snapshot.notes,
            "review_reason": "",
            "created_at": generated_at,
            "updated_at": generated_at,
        }
        self.master = pd.concat(
            [
                self.master,
                _apply_schema(pd.DataFrame([record]), MASTER_COLUMNS, MASTER_SCHEMA),
            ],
            ignore_index=True,
        )
        return next_version, True

    def _update_master_row(self, *, index: int, snapshot: TypedObjectSnapshot, generated_at: str) -> None:
        self.master.at[index, "object_name"] = snapshot.object_name
        self.master.at[index, "research_profile"] = snapshot.research_profile
        self.master.at[index, "definition_payload_json"] = snapshot.definition_payload_json
        self.master.at[index, "definition_hash"] = snapshot.definition_hash
        self.master.at[index, "recommended_status"] = snapshot.recommended_status
        self.master.at[index, "formal_equivalent_object_id"] = snapshot.formal_equivalent_object_id
        self.master.at[index, "formal_equivalent_object_version"] = snapshot.formal_equivalent_object_version
        self.master.at[index, "display_name_zh"] = snapshot.display_name_zh or snapshot.object_name
        self.master.at[index, "notes"] = snapshot.notes
        self.master.at[index, "updated_at"] = generated_at

    def _replace_run_evidence(self, run_id: str, rows: list[TypedObjectEvidence]) -> None:
        existing = self.evidence[self.evidence["run_id"] != run_id].copy()
        new_df = _apply_schema(pd.DataFrame([asdict(item) for item in rows]), EVIDENCE_COLUMNS, EVIDENCE_SCHEMA)
        self.evidence = pd.concat([existing, new_df], ignore_index=True)

    def _upsert_run_index(self, record: TypedRunIndex) -> None:
        filtered = self.run_index[self.run_index["run_id"] != record.run_id].copy()
        row_df = _apply_schema(pd.DataFrame([asdict(record)]), RUN_INDEX_COLUMNS, RUN_INDEX_SCHEMA)
        self.run_index = pd.concat([filtered, row_df], ignore_index=True)

    def refresh_master_derived_fields(self) -> None:
        if self.master.empty:
            return
        current = self.current_records()
        for index, row in current.iterrows():
            object_id = _coerce_string(row["object_id"])
            evidence = self.evidence[self.evidence["object_id"] == object_id].copy()
            evidence = evidence.sort_values(["evidence_time", "version"])
            if evidence.empty:
                continue
            self.master.at[index, "first_seen_run_id"] = _coerce_string(evidence.iloc[0]["run_id"])
            self.master.at[index, "last_seen_run_id"] = _coerce_string(evidence.iloc[-1]["run_id"])
            self.master.at[index, "latest_source_profile"] = _coerce_string(evidence.iloc[-1]["research_profile"])
            self.master.at[index, "latest_summary_json"] = _coerce_string(evidence.iloc[-1]["summary_json"]) or "{}"
            self.master.at[index, "updated_at"] = _coerce_string(evidence.iloc[-1]["evidence_time"]) or _coerce_string(
                self.master.at[index, "updated_at"]
            )

    def set_status(
        self,
        *,
        object_id: str,
        status: str,
        reason: str,
        version: int | None = None,
        source_run_id: str | None = None,
    ) -> dict[str, Any]:
        normalized = str(status).strip().lower()
        if normalized not in VALID_TYPED_STATUSES:
            raise ValueError(f"Unsupported status: {status}")
        matches = self.master[self.master["object_id"] == object_id].copy()
        if version is None:
            matches = matches[matches["is_current"].fillna(False)].copy()
        else:
            matches = matches[matches["version"] == int(version)].copy()
        if matches.empty:
            raise KeyError(f"Object not found: {object_id}")
        index = int(matches.index[-1])
        old_status = _coerce_string(self.master.at[index, "status"]) or "observed"
        changed_at = _now_str()
        self.master.at[index, "status"] = normalized
        self.master.at[index, "review_reason"] = reason
        self.master.at[index, "updated_at"] = changed_at
        row_df = _apply_schema(
            pd.DataFrame(
                [
                    {
                        "object_id": object_id,
                        "version": int(self.master.at[index, "version"]),
                        "old_status": old_status,
                        "new_status": normalized,
                        "reason": reason,
                        "source_run_id": _coerce_string(source_run_id),
                        "changed_at": changed_at,
                    }
                ]
            ),
            STATUS_HISTORY_COLUMNS,
            STATUS_HISTORY_SCHEMA,
        )
        self.status_history = pd.concat([self.status_history, row_df], ignore_index=True)
        return {
            "object_id": object_id,
            "version": int(self.master.at[index, "version"]),
            "old_status": old_status,
            "new_status": normalized,
        }

    def save(self) -> None:
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.metadata_path, self.registry_metadata)
        _atomic_write_dataframe(
            _sort_with_version(self.master, ["object_type", "object_name", "version"]),
            self.master_path,
            self.master_csv_path,
        )
        _atomic_write_dataframe(
            _sort_with_version(self.evidence, ["evidence_time", "object_id", "version"]),
            self.evidence_path,
            self.evidence_csv_path,
        )
        _atomic_write_dataframe(
            _sort_with_version(self.run_index, ["generated_at", "run_id"]),
            self.run_index_path,
            self.run_index_csv_path,
        )
        _atomic_write_dataframe(
            _sort_with_version(self.status_history, ["changed_at", "object_id", "version"]),
            self.status_history_path,
            self.status_history_csv_path,
        )
        self.render_html_review()
        temp_path = _make_temp_path(self.readme_path)
        temp_path.write_text(self._build_readme_text(), encoding="utf-8")
        os.replace(temp_path, self.readme_path)

    def render_html_review(self) -> Path:
        html_text = _render_generic_review_html(
            title=self.review_title,
            registry_metadata=self.registry_metadata,
            master=self.master.copy(),
            run_index=self.run_index.copy(),
            status_history=self.status_history.copy(),
        )
        temp_path = _make_temp_path(self.review_html_path)
        temp_path.write_text(html_text, encoding="utf-8")
        os.replace(temp_path, self.review_html_path)
        return self.review_html_path

    def _build_readme_text(self) -> str:
        return (
            f"# {self.review_title}\n\n"
            f"- Registry slug: `{self.registry_slug}`\n"
            f"- Allowed object types: `{', '.join(self.allowed_object_types)}`\n"
            f"- Current objects: `{int(self.current_records().shape[0])}`\n"
        )
