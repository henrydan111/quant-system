# JQ-Derived Regime-Rotation Research — Targeting 50%+ CAGR / <40% MDD

Created: 2026-06-08 (autonomous /goal). Source idea bank:
`C:\Users\henry\Desktop\聚宽回测系统\聚宽克隆策略\克隆策略优缺点与因子库.md`.

This effort EXTENDS the prior `workspace/research/long_only_50cagr/` effort. It does not repeat
the exhaustive static long-only stock-selection sweep that effort already completed.

---

## 0. Inherited hard facts (do not re-litigate)

- **Prior effort (clean PIT, exhaustive on static long-only stock selection):** honest IS ceiling
  ≈ 12–16% CAGR at <30% MDD; only VALUE and LOW-VOL work long-only; momentum/reversal and ML
  produce catastrophic top-K (falling knives); small/microcap STATIC tilt HURTS. Deployable OOS book
  = value+low-vol k40 monthly RAW → +6.2% price / **+11.6% total return (event-driven, dividends)**,
  −14.5% MDD, beats benchmarks (−42% to −46%). **50%/<30% declared infeasible on clean PIT long-only.**
- **Sealed OOS 2021-01→2026-02 is SPENT** on the prior value/low-vol/V-only/ML configs. The 2021-26
  regime is KNOWN to be choppy (trend overlays whipsawed). => OOS is contaminated for any timing design;
  walk-forward within IS is the primary robustness check; OOS = at most one heavily-discounted confirmation.
- **Data is stock-only.** No ETF / fund / foreign-asset / index-futures data. => JoinQuant ETF-momentum
  family (五福/四季/七星/四象), foreign defensive legs, and clean long-short/market-neutral legs are
  **untestable here.** Index data (7 indices, 2008–2026) and PIT-safe SW2021 industry labels ARE available.
- **All numbers from `sandbox_v*` (v31/v32/val_heavy "190% champions") are PIT-lookahead artifacts — INVALID.**

## 1. Splits (frozen before any tuning)

- **IS / development:** 2014-01-01 → 2020-12-31 (2015 bubble+crash, 2018 bear). Factor warmup from 2013-01.
- **Walk-forward (robustness, inside IS):** `build_walk_forward_folds` (5y train / 2y test, step 1y).
- **Sealed OOS:** 2021-01-01 → 2026-02-27. Run AT MOST ONCE, only if a genuinely new design clears the
  IS+WF bar; result reported as a CONTAMINATED confirmation (regime character already known), not a clean test.

## 2. Modules to test (IS only first; reuse prior tooling)

Reuse, do NOT rewrite: `compute_factors()` (PIT-safe, Ref(...,1)), cached `factors_is/oos.parquet`
(31 factors incl. `val_cftp`), `backtest_harness.run_composite_backtest` (VectorizedBacktester),
`overlay.py` (trend/vol-target, both `shift=1` PIT-safe), `research_utils.build_universe_mask`,
`factor_eval` (IC/quantile/decay), `result_analysis/metrics.py`. EventDriven for final realism+capacity.

- **M0 — Cleanest JQ baseline (大市值价值 / financial-authenticity gate).** Concentrated value book:
  liquid non-ST universe → quality gate (OCF>0, deducted-profit>0, ROA high, netprofit-YoY>0, cheap on B/P
  or C/P) → rank by C/P (`val_cftp`) ± ROA → top-K∈{5,10,20}, monthly. "选不出票即空仓" natural timing
  emerges from an absolute gate. Establish honest IS CAGR/MDD. Lowest-overfit JoinQuant idea.
- **M1 — C/P ∩ low-vol intersection (价值低波).** `val_cftp` top quantile ∩ low-vol decile, equal-weight,
  vs prior VL composite. Confirm the orthogonal-intersection construction.
- **M2 — slope×R² trend-smoothness momentum (T-1, PIT-safe).** Build custom operator
  `Slope(log ADJ_CLOSE_T1, N) * Rsquare(...)`; evaluate IC + long-only top-K. Does ×R² smoothness rescue
  momentum where plain momentum failed? Standalone + as a bull-regime tilt.
- **M3 — Regime/style rotation (the high-CAGR lever).** PIT-safe index-momentum regime from index data
  (中证1000/000852 vs MA(N) lag-1; large-vs-small 000300/000852 relative momentum). States:
  small-cap risk-on → small-cap QUALITY book; large-cap/defensive → value+low-vol; both weak → cash.
  Tiny grid (MA∈{120,200}; ≤2 thresholds). Does regime-GATED small-cap capture lift CAGR materially at
  MDD<40%? (Prior static small tilt hurt — the gate is the untested delta.) Walk-forward mandatory.
- **M4 — Sector momentum tilt.** Industry-relative momentum (`mom_industry_rel_20d`) / sector-mean
  momentum overweight. Additive test only.
- **M5 — Inverse-vol position weighting** vs equal-weight on the chosen book (MDD lever).

## 3. Combination & verdict

Add survivors ONE module at a time; track CAGR / MDD / Sharpe / Calmar / yearly returns / turnover /
trade count / worst year / cost sensitivity (all via `result_analysis/metrics.py`). Capacity check (ADV,
event-driven) for any small-cap-tilted result — the JQ audit's #1 trap is ¥100k looks-great / ¥10M dies.
Report the honest IS ceiling vs the 50%/<40% target. If 50% is unreachable honestly, document exactly
where and why it falls short, and deliver the best honestly-deployable strategy.

## 4. Non-negotiable discipline (CLAUDE.md §7)

Temporal splits only; OOS sacred (≤1 look, disclosed); realistic costs (NO zero-slippage); PIT via
sanctioned doors only; small parameter grids; walk-forward before OOS; centralized metrics; MLflow for
substantive runs; survivorship-safe universe (all_stocks incl. delisted); **no hedge words — run the data
or mark unverified with the test that resolves it.**

## 5. Expected outcome (stated up front, honestly)

Prior exhaustive work + the JQ audit's own conclusion (all "X倍/无惧牛熊" versions = microcap beta +
zero-slippage + handpicked pools + multiple-comparison) make 50% CAGR on clean PIT A-share long-only
*a priori* unlikely. The legitimate question this effort answers with data: **how much does PIT-safe
regime-conditional style rotation lift the honest ceiling above the static ~16%, and at what MDD/capacity?**
A negative result (cannot honestly reach 50%) is a valid, valuable deliverable if the data shows it.
