# report_rc consensus + rating-aggregate materialization — DESIGN PLAN

> **Goal:** materialize analyst-CONSENSUS levels + RATING aggregates from the already-ingested+approved
> `report_rc` PIT ledger to unlock the 6 YELLOW deployed books (#8/#9 预期净利润; #16/#18 评级机构数;
> #5/#17 评级调高家数). Extends the existing `_materialize_report_rc_consensus` (which emits the 4
> eps_diffusion event-flow primitives) with LEVEL + RATING fields. NON-FORMAL parity GOAL, but the
> fields go through the FULL governance toll (materializer → in-place publish → field_status approved →
> GPT §10). Status: **DESIGN — self-review done, awaiting GPT §10 before implementation.**

## 0. The hard caveat (set expectations first)
**report_rc (Tushare 卖方研报 aggregation) is a DIFFERENT VENDOR than 果仁's 朝阳永续 (zyyx) consensus.**
The GREEN cluster reproduced 果仁 to penny-exact factors (same underlying statements); these YELLOW books
will be **APPROXIMATE** — a different analyst panel, different consensus method (median-of-recent vs zyyx's
proprietary weighting), different rating taxonomy. Expect LOWER selection overlap than the 40–48% GREEN
cluster. This is a *coverage/availability* reproduction (can we rank on a faithful-in-spirit consensus),
not a bit-parity one. Honest framing in every output.

## 1. Source data (report_rc, doc 292; raw data/analyst/report_rc/, ledger PIT-anchored)
Per-report rows: `org_name`, `author_name`, `quarter` (预测报告期 "YYYYQ4"=annual / "YYYYQ1..3"=quarterly),
`np` (预测净利润 万元, 98.2%), `op_rt` (预测营业收入 万元, 89.5%), `rd` (预测股息率, 29.7% sparse),
`rating` (卖方评级 str, 100%), `create_time` (★ PIT anchor). **PIT is ALREADY correct** — the ledger
`effective_date` anchors `max(report_date, create_time)` (gap≤45d) else `report_date + 2 open days`
(validated vs the JQ oracle, Spearman 0.94; memory `project_tushare_15000_expansion`). The materializer
reads `effective_date` only — no new PIT logic, no string-date compares.

## 2. New fields (`report_rc__` namespace; same as the eps_diffusion primitives)
| field | 果仁 indicator | definition (as-of trading day d, per stock) |
|---|---|---|
| `report_rc__np_fy1` | 预期净利润1年 | MEDIAN of `np` over orgs whose LATEST active (≤120 open-day TTL) forecast targets **FY1** (§3). 万元. |
| `report_rc__op_rt_fy1` | 预期营收1年 | MEDIAN of `op_rt` over the same FY1-active set. 万元. (unlocks #6's omitted term + #13.) |
| `report_rc__n_active_orgs` | 评级机构数 | # DISTINCT `org_name` with ≥1 active (≤120 TTL) rating as-of d. (org-level, not analyst-level.) |
| `report_rc__rating_up` | 评级调高家数 | # distinct orgs whose latest active rating ORDINAL > that org's IMMEDIATELY-PRIOR rating ordinal (an upgrade), counted while the upgrading report is within TTL. |
| `report_rc__rating_dn` | (symmetry/diag) | downgrades (same logic, <). Not a book input but cheap + needed to validate up is not double-counting. |

`np_fy1`/`op_rt_fy1`/`n_active_orgs` are **daily-carried levels** (ffill within TTL, NaN before first
coverage / after all stale). `rating_up`/`_dn` are **daily counts** of orgs currently-within-TTL of an
upgrade/downgrade event (carried like n_active, NOT event-sparse — 果仁's 评级调高家数 is a standing count).

## 3. FY1 forecast-period mapping (the crux; PIT-correct)
`quarter`="YYYYQ4" = the annual forecast for fiscal year YYYY. **FY1(d) = the smallest fiscal year Y such
that (a) ≥1 "YQ4" forecast is active as-of d AND (b) Y's ANNUAL report is NOT yet disclosed in the income
ledger as-of d.** Rationale: once Y's annual actual is public, "YQ4" stops being a forward estimate. The
"(b) not-yet-disclosed" test reuses the income ledger's annual `effective_date` (cross-ledger join, exactly
like `_materialize_forecast_growth`) — fully PIT (no lookahead; an annual disclosed AFTER d does not count).
- **Fallback** (stock has no income-annual history, e.g. very new listing): FY1 = max(year(d), min forecast
  year present) — degrades gracefully, logged.
- Only Q4 (annual) quarters feed FY1 levels. Quarterly forecasts ("YYYYQ1..3") are IGNORED for the annual
  consensus (a separate `__np_q_next` is DEFERRED — #14 净利润断层 needs it but is lower priority; record gap).

## 4. Rating ordinal normalization (~30 mixed CN/EN strings → 5-point scale)
Build a `RATING_ORDINAL` dict (module constant, fail-OPEN to NaN for unknown strings so a new label can't
silently miscount): 5=买入/强烈推荐/强推/strong buy/buy; 4=增持/推荐/谨慎推荐/跑赢行业/overweight/outperform/
add/accumulate; 3=中性/持有/neutral/hold/market perform; 2=减持/审慎/underweight/reduce; 1=卖出/sell/
underperform. **Upgrade** (per org) = latest ordinal > prior ordinal, both non-NaN. Unknown rating → NaN
ordinal → that org contributes to `n_active_orgs` (it has a rating) but is skipped from up/dn (no ordinal
to compare). Chronological sort (effective,disclosure,report,create_time) before the per-org shift(1),
mirroring the existing eps-revision event ordering (no same-day tie flip).

## 5. Materializer (extend the existing method; reuse ALL infra)
Add to `_materialize_report_rc_consensus` (or a sibling `_materialize_report_rc_aggregates` called from the
same hook) — reuse: ledger read + target-code filter, `normalize_date_series`, calendar-position map,
the 120-open-day TTL interval/union machinery (the `diff`/cumsum sweep), per-stock `_write_feature_series`,
`_apply_field_filter`. New work = the FY1 join + the org-level median/count + the rating-ordinal upgrade
detection. Fields written DIRECTLY in the `report_rc__` namespace (NOT via EVENT_LIKE_DAILY_FIELD_PREFIX),
exactly like the existing 4. Fail-closed if `quarter`/`rating`/`np` columns absent.

## 6. Build + publish + register
- **Publish: IN-PLACE additive** (the stability-factor precedent — purely additive new bins/dir, base
  provider `phasec_profit_dedt_sq_20260624` NOT rotated; `_publish_*_inplace.py` pattern). report_rc is a
  SUB-universe (analyst-covered ~2-3.5k stocks/yr, cap-tilted) → only covered dirs get the new bins.
- **Register**: append the 5 `report_rc__*` fields to the existing `report_rc` block in field_status.yaml
  (already `approved`) + approval YAML + log entry. ⚠ report_rc is an APPROVED family but eps_diffusion was
  REVOKED (restatement canary); these are LEVEL/COUNT fields (not the breadth/diffusion that triggered the
  revoke) — but I will mark them `approved` only after the materialize-parity check, and note the restatement
  caveat. Predictive use MUST `Ref(...,1)` + gate on non-null/recency (sub-universe, sparse).
- Coverage tier = `sub` (analyst-covered).

## 7. Validation (the parity leg)
Reproduce #16 (成长_隔夜动量@周期) / #17 (成长_高波@周期) / #18 (ST_大市值_v3) + #8/#9 (red-dividend) vs their
果仁 xlsx, reading the new fields via `D.features` (`Ref(...,1)`). **EXPECT approximate parity** (vendor diff):
report selection overlap + return, label the consensus as Tushare-approximate. A 评级机构数 sanity check vs
果仁's exported per-holding 评级机构数 value (果仁 各阶段持仓详单 exports factor values) — measures the
vendor gap directly at the holding level (the rung-4 method).

## 8. Self-review (CLAUDE.md §10 prerequisite) — verdict: CLEAN FOR GPT (design stage)
- **PIT / no-lookahead (FIRST):** materializer reads only the ledger `effective_date` (already create_time/+2
  anchored, JQ-validated); FY1's "annual-not-yet-disclosed" test uses the income ledger `effective_date`
  (as-of d, strict) — symmetric PIT, no future annual leaks in. No string-date compares. Consensus carried
  forward only (never backward). The factor layer MUST still `Ref(...,1)` (same-day report visible at d → use
  at d+1) — documented in the registry reason.
- **§3.2 f_ann_date / event-family:** report_rc is an event family anchored on create_time/report_date (no
  f_ann_date) — unchanged; I add no new anchor.
- **Materializer determinism:** median/count/upgrade are order-independent given the chronological pre-sort;
  reuse the proven TTL sweep. Fail-closed on missing columns.
- **Governance:** new fields registered before formal use; in-place additive publish doesn't rotate the base
  build (manifest stays honest re calendar/namespacing; field_status is the field gate). resolve-but-label.
- **Vendor-approximation HONESTLY framed** (§7 rule 10: no hedge — state it's Tushare-vendor-approximate, not
  果仁-penny-parity, and measure the gap).
- **Open risk (for GPT):** (a) the FY1 rolling-year convention vs 朝阳永续's exact 本年/明年 roll; (b) rating
  ordinal coverage of the long tail of strings; (c) restatement caveat inherited from report_rc (eps_diffusion
  revoke) — do LEVEL/COUNT consensus fields carry the same retroactive-restatement risk? (argued lower: a
  level median is less restatement-sensitive than a second-difference breadth, but GPT to confirm.)

## 9. Phasing
P0 data understanding (DONE: doc 292 read, schema/rating/quarter/coverage inspected, existing materializer
read). **P1 (THIS PLAN) → self-review → GPT §10 design review.** P2 implement materializer + canary tests →
GPT §10 post-impl. P3 in-place publish + register. P4 reproduce the 6 books (approximate-parity, labeled).
