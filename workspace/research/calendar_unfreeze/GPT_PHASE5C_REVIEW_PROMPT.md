# GPT 5.5 Pro RE-review #3 — Phase 5-C (post-REWORK-2)

Status: ready to send. Branch `calendar-unfreeze` HEAD `e295ef6`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You
reviewed Phase 5-C (the unattended daily raw job) three times: REWORK, REVISE, then REWORK (2
Blockers + 4 Majors + 3 Minors — the prior partials weren't fully closed). This RE-REVIEW #3 verifies
the subsystem-level hardening. The daily job keeps the RAW layer current between the human-gated
monthly formal bumps and must never touch the Qlib provider/calendar.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD e295ef6)
Files (raw, pinned):
- tushare_lock (NEW): https://raw.githubusercontent.com/henrydan111/quant-system/e295ef6/src/data_infra/tushare_lock.py
- fetcher chokepoint:  https://raw.githubusercontent.com/henrydan111/quant-system/e295ef6/src/data_infra/fetchers/__init__.py
- daily updater:       https://raw.githubusercontent.com/henrydan111/quant-system/e295ef6/src/data_infra/pipeline/update_daily_data.py
- daily ops (manifest/watermark): https://raw.githubusercontent.com/henrydan111/quant-system/e295ef6/src/data_infra/pipeline/daily_ops.py
- orchestrator:        https://raw.githubusercontent.com/henrydan111/quant-system/e295ef6/scripts/daily_raw_job.py
- watchdog:            https://raw.githubusercontent.com/henrydan111/quant-system/e295ef6/scripts/daily_job_watchdog.py
- task manager:        https://raw.githubusercontent.com/henrydan111/quant-system/e295ef6/scripts/register_daily_raw_task.py
- catch-up (daily/fund): https://raw.githubusercontent.com/henrydan111/quant-system/e295ef6/workspace/scripts/catchup_daily_range.py , https://raw.githubusercontent.com/henrydan111/quant-system/e295ef6/workspace/scripts/catchup_fundamentals_range.py
- tests: https://raw.githubusercontent.com/henrydan111/quant-system/e295ef6/tests/data_infra/test_daily_update_5c.py
Self-review (round 4): workspace/research/calendar_unfreeze/PHASE5C_SELF_REVIEW.md

HOW EACH BLOCKER + MAJOR WAS CLOSED

Blocker 1 (age-based lock stole a live multi-hour catch-up; coverage incomplete): NEW
src/data_infra/tushare_lock.py uses `filelock` (a KERNEL lock — the OS releases it when the holder
process dies, so there is NO age-based stealing). Two locks: raw_maintenance_lock (process-exclusive;
acquired by the daily orchestrator, update main, catchup_daily_range, AND catchup_fundamentals_range
[previously unlocked], and the monthly bump inherits it via those subprocesses) and api_call_lock held
INSIDE TushareFetcher._safe_api_call for the call + the rate-limit sleep (covers EVERY sanctioned
caller, incl. ad-hoc scripts). Lock ordering is always maintenance-then-per-call-api, so no deadlock;
QA runs after the maintenance lock releases. A multiprocess test asserts a subprocess-held lock blocks
the parent and is released when the holder is killed (not by age).

Blocker 2 (normalizer coerced is_open='BAD'->0, flipping an open day to closed silently, common-mode):
_validate_trade_cal now REJECTS malformed ground truth — raises on missing columns, null/blank
exchange, non-8-digit cal_date, is_open outside {0,1}, duplicate (exchange,cal_date), or a FRESH fetch
(is_open='1') containing any non-open row. An empty stock_basic/trade_cal response is an error, not a
successful no-op. Tests cover each rejection.

Major 1 (heartbeat advanced over an incomplete earlier session; is_trading_day=False accepted): a
per-session completion MANIFEST (logs/session_status/<date>.json, required_ok = every required endpoint
succeeded) + a CONTIGUOUS watermark (advance_watermark stops at the first incomplete session). The
orchestrator writes required_ok=False when is_trading_day/market_ok is false or errors exist, and the
heartbeat's completed_session = the watermark (NOT the target). If the watermark < target the run exits
BACKLOGGED. The orchestrator has a top-level exception boundary (always alerts) and atomic JSON writes.
The watchdog validates completed_session with re.fullmatch(\d{8}) (no truncation) AND the manifest's
required_ok, and owns daily_job_alert (not qa_alert, which a manual QA clears).

Major 2 (zero-errors excluded several failures): update_phase3_daily_market records failures/empties of
the REQUIRED endpoints (moneyflow, stk_limit) into the errors; a reference-refresh failure is surfaced
even on a closed date.

Major 3 (15-session sliding window = permanent blind horizon): backlog_sessions discovers work from the
persistent watermark whose floor is the monthly-published provider boundary (data/qlib_data/calendars/
day.txt), not a sliding window; MAX_SESSIONS_PER_RUN bounds a run and the remainder is picked up next
run (heartbeat stays at the last contiguous session).

Major 4 (--password leaked on the command line): removed; schtasks /RP * prompts interactively;
UserId/description/command/working-dir/args are XML-escaped.

RE-REVIEW QUESTIONS
1. Blocker 1: is the filelock design correct — raw_maintenance_lock at the entry points AND api_call_lock
   inside _safe_api_call? Is holding api_call_lock across the call + the base_sleep (so the rate-limit
   applies globally) right, or does it over-serialize? Any lock-ordering or reentrancy hazard (a process
   holding raw_maintenance_lock then acquiring api_call_lock per call — different paths)? Is putting a
   cross-process lock in the shared _safe_api_call acceptable given only ingestion fetches Tushare
   (research/backtests read Qlib)?
2. Blocker 2: does strict _validate_trade_cal fully close the common-mode false-pass, and is failing an
   empty stock_basic/trade_cal fetch correct (vs a transient empty that should retry)?
3. Major 1: is the completion-manifest + contiguous-watermark heartbeat now airtight — can the heartbeat
   advance past any incomplete session? Is the provider-boundary floor the right watermark anchor?
4. Major 3: is watermark-anchored backlog + max_sessions_per_run the right bounded self-heal, and does
   exiting BACKLOGGED (non-zero, heartbeat held) correctly keep the watchdog red until the gap fills?
5. Any NEW hole from this round: the shared-fetcher lock's blast radius; the manifest/watermark file
   layout under logs/; the QA subprocess running outside the maintenance lock; the /RP * interactive
   prompt under a scheduled (non-interactive) --register.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
