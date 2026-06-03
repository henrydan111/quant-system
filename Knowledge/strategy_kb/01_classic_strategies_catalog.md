# 01 — Classic Strategy Catalog (cards)

Distilled from Qbot `docs/02-经典策略/`. Each card is re-mapped onto our factor catalog, the 8
orchestrator profiles, and the two engines. **The "PIT / leakage traps" row is ours, not Qbot's** —
Qbot's write-ups carry no PIT guard. Coverage: ✅ have · 🟡 partial · ⬜ gap.

Catalog reference for the factor names used below: `get_factor_catalog()` (171 factors;
categories `val_* qual_* grow_* lev_* liq_* mom_* size_* risk_*` + Layer-2 composites
`comp_*` + industry-relative). See [src/alpha_research/README.md](../../src/alpha_research/README.md).

---

## Card 1 — Multi-factor stock selection (多因子选股) · ✅ have

| | |
|---|---|
| **Category** | Trend-following / quantitative selection |
| **Core logic** | Score every stock by a weighted blend of factors, rank, hold top-k, rebalance. The workhorse archetype. |
| **Signal / factors** | Any subset of our 171-factor catalog. Qbot's reference is a **Fama-French 3-factor** cut → our analogs: market β (none stored, derivable), **size = `size_ln_mcap`**, **value = `val_bp` (book-to-price = HML)**. Richer blends use `qual_roe`, `grow_netprofit_yoy`, `mom_return_20d`, `val_ep_ttm`. |
| **Universe / rebalance / hold** | Qbot ref: CSI300, monthly first trading day, equal-weight top-10, 80% capital. Ours: configurable in the prescription. |
| **Regime fit** | Strong trending / high-dispersion; weak when factor spreads compress. |
| **Our-system path** | Discovery: `factor_screening` profile → ranks/evaluates factors. Validation: `hypothesis_validation` with a `PrescribedRecipe` (universe + components + weights + topk + rebalance + cost). Engine: `VectorizedBacktester` for screening, `EventDrivenBacktester` for the formal run. Composite blends already exist as `comp_*` Layer-2 factors. |
| **PIT / leakage traps** | (1) Fundamentals MUST align on `ann_date` + `shift(1)`; the Fama-French book-to-market uses *reported* book value — load via `pit_research_loader.load_pit_signal_panel` (lag-1), never raw `pit_ledger`. (2) Factor at T must not read close[T] — use `Ref(...,1)`. (3) Monthly rebalance on "first trading day" = use the trade calendar, not month-start dates. |
| **Coverage** | ✅ Core of the whole system; 87/171 factors already `candidate` via the factor-lifecycle arc. |

---

## Card 2 — Fama-French 3-factor (as an explicit model) · 🟡 partial

| | |
|---|---|
| **Category** | Trend-following / selection (regression-scored) |
| **Core logic** | Sort by size (50th pct) × book-to-market (30/70 pct) → 6 portfolios; SMB = small−big, HML = highBM−lowBM; regress each stock's excess return on (Rm−Rf, SMB, HML); pick the most **negative-alpha** (undervalued) names. |
| **Signal / factors** | `size_ln_mcap` (size sort), `val_bp` (book-to-market sort). The regression-alpha residual is *not* a stored factor. |
| **Universe / rebalance / hold** | CSI300, monthly, top-10 most-undervalued, equal weight. |
| **Regime fit** | Classic value+size; size leg has been weak post-2016 in A-shares. |
| **Our-system path** | Constructing the SMB/HML breakpoint portfolios is a `factor_screening`-adjacent task; the per-stock regression-alpha is a **new derived signal** → propose as a candidate factor, validate via `hypothesis_validation`. |
| **PIT / leakage traps** | Rolling β/loadings must be estimated on a **trailing** window ending before T; book value is PIT (`ann_date`). The residual-alpha sort is the leakage-prone step — the regression window cannot include the holding period. |
| **Coverage** | 🟡 Size/value inputs exist; the regression-alpha construction has not been run. Backlog item. |

---

## Card 3 — Small-cap (小市值) · ✅ have (inputs) / 🟡 as a standalone strategy

| | |
|---|---|
| **Category** | Trend-following / selection (single-factor extreme) |
| **Core logic** | Rank entire A-share universe by total market cap ascending; hold the smallest N; monthly rebalance. |
| **Signal / factors** | `size_ln_mcap` (sort ascending = smallest first). |
| **Universe / rebalance / hold** | All A-shares; **exclude** ST, suspended, B-shares, <100-days-listed, delisted; 30 holdings (also 10/20 tested); monthly, first trading day ~09:40; equal-weight, 80% capital. |
| **Regime fit** | Historically huge in A-shares pre-2016; Qbot's own note: "significant drawdown", weak/ineffective 2015–2020. **High crash/liquidity risk.** |
| **Our-system path** | Trivial to express: `size_ln_mcap` bottom-decile in `factor_screening`. The **filters are the real content** — ST via `data/qlib_data/instruments/st_stocks.txt`, IPO 90-day lag + delist via the instruments sidecar (`provider_metadata.build_all_stocks_universe`). Run on `EventDrivenBacktester` so T+1 + limit-up-at-open (small caps gap to limit) are modelled. |
| **PIT / leakage traps** | (1) **Survivorship** — must use the historical universe incl. delisted names (our instruments sidecar handles this; a raw-ledger read bypasses it). (2) Small caps frequently hit limit-up at open → set `forbid_all_trade_at_limit=True`. (3) ST detection must use the range-form `st_stocks.txt`, not `stock_st_daily`. |
| **Coverage** | ✅ factor + filters available; ⬜ no governed end-to-end small-cap run on record. Good **regime-diversification** candidate but flag the drawdown profile. |

---

## Card 4 — Index enhancement (指数增强) · 🟡 partial

| | |
|---|---|
| **Category** | Index-exposure axis → relative return |
| **Core logic** | Hold a portfolio that tracks a benchmark (CSI300/500) but tilts weights toward high-factor-score names within a **tracking-error budget** → benchmark + small consistent alpha. |
| **Signal / factors** | Same factor blend as Card 1, applied as *active weights* vs benchmark weights, not a top-k cut. |
| **Universe / rebalance / hold** | Benchmark constituents (PIT membership!); monthly; weights from optimizer s.t. TE ≤ target, per-name and sector active-weight bounds. |
| **Regime fit** | Strong in bull, moderate sideways, weak bear (still long-only). |
| **Our-system path** | `PortfolioOptimizer` (cvxpy) in [src/portfolio_risk/](../../src/portfolio_risk/) is the natural home — **but that module is currently dormant** (risk model returns hardcoded 0.05, see CLAUDE.md §3 dormant-import boundary). Index enhancement is the **strongest concrete reason to promote `portfolio_risk` from dormant → real** (need a covariance/risk model for TE). |
| **PIT / leakage traps** | Benchmark constituent membership must be **point-in-time** (index reconstitution changes the set) — use the PIT index-weight tables, not today's membership. Benchmark codes use underscore form (`000300_SH`). |
| **Coverage** | 🟡 factors + optimizer scaffold exist; risk model dormant. Backlog: requires a real `MultiFactorRiskModel`. |

---

## Card 5 — Alpha hedge / market-neutral (Alpha对冲) · ⬜ gap

| | |
|---|---|
| **Category** | Relative-value / market-neutral |
| **Core logic** | Long a factor-selected stock book + short index futures sized to neutralize β → harvest pure alpha, β≈0. Stable in bull *and* bear. |
| **Signal / factors** | Long leg = Card 1 blend; hedge ratio = portfolio β to the index. |
| **Universe / rebalance / hold** | Long book monthly; futures hedge rolled at contract expiry; β re-estimated each rebalance. |
| **Regime fit** | The matrix's **bear/sideways winner** — exactly the regime our long-only catalogue is weak in. |
| **Our-system path** | Long leg is fully expressible today. **The short futures leg is the gap** — no futures data, no futures instrument in the engine. Minimum viable version: model the hedge as a short CSI300/500 *index return* overlay (synthetic, no basis/roll) inside a custom result-analysis overlay, clearly labelled as idealized. |
| **PIT / leakage traps** | β must be estimated on a trailing window; the hedge notional uses yesterday's β. Synthetic-hedge version must NOT claim futures-basis realism. |
| **Coverage** | ⬜ Highest-value strategic gap. Closing it = our first non-long-only, regime-diversifying capability. |

---

## Card 6 — RSRS timing (阻力支撑相对强度择时) · ⬜ gap

| | |
|---|---|
| **Category** | Trend-following / market timing overlay |
| **Core logic** | Daily OLS of **high ~ low** prices over N days → slope β is a "resistance-support relative strength". Standardize β over a long window (z-score) → standardized RSRS. Buy when RSRS z > +S, sell/flat when < −S. A *timing* signal, usually applied to an index or as a portfolio-level on/off switch. |
| **Signal / factors** | New — not in our catalog. Inputs: `$high`, `$low` (kline). Typical params: N≈18 regression window, M≈600 standardization window, threshold S≈0.7. |
| **Universe / rebalance / hold** | Applied to a benchmark index or as a global risk switch; daily evaluation. |
| **Regime fit** | Cuts drawdown in trend breaks; whipsaws in choppy markets. |
| **Our-system path** | Express as a Qlib expression over `Ref($high,1)/Ref($low,1)` (regression slope via rolling cov/var operators) → a new candidate factor / signal. Use it as a **regime overlay** on top of Card 1 selection rather than standalone. Validate via `event_driven_signal_research` or `hypothesis_validation`. |
| **PIT / leakage traps** | Regression + standardization windows must end at T−1 (`Ref(...,1)` on both high and low). The z-score's long window must be strictly trailing — a full-sample standardization is the classic RSRS lookahead. |
| **Coverage** | ⬜ Not implemented. Cheap to prototype; good drawdown-control research item. |

---

## Card 7 — Bollinger mean-reversion (布林线均值回归) · 🟡 partial

| | |
|---|---|
| **Category** | Relative-value (mean reversion) |
| **Core logic** | Price band = MA ± k·σ over N days. Buy when price pierces the lower band (oversold), sell at the mean/upper band. |
| **Signal / factors** | MA(close,N), rolling σ(close,N); z = (close−MA)/σ. Related to our `risk_vol_20d`. |
| **Universe / rebalance / hold** | Per-name signal; short holding; works on liquid names. |
| **Regime fit** | Sideways/range-bound; **bleeds in strong trends** (keeps buying the dip). |
| **Our-system path** | Pure Qlib-expression factor: `(Ref($close,1) - Mean(Ref($close,1),20)) / Std(Ref($close,1),20)`, signed for reversion. Screen via `factor_screening`. Mind A-share T+1 + limit rules on entries. |
| **PIT / leakage traps** | Same-day close leakage is the #1 bug — band must be built from `Ref($close,1)`. |
| **Coverage** | 🟡 Volatility input exists; the reversion z-signal not run as a strategy. |

---

## Card 8 — Dual moving-average / MACD / KDJ (双均线 / 技术指标) · 🟡 partial

| | |
|---|---|
| **Category** | Trend-following (technical timing) |
| **Core logic** | Fast MA crosses slow MA → long/flat (golden/death cross). MACD, KDJ, RSI, BOLL are the same family of price-derived technical triggers (Qbot lists 40+). |
| **Signal / factors** | EMA/MA crossovers, MACD histogram, etc. We have `mom_*` momentum factors but not the classic crossover *triggers*. |
| **Universe / rebalance / hold** | Per-name or index timing; event-triggered rebalance. |
| **Regime fit** | Trending; whipsaws sideways. |
| **Our-system path** | Trivial as Qlib expressions; better used as **features feeding `ml_signal_model_research`** than as standalone single-rule strategies (single-MA-cross rarely survives costs in A-shares). |
| **PIT / leakage traps** | Crossover evaluated on `Ref(...,1)` series; trade next open. |
| **Coverage** | 🟡 momentum factors exist; classic triggers not catalogued. Low research priority (well-mined, low edge). |

---

## Card 9 — Grid trading (网格交易) · ⬜ gap (low priority)

| | |
|---|---|
| **Category** | Relative-value (range harvesting) |
| **Core logic** | Place a ladder of buy/sell orders at fixed price intervals around a center; profit from oscillation. |
| **Regime fit** | Range-bound only; **catastrophic in a sustained trend** (accumulates into a falling asset). |
| **Our-system path** | Needs intra-range order simulation our vectorized engine doesn't model well; `EventDrivenBacktester` could but T+1 kills the round-trip cadence. |
| **PIT / leakage traps** | n/a (price-reactive) but A-share T+1 makes the classic grid largely inapplicable to single stocks. |
| **Coverage** | ⬜ Low priority — poor fit for T+1 equities; more an ETF/crypto pattern. |

---

## Card 10 — Pairs trading / statistical arbitrage (配对交易) · ⬜ gap

| | |
|---|---|
| **Category** | Relative-value / arbitrage (market-neutral) |
| **Core logic** | Find two cointegrated names; trade the spread z-score — long the cheap, short the rich, converge to mean. |
| **Signal / factors** | Cointegration test + rolling spread z-score; new construction. |
| **Universe / rebalance / hold** | Within-sector liquid pairs; daily spread monitoring. |
| **Regime fit** | Market-neutral; works sideways; risk = regime break / de-cointegration. |
| **Our-system path** | Long leg easy; **short leg blocked** (no single-stock shorting / borrow in A-shares for most names) → realistically only via ETF pairs or as a long-only "buy the laggard" relative-value tilt. |
| **PIT / leakage traps** | Cointegration estimated on a trailing window; the classic error is selecting the pair using the full sample then "backtesting" on it. |
| **Coverage** | ⬜ Gap; constrained by A-share short-sale reality. Catalog as relative-value research, ETF-pairs variant. |

---

## Card 11 — 4433 fund rotation (4433法则) · ⬜ gap (out of equity scope)

| | |
|---|---|
| **Category** | Trend-following (momentum rotation, funds) |
| **Core logic** | Rank funds: top-1/4 over 1y AND top-1/4 over recent 3/6m AND top-1/3 over 3m AND 1m → rotate into persistent out-performers. |
| **Our-system path** | We have no fund NAV dataset; this is a momentum-persistence pattern transferable to **stocks/industries**: top-quartile-across-multiple-horizons momentum filter using `mom_return_*`. |
| **PIT / leakage traps** | All ranking windows trailing; standard momentum PIT rules. |
| **Coverage** | ⬜ Funds out of scope; the multi-horizon momentum *idea* is a cheap factor-screening experiment. |

---

## Card 12 — Limit-up board-opening (涨停开板) & inflection-point (拐点) · ⬜ gap

| | |
|---|---|
| **Category** | Event-driven (microstructure) |
| **Core logic** | Trade stocks that sealed limit-up then the board "opens" (sell pressure breaks the limit), or local price inflection points — short-horizon momentum/sentiment events. |
| **Signal / factors** | Needs limit-up flags + intraday/board-opening data we don't have at daily granularity. Our `stk_limit` dataset (up/down limit prices) exists but is **quarantined** in the field registry (CLAUDE.md §3, PR 5). |
| **Regime fit** | Speculative/retail-driven momentum; very high turnover. |
| **Our-system path** | Blocked twice: (1) needs intraday board-opening data (we're daily); (2) `stk_limit` is quarantine — cannot enter formal validation until anomaly-reviewed and promoted via a `field_approval_log` entry. |
| **PIT / leakage traps** | Limit-up flag at T must not use T's close; intraday board-opening is inherently same-day → only tradable T+1 here, which destroys the edge. |
| **Coverage** | ⬜ Gap; data + T+1 constraints make it low-feasibility. Documented to record *why* it's parked. |

---

## Quick coverage summary

| Card | Coverage | Note |
|---|---|---|
| 1 Multi-factor selection | ✅ | core of the system |
| 2 Fama-French regression-alpha | 🟡 | inputs exist, regression-alpha unbuilt |
| 3 Small-cap | ✅/🟡 | factor+filters yes, no governed run |
| 4 Index enhancement | 🟡 | needs portfolio_risk un-dormant |
| 5 **Alpha hedge / market-neutral** | ⬜ | **highest-value gap** (regime diversifier) |
| 6 RSRS timing | ⬜ | cheap drawdown-control overlay |
| 7 Bollinger reversion | 🟡 | easy factor, not run |
| 8 Dual-MA / MACD | 🟡 | low edge, ML-feature use |
| 9 Grid | ⬜ | poor T+1 fit |
| 10 Pairs / stat-arb | ⬜ | short-sale constrained |
| 11 4433 rotation | ⬜ | funds OOS; momentum idea transferable |
| 12 Limit-up / inflection | ⬜ | data + T+1 blocked |
