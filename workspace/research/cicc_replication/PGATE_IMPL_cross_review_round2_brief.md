# P-GATE implementation cross-review — Round 2 brief (for GPT 5.5 Pro)

> 2026-06-14. Round-1 verdict was **CHANGES REQUIRED** (10 blocking + 2 non-blocking). All
> 12 findings were ACCEPTED; the fail-closed core is folded in (8 done + 2 partial guards),
> 4 heavier items deferred. This round asks GPT to **(a) verify the fixes actually close the
> findings without regression, and (b) hunt for NEW holes the hardening may have introduced**
> — over-correction (fail-closed-so-hard-nothing-can-ever-promote) is the natural risk, plus
> any new edge the fail-closed paths opened.
>
> GPT 5.5 Pro is web-based. Branch `report-rc-registration`, repo `henrydan111/quant-system`.

## Read

- **Round-1 triage / what changed:** https://github.com/henrydan111/quant-system/blob/report-rc-registration/workspace/research/cicc_replication/PGATE_IMPL_cross_review_response.md
- **Round-1 brief (original context):** https://github.com/henrydan111/quant-system/blob/report-rc-registration/workspace/research/cicc_replication/PGATE_IMPL_cross_review_brief.md
- **The hardening diff (review this):** https://github.com/henrydan111/quant-system/compare/800ebfd...6d0641a
- **Resolver + lattice + adjudicator:** https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/alpha_research/factor_registry/replication_governance.py
- **Gate wiring (`_cohort_ceiling`, `_load_cohort_manifests`, publish handler):** https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/research_orchestrator/factor_lifecycle_steps.py
- **Frozen manifest:** https://github.com/henrydan111/quant-system/blob/report-rc-registration/config/replication/cicc_fundamental_cohort_v1.yaml
- **Tests (65 pass):** https://github.com/henrydan111/quant-system/blob/report-rc-registration/tests/research_orchestrator/test_factor_lifecycle_steps.py · https://github.com/henrydan111/quant-system/blob/report-rc-registration/tests/alpha_research/test_replication_governance.py

## What was folded in (verify these close the findings)

- **F1** fail-CLOSED: an exception from `_cohort_ceiling` (which does all fallible work only AFTER confirming cohort membership) ⟹ refuse the factor; recorded in `refused_by_adjudication_error`.
- **F2** `_load_cohort_manifests` RAISES on any load/sha error (hard stop).
- **F4** short-OOS computed: `compute_oos_quarantine_start` + `truth_observed AND not power_floor_pass → short_oos_power_floor_fail` (`power_floor_pass` defaults False; manual flag is only an override); `oos_quarantine_start` persisted.
- **F6** `require_claim=True` for cohort → empty claim → `missing_domain_claim` (evidence_only).
- **F7** `required_operators` minus `CERTIFIED_BUILTIN_OPERATORS={add_composites}` → `has_uncertified_operator` → blocked.
- **F8** missing matrix evidence → `availability_audit_missing` (evidence_only); `coverage_pass` only when no availability cap.
- **F10** governance records persisted BEFORE status writes.
- **F3/F9 guards** >1 manifest match fails; non-univ_all `primary_claim_universe` fails closed.
- **F12** test pins the auto-evidence one-way-floor invariant.

Live proof: re-running the canary downgraded `comp_cicc_profit` `candidate_ceiling → evidence_only` (`availability_audit_missing`) — never 7-domain-evaluated, so not status-bearing.

Deferred (claimed to gate SCALE, not the current single-factor state): F3 `factor_master` cohort stamp · F5 mechanical composite lineage taint (claimed mitigated by F4+F8) · F9 full declared-domain adjudication · F11 append-only linkage ledger.

## New concerns to probe (the over-correction risks)

1. **Operational deadlock / matrix-evidence prerequisite.** With F8, EVERY cohort factor caps at `evidence_only` at the publish gate unless its 7-domain matrix evidence already exists in `factor_evidence` (auto rows). The canary proves this: `comp_cicc_profit` is stuck at `evidence_only` because the matrix was never run on it. **Is the matrix build ("入目录即全域体检") actually wired as a prerequisite of the lifecycle gate DAG, or is there now a gap where a cohort factor can NEVER reach candidate because nothing in the gate flow produces its matrix evidence first?** If the latter, F8 is correct in spirit but creates a deadlock until the matrix-build step is wired in — is that a new blocking gap?

2. **Is the fail-closed-on-exception assumption airtight?** F1 relies on: "`_cohort_ceiling` does all fallible work AFTER confirming cohort membership, so any exception ⟹ a cohort factor." Membership is `for m in manifests: m.row_for(catalog_factor_id=fid)`. Can `row_for` (or anything before the `return None`) throw for a NON-cohort factor and get it wrongly refused? Is there any path where a healthy non-cohort factor is refused?

3. **Non-univ_all: refuse vs adjudicate.** The F9 guard REFUSES a cohort factor whose `primary_claim_universe != univ_all` rather than adjudicating it on its declared domain. Manifest rows currently default univ_all, so nothing is blocked today. Is "refuse" the right interim, or does it risk silently blocking a legitimate non-univ_all CICC claim later (and note the matrix evidence IS keyed by universe, so per-domain adjudication is feasible — should F9-full be pulled forward)?

4. **Did fail-closed over-correct?** Today, effectively NO CICC cohort factor can promote to candidate (no matrix evidence at gate time → evidence_only; or truth-observed → candidate_ceiling at best). Is this the correct "nothing promotes until properly evaluated + a power-floor pass is computed" posture, or is it now so conservative that the gate is operationally a no-op for the whole cohort — i.e., have we swapped a fail-open hole for a fail-closed wall that hides the fact that the *evaluation pipeline feeding the gate* (matrix build + power-floor engine) is the real missing piece?

5. **Re-assess the deferral line.** Is "safe for the single-factor canary + field registration + offline P-OP, but NOT bulk publish-to-candidate" the right boundary? Are any of the 4 deferred items (esp. F5 lineage given F4+F8 now both cap, and F3 stamp) actually needed sooner than "at scale"? Is the F4+F8 mitigation of F5 sound, or can a composite still leak (e.g., a composite WITH matrix evidence + NO truth_label_end on its manifest row + a clean claim → reaches eligible_for_oos despite observed components)?

## Requested verdict

**APPROVE** / **APPROVE WITH CONDITIONS** / **CHANGES REQUIRED** + numbered findings (blocking/non-blocking + minimum change). Specifically: did the hardening close R1's 12 without regression, and is concern #1 (matrix-evidence prerequisite) or #5 (F5 leak path) a new blocker before the field-registration / P-OP work continues?
