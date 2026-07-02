from __future__ import annotations

import contextvars
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.research_orchestrator.file_lock import file_lock


DEFAULT_CACHE_MANIFEST_DIR = Path("data/hypothesis_cache_manifest")

CACHE_MANIFEST_COLUMNS = (
    "manifest_id",
    "recorded_at",
    "cache_type",
    "cache_key",
    "cache_path",
    "design_hash",
    "hypothesis_id",
    "structural_family",
    "profile_id",
    "run_dir",
    "step_id",
    "stage",
    "window_start",
    "window_end",
    # UNFREEZE_PLAN.md Phase 2 (GPT R2-M4): provider-generation binding — a
    # cache written under one provider build/policy must not be reused under
    # another. Legacy rows backfill "" and therefore fail the reuse check
    # against a real id (one-time safe invalidation after a rotation).
    "provider_build_id",
    "calendar_policy_id",
)

CACHE_MANIFEST_SCHEMA = {
    "manifest_id": "string",
    "recorded_at": "string",
    "cache_type": "string",
    "cache_key": "string",
    "cache_path": "string",
    "design_hash": "string",
    "hypothesis_id": "string",
    "structural_family": "string",
    "profile_id": "string",
    "run_dir": "string",
    "step_id": "string",
    "stage": "string",
    "window_start": "string",
    "window_end": "string",
    "provider_build_id": "string",
    "calendar_policy_id": "string",
}


def _now_str() -> str:
    return pd.Timestamp.utcnow().tz_localize(None).strftime("%Y-%m-%d %H:%M:%S")


def _make_temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")


def _atomic_write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(path)
    df.to_parquet(temp_path, index=False)
    os.replace(temp_path, path)


def _empty_frame() -> pd.DataFrame:
    frame = pd.DataFrame(columns=CACHE_MANIFEST_COLUMNS)
    for column, dtype in CACHE_MANIFEST_SCHEMA.items():
        frame[column] = frame[column].astype(dtype)
    return frame


def _append_row(frame: pd.DataFrame, row: dict[str, Any]) -> pd.DataFrame:
    new_row = pd.DataFrame([row])
    for column in CACHE_MANIFEST_COLUMNS:
        if column not in new_row.columns:
            new_row[column] = ""
    new_row = new_row[list(CACHE_MANIFEST_COLUMNS)]
    for column, dtype in CACHE_MANIFEST_SCHEMA.items():
        new_row[column] = new_row[column].astype(dtype)
    if frame.empty:
        return new_row.reset_index(drop=True)
    return pd.concat([frame, new_row], ignore_index=True)


class CacheKeyMismatchError(ValueError):
    """Raised when a cached artifact is reused across the wrong hypothesis window or stage."""


@dataclass(frozen=True)
class CacheContext:
    design_hash: str = ""
    hypothesis_id: str = ""
    structural_family: str = ""
    profile_id: str = ""
    run_dir: str = ""
    step_id: str = ""


_CACHE_CONTEXT: contextvars.ContextVar[CacheContext | None] = contextvars.ContextVar("cache_context", default=None)


def set_cache_context(cache_context: CacheContext | None):
    return _CACHE_CONTEXT.set(cache_context)


def reset_cache_context(token: contextvars.Token[CacheContext | None]) -> None:
    _CACHE_CONTEXT.reset(token)


def get_cache_context() -> CacheContext | None:
    return _CACHE_CONTEXT.get()


class CacheManifestStore:
    def __init__(self, root_dir: str | Path = DEFAULT_CACHE_MANIFEST_DIR):
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root_dir / "cache_events.parquet"

    def _load(self) -> pd.DataFrame:
        if not self.log_path.exists():
            return _empty_frame()
        frame = pd.read_parquet(self.log_path)
        for column in CACHE_MANIFEST_COLUMNS:
            if column not in frame.columns:
                frame[column] = ""
        frame = frame[list(CACHE_MANIFEST_COLUMNS)].copy()
        for column, dtype in CACHE_MANIFEST_SCHEMA.items():
            frame[column] = frame[column].astype(dtype)
        return frame

    def list_events(self, *, cache_key: str | None = None, cache_path: str | None = None) -> pd.DataFrame:
        frame = self._load()
        if cache_key is not None:
            frame = frame[frame["cache_key"] == str(cache_key)].copy()
        if cache_path is not None:
            frame = frame[frame["cache_path"] == str(cache_path)].copy()
        return frame.reset_index(drop=True)

    def record_cache_write(
        self,
        *,
        cache_type: str,
        cache_key: str,
        cache_path: str,
        cache_context: CacheContext,
        stage: str,
        window_start: str,
        window_end: str,
        provider_build_id: str,
        calendar_policy_id: str,
    ) -> dict[str, Any]:
        """Append a cache-write event to the manifest.

        R4-M4/M5: the provider-generation ids are REQUIRED non-blank — no new
        cache row may record an empty generation (legacy rows written before
        this rule carry "" and are refused on reuse).

        PR 4 of the 2026-05-26 freeze plan: the entire read-append-write
        sequence runs inside ``file_lock`` so concurrent processes do not
        lose rows. Without the lock, two simultaneous calls would each call
        ``_load`` and observe the same baseline frame, each append their own
        row, and the second ``_atomic_write_dataframe`` would overwrite the
        first one's row.

        Lock file: ``<root_dir>/cache_events.lock``.
        """
        for _name, _value in (
            ("provider_build_id", provider_build_id),
            ("calendar_policy_id", calendar_policy_id),
        ):
            if not _value or not str(_value).strip():
                raise CacheKeyMismatchError(
                    f"record_cache_write requires a non-blank {_name} "
                    "(R4-M4: no new cache row without a provider generation)."
                )
        recorded_at = _now_str()
        row = {
            "manifest_id": hashlib.sha256(
                json.dumps(
                    {
                        "cache_key": cache_key,
                        "cache_path": cache_path,
                        "design_hash": cache_context.design_hash,
                        "stage": stage,
                        "window_start": window_start,
                        "window_end": window_end,
                        "recorded_at": recorded_at,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()[:16],
            "recorded_at": recorded_at,
            "cache_type": str(cache_type),
            "cache_key": str(cache_key),
            "cache_path": str(cache_path),
            "design_hash": str(cache_context.design_hash),
            "hypothesis_id": str(cache_context.hypothesis_id),
            "structural_family": str(cache_context.structural_family),
            "profile_id": str(cache_context.profile_id),
            "run_dir": str(cache_context.run_dir),
            "step_id": str(cache_context.step_id),
            "stage": str(stage),
            "window_start": str(window_start),
            "window_end": str(window_end),
            "provider_build_id": str(provider_build_id),
            "calendar_policy_id": str(calendar_policy_id),
        }
        with file_lock(self.root_dir / "cache_events.lock"):
            frame = _append_row(self._load(), row)
            _atomic_write_dataframe(frame, self.log_path)
        return row

    def assert_cache_reusable(
        self,
        *,
        cache_key: str,
        cache_path: str,
        cache_context: CacheContext,
        stage: str,
        window_start: str,
        window_end: str,
        cache_type: str = "",
        provider_build_id: str,
        calendar_policy_id: str,
    ) -> None:
        """Verify a cached artifact is reusable under the current context.

        R4-M4: the provider-generation ids are REQUIRED non-blank; a legacy
        manifest row (recorded "" before the generation-binding rule) then
        mismatches the real ids and is REFUSED — refusal is the deliberate
        legacy-invalidation path (the monthly bump ceremony archives the cache
        manifest; no silent migration mode is reachable from research doors).

        ``cache_type`` controls the design_hash check (Part B, plan
        ``snappy-buzzing-meerkat`` v5):

        - ``cache_type == "qlib_features"``: raw OHLCV/Qlib expressions are
          deterministic across hypotheses, so design_hash mismatches are
          permitted (the loaded data is identical regardless of which
          hypothesis triggered the load). Stage and window mismatches are
          STILL fatal.
        - any other value (including the legacy default ``""``): design_hash
          mismatches remain fatal — the generic guardrail is preserved for
          hypothesis-isolated caches (factor-screening intermediate results,
          ML model checkpoints, etc.) that may be added later.
        """
        for _name, _value in (
            ("provider_build_id", provider_build_id),
            ("calendar_policy_id", calendar_policy_id),
        ):
            if not _value or not str(_value).strip():
                raise CacheKeyMismatchError(
                    f"assert_cache_reusable requires a non-blank {_name} "
                    "(R4-M4: generation binding is mandatory on every reuse check)."
                )
        events = self.list_events(cache_key=cache_key, cache_path=cache_path)
        if events.empty:
            return
        latest = events.sort_values("recorded_at").iloc[-1]
        if cache_type != "qlib_features":
            if str(latest["design_hash"]) != str(cache_context.design_hash):
                raise CacheKeyMismatchError(
                    f"Cache manifest mismatch for {cache_path}: design_hash {latest['design_hash']} != {cache_context.design_hash}"
                )
        if str(latest["stage"]) != str(stage):
            raise CacheKeyMismatchError(
                f"Cache manifest mismatch for {cache_path}: stage {latest['stage']} != {stage}"
            )
        if str(latest["window_start"]) != str(window_start) or str(latest["window_end"]) != str(window_end):
            raise CacheKeyMismatchError(
                f"Cache manifest mismatch for {cache_path}: window "
                f"{latest['window_start']}..{latest['window_end']} != {window_start}..{window_end}"
            )
        # UNFREEZE_PLAN.md Phase 2 (GPT R2-M4): provider-generation binding.
        # Enforced only when the caller supplies the current ids; a legacy row
        # (backfilled "") then mismatches a real id and the cache is refused —
        # a one-time safe invalidation after any provider rotation.
        for column, current in (
            ("provider_build_id", provider_build_id),
            ("calendar_policy_id", calendar_policy_id),
        ):
            if current and str(latest.get(column, "")) != str(current):
                raise CacheKeyMismatchError(
                    f"Cache manifest mismatch for {cache_path}: {column} "
                    f"{latest.get(column, '')!r} != {current!r} — caches do not "
                    "survive a provider rotation (UNFREEZE_PLAN.md M4 binding)."
                )
