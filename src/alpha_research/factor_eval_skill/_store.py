"""Append-only, file-locked sidecar store base for factor-eval-skill provenance.

Mirrors the ``HoldoutSealStore`` pattern (``src/research_orchestrator/holdout_seal.py``):
a string-typed COLUMNS/SCHEMA, an atomic temp-write + ``os.replace``, and the ENTIRE
read-append inside ``file_lock``. These sidecars NEVER add columns to ``factor_master``
(D1: keep the 44-col master schema + its parity tests stable; isolate new provenance so
it can evolve without a master migration).

All columns are stored as strings (like ``HoldoutSealStore``); concrete stores encode
structured fields to canonical JSON and numbers/booleans to their string form, so the
on-disk schema is dtype-stable and parquet-portable. Consumers parse as needed.
"""
from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from src.research_orchestrator.file_lock import file_lock


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _make_temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")


def _atomic_write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(path)
    df.to_parquet(temp_path, index=False)
    os.replace(temp_path, path)


class PublicRecordDisabledError(RuntimeError):
    """Raised when public ``record()`` is invoked on a STATE-MACHINE store (PR3 R9 B1):
    state changes must go through the sanctioned typed transitions — even via the
    unbound base-class entry ``AppendOnlyStore.record(store, ...)``."""


class AppendOnlyStore:
    """Append-only parquet store with a string schema and file-locked writes.

    Subclasses set ``FILENAME``, ``COLUMNS`` (must include ``record_id`` + ``recorded_at``),
    ``SCHEMA`` (all-``"string"`` dtype map), and ``KEY_FIELDS`` (the columns identifying a
    logical record). ``record(**fields)`` writes one row inside ``file_lock``;
    ``latest(**key_filter)`` returns the most-recently-recorded matching row.

    PR3 R9 Blocker 1: a STATE-MACHINE subclass declares ``PUBLIC_RECORD_ENABLED = False``
    — the guard lives IN THE BASE METHOD (checking the actual instance's class), so the
    unbound call ``AppendOnlyStore.record(state_store, state="claimed", ...)`` cannot
    bypass a subclass override and roll an observed state (e.g. ``execution_started``)
    back to re-execute a spent OOS.
    """

    FILENAME: str = ""
    COLUMNS: tuple[str, ...] = ()
    SCHEMA: Mapping[str, str] = {}
    KEY_FIELDS: tuple[str, ...] = ()
    PUBLIC_RECORD_ENABLED: bool = True

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root_dir / self.FILENAME
        self.lock_path = self.root_dir / f"{self.FILENAME}.lock"

    def _empty_frame(self) -> pd.DataFrame:
        frame = pd.DataFrame(columns=list(self.COLUMNS))
        for column, dtype in self.SCHEMA.items():
            frame[column] = frame[column].astype(dtype)
        return frame

    def _load(self) -> pd.DataFrame:
        if not self.log_path.exists():
            return self._empty_frame()
        frame = pd.read_parquet(self.log_path)
        for column in self.COLUMNS:
            if column not in frame.columns:
                frame[column] = pd.NA
        frame = frame[list(self.COLUMNS)].copy()
        for column, dtype in self.SCHEMA.items():
            frame[column] = frame[column].astype(dtype)
        return frame

    def list_all(self) -> pd.DataFrame:
        """Every recorded row, in append order."""
        return self._load().reset_index(drop=True)

    def _record_id(self, row: Mapping[str, Any], recorded_at: str) -> str:
        key = "|".join(str(row.get(field, "")) for field in self.KEY_FIELDS)
        # time_ns salt guarantees uniqueness even for same-second appends of one key.
        return hashlib.sha256(f"{key}|{recorded_at}|{time.time_ns()}".encode("utf-8")).hexdigest()[:16]

    def record(self, **fields: Any) -> dict[str, Any]:
        """Append one row inside ``file_lock``. Unknown keys are rejected fail-closed;
        omitted columns default to empty string. ``record_id`` + ``recorded_at`` are
        stamped here. Returns the written row."""
        # R9 Blocker 1: the check sits HERE (the base method, against the actual
        # instance's class) so AppendOnlyStore.record(state_store, ...) — the unbound
        # bypass of a subclass override — also refuses.
        if type(self).PUBLIC_RECORD_ENABLED is not True:
            raise PublicRecordDisabledError(
                f"{type(self).__name__} is a state machine; public record() is disabled "
                "— state changes go only through the sanctioned typed transitions"
            )
        unknown = set(fields) - set(self.COLUMNS)
        unknown -= {"record_id", "recorded_at"}
        if unknown:
            raise ValueError(f"{type(self).__name__}.record got unknown fields: {sorted(unknown)}")
        with file_lock(self.lock_path):
            recorded_at = _now_str()
            row: dict[str, Any] = {column: "" for column in self.COLUMNS}
            for key, value in fields.items():
                row[key] = "" if value is None else value
            row["recorded_at"] = recorded_at
            row["record_id"] = self._record_id(row, recorded_at)
            frame = pd.concat([self._load(), pd.DataFrame([row])], ignore_index=True)
            _atomic_write_dataframe(frame, self.log_path)
            return row

    def latest(self, **key_filter: Any) -> dict[str, Any] | None:
        """The most-recently-recorded row matching every given key field, or ``None``.
        Uses a stable sort on ``recorded_at`` so equal-timestamp rows keep append order
        (the last appended wins)."""
        frame = self._load()
        for key, value in key_filter.items():
            frame = frame[frame[key].astype("string") == str(value)]
        if frame.empty:
            return None
        ordered = frame.sort_values("recorded_at", kind="stable")
        return ordered.iloc[-1].to_dict()
