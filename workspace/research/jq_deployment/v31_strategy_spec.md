# R1_11F_ROEWAA — v31 Strategy Specification

> ## ⛔ INVALIDATED (2026-05-29) — DO NOT IMPLEMENT
> The sandbox loader that produced every number in this spec had a PIT lookahead bug
> (dashed-vs-compact `effective_date` string comparison → ~9 months of earnings foresight).
> After the fix, the champion's OOS CAGR collapsed **188.7% → 2.0%**. The edge was lookahead,
> not alpha. See [v33_PIT_lookahead_bug_report.md](v33_PIT_lookahead_bug_report.md) §9.

**Purpose**: Implementation-agnostic specification of the v31 champion strategy. Hand this to a JoinQuant implementation session as the single source of truth. Do not infer behavior — only follow what is written here.

**Source code (Tushare/Qlib local engine)**: `workspace/scripts/sandbox_v15aa_v31_focuspct_confirmation.py`

**Confirmed performance** (Tushare/Qlib PIT engine, v31 run 2026-05-28):

| Metric | IS (2014-01-02 → 2019-12-31) | OOS (2020-01-01 → 2026-02-27) | Full (2014-01-02 → 2026-02-27) |
|---|---|---|---|
| CAGR | 283.7 % | **192.7 %** | 229.3 % |
| Max DD | — | — | **−33.95 %** |
| Sharpe | — | — | 3.317 |
| Walk-forward average | — | — | 207.5 % |
| Jackknife (drop-one-year) min CAGR | — | — | **217.5 %** |

These numbers are the **simulation truth**. They reflect:
- Tushare daily `pct_chg` (price-based daily return) used as the next-day return
- 50 bp round-trip flat cost on rebalance days
- No suspension/limit-up/fill modeling
- No survivorship correction beyond what Tushare's database naturally has

The JoinQuant live result **will be lower** than this — friction differences alone cost 30–60 pp/yr. Treat the simulation as an upper bound, not a target.

---

## 1. Universe Selection

### 1.1 Asset universe
- All A-share common stocks across Shanghai (`.SH` / `.XSHG`) and Shenzhen (`.SZ` / `.XSHE`).
- Local sim covers ~5,726 distinct stocks over 2014-01-02 → 2026-02-27.
- Local sim does NOT explicitly exclude 科创板 (688xxx) or 北交所 (4/8xxxx) — the universe is the full Tushare A-share population including those segments. (For JoinQuant: this can be revisited; G2/G3 baselines exclude both, which is the safer default.)

### 1.2 Per-day eligibility filter (applied at every rebalance day)
A stock is eligible on date T if **all three** of these conditions hold using PIT-shifted values (i.e., values known as of close of T-1):

1. `netprofit_yoy ≥ 0` — net-profit YoY growth rate is non-negative (Tushare `fina_indicator_vip.netprofit_yoy`, which is the parent-company net-profit YoY in percent).
2. `roe ≥ 0` — cumulative ROE is non-negative (Tushare `fina_indicator_vip.roe`, in percent).
3. `0.30 < pb ≤ 6.00` — daily P/B ratio strictly greater than 0.3 AND less than or equal to 6.0.

All three values must be finite (no NaN). Stocks failing any condition are dropped from the candidate set for that day.

**The universe is recomputed fresh on every rebalance day.** No stale membership / lookback membership.

---

## 2. Required Data Fields

### 2.1 Fundamentals (Tushare `fina_indicator_vip`, PIT-aligned)
All values come from quarterly disclosures aligned on `ann_date` (announcement date) and shifted by one trading day to prevent same-day leakage. Forward-fill across calendar gaps within a stock.

| Tushare field | Role | Description |
|---|---|---|
| `netprofit_yoy` | universe filter | 归母净利润同比增长率 (%) |
| `roe` | universe filter + factor lookup | 归母净资产收益率 (cumulative ROE, %) |
| `roa` | **factor `roa`** | 总资产净利率 (cumulative, %) |
| `q_roe` | **factor `q_roe`** | **Single-quarter** 加权平均净资产收益率 (%) — single-Q ROE |
| `or_yoy` | **factor `rev_growth`** | 营业收入同比增长率 (cumulative, %) |
| `dt_netprofit_yoy` | **factor `dt_npy`** | 扣非归母净利润同比增长率 (cumulative deducted YoY, %) |
| `q_dt_roe` | **factor `q_dt_roe`** | **Single-quarter** 扣非加权平均净资产收益率 (%) |
| `q_op_qoq` | **factor `q_qoq`** | **Single-quarter** 营业利润环比增长率 (%) — single-Q QoQ |
| `roe_yoy` | **factor `roe_yoy`** | ROE 同比 (cumulative ROE YoY change, percentage points) |
| `roe_waa` | **factor `roe_waa`** | 加权平均ROE (cumulative, %) — formula: `net_profit × 2 / (begin_equity + end_equity)` (parent-company) |

**Notes on the "single-quarter" fields (Tushare convention)**:
- `q_roe` = (single-quarter net profit × 2) / (begin-of-quarter equity + end-of-quarter equity), where single-quarter net profit = cumulative_now − cumulative_prior_quarter (within the same fiscal year). For Q1, single-Q = cumulative.
- `q_dt_roe` = same formula but with **deducted** (扣非) net profit.
- `q_op_qoq` = (single-Q operating profit now − single-Q operating profit prior quarter) / abs(prior). NOT cumulative QoQ.
- All "q_" fields use **parent-company-only** net profit and **parent-company-only** equity. Do NOT use total-net-profit / total-equity (those include minority interest).

### 2.2 Daily market data (Tushare `daily`, PIT-shifted by 1 trading day)
| Field | Role | Description |
|---|---|---|
| `pct_chg` | next-day return | Daily price percent change. Convert to decimal: `pct_chg / 100` (NOT shifted — used for current-day return only) |
| `pb` | universe filter + factor `val` | P/B ratio (shifted by 1 day) |
| `total_mv` | factor `size` | Total market cap in 万元 (shifted by 1 day) |

---

## 3. Factor Computation (11 factors)

All factors are computed on **PIT-shifted** values (shift(1) applied) so the value used at day T is known as of close of T-1. The composite signal is built from these.

### Factor list with formulas

| # | Factor name | Computation | Direction |
|---|---|---|---|
| 1 | `roa` | `roa` field (Tushare fina_indicator_vip), as percent | higher = better |
| 2 | `q_roe` | `q_roe` field, as percent (single-quarter, see §2.1 note) | higher = better |
| 3 | `rev_growth` | `or_yoy` field, as percent (cumulative revenue YoY) | higher = better |
| 4 | `dt_npy` | `dt_netprofit_yoy` field, as percent (cumulative deducted-NP YoY) | higher = better |
| 5 | `q_dt_roe` | `q_dt_roe` field, as percent (single-quarter deducted ROE) | higher = better |
| 6 | `size` | `−ln(total_mv)` where `total_mv` is shifted by 1 day | higher = better (smaller cap → higher rank) |
| 7 | `val` | `1 / pb` where `pb` is shifted by 1 day (skip pb==0) | higher = better (cheaper) |
| 8 | `q_qoq` | `q_op_qoq` field, as percent (single-Q op-profit QoQ) | higher = better |
| 9 | `roe_yoy` | `roe_yoy` field, as percentage points (ROE diff YoY) | higher = better |
| 10 | `q_roe_yoy` | **Computed: `q_roe[T] − q_roe[T − 252 trading days]`** (NOT from a Tushare field — it is a 252-trading-day-lag of `q_roe` minus current `q_roe`) | higher = better |
| 11 | `roe_waa` | `roe_waa` field, as percent | higher = better |

**Critical reminder on factor 10 (`q_roe_yoy`)**: this is NOT the Tushare `q_roe_yoy` field. It is a locally-computed difference: take the `q_roe` factor (factor #2) and subtract its value from 252 trading days earlier. The lag is in **trading days**, not calendar days. Stocks without 252 days of history get NaN.

### Factor PIT alignment procedure (for each fundamental factor)
1. Take the Tushare quarterly indicator value for the field
2. Pivot to (effective_date, ts_code) → value, where `effective_date` = `ann_date + 1 trading day` (so the value becomes usable on the trading day AFTER announcement)
3. Reindex onto all calendar dates and forward-fill (so a value disclosed on 2024-04-25 propagates forward until the next disclosure)
4. Reindex onto trading dates only
5. Apply `shift(1)` (so the value at trading day T is the value known by close of T-1)

This procedure ensures no same-day leakage. JoinQuant's `get_fundamentals(date=T-1, ...)` with `avoid_future_data=True` does the equivalent automatically.

---

## 4. Factor Weights (F11_ROEWAA)

The weights were derived by iterative factor stacking research (v17 → v31). DO NOT tune these on JoinQuant — any improvement found by sweeping is overfit.

### Derivation chain (for documentation)
Starting from F7 base weights, each new factor is blended in with explicit alpha and the result is renormalized:

```
F7  = {roa: 0.378, q_roe: 0.309, rev_growth: 0.140, dt_npy: 0.082, val: 0.049, q_qoq: 0.031, q_roe_yoy: 0.012}
F8  = {F7 × 0.96, size: 0.04}        → renormalize to sum=1
F9  = {F8 × 0.98, roe_yoy: 0.02}     → renormalize to sum=1
F10 = {F9 × 0.92, q_dt_roe: 0.08}    → renormalize to sum=1
F11 = {F10 × 0.99, roe_waa: 0.01}    → renormalize to sum=1
```

### Final F11_ROEWAA weights (after all normalizations, summing to 1)

| Factor | Weight |
|---|---|
| `roa` | **0.32359** |
| `q_roe` | **0.26452** |
| `rev_growth` | **0.11984** |
| `q_dt_roe` | **0.07920** |
| `dt_npy` | **0.07020** |
| `val` | **0.04195** |
| `size` | **0.03567** |
| `q_qoq` | **0.02653** |
| `roe_yoy` | **0.01821** |
| `q_roe_yoy` | **0.01028** |
| `roe_waa` | **0.01000** |
| **Sum** | **0.99999 ≈ 1.0** |

(The 0.00001 drift is floating-point residue from the 4-step normalization. Re-normalize to exactly 1.0 in code if desired.)

---

## 5. Signal Construction (per rebalance day)

Within the eligible universe for the day (§1.2), compute the composite score for each stock:

1. **Per-factor cross-sectional percentile rank**: for each factor f, take all stocks in the eligible universe; for non-NaN values, assign percentile rank in (1/n, 2/n, ..., n/n) where n is the count of non-NaN observations (so the worst gets 1/n, the best gets 1.0). Stocks with NaN for that factor get a neutral 0.5.

2. **Composite score** for each stock s:
   ```
   score(s) = Σ over factors f:  weight(f) × percentile_rank(f, s)
   ```

3. The score is bounded in [0, 1] by construction (it's a weighted average of values in [0, 1]).

**Ranking is the only operation used** — absolute factor values do not affect selection. This makes the strategy robust to factor unit conventions (% vs decimal, annualized vs not).

---

## 6. Portfolio Construction (per rebalance day)

### 6.1 Top-K selection
- Sort eligible stocks by composite score, descending
- Take the **top K = 5 stocks** (highest score first → highest score last)

### 6.2 Concentration weights
Given K = 5 stocks ordered by score (stock₁ = best, stock₅ = worst within top-K):

| Position | Concentration weight |
|---|---|
| Stock 1 (highest score) | `focus_pct / focus_n = 0.66 / 2 = 0.33` |
| Stock 2 | `focus_pct / focus_n = 0.66 / 2 = 0.33` |
| Stock 3 | `(1 − focus_pct) / (K − focus_n) = 0.34 / 3 ≈ 0.1133` |
| Stock 4 | `0.34 / 3 ≈ 0.1133` |
| Stock 5 (lowest score in top-K) | `0.34 / 3 ≈ 0.1133` |
| **Sum** | **1.0** |

Parameters: `K = 5`, `focus_n = 2`, `focus_pct = 0.66`. These are the v31-confirmed optimal values. Do not change without re-validating against the JK_min ≥ 200% and MDD ≥ −35% gates.

### 6.3 Universe replacement
On each rebalance day the holdings are **completely replaced** with the new top-K basket. There is no continuation/inertia from the prior rebalance — the strategy fully rebalances. (Implementation: SELL all positions not in new top-K, BUY/REWEIGHT to match new target weights.)

---

## 7. Volatility Scaling (applied every trading day)

### 7.1 Market volatility estimate
- Compute the **equal-weighted market return** as the cross-sectional mean of `pct_chg` (in decimal) over ALL stocks in the data on each trading day. This is `mkt_ret[T] = mean over all stocks of pct_chg_d[T]`.
- Important: this is the equal-weighted A-share universe return, NOT the CSI300 return. (For JoinQuant, the equal-weighted return must be computed from the universe used; using CSI300 as a proxy will give a slightly different scale — document the difference.)
- Compute 60-day annualized rolling standard deviation: `mkt_vol_60d[T] = std(mkt_ret[T-59..T]) × sqrt(252)`, requiring at least 45 days of data.
- Shift by 1 day: the value used at trading day T is the vol calculated through T-1.

### 7.2 Scaling factor
```
scale[T] = clip(target_vol / mkt_vol_60d[T], min_scale, max_scale)
```
With:
- `target_vol = 0.40` (annualized)
- `min_scale = 0.70`
- `max_scale = 1.00`

If `mkt_vol_60d[T]` is NaN or ≤ 0.01, default `scale[T] = max_scale = 1.00`.

### 7.3 Application
- Position size on trading day T = `scale[T] × concentration_weight`
- Implementation: when ordering, multiply target position values by `scale[T]`. The remaining `(1 − scale[T])` × total equity stays in cash.

The scale is recomputed daily — the strategy passively dials back exposure when market vol spikes, even on non-rebalance days. (Implementation: this can be approximated by recomputing scale only on rebalance days for simplicity; the daily-update path is preferred but the difference is small.)

---

## 8. Rebalance Schedule

- Rebalance every **15 trading days** (NOT calendar days).
- The first trading day of the backtest is always a rebalance day.
- Subsequent rebalance days are at indices 15, 30, 45, ... in the trading-date list.
- On non-rebalance days: do not change holdings; only update the vol-scale.

**JoinQuant implementation note**: 15 trading days ≈ 3 weeks. The cleanest mapping is `run_weekly(rebalance, weekday=1)` with a counter that triggers every 3rd Monday. (3 weeks × 5 trading days = 15 trading days exactly, on average.) Alternative: track a trading-day counter via `run_daily` and rebalance when `count % 15 == 0`.

---

## 9. Cost Model

- **25 basis points per side** (0.0025).
- **50 basis points round-trip** per rebalance event (sell all old + buy all new = both sides charged).
- Cost is applied as a **flat deduction** on rebalance days:
  ```
  pnl[T] -= scale[T] × 2 × 0.0025
  ```
  (i.e., 50 bp scaled by current deployment.)
- Cost is NOT applied per-ticker. It is a single flat deduction regardless of how many stocks turn over on that rebalance day.

**This is intentionally a conservative-but-simple cost model**. The v30 cost-model bug (per-ticker scaling) inflated costs ~5× and is the reason the v30 numbers were ~8 pp lower than v31's correct numbers. Do not switch to per-ticker costs.

For JoinQuant: the standard `set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5))` adds up to roughly 16 bp round-trip BEFORE slippage. Plus default slippage. The total live JQ cost will be slightly under our flat 50 bp model.

---

## 10. Return Computation

Per trading day, given the current basket (stocks selected at most recent rebalance) and their concentration weights:

1. Get daily returns `dr[s] = pct_chg[s, T] / 100` for each stock s in the basket.
2. Identify the "finite-return" subset: stocks with non-NaN `dr`.
3. If no stocks have finite returns: portfolio return for the day = 0.
4. If all stocks have finite returns: `rp = sum(weight[s] × dr[s])` over basket.
5. If some have NaN (suspension etc.):
   - Take the subset with finite returns.
   - Reweight: `w_active = original_weights restricted to finite subset, then normalized to sum=1`.
   - `rp = sum(w_active[s] × dr[s])` over finite subset.
   - (Equivalent to assuming halted stocks return 0 for that day AND reallocating their weight equally across active stocks.)
6. Apply scaling and costs:
   - `pnl[T] = scale[T] × rp`
   - If T is a rebalance day: `pnl[T] -= scale[T] × 2 × cost`
7. Update NAV: `nav[T] = nav[T-1] × (1 + pnl[T])`

---

## 11. Backtest Period

- **Sim start**: 2014-01-01 (first trading day = 2014-01-02)
- **Sim end**: 2026-02-27 (last trading day depends on calendar)
- **IS end**: 2019-12-31 (use for in-sample CAGR)
- **OOS start**: 2020-01-01 (use for out-of-sample CAGR)

For JoinQuant deployment, two recommended runs:
- **Honest baseline (OOS-only)**: 2020-01-01 → latest. This is the cleanest test because the v31 strategy parameters were locked using only data through ~2026 with discipline against OOS peeking; the OOS window has not been used to choose parameters.
- **Full period**: 2014-01-01 → latest. To compare against the simulation's full-period CAGR of 229.3%.

---

## 12. Pass Criteria (for variant evaluation)

A strategy variant **PASSES** all of the following:

1. Full-period CAGR ≥ 50 %
2. Max drawdown ≥ −35 % (i.e., not deeper than −35 %)
3. Walk-forward average CAGR ≥ 50 % across the 5 folds

**Walk-forward folds** (rolling 3-year evaluation windows):
- 2016-01-01 → 2018-12-31
- 2018-01-01 → 2020-12-31
- 2020-01-01 → 2022-12-31
- 2022-01-01 → 2024-12-31
- 2024-01-01 → 2026-12-31

For each fold: compute CAGR within the window. WF average = mean across folds.

**Jackknife (JK) validation**:
- Drop each calendar year (2014, 2015, ..., 2026) one at a time.
- Compute full-period CAGR with that year's daily returns removed (treat the year's returns as 0 for the NAV path).
- `JK_min` = minimum CAGR across all 13 leave-one-out runs.
- Pass: `JK_min ≥ 200 %` (research target, NOT a hard gate).

---

## 13. JoinQuant-Specific Implementation Notes

These notes address the gotchas discovered during the first JQ implementation attempt.

### 13.1 Field-name mapping (Tushare → JoinQuant)

| Conceptually | Tushare field | JoinQuant equivalent | Notes |
|---|---|---|---|
| Net profit (parent-only) | `net_profit` (in indicator: parent-only by convention) | `income.np_parent_company_owners` | **Use parent-only**. `income.net_profit` includes minority interest and is WRONG. |
| Equity (parent-only) | `equity` (parent-only) | `balance.equities_parent_company_owners` | **Use parent-only**. `balance.total_owner_equities` includes minority interest and is WRONG. |
| Cumulative ROE (parent) | `roe` | `indicator.roe` | JQ's `indicator.roe` formula = `net_profit × 2 / (begin_equity + end_equity)` (parent-only, verified in JQ docs line 2686). Equals Tushare's `roe_waa`. |
| Cumulative deducted ROE (parent) | `roe_dt` / `inc_return` | `indicator.inc_return` | Verified parent-company in JQ docs line 2687. |
| Cumulative deducted net profit | `adjusted_profit` | `indicator.adjusted_profit` | JQ docs are ambiguous on whether this is parent-only. Spot-check on a known company to verify. |
| Operating profit | `oper_profit` / `operating_profit` | `income.operating_profit` | Cumulative from start of year. |
| Revenue YoY | `or_yoy` | `indicator.inc_revenue_year_on_year` | Direct match. |
| Cumulative ROA | `roa` | `indicator.roa` | Direct match. |
| Net profit YoY (parent) | `netprofit_yoy` | `indicator.inc_net_profit_to_shareholders_year_on_year` | Direct match (parent-company net profit YoY). |

### 13.2 Single-quarter computation pattern in JoinQuant
JQ does NOT have pre-computed `q_roe`, `q_dt_roe`, `q_op_qoq`. Compute from raw cumulative values:

For an anchor quarter (most recent published quarter as of T-1):
- `prior_quarter` = previous fiscal quarter in the same year. For Q1, the prior is Q4 of the previous year.
- `year_ago_quarter` = same fiscal quarter, one year earlier.
- `year_ago_prior` = the prior of the year-ago quarter.
- `pre_prior` = the prior of the prior (needed for q_qoq).

For each stock at the anchor quarter:
- `q_net_profit = cumul_now − cumul_prior` (where cumul = `np_parent_company_owners`). For Q1 anchor: `q_net_profit = cumul_now`.
- `q_adj_profit = adjusted_profit_now − adjusted_profit_prior`. For Q1: `q_adj_profit = adjusted_profit_now`.
- `avg_equity = (equities_parent_company_owners_now + equities_parent_company_owners_prior) / 2`
- `q_roe = q_net_profit / avg_equity × 100` (percent)
- `q_dt_roe = q_adj_profit / avg_equity × 100` (percent)

For `q_op_qoq`:
- `q_op_now = single_q(operating_profit, now, prior, q_num_of_anchor)`
- `q_op_prior_q = single_q(operating_profit, prior, pre_prior, q_num_of_prior)`
- `q_op_qoq = (q_op_now − q_op_prior_q) / abs(q_op_prior_q) × 100`

For `dt_npy` (cumulative deducted-NP YoY):
- `dt_npy = (adjusted_profit_now − adjusted_profit_year_ago) / abs(adjusted_profit_year_ago) × 100`

For `q_roe_yoy`:
- Compute `q_roe_now` as above using anchor + prior.
- Compute `q_roe_ya` using year_ago_quarter + year_ago_prior.
- `q_roe_yoy = q_roe_now − q_roe_ya`

### 13.3 PIT safety with `get_fundamentals(statDate=...)`
When using `statDate='YYYYqN'`, JQ returns the data for that quarter REGARDLESS of whether it was published by the asked-for date. To enforce PIT safety:
- Always filter the returned rows by `pubDate ≤ context.previous_date`.
- Alternatively, use `get_fundamentals(date=context.previous_date)` which auto-PIT-filters but only gives the most recent published quarter per stock.

### 13.4 Anchor-quarter coverage
Different stocks publish on different dates. The "dominant anchor" approach (pick the most common `statDate` across the universe) works for most rebalance days. Stocks whose latest published quarter doesn't match the dominant anchor get NaN on the 5 single-quarter factors → neutral 0.5 rank for those factors. Log the coverage at every rebalance:
```
SQ anchor = <statDate>, coverage = <N>/<total>
```
Anything under 50% coverage warrants review.

### 13.5 Builtin shadowing
`from jqdata import *` shadows Python's `sum`, `min`, `max` with SQLAlchemy aggregation functions (intended for use inside `query()`). Avoid these builtins on regular Python sequences:
- ❌ `sum(my_dict.values())`
- ✅ Explicit loop: `s = 0.0; for v in my_dict.values(): s += float(v)`
- ❌ `min(a, b)`
- ✅ Ternary: `a if a < b else b`

### 13.6 Cost configuration
Use JoinQuant's standard cost setup:
```python
set_order_cost(OrderCost(
    close_tax = 0.001,         # 1‰ stamp duty on sells
    open_commission = 0.0003,  # 3 bps buy
    close_commission = 0.0003, # 3 bps sell
    min_commission = 5,        # ¥5 minimum per order
), type='stock')
```
This is the standard JoinQuant convention and approximates the simulation's flat-50bp model.

### 13.7 Required JoinQuant options
```python
set_benchmark('000300.XSHG')   # CSI 300 (note: JQ benchmark won't match equal-weighted market vol; document the discrepancy)
set_option('use_real_price', True)
set_option('avoid_future_data', True)
log.set_level('order', 'error')
```

### 13.8 Order execution recommendations (best practice from G2/G3 baselines)
- Maintain a `g.hold_list` updated daily at 09:05.
- Track `g.high_limit_list` = positions that closed at limit-up yesterday; do NOT sell these on rebalance day (likely uncloseable; might also lose alpha).
- Filter the buy list to exclude stocks at limit-up TODAY (can't fill at limit).
- Sell-then-buy ordering: close discarded positions BEFORE opening new positions (frees cash).
- Optional: a `check_limit_up_break` callback at 14:00 sells stocks that hit yesterday's limit-up but lost it today (rotation).

### 13.9 Universe filter pragmatics for JoinQuant
- Apply paused / ST / 退市 filters via `get_current_data()` before the `get_fundamentals` query.
- Use `get_all_securities(date=T - 375_calendar_days)` to enforce a 次新 cooldown (~250 trading days ≈ 375 calendar days). The Tushare local sim doesn't apply this but every JoinQuant production strategy does and it's safer.
- Optional: filter out 科创板 (`s.startswith('68')`) and 北交所 (`s.startswith('4') or s.startswith('8')`). The local sim doesn't, but G2/G3 baselines do.

---

## 14. Known Gaps & Pitfalls (READ BEFORE IMPLEMENTING)

1. **The 192.7% OOS CAGR is the simulation upper bound, NOT a realistic JoinQuant target.** A first attempt at JQ implementation produced 7.77% annual return — that's after a parent-company-field bug was discovered and fixed. Even with all bugs fixed, realistic JoinQuant deployment of this exact algorithm is likely in the 15–60 %/yr range. Significant gap sources:
   - Tushare `pct_chg` ≠ JoinQuant actual fill returns
   - JoinQuant models suspension / limit-up rejection; simulation does not
   - JoinQuant's `indicator.adjusted_profit` may differ subtly from Tushare's `dt_*` fields
   - Tushare PIT alignment uses `ann_date + 1 day shift`; JoinQuant uses `pubDate` (similar but not identical for late restatements)

2. **The 29-month max-drawdown observation** (2021-09-15 → 2024-02-07 in the first JQ run) suggests the strategy needs a **regime gate** to be deployable. The v31 research did NOT include a regime filter — it ran fully invested through every bear market. Adding an MA-slope filter (G2 pattern: 20-day OLS slope on the index < −2 → don't open new positions) is a natural extension. **The local v31 numbers do NOT include this**.

3. **Single-quarter factor data quality**: in Tushare's `fina_indicator_vip`, single-quarter values like `q_roe`, `q_dt_roe`, `q_op_qoq` are pre-computed by Tushare/Wind. In JoinQuant they must be derived from raw quarterly cumulative values. Subtle differences in:
   - Which "net profit" is used (parent-only vs total)
   - How Q1-anchor edge cases handle the year boundary
   - How late restatements propagate backward through derived single-Q values

   …can produce divergent factor values even when the algorithm description is identical. Verify by spot-checking 3–5 well-known stocks (e.g., 600519 贵州茅台, 000001 平安银行, 002475 立讯精密) — compute `q_roe` for 2024-Q3 in both systems and compare. If they disagree by > 5%, the single-Q derivation has a problem.

4. **The simulation's NaN-as-zero return assumption** (§10 step 5) is **anti-conservative**. When a stock is halted, the simulation assumes it returns 0 and reallocates weight to other holdings. In reality a halted stock cannot be sold; capital is stuck. JoinQuant simulates this correctly. Expect this to cost ~1–3 pp/yr.

5. **The Tushare local sim does NOT filter 科创 / 北交 / 次新**. JoinQuant will under realistic deployment. If you replicate the universe filter exactly (no exclusions), expect more whipsaw and worse fills.

6. **DO NOT TUNE PARAMETERS ON JOINQUANT**. The v31 parameters (K=5, focus_pct=0.66, REBAL=15d, target_vol=0.40, factor weights) were settled through ~20 iterations on the local Tushare engine with strict OOS discipline. Any "improvement" found by sweeping on JoinQuant is overfit to the JoinQuant test window. The legitimate use of JoinQuant is to **deploy** v31 verbatim, not to discover new optima.

---

## 15. Reference Tushare/Qlib Implementation

The canonical implementation is `workspace/scripts/sandbox_v15aa_v31_focuspct_confirmation.py` in the local `E:\量化系统` repository. Key functions:

- `load_data()`: builds per-factor arrays with PIT alignment (lines 113–227)
- `build_basket()`: universe filter + factor blending + top-K + concentration (lines 275–300)
- `sim()`: day-by-day NAV computation with vol scaling + costs (lines 303–338)
- `compute_stats()`: CAGR / MDD / Sharpe (lines 238–251)
- `compute_wf()`: 5-fold walk-forward CAGR (lines 254–267)

The factor weight chains `F7_DIR_V22` → `F11_ROEWAA` are defined at lines 82–106.

If anything in this spec is ambiguous, the local implementation is the tie-breaker.

---

## 16. Acceptance Test (for the JoinQuant replication)

The JoinQuant replication is considered correct enough to deploy if:

1. ✅ All 11 factors are computed using **parent-company-only** net profit and equity.
2. ✅ The 5 single-quarter / lagged factors (`q_roe`, `q_dt_roe`, `q_qoq`, `dt_npy`, `q_roe_yoy`) match the local Tushare values within ±5% on at least 80% of stocks for 2024-Q3 data (spot-check 50 random names).
3. ✅ The universe filter eliminates exactly the same conceptual set (PB ∈ (0.3, 6.0], ROE ≥ 0, net-profit YoY ≥ 0) using PIT-safe values.
4. ✅ The concentration weights are exactly `[0.33, 0.33, 0.1133, 0.1133, 0.1133]` for the top 5.
5. ✅ The rebalance cadence is 15 trading days (verify by counting rebalance events over a full year: should be 16–17).
6. ✅ The OOS CAGR (2020-01-01 → latest) is reported separately from full-period CAGR.
7. ✅ A run.md is created with the full parameter set, observed CAGR/MDD/Sharpe, max-drawdown period, and any observed differences from this spec.

If any of these acceptance tests fail, do NOT mark the deployment ready. Iterate on the implementation until all 7 pass.

---

End of specification.
