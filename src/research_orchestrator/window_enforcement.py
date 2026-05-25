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
