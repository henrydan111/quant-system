"""Regression for the price-return vs total-return invariant (CLAUDE.md §3.3).

`EventDrivenBacktester` reports a TOTAL return because `CorporateActionHandler`
credits post-tax cash dividends and bonus shares on the ex-date. If that
crediting silently breaks, the event-driven engine quietly degrades into the
same PRICE return `VectorizedBacktester` reports (raw close-to-close, no
distribution credited). The phase6d isolation proved this empirically:
no-op'ing `CorporateActionHandler.process` collapsed the long_only value book
from +11.64% to +6.59% CAGR ≈ vectorized +6.17% (dividends+bonus = +5.05%).

These tests pin the crediting so that degradation fails loudly instead of
silently turning a total-return run into a price-return one.
"""

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest_engine.event_driven.corporate_actions import CorporateActionHandler

EX_DATE = "20210610"          # ex-date string the handler keys on (YYYYMMDD)
EX_TS = pd.Timestamp("2021-06-10")
DAY_BEFORE = pd.Timestamp("2021-06-09")
CODE = "600000.SH"


class _FakePosition:
    """Minimal stand-in exposing only what CorporateActionHandler mutates."""

    def __init__(self, shares: int, avg_cost: float):
        self.shares = shares
        self.closeable_amount = shares
        self.avg_cost = avg_cost


class _FakePortfolio:
    """Records cash credits and serves positions by code."""

    def __init__(self, positions: dict):
        self._positions = positions
        self.cash_credited = 0.0

    def get_position(self, code):
        return self._positions.get(code)

    def credit_cash(self, amount: float) -> None:
        self.cash_credited += amount


def _div_row(**overrides) -> dict:
    row = {
        "ts_code": CODE,
        "div_proc": "实施",          # only 实施 (implemented) rows are actionable
        "ex_date": EX_DATE,
        "cash_div": 0.0,
        "cash_div_tax": 0.0,
        "stk_div": 0.0,
        "stk_bo_rate": 0.0,
        "stk_co_rate": 0.0,
    }
    row.update(overrides)
    return row


class CorporateActionTotalReturnTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dividends_dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _handler(self, rows) -> CorporateActionHandler:
        pd.DataFrame(rows).to_parquet(Path(self.dividends_dir) / "dividends_2021.parquet")
        return CorporateActionHandler(self.dividends_dir)

    def test_cash_dividend_credited_is_the_total_return_component(self):
        # 0.50 post-tax dividend/share on 1,000 shares -> 500 cash credited.
        handler = self._handler([_div_row(cash_div=0.60, cash_div_tax=0.50)])
        pf = _FakePortfolio({CODE: _FakePosition(shares=1000, avg_cost=10.0)})
        handler.process(EX_TS, pf)
        # This non-zero credit IS the difference between total and price return.
        self.assertAlmostEqual(pf.cash_credited, 0.50 * 1000, places=6)

    def test_total_return_exceeds_price_return_by_exactly_the_dividend(self):
        # The §3.3 invariant in miniature: for the SAME post-ex-date price, the
        # account that credits the dividend (event-driven, total return) ends the
        # day worth exactly `dividend_cash` more than one that does not
        # (vectorized close-to-close, price return).
        handler = self._handler([_div_row(cash_div=0.60, cash_div_tax=0.50)])
        shares, post_ex_price = 1000, 9.5
        pf = _FakePortfolio({CODE: _FakePosition(shares=shares, avg_cost=10.0)})
        handler.process(EX_TS, pf)
        price_return_nav = shares * post_ex_price
        total_return_nav = shares * post_ex_price + pf.cash_credited
        self.assertAlmostEqual(total_return_nav - price_return_nav, 0.50 * shares, places=6)

    def test_bonus_shares_added_on_ex_date(self):
        # 10送5 -> stk_div 0.50 -> +500 shares; avg_cost /= 1.50.
        handler = self._handler([_div_row(stk_div=0.50, stk_bo_rate=0.50)])
        pos = _FakePosition(shares=1000, avg_cost=15.0)
        pf = _FakePortfolio({CODE: pos})
        handler.process(EX_TS, pf)
        self.assertEqual(pos.shares, 1500)
        self.assertEqual(pos.closeable_amount, 1500)
        self.assertAlmostEqual(pos.avg_cost, 15.0 / 1.50, places=6)
        self.assertAlmostEqual(pf.cash_credited, 0.0, places=6)

    def test_no_credit_off_ex_date(self):
        # Away from the ex-date nothing is credited -> a vectorized close-to-close
        # run between non-ex dates correctly sees price movement only.
        handler = self._handler([_div_row(cash_div=0.60, cash_div_tax=0.50)])
        pf = _FakePortfolio({CODE: _FakePosition(shares=1000, avg_cost=10.0)})
        handler.process(DAY_BEFORE, pf)
        self.assertAlmostEqual(pf.cash_credited, 0.0, places=6)

    def test_not_held_is_skipped(self):
        handler = self._handler([_div_row(cash_div=0.60, cash_div_tax=0.50)])
        pf = _FakePortfolio({"000001.SZ": _FakePosition(shares=1000, avg_cost=10.0)})
        handler.process(EX_TS, pf)
        self.assertAlmostEqual(pf.cash_credited, 0.0, places=6)

    def test_unimplemented_dividend_not_actioned(self):
        # 预案 (proposed) rows must NOT credit — only 实施 (implemented) do.
        handler = self._handler([_div_row(div_proc="预案", cash_div=0.60, cash_div_tax=0.50)])
        pf = _FakePortfolio({CODE: _FakePosition(shares=1000, avg_cost=10.0)})
        handler.process(EX_TS, pf)
        self.assertAlmostEqual(pf.cash_credited, 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
