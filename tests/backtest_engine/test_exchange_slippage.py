"""Follow-up Plan #2 — Slippage model regression tests (P0-2, P0-3)."""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest_engine.event_driven.exchange import (
    Exchange,
    FixedSlippage,
    NoSlippage,
    PctSlippage,
)


class NoSlippageTests(unittest.TestCase):
    def test_no_slippage_is_identity(self):
        s = NoSlippage()
        row = pd.Series({"vol": 1000, "amount": 10000})
        self.assertEqual(s.apply(10.0, "buy", 0, row), 10.0)
        self.assertEqual(s.apply(10.0, "sell", 0, row), 10.0)


class FixedSlippageTests(unittest.TestCase):
    def test_default_spread_is_001(self):
        s = FixedSlippage()
        self.assertEqual(s.spread, 0.01)

    def test_buy_adds_spread(self):
        s = FixedSlippage(spread=0.02)
        row = pd.Series({"vol": 1000})
        self.assertAlmostEqual(s.apply(10.0, "buy", 0, row), 10.02)

    def test_sell_subtracts_spread_with_floor(self):
        s = FixedSlippage(spread=0.02)
        row = pd.Series({"vol": 1000})
        self.assertAlmostEqual(s.apply(10.0, "sell", 0, row), 9.98)
        # Floor at 0.01 for tiny prices
        self.assertAlmostEqual(s.apply(0.005, "sell", 0, row), 0.01)


class PctSlippageTests(unittest.TestCase):
    def test_default_rate_is_10bps(self):
        s = PctSlippage()
        self.assertEqual(s.rate, 0.001)

    def test_buy_increases_price(self):
        s = PctSlippage(0.001)
        row = pd.Series({"vol": 1000})
        self.assertAlmostEqual(s.apply(10.0, "buy", 0, row), 10.01)

    def test_sell_decreases_price(self):
        s = PctSlippage(0.001)
        row = pd.Series({"vol": 1000})
        self.assertAlmostEqual(s.apply(10.0, "sell", 0, row), 9.99)


class ExchangeDefaultSlippageTests(unittest.TestCase):
    def test_exchange_default_slippage_is_jq_fixed_0p0003(self):
        """2026-05-22: Exchange() with no slippage_model must default to
        FixedSlippage(0.0003), matching JoinQuant's standard
        FixedSlippage(3/10000). See CLAUDE.md §3 (Exchange default slippage)
        for the deployment-medium rationale."""
        ex = Exchange()
        self.assertIsInstance(ex.slippage_model, FixedSlippage)
        self.assertAlmostEqual(ex.slippage_model.spread, 0.0003)

    def test_exchange_explicit_no_slippage(self):
        """Callers can still explicitly request NoSlippage."""
        ex = Exchange(slippage_model=NoSlippage())
        self.assertIsInstance(ex.slippage_model, NoSlippage)

    def test_exchange_explicit_conservative_10bps(self):
        """Callers can explicitly request the prior conservative default."""
        from src.backtest_engine.event_driven.exchange import (
            CONSERVATIVE_SLIPPAGE_10BPS,
        )
        ex = Exchange(slippage_model=CONSERVATIVE_SLIPPAGE_10BPS)
        self.assertIsInstance(ex.slippage_model, PctSlippage)
        self.assertEqual(ex.slippage_model.rate, 0.001)

    def test_joinquant_default_constant_matches_default(self):
        from src.backtest_engine.event_driven.exchange import (
            JOINQUANT_DEFAULT_SLIPPAGE,
        )
        ex = Exchange()
        # Same spread value, both are FixedSlippage instances
        self.assertEqual(type(ex.slippage_model), type(JOINQUANT_DEFAULT_SLIPPAGE))
        self.assertAlmostEqual(
            ex.slippage_model.spread, JOINQUANT_DEFAULT_SLIPPAGE.spread,
        )


if __name__ == "__main__":
    unittest.main()
