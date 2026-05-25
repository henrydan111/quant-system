"""
Strategy Base Class and Order Types for Event-Driven Backtester

Provides the abstract Strategy class with JoinQuant-style lifecycle:
    1. initialize(context) — called once before backtest starts
    2. before_market_open(context) — pre-market orders (fill at OPEN)
    3. on_bar(context) — end-of-day orders (fill at CLOSE)
    4. after_market_close(context) — bookkeeping, no orders
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """A trading order to be executed by the engine.

    Attributes:
        code: Tushare ts_code (e.g., '000001.SZ').
        direction: 'buy' or 'sell'.
        target_value: Target investment value in ¥ (for buys).
        target_shares: Number of shares to sell (for sells).
            If None, sell all closeable shares.
        reason: Optional reason string for audit trail.
    """
    code: str
    direction: str  # 'buy' or 'sell'
    target_value: float = 0.0
    target_shares: Optional[int] = None
    reason: str = ''


@dataclass
class BacktestContext:
    """Context object passed to strategy at each step.

    Provides access to market data, portfolio state, and exchange rules.

    Attributes:
        date: Current trading date.
        day_data: Full OHLCV DataFrame for all stocks today.
        day_data_indexed: day_data indexed by ts_code for O(1) lookup.
        prev_day_data: Yesterday's full data.
        portfolio: Portfolio instance.
        exchange: Exchange instance.
        feeder: DailyDataFeeder instance.
        trading_day_index: 0-based count since backtest start.
        total_days: Total number of trading days in the backtest.
        phase: Current phase ('pre_open' or 'on_bar').
    """
    date: pd.Timestamp
    day_data: pd.DataFrame
    day_data_indexed: pd.DataFrame
    prev_day_data: pd.DataFrame
    portfolio: object  # Portfolio
    exchange: object  # Exchange
    feeder: object  # DailyDataFeeder
    trading_day_index: int = 0
    total_days: int = 0
    phase: str = 'pre_open'


class Strategy(ABC):
    """Base class for event-driven strategies.

    Lifecycle per trading day (two phases, no intraday):
        1. before_market_open(context) — sees prev_day_data only
           → returns orders to fill at today's OPEN price
        2. on_bar(context) — sees full today's OHLCV
           → returns orders to fill at today's CLOSE price
        3. after_market_close(context) — EOD bookkeeping, no orders

    Subclasses must implement at least `initialize()` and one of
    `before_market_open()` / `on_bar()`.

    State persistence: use `self.g` (SimpleNamespace) to store
    persistent state across days, like JoinQuant's `g`.
    """

    def __init__(self):
        self.g = SimpleNamespace()

    @abstractmethod
    def initialize(self, context: BacktestContext) -> None:
        """Called once before the backtest starts.

        Use this to set strategy parameters on self.g.

        Args:
            context: BacktestContext with feeder, exchange, portfolio.
        """

    def before_market_open(self, context: BacktestContext) -> list[Order]:
        """Pre-market logic. Can only access prev_day_data.

        Returns orders to fill at today's OPEN price.

        Args:
            context: BacktestContext with phase='pre_open'.

        Returns:
            List of Order objects.
        """
        return []

    def on_bar(self, context: BacktestContext) -> list[Order]:
        """Called with full day's OHLCV data.

        Returns orders to fill at today's CLOSE price.
        Use for: stop-loss (check low < stop_price), EOD rebalance, etc.

        Args:
            context: BacktestContext with phase='on_bar'.

        Returns:
            List of Order objects.
        """
        return []

    def after_market_close(self, context: BacktestContext) -> None:
        """EOD bookkeeping. No orders allowed.

        Update self.g state here.

        Args:
            context: BacktestContext with phase='after_close'.
        """
