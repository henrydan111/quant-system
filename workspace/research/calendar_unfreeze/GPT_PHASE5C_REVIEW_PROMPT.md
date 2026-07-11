# GPT 5.5 Pro review — Phase 5-C daily raw job + scheduled task + QA alert

Status: ready to send. Branch `calendar-unfreeze` HEAD `1e6db9a`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. Review
the Phase 5-C IMPLEMENTATION — the unattended steady-state DAILY mechanism that keeps the raw layer
current between the human-gated monthly formal calendar bumps (Phase 5-B, already SHIP'd). This is
orchestration + a small readiness helper + a raw-layer suspend_d write + a QA alert flag + a Windows
scheduled-task manager. It must NOT touch the Qlib provider/calendar (that is the monthly bump's
exclusive job). The design (PHASE5_DESIGN.md §5-C) was already GPT-SHIP'd; this reviews the code.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 1e6db9a)
Files (raw, pinned):
- daily updater: https://raw.githubusercontent.com/henrydan111/quant-system/1e6db9a/src/data_infra/pipeline/update_daily_data.py
- QA runner:     https://raw.githubusercontent.com/henrydan111/quant-system/1e6db9a/scripts/run_daily_qa.py
- task manager:  https://raw.githubusercontent.com/henrydan111/quant-system/1e6db9a/scripts/register_daily_raw_task.py
- wrapper bat:   https://raw.githubusercontent.com/henrydan111/quant-system/1e6db9a/scripts/daily_raw_update.bat
- catch-up delegate: https://raw.githubusercontent.com/henrydan111/quant-system/1e6db9a/workspace/scripts/catchup_daily_range.py
- tests: https://raw.githubusercontent.com/henrydan111/quant-system/1e6db9a/tests/data_infra/test_daily_update_5c.py
Self-review: workspace/research/calendar_unfreeze/PHASE5C_SELF_REVIEW.md

CONTEXT (design invariants):
- D1/D2: the daily job is RAW-ONLY (`--no-qlib`) — it must never advance the calendar, rebuild the
  Qlib provider, rewrite the manifest, or rotate build_id (a daily provider publish would force a
  daily 25-approval rebind). The calendar advances ONLY via the monthly formal bump (5-B).
- D3: spent_oos_end stays 2026-02-27; the born-sealed fresh window grows only via a Phase-6 spend.
- The daily-job readiness is deliberately LENIENT (idempotent, non-publishing, retry-tolerant); the
  FORMAL bump's target_end uses a strict multi-endpoint readiness contract (5-B).
- suspend_timing distinguishes a full-day suspension (no price all day) from an intraday halt (still
  trades) — load-bearing for the monthly-bump daily-completeness proof (5-B), which fails closed on
  a suspend_d file that has S rows but no suspend_timing column.
- §13: registering a Windows scheduled task mutates the machine — must be explicit, not automatic.

WHAT THE IMPLEMENTATION DOES
1. C-1 update_daily_data.py `--last-complete-session`: resolve_last_complete_session(ref_dir,
   close_hour=16, now=None) returns the last trading day <= today (CST) that is COMPLETE — if the
   latest such day is today and now (CST) < 16:00, it rolls back to the prior trading day (today's
   data is still partial pre-close). now is injectable for tests. main() uses it when the flag is
   set (else --date, else calendar-today).
2. C-2 suspend_d in the daily phase3: DailyDataUpdater.write_suspend_d(target_date) is the CANONICAL
   writer — fetch_suspend_d (Tushare default fields incl. suspend_timing) -> keep
   [ts_code, trade_date, suspend_type, suspend_timing] -> ATOMIC OVERWRITE the per-date file (a
   complete same-date snapshot; a re-fetch REPLACES it, preserving suspend_timing — insert_market_data's
   merge would duplicate rows + strip timing on schema change). update_phase3_daily_market calls it
   after its category loop; catchup_daily_range.write_suspend_d now DELEGATES to it (one source of
   truth, respecting the src/ boundary).
3. C-3 run_daily_qa.py: on any failed check, write logs/qa_alert_<date>.flag (failed checks + report
   path); on a recovered same-day run, delete the stale flag. Lightweight — no email/webhook.
4. C-4 daily_raw_update.bat (cd + `update_daily_data.py --no-qlib --last-complete-session` +
   run_daily_qa.py) + register_daily_raw_task.py (schtasks /Create QuantDailyRawUpdate, SC DAILY, ST
   18:30, RL LIMITED, /F). DRY-RUN by default (prints the command); --register/--delete are §13 and
   were NOT executed. CLAUDE.md §6.2a note corrected + §6.2b steady-state section added.

REVIEW QUESTIONS
1. C-1: is resolve_last_complete_session correct and safe as the daily-job target selector? Is the
   close_hour=16 CST cutoff right (daily kline is ~15:00-16:00; is 16:00 enough margin, given the
   task fires at 18:30 anyway)? Any edge (e.g. a half-day session, a calendar with a future is_open
   day, DST — none in CST) where it picks a partial or wrong day? Is falling back to the prior
   session (rather than failing) the right lenient posture for a raw, idempotent, retry-tolerant job?
2. C-2: is wiring suspend_d into update_phase3_daily_market correct, and is it a problem that it runs
   only when market_ok is true (a trading day with empty daily data due to vendor lag would skip
   suspend_d until the next run / the monthly bump's catch-up)? Is the canonical-writer-in-src +
   catch-up-delegates refactor the right module-boundary structure? Any consumer of suspend_d that
   the atomic overwrite (vs the old merge) breaks? (The overwrite was already GPT-blessed for the
   catch-up path; this extends it to the daily job.)
3. D1/D2 safety: does anything in the daily path (with --no-qlib) touch the Qlib provider/calendar/
   manifest, rotate build_id, or advance the calendar? (It should not — confirm the raw-only claim.)
4. C-4: is the schtasks posture right — a DAILY trigger relying on the updater's internal is_open
   check to skip non-trading days, RL LIMITED, dry-run-by-default with --register as the explicit
   §13 action? Is the .bat running QA UNCONDITIONALLY after the update (vs the design's `&&`)
   acceptable (QA always reports, catching update failures too)? Any risk in the hardcoded
   E:\量化系统 path in the .bat?
5. QA alert: is a per-day flag file (+ the task's native exit-code record) an adequate alert for
   this stage, or is a missing-run detector needed (the task not firing at all leaves no flag)?
6. Any NEW hole or PIT/no-lookahead issue introduced by the daily raw job.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
