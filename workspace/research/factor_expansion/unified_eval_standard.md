# Unified Factor Evaluation Standard (统一因子评估标准)

**Status:** design spec (2026-06-10) — pending full-catalog recompute.
**Owner:** factor lifecycle / dashboard 评级 column.
**Problem it solves:** the dashboard 评级 / 5d RankICIR columns were sourced ONLY from
`run_type='screening'` (batch-screening discovery) evidence. Factors promoted through the
`factor_lifecycle` (walk-forward IS) + sealed-OOS path never ran batch screening, so their
grade/rank_icir_5d were empty → displayed `—`. Two parallel, non-comparable口径 (a 5d single-window
letter grade vs a 20d walk-forward ICIR) were being shown in one column. This spec replaces that
with ONE standard computed identically for every factor.

This document is the authoritative definition. Enforced invariants live in
[CLAUDE.md](../../../CLAUDE.md) §3 / §7; the followable lifecycle guide is
[factor_lifecycle/README.md](../../../src/alpha_research/factor_lifecycle/README.md).

---

## Revision 2 — GPT cross-review integration (2026-06-10)

A GPT adversarial cross-review (brief: [unified_eval_cross_review_brief.md](unified_eval_cross_review_brief.md))
flagged real correctness/safety gaps, not just additions. All accepted. The amendments below
**supersede** any contradicting text later in this doc. They split into three groups.

### A. Correctness-critical — BLOCK the full run until implemented

1. **Per-horizon `is_end` clipping for decay (leak fix).** "Peak |ICIR| over 5/10/20/40" is hidden
   **horizon mining** (best-of-4 → optimistic). FIX: (a) each horizon's label-realization date must be
   independently clipped to `is_end` (a 40d label realizing after 2020-12-31 would LEAK — the 20d
   `IsWindowedPanel` bound is NOT sufficient for longer horizons); (b) **report the full horizon
   ICIR vector**, never headline the peak unless multiple-testing-adjusted. Decay is a *shape*
   diagnostic, not a selection metric.
2. **Overlap-adjusted t-stats (statistical-validity fix).** 20d-horizon labels sampled daily overlap
   19/20 → IID t-stats / ICIR significance are inflated ~√20 ≈ 4.5×. FIX: all significance (the
   HLZ t≥3.0 bar, any IC t-stat) uses **Newey-West (≥20 lags)** or **block bootstrap**. The naive
   `mean/std` ICIR is kept as a point estimate but its CI/t-stat MUST be overlap-corrected.
3. **Monotonicity orientation circularity (leak fix).** Orienting by the *same-sample* mean RankIC
   then judging monotonicity on that sample is mild in-sample circularity. FIX: orient by the
   **registry `expected_direction`** (predeclared) where it exists; for drafts without one, orient on
   **train folds** and judge shape on **heldout folds**. Add an explicit `direction_source` column
   (`registry` / `train_fold`) per factor.

### B. Design-correctness — relabel / regroup / version (no leak, but mislabeled)

4. **The 8 approved are NOT a "deployed core book."** Project rule: factor `approved` ≠ tradable-
   strategy-validated; the 2 `report_rc` eps_diffusion approvals are **provisional** (canary overridden,
   revoke if the 2026-06-15 canary fails). RENAME the reference set to **"current approved factor
   reference set"**, attach a **`reference_set_version`** (hash of approved factor ids+definition-hashes),
   and **recompute all residual ICs if the provisional approvals are revoked or the set changes**.
5. **Sub-coverage ICIR is NOT comparable to full-market ICIR.** Labeling is necessary but insufficient
   (analyst-covered names are a *different universe*). FIX: rank within **separate coverage peer groups**
   (`full` / `broad` / `sub`) — NOT one leaderboard — and show sample count + size/sector/liquidity skew.
   Do NOT mechanically down-weight a factor whose *intended* strategy is explicitly sub-universe.
6. **The dashboard is itself an IS search surface (multiple-testing).** Humans sorting 185 IS metrics
   and then designing recipes = **discovery**. FIX: treat the whole sweep as **discovery evidence** —
   freeze the methodology, **version the run** (`eval_run_id` + methodology hash), apply MT-adjusted
   t-stats, keep OOS sparse, and **never let a dashboard number mutate registry status** (already a
   principle — now load-bearing).
7. **Residual-IC vs approved8 is RELATIVE, not universal marginal alpha.** It only proves orthogonality
   to *this small set*, not novelty vs size/industry/liquidity/value/momentum/quality or the candidate
   pool. FIX: report residual IC **vs approved8 AND vs a standard style-control set** (size, industry,
   liquidity, value, momentum, quality) as a companion column. (The small 8-factor base means residual
   IC can sit close to standalone IC — expected, just means the base spans little style space.)
8. **`mono_frac_dominant` is a DIAGNOSTIC, not the headline.** It ignores magnitude, confidence, ties,
   tail damage. Headline monotonicity = **`mono_shape` + the bucket-return vector + adjacent-step
   magnitudes + confidence band**; `mono_frac_dominant` is demoted to a supporting diagnostic.
9. **Turnover formula = true one-way churn** `|A_t Δ A_{t-20}| / (2K) × (252/20)` (NOT `|Δ|/|union|`).
   Still biased by ties/discreteness/small universes/the arbitrary top-20% cut → also report
   **tie-rate**, **top- and bottom-bucket turnover separately**, and (for deployable factors) the
   **actual deployment-basket turnover**.

### C. Missing professional-shop metrics — ADD to Tier 1

10. **Neutralized RankIC / ICIR** (size+industry neutralized — via `neutralization.neutralize_size_industry`)
    alongside the raw — separates genuine alpha from style beta.
11. **Quantile spread — A-share-correct decomposition (NOT a combined net LS spread).** A-shares
    cannot freely short: 融券 covers only the 标的证券 subset (large-cap-biased), inventory is scarce,
    fees 8%+, and the bottom-quantile names a factor wants to short are mostly NON-标的 → a combined
    Q5−Q1 LS spread is a **paper number** (the project already flags `oos_ls_sharpe` as
    "NOT deployable", §3.5). So:
    - **Headline (deployable):** `long_leg_excess_net` = top-quantile **long-only** excess vs
      benchmark (CSI300/500), net of **long-side** cost only (sell stamp-tax 5bps, commission, 过户费,
      slippage; NO borrow fee) — the event-driven long-only top-K口径 the project deploys.
    - **Diagnostic:** decompose **long-leg vs short-leg excess** (vs universe mean) — *where* the alpha
      is. A factor whose alpha sits in the SHORT leg is largely unrealizable in A-shares; flag it.
    - **If an LS spread is shown at all:** restrict the short leg to the **融券标的 universe** and label
      it capacity-constrained — the closest-to-deployable LS. Combined net LS is NEVER a headline.
    - Market-neutral note: long top-quantile + short **index futures** (IF/IC/IM) is the deployable
      neutral form, but it captures the **long-leg excess** (hedges market beta only, not the
      cross-sectional short leg) and carries futures basis (贴水)/capacity cost.
12. **Regime stability** (per-year / bull-bear ICIR; reuse `factor_eval.regime`).
13. **Capacity / liquidity** (ADV-weighted coverage of the active bucket).
14. **Data-quality / tie-outlier diagnostics** + an explicit **provisional-data flag** (e.g.
    `report_rc` factors carry `provisional=true` until the 2026-06-15 canary).

**Net effect on the headline:** the dashboard 评级 stays the heldout RankICIR + sign-consistency, but
now **peer-grouped by coverage tier**, with an **overlap-corrected** significance flag, a
**neutralized** companion, and a **versioned/provisional-aware** marginal column. Nothing here changes
the IS-only / zero-OOS / resolve-but-label guarantees.

---

## Design principles

1. **One口径 for all 185 factors.** Every factor gets the same intrinsic metric set, same
   algorithm, same window — regardless of `draft`/`candidate`/`approved` status.
2. **Evidence ≠ status (resolve-but-label).** The unified metrics are *evidence columns*; the
   IS-only gate NEVER emits `approved` (that needs sealed-OOS). The dashboard must NOT overwrite a
   factor's registry status with the IS verdict. Status badge stays from the registry.
3. **PIT-safe, deterministic, no OOS spend.** Tier 1 + Tier 2 are computed IS-only
   (`is_end=2020-12-31`, walk-forward folded, `is_end`-bounded). Recomputing them spends NO sealed
   OOS budget. Bit-exact reproducible (verified 2026-06-10 against stored lifecycle evidence).
4. **Reuse, never reinvent.** Every metric maps to an existing tested function in
   `src/alpha_research/factor_eval/` or `factor_lifecycle/metrics.py`. No hand-rolled IC/ICIR.
5. **No口径 pollution.** Different horizons / different reference sets NEVER share a column.
   Each column is explicitly named with its horizon and (for relative metrics) its reference set.

---

## Tier 1 — Intrinsic metrics (MANDATORY for every factor)

Factor-intrinsic, uniform, IS-only, horizon = 20d (the project standard). Anchored to
CLAUDE.md §7.4 ("IC, RankIC, ICIR, quantile spread, monotonicity, decay, turnover").

| # | Metric | Column | Source function | Notes |
|---|---|---|---|---|
| 1 | **Heldout RankICIR** (walk-forward folded, `is_end`-bounded) | `is_rank_icir` | `walk_forward_validation.run_is_walk_forward` | The headline / main 评级. Already stored for lifecycle factors. |
| 2 | **Sign-consistency** (across folds / yearly) | `sign_consistency` | same | Direction stability. |
| 3 | **Mean RankIC** | `mean_rank_ic` | `factor_eval.ic_analysis.compute_ic_summary` | Raw strength + sign. |
| 4 | **IC hit-rate** | `ic_hit_rate` | `compute_ic_summary` | Fraction of cross-sections with same-sign IC. |
| 5 | **Quantile monotonicity** (boolean + continuous) + LS spread | `monotonic`, `monotonic_spearman`, `ls_spread` | `quantile_analysis.test_monotonicity` / `compute_long_short_returns` | 5-quantile. **Report BOTH** the boolean and the continuous `spearman_corr` (quantile mean-return vs quantile rank) — the continuous value is the informative one; the boolean is noisy for sparse factors. |
| 6 | **Decay horizon** | `best_decay_horizon` | `decay_analysis.find_optimal_horizon` | Multi-horizon (5/10/20/40); needs multi-horizon labels — computed in the FULL run, not the single-horizon probe. |
| 7 | **Turnover** | `turnover_ann` | `cost_aware_eval.annualized_turnover` | **At the ACTUAL rebalance frequency, NOT daily.** Top-20% one-way membership churn (`|symdiff|/|union|`) between consecutive 20d-spaced rebalances, annualized via `annualized_turnover(series, trading_days=252/20)` = mean(per-rebalance churn) × ~12.6 rebalances/yr. (The first probe used daily churn × 252 → values ~20× inflated; ranking was still sensible.) **New column — was missing from evidence despite §7.4.** |
| 8 | **Coverage** + tier | `coverage`, `coverage_tier` | (non-null fraction of universe×time) | **New column, first-class.** `coverage_tier` = `full` (≥0.90) / `broad` (0.50–0.90) / `sub` (<0.50). For `broad`/`sub` factors the ICIR is **computed on the covered subset** and MUST be labeled so — e.g. `earn_eps_diffusion_60` coverage 0.28 (analyst-covered names only): its ICIR 0.42 is on ~28% of the market, NOT a full-universe number. ICIR's own `min_obs=30` per-cross-section filter already drops thin dates; `coverage` reports the span so ICIR is never read naively. |

A factor missing any Tier-1 column is incompletely evaluated. Items 7 & 8 are the gaps the new
system must backfill.

### The 3 finalized口径 details (locked 2026-06-10)

1. **Coverage is a first-class explanatory column, not decoration.** Sub/broad-coverage factors' ICIR
   is explicitly labeled "on covered subset". `coverage_tier` drives the dashboard so a 0.28-coverage
   ICIR is never compared apples-to-apples with a 1.00-coverage ICIR.
2. **Turnover at the real 20d rebalance frequency** (× ~12.6/yr), not daily churn — yields a
   deployable number. Ranking (fundamental slow / liquidity-reversal fast) holds either way.
3. **Monotonicity reports the continuous Spearman** alongside the boolean; the boolean alone is
   noisy for sparse factors (5-quantile on 28%-coverage data flips easily).
   **Critical fix (found in the 7-factor probe):** `test_monotonicity` returns the sentinel
   `spearman_corr=0.0` whenever the 5-quantile cut collapses to `<3` buckets — which happens for
   **discrete/tie-heavy factors** (e.g. `liq_zero_ret_days_10d`, an integer 0–10 count) and
   **sparse-coverage factors** (`earn_eps_diffusion_60`, cov 0.28, dropped at `min_obs=50`). The
   full run MUST distinguish "not computable" → report `monotonic_spearman=None` + a
   `monotonic_reason` (`insufficient_quantiles(n=…)`), NEVER `0.0` (which reads as "flat /
   non-monotonic" and is wrong). For these factors the trustworthy directional measure is the
   continuous **`mean_rank_ic`** (Tier-1 #3), which is non-zero where monotonicity is uncomputable
   (eps_diffusion mean_rank_ic +0.036, liq_zero_ret +0.022).

   **A single full-5q Spearman does NOT cover the distinct (non-)monotonic shapes.** Verified
   (synthetic, 2026-06-10): full-spearman collapses **U-shape (0.0)**, **inverted-U (0.0)**, and
   **genuine flat (≈0)** to the same value, and a `body_spearman` patch only rescues the *top-tail*
   case. The COMPLETE non-parametric characterization (Patton–Timmermann 2010, *Monotonicity in
   Asset Returns*) is the **adjacent-bucket difference SIGN VECTOR**, oriented by the factor's
   `expected_direction` first (so the intended-best quantile is Q_top; a descending factor is sign-
   flipped before classification, else `---+` mis-reads as U-shape):

   | Shape | step_signs (5q→4 steps) | full spearman | `mono_frac_dominant` |
   |---|---|---|---|
   | monotonic up / down | `++++` / `----` | ±1.0 | 1.00 |
   | **top reversal** (body up, Q_top inverts — eps_diffusion `2.46/3.38/3.92/4.70/2.31`) | `+++-` | 0.56 | 0.75 |
   | **bottom reversal** | `-+++` | 0.82 | 0.75 |
   | **U-shape** | `--++` | 0.0 | 0.50 |
   | **inverted-U** | `++--` | 0.0 | 0.50 |
   | irregular / noise | `+-+-` | ≈0 | 0.50 |

   **Full-run monotonicity columns (replaces the `monotonic_spearman_body` patch):**
   - `monotonic_spearman` — full-5q Spearman (familiar scalar, kept).
   - `mono_step_signs` — the expected-direction-oriented adjacent-diff sign string.
   - `mono_shape` — classified label from the sign string (the 6 cases above).
   - `mono_frac_dominant` = `max(#up, #down) / n_steps` — a monotonicity-strength scalar that, unlike
     Spearman, a single tail reversal only drops to 0.75 (not 0.0). **This is the better headline
     than Spearman.**
   - `monotonic_reason=insufficient_quantiles(n<3)` for the discrete/tie-heavy case (a) below.

   **Three sources of "not cleanly monotonic" the full run disambiguates:**
   (a) **discrete/tie-heavy** (`liq_zero_ret_days_10d`, int 0–10) → qcut <3 buckets →
   `None`+`insufficient_quantiles`; trust `mean_rank_ic`.
   (b) **tail/interior reversal** (`top_reversal` for `earn_eps_diffusion_60`) → `mono_shape` names it;
   a `top_reversal` is a **long-top-quintile deployment red-flag** (independently matches the
   documented eps_diffusion finding: real factor alpha, NOT a deployable long-only book).
   (c) **genuinely flat** → `mono_frac_dominant≈0.5` + `mean_rank_ic≈0`.

---

## Tier 2 — Marginal orthogonal contribution (MANDATORY; RELATIVE metric)

**Why required:** project-confirmed principle (memory `reference_factor_selection_marginal_not_icir`):
select by marginal orthogonal contribution (IC × low correlation to existing set), NOT standalone
ICIR — empirically, greedy-by-marginal combined ICIR 1.02 vs greedy-by-ICIR 0.70.

**Why NOT Tier 1:** marginal contribution is a function of a REFERENCE SET, not a factor-intrinsic
property. The reference set must be fixed and named on the column. It is recomputed whenever the
reference set changes.

**Reference set = the "current approved factor reference set" (the 8 `approved`), VERSIONED and
provisional-aware** — see Revision 2 §B.4. NOT a "deployed core book" (factor `approved` ≠ tradable-
strategy-validated; the 2 `report_rc` eps_diffusion approvals are provisional). Attach
`reference_set_version` (hash of approved ids + definition-hashes); recompute all residual ICs if the
set changes or a provisional approval is revoked. Orthogonalizing against this established set (not the
full churning candidate pool, which would compress every marginal to ~0) matches professional
convention, BUT with only 8 factors the base spans little style space → **also report residual IC vs a
standard style-control set** (size/industry/liquidity/value/momentum/quality; Rev-2 §B.7). For a factor
itself in the approved set, compute **leave-one-out** (marginal vs approved \ {itself}).

Professional institutions evaluate marginal contribution with four standard statistics; this
system adopts the two that are uniformly computable IS-only:

**Tier 2 = ONE column: `marginal_residual_ic_vs_approved8`** (residual IC, exposure view).

| Column | Method | Source function | Definition |
|---|---|---|---|
| `marginal_residual_ic_vs_approved8` | **Residual IC** (exposure view) | `ic_analysis.compute_marginal_ic` | Per-date regress candidate on base set, correlate residual with fwd return. `resid(t)=cand(t)−X_base(t)·β̂(t)`; `marginal_IC=corr(resid, fwd)`. Weight-free; measures unique orthogonal predictive info. Leave-one-out for approved members. |

**Equal-weight incremental ICIR (`marginal_icir_delta`) was TESTED and REJECTED (2026-06-10).** On the
real panel it disagreed in SIGN with the residual IC for 3 of 7 factors and produced **negative
deltas for two `approved` factors** (`liq_zero_ret_days_10d` −0.010, `qual_piotroski_fscore_9pt`
−0.046) while inflating a weakly-orthogonal one (`liq_vol_cv_20d` residual IC −0.021 but delta
**+0.212**). Root cause (verified): equal-weight delta is confounded by (a) equal-weight **dilution**
(adding a moderately-strong factor to an already-strong equal-weight book lowers ICIR even when the
factor carries unique info) and (b) it rewards **standalone strength, not orthogonality** — the exact
OPPOSITE of the project's marginal-selection principle. The professional "incremental IR" uses
**optimal** (max-IR) weights, under which Δ ≥ 0 always; equal-weight Δ is an artifact. If a
combination view is ever wanted, use optimal-weight incremental IR — NEVER equal-weight Δ. Provenance:
`workspace/outputs/unified_eval_verify2.json`.

The two other professional methods — **multivariate Fama-MacBeth t-stat** and **spanning-regression
alpha (GRS)** — are documented for reference but deferred: the FM t-stat is folded into the residual
IC's significance, and the spanning alpha requires LS-return series at portfolio level (a Tier-3
backtest artifact, not an IS panel metric).

**Guardrails (institutional):**
- **Multiple-testing t-bar = 3.0**, not 2.0 (Harvey–Liu–Zhu, "...and the Cross-Section of Expected
  Returns"). We have screened 100+ factors → the higher bar is mandatory.
- **Marginal must hold OOS** to be trusted (IS marginal is inflated). The OOS residual IC is a
  Tier-3 sparse column (only where sealed-OOS was genuinely spent).
- **Correlation/VIF pre-screen** (`correlation.compute_factor_correlation` / `find_redundant_pairs`)
  is a cheap triage before the expensive per-date regression, not a replacement.

---

## Tier 3 — Gold evidence (SPARSE; sealed-OOS only)

Cannot be manufactured for every factor and must never be faked:

| Column | Source | Availability |
|---|---|---|
| `oos_rank_icir`, `oos_ls_sharpe` | sealed-OOS promotion path | Only the 8 `approved` (genuinely spent). |
| IS→OOS sign stability | same | Same. |
| `marginal_residual_ic` (OOS) | sealed-OOS | Same. |

- The 88 `oos_informed_backfill` candidates: 2021–2026 is **burned** — display "OOS burned", never
  re-test as fresh.
- The `draft` factors: OOS **unspent** — display "OOS unspent", do not spend it to populate a column.

This sparsity is the sealed-OOS mechanism working as designed, not a defect.

---

## Per-factor archive (the new system's mandatory record)

Every factor's dashboard card =
**Tier 1 (8 intrinsic) + Tier 2 (2 marginal vs approved-8) + Tier 3 (sparse OOS)**.

Dashboard column mapping:
- **评级 (headline)** = Tier-1 `is_rank_icir` + `sign_consistency` (replaces the old screening grade).
- **边际** = Tier-2 `marginal_residual_ic_vs_approved8` (the selection lens).
- **金牌** = Tier-3 badge, shown only where a real sealed-OOS exists; else "burned"/"unspent".
- Old `screening_grade` / `rank_icir_5d` (5d) → demoted to a "discovery triage" small-print field,
  never the headline (it is a different horizon and was misleading: e.g. `rev_up_down_ratio_20d`
  screening grade "D" while its unified 20d heldout ICIR = −0.20 / sign-cons 0.86 = a real signal).

---

## Verification status

- **2026-06-10:** 7-factor probe (`unified_is_panel_probe.py`) confirmed Tier-1 `is_rank_icir` +
  `sign_consistency` compute identically across approved/candidate/draft and reproduce stored
  lifecycle evidence **bit-exactly** (15 decimals). No OOS spent. See
  `workspace/outputs/unified_is_panel_probe.json`.
- **2026-06-10 (full口径 probe, `unified_eval_probe.py`):** Tier-1 (heldout ICIR, sign-consistency,
  mean RankIC, IC hit-rate, monotonicity, turnover, coverage) + Tier-2 residual-IC marginal computed
  on the 7 factors, all reusing tested `factor_eval` functions. Turnover re-defined to the 20d
  rebalance frequency; coverage tiered (`earn_eps_diffusion_60` flagged `sub`, cov 0.28).
- **2026-06-10 (verify2, `unified_eval_verify2.py`):** the complete monotonicity diagnostic
  (oriented step-signs + `mono_shape` + `mono_frac_dominant`) verified on real data — correctly
  labels `top_reversal` / `inverted_U` / `irregular` / `insufficient_quantiles` where a single
  Spearman could not. Equal-weight `marginal_icir_delta` TESTED → REJECTED (confounded; see Tier 2).
- **NEXT:** run the full-catalog recompute (~40 min, IS-only, cached) — adds decay horizon
  (multi-horizon labels) + the monotonicity shape columns to all field-eligible factors — write the
  new evidence columns, then repoint the dashboard 评级 column.
