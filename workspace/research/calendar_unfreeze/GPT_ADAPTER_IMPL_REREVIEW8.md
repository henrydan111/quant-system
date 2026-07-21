# GPT §10 impl re-review #8 — fold of re-review #7's two path-escape P0s

Independent GPT‑5.5 Pro reviewer. Re-review #7 confirmed the in-run ancestor-chain fix but reproduced
two escapes **outside the lock subsystem**: the broker's own root bootstrap resolved by pathname, and
`write_json`'s `os.replace` was a raw post-write path re-walk. This is the fold.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · fold commit
**`4e76959`**. Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
Files: `scripts/recovery_write_broker.py`, `scripts/raw_recovery_coordinator.py`,
`tests/data_infra/test_recovery_quartet.py`. Suite **230 passed**.

## P0-1 — volume-anchored root bootstrap
`__init__` and `_root_handle()` both used `CreateFileW(str(self.root))`, which walks the whole name, so
`FILE_FLAG_OPEN_REPARSE_POINT` protected only the final component and a junctioned RECOVERY_ROOT
redirected everything. And a swap performed BEFORE construction made the broker cache the **external**
directory's identity as legitimate — an id comparison alone could never catch that.

**Fix:** `_open_root_from_volume_anchor()` opens `C:\` (the trusted anchor you designated) and walks
**every** component of the run root handle-relative with `FILE_OPEN_REPARSE_POINT` + `_check_handle`.
`__init__` binds the root's object identity through that walk; `_root_handle()` re-walks and re-checks
the identity on every acquisition. A junctioned ancestor refuses at construction AND at every use.

## P0-2 — handle-relative rename
**Fix:** `broker.replace_into(tmp, final)` — parent chain opened handle-relative, temp opened relative
to it with `DELETE|FILE_READ_ATTRIBUTES`, renamed via `NtSetInformationFile(FileRenameInformation)`
with that parent handle as `RootDirectory`. No pathname is re-resolved. `write_json` now calls it.
`copy_into`'s trailing `os.utime` likewise became `SetFileTime` on the **held handle**.

Per your ruling, ordinary writes **keep** their delete/replace sharing semantics — only the safe root
bootstrap is shared by all surfaces; the no-delete share mask stays lock-only.

## Regressions (fail on `4a00036`)
- `test_ancestor_of_root_swapped_after_construction_is_refused` — ancestor junctioned after
  construction: `open_for_write` **and** `file_lock` refuse; nothing appears in the external tree.
- `test_ancestor_junction_present_before_broker_construction_is_refused` — the pre-construction case
  (the one an id comparison can't catch): the broker refuses to construct.
- `test_write_json_rename_cannot_escape_via_a_post_write_parent_swap` — the swap still **SUCCEEDS**
  (proving the window is real), `replace_into` **REFUSES**, and no external JSON exists. I first wrote
  this test in a convoluted form, verified by direct probe that it wasn't passing vacuously, then
  rewrote it in the direct form you see.
- `test_replace_into_refuses_cross_parent_rename` + a positive control that `write_json` still works
  atomically and leaves no temp behind.

## Standing pending (per your prior rulings, unchanged)
before §13: F10 fresh-process/write-surface test; the `authorize-fetch` CLI. before A01 live release:
`update_daily_data` → `merge_daily_legs`. before promotion: the output-density gate. before report_rc
fan-out: its digest producer.

## Questions
1. Do these two discharge Gate B — is **fan-out to the remaining 26 families** now unblocked?
2. Any remaining raw-pathname operation on the write surface you can still reproduce? I have swept for
   `os.replace`/`os.utime`/`os.rename`/`shutil` in the recovery modules and routed the ones I found;
   an independent sweep would be worth more than my own.
3. With `C:\` as the anchor, is the bootstrap now sound in your view, or does the `runs`/`run_id`
   creation path (`create_root`, still `mkdir` by pathname) need the same treatment before fan-out?

Suite: **230 passed** (coordinator 78 / ledger 41 / promotion 40 / broker 9 / aux 3 / quartet 59).
`--fetch` exits 3; no Tushare call was made.
