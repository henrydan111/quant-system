r"""
Comprehensive Test Suite for Event-Driven A-Share Backtester

Tests organized by component:
1. Portfolio (T+1, lot size, costs, partial fills)
2. Exchange (limits, ST, IPO, costs, slippage)
3. CorporateActionHandler (dividends, bonus shares)
4. Engine Integration (full loop, edge cases, data compatibility)

Run:
    E:\量化系统\venv\Scripts\python.exe E:\量化系统\tests\harnesses\backtester_smoke.py

Uses real data from data/ directory for integration tests.
"""

import os
import sys
import unittest
import logging
from unittest.mock import patch, MagicMock

import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
sys.path.insert(0, PROJECT_ROOT)

from src.backtest_engine.event_driven.portfolio import Portfolio, Position
from src.backtest_engine.event_driven.exchange import (
    Exchange, CostConfig, NoSlippage, FixedSlippage, PctSlippage,
)
from src.backtest_engine.event_driven.strategy import Strategy, Order, BacktestContext
from src.backtest_engine.event_driven.data_feeder import DailyDataFeeder
from src.backtest_engine.event_driven.engine import BacktestEngine, BacktestResult

logging.basicConfig(level=logging.WARNING)


# ═══════════════════════════════════════════════════════════════════
# 1. PORTFOLIO TESTS
# ═══════════════════════════════════════════════════════════════════

class TestPosition(unittest.TestCase):
    """Test Position T+1 mechanics."""

    def test_new_position_not_closeable(self):
        """#15: Shares bought today cannot be sold today."""
        pos = Position(code='000001.SZ', shares=1000,
                       closeable_amount=0, avg_cost=10.0)
        self.assertEqual(pos.closeable_amount, 0)

    def test_start_new_day_unlocks(self):
        """#16: Next trading day, all shares become closeable."""
        pos = Position(code='000001.SZ', shares=1000,
                       closeable_amount=0, avg_cost=10.0)
        pos.start_new_day()
        self.assertEqual(pos.closeable_amount, 1000)

    def test_add_shares_locks_new(self):
        """#19: Buy more of existing position — new shares locked."""
        pos = Position(code='000001.SZ', shares=700,
                       closeable_amount=700, avg_cost=10.0)
        pos.add_shares(300, 11.0, pd.Timestamp('2024-01-02'))
        self.assertEqual(pos.shares, 1000)
        self.assertEqual(pos.closeable_amount, 700)  # Only old shares

    def test_avg_cost_update(self):
        """#46: Average cost updated on add_shares."""
        pos = Position(code='000001.SZ', shares=500,
                       closeable_amount=500, avg_cost=10.0)
        pos.add_shares(500, 12.0, pd.Timestamp('2024-01-02'))
        expected = (10.0 * 500 + 12.0 * 500) / 1000
        self.assertAlmostEqual(pos.avg_cost, expected, places=4)

    def test_remove_shares_decrements_both(self):
        """#47: Partial sell — shares and closeable both reduced."""
        pos = Position(code='000001.SZ', shares=500,
                       closeable_amount=500, avg_cost=10.0)
        pos.remove_shares(200)
        self.assertEqual(pos.shares, 300)
        self.assertEqual(pos.closeable_amount, 300)

    def test_remove_more_than_closeable_raises(self):
        """#20: Cannot sell more than closeable amount."""
        pos = Position(code='000001.SZ', shares=500,
                       closeable_amount=200, avg_cost=10.0)
        with self.assertRaises(ValueError):
            pos.remove_shares(300)

    def test_is_empty(self):
        """Position is empty when shares == 0."""
        pos = Position(code='000001.SZ', shares=0,
                       closeable_amount=0, avg_cost=10.0)
        self.assertTrue(pos.is_empty)


class TestPortfolio(unittest.TestCase):
    """Test Portfolio cash, buying, selling, and tracking."""

    def setUp(self):
        self.portfolio = Portfolio(100_000)

    def test_initial_state(self):
        """Starting cash and no positions."""
        self.assertEqual(self.portfolio.cash, 100_000)
        self.assertEqual(len(self.portfolio.positions), 0)

    def test_invalid_cash_raises(self):
        """Negative initial cash raises error."""
        with self.assertRaises(ValueError):
            Portfolio(-100)

    def test_buy_lot_rounding(self):
        """#21: Buy rounds down to lot size 100."""
        invested = self.portfolio.buy(
            '000001.SZ', price=8.37, target_value=25000,
            date=pd.Timestamp('2024-01-02'), lot_size=100,
            commission=0.00025
        )
        pos = self.portfolio.get_position('000001.SZ')
        self.assertEqual(pos.shares, 2900)  # 29 lots
        self.assertAlmostEqual(invested, 2900 * 8.37, places=2)

    def test_buy_insufficient_cash(self):
        """#22: Cash too small for even 1 lot."""
        p = Portfolio(400)
        invested = p.buy(
            '000001.SZ', price=10.0, target_value=400,
            date=pd.Timestamp('2024-01-02'), lot_size=100,
            commission=0.00025
        )
        # 400 / (10.0 * 100 * 1.00025) = 0.39 lots -> 0
        self.assertEqual(invested, 0.0)
        self.assertEqual(len(p.positions), 0)

    def test_min_commission(self):
        """#23: Commission below ¥5 gets charged ¥5."""
        p = Portfolio(100_000)
        p.buy('000001.SZ', price=10.0, target_value=1000,
              date=pd.Timestamp('2024-01-02'), lot_size=100,
              commission=0.00025)
        # 100 shares * 10 = 1000, commission = max(0.25, 5) = 5
        self.assertAlmostEqual(p.cash, 100_000 - 1000 - 5, places=2)

    def test_t1_buy_then_sell_same_day(self):
        """#15: Cannot sell shares bought today."""
        self.portfolio.buy(
            '000001.SZ', price=10.0, target_value=10000,
            date=pd.Timestamp('2024-01-02'), lot_size=100,
            commission=0.00025
        )
        self.assertFalse(self.portfolio.can_sell('000001.SZ'))

    def test_t1_buy_sell_next_day(self):
        """#16: Can sell shares next trading day."""
        self.portfolio.buy(
            '000001.SZ', price=10.0, target_value=10000,
            date=pd.Timestamp('2024-01-02'), lot_size=100,
            commission=0.00025
        )
        self.portfolio.start_new_day()
        self.assertTrue(self.portfolio.can_sell('000001.SZ'))

    def test_sell_partial(self):
        """#47: Can sell part of a position."""
        self.portfolio.buy(
            '000001.SZ', price=10.0, target_value=50000,
            date=pd.Timestamp('2024-01-02'), lot_size=100,
            commission=0.00025
        )
        self.portfolio.start_new_day()
        proceeds = self.portfolio.sell(
            '000001.SZ', price=11.0, shares=200,
            date=pd.Timestamp('2024-01-03'),
            commission=0.00025, stamp_tax=0.0005
        )
        self.assertGreater(proceeds, 0)
        pos = self.portfolio.get_position('000001.SZ')
        self.assertIsNotNone(pos)
        self.assertEqual(pos.shares, 4800)  # 5000 - 200

    def test_force_close(self):
        """#40: Force-close adds proceeds to cash, removes position."""
        self.portfolio.buy(
            '000001.SZ', price=10.0, target_value=10000,
            date=pd.Timestamp('2024-01-02'), lot_size=100,
            commission=0.00025
        )
        self.portfolio.force_close('000001.SZ', price=9.0)
        self.assertIsNone(self.portfolio.get_position('000001.SZ'))

    def test_credit_cash(self):
        """Dividend cash is correctly credited."""
        self.portfolio.credit_cash(500)
        self.assertEqual(self.portfolio.cash, 100_500)

    def test_daily_counters_reset(self):
        """#53: Cost and turnover counters reset each day."""
        self.portfolio.buy(
            '000001.SZ', price=10.0, target_value=10000,
            date=pd.Timestamp('2024-01-02'), lot_size=100,
            commission=0.00025
        )
        self.assertGreater(self.portfolio.get_today_costs(), 0)
        self.portfolio.start_new_day()
        self.assertEqual(self.portfolio.get_today_costs(), 0)
        self.assertEqual(self.portfolio.get_today_turnover(), 0)

    def test_total_value_integrity(self):
        """#52: total_value == cash + market_value always."""
        self.portfolio.buy(
            '000001.SZ', price=10.0, target_value=50000,
            date=pd.Timestamp('2024-01-02'), lot_size=100,
            commission=0.00025
        )
        prices = {'000001.SZ': 11.0}
        tv = self.portfolio.total_value(prices)
        mv = self.portfolio.market_value(prices)
        self.assertAlmostEqual(tv, self.portfolio.cash + mv, places=2)

    def test_all_cash_no_positions(self):
        """#49: Empty portfolio return is 0."""
        prices = {}
        tv = self.portfolio.total_value(prices)
        self.assertAlmostEqual(tv, 100_000, places=2)

    def test_weight_calculation(self):
        """Portfolio weight sums correctly."""
        self.portfolio.buy(
            '000001.SZ', price=10.0, target_value=50000,
            date=pd.Timestamp('2024-01-02'), lot_size=100,
            commission=0.00025
        )
        prices = {'000001.SZ': 10.0}
        w = self.portfolio.weight('000001.SZ', prices)
        self.assertGreater(w, 0)
        self.assertLess(w, 1)


# ═══════════════════════════════════════════════════════════════════
# 2. EXCHANGE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestExchange(unittest.TestCase):
    """Test Exchange limit detection, costs, and tradability."""

    def setUp(self):
        self.exchange = Exchange(CostConfig())

    def _make_row(self, open_=10.0, close=10.0, pre_close=10.0,
                  vol=10000, ts_code='000001.SZ'):
        """Create a mock daily data row."""
        return pd.Series({
            'ts_code': ts_code,
            'open': open_,
            'close': close,
            'pre_close': pre_close,
            'vol': vol,
            'high': max(open_, close),
            'low': min(open_, close),
        })

    def test_limit_up_detection(self):
        """#6: Stock at limit-up detected correctly."""
        # Main board: 10% limit
        row = self._make_row(pre_close=10.0, close=11.0)
        self.assertTrue(
            self.exchange.is_limit_up(row, '000001.SZ',
                                       pd.Timestamp('2024-01-02'))
        )

    def test_limit_down_detection(self):
        """#8: Stock at limit-down detected correctly."""
        row = self._make_row(pre_close=10.0, close=9.0)
        self.assertTrue(
            self.exchange.is_limit_down(row, '000001.SZ',
                                         pd.Timestamp('2024-01-02'))
        )

    def test_not_limit(self):
        """Normal close is not limit."""
        row = self._make_row(pre_close=10.0, close=10.50)
        self.assertFalse(
            self.exchange.is_limit_up(row, '000001.SZ',
                                       pd.Timestamp('2024-01-02'))
        )
        self.assertFalse(
            self.exchange.is_limit_down(row, '000001.SZ',
                                         pd.Timestamp('2024-01-02'))
        )

    def test_cant_buy_limit_up(self):
        """#6: Cannot buy when limit-up."""
        row = self._make_row(pre_close=10.0, close=11.0, vol=5000)
        self.assertFalse(
            self.exchange.can_buy(row, '000001.SZ',
                                   pd.Timestamp('2024-01-02'))
        )

    def test_can_sell_limit_up(self):
        """#7: Can sell when limit-up (there are buyers)."""
        row = self._make_row(pre_close=10.0, close=11.0, vol=5000)
        self.assertTrue(
            self.exchange.can_sell(row, '000001.SZ',
                                    pd.Timestamp('2024-01-02'))
        )

    def test_cant_sell_limit_down(self):
        """#8: Cannot sell when limit-down."""
        row = self._make_row(pre_close=10.0, close=9.0, vol=5000)
        self.assertFalse(
            self.exchange.can_sell(row, '000001.SZ',
                                    pd.Timestamp('2024-01-02'))
        )

    def test_can_buy_limit_down(self):
        """#9: Can buy when limit-down (there are sellers)."""
        row = self._make_row(pre_close=10.0, close=9.0, vol=5000)
        self.assertTrue(
            self.exchange.can_buy(row, '000001.SZ',
                                   pd.Timestamp('2024-01-02'))
        )

    def test_suspended_vol_zero(self):
        """#1: Stock with vol=0 is suspended."""
        row = self._make_row(vol=0)
        self.assertTrue(self.exchange.is_suspended(row))

    def test_suspended_vol_nan(self):
        """#5: Stock with vol=NaN is suspended."""
        row = self._make_row(vol=float('nan'))
        self.assertTrue(self.exchange.is_suspended(row))

    def test_suspended_cant_trade(self):
        """#2: Suspended stock can't be bought or sold."""
        row = self._make_row(vol=0)
        self.assertFalse(
            self.exchange.can_buy(row, '000001.SZ',
                                   pd.Timestamp('2024-01-02'))
        )
        self.assertFalse(
            self.exchange.can_sell(row, '000001.SZ',
                                    pd.Timestamp('2024-01-02'))
        )

    def test_st_limit_5pct(self):
        """#11: ST stock uses ±5% limit."""
        # Manually set ST
        self.exchange._st_map = {
            '000001.SZ': [(pd.Timestamp('2020-01-01'),
                           pd.Timestamp('2025-12-31'))]
        }
        pct = self.exchange.get_limit_pct(
            '000001.SZ', True, pd.Timestamp('2024-01-02')
        )
        self.assertAlmostEqual(pct, 0.05)

    def test_chinext_20pct_post_reform(self):
        """#12/#64: ChiNext stock uses ±20% after 2020-08-24."""
        pct = self.exchange.get_limit_pct(
            '300001.SZ', False, pd.Timestamp('2024-01-02')
        )
        self.assertAlmostEqual(pct, 0.20)

    def test_chinext_10pct_pre_reform(self):
        """#63: ChiNext stock uses ±10% before 2020-08-24."""
        pct = self.exchange.get_limit_pct(
            '300001.SZ', False, pd.Timestamp('2020-08-23')
        )
        self.assertAlmostEqual(pct, 0.10)

    def test_star_20pct(self):
        """STAR stock uses ±20%."""
        pct = self.exchange.get_limit_pct(
            '688001.SH', False, pd.Timestamp('2024-01-02')
        )
        self.assertAlmostEqual(pct, 0.20)

    def test_bse_30pct(self):
        """BSE stock uses ±30%."""
        pct = self.exchange.get_limit_pct(
            '830001.BJ', False, pd.Timestamp('2024-01-02')
        )
        self.assertAlmostEqual(pct, 0.30)

    def test_penny_stock_floor(self):
        """#14: Limit-down floors at ¥0.01."""
        up, down = self.exchange.compute_limit_prices(0.10, 0.10)
        self.assertEqual(down, max(round(0.10 * 0.9, 2), 0.01))
        self.assertGreaterEqual(down, 0.01)

    def test_limit_tolerance(self):
        """#13: Close within ±0.005 of limit is detected."""
        # Limit up = 11.00, close at 10.996 should be detected
        row = self._make_row(pre_close=10.0, close=10.996)
        self.assertTrue(
            self.exchange.is_limit_up(row, '000001.SZ',
                                       pd.Timestamp('2024-01-02'))
        )

    # ─── Costs ────────────────────────────────────────────────────

    def test_stamp_tax_pre_20230828(self):
        """#27: Pre 2023-08-28 stamp = 0.1%."""
        cost = self.exchange.compute_sell_cost(
            10000, pd.Timestamp('2023-08-27')
        )
        # commission = max(10000*0.00025, 5) = 5, stamp = 10000*0.001 = 10
        self.assertAlmostEqual(cost, 5 + 10, places=2)

    def test_stamp_tax_post_20230828(self):
        """#28: Post 2023-08-28 stamp = 0.05%."""
        cost = self.exchange.compute_sell_cost(
            10000, pd.Timestamp('2023-08-28')
        )
        # commission = 5, stamp = 10000*0.0005 = 5
        self.assertAlmostEqual(cost, 5 + 5, places=2)

    def test_buy_no_stamp_tax(self):
        """#30: Buy has no stamp tax."""
        cost = self.exchange.compute_buy_cost(
            10000, pd.Timestamp('2024-01-02')
        )
        # commission = max(10000*0.00025, 5) = 5
        self.assertAlmostEqual(cost, 5, places=2)

    # ─── Volume ───────────────────────────────────────────────────

    def test_volume_limit(self):
        """#55: Buy capped at 25% of daily volume."""
        row = self._make_row(open_=10.0, vol=1000)
        # vol=1000手 = 100,000 shares, 25% = 25,000 shares
        max_val = self.exchange.max_buyable_value(row)
        self.assertAlmostEqual(max_val, 25000 * 10.0, places=2)

    # ─── Slippage ─────────────────────────────────────────────────

    def test_no_slippage(self):
        """No slippage returns exact price."""
        row = self._make_row()
        price = NoSlippage().apply(10.0, 'buy', 10000, row)
        self.assertEqual(price, 10.0)

    def test_fixed_slippage_buy(self):
        """#60: Fixed slippage adds spread to buy."""
        s = FixedSlippage(spread=0.02)
        row = self._make_row()
        price = s.apply(10.0, 'buy', 10000, row)
        self.assertAlmostEqual(price, 10.02)

    def test_fixed_slippage_sell(self):
        """Fixed slippage subtracts spread from sell."""
        s = FixedSlippage(spread=0.02)
        row = self._make_row()
        price = s.apply(10.0, 'sell', 10000, row)
        self.assertAlmostEqual(price, 9.98)

    def test_pct_slippage(self):
        """Percentage slippage applied correctly."""
        s = PctSlippage(rate=0.001)
        row = self._make_row()
        buy_price = s.apply(10.0, 'buy', 10000, row)
        sell_price = s.apply(10.0, 'sell', 10000, row)
        self.assertAlmostEqual(buy_price, 10.01)
        self.assertAlmostEqual(sell_price, 9.99)

    def test_lot_size_main_board(self):
        """Main board lot size is 100."""
        self.assertEqual(self.exchange.get_lot_size('000001.SZ'), 100)

    def test_lot_size_chinext(self):
        """ChiNext lot size is 100."""
        self.assertEqual(self.exchange.get_lot_size('300001.SZ'), 100)


# ═══════════════════════════════════════════════════════════════════
# 3. CORPORATE ACTION TESTS (with mock data)
# ═══════════════════════════════════════════════════════════════════

class TestCorporateActions(unittest.TestCase):
    """Test dividend and bonus share processing."""

    def _make_handler_with_action(self, ts_code, ex_date,
                                  cash_div=0, cash_div_tax=0,
                                  stk_div=0, stk_bo_rate=0,
                                  stk_co_rate=0):
        """Create a handler with a single mock action."""
        from src.backtest_engine.event_driven.corporate_actions import (
            CorporateActionHandler
        )
        handler = CorporateActionHandler.__new__(CorporateActionHandler)
        handler.dividends_dir = ''
        handler.by_date = {}
        handler.action_log = []
        action = {
            'ts_code': ts_code,
            'ex_date': ex_date,
            'cash_div': cash_div,
            'cash_div_tax': cash_div_tax,
            'stk_div': stk_div,
            'stk_bo_rate': stk_bo_rate,
            'stk_co_rate': stk_co_rate,
        }
        handler.by_date[ex_date] = [action]
        return handler

    def test_cash_dividend(self):
        """#67: Cash dividend credited: cash_div_tax * shares."""
        handler = self._make_handler_with_action(
            '000001.SZ', '20240715', cash_div_tax=0.50
        )
        p = Portfolio(100_000)
        p.buy('000001.SZ', price=10.0, target_value=10000,
              date=pd.Timestamp('2024-07-10'), lot_size=100,
              commission=0.00025)
        cash_before = p.cash

        handler.process(pd.Timestamp('2024-07-15'), p)
        pos = p.get_position('000001.SZ')
        expected_div = 0.50 * pos.shares
        self.assertAlmostEqual(p.cash - cash_before, expected_div, places=2)

    def test_bonus_shares(self):
        """#68: Bonus shares added, avg_cost adjusted."""
        handler = self._make_handler_with_action(
            '000001.SZ', '20240715', stk_div=0.4
        )
        p = Portfolio(100_000)
        p.buy('000001.SZ', price=10.0, target_value=10000,
              date=pd.Timestamp('2024-07-10'), lot_size=100,
              commission=0.00025)
        pos = p.get_position('000001.SZ')
        old_shares = pos.shares
        old_cost = pos.avg_cost

        handler.process(pd.Timestamp('2024-07-15'), p)
        pos = p.get_position('000001.SZ')
        new_shares = int(old_shares * 0.4)
        self.assertEqual(pos.shares, old_shares + new_shares)
        # avg_cost adjusted down
        self.assertAlmostEqual(pos.avg_cost, old_cost / 1.4, places=4)

    def test_combined_dividend_and_bonus(self):
        """#69: Cash + bonus shares together."""
        handler = self._make_handler_with_action(
            '000001.SZ', '20240715',
            cash_div_tax=0.30, stk_div=0.2
        )
        p = Portfolio(100_000)
        p.buy('000001.SZ', price=10.0, target_value=10000,
              date=pd.Timestamp('2024-07-10'), lot_size=100,
              commission=0.00025)
        pos = p.get_position('000001.SZ')
        old_shares = pos.shares
        cash_before = p.cash

        handler.process(pd.Timestamp('2024-07-15'), p)
        pos = p.get_position('000001.SZ')
        self.assertAlmostEqual(
            p.cash - cash_before, 0.30 * old_shares, places=2
        )
        self.assertEqual(pos.shares, old_shares + int(old_shares * 0.2))

    def test_not_holding_no_effect(self):
        """#70: If not holding, dividend has no effect."""
        handler = self._make_handler_with_action(
            '000001.SZ', '20240715', cash_div_tax=0.50
        )
        p = Portfolio(100_000)
        handler.process(pd.Timestamp('2024-07-15'), p)
        self.assertEqual(p.cash, 100_000)

    def test_bonus_shares_truncated(self):
        """#72: Fractional bonus shares truncated."""
        handler = self._make_handler_with_action(
            '000001.SZ', '20240715', stk_div=0.3
        )
        p = Portfolio(100_000)
        p.buy('000001.SZ', price=10.0, target_value=10000,
              date=pd.Timestamp('2024-07-10'), lot_size=100,
              commission=0.00025)
        pos = p.get_position('000001.SZ')
        old_shares = pos.shares  # 1000
        handler.process(pd.Timestamp('2024-07-15'), p)
        pos = p.get_position('000001.SZ')
        self.assertEqual(pos.shares, old_shares + int(old_shares * 0.3))

    def test_action_log_recorded(self):
        """Corporate actions are logged for BacktestResult."""
        handler = self._make_handler_with_action(
            '000001.SZ', '20240715', cash_div_tax=0.50, stk_div=0.2
        )
        p = Portfolio(100_000)
        p.buy('000001.SZ', price=10.0, target_value=10000,
              date=pd.Timestamp('2024-07-10'), lot_size=100,
              commission=0.00025)
        handler.process(pd.Timestamp('2024-07-15'), p)
        self.assertEqual(len(handler.action_log), 2)  # cash + bonus


# ═══════════════════════════════════════════════════════════════════
# 4. DATA FEEDER TESTS (with real data)
# ═══════════════════════════════════════════════════════════════════

class TestDataFeeder(unittest.TestCase):
    """Test DailyDataFeeder with real data."""

    @classmethod
    def setUpClass(cls):
        """Load feeder once for all tests."""
        cls.feeder = DailyDataFeeder(DATA_DIR)

    def test_trading_calendar(self):
        """Calendar returns correct trading days."""
        cal = self.feeder.get_trading_calendar('2024-01-01', '2024-01-31')
        self.assertGreater(len(cal), 15)
        self.assertLess(len(cal), 25)
        # All should be Timestamps
        for d in cal:
            self.assertIsInstance(d, pd.Timestamp)

    def test_get_day(self):
        """get_day returns a DataFrame with expected columns."""
        self.feeder.preload(pd.Timestamp('2024-01-02'),
                            pd.Timestamp('2024-01-02'))
        df = self.feeder.get_day(pd.Timestamp('2024-01-02'))
        self.assertGreater(len(df), 4000)  # Many stocks
        self.assertIn('ts_code', df.columns)
        self.assertIn('open', df.columns)
        self.assertIn('close', df.columns)
        self.assertIn('vol', df.columns)

    def test_prev_trading_day(self):
        """prev_trading_day works correctly."""
        prev = self.feeder.get_prev_trading_day(
            pd.Timestamp('2024-01-03')
        )
        self.assertEqual(prev, pd.Timestamp('2024-01-02'))

    def test_next_trading_day(self):
        """next_trading_day skips weekends."""
        # 2024-01-05 is Friday
        nxt = self.feeder.get_next_trading_day(
            pd.Timestamp('2024-01-05')
        )
        self.assertEqual(nxt, pd.Timestamp('2024-01-08'))

    def test_is_trading_day(self):
        """Weekend is not a trading day."""
        self.assertFalse(
            self.feeder.is_trading_day(pd.Timestamp('2024-01-06'))
        )
        self.assertTrue(
            self.feeder.is_trading_day(pd.Timestamp('2024-01-02'))
        )


# ═══════════════════════════════════════════════════════════════════
# 5. ENGINE INTEGRATION TESTS (with real data)
# ═══════════════════════════════════════════════════════════════════

class BuyAndHold(Strategy):
    """Test strategy: buy one stock day 1, hold."""

    def initialize(self, context):
        self.g.bought = False

    def before_market_open(self, context):
        if not self.g.bought and context.trading_day_index == 0:
            self.g.bought = True
            return [Order('000001.SZ', 'buy',
                          target_value=50000, reason='test')]
        return []


class AllCashStrategy(Strategy):
    """Test strategy: do nothing, 100% cash."""

    def initialize(self, context):
        pass


class BuyAndSellNextDay(Strategy):
    """Buy day 1 at open, sell day 2 at close."""

    def initialize(self, context):
        self.g.day = 0

    def before_market_open(self, context):
        self.g.day += 1
        if self.g.day == 1:
            return [Order('000001.SZ', 'buy',
                          target_value=50000, reason='buy')]
        return []

    def on_bar(self, context):
        if self.g.day == 2:
            return [Order('000001.SZ', 'sell',
                          reason='sell_all')]
        return []


class MultiStockStrategy(Strategy):
    """Buy 4 stocks on day 1."""

    def initialize(self, context):
        self.g.bought = False

    def before_market_open(self, context):
        if not self.g.bought and context.trading_day_index == 0:
            self.g.bought = True
            return [
                Order('000001.SZ', 'buy', target_value=25000,
                      reason='rebalance'),
                Order('000002.SZ', 'buy', target_value=25000,
                      reason='rebalance'),
                Order('600519.SH', 'buy', target_value=25000,
                      reason='rebalance'),
                Order('000858.SZ', 'buy', target_value=25000,
                      reason='rebalance'),
            ]
        return []


class TestEngine(unittest.TestCase):
    """Integration tests for BacktestEngine with real data."""

    def _run_backtest(self, strategy, start='2024-01-02', end='2024-01-31',
                      benchmark='000852.SH', cash=100_000):
        """Helper to run a short backtest."""
        from src.backtest_engine.event_driven import EventDrivenBacktester
        bt = EventDrivenBacktester(data_dir=DATA_DIR)
        return bt.run(
            strategy=strategy,
            start_time=start,
            end_time=end,
            benchmark=benchmark,
            account=cash,
        )

    def test_buy_and_hold_basic(self):
        """Full buy-and-hold: 1 stock, 22 days."""
        result = self._run_backtest(BuyAndHold())
        self.assertEqual(len(result.report), 22)
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades.iloc[0]['direction'], 'buy')
        self.assertEqual(result.trades.iloc[0]['code'], '000001.SZ')

    def test_all_cash_zero_return(self):
        """#49: All-cash portfolio has 0 return every day."""
        result = self._run_backtest(AllCashStrategy())
        self.assertEqual(len(result.report), 22)
        self.assertTrue((result.report['return'] == 0).all())
        self.assertAlmostEqual(
            result.report['total_value'].iloc[-1], 100_000, places=2
        )

    def test_buy_sell_round_trip(self):
        """Buy day 1, sell day 2 — verify costs deducted."""
        result = self._run_backtest(BuyAndSellNextDay())
        fills = result.trades[result.trades['direction'] == 'sell']
        self.assertEqual(len(fills), 1)
        # After selling, near all-cash (with PnL + costs)
        final = result.report.iloc[-1]['total_value']
        self.assertAlmostEqual(final, result.report.iloc[-1]['cash'],
                               places=0)

    def test_multi_stock(self):
        """Buy 4 stocks — all should show in holdings."""
        result = self._run_backtest(MultiStockStrategy())
        buys = result.trades[result.trades['direction'] == 'buy']
        # Should have 4 buys (or 3 if one stock couldn't be bought)
        self.assertGreaterEqual(len(buys), 3)
        self.assertLessEqual(len(buys), 4)

    def test_equity_curve(self):
        """#50: Equity curve starts at ~1.0."""
        result = self._run_backtest(BuyAndHold())
        ec = result.equity_curve
        self.assertAlmostEqual(ec.iloc[0], 1 + result.report.iloc[0]['return'],
                               places=6)
        self.assertEqual(len(ec), 22)

    def test_daily_holdings_populated(self):
        """Daily holdings has rows for each day × position."""
        result = self._run_backtest(BuyAndHold())
        self.assertEqual(len(result.daily_holdings), 22)
        self.assertIn('weight', result.daily_holdings.columns)
        self.assertIn('unrealized_pnl', result.daily_holdings.columns)

    def test_order_log_includes_all(self):
        """#66: Order log records every order."""
        result = self._run_backtest(BuyAndHold())
        self.assertEqual(len(result.order_log), 1)
        self.assertEqual(result.order_log.iloc[0]['status'], 'FILLED')

    def test_benchmark_returns(self):
        """#65: Benchmark returns are non-zero."""
        result = self._run_backtest(BuyAndHold())
        bench = result.report['bench']
        self.assertFalse((bench == 0).all())

    def test_summary_metrics(self):
        """Summary returns all 23 JQ metrics."""
        result = self._run_backtest(BuyAndHold())
        s = result.summary
        required_keys = [
            '策略收益 (Total Return)', '策略年化收益 (CAGR)',
            '基准收益 (Benchmark Return)', '超额收益 (Excess Return)',
            '阿尔法 (Alpha)', '贝塔 (Beta)',
            '夏普比率 (Sharpe)', '索提诺比率 (Sortino)',
            '信息比率 (Information Ratio)',
            '最大回撤 (Max Drawdown)', '最大回撤区间 (DD Period)',
            '胜率 (Win Rate)', '日胜率 (Daily Win Rate)',
            '盈亏比 (P/L Ratio)',
            '盈利次数 (Win Count)', '亏损次数 (Loss Count)',
            '策略波动率 (Strategy Vol)', '基准波动率 (Benchmark Vol)',
            '日均超额收益 (Avg Daily Excess)',
            '超额收益夏普比率 (Excess Sharpe)',
        ]
        for key in required_keys:
            self.assertIn(key, s, f'Missing metric: {key}')

    def test_max_drawdown_property(self):
        """max_drawdown property returns negative value."""
        result = self._run_backtest(BuyAndHold())
        self.assertLessEqual(result.max_drawdown, 0)

    def test_excess_returns(self):
        """excess_returns = strategy return - benchmark."""
        result = self._run_backtest(BuyAndHold())
        er = result.excess_returns
        expected = result.report['return'] - result.report['bench']
        pd.testing.assert_series_equal(er, expected)

    # ─── Validation Tests ─────────────────────────────────────────

    def test_start_after_end_raises(self):
        """Start date after end date raises ValueError."""
        with self.assertRaises(ValueError):
            self._run_backtest(BuyAndHold(),
                               start='2024-02-01', end='2024-01-01')

    def test_early_start_raises(self):
        """Start before 2008-01-02 raises ValueError."""
        with self.assertRaises(ValueError):
            self._run_backtest(BuyAndHold(),
                               start='2005-01-01', end='2005-12-31')

    def test_missing_benchmark_raises(self):
        """Non-existent benchmark raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self._run_backtest(BuyAndHold(), benchmark='999999.XX')

    # ─── Longer Period Tests ──────────────────────────────────────

    def test_one_year_backtest(self):
        """Run a full year — verifies data loading and stability."""
        result = self._run_backtest(
            BuyAndHold(), start='2023-01-03', end='2023-12-29'
        )
        self.assertGreater(len(result.report), 230)
        self.assertLess(len(result.report), 260)
        # Portfolio value should still be reasonable
        final = result.report.iloc[-1]['total_value']
        self.assertGreater(final, 50_000)
        self.assertLess(final, 200_000)


# ═══════════════════════════════════════════════════════════════════
# 6. METRICS TESTS
# ═══════════════════════════════════════════════════════════════════

class TestNewMetrics(unittest.TestCase):
    """Test the 2 new metrics functions."""

    def test_profit_loss_ratio(self):
        """P/L ratio: mean(wins) / |mean(losses)|."""
        from src.result_analysis.metrics import calculate_profit_loss_ratio
        r = pd.Series([0.01, 0.02, -0.005, -0.01, 0.015])
        ratio = calculate_profit_loss_ratio(r)
        wins_avg = (0.01 + 0.02 + 0.015) / 3
        loss_avg = abs((-0.005 + -0.01) / 2)
        self.assertAlmostEqual(ratio, wins_avg / loss_avg, places=4)

    def test_profit_loss_ratio_no_losses(self):
        """P/L ratio with no losses returns 0."""
        from src.result_analysis.metrics import calculate_profit_loss_ratio
        r = pd.Series([0.01, 0.02, 0.03])
        self.assertEqual(calculate_profit_loss_ratio(r), 0.0)

    def test_max_drawdown_period(self):
        """Max DD period returns correct dates."""
        from src.result_analysis.metrics import calculate_max_drawdown_period
        dates = pd.date_range('2024-01-02', periods=10, freq='B')
        # Small gains then big drop
        r = pd.Series(
            [0.01, 0.02, 0.01, -0.05, -0.03, 0.01, 0.01, 0.02, 0.01, 0.01],
            index=dates
        )
        start, end = calculate_max_drawdown_period(r)
        self.assertIn('2024/01', start)
        self.assertIn('2024/01', end)

    def test_max_drawdown_period_empty(self):
        """Max DD period with empty series returns empty strings."""
        from src.result_analysis.metrics import calculate_max_drawdown_period
        start, end = calculate_max_drawdown_period(pd.Series(dtype=float))
        self.assertEqual(start, '')
        self.assertEqual(end, '')


if __name__ == '__main__':
    print('='*70)
    print('Event-Driven Backtester — Test Suite')
    print('='*70)
    unittest.main(verbosity=2)
