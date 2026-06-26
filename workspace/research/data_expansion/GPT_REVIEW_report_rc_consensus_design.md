# GPT §10 cross-review packet — report_rc consensus + rating-aggregate materializer (DESIGN, R4)

> **R1 REVISE → R2 REVISE → R3 REVISE → all folded (this is R4).** Still design-stage (materializer not yet
> coded — the ALGORITHM is embedded for PIT review BEFORE implementation). Branch `report-rc-registration`
> pushed; the v4 (R1+R2+R3-folded) design doc is live. Convergence: R1 had 1 Blocker; R2/R3 had 0 Blocker
> and shrank to enforceability details. Paste the block below into GPT-5.5 Pro.

## R3 folds (verify each closed)
- **M1** TTL off-by-one → **PINNED option-b**: active iff `0 ≤ p − effective_pos ≤ TTL` (covers `e..e+TTL`,
  IDENTICAL to the existing `_materialize_report_rc_consensus` sweep `[p, min(p+ttl,n_cal−1)]`); expiry event
  `e+TTL+1`; boundary test (active at `e+TTL`, NaN at `e+TTL+1`).
- **M2** per-field status not representable by one block (`DatasetEntry` has ONE status for all fields) →
  register the 5 new fields as **5 SEPARATE single-field dataset entries** (each its own status), promoted/
  demoted independently; + a NO-DUPLICATE-FIELD test.
- **M3** date-restricted promotion not enforceable (`resolve_field` gates by field+stage, not date) →
  **REMOVED**; BINARY: any retroactive drift → stays quarantine; only 0-drift → promote.
- **M4** standing canary needs a fail-closed hook → the canary writes a result JSON BOUND to
  `provider_build_id`; `run_daily_qa.py` runs/verifies it; a missing/stale/failed canary makes the consensus
  fields resolve FAIL at `formal_validation` (mirrors `approval_evidence_binding`).
- **m1** doc metadata refreshed (v4). **m2** data_dictionary/data_tracker PIT updates land in P3 (before the P4 publish).

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A lookahead, a spent OOS window, or a survivorship-filtered universe invalidates the result even if every test passes. This is a DESIGN re-review (R4): R1=REVISE, R2=REVISE, R3=REVISE were returned; all findings are folded (above), now converged to enforceability. Confirm each is genuinely closed and rule whether this is SHIP-to-implement or still REVISE. Do not rubber-stamp; do not invent new scope.

REPO (public — fetch any file to verify against live code)
https://github.com/henrydan111/quant-system   (branch: report-rc-registration)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/<path>

CONTEXT
- CLAUDE.md (§3 invariants, PIT §3.2, formal-run governance §3.4 incl. field-status registry as the data gate, research integrity §7)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/CLAUDE.md
- config/field_registry/field_status.yaml — report_rc block (field_prefixes: $report_rc__ ~L365) that P2 converts to explicit + 5 single-field entries
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/config/field_registry/field_status.yaml
- src/data_infra/field_registry.py — DatasetEntry (one status per entry ~L82), resolver startswith + resolve_field by field+stage (~L89, L251)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/field_registry.py
- src/data_infra/pit_backend.py — NEW rating helpers (~L175); _materialize_report_rc_consensus (the [p,p+ttl] sweep, normalized_analyst_id ~L770) and _materialize_forecast_growth (PIT income _inc_asof, GPT-approved) being mirrored
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/pit_backend.py
- v4 design spec (R1+R2+R3-folded; authoritative):
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/data_expansion/REPORT_RC_CONSENSUS_RATINGS_PLAN.md

SELF-REVIEW PREFLIGHT — verdict CLEAN FOR R4; all R1+R2+R3 findings folded (above). Active window pinned to option-b (matches the existing sweep); expiry e+TTL+1; 5 single-field registry entries (per-field status); binary promotion (no date-restriction); canary fail-closed via run_daily_qa + provider_build_id binding; registry refactor is the first patch. Residual for reviewer: whether the build-bound STANDING output canary (re-materialize+diff; 0-retroactive-drift bar; rating_up/dn any-drift=fail; fail-closed at formal_validation) is now a SUFFICIENT + ENFORCEABLE restatement guard to APPROVE these level/count fields per-field, or whether some/all stay quarantine-only.

WHAT CHANGED (authoritative — embedded text is source of truth; links cross-check)

GOAL: materialize analyst-CONSENSUS levels + RATING aggregates from the already-APPROVED report_rc PIT ledger to reproduce the consensus/rating ranking factors of 6 user-DEPLOYED 果仁 books. report_rc = Tushare 卖方研报 (DIFFERENT vendor than 果仁's 朝阳永续) -> APPROXIMATE-in-spirit, labeled. Also reusable fields.

HELPERS (committed): RATING_ORDINAL_CN/EN -> 5pt; RATING_NON_LABELS {无/blank} -> NaN + excluded from 评级机构数; normalize_rating_to_ordinal (unknown -> NaN); is_real_rating. normalized_org_id(org) = re.sub(r"\s+"," ",NFKC(org).strip()) then strip trailing 证券股份有限公司/股份有限公司/有限责任公司/有限公司 (NOT (香港)). RATING_CHANGE_WINDOW_OPEN_DAYS=120.

ALGORITHM _materialize_report_rc_aggregates(calendar, target_dirs) -> 5 report_rc__ fields. TTL=120 open days; ACTIVE iff 0 <= p - effective_pos <= TTL (covers e..e+TTL, matching the existing sweep); EXPIRY event e+TTL+1. Per covered stock:
(A) np_fy1 / op_rt_fy1 (万元): FY1(d) = latest_disclosed_annual_fy(d)+1 (largest fiscal year Y whose ANNUAL income end_date=Y-12-31 has effective_date<=d; income searchsorted side='right'-1; future annual does NOT count). Fallback FY1=calendar-year(d). RECOMPUTE EVENTS = {annual (Q4) forecast effective pos} ∪ {income annual-roll pos} ∪ {per-forecast EXPIRY pos e+TTL+1}; carry only between. At event p: active = annual forecasts _fy==FY1(cal[p]) AND 0<=p-effective_pos<=TTL; latest-per-normalized_org_id (chronological; missing latest np/op_rt -> org excluded for that metric); fill [p,next_event) median over orgs; NaN if none (aged-out-no-event forecast -> NaN at its expiry). NaN before first; never across an annual roll.
(B) n_active_orgs (评级机构数): distinct normalized_org_id with a REAL rating (is_real_rating) active within TTL; per-org interval union; NaN before first coverage.
(C) rating_up / rating_dn (评级调高家数) STATE MACHINE: per normalized_org_id, chronological walk (state{UP/DN/NONE}, expiry, last_finite_ord); each report sets state for [pos, min(expiry, next-report pos)). finite o: first->NONE; o>last->UP exp=pos+window; o<last->DN exp=pos+window; o==last(reaffirm)->keep PRIOR state to ORIGINAL expiry; last=o. unknown-real-label-> NONE (clears up/dn), coverage=yes. no-rating(无)-> NONE (clears), not coverage. rating_up[d]=# orgs UP on d (baseline 0 during coverage, NaN before). Every later report (any kind) ends prior state -> no double-count.

PHASING (R3-M1): P2 FIRST = explicit-registry refactor BEFORE the materializer hook -- (1) existing report_rc block: drop $report_rc__ prefix, list the 4 eps_diffusion fields explicit-approved; (2) FIVE SEPARATE single-field QUARANTINE entries report_rc_np_fy1/_op_rt_fy1/_n_active_orgs/_rating_up/_rating_dn (R3-M2, per-field status); (3) tests: $report_rc__future_probe NOT approved + no-duplicate-field. P3 implement materializer + normalized_org_id + RATING_CHANGE_WINDOW_OPEN_DAYS + canary/truth-table/state-machine tests + data_dictionary/data_tracker doc updates (m2, before publish). P4 in-place additive publish + provenance JSON / approval YAMLs bound to live provider_build_id/calendar_policy_id + the STANDING output canary (R3-M4 fail-closed via run_daily_qa): BINARY promotion -- a field flips quarantine->approved ONLY on 0 retroactive drift over the snapshot window; ANY rating_up/dn drift = FAIL; a missing/stale/failed canary fails the consensus fields at formal_validation; re-runs on every report_rc mutation, demotes on new drift. P5 reproduce #16/#17/#18/#8/#9 (approximate, labeled) + holding-level 评级机构数 vs 果仁 export.

QUANTITATIVE-RESEARCH PRINCIPLES — check EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (cardinal): FY1 income-disclosed test, active window 0<=p-e<=TTL, expiry events, carry, effective_date anchor.
2. OOS sacred (flag if registration could taint a future sealed test).
3. SURVIVORSHIP: analyst-covered sub-universe disclosed as coverage-bias?
7. NO HEDGE: vendor-approximation stated + measured?
8. FOUR-LAYER: fields Layer-1; book masks/ranks downstream.

REVIEW QUESTIONS (confirm R3 folds, then rule SHIP vs REVISE)
1. M1 closed: is active `0<=p-e<=TTL` + expiry `e+TTL+1` internally consistent and matched to the existing sweep (no off-by-one at the expiry boundary)?
2. M2 closed: do 5 single-field DatasetEntry blocks + a no-duplicate-field test correctly give per-field promote/demote, given DatasetEntry's one-status-per-entry model?
3. M3 closed: is binary (0-drift -> promote, else quarantine) the right call vs the dropped date-restriction, and fully enforceable by the field+stage resolver?
4. M4 closed: is "canary result JSON bound to provider_build_id + run_daily_qa verify + fail-closed at formal_validation" a concrete, sufficient enforcement hook? Is there a remaining path to read an approved consensus field when the canary is stale/failed?
5. Residual: with all four enforced, is approving these vendor-approximate level/count fields (per-field, post-clean-canary) methodologically sound, or should rating_up/dn (change-state, breadth-adjacent) stay quarantine-only indefinitely?
6. Is this SHIP-to-implement, or is there a remaining Blocker/Major? Do not introduce new scope beyond closing the residual.

OUTPUT FORMAT
- Issues Blocker / Major / Minor, each mapped to the principle/invariant, with an exact fix.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
