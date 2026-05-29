"""Offline canaries for the PIT alignment kernel (no provider / live data).

Locks the stateful-q0 contract from the PIT-lookahead prevention plan
(``pit_lookahead_prevention_plan_2026-05-29_v5_FINAL.md`` §6.5). Each test
encodes a failure mode the hand-rolled ``sandbox_v*`` loaders got wrong.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data_infra.pit_alignment_core import (
    DuplicateConflictError,
    PitAlignmentError,
    align_ledger_to_calendar,
)

CAL = pd.DatetimeIndex(pd.bdate_range("2017-10-01", "2020-12-31"))


def _q0(rows, field="roa", lag=0, policy="provider_stateful_q0"):
    df = pd.DataFrame(rows, columns=["ts_code", "effective_date", "end_date", field])
    return align_ledger_to_calendar(
        df, [field], CAL, availability_lag_bars=lag, duplicate_policy=policy
    )[field]


def _val(wide, date, ts):
    """Value at the latest trading day <= ``date``. Snaps the query to a
    calendar day via index-asof (robust to weekend query dates), then reads the
    exact cell with ``.loc`` — preserving NaN (unlike ``Series.asof``, which
    skips NaN and would mask the missing-field q0 contract)."""
    pos = CAL.asof(pd.Timestamp(date))
    return wide[ts].loc[pos]


def test_stateful_q0_restatement_does_not_demote():
    # Q1 visible May, Q2 visible Aug, Q1 RESTATED Sep. q0 must stay Q2.
    rows = [
        ("X", "2020-05-01", "2020-03-31", 10.0),
        ("X", "2020-08-01", "2020-06-30", 20.0),
        ("X", "2020-09-01", "2020-03-31", 11.0),
    ]
    w = _q0(rows)
    assert _val(w, "2020-06-01", "X") == 10.0  # only Q1 visible
    assert _val(w, "2020-08-15", "X") == 20.0  # Q2 = max end_date
    assert _val(w, "2020-09-15", "X") == 20.0  # restated older Q1 must NOT demote q0


def test_original_lookahead_bug_june_sees_q1_not_q3():
    rows = [
        ("Y", "2017-10-27", "2017-09-30", 23.64),
        ("Y", "2018-03-29", "2017-12-31", 31.25),
        ("Y", "2018-05-02", "2018-03-31", 9.05),
        ("Y", "2018-08-03", "2018-06-30", 17.17),
        ("Y", "2018-10-30", "2018-09-30", 25.25),
    ]
    w = _q0(rows)
    assert _val(w, "2018-06-07", "Y") == pytest.approx(9.05)   # Q1, NOT Q3 25.25
    assert _val(w, "2018-01-08", "Y") == pytest.approx(23.64)  # 2017Q3 carried fwd


def test_missing_field_q0_does_not_fall_back():
    # Latest visible period (Q2) reported, but the field is NaN.
    # q0 must serve NaN (no fallback to the older Q1 value).
    rows = [
        ("Z", "2020-05-01", "2020-03-31", 10.0),
        ("Z", "2020-08-01", "2020-06-30", np.nan),
    ]
    w = _q0(rows)
    assert _val(w, "2020-06-01", "Z") == 10.0
    assert np.isnan(_val(w, "2020-08-03", "Z"))
    assert np.isnan(_val(w, "2020-09-15", "Z"))


def test_case_c_same_period_conflict_fails_closed():
    rows = [
        ("W", "2020-05-01", "2020-03-31", 10.0),
        ("W", "2020-05-01", "2020-03-31", 12.0),  # same (ts,eff,end), conflicting
    ]
    with pytest.raises(DuplicateConflictError):
        _q0(rows)


def test_case_c_nan_vs_value_conflict_fails_closed():
    # Mixed null/non-null for the SAME (ts, eff, end, field): last-write-wins
    # would make q0 order-dependent (10.0 or NaN). Must fail closed. (GPT PR#18)
    rows = [
        ("W", "2020-05-01", "2020-03-31", 10.0),
        ("W", "2020-05-01", "2020-03-31", np.nan),
    ]
    with pytest.raises(DuplicateConflictError):
        _q0(rows)


def test_identical_duplicate_is_safe_not_conflict():
    # Fully-identical same-period duplicate (same value) is safe to de-dup.
    rows = [
        ("U", "2020-05-01", "2020-03-31", 10.0),
        ("U", "2020-05-01", "2020-03-31", 10.0),
    ]
    w = _q0(rows)  # must NOT raise
    assert _val(w, "2020-06-01", "U") == 10.0


def test_error_policy_refuses_same_day_multi_period():
    # Annual + Q1 disclosed on the SAME effective_date (real Case A, the 29% pool).
    rows = [
        ("V", "2020-04-30", "2019-12-31", 5.0),
        ("V", "2020-04-30", "2020-03-31", 7.0),
    ]
    with pytest.raises(PitAlignmentError):
        _q0(rows, policy="error")
    # provider_stateful_q0 resolves it to the max end_date (Q1 2020-03-31 = 7).
    w = _q0(rows, policy="provider_stateful_q0")
    assert _val(w, "2020-06-01", "V") == 7.0


def test_availability_lag_shifts_one_trading_bar():
    rows = [("A", "2018-05-02", "2018-03-31", 9.05)]
    w0 = _q0(rows, lag=0)
    w1 = _q0(rows, lag=1)
    i = CAL.get_loc(pd.Timestamp("2018-05-02"))
    assert w0["A"].iloc[i] == pytest.approx(9.05)      # lag 0: usable same day
    assert np.isnan(w1["A"].iloc[i])                    # lag 1: not yet
    assert w1["A"].iloc[i + 1] == pytest.approx(9.05)   # lag 1: next trading bar


def test_unknown_duplicate_policy_raises():
    rows = [("A", "2018-05-02", "2018-03-31", 9.05)]
    with pytest.raises(PitAlignmentError):
        _q0(rows, policy="aggfunc_last")  # the old silent collapse is not a valid policy
