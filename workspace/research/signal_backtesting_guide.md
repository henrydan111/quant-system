# Signal Construction & Backtesting Standards

Standards and procedures for building quantitative signals and running backtests in this system. These rules apply to ALL strategies — factor-based, ML-based, event-driven, or hybrid.

---

## 1. Pipeline Architecture

Every backtest must follow this strict 4-layer pipeline. Layers execute in order; no layer may depend on a downstream layer's output.

```
Layer 1: Factor Computation   →  ALL stocks, ALL dates, no filtering
Layer 2: Universe Selection   →  Boolean mask on Layer 1 output, no row drops
Layer 3: Signal Construction  →  Rank/score within masked sub-universe + forward-fill
Layer 4: Execution            →  Qlib handles tradability, limits, and order generation
```

### 1.1 Layer 1: Factor Computation

**Scope**: The full A-share market (`market='all'`), all trading dates.

**Index convention**: Throughout Layers 1–3 the DataFrame uses a `(instrument, datetime)` MultiIndex. `groupby(level=0)` groups by instrument (for time-series ops: `pct_change`, `ffill`); `groupby(level=1)` groups by date (for cross-sectional ops: `rank`). The final signal is swapped to `(datetime, instrument)` in Layer 3 to match Qlib's expected format.

**Rules**:

1. **Compute all factors on `market='all'` before any universe filtering.** This ensures:
   - Lookback-based features (e.g., 250d return) have the stock's full price history regardless of when it entered a sub-universe.
   - Cross-sectional statistics (percentiles, z-scores, industry neutralization) are computed against the full market distribution.
   - One factor table can serve multiple strategies.

2. **Never use a sub-universe instrument list for lookback features.** `D.features(sub_instruments, ['$close'], ...)` returns data only for dates the stock is a member of that sub-universe. A 250-day lookback on a stock that joined the sub-universe 60 days ago returns NaN.

3. **Use Qlib bin features for raw data.** Features like `$total_mv`, `$revenue_q`, `$close` are pre-stored in Qlib bins with PIT alignment. Load them directly rather than re-deriving from parquet.

4. **Derive computed features from raw features within the same full-universe DataFrame.** Examples:
   ```python
   all_instruments = D.instruments(market='all')
   df = D.features(all_instruments, ['$close', '$total_mv', '$revenue_q', ...],
                    start_time=START, end_time=END)
   df['return_250d'] = df.groupby(level=0)['close'].pct_change(250)
   df['ret_pctrank'] = df.groupby(level=1)['return_250d'].rank(pct=True)
   ```

5. **Memory**: ~5,000 stocks × 4,400 days × 10 features ≈ 1.7 GB. This fits comfortably in memory (system has 32 GB). Always load the full dataset in one call — chunking along the stock axis breaks cross-sectional features (percentile ranks need all stocks per date), and chunking along the date axis breaks lookback features (250d return needs 250 prior rows).

### 1.2 Layer 2: Universe Selection

**Scope**: Define which stocks are eligible for the strategy on each trading day.

**Rules**:

1. **Universe membership is a boolean mask, never a row drop.**
   ```python
   # ✅ Correct: mask
   st_members = D.features(D.instruments(market='st_stocks'), ['$close'],
                           start_time=START, end_time=END)
   is_member = df.index.isin(st_members.index)

   # ❌ Wrong: drop
   df = df.loc[df.index.isin(st_members.index)]  # destroys non-member rows
   ```

2. **Screening conditions are additional boolean masks layered on top of membership.**
   ```python
   has_data = df['total_mv'].notna() & df['revenue_q'].notna()
   passes_return_filter = df['ret_pctrank'].le(0.75)
   is_eligible = is_member & has_data & passes_return_filter
   ```

3. **DO NOT filter by tradability (`vol > 0`).** A suspended stock still has valid factor values in Qlib bins (market cap, revenue are forward-filled by Qlib automatically). It should be ranked alongside tradable stocks. Qlib's Exchange natively blocks all buy/sell orders for suspended stocks (where `$close` is NaN) — see Layer 4.
   ```python
   # ✅ Correct: rank all eligible stocks, including suspended
   is_rankable = is_eligible

   # ❌ Wrong: excluding suspended stocks from ranking
   is_rankable = is_eligible & (df['vol'] > 0)
   ```

4. **Preserve all rows in the DataFrame.** Non-member and non-eligible rows stay in the DataFrame with their factor values intact. This allows re-filtering without recomputation.

### 1.3 Layer 3: Signal Construction

**Scope**: Score or rank all eligible stocks in the sub-universe. Produce a signal Series for Qlib.

**Rules**:

1. **Rank within the sub-universe, not the full market.** Cross-sectional ranks for signal construction use only stocks that are `is_rankable` (= `is_eligible`) on each date. Since suspended stocks are included in `is_eligible` (they have valid forward-filled factor values), they get a fresh rank each day.
   ```python
   df.loc[is_rankable, 'rank_mv'] = (
       df[is_rankable].groupby(level=1)['total_mv']
       .rank(pct=True, ascending=True)
   )
   df['signal'] = df['rank_mv'] + df['rank_rev']  # NaN for non-eligible only
   ```
   Rationale: The ranking determines relative desirability within the investment pool. Ranking ST stocks against all stocks compresses scores into a narrow band, increasing ties and noise.

2. **Forward-fill the signal for edge cases only.** Since suspended stocks are now ranked directly (they have valid factor values in Qlib bins), forward-fill is only needed for stocks that temporarily fail `has_data` (e.g., a stock missing one quarter's revenue report).
   ```python
   df.loc[is_member, 'signal'] = (
       df.loc[is_member, 'signal'].groupby(level=0).ffill()
   )
   ```
   This is a safety net, not the primary mechanism. Most stocks will have a fresh signal each day.

3. **Extract the final signal for universe members only.**
   ```python
   final_signal = df.loc[is_member, 'signal'].dropna()
   final_signal = final_signal.swaplevel().sort_index()  # (datetime, instrument)
   ```
   The `.dropna()` only drops stocks that never had any signal (e.g., newly listed with no factor history).

4. **Signal values must be comparable across dates.** If using percentile ranks (0–1), the signal is naturally bounded. If using raw factor values or ML predictions, ensure the signal is cross-sectionally normalized per date to avoid scale drift.

5. **For ML-based strategies**, the model prediction IS the signal. Apply the same forward-fill rule for stocks that can't be scored on a given day.

### 1.4 Layer 4: Execution

**Scope**: Qlib's backtest engine handles order generation, tradability checks, and portfolio management.

**Rules**:

1. **Never encode tradability logic in the signal.** Don't set signal=0 for suspended stocks or stocks at limit. Qlib's Exchange natively handles suspension and limits:
   - `Exchange._update_limit()` detects suspension via `$close.isna()` and sets `limit_buy=True`, `limit_sell=True`
   - `is_stock_tradable()` combines suspension + price limit checks
   - TopkDropout's sell/buy loops call `is_stock_tradable()` and skip untradable stocks
   - This separation means the signal layer is purely about desirability, not executability

2. **Full parameter reference** — every argument of `VectorizedBacktester.run()` is listed below. All must be set explicitly in your notebook; do not rely on defaults.

   **Strategy parameters:**

   | Parameter | Type | Recommended | Description |
   |-----------|------|-------------|-------------|
   | `predictions` | `pd.Series` | — | Signal with `MultiIndex(datetime, instrument)`. Higher = more desirable. |
   | `start_time` | `str` | — | Backtest start date, e.g. `'2016-01-02'`. |
   | `end_time` | `str` | — | Backtest end date, e.g. `'2025-12-31'`. |
   | `strategy_type` | `str` | `'topk_dropout'` | `'topk_dropout'` (rank-based) or `'weight_strategy'` (weight-based). |
   | `topk` | `int` | Strategy-dependent | Number of top-ranked stocks to hold. |
   | `n_drop` | `int` | Strategy-dependent | Max stocks rotated per rebalance day. Controls turnover. |
   | `hold_thresh` | `int` | Strategy-dependent | Min holding days before a position is eligible for sale (see §1.5). |
   | `only_tradable` | `bool` | `False` | If `True`, pre-filters ranked stocks by tradability. Use `False` — let Qlib's execution loops handle it (see Rule 1). |
   | `forbid_all_trade_at_limit` | `bool` | `True` | If `True`, blocks ALL trades (buy+sell) when a stock is at price limit. See §2.2/§2.3. |
   | `benchmark` | `str` | Strategy-dependent | Benchmark index in Qlib format: `'{code}_{exchange}'` (e.g. `'000001_SH'`). |
   | `account` | `float` | `1_000_000_000` | Initial capital in CNY. Default ¥1B is large enough to avoid lot-size artifacts. |
   | `custom_weights` | `pd.DataFrame` | `None` | Only for `strategy_type='weight_strategy'`. DataFrame with `[datetime, instrument, weight]`. |

   **Exchange parameters** (passed via `exchange_kwargs` dict):

   | Parameter | Type | Recommended | Description |
   |-----------|------|-------------|-------------|
   | `deal_price` | `str` | `'open'` | Price at which orders fill. Use `'open'` for daily strategies (signal computed on D, fill at D+1 open). Never use `'close'` — it implies same-day signal+fill, which is forward-looking. `'$vwap'` is realistic for intraday. |
   | `limit_threshold` | `tuple[str,str]` | Per-segment | Expression tuple for limit-up/limit-down detection. Must match the market segment (see Rule 3 below). |
   | `open_cost` | `float` | `0.0005` | Buy-side commission rate (0.05%). |
   | `close_cost` | `float` | `0.0015` | Sell-side cost rate (0.05% commission + 0.1% stamp tax). |
   | `min_cost` | `float` | `5` | Minimum cost per trade in CNY (¥5). |
   | `freq` | `str` | `'day'` | Trading frequency. Currently only `'day'` is supported. |

3. **Set `limit_threshold` per market segment:**

   | Market | Limit | Qlib Expression |
   |--------|-------|-----------------|
   | Main board | ±10% | `('Ge($pct_chg, 9.5)', 'Le($pct_chg, -9.5)')` |
   | ST stocks | ±5% | `('Ge($pct_chg, 4.5)', 'Le($pct_chg, -4.5)')` |
   | ChiNext/STAR (post-2020) | ±20% | `('Ge($pct_chg, 19.5)', 'Le($pct_chg, -19.5)')` |

   Use a slight margin (e.g., 9.5 instead of 10) to avoid floating-point edge cases.

   > [!IMPORTANT]
   > Qlib's `Exchange` accepts a single `limit_threshold` tuple per backtest. If your universe spans multiple market segments (e.g., a mix of ST and main-board stocks), you cannot apply different thresholds per stock natively. Workarounds:
   > - **Option A**: Run separate backtests per segment with the correct threshold, then merge results.
   > - **Option B**: Use the most conservative threshold (±5%) for the entire backtest. This over-restricts main-board stocks but avoids false fills.
   > - **Option C**: Subclass `Exchange` to look up the per-stock limit from a mapping. This is the correct long-term solution but requires custom code.

4. **Transaction costs must reflect the actual market:**
   ```python
   exchange_kwargs = {
       'open_cost': 0.0005,   # Buy: ~0.05% commission
       'close_cost': 0.0015,  # Sell: 0.05% commission + 0.1% stamp tax
       'min_cost': 5,         # Minimum ¥5 per trade
   }
   ```

### 1.5 Rebalancing & Holding Period

**Scope**: Control how frequently the portfolio is re-evaluated and how long positions are held.

**Rules**:

1. **`hold_thresh`** sets the minimum number of trading days a position must be held before it becomes eligible for sale. On day `d`, a stock bought on day `d - hold_thresh + 1` or later is locked — even if it falls to the worst-ranked stock.

2. **Interaction with `n_drop`**: TopkDropout sells up to `n_drop` eligible stocks per day. If `hold_thresh` locks most positions, fewer than `n_drop` stocks may be sellable on a given day. This is expected — turnover decreases as `hold_thresh` increases.

3. **If a held stock becomes ineligible** (exits the sub-universe) while still within its holding period, the position is retained until `hold_thresh` expires and the stock falls out of the top-K ranking. It is NOT force-sold before the holding period ends.

4. **Daily signal, periodic rebalance**: The pipeline always produces a daily signal. For strategies that rebalance less frequently (weekly/monthly), restrict order generation to rebalance dates while keeping the daily signal alive:
   ```python
   # Example: weekly rebalance (every Monday)
   rebalance_dates = pd.bdate_range(START_DATE, END_DATE, freq='W-MON')
   # Pass rebalance_dates to strategy or use hold_thresh equivalent
   ```
   Do NOT reduce signal frequency by only computing signals on rebalance dates — Qlib's execution layer needs a daily signal to handle intra-period events (suspensions, limit hits, forced sells).

---

## 2. Corner Case Handling

### 2.1 Suspended Stocks (停牌)

A stock ceases trading for an extended period (days to months).

| Stage | Behavior | Implementation | Rule |
|-------|----------|----------------|------|
| Factor computation | Qlib bins forward-fill `$total_mv`, `$revenue_q` etc. automatically; `$close` becomes NaN, `$vol` = 0 | Automatic via Qlib | §1.1 Rule 3 |
| Universe membership | Remains a member (suspension ≠ delisting) | `st_stocks.txt` unchanged | §1.2 Rule 1 |
| Signal | **Ranked normally** — factor values (market cap, revenue) are still valid via Qlib bin forward-fill | `is_rankable = is_eligible` (no vol>0 filter) | §1.2 Rule 3, §1.3 Rule 1 |
| Execution | Qlib Exchange detects `$close=NaN` → sets `limit_buy=True`, `limit_sell=True` → all orders blocked | Automatic via `Exchange._update_limit()` | §1.4 Rule 1 |
| Portfolio | Position frozen at last known weight and value | Automatic via Qlib | §1.5 Rule 3 |
| Post-resumption | Fresh factor values available; normal trading resumes | Automatic | — |

**How Qlib detects suspension** (source: `Exchange._update_limit()`):
```python
suspended = self.quote_df["$close"].isna()
self.quote_df["limit_buy"] = limit_expr.astype("bool") | suspended
self.quote_df["limit_sell"] = limit_expr.astype("bool") | suspended
```
This means we do NOT need to handle suspension in the signal layer — Qlib's Exchange does it natively.

### 2.2 Limit Up (涨停)

A stock's price reaches its maximum allowable daily increase.

| Stage | `forbid_all_trade_at_limit=True` | `forbid_all_trade_at_limit=False` | Rule |
|-------|----------------------------------|-----------------------------------|------|
| Can BUY? | ❌ No | ❌ No (queue is full; can't get filled) | §1.4 Rule 2 |
| Can SELL? | ❌ No (conservative) | ✅ Yes (buyers in queue want it) | §1.4 Rule 2 |
| Signal | Normal score — limit status is an execution concern | Same | §1.4 Rule 1 |

**Recommendation**: Use `True`. In practice, selling at limit-up is possible but undesirable — the stock is likely to continue rising. Most Chinese platform backtests (果仁, 优矿, 聚宽) default to blocking sells at limit-up.

### 2.3 Limit Down (跌停)

A stock's price reaches its maximum allowable daily decrease.

| Stage | `forbid_all_trade_at_limit=True` | `forbid_all_trade_at_limit=False` | Rule |
|-------|----------------------------------|-----------------------------------|------|
| Can BUY? | ❌ No (conservative) | ✅ Yes (sellers in queue want to sell) | §1.4 Rule 2 |
| Can SELL? | ❌ No | ❌ No (no buyers in queue) | §1.4 Rule 2 |
| Signal | Normal score | Same | §1.4 Rule 1 |

**Recommendation**: Use `True`. Blocking buy at limit-down prevents buying stocks in freefall.

### 2.4 Newly Listed Stocks (新股 / 次新股)

| Concern | Handling | Rule |
|---------|----------|------|
| Lookback features return NaN | Expected — stock has no history. Filter via `has_data` mask. | §1.2 Rule 2 |
| Consecutive limit-up after IPO | `is_stock_tradable()` blocks buying during limit-up streak | §1.4 Rule 1 |
| First tradable day | Stock becomes rankable when all required factors become non-NaN | §1.3 Rule 1 |
| Minimum history requirement | Some strategies should mandate N days of data (e.g., skip stocks listed < 60 days) | §1.2 Rule 2 |

### 2.5 Delisted Stocks (退市)

| Concern | Handling | Rule |
|---------|----------|------|
| Universe membership | Stock is removed from instrument file on delisting date | §1.2 Rule 1 |
| If held at delisting | Position liquidated at last traded price — Qlib handles this | §1.4 Rule 1 |
| Delisting during suspension | Position value goes to zero — represents real-world risk | — |
| Survivorship bias | Qlib bins include delisted stocks, so backtests are survivorship-bias-free as long as the instrument file records the correct active dates | §1.1 Rule 1 |

### 2.6 Sub-Universe Transitions

A stock enters or exits the strategy's sub-universe mid-backtest.

| Event | Signal Behavior | Portfolio Behavior | Rule |
|-------|----------------|-------------------|------|
| **Enters sub-universe** | Signal appears (from NaN to scored) | Eligible for purchase on next rebalance | §1.3 Rule 1 |
| **Exits sub-universe** | Signal stops being produced | If held: signal disappears → Qlib ranks it lowest → sells on next tradable day | §1.4 Rule 1 |
| **Temporarily exits then re-enters** | Forward-fill covers the gap | If held: retained during gap via forward-filled signal | §1.3 Rule 2 |

### 2.7 Missing Fundamental Data

A stock's quarterly report is delayed or restated.

| Concern | Handling | Rule |
|---------|----------|------|
| Revenue or earnings NaN for current quarter | Qlib bins forward-fill the last known quarter's value with PIT alignment | §1.1 Rule 3 |
| Factor computed from missing data | Will be NaN → stock fails `has_data` mask → not rankable but retains forward-filled signal | §1.2 Rule 2, §1.3 Rule 2 |
| Restated reports | Our bins use announcement date priority: if a restatement is filed AFTER the original, it supersedes. No lookahead. | — |

---

## 3. Anti-Patterns to Avoid

### 3.1 Filtering before factor computation

```python
# ❌ WRONG: Drops rows, then computes lookback feature
df = df[df['vol'] > 0]
df['return_250d'] = df.groupby(level=0)['close'].pct_change(250)
```
**Problem**: Rows from suspended days are removed, creating gaps in the time series. `pct_change(250)` then spans more than 250 calendar days, computing an incorrect return.

### 3.2 Dropping NaN rows before ranking

```python
# ❌ WRONG: Drops rows
df = df.dropna(subset=['total_mv', 'revenue_q'])
df['rank'] = df.groupby(level=1)['total_mv'].rank(pct=True)
```
**Problem**: Drops suspended stocks and any stock missing one data field. These rows can never be forward-filled. Use `df.loc[mask, 'rank'] = ...` instead.

### 3.3 Encoding tradability in the signal

```python
# ❌ WRONG: Setting signal to 0 for untradable stocks
signal[signal.index.isin(suspended_stocks)] = 0
```
**Problem**: Qlib interprets 0 as a real (low) score, not as "untradable." The stock will be ranked last and targeted for sell, wasting a sell slot. Let Qlib's Exchange handle tradability.

### 3.4 Mixing ranking scope with filter scope

```python
# ❌ WRONG: Filtering by 250d return (all-market percentile), then
# ranking market_cap within the filtered set
df_filtered = df[df['ret_pctrank_allmarket'] <= 0.75]
df_filtered['rank_mv'] = df_filtered.groupby(level=1)['total_mv'].rank(pct=True)
```
**Problem**: The filtering drops rows, removing factor values needed for forward-fill. Use masks:
```python
# ✅ CORRECT
is_rankable = is_member & (df['ret_pctrank'] <= 0.75) & has_data
df.loc[is_rankable, 'rank_mv'] = df[is_rankable].groupby(level=1)['total_mv'].rank(pct=True)
```

### 3.5 Forgetting forward-fill

```python
# ❌ WRONG: Signal without forward-fill
signal = df.loc[is_rankable, 'composite_score']
```
**Problem**: Suspended stocks vanish from signal. Add:
```python
# ✅ CORRECT
df['signal'] = df['composite_score']
df.loc[is_member, 'signal'] = df.loc[is_member, 'signal'].groupby(level=0).ffill()
signal = df.loc[is_member, 'signal'].dropna()
```

---

## 4. Validation Checklist

Run these checks before trusting any backtest result.

### 4.1 Signal Integrity

- [ ] **Coverage**: Signal exists for ≥95% of (date, stock) pairs in the sub-universe.
   ```python
   # Pair-level coverage: what fraction of (stock, date) member pairs have a signal?
   expected_pairs = is_member.sum()                    # total (stock, date) member pairs
   actual_pairs   = final_signal.notna().sum()          # pairs with a signal value
   print(f'Signal coverage: {actual_pairs / expected_pairs:.1%}')
   ```

- [ ] **No future data**: For any stock on any date, all factor values were publicly available by that date. Verify via PIT alignment (announcement_date, not end_date).

- [ ] **Forward-fill present**: Compare `is_member.sum()` vs `final_signal.notna().sum()`. If they differ significantly, forward-fill is missing.

- [ ] **Ranking stability**: On a sample date, remove 1 stock from the universe and re-rank. The top-K should change by at most 1 stock.

### 4.2 Execution Realism

- [ ] **Transaction costs are non-zero**: Verify `open_cost` and `close_cost` are set.

- [ ] **Limit threshold matches market**: ST stocks use ±5%, not the default ±10%.

- [ ] **Deal price is realistic**: `'open'` for daily strategies; never use `'close'` (implies trading at the close, which is forward-looking in a daily rebalance framework).

- [ ] **Benchmark is appropriate**: Use a relevant index (CSI300, CSI500, or SSE Composite), not a flat zero.

### 4.3 Cross-Validation Against Reference

When replicating a known strategy:

- [ ] **Stock selection overlap**: On 5+ sample dates, compare held stocks against the reference. Expect ≥60% overlap.

- [ ] **Factor value match**: For shared stocks, compare raw factor values (market cap, revenue). They should match within 5%.

- [ ] **Annual return pattern**: Year-by-year returns should have the same sign and similar magnitude as the reference.

---

## 5. Implementation Template

The following is the recommended code structure for any strategy notebook. Lines marked `# ← CUSTOMIZE` are the only parts that change between strategies; everything else is fixed pipeline structure.

```python
import qlib
from qlib.data import D
from qlib.config import REG_CN

# ═══════════════════════════════════════════════════════════
# CONFIGURATION — customize all parameters below
# Every parameter from VectorizedBacktester.run() is listed.
# ═══════════════════════════════════════════════════════════

# --- Date range ---
START_DATE    = '2016-01-02'                           # ← CUSTOMIZE: backtest start
END_DATE      = '2025-12-31'                           # ← CUSTOMIZE: backtest end

# --- Strategy parameters ---
STRATEGY_TYPE = 'topk_dropout'                         # ← CUSTOMIZE: 'topk_dropout' or 'weight_strategy'
TOP_K         = 5                                      # ← CUSTOMIZE: portfolio size
N_DROP        = 1                                      # ← CUSTOMIZE: max stocks rotated per rebalance
HOLD_THRESH   = 1                                      # ← CUSTOMIZE: min holding days (see §1.5)
ONLY_TRADABLE = False                                  # DO NOT CHANGE: Qlib handles tradability (§1.4 Rule 1)
FORBID_LIMIT  = True                                   # Block all trades at price limit (§2.2/§2.3)

# --- Universe & benchmark ---
SUB_UNIVERSE  = 'st_stocks'                            # ← CUSTOMIZE: e.g. 'csi300', 'all'
BENCHMARK     = '000001_SH'                            # ← CUSTOMIZE: Qlib format '{code}_{exchange}'

# --- Capital ---
ACCOUNT       = 1_000_000_000                          # Initial capital ¥1B (avoid lot-size artifacts)

# --- Exchange parameters ---
DEAL_PRICE    = 'open'                                 # ← CUSTOMIZE: 'open' (daily) or '$vwap' (intraday)
LIMIT_THRESH  = ('Ge($pct_chg, 4.5)',                  # ← CUSTOMIZE: must match market segment (§1.4 Rule 3)
                 'Le($pct_chg, -4.5)')                 #     ST=4.5, Main=9.5, ChiNext/STAR=19.5
OPEN_COST     = 0.0005                                 # Buy commission: 0.05%
CLOSE_COST    = 0.0015                                 # Sell: 0.05% commission + 0.1% stamp tax
MIN_COST      = 5                                      # Minimum ¥5 per trade

# ═══════════════════════════════════════════════════════════
# LAYER 1: Factor Computation (full market)
# Index convention: (instrument, datetime) MultiIndex
#   groupby(level=0) = per instrument   (time-series ops)
#   groupby(level=1) = per date         (cross-sectional ops)
# ═══════════════════════════════════════════════════════════
all_instruments = D.instruments(market='all')
df = D.features(all_instruments, [                     # ← CUSTOMIZE: raw features
    '$close', '$adj_factor', '$total_mv', '$revenue_q',
    '$vol', '$pct_chg',
], start_time=START_DATE, end_time=END_DATE)

# Derived factors                                      # ← CUSTOMIZE: computed factors
df['return_250d'] = df.groupby(level=0)['close'].pct_change(250)
df['ret_pctrank'] = df.groupby(level=1)['return_250d'].rank(pct=True)

# ═══════════════════════════════════════════════════════════
# LAYER 2: Universe Selection (masks, no drops)
# ═══════════════════════════════════════════════════════════
sub_members = D.features(
    D.instruments(market=SUB_UNIVERSE), ['$close'],
    start_time=START_DATE, end_time=END_DATE
)
is_member = df.index.isin(sub_members.index)

has_data = df['total_mv'].notna() & df['revenue_q'].notna()  # ← CUSTOMIZE: data requirements
passes_screen = df['ret_pctrank'].le(0.75)                    # ← CUSTOMIZE: screening filters

is_eligible = is_member & has_data & passes_screen
is_rankable = is_eligible  # No vol>0 filter — Qlib handles suspension natively

# ═══════════════════════════════════════════════════════════
# LAYER 3: Signal Construction (rank within sub-universe)
# ═══════════════════════════════════════════════════════════
# ← CUSTOMIZE: ranking logic below
df.loc[is_rankable, 'rank_mv'] = (
    df[is_rankable].groupby(level=1)['total_mv']
    .rank(pct=True, ascending=True)
)
df.loc[is_rankable, 'rank_rev'] = (
    df[is_rankable].groupby(level=1)['revenue_q']
    .rank(pct=True, ascending=True)
)
df['signal'] = df['rank_mv'] + df['rank_rev']          # ← CUSTOMIZE: signal formula

# Forward-fill for suspended/temporarily-filtered stocks (DO NOT CUSTOMIZE)
df.loc[is_member, 'signal'] = (
    df.loc[is_member, 'signal'].groupby(level=0).ffill()
)

# Extract final signal (DO NOT CUSTOMIZE)
final_signal = df.loc[is_member, 'signal'].dropna()
final_signal = final_signal.swaplevel().sort_index()    # → (datetime, instrument)

# ═══════════════════════════════════════════════════════════
# LAYER 4: Execution — ALL parameters shown explicitly
# ═══════════════════════════════════════════════════════════
from src.backtest_engine.vectorized import VectorizedBacktester

bt = VectorizedBacktester(config_path='config.yaml', qlib_dir=QLIB_DIR)
result = bt.run(
    # Signal
    predictions              = final_signal,
    # Date range
    start_time               = START_DATE,
    end_time                 = END_DATE,
    # Strategy
    strategy_type            = STRATEGY_TYPE,
    topk                     = TOP_K,
    n_drop                   = N_DROP,
    hold_thresh              = HOLD_THRESH,
    only_tradable            = ONLY_TRADABLE,
    forbid_all_trade_at_limit = FORBID_LIMIT,
    # Universe & benchmark
    benchmark                = BENCHMARK,
    # Capital
    account                  = ACCOUNT,
    # Exchange
    exchange_kwargs = {
        'freq':              'day',
        'deal_price':        DEAL_PRICE,
        'limit_threshold':   LIMIT_THRESH,
        'open_cost':         OPEN_COST,
        'close_cost':        CLOSE_COST,
        'min_cost':          MIN_COST,
    },
)
```

---

## 6. Glossary

| Term | Definition |
|------|-----------|
| **Factor** | A measurable stock attribute (market cap, revenue, momentum). Computed on the full market. |
| **Signal** | A composite score used to rank stocks for portfolio construction. Computed within the sub-universe. |
| **Universe / Sub-universe** | The set of stocks eligible for the strategy (e.g., all ST stocks). |
| **Membership mask** | A boolean per (stock, date) indicating sub-universe membership. |
| **Tradability** | Whether a stock can be bought/sold on a given day (not suspended, not at limit). |
| **Forward-fill** | Carrying forward the last known signal for stocks temporarily lacking a fresh score. |
| **PIT (Point-in-Time)** | Using only data that was publicly available at each historical date. No future information. |
| **TopkDropout** | Qlib's strategy that holds top-K stocks by signal and rotates up to N per day. |
| **Deal price** | The price at which orders are executed in the backtest (`'open'`, `'close'`, or `'$vwap'`). |
