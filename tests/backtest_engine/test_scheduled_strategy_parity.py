"""ScheduledLongOnlyStrategy parity test for plan ``snappy-buzzing-meerkat`` v5.

The Phase 2.a / 2.b / Part D / Part E perf fixes operate on the cache-manifest
plumbing only — they MUST NOT change what orders the strategy emits for a
given schedule + portfolio state. This test pins the order-generation logic
of ``ScheduledLongOnlyStrategy.before_market_open`` against committed golden
fixtures so any logic drift is caught immediately.

Setup:
* Synthetic 30-day calendar (2021-01-04 .. 2021-02-12, weekdays only).
* 10-stock universe ``S00.SZ .. S09.SZ``.
* 3-day rebalance schedule with the target set rotating each rebalance.
* Day-5 holds ``S03.SZ`` (a stock outside the day-8 target set) at a chunk
  large enough that the rebalance must emit a sell order — confirming held
  positions survive any universe-narrowing optimization.

Output captured per rebalance day:
    {date_str: [{'code', 'direction', 'target_value', 'target_shares',
                 'reason'}, ...]}

If the fixture file is missing at first run, the test self-generates it
(useful when extending the synthetic schedule). Subsequent runs assert
byte-for-byte equality. To force a regeneration after an INTENDED change,
delete the fixture file.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


# Located next to this test file so committed fixtures travel with the test.
FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "scheduled_strategy_orders_golden.json"
)


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic universe + schedule
# ─────────────────────────────────────────────────────────────────────────────

UNIVERSE = [f"S{i:02d}.SZ" for i in range(10)]


def _build_calendar() -> list[pd.Timestamp]:
    """30 weekdays starting 2021-01-04 (Monday)."""
    days = []
    cur = pd.Timestamp("2021-01-04")
    while len(days) < 30:
        if cur.weekday() < 5:  # 0..4 = Mon..Fri
            days.append(cur)
        cur += pd.Timedelta(days=1)
    return days


def _build_schedule(calendar: list[pd.Timestamp]) -> dict[pd.Timestamp, dict[str, float]]:
    """3-day rebalance rotating across 5 different target sets.

    Crucially, set #2 (active on day 8) drops S03 — but day 5's set held
    S03, so day 8 must produce a sell order for it.
    """
    target_sets = [
        ["S00.SZ", "S01.SZ", "S02.SZ", "S03.SZ", "S04.SZ"],  # day 0 (cal[0])
        ["S00.SZ", "S01.SZ", "S02.SZ", "S03.SZ", "S05.SZ"],  # day 3
        ["S00.SZ", "S01.SZ", "S02.SZ", "S04.SZ", "S05.SZ"],  # day 6 — drops S03
        ["S00.SZ", "S01.SZ", "S05.SZ", "S06.SZ", "S07.SZ"],  # day 9 — drops S02, S04
        ["S00.SZ", "S05.SZ", "S06.SZ", "S08.SZ", "S09.SZ"],  # day 12
    ]
    schedule: dict[pd.Timestamp, dict[str, float]] = {}
    for i, ts in enumerate(target_sets):
        date = calendar[i * 3]
        schedule[date] = {code: 1.0 / len(ts) for code in ts}
    return schedule


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic prev-day price + portfolio state evolution
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _FakePosition:
    code: str
    shares: int = 0
    closeable_amount: int = 0
    avg_cost: float = 0.0


@dataclass
class _FakePortfolio:
    cash: float = 1_000_000.0
    positions: dict[str, _FakePosition] = field(default_factory=dict)

    def total_value(self, prices: dict[str, float]) -> float:
        equity = self.cash
        for code, pos in self.positions.items():
            equity += pos.shares * float(prices.get(code, pos.avg_cost))
        return equity


class _FakeExchange:
    def get_lot_size(self, _code: str) -> int:  # noqa: D401
        return 100  # SZ main board


def _prev_day_prices(date: pd.Timestamp) -> pd.DataFrame:
    """Deterministic synthetic close prices per stock per day.

    Price = 10 + (day_index % 7) + (stock_index * 0.5) → varies daily and
    cross-sectionally without touching real market data.
    """
    base_day = pd.Timestamp("2021-01-04")
    day_index = (date - base_day).days
    rows = []
    for i, code in enumerate(UNIVERSE):
        rows.append({"ts_code": code, "close": 10.0 + (day_index % 7) + i * 0.5})
    return pd.DataFrame(rows)


def _build_context(
    *, date: pd.Timestamp, portfolio: _FakePortfolio
) -> SimpleNamespace:
    return SimpleNamespace(
        date=date,
        portfolio=portfolio,
        exchange=_FakeExchange(),
        prev_day_data=_prev_day_prices(date),
    )


def _seed_day5_holding(portfolio: _FakePortfolio) -> None:
    """Simulate that day-5 rebalance left a 5000-share holding in S03.SZ
    so the day-8 rebalance (which drops S03) MUST emit a sell order.
    """
    portfolio.positions["S03.SZ"] = _FakePosition(
        code="S03.SZ",
        shares=5000,
        closeable_amount=5000,
        avg_cost=12.0,
    )
    # Drain enough cash to make the simulation realistic.
    portfolio.cash -= 5000 * 12.0


# ─────────────────────────────────────────────────────────────────────────────
# Order capture
# ─────────────────────────────────────────────────────────────────────────────

def _orders_to_dicts(orders) -> list[dict]:
    """Round numeric fields to keep JSON byte-stability across runs."""
    out = []
    for o in orders:
        out.append({
            "code": o.code,
            "direction": o.direction,
            "target_value": round(float(o.target_value), 4) if o.target_value else 0.0,
            "target_shares": int(o.target_shares) if o.target_shares else 0,
            "reason": o.reason,
        })
    return out


def _generate_order_log() -> dict[str, list[dict]]:
    from workspace.research.alpha_mining.event_driven_strategy_research import (
        ScheduledLongOnlyStrategy,
    )

    calendar = _build_calendar()
    schedule = _build_schedule(calendar)
    strategy = ScheduledLongOnlyStrategy(schedule)
    portfolio = _FakePortfolio()

    # Pre-rebalance #2 (cal[6] / day index 6), seed the day-5 holding so the
    # rotation has a real "held but no longer in target" row to handle.
    _seed_day5_holding(portfolio)

    log: dict[str, list[dict]] = {}
    for date in sorted(schedule.keys()):
        ctx = _build_context(date=date, portfolio=portfolio)
        orders = strategy.before_market_open(ctx)
        log[date.strftime("%Y-%m-%d")] = _orders_to_dicts(orders)
    return log


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_scheduled_strategy_orders_match_golden_fixture():
    """Byte-for-byte parity check against committed golden fixtures.

    First run (fixture missing) self-generates the fixture and skips the
    assertion. After committing the fixture, all subsequent runs assert
    byte-for-byte equality.
    """
    actual = _generate_order_log()

    if not FIXTURE_PATH.exists():
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(
            json.dumps(actual, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        pytest.skip(
            f"Generated fresh golden fixture at {FIXTURE_PATH}. "
            "Inspect, commit, and re-run."
        )

    expected_text = FIXTURE_PATH.read_text(encoding="utf-8")
    actual_text = json.dumps(actual, indent=2, sort_keys=True) + "\n"

    if expected_text != actual_text:
        # Surface a useful diff in pytest output.
        import difflib
        diff = "\n".join(
            difflib.unified_diff(
                expected_text.splitlines(),
                actual_text.splitlines(),
                fromfile="golden",
                tofile="actual",
                lineterm="",
            )
        )
        pytest.fail(
            "ScheduledLongOnlyStrategy order-log diverged from golden fixture. "
            f"If the change is intentional, delete {FIXTURE_PATH} and re-run.\n\n"
            f"{diff}"
        )


def test_day8_rebalance_emits_sell_for_dropped_holding():
    """Targeted assertion: the day-5 → day-8 rotation drops S03.SZ from the
    target set; the held 5000 shares must trigger a 'rebalance_exit' sell.
    """
    log = _generate_order_log()

    calendar = _build_calendar()
    day8 = calendar[6].strftime("%Y-%m-%d")  # rebalance #2
    orders = log[day8]
    sells_for_s03 = [
        o for o in orders
        if o["code"] == "S03.SZ" and o["direction"] == "sell"
    ]
    assert sells_for_s03, (
        f"Expected day-8 rebalance to emit a sell for S03.SZ (the held but "
        f"no-longer-target stock), got: {orders}"
    )
    assert sells_for_s03[0]["reason"] == "rebalance_exit"


def test_first_rebalance_emits_only_buys():
    """Sanity: with an empty initial portfolio, the first rebalance has no
    holdings to trim or exit — every order should be a buy.
    """
    from workspace.research.alpha_mining.event_driven_strategy_research import (
        ScheduledLongOnlyStrategy,
    )

    calendar = _build_calendar()
    schedule = _build_schedule(calendar)
    strategy = ScheduledLongOnlyStrategy(schedule)
    portfolio = _FakePortfolio()  # empty positions
    ctx = _build_context(date=calendar[0], portfolio=portfolio)

    orders = strategy.before_market_open(ctx)
    assert orders, "First rebalance should emit at least one order"
    assert all(o.direction == "buy" for o in orders), (
        f"Expected only buys on first rebalance, got: {[o.direction for o in orders]}"
    )
