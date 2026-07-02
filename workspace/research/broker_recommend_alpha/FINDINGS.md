# 券商金股 (broker_recommend) Mother-Signal Validation — FINDINGS

**Date:** 2026-06-28
**Question:** Does the raw 券商月度金股 list carry deployable alpha (Option A of the
"量化选股 + AI 主观增强" framework)?
**Verdict:** **NO.** The apparent edge is a small/mid-cap **size tilt**, not selection alpha.
Against a size-matched benchmark the signal has **zero-to-negative** excess (even with a
dividend bias in its favor), and broker **conviction is anti-predictive**.

---

## Data (newly ingested, RAW)

- Endpoint `broker_recommend` (Tushare doc_id=267, 6000积分), ingested by
  [scripts/fetch_broker_recommend_historical.py](../../../scripts/fetch_broker_recommend_historical.py)
  → `data/analyst/broker_recommend/broker_recommend_{YYYYMM}.parquet`.
- **72 months, 2020-07 .. 2026-06**, 16,706 rows, 2,236 stocks, 80 brokers. History
  effectively **starts 2020-07** (earlier months empty). Schema: `month/broker/ts_code/name`
  (no per-row disclosure date, no rating/target/weight).
- **Conviction is sparse:** mean 1.30 brokers/stock-month, **81% single-broker**, max 13.
- **Broker coverage swings 10–44/month** → counts comparable only within-month.

## Method (PIT-correct, reuses 果仁/jq replication tooling)

- **Visibility anchor:** month-M list tradable at the first trading day **on/after day-4 of M**
  (`entry_d4`, buffers the "1–3日内更新" lag). `entry_d1` run as a sensitivity leg.
- **No-lookahead simulator:** equal-weight, buy-and-hold within block, explicit cash, turnover
  cost ≈0.32%/full-turnover (mirrors `jq_rep_utils.simulate_eqw_monthly`). Book earns strictly
  from the day AFTER each rebalance.
- **Prices:** sanctioned `D.features([...], ["$close*$adj_factor"])` adjusted-close (=total return),
  100% coverage of recommended names. Universe = `board_of ∈ {main, chinext, star}` (excludes 北证/BSE/B-share).
- **Usable window:** holding months **202007..202601 (67 rebalances)**, realized through 2026-02
  (trade calendar frozen at 2026-02-27, so 2026-03..06 lists have no forward window yet).

## Results (2020-07-07 .. 2026-02-27, EW, after cost)

| Book | CAGR | MDD | Sharpe | vs 沪深300 | vs 中证500 | vs 中证1000 |
|---|---|---|---|---|---|---|
| **金股 EW (d4, deployable)** | **3.24%** | **−52.1%** | **0.26** | **+3.08%** | **−2.79%** | **−1.30%** |
| 金股 EW (d1, optimistic) | 5.50% | −50.0% | 0.35 | +5.34% | −0.53% | +0.96% |
| 金股 conviction≥2 (d4) | −1.64% | −57.6% | 0.04 | — | −7.68% | — |
| 金股 conviction≥3 (d4) | −9.38% | −75.5% | −0.21 | — | −15.41% | — |
| 沪深300 (000300) | 0.16% | −45.6% | 0.10 | | | |
| 中证500 (000905) | 6.03% | −41.8% | 0.38 | | | |
| 中证1000 (000852) | 4.54% | −46.7% | 0.31 | | | |

- **Conviction RankIC** (n_brokers vs fwd-1M): mean **−0.015**, ICIR **−0.148**, %>0 = 42% → flat-to-negative.
- **IS/OOS vs 中证500:** IS (2020-07..2023-12) excess **−0.04%** (zero edge); OOS (2024-01..2026-02)
  excess **−8.44%** (badly lagged the small-cap rally).

## Why the verdict holds (confound checks)

1. **Size illusion:** beating 沪深300 (+3.08%) is purely the EW mid/small tilt; vs size-matched
   中证500/1000 the excess is **negative**. Book AnnVol 22.1% sits between 中证500 (20.9%) and
   中证1000 (23.9%) — a mid/small book that loses to both.
2. **Dividend bias is IN FAVOR of 金股** (total-return book vs price-return index, ~+1–2%/yr) →
   the true size-adjusted deficit is ~**−4% to −5%/yr** vs 中证500.
3. **Even gross (zero cost)** ≈ 6.2% CAGR ≈ 中证500's 6.03% → no gross selection alpha either;
   cost + size drag make it clearly negative.
4. **Conviction anti-predictive:** more brokers agreeing → worse (conv3 −9.4% CAGR, −75% MDD).
   Cannot be rescued by conviction weighting.
5. No-lookahead anchor verified; 100% price coverage (no survivorship gap).

## Implication for the framework

The "量化选股" base of Option A is **not a source of alpha**. 券商金股 can serve only as a
**candidate POOL / watchlist**; any edge must come ENTIRELY from a quant + AI overlay on that pool —
the raw list contributes a slight size drag, not alpha. This matches the deep-research caveat
("benchmark unstated, huge dispersion") and the project's prior 0/8 new-data screen.

## Status / next

- Dataset = **RAW, validation-stage**; NOT formalized (no ledger/provider/registry). Given the
  negative verdict, formal materialization is **not warranted** unless a pool-overlay study revives it.
- New code (`fetch_broker_recommend` + bootstrap) would need a GPT cross-review **only if** the
  dataset is kept/formalized.
- Open options (user decision): (a) drop 金股 as a signal; (b) keep as a candidate pool and test a
  quant/AI overlay; (c) lower-turnover "persistent-pick" variant. No promotion either way.
