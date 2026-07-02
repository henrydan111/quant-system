"""Shared live-provider context helpers (side-effect-free).

UNFREEZE_PLAN.md Phase 2 wall, GPT Round-4 m2 (neutral module) + M3
(rotation-safe caching): both sanctioned data doors — the sandbox
``pit_research_loader`` and the formal ``qlib_windowed_features`` — resolve
the live provider's identity and spent-OOS boundary through THIS module, not
through each other.

Reading the LIVE manifest here is the documented exception to the
no-global-policy invariant (D1): the subject of these helpers IS the live
provider (D3 clamps + cache generation binding). Formal artifact replay must
NEVER route through these helpers — it uses the artifact-recorded ids.

Rotation safety (R4-M3): results are cached keyed by the provider manifest
file's ``(st_mtime_ns, st_size)`` — a provider rotation rewrites
``provider_build.json``, so the next call in ANY long-lived process (dashboard
task, orchestrator daemon) re-resolves instead of serving the pre-rotation
identity. Resolution failures always fail closed (raise).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProviderContextError(RuntimeError):
    """Live provider identity/boundary resolution failed — callers fail closed."""


def _data_root() -> Path:
    with open(_PROJECT_ROOT / "config.yaml", "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    raw = (((cfg.get("storage") or {}).get("data_root")) or "./data")
    root = Path(raw)
    return root if root.is_absolute() else (_PROJECT_ROOT / root).resolve()


def _qlib_dir() -> Path:
    return _data_root() / "qlib_data"


# (manifest_stat_key) -> (build_id, policy_id, spent_oos_end_ts, fresh_holdout_start)
_CACHE: dict[tuple[int, int], tuple[str, str, pd.Timestamp, Optional[str]]] = {}


def _resolve() -> tuple[str, str, pd.Timestamp, Optional[str]]:
    from src.data_infra.provider_manifest import load_provider_manifest, manifest_path_for
    from src.research_orchestrator.calendar_policy import (
        load_calendar_policy,
        resolve_spent_oos_boundary,
    )

    qlib_dir = _qlib_dir()
    try:
        manifest_file = Path(manifest_path_for(qlib_dir))
        stat = manifest_file.stat()
        key = (stat.st_mtime_ns, stat.st_size)
    except Exception as exc:
        raise ProviderContextError(
            f"cannot stat the live provider manifest under {qlib_dir}: {exc} — fail closed."
        ) from exc

    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    try:
        manifest = load_provider_manifest(qlib_dir)
        cal_lines = [
            ln.strip()
            for ln in (qlib_dir / "calendars" / "day.txt").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        policy = load_calendar_policy(
            manifest.calendar_policy_id,
            root=_PROJECT_ROOT / "config" / "calendar_policies",
        )
        boundary = resolve_spent_oos_boundary(policy, cal_lines[-1])
    except Exception as exc:
        raise ProviderContextError(
            f"cannot resolve live provider identity/boundary (manifest/policy/calendar): "
            f"{exc} — fail closed."
        ) from exc

    result = (
        str(manifest.provider_build_id),
        str(manifest.calendar_policy_id),
        pd.Timestamp(boundary.spent_oos_end),
        boundary.fresh_holdout_start,
    )
    _CACHE.clear()  # keep exactly the current generation
    _CACHE[key] = result
    return result


def live_provider_ids() -> tuple[str, str]:
    """(provider_build_id, calendar_policy_id) RECORDED by the live manifest."""
    build_id, policy_id, _, _ = _resolve()
    return build_id, policy_id


def live_spent_oos_end() -> pd.Timestamp:
    """The D3 spent-OOS clamp boundary for the live provider."""
    _, _, spent, _ = _resolve()
    return spent


def refresh_live_provider_context() -> None:
    """Explicit invalidation hook for the safe-publish ceremony (R4-M3 option C
    belt — the stat-key mechanism already invalidates on manifest rewrite)."""
    _CACHE.clear()
