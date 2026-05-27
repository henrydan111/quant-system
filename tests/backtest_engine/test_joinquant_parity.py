"""JoinQuant-deployment parity regression tests.

These tests lock in the engine-level invariants needed for local backtests to
predict JoinQuant deployment results faithfully. They cover the changes made
2026-05-22 in response to the P1 G5_A2 cross-stack investigation:

  Task 1 — default slippage + costs match JoinQuant (in test_exchange_*.py)
  Task 2 — this file:
    A. Portfolio.available_cash_after_sells() is NaN-robust (v18 bug regression)
    B. Portfolio.safe_total_value() is alias of NaN-robust total_value
    C. BacktestEngine(fill_mode='jq_daily_avg') synthesizes raw_avg correctly
    D. BacktestEngine(fill_mode='open_close') is the default and unchanged
    E. BacktestEngine(fill_mode='invalid') raises ValueError
    F. FixedSlippage(0.0003) ≠ PctSlippage(0.0003) (documentation-error
       regression — the v8-v19 mimic strategies had this confusion)
"""

import sys
import math
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest_engine.event_driven.exchange import (
    FixedSlippage, PctSlippage,
    JOINQUANT_DEFAULT_SLIPPAGE, CONSERVATIVE_SLIPPAGE_10BPS,
)
from src.backtest_engine.event_driven.portfolio import Portfolio, Position


# ─── A. Portfolio.available_cash_after_sells NaN-safety ─────────────

class AvailableCashAfterSellsTests(unittest.TestCase):
    """v18 bug regression: a suspended sold position's NaN prev-close must
    NOT poison the post-sell cash estimate."""

    def _portfolio_with(self, code: str, shares: int, avg_cost: float,
                        cash: float = 0.0) -> Portfolio:
        p = Portfolio(initial_cash=max(cash, 1.0))   # avoid initial_cash<=0
        p._cash = cash
        p._positions[code] = Position(
            code=code, shares=shares, closeable_amount=shares,
            avg_cost=avg_cost, latest_entry_date=pd.Timestamp('2024-01-01'),
        )
        return p

    def test_finite_price_contributes_shares_times_price(self):
        p = self._portfolio_with('000001.SZ', 1000, avg_cost=10.0, cash=50_000)
        out = p.available_cash_after_sells(
            sold_codes=['000001.SZ'],
            prices={'000001.SZ': 12.5},
        )
        self.assertAlmostEqual(out, 50_000 + 1000 * 12.5)

    def test_nan_price_falls_back_to_avg_cost(self):
        """v18 regression: NaN prev-close must NOT poison avail_cash.
        Falls back to avg_cost when ``price_fallback='avg_cost'`` (default)."""
        p = self._portfolio_with('000001.SZ', 1000, avg_cost=10.0, cash=50_000)
        out = p.available_cash_after_sells(
            sold_codes=['000001.SZ'],
            prices={'000001.SZ': float('nan')},
        )
        self.assertTrue(math.isfinite(out))
        self.assertAlmostEqual(out, 50_000 + 1000 * 10.0)

    def test_missing_price_falls_back_to_avg_cost(self):
        p = self._portfolio_with('000001.SZ', 1000, avg_cost=10.0, cash=50_000)
        out = p.available_cash_after_sells(
            sold_codes=['000001.SZ'],
            prices={},  # no entry at all
        )
        self.assertAlmostEqual(out, 50_000 + 1000 * 10.0)

    def test_zero_or_negative_price_falls_back_to_avg_cost(self):
        p = self._portfolio_with('000001.SZ', 1000, avg_cost=10.0, cash=50_000)
        out_zero = p.available_cash_after_sells(['000001.SZ'], {'000001.SZ': 0.0})
        out_neg = p.available_cash_after_sells(['000001.SZ'], {'000001.SZ': -1.0})
        self.assertAlmostEqual(out_zero, 50_000 + 1000 * 10.0)
        self.assertAlmostEqual(out_neg, 50_000 + 1000 * 10.0)

    def test_zero_fallback_contributes_zero_for_nan_price(self):
        p = self._portfolio_with('000001.SZ', 1000, avg_cost=10.0, cash=50_000)
        out = p.available_cash_after_sells(
            sold_codes=['000001.SZ'],
            prices={'000001.SZ': float('nan')},
            price_fallback='zero',
        )
        self.assertAlmostEqual(out, 50_000)   # NaN suspended → 0 proceeds

    def test_missing_position_skipped(self):
        p = self._portfolio_with('000001.SZ', 1000, 10.0, cash=50_000)
        out = p.available_cash_after_sells(
            sold_codes=['NOT.HELD.SZ', '000001.SZ'],
            prices={'000001.SZ': 12.0, 'NOT.HELD.SZ': 5.0},
        )
        self.assertAlmostEqual(out, 50_000 + 1000 * 12.0)

    def test_v18_scenario_one_suspended_position_after_stoploss(self):
        """The exact v18 bug scenario: portfolio is 94% cash + 1 suspended
        stuck position with NaN prev-close. ``available_cash_after_sells``
        must produce a finite value that sizes 12 fresh buys correctly."""
        p = self._portfolio_with(
            '002360.SZ', shares=2000, avg_cost=20.0, cash=346_376,
        )
        # The suspended position has NaN prev-close (it didn't trade yesterday).
        avail = p.available_cash_after_sells(
            sold_codes=['002360.SZ'],
            prices={'002360.SZ': float('nan')},
        )
        n_empty = 12
        value_per_new = avail / n_empty
        # Must be finite and large enough to clear the strategy's `> 1.0` guard
        self.assertTrue(math.isfinite(value_per_new))
        self.assertGreater(value_per_new, 1.0)
        self.assertAlmostEqual(avail, 346_376 + 2000 * 20.0)

    def test_safe_total_value_alias_is_nan_robust(self):
        p = self._portfolio_with('000001.SZ', 1000, avg_cost=10.0, cash=50_000)
        # NaN price for a held position must not poison the total
        tv = p.safe_total_value({'000001.SZ': float('nan')})
        self.assertTrue(math.isfinite(tv))
        # Falls back to avg_cost via market_value()
        self.assertAlmostEqual(tv, 50_000 + 1000 * 10.0)


# ─── F. Documentation-error regression on slippage models ──────────

class SlippageConventionTests(unittest.TestCase):
    """Lock the fact that PctSlippage(0.0003) and FixedSlippage(0.0003) are
    DIFFERENT by roughly an order of magnitude for microcap prices. This
    confusion silently lived in v8-v19 of the P1 G5_A2 mimic and produced
    a 3-bps-vs-0.3-bps slippage mismatch worth ~3pp CAGR over 12 years."""

    def _row(self):
        return pd.Series({'vol': 1000, 'amount': 10_000})

    def test_pct_and_fixed_with_same_param_differ_for_10yuan_stock(self):
        fixed = FixedSlippage(0.0003)
        pct = PctSlippage(0.0003)
        row = self._row()
        # ¥10 stock
        fix_buy = fixed.apply(10.0, 'buy', 0.0, row)
        pct_buy = pct.apply(10.0, 'buy', 0.0, row)
        self.assertAlmostEqual(fix_buy, 10.0003)
        self.assertAlmostEqual(pct_buy, 10.003)   # 10 * (1 + 0.0003)
        # They differ by ~10× for a ¥10 stock
        fix_bps = (fix_buy - 10.0) / 10.0 * 1e4
        pct_bps = (pct_buy - 10.0) / 10.0 * 1e4
        self.assertAlmostEqual(fix_bps, 0.3, places=2)
        self.assertAlmostEqual(pct_bps, 3.0, places=2)

    def test_named_constants_resolve_to_expected_models(self):
        self.assertIsInstance(JOINQUANT_DEFAULT_SLIPPAGE, FixedSlippage)
        self.assertAlmostEqual(JOINQUANT_DEFAULT_SLIPPAGE.spread, 0.0003)
        self.assertIsInstance(CONSERVATIVE_SLIPPAGE_10BPS, PctSlippage)
        self.assertAlmostEqual(CONSERVATIVE_SLIPPAGE_10BPS.rate, 0.001)


# ─── C, D, E. BacktestEngine fill_mode parameter ───────────────────

class FillModeTests(unittest.TestCase):
    """Engine fill-mode dispatch tests. We test:
      - the static raw_avg column synthesizer
      - the BacktestEngine constructor validator
      - the EventDrivenBacktester.run() signature accepts fill_mode
    Without instantiating a full feeder/exchange (which needs real Qlib
    data); the end-to-end behavior is covered by the existing v21 / v22
    integration runs documented in project_state.md."""

    def test_invalid_fill_mode_raises(self):
        from src.backtest_engine.event_driven.engine import BacktestEngine
        # Construct with mocks for required fields — we only care about
        # the fill_mode validation in __init__.
        from unittest.mock import MagicMock
        with self.assertRaises(ValueError) as cm:
            BacktestEngine(
                feeder=MagicMock(), exchange=MagicMock(), strategy=MagicMock(),
                initial_cash=100_000, fill_mode='oops',
            )
        self.assertIn("fill_mode must be one of", str(cm.exception))

    def test_default_fill_mode_is_open_close(self):
        from src.backtest_engine.event_driven.engine import BacktestEngine
        from unittest.mock import MagicMock
        e = BacktestEngine(
            feeder=MagicMock(), exchange=MagicMock(), strategy=MagicMock(),
            initial_cash=100_000,   # no fill_mode → default
        )
        self.assertEqual(e.fill_mode, 'open_close')

    def test_jq_daily_avg_fill_mode_accepted(self):
        from src.backtest_engine.event_driven.engine import BacktestEngine
        from unittest.mock import MagicMock
        e = BacktestEngine(
            feeder=MagicMock(), exchange=MagicMock(), strategy=MagicMock(),
            initial_cash=100_000, fill_mode='jq_daily_avg',
        )
        self.assertEqual(e.fill_mode, 'jq_daily_avg')

    def test_ensure_raw_avg_synthesizes_correctly(self):
        from src.backtest_engine.event_driven.engine import BacktestEngine
        df = pd.DataFrame(
            {'raw_open': [10.0, 20.0, float('nan')],
             'raw_close': [12.0, 22.0, 25.0]},
            index=['A', 'B', 'C'],
        )
        out = BacktestEngine._ensure_raw_avg_column(df.copy())
        self.assertIn('raw_avg', out.columns)
        self.assertAlmostEqual(out.loc['A', 'raw_avg'], 11.0)
        self.assertAlmostEqual(out.loc['B', 'raw_avg'], 21.0)
        # NaN open → NaN avg (engine downstream guards on pd.isna(price))
        self.assertTrue(pd.isna(out.loc['C', 'raw_avg']))

    def test_ensure_raw_avg_is_idempotent(self):
        from src.backtest_engine.event_driven.engine import BacktestEngine
        df = pd.DataFrame(
            {'raw_open': [10.0], 'raw_close': [12.0], 'raw_avg': [99.0]},
            index=['A'],
        )
        out = BacktestEngine._ensure_raw_avg_column(df)
        # When raw_avg is already present, do not overwrite
        self.assertAlmostEqual(out.loc['A', 'raw_avg'], 99.0)

    def test_event_driven_run_accepts_fill_mode_kwarg(self):
        """API contract: EventDrivenBacktester.run() must accept fill_mode.

        PR 3 of the 2026-05-26 freeze plan changed the default from the
        literal 'open_close' to None so that an ExecutionProfile can supply
        the fill_mode when one is passed. When no profile and no explicit
        fill_mode are given, the wrapper falls back to 'open_close' for
        backwards-compatible sandbox behavior — same effective default,
        different signature default.
        """
        import inspect
        from src.backtest_engine.event_driven import EventDrivenBacktester
        sig = inspect.signature(EventDrivenBacktester.run)
        self.assertIn('fill_mode', sig.parameters)
        # PR 3: default is now None (profile-or-fallback semantics).
        self.assertIsNone(sig.parameters['fill_mode'].default)


if __name__ == '__main__':
    unittest.main()
