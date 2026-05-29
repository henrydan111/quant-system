# v33 Strategy Specification — 11F-ROEWAA Quality/Value, Event-Driven Validated

> ## ⛔ INVALIDATED (2026-05-29) — DO NOT IMPLEMENT
> A PIT lookahead bug was found in the sandbox factor loader that generated every
> performance number in this spec (and §13's reference baskets). The factor arrays
> carried up to ~9 months of earnings foresight. After fixing the loader and
> re-measuring on the same engine, the champion's OOS CAGR collapsed **188.7% → 2.0%**
> (MDD −33.8% → −76.3%) and the val_heavy deployment config collapsed **+81.9% → +9.6%**
> CAGR with a **negative (−3.4%) walk-forward**. The edge was almost entirely lookahead,
> not tradable alpha. **Do not deploy this strategy.** The JoinQuant script itself is
> PIT-correct, so it will not leak — but it will not deliver these numbers either.
> Full detail: [v33_PIT_lookahead_bug_report.md](v33_PIT_lookahead_bug_report.md) §9.
> Any re-derivation must run on PIT-correct factors (production backend / EventDrivenBacktester),
> not a hand-rolled sandbox loader.

**Audience**: a JoinQuant implementation session with ZERO prior context. This
document is self-contained. Implement only what is written here.

**Lineage**: this is the same factor model as the earlier `v31_strategy_spec.md`,
but the performance expectations and the execution rules have been corrected by
two follow-up validations:
  - **v32** fixed an optimistic execution assumption (close[T-1] → open[T]).
  - **v33** ran the champion through the project's realistic `EventDrivenBacktester`
    (T+1, price limits, suspension, board lots, real costs, slippage). This
    collapsed the sandbox CAGR by more than half AND revealed a hard tradability
    ceiling. **Trust the v33 numbers, not the v31/v32 sandbox numbers.**

If anything here conflicts with the older `v31_strategy_spec.md`, THIS document wins.

---

## 0. READ THIS FIRST — Honest Performance Expectations & Hard-Won Lessons

### 0.1 Three-way performance reality (OOS 2020-2026)

| Engine | OOS CAGR | OOS MaxDD | What it models |
|---|---|---|---|
| Custom vectorized sandbox (v31/v32) | 190.8% | −34.84% | perfect fills, full deployment, flat cost — **FANTASY** |
| **EventDrivenBacktester (v33)** | **77.8%** | **−19.44%** | T+1, limit-up unfillability, suspension, lots, real cost + slippage |
| JoinQuant live (a prior naive port) | ~7.77% | −45.82% | a buggy earlier implementation |

Full-period (2014-01-02 → 2026-02-27) under the realistic engine: **CAGR 106.4%,
MaxDD −28.94%, Sharpe 2.57, win-rate 71.6%, P/L 2.44, 1,374 trades.**
IS (2014-2019) = 140.1%, OOS (2020-2026) = 77.8%.

**Your replication target is the v33 column (~77.8% OOS), NOT 190%.** If your
JoinQuant backtest lands near 77.8% OOS you have replicated it correctly. If it
lands near 7.77% you have reproduced the OLD BUG (see §0.3).

### 0.2 THE DEPLOYMENT CEILING (most important finding)

Under realistic execution the strategy could only deploy **~59% of capital on
average in 2020-2026** (vs a ~95% target). ~40% sat in cash. Reason: the signal
selects high-momentum quality names that **systematically lock limit-up (涨停)
and cannot be bought**. In the calmer 2014-2019 window deployment was ~92%; in
the 2020-2026 momentum regime it fell to ~59%.

Consequences you MUST expect and not "fix" by force:
  - Holding count drifts ABOVE the target of 5 (observed mean 7, up to 13)
    because some sells fail (T+1, suspension, limit-down) and stuck positions
    accumulate.
  - The low realized drawdown (−19% OOS) is **mostly a cash-drag artifact**, not
    skill. Do not advertise it as risk control.
  - Capacity is limited. You cannot scale this strategy arbitrarily — the
    limit-up wall is real.

A correct replication will show the SAME under-deployment. If your JoinQuant run
is always ~100% invested, you are almost certainly NOT enforcing limit-up
unbuyability and your returns will be optimistically inflated.

### 0.3 WHY THE OLD JOINQUANT PORT GAVE 7.77% (do NOT repeat these)

The 77.8% (v33) vs 7.77% (old live) gap is **NOT execution** — v33 already models
execution. It is **signal-construction error** in the old port. The two specific
bugs were:

1. **Parent-company equity bug.** Single-quarter ROE factors (`q_roe`,
   `q_dt_roe`) must use **parent-company-only** net profit and equity
   (`np_parent_company_owners`, `equities_parent_company_owners`). The old port
   used total net profit / total equity (`net_profit`, `total_owner_equities`),
   which INCLUDE minority interest and produce a different, weaker signal. JQ's
   own `indicator.roe` formula is parent-company-only (JQ docs) — match it.
2. **Universe over-exclusion.** The old port excluded 科创板(68xxxx),
   北交所(4/8xxxx), and 次新股(<375 days listed). The clean signal that produces
   77.8% uses the FULL Tushare A-share universe with NO such exclusions
   (only the three eligibility filters in §2). Excluding those segments removes
   the exact names that drive the alpha. (You MAY choose to exclude 科创/北交 for
   liquidity reasons, but know that doing so changes the strategy and lowers the
   expected return toward the old number.)

### 0.4 Statistical-honesty caveat

Even 77.8% is optimistic. The factor set + parameters were iterated ~20 times
against the 2020-2026 OOS window during research (v17 → v32), so the OOS number
carries multiple-comparison inflation. A bias-corrected expectation is lower
(plausibly 40-60% if the alpha is real). Treat 77.8% as an upper bound on a
realistic deployment, not a promise.

---

## 1. One-paragraph description

Long-only A-share strategy. Every 15 trading days, rank a quality-filtered
universe by an 11-factor composite (heavily ROA + single-quarter ROE + revenue
growth, lightly value + size + growth-acceleration). Buy the top 5 names with a
concentrated weighting (the best 2 names get 65% of equity between them, the
next 3 split the rest), scaled down when market volatility is high. Fill at the
next open. Skip names that are unbuyable (limit-up / suspended) and substitute
the next-ranked candidate. Hold until the next rebalance. No shorting, no
leverage, no derivatives.

---

## 2. Universe Selection (recomputed fresh every rebalance day)

Start from the full A-share common-stock universe. A stock is ELIGIBLE on
rebalance day T if **all three** conditions hold, evaluated on values known as of
the close of T−1 (point-in-time; see §4 for the PIT rule):

1. `net_profit_yoy >= 0` — parent-company net-profit YoY growth ≥ 0
   (Tushare `fina_indicator_vip.netprofit_yoy`; JQ
   `indicator.inc_net_profit_to_shareholders_year_on_year`), in percent.
2. `roe >= 0` — cumulative ROE ≥ 0 (Tushare `roe`; JQ `indicator.roe`), percent.
3. `0.30 < pb <= 6.00` — daily price-to-book strictly above 0.30 and at most 6.00
   (Tushare daily `pb`; JQ `valuation.pb_ratio`).

All three values must be finite (drop NaN). The eligible set is recomputed on
every rebalance day from scratch — there is no membership carry-over.

**Segment exclusions**: the validated v33 run applied NONE (full universe). See
§0.3 — excluding 科创/北交/次新 is a deviation that lowers expected return.

---

## 3. The 11 Factors and Their Exact Weights

The composite is a weighted sum of cross-sectional **percentile ranks** (see §5).
Higher composite = more desirable. Weights sum to 1.0 and are FROZEN — do not
tune them on JoinQuant (any "improvement" found by tuning on the test window is
overfit).

| # | Factor | Weight | Direction | Definition |
|---|---|---|---|---|
| 1 | `roa` | 0.323590 | higher better | cumulative Return on Assets (%, Tushare `roa` / JQ `indicator.roa`) |
| 2 | `q_roe` | 0.264522 | higher better | **single-quarter** weighted-avg ROE (%) — see §6 |
| 3 | `rev_growth` | 0.119848 | higher better | cumulative revenue YoY growth (%, Tushare `or_yoy` / JQ `indicator.inc_revenue_year_on_year`) |
| 4 | `q_dt_roe` | 0.079200 | higher better | **single-quarter** deducted (扣非) ROE (%) — see §6 |
| 5 | `dt_npy` | 0.070197 | higher better | cumulative **deducted** net-profit YoY growth (%) — see §6 |
| 6 | `val` | 0.041947 | higher better | `1 / pb` (earnings/book yield proxy; pb is daily, PIT-shifted) |
| 7 | `size` | 0.035669 | higher better | `−ln(total_mv)` (small-cap tilt; total_mv = total market cap) |
| 8 | `q_qoq` | 0.026538 | higher better | **single-quarter** operating-profit QoQ growth (%) — see §6 |
| 9 | `roe_yoy` | 0.018216 | higher better | cumulative ROE YoY change (percentage points) — see §6 |
| 10 | `q_roe_yoy` | 0.010273 | higher better | `q_roe(now) − q_roe(252 trading days ago)` — see §6 |
| 11 | `roe_waa` | 0.010000 | higher better | cumulative weighted-avg ROE (%, Tushare `roe_waa`; equals JQ `indicator.roe`) |

Total = 1.000000. (Note factors 2 and 11 are different: `q_roe` is single-quarter;
`roe_waa` is the cumulative weighted-average ROE which JQ's `indicator.roe`
already provides.)

---

## 4. Point-In-Time (PIT) Rule — NO LOOKAHEAD

Every fundamental value used on rebalance day T must have been publicly known by
the close of T−1.

- **In the research engine** (Tushare): each quarterly value is stamped with an
  `effective_date` = the first trading day STRICTLY AFTER its announcement date
  (`ann_date`), then `shift(1)` is applied. This gives a ≥1-trading-day buffer
  between disclosure and use.
- **On JoinQuant**: set `set_option('avoid_future_data', True)` and query
  fundamentals as of `context.previous_date` (T−1). Do NOT use
  `context.current_dt` data for selection. For `get_fundamentals(statDate=...)`
  queries (needed for single-quarter math, §6), JQ does NOT auto-PIT-filter —
  you MUST drop any row whose `pubDate > context.previous_date`.
- Daily fields (`pb`, `total_mv`) are taken from T−1 (previous close).

---

## 5. Signal Construction

For the eligible universe on rebalance day T:

1. For each of the 11 factors, compute the **cross-sectional percentile rank**
   among stocks with a finite value for that factor. Rank in [0,1], higher value
   → higher rank (use ascending rank / N). A stock missing that factor gets a
   neutral rank of 0.5 for that factor only (do not drop the stock).
   - Require at least 3 finite observations to rank; otherwise assign 0.5 to all.
2. Composite score = Σ_f ( weight_f × percentile_rank_f ). Bounded in [0,1].
3. Rank stocks by composite score, descending.

Only ranks matter — absolute factor units (%, decimal) are irrelevant because
percentile rank is invariant to monotone transforms. This makes the strategy
robust to JQ-vs-Tushare unit differences.

---

## 6. Single-Quarter Factor Computation on JoinQuant (the hard part)

Tushare ships `q_roe`, `q_dt_roe`, `q_op_qoq` pre-computed. **JoinQuant does
not** — you must derive them from raw cumulative statements. Use
**parent-company-only** fields throughout (this is the §0.3 bug). All amounts are
year-to-date cumulative within a fiscal year.

JQ raw fields to query (via `get_fundamentals` with `statDate='YYYYqN'`):
  - `income.np_parent_company_owners` — cumulative parent-company net profit
  - `income.operating_profit` — cumulative operating profit
  - `indicator.adjusted_profit` — cumulative deducted (扣非) net profit
  - `balance.equities_parent_company_owners` — parent-company equity (period-end)
  - `indicator.statDate`, `indicator.pubDate` — for anchor + PIT filter

Define a "single-quarter" value from cumulatives: for fiscal quarter Q,
`single_q(Q) = cumulative(Q) − cumulative(Q−1 within same year)`; for Q1,
`single_q(Q1) = cumulative(Q1)`.

For the most-recently-published quarter (the "anchor", chosen as the dominant
`statDate` across the eligible universe), fetch the anchor quarter plus its prior
quarter, its pre-prior quarter, the same quarter one year ago, and that
year-ago quarter's prior. Then:

```
q_net_profit      = single_q(np_parent,        anchor, prior)
q_adjusted_profit = single_q(adjusted_profit,  anchor, prior)
avg_equity        = (equities_parent[anchor] + equities_parent[prior]) / 2

q_roe     = q_net_profit      / avg_equity * 100          # factor 2
q_dt_roe  = q_adjusted_profit / avg_equity * 100          # factor 4

q_op_now   = single_q(operating_profit, anchor, prior)
q_op_prior = single_q(operating_profit, prior, pre_prior)
q_qoq      = (q_op_now − q_op_prior) / abs(q_op_prior) * 100   # factor 8

dt_npy = (adjusted_profit[anchor] − adjusted_profit[year_ago])
         / abs(adjusted_profit[year_ago]) * 100                # factor 5 (cumulative YoY)

# factor 9: cumulative ROE YoY change, in percentage points
roe_yoy = indicator.roe[as of T-1] − indicator.roe[as of T-1 minus ~370 days]

# factor 10: single-quarter ROE YoY
q_roe_ya = single_q net profit / avg equity for the YEAR-AGO quarter, *100
q_roe_yoy = q_roe − q_roe_ya
```

Stocks not at the dominant anchor `statDate` get NaN for the five single-quarter
factors → neutral 0.5 rank (their other six factors still score them). Log the
anchor coverage every rebalance; if coverage is far below 100% the strategy
degrades toward a 6-factor model that week.

Sanity check before trusting: spot-check `q_roe` for 3-5 well-known names
(e.g. 600519, 000001, 002475) for a known quarter and confirm it is computed
from PARENT-company figures.

---

## 7. Portfolio Construction (every rebalance day)

1. From the ranked eligible list, request an **oversized top-N** of N = 15
   candidates (NOT just 5). The extra names are substitution headroom.
2. Walk the 15 in rank order and select up to **K = 5** that are BUYABLE today
   (see §9 substitution). Already-held names are kept without re-checking.
3. Assign **concentration weights** by final selected position:
   - positions 1-2 (the two highest-ranked selected): `0.65 / 2 = 0.325` each
   - positions 3-5: `(1 − 0.65) / 3 = 0.116667` each
   - (parameters: `focus_n = 2`, `focus_pct = 0.65`, `topk = 5`)
4. Multiply every weight by the volatility scale (§8). The remaining
   `(1 − scale)` stays in cash.
5. Full rebalance: sell every currently-held name not in the new target set
   (subject to tradability), then buy/top-up to the scaled target weights.

`focus_pct = 0.65` is the v32-corrected optimum. The earlier `0.66` value FAILS
the −35% drawdown gate under realistic execution; do not use it.

---

## 8. Volatility Scaling (computed at each rebalance)

```
mkt_vol_60d = annualized 60-day stdev of the equal-weighted daily return of the
              whole universe (std × sqrt(252)), as of T−1
scale       = clip( 0.40 / mkt_vol_60d , 0.70 , 1.00 )
```

- `target_vol = 0.40`, `min_scale = 0.70`, `max_scale = 1.00` (NO leverage).
- If `mkt_vol_60d` is NaN or ≤ 0.01, use `scale = 1.00`.
- Apply `scale` to the target weights at rebalance only (not intraday). Observed
  mean scale ≈ 0.954 over 2014-2026.
- On JoinQuant you may approximate the equal-weighted universe vol with the
  benchmark (000300) 60-day vol if computing a full-universe mean is too heavy —
  document the substitution; it shifts `scale` slightly but not materially.

---

## 9. Execution Model — the limit-up substitution that v33 adds

This is the single most important execution detail and the reason v33 differs
from the naive sandbox. Fills happen at the **open** of the rebalance day.

**Buyability prediction (before placing buy orders)**: a NEW candidate (not
already held) is skipped if any of these is true, judged from T−1 data:
  - suspended (停牌) — no T−1 trade / zero volume / on the suspension list
  - locked at upper limit (涨停) at T−1 close — predicted to open limit-up,
    unbuyable
  - locked at lower limit (跌停) at T−1 close
  - no T−1 data at all

Walk the ranked-15 list top-down; for each, if already held → keep; else if
buyable → take; stop once 5 are selected. This mirrors JoinQuant's
`filter_limitup` substitution pattern. On JoinQuant, also rely on the engine's
own fill failure (an order that can't fill at limit just doesn't fill) as the
backstop.

**Selling**: a name you want to exit may be unsellable (suspended / limit-down /
T+1 lock on shares bought today). Those positions persist — this is why the
holding count drifts above 5. Do not force-sell; let them clear when tradable.

**Lots**: orders round to 100-share board lots (手). **T+1**: shares bought today
cannot be sold today.

JoinQuant scheduling that realizes this model:
```python
set_option('use_real_price', True)
set_option('avoid_future_data', True)
log.set_level('order', 'error')
run_daily(rebalance, time='09:30', reference_security='000300.XSHG')
# rebalance() only acts on the 196 scheduled rebalance dates (every 15 trading
# days); on other days it returns immediately.
```

---

## 10. Rebalance Schedule

- Rebalance every **15 trading days** (not calendar days). The first trading day
  of the backtest is a rebalance day; subsequent ones at trading-day indices
  15, 30, 45, … Over 2014-2026 this is ~196 rebalances.
- Between rebalances: hold; do not trade except forced corporate-action effects.
- On JoinQuant, implement with a trading-day counter incremented in a daily
  callback, firing the rebalance when `counter % 15 == 0`.

---

## 11. Costs and Slippage

Use the JoinQuant-default cost model (the project's `CostConfig()` mirrors it):
```python
set_order_cost(OrderCost(
    open_tax=0, close_tax=0.001,          # 0.1% stamp duty on sells
    open_commission=0.0003, close_commission=0.0003,
    close_today_commission=0, min_commission=5
), type='stock')
set_slippage(FixedSlippage(0.0003))       # ≈0.3 bps on a ¥10 stock; JQ standard
```
The v33 run used exactly these (`CostConfig()` + `FixedSlippage(0.0003)`).

---

## 12. Backtest Windows

- Full validation: 2014-01-02 → 2026-02-27, initial capital 1,000,000,
  benchmark 000300 (沪深300).
- IS = 2014-01-02 → 2019-12-31. OOS = 2020-01-01 → 2026-02-27.
- Run the full window once continuously; slice IS/OOS from the daily return
  series for reporting (the strategy runs continuously, it does not reset at the
  IS/OOS boundary).

---

## 13. Factor Alignment Reference Data (verify your JoinQuant factors against these)

These values come from the validated local v32 signal pipeline (Tushare data).
Use them to confirm your JoinQuant factor computation and ranking match. All
values are PIT (as of the prior trading day). Tushare ships the single-quarter
factors pre-computed; your JQ reconstruction (§6) will NOT match to 4 decimals
(different data vendor) but should match in RANK and produce the same or
near-same top-5. Full dump: `workspace/outputs/v33_factor_alignment.txt`.

### 13.1 Per-factor coverage (finite values / universe, full panel 2014-2026)

```
factor          weight   coverage
------------    -------   --------
roa             32.359%     84.0%
q_roe           26.452%     78.1%
rev_growth      11.985%     84.4%
q_dt_roe         7.920%     76.9%
dt_npy           7.020%     82.8%
val              4.195%     67.3%   (1/pb; lower coverage = pb missing/<=0)
size             3.567%     67.8%   (-ln total_mv)
q_qoq            2.654%     77.2%
roe_yoy          1.822%     84.2%
q_roe_yoy        1.027%     69.5%   (needs 252 trading days of q_roe history)
roe_waa          1.000%     85.2%
```

If your JQ coverage for `roa` is far below ~84% (e.g. <60%), your fundamental
query or PIT join is dropping rows — investigate before trusting results. The
~16-23% of names missing a factor get the neutral 0.5 rank for that factor only.

### 13.2 Reference baskets — the exact top-5 your ranking should select

(composite score in brackets; these are the names bought, with positions 1-2
getting 0.325 each and 3-5 getting 0.1167 each, before vol-scaling)

```
2018-06-07 (IS) : 600408.SH(.928) 000789.SZ(.928) 300132.SZ(.923) 000636.SZ(.919) 600802.SH(.914)
2019-06-04 (IS) : 002869.SZ(.952) 300417.SZ(.952) 002605.SZ(.928) 300702.SZ(.918) 002234.SZ(.910)
2021-06-17 (OOS): 605399.SH(.941) 000949.SZ(.940) 603077.SH(.929) 002274.SZ(.921) 002932.SZ(.921)
2023-06-08 (OOS): 603099.SH(.949) 920174.BJ(.938) 002159.SZ(.930) 301004.SZ(.909) 920225.BJ(.904)
```

**CRITICAL ALIGNMENT FINDINGS — these are the highest-value cross-checks:**

1. **The strategy is SMALL/MID-CAP quality-growth, not blue-chip.** Every pick
   above is a small/mid name. If your JQ run keeps selecting large caps, your
   `size = -ln(total_mv)` factor or the universe is wrong.
2. **贵州茅台 (600519) must be EXCLUDED by the PB≤6 filter.** Its `val = 1/pb`
   is 0.06-0.11 → PB ≈ 9-17, far above the 6.0 cap. On all four dates 600519 is
   NOT ELIGIBLE. If your JQ universe includes 茅台, your PB filter is broken.
3. **平安银行 (000001) is ELIGIBLE but rarely picked**, and its `roa` is NaN
   (banks don't report a comparable ROA in the indicator feed) → neutral 0.5 on
   the 32%-weight factor → low composite. Expect banks eligible but unselected.
4. **北交所 appears in the picks (2023-06-08: 920174.BJ, 920225.BJ).** The
   full-universe signal genuinely selects Beijing-Exchange names. **If your JQ
   universe excludes 北交所 you will NOT reproduce these baskets** — this is
   exactly the §0.3 universe-exclusion divergence. Decide deliberately: include
   北交所 (faithful to v33, higher return, thinner liquidity) or exclude it
   (safer fills, lower return) — and DOCUMENT the choice. 北交所 codes are
   `8xxxxx.BJ` / `920xxx.BJ` in this dataset.

### 13.3 Full per-factor breakdown — two reference dates (top-5), raw value (rank)

`2018-06-07` (IS), eligible universe = 1717:
```
code         roa        q_roe      rev_grw    q_dt_roe   dt_npy       val        size        q_qoq      roe_yoy     q_roe_yoy  roe_waa
600408.SH    14.68(.97) 10.28(.99) 48.98(.87) 10.49(.99) 1245.7(.98) 0.39(.50) -12.13(.99) -37.52(.23) 4612.8(1.0)  2.11(.90) 58.83(1.0)
000789.SZ    21.04(.99)  9.99(.99) 52.06(.88) 10.47(.99)  290.4(.94) 0.43(.56) -13.50(.43)  20.17(.74)  184.9(.91)  4.80(.97) 25.12(.99)
300132.SZ    28.22(1.0) 13.22(.99) 64.92(.92) 13.01(1.0)  245.1(.92) 0.18(.02) -12.96(.69)  31.51(.79)  166.9(.90)  8.67(.99) 31.77(.99)
000636.SZ    16.00(.98)  9.38(.98) 53.27(.89)  9.18(.99)  491.5(.96) 0.37(.46) -14.03(.26)  52.59(.85)  320.1(.95)  7.81(.99) 18.08(.96)
600802.SH    13.54(.96) 11.64(.99) 70.41(.94) 11.48(.99)  438.5(.96) 0.23(.14) -12.61(.86) -25.93(.34)  407.1(.96) 16.97(1.0) 42.45(1.0)
```

`2023-06-08` (OOS), eligible universe = 2068:
```
code         roa        q_roe      rev_grw     q_dt_roe   dt_npy      val        size        q_qoq       roe_yoy    q_roe_yoy  roe_waa
603099.SH    17.23(.99) 14.12(1.0) 209.4(.99)  14.05(1.0) 639.8(.96) 0.27(.22) -12.70(.76) 969.3(.98)  628.6(.96)  9.10(.99) 15.45(.94)
920174.BJ    14.66(.98)  6.84(.97)  65.21(.95)  6.58(.98)  86.1(.73) 0.80(.87) -11.24(.98)  15.99(.67)  57.8(.70)  3.67(.94) 18.59(.98)
002159.SZ    12.38(.96)  6.79(.97) 158.2(.99)   6.76(.98) 354.6(.93) 0.34(.35) -12.75(.74) 147.5(.92)  385.5(.94)  5.79(.98) 11.19(.84)
301004.SZ    26.75(1.0) 14.34(1.0)  46.90(.91) 15.11(1.0)  92.4(.74) 0.25(.16) -12.83(.71)  37.89(.78)  21.9(.51)  2.78(.91) 31.68(1.0)
920225.BJ    15.38(.99)  6.40(.97)  30.57(.82)  6.35(.97) 102.5(.77) 0.46(.56) -11.56(.97)  -3.03(.51)  39.4(.63)  1.04(.74) 18.50(.98)
```

Units: roa/q_roe/q_dt_roe/roe_waa in % (ROE-type); rev_growth/dt_npy/q_qoq/roe_yoy
in % growth; val = 1/pb (dimensionless); size = −ln(total_mv) with total_mv in
万元 (so ≈ −12 corresponds to a mid/small cap); q_roe_yoy in percentage points.

### 13.4 Large-cap cross-check — 贵州茅台 600519 (stable, easy to verify on JQ)

600519's PIT factor values were (NOT ELIGIBLE every date — PB cap):
```
date         roa     q_roe   rev_g   q_dt_roe  dt_npy  val    size     q_qoq   roe_waa   eligible?
2018-06-07   25.25   9.16    23.07   9.24      24.11   0.10  -18.41   21.08   24.93     NO (pb≈10)
2019-06-04   26.80   8.75    16.64   8.75      22.48   0.11  -18.53   20.26   24.92     NO (pb≈9)
2021-06-17   23.85   7.51    11.05   7.56      10.19   0.06  -19.42   16.89   21.68     NO (pb≈17)
2023-06-08   27.80   8.07    18.48   8.06      18.97   0.11  -19.15    9.78   24.82     NO (pb≈9)
```
This is the single cleanest alignment check: compute 600519's `q_roe` and `roe`
for 2018-Q1 (as known on 2018-06-06) on JoinQuant. You should get `q_roe ≈ 9.16`
and `roe_waa = indicator.roe ≈ 24.93` (parent-company). If you get a materially
different `q_roe` you have the parent-company / single-quarter math wrong (§6).
And 600519 must fail the universe filter (PB ≈ 10 > 6).

---

## 14. Acceptance Tests (replication is correct if ALL pass)

1. **Factors are parent-company-based.** `q_roe`/`q_dt_roe` use
   `np_parent_company_owners` and `equities_parent_company_owners`, NOT total
   net profit / total equity. (Spot-check 3-5 names vs a known quarter.)
2. **Universe filter** = exactly (`net_profit_yoy ≥ 0`, `roe ≥ 0`,
   `0.30 < pb ≤ 6.00`) on PIT (T−1) values; full universe, no segment exclusion.
3. **Weights** match §3 to 4 decimals and sum to 1.000.
4. **Concentration** = `[0.325, 0.325, 0.11667, 0.11667, 0.11667]` × scale.
5. **Rebalance cadence** = 15 trading days (≈16-17 rebalances/year).
6. **Limit-up substitution is active** — verify some buy orders are skipped/
   substituted and that **OOS deployment is materially below 100%** (expect
   ~55-65% invested in 2020-2026, ~90%+ in 2014-2019). If you are always ~100%
   invested, the substitution / unbuyability is not wired — fix it.
7. **OOS (2020-2026) CAGR lands in roughly the 60-90% band**, NOT ~190% (would
   mean fills are unrealistic) and NOT ~8% (would mean the §0.3 signal bugs are
   present). Full-period CAGR ≈ 100-110%, MaxDD shallow (cash-drag artifact).
8. **Costs** = JQ-default OrderCost + FixedSlippage(0.0003).
9. **Basket alignment (§13.2)** — on at least the four reference dates, your
   pre-substitution top-5 ranking should match the §13.2 names (allow minor
   ordering differences from vendor-data noise, but the SET should overlap ≥3/5).
   Confirm 600519 is excluded by the PB cap and that 920xxx.BJ names appear on
   2023-06-08 IF you include 北交所. A clean per-factor check: 600519 `q_roe`
   ≈ 9.16 and `indicator.roe` ≈ 24.93 as known on 2018-06-06 (§13.4).

Report back: IS CAGR, OOS CAGR, full CAGR, full MaxDD, Sharpe, mean OOS
deployment %, mean holding count, number of blocked/substituted orders, and the
top-5 baskets on the four §13.2 reference dates (for alignment audit).

---

## 15. Reference artifacts (research side, for cross-check)

- Signal engine: `workspace/scripts/sandbox_v15aa_v32_open_execution.py`
  (factor pipeline, exact weights, universe filter).
- Event-driven harness: `workspace/scripts/sandbox_v15aa_v33_event_driven.py`
  (the realistic run this spec is based on).
- Result: `workspace/outputs/v33_event_driven_results.txt` and
  `v33_event_driven_report.parquet`.
- Factor-alignment dump (full, all 4 dates + coverage): generator
  `workspace/scripts/v33_factor_alignment_dump.py`, output
  `workspace/outputs/v33_factor_alignment.txt` (source of the §13 tables).
- Durable record: the 2026-05-29 v33 note at the top of `project_state.md`.

If any instruction here is ambiguous, the research-side `build_ranked` +
`ConcentratedRankedStrategy` in `sandbox_v15aa_v33_event_driven.py` is the
tie-breaker for signal + portfolio construction, and the project's
`EventDrivenBacktester` is the tie-breaker for execution semantics.

---

## 16. Code-format reminder (host project vs JoinQuant)

Stock codes differ across systems — never mix them; JoinQuant silently returns
empty results rather than erroring on a wrong format.

| Stock | Tushare (research) | JoinQuant |
|---|---|---|
| 平安银行 | `000001.SZ` | `000001.XSHE` |
| 贵州茅台 | `600519.SH` | `600519.XSHG` |
| 沪深300 | `000300.SH` | `000300.XSHG` |

Convert: 深交所 (000/002/300 → `.XSHE`), 上交所 (600/601/603/688 → `.XSHG`).

---

End of v33 specification.
