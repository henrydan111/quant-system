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

# store.py lives at src/alpha_research/factor_registry/store.py — parents[3] is the
# project root. Used to resolve the committed field-status registry cwd-independently
# for the P2 field-eligibility snapshot (GPT PR #31 review, finding 4).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_FIELD_STATUS_YAML = _PROJECT_ROOT / "config" / "field_registry" / "field_status.yaml"

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
    # PR P2.1 (Phase-2 schema foundation): latest-mirrors + signal-role metadata +
    # provenance. Evidence/metadata ONLY — none of these affect resolution or
    # promotion (the Phase-1 reader/writer gates key on status/approval_validity/
    # definition_hash, untouched here).
    "latest_oos_rank_icir",
    "latest_lo_sharpe_gross",
    "long_only_viable_provisional",
    "expected_direction",
    "signal_role",
    "signal_role_suggested",
    "requires_inverse_for_long_only",
    "approved_uses",
    "validation_scope",
    "field_eligibility_snapshot_json",
    "last_revalidated_at",
    "latest_provider_build_id",
    "latest_calendar_policy_id",
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
    # PR P2.1: walk-forward / sealed-OOS metrics + GROSS long-only top-bucket metric
    # + evidence-provenance + trust labeling (evidence_class / formal_evidence_eligible).
    "is_rank_icir",
    "oos_rank_icir",
    "sign_consistency",
    "oos_ls_sharpe",
    "retain_pct",
    "lo_excess_ann_gross",
    "lo_sharpe_gross",
    "lo_hit",
    "evidence_class",
    "formal_evidence_eligible",
    "source_path",
    "source_hash",
    "provider_build_id",
    "calendar_policy_id",
    # 2026-06-10 unified formal-eval merge: lifecycle + unified_eval are ONE formal methodology
    # (two run modes — gated orchestrator run vs ungated refresh sweep, split by
    # formal_evidence_eligible). These columns carry the unified metric set; the full record
    # (decay vector, CIs, signed residuals, …) is packed in unified_metrics_json.
    "methodology_hash",
    "universe_id",
    "mean_rank_ic_hac_t",
    "neutralized_rank_icir",
    "neutralized_hac_t",
    "mono_shape",
    "direction_source",
    "coverage",
    "coverage_tier",
    "turnover_ann",
    "resid_ic_vs_approved_stable_oriented",
    "resid_ic_vs_style_controls_v1_oriented",
    "long_leg_ir_proxy_is_csi300",
    "long_leg_ir_proxy_is_csi500",
    "unified_metrics_json",
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
    # PR P2.1
    "latest_oos_rank_icir": "Float64",
    "latest_lo_sharpe_gross": "Float64",
    "long_only_viable_provisional": "string",
    "expected_direction": "string",
    "signal_role": "string",
    "signal_role_suggested": "string",
    "requires_inverse_for_long_only": "boolean",
    "approved_uses": "string",
    "validation_scope": "string",
    "field_eligibility_snapshot_json": "string",
    "last_revalidated_at": "string",
    "latest_provider_build_id": "string",
    "latest_calendar_policy_id": "string",
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
    # PR P2.1
    "is_rank_icir": "Float64",
    "oos_rank_icir": "Float64",
    "sign_consistency": "Float64",
    "oos_ls_sharpe": "Float64",
    "retain_pct": "Float64",
    "lo_excess_ann_gross": "Float64",
    "lo_sharpe_gross": "Float64",
    "lo_hit": "Float64",
    "evidence_class": "string",
    "formal_evidence_eligible": "boolean",
    "source_path": "string",
    "source_hash": "string",
    "provider_build_id": "string",
    "calendar_policy_id": "string",
    # 2026-06-10 unified formal-eval merge (see FACTOR_EVIDENCE_COLUMNS note)
    "methodology_hash": "string",
    "universe_id": "string",
    "mean_rank_ic_hac_t": "Float64",
    "neutralized_rank_icir": "Float64",
    "neutralized_hac_t": "Float64",
    "mono_shape": "string",
    "direction_source": "string",
    "coverage": "Float64",
    "coverage_tier": "string",
    "turnover_ann": "Float64",
    "resid_ic_vs_approved_stable_oriented": "Float64",
    "resid_ic_vs_style_controls_v1_oriented": "Float64",
    "long_leg_ir_proxy_is_csi300": "Float64",
    "long_leg_ir_proxy_is_csi500": "Float64",
    "unified_metrics_json": "string",
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


# PR P2.2: deterministic, fail-closed PROVISIONAL long-only viability from the GROSS
# top-bucket metric (plan §3 thresholds; GPT cross-review decision order). This is a
# gross proxy — the FORMAL cost-adjusted long_only_viable is a later-phase recompute.
LONG_ONLY_VIABILITIES = ("viable", "review_only", "non_viable")


def _derive_long_only_viable(
    lo_sharpe_gross: Any, lo_excess_gross: Any, lo_hit: Any
) -> str:
    """Map the gross LO metric to ``viable`` / ``review_only`` / ``non_viable``.

    Decision order (fail-closed): missing -> non_viable; sharpe>=1.0 & excess>0 &
    hit>=0.60 -> viable; sharpe<0.5 OR excess<=0 -> non_viable; sharpe>=0.5 & excess>0
    -> review_only; else non_viable. ``review_only`` is fail-closed for automated/formal
    long-only use (treat as non-viable) but advisory for human / risk-sleeve review.
    """
    s = _coerce_float(lo_sharpe_gross)
    e = _coerce_float(lo_excess_gross)
    h = _coerce_float(lo_hit)
    if s is None or e is None or h is None:
        return "non_viable"
    if s >= 1.0 and e > 0 and h >= 0.60:
        return "viable"
    if s < 0.5 or e <= 0:
        return "non_viable"
    if s >= 0.5 and e > 0:
        return "review_only"
    return "non_viable"


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
    # PR P2.1 (defaults so existing constructors are unchanged; populated later by
    # the P2.2 derivation + P2.3 importer). Evidence/metadata only.
    latest_oos_rank_icir: float | None = None
    latest_lo_sharpe_gross: float | None = None
    long_only_viable_provisional: str = "non_viable"
    expected_direction: str = ""
    signal_role: str = "unassigned"
    signal_role_suggested: str = "unassigned"
    requires_inverse_for_long_only: bool | None = None
    approved_uses: str = ""
    validation_scope: str = ""
    field_eligibility_snapshot_json: str = ""
    last_revalidated_at: str = ""
    latest_provider_build_id: str = ""
    latest_calendar_policy_id: str = ""


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
    # PR P2.1 (defaults so existing import constructors are unchanged). GROSS LO metric
    # + walk-forward/OOS metrics + provenance + trust labeling.
    is_rank_icir: float | None = None
    oos_rank_icir: float | None = None
    sign_consistency: float | None = None
    oos_ls_sharpe: float | None = None
    retain_pct: float | None = None
    lo_excess_ann_gross: float | None = None
    lo_sharpe_gross: float | None = None
    lo_hit: float | None = None
    evidence_class: str = ""
    formal_evidence_eligible: bool | None = False
    source_path: str = ""
    source_hash: str = ""
    provider_build_id: str = ""
    calendar_policy_id: str = ""
    # 2026-06-10 unified formal-eval merge (defaults keep existing constructors unchanged)
    methodology_hash: str = ""
    # F1b (universe plan §3.2): the evaluation domain of this evidence row.
    # Empty/null on legacy rows == semantically univ_all (pre-F1 full-market runs).
    universe_id: str = ""
    mean_rank_ic_hac_t: float | None = None
    neutralized_rank_icir: float | None = None
    neutralized_hac_t: float | None = None
    mono_shape: str = ""
    direction_source: str = ""
    coverage: float | None = None
    coverage_tier: str = ""
    turnover_ann: float | None = None
    resid_ic_vs_approved_stable_oriented: float | None = None
    resid_ic_vs_style_controls_v1_oriented: float | None = None
    long_leg_ir_proxy_is_csi300: float | None = None
    long_leg_ir_proxy_is_csi500: float | None = None
    unified_metrics_json: str = ""


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
        self._normalize_phase2_metadata()
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

    def _normalize_phase2_metadata(self) -> None:
        """Fail-closed load defaults for the Phase-2 metadata columns (PR P2.1) on
        rows persisted before they existed — mirrors ``_normalize_approval_validity``.
        Only the behaviorally-meaningful string columns are defaulted; numeric/evidence
        columns stay null until the P2.3 importer populates them."""
        if self.factor_master.empty:
            return
        fail_closed_defaults = {
            "signal_role": "unassigned",
            "signal_role_suggested": "unassigned",
            "long_only_viable_provisional": "non_viable",
        }
        for column, default in fail_closed_defaults.items():
            col = self.factor_master[column]
            blank = col.isna() | (col.astype("string").str.strip().fillna("") == "")
            if bool(blank.any()):
                self.factor_master.loc[blank, column] = default

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

    @staticmethod
    def _read_revalidation_csv(path: str | Path, *, kind: str) -> dict[str, dict[str, Any]]:
        """Read one revalidation CSV into ``{factor_id: {metric: value, ...}}``. ``kind``
        selects which columns are pulled: ``catalog``/``derived`` (walk-forward IS/OOS
        ICIR + sign-consistency; ``derived`` adds the GROSS long-only metrics) and
        ``oos_report`` (maps ``ls_sharpe`` -> ``oos_ls_sharpe``). Structured CSV only —
        no markdown (GPT cross-review).

        ``retain_pct`` (GPT PR-#31 finding 5) is schema-reserved but DEFERRED: it is
        absent from every current revalidation CSV and from ``screening_oos_report.csv``,
        and the OOS-screened factors are not yet registry rows. It is populated in a
        later phase when structured walk-forward retention inputs are wired; until then
        the column stays null and MUST NOT be read as if populated."""
        df = pd.read_csv(path)
        out: dict[str, dict[str, Any]] = {}
        common = [("is_rank_icir", "is_rank_icir"), ("oos_rank_icir", "oos_rank_icir"),
                  ("sign_consistency", "sign_consistency")]
        derived_only = [("lo_excess_ann", "lo_excess_ann_gross"), ("lo_sharpe", "lo_sharpe_gross"),
                        ("lo_hit", "lo_hit")]
        for _, r in df.iterrows():
            factor_id = _coerce_string(r.get("factor")).strip()
            if not factor_id:
                continue
            metrics: dict[str, Any] = {"source_path": str(path)}
            for col, key in common:
                if col in df.columns:
                    metrics[key] = _coerce_float(r[col])
            if kind == "derived":
                for col, key in derived_only:
                    if col in df.columns:
                        metrics[key] = _coerce_float(r[col])
            if kind == "oos_report" and "ls_sharpe" in df.columns:
                metrics["oos_ls_sharpe"] = _coerce_float(r["ls_sharpe"])
            out[factor_id] = metrics
        return out

    def import_revalidation(
        self,
        *,
        catalog_csv: str | Path | None = None,
        derived_csv: str | Path | None = None,
        oos_report_csv: str | Path | None = None,
        provider_build_id: str = "",
        calendar_policy_id: str = "",
        evidence_class: str = "historical_investigation",
        run_id: str = "revalidation_import",
        generated_at: str | None = None,
    ) -> dict[str, Any]:
        """PR P2.3: populate ``factor_evidence`` with walk-forward / OOS / GROSS
        long-only metrics from the re-validation artifacts. **Definition-bound +
        fail-closed:** a factor is attached ONLY if its current registry
        ``definition_hash`` equals the current code-catalog hash (registry in sync);
        a factor whose hash has DRIFTED, or that is not a current registry row, is
        SKIPPED and logged — never attached by name alone. Imported rows are labeled
        ``evidence_class=historical_investigation`` + ``formal_evidence_eligible=False``
        (non-approval evidence). Writes evidence ONLY — never ``status`` /
        ``approval_validity`` / ``definition_hash``. Idempotent per
        ``(run_id, factor_id, version)``. Returns a report of attached/skipped factors."""
        merged: dict[str, dict[str, Any]] = {}
        for path, kind in ((catalog_csv, "catalog"), (derived_csv, "derived"), (oos_report_csv, "oos_report")):
            if path is None:
                continue
            for factor_id, metrics in self._read_revalidation_csv(path, kind=kind).items():
                merged.setdefault(factor_id, {}).update(metrics)

        code_hashes = self.current_catalog_definition_hashes()
        now = generated_at or _now_str()
        current = self.factor_master[self.factor_master["is_current"].fillna(False)]
        attached: list[str] = []
        skipped_drift: list[str] = []
        skipped_unknown: list[str] = []
        evidence_rows: list[FactorEvidenceRecord] = []

        for factor_id, metrics in merged.items():
            match = current[current["factor_id"] == factor_id]
            if match.empty:
                skipped_unknown.append(factor_id)
                continue
            row = match.sort_values("version").iloc[-1]
            registry_hash = _coerce_string(row.get("definition_hash"))
            code_hash = code_hashes.get(factor_id)
            if not registry_hash or code_hash is None or registry_hash != code_hash:
                # FAIL-CLOSED: registry definition drifted from the catalog (or unknown
                # to the catalog) — do NOT attach evidence to an ambiguous definition.
                skipped_drift.append(factor_id)
                continue
            evidence_rows.append(FactorEvidenceRecord(
                run_id=run_id, run_type="revalidation", factor_id=factor_id,
                version=int(row["version"]), is_current_at_import=True,
                grade="", rank_icir_5d=None, mean_rank_ic_5d=None, ic_hit_rate_5d=None,
                monotonic=None, best_decay_horizon=None, peak_decay_icir=None,
                ls_ann_return=None, validation_pass_count=None, selected_fold_count=None,
                avg_validation_rank_icir=None, source_run_dir=str(metrics.get("source_path", "")),
                evidence_time=now,
                is_rank_icir=metrics.get("is_rank_icir"), oos_rank_icir=metrics.get("oos_rank_icir"),
                sign_consistency=metrics.get("sign_consistency"),
                oos_ls_sharpe=metrics.get("oos_ls_sharpe"), retain_pct=metrics.get("retain_pct"),
                lo_excess_ann_gross=metrics.get("lo_excess_ann_gross"),
                lo_sharpe_gross=metrics.get("lo_sharpe_gross"), lo_hit=metrics.get("lo_hit"),
                evidence_class=evidence_class, formal_evidence_eligible=False,
                source_path=str(metrics.get("source_path", "")), source_hash=registry_hash,
                provider_build_id=provider_build_id, calendar_policy_id=calendar_policy_id,
            ))
            attached.append(factor_id)

        if evidence_rows:
            # Idempotent: drop any prior rows for the same (run_id, factor_id, version).
            new_keys = {(run_id, r.factor_id, int(r.version)) for r in evidence_rows}
            existing = self.factor_evidence
            if not existing.empty:
                keep = ~existing.apply(
                    lambda x: (
                        _coerce_string(x["run_id"]),
                        _coerce_string(x["factor_id"]),
                        _coerce_int(x["version"]),
                    ) in new_keys,
                    axis=1,
                )
                existing = existing[keep]
            new_df = _apply_schema(
                pd.DataFrame([asdict(r) for r in evidence_rows]),
                FACTOR_EVIDENCE_COLUMNS, FACTOR_EVIDENCE_SCHEMA,
            )
            self.factor_evidence = pd.concat([existing, new_df], ignore_index=True)

        self.refresh_master_derived_fields()
        return {
            "run_id": run_id,
            "attached": sorted(attached),
            "skipped_drift": sorted(skipped_drift),
            "skipped_unknown": sorted(skipped_unknown),
        }

    def record_lifecycle_evidence(
        self,
        *,
        run_id: str,
        verdicts: list[Mapping[str, Any]],
        evidence_class: str,
        source_run_dir: str = "",
        generated_at: str | None = None,
    ) -> dict[str, Any]:
        """Phase 5: append IS-only FORMAL factor-lifecycle evidence for the given verdict
        rows (the publish step passes only candidate-verdict factors). Each row is
        definition-bound (``source_hash`` = the factor's CURRENT ``definition_hash``),
        ``run_type='factor_lifecycle'``, ``formal_evidence_eligible=True``, IS-only metrics
        (``is_rank_icir`` = heldout ICIR, ``sign_consistency``), NO ``oos_*``. Idempotent
        per ``(run_id, factor_id, version)`` so a retry after a status-write failure does
        not duplicate rows. Writes EVIDENCE only — never ``status``.

        FAIL-CLOSED (GPT PR-#34 review): because this is itself a FORMAL-evidence writer,
        it INDEPENDENTLY re-checks definition drift (mirrors ``import_revalidation``) — a
        factor whose registry ``definition_hash`` != the current code-catalog hash, or that
        is unknown to the registry, is SKIPPED (never attached to an ambiguous definition)
        and reported in ``skipped_drift`` / ``skipped_unknown``. ``selected_fold_count``
        carries ``n_heldout_blocks``."""
        now = generated_at or _now_str()
        code_hashes = self.current_catalog_definition_hashes()
        current = self.factor_master[self.factor_master["is_current"].fillna(False)]
        evidence_rows: list[FactorEvidenceRecord] = []
        attached: list[str] = []
        skipped_unknown: list[str] = []
        skipped_drift: list[str] = []
        for v in verdicts:
            fid = _coerce_string(v.get("factor"))
            match = current[current["factor_id"] == fid] if fid else current.iloc[0:0]
            if not fid or match.empty:
                skipped_unknown.append(fid)
                continue
            row = match.sort_values("version").iloc[-1]
            registry_hash = _coerce_string(row.get("definition_hash"))
            code_hash = code_hashes.get(fid)
            if not registry_hash or code_hash is None or registry_hash != code_hash:
                # FAIL-CLOSED: drifted (or unknown to catalog) -> no FORMAL evidence.
                skipped_drift.append(fid)
                continue
            evidence_rows.append(FactorEvidenceRecord(
                run_id=run_id, run_type="factor_lifecycle", factor_id=fid,
                version=int(row["version"]), is_current_at_import=True,
                grade="", rank_icir_5d=None, mean_rank_ic_5d=None, ic_hit_rate_5d=None,
                monotonic=None, best_decay_horizon=None, peak_decay_icir=None,
                ls_ann_return=None, validation_pass_count=None,
                selected_fold_count=_coerce_int(v.get("n_heldout_blocks")),
                avg_validation_rank_icir=None, source_run_dir=str(source_run_dir), evidence_time=now,
                is_rank_icir=_coerce_float(v.get("heldout_rank_icir")), oos_rank_icir=None,
                sign_consistency=_coerce_float(v.get("sign_consistency")),
                oos_ls_sharpe=None, retain_pct=None, lo_excess_ann_gross=None,
                lo_sharpe_gross=None, lo_hit=None,
                evidence_class=str(evidence_class), formal_evidence_eligible=True,
                source_path="", source_hash=registry_hash,
                provider_build_id="", calendar_policy_id="",
            ))
            attached.append(fid)
        if evidence_rows:
            new_keys = {(run_id, r.factor_id, int(r.version)) for r in evidence_rows}
            existing = self.factor_evidence
            if not existing.empty:
                keep = ~existing.apply(
                    lambda x: (
                        _coerce_string(x["run_id"]),
                        _coerce_string(x["factor_id"]),
                        _coerce_int(x["version"]),
                    ) in new_keys,
                    axis=1,
                )
                existing = existing[keep]
            new_df = _apply_schema(
                pd.DataFrame([asdict(r) for r in evidence_rows]),
                FACTOR_EVIDENCE_COLUMNS, FACTOR_EVIDENCE_SCHEMA,
            )
            self.factor_evidence = pd.concat([existing, new_df], ignore_index=True)
            self.refresh_master_derived_fields()
        return {
            "run_id": run_id,
            "attached": sorted(attached),
            "skipped_drift": sorted(skipped_drift),
            "skipped_unknown": sorted(skipped_unknown),
        }

    def record_formal_refresh_evidence(
        self,
        *,
        run_id: str,
        records: list[Mapping[str, Any]],
        methodology_hash: str,
        source_path: str = "",
        generated_at: str | None = None,
    ) -> dict[str, Any]:
        """2026-06-10 unified merge: append FORMAL-methodology evidence from an UNGATED
        refresh sweep (the full-catalog unified evaluation). Same metric口径 and engine as
        the gated ``factor_lifecycle`` runs — the taxonomy is two-class (discovery = screening
        / formal = lifecycle methodology) with the gated/ungated split carried by
        ``formal_evidence_eligible``: automated rows are ``run_type='factor_lifecycle_auto'``,
        ``evidence_class='formal_auto'``, ``formal_evidence_eligible=False`` — they can
        NEVER support a status change (the gated orchestrator run + human gate remains the
        only path; resolve-but-label). Definition-bound FAIL-CLOSED exactly like
        :meth:`record_lifecycle_evidence` (drifted / catalog-unknown factors are skipped).
        Idempotent per ``(run_id, factor_id, version)``. Writes EVIDENCE only — never status.

        Each record is a mapping from the unified-eval full-run output (keys: ``factor``,
        ``heldout_rank_icir``, ``sign_consistency``, ``mean_rank_ic_hac_t``,
        ``neutralized_rank_icir``, ``mono_shape``, ``coverage``, ``turnover_ann``,
        oriented residuals, long-leg IRs, …); the WHOLE record is also packed verbatim into
        ``unified_metrics_json`` so no metric is lost to the column subset.
        """
        now = generated_at or _now_str()
        code_hashes = self.current_catalog_definition_hashes()
        current = self.factor_master[self.factor_master["is_current"].fillna(False)]
        evidence_rows: list[FactorEvidenceRecord] = []
        attached: list[str] = []
        skipped_unknown: list[str] = []
        skipped_drift: list[str] = []
        for rec in records:
            fid = _coerce_string(rec.get("factor"))
            match = current[current["factor_id"] == fid] if fid else current.iloc[0:0]
            if not fid or match.empty:
                skipped_unknown.append(fid)
                continue
            row = match.sort_values("version").iloc[-1]
            registry_hash = _coerce_string(row.get("definition_hash"))
            code_hash = code_hashes.get(fid)
            if not registry_hash or code_hash is None or registry_hash != code_hash:
                skipped_drift.append(fid)
                continue
            evidence_rows.append(FactorEvidenceRecord(
                run_id=run_id, run_type="factor_lifecycle_auto", factor_id=fid,
                version=int(row["version"]), is_current_at_import=True,
                grade="", rank_icir_5d=None, mean_rank_ic_5d=_coerce_float(rec.get("mean_rank_ic")),
                ic_hit_rate_5d=None, monotonic=None, best_decay_horizon=None,
                peak_decay_icir=None, ls_ann_return=None, validation_pass_count=None,
                selected_fold_count=None, avg_validation_rank_icir=None,
                source_run_dir="", evidence_time=now,
                is_rank_icir=_coerce_float(rec.get("heldout_rank_icir")), oos_rank_icir=None,
                sign_consistency=_coerce_float(rec.get("sign_consistency")),
                oos_ls_sharpe=None, retain_pct=None, lo_excess_ann_gross=None,
                lo_sharpe_gross=None, lo_hit=None,
                evidence_class="formal_auto", formal_evidence_eligible=False,
                source_path=str(source_path), source_hash=registry_hash,
                provider_build_id="", calendar_policy_id="",
                methodology_hash=str(methodology_hash),
                universe_id=_coerce_string(rec.get("universe_id")) or "univ_all",
                mean_rank_ic_hac_t=_coerce_float(rec.get("mean_rank_ic_hac_t")),
                neutralized_rank_icir=_coerce_float(rec.get("neutralized_rank_icir")),
                neutralized_hac_t=_coerce_float(rec.get("neutralized_hac_t")),
                mono_shape=_coerce_string(rec.get("mono_shape")),
                direction_source=_coerce_string(rec.get("direction_source")),
                coverage=_coerce_float(rec.get("coverage")),
                coverage_tier=_coerce_string(rec.get("coverage_tier")),
                turnover_ann=_coerce_float(rec.get("turnover_ann")),
                resid_ic_vs_approved_stable_oriented=_coerce_float(
                    rec.get("resid_ic_vs_approved_stable_oriented")),
                resid_ic_vs_style_controls_v1_oriented=_coerce_float(
                    rec.get("resid_ic_vs_style_controls_v1_oriented")),
                long_leg_ir_proxy_is_csi300=_coerce_float(rec.get("long_leg_ir_proxy_is_csi300")),
                long_leg_ir_proxy_is_csi500=_coerce_float(rec.get("long_leg_ir_proxy_is_csi500")),
                unified_metrics_json=json.dumps(
                    {k: (None if isinstance(v, float) and v != v else v) for k, v in dict(rec).items()},
                    ensure_ascii=False, default=str),
            ))
            attached.append(fid)
        if evidence_rows:
            # F1b: replace key includes universe_id so per-domain imports of the SAME
            # run are additive (a csi300 import must not delete the univ_all rows).
            # Legacy rows with empty universe_id coerce to univ_all for keying.
            new_keys = {(run_id, r.factor_id, int(r.version), r.universe_id or "univ_all")
                        for r in evidence_rows}
            existing = self.factor_evidence
            if not existing.empty:
                has_univ = "universe_id" in existing.columns
                keep = ~existing.apply(
                    lambda x: (
                        _coerce_string(x["run_id"]),
                        _coerce_string(x["factor_id"]),
                        _coerce_int(x["version"]),
                        (_coerce_string(x["universe_id"]) if has_univ else "") or "univ_all",
                    ) in new_keys,
                    axis=1,
                )
                existing = existing[keep]
            new_df = _apply_schema(
                pd.DataFrame([asdict(r) for r in evidence_rows]),
                FACTOR_EVIDENCE_COLUMNS, FACTOR_EVIDENCE_SCHEMA,
            )
            self.factor_evidence = pd.concat([existing, new_df], ignore_index=True)
            self.refresh_master_derived_fields()
        return {
            "run_id": run_id,
            "attached": sorted(attached),
            "skipped_drift": sorted(skipped_drift),
            "skipped_unknown": sorted(skipped_unknown),
        }


    # 2026-06-11 directive: the "refresh" label is retired — external taxonomy is
    # discovery / formal only. New rows write run_type='factor_lifecycle_auto'.
    record_formal_auto_evidence = record_formal_refresh_evidence
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

    def set_expected_direction(
        self,
        *,
        factor_id: str,
        expected_direction: str,
        version: int | None = None,
    ) -> None:
        """Metadata-only: set ``factor_master.expected_direction`` on the current row (Phase 7,
        GPT impl-review must-fix). Derived from the lifecycle verdict's SIGNED ICIR
        (``positive`` / ``inverse`` / ``undetermined``) so the durable direction metadata that
        the future ``FrozenSelectionSet`` hash consumes is populated on promotion. Does NOT
        touch ``status`` / ``approval_validity`` / ``definition_hash`` and writes NO
        status-history row — direction is signal metadata, not a lifecycle transition. A blank
        value is a no-op."""
        ed = str(expected_direction or "").strip()
        if not ed:
            return
        # GPT Phase-7 re-confirm note: the lifecycle producer emits only these three; enum-
        # validate fail-closed so a stray value cannot quietly enter the FrozenSelectionSet field.
        valid = {"positive", "inverse", "undetermined"}
        if ed not in valid:
            raise ValueError(
                f"expected_direction must be one of {sorted(valid)} (or blank); got {ed!r}"
            )
        index = self._resolve_master_index(factor_id=factor_id, version=version)
        self.factor_master.at[index, "expected_direction"] = ed
        self.factor_master.at[index, "updated_at"] = _now_str()

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

    def _field_registry_cached(self):
        """Lazily load + cache the committed field-status registry (cwd-independent
        via ``_FIELD_STATUS_YAML``). Cached on the instance — one store run sees one
        registry snapshot."""
        reg = getattr(self, "_field_registry_obj", None)
        if reg is None:
            from src.data_infra.field_registry import load_field_registry
            reg = load_field_registry(_FIELD_STATUS_YAML)
            self._field_registry_obj = reg
        return reg

    def _field_eligibility_snapshot(self, *, factor_kind: str, expression: str) -> str:
        """GPT PR-#31 cross-review finding 4: snapshot the live field-registry
        eligibility of a factor's referenced ``$fields`` at the strict
        ``formal_validation`` stage, as compact JSON.

        BASE factors carry a real Qlib expression and resolve directly. COMPOSITE /
        INDUSTRY_RELATIVE master expressions are PSEUDO-expressions (``COMPOSITE(...)``,
        ``INDUSTRY_REL[...](...)``) with NO ``$field`` tokens, so their true (transitive)
        field dependencies are DEFERRED to Phase 3 (``get_factors`` resolves composite
        deps) — they are marked ``resolved=false`` here. **Fail-closed contract:**
        ``resolved=false`` (composite / registry-load error) AND an empty string ('not
        computed') MUST be treated by any consumer as NOT eligible — never as
        ``all_allowed``. Returns the JSON string (never raises)."""
        if factor_kind != "base":
            return json.dumps(
                {"resolved": False, "reason": f"transitive_deferred_{factor_kind or 'unknown'}"},
                sort_keys=True,
            )
        try:
            from src.data_infra.field_registry import extract_qlib_fields
            registry = self._field_registry_cached()
            tokens = extract_qlib_fields(expression)
            fields: dict[str, str] = {}
            all_allowed = True
            for token in tokens:
                resolution = registry.resolve_field(token, "formal_validation")
                fields[token] = resolution.status_id or ("unknown" if resolution.is_unknown else "")
                if not resolution.allowed:
                    all_allowed = False
            return json.dumps(
                {"resolved": True, "stage": "formal_validation",
                 "all_allowed": all_allowed, "fields": fields},
                sort_keys=True,
            )
        except Exception as exc:  # fail-closed: never emit a misleading all_allowed=true
            LOGGER.warning(
                "field_eligibility snapshot failed (expression=%r): %s — emitting "
                "resolved=false (fail-closed)", expression, exc,
            )
            return json.dumps({"resolved": False, "reason": "registry_error"}, sort_keys=True)

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

            # PR P2.2 + GPT PR-#31 cross-review (findings 1-4): GROSS long-only + OOS
            # mirrors, provenance mirrors, the deterministic fail-closed provisional
            # viability, and the live field-eligibility snapshot. NONE of this changes
            # status/approval_validity/definition_hash (the Phase-1 gates).
            current_def_hash = _coerce_string(row["definition_hash"])
            latest_lo_sharpe_gross = None
            latest_lo_excess_gross = None
            latest_lo_hit = None
            latest_oos_rank_icir = None
            latest_provider_build_id = ""
            latest_calendar_policy_id = ""
            last_revalidated_at = ""
            if not subset.empty and current_def_hash:
                # The P2 mirrors (provenance, last_revalidated_at, OOS/LO, viability)
                # reflect the latest REVALIDATION evidence ONLY (GPT PR-#31 re-review):
                #  - run_type == "revalidation": a `catalog_sync` / screening / research
                #    row must NOT set last_revalidated_at (else a plain sync_catalog would
                #    stamp every factor "revalidated" at the sync timestamp).
                #  - Finding 3 (fail-closed binding): within revalidation rows, only those
                #    whose source_hash is blank (manually-injected; never carries LO) OR
                #    matches the CURRENT definition_hash drive the mirrors. Stale-definition
                #    evidence (nonblank source_hash != current hash, e.g. a skip-drifted
                #    re-import) is ignored even though it remains in factor_evidence.
                source_hashes = subset["source_hash"].map(_coerce_string)
                bound = subset[
                    (subset["run_type"] == "revalidation")
                    & ((source_hashes == "") | (source_hashes == current_def_hash))
                ]
                if not bound.empty:
                    latest_oos_rank_icir = _latest_non_null(bound["oos_rank_icir"], _coerce_float)
                    latest_provider_build_id = _coerce_string(_latest_non_null(bound["provider_build_id"]))
                    latest_calendar_policy_id = _coerce_string(_latest_non_null(bound["calendar_policy_id"]))
                    last_revalidated_at = _coerce_string(_latest_non_null(bound["evidence_time"]))
                    # Finding 2 (no cross-row metric mixing): derive viability from the
                    # SINGLE latest row that actually carries an LO Sharpe, using THAT
                    # row's full tuple. A partial tuple on that row -> non_viable (the
                    # _derive_long_only_viable fail-closed rule), never a resurrected
                    # excess/hit from an older row.
                    lo_bearing = bound[bound["lo_sharpe_gross"].notna()]
                    if not lo_bearing.empty:
                        lo_row = lo_bearing.iloc[-1]
                        latest_lo_sharpe_gross = _coerce_float(lo_row["lo_sharpe_gross"])
                        latest_lo_excess_gross = _coerce_float(lo_row["lo_excess_ann_gross"])
                        latest_lo_hit = _coerce_float(lo_row["lo_hit"])
            viability = _derive_long_only_viable(
                latest_lo_sharpe_gross, latest_lo_excess_gross, latest_lo_hit
            )
            master.at[index, "latest_lo_sharpe_gross"] = latest_lo_sharpe_gross
            master.at[index, "latest_oos_rank_icir"] = latest_oos_rank_icir
            master.at[index, "latest_provider_build_id"] = latest_provider_build_id
            master.at[index, "latest_calendar_policy_id"] = latest_calendar_policy_id
            master.at[index, "last_revalidated_at"] = last_revalidated_at
            master.at[index, "long_only_viable_provisional"] = viability
            # Finding 1: auto-SUGGEST long_only_alpha for a viable factor (spec §P2.1).
            # NEVER touch the authoritative human-assigned `signal_role` (a separate
            # column set only via the gated CLI).
            master.at[index, "signal_role_suggested"] = (
                "long_only_alpha" if viability == "viable" else "unassigned"
            )
            # Finding 4: live field-registry eligibility snapshot of the factor's
            # referenced $fields. Definition-derived (not evidence-derived), so it is
            # set for every factor. Fail-closed: composites / registry errors yield
            # resolved=false, never a false all_allowed=true.
            master.at[index, "field_eligibility_snapshot_json"] = self._field_eligibility_snapshot(
                factor_kind=_coerce_string(row["factor_kind"]),
                expression=_coerce_string(row["expression"]),
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

    def current_catalog_definition_hashes(self) -> dict[str, str]:
        """Return ``{factor_id: definition_hash}`` computed from the CURRENT code
        catalog using the SAME snapshot/hash algorithm ``sync_catalog`` writes
        (``_build_catalog_snapshots``). This is the parity primitive for the P1.3
        definition-binding gate: comparing a registry row's stored ``definition_hash``
        against this map detects drift between the registry and ``catalog.py`` with an
        apples-to-apples hash (covers base / composite / industry-relative). Read-only
        — it recomputes from code and does NOT mutate ``factor_master``."""
        return {snap.factor_id: snap.definition_hash for snap in self._build_catalog_snapshots()}

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
