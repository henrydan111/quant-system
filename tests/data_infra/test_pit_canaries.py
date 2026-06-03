"""Tests for the PIT-correctness canaries (promotion-evidence harness, increment 1).

Positive: every canary passes on the real (correct) PIT pipeline.
Negative (leak-sensitivity): each observable-property CHECK FAILS on a deliberately-leaky input —
proving the canary actually guards the leak it claims to, not a tautology (GPT cross-review req).
"""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_infra.pit_canaries import (
    CANARY_KEYS,
    PASSED,
    run_pit_canaries,
    synthetic_lookahead_canary,
    restatement_canary,
    q0_canary_multiperiod,
    q0_canary_stateful_restatement,
    q0_canary_missing_field,
    availability_assertion_canary,
    check_no_lookahead,
    check_value_at,
    check_strictly_after,
)


class PitCanariesPositiveTests(unittest.TestCase):
    def test_run_all_canaries_pass(self):
        res = run_pit_canaries()
        self.assertEqual(set(res.keys()), set(CANARY_KEYS))
        self.assertTrue(all(v == PASSED for v in res.values()), f"not all passed: {res}")

    def test_each_canary_passes_with_detail(self):
        for fn in (synthetic_lookahead_canary, restatement_canary, q0_canary_multiperiod,
                   q0_canary_stateful_restatement, q0_canary_missing_field, availability_assertion_canary):
            r = fn()
            self.assertEqual(r.status, PASSED, f"{r.name} failed: {r.detail}")


class PitCanariesLeakSensitivityTests(unittest.TestCase):
    """Drive each CHECK with an injected-leak input; it MUST return False (the negative proof)."""

    def test_no_lookahead_check_catches_pre_disclosure_visibility(self):
        cal = pd.DatetimeIndex(pd.to_datetime(["2024-05-03", "2024-05-06", "2024-05-07"]))
        D = pd.Timestamp("2024-05-06")
        leaky = pd.Series([100.0, 100.0, 100.0], index=cal)        # visible BEFORE disclosure -> leak
        leakfree = pd.Series([np.nan, 100.0, 100.0], index=cal)
        self.assertFalse(check_no_lookahead(leaky, D))             # canary catches the leak
        self.assertTrue(check_no_lookahead(leakfree, D))

    def test_value_at_check_catches_missing_field_ffill(self):
        when = pd.Timestamp("2024-08-30")
        ffilled = pd.Series([10.0], index=pd.DatetimeIndex([when]))  # null period wrongly ffilled to 10
        correct = pd.Series([np.nan], index=pd.DatetimeIndex([when]))
        self.assertFalse(check_value_at(ffilled, when, float("nan")))  # canary catches the ffill leak
        self.assertTrue(check_value_at(correct, when, float("nan")))

    def test_value_at_check_catches_premature_restatement(self):
        when = pd.Timestamp("2024-07-01")  # between E1 and the restatement E2
        leaky = pd.Series([12.0], index=pd.DatetimeIndex([when]))   # restated value visible too early
        correct = pd.Series([10.0], index=pd.DatetimeIndex([when]))
        self.assertFalse(check_value_at(leaky, when, 10.0))         # canary catches the early restatement
        self.assertTrue(check_value_at(correct, when, 10.0))

    def test_strictly_after_check_catches_same_day(self):
        disc = pd.Series(pd.to_datetime(["2024-05-06"]))
        same = pd.Series(pd.to_datetime(["2024-05-06"]))           # effective == disclosure -> same-day leak
        strict = pd.Series(pd.to_datetime(["2024-05-07"]))
        self.assertFalse(check_strictly_after(same, disc))         # canary catches same-day
        self.assertTrue(check_strictly_after(strict, disc))


if __name__ == "__main__":
    unittest.main()
