# P-GATE implementation cross-review — response & triage (GPT 5.5 Pro → hardened)

> 2026-06-14. GPT 5.5 Pro verdict: **CHANGES REQUIRED** (10 blocking + 2 non-blocking),
> "do not run a live CICC cohort publish-to-candidate sub-wave yet; the gate is too
> fail-open." Verdict ACCEPTED in full — the findings are mechanical and correct. This
> records the triage. The fail-closed core is **folded in now**; four heavier items are
> deferred with rationale (none blocks *now* — nothing is promoted to candidate, and the
> conservative fail-states are the safety net; they block the *next live sub-wave at scale*).

## Triage

| # | Finding | Verdict | Action |
|---|---|---|---|
| 1 | Fail-open on the protected path (exception → promote as non-cohort) | **ACCEPT — DONE** | `_cohort_ceiling` does all fallible work AFTER confirming cohort membership, so an exception ⟹ a cohort factor → **refuse** it; recorded in `refused_by_adjudication_error`. Never falls back to non-cohort promotion. |
| 2 | Malformed manifest skipped → all cohort look non-cohort | **ACCEPT — DONE** | `_load_cohort_manifests` now **raises** on any load error (sha mismatch = hard governance stop), halting the publish step rather than silently continuing. |
| 3 | Cohort membership via `catalog_factor_id` only; unlinked rows fail open | **ACCEPT — PARTIAL** | DONE: >1 manifest match → fail-closed (ambiguous). DEFERRED: the `factor_master` reverse-stamp (`replication_cohort_id`/`handbook_id`) so a factor *claiming* CICC metadata but resolving to ≠1 row fails closed — required before D4a/D-COMP registration **at scale** (a single forgotten link is the risk). |
| 4 | short-OOS is a manual manifest flag, not computed | **ACCEPT — DONE** | `_cohort_ceiling` computes `oos_quarantine_start` via `compute_oos_quarantine_start(truth_label_end, system_oos_start)`; `resolve_replication_ceiling` caps `short_oos_power_floor_fail` whenever `truth_observed AND not power_floor_pass` (default False until the power-floor engine exists — fail-safe). The manual `oos_eligibility` flag remains only as an additional override. `oos_quarantine_start` now persisted. |
| 5 | Composite lineage taint not inherited | **ACCEPT — DEFERRED (mitigated)** | Mechanical §3.1c component-taint inheritance deferred (before MORE composites). **Mitigation now in place**: F4 (truth_observed) + F8 (missing matrix evidence) both independently cap a composite of observed components — the canary `comp_cicc_profit` now lands at `evidence_only`, so the "clean composite reaches eligible_for_oos" leak GPT described is already blocked by two other caps even without lineage taint. |
| 6 | Missing active claim still allows promotion | **ACCEPT — DONE** | `require_claim=True` for cohort factors → empty `claim_class` adds `missing_domain_claim` (evidence_only cap). No cohort factor promotes without exactly one active claim for the adjudicated universe. |
| 7 | `required_operators` not wired to the operator block | **ACCEPT — DONE** | `CERTIFIED_BUILTIN_OPERATORS = {add_composites}` whitelist; `_cohort_ceiling` sets `has_uncertified_operator = bool(required_ops - whitelist)`. "No cert store yet" never means certified. |
| 8 | Missing matrix evidence behaves like coverage pass | **ACCEPT — DONE** | `coverage_observed=False` → `availability_audit_missing` (evidence_only cap); `coverage_pass` is only acquired when no availability cap fires. Auto-evidence may lower the ceiling; its **absence** never passes. |
| 9 | Declared domain ignored (univ_all-only gate) | **ACCEPT — PARTIAL** | DONE: a manifest `primary_claim_universe != univ_all` → fail-closed refuse (the univ_all-only gate cannot adjudicate it). DEFERRED: full per-factor declared-domain adjudication (derive target universe from the claim) — required before any non-univ_all CICC claim. |
| 10 | Governance persistence happens AFTER status writes | **ACCEPT — DONE** | Reordered: all cohort `ReplicationGovernanceRecord`s are upserted BEFORE `record_lifecycle_evidence` + `set_status`. A governance-store failure raises before any status write. |
| 11 | `catalog_factor_id` excluded from sha needs a linkage ledger | **ACCEPT — DEFERRED (non-blocking)** | The sha-exclusion is sound (operational linkage ≠ frozen science). The append-only `cohort_factor_linkage` ledger + `definition_hash` binding is recorded as required before reporting / scale. |
| 12 | Document the auto-evidence one-way-floor invariant in tests | **ACCEPT — DONE** | `test_auto_evidence_is_a_one_way_floor`: missing required evidence yields a ceiling ≤ the observed-evidence ceiling and never a pass. |

## What changed (code)

- [replication_governance.py](../../../src/alpha_research/factor_registry/replication_governance.py): new caps `missing_domain_claim` + `availability_audit_missing` (evidence_only); `CERTIFIED_BUILTIN_OPERATORS`; `resolve_replication_ceiling` gains `truth_observed` / `coverage_observed` / `require_claim` (back-compat defaults) and the mechanical short-OOS / missing-claim / missing-evidence caps; `coverage_pass` gated on no availability cap.
- [factor_lifecycle_steps.py](../../../src/research_orchestrator/factor_lifecycle_steps.py): `_load_cohort_manifests` raises on load error (F2); `_cohort_ceiling` computes the OOS quarantine, wires `required_operators`, fails closed on >1 match / non-univ_all (F3/F9 guards); the publish handler refuses on adjudication error (F1), persists governance BEFORE status (F10), and reports `refused_by_ceiling` / `refused_by_adjudication_error` separately.
- Tests: 65 pass (`test_replication_governance` 45 + `test_factor_lifecycle_steps` 20), incl. every new fail-closed path.
- **Live demonstration**: re-running the canary under the hardened logic downgraded `comp_cicc_profit` from `candidate_ceiling` → **`evidence_only`** (`availability_audit_missing`) — it has never been 7-domain-evaluated, so it is correctly not status-bearing. The exact F8 hole GPT flagged, closed and shown.

## Deferred (required before the next live CICC publish-to-candidate sub-wave at scale)

1. **F3 stamp** — `factor_master.replication_cohort_id`/`handbook_id` reverse linkage + "claims CICC metadata but ≠1 manifest row → fail closed".
2. **F5 mechanical lineage taint** — record component `lineage`/`component_selection` taints before composite claim registration (currently mitigated by F4+F8).
3. **F9 full** — per-factor declared-domain adjudication (non-univ_all claims currently blocked, not adjudicated).
4. **F11 linkage ledger** — append-only `cohort_factor_linkage` with `definition_hash` binding.

Per GPT: with the DONE set, the gate is no longer fail-open; the deferred items gate *scale*, not the current state (nothing promoted to candidate; a fresh CICC factor with no evidence now correctly caps at `evidence_only`).
