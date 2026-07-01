"""Regression tests for the opt-in 果仁 不卖条件 涨停不卖 engine fill-step (`hold_on_limit_up`).

GPT R1 P2 (no direct tests). Covers the engine sell-loop branch in
``BacktestEngine._execute_orders`` (engine.py): default-off still sells, opt-in TRUE limit-up retains the
position + cash, a no-limit coverage-hole day does NOT hold (mirrors can_sell's is_true_no_limit_day
rescue), and the daily-AVERAGE fill uses all-day-lock semantics (not is_limit_up on the synthetic avg).
The exchange is mocked so each limit-state combination is exercised in isolation; the portfolio is real.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from src.backtest_engine.event_driven.engine import BacktestEngine
from src.backtest_engine.event_driven.portfolio import Position
from src.backtest_engine.event_driven.strategy import Order

_CODE = "A.SZ"
_DATE = pd.Timestamp("2024-06-03")


def _mk_engine(*, hold_flag: bool, is_limit_up=False, is_all_day_limit_up=False,
               is_true_no_limit_day=False) -> BacktestEngine:
    eng = BacktestEngine(feeder=MagicMock(), exchange=MagicMock(), strategy=MagicMock(),
                         initial_cash=1_000_000.0)
    ex = eng.exchange
    ex.is_limit_up.return_value = is_limit_up
    ex.is_all_day_limit_up.return_value = is_all_day_limit_up
    ex.is_true_no_limit_day.return_value = is_true_no_limit_day
    ex.can_sell.return_value = True
    ex.max_sellable_shares.return_value = 1000
    ex.apply_slippage.side_effect = lambda price, direction, row: price
    ex.compute_sell_cost_breakdown.return_value = MagicMock(total=0.0)
    eng.portfolio._positions[_CODE] = Position(code=_CODE, shares=1000, closeable_amount=1000, avg_cost=8.0)
    if hold_flag:
        eng._hold_on_limit_up = True
    return eng


def _row(fill_col: str, price: float = 10.0) -> pd.DataFrame:
    return pd.DataFrame({fill_col: [price]}, index=[_CODE])


def _sell(eng: BacktestEngine, fill_col: str = "raw_open") -> None:
    eng._execute_orders([Order(code=_CODE, direction="sell", target_shares=1000)],
                        _row(fill_col), _DATE, fill_col)


def test_default_off_sells_limit_up():
    """Flag OFF (default): a limit-up name is sold as before — zero behavior change."""
    eng = _mk_engine(hold_flag=False, is_limit_up=True)
    _sell(eng)
    assert _CODE not in eng.portfolio.positions


def test_hold_on_true_limit_up_retains_position_and_cash():
    """Flag ON + genuine limit-up: the SELL is skipped, position + cash retained (capital not redeployed)."""
    eng = _mk_engine(hold_flag=True, is_limit_up=True, is_true_no_limit_day=False)
    cash0 = eng.portfolio.cash
    _sell(eng)
    assert _CODE in eng.portfolio.positions
    assert eng.portfolio.cash == cash0


def test_no_limit_coverage_hole_does_not_hold():
    """Flag ON but TRUE no-limit day (is_limit_up spuriously True via missing up_limit): must still SELL
    (mirror the can_sell is_true_no_limit_day rescue — no real limit to hold against). GPT R1 P2."""
    eng = _mk_engine(hold_flag=True, is_limit_up=True, is_true_no_limit_day=True)
    _sell(eng)
    assert _CODE not in eng.portfolio.positions


def test_avg_fill_uses_all_day_lock_semantics():
    """Daily-AVERAGE fill: hold only on the 一字 all-day lock, NOT on is_limit_up of the synthetic avg."""
    # all-day-locked -> hold
    held = _mk_engine(hold_flag=True, is_all_day_limit_up=True, is_limit_up=False, is_true_no_limit_day=False)
    _sell(held, fill_col="raw_avg")
    assert _CODE in held.portfolio.positions
    # NOT all-day-locked (is_limit_up True is irrelevant for avg fill) -> sells
    sold = _mk_engine(hold_flag=True, is_all_day_limit_up=False, is_limit_up=True, is_true_no_limit_day=False)
    _sell(sold, fill_col="raw_avg")
    assert _CODE not in sold.portfolio.positions
