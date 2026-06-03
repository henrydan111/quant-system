"""PIT-correctness canaries for the promotion-evidence harness.

The promotion gate ([release_gate.py](../research_orchestrator/release_gate.py)) requires a
`promotion_evidence` artifact in which a set of PIT-correctness checks are each explicitly
``"passed"``. This module PRODUCES those attestations: each canary runs a real PIT-backend kernel
(`pit_alignment_core.align_ledger_to_calendar` / `pit_backend.strictly_next_open_trade_day`) on a
controlled synthetic fixture with a KNOWN leak-free answer, and returns ``"passed"`` iff the kernel
produces that answer. A canary that FAILS means the PIT pipeline regressed — the harness then
refuses to emit a passing artifact (fail-closed).

Design ref: workspace/research/factor_expansion/promotion_evidence_harness_design.md (GPT-reviewed).
The check is split from the fixture/kernel call so the negative (injected-leak) tests can drive each
check with a deliberately-leaky input and confirm it returns ``"failed"`` — proving the canary is
sensitive to the leak it guards, not a tautology.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

try:  # support both the src-on-path (data_infra.X) and root-on-path (src.data_infra.X) conventions
    from data_infra.pit_alignment_core import align_ledger_to_calendar, PitAlignmentError
    from data_infra.pit_backend import strictly_next_open_trade_day
except ModuleNotFoundError:  # pragma: no cover
    from src.data_infra.pit_alignment_core import align_ledger_to_calendar, PitAlignmentError
    from src.data_infra.pit_backend import strictly_next_open_trade_day

PASSED = "passed"
FAILED = "failed"

# The 6 PIT canary keys the promotion gate requires (the 7th required check,
# unsafe_pit_dates_lint, is the standalone PIT002 lint, produced by the harness separately).
CANARY_KEYS = (
    "synthetic_lookahead_canary",
    "restatement_canary",
    "q0_canary_multiperiod",
    "q0_canary_stateful_restatement",
    "q0_canary_missing_field",
    "availability_assertion",
)


@dataclass(frozen=True)
class CanaryResult:
    name: str
    status: str
    detail: str


def _cal(dates) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(sorted(pd.Timestamp(d) for d in dates))


def _ledger(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["ts_code", "effective_date", "end_date", "metric"])


def _align(ledger: pd.DataFrame, calendar: pd.DatetimeIndex, *, policy: str = "error") -> pd.Series:
    """Align one symbol's `metric` onto the calendar; return the q0 Series for that symbol."""
    out = align_ledger_to_calendar(ledger, ["metric"], calendar, availability_lag_bars=0, duplicate_policy=policy)
    df = out["metric"]
    return df[df.columns[0]]  # single symbol


# ── observable-property checks (pure; the negative tests drive these directly) ──────────────

def check_no_lookahead(aligned: pd.Series, disclosure: pd.Timestamp) -> bool:
    """A value disclosed at `disclosure` must NOT be visible on any calendar date < disclosure."""
    before = aligned[aligned.index < disclosure]
    return bool(before.isna().all())


def check_value_at(aligned: pd.Series, when: pd.Timestamp, expected: float) -> bool:
    v = aligned.get(when)
    if expected != expected:  # NaN expected
        return bool(pd.isna(v))
    return bool(v is not None and not pd.isna(v) and abs(float(v) - expected) < 1e-9)


def check_strictly_after(effective: pd.Series, disclosure: pd.Series) -> bool:
    """Every non-NaT effective day must be STRICTLY after its disclosure day."""
    pairs = [(e, d) for e, d in zip(effective, disclosure) if not pd.isna(e)]
    return bool(pairs) and all(pd.Timestamp(e) > pd.Timestamp(d) for e, d in pairs)


# ── the 6 canaries ──────────────────────────────────────────────────────────────────────────

def synthetic_lookahead_canary() -> CanaryResult:
    """A value disclosed at E is NaN before E and present at E (no lookahead)."""
    E = pd.Timestamp("2024-05-06")
    cal = _cal(["2024-05-03", "2024-05-06", "2024-05-07"])
    aligned = _align(_ledger([{"ts_code": "X", "effective_date": E, "end_date": "2024-03-31", "metric": 100.0}]), cal)
    ok = check_no_lookahead(aligned, E) and check_value_at(aligned, E, 100.0)
    return CanaryResult("synthetic_lookahead_canary", PASSED if ok else FAILED,
                        f"pre-disclosure NaN={check_no_lookahead(aligned, E)}, at-E={aligned.get(E)}")


def restatement_canary() -> CanaryResult:
    """A late restatement of a period updates its q0 at the restatement's effective date, not before."""
    E1, E2 = pd.Timestamp("2024-05-06"), pd.Timestamp("2024-09-02")
    cal = _cal(["2024-05-06", "2024-07-01", "2024-09-02", "2024-10-01"])
    aligned = _align(_ledger([
        {"ts_code": "X", "effective_date": E1, "end_date": "2024-03-31", "metric": 10.0},
        {"ts_code": "X", "effective_date": E2, "end_date": "2024-03-31", "metric": 12.0},  # restate Q1
    ]), cal)
    ok = (check_value_at(aligned, E1, 10.0) and check_value_at(aligned, pd.Timestamp("2024-07-01"), 10.0)
          and check_value_at(aligned, E2, 12.0) and check_value_at(aligned, pd.Timestamp("2024-10-01"), 12.0))
    return CanaryResult("restatement_canary", PASSED if ok else FAILED,
                        f"pre-restate={aligned.get(pd.Timestamp('2024-07-01'))}, post={aligned.get(E2)}")


def q0_canary_multiperiod() -> CanaryResult:
    """Case-A (same effective date, 2 fiscal periods): provider_stateful_q0 picks the latest period;
    the fail-closed 'error' policy refuses the multi-period collapse."""
    E = pd.Timestamp("2024-08-30")
    cal = _cal(["2024-08-30", "2024-09-02"])
    led = _ledger([
        {"ts_code": "X", "effective_date": E, "end_date": "2024-03-31", "metric": 10.0},  # Q1
        {"ts_code": "X", "effective_date": E, "end_date": "2024-06-30", "metric": 20.0},  # Q2 (latest)
    ])
    aligned = _align(led, cal, policy="provider_stateful_q0")
    stateful_ok = check_value_at(aligned, E, 20.0)  # q0 = latest period (Q2)
    fail_closed = False
    try:
        _align(led, cal, policy="error")
    except PitAlignmentError:
        fail_closed = True
    return CanaryResult("q0_canary_multiperiod", PASSED if (stateful_ok and fail_closed) else FAILED,
                        f"stateful_q0={aligned.get(E)} (want 20), error_policy_raised={fail_closed}")


def q0_canary_stateful_restatement() -> CanaryResult:
    """Stateful q0 under a restatement of the CURRENT period: q0 follows the restated latest period."""
    E1, E2 = pd.Timestamp("2024-08-30"), pd.Timestamp("2024-10-15")
    cal = _cal(["2024-08-30", "2024-09-15", "2024-10-15", "2024-11-01"])
    aligned = _align(_ledger([
        {"ts_code": "X", "effective_date": E1, "end_date": "2024-03-31", "metric": 10.0},  # Q1
        {"ts_code": "X", "effective_date": E1, "end_date": "2024-06-30", "metric": 20.0},  # Q2 (latest)
        {"ts_code": "X", "effective_date": E2, "end_date": "2024-06-30", "metric": 25.0},  # restate Q2
    ]), cal, policy="provider_stateful_q0")
    ok = (check_value_at(aligned, E1, 20.0) and check_value_at(aligned, pd.Timestamp("2024-09-15"), 20.0)
          and check_value_at(aligned, E2, 25.0) and check_value_at(aligned, pd.Timestamp("2024-11-01"), 25.0))
    return CanaryResult("q0_canary_stateful_restatement", PASSED if ok else FAILED,
                        f"pre={aligned.get(pd.Timestamp('2024-09-15'))} (want 20), post={aligned.get(E2)} (want 25)")


def q0_canary_missing_field() -> CanaryResult:
    """A reported latest period with a NULL field carries NaN at q0 — it is NOT forward-filled
    from the prior period (the missing-field trap)."""
    E1, E2 = pd.Timestamp("2024-05-06"), pd.Timestamp("2024-08-30")
    cal = _cal(["2024-05-06", "2024-07-01", "2024-08-30", "2024-10-01"])
    aligned = _align(_ledger([
        {"ts_code": "X", "effective_date": E1, "end_date": "2024-03-31", "metric": 10.0},      # Q1 present
        {"ts_code": "X", "effective_date": E2, "end_date": "2024-06-30", "metric": np.nan},     # Q2 null
    ]), cal)
    ok = (check_value_at(aligned, E1, 10.0)
          and check_value_at(aligned, E2, float("nan"))            # NaN at the null period, NOT 10
          and check_value_at(aligned, pd.Timestamp("2024-10-01"), float("nan")))
    return CanaryResult("q0_canary_missing_field", PASSED if ok else FAILED,
                        f"at-null-period={aligned.get(E2)} (want NaN, not 10)")


def availability_assertion_canary() -> CanaryResult:
    """Disclosure dates map to a STRICTLY-later open trading day (no same-day visibility)."""
    cal = _cal(["2024-05-06", "2024-05-07", "2024-05-08", "2024-05-09", "2024-05-10", "2024-05-13"])
    disc = pd.Series(pd.to_datetime(["2024-05-06", "2024-05-11"]))  # a trading day + a Saturday
    eff = strictly_next_open_trade_day(disc, cal)
    ok = check_strictly_after(eff, disc)
    return CanaryResult("availability_assertion", PASSED if ok else FAILED,
                        f"disclosure->effective: {list(zip([str(d.date()) for d in disc], [str(pd.Timestamp(e).date()) for e in eff]))}")


def run_pit_canaries() -> dict[str, str]:
    """Run all 6 PIT canaries; return ``{canary_key: 'passed'|'failed'}`` (gate-artifact shape)."""
    results = [
        synthetic_lookahead_canary(), restatement_canary(), q0_canary_multiperiod(),
        q0_canary_stateful_restatement(), q0_canary_missing_field(), availability_assertion_canary(),
    ]
    return {r.name: r.status for r in results}
