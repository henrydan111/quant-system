# GPT 5.5 Pro RE-review #4 — Phase 5-C (post-REWORK-3, full hardening)

Status: ready to send. Branch `calendar-unfreeze` HEAD `425dff7`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You have
reviewed Phase 5-C (the unattended daily raw job) four times: REWORK, REVISE, REWORK, then REWORK again
(2 Blockers + 4 Majors + 3 Minors — the subsystem hadn't truly closed: the monthly formal build could
read a moving raw tree, the calendar validator missed a MISSING session, .pro wasn't an enforceable
chokepoint, the manifest could false-green, publish wasn't transactional, and "complete" ignored an
engine-required endpoint). The operator asked for FULL hardening — everything, not just correctness
bugs. This RE-REVIEW #4 verifies that closure. The daily job keeps the RAW layer current between the
human-gated monthly formal bumps and must NEVER touch the Qlib provider/calendar (that advances only via
the monthly bump). spent_oos_end stays frozen at 2026-02-27; the post-freeze fresh window is born sealed.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 425dff7)
Files (raw, pinned):
- tushare_lock:        https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/src/data_infra/tushare_lock.py
- fetcher proxy:       https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/src/data_infra/fetchers/__init__.py
- daily updater:       https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/src/data_infra/pipeline/update_daily_data.py
- daily ops (manifest/watermark): https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/src/data_infra/pipeline/daily_ops.py
- orchestrator:        https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/scripts/daily_raw_job.py
- watchdog:            https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/scripts/daily_job_watchdog.py
- task manager:        https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/scripts/register_daily_raw_task.py
- daily QA + PRO001:   https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/scripts/run_daily_qa.py
- PRO001 lint (NEW):   https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/scripts/lint_no_bare_pro.py
- monthly bump (barrier): https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/scripts/monthly_calendar_bump.py
- catch-up (daily/fund): https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/workspace/scripts/catchup_daily_range.py , https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/workspace/scripts/catchup_fundamentals_range.py
- tests: https://raw.githubusercontent.com/henrydan111/quant-system/425dff7/tests/data_infra/test_daily_update_5c.py
Self-review (round 5, REWORK-3 table): workspace/research/calendar_unfreeze/PHASE5C_SELF_REVIEW.md

HOW EACH BLOCKER + MAJOR FROM REWORK-3 WAS CLOSED

Blocker 1 (the formal MONTHLY build could be constructed from a MOVING raw tree — catch-up released its
lock, then the provider build read raw parquet that a concurrent daily job could be rewriting → a formal
provider_build_id would not be reproducible from a pinned raw input):
  - monthly_calendar_bump.phase_execute now wraps the ENTIRE impl (catch-up -> Qlib build -> audits ->
    report) in ONE raw_maintenance_lock() barrier, so no daily job / catch-up can mutate raw between the
    catch-up and the build.
  - raw_maintenance_lock is ENV-REENTRANT: the parent sets QUANT_RAW_MAINT_LOCK_HELD=1; a nested/child
    acquire (the bump's own catch-up subprocess, which also calls raw_maintenance_lock) becomes a NO-OP
    instead of dead-locking on the same cross-process filelock. On release the parent clears the env.
  - the report records raw_input_digest(parent_end, target_end) as an attestation of the raw input slice
    the build consumed.

Blocker 2 (calendar validation was only SYNTACTIC — it rejected malformed rows but a calendar that
simply OMITTED a trading session [a hole] passed, so the daily loop would silently skip a real session):
  - _validate_trade_cal now enforces pretrade_date CHAIN CONTINUITY per exchange: for every open day the
    published pretrade_date must equal the immediately-preceding open day's cal_date; a missing session
    leaves a dangling pretrade_date -> raise. (Verified against the live calendar: 8,797 rows, a SINGLE
    exchange 'SSE' [the canonical A-share calendar; SZSE shares an identical trading calendar and is not
    stored separately], 0 continuity breaks -> enforcement is safe. The groupby-exchange logic is
    multi-exchange-ready but the live ground truth is SSE-only.)
  - the merged (existing + forward-fetched) calendar is REVALIDATED before persist (a merge can't smuggle
    in a hole), and the orchestrator refreshes the calendar INSIDE the maintenance lock BEFORE resolving
    the target session.

Major 1 (_safe_api_call was the intended Tushare chokepoint but nothing ENFORCED it — any script could
call `ts.pro_api().xxx()` directly and bypass the account lock + rate spacing, violating "never parallel
fetchers against the account"):
  - TushareFetcher.pro is now a _LockedPro PROXY. `self.pro.report_rc(...)` resolves via __getattr__ to a
    wrapped callable that routes through spaced_call() (holds api_call_lock + waits on a shared cross-
    process next_allowed timestamp + bumps a global cooldown on a rate-limit error). So EVERY caller —
    internal fetch methods AND external ad-hoc scripts that do `fetcher.pro.xxx` — is serialized+spaced,
    with no per-method opt-in. _safe_api_call no longer re-locks (the proxy owns it) to avoid double-lock.
  - a NEW AST lint (scripts/lint_no_bare_pro.py, PRO001) bans `ts.pro_api()` / `tushare.pro_api()`
    construction anywhere except fetchers/__init__.py, and is wired into run_daily_qa.py so a bypass fails
    QA. Currently clean.

Major 2 (the completion manifest could FALSE-GREEN and didn't SELF-HEAL): three fixes —
  - session_required_ok is STRICT: required_ok must be the JSON boolean True (a stringified "false" is
    truthy in Python — now rejected) AND the manifest's embedded date must equal the filename.
  - backlog_sessions scans the WHOLE (floor, target] interval from the provider floor, not only sessions
    after the cached watermark, so a bad/rebased watermark can't hide an earlier incomplete session.
  - contiguous_watermark RECOMPUTES from the floor on every call and never trusts the persisted value, so
    a poisoned future watermark (e.g. 20990101) can't false-green, and it automatically rebases when the
    monthly provider floor advances. The heartbeat is written only if watermark == target AND qa_ok.

Major 3 (QA + the completion/heartbeat publish ran OUTSIDE the maintenance transaction, so another
process could interleave writes between the update and the heartbeat):
  - the daily orchestrator (_run) now holds ONE raw_maintenance_lock across the whole attempt: refresh
    calendar -> resolve target -> discover backlog -> update each session -> QA subprocess -> recompute
    watermark -> heartbeat. QA runs inside the held lock.

Major 4 ("session complete" checked only that SOME OHLCV landed, so a session missing adj_factor — an
ENGINE-REQUIRED field, §3.3 ENGINE_REQUIRED_FIELDS — was marked complete):
  - update_market_data now flags empty/thin adj_factor (floor 0.98 coverage) and daily_basic (floor 0.90)
    as a _market_error, propagated into the session errors, so required_ok=False and the watermark holds.

Minors: a GLOBAL rate backoff (the next_allowed timestamp is shared under api_call_lock, so a 429 cooldown
applies across processes, not per-fetcher); /RP * now has a TTY preflight (refuses --user without an
interactive console) + rolls back a half-installed task pair; the watchdog self-clears its own
daily_job_alert on a recovered run.

VERIFICATION
104 tests green: test_daily_update_5c (incl. barrier-reentrant no-op under QUANT_RAW_MAINT_LOCK_HELD;
strict-manifest; poisoned-future-cache recompute-from-floor; empty-adj_factor market error; kernel-lock
multiprocess) + catch-up range safety + monthly bump + report_rc ledger + provider_boundary +
calendar_policy. PRO001 lint clean. monthly_calendar_bump --plan and register_daily_raw_task dry-run
smoke-tested. C-4 scheduled-task registration stays HELD for the operator (§13 machine mutation).

RE-REVIEW QUESTIONS
1. Blocker 1: does the env-reentrant barrier truly guarantee an immutable raw input for the formal build?
   Is QUANT_RAW_MAINT_LOCK_HELD the right reentrancy signal, or is there a path where a grandchild
   process loses the env and dead-locks, OR where a sibling process (no env inheritance) mutates raw
   during the build? Is raw_input_digest(parent_end, target_end) a sufficient attestation, or should it
   hash the actual raw bytes/parquet mtimes rather than just the date bounds?
2. Blocker 2: does pretrade_date chain-continuity fully close the missing-session hole given the live
   calendar is SSE-only (single exchange), and is per-exchange grouping the right shape if a future
   fetch ever adds SZSE/BSE rows? The calendar is fetched with is_open='1' (open-days-only, closed dates
   ABSENT) — any calendar shape (half-day, exchange-specific holiday, a genuine one-off SSE/SZSE
   divergence) that would FALSE-REJECT a valid calendar?
3. Major 1: is the _LockedPro proxy an airtight chokepoint? Can any attribute path escape it (e.g.
   `fetcher.pro.__class__`, a cached bound method, a data attribute vs a callable, `getattr` on a nested
   client)? Does routing EVERY .pro access through a cross-process lock over-serialize legitimate
   read-only metadata calls? Is the PRO001 AST lint's allow-list (fetchers/__init__.py only) the right
   boundary?
4. Major 2: is recompute-from-floor-every-call the right anti-false-green invariant, or does it mask a
   real need to persist progress (cost: O(open-days) manifest reads per call)? Can a floor that moves
   BACKWARD (a botched monthly rollback) cause the watermark to regress dangerously?
5. Major 3/4: is holding the maintenance lock across the QA subprocess acceptable (the subprocess itself
   re-enters raw_maintenance_lock as a no-op via the env barrier — confirm that's safe and not masking a
   genuinely-needed second lock)? Is adj_factor+daily_basic the right required-endpoint set, or are there
   other engine-required daily fields whose absence should hold the watermark?
6. Any NEW hole from this round: the barrier's blast radius into the monthly bump; the proxy's
   interaction with pickling/multiprocessing; whether the digest belongs in the provider attestation
   chain (§3.4) rather than just the bump report.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
