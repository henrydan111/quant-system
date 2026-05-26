"""v14 — replay JoinQuant's exact trade log through our EventDrivenBacktester.

If v14's CAGR ≈ JQ's CAGR (90.86%):
  → The data/selection is reproducible; the 19.66pp v11/v13 gap is purely
    trajectory-divergence from selection mechanics (data ranking sub-bps,
    trade-day-decision precision).

If v14's CAGR ≈ v11/v13 CAGR (~71%):
  → The execution engine itself is the gap (slippage, costs, fills, MTM).

Strategy: read JQ trades.csv, pre-compute a per-date list of (code,
direction, target_shares_or_value, ...) orders, then execute them at the
engine's open price on the trade date. Buys use the share count from JQ's
trade record (target_shares = JQ's amount); sells too.

Note: JQ's trade.price is the FILL price; we use target_shares as the
quantity. Our engine fills at our local open price, so any difference
between JQ's fill price and our open price will be the executable-edge gap.
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
from src.backtest_engine.event_driven.exchange import CostConfig, FixedSlippage
from src.backtest_engine.event_driven.strategy import (
    BacktestContext,
    Order,
    Strategy,
)

LOGGER = logging.getLogger("p1_jq_mimic_v15")

START_DATE = pd.Timestamp("2014-01-01")
END_DATE = pd.Timestamp("2026-02-27")
INITIAL_CAPITAL = 100_000.0
BENCHMARK = "000300.SH"
SLIPPAGE_YUAN_PER_SHARE = 3.0 / 10000.0  # v15: match JQ FixedSlippage(3/10000) = 0.0003 ¥/share

JQ_TRADES_CSV = Path(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv")
OUTPUT_DIR = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v15_jq_slippage_run"


class JQReplayStrategy(Strategy):
    """Replays a pre-loaded JoinQuant trade log through our engine.

    Schedule:
      replay_schedule[date_ts] = list of Order objects to execute
        before_market_open on that date (fills at the engine's open price).

    Sells before buys to free up cash for buying.
    """

    def __init__(self, replay_schedule: dict[pd.Timestamp, list[Order]]):
        super().__init__()
        self.replay_schedule = replay_schedule

    def initialize(self, context: BacktestContext) -> None:
        LOGGER.info(
            "JQReplayStrategy init: %d trade dates, %d total orders",
            len(self.replay_schedule),
            sum(len(v) for v in self.replay_schedule.values()),
        )

    def before_market_open(self, context: BacktestContext) -> list[Order]:
        date_key = pd.Timestamp(context.date).normalize()
        orders = self.replay_schedule.get(date_key, [])
        return orders

    def on_bar(self, context: BacktestContext) -> list[Order]:
        return []


def build_replay_schedule() -> dict[pd.Timestamp, list[Order]]:
    """Parse JQ trades.csv into our engine's per-day Order list.

    JQ trade columns: action, amount, time, security, price, side, status, type
      action: 'open' (buy) or 'close' (sell)
      amount: number of shares
      security: stock code in JQ format (.XSHE/.XSHG)
      price: JQ's fill price (informational; we fill at our open)
    """
    df = pd.read_csv(JQ_TRADES_CSV, parse_dates=["time"])
    df["date"] = df["time"].dt.normalize()
    # Convert JQ → Tushare format
    df["code_ts"] = (
        df["security"]
        .str.replace(".XSHE", ".SZ", regex=False)
        .str.replace(".XSHG", ".SH", regex=False)
    )
    LOGGER.info(f"JQ trades loaded: {len(df)} trades from {df['date'].min().date()} to {df['date'].max().date()}")

    schedule: dict[pd.Timestamp, list[Order]] = {}
    for date, grp in df.groupby("date"):
        orders: list[Order] = []
        # Sort: sells first (action='close'), buys after (action='open')
        grp_sorted = grp.sort_values("action", ascending=False)  # 'close' < 'open'
        for _, row in grp_sorted.iterrows():
            code = row["code_ts"]
            shares = int(row["amount"])
            if row["action"] == "close":
                orders.append(Order(code=code, direction="sell", target_shares=shares, reason="jq_replay_sell"))
            elif row["action"] == "open":
                # Engine doesn't accept target_shares for buys; convert via JQ's fill price.
                # The engine will fill at OUR open price, so the actual share count
                # will differ from JQ by (jq_fill_price / our_open_price). Slippage edge.
                jq_price = float(row["price"])
                jq_value = jq_price * shares
                orders.append(Order(code=code, direction="buy", target_value=jq_value, reason="jq_replay_buy"))
        schedule[pd.Timestamp(date)] = orders
    LOGGER.info(f"Replay schedule built: {len(schedule)} dates, {sum(len(v) for v in schedule.values())} orders")
    return schedule


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGGER.info(f"Output dir: {OUTPUT_DIR}")

    replay_schedule = build_replay_schedule()
    strategy = JQReplayStrategy(replay_schedule=replay_schedule)

    backtester = EventDrivenBacktester(data_dir=str(PROJECT_ROOT / "data"))

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
        slippage=FixedSlippage(SLIPPAGE_YUAN_PER_SHARE),  # v15: JQ convention ¥0.0003/share
        volume_limit=1.0,
        preload_fields=DEFAULT_PRELOAD_FIELDS,
    )

    # Export results
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
    if hasattr(result, "trades"):
        trd = result.trades
        if isinstance(trd, pd.DataFrame) and not trd.empty:
            trd.to_csv(trades_path, index=False)
            LOGGER.info(f"Wrote trades: {trades_path}")

    LOGGER.info("v14 (JQ-replay) run complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
