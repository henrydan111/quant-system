# GPT 5.5 Pro RE-review #7 — Phase 5-B monthly_calendar_bump driver (post-REWORK-7)

Status: ready to send. Branch `calendar-unfreeze` HEAD `118cf1a`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You
have reviewed this monthly calendar freeze-bump DRIVER seven times; it has converged each round.
Round 6 (6483567) you confirmed B1-a (the chained completeness proof from the verified parent anchor)
and the earlier M1 (calendar-missing day + all-core-bin span) RESOLVED, and returned two items:
Blocker B1 (a legacy suspend_d file without suspend_timing still treated every S as full-day, which
can excuse an intraday-halted missing name) and Major M1 (cyq_perf checked only at target_end, not
per new day). Both fixed. This RE-REVIEW #7 verifies them.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 118cf1a)
Files (raw, pinned):
- driver:  https://raw.githubusercontent.com/henrydan111/quant-system/118cf1a/scripts/monthly_calendar_bump.py
- catchup: https://raw.githubusercontent.com/henrydan111/quant-system/118cf1a/workspace/scripts/catchup_daily_range.py
- tests:   https://raw.githubusercontent.com/henrydan111/quant-system/118cf1a/tests/data_infra/test_monthly_calendar_bump.py
Self-review (round 8): workspace/research/calendar_unfreeze/PHASE5B_SELF_REVIEW.md

CONTEXT: the FORMAL completeness gate (assert_endpoints_complete_range) runs post-catch-up and chains
the set-level daily continuity proof from the verified parent-end anchor through every new day. A name
that traded on the prior (verified) day must trade today unless delisted or FULL-DAY suspended.
fetch_suspend_d returns Tushare default fields (incl. suspend_timing); the daily updater's suspend_d
path historically dropped timing (some stored files lack the column).

HOW THE 2 ROUND-6 ITEMS WERE FIXED

B1 (legacy suspend_d without suspend_timing wrongly excused all S as full-day): FIXED, fail-CLOSED.
_suspended_full_day now:
  - requires columns {ts_code, trade_date, suspend_type}; verifies trade_date == date (empty file
    allowed — a day with no suspensions is legitimate);
  - if the file has NO suspend_timing column AND contains any S rows -> return ok=False
    ("has S rows but NO suspend_timing - cannot distinguish full-day from intraday; re-fetch"). An
    empty file (no S) passes with zero full-day suspensions;
  - if suspend_timing IS present -> full-day = S with empty/None timing (intraday halts do NOT
    excuse absence).
To keep the gate PASSABLE end-to-end, catchup_daily_range now writes suspend_d per-date DIRECTLY
(atomic overwrite) instead of via insert_market_data's merge: suspend_d(date) is a complete same-date
snapshot, so a re-fetch REPLACES it and PRESERVES suspend_timing (the merge would duplicate rows and
strip timing on a schema change). A bump's freshly-fetched gated days therefore carry clean timing;
a legacy no-timing day fails until the catch-up re-fetches it. LIVE: _suspended_full_day('20260702')
ok, timing_present=True, full_day=17; _suspended_full_day('20260703') (legacy, S, no timing) fails
closed. Test: legacy-no-timing-with-S -> fail.

M1 (cyq_perf checked only at target_end): FIXED. assert_endpoints_complete_range now proves cyq_perf
coverage for EVERY new day in (parent_end, target_end], immediately after that day's daily-fresh
coverage, vs that day's proven daily universe. An intermediate partial/missing cyq_perf day now fails
the gate. (target_end is the loop's last day, so the previous separate target-only cyq check is
removed — no double check.) LIVE: the range gate fails at the first new day (20260702) because
cyq_perf_20260702 is absent locally — the per-day check is active.

RE-REVIEW QUESTIONS
1. Is failing closed on a legacy suspend_d (S rows, no timing column) the correct posture, given the
   catch-up re-fetch restores timing? Is the empty-file-passes rule right (a day with genuinely no
   suspensions has an empty suspend_d and must not fail)?
2. Is the suspend_d overwrite (vs insert_market_data merge) in catchup_daily_range safe and correct?
   suspend_d(date) is treated as a complete same-date snapshot that a re-fetch fully replaces — any
   consumer that relied on the merge/accumulate behavior? (The event-driven suspension proxy /
   suspension_ranges builder read the historical suspend_d; this changes only the daily catch-up
   write path, atomic via os.replace.)
3. Is per-new-day cyq_perf coverage the right completeness contract, or is target_end-only actually
   sufficient given Stage-D backfills the whole gap and repartitions by trade_date (i.e., is a
   per-day partial even possible after a successful Stage-D run)?
4. Any NEW hole: the atomic overwrite dropping a column a downstream reader expects; the empty-file
   DataFrame schema; the fail-closed reason not being reachable when suspend_timing is present-but-
   all-null (treated as full-day — correct?); the per-day cyq check reading cyq_perf_<day>.parquet
   for every new day.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
