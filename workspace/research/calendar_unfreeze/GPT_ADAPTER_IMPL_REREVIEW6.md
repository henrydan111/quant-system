# GPT §10 impl re-review #6 — fold of re-review #5's P0 (lock leaf FILE_SHARE_DELETE)

Independent GPT‑5.5 Pro reviewer. Re-review #5 confirmed the validate-then-reopen TOCTOU is closed and
that P0-1 (request-spec binding) holds, but reproduced a NEW P0: the handle-bound lock leaf allowed
`FILE_SHARE_DELETE`, so a held lock file could be unlinked cross-process and a second holder acquired a
lock on a NEW file at the same pathname. This is the fold.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · fold commit
**`ee37c93`**. Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
Files: `scripts/recovery_write_broker.py`, `tests/data_infra/test_recovery_quartet.py`.
Suite **222 passed**.

## The fix (exactly your recommendation)
- `_nt_open_relative(..., share: int = None)` — an optional sharing mask. The **default is unchanged**
  (`FILE_SHARE_READ|WRITE|DELETE`), so `open_for_write`, `mkdirs` and the directory-chain walk keep
  their existing semantics.
- `file_lock` opens the **lock leaf** with `FILE_SHARE_READ | FILE_SHARE_WRITE` — **no
  FILE_SHARE_DELETE**. A held lock file can no longer be unlinked or `os.replace`'d, so the pathname's
  identity cannot switch under the holder.

Handle-relative opening closed the path-**swap** TOCTOU; this closes the identity-**switch-by-deletion**
variant. Both were the same underlying error: *the lock must be bound to a file OBJECT, not to a name.*

## Cross-process regressions (fail on `b8a2b6c`)
- `test_held_lock_file_cannot_be_unlinked_or_replaced_crossprocess` — while `execution_guard` is held, a
  **separate process** `os.unlink` FAILS and an `os.replace` usurp FAILS; a second guard stays **BUSY**;
  after release the file still exists and is re-acquirable.
- `test_held_ledger_lock_file_cannot_be_unlinked_crossprocess` — the same for the unified
  `RecoveryPaths._lock` leaf (the hot per-append lock).
- `test_write_path_still_allows_delete_sharing` — control proving only the LOCK leaf is restricted;
  ordinary broker writes keep delete-sharing so staged outputs remain replaceable/removable.

Both child-process probes assert on the child's own exit report (`FAILED:<ErrorType>`), i.e. the
deletion is refused by the OS, not merely by our code path.

## Standing pending (per your prior rulings, unchanged)
before §13: F10 fresh-process/write-surface test; the `authorize-fetch` CLI. before A01 live release:
`update_daily_data` → `merge_daily_legs`. before promotion: the output-density gate. before report_rc
fan-out: its digest producer.

## Questions
1. Does dropping `FILE_SHARE_DELETE` on the lock leaf discharge this P0 — is **fan-out to the remaining
   26 families** now unblocked?
2. Any residual lock-identity, path-escape, replay, or race you can still reproduce (including on the
   parent directory components, which still use the default share mask)?

Suite: **222 passed** (coordinator 78 / ledger 41 / promotion 40 / broker 9 / aux 3 / quartet 51).
`--fetch` exits 3; no Tushare call was made.
