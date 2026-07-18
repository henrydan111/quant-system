# Adapter phase — design + threat model **v2** (folds GPT design re-review #1: 11 findings)

Status: DESIGN v2 (pre-implementation). Interface-freeze unit = a mocked **vertical quartet**
(A01 `market/daily` + per-stock `income` + event `top_list` + monthly `broker_recommend`); A01 is the
first *implemented* adapter but the interface freezes only after the quartet passes the same machinery
(F11). No Tushare call; `--fetch` stays exit 3 until §13.

v1 verdict was REWORK: the opaque-lambda `call`, caller-computed terminals, constructor-only §13, and
population-parity-as-merge-correctness were all unsound. v2 moves the fetch mechanics INTO the
ledger-owned boundary and makes every call declarative + validated. GPT confirmed the two v1 keepers:
(a) pure adapter / ledger-owned persistence — no family needs adapter-side disk; (b) separate leg
receipts + consolidation merge preserves provenance (population parity alone is NOT merge correctness).

## 0. What changed from v1 (finding → resolution)
- **F1** opaque callable → **`PageCallSpec`** (declarative, serializable), validated by the ledger vs
  the frozen request; a **typed executor** does EXACTLY ONE wire call via new `fetch_*_page_once`
  methods (not `_safe_api_call`, which retries — verified: `for attempt in range(max_retries)`). Retries
  become NEW ledger leases. Recipes/page-preps/merge-rules are hashed into the real `adapter_bundle_hash`.
- **F2** constructor-only §13 → **`FetchAuthorization`** validated INSIDE the ledger lease at every live
  page; immutable run-mode (`synthetic_nonpromotable` | `live_authorized`); promotion refuses
  synthetic/mixed. Credential from secure env/config, never a CLI arg or ledger field.
- **F3** caller-computed `terminal_claim` → **`fetch_page` returns `PageResult(row_count, terminal_kind,
  next_offset)`**; ledger derives the terminal; **`next_fetch_action(rid)`** owns resume.
- **F4** `confirm_empty` missing its canary → **deterministic empty-scheduler** (2nd empty lease, verdict
  DEFERRED until a same-endpoint nonempty canary verifies).
- **F5** response never scoped to the request → **`response_scope_spec`** (equality / range bounds),
  applied page-by-page pre-cert AND post-concat.
- **F6** family-level freeze on a one-plan ledger → **`freeze_run_plan(specs, declared_families)`** once
  per run; `run_family` executes only its already-frozen subset.
- **F7** `receipt_output_of(...page)` contradiction → **`request_output_of(endpoint, request)`** (no page
  arg; page receipts are ledger-owned) + a SEPARATE **`consolidate_family`** step (not in `run_family`).
- **F8** derived digests never produced at fetch → **`prepare_raw_page(endpoint, df)`** registry inside
  the ledger boundary (adds ONLY `derived_fields_for(endpoint)` cols; records vendor-payload hash +
  prepared-receipt hash).
- **F9** population parity ≠ merge correctness → **reuse the production canonical merger**
  (update_daily_data.py: drop aux `close`, 100% positive adj_factor coverage, ≥90% daily_basic coverage,
  one_to_one, no dup keys, target-date equality).
- **F10** synthetic monitor can't prove live construction → add a **fresh-subprocess, network-denied
  live-construction test** (stub tushare; monitor installed BEFORE import; `ts.pro_api(token)`, never
  `ts.set_token()`).
- **F11** A01 alone under-covers the shapes → freeze the interface only after the **quartet**.

## 1. Core boundary (GPT-confirmed): the adapter never touches disk
The adapter is declarative + pure: it emits `PageCallSpec`s and pure transform/merge rules. ALL
persistence (page receipts, per-request outputs, consolidated family outputs, promotion) is owned by the
ledger + no-follow broker under `staging_data`. This structurally avoids the verified E: leak points
(import-time handlers, `StorageManager`, `main()` reference downloads). The one residual surface —
fetcher CONSTRUCTION (config.yaml → E:, import-time logging, credential cache) — is exercised by a
dedicated live-construction write test (F10), not the synthetic run.

## 2. Types (the frozen interface)

### 2a. `PageCallSpec` (serializable — replaces the lambda; F1)
```
PageCallSpec(endpoint: str, base_params: dict, limit: int, offset: int, recipe_id: str)
```
- `base_params` are the request's vendor params (e.g. {"trade_date":"20260102"}); `limit/offset` are the
  page cursor (limit == the signed `pagination_spec.page_limit`; single_page ⇒ limit sentinel, one page).
- `recipe_id` names a registered call recipe (`ADAPTER_RECIPES[recipe_id]`) — a pure function
  `(fetcher, base_params, limit, offset) -> zero-arg one-call thunk`. Recipes are hashed into
  `adapter_bundle_hash`. **The ledger validates `spec.endpoint == frozen.endpoint` and
  `spec.base_params == frozen.params` BEFORE execution** — a spec that names the wrong endpoint/date is
  refused (closes the "wrong closure" hole from the request side; F5 closes it from the response side).

### 2b. `Executor` (the §13 chokepoint lives here; F2)
```
class Executor(Protocol): def run_page(spec: PageCallSpec) -> DataFrame   # EXACTLY ONE wire call
SyntheticExecutor(fixtures)   # no tushare import; used by the pre-fetch test matrix
LiveExecutor(fetcher, authorization: FetchAuthorization)   # constructed only under a valid authorization
```
The ledger invokes `executor.run_page(spec)` INSIDE the open lease. For `LiveExecutor`, the ledger
re-validates the `FetchAuthorization` (scope covers this endpoint, `plan_sha256`/`adapter_bundle_hash`
match the frozen run, not expired) at EVERY page — so even a mis-wired orchestrator cannot reach the
vendor without a live authorization bound to THIS plan.

### 2c. `FetchAuthorization` (non-secret; F2)
```
FetchAuthorization(run_id, plan_sha256, adapter_bundle_hash, endpoint_scope: set, expires_at)
```
Records ONE immutable run mode on the ledger: `synthetic_nonpromotable` (any synthetic page) or
`live_authorized`. **Promotion refuses a run that is synthetic or mixed-mode.** The Tushare credential is
read from secure env/config only after authorization; it is NEVER a CLI argument or a ledger field.

### 2d. `AdapterSpec` (declarative, no I/O)
```
partition_of(request) -> str                     # per-date: request["trade_date"]; per-period: ["period"];
                                                 # per-stock: ["ts_code"]; per-(period,type): f"{period}_{rt}"
request_output_of(endpoint, request) -> str      # RELATIVE per-REQUEST output path under staging_data
                                                 # (NO page arg — page receipts are ledger-owned; F7)
page_call_spec(endpoint, request, limit, offset) -> PageCallSpec
response_scope_spec(endpoint) -> ResponseScope   # how a page's rows must match the request (F5)
merge(endpoint_frames) -> DataFrame              # multi-source only; MUST reuse the canonical merger (F9)
```
`natural_key` / `content_dedup_key` / `max_content_dups` / `empty_policy` come from the MATRIX + signed
contract, never the adapter.

### 2e. `ResponseScope` (F5)
Per-endpoint, matrix/contract-derived: a set of `(column, mode, value)` where mode ∈ {`eq`,
`in_range[lo,hi]`}. E.g. per-date daily ⇒ `trade_date eq request["trade_date"]`; per-stock income ⇒
`ts_code eq request["ts_code"]`; report_rc month range ⇒ `report_date in_range[start,end]`. The ledger
applies it page-by-page BEFORE receipt certification and again after concatenation; a row outside scope
(wrong date/stock — vendor or cache error) REFUSES.

## 3. Ledger-side changes (this phase edits the ledger, not just adds adapters)
- `fetch_page(rid, page, executor, spec)` — validates `spec` vs the frozen request, opens the lease,
  calls `executor.run_page(spec)` (one wire call), runs `prepare_raw_page(endpoint, df)` (F8), applies
  `response_scope_spec` (F5), records the receipt (vendor-payload hash + prepared-receipt hash), derives
  and returns `PageResult(row_count, terminal_kind, next_offset)` (F3).
- `next_fetch_action(rid) -> SKIP_TERMINAL | FETCH(page, offset) | VERIFY | RETRY_PAGE` — lock-protected,
  ledger-owned resume cursor (F3); safe re-entry after a crash / for a second family.
- `prepare_raw_page(endpoint, df)` — trusted registry; adds ONLY `derived_fields_for(endpoint)` columns
  (`row_payload_digest` for top_list/top_inst/block_trade; `report_rc_payload_digest` for report_rc)
  before hashing and before any non-injective normalization (F8).
- terminal derivation (F3): `n > limit` ⇒ REFUSE; `n == limit` ⇒ nonterminal (fetch next offset);
  `0 < n < limit` ⇒ `last_partial`; `n == 0` ⇒ `empty_terminal`. An exact-limit true final page ⇒ one
  trailing-empty call, as today's typed terminal proofs require.

## 4. Orchestration
```
freeze_run_plan(specs, contracts, declared_families)     # ONCE per run (F6): all families' plan rows
run_family(spec, ledger, executor):                      # executes only spec's already-frozen subset
    for rid in spec's requests:
        while True:
            act = ledger.next_fetch_action(rid)           # ledger owns resume + terminal (F3)
            if act.kind == FETCH:
                ledger.fetch_page(rid, act.page, executor, spec.page_call_spec(ep, req, limit, act.offset))
            elif act.kind == RETRY_PAGE: ... (new lease)
            elif act.kind == VERIFY: ledger.verify_request(rid); break
            elif act.kind == SKIP_TERMINAL: break         # already verified (resume)
        # sparse empties (F4): if the request resolved empty, the empty-scheduler opens a 2nd empty lease
        # and DEFERS the verdict until a same-endpoint nonempty canary verifies, then
        # confirm_empty(rid, canary_request_id=<verified canary>); no canary ever ⇒ stays unverified.
consolidate_family(spec, ledger):                        # SEPARATE step (F7), NOT in run_family
    assert consolidation_allowed(family)                 # every constituent request verified
    inputs = load hash-bound request outputs
    merged = spec.merge(inputs)                          # canonical merger (F9)
    broker.write(family_output, merged); ledger.record_consolidation_verdict(inputs->output)
```

## 5. A01 (first implemented adapter; merge reuses production invariants — F9)
- 3 legs: `daily` (single_page), `daily_basic` (single_page), `adj_factor` (offset_paged 5000, via
  `fetch_adj_factor_page_once(trade_date, limit, offset)` — NEW; the current `fetch_adj_factor` takes no
  limit/offset, verified).
- `partition_of = request["trade_date"]`; `response_scope = trade_date eq request`.
- `merge` = the extracted canonical merger from update_daily_data.py: drop `daily_basic.close`, left-join
  daily_basic + adj_factor on `(ts_code, trade_date)`, require output rows == daily, 100% positive
  adj_factor coverage of priced codes, ≥90% daily_basic coverage, one_to_one, no duplicate output keys,
  all rows `trade_date == request`. Runs in `consolidate_family`, NOT `run_family` (F7 acceptance fix).

## 6. Threat model (FROZEN; updated for v2)
- **Trusted:** the ledger (owns lease/executor-invoke/prepare/scope/record/hash/terminal/resume), the
  no-follow broker, signed contracts + `RecoveryPaths` + the matrix, the promotion SM, the recipe
  registry (hashed into `adapter_bundle_hash`).
- **Untrusted:** (a) the executor RESULT — a DataFrame the ledger hashes+counts+scopes ITSELF; (b) the
  `PageCallSpec` — validated vs the frozen request before execution; (c) the fetcher class as a DRIVER
  (paths injected; construction is the one residual surface, tested by F10); (d) the vendor RESPONSE
  schema + scope (`required_fields`, `response_scope_spec`).
- **§13 authorization** validated INSIDE the ledger lease at every live page is the SOLE authority; the
  synthetic path cannot reach tushare (no fetcher constructed) and its run-mode is non-promotable.
- **In scope:** E: write leaks, path defaults, wrong-endpoint/date closures (both request-spec + response
  scope), truncation via pagination, crash-resume mid-run, dense/sparse empties + canary, schema drift,
  mid-flight contract edit (re-bind per page), receipt containment, synthetic-vs-live promotability.
- **Out of scope (user directive 2026-07-16):** mid-operation adversarial races; promotion is
  HUMAN-DRIVEN per family.
- **Acceptance (interface-freeze QUARTET — A01 + income + top_list + broker_recommend):** each runs the
  FULL machinery (freeze_run_plan → run_family → verify/confirm_empty → consolidate_family) under a
  `SyntheticExecutor`, with (i) ZERO writes outside run-root (allowlist monitor) + the fresh-subprocess
  live-construction test (F10) green; (ii) real Tushare calls impossible without a §13 authorization
  bound to the frozen plan; (iii) the pre-fetch test matrix green: single / exact-limit multipage +
  trailing-empty / n>limit refusal / retry-as-new-lease / partial-crash + `next_fetch_action` resume /
  dense-empty refusal / sparse-canary defer + confirm / null+dup key / schema-drift / **response-scope
  wrong-date+wrong-stock refusal** / **prepare_raw_page digest** / merge one_to_one + coverage /
  containment; (iv) promotion refuses the synthetic run-mode.

## 7. Tracked promotion preconditions (unchanged; NOT this unit): per-date/period output-density gate;
fina_mainbz revision-timing probe; fina_indicator_vip §13 period-discovery probe (sign A07).

## Open questions for the reviewer
1. Is the recipe-registry-hashed-into-`adapter_bundle_hash` sufficient to make the `PageCallSpec` path
   tamper-evident, or must the ledger also pin the recipe source?
2. `next_fetch_action` as the SOLE resume/terminal authority — does it fully subsume the old
   caller-driven loop, or is there a page-ordering race between `FETCH` and a concurrent `RETRY_PAGE`?
3. Is the `synthetic_nonpromotable` run-mode + promotion refusal the right synthetic/live firewall, or
   should synthetic and live use physically separate run roots?
