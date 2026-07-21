# GPT §10 impl re-review #7 — fold of re-review #6's P0 (lock ancestor chain)

Independent GPT‑5.5 Pro reviewer. Re-review #6 confirmed the leaf `FILE_SHARE_DELETE` fix but
reproduced the parent-directory window (the residual I had flagged for you to probe). This is the fold.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · fold commit
**`4a00036`**. Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
Files: `scripts/recovery_write_broker.py`, `tests/data_infra/test_recovery_quartet.py`.
Suite **225 passed**.

## The fix (exactly your recommendation)
`share` now threads through the **whole** lock chain:
- `_root_handle(share=None)` — default unchanged.
- `_dir_handle_chain(rel_parts, *, create, share=None)` — propagates to the root AND every intermediate
  component.
- `file_lock` uses `FILE_SHARE_READ | FILE_SHARE_WRITE` for **root + intermediates + leaf**.

Defaults are unchanged everywhere else (`open_for_write`, `mkdirs`, ordinary chain walks keep
`READ|WRITE|DELETE`), so only lock chains are restricted.

This is the **third face of one root error** — *a lock must bind a file OBJECT, not a name*:
#4 closed the ancestor **path-swap** (junction) variant; #5 the leaf **identity-switch-by-deletion**;
#6 the ancestor **rename-while-open**.

## Regressions (cross-process, fail on `ee37c93`)
- `test_parent_dir_cannot_be_swapped_in_the_parent_open_to_leaf_open_window` — wraps
  `_dir_handle_chain` to ARM the attack in the **exact** window you exploited (fires the instant the
  parent handle is returned, before the leaf opens): the child `rename`+`mkdir` **FAILS**, the lock
  lives at the real pathname, no `ledger_moved` exists, and a second guard stays **BUSY**.
- `test_run_root_cannot_be_renamed_while_a_lock_is_held` — the run root cannot be renamed under a held
  guard.
- `test_ledger_lock_parent_chain_is_also_delete_protected` — the unified `RecoveryPaths._lock` chain has
  the same protection.
- **Your flagged test gap, fixed:** `test_write_path_still_allows_delete_sharing` now unlinks **while
  the write handle is OPEN** (proving ordinary writes retain delete-sharing); the previous version
  unlinked after close and proved nothing about the share mask.

All child-process probes assert on the child's own report (`SWAP_FAILED:<ErrorType>` /
`FAILED:<ErrorType>`), i.e. the OS refuses, not our code.

## Standing pending (per your prior rulings, unchanged)
before §13: F10 fresh-process/write-surface test; the `authorize-fetch` CLI. before A01 live release:
`update_daily_data` → `merge_daily_legs`. before promotion: the output-density gate. before report_rc
fan-out: its digest producer.

## Questions
1. Does hardening the full ancestor chain discharge this P0 — is **fan-out to the remaining 26
   families** now unblocked?
2. Any residual lock-identity, path-escape, replay, or race you can still reproduce? In particular I'd
   value your read on whether any OTHER broker caller (not just locks) needs the restricted share mask,
   and whether the volume root / drive-level components are in scope for this class.

Suite: **225 passed** (coordinator 78 / ledger 41 / promotion 40 / broker 9 / aux 3 / quartet 54).
`--fetch` exits 3; no Tushare call was made.
