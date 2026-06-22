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


if __name__ == "__main__":
    unittest.main()
