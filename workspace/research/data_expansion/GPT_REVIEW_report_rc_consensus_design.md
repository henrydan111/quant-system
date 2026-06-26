# GPT §10 cross-review packet — report_rc consensus + rating-aggregate materializer (DESIGN, R3)

> **R1 REVISE → R2 REVISE → all folded (this is R3).** Still design-stage (materializer not yet coded — the
> ALGORITHM is embedded for PIT review BEFORE implementation). Branch `report-rc-registration` pushed; the
> v3 (R1+R2-folded) design doc is live. Paste the block below into GPT-5.5 Pro.

## R2 folds (verify each closed)
- **M1** registry fix ordered too late → **phasing reordered: the explicit-registry refactor is now the
  FIRST patch (P2)**, landing before the materializer hook (P3) — no path can write a new `$report_rc__*`
  bin while the prefix wildcard is approved.
- **M2** FY1 TTL silently expires between events → **TTL-EXPIRY events** (`effective_pos+TTL+1`) added to the
  recompute set; truth-table test (6) "valid at p, expires before next event → NaN".
- **M3** canary bar too discretionary → **pre-registered HARD pass/fail + STANDING canary**: any retroactive
  drift on a date ≤ snapshot-1 calendar end keeps the field quarantined/date-restricted; ANY rating_up/dn
  drift → FAIL; re-runs on every report_rc mutation, can DEMOTE a promoted field.
- **M4** unknown rating must clear state → **state machine redefined: every later org report supersedes** —
  finite-changed → up/dn; finite-unchanged → keep prior to ORIGINAL TTL; unknown-real → coverage-only +
  clears up/dn; no-rating → clears + not coverage. Tests: upgrade→{unknown,no-rating,downgrade,reaffirm}.
- **m1** stale docs → update data_dictionary.md + data_tracker.md (create_time/+2 anchor + new quarantine
  fields) in P3.
- **m2** org collision → drop `(香港)` from suffix-strip (keeps HK arm distinct) + pre-publish top-collision
  audit + denylist/alias map.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A lookahead, a spent OOS window, or a survivorship-filtered universe invalidates the result even if every test passes. This is a DESIGN re-review (R3): R1=REVISE then R2=REVISE were returned; all findings are folded (above). Confirm each is genuinely closed and the residual restatement risk is adequately governed, BEFORE implementation. Do not rubber-stamp.

REPO (public — fetch any file to verify against live code)
https://github.com/henrydan111/quant-system   (branch: report-rc-registration)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/<path>

CONTEXT
- CLAUDE.md (§3 invariants, PIT §3.2, formal-run governance §3.4 incl. field-status registry as the data gate, research integrity §7)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/CLAUDE.md
- config/field_registry/field_status.yaml — report_rc block (field_prefixes: $report_rc__ ~L365) that P2 converts to explicit
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/config/field_registry/field_status.yaml
- src/data_infra/field_registry.py — resolver startswith prefix matching (the gate P2 closes)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/field_registry.py
- src/data_infra/pit_backend.py — NEW rating helpers (~L175); _materialize_report_rc_consensus (TTL sweep, normalized_analyst_id ~L770) and _materialize_forecast_growth (PIT-strict income _inc_asof, GPT-approved R1->R4) being mirrored
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/pit_backend.py
- v3 design spec (R1+R2-folded; authoritative):
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/data_expansion/REPORT_RC_CONSENSUS_RATINGS_PLAN.md

SELF-REVIEW PREFLIGHT — verdict CLEAN FOR R3; all R1+R2 findings folded (above); checked §3 invariants + each quant principle. Reads only ledger effective_date (create_time/+2 anchored); FY1 income-disclosed test strict as-of d; consensus recomputed at forecast/roll/EXPIRY events, carried only between (never served stale); rating state cleared by every later report; registry refactor is the first patch; canary pre-registered+standing. Residual for reviewer: is the standing field-level output canary (re-materialize+diff, hard 0-retroactive-drift bar, rating_up/dn any-drift=fail) a SUFFICIENT restatement guard to APPROVE these LEVEL/COUNT fields, or do they stay quarantine indefinitely.

WHAT CHANGED (authoritative — embedded text is source of truth; links cross-check)

GOAL: materialize analyst-CONSENSUS levels + RATING aggregates from the already-APPROVED report_rc PIT ledger to reproduce the consensus/rating ranking factors of 6 user-DEPLOYED 果仁 books. report_rc = Tushare 卖方研报 (DIFFERENT vendor than 果仁's 朝阳永续) -> APPROXIMATE-in-spirit, labeled. Also reusable fields.

HELPERS (committed): RATING_ORDINAL_CN/EN -> 5pt; RATING_NON_LABELS {无/blank} -> NaN + excluded from 评级机构数; normalize_rating_to_ordinal (unknown -> NaN); is_real_rating. NEW (M3): normalized_org_id(org) = re.sub(r"\s+"," ",NFKC(org).strip()) then strip trailing 证券股份有限公司/股份有限公司/有限责任公司/有限公司 (NOT (香港)). NEW (M4-prior): RATING_CHANGE_WINDOW_OPEN_DAYS=120 (distinct from forecast TTL).

ALGORITHM _materialize_report_rc_aggregates(calendar, target_dirs) -> 5 report_rc__ fields. TTL=120 open days. Per covered stock:
(A) np_fy1 / op_rt_fy1 (万元): FY1(d) = latest_disclosed_annual_fy(d)+1 (largest fiscal year Y whose ANNUAL income report end_date=Y-12-31 has effective_date<=d; income ledger searchsorted side='right'-1; future annual does NOT count). Fallback FY1=calendar-year(d). RECOMPUTE EVENTS (M2) = {annual (Q4) forecast effective positions} ∪ {income annual-roll positions} ∪ {per-forecast TTL-EXPIRY positions effective_pos+TTL+1}; carry only between consecutive events. At event p: active = annual forecasts _fy==FY1(cal[p]) AND effective_pos in (p-TTL,p]; latest-per-normalized_org_id (chronological pre-sort; if latest np/op_rt missing -> org EXCLUDED for that metric, m1); fill [p,next_event) with median over orgs; NaN if none active (so an aged-out-with-no-event forecast drops at its expiry -> NaN). NaN before first computable; never carried across an annual roll.
(B) n_active_orgs (评级机构数): distinct normalized_org_id with a REAL rating (is_real_rating) active within TTL; per-org interval union; NaN before first real-rating coverage.
(C) rating_up / rating_dn (评级调高家数), STATE MACHINE (M4): per normalized_org_id, chronological walk with (state{UP/DN/NONE}, expiry, last_finite_ord); each report sets state for [its pos, min(expiry, next-report pos)). finite o: first->NONE(baseline); o>last->UP exp=pos+window; o<last->DN exp=pos+window; o==last(reaffirm)->keep PRIOR state to ORIGINAL expiry; then last=o. unknown-real-label-> NONE (clears up/dn), coverage=yes, last unchanged. no-rating(无)-> NONE (clears), not coverage. rating_up[d]=# orgs in UP on d (baseline 0 during coverage, NaN before). Every later report (ANY kind) ends the prior state -> no upgraded-then-{down/unknown/no-rating} double-count.

All float32, report_rc__ namespace (direct). PHASING (M1): P2 FIRST = explicit-registry refactor (drop $report_rc__ prefix; 4 eps_diffusion fields explicit-approved; 5 new explicit-QUARANTINE; $report_rc__future_probe NOT-approved test) BEFORE the materializer hook. P3 implement materializer+normalized_org_id+RATING_CHANGE_WINDOW_OPEN_DAYS+canary/truth-table/state-machine tests + data_dictionary/data_tracker doc updates (m1). P4 in-place additive publish + provenance JSON / approval YAML bound to live provider_build_id/calendar_policy_id + STANDING output canary (M1/M3): pre-registered HARD bar -- any retroactive drift on a date <= snapshot-1 calendar end keeps the field quarantined/date-restricted; ANY rating_up/dn drift = FAIL; only 0-retroactive-drift fields promote; re-runs on every report_rc mutation, can DEMOTE. P5 reproduce #16/#17/#18/#8/#9 (approximate, labeled) + holding-level 评级机构数 vs 果仁 export.

QUANTITATIVE-RESEARCH PRINCIPLES — check EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (cardinal): FY1 income-disclosed test, active window (p-TTL,p], expiry events, carry, effective_date anchor.
2. OOS sacred (flag if registration could taint a future sealed test).
3. SURVIVORSHIP: analyst-covered sub-universe disclosed as coverage-bias?
7. NO HEDGE: vendor-approximation stated + measured?
8. FOUR-LAYER: fields Layer-1; book masks/ranks downstream.

REVIEW QUESTIONS (confirm R2 folds, then the residual)
1. M1 closed: is the registry refactor as the FIRST patch (before the materializer hook) sufficient that no $report_rc__* bin can be written while the wildcard is approved? Any other write path (a different materializer, a manual build) that could create a bin pre-refactor?
2. M2 closed: do the TTL-EXPIRY events fully remove stale-serving, and is the (p-TTL,p] active window + expiry-event recompute internally consistent (no off-by-one at the expiry boundary)?
3. M3 closed (the NAMED top risk): is the pre-registered hard bar (0 retroactive drift over the snapshot window; ANY rating_up/dn drift=fail) + a STANDING canary a SUFFICIENT restatement guard to APPROVE level/count fields, or should they remain quarantine-only (research-usable, never formal)? Is "date-restricted to the drift-free tail" a sound partial-promotion, or over-engineering?
4. M4 closed: does the supersede-on-every-report state machine fully prevent stale direction state? Any sequence (e.g. unknown between two finite ratings) that mis-classifies?
5. Residual PIT/correctness: FY1=(latest-disclosed-annual)+1 lookahead-free? float32 on ~1e5-1e6 万元 medians; searchsorted side conventions; the no-double-count claim under reaffirm+expiry interaction.
6. Anything that should still BLOCK implementation, or is this SHIP-to-implement?

OUTPUT FORMAT
- Issues Blocker / Major / Minor, each mapped to the principle/invariant, with an exact fix.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
