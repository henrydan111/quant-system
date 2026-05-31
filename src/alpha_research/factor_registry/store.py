"""File-backed formal factor registry for the official factor catalog."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from src.alpha_research.factor_library.catalog import (
    get_category_map,
    get_composite_defs,
    get_factor_catalog,
)

LOGGER = logging.getLogger(__name__)

SCHEMA_VERSION = 1
CANDIDATE_SCREENING_GRADES = {"A (Graduated)", "B (Strong IC)"}
VALID_STATUSES = ("draft", "candidate", "approved", "deprecated")
# approval_validity qualifies an `approved` row: is the approval still trustworthy
# against the CURRENT provider/calendar, or has a rebuild invalidated it? Non-approved
# rows are vacuously "valid". Fail-closed: a missing value on an `approved` row is
# treated as requiring revalidation (see FactorRegistryStore._normalize_approval_validity).
VALID_APPROVAL_VALIDITIES = ("valid", "requires_revalidation", "stale")

FACTOR_MASTER_COLUMNS = [
    "factor_id",
    "version",
    "is_current",
    "status",
    "approval_validity",
    "recommended_status",
    "object_type",
    "factor_kind",
    "category",
    "family",
    "expression",
    "components_json",
    "weights_json",
    "negate_json",
    "definition_hash",
    "definition_binding",
    "first_seen_run_id",
    "last_seen_run_id",
    "latest_screening_grade",
    "latest_rank_icir_5d",
    "latest_monotonic",
    "latest_best_decay_horizon",
    "latest_validation_pass_count",
    "latest_selected_fold_count",
    "display_name_zh",
    "notes",
    "deprecated_reason",
    "created_at",
    "updated_at",
]

FACTOR_EVIDENCE_COLUMNS = [
    "run_id",
    "run_type",
    "factor_id",
    "version",
    "is_current_at_import",
    "grade",
    "rank_icir_5d",
    "mean_rank_ic_5d",
    "ic_hit_rate_5d",
    "monotonic",
    "best_decay_horizon",
    "peak_decay_icir",
    "ls_ann_return",
    "validation_pass_count",
    "selected_fold_count",
    "avg_validation_rank_icir",
    "source_run_dir",
    "evidence_time",
]

RUN_INDEX_COLUMNS = [
    "run_id",
    "run_type",
    "run_dir",
    "generated_at",
    "start_date",
    "end_date",
    "benchmark",
    "include_new_data",
    "requested_kernels",
    "effective_kernels",
    "imported_at",
]

STATUS_HISTORY_COLUMNS = [
    "factor_id",
    "version",
    "old_status",
    "new_status",
    "reason",
    "source_run_id",
    "changed_at",
]

FACTOR_MASTER_SCHEMA = {
    "factor_id": "string",
    "version": "Int64",
    "is_current": "boolean",
    "status": "string",
    "approval_validity": "string",
    "recommended_status": "string",
    "object_type": "string",
    "factor_kind": "string",
    "category": "string",
    "family": "string",
    "expression": "string",
    "components_json": "string",
    "weights_json": "string",
    "negate_json": "string",
    "definition_hash": "string",
    "definition_binding": "string",
    "first_seen_run_id": "string",
    "last_seen_run_id": "string",
    "latest_screening_grade": "string",
    "latest_rank_icir_5d": "Float64",
    "latest_monotonic": "boolean",
    "latest_best_decay_horizon": "Int64",
    "latest_validation_pass_count": "Int64",
    "latest_selected_fold_count": "Int64",
    "display_name_zh": "string",
    "notes": "string",
    "deprecated_reason": "string",
    "created_at": "string",
    "updated_at": "string",
}

FACTOR_EVIDENCE_SCHEMA = {
    "run_id": "string",
    "run_type": "string",
    "factor_id": "string",
    "version": "Int64",
    "is_current_at_import": "boolean",
    "grade": "string",
    "rank_icir_5d": "Float64",
    "mean_rank_ic_5d": "Float64",
    "ic_hit_rate_5d": "Float64",
    "monotonic": "boolean",
    "best_decay_horizon": "Int64",
    "peak_decay_icir": "Float64",
    "ls_ann_return": "Float64",
    "validation_pass_count": "Int64",
    "selected_fold_count": "Int64",
    "avg_validation_rank_icir": "Float64",
    "source_run_dir": "string",
    "evidence_time": "string",
}

RUN_INDEX_SCHEMA = {
    "run_id": "string",
    "run_type": "string",
    "run_dir": "string",
    "generated_at": "string",
    "start_date": "string",
    "end_date": "string",
    "benchmark": "string",
    "include_new_data": "boolean",
    "requested_kernels": "string",
    "effective_kernels": "string",
    "imported_at": "string",
}

STATUS_HISTORY_SCHEMA = {
    "factor_id": "string",
    "version": "Int64",
    "old_status": "string",
    "new_status": "string",
    "reason": "string",
    "source_run_id": "string",
    "changed_at": "string",
}


def _json_dumps(payload: Any) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _hash_object(payload: Any) -> str:
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def _json_list(values: list[Any]) -> str:
    return json.dumps(values, ensure_ascii=True, separators=(",", ":"))


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _make_temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(path)
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True, default=str)
    os.replace(temp_path, path)


def _atomic_write_dataframe(df: pd.DataFrame, parquet_path: Path, csv_path: Path) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_tmp = _make_temp_path(parquet_path)
    csv_tmp = _make_temp_path(csv_path)
    df.to_parquet(parquet_tmp, index=False)
    df.to_csv(csv_tmp, index=False, encoding="utf-8")
    os.replace(parquet_tmp, parquet_path)
    os.replace(csv_tmp, csv_path)


def _normalize_run_dir(run_dir: str | Path | None) -> str:
    if run_dir is None:
        return ""
    value = str(run_dir).strip()
    if not value:
        return ""
    if "://" in value:
        return value
    return str(Path(value).resolve())


def _compute_run_id(run_type: str, run_dir: str | Path | None, generated_at: str) -> str:
    payload = f"{run_type}|{_normalize_run_dir(run_dir)}|{generated_at}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _coerce_bool(value: Any) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _coerce_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _coerce_int(value: Any) -> int | None:
    as_float = _coerce_float(value)
    if as_float is None:
        return None
    return int(round(as_float))


def _coerce_string(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _coerce_series(series: pd.Series, dtype: str) -> pd.Series:
    if dtype == "string":
        return series.astype("string")
    if dtype == "Float64":
        return pd.to_numeric(series, errors="coerce").astype("Float64")
    if dtype == "Int64":
        return pd.to_numeric(series, errors="coerce").astype("Int64")
    if dtype == "boolean":
        return series.map(_coerce_bool).astype("boolean")
    return series


def _build_empty_table(columns: list[str], schema: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame({column: pd.Series(dtype=schema[column]) for column in columns})


def _apply_schema(df: pd.DataFrame, columns: list[str], schema: dict[str, str]) -> pd.DataFrame:
    working = df.copy()
    for column in columns:
        if column not in working.columns:
            working[column] = pd.Series([pd.NA] * len(working))
        working[column] = _coerce_series(working[column], schema[column])
    return working[columns]


def _sort_with_version(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    return df.sort_values(columns, kind="stable", na_position="last").reset_index(drop=True)


def _latest_non_null(series: pd.Series, converter=None) -> Any:
    for value in reversed(series.tolist()):
        if value is None or pd.isna(value):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return converter(value) if converter is not None else value
    return None


def _build_catalog_snapshot_uri(catalog_hash: str, composite_hash: str) -> str:
    return f"catalog_sync://snapshot?catalog_hash={catalog_hash}&composite_hash={composite_hash}"


def _resolved_bool(value: Any) -> bool:
    coerced = _coerce_bool(value)
    return bool(coerced) if coerced is not None else False


def _coerce_string_list(series: pd.Series) -> list[str]:
    values = []
    for value in series.tolist():
        text = _coerce_string(value).strip()
        if text:
            values.append(text)
    return values


@dataclass(frozen=True)
class FactorDefinitionSnapshot:
    factor_id: str
    factor_kind: str
    category: str
    family: str
    expression: str
    components_json: str
    weights_json: str
    negate_json: str
    definition_hash: str
    display_name_zh: str


@dataclass(frozen=True)
class FactorMasterRecord:
    factor_id: str
    version: int
    is_current: bool
    status: str
    approval_validity: str
    recommended_status: str
    object_type: str
    factor_kind: str
    category: str
    family: str
    expression: str
    components_json: str
    weights_json: str
    negate_json: str
    definition_hash: str
    definition_binding: str
    first_seen_run_id: str
    last_seen_run_id: str
    latest_screening_grade: str
    latest_rank_icir_5d: float | None
    latest_monotonic: bool | None
    latest_best_decay_horizon: int | None
    latest_validation_pass_count: int | None
    latest_selected_fold_count: int | None
    display_name_zh: str
    notes: str
    deprecated_reason: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class FactorEvidenceRecord:
    run_id: str
    run_type: str
    factor_id: str
    version: int
    is_current_at_import: bool
    grade: str
    rank_icir_5d: float | None
    mean_rank_ic_5d: float | None
    ic_hit_rate_5d: float | None
    monotonic: bool | None
    best_decay_horizon: int | None
    peak_decay_icir: float | None
    ls_ann_return: float | None
    validation_pass_count: int | None
    selected_fold_count: int | None
    avg_validation_rank_icir: float | None
    source_run_dir: str
    evidence_time: str


@dataclass(frozen=True)
class RunIndexRecord:
    run_id: str
    run_type: str
    run_dir: str
    generated_at: str
    start_date: str
    end_date: str
    benchmark: str
    include_new_data: bool | None
    requested_kernels: str
    effective_kernels: str
    imported_at: str


@dataclass(frozen=True)
class StatusHistoryRecord:
    factor_id: str
    version: int
    old_status: str
    new_status: str
    reason: str
    source_run_id: str
    changed_at: str


class FactorRegistryStore:
    """Manage the formal factor registry stored under data/factor_registry."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.metadata_path = self.root / "registry_metadata.json"
        self.factor_master_path = self.root / "factor_master.parquet"
        self.factor_master_csv_path = self.root / "factor_master.csv"
        self.factor_evidence_path = self.root / "factor_evidence.parquet"
        self.factor_evidence_csv_path = self.root / "factor_evidence.csv"
        self.run_index_path = self.root / "run_index.parquet"
        self.run_index_csv_path = self.root / "run_index.csv"
        self.status_history_path = self.root / "status_history.parquet"
        self.status_history_csv_path = self.root / "status_history.csv"
        self.review_html_path = self.root / "factor_registry_review.html"

        self.registry_metadata = {
            "schema_version": SCHEMA_VERSION,
            "catalog_sync_last_at": "",
            "catalog_factor_count": 0,
            "catalog_composite_count": 0,
        }

        self.factor_master = _build_empty_table(FACTOR_MASTER_COLUMNS, FACTOR_MASTER_SCHEMA)
        self.factor_evidence = _build_empty_table(FACTOR_EVIDENCE_COLUMNS, FACTOR_EVIDENCE_SCHEMA)
        self.run_index = _build_empty_table(RUN_INDEX_COLUMNS, RUN_INDEX_SCHEMA)
        self.status_history = _build_empty_table(STATUS_HISTORY_COLUMNS, STATUS_HISTORY_SCHEMA)

        self.current_catalog_hash = ""
        self.current_composite_hash = ""
        self.current_catalog_factor_count = 0
        self.current_catalog_composite_count = 0
        self.load()

    def load(self) -> None:
        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.registry_metadata.update(payload)

        self.factor_master = self._load_table(
            self.factor_master_path,
            self.factor_master_csv_path,
            FACTOR_MASTER_COLUMNS,
            FACTOR_MASTER_SCHEMA,
        )
        self._normalize_approval_validity()
        self.factor_evidence = self._load_table(
            self.factor_evidence_path,
            self.factor_evidence_csv_path,
            FACTOR_EVIDENCE_COLUMNS,
            FACTOR_EVIDENCE_SCHEMA,
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

    def _normalize_approval_validity(self) -> None:
        """Fail-closed backfill of ``approval_validity`` for rows persisted before
        the column existed (PR P1.1). A non-approved row is vacuously ``"valid"``;
        a pre-existing ``approved`` row with no recorded validity is set to
        ``"requires_revalidation"`` — a formal artifact must POSITIVELY attest a
        valid approval, never silently inherit one across a schema upgrade."""
        if self.factor_master.empty:
            return
        validity = self.factor_master["approval_validity"]
        blank = validity.isna() | (validity.astype("string").str.strip().fillna("") == "")
        if not bool(blank.any()):
            return
        status = self.factor_master["status"].astype("string").str.lower().str.strip().fillna("")
        self.factor_master.loc[blank & (status == "approved"), "approval_validity"] = "requires_revalidation"
        self.factor_master.loc[blank & (status != "approved"), "approval_validity"] = "valid"

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.metadata_path, self.registry_metadata)
        _atomic_write_dataframe(
            _sort_with_version(self.factor_master, ["factor_id", "version"]),
            self.factor_master_path,
            self.factor_master_csv_path,
        )
        _atomic_write_dataframe(
            _sort_with_version(self.factor_evidence, ["evidence_time", "run_type", "factor_id", "version"]),
            self.factor_evidence_path,
            self.factor_evidence_csv_path,
        )
        _atomic_write_dataframe(
            _sort_with_version(self.run_index, ["generated_at", "run_type", "run_id"]),
            self.run_index_path,
            self.run_index_csv_path,
        )
        _atomic_write_dataframe(
            _sort_with_version(self.status_history, ["changed_at", "factor_id", "version"]),
            self.status_history_path,
            self.status_history_csv_path,
        )
        self.render_html_review()

    def sync_catalog(
        self,
        *,
        record_run: bool = True,
        generated_at: str | None = None,
    ) -> dict[str, Any]:
        generated_at = generated_at or _now_str()
        snapshots = self._build_catalog_snapshots()
        snapshot_names = {snapshot.factor_id for snapshot in snapshots}

        if not self.factor_master.empty:
            removed_mask = self.factor_master["is_current"].fillna(False) & ~self.factor_master["factor_id"].isin(snapshot_names)
            if removed_mask.any():
                self.factor_master.loc[removed_mask, "is_current"] = False
                self.factor_master.loc[removed_mask, "updated_at"] = generated_at

        for snapshot in snapshots:
            self._upsert_snapshot(snapshot, generated_at)

        if record_run:
            self._record_catalog_sync_run(generated_at)

        self.refresh_master_derived_fields()
        self.registry_metadata.update(
            {
                "schema_version": SCHEMA_VERSION,
                "catalog_sync_last_at": generated_at,
                "catalog_factor_count": self.current_catalog_factor_count,
                "catalog_composite_count": self.current_catalog_composite_count,
            }
        )
        return {
            "generated_at": generated_at,
            "current_factor_count": int(self.factor_master["is_current"].fillna(False).sum()),
            "catalog_factor_count": self.current_catalog_factor_count,
            "catalog_composite_count": self.current_catalog_composite_count,
        }

    def import_screening(self, run_dir: str | Path) -> dict[str, Any]:
        run_dir = Path(run_dir).resolve()
        metadata_path = run_dir / "factor_screening_run_metadata.json"
        report_path = run_dir / "factor_screening_report.csv"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Missing screening metadata: {metadata_path}")
        if not report_path.exists():
            raise FileNotFoundError(f"Missing screening report: {report_path}")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        generated_at = _coerce_string(metadata.get("generated_at")) or _now_str()
        self.sync_catalog(record_run=False, generated_at=generated_at)

        report_df = self._normalize_factor_column(pd.read_csv(report_path))
        factor_ids = report_df["factor"].astype(str).str.strip().tolist()
        self._ensure_known_current_factors(factor_ids)

        run_id = _compute_run_id("screening", run_dir, generated_at)
        current_versions = self._current_version_map()
        version_map, definition_binding = self._resolve_import_versions(
            factor_ids=factor_ids,
            catalog_hash=_coerce_string(metadata.get("catalog_hash")),
            composite_hash=_coerce_string(metadata.get("composite_hash")),
        )

        evidence_rows: list[FactorEvidenceRecord] = []
        for row in report_df.to_dict(orient="records"):
            factor_id = _coerce_string(row.get("factor")).strip()
            version = int(version_map[factor_id])
            evidence_rows.append(
                FactorEvidenceRecord(
                    run_id=run_id,
                    run_type="screening",
                    factor_id=factor_id,
                    version=version,
                    is_current_at_import=current_versions.get(factor_id) == version,
                    grade=_coerce_string(row.get("grade")),
                    rank_icir_5d=_coerce_float(row.get("rank_icir_5d")),
                    mean_rank_ic_5d=_coerce_float(row.get("mean_rank_ic_5d")),
                    ic_hit_rate_5d=_coerce_float(row.get("ic_hit_rate_5d")),
                    monotonic=_coerce_bool(row.get("monotonic")),
                    best_decay_horizon=None,
                    peak_decay_icir=None,
                    ls_ann_return=_coerce_float(row.get("ls_ann_return")),
                    validation_pass_count=None,
                    selected_fold_count=None,
                    avg_validation_rank_icir=None,
                    source_run_dir=str(run_dir),
                    evidence_time=generated_at,
                )
            )
            self._set_definition_binding(factor_id, version, definition_binding, generated_at)

        self._replace_run_evidence(run_id, evidence_rows)
        self._upsert_run_index(
            RunIndexRecord(
                run_id=run_id,
                run_type="screening",
                run_dir=str(run_dir),
                generated_at=generated_at,
                start_date=_coerce_string(metadata.get("start_date")),
                end_date=_coerce_string(metadata.get("end_date")),
                benchmark="",
                include_new_data=_coerce_bool(metadata.get("include_new_data")),
                requested_kernels=_coerce_string(metadata.get("requested_kernels")),
                effective_kernels=_coerce_string(metadata.get("effective_kernels")),
                imported_at=_now_str(),
            )
        )
        self.refresh_master_derived_fields()
        return {
            "run_id": run_id,
            "run_type": "screening",
            "factor_count": len(evidence_rows),
            "definition_binding": definition_binding,
        }

    def import_research(self, run_dir: str | Path) -> dict[str, Any]:
        run_dir = Path(run_dir).resolve()
        metadata_path = run_dir / "run_metadata.json"
        metrics_path = run_dir / "factor_research_metrics.csv"
        decisions_path = run_dir / "factor_selection_decisions.csv"
        selected_path = run_dir / "selected_core_factors_by_fold.csv"
        for path in (metadata_path, metrics_path, decisions_path, selected_path):
            if not path.exists():
                raise FileNotFoundError(f"Missing research artifact: {path}")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        generated_at = _coerce_string(metadata.get("generated_at")) or _now_str()
        self.sync_catalog(record_run=False, generated_at=generated_at)

        metrics_df = self._normalize_factor_column(pd.read_csv(metrics_path))
        decisions_df = self._normalize_factor_column(pd.read_csv(decisions_path))
        selected_df = self._normalize_factor_column(pd.read_csv(selected_path))

        factor_ids = sorted(
            {
                *_coerce_string_list(metrics_df.get("factor", pd.Series(dtype="string"))),
                *_coerce_string_list(decisions_df.get("factor", pd.Series(dtype="string"))),
                *_coerce_string_list(selected_df.get("factor", pd.Series(dtype="string"))),
            }
        )
        self._ensure_known_current_factors(factor_ids)

        upstream_screening = self._load_upstream_screening_metadata(metadata)
        catalog_hash = (
            _coerce_string(metadata.get("screening_catalog_hash"))
            or _coerce_string(upstream_screening.get("catalog_hash"))
        )
        composite_hash = (
            _coerce_string(metadata.get("screening_composite_hash"))
            or _coerce_string(upstream_screening.get("composite_hash"))
        )

        run_id = _compute_run_id("research", run_dir, generated_at)
        current_versions = self._current_version_map()
        version_map, definition_binding = self._resolve_import_versions(
            factor_ids=factor_ids,
            catalog_hash=catalog_hash,
            composite_hash=composite_hash,
        )

        decision_summary = self._build_research_decision_summary(decisions_df, selected_df)
        metrics_map = {
            _coerce_string(row["factor"]): row
            for row in metrics_df.to_dict(orient="records")
            if _coerce_string(row.get("factor"))
        }

        evidence_rows: list[FactorEvidenceRecord] = []
        for factor_id in factor_ids:
            metric_row = metrics_map.get(factor_id, {})
            summary_row = decision_summary.get(factor_id, {})
            version = int(version_map[factor_id])
            evidence_rows.append(
                FactorEvidenceRecord(
                    run_id=run_id,
                    run_type="research",
                    factor_id=factor_id,
                    version=version,
                    is_current_at_import=current_versions.get(factor_id) == version,
                    grade=_coerce_string(metric_row.get("grade")),
                    rank_icir_5d=_coerce_float(metric_row.get("rank_icir_5d")),
                    mean_rank_ic_5d=_coerce_float(metric_row.get("mean_rank_ic_5d")),
                    ic_hit_rate_5d=_coerce_float(metric_row.get("ic_hit_rate_5d")),
                    monotonic=_coerce_bool(metric_row.get("monotonic")),
                    best_decay_horizon=_coerce_int(metric_row.get("best_decay_horizon")),
                    peak_decay_icir=_coerce_float(metric_row.get("peak_decay_icir")),
                    ls_ann_return=_coerce_float(metric_row.get("ls_ann_return")),
                    validation_pass_count=_coerce_int(summary_row.get("validation_pass_count", 0)),
                    selected_fold_count=_coerce_int(summary_row.get("selected_fold_count", 0)),
                    avg_validation_rank_icir=_coerce_float(summary_row.get("avg_validation_rank_icir")),
                    source_run_dir=str(run_dir),
                    evidence_time=generated_at,
                )
            )
            self._set_definition_binding(factor_id, version, definition_binding, generated_at)

        self._replace_run_evidence(run_id, evidence_rows)
        start_date, end_date = self._extract_research_window(metadata, upstream_screening)
        self._upsert_run_index(
            RunIndexRecord(
                run_id=run_id,
                run_type="research",
                run_dir=str(run_dir),
                generated_at=generated_at,
                start_date=start_date,
                end_date=end_date,
                benchmark=_coerce_string(metadata.get("benchmark")),
                include_new_data=_coerce_bool(upstream_screening.get("include_new_data")),
                requested_kernels=(
                    _coerce_string(metadata.get("screening_requested_kernels"))
                    or _coerce_string(metadata.get("kernel_meta", {}).get("requested_kernels"))
                ),
                effective_kernels=(
                    _coerce_string(metadata.get("screening_effective_kernels"))
                    or _coerce_string(metadata.get("kernel_meta", {}).get("effective_kernels"))
                ),
                imported_at=_now_str(),
            )
        )
        self.refresh_master_derived_fields()
        return {
            "run_id": run_id,
            "run_type": "research",
            "factor_count": len(evidence_rows),
            "definition_binding": definition_binding,
        }

    def set_status(
        self,
        *,
        factor_id: str,
        status: str,
        reason: str,
        version: int | None = None,
        source_run_id: str | None = None,
        promotion_evidence: Mapping[str, Any] | None = None,
        current_git_sha: str | None = None,
    ) -> dict[str, Any]:
        status = status.strip().lower()
        if status not in VALID_STATUSES:
            raise ValueError(f"Unsupported status: {status}")

        # Writer gate (PR P1.1): a transition to a PRIVILEGED status ("approved")
        # is refused unless promotion_evidence proves an INDEPENDENT PIT-correct
        # reproduction AND passes the lint/parity/clean-tree/git-sha checks, with a
        # MANDATORY current_git_sha binding the approval to a committed HEAD. Mirrors
        # StrategyRegistryStore.set_status. Non-privileged transitions are unchanged.
        # Lazy import: store.py lives in alpha_research, release_gate in
        # research_orchestrator — importing at call time avoids a module-load cycle.
        from src.research_orchestrator.release_gate import (
            PRIVILEGED_REGISTRY_STATUSES,
            PromotionGateError,
            assert_promotion_artifact_eligible,
        )

        if status in PRIVILEGED_REGISTRY_STATUSES:
            if not current_git_sha:
                raise PromotionGateError(
                    f"Promotion gate blocked factor:{factor_id}: current_git_sha is "
                    f"required for a privileged factor-registry status transition "
                    f"(binds the approval to a committed HEAD)"
                )
            artifact = dict(promotion_evidence or {})
            # Force (NOT setdefault) the transition status into the artifact: a
            # caller-supplied promotion_status="draft"/"candidate" would otherwise
            # make the gate evaluate the artifact as non-privileged and trivially
            # pass — an approval bypass (GPT cross-review P0).
            artifact["promotion_status"] = status
            assert_promotion_artifact_eligible(
                artifact,
                current_git_sha=current_git_sha,
                artifact_label=f"factor:{factor_id}",
            )

        index = self._resolve_master_index(factor_id=factor_id, version=version)
        changed_at = _now_str()
        old_status = _coerce_string(self.factor_master.at[index, "status"]) or "draft"

        self.factor_master.at[index, "status"] = status
        self.factor_master.at[index, "updated_at"] = changed_at
        if status in PRIVILEGED_REGISTRY_STATUSES:
            # The gate above passed, so this is a fresh, valid approval.
            self.factor_master.at[index, "approval_validity"] = "valid"
        if status == "deprecated":
            self.factor_master.at[index, "deprecated_reason"] = reason
        elif old_status == "deprecated":
            self.factor_master.at[index, "deprecated_reason"] = ""

        record = StatusHistoryRecord(
            factor_id=factor_id,
            version=int(self.factor_master.at[index, "version"]),
            old_status=old_status,
            new_status=status,
            reason=reason,
            source_run_id=_coerce_string(source_run_id),
            changed_at=changed_at,
        )
        self.status_history = pd.concat(
            [self.status_history, _apply_schema(pd.DataFrame([asdict(record)]), STATUS_HISTORY_COLUMNS, STATUS_HISTORY_SCHEMA)],
            ignore_index=True,
        )
        return {
            "factor_id": factor_id,
            "version": int(self.factor_master.at[index, "version"]),
            "old_status": old_status,
            "new_status": status,
        }

    def set_approval_validity(
        self,
        *,
        factor_id: str,
        validity: str,
        reason: str,
        version: int | None = None,
    ) -> dict[str, Any]:
        """Update ``approval_validity`` on a row (e.g. provider-rebuild drift ->
        "stale"). Records a status_history entry (lifecycle status unchanged; the
        reason documents the validity transition). The drift->stale path is not
        wired into provider-rebuild detection in Phase 1."""
        validity = validity.strip().lower()
        if validity not in VALID_APPROVAL_VALIDITIES:
            raise ValueError(f"Unsupported approval_validity: {validity}")
        index = self._resolve_master_index(factor_id=factor_id, version=version)
        changed_at = _now_str()
        current_status = _coerce_string(self.factor_master.at[index, "status"]) or "draft"
        old_validity = _coerce_string(self.factor_master.at[index, "approval_validity"]) or "valid"
        # This method is the drift/downgrade path (valid -> requires_revalidation /
        # stale). Re-affirming an APPROVED row back to "valid" would re-open it as a
        # formal factor WITHOUT the promotion gate — refuse it (GPT cross-review P0).
        # Re-validation must go through set_status(status="approved", promotion_evidence=...,
        # current_git_sha=...). Non-approved rows' validity is cosmetic, so unrestricted.
        if current_status == "approved" and validity == "valid":
            raise ValueError(
                f"cannot set approval_validity='valid' on approved factor:{factor_id} via "
                f"set_approval_validity; re-affirm through the promotion gate "
                f"(set_status(status='approved', promotion_evidence=..., current_git_sha=...)). "
                f"Downgrades (valid->requires_revalidation/stale) are allowed."
            )
        self.factor_master.at[index, "approval_validity"] = validity
        self.factor_master.at[index, "updated_at"] = changed_at
        record = StatusHistoryRecord(
            factor_id=factor_id,
            version=int(self.factor_master.at[index, "version"]),
            old_status=current_status,
            new_status=current_status,
            reason=f"approval_validity {old_validity}->{validity}: {reason}",
            source_run_id="",
            changed_at=changed_at,
        )
        self.status_history = pd.concat(
            [self.status_history, _apply_schema(pd.DataFrame([asdict(record)]), STATUS_HISTORY_COLUMNS, STATUS_HISTORY_SCHEMA)],
            ignore_index=True,
        )
        return {
            "factor_id": factor_id,
            "version": int(self.factor_master.at[index, "version"]),
            "old_approval_validity": old_validity,
            "new_approval_validity": validity,
        }

    def export_current(
        self,
        output_path: str | Path,
        *,
        status: str | None = None,
        include_invalid: bool = False,
    ) -> int:
        current_df = self.factor_master[self.factor_master["is_current"].fillna(False)].copy()
        if status:
            normalized = status.strip().lower()
            if normalized not in VALID_STATUSES:
                raise ValueError(f"Unsupported status: {status}")
            current_df = current_df[current_df["status"] == normalized].copy()
            # Fail-closed (PR P1.1): an "approved" export is the deployable set, so it
            # must exclude approvals invalidated by a provider rebuild unless the
            # caller explicitly asks for stale rows (audit/review export).
            if normalized == "approved" and not include_invalid:
                current_df = current_df[current_df["approval_validity"] == "valid"].copy()

        current_df = _sort_with_version(current_df, ["factor_kind", "category", "factor_id", "version"])
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() == ".parquet":
            current_df.to_parquet(output_path, index=False)
        else:
            current_df.to_csv(output_path, index=False, encoding="utf-8")
        return len(current_df)

    def render_html_review(self, output_path: str | Path | None = None) -> Path:
        from src.alpha_research.factor_registry.report import build_factor_registry_review_html

        target_path = Path(output_path).resolve() if output_path is not None else self.review_html_path
        html_text = build_factor_registry_review_html(
            registry_metadata=self.registry_metadata,
            factor_master=self.factor_master.copy(),
            factor_evidence=self.factor_evidence.copy(),
            run_index=self.run_index.copy(),
            status_history=self.status_history.copy(),
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = _make_temp_path(target_path)
        temp_path.write_text(html_text, encoding="utf-8")
        os.replace(temp_path, target_path)
        return target_path

    def summary_text(self) -> str:
        current_df = self.factor_master[self.factor_master["is_current"].fillna(False)].copy()
        status_counts = current_df["status"].fillna("draft").value_counts().sort_index()
        family_counts = current_df["family"].fillna("").value_counts().sort_index()
        category_counts = current_df["category"].fillna("").value_counts().sort_index()

        lines = [
            f"Current formal factors: {len(current_df)}",
            "",
            "Status counts:",
        ]
        for status in VALID_STATUSES:
            lines.append(f"  {status}: {int(status_counts.get(status, 0))}")
        lines.append("")
        lines.append("Family counts:")
        for family, count in family_counts.items():
            lines.append(f"  {family}: {int(count)}")
        lines.append("")
        lines.append("Category counts:")
        for category, count in category_counts.items():
            lines.append(f"  {category}: {int(count)}")
        return "\n".join(lines)

    def refresh_master_derived_fields(self) -> None:
        if self.factor_master.empty:
            return

        master = self.factor_master.copy()
        evidence = self.factor_evidence.copy()
        if not evidence.empty:
            evidence["__evidence_sort"] = pd.to_datetime(evidence["evidence_time"], errors="coerce")
            evidence = evidence.sort_values(["__evidence_sort", "run_id"], kind="stable")

        for index, row in master.iterrows():
            factor_id = _coerce_string(row["factor_id"])
            version = _coerce_int(row["version"])
            if version is None:
                continue
            subset = evidence[
                (evidence["factor_id"] == factor_id)
                & (evidence["version"] == version)
            ].copy()

            first_seen_run_id = ""
            last_seen_run_id = ""
            latest_screening_grade = ""
            latest_rank_icir_5d = None
            latest_monotonic = None
            latest_best_decay_horizon = None
            latest_validation_pass_count = None
            latest_selected_fold_count = None

            if not subset.empty:
                first_seen_run_id = _coerce_string(subset.iloc[0]["run_id"])
                last_seen_run_id = _coerce_string(subset.iloc[-1]["run_id"])
                screening_subset = subset[subset["run_type"] == "screening"]
                if not screening_subset.empty:
                    latest_screening_grade = _coerce_string(screening_subset.iloc[-1]["grade"])
                analysis_subset = subset[subset["run_type"].isin(["screening", "research"])]
                if not analysis_subset.empty:
                    latest_rank_icir_5d = _latest_non_null(analysis_subset["rank_icir_5d"], _coerce_float)
                    latest_monotonic = _latest_non_null(analysis_subset["monotonic"], _coerce_bool)
                    latest_best_decay_horizon = _latest_non_null(
                        analysis_subset["best_decay_horizon"],
                        _coerce_int,
                    )
                    latest_validation_pass_count = _latest_non_null(
                        analysis_subset["validation_pass_count"],
                        _coerce_int,
                    )
                    latest_selected_fold_count = _latest_non_null(
                        analysis_subset["selected_fold_count"],
                        _coerce_int,
                    )

            master.at[index, "first_seen_run_id"] = first_seen_run_id
            master.at[index, "last_seen_run_id"] = last_seen_run_id
            master.at[index, "latest_screening_grade"] = latest_screening_grade
            master.at[index, "latest_rank_icir_5d"] = latest_rank_icir_5d
            master.at[index, "latest_monotonic"] = latest_monotonic
            master.at[index, "latest_best_decay_horizon"] = latest_best_decay_horizon
            master.at[index, "latest_validation_pass_count"] = latest_validation_pass_count
            master.at[index, "latest_selected_fold_count"] = latest_selected_fold_count
            master.at[index, "recommended_status"] = self._derive_recommended_status(
                latest_screening_grade=latest_screening_grade,
                latest_validation_pass_count=latest_validation_pass_count,
                latest_selected_fold_count=latest_selected_fold_count,
            )

        self.factor_master = _apply_schema(master, FACTOR_MASTER_COLUMNS, FACTOR_MASTER_SCHEMA)

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

    def _build_catalog_snapshots(self) -> list[FactorDefinitionSnapshot]:
        from src.alpha_research.factor_library.catalog import (
            get_industry_relative_defs,
        )
        catalog = get_factor_catalog(include_new_data=True)
        composite_defs = get_composite_defs()
        industry_rel_defs = get_industry_relative_defs()
        category_map = get_category_map()

        self.current_catalog_hash = _hash_object(catalog)
        self.current_composite_hash = _hash_object(composite_defs)
        self.current_catalog_factor_count = len(catalog)
        self.current_catalog_composite_count = len(composite_defs)

        snapshots: list[FactorDefinitionSnapshot] = []
        for factor_id, expression in catalog.items():
            expression_text = _coerce_string(expression)
            snapshots.append(
                FactorDefinitionSnapshot(
                    factor_id=factor_id,
                    factor_kind="base",
                    category=_coerce_string(category_map.get(factor_id, "Other")),
                    family=factor_id.split("_")[0],
                    expression=expression_text,
                    components_json="[]",
                    weights_json="[]",
                    negate_json="[]",
                    definition_hash=hashlib.sha256(
                        f"base|{factor_id}|{expression_text}".encode("utf-8")
                    ).hexdigest(),
                    display_name_zh=factor_id,
                )
            )

        for definition in composite_defs:
            factor_id = _coerce_string(definition["name"])
            components = [_coerce_string(item) for item in definition.get("components", [])]
            if not components:
                raise ValueError(f"Composite factor {factor_id} is missing components")
            if definition.get("weights") is None:
                effective_weights = [round(1.0 / len(components), 12)] * len(components)
            else:
                effective_weights = [float(item) for item in definition.get("weights", [])]
            if definition.get("negate") is None:
                effective_negate = [False] * len(components)
            else:
                effective_negate = [bool(item) for item in definition.get("negate", [])]
            if len(effective_weights) != len(components):
                raise ValueError(f"Composite factor {factor_id} has mismatched weights")
            if len(effective_negate) != len(components):
                raise ValueError(f"Composite factor {factor_id} has mismatched negate flags")

            components_json = _json_list(components)
            weights_json = _json_list(effective_weights)
            negate_json = _json_list(effective_negate)
            snapshots.append(
                FactorDefinitionSnapshot(
                    factor_id=factor_id,
                    factor_kind="composite",
                    category=_coerce_string(category_map.get(factor_id, "Composite")),
                    family=factor_id.split("_")[0],
                    expression=f"COMPOSITE({', '.join(components)})",
                    components_json=components_json,
                    weights_json=weights_json,
                    negate_json=negate_json,
                    definition_hash=hashlib.sha256(
                        (
                            f"composite|{factor_id}|{components_json}|"
                            f"{weights_json}|{negate_json}"
                        ).encode("utf-8")
                    ).hexdigest(),
                    display_name_zh=factor_id,
                )
            )

        # Industry-relative composites (Layer 2 — require external SW2021 labels).
        # Plan vast-exploring-rabbit v8 phase B3.
        for definition in industry_rel_defs:
            factor_id = _coerce_string(definition["name"])
            base = _coerce_string(definition["base"])
            kind = _coerce_string(definition["kind"])
            expression = f"INDUSTRY_REL[{kind}]({base})"
            components_json = _json_list([base])
            weights_json = _json_list([1.0])
            negate_json = _json_list([False])
            snapshots.append(
                FactorDefinitionSnapshot(
                    factor_id=factor_id,
                    factor_kind="industry_relative",
                    category=_coerce_string(category_map.get(factor_id, "IndustryRelative")),
                    family=factor_id.split("_")[0],
                    expression=expression,
                    components_json=components_json,
                    weights_json=weights_json,
                    negate_json=negate_json,
                    definition_hash=hashlib.sha256(
                        f"industry_relative|{factor_id}|{base}|{kind}".encode("utf-8")
                    ).hexdigest(),
                    display_name_zh=factor_id,
                )
            )

        return snapshots

    def _upsert_snapshot(self, snapshot: FactorDefinitionSnapshot, generated_at: str) -> None:
        factor_view = self.factor_master[self.factor_master["factor_id"] == snapshot.factor_id]
        current_view = factor_view[factor_view["is_current"].fillna(False)]
        matching_view = factor_view[factor_view["definition_hash"] == snapshot.definition_hash]

        if not matching_view.empty:
            target_index = int(matching_view.sort_values("version").index[-1])
            if not current_view.empty:
                other_current = [idx for idx in current_view.index.tolist() if idx != target_index]
                if other_current:
                    self.factor_master.loc[other_current, "is_current"] = False
                    self.factor_master.loc[other_current, "updated_at"] = generated_at
            self._apply_snapshot_to_row(target_index, snapshot, generated_at, is_current=True)
            return

        if not current_view.empty:
            self.factor_master.loc[current_view.index, "is_current"] = False
            self.factor_master.loc[current_view.index, "updated_at"] = generated_at

        version = 1 if factor_view.empty else int(factor_view["version"].max()) + 1
        record = FactorMasterRecord(
            factor_id=snapshot.factor_id,
            version=version,
            is_current=True,
            status="draft",
            approval_validity="valid",
            recommended_status="draft",
            object_type="factor",
            factor_kind=snapshot.factor_kind,
            category=snapshot.category,
            family=snapshot.family,
            expression=snapshot.expression,
            components_json=snapshot.components_json,
            weights_json=snapshot.weights_json,
            negate_json=snapshot.negate_json,
            definition_hash=snapshot.definition_hash,
            definition_binding="verified",
            first_seen_run_id="",
            last_seen_run_id="",
            latest_screening_grade="",
            latest_rank_icir_5d=None,
            latest_monotonic=None,
            latest_best_decay_horizon=None,
            latest_validation_pass_count=None,
            latest_selected_fold_count=None,
            display_name_zh=snapshot.display_name_zh,
            notes="",
            deprecated_reason="",
            created_at=generated_at,
            updated_at=generated_at,
        )
        record_df = _apply_schema(pd.DataFrame([asdict(record)]), FACTOR_MASTER_COLUMNS, FACTOR_MASTER_SCHEMA)
        self.factor_master = pd.concat([self.factor_master, record_df], ignore_index=True)

    def _apply_snapshot_to_row(
        self,
        index: int,
        snapshot: FactorDefinitionSnapshot,
        generated_at: str,
        *,
        is_current: bool,
    ) -> None:
        existing_display_name = _coerce_string(self.factor_master.at[index, "display_name_zh"])
        self.factor_master.at[index, "is_current"] = is_current
        self.factor_master.at[index, "object_type"] = "factor"
        self.factor_master.at[index, "factor_kind"] = snapshot.factor_kind
        self.factor_master.at[index, "category"] = snapshot.category
        self.factor_master.at[index, "family"] = snapshot.family
        self.factor_master.at[index, "expression"] = snapshot.expression
        self.factor_master.at[index, "components_json"] = snapshot.components_json
        self.factor_master.at[index, "weights_json"] = snapshot.weights_json
        self.factor_master.at[index, "negate_json"] = snapshot.negate_json
        self.factor_master.at[index, "definition_hash"] = snapshot.definition_hash
        self.factor_master.at[index, "display_name_zh"] = existing_display_name or snapshot.display_name_zh
        self.factor_master.at[index, "updated_at"] = generated_at

    def _record_catalog_sync_run(self, generated_at: str) -> None:
        run_dir = _build_catalog_snapshot_uri(self.current_catalog_hash, self.current_composite_hash)
        run_id = _compute_run_id("catalog_sync", run_dir, generated_at)
        current_df = self.factor_master[self.factor_master["is_current"].fillna(False)].copy()

        evidence_rows = [
            FactorEvidenceRecord(
                run_id=run_id,
                run_type="catalog_sync",
                factor_id=_coerce_string(row["factor_id"]),
                version=int(row["version"]),
                is_current_at_import=True,
                grade="",
                rank_icir_5d=None,
                mean_rank_ic_5d=None,
                ic_hit_rate_5d=None,
                monotonic=None,
                best_decay_horizon=None,
                peak_decay_icir=None,
                ls_ann_return=None,
                validation_pass_count=None,
                selected_fold_count=None,
                avg_validation_rank_icir=None,
                source_run_dir=run_dir,
                evidence_time=generated_at,
            )
            for _, row in current_df.iterrows()
        ]

        self._replace_run_evidence(run_id, evidence_rows)
        self._upsert_run_index(
            RunIndexRecord(
                run_id=run_id,
                run_type="catalog_sync",
                run_dir=run_dir,
                generated_at=generated_at,
                start_date="",
                end_date="",
                benchmark="",
                include_new_data=True,
                requested_kernels="",
                effective_kernels="",
                imported_at=generated_at,
            )
        )

    def _normalize_factor_column(self, df: pd.DataFrame) -> pd.DataFrame:
        working = df.copy()
        if "factor" in working.columns:
            working["factor"] = working["factor"].astype("string")
            return working
        if len(working.columns) == 0:
            raise ValueError("Input table has no columns")
        first_column = str(working.columns[0])
        if first_column.lower().startswith("unnamed"):
            working = working.rename(columns={first_column: "factor"})
            working["factor"] = working["factor"].astype("string")
            return working
        raise ValueError("Input table is missing a factor column")

    def _ensure_known_current_factors(self, factor_ids: list[str]) -> None:
        current_names = set(self._current_version_map())
        unknown = sorted(set(factor_ids) - current_names)
        if unknown:
            raise ValueError(f"Found unmanaged formal factors in import: {', '.join(unknown[:10])}")

    def _current_version_map(self) -> dict[str, int]:
        current_df = self.factor_master[self.factor_master["is_current"].fillna(False)].copy()
        if current_df.empty:
            return {}
        return {
            _coerce_string(row["factor_id"]): int(row["version"])
            for _, row in current_df.iterrows()
        }

    def _resolve_import_versions(
        self,
        *,
        factor_ids: list[str],
        catalog_hash: str,
        composite_hash: str,
    ) -> tuple[dict[str, int], str]:
        current_versions = self._current_version_map()
        if catalog_hash and composite_hash:
            if (
                catalog_hash == self.current_catalog_hash
                and composite_hash == self.current_composite_hash
            ):
                return {factor_id: current_versions[factor_id] for factor_id in factor_ids}, "verified"

            snapshot_run_id = self._find_catalog_snapshot_run_id(catalog_hash, composite_hash)
            if snapshot_run_id:
                version_map = self._catalog_snapshot_version_map(snapshot_run_id)
                if all(factor_id in version_map for factor_id in factor_ids):
                    return {factor_id: version_map[factor_id] for factor_id in factor_ids}, "verified"

        return {factor_id: current_versions[factor_id] for factor_id in factor_ids}, "legacy_best_effort"

    def _find_catalog_snapshot_run_id(self, catalog_hash: str, composite_hash: str) -> str | None:
        target_run_dir = _build_catalog_snapshot_uri(catalog_hash, composite_hash)
        matches = self.run_index[
            (self.run_index["run_type"] == "catalog_sync")
            & (self.run_index["run_dir"] == target_run_dir)
        ]
        if matches.empty:
            return None
        matches = matches.sort_values("generated_at", kind="stable")
        return _coerce_string(matches.iloc[-1]["run_id"]) or None

    def _catalog_snapshot_version_map(self, run_id: str) -> dict[str, int]:
        evidence = self.factor_evidence[
            (self.factor_evidence["run_id"] == run_id)
            & (self.factor_evidence["run_type"] == "catalog_sync")
        ]
        if evidence.empty:
            return {}
        return {
            _coerce_string(row["factor_id"]): int(row["version"])
            for _, row in evidence.iterrows()
        }

    def _replace_run_evidence(self, run_id: str, evidence_rows: list[FactorEvidenceRecord]) -> None:
        self.factor_evidence = self.factor_evidence[self.factor_evidence["run_id"] != run_id].copy()
        if evidence_rows:
            evidence_df = _apply_schema(
                pd.DataFrame([asdict(row) for row in evidence_rows]),
                FACTOR_EVIDENCE_COLUMNS,
                FACTOR_EVIDENCE_SCHEMA,
            )
            self.factor_evidence = pd.concat([self.factor_evidence, evidence_df], ignore_index=True)

    def _upsert_run_index(self, record: RunIndexRecord) -> None:
        self.run_index = self.run_index[self.run_index["run_id"] != record.run_id].copy()
        record_df = _apply_schema(pd.DataFrame([asdict(record)]), RUN_INDEX_COLUMNS, RUN_INDEX_SCHEMA)
        self.run_index = pd.concat([self.run_index, record_df], ignore_index=True)

    def _set_definition_binding(
        self,
        factor_id: str,
        version: int,
        definition_binding: str,
        updated_at: str,
    ) -> None:
        mask = (
            (self.factor_master["factor_id"] == factor_id)
            & (self.factor_master["version"] == version)
        )
        if not mask.any():
            raise KeyError(f"Missing factor master row for {factor_id} v{version}")
        self.factor_master.loc[mask, "definition_binding"] = definition_binding
        self.factor_master.loc[mask, "updated_at"] = updated_at

    def _resolve_master_index(self, *, factor_id: str, version: int | None) -> int:
        if version is None:
            matches = self.factor_master[
                (self.factor_master["factor_id"] == factor_id)
                & (self.factor_master["is_current"].fillna(False))
            ]
        else:
            matches = self.factor_master[
                (self.factor_master["factor_id"] == factor_id)
                & (self.factor_master["version"] == version)
            ]
        if matches.empty:
            if version is None:
                raise KeyError(f"Current factor version not found: {factor_id}")
            raise KeyError(f"Factor version not found: {factor_id} v{version}")
        if len(matches) > 1:
            raise ValueError(f"Multiple factor rows matched for {factor_id}")
        return int(matches.index[0])

    def _derive_recommended_status(
        self,
        *,
        latest_screening_grade: str,
        latest_validation_pass_count: int | None,
        latest_selected_fold_count: int | None,
    ) -> str:
        screening_grade = latest_screening_grade.strip()
        validation_pass_count = latest_validation_pass_count or 0
        selected_fold_count = latest_selected_fold_count or 0
        if validation_pass_count >= 4 and selected_fold_count >= 4:
            return "approved"
        if screening_grade in CANDIDATE_SCREENING_GRADES:
            return "candidate"
        return "draft"

    def _load_upstream_screening_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        screening_run_dir = _coerce_string(metadata.get("screening_run_dir"))
        if not screening_run_dir:
            return {}
        screening_metadata_path = Path(screening_run_dir) / "factor_screening_run_metadata.json"
        if not screening_metadata_path.exists():
            return {}
        try:
            return json.loads(screening_metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            LOGGER.warning("Failed to decode upstream screening metadata: %s", screening_metadata_path)
            return {}

    def _extract_research_window(
        self,
        metadata: dict[str, Any],
        upstream_screening: dict[str, Any],
    ) -> tuple[str, str]:
        if upstream_screening.get("start_date") and upstream_screening.get("end_date"):
            return (
                _coerce_string(upstream_screening.get("start_date")),
                _coerce_string(upstream_screening.get("end_date")),
            )

        date_values: list[pd.Timestamp] = []
        for fold in metadata.get("folds", []):
            for key in (
                "train_start",
                "train_end",
                "validation_start",
                "validation_end",
                "test_start",
                "test_end",
            ):
                value = _coerce_string(fold.get(key))
                if value:
                    date_values.append(pd.Timestamp(value))
        holdout = metadata.get("holdout") or {}
        for key in ("train_start", "train_end", "validation_start", "validation_end", "start", "end"):
            value = _coerce_string(holdout.get(key))
            if value:
                date_values.append(pd.Timestamp(value))
        if not date_values:
            return "", ""
        return (min(date_values).strftime("%Y-%m-%d"), max(date_values).strftime("%Y-%m-%d"))

    def _build_research_decision_summary(
        self,
        decisions_df: pd.DataFrame,
        selected_df: pd.DataFrame,
    ) -> dict[str, dict[str, Any]]:
        summary: dict[str, dict[str, Any]] = {}
        if not decisions_df.empty:
            working = decisions_df.copy()
            working["validation_pass_bool"] = working["validation_pass"].map(_resolved_bool)
            grouped = working.groupby("factor", dropna=False)
            for factor_id, group in grouped:
                factor_name = _coerce_string(factor_id)
                summary[factor_name] = {
                    "validation_pass_count": int(group["validation_pass_bool"].fillna(False).sum()),
                    "avg_validation_rank_icir": _coerce_float(group["val_rank_icir"].mean()),
                    "selected_fold_count": 0,
                }

        if not selected_df.empty:
            grouped = selected_df.groupby("factor", dropna=False)["fold_id"].nunique()
            for factor_id, count in grouped.items():
                factor_name = _coerce_string(factor_id)
                summary.setdefault(
                    factor_name,
                    {
                        "validation_pass_count": 0,
                        "avg_validation_rank_icir": None,
                        "selected_fold_count": 0,
                    },
                )
                summary[factor_name]["selected_fold_count"] = int(count)
        return summary
