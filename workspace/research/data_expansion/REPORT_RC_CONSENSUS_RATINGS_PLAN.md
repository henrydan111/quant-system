# report_rc consensus + rating-aggregate materialization — DESIGN PLAN (v4, GPT R1+R2+R3-folded)

> **Goal:** materialize analyst-CONSENSUS levels + RATING aggregates from the already-ingested+approved
> `report_rc` PIT ledger to unlock the 6 YELLOW deployed books (#8/#9 预期净利润; #16/#18 评级机构数;
> #5/#17 评级调高家数). Extends the existing `_materialize_report_rc_consensus` (the 4 eps_diffusion
> event-flow primitives) with LEVEL + RATING fields. Fields go through the FULL governance toll. Status:
> **DESIGN — GPT §10 R1→R2→R3 = REVISE, all folded (below); awaiting R4.**

## GPT R3 REVISE → folds (2026-06-27) — 0 Blocker, 4 Major + 2 Minor (ENFORCEABILITY)
- **M1 (TTL window off-by-one):** doc had expiry `e+TTL+1` but the algorithm said active `(p-TTL,p]` (=
  expiry `e+TTL`). → **PINNED to option-b:** active iff `0 ≤ p − effective_pos ≤ TTL` (covers `e..e+TTL`,
  matching the EXISTING `_materialize_report_rc_consensus` sweep `[p, min(p+ttl, n_cal-1)]`); expiry event
  `e+TTL+1`. Boundary test: active at `e+TTL`, NaN at `e+TTL+1`.
- **M2 (per-field status not representable by one block):** `DatasetEntry` has ONE status for all `fields`.
  → register the 5 new fields as **5 SEPARATE single-field dataset entries** (each its own status), promoted/
  demoted independently; + a no-duplicate-field test (a field never in two blocks).
- **M3 (date-restricted promotion not enforceable):** `resolve_field()` gates by field+stage, NOT date. →
  **REMOVE date-restriction entirely.** BINARY: any retroactive drift → field stays quarantine; only
  0-retroactive-drift → promote.
- **M4 (standing canary needs a fail-closed hook):** → name the enforcement: the canary writes a result
  JSON BOUND to `provider_build_id`; **daily QA** runs/verifies it; if the canary is missing / stale (≠
  current build) / failed, the approved consensus fields **FAIL formal validation** (resolver/release-gate
  fail-closed), exactly like `approval_evidence_binding`.
- **m1 (stale doc metadata):** this header + §8 label updated to v4/R4. **m2:** the data_dictionary /
  data_tracker PIT updates land in **P3 (before the P4 publish)** — made explicit in §9.

## GPT R1 REVISE → folds (2026-06-26)
- **B1 (prefix auto-approval — the data gate is bypassed):** the existing `report_rc` block approves
  EVERY `$report_rc__*` via `field_prefixes: $report_rc__` (field_status.yaml:368; resolver `startswith`).
  → **FOLD:** §6 now (a) converts the existing block to EXPLICIT `fields:` (the 4 eps_diffusion primitives,
  no prefix), (b) registers the 5 new fields as a SEPARATE **quarantine** block (explicit `fields:`),
  (c) adds a registry test that `$report_rc__future_probe` is NOT formal-approved.
- **M1 (promote too fast vs restatement risk):** → register all 5 **quarantine** first; a TWO-SNAPSHOT
  OUTPUT canary on the MATERIALIZED bins (not raw rows / 果仁 parity); promote each field independently
  only after drift is classified acceptable. `rating_up/dn` (change-state) get breadth-family scrutiny.
- **M2 (FY1 had two definitions):** → **PINNED** to ONE: `FY1(d) = latest_disclosed_annual_fy(d) + 1`
  (§3); the field def + approval YAML repeat it verbatim; truth-table tests enumerated.
- **M3 (raw org_name too weak):** → add `normalized_org_id` (NFKC+trim+collapse + trailing legal-suffix
  strip) used for ALL org-level fields AND the FY1 latest-per-org consensus; + an alias audit.
- **M4 (rating TTL is a hidden modeling choice):** → dedicated constant `RATING_CHANGE_WINDOW_OPEN_DAYS`
  (NOT the reused forecast TTL) + the registry reason states it is a pre-registered 120-open-day window
  (any other window = a NEW field, never a post-hoc 30/60/90/120 comparison).
- **m1 (latest-per-org missing value):** → latest row per org wins; if its metric is missing, that org is
  EXCLUDED for that metric at that recompute (NO fallback to an older finite estimate). Tested.
- **m2 (in-place publish evidence):** → materialization provenance JSON (bins/counts/hashes/coverage) +
  approval YAML bound to live `provider_build_id`/`calendar_policy_id` + daily-QA evidence check.

## GPT R2 REVISE → folds (2026-06-27) — 0 Blocker, 4 Major + 2 Minor
- **M1 (registry fix ordered too late):** the LIVE registry still prefix-approves `$report_rc__*` NOW.
  → **phasing reordered (§9):** the explicit-registry refactor (drop prefix + 4 explicit approved + 5
  quarantine + future_probe test) is the **FIRST patch**, landing before/with the materializer hook — no
  build/publish path can create a new `$report_rc__*` bin while the wildcard is approved.
- **M2 (FY1 TTL silently expires between events):** the carry-forward served a forecast even after it aged
  past 120 open days with no intervening event. → **add TTL-EXPIRY events** (`effective_pos + TTL + 1` per
  forecast) to the recompute set; recompute at forecast / annual-roll / EXPIRY; truth-table test "valid at
  p, expires before the next event → NaN" (§3).
- **M3 (canary bar too discretionary):** "bounded drift → assess" is too soft. → **pre-registered HARD
  rules + STANDING canary** (§6/§7): any retroactive output drift on dates ≤ snapshot-1's calendar end →
  the field stays quarantined/date-restricted; ANY `rating_up/dn` drift → FAIL; the canary re-runs on every
  report_rc mutation and can DEMOTE a promoted field.
- **M4 (unknown rating must CLEAR direction state):** an old upgrade wrongly stayed "current" after a newer
  unmappable report. → **redefined state machine (§4):** every later org report supersedes — finite-changed
  → up/dn (TTL); finite-unchanged → keep prior change only to its ORIGINAL TTL; unknown-real-label →
  coverage only + CLEARS up/dn from that date; no-rating → clears + not coverage. Tests: upgrade→unknown,
  upgrade→no-rating, upgrade→downgrade.
- **m1 (stale docs):** update data_dictionary.md + data_tracker.md report_rc entries (create_time/+2 anchor
  + the new quarantine fields) before publish.
- **m2 (org collision):** drop `(香港)` from the suffix-strip (it distinguishes the HK research arm) + a
  top-collision audit (raw names per normalized id, counts, representative stocks) + a denylist/alias map.

## 0. The hard caveat (set expectations first)
**report_rc (Tushare 卖方研报 aggregation) is a DIFFERENT VENDOR than 果仁's 朝阳永续 (zyyx) consensus.**
These YELLOW reproductions will be **APPROXIMATE** (different analyst panel, consensus method, rating
taxonomy) — expect LOWER overlap than the 40–48% GREEN cluster. This is a *coverage/availability*
reproduction, not bit-parity. Stated honestly (§7.10 no-hedge) in every output, and measured at the
holding level vs 果仁's exported factor values. Dual value: the fields are also reusable for future research.

## 1. Source data (report_rc, doc 292; ledger PIT-anchored, ALREADY APPROVED 2026-06-09)
Per-report: `org_name`, `author_name`, `quarter` (预测报告期 "YYYYQ4"=annual / "YYYYQ1..3"=quarterly; 99.3%
annual), `np` (预测净利润 万元, 98.2%), `op_rt` (预测营业收入 万元, 89.5%), `rating` (卖方评级 str, 100%),
`create_time` (★ PIT anchor). **PIT is ALREADY correct + JQ-validated** — the ledger `effective_date`
anchors `max(report_date, create_time)` (gap≤45d) else `report_date + 2 open days` (Spearman 0.94 vs the
JQ oracle). The materializer reads `effective_date` only — NO new PIT logic, NO string-date compares, NO
re-anchoring.

## 2. New fields (`report_rc__` namespace; registered EXPLICITLY, quarantine-first)
| field | 果仁 | definition (as-of trading day d, per stock) |
|---|---|---|
| `report_rc__np_fy1` | 预期净利润1年 | MEDIAN over `normalized_org_id` of each org's LATEST active (≤120 open-day TTL) forecast `np` for **FY1** (§3). 万元. |
| `report_rc__op_rt_fy1` | 预期营收1年 | MEDIAN over orgs of the latest active forecast `op_rt` for FY1. 万元. |
| `report_rc__n_active_orgs` | 评级机构数 | # DISTINCT `normalized_org_id` with ≥1 active (≤120 TTL) REAL rating (`is_real_rating`). |
| `report_rc__rating_up` | 评级调高家数 | # distinct orgs whose CURRENT direction-state (latest rating-change within `RATING_CHANGE_WINDOW_OPEN_DAYS`) is an UPGRADE. |
| `report_rc__rating_dn` | (symmetry/diag) | downgrades (latest-change = down). |

`np_fy1`/`op_rt_fy1`/`n_active_orgs` = daily-carried levels (NaN before first coverage / no active set).
`rating_up`/`_dn` = daily counts, **baseline 0 during rating coverage** (where `n_active_orgs` is defined),
NaN before first coverage. New constant `RATING_CHANGE_WINDOW_OPEN_DAYS = 120` (distinct from the forecast
`REPORT_RC_ACTIVE_TTL_OPEN_DAYS`, even if equal — a pre-registered window, M4).

## 3. FY1 forecast-period mapping — PINNED (M2)
**`FY1(d) = latest_disclosed_annual_fy(d) + 1`**, where `latest_disclosed_annual_fy(d)` = the largest fiscal
year Y whose ANNUAL income report (`end_date = Y-12-31`) has `effective_date ≤ d` in the income ledger
(`searchsorted(side="right") − 1`; an annual disclosed AFTER d does NOT count — PIT-strict, mirrors the
GPT-approved `_materialize_forecast_growth._inc_asof`). Once Y's annual ACTUAL is public, "YQ4" stops being
a forward estimate, so FY1 rolls to Y+1. **Fallback** (no income annual ever disclosed — a new listing):
`FY1 = calendar-year(d)`, logged. Only annual (`quarter` ends "Q4") forecasts feed the FY1 levels;
quarterly forecasts ignored (#14 净利润断层's 预期净利润Q DEFERRED — only 0.7% of rows are quarterly).
**Latest-per-org missing-value rule (m1):** the org's LATEST active FY1 forecast wins; if that row's
`np`/`op_rt` is missing, the org is EXCLUDED from that metric's median at that recompute (no fallback to an
older finite row — a newer visible report supersedes).
**Active window + recompute events (M1/M2 — pinned, option-b):** a forecast at `effective_pos = e` is
active at `p` iff **`0 ≤ p − e ≤ TTL`** (covers `e..e+TTL`, identical to the existing
`_materialize_report_rc_consensus` interval sweep `[p, min(p+ttl, n_cal−1)]`); its expiry event is
`e + TTL + 1` (the first `p` with `p − e > TTL`). The consensus is recomputed at {annual-forecast effective
positions} ∪ {income annual-roll positions} ∪ **{per-forecast TTL-EXPIRY positions `e + TTL + 1`}**, and
carried only between consecutive events. So a forecast that ages past its window with NO intervening event
drops out of the active set at its expiry (the level recomputes from the remaining active forecasts, or →
NaN if none) — NEVER served stale. Boundary test: a lone forecast is active at `e+TTL`, NaN at `e+TTL+1`.
**Truth-table tests (M2):** (1) pre-annual-disclosure (FY1 = current year), (2) on the annual effective
date (roll), (3) post-roll with NO new FY1 forecast (NaN, not stale carry), (4) no income history
(fallback), (5) multiple active Q4 years present (pick FY1 only), (6) a single forecast valid at p with NO
forecast/income event before its expiry → the level goes NaN at `effective_pos + TTL + 1`.

## 4. Rating ordinal + org normalization (M3, M4)
`RATING_ORDINAL_CN/EN` → 5-pt (committed + validated, 93.4% of 793k rows); `RATING_NON_LABELS` (无/blank)
→ NaN ordinal AND excluded from `n_active_orgs`; unknown real label → NaN ordinal but counts toward coverage
(`is_real_rating`). **`normalized_org_id(org)`** (NEW, M3): `re.sub(r"\s+"," ",NFKC(org).strip())` then strip
trailing legal suffixes (证券股份有限公司 / 股份有限公司 / 有限责任公司 / 有限公司) — **NOT `(香港)`** (it
distinguishes the HK research arm; m2) — so "中信证券股份有限公司" ≡ "中信证券" but "中信建投证券" /
"中信证券(香港)" stay distinct. Used for `n_active_orgs`, `rating_up/dn`, AND the FY1 latest-per-org consensus.
**Pre-publish collision audit (m2):** top normalized-id collisions (raw names per id + row counts +
representative stocks) → a denylist/alias map for any over-merge.

**Rating direction-state machine (M4 — every later org report supersedes).** Per `normalized_org_id`, walk
reports chronologically with `(state∈{UP,DN,NONE}, expiry, last_finite_ord)`; each report sets the state for
`[its pos, min(expiry, next-report pos))`:
- **finite ordinal `o`**: first finite → NONE (sets baseline); `o > last_finite_ord` → UP, expiry=pos+window;
  `o < last_finite_ord` → DN, expiry=pos+window; `o == last_finite_ord` (reaffirm) → keep the PRIOR state to
  its ORIGINAL expiry (no extension); then `last_finite_ord = o`.
- **unknown real label** (NaN ordinal, `is_real_rating`): state → NONE (CLEARS up/dn from this date);
  coverage = yes; `last_finite_ord` unchanged.
- **explicit no-rating** (`无`/blank): state → NONE (clears); NOT coverage.
`rating_up[d]` = # distinct orgs in UP state on d (baseline 0 during coverage, NaN before); `rating_dn`
likewise. An org's state ALWAYS ends at its next report (ANY kind) or its expiry → an upgraded-then-
{downgraded / unknown / no-rating} org is never double-counted. Tests: upgrade→unknown (clears),
upgrade→no-rating (clears), upgrade→downgrade (flips to dn), upgrade→reaffirm (holds to original TTL).
Holding-level compare vs 果仁's exported 评级机构数.

## 5. Materializer `_materialize_report_rc_aggregates` (reuse ALL infra)
Reuse: ledger read + target-code filter, `normalize_date_series`, the calendar-position map, the
120-open-day TTL interval/union sweep (`diff`/cumsum), per-stock `_write_feature_series`,
`_apply_field_filter`; the income cross-ledger as-of (`searchsorted`) from `_materialize_forecast_growth`.
Fail-closed if `quarter`/`rating`/`np` columns absent. Fields written DIRECTLY in `report_rc__` (NOT via
EVENT_LIKE_DAILY_FIELD_PREFIX), like the existing 4. Called from the same materialize hook as
`_materialize_report_rc_consensus`.

## 6. Build + publish + register (B1, M1, m2)
- **Publish: IN-PLACE additive** (stability-factor precedent — new bins only, base provider
  `phasec_profit_dedt_sq_20260624` NOT rotated). report_rc sub-universe (~2-3.5k stocks/yr, cap-tilted).
- **Registry (B1 — explicit, NOT prefix):**
  1. Convert the existing `report_rc` block: drop `field_prefixes`, add explicit `fields:` =
     `$report_rc__eps_up` / `__eps_dn` / `__eps_revision_count` / `__n_active_analysts` (status unchanged
     = approved). This CLOSES the wildcard hole — an unlisted `$report_rc__*` is no longer auto-approved.
  2. **5 SEPARATE single-field dataset entries (R3-M2 — `DatasetEntry` carries ONE status for all its
     `fields`, so per-field promotion REQUIRES per-field ENTRIES):** `report_rc_np_fy1` /
     `report_rc_op_rt_fy1` / `report_rc_n_active_orgs` / `report_rc_rating_up` / `report_rc_rating_dn`, each
     status **quarantine**, explicit single `fields:`, the pre-registered 120d window + vendor caveat in
     each reason. Promoted/demoted INDEPENDENTLY by flipping that entry's status — a field is NEVER in two
     blocks.
  3. Registry tests: `resolve_field('$report_rc__future_probe','formal_validation')` is NOT approved (no
     prefix auto-approval survives); + a NO-DUPLICATE-FIELD test (no `$field` token appears in two dataset
     entries — guards the 5-entry split, R3-M2).
- **Evidence (m2):** materialization provenance JSON (bins added, per-field counts, byte-hash, coverage,
  `provider_build_id` binding) + each approval YAML bound to live `provider_build_id` + `calendar_policy_id`
  (daily-QA `approval_evidence_binding` checks it, like quality_stability).
- **Promotion (BINARY, R3-M3 — no date-restriction; `resolve_field` gates by field+stage, NOT date):** a
  field's entry flips quarantine→approved ONLY on **0 retroactive drift** over the §7 canary window; ANY
  drift → stays quarantine. Predictive use MUST `Ref(...,1)` + gate non-null/recency (sub-universe, sparse).

## 7. Validation (M1 output canary + the parity leg)
- **Field-level restatement canary (M1/M3/M4 — PRE-REGISTERED HARD RULES, STANDING + FAIL-CLOSED; the
  load-bearing gate):** snapshot the 5 materialized bins now; re-materialize from a fresh report_rc pull
  ≥1 week later; diff per (code, date) for retroactive drift (the `report_rc_backfill_canary` pattern, on
  the OUTPUT bins). **Pass/fail FIXED before snapshot-1 (no post-hoc "assess", NO date-restriction —
  R3-M3 dropped it as unenforceable by the field+stage resolver):** (a) ANY retroactive drift on a date ≤
  snapshot-1's provider-calendar end → that field STAYS quarantine; (b) ANY `rating_up`/`rating_dn` drift →
  FAIL (breadth-family rule); (c) promotable ONLY with 0 retroactive drift over the window. **Enforcement
  (R3-M4 — fail-closed hook):** the canary writes a result JSON BOUND to the live `provider_build_id`;
  `scripts/run_daily_qa.py` runs/verifies it; a MISSING / STALE (build-mismatched) / FAILED canary makes
  the consensus fields resolve as FAIL at `formal_validation` (a daily-QA + release-gate check mirroring
  `approval_evidence_binding`). **STANDING:** re-runs on every report_rc ledger/provider mutation and
  DEMOTES an already-promoted field on new drift. NO field promoted before the first clean run.
- **Parity leg (approximate, labeled):** reproduce #16/#17/#18/#8/#9 vs their 果仁 xlsx via `D.features`
  (`Ref(...,1)`); report selection overlap + return; holding-level 评级机构数 vs 果仁's exported value
  (rung-4 method) to measure the vendor gap directly.

## 8. Self-review (CLAUDE.md §10) — verdict: CLEAN FOR R4 (all R1+R2+R3 findings folded)
- **PIT / no-lookahead (FIRST):** reads ledger `effective_date` only (create_time/+2 anchored); the FY1
  income-disclosed test is strict as-of d (mirrors the GPT-approved `_inc_asof`); consensus carried
  forward only; factor layer adds `Ref(...,1)`. No string-date compares.
- **Governance:** B1 closes the prefix auto-approval; new fields quarantine-first behind a field-level
  output canary (M1); explicit registry + provenance binding (m2). resolve-but-label.
- **Determinism:** median/count/upgrade order-independent given the chronological pre-sort; org identity
  stabilized by `normalized_org_id` (M3); reuse the proven TTL sweep + income as-of.
- **No-hedge:** vendor-approximation stated as fact + measured (§7). Rating window pre-registered (M4).
- **Residual for R2:** is the field-level output canary (re-materialize + diff) the right restatement
  guard for LEVEL/COUNT fields; is `(latest-disclosed-annual)+1` an acceptable approximate FY1 vs 朝阳永续.

## 9. Phasing (M1 — registry refactor is the FIRST patch)
P0 understanding (DONE). **P1 design → R1 REVISE → R2 REVISE → FOLDED (this v3) → R3.**
**P2 (FIRST patch, M1) — explicit-registry refactor:** drop the `$report_rc__` prefix, list the 4
eps_diffusion fields as explicit-approved + the 5 new fields as explicit-**quarantine** + the
`$report_rc__future_probe` not-approved test. Closes the wildcard BEFORE any path can write a new bin.
**P3 — implement** `_materialize_report_rc_aggregates` + `normalized_org_id` + `RATING_CHANGE_WINDOW_OPEN_DAYS`
+ canary/truth-table/state-machine tests + the stale-doc updates (data_dictionary / data_tracker, m1) → GPT
post-impl. **P4 — in-place additive publish** + provenance JSON / bound approval YAML + the STANDING output
canary → per-field promote (ONLY 0-retroactive-drift fields). **P5 — reproduce** the 6 books (approximate,
labeled) + the holding-level 评级机构数 vs 果仁 export.
