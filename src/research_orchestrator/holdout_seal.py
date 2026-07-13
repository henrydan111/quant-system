"""Global holdout seal to prevent repeat OOS access for a design hash."""

from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.research_orchestrator.file_lock import file_lock

SEAL_COLUMNS = [
    "event_id",
    "recorded_at",
    "design_hash",
    "seal_key",
    "hypothesis_id",
    "structural_family",
    "profile_id",
    "run_dir",
    "step_id",
    "stage",
    # R4/D3.4 (calendar unfreeze): provider-generation binding of the spend.
    # Legacy rows backfill "" via the _load column loop.
    "provider_build_id",
    "calendar_policy_id",
    # PR3 REWORK (R1 Blocker 1/2): the claim is bound to ONE evaluation request; the
    # promotion gate cross-checks artifact.request_hash == seal_event.request_hash.
    "request_hash",
]

SEAL_SCHEMA = {
    "event_id": "string",
    "recorded_at": "string",
    "design_hash": "string",
    # PR P1.4: the seal is keyed by seal_key (defaults to design_hash for
    # back-compat). A FrozenSelectionSet-driven OOS run passes frozen_set_hash so the
    # holdout budget is spent per frozen selection set, not per mutable design_hash.
    "seal_key": "string",
    "hypothesis_id": "string",
    "structural_family": "string",
    "profile_id": "string",
    "run_dir": "string",
    "step_id": "string",
    "stage": "string",
    "provider_build_id": "string",
    "calendar_policy_id": "string",
    "request_hash": "string",
}


def resolve_configured_global_holdout_root() -> Path:
    """PR3 R4 Blocker 1 — the ONE configured global holdout-seal root. OOS claim paths
    must derive every sealed store (seal events, override authorizations, the canonical
    A5/A6 ledger, the A5 reproduction records) from THIS resolver — never from a
    caller-supplied path, which would let a caller fork a parallel sealed world and
    re-read the same OOS window. Resolution: ``research_governance.holdout_seal_root``
    in config.yaml when present, else the canonical ``<project_root>/data/holdout_seals``
    (the factor-eval CLI's historical default). Tests monkeypatch THIS function; they
    never pass a store path into a claim entry point."""
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            configured = (cfg.get("research_governance") or {}).get("holdout_seal_root")
            if configured:
                return Path(str(configured)).resolve()
        except Exception:  # noqa: BLE001 — unreadable config falls back to the canonical default
            pass
    return (project_root / "data" / "holdout_seals").resolve()


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
        # PR P1.4 back-compat: rows written before seal_key existed inherit
        # seal_key = design_hash, so an old design_hash-keyed seal still blocks a
        # re-claim under the default (seal_key defaults to design_hash). No mixed
        # write-seal_key / read-design_hash window: every read goes through here.
        if not frame.empty:
            blank = frame["seal_key"].isna() | (
                frame["seal_key"].astype("string").str.strip().fillna("") == ""
            )
            frame.loc[blank, "seal_key"] = frame.loc[blank, "design_hash"]
        return frame

    def list_events(
        self, design_hash: str | None = None, seal_key: str | None = None
    ) -> pd.DataFrame:
        frame = self._load()
        if seal_key is not None:
            frame = frame[frame["seal_key"] == str(seal_key)].copy()
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
        seal_key: str | None = None,
        provider_build_id: str = "",
        calendar_policy_id: str = "",
        request_hash: str = "",
    ) -> dict[str, Any]:
        """Claim OOS access for a seal_key (defaults to design_hash); raise if sealed.

        PR 4 of the 2026-05-26 freeze plan: the entire read-check-write
        sequence runs inside ``file_lock`` so two concurrent processes that
        attempt to claim the same design_hash CANNOT both pass the
        ``frame.empty`` check and both write a seal event. Without the lock,
        the only protection was atomic-write at the end, which prevents
        partial-file corruption but does NOT prevent duplicate seal events.

        Lock file: ``<root_dir>/holdout_events.lock``.
        """
        # PR P1.4: the seal is keyed by seal_key; empty/None falls back to design_hash
        # so existing callers (and old rows via the _load backfill) are unchanged.
        effective_seal_key = str(seal_key).strip() if seal_key else str(design_hash)
        normalized_run_dir = str(Path(run_dir).resolve())
        with file_lock(self.root_dir / "holdout_events.lock"):
            frame = self.list_events(seal_key=effective_seal_key)
            if not frame.empty:
                first_row = frame.iloc[0].to_dict()
                same_run = (
                    str(first_row.get("run_dir", "")) == normalized_run_dir
                    and str(first_row.get("step_id", "")) == str(step_id)
                )
                if allow_same_run and same_run:
                    # R4 (calendar unfreeze, D3.4): a crash-resume must not
                    # silently continue under a DIFFERENT provider generation —
                    # the claim was spent against specific data. Enforced when
                    # the resuming caller supplies its ids; a legacy recorded
                    # "" mismatching a real id fails closed too.
                    # PR3 REWORK (R1 Blocker 1): the same rule binds request_hash —
                    # a resume under a CHANGED evaluation request is a new spend
                    # attempt, never a recovery.
                    for column, current, why in (
                        ("provider_build_id", provider_build_id,
                         "provider generation changed — UNFREEZE_PLAN.md D3.4"),
                        ("calendar_policy_id", calendar_policy_id,
                         "provider generation changed — UNFREEZE_PLAN.md D3.4"),
                        ("request_hash", request_hash,
                         "the evaluation request changed — PR3 R1 Blocker 1"),
                    ):
                        recorded = str(first_row.get(column, "") or "")
                        if current and recorded != str(current):
                            raise ValueError(
                                f"Holdout seal recovery refused: claim for seal_key "
                                f"{effective_seal_key} was spent under {column}="
                                f"{recorded!r} but the resume runs under {current!r} "
                                f"({why})."
                            )
                    return first_row
                raise ValueError(
                    "Holdout sealed for seal_key "
                    f"{effective_seal_key} (design_hash {design_hash}); first access was "
                    f"{first_row.get('recorded_at')} by {first_row.get('run_dir')}"
                )

            recorded_at = _now_str()
            row = {
                "event_id": hashlib.sha256(
                    f"{effective_seal_key}|{normalized_run_dir}|{step_id}|{recorded_at}".encode("utf-8")
                ).hexdigest()[:16],
                "recorded_at": recorded_at,
                "design_hash": str(design_hash),
                "seal_key": effective_seal_key,
                "hypothesis_id": str(hypothesis_id),
                "structural_family": str(structural_family),
                "profile_id": str(profile_id),
                "run_dir": normalized_run_dir,
                "step_id": str(step_id),
                "stage": str(stage),
                # R4/D3.4 generation binding ("" = legacy caller, unset sentinel)
                "provider_build_id": str(provider_build_id),
                "calendar_policy_id": str(calendar_policy_id),
                # PR3: the one-request binding ("" = legacy caller)
                "request_hash": str(request_hash),
            }
            frame = pd.concat([self._load(), pd.DataFrame([row])], ignore_index=True)
            _atomic_write_dataframe(frame, self.log_path)
            return row
