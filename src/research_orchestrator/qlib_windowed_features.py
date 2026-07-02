from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.research_orchestrator.cache_manifest import (
    CacheContext,
    CacheKeyMismatchError,
    CacheManifestStore,
    ProviderGenerationMismatchError,
    get_cache_context,
)
from src.research_orchestrator.research_access_context import (
    HoldoutSealViolation,
    HoldoutWindowViolation,
    get_research_access_context,
)

logger = logging.getLogger(__name__)


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
    # PR 6 of 2026-05-26 freeze plan: data-layer enforcement of the formal
    # research access context. When a ResearchAccessContext is active (set
    # by SealedBacktestRunner.run_workspace_pipeline or a formal validation
    # handler), every read through this wrapper must satisfy its window /
    # seal / allowed_fields constraints. Sandbox/no-context calls skip this
    # check unchanged.
    research_ctx = get_research_access_context()
    if research_ctx is not None:
        research_ctx.validate_read(
            start_time=start_time,
            end_time=end_time,
            fields=list(fields),
        )

    # D3 born-sealed clamp (UNFREEZE_PLAN.md, GPT Round-1 B1): dates beyond the
    # live policy's spent-OOS boundary are reachable ONLY under an active
    # ResearchAccessContext that has actually claimed the holdout seal. A
    # no-context (discovery) read past the boundary fails closed — the old
    # "sandbox/no-context calls skip this check" behavior is exactly the leak
    # the pre-publish wall exists to close. Boundary resolution failure fails
    # closed too (the resolver raises).
    from src.data_infra.provider_context import (
        live_provider_ids,
        live_qlib_provider_dir,
        live_spent_oos_end,
        qlib_bound_provider_dir,
    )

    boundary_end = live_spent_oos_end()
    if pd.Timestamp(end_time) > boundary_end:
        if research_ctx is None:
            raise HoldoutWindowViolation(
                f"read end_time={end_time} exceeds the spent-OOS boundary "
                f"{boundary_end.date()} with NO active ResearchAccessContext — "
                "the post-boundary window is born-sealed (UNFREEZE_PLAN.md D3); "
                "it is reachable only through the sealed-OOS formal path."
            )
        if not getattr(research_ctx, "holdout_seal_claimed", False):
            raise HoldoutSealViolation(
                f"read end_time={end_time} exceeds the spent-OOS boundary "
                f"{boundary_end.date()} but the active ResearchAccessContext has "
                "holdout_seal_claimed=False — claim the holdout seal before touching "
                "the born-sealed fresh window (UNFREEZE_PLAN.md D3)."
            )

    manifest = CacheManifestStore(cache_manifest_dir)
    cache_key = _deterministic_cache_path(freq, fields, start_time, end_time)
    cache_path = cache_key
    # M4 provider-generation binding: a manifest row written under another
    # provider build/policy (incl. legacy ""-rows) never validates reuse.
    live_build_id, live_policy_id = live_provider_ids()

    # M4 self-heal review, GPT M2 (+ R2 escalation): this is a LIVE-provider
    # door — manifest rows are stamped with live ids, so a process whose
    # in-process Qlib binding provably points elsewhere (staged/archived
    # provider) must not read or write here. A POSITIVE probe mismatch fails
    # closed for everyone. An INCONCLUSIVE probe (qlib stubbed / not yet
    # initialized / config API drift) is tolerated only for no-context
    # sandbox liveness; under an active ResearchAccessContext the binding
    # must be PROVEN before a formal read is stamped (R2-M2).
    bound_dir = qlib_bound_provider_dir()
    if bound_dir is None:
        if research_ctx is not None:
            raise CacheKeyMismatchError(
                "qlib_windowed_features is a live-provider door under an active "
                "ResearchAccessContext, but the in-process Qlib provider binding "
                "could not be proven. Refusing to stamp formal reads with live "
                "provider ids on an inconclusive probe."
            )
    else:
        live_dir = live_qlib_provider_dir()
        if bound_dir != live_dir:
            raise CacheKeyMismatchError(
                "qlib_windowed_features is a live-provider door: the in-process "
                f"Qlib binding {bound_dir} != live provider {live_dir}. Reads "
                "against staged/archived providers must not stamp live ids — "
                "use a non-formal parity helper instead."
            )

    # M4 self-heal review, GPT B1: a formal run pins its provider generation
    # in the ResearchAccessContext at run start. If the live provider rotates
    # WHILE the context is active, every later read hard-fails (base class —
    # the self-heal catch below cannot swallow it): one evidence artifact must
    # never mix provider generations. With no active context (sandbox live
    # reads), the live ids are the binding.
    if research_ctx is not None:
        expected_build_id = str(research_ctx.provider_build_id)
        expected_policy_id = str(research_ctx.calendar_policy_id)
        if (live_build_id, live_policy_id) != (expected_build_id, expected_policy_id):
            raise CacheKeyMismatchError(
                "Live provider generation changed during an active "
                f"ResearchAccessContext: live=({live_build_id}, {live_policy_id}) "
                f"!= context=({expected_build_id}, {expected_policy_id}). "
                "Abort this formal run and restart under a single provider generation."
            )
        binding_build_id = expected_build_id
        binding_policy_id = expected_policy_id
    else:
        binding_build_id = live_build_id
        binding_policy_id = live_policy_id

    try:
        manifest.assert_cache_reusable(
            cache_key=cache_key,
            cache_path=cache_path,
            cache_context=effective_context,
            stage=stage,
            window_start=start_time,
            window_end=end_time,
            cache_type="qlib_features",
            provider_build_id=binding_build_id,
            calendar_policy_id=binding_policy_id,
        )
    except ProviderGenerationMismatchError as exc:
        # Provider rotated since this key's latest manifest row (BEFORE this
        # run/context started — a mid-run rotation is caught above). This door
        # holds no cached artifact — D.features below always recomputes from
        # the live provider — so a stale-generation row must not brick the key
        # permanently: proceed, and record_cache_write below appends a fresh
        # row under the live generation (the next read then passes; the stale
        # row stays behind as the rotation audit trail). The subclass is
        # raised only after design_hash/stage/window all matched — those
        # violations still propagate.
        logger.warning(
            "cache generation rotated for %s — recomputing from the live "
            "provider and re-binding to (%s, %s); stage=%s run_id=%s "
            "step_id=%s; refused stale row: %s",
            cache_key,
            binding_build_id,
            binding_policy_id,
            stage,
            getattr(research_ctx, "run_id", ""),
            getattr(research_ctx, "step_id", ""),
            exc,
        )
    frame = D.features(  # noqa: bare-qlib-features  (canonical chokepoint)
        instruments,
        list(fields),
        start_time=start_time,
        end_time=end_time,
    )
    if not frame.empty and isinstance(frame.index, pd.MultiIndex):
        date_values = pd.to_datetime(frame.index.get_level_values("datetime"))
        mask = (date_values >= pd.Timestamp(start_time)) & (date_values <= pd.Timestamp(end_time))
        frame = frame[mask].copy()
    # R2-M1 (TOCTOU): the live provider may rotate AFTER the pre-read pin and
    # BEFORE/DURING D.features — the frame could then hold rotated-provider
    # bytes while the manifest row would stamp the pre-rotation binding ids.
    # Re-check and DISCARD the read instead of recording it (applies to the
    # no-context sandbox path too — never write a row under possibly-stale
    # ids). The next call re-pins under the new generation (no context) or
    # hard-fails at the pre-read pin (active context).
    current_build_id, current_policy_id = live_provider_ids()
    if (current_build_id, current_policy_id) != (binding_build_id, binding_policy_id):
        raise CacheKeyMismatchError(
            "Live provider generation changed during qlib_windowed_features "
            f"read: live=({current_build_id}, {current_policy_id}) "
            f"!= bound=({binding_build_id}, {binding_policy_id}). "
            "Discarding this read; restart under a single provider generation."
        )
    manifest.record_cache_write(
        cache_type="qlib_features",
        cache_key=cache_key,
        cache_path=cache_path,
        cache_context=effective_context,
        stage=stage,
        window_start=start_time,
        window_end=end_time,
        provider_build_id=binding_build_id,
        calendar_policy_id=binding_policy_id,
    )
    return frame
