# Adapter phase — design + threat model **v3** (folds GPT design re-review #2: 6 remaining findings)

Status: DESIGN v3 (pre-implementation). Interface-freeze unit = the mocked **vertical quartet**
(A01 `market/daily` + per-stock `income` + event `top_list` + monthly `broker_recommend`) — which must
also exercise the four PHYSICAL consolidation layouts (F7). A01 is the first *implemented* adapter; the
interface freezes only after the quartet passes. No Tushare call; `--fetch` stays exit 3 until §13.

re-review #2 discharged F6/F8/F9/F10/F11 and held F1–F5, F7. v3's theme: **every fetch-affecting fact is
declarative DATA, frozen into the plan, content-hashed, and enforced by the LEDGER at an atomic
boundary** — no arbitrary function, no caller-derived cursor, no constructible-only authorization.

## 0. Changed from v2 (finding → v3 resolution)
- **F1** recipes were still arbitrary thunks → **`CallRecipe(recipe_id, vendor_method, parameter_map,
  pagination_mode)`** is DECLARATIVE DATA; ONE generic **`fetcher.fetch_page_once(vendor_method,
  **kwargs)`** does exactly one wire call; `recipe_id` is FROZEN in every plan row; the ledger validates
  `recipe_id`/`limit`==contract/`offset`+`page`==claimed-cursor/single-page-sentinel; a lint forbids
  `_safe_api_call` or any loop inside `fetch_page_once`.
- **F2** `FetchAuthorization` was constructible-only → §13 is a hash-chained **`fetch_authorized` LEDGER
  EVENT** written by an explicit user action (auth id, actor, issued/expiry, plan_sha256, bundle_sha256,
  endpoint scope); `fetch_page` validates the EVENT, never a passed dataclass. Run-mode is fixed at
  `run_created`; an executor-mode/run-mode mismatch REFUSES before opening any lease (mixed mode
  unreachable, not merely non-promotable).
- **F3** single_page vs `n>limit`, and a `next_fetch_action→fetch_page` TOCTOU → single_page terminal is
  defined SEPARATELY (page 1, offset 0 → `single_page_contract`, never compared to an offset limit);
  the authoritative op is **`claim_next_fetch(rid)`** which derives the cursor AND opens/reserves the
  lease ATOMICALLY under one lock (concurrent caller sees `IN_FLIGHT`); retry only after a recorded
  failure or an explicit crash-abandon transition.
- **F4** the action enum couldn't express the empty lifecycle → added **`RETRY_EMPTY_CONFIRM`**,
  **`WAIT_FOR_CANARY`**, **`CONFIRM_EMPTY(canary_request_id)`**; `VERIFY` is NEVER returned for an
  entirely-empty sparse request; canary selection is deterministic.
- **F5** `response_scope_spec(endpoint)` lacked the request's values and wasn't frozen →
  **`response_scope_of(endpoint, request) -> ResponseScope`** with the concrete rule-id + values FROZEN
  in each plan row; validated at plan-freeze, page-receipt, and post-concatenation; TYPED date parsing
  for ranges (never string compare).
- **F7** consolidation modeled one `family_output`, but the quartet has 4 physical layouts → a frozen
  **`ConsolidationSpec`** (input grouping, `output_partition_of_row`, `family_output_of`, merge/repartition
  recipe id, confirmed-empty contribution policy, row-conservation/dedup invariants); handles the
  per-stock→per-`end_date` repartition (income, verified at storage/__init__.py) and event/monthly
  layouts.
- **Q1** → one canonical **`adapter_bundle_manifest`** (relative path + sha256 of every call-recipe /
  `fetch_page_once` / response-scope / prepare / merge / consolidation module + the declarative registry
  entries), hash-chained at plan freeze, RECOMPUTED on resume and before live execution/consolidation.
  Git HEAD is insufficient (a dirty relevant file is undetected).

Discharged, retained with the noted riders: **F6** run-level freeze; **F8** `prepare_raw_page` (its
producer ids/source go in the bundle manifest; vendor hash computed BEFORE prep; prep adds only declared
cols); **F9** extract the inline update_daily_data merge (which does NOT currently use
`validate="one_to_one"` — verified) into a shared PURE canonical merger called by BOTH production and
recovery; **F10** the live-construction test imports the REAL installed tushare under monitor+socket
guard and stubs ONLY `pro_api`/client (never the whole module); **F11** quartet.

## 1. Core boundary (GPT-confirmed): the adapter is declarative; the ledger owns everything mutating
The adapter contributes DATA only: `CallRecipe`s, `ResponseScope` rules, a `ConsolidationSpec`, pure
merge functions. The ledger owns leases, the executor invocation, prep, scope enforcement, receipts,
per-request outputs, consolidation, and resume. No adapter-side disk. The one residual surface (fetcher
construction) is covered by the F10 live-construction test.

## 2. Types (the frozen, content-hashed interface)

### 2a. `CallRecipe` — declarative data (F1)
```
CallRecipe(recipe_id, vendor_method, parameter_map: dict[str,str], pagination_mode)
```
`parameter_map` maps request keys → vendor kwargs (e.g. {"trade_date":"trade_date"}); no code. The plan
row freezes `recipe_id`. Execution: the ledger builds kwargs from `parameter_map(request) + {limit,
offset}` for the claimed cursor and calls the ONE generic `fetcher.fetch_page_once(vendor_method,
**kwargs)` exactly once. Validation before the call: `recipe_id` is the endpoint's frozen recipe;
`limit` == the signed contract `page_limit` (or the single-page sentinel); `offset`/`page` == the
atomically claimed cursor; single_page ⇒ page 1/offset 0.

### 2b. §13 authorization = a ledger EVENT (F2)
An explicit user action (`research_orchestrator_cli`-style `authorize-fetch`) writes a hash-chained
`fetch_authorized` event: `{auth_id, actor, issued_at, expires_at, plan_sha256, bundle_sha256,
endpoint_scope}`. `fetch_page` (live mode) validates THAT event is present, unexpired, scope-covers the
endpoint, and its `plan_sha256`/`bundle_sha256` match the frozen run — before every wire call. Run-mode
(`synthetic_nonpromotable` | `live_authorized`) is written at `run_created`; the executor's mode must
equal the run-mode or the ledger refuses BEFORE opening a lease. Promotion independently refuses every
non-`live_authorized` run. The Tushare credential is read from secure env/config after authorization;
never a CLI arg or ledger field.

### 2c. `AdapterSpec` (declarative, no I/O)
```
partition_of(request) -> str
request_output_of(endpoint, request) -> str            # per-REQUEST output (no page arg)
call_recipe(endpoint) -> recipe_id                     # the frozen recipe for this endpoint
response_scope_of(endpoint, request) -> ResponseScope  # concrete rule-id + values (F5)
consolidation_spec(family) -> ConsolidationSpec        # F7
```
`natural_key`/`content_dedup_key`/`max_content_dups`/`empty_policy` come from the matrix + contract.

### 2d. `ResponseScope` (F5) — frozen per plan row
`{rule_id, checks: [(column, mode, value)]}` where mode ∈ {`eq`, `date_in_range[lo,hi]`}. Values are
CONCRETE (from the request). Validated at plan-freeze (well-formed), at each page receipt, and after
concatenation. Range checks parse dates typed (`YYYYMMDD` → date), never string `<=`.

### 2e. `ConsolidationSpec` (F7) — frozen per family
```
ConsolidationSpec(
  input_grouping,                 # how request outputs group into one consolidation unit
  output_partition_of_row,        # row -> output partition key  (A01: trade_date; income: end_date;
                                  #   top_list: trade_date; broker_recommend: month)
  family_output_of,               # output partition -> relative family output path
  recipe_id,                      # merge/repartition recipe (canonical, hashed)
  empty_contribution,             # confirmed-empty request -> {zero_rows | omit_output | empty_file}
  row_conservation)               # e.g. income: sum(input rows) == sum(output rows) after declared dedup
```
Consolidation records EVERY input verdict exactly once and binds each output's path+bytes+row_count.
A01 = 3-leg merge per trade_date; income = per-stock inputs REPARTITIONED to per-`end_date` files
(request axis ≠ output axis); top_list = one file per event date, empties `omit_output`; broker_recommend
= one file per month.

## 3. Ledger-side changes (this phase edits the ledger)
- **`claim_next_fetch(rid) -> ClaimResult`** (F3, the mutation authority): under ONE lock, derives the
  cursor (single_page ⇒ page1/offset0; offset ⇒ next uncovered offset), and OPENS/RESERVES the lease
  atomically. Returns `FETCH(page, offset, lease_id)` | `IN_FLIGHT` | `VERIFY` | `RETRY_EMPTY_CONFIRM` |
  `WAIT_FOR_CANARY` | `CONFIRM_EMPTY(canary_request_id)` | `SKIP_TERMINAL` | `RETRY_PAGE`(only after a
  recorded failure/crash-abandon). `next_fetch_action(rid)` remains a READ-ONLY status view.
- **`fetch_page(rid, lease_id, executor, spec)`** validates `spec` vs the frozen request + the claimed
  lease, invokes `executor.run_page(spec)` (one wire call), runs `prepare_raw_page` (F8), applies
  `response_scope` (F5), records the receipt (vendor-payload hash BEFORE prep + prepared-receipt hash),
  and returns `PageResult(row_count, terminal_kind, next_offset)`. Terminal: single_page ⇒
  `single_page_contract`; offset ⇒ `n>limit` REFUSE / `n==limit` nonterminal / `0<n<limit` last_partial /
  `n==0` empty_terminal.
- **crash-abandon**: an orphaned OPEN lease is converted to `abandoned` ONLY via an explicit crash-resume
  rule, after acquiring a process-lifetime run-execution lock (Q2).
- **bundle manifest**: recomputed and matched at freeze, resume, and before every live page/consolidation
  (Q1).

## 4. Orchestration
```
freeze_run_plan(specs, contracts, declared_families, bundle_manifest)   # ONCE per run (F6)
run_family(spec, ledger, executor):                                     # executes its frozen subset
    for rid in spec's requests:
        while True:
            act = ledger.claim_next_fetch(rid)          # atomic: derives cursor + reserves lease (F3)
            if   act.kind == FETCH:  ledger.fetch_page(rid, act.lease_id, executor, spec_for(rid, act))
            elif act.kind == RETRY_EMPTY_CONFIRM: ledger.fetch_page(...)      # 2nd empty lease (F4)
            elif act.kind == WAIT_FOR_CANARY:     defer(rid); break          # revisit after canary
            elif act.kind == CONFIRM_EMPTY:       ledger.confirm_empty(rid, act.canary_request_id); break
            elif act.kind == VERIFY:              ledger.verify_request(rid); break
            elif act.kind in (SKIP_TERMINAL, IN_FLIGHT): break
consolidate_family(spec, ledger):                       # SEPARATE step (F7)
    assert consolidation_allowed(family)                # every constituent request verified/confirmed
    per ConsolidationSpec: group inputs -> merge/repartition (canonical recipe) -> broker.write ->
        record consolidation verdict (inputs -> each output path+bytes+rowcount; row_conservation)
```
Deferred (`WAIT_FOR_CANARY`) requests are re-driven after a same-endpoint canary verifies; if none ever
verifies, they stay unverified (never `VERIFY`d empty).

## 5. A01 (first implemented adapter)
3 legs (daily/daily_basic single_page; adj_factor offset_paged 5000 via `fetch_page_once("adj_factor",
trade_date=…, limit=…, offset=…)`); `response_scope = trade_date eq request`; `ConsolidationSpec` =
per-trade_date 3-leg merge via the extracted canonical merger (drop `daily_basic.close`, left-join on
(ts_code,trade_date), `validate="one_to_one"`, output rows == daily, 100% positive adj_factor coverage,
≥90% daily_basic coverage, no dup keys, all rows trade_date == partition). The merger is a SHARED pure
function that production (update_daily_data) is refactored to call too (F9).

## 6. Threat model (FROZEN; v3)
- **Trusted:** the ledger (leases/claim/executor-invoke/prep/scope/record/hash/terminal/resume/
  consolidation), the no-follow broker, signed contracts + `RecoveryPaths` + matrix, the promotion SM,
  the content-hashed `adapter_bundle_manifest`.
- **Untrusted:** the executor RESULT (hashed+counted+scoped by the ledger); the `PageCallSpec`/cursor
  (validated vs frozen request + claimed lease); the fetcher class as DRIVER (construction tested by
  F10); the vendor RESPONSE (schema `required_fields` + `response_scope`); a passed `FetchAuthorization`
  object (only the ledger EVENT is trusted).
- **§13** = the hash-chained `fetch_authorized` event validated in-lease is the SOLE vendor authority;
  synthetic run-mode is unreachable-for-live and non-promotable.
- **In scope:** E: leaks, path defaults, wrong-endpoint/date (request cursor + response scope), one-call
  enforcement, truncation, crash-resume + concurrent-claim TOCTOU, dense/sparse empties + canary, schema
  drift, mid-flight contract/recipe edit (manifest recompute + per-page re-bind), containment,
  synthetic/live firewall, consolidation row-conservation.
- **Out of scope (user 2026-07-16):** mid-operation adversarial races; promotion is HUMAN-DRIVEN.
- **Acceptance (interface-freeze QUARTET):** each of A01/income/top_list/broker_recommend runs the full
  machinery (freeze_run_plan → run_family via `claim_next_fetch` → verify/confirm_empty →
  consolidate_family) under a `SyntheticExecutor` in a synthetic-mode run, exercising its PHYSICAL
  consolidation layout (F7), with the pre-fetch test matrix green: single-page / exact-limit multipage +
  trailing-empty / n>limit refuse / retry-as-new-lease / concurrent-claim → IN_FLIGHT / crash +
  claim-resume / dense-empty refuse / sparse WAIT_FOR_CANARY→CONFIRM_EMPTY / null+dup key / schema drift /
  response-scope wrong-date+wrong-stock refuse / prepare_raw_page digest / merge one_to_one + coverage /
  income row-conservation repartition / containment / bundle-manifest tamper (dirty file) refuse /
  executor-mode≠run-mode refuse pre-lease / live-construction write test (F10); promotion refuses the
  synthetic run.

## 7. Tracked promotion preconditions (unchanged; NOT this unit): output-density gate; fina_mainbz
revision-timing probe; fina_indicator_vip §13 period-discovery probe (sign A07).

## Open questions for the reviewer
1. Is `parameter_map` (request-key → vendor-kwarg) expressive enough for all 30 endpoints, or does any
   need a value transform (e.g. period→start/end derivation) that would reintroduce code?
2. For income's per-stock→per-`end_date` repartition, is `row_conservation = sum(inputs)==sum(outputs)
   after declared dedup` the right invariant given a restatement can legitimately change row counts
   across a re-run?
3. Does the `fetch_authorized` ledger event + in-lease validation fully close F2, or must the authorize
   action ALSO be a distinct OS-user/credential step outside this process?
