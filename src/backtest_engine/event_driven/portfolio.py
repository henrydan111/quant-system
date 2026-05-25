"""
Portfolio and Position Management for Event-Driven Backtester

Tracks cash, positions with T+1 share-level locking, and daily cost/turnover.
Handles lot-size rounding, commission minimums, and forced position closures.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Single stock position with T+1 share-level tracking.

    T+1 Rule: Newly bought shares cannot be sold until the next trading day.
    This is enforced via `closeable_amount` — only shares from prior days
    are closeable. At start_new_day(), all shares become closeable.

    Attributes:
        code: Tushare ts_code (e.g., '000001.SZ').
        shares: Total shares held.
        closeable_amount: Shares that can be sold today.
        avg_cost: Volume-weighted average entry price.
        latest_entry_date: Date of the most recent purchase.
    """
    code: str
    shares: int = 0
    closeable_amount: int = 0
    avg_cost: float = 0.0
    latest_entry_date: Optional[pd.Timestamp] = None

    def start_new_day(self) -> None:
        """Called at start of each trading day — all shares become closeable."""
        self.closeable_amount = self.shares

    def add_shares(self, new_shares: int, price: float,
                   date: pd.Timestamp) -> None:
        """Buy more shares. New shares are NOT closeable today.

        Args:
            new_shares: Number of shares to add.
            price: Fill price per share.
            date: Trade date.
        """
        if new_shares <= 0:
            return
        total_cost = self.avg_cost * self.shares + price * new_shares
        self.shares += new_shares
        self.avg_cost = total_cost / self.shares
        # closeable_amount stays unchanged — new shares locked until tomorrow
        self.latest_entry_date = date

    def remove_shares(self, sell_shares: int) -> None:
        """Sell shares. Decrements both shares and closeable_amount.

        Args:
            sell_shares: Number of shares to remove.

        Raises:
            ValueError: If trying to sell more than closeable.
        """
        if sell_shares > self.closeable_amount:
            raise ValueError(
                f'Cannot sell {sell_shares} shares of {self.code}: '
                f'only {self.closeable_amount} closeable '
                f'(total: {self.shares})'
            )
        self.shares -= sell_shares
        self.closeable_amount -= sell_shares

    @property
    def is_empty(self) -> bool:
        """True if no shares are held."""
        return self.shares <= 0


class Portfolio:
    """Tracks cash, positions, and daily equity.

    Enforces:
    - T+1: cannot sell shares bought today (tracked per-share via closeable_amount)
    - Lot sizes: rounds to 100 or 200 shares
    - Min commission: ¥5 per trade
    - Partial fills: if cash insufficient for full lot, buy fewer lots

    Args:
        initial_cash: Starting cash balance in ¥.
    """

    def __init__(self, initial_cash: float):
        if initial_cash <= 0:
            raise ValueError(f'initial_cash must be positive, got {initial_cash}')
        self._cash = float(initial_cash)
        self._positions: dict[str, Position] = {}
        self._today_costs = 0.0
        self._today_turnover = 0.0

    @property
    def cash(self) -> float:
        """Current cash balance."""
        return self._cash

    @property
    def positions(self) -> dict[str, Position]:
        """All current positions (code -> Position)."""
        return self._positions

    def start_new_day(self) -> None:
        """Call at start of each trading day.

        Makes all shares closeable (T+1 unlock).
        Resets daily cost and turnover counters.
        """
        for pos in self._positions.values():
            pos.start_new_day()
        self._today_costs = 0.0
        self._today_turnover = 0.0

    def buy(self, code: str, price: float, target_value: float,
            date: pd.Timestamp, lot_size: int,
            commission: float = None, min_commission: float = 5.0,
            total_cost: float = None) -> float:
        """Buy shares of a stock.

        Rounds down to nearest lot size. Deducts cost from cash.

        Cost source: when ``total_cost`` is provided (the preferred path
        via ``Exchange.compute_buy_cost_breakdown()``), it is used as the
        pre-computed cost for cash deduction. When ``total_cost`` is None
        (backward-compatible path for direct callers), cost is computed
        from ``commission`` and ``min_commission`` rates.

        Args:
            code: Stock ts_code.
            price: Fill price per share (after slippage).
            target_value: Target investment value in ¥.
            date: Trade date.
            lot_size: Lot size (100 for main/ChiNext, 200 for BSE).
            commission: Commission rate (e.g., 0.00025). Used only when
                total_cost is None.
            min_commission: Minimum commission in ¥. Used only when
                total_cost is None.
            total_cost: Pre-computed total cost from Exchange breakdown.
                When provided, ``commission`` and ``min_commission`` are
                ignored.

        Returns:
            Actual invested value (price * shares), or 0 if trade skipped.
        """
        import math
        if price <= 0 or not math.isfinite(price):
            return 0.0
        if target_value <= 0 or not math.isfinite(target_value):
            return 0.0

        # Default commission for backward-compatible callers
        if commission is None:
            commission = 0.00025

        # Round down to nearest lot size
        max_lots = int(target_value / (price * lot_size))
        if max_lots <= 0:
            return 0.0
        shares = max_lots * lot_size
        trade_value = shares * price

        # Calculate cost: use pre-computed total if available, else legacy path
        if total_cost is not None:
            # Scale total_cost proportionally if trade_value < target_value
            # (because lot rounding can reduce the actual trade below target)
            cost = total_cost * (trade_value / target_value) if target_value > 0 else 0.0
        else:
            cost = max(trade_value * commission, min_commission)

        # Check if we can afford it
        total_deduction = trade_value + cost
        if total_deduction > self._cash:
            # Try fewer lots
            if total_cost is not None:
                # Estimate affordable lots with the pre-computed rate
                effective_rate = total_cost / target_value if target_value > 0 else 0.0
                max_lots = int(self._cash / (price * lot_size * (1 + effective_rate)))
            else:
                max_lots = int((self._cash - min_commission) / (price * lot_size * (1 + commission)))
            if max_lots <= 0:
                return 0.0
            shares = max_lots * lot_size
            trade_value = shares * price
            if total_cost is not None:
                cost = total_cost * (trade_value / target_value) if target_value > 0 else 0.0
            else:
                cost = max(trade_value * commission, min_commission)
            total_deduction = trade_value + cost

        # Execute
        self._cash -= total_deduction
        self._today_costs += cost
        self._today_turnover += trade_value

        if code in self._positions:
            self._positions[code].add_shares(shares, price, date)
        else:
            self._positions[code] = Position(
                code=code,
                shares=shares,
                closeable_amount=0,  # T+1: not closeable today
                avg_cost=price,
                latest_entry_date=date,
            )

        logger.debug('BUY %s: %d shares @ %.2f = %.2f (cost=%.2f, cash=%.2f)',
                     code, shares, price, trade_value, cost, self._cash)
        return trade_value

    def sell(self, code: str, price: float, shares: int,
             date: pd.Timestamp,
             commission: float = None, stamp_tax: float = None,
             min_commission: float = 5.0,
             total_cost: float = None) -> float:
        """Sell shares of a stock.

        Cost source: when ``total_cost`` is provided (the preferred path
        via ``Exchange.compute_sell_cost_breakdown()``), it is used as the
        pre-computed cost for cash deduction. When ``total_cost`` is None
        (backward-compatible path for direct callers), cost is computed
        from ``commission``, ``stamp_tax``, and ``min_commission`` rates.

        Args:
            code: Stock ts_code.
            price: Fill price per share (after slippage).
            shares: Number of shares to sell.
            date: Trade date.
            commission: Commission rate. Used only when total_cost is None.
            stamp_tax: Stamp tax rate (seller only). Used only when total_cost is None.
            min_commission: Minimum commission in ¥. Used only when total_cost is None.
            total_cost: Pre-computed total cost from Exchange breakdown.
                When provided, ``commission``, ``stamp_tax``, and ``min_commission``
                are ignored.

        Returns:
            Net proceeds (after costs), or 0 if trade skipped.
        """
        pos = self._positions.get(code)
        if pos is None:
            logger.warning('Sell attempted on non-existent position: %s', code)
            return 0.0

        if price <= 0 or shares <= 0:
            return 0.0

        # Cap at closeable amount
        actual_shares = min(shares, pos.closeable_amount)
        if actual_shares <= 0:
            return 0.0

        trade_value = actual_shares * price
        if total_cost is not None:
            # Use pre-computed cost from Exchange
            computed_cost = total_cost
        else:
            # Legacy path: compute from rates
            if commission is None:
                commission = 0.00025
            if stamp_tax is None:
                stamp_tax = 0.0005
            comm_cost = max(trade_value * commission, min_commission)
            tax_cost = trade_value * stamp_tax
            computed_cost = comm_cost + tax_cost
        net_proceeds = trade_value - computed_cost

        # Execute
        pos.remove_shares(actual_shares)
        self._cash += net_proceeds
        self._today_costs += computed_cost
        self._today_turnover += trade_value

        # Clean up empty positions
        if pos.is_empty:
            del self._positions[code]

        logger.debug('SELL %s: %d shares @ %.2f = %.2f (cost=%.2f, cash=%.2f)',
                     code, actual_shares, price, trade_value, total_cost, self._cash)
        return net_proceeds

    def credit_cash(self, amount: float) -> None:
        """Credit cash to the portfolio (e.g., from dividends).

        Args:
            amount: Cash amount in ¥ to add.
        """
        self._cash += amount

    def force_close(self, code: str, price: float) -> None:
        """Force-close a position at given price (e.g., delisting).

        No commission or stamp tax applied.

        Args:
            code: Stock ts_code.
            price: Close price.
        """
        pos = self._positions.get(code)
        if pos is None:
            return
        proceeds = pos.shares * price
        self._cash += proceeds
        logger.warning('Force-closed %s: %d shares @ %.2f = %.2f',
                      code, pos.shares, price, proceeds)
        del self._positions[code]

    def market_value(self, prices: dict[str, float]) -> float:
        """Total market value of all positions.

        Args:
            prices: Dict of {ts_code: close_price}.

        Returns:
            Sum of shares * price for each held position.
        """
        import math
        total = 0.0
        for code, pos in self._positions.items():
            price = prices.get(code, pos.avg_cost)
            # Guard against NaN prices — use avg_cost as fallback
            if not isinstance(price, (int, float)) or not math.isfinite(price):
                price = pos.avg_cost
            total += pos.shares * price
        return total

    def total_value(self, prices: dict[str, float]) -> float:
        """Total portfolio value (cash + market value).

        Args:
            prices: Dict of {ts_code: close_price}.

        Returns:
            Cash + sum of all position values.
        """
        return self._cash + self.market_value(prices)

    def get_position(self, code: str) -> Optional[Position]:
        """Get a position by code, or None if not held.

        Args:
            code: Stock ts_code.
        """
        return self._positions.get(code)

    def can_sell(self, code: str, shares: int = 1) -> bool:
        """Check if we can sell the specified number of shares.

        Checks T+1 closeable_amount.

        Args:
            code: Stock ts_code.
            shares: Number of shares to sell.
        """
        pos = self._positions.get(code)
        if pos is None:
            return False
        return pos.closeable_amount >= shares

    def weight(self, code: str, prices: dict[str, float]) -> float:
        """Get the portfolio weight of a position.

        Args:
            code: Stock ts_code.
            prices: Dict of {ts_code: close_price}.

        Returns:
            Weight as a fraction (0.0 to 1.0).
        """
        tv = self.total_value(prices)
        if tv <= 0:
            return 0.0
        pos = self._positions.get(code)
        if pos is None:
            return 0.0
        price = prices.get(code, pos.avg_cost)
        return (pos.shares * price) / tv

    def get_today_costs(self) -> float:
        """Total transaction costs incurred today."""
        return self._today_costs

    def get_today_turnover(self) -> float:
        """Total traded value today (buy + sell)."""
        return self._today_turnover

    # ─── JoinQuant-parity sizing helpers (added 2026-05-22) ────────────
    #
    # The local v18 mimic strategy (a no-trim experimental variant in the
    # P1 G5_A2 investigation) had a NaN-poisoning bug: it used
    # ``avail_cash = self.cash + sum(pos.shares * prev_prices.get(c))``
    # over the sold-positions list, and a single suspended position with a
    # NaN prev-close turned avail_cash into NaN, then value_per_new = NaN,
    # then ``value_per_new > 1.0`` evaluated False, then NO buys were
    # generated → the portfolio stuck in cash for the entire 2015-08-19 →
    # 2015-09-14 股灾 recovery. The bug was strategy-script-local (the
    # engine's Portfolio.market_value() already falls back to avg_cost),
    # but this helper exposes the safe pattern at the API boundary so
    # future strategy code cannot accidentally re-introduce it.
    def available_cash_after_sells(
        self,
        sold_codes,
        prices: dict[str, float],
        price_fallback: str = 'avg_cost',
    ) -> float:
        """Estimate cash available after a list of pending sells executes.

        The engine settles sells before buys within a bar, so a strategy that
        sizes buys at ``cash / n_empty_slots`` will under-deploy unless it
        adds the expected sell proceeds first. This helper computes the
        post-sell cash NaN-robustly: each sell contributes
        ``shares × price`` if price is finite and positive, otherwise it
        falls back to ``avg_cost`` (the v11/v20 behavior of
        ``Portfolio.market_value``) and finally to 0.

        Args:
            sold_codes: Iterable of ts_codes the strategy is about to sell.
            prices: Dict of {ts_code: reference price} (typically yesterday's
                close from ``context.prev_day_data``).
            price_fallback: ``'avg_cost'`` (default) falls back to the
                position's avg_cost when the price dict has NaN/missing/<=0
                for that code. ``'zero'`` contributes 0 for those (the
                most conservative estimate). Suspended positions can't
                actually be sold so contributing 0 is also defensible —
                ``'zero'`` is the pessimistic/safest setting; ``'avg_cost'``
                mirrors what ``market_value`` does for valuation.

        Returns:
            ``self.cash + Σ_{c ∈ sold_codes} (shares × safe_price)`` —
            always finite and non-negative.
        """
        import math
        extra = 0.0
        for code in sold_codes:
            pos = self._positions.get(code)
            if pos is None:
                continue
            px = prices.get(code)
            if (px is None
                    or not isinstance(px, (int, float))
                    or not math.isfinite(px)
                    or px <= 0):
                if price_fallback == 'avg_cost':
                    px = (pos.avg_cost
                          if (pos.avg_cost and math.isfinite(pos.avg_cost)
                              and pos.avg_cost > 0)
                          else 0.0)
                else:
                    px = 0.0
            extra += pos.shares * px
        out = self._cash + extra
        # Defensive final clamp — never return NaN/inf
        if not math.isfinite(out) or out < 0:
            return self._cash
        return out

    def safe_total_value(self, prices: dict[str, float]) -> float:
        """NaN-robust total portfolio value (cash + market value).

        Alias of ``total_value()`` — ``market_value()`` already falls back
        to ``avg_cost`` for NaN/missing prices. This helper exists for
        explicitness in JoinQuant-parity strategy code where NaN safety is
        load-bearing for the sizing guard (``value > 1.0``).
        """
        return self.total_value(prices)
