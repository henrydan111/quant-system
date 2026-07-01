# P-GATE implementation cross-review brief (for GPT 5.5 Pro)

> 2026-06-14. This asks GPT 5.5 Pro to **adversarially review the IMPLEMENTATION** of the
> first four pieces of the CICC Rev5 roadmap's "minimum prerequisite set". The DESIGN
> (Rev5) is already 3-round-APPROVED — do **not** re-litigate it; review whether the code
> faithfully + safely realizes it, and surface bugs / governance holes / unsafe shortcuts.
>
> GPT 5.5 Pro is web-based — all artifacts are on GitHub, branch `report-rc-registration`
> (HEAD `800ebfd`), repo `henrydan111/quant-system`. Links below.

## The repo, paths, commits

Approved design (context, do not re-review):
- Rev5 roadmap: https://github.com/henrydan111/quant-system/blob/report-rc-registration/workspace/research/cicc_replication/REMAINING_CICC_FORMAL_EVAL_PLAN.md
- Universe plan Draft-7 (the governance substrate): https://github.com/henrydan111/quant-system/blob/report-rc-registration/workspace/research/factor_expansion/universe_coupled_evaluation_plan.md

The implementation under review (4 commits):
- `7b0197a` governance skeleton · `a4b712c` adjudicator · `a1bf19e` gate wiring · `800ebfd` canary
- Compare view: https://github.com/henrydan111/quant-system/compare/d2eb418...800ebfd

Files:
- Governance module (schema + lattice + adjudicator + store): https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/alpha_research/factor_registry/replication_governance.py
- Frozen cohort manifest: https://github.com/henrydan111/quant-system/blob/report-rc-registration/config/replication/cicc_fundamental_cohort_v1.yaml
- Gate wiring (publish handler + `_cohort_ceiling`): https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/research_orchestrator/factor_lifecycle_steps.py
- Existing claim/taint infra (consumed): https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/alpha_research/factor_registry/domain_claims.py
- Tests: https://github.com/henrydan111/quant-system/blob/report-rc-registration/tests/alpha_research/test_replication_governance.py
- Canary driver: https://github.com/henrydan111/quant-system/blob/report-rc-registration/workspace/scripts/canary_cicc_profit.py

## What was built (vs Rev5)

1. **Governance skeleton (Rev5 §9/§12)** — `CohortManifest` (frozen YAML + content-addressed `manifest_sha`); the 5 cohort denominators (`source`/`daily_replicability`/`formalization_candidate` frozen; `exact_oos_eligible`/`sealed_attempt` tracked); `compute_oos_quarantine_start` (§9.3 `max(system_oos_start, truth_label_end+horizon+embargo)`, calendar-injected); `ReplicationGovernanceRecord` store (one record per (cohort,factor,claim), replacing six ledgers, §12.3).

2. **Deterministic `status_ceiling` lattice (§12.4)** — `resolve_status_ceiling`: strict→loose (`blocked → dev_evidence_only → evidence_only → candidate_ceiling → eligible_for_oos → eligible_for_approved`); strictest **cap** wins; **caps** (must be removed) vs **gates** (must be acquired) kept separate; `orientation_undetermined` and other `NON_CEILING_FLAGS` fail closed if passed as a cap (§11.1b — a weak signal is not disqualified).

3. **Adjudicator** — `resolve_replication_ceiling` composes manifest (tier + oos_eligibility) + 7-domain matrix evidence (coverage_tier + effective_ic_days) + `FactorDomainClaim` (class) into the ceiling. Conservative: `tainted_post_hoc_max_stat` is NOT `clean_or_calibrated` until P-CAL exists; an uncertified operator hard-blocks; §3.9 depth floor (`effective_ic_days < 756 → evidence_only`).

4. **Gate wiring (item 2b-i, approach A = consult the standing 7-domain matrix, do NOT re-run domains in the gate)** — `handle_factor_lifecycle_registry_publish` adjudicates CICC-cohort factors (matched by `catalog_factor_id` in a manifest); ceiling below candidate → **refuse** promotion (stays draft, no signed evidence); candidate_ceiling+ → promote as before; a `ReplicationGovernanceRecord` is persisted either way.

5. **Canary (item 3)** — `comp_cicc_profit` (CICC Profit = CFOA+ROE+ROIC) registered → claimed → adjudicated → **candidate_ceiling** (`short_oos_power_floor_fail`); validated on the live registry. Also corrected two §8 over-optimisms: D4a needs a field-registration sub-wave (slot fields are `unknown_field`), and only Profit is a clean D-COMP composite.

## Design decisions I want scrutinized (these are MINE, not in the approved plan)

- **Fail-OPEN gate adjudication.** In the publish handler, any exception in `_cohort_ceiling` is caught and treated as non-cohort (promote as before), with a loud log. Rationale: a bug in new governance must not break the human-gated publish; `candidate` is resolve-but-label; the sealed-OOS gate still guards `approved`.
- **Approach A (consult, don't re-run).** The gate keeps its univ_all walk-forward for the fresh verdict and CONSULTS the 7-domain matrix (auto-evidence, `formal_evidence_eligible=False`) for the ceiling, rather than re-running 7 domains per gate.
- **`catalog_factor_id` excluded from `manifest_sha`** — post-registration operational linkage, not part of the frozen scientific declaration, so linking a factor never churns the frozen hash.
- **The dominant cap is the manifest's hand-set `oos_eligibility: short_window`**, not a computed remaining-OOS-window power-floor check.

## Self-exposed blind spots (assess whether blocking or acceptable)

1. **Fail-open hole**: if `_cohort_ceiling` throws for ALL cohort factors (e.g., manifest fails to load), every cohort factor silently promotes WITHOUT a ceiling check, defeating P-GATE — and the handler can't distinguish cohort from non-cohort when the helper itself throws. Only mitigation is logging.
2. **Auto-evidence influences a (negative) status decision**: the matrix (evidence-only) feeds the ceiling that can REFUSE candidate promotion. It only caps, never promotes — but is that consistent with "automated evidence never drives status"?
3. **short_oos cap is a manual flag, not computed**: `oos_quarantine_start` is left unset on the record; the cap comes from `oos_eligibility: short_window` hand-set in the manifest. A row that omits it defaults to `pending` (no short-oos cap) and could reach `eligible_for_oos`. Should the adjudicator instead COMPUTE the quarantine from `truth_label_end` + check the §9.4 power floor mechanically?
4. **No composite lineage taint (§3.1c)**: `comp_cicc_profit`'s claim is `clean_singleton_primary` even though its components were truth-observed 2010-2022. The manifest's `short_window` produced the correct `candidate_ceiling`, but a future composite of observed components with `oos_eligibility` omitted (or a composite not in any manifest) would get clean + reach `eligible_for_oos`, leaking the components' observation.
5. **univ_all-only gate**: `gate_universe` is hard-coded `univ_all`; a factor whose declared `primary_intended_universe` is non-univ_all is still adjudicated on univ_all. The universe-plan §3.3 "adjudicate by declared domain" is not yet wired.
6. **Manifest is a human-authored frozen file**: the entire ceiling hinges on the per-row `replication_tier_planned` + `oos_eligibility` being correct; `truth_table_manifest` QA (§11.3) is lazy/not-yet-done.

## Requested verdict

Per the prior rounds' format: an overall verdict (**APPROVE** / **APPROVE WITH CONDITIONS** / **CHANGES REQUIRED**) plus a numbered list of findings, each tagged **blocking** / **non-blocking**, with the specific minimum change. Focus especially on blind spots 1, 3, 4, 5 (the mechanical gaps) — are any of them blocking before the next sub-wave (D4a field registration / P-OP / more D-COMP composites), or are they acceptable given the conservative fail-states and that nothing has been promoted to `candidate` yet?
