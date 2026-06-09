"""Tests for delisting force-close hardening (layer-4 fallback robustness).

Context (verified against real data, 2026-06-09):

  * A suspended-but-listed stock returns a row with NaN OHLCV; a *delisted*
    stock drops out of the PIT 'all' universe entirely. ``_handle_delistings``
    force-closes any held name that vanished from today's data.
  * The pre-delisting collapse (退市整理期 / consecutive limit-downs) is ALREADY
    captured day-by-day in the price path, so the force-close should price at
    the true last traded value — NOT apply a synthetic haircut (that would
    double-count) and NOT fall back to the optimistic ``avg_cost``.

Two soft spots are hardened here:

  1. ``avg_cost`` fallback was optimistic when the last real close was missing.
     Fix: carry forward the last KNOWN real close via ``_last_valid_price``
     (``BacktestEngine._resolve_delist_price``), surviving a suspension gap.
  2. A NaN last-in-universe close (the final bar before delisting was a NaN
     suspension row) propagated ``shares * NaN`` into cash. Fix: a NaN/negative
     guard in ``Portfolio.force_close`` floors to 0.0 (total loss), and the
     resolver never returns NaN.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.backtest_engine.event_driven.engine import BacktestEngine
from src.backtest_engine.event_driven.portfolio import Portfolio, Position


# ─── Helpers ──────────────────────────────────────────────────────────


def _mk_engine(initial_cash: float = 1_000_000.0) -> BacktestEngine:
    """A BacktestEngine with mocked feeder/exchange/strategy (only the
    portfolio + delisting logic under test). __init__ does no feeder I/O."""
    return BacktestEngine(
        feeder=MagicMock(),
        exchange=MagicMock(),
        strategy=MagicMock(),
        initial_cash=initial_cash,
    )


def _seed_position(engine: BacktestEngine, code: str, shares: int,
                   avg_cost: float) -> None:
    engine.portfolio._positions[code] = Position(
        code=code, shares=shares, closeable_amount=shares, avg_cost=avg_cost,
    )


def _day(ts_codes: list[str], closes: list[float] | None = None) -> pd.DataFrame:
    data = {"ts_code": ts_codes}
    if closes is not None:
        data["close"] = closes
    return pd.DataFrame(data)


# ─── Portfolio.force_close guard ──────────────────────────────────────


class TestForceCloseGuard:
    def test_valid_price_credits_proceeds(self):
        pf = Portfolio(initial_cash=100.0)
        pf._positions["A.SZ"] = Position("A.SZ", 1000, 1000, 5.0)
        pf.force_close("A.SZ", price=4.0)
        assert pf.cash == pytest.approx(100.0 + 1000 * 4.0)
        assert "A.SZ" not in pf.positions

    def test_nan_price_floors_to_zero_no_nan_cash(self):
        pf = Portfolio(initial_cash=100.0)
        pf._positions["A.SZ"] = Position("A.SZ", 1000, 1000, 5.0)
        pf.force_close("A.SZ", price=float("nan"))
        # Total loss: no proceeds credited, cash stays finite (not NaN).
        assert pf.cash == pytest.approx(100.0)
        assert not pd.isna(pf.cash)
        assert "A.SZ" not in pf.positions

    def test_negative_price_floors_to_zero(self):
        pf = Portfolio(initial_cash=100.0)
        pf._positions["A.SZ"] = Position("A.SZ", 1000, 1000, 5.0)
        pf.force_close("A.SZ", price=-3.0)
        assert pf.cash == pytest.approx(100.0)
        assert "A.SZ" not in pf.positions

    def test_missing_position_is_noop(self):
        pf = Portfolio(initial_cash=100.0)
        pf.force_close("NOPE.SZ", price=4.0)
        assert pf.cash == pytest.approx(100.0)


# ─── _resolve_delist_price preference ladder ──────────────────────────


class TestResolveDelistPrice:
    def _prev(self, rows: dict[str, float]) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(
            {"ts_code": list(rows), "close": list(rows.values())}
        ).set_index("ts_code")

    def test_prefers_cached_last_real_price(self):
        eng = _mk_engine()
        eng._last_valid_price["A.SZ"] = 7.5
        pos = Position("A.SZ", 1000, 1000, 99.0)  # avg_cost much higher
        # Even with a (stale) prev close present, the cache wins.
        price = eng._resolve_delist_price("A.SZ", pos, self._prev({"A.SZ": 3.0}))
        assert price == pytest.approx(7.5)

    def test_falls_back_to_prev_close_when_no_cache(self):
        eng = _mk_engine()
        pos = Position("A.SZ", 1000, 1000, 99.0)
        price = eng._resolve_delist_price("A.SZ", pos, self._prev({"A.SZ": 3.0}))
        assert price == pytest.approx(3.0)

    def test_skips_nan_cache_and_nan_prev_to_avg_cost(self):
        eng = _mk_engine()
        eng._last_valid_price["A.SZ"] = float("nan")
        pos = Position("A.SZ", 1000, 1000, 12.0)
        price = eng._resolve_delist_price(
            "A.SZ", pos, self._prev({"A.SZ": float("nan")})
        )
        assert price == pytest.approx(12.0)  # avg_cost last resort

    def test_zero_when_nothing_available(self):
        eng = _mk_engine()
        pos = Position("A.SZ", 1000, 1000, 0.0)  # never priced, no cost
        price = eng._resolve_delist_price("A.SZ", pos, pd.DataFrame())
        assert price == 0.0
        assert not pd.isna(price)


# ─── _record_day carry-forward cache population ───────────────────────


class TestCarryForwardCache:
    def test_cache_updates_on_real_and_retains_across_nan(self):
        eng = _mk_engine()
        _seed_position(eng, "A.SZ", 1000, 10.0)
        d = pd.Timestamp("2021-01-04")
        eng._record_day(d, {"A.SZ": 12.0})
        assert eng._last_valid_price["A.SZ"] == pytest.approx(12.0)
        # Suspension day → NaN close must NOT overwrite the last real price.
        eng._record_day(d, {"A.SZ": float("nan")})
        assert eng._last_valid_price["A.SZ"] == pytest.approx(12.0)
        # Absent from prices entirely → still retained.
        eng._record_day(d, {})
        assert eng._last_valid_price["A.SZ"] == pytest.approx(12.0)


# ─── _handle_delistings end-to-end ────────────────────────────────────


class TestHandleDelistings:
    def test_normal_delisting_uses_last_traded_close_no_regression(self):
        # Held name vanishes from today's data; prev day has its real last
        # close (the post-crash bottom). Force-close there — unchanged behavior.
        eng = _mk_engine()
        eng.portfolio._cash = 0.0  # test-only: isolate proceeds
        _seed_position(eng, "DEAD.SZ", 10_000, 6.99)  # bought near the peak
        day_today = _day(["LIVE.SZ"])                  # DEAD gone
        day_prev = _day(["LIVE.SZ", "DEAD.SZ"], [20.0, 0.33])  # last bar 0.33
        eng._handle_delistings(day_today, day_prev, pd.Timestamp("2025-10-14"))
        assert "DEAD.SZ" not in eng.portfolio.positions
        assert eng.portfolio.cash == pytest.approx(10_000 * 0.33)

    def test_suspension_gap_carries_forward_last_real_price(self):
        # Stock traded last at 0.50 (cached while held), then suspended (prev
        # day close is NaN), then delisted today. The OLD code would read the
        # NaN prev close → NaN cash. The hardened path uses the cached 0.50.
        eng = _mk_engine()
        eng.portfolio._cash = 0.0  # test-only: isolate proceeds
        _seed_position(eng, "SUSP.SZ", 10_000, 9.0)
        eng._last_valid_price["SUSP.SZ"] = 0.50  # last real close before halt
        day_today = _day(["LIVE.SZ"])
        day_prev = _day(["LIVE.SZ", "SUSP.SZ"], [20.0, float("nan")])  # halted
        eng._handle_delistings(day_today, day_prev, pd.Timestamp("2025-11-11"))
        assert "SUSP.SZ" not in eng.portfolio.positions
        assert eng.portfolio.cash == pytest.approx(10_000 * 0.50)
        assert not pd.isna(eng.portfolio.cash)

    def test_nan_everywhere_does_not_produce_nan_cash(self):
        # Pathological: no cache, prev close NaN, avg_cost 0. Must floor to 0,
        # never NaN (the guard in force_close + the resolver both backstop).
        eng = _mk_engine()
        eng.portfolio._cash = 0.0  # test-only: isolate proceeds
        _seed_position(eng, "GHOST.SZ", 10_000, 0.0)
        day_today = _day(["LIVE.SZ"])
        day_prev = _day(["LIVE.SZ", "GHOST.SZ"], [20.0, float("nan")])
        eng._handle_delistings(day_today, day_prev, pd.Timestamp("2025-11-11"))
        assert "GHOST.SZ" not in eng.portfolio.positions
        assert eng.portfolio.cash == pytest.approx(0.0)
        assert not pd.isna(eng.portfolio.cash)

    def test_still_held_name_not_force_closed(self):
        # A name still present in today's data (even suspended/NaN row) is in
        # today_codes → must NOT be force-closed (carried, not delisted).
        eng = _mk_engine()
        _seed_position(eng, "HELD.SZ", 10_000, 5.0)
        day_today = _day(["HELD.SZ", "LIVE.SZ"])  # HELD still in universe
        day_prev = _day(["HELD.SZ", "LIVE.SZ"], [5.0, 20.0])
        eng._handle_delistings(day_today, day_prev, pd.Timestamp("2025-06-15"))
        assert "HELD.SZ" in eng.portfolio.positions
        assert eng.portfolio.positions["HELD.SZ"].shares == 10_000
