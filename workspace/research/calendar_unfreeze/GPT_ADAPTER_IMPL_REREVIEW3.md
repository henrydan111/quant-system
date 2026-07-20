# GPT §10 impl re-review #3 — fold of re-review #2's concurrency/atomicity residuals

Independent GPT‑5.5 Pro reviewer. Re-review #2 held Gate B on six reproduced residuals (claim replay,
pre-mode legacy fetch, direct LiveExecutor, abandon race, non-LedgerError IN_FLIGHT, consolidation
TOCTOU). This is the fold. The invariant class applied: **a validated fact is CONSUMED in the same
critical section, and mutual exclusion is a LOCK, not a narrative.**

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · fold commit
**`00351b0`**. Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
Files: `scripts/recovery_ledger.py`, `scripts/recovery_adapters.py`,
`tests/data_infra/test_recovery_quartet.py` (42 tests), `tests/data_infra/test_recovery_ledger.py`
(fixture capability). Suite **213 passed**.

## Finding → fix
| # | your finding (reproduced) | fix |
|---|---|---|
| Claim replay | two presenters of the same valid Claim both passed validation → two wire calls | (a) a CROSS-PROCESS **run-execution FileLock** (fresh instance per call — deliberately NON-reentrant even in-process) held for the whole dispatch→call→close span; (b) the claim is **CONSUMED**: `lease_dispatch_started` written in the SAME `rp._lock` critical section as the validation, before any call. A concurrent presenter refuses at the lock; a later one refuses on dispatched/consumed |
| Legacy pre-mode | fetch first, declare `live_authorized` after → certified data without §13 | `fetch_page` is **DEFAULT-OFF** (`_legacy_fetch_enabled=False`; only the ledger battery flips it per instance) AND a declared run mode refuses regardless of the flag — both refusals fire before any lease and before the callable |
| Direct LiveExecutor | `run_page` straight to `fetch_page_once`, no ledger/mode/auth | `run_page` demands a **ONE-SHOT dispatch token** minted by the ledger inside the dispatch critical section (`consume_dispatch_token` pops it); no/guessed/replayed token refuses before touching the fetcher. Discipline vs casual misuse per the scoped threat model (the `_LockedPro` pattern); deliberate in-process bypass stays the lint's job |
| Abandon race | abandon mid-request → retry succeeded → zombie ALSO closed the old lease (two page-1 attempts) | `abandon_orphan_leases` **REQUIRES the run-execution lock** (short timeout — a live worker's span makes it refuse); **second guard:** `_close_lease_record` refuses an ABANDONED/FAILED lease outright, so even a worker that crashed between guards can never record a stale attempt |
| Non-LedgerError IN_FLIGHT | Arrow serialization inside the close escaped per-site handlers | a **total `BaseException` safety net** around the whole post-dispatch body closes the lease as `lease_failed` (idempotent — skips when already consumed) |
| Consolidation TOCTOU | singleton check and final event not in one critical section | `consolidate_family` runs ENTIRELY under the run-execution lock; a second consolidator serializes at the lock, then refuses on the `family_consolidated` event it sees inside it. Crash mid-way leaves NO event → the deterministic redo is idempotent |

Your question-2 ruling implemented exactly: the run-lifetime lock covers claim→call→close on the
worker side; abandon only proceeds after acquiring it; close refuses abandoned leases as the second
protection.

## The regressions you asked for (each fails on `7d019f7`)
- `test_valid_claim_replay_cannot_reach_the_vendor_twice` — a REENTRANT executor re-presents the SAME
  claim mid-flight → refuses at the busy lock; sequential replay → consumed; **executor invocations == 1**.
- `test_abandon_refused_while_a_worker_holds_the_execution_lock`.
- `test_abandoned_lease_can_never_close` — zombie's stale claim refuses at binding AND a direct
  `_close_lease_record` refuses at the second guard; exactly ONE attempt row survives.
- `test_legacy_fetch_page_is_default_off_and_mode_refused` — pre-mode default-off + declared-mode
  refusal even with the battery capability; callback never invoked either way.
- `test_direct_live_executor_call_is_not_a_thing` — no token and guessed token both refuse; the
  fetcher spy records ZERO calls.
- `test_any_post_claim_exception_closes_the_lease` — a function-object poison column dies at
  serialization; next claim is RETRY_PAGE, not IN_FLIGHT.
- `test_consolidation_serializes_on_the_execution_lock` — refuses while the lock is held elsewhere,
  consolidates exactly once after.

## Notes for your verification
- The run-execution lock is `filelock.FileLock` on `<run>/ledger/run_execution.lock`; fresh instance
  per operation so two objects in ONE process also mutually exclude (Windows byte-range lock).
- The dispatch token is process-local by design: it exists only between dispatch and close of one
  call; a crash forfeits it (the lease closes via the net or abandon). It is NOT the correctness
  boundary — the durable `lease_dispatch_started` marker is.
- `run_family`'s per-request loop is unchanged: claims and fetches serialize naturally on the lock.

## Standing pending items (per your prior ruling, unchanged)
before §13: F10 fresh-process/write-surface test; the `authorize-fetch` CLI. before A01 live release:
the `update_daily_data` → `merge_daily_legs` refactor. before promotion: the output-density gate.
before report_rc fan-out: its digest producer.

## Questions
1. Do these six discharge Gate B — is **fan-out to the remaining 26 families** now unblocked?
2. Any residual replay/bypass/race you can still reproduce in the claimed path, the abandon flow, or
   consolidation?

Suite: **213 passed** (coordinator 78 / ledger 41 / promotion 40 / broker 9 / aux 3 / quartet 42).
`--fetch` exits 3; no Tushare call was made.
