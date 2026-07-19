# GPT §10 DESIGN re-review #3 — adapter phase v3 (folds the 6 remaining findings)

Independent GPT‑5.5 Pro reviewer. re-review #2 discharged F6/F8/F9/F10/F11 and held F1–F5, F7. This is
the fold — still DESIGN-STAGE. Approving v3 FREEZES the interface + threat model for the quartet
implementation.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · HEAD after push.
Design v3: `…/workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md` (fully rewritten).

## Held finding → v3 resolution
| # | held finding | v3 resolution |
|---|---|---|
| F1 | recipes still arbitrary thunks; validation too thin | **`CallRecipe(recipe_id, vendor_method, parameter_map, pagination_mode)`** = declarative DATA; ONE generic **`fetcher.fetch_page_once(vendor_method, **kwargs)`** (exactly one wire call); `recipe_id` FROZEN per plan row; ledger validates recipe_id / `limit`==contract / `offset`+`page`==atomically-claimed cursor / single-page sentinel; lint forbids `_safe_api_call`/loops in `fetch_page_once` |
| F2 | authorization constructible-only; mixed only non-promotable | §13 = a hash-chained **`fetch_authorized` LEDGER EVENT** (auth_id, actor, issued/expiry, plan_sha256, bundle_sha256, scope) from an explicit user action; `fetch_page` validates the EVENT; run-mode fixed at `run_created`; **executor-mode ≠ run-mode REFUSES before opening any lease** (mixed unreachable); promotion refuses non-live |
| F3 | single_page vs n>limit; next_fetch_action→fetch_page TOCTOU | single_page terminal defined SEPARATELY (page1/offset0 → `single_page_contract`); **`claim_next_fetch(rid)`** derives the cursor AND opens/reserves the lease ATOMICALLY under one lock (concurrent → `IN_FLIGHT`); retry only after recorded failure/crash-abandon |
| F4 | action enum can't express the empty lifecycle | added **`RETRY_EMPTY_CONFIRM`**, **`WAIT_FOR_CANARY`**, **`CONFIRM_EMPTY(canary_request_id)`**; `VERIFY` never for an empty sparse request; deterministic canary selection |
| F5 | response_scope lacked the request's values; not frozen | **`response_scope_of(endpoint, request)`** with concrete rule-id + values FROZEN per plan row; validated at freeze / page-receipt / post-concat; TYPED date parsing for ranges |
| F7 | one `family_output`, but 4 physical layouts | frozen **`ConsolidationSpec`** (input_grouping, `output_partition_of_row`, `family_output_of`, merge/repartition recipe id, `empty_contribution` {zero_rows\|omit_output\|empty_file}, `row_conservation`); handles per-stock→per-`end_date` repartition (income, verified at storage/__init__.py), event/monthly layouts; records each input verdict once + binds output path/bytes/rowcount |
| Q1 | hash the registry? | one canonical **`adapter_bundle_manifest`** = relative path + sha256 of every call-recipe/`fetch_page_once`/response-scope/prepare/merge/consolidation module + declarative entries; hash-chained at freeze, RECOMPUTED on resume + before live exec/consolidation (git HEAD insufficient — dirty file undetected) |

Riders on the discharged findings folded too: **F8** producer ids/source in the manifest, vendor hash
BEFORE prep, prep adds only declared cols; **F9** extract the inline update_daily_data merge (verified: no
`validate=`) into a SHARED pure canonical merger both production + recovery call; **F10** import the REAL
tushare under monitor+socket guard, stub only `pro_api`/client.

## Your Q2/Q3 answers, applied
- Q2: `claim_next_fetch` is the atomic mutation authority; `next_fetch_action` demoted to read-only
  status; orphaned lease → `abandoned` only via explicit crash-resume after a process-lifetime
  run-execution lock.
- Q3: immutable ledger run-mode is the correctness firewall (executor-mode mismatch refuses pre-lease);
  synthetic uses a separate temp root, live the real root (hygiene); promotion refuses non-live.

## Verified before folding (§7 rule 10)
income per-stock→per-`end_date` repartition is real (`insert_fundamental_data` partitions by end_date);
update_daily_data merges use NO `validate=` (F9 factual note confirmed); `fetch_adj_factor` has no
limit/offset + `_safe_api_call` retries (F1, from #1).

## New open questions
1. Is `parameter_map` (request-key → vendor-kwarg, no code) expressive enough for all 30 endpoints, or
   does any need a value transform (period→start/end) that reintroduces code into the recipe?
2. For income's repartition, is `row_conservation = sum(inputs)==sum(outputs) after declared dedup` right
   given a restatement can legitimately change counts across a re-run?
3. Does the `fetch_authorized` event + in-lease validation fully close F2, or must the authorize action
   be a distinct OS-user/credential step outside this process?

## Self-review (mine): clean for design re-review. §3 invariants intact (raw re-fetch, PIT downstream,
fina_mainbz quarantine preserved); threat model re-frozen for v3 (declarative recipe + ledger EVENT auth +
atomic claim + frozen response-scope + ConsolidationSpec row-conservation).

Return per finding: discharged / not, whether it blocks the interface freeze, and the concrete change.
