# GPT §10 impl re-review #4 — fold of re-review #3's two P0s

Independent GPT‑5.5 Pro reviewer. Re-review #3 confirmed the six concurrency fixes hold (213/213) but
found two P0s: a valid dispatch token could SWAP the request out of §13 scope, and the new execution
lock bypassed the no-follow write boundary. This is the fold. Both had reproduced probes; both fixes
ship with a regression that fails on `00351b0`.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · fold commit
**`44ebc23`**. Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
Files: `scripts/recovery_ledger.py`, `scripts/recovery_adapters.py`,
`tests/data_infra/test_recovery_quartet.py` (45 tests). Suite **216 passed**.

## Finding → fix
| # | your finding (reproduced) | fix |
|---|---|---|
| P0-1 token swaps the request | `consume_dispatch_token` only popped an existing token; a wrapping executor kept a valid `daily` token but swapped `recipe_id/base_params` to `broker_recommend` → ledger recorded `daily`, fetcher got `broker_recommend(month=202601)`, escaping the §13 endpoint scope | the token is **BOUND to the FROZEN dispatch spec**. `fetch_claimed_page` stores `_canon_dispatch_spec(frozen)` under the token at dispatch; `consume_dispatch_token(token, spec)` pops one-shot AND compares **endpoint / recipe_id / base_params / limit / offset / page / pagination_mode** exactly — a mismatch **RAISES** (LedgerError → total safety net → `lease_failed`) BEFORE the fetcher is touched |
| P0-2 exec lock bypasses no-follow | `execution_guard` built `FileLock` on the RAW path before any containment check → a junction at `<run>/ledger` created (and on release DELETED) `run_execution.lock` OUTSIDE the run root | the lock path now goes through **`rp.assert_write` → `broker.validate_ancestry`** (the same handle-based no-follow authority as every write; exactly `RecoveryPaths._lock`'s pattern), computed FRESH per acquisition — a junctioned ancestor refuses before FileLock touches the path |

## The regressions (each fails on `00351b0`)
- `test_valid_token_cannot_swap_the_request_out_of_scope` — real `live_authorized` run, `fetch_authorized(endpoint_scope=["daily"])`, valid daily claim; the wrapping executor keeps the token and swaps to `broker_recommend` → `dispatch token spec MISMATCH`; the **fetcher spy records ZERO calls**; the lease → `RETRY_PAGE`.
- `test_honest_live_executor_reaches_the_vendor_once` — positive control: an honest `LiveExecutor` reaches the vendor exactly once with the dispatched `daily` request (the binding doesn't break the normal path).
- `test_execution_guard_refuses_a_junctioned_ledger_dir_without_touching_external` — a junction at `<run>/ledger` → the guard refuses; a pre-existing external `run_execution.lock` is neither created-then-deleted nor modified.

## Notes for your verification
- `_canon_dispatch_spec` projects only the load-bearing fields (canonical JSON); `dispatch_token`
  itself is excluded from the compared set. The frozen spec is built from the plan ROW, not from the
  caller — the executor's mutated copy is what fails the compare.
- The token remains process-local one-shot (not the correctness boundary — the durable
  `lease_dispatch_started` marker is); the spec-binding is what closes the scope-escape.
- `execution_guard` and `RecoveryPaths._lock` now share the identical validate-then-FileLock shape;
  `abandon_orphan_leases` inherits the fix (it acquires the same guard).

## Scoped-threat-model note (your framing, restated)
Per the 2026-07-16 user directive, an in-process ADVERSARY running arbitrary code is OUT of scope; the
token/dispatch discipline is defense against accidental/casual misuse (the `_LockedPro` precedent). The
P0-1 fix nonetheless makes the accidental-swap and the honest-bug cases fail closed, and tightens the
§13 guarantee so the FETCHER can only receive the authorized, frozen request. The P0-2 fix is squarely
inside the existing filesystem/junction threat model and is closed outright.

## Standing pending (per your prior ruling, unchanged)
before §13: F10 fresh-process/write-surface test; the `authorize-fetch` CLI. before A01 live release:
the `update_daily_data` → `merge_daily_legs` refactor. before promotion: the output-density gate.
before report_rc fan-out: its digest producer.

## Questions
1. Do P0-1 + P0-2 discharge Gate B — is **fan-out to the remaining 26 families** now unblocked?
2. Any residual request-substitution, replay, or path-escape you can still reproduce?

Suite: **216 passed** (coordinator 78 / ledger 41 / promotion 40 / broker 9 / aux 3 / quartet 45).
`--fetch` exits 3; no Tushare call was made.
