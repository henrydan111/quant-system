# 00 — Strategy Taxonomy (the spine)

Distilled from Qbot `docs/01-新手指引/量化策略的分类和原理.md`, re-framed for our A-share equity system.
Use this to **place an idea before spending compute**: which category, which regime, which of our
profiles. The cards in [01](01_classic_strategies_catalog.md)/[02](02_intelligent_methods_and_research_backlog.md)
slot into this frame.

---

## Top-level: three trading philosophies

### 1. Trend-following / directional (趋势性策略)
**Premise:** information diffuses gradually; price momentum persists. Long-biased or long/short.
- **Quantitative stock selection** — multi-factor rank → top-k long. *Our bread and butter.*
- **Equity long/short** — selection + timing overlay, both legs.
- **Macro / multi-asset** — predict macro regime, rotate across asset classes. *Out of our equity scope.*
- **CTA / managed futures** — systematic futures trend or reversal. *Out of scope (no futures module).*

Regime: strong in trending markets, weak in range-bound.

### 2. Relative-value / market-neutral (相对价值策略)
**Premise:** extract mispricing convergence with β≈0; absolute return independent of market direction.
- **Market-neutral / Alpha** — long quant stock portfolio, short index futures to β≈0.
- **Arbitrage** — structural mispricing across related assets / time (pairs, cross-listing, calendar).

Regime: stable across bull/bear; **best in sideways/crisis**; reduces timing risk.

### 3. Event-driven (事件驱动策略)
**Premise:** trade identifiable catalysts — M&A, placements, block trades, limit-up board-opening,
earnings surprises, index reconstitution.
Regime: works when forecastable corporate events create temporary dislocations.

---

## Secondary axis A — index exposure

| | Goal | Construction | Our analog |
|---|---|---|---|
| **Index enhancement** | relative return (beat benchmark) | long-only, tracking-error constrained tilt | `PortfolioOptimizer` + factor tilt vs CSI300/500 |
| **Market neutral** | absolute return | full hedge, β≈0 | long book − short index-future leg (no futures yet ⬜) |

## Secondary axis B — trading frequency

| Band | Annual turnover | Driver | Our fit |
|---|---|---|---|
| Mid-low | 50–100× | fundamental + price/volume factors | ✅ primary regime (monthly/weekly rebalance) |
| Mid-high | ~100× | faster factor refresh | 🟡 possible via daily factors |
| Intraday / T+0 | ~200× | same-day round-trips, end-of-day flat | ⬜ no intraday data/engine; A-share T+1 limits this |

> Our `EventDrivenBacktester` already models A-share **T+1**, multi-tier limits, suspensions — so the
> realistic frequency ceiling for *us* is mid-low to mid-high. T+0 is out of scope.

---

## Market-regime suitability matrix

| Strategy family | Bull | Bear | Sideways / Crisis |
|---|---|---|---|
| Trend-following / selection | Strong | Weak | Weak |
| Index enhancement | Strong | Weak | Moderate |
| Market neutral / Alpha | Moderate | Strong | **Strong** |
| Event-driven | Moderate | Moderate | Variable |
| CTA (out of scope) | Moderate | Strong | Strong |

**Research implication for us:** our catalogue is almost entirely **trend-following / selection**, which
the matrix shows is *weak in bear and sideways*. The biggest diversification gap is a **market-neutral /
relative-value** capability (needs a short/hedge leg) — see the backlog in
[02](02_intelligent_methods_and_research_backlog.md).

---

## Evolution of Chinese quant (context)

Qbot frames domestic quant in ~4 phases (2001→present): early price-volume → multi-factor →
ML integration → execution optimization + fundamental quantification. We sit at the **multi-factor +
ML-integration** stage with strong governance; the frontier directions (RL execution, LLM/news signals,
automated factor generation) are catalogued as backlog, not yet exercised.
