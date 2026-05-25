from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.research_orchestrator.cache_manifest import (
    CacheContext,
    CacheManifestStore,
    get_cache_context,
)


def _deterministic_cache_path(freq: str, fields: list[str], start: str, end: str) -> str:
    payload = {
        "freq": freq,
        "fields": sorted(str(field) for field in fields),
        "start": str(start),
        "end": str(end),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"qlib::{freq}::{digest}"


def qlib_windowed_features(
    *,
    instruments: Any,
    fields: list[str],
    start_time: str,
    end_time: str,
    cache_context: CacheContext,
    stage: str,
    freq: str = "day",
    cache_manifest_dir: str | Path = "data/hypothesis_cache_manifest",
) -> pd.DataFrame:
    from qlib.data import D

    effective_context = cache_context
    inherited_context = get_cache_context()
    if inherited_context is not None and not any(
        [
            effective_context.design_hash,
            effective_context.hypothesis_id,
            effective_context.structural_family,
            effective_context.profile_id,
            effective_context.run_dir,
            effective_context.step_id,
        ]
    ):
        effective_context = inherited_context
    manifest = CacheManifestStore(cache_manifest_dir)
    cache_key = _deterministic_cache_path(freq, fields, start_time, end_time)
    cache_path = cache_key
    manifest.assert_cache_reusable(
        cache_key=cache_key,
        cache_path=cache_path,
        cache_context=effective_context,
        stage=stage,
        window_start=start_time,
        window_end=end_time,
        cache_type="qlib_features",
    )
    frame = D.features(
        instruments,
        list(fields),
        start_time=start_time,
        end_time=end_time,
    )
    if not frame.empty and isinstance(frame.index, pd.MultiIndex):
        date_values = pd.to_datetime(frame.index.get_level_values("datetime"))
        mask = (date_values >= pd.Timestamp(start_time)) & (date_values <= pd.Timestamp(end_time))
        frame = frame[mask].copy()
    manifest.record_cache_write(
        cache_type="qlib_features",
        cache_key=cache_key,
        cache_path=cache_path,
        cache_context=effective_context,
        stage=stage,
        window_start=start_time,
        window_end=end_time,
    )
    return frame
