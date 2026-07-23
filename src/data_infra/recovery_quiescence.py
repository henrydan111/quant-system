# -*- coding: utf-8 -*-
"""The raw-store quiescence hook, wired into every raw consumer's entry point.

WHY THIS MODULE EXISTS. `scripts/recovery_promotion.py` writes a durable
`data/.recovery_in_progress` sentinel before it swaps a recovered family into the live store, and it
exposes `assert_no_active_recovery()` for consumers to fail closed against. Its own module docstring
recorded, in a section headed *"NOT YET TRUE, do not claim otherwise"*, that the hook had **no
production caller** — so a daily job, a provider rebuild or a monthly bump could read a raw tree while
it was being replaced underneath them. It called wiring this in a **HARD PRE-PROMOTION INTEGRATION
GATE**: required before any promotion is authorized.

That gate was NOT discharged before `market/daily` was promoted on 2026-07-22. This module discharges
it. The promotion machinery lives under `scripts/`, which `src/` must not import from, so the check is
re-implemented here as the same two lines of fact (does the sentinel file exist?) rather than reaching
across the boundary — the sentinel's NAME is the contract between them, and a test pins the two names
together so they cannot drift.

WHAT IT DOES AND DOES NOT BUY. It fails a consumer closed at ENTRY. It does not stop a consumer that
was ALREADY RUNNING when the sentinel appeared — that needs the shared/exclusive generation barrier
described in the promotion module, which does not exist yet. Do not describe this as full concurrent-
consumer defence.
"""
from __future__ import annotations

import os
from pathlib import Path

#: must equal `recovery_promotion.SENTINEL_NAME`; pinned by
#: tests/data_infra/test_recovery_quiescence.py so the two cannot drift apart
SENTINEL_NAME = ".recovery_in_progress"

#: set to "1" to proceed anyway. For the recovery operator's OWN tooling, which legitimately runs while
#: the sentinel is armed. Deliberately an env var and not a function argument: every consumer refuses
#: identically, and the override is visible in the invocation rather than buried in a call site.
OVERRIDE_ENV = "QUANT_ALLOW_DURING_RECOVERY"


class RawStoreQuiescenceError(RuntimeError):
    """The raw store is mid-promotion; reading or writing it now can see a half-swapped tree."""


def assert_no_active_recovery(data_root=None) -> None:
    """Fail closed if a raw-store promotion is in progress. Call at the ENTRY of any raw consumer."""
    if os.environ.get(OVERRIDE_ENV) == "1":
        return
    root = Path(data_root) if data_root is not None else _default_data_root()
    sentinel = root / SENTINEL_NAME
    if sentinel.exists():
        raise RawStoreQuiescenceError(
            f"RECOVERY_IN_PROGRESS: the raw store is mid-promotion ({sentinel}).\n"
            f"  A raw tree may be half-swapped right now, so reading or writing it is unsafe.\n"
            f"  The sentinel clears when the operator finishes QA + the first verified backup.\n"
            f"  To proceed anyway (recovery tooling only): set {OVERRIDE_ENV}=1")


def _default_data_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data"
