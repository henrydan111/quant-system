"""Tests for RankedFallbackStrategy (added 2026-05-20).

The strategy implements JoinQuant's ``filter_limitup`` pattern as a
substitution mechanism: given a ranked candidate list per rebalance date,
walk the list and pick the first ``topk`` that pass the buyability filter
(not suspended today, not locked at limit yesterday). Currently-held names
inside the top-``topk`` range are kept regardless of the filter.

These tests pin the substitution behavior on synthetic data without needing
a full backtest. They cover:

  - All candidates buyable → returns first ``topk``.
  - Top candidates locked at upper limit yesterday → substitutes to next-ranked.
  - Top candidates suspended (via SuspensionLookup) → substitutes.
  - Currently-held names kept regardless of buyability.
  - Empty candidates → empty orders.
  - topk respected even when ranked list is shorter than topk * 2.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.backtest_engine.event_driven.portfolio import Portfolio, Position
from src.backtest_engine.event_driven.strategies import (
    RankedFallbackStrategy,
    _emit_rebalance_orders,
)
from src.backtest_engine.event_driven.strategy import BacktestContext


def _mk_prev_data(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _mk_exchange(
    *,
    limit_up_codes: set[str] | None = None,
    limit_down_codes: set[str] | None = None,
    suspended_codes: set[str] | None = None,
    lot_size: int = 100,
) -> MagicMock:
    """Build a mock Exchange with deterministic tradability flags."""
    limit_up = limit_up_codes or set()
    limit_down = limit_down_codes or set()
    suspended = suspended_codes or set()
    ex = MagicMock()
    ex.is_limit_up.side_effect = lambda row, code, date: code in limit_up
    ex.is_limit_down.side_effect = lambda row, code, date: code in limit_down
    ex.is_suspended.side_effect = lambda row, code=None, date=None: code in suspended
    ex.get_lot_size.return_value = lot_size
    return ex


def _mk_portfolio(holdings: dict[str, tuple[int, float]] | None = None,
                  cash: float = 1_000_000.0) -> MagicMock:
    """Mock Portfolio. holdings = {code: (shares, avg_cost)}."""
    holdings = holdings or {}
    pf = MagicMock()
    positions = {}
    for code, (shares, avg_cost) in holdings.items():
        pos = SimpleNamespace(shares=shares, avg_cost=avg_cost, security=code)
        positions[code] = pos
    pf.positions = positions
    pf.cash = cash
    pf.total_value.side_effect = lambda prices: (
        cash + sum(pos.shares * prices.get(c, pos.avg_cost) for c, pos in positions.items())
    )
    return pf


def _mk_context(
    *,
    date: str,
    prev_rows: list[dict],
    holdings: dict[str, tuple[int, float]] | None = None,
    cash: float = 1_000_000.0,
    limit_up_codes: set[str] | None = None,
    limit_down_codes: set[str] | None = None,
    suspended_codes: set[str] | None = None,
) -> BacktestContext:
    return BacktestContext(
        date=pd.Timestamp(date),
        day_data=pd.DataFrame(),
        day_data_indexed=pd.DataFrame(),
        prev_day_data=_mk_prev_data(prev_rows),
        portfolio=_mk_portfolio(holdings=holdings, cash=cash),
        exchange=_mk_exchange(
            limit_up_codes=limit_up_codes,
            limit_down_codes=limit_down_codes,
            suspended_codes=suspended_codes,
        ),
        feeder=MagicMock(),
        trading_day_index=0,
        total_days=1,
        phase="pre_open",
    )


def _ohlcv(code: str, close: float = 10.0, **kwargs) -> dict:
    base = {
        "ts_code": code,
        "open": close * 0.99,
        "high": close * 1.01,
        "low": close * 0.98,
        "close": close,
        "pre_close": close * 0.99,
        "vol": 1_000_000,
        "trade_date": pd.Timestamp("2021-01-04"),
    }
    base.update(kwargs)
    return base


# ─── Tests ────────────────────────────────────────────────────────────


class TestRankedFallbackStrategyHappyPath:
    def test_all_buyable_picks_first_topk(self):
        candidates = [f"A{i:02d}.SZ" for i in range(10)]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=5,
        )
        ctx = _mk_context(
            date="2021-01-05",
            prev_rows=[_ohlcv(c) for c in candidates],
        )
        orders = strat.before_market_open(ctx)
        buy_codes = sorted(o.code for o in orders if o.direction == "buy")
        # Expect first 5 candidates as buys (sorted alphabetically by emit code)
        assert buy_codes == sorted(candidates[:5]), (
            f"Expected first 5 from rank, got {buy_codes}"
        )

    def test_empty_schedule_emits_no_orders(self):
        strat = RankedFallbackStrategy(ranked_schedule={}, topk=5)
        ctx = _mk_context(date="2021-01-05", prev_rows=[])
        assert strat.before_market_open(ctx) == []

    def test_topk_validation(self):
        with pytest.raises(ValueError, match="topk must be >= 1"):
            RankedFallbackStrategy(ranked_schedule={}, topk=0)


class TestRankedFallbackSubstitution:
    """The core mechanism: skip primaries locked-yesterday, pick next-ranked."""

    def test_top_locked_up_substitutes_to_next(self):
        # Ranked: A,B,C,D,E,F,G  topk=3
        # A and C locked up yesterday → expect target = B,D,E
        candidates = ["A.SZ", "B.SZ", "C.SZ", "D.SZ", "E.SZ", "F.SZ", "G.SZ"]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=3,
        )
        ctx = _mk_context(
            date="2021-01-05",
            prev_rows=[_ohlcv(c) for c in candidates],
            limit_up_codes={"A.SZ", "C.SZ"},
        )
        orders = strat.before_market_open(ctx)
        buy_codes = sorted(o.code for o in orders if o.direction == "buy")
        assert buy_codes == ["B.SZ", "D.SZ", "E.SZ"]

    def test_top_locked_down_substitutes_to_next(self):
        candidates = ["A.SZ", "B.SZ", "C.SZ", "D.SZ"]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=2,
        )
        ctx = _mk_context(
            date="2021-01-05",
            prev_rows=[_ohlcv(c) for c in candidates],
            limit_down_codes={"A.SZ"},
        )
        orders = strat.before_market_open(ctx)
        buy_codes = sorted(o.code for o in orders if o.direction == "buy")
        assert buy_codes == ["B.SZ", "C.SZ"]

    def test_suspended_substitutes_to_next(self):
        candidates = ["A.SZ", "B.SZ", "C.SZ", "D.SZ"]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=2,
        )
        ctx = _mk_context(
            date="2021-01-05",
            prev_rows=[_ohlcv(c) for c in candidates],
            suspended_codes={"B.SZ"},
        )
        orders = strat.before_market_open(ctx)
        buy_codes = sorted(o.code for o in orders if o.direction == "buy")
        assert buy_codes == ["A.SZ", "C.SZ"]

    def test_runs_out_of_candidates_emits_only_available(self):
        # If after substitution we don't have topk, emit what we have, not pad with junk.
        candidates = ["A.SZ", "B.SZ", "C.SZ"]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=10,
        )
        ctx = _mk_context(
            date="2021-01-05",
            prev_rows=[_ohlcv(c) for c in candidates],
            limit_up_codes={"A.SZ"},
        )
        orders = strat.before_market_open(ctx)
        buy_codes = sorted(o.code for o in orders if o.direction == "buy")
        assert buy_codes == ["B.SZ", "C.SZ"]  # 2 picks, both that pass filter


class TestRankedFallbackHeldKept:
    """Currently-held names inside top-K range are kept regardless of buyability."""

    def test_held_in_topk_range_kept_even_if_locked(self):
        # Holding A and C. Ranked top-3 is A, B, C. A is locked-up YESTERDAY.
        # Even though new entries for A would be skipped by the lock predictor,
        # A is already held — strategy should NOT exit A. Top-up buys are fine
        # (that's how the rebalance keeps target weight); the key invariant is
        # that held names in the top-K range are NOT pushed out by lock prediction.
        candidates = ["A.SZ", "B.SZ", "C.SZ", "D.SZ", "E.SZ"]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=3,
        )
        ctx = _mk_context(
            date="2021-01-05",
            prev_rows=[_ohlcv(c) for c in candidates],
            holdings={"A.SZ": (1000, 10.0), "C.SZ": (1000, 10.0)},
            limit_up_codes={"A.SZ"},  # A locked yesterday — but A is held, must be kept
        )
        orders = strat.before_market_open(ctx)
        # Invariant 1: A and C (held + in target) are NOT exited.
        sell_exits = {o.code for o in orders if o.direction == "sell" and o.reason == "rebalance_exit"}
        assert "A.SZ" not in sell_exits, "Held A must not be force-exited by lock predictor"
        assert "C.SZ" not in sell_exits, "Held C must not be exited (in target)"
        # Invariant 2: B (new, buyable) is bought.
        new_buy_codes = {o.code for o in orders if o.direction == "buy"}
        assert "B.SZ" in new_buy_codes, "B must be bought as new top-3 entry"
        # Top-up buys for held A/C are acceptable (rebalance to target weight).
        # D, E should NOT be in target (top-3 is A, B, C).
        assert "D.SZ" not in new_buy_codes
        assert "E.SZ" not in new_buy_codes

    def test_unheld_locked_at_top_unchanged_when_locked_filter_drops_them(self):
        # Tests that lock-prediction drops names properly when held set is empty.
        candidates = ["A.SZ", "B.SZ", "C.SZ"]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=2,
        )
        ctx = _mk_context(
            date="2021-01-05",
            prev_rows=[_ohlcv(c) for c in candidates],
            limit_up_codes={"A.SZ"},
        )
        buy_codes = sorted(o.code for o in strat.before_market_open(ctx)
                          if o.direction == "buy")
        assert buy_codes == ["B.SZ", "C.SZ"]


class TestRankedFallbackSuspensionRegression:
    """Regression for the 2026-05-20 bug where the strategy passed a synthetic
    empty row to is_suspended, hitting the ``vol==0`` fallback and rejecting
    EVERY candidate as suspended. The fix: pass YESTERDAY'S real row so the
    vol-fallback sees the actual prior-day volume.
    """

    def _exchange_with_vol_fallback(self, *, suspended_codes: set[str] | None = None) -> MagicMock:
        """Mock an Exchange whose is_suspended honors the row['vol']==0 fallback
        when authoritative SuspensionLookup is NOT wired — same behavior as
        the real Exchange when ``self._suspension_lookup is None``."""
        suspended = suspended_codes or set()
        ex = MagicMock()

        def fake_is_suspended(row, code=None, date=None):
            if code in suspended:
                return True
            vol = row.get("vol", 0) if hasattr(row, "get") else 0
            if pd.isna(vol) or vol == 0:
                return True
            return False

        ex.is_suspended.side_effect = fake_is_suspended
        ex.is_limit_up.side_effect = lambda row, code, date: False
        ex.is_limit_down.side_effect = lambda row, code, date: False
        ex.get_lot_size.return_value = 100
        return ex

    def test_prev_day_vol_signal_does_not_falsely_suspend_all(self):
        """Verifies the fix: passing a real prev-day row (vol > 0) does NOT
        trigger the vol-fallback. Without the fix, ALL candidates were rejected
        and the portfolio stayed at 100% cash for the entire backtest.
        """
        candidates = ["A.SZ", "B.SZ", "C.SZ"]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=2,
        )
        ctx = BacktestContext(
            date=pd.Timestamp("2021-01-05"),
            day_data=pd.DataFrame(),
            day_data_indexed=pd.DataFrame(),
            prev_day_data=_mk_prev_data([_ohlcv(c) for c in candidates]),
            portfolio=_mk_portfolio(),
            exchange=self._exchange_with_vol_fallback(),
            feeder=MagicMock(),
        )
        orders = strat.before_market_open(ctx)
        buys = sorted(o.code for o in orders if o.direction == "buy")
        assert buys == ["A.SZ", "B.SZ"], (
            f"Expected first 2 to be bought (no suspension), got {buys}. "
            "Regression: synthetic-empty-row bug returned no buys."
        )

    def test_prev_day_zero_vol_is_still_suspended(self):
        """Sanity check: a stock that DID have vol==0 yesterday should still be
        treated as suspended (the fix preserves the vol-fallback for the
        actual no-trading case)."""
        candidates = ["A.SZ", "B.SZ", "C.SZ"]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=2,
        )
        ctx = BacktestContext(
            date=pd.Timestamp("2021-01-05"),
            day_data=pd.DataFrame(),
            day_data_indexed=pd.DataFrame(),
            prev_day_data=_mk_prev_data([
                _ohlcv("A.SZ", vol=0),  # suspended yesterday
                _ohlcv("B.SZ"),
                _ohlcv("C.SZ"),
            ]),
            portfolio=_mk_portfolio(),
            exchange=self._exchange_with_vol_fallback(),
            feeder=MagicMock(),
        )
        orders = strat.before_market_open(ctx)
        buys = sorted(o.code for o in orders if o.direction == "buy")
        assert buys == ["B.SZ", "C.SZ"], (
            f"A.SZ with vol=0 yesterday should be skipped (suspended). Got {buys}"
        )

    def test_unheld_locked_at_top_skipped(self):
        # Holding nothing. Top of rank is locked. Should skip and substitute.
        candidates = ["A.SZ", "B.SZ", "C.SZ"]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=2,
        )
        ctx = _mk_context(
            date="2021-01-05",
            prev_rows=[_ohlcv(c) for c in candidates],
            limit_up_codes={"A.SZ"},
        )
        buy_codes = sorted(o.code for o in strat.before_market_open(ctx)
                          if o.direction == "buy")
        assert buy_codes == ["B.SZ", "C.SZ"]


def _mk_real_portfolio(
    holdings: dict[str, tuple[int, float]] | None = None,
    cash: float = 0.0,
) -> Portfolio:
    """A real Portfolio (not a mock) seeded with `holdings = {code: (shares, avg_cost)}`.

    Used by the NaN-price regression below: the real Portfolio's
    ``market_value`` / ``total_value`` already fall back to ``avg_cost`` for a
    NaN price (portfolio.py), so ``portfolio_value`` stays finite — exactly as
    in production. This isolates the crash to the trim loop's ``int()`` call,
    rather than masking it behind a NaN portfolio value from a naive mock.
    """
    holdings = holdings or {}
    pf = Portfolio(initial_cash=max(cash, 1.0))
    pf._cash = float(cash)  # test-only: set exact cash after construction
    for code, (shares, avg_cost) in holdings.items():
        pf._positions[code] = Position(
            code=code,
            shares=shares,
            closeable_amount=shares,
            avg_cost=avg_cost,
        )
    return pf


class TestRankedFallbackNaNPriceCarry:
    """Regression: a currently-HELD name that is suspended / has no price on the
    rebalance day surfaces a NaN ``ref_price`` (prev-day close is NaN). Before the
    fix, the trim loop computed ``int(max(diff, 0) / NaN / lot) * lot`` →
    ``ValueError: cannot convert float NaN to integer``, crashing the entire
    EventDrivenBacktester run (engine.py → strategies.py:245 → :76).

    The fix skips the trim for any held name with a NaN / non-positive ref_price
    and carries the position to the next rebalance. These tests pin: (1) no
    crash, (2) the suspended held name emits NO sell order (carried), and
    (3) the rest of the rebalance — a normally-priced, over-allocated held name —
    is still trimmed, so the guard is surgical.
    """

    def test_held_suspended_nan_price_does_not_crash_and_is_carried(self):
        # SUSP.SZ: held + target, suspended (prev close NaN) → must be carried.
        # NORM.SZ: held + target, normally priced + over-allocated → still trimmed.
        candidates = ["NORM.SZ", "SUSP.SZ"]
        strat = RankedFallbackStrategy(
            ranked_schedule={pd.Timestamp("2021-01-05"): candidates},
            topk=2,
        )
        ctx = BacktestContext(
            date=pd.Timestamp("2021-01-05"),
            day_data=pd.DataFrame(),
            day_data_indexed=pd.DataFrame(),
            prev_day_data=_mk_prev_data([
                _ohlcv("NORM.SZ", close=20.0),
                _ohlcv("SUSP.SZ", close=float("nan"), vol=0),  # suspended → NaN price
            ]),
            # NORM over-allocated at target 0.5: 10k sh * 20 = 200k vs target 150k.
            portfolio=_mk_real_portfolio(
                holdings={"NORM.SZ": (10_000, 10.0), "SUSP.SZ": (10_000, 10.0)},
                cash=0.0,
            ),
            exchange=_mk_exchange(),
            feeder=MagicMock(),
        )

        # The crux: this used to raise ValueError on the NaN ref_price.
        orders = strat.before_market_open(ctx)

        susp_orders = [o for o in orders if o.code == "SUSP.SZ"]
        assert susp_orders == [], (
            "Suspended held name (NaN price) must emit NO order — carried to next "
            f"rebalance. Got: {susp_orders}"
        )
        # The position itself is untouched by order emission (engine applies fills,
        # not the strategy) — it remains held for the next rebalance.
        assert ctx.portfolio.positions["SUSP.SZ"].shares == 10_000

        # Surgical: the normally-priced, over-allocated held name is still trimmed.
        norm_trims = [
            o for o in orders
            if o.code == "NORM.SZ" and o.direction == "sell" and o.reason == "rebalance_trim"
        ]
        assert len(norm_trims) == 1, (
            f"Over-allocated NORM.SZ should still be trimmed; got {orders}"
        )
        # 200k current vs 150k target → trim ~50k / 20 = 2500 shares (lot 100).
        assert norm_trims[0].target_shares == 2500

    def test_emit_rebalance_orders_skips_nan_ref_price_directly(self):
        # Unit-level pin on the helper that owns the bug.
        ctx = BacktestContext(
            date=pd.Timestamp("2021-01-05"),
            day_data=pd.DataFrame(),
            day_data_indexed=pd.DataFrame(),
            prev_day_data=_mk_prev_data([
                _ohlcv("SUSP.SZ", close=float("nan"), vol=0),
            ]),
            portfolio=_mk_real_portfolio(
                holdings={"SUSP.SZ": (10_000, 10.0)},
                cash=100_000.0,
            ),
            exchange=_mk_exchange(),
            feeder=MagicMock(),
        )
        # SUSP held AND a target → hits the trim loop (the crash site).
        orders = _emit_rebalance_orders({"SUSP.SZ": 0.5}, ctx)
        assert all(o.code != "SUSP.SZ" or o.direction != "sell" for o in orders), (
            f"NaN-priced held name must not be sold/trimmed; got {orders}"
        )
