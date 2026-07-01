# Factor Eval Methodology v1 — GPT 5.5 Pro cross-review response

> Review verdict: **CHANGES REQUIRED** — approve the stage architecture, ship **v1.1** after 7
> minimum changes. Reviewed against the v1 permalink @ `1ca2be6`. **Disposition: ALL findings
> ACCEPTED** (no pushback — the two blocking issues are genuine defects in v1). Two
> implementation refinements added below where GPT's recommendation has a blast-radius nuance.
> Changes folded into [FACTOR_EVAL_METHODOLOGY_v1.1.md](FACTOR_EVAL_METHODOLOGY_v1.1.md).

## Disposition table

| # | Finding | Disposition | Resolution in v1.1 |
|---|---|---|---|
| **B1** | Style-residual contradiction ("clean selection basis" vs "annotation-only") | **ACCEPT** (real defect) | Stage 2/4/6: selection score = **direction-aligned raw heldout RankICIR/mean RankIC + redundancy penalty**; `resid_ic_vs_style_controls_v1` is a **reference-invariant diagnostic ("distinct from generic styles?"), NOT the default selection score** — usable as the score *only* when the style book is the declared benchmark being tested. |
| **B2** | Canonical gate universe left open | **ACCEPT** (the cop-out that caused E-wave) | New **§A4 Dual-scope regime** (below), wired hard into Stage 5/7. |
| 3 | Stage 3 must be machine-binding, not a reader | **ACCEPT** | Stage 3 emits machine-readable `quality_flags` + `status_effect` caps; Stage 5/6/7 **must** read them (fail-closed). |
| 4 | `approved` needs strict scope language (display/API invariant) | **ACCEPT** + refinement | Part D: `approved = approved_on_scope`; scope-stamp is a **display/API invariant**. *Refinement:* implement as **display/semantics, do NOT rename the status enum** (see R1). |
| 5 | Stage 7 bar disconnected from deployment | **ACCEPT** + refinement | Keep one lifecycle `approved`; surface as **`approved_signal[scope]`** + always show `deployable_on_<universe>: yes/no/untested` beside it. |
| 6 | Deployment may overfit spent OOS | **ACCEPT** | Stage 8 requires a **`DeploymentFrozenPlan`** (hashed, one-shot); later runs labeled `post_oos_exploratory`. Mirrors `FrozenSelectionSet` at the deployment layer. |
| 7 | Net-of-cost diagnostics belong in Stage 2/3 | **ACCEPT** | Stage 2/3 add turnover-normalized IC, holding-period decay, long-leg turnover, one-way cost-drag-by-universe, capacity/limit-hit proxies — as **caps/warnings**, not full backtests. |
| 8 | Cohort-level pre-registration for handbook/family expansions | **ACCEPT** | Stage 0 adds a **`CohortHypothesis`** (all formulas, family, direction policy, allowed variants, dedup rules, caps, target universe, **no-add-after-results**). *Note:* `cicc_price_volume_cohort_v2.yaml` is the proto-artifact — formalize it. |
| 9 | Stage 4 must separate cohort-redundancy from book-marginality | **ACCEPT** | Stage 4 emits two records: `cohort_redundancy` (vs own family) and `book_marginality` (vs approved/target book); "not redundant within cohort" ≠ "adds to the deployed book". |
| F1–F8 | Part F open questions | **ACCEPT GPT's answers** | Part F rewritten as **RESOLVED** with the dual-scope regime, scope-stamped single status, one-OOS-per-targeted-frozen-set, two-tier marginal, sign-stability hard for deployment-bound, deployment-as-metadata-shown-beside-approved, net-of-cost in Stage 2/3, Stages 2–4 bundled-but-separate-outputs. |

## The dual-scope regime (B2 resolution — the load-bearing decision)

```
research candidate        : may be earned on univ_all, MUST be scope-stamped,
                            does NOT imply deployability.
deployment-bound candidate: must PASS (or be explicitly accepted on) the declared
                            target investable universe — normally univ_liquid_top300
                            or a declared ESTU. liquid evidence is a HARD selection input.
approved[signal, scope]   : approved on the SAME universe/scope as the FrozenSelectionSet
                            being validated. full-provider approved ≠ liquid-top300 approved.
```

`univ_liquid_top300` is **not** the single canonical universe for all research (that would wrongly
reject broad-but-useful signals destined for a top-800 / CSI1000 / market-neutral book), **but it is
mandatory for any claim of deployable relevance.**

## Two implementation refinements (where I diverge slightly on *how*, not *what*)

- **R1 — `approved_signal` is display/semantics, not an enum rename.** GPT recommends scope-stamped
  `approved_signal`. The status *value* `approved` is referenced by the writer gate, the resolver
  allow-set, the release gate, and ~dozens of tests; renaming the enum is a large, risky blast
  radius for no governance gain. v1.1 keeps the enum value `approved` and makes **the
  display/API/registry render it as `approved_signal[universe, metric, window]`** with deployability
  shown beside it. Same guarantee, no churn. (GPT's own "keep one lifecycle approved status" line
  supports this.)
- **R2 — the cohort manifest already exists as the proto-`CohortHypothesis`.** Finding 8's artifact
  is not net-new: `config/replication/cicc_price_volume_cohort_v2.yaml` already pins source chart,
  formulas, dedup/proxy rules, and family caps. v1.1 generalizes *that* artifact + adds the missing
  fields (a-priori direction policy + the explicit **no-add-after-results** clause) rather than
  inventing a parallel structure.

## Bottom line

The architecture stands; v1.1 resolves both blocking issues and the 7 required changes. Net effect
(GPT's own summary, which I endorse): with these changes the methodology would have caught E-wave's
liquid-universe weakness **at Stage 3, before any OOS spend**, selected reps without the
style-residual confusion, spent the seal on a **properly scoped** frozen set, and recorded the
deployment failure as a **strategy-layer metadata** result rather than a factor-status contradiction.
