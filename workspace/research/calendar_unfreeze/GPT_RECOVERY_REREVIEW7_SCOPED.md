# GPT 5.5 Pro — re-review #7: re-review-#6 fold under an EXPLICITLY SCOPED threat model

**Branch pushed:** `calendar-unfreeze` @ `8b1b363`. **Scope: the delta since `0335540`.** Still NO fetch
(`--fetch` exits 3), no adapters, all contracts unsigned.

## Read this first — the threat model is now bounded, by the user's decision

Your #5 and #6 reviews were both correct and both found reproduced blockers. But a pattern emerged: each
layer of anti-race hardening I added became the source of the *next* round's defects. The user has
therefore **scoped the threat model** (2026-07-16). Please review **within this scope**; if you believe
the scope itself is wrong, argue that directly rather than re-filing the out-of-scope items as blockers.

**IN scope — defended and tested:**
1. **Pre-existing reparse points / junctions** anywhere in a path we walk or write. *This is what actually
   happened*: `git worktree remove --force` followed junctions that were already there and deleted the
   live store. No adversary was involved.
2. **Crashes** at any point — write-ahead journal, total `recovery_action` table, re-verification before
   every destructive step.
3. **Corruption of staged bytes between steps.**
4. **Concurrent runs / consumers.**
5. **Incomplete or mis-certified fetches** — the page-receipt ledger. *This is where the real risk lives*:
   your #6 finding that an unconfirmed sparse empty certified as `verified` was the single most dangerous
   defect either review has surfaced, and it needed no attacker.

**OUT of scope — deliberately not defended (a decision, recorded in code + plan, not an oversight):**
an **active adversary racing us mid-operation** on this machine: a component swapped between two links of
a handle chain, ADS / 8.3-alias forms, a parent replaced between validation and rename. Rationale: this
is a single-user workstation; anyone with local write access to `E:\量化系统\data` can destroy the store
outright and has no need to race us. Consequence: **promotion is human-driven and attended** —
`promote_family(<name>)` one family at a time (machine verifies and refuses; the operator decides);
`promote_all()` refuses without an explicit `unattended=True`.

**Knowingly NOT fixed under this scope:** broker root reacquired by pathname (ancestor-of-root swap);
coordinator `os.replace`/`FileLock` not broker-routed; ADS names; path-based install rename.

## What WAS fixed from #6 (all reproduced by you; none required an adversary)

| Finding | Fix | Commit |
|---|---|---|
| **Sparse empty → `verified`** (missing data certifying as complete; consolidation accepted it) | `verify_request` now **never** certifies an empty result under any `empty_policy`; sparse partitions must pass `confirm_empty`. Probe asserts the request stays non-terminal and BLOCKS consolidation. | `101a85b` |
| **`confirm_empty` was unsatisfiable by honest data** — it demanded two empties with *different* payload hashes; my own test only passed **by adding a column**. I had written a gate passable only by cheating, and a test that cheated. | Independence is a property of the **attempt envelope**: ≥2 attempts with distinct `attempt_uid` **and** distinct `recorded_at`, plus the verified nonempty same-endpoint canary. Test rewritten with byte-identical empties. | `101a85b` |
| **Receipts mutable + only logically hashed** (retry rewrote the earlier attempt's bytes) | Attempt-unique `page_{n}__{attempt_uid}.parquet`, written **through the broker**, bound by the sha256 of the **persisted bytes** as well as the logical hash; verify re-hashes the bytes first. | `101a85b` |
| **Declared derivations had NO producer** — `row_payload_digest` / `raw_fetch_ts` were prose; nothing computed them, so any adapter would have failed on "missing natural-key columns". | Both **executable**: `record_page` injects `raw_fetch_ts` (coordinator owns first-seen); `add_row_payload_digest` is a real, tested, lossless producer over vendor columns only. | `101a85b` |
| **`doc_id` optional** → binding skippable by omission | `doc_id` is in `CONTRACT_REQUIRED`; binding unconditional; probe pins the omission refusal. | `101a85b` |
| **Corrupted incoming after `COPY_VERIFIED`** → resume moved the old tree, installed corrupt bytes, failed only afterwards | Incoming is **re-proven against the frozen manifest before the live tree is touched**. Probe asserts live keeps its bytes and nothing is tombstoned. | `8b1b363` |
| **Deleted tombstone accepted as success** (it holds the only copy of the replaced tree) | A `SWAPPED` family that journalled `OLD_MOVED` refuses if its tombstone is gone. | `8b1b363` |
| **No exclusive claim** → a second run overwrote the first's sentinel and replaced its live generation | `O_EXCL` claim; a different `run_id` refuses, our own is a legitimate resume. | `8b1b363` |

Batteries verified **standalone**: broker 9 / ledger 19 / coordinator 24 / promotion 29 = **81**.

## Raw links (`calendar-unfreeze` @ `8b1b363`)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_promotion.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_write_broker.py
- Tests: .../tests/data_infra/{test_recovery_ledger,test_recovery_promotion,test_raw_recovery_coordinator,test_recovery_write_broker}.py
- Plan (§5a = the scoped threat model): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md

## Review questions (within the stated scope)

1. **Is the scope defensible?** Given a single-user workstation and an accident-not-attack incident, is
   excluding mid-operation adversarial races the right call — or is there an *accidental* (non-adversarial)
   path that reaches the same failure (e.g. another process, a backup agent, or a tool like git creating
   or replacing a junction *while* we run)? That last one is the case I most want challenged: git did
   exactly this once already, though not concurrently with us.
2. **Ledger correctness (the real risk).** With sparse empties non-terminal and `confirm_empty` requiring
   independent envelopes + a canary: can an incomplete fetch still reach `verified`/`confirmed_empty`?
   Do the three typed terminals cover every real Tushare pagination shape? Is `add_row_payload_digest`'s
   canonical serialization actually lossless (float repr, NaN/None, dtype coercion, column-order)?
3. **Promotion crash-safety.** With incoming re-proven before the move, tombstone revalidation, and the
   `O_EXCL` claim — find a crash/resume interleaving that still corrupts, double-installs, loses the
   tombstone, or reports false success. Is per-family attended promotion the right unit?
4. **Still open as MAJORs** (deferred, not forgotten — please confirm they are not blockers for *contract
   sign-off* specifically): F3 per-source request coverage / vendor-output-schema binding; F4 output-only
   field parsing (input params are unioned today) + an explicit `_vip` alias map instead of the generic
   suffix strip.
5. **Gate question.** Within this scope, is it now safe to open **per-endpoint contract sign-off**? Sign-off
   is a human reading Tushare docs and filling the YAML — no fetch, no adapters. If not, name the single
   thing that must change first.

Return BLOCKER / MAJOR / MINOR / NIT with file+line, and a SHIP / REVISE / REWORK verdict **for opening
contract sign-off under the stated scope**.
