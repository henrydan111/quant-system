from __future__ import annotations

from typing import Any

import pandas as pd


def _normalize_stage(stage: str) -> str:
    value = str(stage or "is_only").strip().lower()
    return "oos_test" if "oos" in value else "is_only"


def _normalize_date(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return pd.Timestamp(text)


def _format_date(value: pd.Timestamp | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d")


def clamp_window_to_hypothesis(
    hypothesis: Any | None,
    start: Any,
    end: Any,
    *,
    stage: str,
) -> tuple[str, str]:
    start_ts = _normalize_date(start)
    end_ts = _normalize_date(end)
    if hypothesis is None or getattr(hypothesis, "time_split", None) is None:
        if start_ts is not None and end_ts is not None and start_ts > end_ts:
            raise ValueError(f"Invalid date window: start {start_ts.date()} is after end {end_ts.date()}")
        return _format_date(start_ts), _format_date(end_ts)

    split = hypothesis.time_split
    normalized_stage = _normalize_stage(stage)
    if normalized_stage == "oos_test":
        floor = _normalize_date(split.oos_start)
        ceiling = _normalize_date(split.oos_end)
    else:
        floor = _normalize_date(split.is_start)
        ceiling = _normalize_date(split.is_end)

    start_candidates = [item for item in (start_ts, floor) if item is not None]
    end_candidates = [item for item in (end_ts, ceiling) if item is not None]
    effective_start = max(start_candidates) if start_candidates else None
    effective_end = min(end_candidates) if end_candidates else None
    if effective_start is not None and effective_end is not None and effective_start > effective_end:
        raise ValueError(
            "Hypothesis time window clamp produced an empty range: "
            f"start={effective_start.strftime('%Y-%m-%d')} end={effective_end.strftime('%Y-%m-%d')}"
        )
    return _format_date(effective_start), _format_date(effective_end)


def enforce_is_window_if_hypothesis(
    context: Any,
    start: Any,
    end: Any,
    *,
    stage: str,
) -> tuple[str, str]:
    request = getattr(context, "request", None)
    hypothesis = getattr(request, "hypothesis", None)
    return clamp_window_to_hypothesis(hypothesis, start, end, stage=stage)


def assert_v14_a8_no_legacy_virgin_oos_claim(
    *,
    stage: str,
    time_split: Any,
    caller: str,
) -> None:
    """v1.4 A8 (implementation-review rounds 1-2, 2026-07-03): the SHARED pre-claim guard
    for every LEGACY (design_hash / frozen_set_hash keyed) OOS seal path. A post-2026-02-27
    VIRGIN window may be spent only by the PR3 StrategyRegistryStore/book_seal_key path or
    a pre-authorized A5 override study. Called from BOTH legacy claim sites: the
    orchestrator chokepoint (steps._claim_holdout_access_if_needed) AND
    SealedBacktestRunner._claim_if_oos (round-2 Blocker 1: the runner claims directly and
    its effective_seal_key falls back to design_hash). Fail-closed: an undeterminable OOS
    end date refuses rather than guessing."""
    if stage != "oos_test":
        return
    split = time_split if isinstance(time_split, dict) else {}
    oos_end = str(
        split.get("oos_end")
        or split.get("end_date")
        or split.get("end")
        or ""
    )
    if not oos_end:
        raise RuntimeError(
            f"v1.4_A8_virgin_window_guard_unable_to_determine_oos_end: {caller} "
            "cannot claim legacy OOS without an explicit OOS end date."
        )
    from src.alpha_research.factor_eval_skill.multiplicity import is_virgin_window

    if is_virgin_window(oos_end):
        raise RuntimeError(
            "v1.4_A8_virgin_window_legacy_path_blocked: "
            f"{caller} uses the legacy design_hash/frozen_set OOS seal identity, which is "
            "PERMANENTLY refused on post-2026-02-27 virgin windows. Spend virgin OOS only "
            "through the book path (factor_eval_skill.book_seal.run_book_sealed_evaluation, "
            "seal_key=book_seal_key; PR3) or a pre-authorized A5 override study "
            "(cmd_seal fresh_window_override_id). Already-burned windows still pass here."
        )
