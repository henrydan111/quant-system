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
   then judging monotonicity on that sample is mild in-sample circularity. FIX: orient by a
   **predeclared ECONOMIC prior** where one exists; otherwise orient on **train folds** and judge shape
   on **heldout folds**. Add an explicit `direction_source` column (`economic_prior` / `train_fold` /
   `undetermined`). ⚠ **Rev3 correction:** the registry `expected_direction` is NOT a predeclared prior —
   it is OBSERVED from the heldout ICIR (`_expected_direction(heldout)`), so using it is itself circular
   (see Rev3 §A.3). Never use the registry field for orientation.

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

## Revision 3 — GPT 5.5 Pro code-grounded review (2026-06-10)

A second review (GPT 5.5 Pro, browsed the repo + read the implementing modules) found the v2 plan's
**capability matrix overstated readiness**: several rows were labeled ✅ where the cited function does
LESS than claimed (the primitive exists, but the *composed metric helper* is not yet written/tested).
**All 4 falsifiable code claims were independently verified TRUE** (`venv` spot-checks, 2026-06-10):

1. **`statistical_tests.bootstrap_sharpe_ci` is IID `rng.choice(replace=True)` Sharpe resampling** — NOT
   a block bootstrap, NOT an IC/RankIC t-stat. → overlap-adjusted significance is **❌ NOT implemented**
   (v2's ⚠️ was too generous). `deflated_sharpe_ratio` is a simplified `√(2·lnN)/√T` uplift (not
   dependence/effective-trials aware).
2. **`decay_analysis.compute_ic_decay` computes `price(t+h)/price(t)−1` internally with NO `is_end`
   guard** → feeding it a price series leaks for h>20 (a 40d label realizes ~Feb-2021, past `is_end`).
   **HIGHEST-priority leak fix.**
3. **Registry `expected_direction` is OBSERVED, not predeclared** — `walk_forward_validation._expected_direction(heldout)`
   derives it from the heldout ICIR sign, persisted via `factor_lifecycle_steps.set_expected_direction`.
   → Rev-2 §A.3's "orient monotonicity by registry `expected_direction`" is **CIRCULAR** for those 30
   factors (direction observed on the same IS window the shape is judged on).
4. **`regime.py` summarizes a return series by calendar year** (mean/vol/positive/count) — NOT per-year
   ICIR from an IC series, NOT bull/bear regimes.

### Corrected capability labels (supersede §1 of [unified_eval_plan_v2.md](unified_eval_plan_v2.md))

| Metric | v2 | Corrected | Why |
|---|---|---|---|
| Heldout ICIR / sign-cons, mean-IC point est., neutralized IC, correlation/redundancy | ✅ | ✅ | engine + `neutralize_size_industry` + `correlation` genuinely do this |
| Overlap-adjusted significance (t/CI) | ⚠️ | **❌** | bootstrap is IID Sharpe; no HAC; no statsmodels |
| `mono_shape` / oriented step-signs / `insufficient_quantiles` | ✅ | **⚠️** | exists only in my **probe** script, not a tested module fn |
| Decay full vector + per-horizon clip | ✅ | **⚠️** | needs per-horizon `load_is_windowed_panel`; raw `compute_ic_decay` leaks |
| Turnover one-way `/(2K)` + tie/top/bottom | ✅ | **⚠️** | `annualized_turnover` only annualizes; churn formula is custom-unwritten |
| Long-leg excess net vs benchmark; LS decomposition | ✅ | **⚠️** | benchmark-excess + China long-side cost + orientation-aware long leg = custom-unwritten |
| DSR/PSR, regime-ICIR, capacity, persistence, data-quality | ✅ | **⚠️** | primitives only; composed/tested helpers not written |
| Monotonicity orientation by predeclared direction | ⚠️ | **🔴 circular** | registry field is observed; must NOT be used |

### Two must-fix-FIRST (highest priority, before any helper work)

- **Decay leak:** production decay MUST call `load_is_windowed_panel(..., horizon=h)` separately per
  horizon (each independently `is_end`-clips realization) and compute IC vs `panel.label`. NEVER feed a
  single price series to `compute_ic_decay`.
- **Direction non-circularity:** do NOT use the registry `expected_direction` for monotonicity. Either
  (a) **predeclare economic directions** by hand from factor definitions, or (b) **fold-pure train-fold
  orientation** (estimate sign on train fold ONLY, freeze, judge shape on that fold's heldout block).
  Add `direction_source ∈ {economic_prior, train_fold, undetermined}`.

### Accepted refinements

- **Significance:** **HAC/Newey-West is PRIMARY** (Bartlett kernel, lag ≥ horizon; default `lag=40`,
  report sensitivity 20/40/60), **block bootstrap = robustness** (moving/circular blocks on the
  date-level IC series, block_len≈40, NOT IID). Implement HAC internally (no new dep) OR pin
  `statsmodels` in [requirements.txt](../../../requirements.txt) (it is currently absent).
- **`style_controls_v1` (FROZEN + hashed; all 14 verified present in catalog):** `size_ln_mcap`,
  `size_ln_mcap_sq`, `val_ep_ttm`, `val_bp`, `val_sp_ttm`, `mom_return_20d`, `mom_return_120d`,
  `rev_return_5d`, `qual_gross_profitability`, `qual_accruals`, `liq_log_dollar_vol`, `liq_turnover_20d`,
  `liq_amihud_20d`, `risk_vol_20d`. One frozen pipeline: winsorize → cs-z/rank → regress (controls
  [+ industry dummies if the column says so]); **do NOT** pre-neutralize controls AND add size/industry
  dummies (double-counts). Report **residual coverage** (listwise deletion changes the universe).
- **Two marginal columns, two reference variants:** `resid_ic_vs_approved_stable` (EXCLUDES the 2
  provisional report_rc approvals; **default sortable**) + `resid_ic_vs_approved_current` (includes,
  `provisional_ref=true`) + `resid_ic_vs_style_controls_v1`. The 2 provisionals are 25% of an 8-factor
  base and correlated with the endpoint family under review → never the canonical novelty measure.
- **Add (capable, elevate):** conditional IC by size bucket (`compute_ic_by_group`), top-bucket style
  exposures, coverage-drift-over-time (esp. `report_rc`), execution-friction flags (suspended/limit-
  block/ST/new-listing/missing-price rate in the active bucket), **benchmark-assignment discipline**
  (pre-assign CSI300/500 by universe/size profile or show both — never pick after seeing excess).
- **Cut from headline:** naive ICIR significance, peak/best decay horizon, combined LS, DSR-as-is,
  bull/bear-regime ICIR (until implemented), factor-return skew/kurt/tail.
- **Tight dashboard core:** `coverage_tier`, `coverage`, `heldout_rank_icir`, `sign_consistency`,
  HAC-t/q for mean RankIC, `mean_rank_ic`, `neutralized_rank_icir`, `long_leg_excess_net_ir`,
  `turnover_ann`, `mono_shape/reason`, compact decay vector, `resid_ic_vs_approved_stable`,
  `resid_ic_vs_style_controls_v1`, `reference_set_version`/`provisional_flag`.
- **Freeze + hash BEFORE the full run** (methodology hash): `style_controls_v1`, benchmark assignment,
  HAC/bootstrap settings, cost assumptions, `reference_set_version`. The 185-factor dashboard is
  discovery → multiplicity is NOT just 185 (× horizons × directions × shapes × controls × peer-groups
  × benchmarks × cost assumptions × human column-sorting); DSR with `N=185` is under-deflated.

### Net effect

The plan is directionally right but **NOT yet implementation-ready**: the full run is blocked on writing
+ testing real helpers (HAC t-stat, mono_shape module fn, per-horizon decay, one-way turnover,
long-leg-excess), fixing the decay leak + the direction circularity, and freezing/hashing the
methodology. v2 §1 ✅/⚠️ labels are corrected above.

---

## Revision 4 — GPT 5.5 Pro P1 review (2026-06-10, commit 199ead3)

A third GPT 5.5 Pro review (of the COMPLETED P1 pipeline) gated the full-185 run on fixes — all
verified true against the committed code and implemented. **Must-fix-before-185 (done):**

1. **Orientation circularity (drivers).** The driver oriented on the first 60% of IS dates then judged
   the shape on the FULL IS (incl. that 60%). FIXED: shape is now judged on the **heldout 40% only**
   (`shape_eval_window=heldout_after_orientation`); the train window decides the sign, the heldout
   window decides the shape.
2. **`orientation_valid` gating.** `long_leg_excess_ir` and the intended-best shape were computed even
   when `orientation_valid=False`. FIXED: both drivers now emit `None`+`orientation_undetermined`
   when the orientation is weak/undetermined (no intended-best claim).
3. **Methodology freeze incompleteness.** `EvalMethodology` now also hashes: orientation policy +
   `orientation_train_frac`/`min_train_t`/`shape_eval_window`, every per-date `*_min_obs`/`*_min_names`,
   `trading_days`, `include_initial_cost`, `residual_transform`/`residual_metric`, the neutralization
   source fields, the benchmark close field + calendar policy, the bootstrap settings, `code_commit`,
   and `reference_set_definition_hashes`/`style_control_definition_hashes` (ids-only was insufficient).
4. **Data-driver hash gap.** `unified_eval_driver_data.py` now instantiates `EvalMethodology` and stamps
   `methodology_hash` on every neutralized/benchmark row (was a hashless side JSON).
5. **Neutralized `min_obs` bug.** `neutralized_rank_icir` now passes `neutralize_min_obs` INTO
   `neutralize_size_industry` (was silently using its hidden default 50 while the wrapper said 30); the
   neutralization-min and IC-min are now two distinct hashed knobs.
6. **`index_forward_returns` leak guard.** Now takes `is_end` and raises `IsEndLeakageError` on an
   uncapped benchmark close (was leak-safe only by caller discipline).
7. **Fixed rebalance calendar.** `one_way_turnover` / `long_leg_excess_ir` accept a shared
   `rebalance_dates` schedule (a trading-calendar grid) so factors are compared on the SAME rebalance
   dates (was each factor's own `dates[::20]` → not comparable).
8. **Signed vs oriented residuals.** Residual ICs are stored BOTH signed and orientation-normalized
   (`*_signed` / `*_oriented`); an inverse factor's negative signed residual is GOOD, so a dashboard
   must sort on the oriented value, never "more positive signed = better".
9. **Effective coverage.** `residual_ic_vs_controls` reports `effective_residual_coverage` (candidate ∩
   label ∩ controls, over candidate ∩ label) alongside `raw_control_coverage` — listwise deletion + the
   label's trailing-horizon drop can make it materially smaller.
10. **`resid_ic_vs_approved_current`.** The driver now computes residual IC vs BOTH the stable set
    (default) and the current set (incl. the 2 provisionals, flagged).

**Interpretation rules (Rev4):**
- **Multiple-testing bar is direction-aware:** a factor passes on `|hac_t| ≥ mt_t_bar` (3.0), with the
  SIGN reported separately — inverse factors have `hac_t < 0` and must NOT be failed by a literal `≥`.
- **Neutralized-only significance is its own status:** a factor that clears the bar ONLY after
  size+industry neutralization (e.g. `qual_gross_profitability`: raw HAC-t 1.37 → neutralized 3.17) is
  `raw=weak / neutralized=significant` → deployable ONLY as a size+industry-neutralized construction,
  NOT a raw-factor pass. Confirm with size-bucket conditional IC + before/after style exposures before
  acting (size-neutralization can also remove a size-correlated NOISE component — promising, not
  self-validating).
- **Benchmark headline discipline:** show BOTH CSI300 and CSI500 long-leg IR; neither is a sortable
  "best benchmark" column (CSI500 > CSI300 for all 7 must not become a post-hoc benchmark choice).

**Deferred (nice-to-have):** residual-regression condition-number / effective-rank diagnostics (keep
size² but monitor VIF); neutralized-signal long-leg IR for neutralized-only winners; size-bucket
conditional IC + top-bucket style exposures.

### Revision 5 — two-class evidence taxonomy: lifecycle + unified_eval MERGED (2026-06-10, user directive)

The user directed: factors have exactly TWO evaluation types. The unified evaluation IS the lifecycle
methodology run at full-catalog scale, so they merge into one "formal" class:

| eval type | what it is | evidence rows |
|---|---|---|
| **discovery** | the legacy batch screening (5d letter grades, triage) | `run_type='screening'/'research'` |
| **formal** | THE formal methodology (this spec): walk-forward heldout ICIR + sign-consistency + HAC + neutralized + shapes + residuals + decay + turnover + coverage + long-leg | `run_type='factor_lifecycle'` (gated) + `run_type='factor_lifecycle_refresh'` (ungated sweep) |

The taxonomy is DERIVED at read time from `run_type` (no schema repurposing — `evidence_class` keeps
its honesty-label role, e.g. `oos_informed_backfill`). **Within formal, the gated/ungated split is
load-bearing and carried by the existing `formal_evidence_eligible` column:**

- **gated run** (orchestrator `factor_lifecycle` + human gate) → `formal_evidence_eligible=True` —
  the ONLY rows that can support a status change (resolve-but-label unchanged).
- **refresh run** (the automated full-catalog sweep) → `formal_evidence_eligible=False`,
  `evidence_class='unified_refresh'` — same engine, same口径, refreshes the dashboard for all 185;
  can NEVER support a status change. An ungated sweep must never masquerade as a gate verdict.

Implementation (2026-06-10): evidence schema widened with the unified metric columns
(`methodology_hash`, `mean_rank_ic_hac_t`, `neutralized_*`, `mono_shape`, `direction_source`,
`coverage[_tier]`, `turnover_ann`, oriented residuals, long-leg IRs, + `unified_metrics_json` carrying
the full record); new fail-closed definition-bound writer
`FactorRegistryStore.record_formal_refresh_evidence` (mirrors `record_lifecycle_evidence`; idempotent
per run_id); importer [import_unified_refresh_evidence.py](../../../workspace/scripts/import_unified_refresh_evidence.py)
(dry-run default). Old evidence parquets widen transparently on load (new columns = NA). Tests:
`FormalRefreshEvidenceTests` in [test_factor_registry.py](../../../tests/alpha_research/test_factor_registry.py)
(never-gate-eligible, drift fail-closed, idempotency, schema widening) — full file 32 passed +
lifecycle-steps 17 + promotion gates 47.

**Staged follow-up (gated-run enrichment):** extend the `factor_lifecycle` walk_forward/publish
handlers so a GATED run also persists the full unified metric set (today its rows carry the headline
subset — same engine, same numbers). Until then, gated rows = headline metrics, refresh rows = full
set; the dashboard prefers gated rows where both exist (`formal_evidence_eligible` first).

### Rev4 addendum — fourth-pass self-audit (2026-06-10, pre-185 gate)

A line-by-line re-read of the whole module + drivers + a live lint run found and fixed:

- **F1 (substantive):** `code_commit` / `reference_set_definition_hashes` / `style_control_definition_hashes`
  existed as hashed FIELDS but the drivers left them EMPTY — the hash did not actually pin the code
  version or factor definitions. FIXED via the shared builder
  [workspace/scripts/unified_eval_common.py](../../../workspace/scripts/unified_eval_common.py)
  `build_frozen_methodology()`: git HEAD + `FactorRegistryStore.current_catalog_definition_hashes()`
  (the P1.3 definition-binding algorithm) + reference sets read LIVE from the registry (a revoked
  provisional approval changes the hash and forces a recompute). Both drivers now share this one
  construction → identical hash by construction. Hash `394e40c9` → **`e4508ffd`** (the pre-185 final).
- **F2 (scale):** the measured cost was ~2 min/factor (≈6–10 h for 185), dominated by per-factor decay
  panel rebuilds and per-candidate control re-transforms — both factor-INDEPENDENT. Added
  `build_decay_labels()` (labels built once per horizon) + `preprocess_for_residual()` (winsor+cs-z
  built once per name), with **equivalence tests** proving the fast paths reproduce the direct paths
  bit-identically.
- **F3 (compliance):** all 5 workspace scripts now carry the `SCRIPT_STATUS` header block
  (`research_tooling`, `formal_research_allowed: false`, Class C).
- **F4:** the frozen bootstrap settings are now actually USED — the driver emits
  `mean_rank_ic_boot_ci` (moving-block CI) per factor.
- **F5 (noted, not a violation):** the data driver reads `$total_mv` / index `$close` via bare
  `D.features` — MARKET data, not PIT statement fundamentals; the bare-features lint scans `src/` only
  (verified by running it). The script header marks this path sandbox-grade: its numbers must never
  feed a formal run.
- Minor: coverage-tier thresholds (0.90/0.50) moved into the hashed methodology
  (`coverage_full_min`/`coverage_broad_min`); stale docstrings fixed; dead import removed; turnover
  annualization caveat documented (compare `n_rebalances_used` vs `n_rebalance_candidates` for
  gap-skipping factors). Pre-existing PIT002 hits in `validate_pit_vs_vendor_q.py` are unrelated
  (earlier session's file).

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
   Asset Returns*) is the **adjacent-bucket difference SIGN VECTOR**, oriented by the **non-circular
   direction** (`resolve_orientation`: economic prior, else train-fold sign — NEVER the observed
   registry `expected_direction`; Rev3 §A.3) so the intended-best quantile is Q_top (a descending
   factor is sign-flipped before classification, else `---+` mis-reads as U-shape):

   | Shape | step_signs (5q→4 steps) | full spearman | `mono_frac_dominant` |
   |---|---|---|---|
   | monotonic up / down | `++++` / `----` | ±1.0 | 1.00 |
   | **top reversal** (body up, Q_top inverts — eps_diffusion `2.46/3.38/3.92/4.70/2.31`) | `+++-` | 0.56 | 0.75 |
   | **bottom reversal** | `-+++` | 0.82 | 0.75 |
   | **U-shape** | `--++` | 0.0 | 0.50 |
   | **inverted-U** | `++--` | 0.0 | 0.50 |
   | irregular / noise | `+-+-` | ≈0 | 0.50 |

   **Full-run monotonicity columns (replaces the `monotonic_spearman_body` patch):**
   - **Headline = `mono_shape` + the bucket-return vector + adjacent-step magnitudes + a CI/`mono_reason`**
     (per Rev2 §B.8 — NOT a single scalar).
   - `mono_step_signs` — the non-circularly-oriented adjacent-diff sign string.
   - `monotonic_spearman` — full-5q Spearman (familiar scalar, supporting).
   - `mono_frac_dominant` = `max(#up, #down) / n_steps` — a **supporting DIAGNOSTIC** (a single tail
     reversal only drops it to 0.75 vs Spearman's 0.0). It ignores magnitude/confidence/ties, so it is
     NOT the headline (Rev2 §B.8 supersedes any earlier "better headline" wording).
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
- **2026-06-10 (P0a/P0b/P0c implemented + tested):** the correctness/statistics core now lives in the
  tested module [src/alpha_research/factor_eval/unified_eval.py](../../../src/alpha_research/factor_eval/unified_eval.py)
  ([tests/alpha_research/test_unified_eval.py](../../../tests/alpha_research/test_unified_eval.py),
  **19 passed**):
  - **P0a** — `leak_safe_decay_ic_vector` (per-horizon `is_end`-clipped; closes the `compute_ic_decay`
    leak), `resolve_orientation` (economic-prior / train-fold; NEVER the observed registry direction),
    `classify_quantile_shape` (promoted to a module fn).
  - **P0b** — `hac_mean_tstat` (internal Bartlett Newey-West HAC; no statsmodels; test proves
    HAC-SE > IID-SE for positive autocorrelation = the overlap fix) + `moving_block_bootstrap_mean_ci`
    (date-level moving blocks, deterministic).
  - **P0c** — `one_way_turnover` (true `|Δ|/(|A|+|prev|)×252/rebal` + tie-rate + top/bottom) +
    `long_leg_excess_ir` (A-share deployable long-leg-excess-vs-benchmark IR, net long-side cost).
- **2026-06-10 (P1 + P1b-data implemented + 7-factor verify PASSED, methodology_hash 9ca32dc9):**
  `EvalMethodology` (frozen+hashed), `residual_ic_vs_controls`, `neutralized_rank_icir`,
  `index_forward_returns` + the two drivers. HAC significance works (gross_profitability raw HAC-t 1.37
  below the 3.0 bar; neutralized 3.17 above → neutralized-only). 28→32 tests after the GPT-R3 fixes.
- **2026-06-10 (GPT 5.5 Pro P1 review → Revision 4):** 10 must-fix items implemented (orientation
  shape-on-heldout, `orientation_valid` gating, complete methodology freeze, data-driver hash stamp,
  neutralized `min_obs` bug, `index_forward_returns` is_end guard, fixed rebalance calendar, signed vs
  oriented residuals, effective coverage, `resid_ic_vs_approved_current`). See Revision 4.
- **NEXT (full run → dashboard):** with the methodology frozen+hashed and the 7-factor pipeline GPT-
  reviewed, run the full-catalog (185) IS-only recompute → write the evidence columns (raw / neutralized
  / oriented-residual / long-leg-proxy, coverage-tier-peer-grouped) → repoint the dashboard 评级.
