# GPT §10 impl re-review #5 — fold of re-review #4's P0-2 (lock TOCTOU)

Independent GPT‑5.5 Pro reviewer. Re-review #4 confirmed P0-1 (token binds spec) is closed and no
request-substitution/replay remained, but held P0-2: the execution lock still had a validate-then-
reopen-by-pathname TOCTOU (a junction swapped into `<run>/ledger` after `assert_write` was followed by
`FileLock(str(path))`, and on release deleted an external lock file). This is the fold.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · fold commit
**`b8a2b6c`**. Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
Files: `scripts/recovery_write_broker.py` (new `file_lock`), `scripts/recovery_ledger.py`
(`execution_guard`), `scripts/raw_recovery_coordinator.py` (`RecoveryPaths._lock` unified),
`tests/data_infra/test_recovery_quartet.py`. Suite **219 passed**.

## The fix — a handle-bound lock primitive (no pathname is ever re-walked)
`NoFollowWriteBroker.file_lock(target)`:
1. `validate_ancestry(target)` — the lexical/handle PRE-FILTER (unchanged; explicitly NOT the boundary).
2. `_dir_handle_chain(parent.parts, create=True)` — opens each parent component RELATIVE to the held
   parent handle (the existing GPT-re-review-#5 F1 primitive; `OBJECT_ATTRIBUTES.RootDirectory` pins
   resolution to the open directory object, so no ancestor swap redirects it).
3. `_nt_open_relative(parent_h, leaf, FILE_OPEN_REPARSE_POINT)` + `_check_handle` — a junction swapped
   into any component opens AS the reparse point and is REFUSED, never followed.
4. `LockFileEx(exclusive)` on THAT handle (poll-with-timeout → a `BUSY` refusal).
5. release = `UnlockFileEx` + `CloseHandle`; the lock file is **NEVER deleted** (deleting a pathname is
   exactly how the old code removed an external file). A persistent zero-byte lock file is standard.

`execution_guard` and `RecoveryPaths._lock` are **both** routed through this one primitive (you flagged
the latter as the same validate-then-path pattern). There is no longer any "validate then open by path"
lock in the codebase.

## The decisive regression (fails on `44ebc23`)
`test_lock_closes_the_validate_then_swap_toctou`: wraps `validate_ancestry` to ARM the attack — the
instant validation returns on the honest path, it `mklink /J`'s `<run>/ledger` to an external dir (the
exact window you exploited). `execution_guard` then opens the handle chain → the junctioned `ledger`
component opens as a reparse point → **REFUSED**; the external `run_execution.lock` is asserted
byte-identical afterward (never opened/created/deleted). Plus `test_handle_lock_provides_real_cross_
object_mutual_exclusion` (a second holder refuses BUSY — the fix didn't weaken the lock) and
`test_handle_lock_file_is_not_deleted_on_release`.

## Notes for your verification
- `file_lock` reuses the broker's existing handle-relative machinery verbatim
  (`_dir_handle_chain`/`_nt_open_relative`/`_check_handle`); only `LockFileEx`/`UnlockFileEx` +
  `_OVERLAPPED` are new ctypes bindings.
- The lock is a real cross-process OS byte-range lock (LockFileEx on the file object), so two processes
  mutually exclude; a fresh handle per acquisition keeps it non-reentrant in-process (an operator
  abandon still cannot slip inside a worker's span).
- `RecoveryPaths._lock` is the hot per-append lock; the whole coordinator + ledger + promotion
  batteries run on the unified primitive (coordinator 78 / ledger 41 / promotion 40 all green), so the
  change is exercised end-to-end, not just by the new tests.

## Standing pending (per your prior rulings, unchanged)
before §13: F10 fresh-process/write-surface test; the `authorize-fetch` CLI. before A01 live release:
`update_daily_data` → `merge_daily_legs`. before promotion: the output-density gate. before report_rc
fan-out: its digest producer.

## Questions
1. Does the handle-bound lock discharge P0-2 — is **fan-out to the remaining 26 families** now
   unblocked?
2. Any residual path-escape, replay, or race you can still reproduce in the lock, the claimed path, the
   abandon flow, or consolidation?

Suite: **219 passed** (coordinator 78 / ledger 41 / promotion 40 / broker 9 / aux 3 / quartet 48).
`--fetch` exits 3; no Tushare call was made.
