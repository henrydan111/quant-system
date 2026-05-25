"""P1.0-mimic: 100% port of JoinQuant G5_A2 to the local EventDrivenBacktester.

Adds the four overlays missing from P1 baseline:
  1. Calendar blackout (pass_months=[1,4]) — sell all in January and April
  2. Individual stoploss (sell if close < avg_cost * 0.88, i.e. -12% from cost)
  3. Market trend stoploss (sell ALL if mean close/open across 中小综 proxy ≤ 0.94)
  4. ChiNext (300xxx) inclusion in universe
  5. 3 bps slippage (matches JoinQuant's FixedSlippage(3/10000))

Differences vs JoinQuant that I deliberately keep (for honest local-engine apples-to-apples):
  - Initial capital ¥2,000,000 (JQ used ¥100k — but ¥100k is unrealistic toy capital)
  - 25% daily volume cap (local engine default; JQ doesn't enforce, but more realistic)
  - PIT-shifted size: Ref($total_mv, 1) instead of same-day total_mv
  - Local engine multi-tier limits, T+1 settlement, suspension guard
  - Local engine transfer fee 2bps (JQ doesn't model it; small effect)
  - Benchmark HS300 (JQ uses 上证综指; for return comparison this doesn't matter)

Run:
  venv/Scripts/python.exe workspace/scripts/p1_jq_g5a2_mimic.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(r"E:/量化系统")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest_engine.event_driven import EventDrivenBacktester
from src.backtest_engine.event_driven.exchange import CostConfig, PctSlippage
from src.backtest_engine.event_driven.strategy import (
    BacktestContext,
    Order,
    Strategy,
)

LOGGER = logging.getLogger("p1_jq_mimic_v18")

# v13: path to the JQ research-export CSV with PIT 中小综 membership per Tuesday.
JQ_PIT_UNIVERSE_CSV = pd.Series(["E:/量化系统/Knowledge/zxz_399101_pit_membership_tuesdays.csv"]).iloc[0]

# Run constants — v5 extends to 2026-02-27 (data calendar end) to match
# JoinQuant's 12.37y backtest window (2014-01-02 → 2026-05-15) as closely as
# our local data permits.
START_DATE = pd.Timestamp("2014-01-01")
END_DATE = pd.Timestamp("2026-02-27")
INITIAL_CAPITAL = 100_000.0  # v8: match JQ G5_A2's initial cash exactly
BENCHMARK = "000300.SH"
STOCK_NUM = 12
PASS_MONTHS = {1, 4}
STOPLOSS_LIMIT = 0.88
STOPLOSS_MARKET = 0.94
SLIPPAGE_BPS = 3.0 / 10000.0  # 3 bps — match JQ FixedSlippage(3/10000)

# Universe: 中小综 proxy = mainboard (00/60) + ChiNext (300) — exclude STAR (688), BSE (4/8)
ALLOWED_PREFIXES = ("00", "30", "60")
EXCLUDED_PREFIXES_EXPLICIT = ("688", "301")  # 301 = 创业板 next-gen (post 2020), include per JQ
# Actually filter_kcbj_stock in JQ excludes 科创板 (688) + 北交所 (4/8 + recent 9), keeps 创业板 (30/301).

OUTPUT_DIR = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v18_no_trim_run"

# v2 (2026-05-20): restrict universe to 002/003 ONLY (原中小板).
RESTRICT_TO_SMB_ONLY = True

# v5 (2026-05-20): at-open limit-up filter. JoinQuant's filter_limitup_stock
# runs at Tuesday 10:30 with intraday minute data, so it knows whether each
# stock is currently locked at the upper limit. We approximate by checking
# today's open vs today's up_limit (both PIT-correct at the 9:30 trading
# moment — using today's open to decide a today-open trade is not lookahead).
#
# Implementation: build the schedule with TOP_K_CANDIDATES (= 2 × STOCK_NUM)
# at decision time, then filter out candidates whose today's open == today's
# up_limit (locked at open), then take the first STOCK_NUM that pass. This
# matches JQ's effective behavior at the daily-bar granularity we have.
AT_OPEN_FILTER = True
TOP_K_CANDIDATES = 100  # v11: match JQ's filter-then-top-100-then-top-24-then-top-12 buffer

# v3 (2026-05-20): SURVIVORSHIP BIAS TEST. JoinQuant's get_index_stocks('399101.XSHE')
# likely returns the frozen 2021-04 membership applied to ALL historical dates,
# which means JQ tests on stocks that survived to 2021-04. If true, JQ's reported
# numbers are inflated by ~hundreds of pp in bull years where survivors massively
# outperformed delistees.
#
# v3 simulates this by restricting the universe to 002/003 stocks that were ALIVE
# as of 2024-01-01 (survived the full IS window). If v3 results close the 2015/2022
# gaps vs JQ, the hypothesis is confirmed.
RESTRICT_TO_SURVIVORS_ONLY = True
SURVIVOR_CUTOFF_DATE = pd.Timestamp("2024-01-01")


class JoinQuantG5MimicStrategyV6(Strategy):
    """v6: v5 + JoinQuant's `g.yesterday_HL_list` retention + 14:30 limit-up
    reversal substitution. New schedule format: each rebal date carries the
    ranked TOP-K list (typically 24 = 2 * STOCK_NUM), and the strategy:

    1. at rebalance (before_market_open): picks first STOCK_NUM from the ranked
       list that pass the at-open lock filter, AND retains held stocks that
       closed at upper limit yesterday (the `yesterday_HL_list` mechanism)
    2. at end-of-day (on_bar): for each retained yesterday-HL stock, if today's
       close < today's up_limit, sell it AND fill the freed slot from the
       ranked list (the `check_limit_up` + `check_remain_amount` mechanism)
    """

    def __init__(
        self,
        ranked_schedule: dict[pd.Timestamp, list[str]],
        market_stoploss_universe: dict[pd.Timestamp, set[str]],
        per_day_quotes: dict,
        pass_months: set[int] = PASS_MONTHS,
        stoploss_limit: float = STOPLOSS_LIMIT,
        stoploss_market: float = STOPLOSS_MARKET,
        stock_num: int = STOCK_NUM,
    ):
        """`ranked_schedule[date]` → list of ts_codes, ranked smallest first.
        `per_day_quotes[(date, ts_code)]` → dict with keys 'close', 'open',
        'up_limit'. Built once at schedule-construction time from Qlib.
        """
        super().__init__()
        self.ranked_schedule = ranked_schedule
        self.market_stoploss_universe = market_stoploss_universe
        self.per_day_quotes = per_day_quotes
        self.pass_months = pass_months
        self.stoploss_limit = stoploss_limit
        self.stoploss_market = stoploss_market
        self.stock_num = stock_num

    def initialize(self, context: BacktestContext) -> None:
        self.g.market_stop_fired_today = False
        self.g.yesterday_HL_set: set[str] = set()
        # The most-recent rebalance day's ranked list — used for substitution
        # on subsequent days when retained yesterday-HL stocks reverse.
        self.g.last_ranked_list: list[str] = []
        LOGGER.info(
            "Mimic-v6 init: pass_months=%s stoploss_limit=%.2f stoploss_market=%.2f "
            "stock_num=%d. yesterday_HL_list retention + 14:30 substitution ENABLED.",
            sorted(self.pass_months), self.stoploss_limit, self.stoploss_market, self.stock_num,
        )

    # ── Helpers ─────────────────────────────────────────────────────────

    def _get_quote(self, code: str, date: pd.Timestamp) -> dict | None:
        return self.per_day_quotes.get((pd.Timestamp(date), code))

    def _check_market_stoploss(self, context: BacktestContext) -> bool:
        """v9 patch: mimic JoinQuant's get_price() convention where suspended stocks
        return last_close for both open and close, making their close/open ratio = 1.0.

        Implementation: the basket is the universe-eligible set on the prev_date.
        Stocks present in context.prev_day_data with valid open/close contribute
        their actual ratio. Stocks in the universe but ABSENT from prev_day_data
        (= suspended/halted that day; Qlib row is NaN) contribute ratio = 1.0.
        """
        if context.prev_day_data is None or context.prev_day_data.empty:
            return False
        uni = self.market_stoploss_universe.get(pd.Timestamp(context.date))
        if not uni:
            return False
        prev = context.prev_day_data
        mask = prev["ts_code"].isin(uni)
        slice_ = prev.loc[mask, ["close", "open", "ts_code"]].dropna(subset=["close", "open"])
        slice_ = slice_[(slice_["open"] > 0)]
        if len(slice_) < 100:
            return False
        n_trading = len(slice_)
        ratio_trading = (slice_["close"] / slice_["open"]).mean()
        # JQ convention: stocks in universe but absent from trading data → ratio = 1.0
        n_universe = len(uni)
        n_suspended = max(n_universe - n_trading, 0)
        if n_universe > 0:
            ratio = (ratio_trading * n_trading + 1.0 * n_suspended) / n_universe
        else:
            ratio = ratio_trading
        if ratio <= self.stoploss_market:
            LOGGER.info(
                "Market stoploss fired on %s: mean(close/open)=%.4f over %d trading + %d suspended=1.0 / %d total (threshold %.2f)",
                context.date, ratio, n_trading, n_suspended, n_universe, self.stoploss_market
            )
            return True
        return False

    def _sell_all(self, context: BacktestContext, reason: str) -> list[Order]:
        return [Order(code=c, direction="sell", reason=reason) for c in list(context.portfolio.positions)]

    def _update_yesterday_HL_set(self, context: BacktestContext) -> set[str]:
        """Held stocks that closed at upper limit yesterday — to be RETAINED
        for one extra day even if they leave today's target_list. Mirrors
        JoinQuant's `prepare_stock_list` which builds `g.yesterday_HL_list`
        from the held set + yesterday's close==high_limit condition."""
        held = set(context.portfolio.positions)
        if not held or context.prev_day_data is None or context.prev_day_data.empty:
            return set()
        prev = context.prev_day_data
        # We need yesterday's up_limit for each held stock. The prev_day_data
        # has close/open but not necessarily up_limit. Use per_day_quotes which
        # we precomputed.
        prev_date = pd.Timestamp(prev["trade_date"].iloc[0]) if "trade_date" in prev.columns else None
        if prev_date is None:
            # Fallback: try the prev_day_data's date attribute via context's feeder
            # Use a 1-day lookback heuristic on context.date
            prev_date = pd.Timestamp(context.date) - pd.Timedelta(days=1)
            # Walk back to a trading day in per_day_quotes
            for _ in range(10):
                if any((prev_date, c) in self.per_day_quotes for c in held):
                    break
                prev_date -= pd.Timedelta(days=1)
        hl: set[str] = set()
        for code in held:
            q = self._get_quote(code, prev_date)
            if q is None:
                continue
            close = q.get("close")
            up_limit = q.get("up_limit")
            if close is None or up_limit is None:
                continue
            if close >= up_limit - 1e-4:
                hl.add(code)
        return hl

    def _at_open_unlocked(self, code: str, date: pd.Timestamp) -> bool:
        """v10: tradeable at open = NOT locked at limit-up AND NOT locked at limit-down.

        JoinQuant runs `filter_limitup_stock` AND `filter_limitdown_stock` at 10:30
        based on the 1-minute close vs today's high_limit / low_limit. For daily-bar
        data, the cleanest proxy is the OPEN price: if open == down_limit, the stock
        opened locked at limit-down (queue exceeded). Per the 2024-02-06 audit, 5
        of v9's 12 picks opened exactly at down_limit; these dropped further on D+1
        (avg -8.5%) vs JQ's picks (avg -6.3%). Excluding them at decision time
        eliminates the systematic adverse selection in micro-cap-crash regimes.
        """
        q = self._get_quote(code, date)
        if q is None:
            return False
        open_ = q.get("open")
        up_limit = q.get("up_limit")
        down_limit = q.get("down_limit")
        if open_ is None or up_limit is None:
            return False
        if open_ >= up_limit - 1e-4:
            return False  # locked at limit-up at open
        if down_limit is not None and open_ <= down_limit + 1e-4:
            return False  # locked at limit-down at open
        return True

    def _close_unlocked(self, code: str, date: pd.Timestamp) -> bool:
        """True iff today's close < today's up_limit. Used at on_bar (EOD)
        to determine whether a retained yesterday-HL stock has failed to
        re-lock today and must be sold."""
        q = self._get_quote(code, date)
        if q is None:
            return False
        close = q.get("close")
        up_limit = q.get("up_limit")
        if close is None or up_limit is None:
            return False
        return close < up_limit - 1e-4

    # ── Lifecycle ──────────────────────────────────────────────────────

    def before_market_open(self, context: BacktestContext) -> list[Order]:
        self.g.market_stop_fired_today = False

        # 1. Pass-month → sell all (mirrors JQ close_account at 14:50)
        if context.date.month in self.pass_months:
            self.g.yesterday_HL_set = set()
            return self._sell_all(context, "pass_month")

        # 2. Market stoploss — v9 patch: even if stoploss fires, on a Tuesday
        #    rebal day we ALSO do the weekly_adjustment buys (mimic JQ's
        #    separate run_daily(sell_stocks, '10:00') + run_weekly(weekly_adjustment,
        #    2, '10:30') schedule — the buys happen 30 minutes AFTER the sells).
        stoploss_fired = self._check_market_stoploss(context)
        if stoploss_fired:
            self.g.market_stop_fired_today = True
            self.g.yesterday_HL_set = set()
            sell_orders = self._sell_all(context, "market_stoploss")
            # If it's NOT a rebal day, no buys to add — just sell-all and return.
            if pd.Timestamp(context.date) not in self.ranked_schedule:
                return sell_orders
            # Else: fall through to rebal logic, but treat as if no positions held
            # (since stoploss sold everything). The buy code below uses
            # context.portfolio.positions which DOES still show the positions
            # (sells haven't been executed yet). We need to compute as if cash.
            # Easiest: track market_stop_fired_today and skip held-set logic.
            # Yesterday_HL_set was cleared, so retention won't keep anything.

        else:
            # 3. Update yesterday_HL_set BEFORE deciding sells
            self.g.yesterday_HL_set = self._update_yesterday_HL_set(context)

            # 4. Non-rebalance day — no orders (stoploss handled in on_bar)
            if pd.Timestamp(context.date) not in self.ranked_schedule:
                return []

        ranked = self.ranked_schedule[pd.Timestamp(context.date)]
        # Remember for on_bar substitution if a yesterday-HL stock reverses later today
        self.g.last_ranked_list = list(ranked)

        # Apply at-open filter: first STOCK_NUM of ranked that pass the lock test
        target_unlocked: list[str] = []
        for code in ranked:
            if len(target_unlocked) >= self.stock_num:
                break
            if self._at_open_unlocked(code, context.date):
                target_unlocked.append(code)
        target_set = set(target_unlocked)

        # Compute portfolio value at prev close prices
        prev_prices: dict[str, float] = {}
        if context.prev_day_data is not None and not context.prev_day_data.empty:
            prev_prices = (
                context.prev_day_data.set_index("ts_code")["close"].astype(float).to_dict()
            )
        portfolio_value = context.portfolio.total_value(prev_prices)
        if portfolio_value <= 0:
            portfolio_value = context.portfolio.cash
        per_slot_value = portfolio_value / max(self.stock_num, 1)

        orders: list[Order] = []
        current_positions = dict(context.portfolio.positions)
        held = set(current_positions)

        # v9 patch: if stoploss fired, treat as effectively cash for buy sizing.
        # The sell_all orders are already in sell_orders (prepended below).
        # The buys should target full per_slot_value for each of the 12 target slots,
        # since the engine settles sells-then-buys within the same bar.
        if stoploss_fired:
            held = set()  # buy code below treats no overlap with target_set
            current_positions = {}

        # SELL: held but NOT in target AND NOT in yesterday_HL_set
        # ← the JoinQuant retention rule lives here
        sold_codes: list[str] = []
        for code in sorted(held - target_set):
            if code in self.g.yesterday_HL_set:
                continue  # RETAIN — JoinQuant mechanism
            orders.append(Order(code=code, direction="sell", reason="rebalance_exit"))
            sold_codes.append(code)

        # v18: JoinQuant buy_security sizing — NO TRIM, NO TOP-UP.
        # JoinQuant's weekly_adjustment only buys EMPTY target slots
        # (positions[stock].total_amount == 0) and lets retained winners run.
        #   value = cash / (target_num - position_count)
        # where position_count is the count AFTER sells. We estimate the
        # post-sell cash by adding the prev-close value of the sold positions
        # to current cash (engine settles sells-then-buys within the bar, so
        # the proceeds are available to the buys).
        empty_slots = [c for c in target_unlocked if c not in held]
        n_empty = len(empty_slots)
        if n_empty > 0:
            est_sell_proceeds = 0.0
            for c in sold_codes:
                pos = current_positions.get(c)
                if pos is not None:
                    est_sell_proceeds += pos.shares * float(prev_prices.get(c, pos.avg_cost if pos.avg_cost > 0 else 0))
            avail_cash = context.portfolio.cash + est_sell_proceeds
            value_per_new = avail_cash / n_empty
            _dd = pd.Timestamp(context.date)
            if pd.Timestamp("2015-08-15") <= _dd <= pd.Timestamp("2015-09-20"):
                LOGGER.warning(
                    "DBG2 %s: n_empty=%d est_proceeds=%.0f avail_cash=%.0f value_per_new=%.2f guard=%s",
                    _dd.date(), n_empty, est_sell_proceeds, avail_cash, value_per_new, value_per_new > 1.0,
                )
            if value_per_new > 1.0:
                for code in empty_slots:
                    orders.append(Order(
                        code=code, direction="buy",
                        target_value=value_per_new,
                        reason="rebalance_buy" if not stoploss_fired else "stoploss_then_rebal_buy",
                    ))

        # DEBUG: log decision detail for the 2015 stuck-cash window
        _d = pd.Timestamp(context.date)
        if pd.Timestamp("2015-08-15") <= _d <= pd.Timestamp("2015-09-20"):
            n_buy = sum(1 for o in orders if o.direction == "buy")
            n_sell_orders = sum(1 for o in orders if o.direction == "sell")
            LOGGER.warning(
                "DBG %s: stoploss_fired=%s n_held=%d n_target_unlocked=%d n_empty=%d "
                "cash=%.0f buy_orders=%d sell_orders=%d sellall=%d",
                _d.date(), stoploss_fired, len(held), len(target_unlocked),
                len(empty_slots), context.portfolio.cash, n_buy, n_sell_orders,
                len(sell_orders) if stoploss_fired else 0,
            )

        # v9 patch: prepend the sell_all orders from the stoploss firing
        # (the engine processes orders in list order; sells before buys
        # is the safe ordering)
        if stoploss_fired:
            return sell_orders + orders
        return orders

    def on_bar(self, context: BacktestContext) -> list[Order]:
        if context.date.month in self.pass_months:
            return []
        if getattr(self.g, "market_stop_fired_today", False):
            return []

        orders: list[Order] = []
        if context.day_data is None or context.day_data.empty:
            return orders
        day_idx = context.day_data_indexed
        held = dict(context.portfolio.positions)

        # 1. Individual stoploss (existing v5 logic)
        for code, pos in list(held.items()):
            if code not in day_idx.index:
                continue
            row = day_idx.loc[code]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            close = float(row.get("close", 0) or 0)
            if close <= 0:
                continue
            avg_cost = float(pos.avg_cost) if pos.avg_cost > 0 else close
            if avg_cost <= 0:
                continue
            if close < avg_cost * self.stoploss_limit:
                orders.append(Order(code=code, direction="sell", reason="stoploss_individual"))

        # 2. yesterday_HL reversal check + substitution
        # For each retained yesterday-HL stock, if today's close < today's
        # up_limit, sell. Track freed slots and fill from last_ranked_list.
        yhl = self.g.yesterday_HL_set
        if yhl:
            yhl_sold_codes: set[str] = set()
            for code in list(yhl):
                if code not in held:
                    continue
                if self._close_unlocked(code, context.date):
                    orders.append(Order(code=code, direction="sell", reason="limitup_reversal"))
                    yhl_sold_codes.add(code)

            # Substitution: how many slots will be free after these sells?
            # (Conservative: only count yhl reversal sells; not the individual stoploss
            # sells above, since those are independent risk events.)
            if yhl_sold_codes and self.g.last_ranked_list:
                will_be_held = set(held) - yhl_sold_codes
                slots_to_fill = max(0, self.stock_num - len(will_be_held))
                if slots_to_fill > 0:
                    # Walk last_ranked_list, skip already-held / sold, skip locked-at-open,
                    # skip locked at today's close (likely uncloseable later).
                    sub_codes: list[str] = []
                    for code in self.g.last_ranked_list:
                        if len(sub_codes) >= slots_to_fill:
                            break
                        if code in held:  # already in portfolio
                            continue
                        if code in yhl_sold_codes:
                            continue
                        # At-open filter (would not have been able to buy at open)
                        if not self._at_open_unlocked(code, context.date):
                            continue
                        # Also skip if locked at close (we'd be substituting INTO a locked name)
                        q = self._get_quote(code, context.date)
                        if q is None:
                            continue
                        close = q.get("close")
                        up_limit = q.get("up_limit")
                        if close is not None and up_limit is not None and close >= up_limit - 1e-4:
                            continue
                        sub_codes.append(code)

                    # v18: JQ check_remain_amount sizing — use available cash
                    # divided by the number of empty slots (NOT equal-weight).
                    est_proceeds = 0.0
                    for c in yhl_sold_codes:
                        pos = held.get(c)
                        q = self._get_quote(c, context.date)
                        if pos is not None and q is not None and q.get("close") is not None:
                            est_proceeds += pos.shares * float(q["close"])
                    avail_cash = context.portfolio.cash + est_proceeds
                    value_per_new = avail_cash / max(len(sub_codes), 1)
                    for code in sub_codes:
                        if value_per_new > 1.0:
                            orders.append(Order(
                                code=code, direction="buy",
                                target_value=value_per_new,
                                reason="limitup_substitute",
                            ))

        return orders


# ── Universe + schedule construction ────────────────────────────────────


def load_st_ranges() -> pd.DataFrame:
    """Load authoritative ST range table from sidecar."""
    path = PROJECT_ROOT / "data/qlib_data/instruments/st_stocks.txt"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        # Format: qlib_code \t start_date \t end_date (YYYYMMDD)
        rows.append({
            "qlib_code": parts[0],
            "start": pd.to_datetime(parts[1], format="%Y-%m-%d", errors="coerce"),
            "end": pd.to_datetime(parts[2], format="%Y-%m-%d", errors="coerce"),
        })
    df = pd.DataFrame(rows)
    df["ts_code"] = df["qlib_code"].str.replace("_", ".").str.upper()
    return df


def _load_jq_pit_membership() -> dict[pd.Timestamp, set[str]]:
    """Load the JoinQuant research-export of 中小综 (399101.XSHE) PIT membership.

    File: zxz_399101_pit_membership_tuesdays.csv — every Tuesday 2014-01-07 to
    2026-02-24 with the actual constituents JoinQuant's get_index_stocks would
    have returned at that date. Codes are in JQ format (.XSHE / .XSHG); we
    convert to Tushare format (.SZ / .SH) to match the rest of the pipeline.

    Returns: {Tuesday_date: set(ts_code_in_tushare_format)}
    """
    df = pd.read_csv(JQ_PIT_UNIVERSE_CSV)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    # JQ → Tushare
    df["ts_code"] = (
        df["ts_code"]
        .str.replace(".XSHE", ".SZ", regex=False)
        .str.replace(".XSHG", ".SH", regex=False)
    )
    pit: dict[pd.Timestamp, set[str]] = {
        d: set(grp["ts_code"]) for d, grp in df.groupby("date")
    }
    LOGGER.info(
        f"JQ PIT 中小综 membership loaded: {len(pit)} Tuesday snapshots, "
        f"median size {int(np.median([len(v) for v in pit.values()]))}"
    )
    return pit


def build_universe_per_date(start_date: pd.Timestamp, end_date: pd.Timestamp) -> dict[pd.Timestamp, set[str]]:
    """v13: per-date set of ts_codes eligible to be picked.

    Strategy: take the JQ PIT 中小综 membership (forward-filled from the
    nearest prior Tuesday snapshot) and intersect with our 375d-listed +
    non-ST filter. Reproduces JoinQuant's get_stock_list flow exactly:
      initial_list = get_index_stocks('399101.XSHE')   # JQ PIT
      initial_list = filter_new_stock(375d)            # local
      initial_list = filter_st_stock(...)              # local
    """
    LOGGER.info("v13: building per-date universe from JQ PIT membership ∩ local filters…")
    sb = pd.read_parquet(PROJECT_ROOT / "data/reference/stock_basic.parquet")
    sb["list_date"] = pd.to_datetime(sb["list_date"], format="%Y%m%d", errors="coerce")
    sb["delist_date"] = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")

    # Trading calendar
    cal = pd.read_parquet(PROJECT_ROOT / "data/reference/trade_cal.parquet")
    cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
    cal = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= start_date) & (cal["cal_date"] <= end_date)]
    cal = cal.sort_values("cal_date").reset_index(drop=True)

    st = load_st_ranges()
    LOGGER.info(f"ST ranges loaded: {len(st)} rows")

    # JQ PIT membership
    jq_pit = _load_jq_pit_membership()
    jq_dates_sorted = sorted(jq_pit.keys())
    jq_dates_array = np.array([d.value for d in jq_dates_sorted])

    def get_jq_members_asof(d: pd.Timestamp) -> set[str]:
        """Return JQ membership at the largest Tuesday t <= d. Forward-fill."""
        idx = np.searchsorted(jq_dates_array, d.value, side="right") - 1
        if idx < 0:
            # Before any snapshot — use the first Tuesday's data (one-week gap at start of window)
            return jq_pit[jq_dates_sorted[0]]
        return jq_pit[jq_dates_sorted[idx]]

    universe: dict[pd.Timestamp, set[str]] = {}
    for d in cal["cal_date"]:
        d_ts = pd.Timestamp(d)
        # 1. JQ PIT membership (forward-filled from nearest prior Tuesday)
        jq_members = get_jq_members_asof(d_ts)
        # 2. 375d listing age + delisting filter (local)
        list_cutoff = d_ts - pd.Timedelta(days=375)
        elig = sb[
            (sb["ts_code"].isin(jq_members))
            & (sb["list_date"] <= list_cutoff)
            & ((sb["delist_date"].isna()) | (sb["delist_date"] > d_ts))
        ]
        # 3. ST exclusion
        st_today = st[
            (st["start"].notna())
            & (st["start"] <= d_ts)
            & ((st["end"].isna()) | (st["end"] > d_ts))
        ]
        st_codes = set(st_today["ts_code"])
        eligible_codes = set(elig["ts_code"]) - st_codes
        universe[d_ts] = eligible_codes

    LOGGER.info(
        "v13 universe built: %d trading days; median size %d, min %d, max %d",
        len(universe),
        int(np.median([len(v) for v in universe.values()])),
        int(min(len(v) for v in universe.values())),
        int(max(len(v) for v in universe.values())),
    )
    return universe


def compute_rebalance_schedule_v6(
    universe_by_date: dict[pd.Timestamp, set[str]],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    stock_num: int = STOCK_NUM,
    pass_months: set[int] = PASS_MONTHS,
) -> tuple[dict[pd.Timestamp, list[str]], dict]:
    """v6: returns (ranked_schedule, per_day_quotes).

    ranked_schedule[date] = ordered list of TOP-K codes (smallest market_cap first).
    per_day_quotes[(date, code)] = {'close': float, 'open': float, 'up_limit': float}
    for EVERY trading day × code in the universe (not just rebal dates), so the
    strategy can look up yesterday's close/up_limit (for yesterday_HL detection)
    and today's close/up_limit (for on_bar reversal check) on any day.
    """
    LOGGER.info("Computing weekly-Tuesday rebalance schedule…")
    cal = pd.read_parquet(PROJECT_ROOT / "data/reference/trade_cal.parquet")
    cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
    cal = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= start_date) & (cal["cal_date"] <= end_date)]
    cal = cal.sort_values("cal_date").reset_index(drop=True)
    cal["weekday"] = cal["cal_date"].dt.weekday  # Mon=0, Tue=1
    cal["iso_year_week"] = cal["cal_date"].dt.isocalendar().year.astype(str) + "-" + cal["cal_date"].dt.isocalendar().week.astype(str)

    # First trading day per week with weekday >= 1 (Tuesday or later, since some weeks have no Tuesday due to holidays)
    rebal_dates: list[pd.Timestamp] = []
    for _, grp in cal.groupby("iso_year_week", sort=False):
        tue = grp[grp["weekday"] >= 1].sort_values("cal_date")
        if not tue.empty:
            rebal_dates.append(pd.Timestamp(tue.iloc[0]["cal_date"]))

    # Skip pass-months entirely (JQ's no_trading_today_signal blocks weekly_adjustment)
    rebal_dates = [d for d in rebal_dates if d.month not in pass_months]
    LOGGER.info(f"Rebalance dates: {len(rebal_dates)} (after pass-month skip)")

    # Compute size on the WHOLE possible universe over the full window
    import qlib
    from qlib.data import D
    qlib_dir = str(PROJECT_ROOT / "data/qlib_data")
    qlib.init(provider_uri=qlib_dir, kernels=1)

    all_codes_ts = set()
    for codes in universe_by_date.values():
        all_codes_ts.update(codes)
    qlib_codes = sorted(c.replace(".", "_") for c in all_codes_ts)
    feature_list = ["Ref($total_mv, 1)", "$open", "$close", "$up_limit", "$down_limit"]
    LOGGER.info(
        f"Computing {feature_list} for {len(qlib_codes)} instruments across full window…"
    )
    feat_start = (start_date - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    feat_end = (end_date + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    df = D.features(qlib_codes, feature_list, start_time=feat_start, end_time=feat_end, freq="day")
    df.columns = ["total_mv_lag1", "today_open", "today_close", "today_up_limit", "today_down_limit"]
    LOGGER.info(f"Feature loaded: {df.shape}")

    # Build per_day_quotes: (date, ts_code_upper) -> {'close', 'open', 'up_limit'}
    LOGGER.info("Building per_day_quotes lookup for the entire window…")
    df_rs = df.reset_index()  # columns: instrument, datetime, total_mv_lag1, today_open, today_close, today_up_limit
    df_rs["date"] = pd.to_datetime(df_rs["datetime"]).dt.normalize()
    df_rs["ts_code"] = df_rs["instrument"].str.upper().str.replace("_", ".")
    per_day_quotes: dict = {}
    for row in df_rs.itertuples(index=False):
        per_day_quotes[(row.date, row.ts_code)] = {
            "close": float(row.today_close) if pd.notna(row.today_close) else None,
            "open": float(row.today_open) if pd.notna(row.today_open) else None,
            "up_limit": float(row.today_up_limit) if pd.notna(row.today_up_limit) else None,
            "down_limit": float(row.today_down_limit) if pd.notna(row.today_down_limit) else None,
        }
    LOGGER.info(f"per_day_quotes lookup: {len(per_day_quotes)} entries")

    # Build ranked_schedule: for each rebal date, ordered TOP_K_CANDIDATES list
    df = df.dropna(subset=["total_mv_lag1"])
    ranked_schedule: dict[pd.Timestamp, list[str]] = {}
    for rd in rebal_dates:
        try:
            slice_ = df.xs(rd, level=1)
        except KeyError:
            continue
        eligible_qlib = {c.replace(".", "_") for c in universe_by_date.get(rd, set())}
        slice_ = slice_[slice_.index.isin(eligible_qlib)]
        if len(slice_) < stock_num:
            continue
        top_k = slice_.nsmallest(TOP_K_CANDIDATES, "total_mv_lag1")
        ranked = [idx.upper().replace("_", ".") for idx in top_k.index]
        if ranked:
            ranked_schedule[rd] = ranked

    LOGGER.info(
        f"Schedule built: {len(ranked_schedule)} rebalance dates × top-{TOP_K_CANDIDATES} ranked lists. "
        f"At-open filter + yesterday_HL retention applied at runtime in the strategy."
    )
    return ranked_schedule, per_day_quotes


def build_market_stoploss_universe(
    universe_by_date: dict[pd.Timestamp, set[str]],
) -> dict[pd.Timestamp, set[str]]:
    """For market stoploss, use the same per-date universe (proxy for 中小综)."""
    return universe_by_date


# ── Main ───────────────────────────────────────────────────────────────


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGGER.info(f"Output dir: {OUTPUT_DIR}")

    # 1. Universe
    universe_by_date = build_universe_per_date(START_DATE, END_DATE)
    market_stop_uni = build_market_stoploss_universe(universe_by_date)

    # 2. Schedule + per-day quotes lookup
    ranked_schedule, per_day_quotes = compute_rebalance_schedule_v6(universe_by_date, START_DATE, END_DATE)
    sample_date = next(iter(ranked_schedule))
    LOGGER.info(f"Sample ranked schedule [{sample_date.date()}]: {ranked_schedule[sample_date][:6]}...")

    # 3. Run backtest
    LOGGER.info("Launching EventDrivenBacktester with v6 strategy…")
    backtester = EventDrivenBacktester(data_dir=str(PROJECT_ROOT / "data"))
    strategy = JoinQuantG5MimicStrategyV6(
        ranked_schedule=ranked_schedule,
        market_stoploss_universe=market_stop_uni,
        per_day_quotes=per_day_quotes,
    )
    # CRITICAL: pass preload_fields so the engine pre-loads all OHLCV in one bulk read
    # instead of issuing a D.features() per day (which is the 15-22 sec/day slow path
    # documented in project_state.md update note 2026-04-29). With preload, the
    # per-day cost drops to ~150 ms.
    DEFAULT_PRELOAD_FIELDS = [
        "$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor",
    ]
    result = backtester.run(
        strategy=strategy,
        start_time=START_DATE.strftime("%Y-%m-%d"),
        end_time=END_DATE.strftime("%Y-%m-%d"),
        benchmark=BENCHMARK,
        account=INITIAL_CAPITAL,
        exchange_config=CostConfig(),
        slippage=PctSlippage(SLIPPAGE_BPS),
        volume_limit=1.0,   # v7: no volume cap (test HYPOTHESIS C). JoinQuant's default has no cap.
        preload_fields=DEFAULT_PRELOAD_FIELDS,
    )

    # 4. Export results
    report_path = OUTPUT_DIR / "event_driven_report.csv"
    trades_path = OUTPUT_DIR / "event_driven_trades.csv"

    if hasattr(result, "to_dataframe"):
        rpt = result.to_dataframe()
    elif hasattr(result, "report"):
        rpt = result.report
    elif hasattr(result, "daily"):
        rpt = result.daily
    else:
        rpt = pd.DataFrame()
    if not rpt.empty:
        rpt.to_csv(report_path, index=False)
        LOGGER.info(f"Wrote report: {report_path}")

    trades_attr = None
    for attr in ("trades", "to_trades", "trade_log", "trades_df"):
        if hasattr(result, attr):
            trades_attr = getattr(result, attr)
            break
    if trades_attr is not None:
        td = trades_attr() if callable(trades_attr) else trades_attr
        if isinstance(td, pd.DataFrame) and not td.empty:
            td.to_csv(trades_path, index=False)
            LOGGER.info(f"Wrote trades: {trades_path}")

    # 5. Yearly comparison vs JoinQuant G5_A2
    if not rpt.empty and "return" in rpt.columns:
        rpt["date"] = pd.to_datetime(rpt["date"])
        rpt["year"] = rpt["date"].dt.year
        yearly = rpt.groupby("year")["return"].apply(lambda x: float((1 + x).prod() - 1))
        bench = rpt.groupby("year")["bench"].apply(lambda x: float((1 + x).prod() - 1))
        jq_g5a2 = {
            2014: 1.137, 2015: 4.072, 2016: 0.874, 2017: 0.058,
            2018: 0.390, 2019: 0.602, 2020: 0.560, 2021: 0.702,
            2022: 1.963, 2023: 0.559,
        }
        out = pd.DataFrame({"mimic": yearly, "bench": bench, "jq_g5a2": pd.Series(jq_g5a2)})
        out["mimic_minus_jq_pp"] = (out["mimic"] - out["jq_g5a2"]) * 100
        print()
        print("=== Yearly comparison: P1.0-mimic vs JoinQuant G5_A2 ===")
        print(out.to_string(float_format=lambda x: f"{x:7.4f}" if abs(x) < 100 else f"{x:.1f}"))
        out.to_csv(OUTPUT_DIR / "yearly_comparison.csv")
        cum = float((1 + rpt["return"]).prod() - 1)
        n_years = len(rpt) / 242
        cagr = (1 + cum) ** (1 / n_years) - 1 if n_years > 0 else 0
        print()
        print(f"Stitched total return: {cum*100:.2f}%  CAGR: {cagr*100:.2f}%  Days: {len(rpt)}")

    LOGGER.info("Mimic run complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
