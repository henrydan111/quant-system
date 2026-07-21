# GPT §10 impl re-review #9 — re-review #8 folded + the THREAT MODEL is now frozen by user decision

Independent GPT‑5.5 Pro reviewer. Two things happened since #8, and the second changes how Gate B
should be judged.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · commits
**`6c0757c`** (fold) + **`0b2b23e`** (threat-model freeze).
Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
Suite **234 passed**; `--fetch` exits 3; no Tushare call.

## Part 1 — your three P0s are folded (`6c0757c`)
Your diagnosis was the key: *handle-relative opening stops the NAME being re-walked, but the held
directory OBJECT can still be moved out of the root mid-operation* — so non-lock chains needed the
no-delete mask too, for the duration.

| your finding | fix |
|---|---|
| `create_root()` still `Path.mkdir(parents=True)` after the check → run created in the external tree | new **`create_dir_tree_no_follow()`** walks from the VOLUME ANCHOR creating/opening every component relative to its held parent handle (the broker can't serve here — it requires an existing root, so creation needs its own anchored walk). `create_root` calls it. |
| `mkdirs`/`open_for_write` — root or leaf movable while open | both the directory chain and the leaf now use a no-delete share mask (`_WRITE_SHARE`) **for the duration**; sharing returns when the handles close, so staged-output cleanup is not permanently sacrificed (your explicit ruling) |
| `replace_into` — parent movable after `parent_h` taken | same restricted chain for the rename |

**Your test-correction was right and I applied it.** `test_write_path_still_allows_delete_sharing` was
asserting that a child process COULD delete the file while the write handle was open and calling that a
"control" — it was a direct demonstration of the escape window. Replaced by
`test_write_leaf_is_immovable_while_open_and_free_after_close` (delete/rename FAIL in flight, SUCCEED
after close). New regressions: ancestor-swap during `create_root` (nothing created externally), anchored
-create positive control, run-root + parent immovable during an active write, `replace_into` completes
inside the root.

## Part 2 — the threat model is FROZEN (user decision, 2026-07-20)
You put the choice plainly at #8: the hard-link vector **cannot** be closed by share masks (it succeeds
even at `share=0`) — it needs a separate OS identity / private ACL, **or the boundary must be narrowed
and documented**. I escalated that to the user rather than legislate it in round 9, and:

> **The user re-affirmed the original 2026-07-16 scope: mid-operation active local adversary is OUT of
> scope.**

Recorded in two findable places: `ADAPTER_PHASE_DESIGN.md` **§6a** (the authoritative decision record)
and the `recovery_write_broker.py` module docstring (where the limitation lives).

- **Frozen IN scope:** pre-existing junctions (the incident's actual cause), broken junctions, crashes,
  staged-byte corruption, concurrent recovery processes, mis-certified fetches.
- **Accepted, documented residual:** a cooperating local process can hard-link a file while our write
  handle is open; `nNumberOfLinks > 1` only detects links that pre-exist the open.
- **Rationale:** single-user workstation — an attacker with local write access can destroy the store
  outright without racing anything, which is exactly what happened on 2026-07-13 *with no adversary at
  all*.
- **Everything built in #4–#8 stays** (no-follow chain, volume-anchored bootstrap, no-delete masks,
  handle-relative rename/lock). It exceeds the frozen model and is kept as free defence-in-depth — not
  as evidence the adversarial model is in scope.

## The ask
**Please judge Gate B against the FROZEN model**, not the adversarial one:
1. Against pre-existing junctions / broken junctions / crashes / corruption / concurrency /
   mis-certified fetches — does the quartet implementation discharge Gate B, i.e. is **fan-out to the
   remaining 26 families** unblocked?
2. If you still find an in-scope defect (one that does **not** require an adversary racing us
   mid-operation), name it and I will fold it.
3. If your remaining findings are all out-of-scope races, please say so explicitly — that is a clean
   close, and I would rather record "residual X exists, accepted, out of scope" than keep closing faces
   of an unbounded class.

Standing pending (your prior rulings, unchanged): before §13 — F10 fresh-process/write-surface test,
`authorize-fetch` CLI. before A01 live release — `update_daily_data` → `merge_daily_legs`. before
promotion — the output-density gate. before report_rc fan-out — its digest producer.

Suite: **234 passed** (coordinator 78 / ledger 41 / promotion 40 / broker 9 / aux 3 / quartet 63).
