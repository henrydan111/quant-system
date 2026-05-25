"""Append-only hypothesis registry built on a single parquet event log."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from src.research_orchestrator.file_lock import file_lock

if TYPE_CHECKING:
    from src.research_orchestrator.hypothesis import Hypothesis

EVENT_COLUMNS = [
    "event_id",
    "event_type",
    "event_sequence",
    "recorded_at",
    "hypothesis_id",
    "design_hash",
    "prose_hash",
    "structural_family",
    "economic_family",
    "profile_id",
    "hypothesis_json",
    "run_id",
    "run_dir",
    "gate_id",
    "gate_stage",
    "decision",
    "decision_by",
    "decision_reason",
    "measured_values_json",
    "criteria_results_json",
    "override_reason",
    "override_by",
]

EVENT_SCHEMA = {
    "event_id": "string",
    "event_type": "string",
    "event_sequence": "Int64",
    "recorded_at": "string",
    "hypothesis_id": "string",
    "design_hash": "string",
    "prose_hash": "string",
    "structural_family": "string",
    "economic_family": "string",
    "profile_id": "string",
    "hypothesis_json": "string",
    "run_id": "string",
    "run_dir": "string",
    "gate_id": "string",
    "gate_stage": "string",
    "decision": "string",
    "decision_by": "string",
    "decision_reason": "string",
    "measured_values_json": "string",
    "criteria_results_json": "string",
    "override_reason": "string",
    "override_by": "string",
}

VALID_EVENT_TYPES = ("registration", "gate_decision", "manual_override", "retirement")
VALID_STATUSES = (
    "pre_registered",
    "is_passed",
    "is_rejected",
    "is_quarantined",
    "oos_passed",
    "oos_rejected",
    "oos_quarantined",
    "retired",
    "terminal",
)


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _make_temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")


def _atomic_write_dataframe(df: pd.DataFrame, parquet_path: Path) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(parquet_path)
    df.to_parquet(temp_path, index=False)
    os.replace(temp_path, parquet_path)


def _empty_frame() -> pd.DataFrame:
    frame = pd.DataFrame(columns=EVENT_COLUMNS)
    for column, dtype in EVENT_SCHEMA.items():
        frame[column] = frame[column].astype(dtype)
    return frame


def _load_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return _empty_frame()
    frame = pd.read_parquet(path)
    for column in EVENT_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame = frame[EVENT_COLUMNS].copy()
    for column, dtype in EVENT_SCHEMA.items():
        frame[column] = frame[column].astype(dtype)
    return frame


def _append_row(frame: pd.DataFrame, row: dict[str, Any]) -> pd.DataFrame:
    new_row = pd.DataFrame([row])
    for column in EVENT_COLUMNS:
        if column not in new_row.columns:
            new_row[column] = ""
    new_row = new_row[EVENT_COLUMNS]
    for column, dtype in EVENT_SCHEMA.items():
        new_row[column] = new_row[column].astype(dtype)
    if frame.empty:
        return new_row.reset_index(drop=True)
    return pd.concat([frame, new_row], ignore_index=True)


def _make_event_id(event_type: str, design_hash: str, recorded_at: str, event_sequence: int) -> str:
    raw = f"{event_type}|{design_hash}|{recorded_at}|{event_sequence}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_decision(decision: str) -> str:
    value = str(decision).strip().lower()
    if value in {"approve", "approved", "pass", "passed"}:
        return "approved"
    if value in {"reject", "rejected", "fail", "failed"}:
        return "rejected"
    if value in {"quarantine", "quarantined"}:
        return "quarantined"
    if not value:
        raise ValueError("Gate decision cannot be empty.")
    return value


def _status_from_gate(gate_stage: str, decision: str) -> str:
    decision = _normalize_decision(decision)
    stage = str(gate_stage).strip().lower()
    if decision == "quarantined":
        if stage in {"oos_verdict", "oos_test"} or "oos" in stage:
            return "oos_quarantined"
        return "is_quarantined"
    if decision == "approved":
        if stage in {"oos_verdict", "oos_test"} or "oos" in stage:
            return "oos_passed"
        return "is_passed"
    if stage in {"oos_verdict", "oos_test"} or "oos" in stage:
        return "oos_rejected"
    return "is_rejected"


def _compute_run_id(run_dir: str, profile_id: str, gate_id: str) -> str:
    payload = {
        "run_dir": str(Path(run_dir).resolve()),
        "profile_id": str(profile_id),
        "gate_id": str(gate_id),
    }
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()[:16]


def _resolve_economic_family_for_master_view(events_for_hypothesis: pd.DataFrame) -> str:
    overrides = events_for_hypothesis[
        (events_for_hypothesis["event_type"] == "manual_override")
        & (events_for_hypothesis["override_reason"].astype(str).str.startswith("economic_family_backfilled:"))
    ]
    if not overrides.empty:
        latest = overrides.sort_values("event_sequence").tail(1).iloc[0]
        return str(latest["override_reason"]).split(":", 1)[1].strip()
    reg_rows = events_for_hypothesis[events_for_hypothesis["event_type"] == "registration"]
    if reg_rows.empty:
        return ""
    return str(reg_rows.iloc[0].get("economic_family", "") or "")


def _status_history_from_events(events: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    if events.empty:
        return pd.DataFrame(
            columns=[
                "hypothesis_id",
                "design_hash",
                "old_status",
                "new_status",
                "reason",
                "source_run_id",
                "gate_id",
                "changed_by",
                "changed_at",
            ]
        )
    for design_hash, group in events.sort_values(["design_hash", "event_sequence"]).groupby("design_hash", sort=False):
        current_status = ""
        for _, row in group.iterrows():
            event_type = str(row["event_type"])
            if event_type == "registration":
                new_status = "pre_registered"
                records.append(
                    {
                        "hypothesis_id": str(row["hypothesis_id"]),
                        "design_hash": str(design_hash),
                        "old_status": current_status,
                        "new_status": new_status,
                        "reason": "Hypothesis registered",
                        "source_run_id": "",
                        "gate_id": "pre_registration",
                        "changed_by": "",
                        "changed_at": str(row["recorded_at"]),
                    }
                )
                current_status = new_status
            elif event_type == "gate_decision":
                new_status = _status_from_gate(str(row["gate_stage"]), str(row["decision"]))
                records.append(
                    {
                        "hypothesis_id": str(row["hypothesis_id"]),
                        "design_hash": str(design_hash),
                        "old_status": current_status,
                        "new_status": new_status,
                        "reason": str(row["decision_reason"]),
                        "source_run_id": str(row["run_id"]),
                        "gate_id": str(row["gate_id"]),
                        "changed_by": str(row["decision_by"]),
                        "changed_at": str(row["recorded_at"]),
                    }
                )
                current_status = new_status
            elif event_type == "retirement":
                records.append(
                    {
                        "hypothesis_id": str(row["hypothesis_id"]),
                        "design_hash": str(design_hash),
                        "old_status": current_status,
                        "new_status": "retired",
                        "reason": str(row["decision_reason"]),
                        "source_run_id": "",
                        "gate_id": "",
                        "changed_by": str(row["override_by"]),
                        "changed_at": str(row["recorded_at"]),
                    }
                )
                current_status = "retired"
    return pd.DataFrame.from_records(records)


class HypothesisRegistryStore:
    """Append-only registry for formal hypotheses and their gate history."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root_dir / "hypothesis_events.parquet"

    def _load_unlocked(self) -> pd.DataFrame:
        return _load_frame(self.log_path)

    def _locked_append(self, row: dict[str, Any]) -> dict[str, Any]:
        with file_lock(self.root_dir / ".hypothesis_events.lock", timeout_seconds=30):
            frame = self._load_unlocked()
            next_seq = int(frame["event_sequence"].max()) + 1 if not frame.empty else 1
            row = dict(row)
            row["event_sequence"] = next_seq
            row["event_id"] = _make_event_id(
                str(row["event_type"]),
                str(row["design_hash"]),
                str(row["recorded_at"]),
                next_seq,
            )
            frame = _append_row(frame, row)
            _atomic_write_dataframe(frame, self.log_path)
            return row

    @property
    def events(self) -> pd.DataFrame:
        return self._load_unlocked()

    @property
    def master(self) -> pd.DataFrame:
        return self._derive_master_view()

    @property
    def evidence(self) -> pd.DataFrame:
        events = self.events
        if events.empty:
            return pd.DataFrame(
                columns=[
                    "event_id",
                    "hypothesis_id",
                    "design_hash",
                    "run_id",
                    "run_dir",
                    "profile_id",
                    "gate_id",
                    "gate_stage",
                    "decision",
                    "decision_reason",
                    "decision_by",
                    "measured_values_json",
                    "criteria_results_json",
                    "recorded_at",
                ]
            )
        return events[events["event_type"] == "gate_decision"].copy().reset_index(drop=True)

    @property
    def run_index(self) -> pd.DataFrame:
        evidence = self.evidence
        if evidence.empty:
            return pd.DataFrame(
                columns=[
                    "run_id",
                    "hypothesis_id",
                    "design_hash",
                    "run_dir",
                    "profile_id",
                    "gate_stage",
                    "decision",
                    "recorded_at",
                ]
            )
        return evidence[
            ["run_id", "hypothesis_id", "design_hash", "run_dir", "profile_id", "gate_stage", "decision", "recorded_at"]
        ].copy()

    @property
    def status_history(self) -> pd.DataFrame:
        return _status_history_from_events(self.events)

    def save(self) -> None:
        # Writes are committed on every mutating call. This is kept for API compatibility.
        return None

    def _derive_master_view(self) -> pd.DataFrame:
        events = self.events.copy()
        if events.empty:
            return pd.DataFrame(
                columns=[
                    "hypothesis_id",
                    "design_hash",
                    "prose_hash",
                    "structural_family",
                    "economic_family",
                    "status",
                    "latest_gate_stage",
                    "latest_verdict",
                    "first_registered_at",
                    "updated_at",
                    "hypothesis_json",
                    "latest_decision_reason",
                    "override_count",
                ]
            )
        events = events.sort_values(["design_hash", "event_sequence"]).reset_index(drop=True)
        records: list[dict[str, Any]] = []
        for design_hash, group in events.groupby("design_hash", sort=False):
            reg_rows = group[group["event_type"] == "registration"]
            if reg_rows.empty:
                continue
            first_reg = reg_rows.iloc[0]
            last_gate = group[group["event_type"] == "gate_decision"].tail(1)
            overrides = group[group["event_type"] == "manual_override"]
            retirement = group[group["event_type"] == "retirement"].tail(1)
            if not retirement.empty:
                status = "retired"
                updated_at = str(retirement.iloc[0]["recorded_at"])
                latest_verdict = "retired"
                latest_gate_stage = str(last_gate.iloc[0]["gate_stage"]) if not last_gate.empty else ""
                latest_decision_reason = str(retirement.iloc[0]["decision_reason"])
            elif not last_gate.empty:
                gate_row = last_gate.iloc[0]
                status = _status_from_gate(str(gate_row["gate_stage"]), str(gate_row["decision"]))
                updated_at = str(gate_row["recorded_at"])
                latest_verdict = str(gate_row["decision"])
                latest_gate_stage = str(gate_row["gate_stage"])
                latest_decision_reason = str(gate_row["decision_reason"])
            else:
                status = "pre_registered"
                updated_at = str(first_reg["recorded_at"])
                latest_verdict = ""
                latest_gate_stage = ""
                latest_decision_reason = ""
            records.append(
                {
                    "hypothesis_id": str(first_reg["hypothesis_id"]),
                    "design_hash": str(design_hash),
                    "prose_hash": str(first_reg["prose_hash"]),
                    "structural_family": str(first_reg["structural_family"]),
                    "economic_family": _resolve_economic_family_for_master_view(group),
                    "status": status,
                    "latest_gate_stage": latest_gate_stage,
                    "latest_verdict": latest_verdict,
                    "first_registered_at": str(first_reg["recorded_at"]),
                    "updated_at": updated_at,
                    "hypothesis_json": str(first_reg["hypothesis_json"]),
                    "latest_decision_reason": latest_decision_reason,
                    "override_count": int(len(overrides)),
                }
            )
        return pd.DataFrame.from_records(records)

    def get(self, hypothesis_id: str) -> dict[str, Any] | None:
        working = self.master[self.master["hypothesis_id"] == str(hypothesis_id)].copy()
        if working.empty:
            return None
        return working.sort_values("updated_at").iloc[-1].to_dict()

    def get_by_design_hash(self, design_hash: str) -> dict[str, Any] | None:
        working = self.master[self.master["design_hash"] == str(design_hash)].copy()
        if working.empty:
            return None
        return working.sort_values("updated_at").iloc[-1].to_dict()

    def list_by_status(self, status: str) -> pd.DataFrame:
        working = self.master
        if not status:
            return working.copy()
        return working[working["status"] == str(status)].copy()

    def has_manual_override(self, design_hash: str, override_reason_prefix: str) -> bool:
        events = self.events
        if events.empty:
            return False
        mask = (
            (events["design_hash"] == str(design_hash))
            & (events["event_type"] == "manual_override")
            & (events["override_reason"].astype(str).str.startswith(str(override_reason_prefix)))
        )
        return bool(mask.any())

    def register(self, hypothesis: "Hypothesis") -> dict[str, Any]:
        hypothesis.validate()
        design_hash = hypothesis.design_hash()
        existing = self.get_by_design_hash(design_hash)
        if existing is not None:
            return {
                "already_exists": True,
                "hypothesis_id": existing["hypothesis_id"],
                "design_hash": design_hash,
                "status": existing["status"],
            }
        timestamp = _now_str()
        self._locked_append(
            {
                "event_type": "registration",
                "recorded_at": timestamp,
                "hypothesis_id": str(hypothesis.hypothesis_id),
                "design_hash": design_hash,
                "prose_hash": hypothesis.prose_hash(),
                "structural_family": hypothesis.structural_family(),
                "economic_family": hypothesis.economic_family(),
                "profile_id": "",
                "hypothesis_json": _json_dumps(hypothesis.to_dict()),
                "run_id": "",
                "run_dir": "",
                "gate_id": "",
                "gate_stage": "",
                "decision": "",
                "decision_by": "",
                "decision_reason": "",
                "measured_values_json": "",
                "criteria_results_json": "",
                "override_reason": "",
                "override_by": "",
            }
        )
        return {
            "already_exists": False,
            "hypothesis_id": hypothesis.hypothesis_id,
            "design_hash": design_hash,
            "status": "pre_registered",
        }

    def record_gate_decision(
        self,
        *,
        hypothesis_id: str,
        design_hash: str,
        run_dir: str,
        profile_id: str,
        gate_id: str,
        gate_stage: str,
        decision: str,
        decision_by: str,
        decision_reason: str,
        measured_values: dict[str, Any] | None = None,
        criteria_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        existing = self.get_by_design_hash(design_hash)
        if existing is None:
            raise KeyError(f"Hypothesis design_hash not found in registry: {design_hash}")
        timestamp = _now_str()
        run_id = _compute_run_id(run_dir, profile_id, gate_id)
        normalized = _normalize_decision(decision)
        self._locked_append(
            {
                "event_type": "gate_decision",
                "recorded_at": timestamp,
                "hypothesis_id": str(hypothesis_id),
                "design_hash": str(design_hash),
                "prose_hash": str(existing.get("prose_hash", "")),
                "structural_family": str(existing.get("structural_family", "")),
                "economic_family": str(existing.get("economic_family", "")),
                "profile_id": str(profile_id),
                "hypothesis_json": "",
                "run_id": run_id,
                "run_dir": str(Path(run_dir).resolve()),
                "gate_id": str(gate_id),
                "gate_stage": str(gate_stage),
                "decision": normalized,
                "decision_by": str(decision_by),
                "decision_reason": str(decision_reason),
                "measured_values_json": _json_dumps(measured_values or {}),
                "criteria_results_json": _json_dumps(criteria_results or []),
                "override_reason": "",
                "override_by": "",
            }
        )
        return {
            "hypothesis_id": str(hypothesis_id),
            "design_hash": str(design_hash),
            "run_id": run_id,
            "gate_id": str(gate_id),
            "gate_stage": str(gate_stage),
            "decision": normalized,
            "new_status": _status_from_gate(gate_stage, normalized),
        }

    def record_manual_override(
        self,
        *,
        hypothesis_id: str,
        design_hash: str,
        override_reason: str,
        override_by: str,
    ) -> dict[str, Any]:
        existing = self.get_by_design_hash(design_hash)
        if existing is None:
            raise KeyError(f"Hypothesis design_hash not found in registry: {design_hash}")
        timestamp = _now_str()
        row = self._locked_append(
            {
                "event_type": "manual_override",
                "recorded_at": timestamp,
                "hypothesis_id": str(hypothesis_id),
                "design_hash": str(design_hash),
                "prose_hash": str(existing.get("prose_hash", "")),
                "structural_family": str(existing.get("structural_family", "")),
                "economic_family": str(existing.get("economic_family", "")),
                "profile_id": "",
                "hypothesis_json": "",
                "run_id": "",
                "run_dir": "",
                "gate_id": "",
                "gate_stage": "",
                "decision": "",
                "decision_by": "",
                "decision_reason": "",
                "measured_values_json": "",
                "criteria_results_json": "",
                "override_reason": str(override_reason),
                "override_by": str(override_by),
            }
        )
        return {
            "hypothesis_id": str(hypothesis_id),
            "design_hash": str(design_hash),
            "event_id": str(row["event_id"]),
            "override_reason": str(override_reason),
        }

    def summary_text(self) -> str:
        master = self.master
        if master.empty:
            return "Hypothesis registry is empty."
        counts = master["status"].astype(str).value_counts().sort_index()
        lines = [f"Hypothesis registry: {len(master)} record(s)"]
        for status, count in counts.items():
            lines.append(f"- {status}: {int(count)}")
        return "\n".join(lines)
