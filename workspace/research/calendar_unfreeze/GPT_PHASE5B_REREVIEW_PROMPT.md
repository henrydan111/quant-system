# GPT 5.5 Pro RE-review #6 — Phase 5-B monthly_calendar_bump driver (post-REWORK-6)

Status: ready to send. Branch `calendar-unfreeze` HEAD `6483567`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You
have reviewed this monthly calendar freeze-bump DRIVER six times; it has converged each round. Round
5 (29f5cba) you confirmed M1, the stale-file guard, and the endpoint split RESOLVED, and returned
Blocker B1 with two sub-holes: B1-a (the continuity proof anchored on an UNVERIFIED prior daily, and
only target_end was proven) and B1-b (suspend_d not trade_date-verified; every S treated as full-day
though intraday halts still trade). Both fixed. This RE-REVIEW #6 verifies them.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 6483567)
Files (raw, pinned):
- driver: https://raw.githubusercontent.com/henrydan111/quant-system/6483567/scripts/monthly_calendar_bump.py
- tests:  https://raw.githubusercontent.com/henrydan111/quant-system/6483567/tests/data_infra/test_monthly_calendar_bump.py
Self-review (round 7): workspace/research/calendar_unfreeze/PHASE5B_SELF_REVIEW.md

CONTEXT: split gate — daily/moneyflow/stk_limit gate target_end PRE-catch-up (cheap: trade_date +
rolling baseline + coverage); the FORMAL completeness gate runs POST-catch-up before policy minting.
stock_basic has list_date/delist_date (YYYYMMDD str). suspend_d per-date files: (ts_code, trade_date,
suspend_type in {S,R}[, suspend_timing]). fetch_suspend_d returns Tushare default fields (incl.
suspend_timing) and insert_market_data stores all columns, so a freshly-fetched day carries timing
(confirmed live: 20260702 has it; 20260703 — an older fetch — does not).

HOW THE 2 ROUND-5 SUB-HOLES WERE FIXED

B1-a (unverified anchor; only target_end proven): FIXED with assert_endpoints_complete_range(
parent_end, target_end). It CHAINS the proof from a VERIFIED anchor forward through EVERY new day:
  - anchor = parent_end (the settled published parent's calendar_end). Required date_ok + above
    floor before chaining (a minimal anchor sanity — the published parent is the trusted baseline).
  - for each new trading day d in (parent_end, target_end], in order:
      _daily_universe(d)  (trade_date == d + rolling-baseline partial detector)
      _daily_set_continuity_from_prior(d, prior_date, PRIOR_VERIFIED_CODES, daily_codes, sb)
      _coverage_gate(d, daily-fresh)
    then prior := d's daily_codes (the next day chains from THIS just-proven day — never an
    unverified read). There is no skipped_prior_unverified->True path.
  - cyq_perf coverage at target_end (Stage-D backfills the whole gap to target).
This closes the inherited-missing-set hole (a persistently-missing name is caught the first day it
diverges from the verified chain) and the only-target_end hole. LIVE: chain(20260701 -> 20260702,
20260703): both new days continuity missing 0 / unexpected 0 (zero false positives on real complete
sessions); cyq_perf correctly blocks at target (absent).

B1-b (suspend_d not date-verified; all S = full-day): FIXED in _suspended_full_day(date):
  - verify trade_date == date (a stale/mispartitioned suspend_d cannot excuse a missing code).
  - only FULL-DAY suspensions excuse an absent daily row: suspend_type == 'S' AND suspend_timing
    is empty/None. An INTRADAY halt (timing like '09:30-10:00') still trades, so it must NOT excuse
    absence.
  - when the stored file has the suspend_timing column, the intraday filter is exact; when it does
    not (legacy), fall back to treating every S as full-day WITH a warning. Confirmed live:
    20260702's suspend_d already carries suspend_timing, so the exact filter is active for
    freshly-fetched gated days. Test: an intraday-halted name is NOT excused (fail); an empty-timing
    full-day suspension IS excused (pass).

RE-REVIEW QUESTIONS
1. Is the chained proof from the parent-end anchor the right formal structure? Is requiring only
   date_ok + floor on the ANCHOR (rather than re-proving the parent's full history) acceptable, given
   the parent was already published + audited? Any way a hole slips in at the anchor boundary itself?
2. B1-b: is "full-day = S with empty suspend_timing" the correct Tushare semantics? Is the legacy
   fallback (no timing column -> all-S-full-day + warning) an acceptable interim, given freshly
   fetched gated days DO carry timing — or must the driver force-refetch suspend_d (with timing) for
   any gated day whose stored file lacks it before the gate can pass? (This is the one remaining
   documented residual: an intraday-halted name missing from a partial daily on a legacy-timing day
   could be wrongly excused.)
3. Is cyq_perf-at-target_end-only correct, or should cyq coverage be proven per new day across the
   range like daily-fresh?
4. Any NEW hole: the anchor requiring the parent_end daily file to still be present/date_ok at bump
   time; the per-day stock_basic read hoisted once (delist/list are date-filtered per day — correct?);
   the resumed-set (R) used only for the WARN-level unexpected check; chaining prior_date labels.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
