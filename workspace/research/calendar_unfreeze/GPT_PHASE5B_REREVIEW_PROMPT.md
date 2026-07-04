# GPT 5.5 Pro RE-review #4 — Phase 5-B monthly_calendar_bump driver (post-REWORK-4)

Status: ready to send. Branch `calendar-unfreeze` HEAD `319dbcf`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You
have reviewed this monthly calendar freeze-bump DRIVER four times; it has converged each round
(7 -> 5 -> 5 -> 2 findings). Round 3 (971282a) you confirmed B2 (full-SHA), M2 (halo month-zero),
m1 (cyq resume) RESOLVED, and returned 2 findings: Blocker B1 (daily itself can be partial above
the row floor -> the coverage denominator is unsafe; and files aren't verified trade_date==date)
and Major M1 (bin-length only checked close.day.bin). Both fixed. This RE-REVIEW #4 verifies them.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 319dbcf)
Files (raw, pinned):
- driver:  https://raw.githubusercontent.com/henrydan111/quant-system/319dbcf/scripts/monthly_calendar_bump.py
- catchup: https://raw.githubusercontent.com/henrydan111/quant-system/319dbcf/workspace/scripts/catchup_fundamentals_range.py
- audit:   https://raw.githubusercontent.com/henrydan111/quant-system/319dbcf/workspace/scripts/audit_thaw_frozen_prefix.py
- tests:   https://raw.githubusercontent.com/henrydan111/quant-system/319dbcf/tests/data_infra/test_monthly_calendar_bump.py
Self-review (round 5): workspace/research/calendar_unfreeze/PHASE5B_SELF_REVIEW.md

CONTEXT (unchanged): D3 spent_oos_end frozen 2026-02-27; split endpoint gate (daily-fresh
pre-catch-up, cyq_perf post-catch-up, report_rc halo inside Stage E, all fail-closed); frozen-prefix
audit full-SHA in monthly mode; publish §13 human-gated. Live daily counts are stable: 5507-5517
over the last ~12 sessions (<0.3% day-to-day variation).

HOW THE 2 ROUND-3 FINDINGS WERE FIXED

B1 (daily itself can be partial above the 4000 floor -> unsafe denominator; files not date-verified):
FIXED — `daily` is now a completeness OBJECT, not just the denominator. _daily_universe(date) proves:
  1. file trade_date == date: _read_codes_for_trade_date reads (ts_code, trade_date), keeps only
     rows whose trade_date == date, and sets date_ok = (the file's trade_date set == {date}). A
     stale/mispartitioned file (right name, wrong trade_date) -> date_ok False -> reject (your
     second B1 form).
  2. code count >= MIN_PLAUSIBLE_DAILY_ROWS (absolute floor).
  3. code count >= DAILY_BASELINE_FLOOR(0.98) x median(last DAILY_BASELINE_WINDOW=10 complete
     sessions' daily counts). Because the universe count is stable (<0.3% variation), 0.98 is a
     tight partial detector: a partial daily still above 4000 (e.g. 4500 of ~5510) -> ratio 0.82 ->
     reject.
Every endpoint coverage (moneyflow/stk_limit pre; cyq_perf post) is then measured against this
PROVEN-complete daily universe, and each endpoint file is itself trade_date-verified. Live:
_daily_universe('20260703') -> ok, 5516 codes vs baseline 5511 (ratio 1.0009), date_ok True;
endpoint_ready True (moneyflow 0.9414, stk_limit 1.0); assert_endpoints_complete False (cyq_perf
0.0). Tests added: partial-daily-above-floor (12 vs baseline 20 -> reject), stale-trade_date.
  DESIGN CHOICE (scrutinize): you offered two daily-completeness proofs — an expected-universe
  reconstruction (list/delist bounds minus suspended) or a rolling stable-count baseline. I chose
  the BASELINE: dependency-light (no stock_basic/suspend_d reconciliation, each with its own PIT and
  completeness caveats), and it targets the actual failure mode (an interrupted fetch loses a large
  chunk -> a big count drop). DOCUMENTED LIMIT: a <2% mild partial (~110 names) sits within the
  0.98 band and is not distinguished from natural universe drift; interrupted fetches are not mild,
  so the baseline separates cleanly. Is the baseline acceptable, or do you consider the
  expected-universe reconstruction load-bearing enough to block?

M1 (bin-length only checked close.day.bin): FIXED — _bin_span(path) -> (start_pos, last_pos) with a
size%4 guard, and the survivorship audit now requires EVERY core bin
(open/high/low/close/vol/amount/adj_factor.day.bin) to satisfy start_pos <= day_pos <= last_pos for
each raw-priced (code, day). A truncated vol/amount/adj_factor bin is now caught, not just close.
Live: all 7 bins of 000001 reach the calendar end index (4492).

RE-REVIEW QUESTIONS
1. B1 rolling baseline: with live daily counts at 5507-5517 (<0.3% variation), is the 0.98 floor
   over a 10-session median a sufficient partial-daily detector, or is the documented <2%-mild-
   partial gap material enough to require the expected-universe (list/delist - suspend)
   reconstruction? Is median (vs min) the right baseline statistic?
2. B1 trade_date verification: is date_ok = (file's trade_date set == {date}) the right stale-file
   guard? Any endpoint where multiple trade_dates in one file is legitimate (so this over-rejects)?
3. M1 all-bin span: is start_pos <= day_pos <= last_pos for every core bin correct, and is scoping
   the check to days the code is RAW-PRICED on the right way to avoid false-flagging suspended /
   delisted days (which have no raw row)?
4. Any NEW hole from this round: the baseline now uses the SAME trade_date-filtered code count for
   prior sessions AND the target (apples-to-apples; only date-correct prior sessions above the floor
   count toward the median); the _open_trading_days empty-on-missing-calendar guard; the span cache
   keyed by (code, binname).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
