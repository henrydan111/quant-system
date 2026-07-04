# GPT 5.5 Pro re-review prompt — Phase 5 design v2 (Round 2)

Status: ready to send AFTER `git push` of branch `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is ROUND 2 (re-review) of the Phase-5 steady-state update mechanism design. In Round 1 you returned REVISE with 1 Blocker (B1: report_rc monthly catch-up not fail-closed for late create_time rows — a recovered post-2026-02-27 row could be anchored at report_date+lag EARLIER than its create_time = lookahead), 3 Major (M1 target_end readiness must be mandatory for formal publish; M2 frozen-prefix audit insufficient for fresh-window survivorship; M3 approved-exceptions can become drift laundering) and 1 Minor (m1 rebuild-cost thresholds). You fetched the live repo AND the Tushare API docs. All 5 findings were ACCEPTED (none declined) and you RULED the central Q2 decision (freeze spent_oos_end across bumps) correct and safe. Your job now: verify each finding is adequately folded, and check whether the revision introduced new problems. Do not re-litigate what you already approved (esp. Q2).

REPO (public — raw fetch worked for you last round; embedded deltas are authoritative if it fails)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Design v2: workspace/research/calendar_unfreeze/PHASE5_DESIGN.md (§10 = R1 disposition table)
Self-review incl. Round-2 preflight: workspace/research/calendar_unfreeze/PHASE5_SELF_REVIEW.md
The report_rc anchor code you cited: src/data_infra/pit_backend.py (REPORT_RC_BACKFILL_GAP_DAYS=45 at ~L286; the contemporaneous/backfill split + the "clean-era large gap anchored earlier than create_time" WARNING at ~L2461-2486)

SELF-REVIEW PREFLIGHT (Round 2) — verdict "clean". I independently verified B1 against pit_backend.py:2461-2486 (not rubber-stamping you): the gap<=45d contemporaneous rule anchors larger-gap rows at report_date+2, and the code itself only WARNs that a clean-era large-gap row is anchored earlier than create_time — confirmed a real fresh-window lookahead in a monthly regime. All 5 fixes fold your exact replacement text. I flag one implementation risk for you: the B1 report_rc anchor change touches the load-bearing §3 statement-family PIT logic, but only TIGHTENS it (fresh-window rows never anchored earlier than visibility; the historical 2022-05 bulk-backfill stamp on 2010-2021 reports is untouched since those report_dates < fresh_holdout_start).

WHAT CHANGED (authoritative — the complete R1-fix delta)

--- Delta 1 · §5.1 step 3 report_rc (B1) ---
report_rc REMOVED from the generic "create_time increment + overlap" catch-up. New rule:
- fetched by report_date REPLAY (create_time is an OUTPUT visibility field, not a server-side cursor); each bump replays all report_date in [fresh_holdout_start, target_end] + a documented overlap window; stores vendor_create_time / raw_fetch_ts / ingest batch id / provider as_of_cutoff.
- for report_date >= fresh_holdout_start the bulk-backfill fallback is DISABLED: create_time present -> disclosure = max(report_date, create_time); create_time missing -> quarantine or disclosure = raw_fetch_ts; NEVER report_date + lag. Any post-2026-02-27 row that current code would anchor earlier than create_time = build-BLOCKING PIT error, not a warning.
- the bump must FAIL if replay finds a post-2026-02-27 row with effective_date <= target_end that was absent from the previous eligible bump's raw snapshot, unless added with effective no earlier than its create_time/raw_fetch_ts.
- if the replay rule is not implemented, report_rc moves to a daily post-22:00 CST job with the same fail-closed anchor rule.
cyq_perf explicitly RULED (your Q3) to stay monthly: per-symbol trade_date factual dataset, PIT-equivalent if the bump probes readiness + fetches full symbol/date range to target_end + coverage check + no publish before endpoint complete.

--- Delta 2 · §4.1 + §5.1 step 2 (M1) ---
Daily readiness stays loose (idempotent, no publish, retry). FORMAL bump target_end requires a mandatory endpoint-readiness contract: trade_cal is_open==1; post-vendor-update clock per required endpoint family; non-empty daily for D; expected/stable-count for market-wide daily endpoints; per-symbol/expected-coverage for cyq_perf; report_rc past its update window OR excluded from same-day completeness. Any probe fails -> target_end rolls back to the most recent all-green open day. Clock+calendar may schedule raw ingest but may NOT authorize a formal target_end.

--- Delta 3 · §5.1 step 6 split into two audits (M2) ---
(a) frozen-prefix audit (unchanged: bin byte-identity + calendar append-only + sidecar membership matrix, set discovered from tree) — protects pre-2026-02-27 replay.
(b) NEW fresh-window universe audit for [fresh_holdout_start, target_end]: fail the bump unless every symbol with any price row in raw daily is represented in the provider feature tree AND in all_stocks on all eligible trading days between list/delist bounds; separately audit stock_basic L/D/pause + namechange + stock_st_daily + suspend_d + index-weight sidecars vs regenerated instruments. Completeness + no-survivorship gate, NO blanket exceptions.

--- Delta 4 · §5.1 step 6 approved-exceptions (M3) ---
Exceptions are append-only, per-bump, TYPED records: exception id, root cause, dataset/field, symbol set, date range, gross diff, net diff, reviewer, expiry condition, evidence path. Dry-run report shows gross drift AND exception-adjusted drift AND cumulative trend by type. Same exception type recurring for two consecutive bumps -> permanent migration note + tests OR blocker; never silently re-approved by count. No wildcard date ranges, no "all symbols," no reuse without a new diff hash. (Frozen-prefix audit only; the fresh-window audit has no exceptions.)

--- Delta 5 · §6 (your Q2 ruling folded) + §8 (m1) ---
§6: spent_oos_end freeze RULED correct+safe; the "data present but unusable" tension is operational friction, not a validity defect; any future release of aged fresh data must be a SPEND EVENT (a "research-window release seal" that stamps a new policy, records the released slice, advances spent_oos_end for that policy, binds the consuming book lineage, reserves a later untouched holdout) — NOT automatic age-based release. This mechanism is Phase 6, not Phase 5.
§8 m1: monthly full rebuild stays default; instrument every bump (upstream/materialization/audit time, peak disk, file count, retry count); open the true-append materializer project ONLY after two consecutive bumps breach the maintenance window or disk headroom, or the provider cannot be rebuilt+audited before the next scheduled publication.

RE-REVIEW QUESTIONS (Round 2)
1. B1: does the report_date-replay + fresh-window-no-backfill + max(report_date,create_time) + quarantine-if-missing + block-if-would-anchor-earlier rule fully close the late-arrival lookahead? Any residual (e.g. a row whose create_time itself is unreliable, or the overlap window sizing)?
2. M1/M2/M3: adequately folded? Is the fresh-window universe audit (M2) the right completeness gate, or does it need the delisting/IPO-lag contract explicitly (the all_stocks sidecar's list/delist bounds)?
3. New-issue scan on the deltas only — especially: does the B1 anchor change risk breaking the HISTORICAL report_rc behavior (2022-05 bulk-backfill on 2010-2021 reports), or is the fresh_holdout_start boundary a clean separator? Does moving report_rc to daily (the fallback) create a NEW build_id-rotation problem (it's a raw-layer fetch, so it should not — confirm)?
4. Is v2 ready to implement (SHIP), or what remains?

OUTPUT FORMAT
- Per finding (B1, M1, M2, M3, m1): RESOLVED / PARTIALLY RESOLVED / NOT RESOLVED with the exact remaining gap.
- New issues ranked Blocker / Major / Minor with offending text quoted + exact replacement.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
