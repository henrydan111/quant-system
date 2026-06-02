# Backtest Engine (`src/backtest_engine/`)

The Backtest Engine simulates trading strategies using data from `data_infra` and predictive signals from `alpha_research`. It provides **two complementary backtesting engines**, each serving a distinct purpose in the research pipeline: `VectorizedBacktester` for rapid screening and `EventDrivenBacktester` for execution-realistic validation.

## Architecture

```text
backtest_engine/
├── README.md                    ← this file
├── vectorized/                  # Qlib-integrated signal backtester
│   └── __init__.py              → VectorizedBacktester, BacktestResult
└── event_driven/                # Custom A-share backtester
    ├── __init__.py              → EventDrivenBacktester (high-level API)
    ├── data_feeder.py           → QlibDataFeeder (PIT data layer)
    ├── engine.py                → BacktestEngine, BacktestResult (main loop)
    ├── exchange.py              → Exchange, CostConfig, Slippage models
    ├── portfolio.py             → Portfolio, Position (T+1 tracking)
    ├── strategy.py              → Strategy base class, Order, BacktestContext
    └── corporate_actions.py     → CorporateActionHandler (dividends, bonus shares)
```

## Engine Comparison

| Feature | VectorizedBacktester | EventDrivenBacktester |
|---------|---------------------|-----------------------|
| **Backend** | Qlib `backtest()` | Custom Python engine |
| **Strategy Input** | Score-ranked signal → TopkDropout/Weight | Custom `Strategy` class (JQ-style) |
| **Execution Model** | Qlib SimulatorExecutor | Sells-before-buys, 2-phase per day |
| **Price Limits** | Expression-based (`$pct_chg ≥ 9.5`) | Tushare `$up_limit`/`$down_limit` (primary), computed `pre_close × (1 ± limit%)` fallback |
| **Limit Tiers** | Single ±9.5% threshold | Multi-tier: Main 10%, ST 5%, ChiNext/STAR 20%, BSE 30% |
| **T+1 Settlement** | Qlib handles internally | Explicit share-level `closeable_amount` tracking |
| **Corporate Actions** | Not supported | Cash dividends (post-tax) + bonus shares |
| **Lot Sizes** | Not enforced | 100-share lots, rounded down |
| **Slippage** | Not configurable | Pluggable: None, Fixed (¥/share), Percentage |
| **Volume Limits** | Not enforced | 25% of daily volume per order (configurable) |
| **IPO Period** | Not modeled | Board-specific no-limit windows (1 or 5 days) |
| **Delistings** | Qlib handles | Force-close at last known price |
| **Stamp Tax** | Fixed 0.15% combined rate | Date-aware: 0.1% → 0.05% (2023-08-28) |
| **Output** | Qlib report + positions | 5 DataFrames + 21 JQ-compatible metrics |
| **Best For** | Rapid signal screening, multi-signal compare | Strategy validation, JQ parity checks |

---

## 1. Vectorized Engine (`vectorized/`)

Production-quality Qlib wrapper. Reads `config.yaml` for paths and risk parameters.

### Quick Start

```python
from src.backtest_engine.vectorized import VectorizedBacktester

bt = VectorizedBacktester()
result = bt.run(
    predictions=signal_df,           # MultiIndex(datetime, instrument)
    start_time="2020-01-01",
    end_time="2023-12-31",
    benchmark="000300_SH",           # underscore format, NOT 'SH000300'
    topk=50, n_drop=5,
    only_tradable=False,
    forbid_all_trade_at_limit=True,
    exchange_kwargs={"deal_price": "open"},
)
print(result.summary)
```

### `run()` Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `predictions` | DataFrame/Series | *required* | Scores with `MultiIndex(datetime, instrument)` |
| `start_time` | str | *required* | Backtest start date, e.g. `"2020-01-01"` |
| `end_time` | str | *required* | Backtest end date |
| `benchmark` | str | `"000300_SH"` | Benchmark index code (underscore format) |
| `account` | float | `1e9` | Initial capital in ¥ |
| `topk` | int | `50` | Number of top stocks to hold |
| `n_drop` | int | `5` | Stocks to rotate per rebalance |
| `exchange_kwargs` | dict | A-share defaults | Override exchange config |
| `strategy_type` | str | `"topk_dropout"` | `"topk_dropout"` or `"weight_strategy"` |
| `hold_thresh` | int | `1` | Minimum holding periods |
| `only_tradable` | bool | `False` | Only trade tradable stocks |
| `forbid_all_trade_at_limit` | bool | `False` | Cancel ALL trades when any target is at limit |

> **Research convention:** For daily-strategy research, set execution parameters explicitly and prefer `deal_price='open'`, `only_tradable=False`, and `forbid_all_trade_at_limit=True`. The current code defaults for `deal_price` and `forbid_all_trade_at_limit` are convenience values and should not be relied on for production-style research.

### Default A-Share Exchange Config

```python
{
    "freq": "day",
    "limit_threshold": ("Ge($pct_chg, 9.5)", "Le($pct_chg, -9.5)"),  # 涨跌停 ±9.5%
    "deal_price": "close",
    "open_cost": 0.0005,          # 买入佣金 0.05%
    "close_cost": 0.0015,         # 卖出佣金+印花税 0.15%
    "min_cost": 5,                # 最低佣金 ¥5
}
```

> **NOTE on `limit_threshold`**: Uses Qlib expression syntax with `$pct_chg` (Tushare percentage field, e.g. 9.5 = 9.5%). The `Ge`/`Le` operators are Qlib's built-in comparison functions. Do NOT use Python comparison operators (`>=`, `<=`) — `Feature` objects have no `__ge__` method.

### `BacktestResult` (Vectorized)

| Attribute | Type | Description |
|-----------|------|-------------|
| `report` | DataFrame | Daily return, cost, bench, turnover |
| `positions` | dict | Daily holdings |
| `indicators` | dict | Qlib trading indicators |
| `summary` | dict | Lazily computed: Sharpe, Sortino, MDD, win rate, IR, etc. |
| `config` | dict | Backtest configuration used |

---

## 2. Event-Driven Engine (`event_driven/`)

A realistic share-level backtester for China A-shares that runs independently of Qlib's backtest infrastructure while using Qlib as its **data layer** for PIT-correct feature retrieval. Designed for JoinQuant-compatible strategy validation with precise modeling of T+1 settlement, multi-tier price limits, corporate actions, and date-aware transaction costs.

### Quick Start

```python
from src.backtest_engine.event_driven import (
    EventDrivenBacktester, Strategy, BacktestContext, Order,
)

class SmallCapRotation(Strategy):
    def initialize(self, ctx: BacktestContext):
        self.g.rebalance_days = 5
        self.g.day_count = 0

    def before_market_open(self, ctx: BacktestContext) -> list[Order]:
        self.g.day_count += 1
        if self.g.day_count % self.g.rebalance_days != 1:
            return []

        orders = []
        # Sell all existing positions
        for code in list(ctx.portfolio.positions.keys()):
            orders.append(Order(code, 'sell', reason='rebalance'))

        # Buy top 10 by signal from prev_day_data
        # (strategy logic here)
        return orders

bt = EventDrivenBacktester(data_dir='e:/量化系统/data')
result = bt.run(
    strategy=SmallCapRotation(),
    start_time='2023-01-01',
    end_time='2025-12-31',
    benchmark='000852.SH',      # CSI 1000
    account=100_000,
    preload_fields=['$close', '$open', '$vol', '$amount', '$pre_close',
                    '$high', '$low', '$total_mv'],
)
print(pd.Series(result.summary).to_string())
```

### `EventDrivenBacktester.run()` Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy` | Strategy | *required* | Strategy instance implementing the lifecycle |
| `start_time` | str | *required* | Start date (`'YYYY-MM-DD'`) |
| `end_time` | str | *required* | End date (`'YYYY-MM-DD'`) |
| `benchmark` | str | `None` | Benchmark index code (e.g. `'000852.SH'`). Reads from `data/market/index/` |
| `account` | float | `100_000` | Initial cash in ¥ |
| `exchange_config` | CostConfig | A-share defaults | Custom cost configuration |
| `slippage` | SlippageModel | `NoSlippage()` | Slippage model (`NoSlippage`, `FixedSlippage`, `PctSlippage`) |
| `volume_limit` | float | `0.25` | Max fraction of daily volume per order |
| `preload_fields` | list[str] | `None` | Qlib fields to pre-cache for the entire date range (e.g. `['$close', '$total_mv']`) |

---

## Module Deep-Dive

### 2.1 Data Feeder (`data_feeder.py`)

The `QlibDataFeeder` is the PIT-correct data backbone. It initializes Qlib, loads the trading calendar, and provides all market/fundamental data to the engine.

#### Point-in-Time (PIT) Guarantee

The feeder provides PIT correctness through a **two-layer architecture**:

```text
Layer 1: Qlib .bin Backend (built by build_qlib_backend.py)
  ├── Market data: direct daily OHLCV (inherently PIT)
  └── Fundamental data: PIT-aligned via 3-step process:
      1. ann_date alignment: merge_asof(direction='backward')
         → uses announcement date, NOT report end_date
      2. shift(1): prevent intraday lookahead
         → data visible only from the NEXT trading day
      3. Forward-fill: carry last known value across trading days
         → no gaps between quarterly announcements

Layer 2: QlibDataFeeder (runtime)
  ├── D.features(): retrieves PIT-correct data from .bin files
  ├── preload_features(): batch-caches entire date range in memory
  └── get_features(): O(1) cache lookup or fallback to D.features()
```

> **Key Guarantee**: When the strategy queries `$n_income_attr_p` on 2024-01-15, it sees the value from the most recent earnings report whose `ann_date` is **before** 2024-01-14 (due to `shift(1)`). It can never see future announcements.

#### API Reference

| Method | Description |
|--------|-------------|
| `__init__(data_dir, qlib_dir?, stock_basic_path?)` | Initialize Qlib, load calendar and stock_basic |
| `preload_features(index_name, fields, start, end)` | Bulk-cache features for fast backtesting |
| `get_features(instruments, fields, start, end)` | Get PIT features (cache-first, then D.features fallback) |
| `get_index_constituents(index_name, date)` | PIT-correct index members (prevents survivorship bias) |
| `get_trading_calendar(start, end)` | List of trading days in range |
| `get_prev_trading_day(date)` | Previous trading day |
| `get_next_trading_day(date)` | Next trading day |
| `is_trading_day(date)` | Check if date is a trading day |
| `count_trading_days(start, end)` | Count trading days (inclusive) |
| `get_stock_basic()` | Full stock_basic reference table |

#### Code Format Conversion

The feeder bridges two naming conventions:

| Context | Format | Example |
|---------|--------|---------|
| Qlib internal | Underscore | `000001_SZ` |
| Tushare / Strategy / Portfolio | Dot | `000001.SZ` |

All public APIs accept and return **Tushare-format** codes. Conversion is handled internally via `_to_qlib_code()` and `_to_tushare_code()`.

#### Performance Optimization

Without preloading, each day calls `D.features()` for the full universe — this is extremely slow (~5+ minutes for 1 year). The `preload_features()` method solves this:

```python
# In EventDrivenBacktester.run():
feeder.preload_features('all', preload_fields, start_time, end_time)
# One bulk D.features() call → cached DataFrame → O(1) slicing per day
# Result: 1-year backtest drops from >5 min to ~24 seconds
```

---

### 2.2 Engine (`engine.py`)

The `BacktestEngine` orchestrates the daily simulation loop.

#### Daily Simulation Flow

```text
For each trading day in calendar:
┌──────────────────────────────────────────────────────────┐
│ 1. portfolio.start_new_day()                             │
│    → T+1 unlock: all shares become closeable             │
│    → Reset daily cost/turnover counters                  │
│                                                          │
│ 2. corp_action_handler.process(date, portfolio)          │
│    → Credit cash dividends (post-tax, per-share × qty)   │
│    → Add bonus shares (stk_div rate × existing shares)   │
│                                                          │
│ 3. _handle_delistings()                                  │
│    → Force-close positions missing from today's universe  │
│    → Uses prev_day close or avg_cost as liquidation price │
│                                                          │
│ 4. Phase 1: before_market_open (pre_open)                │
│    → Strategy sees prev_day_data only                    │
│    → Orders filled at today's OPEN price                 │
│    → Sells processed before buys                         │
│                                                          │
│ 5. Phase 2: on_bar (EOD)                                 │
│    → Strategy sees full OHLCV for today                  │
│    → Orders filled at today's CLOSE price                │
│    → Sells processed before buys                         │
│                                                          │
│ 6. Phase 3: after_market_close                           │
│    → Bookkeeping only, no orders                         │
│                                                          │
│ 7. _record_day()                                         │
│    → Snapshot portfolio value, cash, positions            │
│    → Per-stock: shares, weight, unrealized P&L            │
└──────────────────────────────────────────────────────────┘
```

#### Order Execution Pipeline

Within each phase, orders follow a strict pipeline:

```text
Orders from strategy
        │
  ┌─────┴─────┐
  │  Separate  │
  │ sells/buys │
  └─────┬─────┘
        │
  SELLS FIRST (frees cash)
  │ for each sell:
  │  ├── Check: stock in day_data? (else BLOCKED: delisted)
  │  ├── Check: exchange.can_sell()? (suspension, limit-down)
  │  ├── Check: portfolio.can_sell()? (T+1 closeable)
  │  ├── Volume cap: min(target, max_sellable, closeable)
  │  ├── Slippage adjustment on fill price
  │  ├── Date-aware stamp tax (0.1% pre-2023/08/28, 0.05% after)
  │  └── portfolio.sell() → cash += net_proceeds
  │
  THEN BUYS
  │ for each buy:
  │  ├── Check: stock in day_data?
  │  ├── Check: exchange.can_buy()? (suspension, limit-up, IPO)
  │  ├── Volume cap: min(target_value, max_buyable_value)
  │  ├── Slippage adjustment on fill price
  │  ├── Lot-size rounding (100-share lots, rounded down)
  │  ├── Cash sufficiency check (auto-reduce lots if needed)
  │  └── portfolio.buy() → cash -= (trade_value + commission)
  │
  All orders logged to _order_log (FILLED or BLOCKED + reason)
```

#### `BacktestResult` (Event-Driven)

The result contains **5 DataFrames** for comprehensive post-hoc analysis:

| DataFrame | Index | Key Columns | Description |
|-----------|-------|-------------|-------------|
| `report` | date | return, cost, bench, turnover, total_value, cash, market_value, n_positions | Daily portfolio-level metrics |
| `trades` | — | date, code, direction, shares, price, value, cost, cash_after, reason | Every executed (FILLED) trade |
| `order_log` | — | date, code, direction, status, shares, price, value, cost, detail, reason | All orders including BLOCKED with rejection reason |
| `daily_holdings` | — | date, code, shares, closeable, avg_cost, market_price, market_value, weight, unrealized_pnl, pnl_pct | Per-stock daily snapshots |
| `corporate_actions` | — | date, code, type, per_share/rate, shares, total | Dividends and bonus shares credited |

#### Summary Metrics (21 JQ-Compatible)

The `result.summary` property computes 21 metrics matching JoinQuant format:

| Metric | Key | Description |
|--------|-----|-------------|
| 策略收益 | Total Return | Cumulative portfolio return |
| 策略年化收益 | CAGR | Compound annual growth rate |
| 基准收益 | Benchmark Return | Cumulative benchmark return |
| 超额收益 | Excess Return | Strategy minus benchmark |
| 阿尔法 | Alpha | CAPM alpha |
| 贝塔 | Beta | CAPM beta |
| 夏普比率 | Sharpe | Risk-adjusted return (rf=3%) |
| 索提诺比率 | Sortino | Downside-risk-adjusted return |
| 信息比率 | Information Ratio | Excess return per tracking error |
| 最大回撤 | Max Drawdown | Peak-to-trough decline |
| 最大回撤区间 | DD Period | Start/end dates of max DD |
| 超额最大回撤 | Excess Max DD | Max DD of excess returns |
| 胜率 | Win Rate | % of positive-return days |
| 日胜率 | Daily Win Rate | Same as above (explicit) |
| 盈亏比 | P/L Ratio | Avg win / avg loss |
| 盈利次数 | Win Count | Days with positive return |
| 亏损次数 | Loss Count | Days with negative return |
| 策略波动率 | Strategy Vol | Annualized std of returns |
| 基准波动率 | Benchmark Vol | Annualized std of benchmark |
| 日均超额收益 | Avg Daily Excess | Mean daily excess return |
| 超额夏普 | Excess Sharpe | Sharpe of excess returns |

---

### 2.3 Exchange (`exchange.py`)

The `Exchange` class simulates real A-share market microstructure.

#### Transaction Costs (`CostConfig`)

| Field | Default | Description |
|-------|---------|-------------|
| `buy_commission` | 0.025% | Commission on buy orders |
| `sell_commission` | 0.025% | Commission on sell orders |
| `stamp_tax` | 0.05% | Stamp tax after 2023-08-28 |
| `stamp_tax_pre_20230828` | 0.10% | Stamp tax before 2023-08-28 |
| `min_commission` | ¥5 | Minimum per-trade commission |

> **Date-Aware Stamp Tax**: The stamp tax rate changed from 0.1% to 0.05% on 2023-08-28 per State Council decree. The engine applies the correct rate based on trade date, not a static approximation.

#### Multi-Tier Price Limits

| Board | Prefix | Limit | Effective |
|-------|--------|-------|-----------|
| Main Board (主板) | 00/60 | ±10% | Always |
| ST/\*ST | Any | ±5% | When flagged in `st_stocks.txt` |
| ChiNext (创业板) | 300/301 | ±10% → ±20% | ±20% since 2020-08-24 |
| STAR (科创板) | 688/689 | ±20% | Since 2019-07-22 launch |
| BSE (北交所) | 83/87/43/92 | ±30% | Always |

Limit prices are resolved by `Exchange.resolve_limit_prices()`: **primary** source is Tushare's published `$up_limit` / `$down_limit` (the exchange's own daily limit prices, carrying the exact fen-rounding, ex-rights adjustment, and special regimes such as the main-board IPO-first-day ±44% rule); **fallback** (when those fields are absent/NaN — e.g. BSE 2021-launch names, IPO no-limit days, a few legacy stocks) is the computed band `limit_up = round_half_up(pre_close × (1 + limit_pct), 2)`. Comparison uses a ±0.005 tolerance (half a 分). The fields are in `ENGINE_REQUIRED_FIELDS` so formal runs preload them; `stk_limit` is `approved` in the field registry (promoted 2026-06-02). Coverage/value audit: `workspace/scripts/diag_stk_limit_coverage.py`.

#### Tradability Rules

| Check | Buy | Sell |
|-------|-----|------|
| Suspended (`vol == 0`) | ❌ Blocked | ❌ Blocked |
| Limit-up (`close == limit_up`) | ❌ Blocked (no sellers) | ✅ Allowed |
| Limit-down (`close == limit_down`) | ✅ Allowed | ❌ Blocked (no buyers) |
| IPO no-limit period | ✅ Override: buyable even at limit-up | N/A |

#### IPO No-Limit Windows

| Board | No-Limit Period |
|-------|-----------------|
| Main Board (沪深主板) | Listing day only (1 day) |
| ChiNext post-reform | First 5 trading days |
| STAR (科创板) | First 5 trading days |
| BSE (北交所) | Listing day only (1 day) |

#### Slippage Models

```python
# No slippage (default)
slippage = NoSlippage()

# Fixed spread per share (¥0.02, like JoinQuant)
slippage = FixedSlippage(spread=0.02)     # buy: price + 0.02, sell: price - 0.02

# Percentage-based (0.1%)
slippage = PctSlippage(rate=0.001)        # buy: price × 1.001, sell: price × 0.999
```

#### Volume Limits

Each order is capped at `volume_limit` (default 25%) of the stock's daily volume:
- **Buy**: `max_buyable_value = vol × 100 × 0.25 × open_price`
- **Sell**: `max_sellable_shares = vol × 100 × 0.25`

> Note: `vol` in the data is in 手 (lots of 100 shares), so `vol × 100` = actual shares.

#### ST Detection

ST status is loaded from `data/qlib_data/instruments/st_stocks.txt` (Qlib instrument format with tab-delimited date ranges). The feeder converts codes on load. `is_st(code, date)` performs a range check against all ST periods for the stock.

---

### 2.4 Portfolio (`portfolio.py`)

The `Portfolio` class provides share-level position tracking with T+1 enforcement.

#### T+1 Settlement System

```text
Day 1 (Buy): portfolio.buy('000001.SZ', 10.0, 10000, date, lot_size=100)
  → Position created: shares=1000, closeable_amount=0
  → Cannot sell: closeable=0

Day 2 (start_new_day): position.start_new_day()
  → closeable_amount = shares = 1000
  → Can now sell up to 1000 shares

Day 2 (Buy more): portfolio.buy('000001.SZ', 11.0, 5500, date, lot_size=100)
  → shares=1500, closeable_amount=1000 (new 500 locked)
  → avg_cost recalculated: (1000×10 + 500×11) / 1500 = 10.33

Day 3 (start_new_day):
  → closeable_amount = 1500 (all unlocked)
```

#### Position Tracking (`Position` dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `code` | str | Tushare ts_code |
| `shares` | int | Total shares held |
| `closeable_amount` | int | Shares sellable today (T+1) |
| `avg_cost` | float | Volume-weighted average entry price |
| `latest_entry_date` | Timestamp | Date of most recent purchase |

#### Buy Logic Details

1. Compute lots: `max_lots = int(target_value / (price × lot_size))`
2. Calculate cost: `max(trade_value × commission, min_commission)`
3. Check cash: if `trade_value + cost > cash`, reduce lots until affordable
4. Deduct: `cash -= (trade_value + cost)`
5. Create/update position with `closeable_amount=0` for new shares

#### Sell Logic Details

1. Cap at `closeable_amount` (T+1 enforcement)
2. Commission: `max(trade_value × commission, min_commission)`
3. Stamp tax: `trade_value × stamp_rate` (date-aware)
4. Net proceeds: `trade_value - commission - stamp`
5. Credit: `cash += net_proceeds`
6. Delete position if `shares == 0`

---

### 2.5 Strategy (`strategy.py`)

Abstract base class with a **JoinQuant-style lifecycle**. Strategies implement trading logic by overriding lifecycle methods and returning `Order` objects.

#### Lifecycle

```text
┌─────────────────────────────────────────────────┐
│ initialize(context)         ← Once, before Day 1│
│   Set up self.g (persistent state namespace)    │
├─────────────────────────────────────────────────┤
│ FOR EACH TRADING DAY:                           │
│                                                 │
│ before_market_open(context)  ← Phase 1          │
│   • Sees: prev_day_data ONLY (no today's data)  │
│   • Returns: list[Order] → filled at OPEN       │
│                                                 │
│ on_bar(context)              ← Phase 2          │
│   • Sees: full today's OHLCV                    │
│   • Returns: list[Order] → filled at CLOSE      │
│   • Use for: stop-loss, EOD rebalance           │
│                                                 │
│ after_market_close(context)  ← Phase 3          │
│   • Bookkeeping only, no orders                 │
│   • Update self.g counters/state                │
└─────────────────────────────────────────────────┘
```

#### `BacktestContext` Fields

| Field | Type | When Available | Description |
|-------|------|---------------|-------------|
| `date` | Timestamp | Always | Current trading date |
| `day_data` | DataFrame | Phase 2+ | Full OHLCV for all stocks today |
| `day_data_indexed` | DataFrame | Phase 2+ | Same, indexed by `ts_code` for O(1) lookup |
| `prev_day_data` | DataFrame | Always | Yesterday's full data |
| `portfolio` | Portfolio | Always | Portfolio instance (cash, positions) |
| `exchange` | Exchange | Always | Exchange rules (limits, costs, ST) |
| `feeder` | QlibDataFeeder | Always | Data feeder for ad-hoc queries |
| `trading_day_index` | int | Always | 0-based day count since start |
| `total_days` | int | Always | Total trading days in backtest |
| `phase` | str | Always | `'pre_open'`, `'on_bar'`, or `'after_close'` |

#### `Order` Fields

| Field | Type | Description |
|-------|------|-------------|
| `code` | str | Stock ts_code (e.g., `'000001.SZ'`) |
| `direction` | str | `'buy'` or `'sell'` |
| `target_value` | float | Target ¥ amount for buys |
| `target_shares` | int | Shares to sell (None = sell all closeable) |
| `reason` | str | Audit trail reason string |

#### Persistent State (`self.g`)

The `self.g` attribute is a `SimpleNamespace` that persists across trading days, equivalent to JoinQuant's `g` object:

```python
class MyStrategy(Strategy):
    def initialize(self, ctx):
        self.g.rebalance_days = 5
        self.g.custom_universe = []
        self.g.day_count = 0
```

---

### 2.6 Corporate Actions (`corporate_actions.py`)

Handles cash dividends and bonus shares (送股 + 转增股) on ex-dates.

#### Data Source

```text
data/corporate/dividends/dividends_{year}.parquet
  └── 20 files, partitioned by end_date year (2007–2026)
  └── Filtered: div_proc == '实施' AND ex_date IS NOT NULL
```

#### Processing

Called **once per trading day, before any trading**:

| Action Type | Calculation | Effect |
|-------------|-------------|--------|
| Cash dividend | `cash_div_tax × shares` | `portfolio.credit_cash(amount)` |
| Bonus shares | `int(shares × stk_div)` | `position.shares += new`, `avg_cost /= (1 + rate)` |

> **Units**: All per-share values (NOT per-10-shares). `stk_div = stk_bo_rate + stk_co_rate` (verified across 4,153 rows). Cash dividends use `cash_div_tax` (post-tax amount).

> **Bonus Share Availability**: Bonus shares are immediately closeable (no T+1 lock), matching real exchange rules where bonus shares from corporate actions are available for trading on the ex-date.

---

## Cross-Module Relationships

```text
                    ┌───────────────────┐
                    │  config.yaml      │
                    │  (data paths,     │
                    │   risk params)    │
                    └────────┬──────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    alpha_research     data_infra     Qlib .bin Backend
    (factor signals)   (Parquet)      (PIT-aligned)
              │              │              │
              │         ┌────┴────┐         │
              │         │         │         │
              ▼         ▼         ▼         │
         VectorizedBacktester  EventDrivenBacktester
              │                     │       │
              │              ┌──────┘       │
              │              ▼              │
              │        QlibDataFeeder ──────┘
              │              │
              │         ┌────┴────┐
              │         ▼         ▼
              │     Exchange  Portfolio
              │         │         │
              └────┬────┘         │
                   ▼              │
              BacktestResult ◄────┘
                   │
                   ▼
            result_analysis
            ├── BacktestReport
            ├── metrics.py
            └── plotters.py
```

> **RULE**: Always use `src.result_analysis` for performance evaluation. Do NOT write custom metric functions in notebooks. If a metric is missing, add it to `metrics.py`.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `qlib` | Data backend (.bin), vectorized backtest, D.features() |
| `pandas`, `numpy` | Data manipulation |
| `pyyaml` | Config loading |

## Data Dependencies

| File/Directory | Used By | Format |
|----------------|---------|--------|
| `data/qlib_data/` | QlibDataFeeder, VectorizedBacktester | Qlib .bin |
| `data/reference/stock_basic.parquet` | QlibDataFeeder (IPO dates, market type) | Parquet |
| `data/qlib_data/instruments/st_stocks.txt` | Exchange (ST detection) | Tab-delimited text |
| `data/corporate/dividends/` | CorporateActionHandler | Parquet (yearly) |
| `data/market/index/index_{code}.parquet` | BacktestEngine (benchmark) | Parquet |
| `config.yaml` | VectorizedBacktester (qlib_data_dir, exchange) | YAML |
