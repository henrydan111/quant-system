# Residual control-scope inconsistency — findings + methodology brief for GPT 5.5 Pro

**Status:** root cause CONFIRMED to the exact value (two-way bit-reproduction below). This is a real
eval-correctness bug in the unified-eval residual neutralization, surfaced by the reference-decoupling
migration's value-safety proof. It affects `resid_ic_vs_style_controls_v1` **and**
`resid_ic_vs_approved_*` (the Layer-2 marginal-vs-book metric the decoupling is about), and it makes the
universe-matrix's residual columns **internally inconsistent** (computed two different ways depending on
batch ordering). **We need a methodology call on the intended control scope before fixing + re-running.**

Data drift is fully ruled out (factor values bit-identical). This is not the migration's problem per se —
the migration proof just happened to be the instrument that caught it.

---

## 1. How it surfaced

The reference-decoupling migration includes a V4 value-safety proof: recompute a stratified sample of
legacy matrix cells with current code and assert the reference-INVARIANT Layer-1 columns reproduce the
stored values. Result: **8/24 reproduce exactly; 16/24 differ — but ONLY on two field families:**

- `quantile_profile` — **cosmetic**: the `cd398dc` commit added an `'oriented': True` key to each decile
  entry; the `ann_return` values are identical (`max_rel_dev = 0.0`).
- `resid_*_style_controls_v1` — **real** numeric (0.3 %–10 %).

Core metrics (`mean_rank_ic`, `heldout_rank_icir`, neutralized IC, decay, turnover, long-leg) reproduce
**everywhere**. The residual mismatch hit exactly the **resident-set factors** (the frozen style controls
+ the approved book) and spared non-resident drafts — and the *same* factor `alpha_block_discount_20d`
passed in 2 universes but failed in 1, i.e. the split is **per-cell**, not per-factor.

## 2. Investigation (each step a controlled experiment)

1. **Data drift ruled out.** Seed-cache value vs a fresh `compute_factors` over 2010-2020, for
   `liq_amihud_20d`, `risk_vol_20d`, `grow_n_income_attr_p_yoy_accel_q`, `earn_sue_ni_assets`,
   `earn_eps_diffusion_120`, `val_ep_ttm`, `qual_gross_profitability`: **bit-identical** (`max abs diff
   0.000e+00`, corr 1.0). The 2010-2020 factor values are perfectly stable.

2. **Residual function is deterministic + batch-independent.** Calling `residual_ic_vs_controls` directly
   with a fixed `proc` dict, single-factor vs 15-factor batch: identical `proc[candidate]`, 0/13 controls
   differ, residual identical. So the residual *function* is not the source.

3. **Single vs batch vs legacy, through `_evaluate_batch` (`liq_amihud_20d @ univ_csi1000`):**

   | field | A: single-factor | B: 15-factor batch | LEGACY (full seed batch) |
   |---|---|---|---|
   | `mean_rank_ic` | 0.0758015706750265 | 0.0758015706750265 | 0.0758015706750265 |
   | `heldout_rank_icir` | 0.6002234557358826 | 0.6002234557358826 | 0.6002234557358826 |
   | `resid_ic_vs_style_controls_v1_signed` | **−0.014566** | **−0.015175** | **−0.016068** |

   IC/ICIR invariant; the residual is **monotonic in batch size** — it depends on the eval batch
   composition.

4. **Exact two-way reproduction (the smoking gun).** Recomputing the residual for the same cell, varying
   ONLY the control-processing scope:

   ```
   controls FULL-MARKET (resident_processed)  -> resid -0.014566   == the single-factor recompute
   controls UNIVERSE-MASKED (batch_processed) -> resid -0.016068   == the LEGACY stored value
   ```

   Both reproduce to the bit. The entire delta is the control-processing **scope**.

## 3. Root cause

In `_evaluate_batch` ([unified_eval_full_run.py](workspace/scripts/unified_eval_full_run.py), ~line 189-191):

```python
batch_processed = preprocess_for_residual({n: batch_df[n] for n in names}, names, winsor=...)
processed = {**ctx["resident_processed"], **batch_processed}   # <-- mixes two scopes
```

- `ctx["resident_processed"]` is built once in `build_base_ctx` from the **unmasked, full-market** seed →
  controls winsorized + z-scored over the **full market**.
- `batch_processed` is built from the **universe-masked** `batch_df` → controls (those co-evaluated in the
  batch) winsorized + z-scored over the **evaluation universe**.

A control's processing scope therefore depends on **whether it shares the eval batch with the candidate**.
In the matrix, the resident set (style controls + approved book) is computed in **batch-0**, so for those
factors every style control is in `batch_processed` → **universe-masked**; non-resident factors evaluate in
later batches, so their controls fall through to `resident_processed` → **full-market**. Hence the
resident/non-resident split, and the per-cell variation (a cell's scope depends on which batch evaluated it
during the resumable incremental build).

**Why the residual changes with scope, precisely:** the OLS residual is invariant to affine transforms of
the regressors (with an intercept), so the z-score *scaling* difference between full-market and
universe-masked is irrelevant. The non-affine part is **winsorization** — clipping at full-market vs
universe percentiles clips different observations, which changes the residual. (Verified: the difference
vanishes if winsorization scope is held constant.)

## 4. Impact

- **`resid_ic_vs_approved_*` has the same bug** — it uses the same `processed` dict (lines ~259-264). This
  is the marginal-vs-book metric the whole decoupling effort is about, and a **gate-selection metric** (the
  D4a cohort adjudication read it). Some factors' marginal residuals were computed against masked controls,
  others against full-market controls.
- **The matrix evidence is internally inconsistent** — `resid_*` columns are computed two ways across the
  1,526 matrix rows, as an artifact of batch ordering.
- **A native re-run reproduces the bug** (batch-0 still masks, later batches don't) unless the scope is
  made consistent first.
- The **value-copy migration is moot** — there is no single "correct" legacy residual to copy.

## 5. How institutions handle this (Barra / Axioma risk-model practice)

- Style/risk factor exposures are standardized + winsorized **once on a fixed broad estimation universe**
  (full market or a broad index), producing **universe-independent** exposures. A stock's size/value
  exposure is defined relative to the whole market, not re-derived per sub-portfolio.
- Alphas are neutralized against these fixed exposures; to evaluate within a sub-universe you **restrict to
  the sub-universe's names at the IC/portfolio step only** — you do **not** re-standardize the style
  exposures within the sub-universe.
- Principle: the style definition is **stable and shared across universes**; only the evaluation scope
  changes. Re-standardizing per sub-universe (the "universe-masked" path) is non-standard.

→ The institutional standard maps to **consistent full-market control processing**. It is also the cheaper
fix here (`resident_processed` is already full-market; the fix is to stop `batch_processed` from overriding
controls). A secondary inconsistency: the **candidate** is currently masked-scope processed; full Barra
consistency would process the candidate at full-market scope too (making the residual a market-neutral
quantity whose IC is then measured per-universe).

## 6. Decision needed (the methodology call)

1. **Control scope:** consistent **full-market** (Barra-standard, cheaper) vs consistent **universe-masked**
   (re-standardize style within each evaluation universe)?
2. **Candidate scope:** keep the candidate masked (mild residual scope mismatch, but consistent across
   factors) or also move it to full-market (full Barra consistency; residual becomes universe-independent,
   IC measured per-universe)?
3. **Winsorization specifically** is the only non-affine lever — confirm it should be done at the chosen
   scope consistently.

## 7. Recommended sequence (pending the call)

1. Fix the control-scope inconsistency in `_evaluate_batch` / `build_base_ctx` (one scope, consistently).
2. Re-run the universe matrix natively → consistent `resid_*` columns.
3. Re-confirm any gate adjudication that selected on `resid_ic_vs_approved_*` (D4a cohort) under the fixed
   metric.
4. Apply the reference-decoupling infra (schema / row_role keying / Layer2ResidualStore / canonical view /
   stable run_id) to the freshly re-run rows; drop the value-copy migration.

**Reproduction artifacts:** `workspace/outputs/unified_eval_matrix/migration_sample_recompute_token.json`
(per-cell pass/diff + `max_rel_dev`); diagnostics in this session's logs. All numbers above are exact
(bit-level) reproductions, not estimates.
