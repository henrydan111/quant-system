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

## Selection criterion (user decision 2026-06-15): anchor on the STYLE residual

Factor selection anchors on `resid_ic_vs_style_controls_v1` — the residual vs the FROZEN 14-factor
institutional style set (size/value/momentum/reversal/quality/liquidity/vol), a reference-INVARIANT
Layer-1 metric. `resid_ic_vs_approved_{stable,current}` (marginal-vs-book) is **demoted to a descriptive
Layer-2 metric** (combination-time / dashboard), NOT a selection criterion.

Verified: NO code makes a pass/fail/selection decision on `resid_ic_vs_approved` — it appears only in the
dashboard display (`content.py`, labelled "marginal") and the evidence store. The formal gates
(`factor_lifecycle` IS walk-forward, sealed-OOS, `_cohort_ceiling`) read IC/ICIR/sign-consistency/
OOS-Sharpe/governance, never the residuals. So this decision changes the **selection principle + dashboard
emphasis**, not the formal-gate code.

Consequence: the "recompute on every approval" pressure leaves the selection path entirely — the selection
basis (style residual) is reference-invariant by construction. The two-layer architecture is validated:
**Layer-1 (matrix, invariant, incl. style residual) = selection basis; Layer-2 (approved residual) =
descriptive**. The D4a "re-confirm" is therefore a **re-rank of the cohort by the rebuilt style residual**,
not the reversal of any landed formal decision (none read the approved residual).

## GPT pre-flight review (conditional GO) — hardening status

GPT 5.5 Pro pre-flighted the ~30h rebuild and returned **conditional GO**: do NOT launch until the
fail-closed hardening lands + the 3-path smoke passes. Status:

| # | GPT requirement | Status |
|---|---|---|
| 1 | `_done_factors` must NOT count error / partial / wrong-hash-or-scope rows as done | **DONE** — `_is_success_record(rec, expected_schema, expected_layer1_by_universe)` + validator-gated `_done_factors`; matrix + layer2 pass the methodology-aware validator. Unit-tested. |
| 2 | Sanitize/truncate the JSONL tail before append (not just ignore a partial line) | **DONE** — `_sanitize_results_tail` backs up `results.corrupt.<n>.jsonl` + rewrites valid-only, ends with `\n`; called at producer startup. Unit-tested. |
| 3 | Assert `residual_panel` is UNMASKED when `eval_mask` present (no silent masked fallback) | **DONE** — `_assert_residual_panel_broad` (aggregate non-null-outside check, robust to sparse factors) in `_evaluate_batch`. Unit-tested (raises on a masked panel). |
| 4 | Positively QUARANTINE old contaminated rows before import (not rely on a helper) | **DONE** — `row_role=legacy_contaminated_residual_scope`; `canonical_layer1_evidence` DROPS quarantine roles; `store.quarantine_legacy_residual_scope()` + `quarantine_legacy_residual_scope.py` (dry-run default). Unit-tested. |
| 5 | Run lock (single writer) | **DONE** — `run.lock` (pid/host/git/hashes), refuse-if-exists + `--force` for stale, released via `atexit`. |
| 6 | 3-path smoke (batch-0 resident + non-resident remaining-batch + Layer-2; batch-order invariance) | **RUNNING** (matrix `--limit 20 univ_all,csi1000` + layer2). |
| 7 | `eval_mask` alignment fail-closed (missing mask rows RAISE, not `fillna(False)`; `Series.where`) | **DONE** — `_mask_to_eval_universe` raises on missing rows + asserts unique/aligned index. Unit-tested. |
| 8 | run_id per-universe (hashes differ by universe) | **DONE** — `matrix_<schema>_<universe>_<layer1_hash>`. |
| 9 | Don't reuse smoke records — full run from a CLEAN outdir | **PENDING (op)** — delete smoke `results.jsonl`/`methodologies.json` before the full run (caches + legacy archive kept). |
| 10 | Cache manifest (stale-cache tripwire) | **DONE** — `cache_manifest.json` (time_split/schema/hashes/cache-digests); fails closed on time_split/schema drift. |

**Launch checklist (GPT):** clean outdir · JSONL sanitizer + validated done-set · residual-panel guard ·
3-path smoke · cache manifest · legacy quarantine · run lock. All code-side items landed + tested
(83 green across the touched files); remaining = run the 3-path smoke (in flight) + the operational
pre-launch steps (clean outdir, quarantine run).

## Sequence

1. Patch residual scope (Option C) + `residual_preprocess_scope` hashed.
2. Land the (already-built, tested) reference-decoupling infra together with the scope fix, so the fresh matrix
   is born under the decoupled schema.
3. Rerun the 7-domain matrix (every factor×universe whose residuals enter dashboards/gates).
4. Re-confirm D4a / P-GATE decisions that consumed `resid_ic_vs_approved_*`.
5. Import the fresh evidence; mark the old matrix `legacy_contaminated_residual_scope`.
6. **Do NOT value-copy migrate** the old residual columns.
