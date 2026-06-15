# Residual control-scope fix — GPT 5.5 Pro verdict + implementation plan

GPT 5.5 Pro reviewed [the findings](RESIDUAL_CONTROL_SCOPE_BUG_findings.md) and returned a methodology
ruling. This doc records the verdict and the implementation contract.

## Verdict (canonical residual definition)

```
canonical resid_ic_vs_style_controls_v1 / resid_ic_vs_approved_*:
  raw full panel
  → winsorize + z-score on a FIXED broad estimation universe (ESTU_STYLE_V1; = univ_all for now)
  → mask to the evaluation universe
  → per-date OLS residual within that universe
  → residual IC within that universe
```

- **Control scope:** consistent **broad ESTU** (Barra/Axioma-standard: style exposures standardized once on a
  fixed broad universe → universe-INDEPENDENT; sub-universe enters only at IC/portfolio time). Universe-local
  control standardization is a valid *secondary diagnostic*, NOT the canonical gate metric.
- **Candidate scope:** the candidate is **also** broad-ESTU standardized, THEN masked — NOT candidate-masked +
  controls-broad (that is asymmetric: a locally-shaped dependent variable compared against globally-shaped
  controls). GPT explicitly rejected "merely stop `batch_processed` overriding controls while leaving the
  candidate masked."
- **Winsorization** is the only non-affine lever (OLS residual is affine-invariant with an intercept); it must
  be done at the declared broad scope, consistently for candidate + controls.
- `residual_preprocess_scope` is a **hashed methodology knob** — changing it forces a residual-matrix rerun.

## Blast radius (confirmed against the code)

- Affected: `resid_ic_vs_style_controls_v1`, `resid_ic_vs_approved_{stable,current}_*` (the only paths using the
  mixed `processed` dict). The marginal-vs-book residual is a **gate-selection metric** — D4a / P-GATE
  decisions that read it must be **re-confirmed** under the fix.
- NOT affected: `mean_rank_ic`, `heldout_rank_icir`, neutralized IC, decay, turnover, long-leg (they use the
  masked raw candidate + label, computed before residuals). Old rows: raw metrics keepable as diagnostic, but
  the row is NOT clean methodology-equivalent evidence; mark `legacy_contaminated_residual_scope`.

## Implementation (Option C — make the contract hard to violate)

1. **`residual_ic_vs_controls`** gains `eval_mask: pd.Series | None` (+ `preprocess_scope` label). It receives
   broad-ESTU `processed_controls` (candidate + controls, full panel), then **masks proc series + label to
   `eval_mask`** before `compute_marginal_ic`. Asserts every processed series + the mask span the panel index.
   `eval_mask=None` → full-panel (univ_all) behavior, unchanged.
2. **`_evaluate_batch`**: the residual section preprocesses the candidate from the **UNMASKED** panel
   (`ctx["residual_panel"]`, broad ESTU) — `processed = {**resident_processed, **batch_processed_broad}` (both
   broad now) — and passes `ctx["eval_mask"]` to `residual_ic_vs_controls`. The raw-metric paths (IC / WF /
   quantile / turnover / coverage) keep using the **masked** candidate (universe IC), unchanged. (GPT Option A:
   carry both the masked panel for raw metrics and the unmasked panel for residual preprocessing.)
3. **Matrix / layer2 callers** pass `residual_panel`=unmasked batch_df + `eval_mask`=universe mask; the
   full-market sweep (univ_all) passes `eval_mask=None` (broad == eval, already correct — that is why univ_all
   factors were unaffected).
4. **`EvalMethodology`**: add `residual_preprocess_scope="ESTU_STYLE_V1"` to the hashed fields (and to
   `layer1_methodology_hash`, since the residual is a Layer-1 metric). Bumps the hash → rerun required.
5. **R4 invariance test** + the migration sample-recompute call `_evaluate_batch` directly — update to pass
   `eval_mask=None` (or all-True) so they stay green.

## Required tests (GPT)

1. **Batch-order invariance** — same factor×universe as batch-0 / later-batch / single-factor → residual columns
   identical (the regression test that would have caught this bug).
2. **Scope contract** — broad-transform-then-mask == canonical; universe-local-transform differs on a
   constructed panel with a heavy-tailed control (so winsorization bites).
3. **Residual-only blast-radius** — old vs fixed: `mean_rank_ic`/`heldout_rank_icir` unchanged; residual columns
   may change.
4. **Methodology-hash** — changing `residual_preprocess_scope` changes the hash (+ layer1 hash).
5. **Universe guard** — `processed_full` non-null outside the universe; after masking, `compute_marginal_ic`
   sees only universe names (n rows == universe breadth).

## Sequence

1. Patch residual scope (Option C) + `residual_preprocess_scope` hashed.
2. Land the (already-built, tested) reference-decoupling infra together with the scope fix, so the fresh matrix
   is born under the decoupled schema.
3. Rerun the 7-domain matrix (every factor×universe whose residuals enter dashboards/gates).
4. Re-confirm D4a / P-GATE decisions that consumed `resid_ic_vs_approved_*`.
5. Import the fresh evidence; mark the old matrix `legacy_contaminated_residual_scope`.
6. **Do NOT value-copy migrate** the old residual columns.
