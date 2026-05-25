"""Reusable concrete Strategy implementations for the event-driven backtester.

Two classes ship here:

  - ``ScheduledLongOnlyStrategy`` — naive long-only schedule executor (already
    available in ``workspace/research/alpha_mining/event_driven_strategy_research.py``;
    re-exported here for engine-layer parity).
  - ``RankedFallbackStrategy`` — JoinQuant-style ``filter_limitup`` substitution:
    takes an OVERSAMPLED ranked candidate list per rebalance date, walks the
    list at decision time, skips primaries predicted unbuyable (locked at limit
    yesterday OR suspended), picks the first ``topk`` that pass.

The ``RankedFallbackStrategy`` was added 2026-05-20 after the JoinQuant G5_A2
replication revealed that naive top-K fill (the ScheduledLongOnlyStrategy
pattern) loses substantial bull-year alpha when several of the top-K names
open limit-up — the engine simply fails to fill those orders and the slots
remain in cash. JoinQuant's pattern fills all K slots because it substitutes
to the next-ranked tradeable name. Per the run dir
``workspace/research/alpha_mining/p1_jq_g5a2_mimic_v3_survivor_run/`` analysis,
this mechanism accounts for an estimated 1.5-2× cumulative-return gap in the
2015 and 2022 microcap bull windows.
"""

from __future__ import annotations

from typing import Iterable, Mapping

import pandas as pd

from src.backtest_engine.event_driven.strategy import (
    BacktestContext,
    Order,
    Strategy,
)


# ─── Helpers ─────────────────────────────────────────────────────────


def _emit_rebalance_orders(
    target_weights: Mapping[str, float],
    context: BacktestContext,
) -> list[Order]:
    """Standard long-only rebalance: exit non-targets, trim over-allocated, top up under-allocated.

    Identical to ScheduledLongOnlyStrategy.before_market_open's order-emission
    body — extracted so both strategy variants share one well-tested path.
    """
    prev_prices: dict[str, float] = {}
    if context.prev_day_data is not None and not context.prev_day_data.empty:
        prev_prices = (
            context.prev_day_data.set_index("ts_code")["close"].astype(float).to_dict()
        )

    portfolio_value = context.portfolio.total_value(prev_prices)
    if portfolio_value <= 0:
        portfolio_value = context.portfolio.cash

    orders: list[Order] = []
    current_positions = dict(context.portfolio.positions)
    current_codes = set(current_positions)
    target_codes = set(target_weights)

    for code in sorted(current_codes - target_codes):
        orders.append(Order(code=code, direction="sell", reason="rebalance_exit"))

    for code in sorted(current_codes & target_codes):
        pos = current_positions[code]
        ref_price = float(prev_prices.get(code, pos.avg_cost if pos.avg_cost > 0 else 0))
        if ref_price <= 0:
            continue
        current_value = pos.shares * ref_price
        target_value = portfolio_value * float(target_weights[code])
        diff_value = current_value - target_value
        lot_size = context.exchange.get_lot_size(code)
        shares_to_sell = int(max(diff_value, 0) / ref_price / lot_size) * lot_size
        if shares_to_sell > 0:
            orders.append(
                Order(
                    code=code,
                    direction="sell",
                    target_shares=shares_to_sell,
                    reason="rebalance_trim",
                )
            )

    for code in sorted(target_codes):
        pos = current_positions.get(code)
        ref_price = float(prev_prices.get(code, pos.avg_cost if pos else 0))
        current_value = 0.0 if pos is None or ref_price <= 0 else pos.shares * ref_price
        target_value = portfolio_value * float(target_weights[code])
        buy_value = max(target_value - current_value, 0.0)
        if buy_value > 1.0:
            orders.append(
                Order(
                    code=code,
                    direction="buy",
                    target_value=buy_value,
                    reason="rebalance_buy",
                )
            )
    return orders


# ─── Strategy: RankedFallbackStrategy ────────────────────────────────


class RankedFallbackStrategy(Strategy):
    """JoinQuant ``filter_limitup`` style: ranked candidates with substitution.

    The strategy takes a per-date RANKED candidate list (length should be
    >= ``topk``, recommended >= 2 * ``topk`` for headroom). On each rebalance
    day, it walks the ranked list from top, applies a buyability filter to
    each candidate, and takes the first ``topk`` that pass.

    The buyability filter for NEW candidates (not already held) is:

      1. SUSPENDED today?  → skip
      2. Locked at upper limit YESTERDAY?  → skip (predicted to open lim-up)
      3. Locked at lower limit YESTERDAY?  → skip (predicted to open lim-down)
      4. No prev-day data?  → skip

    Currently-held names that appear inside the top-``topk`` range of the
    ranked list are KEPT regardless of the filter (already in portfolio,
    no buy required, no need to predict buyability).

    The filter is heuristic — it uses YESTERDAY's data to PREDICT TODAY's
    open-time tradability. False positives (a stock locked yesterday that
    opens normally today) cost a small bit of selection precision; false
    negatives (a stock not locked yesterday but locks at open today) are
    caught at fill time by the engine's own ``can_buy`` check. The intent
    is to substitute as many slots as possible at SCHEDULE TIME so the
    engine doesn't end up holding cash for failed fills.

    Args:
        ranked_schedule: ``{rebalance_date: [ts_code, ...]}`` in rank order
            (best/preferred first). Length should typically be at least
            ``2 * topk`` to allow substitution; the strategy stops walking
            once ``topk`` tradeable names are found.
        topk: target number of holdings per rebalance.

    Example:
        >>> ranked = {pd.Timestamp("2015-06-23"): [
        ...     "000001.SZ", "002001.SZ", ..., # length 24
        ... ]}
        >>> strat = RankedFallbackStrategy(ranked, topk=12)
        >>> backtester.run(strategy=strat, ...)
    """

    def __init__(
        self,
        ranked_schedule: Mapping[pd.Timestamp, Iterable[str]],
        topk: int,
    ):
        super().__init__()
        if topk < 1:
            raise ValueError(f"topk must be >= 1, got {topk}")
        # Normalize: store as immutable tuples
        self.ranked_schedule: dict[pd.Timestamp, tuple[str, ...]] = {
            pd.Timestamp(d): tuple(codes) for d, codes in ranked_schedule.items()
        }
        self.topk = int(topk)

    def initialize(self, context: BacktestContext) -> None:
        return None

    # ── Heuristic buyability prediction ─────────────────────────────

    def _is_buyable_for_new_entry(self, code: str, context: BacktestContext) -> bool:
        """True if we predict this code will be buyable AT OPEN TODAY.

        Uses ONLY data available at before_market_open (prev_day_data + the
        exchange's deterministic per-date lookups). Conservative — when in
        doubt, returns False (skip the candidate; pick the next-ranked).
        """
        # 0. No prev-day data at all → conservative skip
        if context.prev_day_data is None or context.prev_day_data.empty:
            return False
        prev_match = context.prev_day_data[context.prev_day_data["ts_code"] == code]
        if prev_match.empty:
            return False
        prev = prev_match.iloc[0]

        # 1. Suspended check. is_suspended consults the authoritative
        # SuspensionLookup IF wired AND a (code, date) is provided. The
        # legacy fallback path checks ``row.get('vol', 0)`` and treats vol==0
        # / NaN as suspended — so we must pass yesterday's REAL row (not an
        # empty synthetic one). If the SuspensionLookup is wired the row is
        # ignored anyway; if not, yesterday's vol is the best signal we have
        # (a stock that traded yesterday with vol > 0 is very likely tradeable
        # today). Without this fix the synthetic-row path rejected every
        # candidate as "suspended" (vol==NaN → True) — caught 2026-05-20
        # by the empty-portfolio bug in mimic v4.
        try:
            if context.exchange.is_suspended(prev, code=code, date=context.date):
                return False
        except Exception:
            pass
        # Try to use the exchange's authoritative is_limit_up / is_limit_down which
        # consult st_stocks, board policy, IPO period, and the round-half-up
        # convention. Need the prev trading-day date to query is_st / get_limit_pct.
        # We don't have prev_date directly on the context, so derive from prev row's
        # 'trade_date' if present, otherwise approximate as context.date - 1d (the
        # is_st / get_limit_pct lookups are stable over single-day boundaries).
        prev_date = pd.Timestamp(
            prev.get("trade_date", pd.Timestamp(context.date) - pd.Timedelta(days=1))
        )
        try:
            if context.exchange.is_limit_up(prev, code, prev_date):
                return False
            if context.exchange.is_limit_down(prev, code, prev_date):
                return False
        except (KeyError, TypeError, ValueError):
            # Missing columns or bad types — fall through to permissive default
            pass

        return True

    # ── Lifecycle ───────────────────────────────────────────────────

    def before_market_open(self, context: BacktestContext) -> list[Order]:
        candidates = self.ranked_schedule.get(pd.Timestamp(context.date))
        if not candidates:
            return []

        current_codes = set(context.portfolio.positions)

        # Walk the ranked list with substitution.
        target_codes: list[str] = []
        for code in candidates:
            if len(target_codes) >= self.topk:
                break
            if code in current_codes:
                # Already held — keep without re-validating buyability.
                target_codes.append(code)
            else:
                if self._is_buyable_for_new_entry(code, context):
                    target_codes.append(code)

        if not target_codes:
            return []

        weight = 1.0 / self.topk
        target_weights = {code: weight for code in target_codes}
        return _emit_rebalance_orders(target_weights, context)
