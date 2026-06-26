# GPT §10 cross-review packet — report_rc consensus + rating-aggregate materializer (DESIGN, R2)

> **R1 = REVISE → all 7 findings folded (this is the R2 re-review).** Still design-stage (materializer not
> yet coded — the ALGORITHM is embedded for PIT review BEFORE implementation). Branch
> `report-rc-registration` pushed; the v2 (R1-folded) design doc is live. Paste the block below into GPT-5.5 Pro.

## R1 folds (verify each closed)
- **B1** prefix auto-approval → registry becomes EXPLICIT: existing `report_rc` block drops
  `field_prefixes`, lists the 4 eps_diffusion fields explicitly; the 5 new fields go in a SEPARATE
  **quarantine** block; + a test that `$report_rc__future_probe` is NOT formal-approved.
- **M1** restatement risk → all 5 quarantine-first; a field-level TWO-SNAPSHOT OUTPUT canary (re-materialize
  + diff) gates per-field promotion; rating_up/dn get breadth-family scrutiny.
- **M2** FY1 ambiguity → PINNED to `latest_disclosed_annual_fy(d)+1` (single def, repeated in field+YAML) +
  5 truth-table tests.
- **M3** raw org_name → `normalized_org_id` (NFKC+trim+collapse + trailing legal-suffix strip) for all
  org-level fields AND FY1 latest-per-org; + alias audit; + the per-org latest-change-state model (no
  upgraded-then-downgraded double-count).
- **M4** hidden TTL → dedicated `RATING_CHANGE_WINDOW_OPEN_DAYS=120` + pre-registered in the registry reason.
- **m1** latest-per-org missing value → latest row wins; missing metric → org excluded (no older-finite fallback).
- **m2** publish evidence → provenance JSON + approval YAML bound to live provider_build_id/calendar_policy_id + daily QA.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A lookahead, a spent OOS window, or a survivorship-filtered universe invalidates the result even if every test passes. This is a DESIGN re-review (R2): R1=REVISE was returned and all 7 findings are folded (above). Confirm each is genuinely closed, and judge the ALGORITHM's PIT-correctness + governance BEFORE implementation. Do not rubber-stamp.

REPO (public — fetch any file to verify against live code)
https://github.com/henrydan111/quant-system   (branch: report-rc-registration)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/<path>

CONTEXT
- CLAUDE.md (§3 invariants, PIT §3.2, formal-run governance §3.4 incl. field-status registry as the data gate, research integrity §7)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/CLAUDE.md
- config/field_registry/field_status.yaml — the report_rc block (currently field_prefixes: $report_rc__, ~line 365) that B1 converts to explicit
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/config/field_registry/field_status.yaml
- src/data_infra/pit_backend.py — NEW rating helpers (~line 175); existing _materialize_report_rc_consensus (TTL interval sweep + normalized_analyst_id ~line 770) and _materialize_forecast_growth (PIT-strict income _inc_asof, GPT-approved R1->R4) being mirrored
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/pit_backend.py
- src/data_infra/field_registry.py — the resolver (startswith prefix matching) that B1 addresses
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/field_registry.py
- v2 design spec (R1-folded; authoritative):
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/data_expansion/REPORT_RC_CONSENSUS_RATINGS_PLAN.md

SELF-REVIEW PREFLIGHT — verdict CLEAN FOR R2; all 7 R1 findings folded (above); checked §3 invariants + each quant principle. Reads only ledger effective_date (create_time/+2 anchored, JQ Spearman 0.94); FY1 income-disclosed test strict as-of d (mirrors _inc_asof); consensus carried forward only; factor adds Ref(,1). Residual for reviewer: (a) is a field-level re-materialize+diff OUTPUT canary the right restatement guard for LEVEL/COUNT fields; (b) is (latest-disclosed-annual)+1 an acceptable approximate FY1 vs 朝阳永续 (different vendor).

WHAT CHANGED (authoritative — embedded text is source of truth; links cross-check)

GOAL: materialize analyst-CONSENSUS levels + RATING aggregates from the already-APPROVED report_rc PIT ledger to reproduce the consensus/rating ranking factors of 6 user-DEPLOYED 果仁 books. report_rc = Tushare 卖方研报 (a DIFFERENT vendor than 果仁's 朝阳永续) -> APPROXIMATE-in-spirit, not bit-parity (labeled). Also reusable fields for future research.

HELPERS (committed, validated vs 793k rows): RATING_ORDINAL_CN/EN -> 5pt; RATING_NON_LABELS {无/blank} -> NaN ordinal + excluded from 评级机构数; normalize_rating_to_ordinal (unknown -> NaN, fail-OPEN); is_real_rating. NEW (M3): normalized_org_id(org) = re.sub(r"\s+"," ",NFKC(org).strip()) then strip trailing 证券股份有限公司/股份有限公司/有限责任公司/有限公司/(香港) so 中信证券股份有限公司 == 中信证券, 中信建投证券 stays distinct. NEW (M4): RATING_CHANGE_WINDOW_OPEN_DAYS=120 (distinct constant from the forecast TTL).

ALGORITHM _materialize_report_rc_aggregates(calendar, target_dirs) -> 5 report_rc__ fields. TTL=120 open days. Per covered stock:
(A) np_fy1 / op_rt_fy1 (万元): FY1(d) = latest_disclosed_annual_fy(d)+1, where latest_disclosed_annual_fy(d) = largest fiscal year Y whose ANNUAL income report (end_date=Y-12-31) has effective_date<=d (income ledger searchsorted side='right'-1; an annual disclosed AFTER d does NOT count). Fallback (no annual): FY1=calendar-year(d). Events = {annual (Q4) forecast effective positions} ∪ {income annual-disclosure positions (roll FY1)}. At event p: active = annual forecasts _fy==FY1(cal[p]) AND effective_pos in (p-TTL,p]; latest-per-normalized_org_id (chronological pre-sort -> last wins; if its np/op_rt missing, that org EXCLUDED for that metric -- m1, no older-finite fallback); fill [p,next_event) with median over orgs. No active FY1 forecast -> NaN (old-FY1 consensus STOPS at its annual disclosure, never carried across the roll). NaN before first computable; carried between events (果仁 snapshot, no daily decay).
(B) n_active_orgs (评级机构数): distinct normalized_org_id with a REAL rating (is_real_rating) active within TTL; per-org interval union, count distinct live/day; NaN before first real-rating coverage.
(C) rating_up / rating_dn (评级调高家数): per normalized_org_id, ordinal seq (unknown skipped); CHANGE = ordinal != prior finite ordinal; the org's CURRENT direction-state = its LATEST change, held RATING_CHANGE_WINDOW_OPEN_DAYS open days OR until its next change -> an upgraded-then-downgraded org counts ONLY in dn, never both. rating_up[d] = # orgs in up-state; BASELINE 0 during rating coverage (where n_active_orgs defined), NaN before first coverage.

All float32, report_rc__ namespace (direct, not EVENT_LIKE_DAILY_FIELD_PREFIX). PUBLISH in-place additive (no base-build rotation). REGISTER (B1, explicit): (1) convert the existing report_rc block field_prefixes -> explicit 4 eps_diffusion fields; (2) NEW report_rc_consensus block, status QUARANTINE, explicit 5 fields + pre-registered 120d window in the reason; (3) test $report_rc__future_probe NOT approved. EVIDENCE (m2): provenance JSON + approval YAML bound to live provider_build_id/calendar_policy_id + daily QA. PROMOTE (M1) per-field only after a field-level two-snapshot OUTPUT canary (re-materialize >=1wk later, diff per (code,date)) classifies drift acceptable; rating_up/dn breadth-scrutinized. Factor layer Ref(,1)+recency gate. VALIDATION: reproduce #16/#17/#18/#8/#9 (approximate, labeled) + holding-level 评级机构数 vs 果仁 export.

QUANTITATIVE-RESEARCH PRINCIPLES — check EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (cardinal): the FY1 income-disclosed test, active window (p-TTL,p], consensus carry, effective_date anchor.
2. OOS sacred (flag if registration could taint a future sealed test).
3. SURVIVORSHIP: analyst-covered sub-universe (cap-tilted) disclosed as coverage-bias, not survivorship-by-omission?
7. NO HEDGE: vendor-approximation stated as fact + measured?
8. FOUR-LAYER: fields Layer-1; book masks/ranks downstream.

REVIEW QUESTIONS (PIT FIRST — confirm the folds, then judge residuals)
1. B1 closed? Does converting field_prefixes -> explicit fields (4 existing approved + 5 new quarantine) + the future_probe test fully close the wildcard auto-approval, with no other report_rc__ prefix dependency elsewhere (materializer writes explicit names; resolver gates)?
2. M1 / restatement (the named top risk): is a field-level re-materialize+diff OUTPUT canary the correct guard for LEVEL (median np) + COUNT (n_active_orgs/rating_up) fields, given report_rc payloads re-date to best-known-state? Is quarantine-until-canary + per-field promotion sufficient, or do level/count fields need a different invariant than the breadth form?
3. M2 / PIT: is FY1=(latest-disclosed-annual)+1 lookahead-free (mirrors _inc_asof)? Do the 5 truth-table cases cover the failure modes (annual season, new listing, post-roll-no-forecast)?
4. M3: does normalized_org_id (suffix-strip) risk OVER-merging distinct brokers, and does the per-org latest-change-state correctly prevent double-counting? Granularity org vs analyst correct for 评级机构数/调高家数?
5. M4: is a dedicated pre-registered 120-open-day constant (vs encoding the window in the field name) acceptable against the multiple-testing concern?
6. m1/m2: latest-row-wins-exclude-if-missing correct? Provenance-JSON + bound-YAML + daily-QA the right evidence bar (matches the quality_stability in-place precedent)?
7. Any remaining correctness trap: Tushare(.) vs Qlib(_) codes (ledger is qlib_code), median/NaN propagation, float32 on ~1e5-1e6 万元 magnitudes, searchsorted side conventions, the FY1-roll boundary.

OUTPUT FORMAT
- Issues Blocker / Major / Minor, each mapped to the principle/invariant, with an exact fix.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
