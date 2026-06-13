# P-GATE implementation — Round 2 response & triage (GPT 5.5 Pro → folded in)

> 2026-06-14. GPT 5.5 Pro Round-2 verdict: **APPROVE WITH CONDITIONS** — "field-registration
> and offline P-OP work can continue; do NOT run the next live CICC publish-to-candidate wave
> until the conditions are met." Verdict accepted. The cheap, clearly-correct conditions are
> **folded in now** (they close real residual holes without the heavy matrix producer); the
> remaining "before live publish" conditions are deferred with rationale (live publish is
> paused, so they gate the next wave, not the current field-registration / P-OP work).

## Triage of the 9 findings + 6 conditions

| Finding / Cond | Verdict | Action |
|---|---|---|
| **2 / Cond-1b** stale matrix evidence can satisfy F8 | **DONE** | `_cohort_ceiling` now counts matrix evidence as coverage ONLY when its `source_hash == current definition_hash`; unknown current hash or no matching fresh row → `coverage_observed=False` → `availability_audit_missing`. A changed-expression factor can no longer ride a stale auto row. |
| **4 / Cond-3** row truth window should fall back to cohort window | **DONE** | `truth_label_end = row.truth_table_label_end or manifest.handbook_label_window_end`. A lazily-enumerated row that omits the date can no longer escape the short-OOS cap. |
| **3 / Cond-4** composite lineage leakable | **DONE (F5-lite)** | A composite inherits `truth_observed` from any truth-observed component (`_composite_components` × manifest rows). Closes the "composite row omits truth + components observed → looks clean" leak. Full §3.1c lineage taint still deferred, but the leak path is closed. |
| **5 / Cond-2** active-claim cardinality not enforced | **DONE** | `_cohort_ceiling` raises on >1 active claim for the universe (fail-closed); uses `iloc[0]` only after the uniqueness check. 0 claims → `missing_domain_claim` (unchanged). |
| **9 (persist) / Cond-6b** quarantine-approx flag discarded | **DONE** | `_cohort_ceiling` returns `oos_quarantine_approximate`; the publish handler persists it on the `ReplicationGovernanceRecord`. |
| **4 (minimum change)** distinguish missing-prerequisite vs governance-cap | **DONE** | publish outputs now split `refused_by_missing_prerequisite` (has `availability_audit_missing`) vs `refused_by_true_governance_cap` — the operator can tell "the evidence producer never ran" from "real governance failure". |
| **1 / Cond-1** 7-domain matrix PRODUCER not a DAG prerequisite | **DEFERRED (the headline live-publish blocker)** | F8 correctly demands matrix evidence; the lifecycle DAG does not yet produce it pre-publish. Wiring a `factor_lifecycle_auto_matrix_7domain` step (or an explicit `matrix_prerequisite_missing` refuse + a generate-command) is the main condition before the next live publish. GPT: **not** a blocker for field-registration / P-OP. |
| **6 / Cond-5** manifest hard-stop over-blocks non-CICC runs | **DEFERRED (non-blocking)** | Current global hard-stop is safe (over-blocks, never lets through). A `require_replication_governance` run/profile flag to scope it is a refinement; recorded. |
| **8** no governance record for adjudication-error refusals | **DEFERRED (non-blocking)** | The error is surfaced in `refused_by_adjudication_error` + logged; the factor is refused (not promoted). A durable audit row is a nicety; recorded. |
| **9 (enforce)** require `approximate=False` before sealed OOS | **DEFERRED (future OOS gate)** | The flag is now persisted; enforcing `approximate=False` (or recomputing with an injected trade calendar) belongs at the sealed-OOS handler, not the candidate gate. Recorded. |
| **F3 stamp / F9-full / F11 ledger** (from R1) | **STILL DEFERRED** | Unchanged from R1 — gate scale / non-univ_all / reporting, not the current state. |

## Round-1 fix verification (GPT's table, confirmed)

F1 closed (cohort) · F2 closed · F3 partial (ok for single canary) · **F4 now closed** (cohort fallback added) · **F5 leak closed via F5-lite** · **F6 now fully closed** (multi-claim enforced) · F7 closed · F8 closed (+ freshness) · F9 safe interim · F10 closed · F11 deferred · F12 closed.

## Tests

`test_factor_lifecycle_steps` + `test_replication_governance` = **68 pass** (+3 new `_cohort_ceiling` unit tests: stale-evidence-ignored, multi-claim-fail-closed, composite-inherits-component-truth; + the prerequisite-split assertion). Canary re-verified: `comp_cicc_profit` still `evidence_only` (`availability_audit_missing`) — no matrix evidence.

## The one condition before the next live CICC publish-to-candidate wave

**Wire the 7-domain matrix producer as a gate prerequisite + require evidence freshness** (Finding 1 / Cond-1). Everything else GPT raised is either folded in or deferred-non-blocking. Field registration (D4a) and offline P-OP can proceed now.
