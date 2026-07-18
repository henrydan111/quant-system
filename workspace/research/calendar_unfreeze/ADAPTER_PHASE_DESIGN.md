# Adapter phase — design + threat model (review unit: interface + A01 reference)

Status: DESIGN (pre-implementation). One review unit = the adapter interface + the A01 `market/daily`
reference adapter + its pre-fetch test matrix. Fan-out (the other 29 families) is a SEPARATE unit after
A01 is blessed. No Tushare call; `--fetch` stays exit 3 until §13.

Grounding (read before reviewing): the sign-off gate is open (31 signed, `--plan` = 30
`BLOCKED(UNBOUND callable)` + A07 held); ledger `fetch_page(rid, page, call, terminal_claim)` where
`call` is a ZERO-ARG callable making EXACTLY ONE vendor call and returning a DataFrame (the ledger owns
the lease/invoke/record/hash); plan-row shape `_PLAN_REQUIRED` = {request_id, endpoint, dataset, params,
partition, empty_policy, receipt_output, natural_key, content_dedup_key, page_limit, pagination_mode,
max_content_dups} (+ contract_sha256, doc_sha256); `RecoveryPaths` = {root (C:-rooted), staging_data,
ledger_path, plan_path}; `request_id = hash(endpoint, params, partition)`.

## 1. The core simplification — the adapter NEVER touches disk
The adapter is a PURE FETCH function: `call() -> DataFrame`, in memory. ALL persistence (receipts,
consolidated outputs, promotion) is owned by the ledger + the no-follow write broker under `staging_data`.
Consequence: the adapter has NO `StorageManager.insert_*`, NO parquet writes, NO log files — so the
verified E: leak points (import-time handlers, `fetch_bucket_a` DATA/LOGS, `main()` reference downloads)
are structurally avoided, not just patched. The only residual E: risk is the fetcher CONSTRUCTION
(config.yaml → E: paths, import-time logging); the adapter neutralizes that (below) and a write-surface
allowlist test proves zero writes outside run-root.

## 2. Interfaces (three pieces)

### 2a. `AdapterSpec` (per matrix owner) — declarative, no I/O
```
partition_of(request: dict) -> str          # per-date: request["trade_date"]; per-period: ["period"];
                                            # per-stock: ["ts_code"]; per-(period,type): f"{period}_{rt}"
receipt_output_of(endpoint, request, page) -> str   # RELATIVE path under staging_data, per (endpoint,
                                            # request, page); distinct per leg — the ledger re-checks
                                            # containment + no-share
tushare_call(fetcher, endpoint, request, page_limit, offset) -> Callable[[], DataFrame]
                                            # binds ONE class-method call (never main()); e.g.
                                            # lambda: fetcher.fetch_daily_data(trade_date=req["trade_date"])
                                            # paged legs pass limit=page_limit, offset=offset
merge(endpoint_frames: dict[str, DataFrame]) -> DataFrame     # multi-source only (A01); single-source
                                            # returns the one frame unchanged
```
`natural_key`, `content_dedup_key`, `max_content_dups`, `empty_policy` come from the MATRIX row +
signed contract, never from the adapter (the adapter cannot widen its own key).

### 2b. Plan builder `build_plan_rows(spec, contracts) -> list`
For each `source_endpoint`, `resolve_population(contract[ep].request_population)` → one plan_row per
(endpoint, request): `params=request`, `partition=spec.partition_of(request)`,
`receipt_output=spec.receipt_output_of(...)`, `page_limit`/`pagination_mode` from the contract's
`pagination_spec`, `empty_policy`/`natural_key`/`content_dedup_key`/`max_content_dups` from
matrix+contract, `contract_sha256`/`doc_sha256` from the signed contract. A01 → 3 legs × 4493 dates =
13,479 rows, each its own receipt; `assert_multi_source_merge_coverage` already proves the 3 legs cover
the same population.

### 2c. Fetch orchestrator `run_family(spec, contracts, call_provider, *, authorization)`
1. `plan = build_plan_rows(spec, contracts)`; `freeze_request_plan(ledger, plan, contracts, declared_families={spec.output_family})`.
2. per request row: page-drive —
   ```
   off = 0; page = 1
   while True:
       call = call_provider(spec, ep, request, page_limit, off)   # zero-arg
       n = ledger.fetch_page(rid, page, call, terminal_claim=<computed>)
       if pagination_mode == "single_page": break
       if n < page_limit: break            # short page = terminal (ledger checks the trailing-empty rule)
       off += n; page += 1
   ```
   then `ledger.verify_request(rid)` (dense/non-empty) or `ledger.confirm_empty(rid)` (sparse empties).
3. consolidation (merge legs per partition into the family output) + promotion run AS SEPARATE, later
   steps through the promotion SM — NOT inside `run_family`.

## 3. The §13 gate (where the real vendor call is authorized)
`call_provider` is the seam. TWO implementations:
- **`synthetic_call_provider(fixtures)`** — returns canned DataFrames; used by the pre-fetch test matrix.
  Never imports tushare.
- **`live_call_provider(fetcher, token)`** — binds `fetcher.fetch_*`; constructed ONLY when an explicit
  §13 `FetchAuthorization` (a token the USER supplies at the CLI, not a default) is present. `cmd_fetch`
  without it stays `REFUSED, exit 3`. The authorization is checked at orchestrator entry AND is required
  to CONSTRUCT the fetcher (no fetcher, no possible call). The pre-fetch test matrix runs the full
  orchestrator with the synthetic provider, so 100% of adapter logic is covered with zero Tushare risk.

## 4. Fetcher construction (the one residual E: surface)
`live_call_provider` builds `TushareFetcher` with: every path arg from `RecoveryPaths` (no config.yaml
default root); logging reconfigured to the run-root (import-time E: handlers removed/redirected BEFORE
construction); `ts.set_token()` token-cache write either avoided or its exact path allowlisted. A
write-surface allowlist monitor test asserts the ONLY writes during a full synthetic A01 run are under
run-root + the machine-global api-lock namespace — any other path FAILS the test.

## 5. A01 (the concrete first adapter)
- 3 legs: `daily` (single_page 6000-safe), `daily_basic` (single_page), `adj_factor` (offset_paged 5000).
- `partition_of = request["trade_date"]`; `tushare_call` binds `fetch_daily_data` / `fetch_adj_factor`
  per date; `merge` = left-join daily_basic + adj_factor onto daily on `(ts_code, trade_date)`.
- population = 4493 SSE sessions (reference-pinned); each leg verified; merged per-date output
  `market/daily/<yyyy>/daily_<date>.parquet`.

## 6. Threat model (FROZEN before implementation)
- **Trusted:** the ledger (owns lease/invoke/record/hash/verify/terminal proofs), the no-follow broker
  (handle-relative writes), the signed contracts + `RecoveryPaths`, the promotion SM.
- **Untrusted:** (a) the adapter's `call` RESULT — a DataFrame the ledger hashes+counts ITSELF, never a
  claimed count; (b) the fetcher class as a DRIVER — its defaults point at E:, so all paths are injected
  and the write-surface test is the proof; (c) the vendor RESPONSE schema — checked vs signed
  `required_fields` in `verify_request`.
- **§13 authorization** is the SOLE authority for a real vendor call; the test path cannot reach tushare
  (no fetcher constructed).
- **In scope:** E: write leaks, path defaults, truncation via wrong pagination, crash-resume mid-plan,
  dense-refuse vs sparse-canary empties, schema drift, a contract edited mid-flight (re-bind on every
  call), receipt containment.
- **Out of scope (user directive 2026-07-16):** mid-operation adversarial races (handle swaps, ADS,
  install-checkpoint swap); promotion is HUMAN-DRIVEN per family.
- **Acceptance (A01):** a full synthetic-provider `run_family(A01)` produces verified requests for all 3
  legs + a merged per-date output, with (i) ZERO writes outside run-root (allowlist monitor), (ii) real
  Tushare calls impossible without a §13 token, (iii) the pre-fetch test matrix (single/exact-limit
  multipage+trailing-empty/retry/partial-crash+resume/dense-empty-refusal/sparse-canary/null+dup-key/
  schema-drift/merge-coverage/containment) all green.

## 7. Tracked preconditions carried from sign-off (NOT this unit's scope)
(a) per-date/period OUTPUT-density gate (consolidation); (b) fina_mainbz revision-timing probe
(formal-PIT quarantine); (c) fina_indicator_vip §13 period-discovery probe (sign A07). These gate
PROMOTION, not adapter construction.

## Open design questions for the reviewer
1. Is "adapter never touches disk; ledger owns all persistence" the right boundary, or does any family
   need adapter-side staging before the receipt?
2. Is the `call_provider` seam the right §13 chokepoint, or should the token gate sit lower (inside
   `fetch_page`)?
3. A01 merge at CONSOLIDATION (3 separate leg receipts) vs at fetch — is per-leg-receipt + consolidation
   merge correct given `assert_multi_source_merge_coverage` already validates leg population parity?
