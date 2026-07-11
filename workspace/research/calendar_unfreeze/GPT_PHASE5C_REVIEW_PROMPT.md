# GPT 5.5 Pro RE-review — Phase 5-C (post-REWORK)

Status: ready to send. Branch `calendar-unfreeze` HEAD `7f1fb1d`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You
reviewed the Phase 5-C daily-raw-job implementation and returned REWORK (2 Blockers, 4 Majors, 2
Minors — all deployment-level). This RE-REVIEW verifies the fixes. Phase 5-C is the unattended daily
mechanism that keeps the RAW layer current between the human-gated monthly formal calendar bumps; it
must never touch the Qlib provider/calendar.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 7f1fb1d)
Files (raw, pinned):
- daily updater: https://raw.githubusercontent.com/henrydan111/quant-system/7f1fb1d/src/data_infra/pipeline/update_daily_data.py
- QA runner:     https://raw.githubusercontent.com/henrydan111/quant-system/7f1fb1d/scripts/run_daily_qa.py
- task manager:  https://raw.githubusercontent.com/henrydan111/quant-system/7f1fb1d/scripts/register_daily_raw_task.py
- watchdog:      https://raw.githubusercontent.com/henrydan111/quant-system/7f1fb1d/scripts/daily_job_watchdog.py
- wrapper bat:   https://raw.githubusercontent.com/henrydan111/quant-system/7f1fb1d/scripts/daily_raw_update.bat
- catch-up:      https://raw.githubusercontent.com/henrydan111/quant-system/7f1fb1d/workspace/scripts/catchup_daily_range.py
- consumer:      https://raw.githubusercontent.com/henrydan111/quant-system/7f1fb1d/workspace/research/ai_research_dept/engine/event_store.py
- tests: https://raw.githubusercontent.com/henrydan111/quant-system/7f1fb1d/tests/data_infra/test_daily_update_5c.py
Self-review (round 2): workspace/research/calendar_unfreeze/PHASE5C_SELF_REVIEW.md

HOW EACH FINDING WAS FIXED (verify real + complete + no new hole)

B1 (first daily run TRUNCATED the calendar it uses to pick the next session -> stuck on day one, and
QA read the truncated calendar and reported PASS): update_reference_data now fetches a FORWARD horizon
(end_date = next year-end) and MERGES by (exchange, cal_date) — drop_duplicates keep="last", sorted,
atomic os.replace — instead of overwriting with a target-bounded response. resolve_last_complete_session
FAILS CLOSED if the calendar's max date < today (CST). Regression test: a "Monday" update_reference_data
run leaves the future calendar intact and the Tuesday selector returns Tuesday.

B2 (.bat failed under code page 936 because `cd /d E:\<chinese>` is UTF-8 bytes misdecoded to a
nonexistent path): the wrapper is now ASCII-only and self-relative — `cd /d "%~dp0.."` (%~dp0 is the
OS-encoded script dir at runtime, not a literal in the .bat's bytes) with `|| exit /b 2`, and it
propagates the combined update+QA exit code.

M1 (updater failures logged but returned exit 0, hiding a crash behind QA's code): main() now returns
0/1 and `sys.exit(main())`. update_for_date returns is_trading_day + errors; a trading day with missing
daily data or a suspend_d error -> non-zero. The .bat captures both the updater's and QA's exit codes
and returns non-zero if either failed. (A non-trading day is a legitimate exit 0.)

M2 ("18:30" used the HOST's local time — this host is US-timezone — and missed launches were
unrecovered): register_daily_raw_task.py now registers via Task Scheduler XML with a StartBoundary
carrying +08:00 (true CHINA time regardless of host TZ), StartWhenAvailable=true, RestartOnFailure
(PT30M x3), MultipleInstancesPolicy=IgnoreNew, RunLevel LeastPrivilege. The XML is written UTF-16 so
the Chinese repo path is safe. run_daily_qa.py now uses Asia/Shanghai for its cutoff + report/alert
timestamp, and writes a success heartbeat (logs/daily_job_heartbeat.json). A NEW independent watchdog
(QuantDailyRawWatchdog, 10:00 CST) reads the heartbeat and, if the last QA success is older than the
last complete trading session, writes an alert flag + exits non-zero — catching a silently-missed run.

M3 (suspend_d writer could overwrite a valid snapshot with malformed/wrong-date data): write_suspend_d
now, for a nonempty response, requires all four columns AND every trade_date == target_date, else
RAISES (preserving the prior snapshot). It writes via a UNIQUE temp file (tempfile.mkstemp) + atomic
replace (a fixed .tmp collided with the overlapping monthly job). Tests: wrong-date-preserves-prior,
missing-timing-raises.

M4 (a downstream suspension consumer couldn't see the year-partitioned files): event_store.py
gen_suspend_events glob("*.parquet") -> rglob("suspend_d_*.parquet") (root found 0, recursive 85).

m1: catch-up run_one_day no longer re-fetches suspend_d (update_phase3_daily_market writes it) —
removes the double Tushare hit per session.
m2: the close cutoff is 17:30 CST (close_hhmm; daily_basic updates to ~17:00), and a pre-close-only-today
now RAISES rather than returning a partial session.

RE-REVIEW QUESTIONS
1. B1: is the forward-horizon fetch + (exchange,cal_date) merge the right fix, and does the selector's
   fail-closed-on-stale-calendar fully close the day-one lockup? Any residual where a merge could still
   lose future sessions (e.g. the fetch returning fewer future dates than the existing file — the merge
   keeps the union, correct?)?
2. M2: is the XML +08:00 StartBoundary the correct way to pin the trigger to CST on a US-timezone host,
   and are StartWhenAvailable + RestartOnFailure + the independent watchdog sufficient for missed-run
   recovery? Is InteractiveToken/LeastPrivilege the right principal (vs S4U for a truly-unattended
   server), given no stored password?
3. M3: is validating (four columns + trade_date==target) before an atomic unique-temp replace the right
   safety, or is the repository file_lock still needed given two jobs can target the same date?
4. M1: does main() now surface every deployment-relevant failure (missing daily, suspend_d error), and
   is deferring gap-backfill of a transiently-missing session to the monthly bump's catch-up acceptable,
   or must the daily job itself retry a missing prior session?
5. Any NEW hole from the rework: the calendar merge dtype/sort; the .bat combined exit logic; the
   watchdog's dependence on resolve_last_complete_session (shared failure mode); the event_store change.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
