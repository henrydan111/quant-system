"""Data-layer OOS / formal-research access context.

PR 6 of the 2026-05-26 freeze plan.

The wrapper-level OOS backstop already exists (``EventDrivenBacktester.run``
checks the seal store before each OOS run). But until this module landed, a
pipeline could still bypass the wrapper by reading Qlib data directly via
``qlib_windowed_features`` or even ``D.features``. The ``ResearchAccessContext``
is a ``contextvars.ContextVar`` that propagates the allowed-window /
seal-claimed / allowed-fields constraints down to the data-access layer, so
any unprotected read raises loudly rather than silently leaking holdout data.

Public surface
==============

* :class:`ResearchAccessContext` — frozen dataclass.
* :func:`set_research_access_context`, :func:`reset_research_access_context`,
  :func:`get_research_access_context` — low-level contextvar helpers.
* :func:`research_access_context` — context manager (recommended).
* :class:`HoldoutWindowViolation`, :class:`HoldoutSealViolation`,
  :class:`FieldAccessViolation` — what the data layer raises on a bad read.

Usage
=====

::

    with research_access_context(ResearchAccessContext(
        run_id=run_id, step_id=step_id, stage="oos_test",
        design_hash=design_hash,
        allowed_start=oos_start, allowed_end=oos_end,
        provider_build_id=manifest.provider_build_id,
        calendar_policy_id="frozen_20260227_system_build",
        holdout_context_id=holdout_context.run_dir,
        holdout_seal_claimed=True,
    )):
        result = pipeline_fn(...)  # any qlib_windowed_features call inside
                                   # inherits the constraint via the contextvar
"""

from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────


class HoldoutWindowViolation(RuntimeError):
    """Raised when a data read falls outside the context's [allowed_start, allowed_end]."""


class HoldoutSealViolation(RuntimeError):
    """Raised when an OOS-stage read happens without holdout_seal_claimed=True."""


class FieldAccessViolation(RuntimeError):
    """Raised when a data read requests fields outside the context's allowed_fields."""


class MissingResearchAccessContextError(RuntimeError):
    """Raised when a formal stage runs without an active ResearchAccessContext.

    Added in PR 8 fix #8 of the 2026-05-26 freeze plan. Formal validation
    handlers call :func:`require_research_access_context` to confirm a
    context is installed BEFORE they touch any data; sandbox runs do not.
    """


FORMAL_STAGES: frozenset[str] = frozenset(
    {"formal_validation", "oos_test", "registry_publish"}
)


# ─────────────────────────────────────────────────────────────────────────
# Context dataclass
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResearchAccessContext:
    """Constraints the data layer must respect for the current research step.

    All fields are required EXCEPT ``allowed_fields`` (optional whitelist;
    None means no field-level constraint, only window + seal constraints).

    The dataclass is frozen so a context cannot be mutated mid-flight by
    the pipeline it constrains.
    """
    run_id: str
    step_id: str
    stage: str
    design_hash: str
    allowed_start: pd.Timestamp
    allowed_end: pd.Timestamp
    provider_build_id: str
    calendar_policy_id: str
    holdout_context_id: Optional[str] = None
    holdout_seal_claimed: bool = False
    allowed_fields: Optional[frozenset[str]] = None

    @classmethod
    def from_split(
        cls,
        *,
        run_id: str,
        step_id: str,
        stage: str,
        design_hash: str,
        time_split: dict,
        provider_build_id: str,
        calendar_policy_id: str,
        holdout_context_id: Optional[str] = None,
        holdout_seal_claimed: bool = False,
        allowed_fields: Optional[Iterable[str]] = None,
    ) -> "ResearchAccessContext":
        """Build a context from a ``time_split`` dict (the orchestrator-native form)."""
        if stage == "oos_test":
            start_key, end_key = "oos_start", "oos_end"
        else:
            start_key, end_key = "is_start", "is_end"

        start = time_split.get(start_key)
        end = time_split.get(end_key)
        if not start or not end:
            raise ValueError(
                f"time_split missing {start_key}/{end_key} for stage={stage!r}: {time_split}"
            )

        return cls(
            run_id=str(run_id),
            step_id=str(step_id),
            stage=str(stage),
            design_hash=str(design_hash),
            allowed_start=pd.Timestamp(start),
            allowed_end=pd.Timestamp(end),
            provider_build_id=str(provider_build_id),
            calendar_policy_id=str(calendar_policy_id),
            holdout_context_id=str(holdout_context_id) if holdout_context_id else None,
            holdout_seal_claimed=bool(holdout_seal_claimed),
            allowed_fields=frozenset(allowed_fields) if allowed_fields is not None else None,
        )

    def validate_read(
        self,
        *,
        start_time: str | pd.Timestamp,
        end_time: str | pd.Timestamp,
        fields: Iterable[str] = (),
    ) -> None:
        """Raise if the requested read violates this context.

        Called from ``qlib_windowed_features`` before every ``D.features``
        invocation. Sandbox/no-context calls never reach here because
        callers wrap the check with ``get_research_access_context() is not None``.
        """
        start_ts = pd.Timestamp(start_time)
        end_ts = pd.Timestamp(end_time)

        if start_ts < self.allowed_start:
            raise HoldoutWindowViolation(
                f"Read start={start_ts} is before allowed window start "
                f"{self.allowed_start} (run={self.run_id}, step={self.step_id}, "
                f"stage={self.stage})."
            )
        if end_ts > self.allowed_end:
            raise HoldoutWindowViolation(
                f"Read end={end_ts} is after allowed window end "
                f"{self.allowed_end} (run={self.run_id}, step={self.step_id}, "
                f"stage={self.stage})."
            )

        if self.stage == "oos_test" and not self.holdout_seal_claimed:
            raise HoldoutSealViolation(
                f"OOS read on design_hash={self.design_hash} "
                f"(run={self.run_id}, step={self.step_id}) without "
                "holdout_seal_claimed=True. Acquire a seal claim via "
                "SealedBacktestRunner before reading any data."
            )

        if self.allowed_fields is not None:
            requested = set(fields)
            extra = requested - self.allowed_fields
            if extra:
                raise FieldAccessViolation(
                    f"Read requested fields {sorted(extra)} not in allowed_fields "
                    f"{sorted(self.allowed_fields)} (run={self.run_id}, "
                    f"step={self.step_id}, stage={self.stage})."
                )


# ─────────────────────────────────────────────────────────────────────────
# Contextvar plumbing
# ─────────────────────────────────────────────────────────────────────────


_RESEARCH_ACCESS_CONTEXT: contextvars.ContextVar[ResearchAccessContext | None] = (
    contextvars.ContextVar("research_access_context", default=None)
)


def set_research_access_context(
    ctx: ResearchAccessContext | None,
) -> contextvars.Token[ResearchAccessContext | None]:
    return _RESEARCH_ACCESS_CONTEXT.set(ctx)


def reset_research_access_context(
    token: contextvars.Token[ResearchAccessContext | None],
) -> None:
    _RESEARCH_ACCESS_CONTEXT.reset(token)


def get_research_access_context() -> ResearchAccessContext | None:
    return _RESEARCH_ACCESS_CONTEXT.get()


@contextmanager
def research_access_context(
    ctx: ResearchAccessContext | None,
) -> Iterator[ResearchAccessContext | None]:
    """Context manager — preferred API.

    ``None`` is allowed (no-op) so callers can pass a flag-controlled context
    without branching at every call site.
    """
    token = set_research_access_context(ctx)
    try:
        yield ctx
    finally:
        reset_research_access_context(token)


def require_research_access_context(stage: str) -> ResearchAccessContext:
    """PR 8 fix #8 — formal stages MUST run with an active context.

    Raises :class:`MissingResearchAccessContextError` if the current stage is
    in :data:`FORMAL_STAGES` and ``get_research_access_context()`` returns
    None. Sandbox/screening stages return the current context (which may be
    None — they are explicitly tolerant).

    Call from every formal-validation handler before touching feature data:

        ctx = require_research_access_context(step.stage)

    Returns the active context so callers can also use the fields (run_id,
    design_hash, etc.) for logging.
    """
    current = get_research_access_context()
    if stage in FORMAL_STAGES and current is None:
        raise MissingResearchAccessContextError(
            f"Formal stage={stage!r} runs MUST install a ResearchAccessContext "
            "before touching feature data. Wrap the call in "
            "`with research_access_context(ResearchAccessContext.from_split(...))`."
        )
    return current  # type: ignore[return-value]
