# Design — Market-Neutral / Index-Hedged Leg from the 6 Approved Factors

**Status:** DESIGN for review (no code/run yet). **Author:** Claude, 2026-06-04.
**Decision owner:** user (+ optional GPT cross-review), mirroring prior research phases.

## 1. Objective & why now

The live book is **100% long-only** (the `long_only_50cagr` defensive value+low-vol top-40,
just confirmed tradable at +11.64% total return / −14.5% MDD / 0.80 Sharpe over 2021-26). The
strategy-KB taxonomy names the **single biggest diversification gap** as a **market-neutral /
relative-value leg** (`Knowledge/strategy_kb/00_strategy_taxonomy.md`, Card 5) — the long-only
book is weak in bear/sideways regimes; a β≈0 alpha leg is the complement.

We now have raw material for it: the **6 sealed-OOS `approved` factors** (the first approved-tier
factors), each with a paper cross-sectional **LS Sharpe > 1.0** @ 5d primary horizon — i.e. a
*market-neutral* edge by construction (cross-sectional, dollar-balanced). This design turns those
6 into a candidate MN leg, within the hard A-share constraints.

The 6 (sign-oriented to `expected_direction` in the registry; all positive after orientation):

| factor | category | oriented dir | OOS rank_icir | OOS LS Sharpe (5d) |
|---|---|---|---|---|
| `liq_zero_ret_days_10d` | liquidity | (inverse raw) | +0.41 | +2.14 |
| `rev_turnover_spike_5d` | reversal | + | +0.28 | +2.68 |
| `grow_total_revenue_yoy_accel_q` | growth-accel | + | +0.26 | +3.44 |
| `grow_n_income_attr_p_yoy_accel_q` | growth-accel | + | +0.25 | +1.96 |
| `grow_operate_profit_yoy_accel_q` | growth-accel | + | +0.20 | +1.49 |
| `qual_piotroski_fscore_9pt` | quality | + | +0.21 | +1.20 |

## 2. The three hard constraints (these shape everything)

1. **OOS is burned.** 2021-26 was spent once for the frozen-13 set these 6 came from (and the
   calendar is frozen at 2026-02-27 → no fresh OOS window exists). **There is no clean OOS for
   these factors.** Any 2021-26 result on them is IS-construction + a contaminated read, NOT
   clean evidence. (A genuinely-sealed test requires post-2026 data the system does not yet have.)
2. **No short instrument.** KB Card 5 + Card 8: A-shares have **no single-stock borrow** for most
   names, and **the system has no index-futures data and no futures instrument in the engine.**
   So a true stock-level long/short and a real futures hedge are both **untestable today**.
3. **Cross-sectional LS ≠ long-only net.** The `long_only_50cagr` KEY FINDING: in A-shares,
   cross-sectional IC factors make *catastrophic* long-only top-K (falling knives); only
   value/low-vol convert. Of these 6, reversal/liquidity/growth-accel are exactly that risk —
   only `qual_piotroski` plausibly survives naked long-only.

## 3. The three realizable forms (and what each can/can't prove)

| Form | What it is | Deployable? | What it proves | Constraint |
|---|---|---|---|---|
| **A. Paper cross-sectional LS** | long top-Q composite, short bottom-Q, equal notional | **No** (no single-stock short) | the factor *alpha* exists & its magnitude (IS) | research measurement only |
| **B. Synthetic index-hedged long** | long top-Q book − β·(CSI300/500 index return), β on trailing window | **Idealized only** (KB Card 5 MVP: synthetic, no basis/roll/borrow cost) | the β≈0 alpha *after* market removal | no futures data → cannot claim basis/roll realism |
| **C. Enhanced-index long-only** | long top-Q tilt vs benchmark (fully investable) | **Yes** | the *active* (excess) return a long-only tilt captures | captures only the long half of the LS edge |

**Recommendation:** build A + B + C on **clean IS 2014-2020**, in that order. A measures the raw
alpha; B is the closest-to-MN form testable today (explicitly idealized per Card 5); C is the only
*deployable-today* form (no shorting needed). Do **not** present B as a real market-neutral return
(no futures basis/roll/borrow) — label it "idealized synthetic hedge."

## 4. Construction

- **Signal:** reuse `compute_factors()` (PIT-safe wrapper, `Ref(...,1)`-shifted) for the 6 over
  COMPUTE_START 2013 → IS 2014-2020. Composite = equal-weight cross-sectional rank, each factor
  oriented to its registry `expected_direction` (the `build_composite_signal` pattern from
  `long_only_50cagr/backtest_harness.py`, re-weighting only — no new data access).
- **Universe:** the `core` liquid non-ST universe (same as long_only) — MN needs tradeable names
  on both nominal legs.
- **Quantiles:** `factor_eval.compute_quantile_returns` / `compute_long_short_returns` (the exact
  tools the screening + promotion harness used) for form A; the long_only top-K harness for C.
- **Hedge (form B):** synthetic — subtract `β · index_return` (CSI300=000300_SH or CSI500=000905_SH),
  β estimated on a **trailing** window (PIT-safe, yesterday's β), via a custom overlay in
  `result_analysis` or by extending `long_only_50cagr/overlay.py`. No futures contract simulated.

## 5. Validation protocol (honest, given the burned OOS)

- **IS walk-forward 2014-2020** (5y/2y/1y, `build_walk_forward_folds`) for forms A/B/C: LS Sharpe,
  IC/ICIR, quantile monotonicity, decay, turnover, capacity, per-fold sign stability.
- **No clean OOS.** 2021-26 is burned for these factors → if run at all, label it explicitly
  "contaminated / not OOS." A genuinely-sealed validation needs post-2026 data (not available).
- **Realistic costs** for form C (deployable): JoinQuant `CostConfig()`, and remember the
  **vectorized=price-return caveat** — for net-return claims on a high-yield tilt, use the
  EventDriven (total-return) engine or label vectorized output "price return."
- **MLflow** logging for any substantive run; **no hedge words** on results (CLAUDE.md §7.10).

## 6. Risks / open questions for cross-review

1. **Selection staleness / no-clean-OOS.** These 6 were chosen using data through 2026; their
   2021-26 OOS is spent. Is an *IS-only* (2014-2020) re-validation of an MN composite built from
   them meaningful, or is the edge already too contaminated to trust without fresh data? (My view:
   IS walk-forward measures whether the *composite* has stable cross-sectional alpha in-sample —
   useful as R&D signal — but deployment must wait for a clean post-2026 OOS or be treated as
   paper.)
2. **Is form B worth building** given it's idealized (no futures data)? Or jump straight to form C
   (deployable) + a paper-LS (form A) alpha measurement, and defer B until index-futures data is
   ingested (a data-infra prerequisite — a separate ticket)?
3. **Factor mix:** all 3 `grow_*_yoy_accel` are one theme (growth acceleration) — the composite is
   effectively liquidity + reversal + (3× growth-accel) + quality. Down-weight the growth cluster
   to avoid theme concentration?
4. **Capacity / crowding:** reversal + liquidity signals are capacity-limited and crowded; the MN
   book's realistic capacity + the long_only book's overlap (does the MN leg just re-buy the
   long-only names?) need checking.
5. **Should this even be a registry strategy yet?** Factor `approved` ≠ tradable-strategy validated;
   strategy promotion is a separate gate, and with no clean OOS this can't pass it. So this is
   explicitly **exploratory R&D toward the MN leg**, not a promotion candidate.

## 7. Phased plan & deliverables (if approved to build)

- **P1** — compute the 6 over IS (cache `factors_is.parquet`), build the oriented composite, run
  **form A** (paper LS) walk-forward → does the composite have stable IS cross-sectional alpha?
- **P2** — **form C** (enhanced-index long-only tilt) IS walk-forward + EventDriven net-return
  (total-return) → the deployable-today read.
- **P3** — **form B** (synthetic index-hedged) IS, clearly labeled idealized → the β≈0 alpha read.
- **P4** — write FINDINGS; if the IS edge is real + stable, file the **index-futures-data ingestion**
  as the data-infra prerequisite for a *real* MN leg + a future clean-OOS plan.
- Workspace: `workspace/research/market_neutral_leg/` (scripts, FINDINGS.md), outputs under
  `workspace/outputs/market_neutral_leg/`.

## 8. Verdict requested

GO to build P1 (paper-LS IS validation) as the first step — or redirect (e.g., "form C first",
"defer B", "down-weight growth", "this needs fresh data before any build"). The whole effort is
IS-only R&D with no clean OOS available; deployment is gated separately.
