# GPT 5.5 Pro RE-review #5 — Phase 5-C (post-REWORK-4)

Status: ready to send. Branch `calendar-unfreeze` HEAD `d9b04b0`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You have
reviewed Phase 5-C (the unattended daily raw job) five times. Re-review #4 (HEAD afa7f35) returned
REWORK: the official battery passed but your INDEPENDENT PROBES reproduced 3 Blockers + 5 Majors + 3
Minors — the "full hardening" was wrong at the root (the env-boolean lock reentrancy was a forgeable +
orphan-prone bypass; calendar continuity was silently skipped; an invalid adj_factor could still be
coerced to 1.0). This RE-REVIEW #5 verifies the closure. The daily job keeps the RAW layer current
between the human-gated monthly formal bumps and must NEVER touch the Qlib provider/calendar (that
advances only via the monthly bump). spent_oos_end stays frozen at 2026-02-27; the post-freeze window
is born sealed.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD d9b04b0)
Files (raw, pinned):
- tushare_lock (env reentrancy REMOVED + spacing fail-closed): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/src/data_infra/tushare_lock.py
- fetcher proxy (discipline-not-security + pickle reject): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/src/data_infra/fetchers/__init__.py
- daily updater (continuity + MarketDataError + resolve dedup): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/src/data_infra/pipeline/update_daily_data.py
- daily ops (compute/persist split + manifest digest + bool-strict): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/src/data_infra/pipeline/daily_ops.py
- pit_backend (adj_factor fail-closed): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/src/data_infra/pit_backend.py  (see _load_price_frame)
- daily orchestrator (floor attestation + soft-skip + QA-bound heartbeat): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/scripts/daily_raw_job.py
- watchdog (pure compute + QA binding): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/scripts/daily_job_watchdog.py
- monthly bump (lock restructure + content manifest + verify-before-publish): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/scripts/monthly_calendar_bump.py
- task manager (export-before-mutate rollback): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/scripts/register_daily_raw_task.py
- PRO001 lint (expanded): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/scripts/lint_no_bare_pro.py
- catch-up (self-locking): https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/workspace/scripts/catchup_daily_range.py , https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/workspace/scripts/catchup_fundamentals_range.py
- tests: https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/tests/data_infra/test_daily_update_5c.py , https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/tests/data_infra/test_fetchers.py , https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/tests/data_infra/test_pit_backend.py , https://raw.githubusercontent.com/henrydan111/quant-system/d9b04b0/tests/data_infra/test_monthly_calendar_bump.py
Self-review (round 6, per-finding table): workspace/research/calendar_unfreeze/PHASE5C_SELF_REVIEW.md

HOW EACH BLOCKER + MAJOR FROM REWORK-4 WAS CLOSED

Blocker 1 (env reentrancy = forgeable bypass + orphaned inheriting child overlapping a new sibling
writer after the parent dies): the QUANT_RAW_MAINT_LOCK_HELD env barrier is REMOVED — nothing reads it;
every process acquires the REAL kernel lock. The nesting it existed for (the monthly bump wrapping its
catch-up subprocesses) is restructured: phase_execute holds NO lock; the two catch-up subprocesses each
SELF-acquire raw_maintenance_lock (serial); then _build_under_lock holds ONE in-process
raw_maintenance_lock across completeness -> manifest -> the in-process staged build -> audits (verified:
no subprocess nested inside that scope re-acquires the lock — the frozen-prefix audit subprocess does
not). Holding the lock across the in-process build is now the PRIMARY integrity guarantee (no writer
can mutate raw mid-build). Test: a live subprocess holds the lock; the parent WITH the env var forged
still times out; after the holder is killed the OS releases it and the parent acquires.

Blocker 2 (continuity silently skipped + multi-exchange double-count): _validate_trade_cal now
validates EACH open row after the first INDEPENDENTLY (pretrade_date must be 8-digit and equal the
immediately-preceding open cal_date) — it NO LONGER gates the whole chain on
`op["pretrade_date"].str.fullmatch(r"\d{8}").all()` (the live calendar's first pretrade_date is None, so
`.all()` was False and continuity was skipped for every fresh=False validation — your exact repro). The
first open row is exempt (predecessor may sit outside the frame). exchange is enforced == "SSE" (a
second exchange is refused — it cannot be represented by one market calendar and would double-count).
_open_days and resolve_last_complete_session dedup dates (fixing cands[-2] being still-today). Verified
live: passes with 0 breaks; a removed middle session and an injected SZSE row are both rejected.

Blocker 3 (invalid/missing adj_factor passes the formal path -> 1.0): update_market_data validates the
daily frame schema + target trade_date + unique (ts_code, trade_date) keys + required-field coverage
(adj_factor 0.98 / daily_basic 0.90) + post-merge non-null adj_factor coverage BEFORE committing; on a
required-field failure it RAISES the typed MarketDataError and does NOT write (prior preserved) — the
`_market_error` optional side channel is GONE; update_for_date and the catch-up consume the exception.
pit_backend._load_price_frame FAILS CLOSED: a missing adj_factor column raises BuildGateError (1.0 only
under the QUANT_ALLOW_UNIT_ADJ_FACTOR test escape), and a null adj_factor on a (long-format, always
priced) raw row raises BuildGateError instead of coercing to 1.0. Scanned 48 raw daily files across the
range: 0 priced-null-adj, so the guard does not false-block a real build. Tests cover raise-on-empty +
the fail-closed price-frame paths.

Major 1 (proxy/lint not airtight; unpicklable obscurely): _LockedPro is documented as DISCIPLINE, not a
security boundary (introspection can always reach the client) — the guarantee rests on the lint +
convention. __getattribute__+__slots__ still closes the casual `.pro._real`; __reduce__ explicitly
rejects pickling (Windows spawn). PRO001 expanded to flag `from tushare import pro_api|DataApi` (catches
aliasing), DataApi() construction, object.__getattribute__(..., "_real"|"_base_sleep"), and .__closure__
introspection. AGENTS.md §1 aligned (external .pro is locked+spaced but NOT retried — prefer fetch_*).
Major 2 (watchdog lost QA binding + mutated progress state): split compute_contiguous_watermark (PURE,
no persist — the watchdog uses it) from contiguous_watermark (writer). The heartbeat is QA-BOUND
(qa_ok + floor + a manifest_set_digest over (floor, target]); the watchdog requires BOTH the recomputed
watermark == expected AND a heartbeat certifying qa_ok for this target/floor/digest before it reports OK
or clears the alert — a QA-failed-but-manifests-complete run stays red.
Major 3 (weak/incomplete digest not build-bound): _raw_input_manifest is a full-CONTENT SHA-256 over
the fresh-window per-date files (+ cyq_perf, + report_rc) — no size+mtime collision; the 256-bit root is
recorded in the report + handoff and RE-VERIFIED before publish (phase_publish re-hashes under the lock
and refuses on mismatch — fail closed). Window-scoped to (parent_end, target_end] so legitimate forward
daily progress after target_end never false-fails the re-verify.
Major 4 (unattested/future floor): _provider_floor validates day.txt syntax + ascending order, requires
the tail == provider_build.json provider.calendar_end_date AND that tail be a real open SSE session in
trade_cal, inside the maintenance transaction; floor > target (calendar ahead of reality) now ALERTS
instead of returning success.
Major 5 (rollback deletes a pre-existing working task): the installer exports both task XML definitions
BEFORE mutating; on a half-failed pair install it restores the previous daily definition (or deletes it
only if it did not pre-exist), and persists a backup if the restore itself fails.
Minors: rate spacing is fail-closed (if the shared next-allowed can't be read/written, it sleeps
in-band under the API lock — never zero); write_session_status requires type(required_ok) is bool; the
daily job uses a 900s lock timeout + soft-skip (filelock.Timeout) instead of blocking behind a monthly
build until its 4h task limit kills it.

VERIFICATION
422 tests pass + 9 skipped across the whole tests/data_infra/ suite (+ calendar_policy), including new
tests: forged-env-no-bypass multiprocess, MarketDataError raise + no-write, missing-session reject,
provider-floor attestation (mismatch/unsorted/future), watchdog-requires-QA-heartbeat, spacing-fail-
closed, _LockedPro pickle-reject, pit_backend adj fail-closed, raw-input-manifest content-hash byte-swap.
PRO001 lint clean (+ positive catch of all 4 bypass forms). 12 files compile + 3 script import-smoke.
C-4 scheduled-task registration stays HELD for the operator (§13).

RESIDUALS I AM DISCLOSING (please scrutinise)
- The monthly bump's end-to-end path (_build_impl under the lock, verify-before-publish in phase_publish)
  is a multi-hour operator-gated run I CANNOT integration-test here; I unit-tested _raw_input_manifest
  and the helpers, and verified no lock-acquiring subprocess is nested inside the lock scope by grep.
- The pit_backend guard's "no false-block" claim rests on a 48-file SAMPLE scan (clean), not the full
  ~4500-file tree; the guard is fail-closed by design, so a genuine legacy hole would surface as a
  precise BuildGateError for the operator to fix, not a silent corruption.

RE-REVIEW QUESTIONS
1. Blocker 1: is the lock model now correct — catch-ups self-lock, build holds one in-process lock, no
   env boolean? Is holding raw_maintenance_lock across the multi-hour in-process build acceptable given
   the daily job's 900s-timeout soft-skip, or is there a starvation/priority-inversion path? Any nested
   subprocess inside the lock scope that re-acquires it (I claim none)?
2. Blocker 2: does per-row continuity fully close the missing-session hole for the live SSE-only calendar
   AND on the fresh forward-fetch + merged frames? Any valid calendar shape (half-day, first-of-history)
   that would now FALSE-REJECT? Are _open_days + resolve_last_complete_session the only date consumers
   that needed dedup?
3. Blocker 3: is raising MarketDataError (+ atomic write, prior preserved) + the pit_backend fail-closed
   guard the right non-ignorable design? Is the 0.98 post-merge non-null adj coverage floor right, or
   should it be 1.0 for a present session? Does removing the fillna(1.0) risk any LEGITIMATE NaN-adj row
   the builder used to tolerate (I argue raw daily is long-format = always priced, so a NaN is a hole)?
4. Major 2/3/4: is the QA-bound heartbeat (qa_ok + floor + manifest digest) sufficient to prevent a
   stale/cross-run green? Is the content-manifest window-scoping to (parent_end, target_end] correct for
   verify-before-publish (immutable once complete), or is there an append path that mutates a past
   session's file? Is binding the floor to provider_build.json.calendar_end_date the right attestation?
5. Any NEW hole from this round: the _build_impl refactor (5 params threaded), the manifest re-hash cost,
   the soft-skip returning 0 (does the watchdog still catch a persistent gap?), the task-restore path for
   a Password-logon task.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
