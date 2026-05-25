"""Follow-up Plan #2 — Exchange cost model regression tests.

Tests the consolidated cost helpers (P0-1, P0-4a/b) and the stamp tax
date boundary. Every test in this file locks a specific cost computation
against expected values — if Exchange internals change, these tests
surface the delta immediately.
"""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest_engine.event_driven.exchange import (
    CostBreakdown,
    CostConfig,
    Exchange,
    NoSlippage,
)


class CostBreakdownTests(unittest.TestCase):

    def test_sell_cost_breakdown_returns_named_tuple(self):
        # 2026-05-22: default CostConfig is JoinQuant (no transfer fee, no 2023 cut).
        # Use realistic_china() to get transfer_fee > 0.
        ex = Exchange(cost_config=CostConfig.realistic_china(), slippage_model=NoSlippage())
        result = ex.compute_sell_cost_breakdown(100_000, pd.Timestamp("2024-01-15"))
        self.assertIsInstance(result, CostBreakdown)
        self.assertGreater(result.commission, 0)
        self.assertGreater(result.stamp, 0)
        self.assertGreater(result.transfer_fee, 0)
        self.assertAlmostEqual(
            result.total,
            result.commission + result.stamp + result.transfer_fee,
            places=6,
        )

    def test_buy_cost_breakdown_has_zero_stamp(self):
        # Realistic preset still carries transfer_fee on buys.
        ex = Exchange(cost_config=CostConfig.realistic_china(), slippage_model=NoSlippage())
        result = ex.compute_buy_cost_breakdown(100_000, pd.Timestamp("2024-01-15"))
        self.assertIsInstance(result, CostBreakdown)
        self.assertEqual(result.stamp, 0.0)
        self.assertGreater(result.commission, 0)
        self.assertGreater(result.transfer_fee, 0)

    def test_scalar_sell_cost_equals_breakdown_total(self):
        ex = Exchange(slippage_model=NoSlippage())
        date = pd.Timestamp("2024-06-15")
        scalar = ex.compute_sell_cost(50_000, date)
        breakdown = ex.compute_sell_cost_breakdown(50_000, date)
        self.assertAlmostEqual(scalar, breakdown.total, places=6)

    def test_scalar_buy_cost_equals_breakdown_total(self):
        ex = Exchange(slippage_model=NoSlippage())
        date = pd.Timestamp("2024-06-15")
        scalar = ex.compute_buy_cost(50_000, date)
        breakdown = ex.compute_buy_cost_breakdown(50_000, date)
        self.assertAlmostEqual(scalar, breakdown.total, places=6)


class CommissionTests(unittest.TestCase):

    def test_commission_min_enforced(self):
        """Trade value * rate < min_commission -> min_commission used."""
        config = CostConfig(buy_commission=0.00025, min_commission=5.0)
        ex = Exchange(cost_config=config, slippage_model=NoSlippage())
        # 1000 * 0.00025 = 0.25, which is < min 5.0
        bd = ex.compute_buy_cost_breakdown(1_000, pd.Timestamp("2024-01-15"))
        self.assertAlmostEqual(bd.commission, 5.0)

    def test_commission_proportional(self):
        """Trade value * rate >= min_commission -> proportional."""
        config = CostConfig(buy_commission=0.00025, min_commission=5.0)
        ex = Exchange(cost_config=config, slippage_model=NoSlippage())
        # 100_000 * 0.00025 = 25.0
        bd = ex.compute_buy_cost_breakdown(100_000, pd.Timestamp("2024-01-15"))
        self.assertAlmostEqual(bd.commission, 25.0)


class StampTaxBoundaryTests(unittest.TestCase):

    # The 2023-08-28 stamp-tax cut is ONLY applied under the realistic_china
    # preset. The default JoinQuant preset uses 0.1% constant (matches JQ).
    def test_stamp_tax_pre_20230828_realistic(self):
        """realistic_china preset: sell on 2023-08-27 uses pre-change rate 0.001."""
        ex = Exchange(cost_config=CostConfig.realistic_china(), slippage_model=NoSlippage())
        bd = ex.compute_sell_cost_breakdown(100_000, pd.Timestamp("2023-08-27"))
        self.assertAlmostEqual(bd.stamp, 100_000 * 0.001)

    def test_stamp_tax_on_20230828_realistic(self):
        """realistic_china preset: boundary day 2023-08-28 uses new rate 0.0005."""
        ex = Exchange(cost_config=CostConfig.realistic_china(), slippage_model=NoSlippage())
        bd = ex.compute_sell_cost_breakdown(100_000, pd.Timestamp("2023-08-28"))
        self.assertAlmostEqual(bd.stamp, 100_000 * 0.0005)

    def test_stamp_tax_post_20230828_realistic(self):
        """realistic_china preset: sell on 2023-08-29 uses new rate 0.0005."""
        ex = Exchange(cost_config=CostConfig.realistic_china(), slippage_model=NoSlippage())
        bd = ex.compute_sell_cost_breakdown(100_000, pd.Timestamp("2023-08-29"))
        self.assertAlmostEqual(bd.stamp, 100_000 * 0.0005)

    def test_default_stamp_tax_is_jq_constant(self):
        """2026-05-22: default CostConfig() uses 0.1% stamp tax CONSTANT (JoinQuant).
        Both pre and post 2023-08-28 should yield 0.001 — no boundary."""
        ex = Exchange(slippage_model=NoSlippage())   # default cost_config
        bd_pre = ex.compute_sell_cost_breakdown(100_000, pd.Timestamp("2023-08-27"))
        bd_post = ex.compute_sell_cost_breakdown(100_000, pd.Timestamp("2023-08-29"))
        self.assertAlmostEqual(bd_pre.stamp, 100_000 * 0.001)
        self.assertAlmostEqual(bd_post.stamp, 100_000 * 0.001)


class TransferFeeTests(unittest.TestCase):

    def test_transfer_fee_on_buy(self):
        config = CostConfig(transfer_fee=0.00002)
        ex = Exchange(cost_config=config, slippage_model=NoSlippage())
        bd = ex.compute_buy_cost_breakdown(100_000, pd.Timestamp("2024-01-15"))
        self.assertAlmostEqual(bd.transfer_fee, 100_000 * 0.00002)

    def test_transfer_fee_on_sell(self):
        config = CostConfig(transfer_fee=0.00002)
        ex = Exchange(cost_config=config, slippage_model=NoSlippage())
        bd = ex.compute_sell_cost_breakdown(100_000, pd.Timestamp("2024-01-15"))
        self.assertAlmostEqual(bd.transfer_fee, 100_000 * 0.00002)

    def test_transfer_fee_default_is_zero_jq(self):
        """2026-05-22: default CostConfig() has transfer_fee=0 (JoinQuant
        does not model 过户费). Use realistic_china() to get 0.2 bps."""
        self.assertEqual(CostConfig().transfer_fee, 0.0)

    def test_transfer_fee_realistic_china_is_2bps(self):
        self.assertAlmostEqual(CostConfig.realistic_china().transfer_fee, 0.00002)


class CostConfigPresetTests(unittest.TestCase):
    """Locks the JoinQuant-default vs realistic-china preset semantics."""

    def test_joinquant_default_matches_jq_ordercost(self):
        """CostConfig() (== CostConfig.joinquant_default()) must equal JoinQuant:
        OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5/10000,
                  close_commission=2.5/10000, min_commission=5).
        """
        c = CostConfig()
        self.assertEqual(c.buy_commission, 2.5 / 10000)
        self.assertEqual(c.sell_commission, 2.5 / 10000)
        self.assertEqual(c.stamp_tax, 0.001)
        self.assertEqual(c.stamp_tax_pre_20230828, 0.001)
        self.assertEqual(c.min_commission, 5.0)
        self.assertEqual(c.transfer_fee, 0.0)

    def test_joinquant_default_factory_equals_default(self):
        c1, c2 = CostConfig(), CostConfig.joinquant_default()
        self.assertEqual(c1, c2)

    def test_realistic_china_preset(self):
        c = CostConfig.realistic_china()
        self.assertEqual(c.stamp_tax, 0.0005)
        self.assertEqual(c.stamp_tax_pre_20230828, 0.001)
        self.assertEqual(c.transfer_fee, 0.00002)


if __name__ == "__main__":
    unittest.main()
