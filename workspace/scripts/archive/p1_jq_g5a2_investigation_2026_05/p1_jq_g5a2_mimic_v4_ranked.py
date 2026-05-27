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
from src.backtest_engine.event_driven.strategies import RankedFallbackStrategy
from src.backtest_engine.event_driven.strategy import (
    BacktestContext,
    Order,
    Strategy,
)

LOGGER = logging.getLogger("p1_jq_mimic")

# Run constants
START_DATE = pd.Timestamp("2014-01-01")
END_DATE = pd.Timestamp("2023-12-31")
INITIAL_CAPITAL = 2_000_000.0
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

OUTPUT_DIR = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v4_ranked_run"

# v2 (2026-05-20): restrict universe to 002/003 ONLY (原中小板).
RESTRICT_TO_SMB_ONLY = True

# v3 (2026-05-20): SURVIVORSHIP BIAS TEST. Setting to False here — v4 uses the
# v2 universe (no survivor restriction) so it's a clean A/B vs v2 isolating
# the substitution effect.
RESTRICT_TO_SURVIVORS_ONLY = False
SURVIVOR_CUTOFF_DATE = pd.Timestamp("2024-01-01")

# v4 (2026-05-20): RankedFallbackStrategy with top-24 ranked candidates per
# rebalance date. Walks the ranked list, skips locked/suspended, picks first 12.
# This mirrors JoinQuant's `filter_limitup_stock` substitution pattern that
# the v1/v2/v3 ScheduledLongOnlyStrategy doesn't implement.
RANKED_OVERSAMPLE = 24  # top-24 candidates per date (2 × STOCK_NUM)


class JoinQuantG5MimicStrategy(Strategy):
    """100% JoinQuant G5_A2 mimic with calendar blackout + dual stoploss.

    v4 (2026-05-20): switched from naive top-K weights (dict[date, dict[code, weight]])
    to RANKED candidate lists (dict[date, list[code]]) so we can substitute when
    top picks are locked at limit yesterday / suspended today. This is the
    filter_limitup_stock mechanism JoinQuant uses; cumulative-return impact is
    largest in bull years (2015, 2022).
    """

    def __init__(
        self,
        ranked_schedule: dict[pd.Timestamp, list[str]],
        market_stoploss_universe: dict[pd.Timestamp, set[str]],
        pass_months: set[int] = PASS_MONTHS,
        stoploss_limit: float = STOPLOSS_LIMIT,
        stoploss_market: float = STOPLOSS_MARKET,
        stock_num: int = STOCK_NUM,
    ):
        super().__init__()
        self.ranked_schedule = ranked_schedule
        self.market_stoploss_universe = market_stoploss_universe
        self.pass_months = pass_months
        self.stoploss_limit = stoploss_limit
        self.stoploss_market = stoploss_market
        self.stock_num = stock_num
        # Embed a RankedFallbackStrategy for the substitution logic.
        # We delegate the "build target weights" step to it on non-blackout days.
        self._ranked = RankedFallbackStrategy(ranked_schedule, topk=stock_num)
        # State
        self.g.market_stop_fired_today = False

    def initialize(self, context: BacktestContext) -> None:
        LOGGER.info(
            "Mimic init: pass_months=%s stoploss_limit=%.2f stoploss_market=%.2f stock_num=%d",
            sorted(self.pass_months),
            self.stoploss_limit,
            self.stoploss_market,
            self.stock_num,
        )
        return None

    # ── Helpers ─────────────────────────────────────────────────────────

    def _check_market_stoploss(self, context: BacktestContext) -> bool:
        """JQ market stoploss: mean(prev_day close/open) across 中小综 proxy ≤ 0.94 → sell all."""
        if context.prev_day_data is None or context.prev_day_data.empty:
            return False
        uni = self.market_stoploss_universe.get(pd.Timestamp(context.date))
        if not uni:
            return False
        prev = context.prev_day_data
        mask = prev["ts_code"].isin(uni)
        slice_ = prev.loc[mask, ["close", "open"]].dropna()
        slice_ = slice_[(slice_["open"] > 0)]
        if len(slice_) < 100:
            return False
        ratio = (slice_["close"] / slice_["open"]).mean()
        if ratio <= self.stoploss_market:
            LOGGER.info(
                "Market stoploss fired on %s: mean(close/open)=%.4f over %d names (threshold %.2f)",
                context.date, ratio, len(slice_), self.stoploss_market
            )
            return True
        return False

    def _sell_all_orders(self, context: BacktestContext, reason: str) -> list[Order]:
        return [
            Order(code=code, direction="sell", reason=reason)
            for code in list(context.portfolio.positions)
        ]

    # ── Lifecycle ──────────────────────────────────────────────────────

    def before_market_open(self, context: BacktestContext) -> list[Order]:
        self.g.market_stop_fired_today = False

        # 1. Pass-month → sell all
        if context.date.month in self.pass_months:
            return self._sell_all_orders(context, "pass_month")

        # 2. Market stoploss (pre-open check on yesterday's data)
        if self._check_market_stoploss(context):
            self.g.market_stop_fired_today = True
            return self._sell_all_orders(context, "market_stoploss")

        # 3. Normal schedule rebalance via RankedFallbackStrategy substitution
        #    (delegates the ranked-substitution logic; emits the same Order objects).
        if pd.Timestamp(context.date) not in self.ranked_schedule:
            return []
        return self._ranked.before_market_open(context)

        # The old direct-target-weights path is dead code below — left for reference.
        target_weights = {}  # type: ignore
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

        # Exit positions not in target
        for code in sorted(current_codes - target_codes):
            orders.append(Order(code=code, direction="sell", reason="rebalance_exit"))

        # Trim positions over target
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

        # Buy new + top-ups
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

    def on_bar(self, context: BacktestContext) -> list[Order]:
        """Individual stoploss: close < avg_cost * 0.88 → sell. Skip in pass months / after market stop."""
        if context.date.month in self.pass_months:
            return []
        if getattr(self.g, "market_stop_fired_today", False):
            return []

        orders: list[Order] = []
        if context.day_data is None or context.day_data.empty:
            return orders
        day_idx = context.day_data_indexed
        for code, pos in list(context.portfolio.positions.items()):
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


def build_universe_per_date(start_date: pd.Timestamp, end_date: pd.Timestamp) -> dict[pd.Timestamp, set[str]]:
    """Per-date set of ts_codes eligible to be picked.

    Mimics JoinQuant filter_new_stock(375d) + filter_st_stock + filter_kcbj_stock
    (excludes 科创/北交所; keeps 创业板). Delisted stocks fall out of eligibility
    on/after their delist_date.
    """
    LOGGER.info("Building per-date universe…")
    sb = pd.read_parquet(PROJECT_ROOT / "data/reference/stock_basic.parquet")
    sb["list_date"] = pd.to_datetime(sb["list_date"], format="%Y%m%d", errors="coerce")
    sb["delist_date"] = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")
    if RESTRICT_TO_SMB_ONLY:
        # v2: match JoinQuant 中小综 (399101.XSHE) — ONLY 002/003 (原中小板)
        sb = sb[sb["ts_code"].str.startswith("002") | sb["ts_code"].str.startswith("003")]
        LOGGER.info(f"v2 universe filter: 002/003 only — {len(sb)} historical stock_basic rows")
    else:
        # v1: broad mainboard + ChiNext (over-broad vs JoinQuant)
        sb = sb[sb["ts_code"].str[:2].isin(("00", "30", "60")) & ~sb["ts_code"].str.startswith("688")]

    if RESTRICT_TO_SURVIVORS_ONLY:
        # v3: survivorship-bias test. Keep ONLY stocks alive at SURVIVOR_CUTOFF_DATE
        # (i.e., delist_date is NaN OR > cutoff). This simulates JoinQuant's likely
        # behavior of get_index_stocks('399101.XSHE') returning the 2021-04 frozen
        # membership, applied to all historical dates.
        before_n = len(sb)
        sb = sb[sb["delist_date"].isna() | (sb["delist_date"] >= SURVIVOR_CUTOFF_DATE)]
        LOGGER.info(
            f"v3 survivor filter: keep stocks alive at {SURVIVOR_CUTOFF_DATE.date()} — "
            f"{before_n} → {len(sb)} (dropped {before_n - len(sb)} delisted)"
        )

    # Trading calendar
    cal = pd.read_parquet(PROJECT_ROOT / "data/reference/trade_cal.parquet")
    cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
    cal = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= start_date) & (cal["cal_date"] <= end_date)]
    cal = cal.sort_values("cal_date").reset_index(drop=True)

    st = load_st_ranges()
    LOGGER.info(f"ST ranges loaded: {len(st)} rows")

    universe: dict[pd.Timestamp, set[str]] = {}
    for d in cal["cal_date"]:
        d_ts = pd.Timestamp(d)
        list_cutoff = d_ts - pd.Timedelta(days=375)
        elig = sb[
            (sb["list_date"] <= list_cutoff)
            & ((sb["delist_date"].isna()) | (sb["delist_date"] > d_ts))
        ]
        # ST exclusion: any ST range where start <= d < end
        st_today = st[
            (st["start"].notna())
            & (st["start"] <= d_ts)
            & ((st["end"].isna()) | (st["end"] > d_ts))
        ]
        st_codes = set(st_today["ts_code"])
        eligible_codes = set(elig["ts_code"]) - st_codes
        universe[d_ts] = eligible_codes

    LOGGER.info(
        "Universe built: %d trading days; median size %d, min %d, max %d",
        len(universe),
        int(np.median([len(v) for v in universe.values()])),
        int(min(len(v) for v in universe.values())),
        int(max(len(v) for v in universe.values())),
    )
    return universe


def compute_rebalance_schedule(
    universe_by_date: dict[pd.Timestamp, set[str]],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    stock_num: int = STOCK_NUM,
    pass_months: set[int] = PASS_MONTHS,
) -> dict[pd.Timestamp, dict[str, float]]:
    """Weekly Tuesday rebalance: top-N smallest by Ref($total_mv, 1)."""
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
    LOGGER.info(f"Computing Ref($total_mv, 1) for {len(qlib_codes)} instruments across full window…")
    # Use the rebalance-date range plus a 5-day buffer
    feat_start = (min(rebal_dates) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    feat_end = (max(rebal_dates) + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    df = D.features(qlib_codes, ["Ref($total_mv, 1)"], start_time=feat_start, end_time=feat_end, freq="day")
    df.columns = ["total_mv_lag1"]
    LOGGER.info(f"Feature loaded: {df.shape}")
    # MultiIndex (instrument, datetime) per Qlib convention
    df = df.dropna()

    # v4 (2026-05-20): emit ranked top-(stock_num × oversample) candidates per date
    # so RankedFallbackStrategy can substitute when primaries are locked-up/suspended.
    ranked_size = stock_num * 2  # top-24 for stock_num=12
    schedule: dict[pd.Timestamp, list[str]] = {}
    for rd in rebal_dates:
        try:
            slice_ = df.xs(rd, level=1)
        except KeyError:
            continue
        eligible_qlib = {c.replace(".", "_") for c in universe_by_date.get(rd, set())}
        slice_ = slice_[slice_.index.isin(eligible_qlib)]
        if len(slice_) < stock_num:
            continue
        smallest = slice_.nsmallest(ranked_size, "total_mv_lag1")
        # In rank order: smallest first (best ranked = lowest market cap)
        codes_in_rank = [idx.upper().replace("_", ".") for idx in smallest.index]
        schedule[rd] = codes_in_rank

    LOGGER.info(f"Ranked schedule built: {len(schedule)} dates, ~{ranked_size} candidates each")
    return schedule


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

    # 2. Schedule
    schedule = compute_rebalance_schedule(universe_by_date, START_DATE, END_DATE)
    LOGGER.info(f"Sample schedule entry: {next(iter(schedule.items()))}")

    # 3. Run backtest
    LOGGER.info("Launching EventDrivenBacktester…")
    backtester = EventDrivenBacktester(data_dir=str(PROJECT_ROOT / "data"))
    strategy = JoinQuantG5MimicStrategy(
        ranked_schedule=schedule,
        market_stoploss_universe=market_stop_uni,
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
        volume_limit=0.25,
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
