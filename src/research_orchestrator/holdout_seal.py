"""Global holdout seal to prevent repeat OOS access for a design hash."""

from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

SEAL_COLUMNS = [
    "event_id",
    "recorded_at",
    "design_hash",
    "hypothesis_id",
    "structural_family",
    "profile_id",
    "run_dir",
    "step_id",
    "stage",
]

SEAL_SCHEMA = {
    "event_id": "string",
    "recorded_at": "string",
    "design_hash": "string",
    "hypothesis_id": "string",
    "structural_family": "string",
    "profile_id": "string",
    "run_dir": "string",
    "step_id": "string",
    "stage": "string",
}


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _make_temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")


def _atomic_write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(path)
    df.to_parquet(temp_path, index=False)
    os.replace(temp_path, path)


def _empty_frame() -> pd.DataFrame:
    frame = pd.DataFrame(columns=SEAL_COLUMNS)
    for column, dtype in SEAL_SCHEMA.items():
        frame[column] = frame[column].astype(dtype)
    return frame


class HoldoutSealStore:
    """Append-only global seal log for holdout access."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root_dir / "holdout_events.parquet"

    def _load(self) -> pd.DataFrame:
        if not self.log_path.exists():
            return _empty_frame()
        frame = pd.read_parquet(self.log_path)
        for column in SEAL_COLUMNS:
            if column not in frame.columns:
                frame[column] = pd.NA
        frame = frame[SEAL_COLUMNS].copy()
        for column, dtype in SEAL_SCHEMA.items():
            frame[column] = frame[column].astype(dtype)
        return frame

    def list_events(self, design_hash: str | None = None) -> pd.DataFrame:
        frame = self._load()
        if design_hash is not None:
            frame = frame[frame["design_hash"] == str(design_hash)].copy()
        return frame.reset_index(drop=True)

    def claim_holdout_access(
        self,
        *,
        design_hash: str,
        hypothesis_id: str,
        structural_family: str,
        profile_id: str,
        run_dir: str,
        step_id: str,
        stage: str = "oos_test",
        allow_same_run: bool = False,
    ) -> dict[str, Any]:
        frame = self.list_events(design_hash=design_hash)
        normalized_run_dir = str(Path(run_dir).resolve())
        if not frame.empty:
            first_row = frame.iloc[0].to_dict()
            same_run = (
                str(first_row.get("run_dir", "")) == normalized_run_dir
                and str(first_row.get("step_id", "")) == str(step_id)
            )
            if allow_same_run and same_run:
                return first_row
            raise ValueError(
                "Holdout sealed for design_hash "
                f"{design_hash}; first access was {first_row.get('recorded_at')} "
                f"by {first_row.get('run_dir')}"
            )

        recorded_at = _now_str()
        row = {
            "event_id": hashlib.sha256(
                f"{design_hash}|{normalized_run_dir}|{step_id}|{recorded_at}".encode("utf-8")
            ).hexdigest()[:16],
            "recorded_at": recorded_at,
            "design_hash": str(design_hash),
            "hypothesis_id": str(hypothesis_id),
            "structural_family": str(structural_family),
            "profile_id": str(profile_id),
            "run_dir": normalized_run_dir,
            "step_id": str(step_id),
            "stage": str(stage),
        }
        frame = pd.concat([self._load(), pd.DataFrame([row])], ignore_index=True)
        _atomic_write_dataframe(frame, self.log_path)
        return row
