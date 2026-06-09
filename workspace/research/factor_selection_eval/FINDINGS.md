# Is "chase okay-IC + low-correlation, not high-ICIR" sound? — VERDICT: YES, with refinement

Date: 2026-06-08. Empirical test on the cached 31-factor IS panel (2014-2020, PIT-safe, fwd_20d).
Metric = RankIC series per factor; "combined ICIR" = RankICIR of the equal-weight mean of oriented
per-day ranks. Script: `eval_icir_vs_correlation.py`; results: `icir_vs_corr_results.json`.

## Verdict

**The observation is SOUND for MULTI-FACTOR model building, and the data confirms it strongly — but
it must be restated precisely.** The right objective is the COMBINED information ratio, which rewards
each factor's MARGINAL ORTHOGONAL contribution = genuine IC × low correlation to the existing set.
Standalone ICIR is the wrong selection criterion for ADDING a factor; but low correlation is
necessary, not sufficient (zero-IC factors add nothing), and high ICIR is not "bad" — high-ICIR +
low-correlation is ideal. For SINGLE-factor standalone deployment, standalone ICIR IS the right metric.

## The decisive evidence

**C. Greedy-by-ICIR vs greedy-by-marginal (6 factors):**
- Pick the 6 HIGHEST-ICIR factors → combined ICIR = **0.704** (≈ the single best factor 0.711!),
  avg payoff-corr 0.471. They're all the same lottery/liquidity/low-vol cluster → zero diversification.
- Forward-select by MARGINAL combined ICIR → combined ICIR = **1.019** (+45%), avg payoff-corr 0.063,
  and it has LOWER mean IC (0.091 < 0.115). Literally "okay IC + low correlation beats high ICIR."

**D. Breadth law, standalone strength held ~constant:** two 4-factor sets with ~equal avg standalone
ICIR (~0.27):
- LOW-corr quartet (avg corr −0.19) → combined ICIR **0.696**
- HIGH-corr quartet (4 value factors, avg corr +0.89) → combined ICIR **0.278**
Same per-factor strength, **2.5× higher combined ICIR from low correlation alone.** Matches
IR_combined ≈ IR·√(k/(1+(k−1)ρ)): the high-corr value cluster ≈ one factor.

## The necessary refinements (honest nuances the data forced)

**A. Both axes matter; correlation is the larger one.** Standardized regression of pair-add increment:
standalone_ICIR β=+0.80, payoff_corr_to_base β=**−0.88**. Correlation dominates but strength still has
a real positive effect — it's "weight both," not "ignore ICIR."

**B. A high-ICIR factor that is only moderately correlated can still win a single add.** Pairing the
base with liq_log_dollar_vol (ICIR 0.62, corr 0.41) added +0.085 vs grow_opprofit_qoq (ICIR 0.29,
corr 0.04) +0.057. Strength is not negligible — a high-ICIR, *reasonably* orthogonal factor is best.

**E. Zero-IC + low-correlation adds nothing.** base + pure-noise (uncorrelated, ~0 IC) → increment
−0.003 ≈ 0. "Okay IC" is a hard necessary condition; you cannot diversify your way out of no signal.

## Why this bites THIS project specifically

The highest-standalone-ICIR factors here are the reversal/liquidity/low-vol cluster (rev_max_return_20d
0.71, liq_log_dollar_vol 0.62, risk_vol 0.50, liq_turnover 0.50) — mutually correlated AND (per prior
research) microcap-lottery names that DON'T convert to long-only top-K. Chasing ICIR concentrates risk
in one redundant, untradeable cluster. The growth/quality/value factors have lower standalone ICIR but
are the orthogonal diversifiers (greedy-by-marginal picked rev_max + 3 growth + liquidity + accruals).
This is exactly why project_state notes "cross-sectional factor expansion is saturated" and "targeted
alpha-blend > random Dirichlet for robustness" — the existing set is correlated, so more high-ICIR
factors of the same kind don't help.

## Actionable recommendation

Select/promote factors by **marginal contribution to the current approved set**, not standalone ICIR:
incremental combined ICIR, or orthogonalized IC (IC of the factor's residual after regressing out the
existing book). The factor_eval toolkit already computes a factor-correlation matrix (phase1_factor_corr)
and the orchestrator does "correlation-cluster assignment" — so wire an orthogonality/marginal-IC
criterion into the candidate→approved gate (currently keyed on standalone rank_icir_20d). Keep a
minimum standalone IC floor (the zero-IC caveat) and prefer high-ICIR-AND-orthogonal where available.
