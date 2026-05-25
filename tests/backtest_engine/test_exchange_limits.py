"""Follow-up Plan #2 — Limit price + IPO period regression tests (P1-1, P1-2)."""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest_engine.event_driven.exchange import (
    Exchange,
    NoSlippage,
    _round_half_up_2dp,
)


class RoundHalfUpTests(unittest.TestCase):
    """P1-1: verify the rounding helper uses round-half-up, not banker's."""

    def test_round_half_up_exact(self):
        self.assertEqual(_round_half_up_2dp(10.125), 10.13)  # banker's would give 10.12

    def test_round_half_up_down(self):
        self.assertEqual(_round_half_up_2dp(10.124), 10.12)

    def test_round_half_up_up(self):
        self.assertEqual(_round_half_up_2dp(10.126), 10.13)

    def test_round_half_up_negative(self):
        # Decimal ROUND_HALF_UP rounds .5 AWAY from zero, so -10.125 -> -10.13
        # This is correct for the mathematical definition; limit prices are
        # always positive in A-shares so the negative case doesn't arise.
        self.assertEqual(_round_half_up_2dp(-10.125), -10.13)

    def test_round_half_up_whole_number(self):
        self.assertEqual(_round_half_up_2dp(10.00), 10.00)


class LimitPriceTests(unittest.TestCase):
    def setUp(self):
        self.ex = Exchange(slippage_model=NoSlippage())

    def test_main_board_limit_10pct(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("000001.SZ", False, pd.Timestamp("2024-01-15")),
            0.10,
        )

    def test_st_limit_5pct(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("000001.SZ", True, pd.Timestamp("2024-01-15")),
            0.05,
        )

    def test_chinext_pre_2020_reform(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("300001.SZ", False, pd.Timestamp("2020-08-23")),
            0.10,
        )

    def test_chinext_post_2020_reform(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("300001.SZ", False, pd.Timestamp("2020-08-24")),
            0.20,
        )

    def test_star_limit_20pct(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("688001.SH", False, pd.Timestamp("2024-01-15")),
            0.20,
        )

    def test_bse_limit_30pct(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("830001.BJ", False, pd.Timestamp("2024-01-15")),
            0.30,
        )

    def test_limit_price_rounding_half_up_boundary(self):
        """A pre_close that produces .xx5 midpoint should round up."""
        # pre_close=10.05, limit_pct=0.10
        # limit_up = 10.05 * 1.10 = 11.055 -> round-half-up -> 11.06
        # (banker's would give 11.06 here too, so use a trickier case)
        # pre_close=10.25, limit_pct=0.10
        # limit_up = 10.25 * 1.10 = 11.275 -> round-half-up -> 11.28
        # (banker's round(11.275, 2) -> 11.28 also, hmm)
        # Better: pre_close=10.15, limit_pct=0.10
        # limit_up = 10.15 * 1.10 = 11.165 -> round-half-up -> 11.17
        # banker's: round(11.165, 2) -> 11.16  (half-to-even rounds DOWN)
        limit_up, _ = self.ex.compute_limit_prices(10.15, 0.10)
        self.assertAlmostEqual(limit_up, 11.17, places=2)


if __name__ == "__main__":
    unittest.main()
