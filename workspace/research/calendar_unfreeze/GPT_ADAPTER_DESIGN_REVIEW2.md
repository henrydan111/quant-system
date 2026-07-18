# GPT §10 DESIGN re-review #2 — adapter phase v2 (folds 11 findings)

Independent GPT‑5.5 Pro reviewer. Your v1 verdict was REWORK/HOLD (11 findings). This is the design fold
— still DESIGN-STAGE, no implementation. Approving v2 FREEZES the interface + threat model the quartet
implementation is then judged against.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · HEAD after push.
Design v2: `…/workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md` (read this — fully rewritten).

## Finding → v2 resolution
| # | v1 finding | v2 resolution |
|---|---|---|
| F1 | opaque callable; `_safe_api_call` retries; `fetch_adj_factor` no paging | **`PageCallSpec(endpoint, base_params, limit, offset, recipe_id)`** validated by the ledger vs the frozen request; typed **`Executor.run_page`** does EXACTLY ONE wire call via new **`fetch_*_page_once`**; retries = new leases; recipes hashed into `adapter_bundle_hash`. (Verified: `fetch_adj_factor(trade_date,ts_code,start,end)` has no limit/offset; `_safe_api_call` loops `range(max_retries)`.) |
| F2 | constructor-only §13; synthetic looks promotable | **`FetchAuthorization(run_id, plan_sha256, adapter_bundle_hash, endpoint_scope, expires_at)`** validated INSIDE the ledger lease at every live page; immutable run-mode `synthetic_nonpromotable`\|`live_authorized`; **promotion refuses synthetic/mixed**; credential from secure env only, never CLI/ledger |
| F3 | caller-computed `terminal_claim`; always page 1 | **`fetch_page` returns `PageResult(row_count, terminal_kind, next_offset)`** (ledger derives terminal: n>limit refuse / n==limit nonterminal / 0<n<limit last_partial / n==0 empty_terminal); **`next_fetch_action(rid)`** owns resume (SKIP_TERMINAL/FETCH/VERIFY/RETRY_PAGE) |
| F4 | `confirm_empty` missing canary | **deterministic empty-scheduler**: 2nd empty lease, verdict DEFERRED until a same-endpoint nonempty canary verifies → `confirm_empty(rid, canary_request_id)`; no canary ⇒ unverified |
| F5 | response never scoped to the request | **`response_scope_spec`** (eq / in_range), applied page-by-page pre-cert AND post-concat; wrong date/stock REFUSES |
| F6 | family-level freeze on a one-plan ledger | **`freeze_run_plan(specs, declared_families)`** once per run; `run_family` executes only its frozen subset |
| F7 | `receipt_output_of(...page)` contradiction; consolidation ambiguity | **`request_output_of(endpoint, request)`** (no page arg); SEPARATE **`consolidate_family`** step (NOT in `run_family`); A01 acceptance wording fixed |
| F8 | derived digests never produced at fetch | **`prepare_raw_page(endpoint, df)`** registry inside the ledger boundary; adds ONLY `derived_fields_for(endpoint)` cols before hashing; records vendor-payload + prepared-receipt hashes |
| F9 | population parity ≠ merge correctness | **reuse the production canonical merger** (update_daily_data.py — verified: drops aux `close`, 100% positive adj_factor coverage, ≥90% daily_basic coverage, one_to_one, no dup keys, target-date equality) in `consolidate_family` |
| F10 | synthetic monitor can't prove live construction | add a **fresh-subprocess, network-denied live-construction test** (stub tushare; monitor before import; `ts.pro_api(token)`, never `ts.set_token()`) alongside the synthetic full-run monitor |
| F11 | A01 alone under-covers the shapes | interface-freeze unit = **quartet** (A01 `market/daily` + per-stock `income` + event `top_list` + monthly `broker_recommend`); A01 is the first *implemented* adapter, freeze after the quartet |

## Your direct-answer keepers (retained in v2)
Pure adapter / ledger-owned persistence (no adapter-side disk); separate leg receipts + consolidation
merge (provenance-preserving); the exact-limit trailing-empty terminal behavior. §13 enforcement moved
lower (into the executor inside the lease); credential kept out of the ledger.

## New open questions (v2 introduces these)
1. Is recipe-registry-hashed-into-`adapter_bundle_hash` enough to make the `PageCallSpec` path
   tamper-evident, or must the ledger also pin the recipe source bytes?
2. Does `next_fetch_action` as the SOLE resume/terminal authority fully subsume the caller loop, or is
   there a page-ordering race between a `FETCH` and a concurrent `RETRY_PAGE` on the same request?
3. `synthetic_nonpromotable` run-mode + promotion refusal vs physically separate run roots for
   synthetic/live — which is the right firewall?

## Self-review (mine)
Verified the two most design-shaping claims before folding (F1 `fetch_adj_factor` signature + retry loop;
F9 production merge invariants) — both exactly as you stated. §3: adapters re-fetch RAW only, PIT
alignment downstream, fina_mainbz quarantine preserved. Threat model re-frozen for v2 (executor result +
PageCallSpec + fetcher-driver + response scope untrusted; §13 in-lease is sole vendor authority;
synthetic non-promotable). Verdict: clean for design re-review.

Return per finding: discharged / not, whether it blocks the interface freeze, and the concrete change.
This gate, once approved, freezes the interface for the quartet implementation.
