# GPT 5.5 Pro RE-review #2 — Phase 5-C (post-REVISE)

Status: ready to send. Branch `calendar-unfreeze` HEAD `a8778ca`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You
reviewed Phase 5-C (the unattended daily raw job) twice: REWORK (2B/4M/2m, fixed) then REVISE (0
Blockers; 4 prior fully fixed, 4 partial). This RE-REVIEW #2 verifies the 4 partials are now fully
closed. The daily job must keep the RAW layer current between the human-gated monthly formal bumps
and never touch the Qlib provider/calendar.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD a8778ca)
Files (raw, pinned):
- orchestrator (NEW): https://raw.githubusercontent.com/henrydan111/quant-system/a8778ca/scripts/daily_raw_job.py
- daily ops (NEW):    https://raw.githubusercontent.com/henrydan111/quant-system/a8778ca/src/data_infra/pipeline/daily_ops.py
- daily updater:      https://raw.githubusercontent.com/henrydan111/quant-system/a8778ca/src/data_infra/pipeline/update_daily_data.py
- QA runner:          https://raw.githubusercontent.com/henrydan111/quant-system/a8778ca/scripts/run_daily_qa.py
- watchdog:           https://raw.githubusercontent.com/henrydan111/quant-system/a8778ca/scripts/daily_job_watchdog.py
- task manager:       https://raw.githubusercontent.com/henrydan111/quant-system/a8778ca/scripts/register_daily_raw_task.py
- wrapper bat:        https://raw.githubusercontent.com/henrydan111/quant-system/a8778ca/scripts/daily_raw_update.bat
- catch-up:           https://raw.githubusercontent.com/henrydan111/quant-system/a8778ca/workspace/scripts/catchup_daily_range.py
- consumer:           https://raw.githubusercontent.com/henrydan111/quant-system/a8778ca/workspace/research/ai_research_dept/engine/event_store.py
- tests: https://raw.githubusercontent.com/henrydan111/quant-system/a8778ca/tests/data_infra/test_daily_update_5c.py
Self-review (round 3): workspace/research/calendar_unfreeze/PHASE5C_SELF_REVIEW.md

HOW THE 4 PARTIALS WERE CLOSED

M1 (heartbeat not bound to a successful raw update -> watchdog false-green after an update failure,
or after a manual QA pass): a NEW orchestrator daily_raw_job.py owns the daily job. It (1) resolves
the last complete session + bounded gap sessions, (2) runs update_for_date for each under the
account lock, collecting errors, (3) runs QA as a subprocess, and (4) writes the heartbeat
{completed_session, at_cst} ONLY when there are zero update errors AND QA passed. run_daily_qa.py NO
LONGER writes the heartbeat (it owns only qa_alert). The watchdog now reads completed_session,
validates it (8-digit, <= expected, and a real daily_<date>.parquet exists), and catches ALL
exceptions (a missing/corrupt calendar is alert-worthy, not a silent crash). The .bat calls the
orchestrator.

M2 (is_open='1' fetch -> the calendar holds ONLY open days, so the old is_open==0 check treated a
Saturday as a trading day and reported "missing daily data"; and ref/calendar errors were swallowed):
the trading-day decision is now open-days MEMBERSHIP — absent within calendar coverage = non-trading
(exit 0); a date BEYOND coverage = an error (insufficient calendar). update_reference_data records
its failure into the returned errors (M1 exit contract). catch-up run_one_day RAISES when the
suspend_d write failed (so the day is marked failed + retried), and suspend_refresh failures now
count toward the catch-up's non-zero exit.

M3 (not fully unattended; single-session recovery only): register_daily_raw_task.py gains
--user/--password -> a Password-logon Principal (runs across logout/reboot AND keeps network for
Tushare; S4U has no network), defaulting to InteractiveToken with StartWhenAvailable + the watchdog.
daily_ops.missing_open_sessions is a bounded, oldest-first gap walker; the orchestrator processes all
missing sessions before the target, so a multi-session outage self-heals.

M4 (unique temp != cross-process lock): daily_ops.account_lock is a cross-process Tushare-account
lock (O_EXCL lockfile, steals a stale lock after 1h) wrapping the daily main, the orchestrator, and
the monthly catch-up (CLAUDE.md §6.1: never parallel fetchers). _normalize_trade_cal coerces
exchange/cal_date to str + is_open to int before the merge/sort (the mixed-dtype crash was swallowed,
leaving a stale calendar); _atomic_write_parquet uses a unique temp for the calendar + stock_basic.

Minors: the .bat is pure ASCII (0 non-ASCII bytes) and --query combines schtasks return codes;
event_store reads only the requested per-date suspend files (paths built from `days`), not all
history; data_dictionary.md documents the per-date suspend_d store.

RE-REVIEW QUESTIONS
1. M1: is binding the heartbeat to (zero update errors AND QA pass) in the orchestrator, with the
   watchdog validating completed_session against a real daily file, a complete fix — any path where
   the heartbeat still advances after a deployment-relevant failure (e.g. a gap session silently
   skipped, or update_for_date returning is_trading_day False for a real trading day)?
2. M4: does the account_lock (O_EXCL + stale-steal) correctly serialize the daily job, the monthly
   catch-up, and a manual run, and is the 1h stale-steal safe (a legitimately long monthly catch-up
   could exceed it)? Is wrapping at the entry points sufficient, or is per-resource locking still
   needed for the calendar/suspend_d writes given the account lock already serializes all fetchers?
3. M2: is open-days membership (absent-in-coverage = non-trading; beyond-coverage = error) the
   correct trading-day contract for an is_open='1'-only calendar? Does the orchestrator's gap walker
   + membership correctly avoid re-processing / falsely-failing a genuine non-trading day inside the
   lookback window?
4. M3: is the Password-logon option (with a documented default of InteractiveToken) the right
   unattended posture, and is a bounded oldest-first gap walker the right self-heal (vs deferring to
   the monthly bump)? What lookback bound is appropriate?
5. Any NEW hole from this round: the orchestrator running update_for_date per gap session (repeated
   reference/fundamental refresh); the account_lock held across the whole session loop + QA is
   outside it; the watchdog's dependence on the same resolver as the job.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
