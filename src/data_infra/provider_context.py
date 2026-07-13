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

Rotation safety (R4-M3, hardened by R5-M7 to CONTENT identity): results are
cached keyed by the provider manifest file's
``(path, st_mtime_ns, st_size, sha256(provider_build.json))``. The sha256 is
over the manifest file only (~1KB — negligible), computed on EVERY call, so a
rotation is detected even when a rewrite preserves size and coarse-granularity
mtime (Windows / copied / atomic-publish filesystems) — without this, a
long-lived process (dashboard task, orchestrator daemon) could stamp
cache/seal/promotion provenance with stale ids. Resolution failures always
fail closed (raise).
"""
from __future__ import annotations

import hashlib
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


# (path, st_mtime_ns, st_size, manifest_sha256)
#   -> (build_id, policy_id, spent_oos_end_ts, fresh_holdout_start)
_CACHE: dict[tuple[str, int, int, str], tuple[str, str, pd.Timestamp, Optional[str]]] = {}


def _resolve() -> tuple[str, str, pd.Timestamp, Optional[str]]:
    from src.data_infra.provider_manifest import load_provider_manifest, manifest_path_for
    from src.research_orchestrator.calendar_policy import (
        load_calendar_policy,
        resolve_spent_oos_boundary,
    )

    qlib_dir = _qlib_dir()
    try:
        manifest_file = Path(manifest_path_for(qlib_dir))
        # R5-M7: content identity, not only (mtime, size) — hash the manifest
        # bytes on every call so a same-size / preserved-mtime rewrite still
        # invalidates the cache. R6-m5 TOCTOU hardening: stat-before / read /
        # stat-after — a manifest mutated mid-read fails closed (retry).
        stat_before = manifest_file.stat()
        digest = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
        stat = manifest_file.stat()
    except Exception as exc:
        raise ProviderContextError(
            f"cannot stat/read the live provider manifest under {qlib_dir}: {exc} — fail closed."
        ) from exc
    if (stat_before.st_mtime_ns, stat_before.st_size) != (stat.st_mtime_ns, stat.st_size):
        raise ProviderContextError(
            f"live provider manifest under {qlib_dir} changed during read — "
            "fail closed (mid-publish; retry)."
        )
    # Phase 5-B B6: the publish-state marker is part of the provider's IDENTITY for gated
    # reads — fold its content digest into the cache key so a --finalize-qa flip (which
    # does not touch the manifest) re-runs the gates instead of serving a cached verdict.
    state_file = qlib_dir / "metadata" / "publish_state.json"
    try:
        state_digest = (
            hashlib.sha256(state_file.read_bytes()).hexdigest() if state_file.exists() else "absent"
        )
    except Exception as exc:
        raise ProviderContextError(
            f"cannot read the live provider publish-state marker under {qlib_dir}: {exc} — fail closed."
        ) from exc
    key = (str(manifest_file), stat.st_mtime_ns, stat.st_size, digest + ":" + state_digest)

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

    # Phase 5-B (GPT re-review Blockers 5 + 6): BOTH sanctioned data doors — the sandbox
    # pit_research_loader and the formal qlib_windowed_features — resolve through here, so
    # this is where the raw-input attestation and the QA-quarantine publish-state become
    # load-bearing for every gated read (the event-driven runtime validator re-checks them
    # independently for formal backtests). Gate errors surface verbatim, wrapped as the
    # fail-closed context error callers already handle.
    try:
        from src.research_orchestrator.release_gate import (
            assert_provider_publish_state,
            assert_provider_raw_attestation,
        )
        assert_provider_raw_attestation(
            manifest=manifest, policy=policy, artifact_label="live-provider resolution")
        assert_provider_publish_state(
            qlib_dir=qlib_dir, policy=policy, manifest=manifest,
            artifact_label="live-provider resolution")
    except ProviderContextError:
        raise
    except Exception as exc:
        raise ProviderContextError(
            f"live provider refused by the publish gates: {exc} — fail closed."
        ) from exc

    # R6-m5: the miss path re-reads the manifest inside load_provider_manifest;
    # re-hash after the full resolution and require the content identity to be
    # UNCHANGED vs the key — a rotation landing mid-resolution fails closed
    # instead of caching a key/value pair built from two different manifests.
    try:
        post_digest = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
    except Exception as exc:
        raise ProviderContextError(
            f"cannot re-verify the live provider manifest under {qlib_dir}: {exc} — fail closed."
        ) from exc
    if post_digest != digest:
        raise ProviderContextError(
            f"live provider manifest under {qlib_dir} rotated during resolution — "
            "fail closed (retry)."
        )

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


def live_qlib_provider_dir() -> Path:
    """The live provider directory these helpers describe, resolved."""
    return _qlib_dir().resolve()


def qlib_bound_provider_dir() -> Optional[Path]:
    """Best-effort probe of the IN-PROCESS Qlib provider binding.

    Returns the resolved directory Qlib was ``init``-ed against, or ``None``
    when the probe is inconclusive (qlib absent/stubbed, not yet initialized,
    or config API drift). Never raises. Consumers treat a POSITIVE mismatch
    against ``live_qlib_provider_dir()`` as fail-closed evidence that the
    process is reading a staged/archived provider while stamping live ids
    (M4 self-heal review, GPT M2); an inconclusive probe is NOT evidence.
    """
    try:
        from qlib.config import C  # probe only, never at import time
    except Exception:
        return None
    candidates: list[object] = []
    try:
        dpm = getattr(C, "dpm", None)
        if dpm is not None:
            candidates.append(getattr(dpm, "provider_uri", None))
    except Exception:
        pass
    try:
        candidates.append(C.get("provider_uri", None))
    except Exception:
        pass
    for cand in candidates:
        if isinstance(cand, dict):
            cand = cand.get("__DEFAULT_FREQ") or next(iter(cand.values()), None)
        if not cand:
            continue
        try:
            return Path(str(cand)).expanduser().resolve()
        except Exception:
            continue
    return None
