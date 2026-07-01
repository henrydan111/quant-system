# D4a / D-COMP / P-GATE decision-delta — cross-review brief (for GPT 5.5 Pro)

**Gate:** APPROVE → declare the residual-control-scope arc CLOSED (bug → fix → two-layer decoupling
→ ~38h rebuild → gated live import → **this** decision-delta). / CHANGES REQUIRED. This is *your*
explicitly-required final post-import step: "for the D4a/D-COMP/P-GATE cohort factors that consumed
`resid_ic_vs_approved_*`, compute old contaminated vs new corrected residual → unchanged / flipped /
needs-readjudication; if a decision flips: old pass→fail supersede, old fail→pass review-eligible (not
auto-promote), ranking change → rerun marginal-contribution selection."

**Repo:** https://github.com/henrydan111/quant-system  **Reviewed commit:** `a43bd0e` on `report-rc-registration`
**Artifact (human-facing):**
https://github.com/henrydan111/quant-system/blob/a43bd0e/workspace/research/cicc_replication/D4A_PGATE_DECISION_DELTA.md
**Builder (read-only; JSON output is gitignored, reproducible):**
https://github.com/henrydan111/quant-system/blob/a43bd0e/workspace/scripts/d4a_pgate_decision_delta.py

## Result: 0 decisions flipped, 0 material ranking moves

**Scope** — 34 cohort factors carry a `catalog_factor_id` link in the two v2 manifests
([fundamental](https://github.com/henrydan111/quant-system/blob/a43bd0e/config/replication/cicc_fundamental_cohort_v2.yaml),
[price-volume](https://github.com/henrydan111/quant-system/blob/a43bd0e/config/replication/cicc_price_volume_cohort_v2.yaml)):

- **28 adjudicated under the contaminated matrix** (have a quarantined `legacy_contaminated_residual_scope` univ_all row) — the decision-delta set.
  - **10 with a *persisted* Phase-D P-GATE governance ceiling**: `comp_cicc_profit` + the 9 D4a difference factors (`qual_{ccrd,cfoad,csrd,curd,dad,dted,qrd,road,roed}`).
  - **18 D5 base factors** registered as drafts but never run through the ceiling-wired gate with a persisted record (no "old recorded ceiling" exists for them — see the question below).
- **6 born under the corrected methodology** (E1a `mmt_*`, task #34) — no legacy row, never consumed the contaminated residual → out of scope.

### Four independent proofs

**(1) Structural — the ceiling cannot read a residual.**
[`resolve_replication_ceiling`](https://github.com/henrydan111/quant-system/blob/a43bd0e/src/alpha_research/factor_registry/replication_governance.py#L285-L302)
takes `replication_tier, claim_class, coverage_tier, effective_ic_days, oos_eligibility,
cross_section_below_min, has_uncertified_operator, max_stat_calibrated, denominator_frozen,
sealed_oos_pass, power_floor_pass, truth_observed, coverage_observed, require_claim,
min_effective_ic_days`. **Residual parameters: NONE** (introspected at runtime by the builder).
`grep resid` in BOTH gate files
([replication_governance.py](https://github.com/henrydan111/quant-system/blob/a43bd0e/src/alpha_research/factor_registry/replication_governance.py),
[factor_lifecycle_steps.py](https://github.com/henrydan111/quant-system/blob/a43bd0e/src/research_orchestrator/factor_lifecycle_steps.py)):
**0 matches**.

**(2) Gate-input stability.** The only matrix-derived inputs `_cohort_ceiling` reads are
`coverage_tier` + `effective_ic_days`
([factor_lifecycle_steps.py#L515-L527](https://github.com/henrydan111/quant-system/blob/a43bd0e/src/research_orchestrator/factor_lifecycle_steps.py#L515-L527)).
For **every** cohort factor at univ_all the legacy (old) and native (new) rows carry an **identical**
`coverage_tier` + `effective_ic_days` (and identical `mean_rank_ic`/`heldout_rank_icir`). The fix
touches only the residual path; the raw-IC/coverage paths are byte-stable. Builder reports **0 mismatches**.

**(3) Ceiling equality.** For each of the 10 factors with a persisted Phase-D governance ceiling
(produced under the contaminated evidence), the live `_cohort_ceiling` re-run against the **corrected
native evidence** returns the identical ceiling — all 10 stay `candidate_ceiling`. **0 differences.**

**(4) Residual delta.** At **univ_all** (the gate domain) the eval universe == the broad ESTU, so
transform-then-mask is a structural no-op there. Across the 28 contaminated-era factors:
`resid_ic_vs_approved_*` sign-flips = **0**, movers |Δ|>0.01 = **0**. Largest approved-stable movers:
`qual_road` −6.33e-3, `qual_roed` −6.26e-3 — expected (ROE/ROA-family vs an ROE-correlated approved
book; the marginal-vs-book residual is genuinely scope-sensitive for them, exactly the asymmetry the
fix corrects) but it is the **demoted descriptive Layer-2 metric** (no gate reads it), **no sign flip**,
their **style residual moves only −3.2e-4 / −7.4e-4**, ceiling unchanged.

**Selection re-rank** by the style residual (`resid_ic_vs_style_controls_v1`, the 2026-06-15 selection
criterion) at univ_all: **Spearman 0.9975 / Kendall 0.9853**. The only rank change is
`grow_or_q_yoy` ↔ `grow_op_q_yoy` swapping ranks 0↔1, separated by **2.1e-5** in style residual — a
co-equal tie swapping within recompute noise (classified `tie_within_noise`, threshold 1e-3).
**Material rank moves (separation ≥ 1e-3): 0.**

### GPT flip-rules — none triggered

| rule | triggered? | why |
|---|---|---|
| old pass → new fail ⟹ supersede | NO | 0 ceilings changed |
| old fail → new pass ⟹ review-eligible | NO | same |
| ranking change ⟹ re-run marginal selection | NO | Spearman 0.9975; lone swap is a 2.1e-5 tie, 0 material moves |

## Specific questions for you

1. **Is the structural-independence proof (1)+(2) sufficient** to conclude no P-GATE/D4a/D-COMP
   decision can have been moved by the residual rebuild — i.e. do you accept "gate signature has no
   residual input + the two matrix inputs it does read are byte-identical old-vs-new" as dispositive,
   with (3) ceiling-equality as the empirical confirmation on the 10 persisted cases?

2. **The 18 D5 base factors have no persisted Phase-D ceiling** (never run through `gate_cohort_factors
   --live`), so proof (3) is vacuous for them — they rest on (1)+(2) only. Is that acceptable, or do
   you want all 18 explicitly re-adjudicated through `_cohort_ceiling` now (they would all resolve
   `candidate_ceiling`, gate inputs being identical) and the result persisted, so the artifact carries
   a recorded ceiling for every contaminated-era factor rather than a structural argument?

3. **The tie-swap classification** — treating a 2.1e-5 style-residual swap between two adjacent
   co-equal factors as `tie_within_noise` (not a material ranking change, so no marginal-selection
   re-run) — is the 1e-3 noise floor defensible, or do you want the marginal-contribution selection
   re-run regardless to demonstrate the swap is selection-irrelevant (no cohort selection cut is live;
   both factors sit at `candidate_ceiling`)?

4. **Anything missing** from the decision-delta to declare the arc closed — a residual family,
   universe, or decision surface not covered? (Note: `resid_ic_vs_approved_current` from
   `unified_metrics_json` was checked alongside `_stable`; sub-universe residual deltas were not
   tabulated here because the univ_all-only gate fail-closed refuses non-univ_all claims, so no landed
   decision was adjudicated on a sub-universe value.)
