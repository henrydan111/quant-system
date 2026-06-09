# Unified Factor Evaluation — Capability-Assessed Plan v2 (for GPT 5.5 Pro review)

**Date:** 2026-06-10 · **Branch:** `report-rc-registration` · **Repo:** github.com/henrydan111/quant-system
**Reviewer:** GPT 5.5 Pro (cloud). You can browse the repo via GitHub; file paths below are repo-relative
(`blob/report-rc-registration/<path>`). `data/`, `workspace/outputs/`, `mlruns/` are **gitignored** —
you will NOT see raw data or result JSONs on GitHub, so all verified numbers are **inlined** here.

**What this document is:** the v1 design + the first GPT cross-review were integrated into
`workspace/research/factor_expansion/unified_eval_standard.md` (Revision 2). This v2 plan then
**assessed every proposed metric against what the system can actually compute today** (existing
functions + available data), enriched the set with everything else we are capable of, and reorganized
it into an implementable plan. Your job: review the **capability-constrained** plan — are the
substitutions sound, is the set complete, what should we cut or reprioritize? Questions in §6.

---

## 0. Context (self-contained)

A-share (China) long-only quant platform (no leverage; shorting is structurally constrained — see §4).
~185 factors in a catalog; each a registry row with status `draft` → `candidate` (passed an IS-only
walk-forward gate) → `approved` (passed a single-shot **sealed OOS** gate). 8 approved, ~88 candidate,
~89 draft. **`approved` ≠ tradable-strategy-validated**; the 2 `report_rc` eps_diffusion approvals are
**provisional** (a canary was overridden; revoke if the 2026-06-15 canary fails).

**Problem:** the dashboard "rating" column was sourced only from a legacy 5-day batch-screening grade;
walk-forward/sealed-OOS-promoted factors never ran it → blank → "—". We replace it with ONE standard
computed identically for every factor, IS-only (window 2014–2020, `is_end`=2020-12-31), zero OOS spend,
**evidence-only** (never mutates registry status). Authoritative spec:
[unified_eval_standard.md](unified_eval_standard.md). Walk-forward engine:
[src/alpha_research/factor_lifecycle/walk_forward_validation.py](../../../src/alpha_research/factor_lifecycle/walk_forward_validation.py).

---

## 1. Capability matrix — can we do it today?

Legend: ✅ ready (existing fn + data) · ⚠️ partial (gap/assumption noted) · ❌ not now (missing data/dep).
Every "implementing fn" is an existing, tested module — reuse, not reinvent.

### Tier 1 — intrinsic (per factor, IS-only)

| Metric | Cap | Implementing fn / data | Gap / note |
|---|---|---|---|
| Heldout RankICIR (walk-forward folded, `is_end`-bounded) | ✅ | `walk_forward_validation.run_is_walk_forward` | **verified bit-exact** vs stored evidence |
| Sign-consistency (folds) | ✅ | same | — |
| Mean RankIC, IC hit-rate | ✅ | `factor_eval/ic_analysis.py::compute_ic_summary` | — |
| **Overlap-adjusted t-stat / CI** (20d labels overlap 19/20) | ⚠️ | `factor_eval/statistical_tests.py::bootstrap_sharpe_ci` (block bootstrap) | **statsmodels NOT installed** → no Newey-West `cov_hac`; use block bootstrap (no new dep) OR add statsmodels |
| Monotonicity: `mono_shape` + step-signs + bucket vector + step magnitudes | ✅ | `factor_eval/quantile_analysis.py` + classifier (verified on real data) | `mono_frac_dominant` = diagnostic only |
| Monotonicity orientation by **predeclared** direction | ⚠️ | registry `expected_direction` | populated **30/185** (8/8 approved, 17/88 cand, 5/89 draft) → **train-fold orientation fallback** for the other 155 |
| **Decay** full horizon vector 5/10/20/40, **per-horizon `is_end` clip** | ✅ | per-horizon `load_is_windowed_panel` (`IsWindowedPanel.__post_init__` enforces the clip) + `factor_eval/decay_analysis.py` | +compute: 4 label sets (factor values computed once); **report full vector, not peak** |
| Decay half-life | ✅ | derived from the vector | — |
| **Turnover** one-way `|A_t Δ A_{t-20}|/(2K)×(252/20)` + tie-rate + top/bottom split | ✅ | `factor_eval/cost_aware_eval.py::annualized_turnover` + custom churn | verified (sensible 1.9–11×/yr ranking) |
| Coverage + tier (full/broad/sub) + sample count + size/sector/liq skew | ✅ | panel + `data_infra/provider_metadata.py` | `earn_eps_diffusion_60` flagged `sub` (0.28) |
| **Neutralized** RankIC / ICIR (size + industry) | ✅ | `factor_eval/neutralization.py::neutralize_size_industry` + `$total_mv` + PIT `build_industry_series_asof` (SW2021) | PIT-correct industry |
| **Quantile spread — long-leg excess net vs benchmark** (deployable headline) | ✅ | CSI300/500 (`000300_SH`/`000905_SH`, 2008–2026) + `CostConfig.realistic_china` | long-side cost only (no borrow fee) |
| Long/short **leg decomposition** (diagnostic — where is the alpha) | ✅ | `quantile_analysis.py` | short leg flagged **unrealizable in A-shares** |
| LS spread restricted to **融券标的** universe (capacity-constrained diagnostic) | ⚠️ | eligible set derivable from `margin_detail` coverage | borrow fee not in data → **fixed-haircut assumption** |
| Index-futures market-neutral **basis cost** | ❌ | — | **no IF/IC/IM futures data ingested** → describe qualitatively, never quote a hedged net number |
| Long-leg Sharpe / MDD / Calmar / IR / win-rate | ✅ | `result_analysis/metrics.py` (full suite) | — |
| Factor-return skew / kurtosis / tail-ratio | ✅ | `result_analysis/metrics.py` | — |
| **Deflated Sharpe / PSR** (multiple-testing-aware) | ✅ | `statistical_tests.py::deflated_sharpe_ratio` / `probabilistic_sharpe_ratio` | — |
| **Regime stability** (per-year / bull-bear ICIR) | ✅ | `factor_eval/regime.py::summarize_regime_performance` / `regime_pass_count` | — |
| Capacity / liquidity (ADV-weighted coverage of the active bucket) | ✅ | `$amount` | — |
| Signal autocorrelation / persistence | ✅ | custom (cheap) | — |
| Tie / outlier data-quality + **provisional-data flag** | ✅ | custom + `report_rc` provisional marker | — |

### Tier 2 — marginal orthogonal contribution (relative, VERSIONED)

| Metric | Cap | Implementing fn / data | Gap / note |
|---|---|---|---|
| `marginal_residual_ic` vs **current approved reference set** (leave-one-out) | ✅ | `ic_analysis.py::compute_marginal_ic` | verified on real data |
| `reference_set_version` hash + provisional-aware recompute | ✅ | registry `definition_hash` + `status` | recompute residuals if approved set changes / provisional revoked |
| `marginal_residual_ic` vs **standard style controls** (size/value/mom/qual/liq) | ✅ | `compute_marginal_ic` + style base from catalog (Size 4 / Value 11 / Momentum 15 / Quality 21 / Liquidity 15) | **canonicalize the control set** (open Q5.) |
| Correlation / redundancy to the approved composite | ✅ | `factor_eval/correlation.py::compute_factor_correlation` / `find_redundant_pairs` | — |
| HLZ multiple-testing t-bar = 3.0 (overlap-adjusted) | ⚠️ | block bootstrap | tied to the t-stat gap above |
| ~~Equal-weight incremental ICIR delta~~ | ✅ tested → **REJECTED** | — | confounded (dilution + rewards raw strength); optimal-weight IR if ever wanted |

### Tier 3 — gold evidence (SPARSE, sealed-OOS only)

| Metric | Cap | Note |
|---|---|---|
| `oos_rank_icir`, `oos_ls_sharpe`, IS→OOS sign stability | ✅ existing | only the 8 approved (genuinely spent); burned/unspent labeled; **never faked** |

### Governance / safety

| Item | Cap | Note |
|---|---|---|
| `eval_run_id` + methodology hash (version the sweep as discovery) | ✅ | the 185-metric dashboard is an IS **search surface** → multiple-testing-versioned |
| Resolve-but-label (dashboard never mutates registry status) | ✅ | load-bearing |
| Per-horizon `is_end` clip + PIT loaders + provisional flags = leak-safe | ✅ | the only leak risks are the 3 correctness fixes in §2 |

---

## 2. Capability-driven decisions (substitutions for the gaps)

1. **Overlap-adjusted significance → block bootstrap** (statsmodels absent). Keeps zero-new-dependency.
   *Alternative:* add `statsmodels` to [requirements.txt](../../../requirements.txt) for Newey-West HAC
   (a dependency add — needs sign-off). **Decision needed (Q1).**
2. **Monotonicity orientation:** predeclared `expected_direction` where present (30/185), else **train-fold
   sign, judged on heldout folds** (removes the same-sample circularity GPT flagged). Add a
   `direction_source` column (`registry` / `train_fold`).
3. **Short-side realism:** combined LS is a *diagnostic only*. The deployable headline is **long-leg
   excess net of long-side cost vs CSI300/500**. The 融券标的-restricted LS uses a **fixed borrow-fee
   haircut** (no fee data). Index-futures-hedged neutral is **qualitative only** (no futures data).
4. **Decay** reports the **full 5/10/20/40 ICIR vector + half-life**, never a mined peak; each horizon
   independently `is_end`-clipped.

**The 3 correctness-critical fixes (BLOCK the full run):** per-horizon `is_end` clip (decay leak),
overlap-adjusted significance (inflated t), train-fold monotonicity orientation (circularity). All three
are **buildable now** with the functions above.

---

## 3. Verified results so far (inlined — JSONs are gitignored)

7 representative factors (3 approved / 3 candidate / 1 draft), IS 2014–2020, h=20, IS-only, zero OOS
spent, all via the existing `factor_eval` functions. Heldout ICIR + sign-consistency reproduce stored
evidence **bit-exactly**.

| factor | status | heldICIR | meanRankIC | turn/yr | cov | tier | mono_shape | marginal_resid_IC |
|---|---|---|---|---|---|---|---|---|
| earn_eps_diffusion_60 | approved | +0.417 | +0.036 | 6.9 | 0.28 | sub | top_reversal | +0.012 |
| liq_zero_ret_days_10d | approved | +0.302 | +0.022 | 8.0 | 1.00 | full | insufficient_q | +0.018 |
| qual_piotroski_fscore_9pt | approved | +0.320 | +0.024 | 3.5 | 1.00 | full | irregular | +0.015 |
| liq_vol_cv_20d | candidate | −0.700 | −0.052 | 11.0 | 1.00 | full | monotonic_up | −0.021 |
| qual_gross_profitability | candidate | +0.138 | +0.018 | 3.0 | 0.98 | full | monotonic_up | +0.019 |
| rev_up_down_ratio_20d | candidate | −0.204 | −0.021 | 10.4 | 1.00 | full | inverted_U | −0.004 |
| qual_q_gross_margin | draft | +0.053 | +0.006 | 1.9 | 0.98 | full | top_reversal | +0.013 |

Marginal residual IC confirmed the project principle (select by marginal orthogonal contribution, not
standalone ICIR): `liq_vol_cv_20d` has the biggest standalone |ICIR| (0.70) but retains only ~37% after
orthogonalization (redundant); `qual_gross_profitability` retains ~109% (genuinely orthogonal). The
monotonicity diagnostic independently flagged `earn_eps_diffusion_60` as `top_reversal` — a long-top-
quintile deployment red-flag matching the prior documented "real factor, not a deployable long-only
book" finding. Equal-weight ICIR delta was tested and rejected (disagreed in sign for 3/7; negative for
two approved factors due to equal-weight dilution).

---

## 4. A-share shorting constraint (why the LS口径 is long-leg-centric)

融券 (securities lending) covers only the 标的证券 subset (large-cap-biased); inventory is scarce, fees
8%+, and the bottom-quintile names a factor wants to short are mostly NON-标的. Index futures (IF/IC/IM)
hedge market beta only, not the cross-sectional short leg — and we have **no futures data ingested**. So
a combined Q5−Q1 LS spread is a paper number (the project already flags `oos_ls_sharpe` as "NOT
deployable"). Deployable = **long-leg excess net of cost vs benchmark**; the leg decomposition is the
A-share-relevant diagnostic (alpha in the long leg = usable; alpha in the short leg = mostly not).

---

## 5. Implementation phases

- **P0 — correctness fixes (block full run):** per-horizon `is_end` clip; block-bootstrap significance;
  train-fold monotonicity orientation. Build into the production script; re-verify on the 7-factor subset.
- **P1 — full-catalog IS recompute (~40 min, cached):** all field-eligible factors → Tier 1 + Tier 2
  (residual IC vs approved-ref + vs style controls) + governance stamps; write new evidence columns.
- **P2 — dashboard repoint:** rating = heldout ICIR + sign-consistency, **peer-grouped by coverage tier**,
  overlap-corrected significance flag, neutralized companion, versioned/provisional-aware marginal,
  long-leg-excess deployment column; demote legacy 5d grade to small-print.
- **P3 — deferred (capability-gapped):** index-futures basis cost (needs `fut_daily` ingestion);
  optional statsmodels Newey-West; actual deployment-basket turnover from event-driven runs.

---

## 6. Review questions for GPT 5.5 Pro

1. **Significance gap:** block bootstrap (no new dep) vs adding `statsmodels` for Newey-West HAC on the
   overlapping 20d labels — which is more defensible for ICIR/IC t-stats, and does block bootstrap need a
   specific block length (~20? ~2×horizon?) to be valid here?
2. **Style-control set (Q5 in the matrix):** which specific catalog factors should be the canonical
   size/value/momentum/quality/liquidity controls for the residual-IC-vs-controls column, and should the
   controls themselves be neutralized/orthogonalized first to avoid double-counting?
3. **Train-fold monotonicity orientation** for the 155 factors lacking a predeclared direction — sound,
   or does orienting on train folds and judging shape on heldout folds still leak / add variance? Better
   alternative given only 30/185 have `expected_direction`?
4. **Completeness:** given the A-share long-only constraint, is anything **we are capable of** still
   missing from Tier 1/2 (e.g. you'd expect factor-timing/crowding, IC-skew, conditional-IC by size
   bucket, cost-curve/capacity at multiple AUM levels)?
5. **Cut list:** which of the enriched metrics are low-value / redundant / not worth the compute for a
   descriptive dashboard (vs a promotion gate)? We want signal, not 25 noisy columns.
6. **Residual leak / MT risk** in the capability-constrained design — anything in §1–§2 that is still
   leak-prone or that under-counts the multiple-testing exposure of a 185-factor IS dashboard?
7. **Provisional reference set:** is leave-one-out residual IC vs an 8-factor set that includes 2
   *provisional* approvals (canary-overridden) trustworthy enough to display, or should provisional
   factors be excluded from the reference base until the 2026-06-15 canary resolves?
