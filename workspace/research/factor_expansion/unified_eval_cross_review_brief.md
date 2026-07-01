# Cross-Review Brief — Unified Factor Evaluation Standard (2026-06-10)

**For:** GPT cross-review. You have NOT seen the conversation that produced this — it is self-contained.
**Your job:** adversarially review the *design and the口径 (metric-definition) decisions* below. Flag
anything statistically unsound, leak-prone, internally inconsistent, or that contradicts the project's
own stated principles. Concrete counter-arguments > generic praise. The full spec is
[unified_eval_standard.md](unified_eval_standard.md); verification artifacts are
`workspace/outputs/unified_eval_probe.json` and `unified_eval_verify2.json`.

---

## 1. Context (the system)

A-share quant platform. ~185 factors in a catalog, each a row in a registry with a **status**:
`draft` (defined, unproven) → `candidate` (passed an **in-sample-only walk-forward** gate) →
`approved` (passed an independent **sealed out-of-sample (OOS)** gate; deployable-grade). There are
**8 approved**, ~88 `candidate`, ~89 `draft`.

Two safety rails matter for this review:
- **Sealed OOS is single-shot.** 88 candidates are `oos_informed_backfill` → their 2021–2026 window
  is "burned" (already observed); `draft` factors' OOS is unspent. You CANNOT manufacture a fresh OOS
  number for every factor.
- **IS walk-forward is `is_end`-bounded** (factor date AND label-realization date ≤ `is_end`=2020-12-31),
  leak-proof by construction. Window: IS 2014–2020, horizon 20d.

**Problem being solved:** the dashboard's "评级 / RankICIR" column was sourced ONLY from a legacy
batch-screening (`run_type='screening'`) evidence row that writes a 5-day-horizon letter grade. Factors
promoted via the walk-forward + sealed-OOS path never ran that screening → their grade was empty →
displayed "—". Two non-comparable口径 (5d letter grade vs 20d walk-forward ICIR) were in one column.
We are replacing that with ONE standard computed identically for every factor.

## 2. The proposed standard (3 tiers)

### Tier 1 — intrinsic, MANDATORY for every factor, IS-only, horizon 20d
1. **Heldout RankICIR** (walk-forward folded, `is_end`-bounded) — headline. *Already stored for
   lifecycle factors; recompute reproduces it bit-exactly (15 decimals).*
2. **Sign-consistency** across folds.
3. **Mean RankIC**, 4. **IC hit-rate** (from `compute_ic_summary`).
5. **Monotonicity** — see §4 (the most-scrutinized piece).
6. **Decay horizon** (peak |ICIR| over horizons 5/10/20/40) — NOT yet verified (needs multi-horizon labels).
7. **Turnover** — top-20% one-way membership churn at the **20d rebalance** frequency, annualized
   ×(252/20). (First attempt used daily churn ×252 → ~20× inflated; corrected.)
8. **Coverage** + `coverage_tier` (`full` ≥0.90 / `broad` 0.50–0.90 / `sub` <0.50). For `sub`/`broad`,
   ICIR is "on the covered subset" and labeled so (e.g. `earn_eps_diffusion_60` cov **0.28** = analyst-
   covered names only; its ICIR 0.42 is NOT a full-market number).

### Tier 2 — marginal orthogonal contribution, MANDATORY, RELATIVE metric
- **ONE column: `marginal_residual_ic_vs_approved8`** (residual IC / exposure view): per-date regress
  the candidate on the base set, correlate the residual with forward return. Weight-free. Reference set
  = **the 8 approved factors** (the deployed core book; professional convention orthogonalizes against
  the established model, not the full candidate pool). **Leave-one-out** for approved members.
- Multiple-testing t-bar = **3.0** (Harvey–Liu–Zhu), not 2.0.
- **Equal-weight incremental-ICIR delta was tested and REJECTED** — see §5.

### Tier 3 — gold evidence, SPARSE (sealed-OOS only)
`oos_rank_icir`, `oos_ls_sharpe`, IS→OOS sign stability. Only where OOS was genuinely spent (the 8
approved). Burned candidates → "OOS burned"; drafts → "OOS unspent". Never faked. This sparsity is the
sealed-OOS mechanism working as designed.

**Critical separation:** these are EVIDENCE columns; the IS gate NEVER emits `approved`. The dashboard
must NOT overwrite a factor's registry status with an IS verdict (resolve-but-label).

## 3. Verification done (real data, IS-only, zero OOS spent, all reusing tested `factor_eval` functions)

7 representative factors (3 approved / 3 candidate / 1 draft):

| factor | status | heldICIR | meanRankIC | turn/yr | cov | tier | mono_shape | marginal_resid_IC |
|---|---|---|---|---|---|---|---|---|
| earn_eps_diffusion_60 | approved | +0.417 | +0.036 | 6.9 | 0.28 | sub | top_reversal | +0.012 |
| liq_zero_ret_days_10d | approved | +0.302 | +0.022 | 8.0 | 1.00 | full | insufficient_q | +0.018 |
| qual_piotroski_fscore_9pt | approved | +0.320 | +0.024 | 3.5 | 1.00 | full | irregular | +0.015 |
| liq_vol_cv_20d | candidate | −0.700 | −0.052 | 11.0 | 1.00 | full | monotonic_up | −0.021 |
| qual_gross_profitability | candidate | +0.138 | +0.018 | 3.0 | 0.98 | full | monotonic_up | +0.019 |
| rev_up_down_ratio_20d | candidate | −0.204 | −0.021 | 10.4 | 1.00 | full | inverted_U | −0.004 |
| qual_q_gross_margin | draft | +0.053 | +0.006 | 1.9 | 0.98 | full | top_reversal | +0.013 |

- Heldout ICIR + sign-consistency reproduce stored lifecycle evidence **bit-exactly**.
- Marginal residual IC behaves as theory predicts: `liq_vol_cv_20d` has the biggest standalone |ICIR|
  (0.70) but retains only ~37% after orthogonalization (largely redundant); `qual_gross_profitability`
  has small standalone (0.138) but retains ~109% (genuinely orthogonal new info). This confirms the
  project's empirically-established principle: **select by marginal orthogonal contribution, not
  standalone ICIR** (greedy-by-marginal combined ICIR 1.02 vs greedy-by-ICIR 0.70).

## 4. Monotonicity diagnostic (the most-scrutinized piece — please review hard)

A single 5-quantile Spearman was shown (synthetic + real) to be insufficient: it collapses U-shape (0.0),
inverted-U (0.0), and genuine flat (≈0) to the same value, and is killed by a single tail reversal. The
replacement (Patton–Timmermann 2010 spirit) is the **expected-direction-oriented adjacent-bucket
difference SIGN VECTOR** + a shape classifier:

| shape | step_signs (5q→4) | full spearman | mono_frac_dominant |
|---|---|---|---|
| monotonic up/down | `++++`/`----` | ±1.0 | 1.00 |
| top reversal (body up, top inverts) | `+++-` | 0.56 | 0.75 |
| bottom reversal | `-+++` | 0.82 | 0.75 |
| U-shape | `--++` | 0.0 | 0.50 |
| inverted-U | `++--` | 0.0 | 0.50 |
| irregular | `+-+-` | ≈0 | 0.50 |

Columns: `monotonic_spearman` (full), `mono_step_signs`, `mono_shape`, `mono_frac_dominant`
(= max(#up,#down)/n_steps — proposed as the better headline than Spearman). Discrete/tie-heavy factors
that can't form ≥3 quantiles → `None` + `insufficient_quantiles`. A `top_reversal` is flagged as a
long-top-quintile **deployment red-flag** (independently matches a prior documented finding that
`earn_eps_diffusion_60` is a real factor but NOT a deployable long-only book).

## 5. Decision we want you to stress-test: rejecting equal-weight incremental-ICIR

We considered a 2nd Tier-2 column = ΔICIR of an equal-weight sign-oriented composite when the candidate
is added to approved-8. On real data it **disagreed in sign with the residual IC for 3/7 factors** and
gave **negative deltas for two approved factors** (`liq_zero_ret` −0.010, `piotroski` −0.046) while
inflating a weakly-orthogonal one (`liq_vol_cv` residual IC −0.021 but Δ **+0.212**). Our diagnosis:
equal-weight Δ is confounded by (a) equal-weight dilution and (b) it rewards standalone strength, not
orthogonality — the opposite of the selection principle. We therefore **dropped it**, keeping only the
weight-free residual IC, and noted that a combination view should use **optimal (max-IR) weights**
(where Δ≥0) if ever wanted.

## 6. Specific review questions

1. **Reference set for marginal = the 8 approved, leave-one-out.** Sound? Better alternative given only
   8 approved (small base; the residual regression has 7–8 regressors per date)? Is 8 factors enough to
   meaningfully orthogonalize against, or does a tiny base make residual IC ≈ standalone IC?
2. **`mono_frac_dominant` as the headline monotonicity scalar** (over Spearman). Agree? Failure modes?
   Does the expected-direction orientation introduce any circularity (we orient by sign of mean RankIC,
   then judge monotonicity)?
3. **Was rejecting equal-weight Δ correct**, or is a negative Δ for piotroski actually telling us
   something real (redundancy) that residual IC's +0.015 hides? Which is the truer "marginal" signal?
4. **Turnover** at a fixed 20d rebalance with top-20% symmetric-difference churn — is this a sound,
   comparable cross-factor proxy, or does it bias against high-coverage/low-dispersion factors?
5. **Coverage handling** — is "label the ICIR as on-covered-subset" enough, or should sub-coverage
   factors' ICIR be down-weighted / not directly comparable to full-coverage ICIR at all?
6. **Anything leak-prone or multiple-testing-unsafe** in computing all these IS-only metrics for 185
   factors and surfacing them on a dashboard? (We are NOT making promotion decisions from these — they
   are descriptive evidence; promotion still requires the separate sealed-OOS gate.)
7. Any **missing mandatory metric** a professional shop would require that we omitted?
