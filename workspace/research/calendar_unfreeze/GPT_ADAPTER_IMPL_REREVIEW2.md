# GPT §10 impl re-review #2 — fold of Gate B's REWORK (3 BLOCKERs + 1 MAJOR + 2 minors)

Independent GPT‑5.5 Pro reviewer. Your bundled review CONFIRMED Gate A (the quartet interface is
frozen) and returned REWORK on Gate B with three reproduced BLOCKERs + one MAJOR + two minor notes.
This is the fold. Every fix ships with a regression that fails on the pre-fix code.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · fold commit
**`7d019f7`** (on top of the reviewed `5cc3b9a`).
Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
Files: `scripts/recovery_ledger.py`, `scripts/recovery_adapters.py`,
`tests/data_infra/test_recovery_quartet.py` (now 36 tests; full recovery suite **207 passed**).

## Finding → fix
| # | your finding (reproduced) | fix |
|---|---|---|
| B1 | a forged `Claim` (any offset/lease id) was accepted; could verify a skipped page | claim is BOUND to its durable lease: `claim_next_fetch` PERSISTS `offset` in the `lease_open` row; `fetch_claimed_page` requires an exact (request, page, offset, opened_at) match against an EXISTING, UNUSED lease before any executor call; a forged presentation does NOT close the real lease (cannot kill an in-flight fetch); re-checked at close (`_close_lease_record` refuses a response with no matching OPEN lease for that request+page — covers the legacy path too) |
| B2 | legacy `fetch_page` bypassed §13 — a declared live run certified a response with no `fetch_authorized` event | `fetch_page` REFUSES whenever a run mode is declared — before any lease opens and before the callable could run (regression proves the callback is never invoked and no lease_open is appended). The below-contract batteries never declare a mode, which is exactly what scopes them out of production |
| B3 | bundle checked only at `run_family`; consolidation could run after drift and overwrite outputs | `consolidate_family` now (a) recomputes the content-hashed bundle itself — drift refuses; (b) is a SINGLETON per family per run — a repeat refuses (chained verdicts never overwritten); (c) binds the RE-READ output bytes (write → fsync → re-read → compare) before recording the verdict |
| MAJOR | post-claim contract/auth refusal left the lease OPEN forever (permanent IN_FLIGHT); no crash-abandon | every post-claim refusal path now records `lease_failed` (next claim = `RETRY_PAGE`, regression-pinned). Crash-abandon implemented: `abandon_orphan_leases(rid, reason=...)` — the EXPLICIT operator transition (auditable non-blank reason required; `run_family` never calls it; per the attended-recovery model the operator asserts no other process is mid-flight); claim treats `lease_abandoned` as closed+failed → RETRY_PAGE |
| minor | authorization recorded a username, not a SID | the event now records BOTH `os_username` and the actual Windows SID (`whoami /user`; evidence, not the boundary) |
| minor | the battery imported tushare via the shape lint | the lint reads the SOURCE FILE (the text is the fact being linted); the battery genuinely imports no tushare |

## Your deviation rulings, applied
1. ledger-built specs: now discharged per your condition — the supplied Claim is bound to its exact
   durable open lease (request, page, offset, opened_at, unused) before anything runs.
2. bundle-in-genesis retained AND the pre-consolidation recompute added (they guard different edits).
3. dense-empty-at-verify: accepted as-is (your ruling).
4. legacy door: restricted exactly as you specified (refuse once a run mode is declared) + the
   never-invoked regression.
5. RETRY_PAGE + crash-abandon: implemented as above.

## New regressions (each fails on `5cc3b9a`)
`test_forged_claim_with_nonexistent_lease_refused` (executor never invoked),
`test_altered_claim_offset_refused_without_killing_the_lease` (the REAL claim still works after the
forged one refuses), `test_legacy_fetch_page_refused_once_a_run_mode_is_declared` (callback never runs,
no lease trace), `test_consolidation_refuses_a_drifted_bundle_and_repeats` (drift + singleton),
`test_post_claim_contract_refusal_closes_the_lease` (RETRY_PAGE, not IN_FLIGHT),
`test_orphaned_lease_abandon_and_resume` (IN_FLIGHT → abandon → RETRY_PAGE → verified).

## Standing per your pending-item ruling (unchanged by this fold)
- before §13 (not fan-out): F10 fresh-process/write-surface test; the separate `authorize-fetch` CLI.
- before A01 live release: production refactor onto `merge_daily_legs`.
- before promotion/consolidated release: the output-density gate.
- before report_rc fan-out only: its digest producer.

## Questions
1. Do B1–B3 + the MAJOR now discharge Gate B — i.e. is **fan-out to the remaining 26 families**
   unblocked (with the §13-gated items still pending as ruled)?
2. Is the operator-driven `abandon_orphan_leases` (explicit auditable reason, no automatic invocation,
   attended single-operator model) an acceptable crash-abandon shape, or must it also demand a
   process-lifetime run-execution lock artifact before converting orphans?
3. Any residual forged-token or bypass surface in the claimed path you can still reproduce?

Suite: **207 passed** (coordinator 78 / ledger 41 / promotion 40 / broker 9 / aux 3 / quartet 36).
`--fetch` exits 3; no Tushare call was made.
