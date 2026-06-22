"""Regression (GPT cross-review Blocker-1, 2026-06-22): the pre-open
BacktestContext must WITHHOLD same-day OHLCV from strategy code.

The Strategy contract says before_market_open "Can only access prev_day_data"
(strategy.py docstring), but the engine previously passed the full same-day
day_data/day_data_indexed into the pre_open context — a latent no-lookahead
violation (a strategy reading context.day_data there would see today's
close/high/low). The fix withholds them (empty frames) at pre_open and restores
them for on_bar (EOD, knowable at close). Real-data integration test.
"""
from __future__ import annotations

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
sys.path.insert(0, PROJECT_ROOT)

from src.backtest_engine.event_driven import EventDrivenBacktester  # noqa: E402
from src.backtest_engine.event_driven.strategy import Strategy  # noqa: E402
from src.backtest_engine.event_driven.pre_open_guard import PreOpenLookaheadError  # noqa: E402


class _SpyPreOpen(Strategy):
    def initialize(self, context):
        self.g.pre_open_empty = []
        self.g.on_bar_nonempty = []

    def before_market_open(self, context):
        self.g.pre_open_empty.append(
            bool(context.day_data.empty) and bool(context.day_data_indexed.empty)
        )
        return []

    def on_bar(self, context):
        self.g.on_bar_nonempty.append(not context.day_data.empty)
        return []


class _LeakyFeeder(Strategy):
    """Tries the feeder + exchange same-day side channels pre-open (GPT R2 B1)."""

    def initialize(self, context):
        self.g.blocked = []
        self.g.legit_ok = []

    def before_market_open(self, context):
        def _blocked(fn):
            try:
                fn()
                return False  # NOT raised = the side channel leaked
            except PreOpenLookaheadError:
                return True

        f, x = context.feeder, context.exchange
        probes = [
            lambda: f.get_features(["000001_SZ"], ["$close"],          # direct same-day read
                                   start_time=context.date, end_time=context.date),
            lambda: f._inner,        # the wrapper's stored raw feeder (GPT R3 exploit)
            lambda: f.__dict__,      # introspection escape
            lambda: x._feeder,       # raw feeder via the exchange
            lambda: x._inner,        # the wrapper's stored raw exchange (GPT R3 exploit)
            lambda: x.__dict__,
        ]
        self.g.blocked.append(all(_blocked(p) for p in probes))
        # a LEGIT public tradability method must still work through the view
        self.g.legit_ok.append(x.get_lot_size("000001.SZ") == 100)
        return []


class TestPreOpenContextIsolation(unittest.TestCase):
    def test_pre_open_withholds_same_day_ohlcv(self):
        strat = _SpyPreOpen()
        EventDrivenBacktester(data_dir=DATA_DIR).run(
            strategy=strat, start_time="2024-01-02", end_time="2024-01-10",
            benchmark="000852.SH", account=100_000,
        )
        self.assertTrue(strat.g.pre_open_empty, "before_market_open never ran")
        self.assertTrue(
            all(strat.g.pre_open_empty),
            "before_market_open LEAKED same-day OHLCV (no-lookahead violation)",
        )
        self.assertTrue(
            any(strat.g.on_bar_nonempty),
            "on_bar should see the full same-day OHLCV",
        )

    def test_pre_open_blocks_feeder_and_exchange_side_channels(self):
        strat = _LeakyFeeder()
        EventDrivenBacktester(data_dir=DATA_DIR).run(
            strategy=strat, start_time="2024-01-02", end_time="2024-01-10",
            benchmark="000852.SH", account=100_000,
        )
        self.assertTrue(strat.g.blocked, "before_market_open never ran")
        self.assertTrue(all(strat.g.blocked),
                        "a pre-open same-day side channel leaked — feeder/exchange "
                        "get_features / _inner / _feeder / __dict__ must ALL be blocked")
        self.assertTrue(all(strat.g.legit_ok),
                        "a legit public exchange method (get_lot_size) must still work pre-open")


class _FakeFeeder:
    def get_features(self, instruments, fields, start_time, end_time, *a, **k):
        return "DATA"

    def get_day(self):
        return "DAY"


class _FakeExchange:
    def __init__(self):
        self._feeder = _FakeFeeder()

    def get_lot_size(self, code):
        return 100

    def is_suspended(self, *a, **k):
        return False


class TestPreOpenGuardUnit(unittest.TestCase):
    """Fast unit tests for the wrapper side-channel blocks (no engine / no real data)."""

    @staticmethod
    def _blocked(fn):
        try:
            fn()
            return False
        except PreOpenLookaheadError:
            return True

    def test_phase_bound_feeder_blocks_inner_and_bounds_reads(self):
        import pandas as pd
        from src.backtest_engine.event_driven.pre_open_guard import PhaseBoundFeeder
        f = PhaseBoundFeeder(_FakeFeeder(), pd.Timestamp("2024-01-05"))
        self.assertTrue(self._blocked(lambda: f._inner))       # GPT R3 _inner escape
        self.assertTrue(self._blocked(lambda: f.__dict__))
        self.assertTrue(self._blocked(lambda: f.get_day()))    # non-get_features access
        self.assertTrue(self._blocked(                          # future read
            lambda: f.get_features([], [], "2024-01-01", "2024-01-06")))
        self.assertEqual(                                       # end_time <= max -> ok
            f.get_features([], [], "2024-01-01", "2024-01-05"), "DATA")

    def test_strategy_exchange_view_blocks_inner_forwards_public(self):
        from src.backtest_engine.event_driven.pre_open_guard import StrategyExchangeView
        x = StrategyExchangeView(_FakeExchange())
        self.assertTrue(self._blocked(lambda: x._feeder))
        self.assertTrue(self._blocked(lambda: x._inner))       # GPT R3 _inner escape
        self.assertTrue(self._blocked(lambda: x.__dict__))
        self.assertEqual(x.get_lot_size("X"), 100)             # legit public method forwarded
        self.assertFalse(x.is_suspended())


if __name__ == "__main__":
    unittest.main()
