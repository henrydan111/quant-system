# GPT 5.5 Pro RE-review #5 — Phase 5-B monthly_calendar_bump driver (post-REWORK-5)

Status: ready to send. Branch `calendar-unfreeze` HEAD `29f5cba`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You
have reviewed this monthly calendar freeze-bump DRIVER five times; it has converged each round
(7 -> 5 -> 5 -> 2 -> 2). Round 4 (20e096c) you confirmed the stale-file guard, endpoint split, and
all-core-bin span model RESOLVED, and returned Blocker B1 (a count baseline is not a completeness
proof — a daily missing <2% of names passes, invisible to the survivorship audit) and Major M1 (a
fresh raw-priced day absent from the provider calendar was silently skipped). Both fixed with the
set-level completeness proof you asked for. This RE-REVIEW #5 verifies them.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 29f5cba)
Files (raw, pinned):
- driver:  https://raw.githubusercontent.com/henrydan111/quant-system/29f5cba/scripts/monthly_calendar_bump.py
- tests:   https://raw.githubusercontent.com/henrydan111/quant-system/29f5cba/tests/data_infra/test_monthly_calendar_bump.py
Self-review (round 6): workspace/research/calendar_unfreeze/PHASE5B_SELF_REVIEW.md

CONTEXT: split endpoint gate — daily/moneyflow/stk_limit gate target_end PRE-catch-up (cheap
candidate selection: trade_date-correct + rolling baseline + coverage); cyq_perf + the SET-LEVEL
daily completeness proof run POST-catch-up in assert_endpoints_complete (the formal gate before a
policy is minted, where prev daily + stock_basic + suspend_d(date) are all present). Tushare code
000001.SZ; the endpoint/coverage/continuity path compares codes in dotted-upper form (000001.SZ)
per _read_codes_for_trade_date; the survivorship audit uses underscore form (000001_SZ) for the
provider feature tree. stock_basic has list_date/delist_date (YYYYMMDD str, delist null=listed);
suspend_d per-date files have (ts_code, trade_date, suspend_type in {S,R}).

HOW THE 2 ROUND-4 FINDINGS WERE FIXED

B1 (count baseline is not a completeness proof): FIXED with _daily_set_continuity(date, daily_codes)
run in assert_endpoints_complete (post-catch-up). The proof:
  prior_codes = the previous session's verified daily code set (a name here TRADED yesterday, so it
                was listed AND not suspended yesterday).
  delisted    = stock_basic where delist_date <= date.
  suspended   = suspend_d(date) rows with suspend_type == 'S' (a NEW suspension today).
  ipo_today   = stock_basic where list_date == date.
  expected    = (prior_codes - delisted - suspended) | (ipo_today - suspended)
  missing     = expected - daily_codes  -> if non-empty, FAIL (survivorship hole).
KEY INSIGHT (why no historical suspension-state reconstruction is needed): a prior-session name was
TRADING yesterday, so the ONLY PIT reasons it can be absent today are (a) it delisted, or (b) it
suspended TODAY (an S event dated today). A name suspended on an earlier day would not have traded
yesterday, so it is not in prior_codes and cannot be a false "missing". A missing suspend_d(date)
file -> FAIL closed (cannot prove completeness). unexpected names (today - prior - ipo - resumed) ->
WARN, not fail (additions aren't a survivorship risk). The rolling count baseline is demoted to a
cheap PRE-catch-up early detector. LIVE (real data): _daily_set_continuity('20260703') -> ok=True;
prior 5517, suspended_today 18, delisted 333, ipo 0, MISSING 0, UNEXPECTED 0 — zero false positives
on a genuinely complete session. Tests: unexplained-vanished-name -> fail; delisted allowed + a
missing IPO -> fail; suspend_d-missing -> fail closed.

M1 (fresh raw-priced day absent from provider calendar silently skipped): FIXED. `pos_d is None`
now appends a raw_price_day_not_in_provider_calendar violation and continues, instead of skipping
the bin-span check. The all-core-bin span check (open/high/low/close/vol/amount/adj_factor spanning
each raw-priced day) is retained.

RE-REVIEW QUESTIONS
1. Is the set-continuity proof a sufficient formal daily-completeness gate? Specifically: is the
   "a prior-session trader can only vanish via delist or a same-day-S suspension" argument airtight
   (so no historical suspension-range reconstruction is needed)? Any A-share case where a name
   trades one day, is legitimately absent the next, and has NEITHER a delist_date <= date NOR an S
   event dated that day (e.g. a suspension whose S event is dated the prior evening / a half-day /
   an exchange-halt with no suspend_d row)?
2. Is failing closed on a missing suspend_d(date) correct, or will it over-block when suspend_d
   legitimately has zero rows on a day with no suspensions? (Note: the file is written per-date by
   the catch-up even when empty; absence — not emptiness — triggers the fail. Is that the right
   distinction?)
3. Is running the set proof POST-catch-up only (not pre, for target_end selection) acceptable —
   given target_end is a candidate and the formal gate before policy minting is post-catch-up?
4. Is the IPO check (list_date == date names must be present) correct, or can a name legitimately
   list on `date` yet have no first-day price row (e.g. listed-but-halted debut)?
5. Any NEW hole: the dotted-upper vs underscore code-form split between the continuity/coverage path
   and the survivorship-audit path; delist_date/list_date string comparison; the unexpected-names
   WARN-not-fail choice.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
