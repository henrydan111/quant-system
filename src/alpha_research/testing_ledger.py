"""Append-only testing ledger keyed by structural and economic families."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EVENT_COLUMNS = [
    "event_id",
    "recorded_at",
    "event_kind",
    "related_event_id",
    "supersedes_event_id",
    "hypothesis_id",
    "design_hash",
    "prose_hash",
    "structural_family",
    "economic_family",
    "profile_id",
    "run_id",
    "run_dir",
    "test_name",
    "stage",
    "statistic_name",
    "statistic_value",
    "p_value",
    "n_obs",
    "sharpe",
    "cost_bps_assumed",
    "verdict",
    "decision_by",
    "decision_reason",
    "notes",
]

EVENT_SCHEMA = {
    "event_id": "string",
    "recorded_at": "string",
    "event_kind": "string",
    "related_event_id": "string",
    "supersedes_event_id": "string",
    "hypothesis_id": "string",
    "design_hash": "string",
    "prose_hash": "string",
    "structural_family": "string",
    "economic_family": "string",
    "profile_id": "string",
    "run_id": "string",
    "run_dir": "string",
    "test_name": "string",
    "stage": "string",
    "statistic_name": "string",
    "statistic_value": "Float64",
    "p_value": "Float64",
    "n_obs": "Int64",
    "sharpe": "Float64",
    "cost_bps_assumed": "Float64",
    "verdict": "string",
    "decision_by": "string",
    "decision_reason": "string",
    "notes": "string",
}

EVENT_KINDS = ("measurement", "verdict", "register", "manual_override")


def _now() -> datetime:
    return datetime.now()


def _now_str() -> str:
    return _now().strftime("%Y-%m-%d %H:%M:%S")


def _make_temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")


def _atomic_write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(path)
    df.to_parquet(temp_path, index=False)
    os.replace(temp_path, path)


def _empty_frame() -> pd.DataFrame:
    frame = pd.DataFrame(columns=EVENT_COLUMNS)
    for column, dtype in EVENT_SCHEMA.items():
        frame[column] = frame[column].astype(dtype)
    return frame


def _append_row(frame: pd.DataFrame, row: dict[str, Any]) -> pd.DataFrame:
    new_row = pd.DataFrame([row])
    for column in EVENT_COLUMNS:
        if column not in new_row.columns:
            new_row[column] = pd.NA
    new_row = new_row[EVENT_COLUMNS]
    for column, dtype in EVENT_SCHEMA.items():
        new_row[column] = new_row[column].astype(dtype)
    if frame.empty:
        return new_row.reset_index(drop=True)
    return pd.concat([frame, new_row], ignore_index=True)


class TestingLedgerStore:
    """Append-only daily shard store for multiple-testing accounting."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _shard_path(self, day: datetime | None = None) -> Path:
        stamp = (day or _now()).strftime("%Y%m%d")
        return self.root_dir / f"testing_events_{stamp}.parquet"

    def _load_shard(self, path: Path) -> pd.DataFrame:
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

    def _event_id(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def record_event(
        self,
        *,
        hypothesis_id: str,
        design_hash: str,
        prose_hash: str,
        structural_family: str,
        profile_id: str,
        run_id: str,
        run_dir: str,
        test_name: str,
        stage: str,
        statistic_name: str,
        statistic_value: float | None = None,
        p_value: float | None = None,
        n_obs: int | None = None,
        sharpe: float | None = None,
        cost_bps_assumed: float | None = None,
        notes: str = "",
        economic_family: str = "",
        event_kind: str = "measurement",
        related_event_id: str = "",
        supersedes_event_id: str = "",
        verdict: str = "",
        decision_by: str = "",
        decision_reason: str = "",
    ) -> dict[str, Any]:
        if event_kind not in EVENT_KINDS:
            raise ValueError(f"Unsupported testing-ledger event_kind: {event_kind}")
        recorded_at = _now_str()
        row = {
            "event_id": self._event_id(
                {
                    "hypothesis_id": hypothesis_id,
                    "design_hash": design_hash,
                    "run_id": run_id,
                    "test_name": test_name,
                    "stage": stage,
                    "recorded_at": recorded_at,
                    "event_kind": event_kind,
                    "related_event_id": related_event_id,
                    "supersedes_event_id": supersedes_event_id,
                }
            ),
            "recorded_at": recorded_at,
            "event_kind": str(event_kind),
            "related_event_id": str(related_event_id),
            "supersedes_event_id": str(supersedes_event_id),
            "hypothesis_id": str(hypothesis_id),
            "design_hash": str(design_hash),
            "prose_hash": str(prose_hash),
            "structural_family": str(structural_family),
            "economic_family": str(economic_family),
            "profile_id": str(profile_id),
            "run_id": str(run_id),
            "run_dir": str(Path(run_dir).resolve()),
            "test_name": str(test_name),
            "stage": str(stage),
            "statistic_name": str(statistic_name),
            "statistic_value": statistic_value,
            "p_value": p_value,
            "n_obs": n_obs,
            "sharpe": sharpe,
            "cost_bps_assumed": cost_bps_assumed,
            "verdict": str(verdict),
            "decision_by": str(decision_by),
            "decision_reason": str(decision_reason),
            "notes": str(notes),
        }
        shard_path = self._shard_path()
        shard = _append_row(self._load_shard(shard_path), row)
        _atomic_write_dataframe(shard, shard_path)
        return row

    def record_verdict(
        self,
        *,
        related_event_id: str,
        design_hash: str,
        verdict: str,
        decision_by: str,
        reason: str,
        run_id: str,
        run_dir: str,
    ) -> dict[str, Any]:
        measurement = self.get_event(related_event_id)
        if measurement is None:
            raise KeyError(f"Measurement event not found: {related_event_id}")
        prior = self.get_verdict_for_measurement(related_event_id)
        return self.record_event(
            hypothesis_id=str(measurement.get("hypothesis_id", "")),
            design_hash=str(design_hash),
            prose_hash=str(measurement.get("prose_hash", "")),
            structural_family=str(measurement.get("structural_family", "")),
            economic_family=str(measurement.get("economic_family", "")),
            profile_id=str(measurement.get("profile_id", "")),
            run_id=str(run_id),
            run_dir=str(run_dir),
            test_name=str(measurement.get("test_name", "")),
            stage=str(measurement.get("stage", "")),
            statistic_name=str(measurement.get("statistic_name", "")),
            statistic_value=measurement.get("statistic_value"),
            p_value=measurement.get("p_value"),
            n_obs=measurement.get("n_obs"),
            sharpe=measurement.get("sharpe"),
            cost_bps_assumed=measurement.get("cost_bps_assumed"),
            notes=str(reason),
            event_kind="verdict",
            related_event_id=str(related_event_id),
            supersedes_event_id=str(prior.get("event_id", "")) if prior is not None else "",
            verdict=str(verdict),
            decision_by=str(decision_by),
            decision_reason=str(reason),
        )

    def list_events(
        self,
        *,
        structural_family: str | None = None,
        design_hash: str | None = None,
        event_kind: str | None = None,
        economic_family: str | None = None,
    ) -> pd.DataFrame:
        shards = sorted(self.root_dir.glob("testing_events_*.parquet"))
        if not shards:
            return _empty_frame()
        frames = [self._load_shard(path) for path in shards]
        frame = pd.concat(frames, ignore_index=True) if frames else _empty_frame()
        if structural_family:
            frame = frame[frame["structural_family"] == str(structural_family)].copy()
        if design_hash:
            frame = frame[frame["design_hash"] == str(design_hash)].copy()
        if event_kind:
            frame = frame[frame["event_kind"] == str(event_kind)].copy()
        if economic_family:
            frame = frame[frame["economic_family"] == str(economic_family)].copy()
        return frame.reset_index(drop=True)

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        frame = self.list_events()
        frame = frame[frame["event_id"] == str(event_id)].copy()
        if frame.empty:
            return None
        return frame.sort_values("recorded_at").tail(1).iloc[0].to_dict()

    def family_test_count(self, structural_family: str, *, kind: str | None = None) -> int:
        frame = self.list_events(structural_family=structural_family, event_kind=kind)
        return int(len(frame))

    def get_economic_family_count(self, economic_family: str) -> int:
        frame = self.list_events(economic_family=economic_family, event_kind="measurement")
        return int(len(frame))

    def get_family_variance(self, structural_family: str) -> float | None:
        frame = self.list_events(structural_family=structural_family, event_kind="measurement")
        sharpes = frame["sharpe"].dropna().astype(float).values
        if len(sharpes) < 2:
            return None
        return float(np.var(sharpes, ddof=1))

    def get_verdict_for_measurement(self, event_id: str) -> dict[str, Any] | None:
        frame = self.list_events(event_kind="verdict")
        frame = frame[frame["related_event_id"] == str(event_id)].copy()
        if frame.empty:
            return None
        return frame.sort_values("recorded_at").tail(1).iloc[0].to_dict()
