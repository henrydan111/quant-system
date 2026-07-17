# GPT §10 re-review — sign-off HOLD fold (9 findings) + 3 invariant-class additions

Independent GPT‑5.5 Pro reviewer. Your prior verdict was **HOLD/REWORK** (4 BLOCKER + 4 MAJOR + 1 MINOR)
on the all-32 sign-off at `5e0e917`. Every finding was reproduced against the data/code before fixing.
This is the fold.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · HEAD **`d8516ef`**
Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
Files: `…/workspace/configs/recovery_endpoint_contracts.yaml`, `…/scripts/raw_recovery_coordinator.py`,
`…/scripts/build_aux_pit_ledgers.py`, `…/tests/data_infra/test_recovery_ledger.py`,
`…/tests/data_infra/test_build_aux_pit_ledgers_fina_mainbz_bz_code.py`.

## Finding → fix (each verified against the data/code first)

| # | Your finding | Fix | Evidence I verified |
|---|---|---|---|
| B1 | fina_indicator_vip signed 73 of 98 as complete | **UNSIGNED** — empty `{}` stub, stays `BLOCKED(contract)` pending a §13 period-discovery probe | manifest `profiled_datasets['indicators'].file_count == 98`; the 25 non-quarter periods are NOT enumerable from survivors (manifest holds only the count; pit_ledger/normalized/fundamentals empty) |
| B2 | cyq_perf per-date density on per-stock requests | matrix + contract `dense_refuse → sparse_canary` | stock_basic: 95 codes `delist_date<20180102` + 2 `list_date>20260701` = 97 always-empty requests |
| B3 | disclosure_date single_page, doc caps 3000 | `single_page → offset_paged, page_limit 3000` | doc 162 单次最大3000; baseline 266,225 rows / 73 quarters ≈ 3647 > 3000 |
| B4 | pagination not bound to reality | statement families → offset_paged (2000 per-stock / 10000 VIP); pledge_stat 3000**→1000**; fina_mainbz 10000**→100**; top10 6000**→5000** | `_fetch_statement`→`_fetch_paginated`; doc 110=1000, doc 81=单次最大100行, doc 62=5000. report_rc 3000 / repurchase 2000 confirmed correct |
| M1 | PIT strings confuse observation vs availability | after-close set → "T outcome, after close, usable T+1"; adj_factor stays session-open (premarket, doc 28) w/ cadence fixed; stk_limit stays session-open (pre-open limit prices); broker_recommend → ~day-4; pledge_stat lag UNRESOLVED; suspend_d → no guaranteed pre-open | doc 28 premarket 9:15–9:20; §3.3 stk_limit session-open-knowable |
| M2 | income_vip/cashflow_vip dense at (period,report_type) | matrix + contract `dense_refuse → sparse_canary` | `_fetch_statement_report_types` appends only non-empty legs (skips empty report_type=3) |
| M3 | suspend_d starts 2008 | bounds start `20080102 → 19901219` | pinned calendar = 8672 open sessions; 4179 pre-2008 were omitted |
| M4 | fina_mainbz downstream dedup omits bz_code | `build_aux_pit_ledgers.py` DEDUP_KEYS + `bz_code` + regression test | old key collapses a P vs I fixture 2→1; new key keeps 2 |
| MINOR | seam removed proof that verify_request calls the gate | added a 2-request frozen-plan test (daily needs `close` → reject; moneyflow needs ts_code → pass) | `_assert_response_fields` is called at recovery_ledger.py:585 inside `verify_request` |

## Three additions I made under the SAME invariant (B4), NOT in your list — please confirm
"Bind pagination to reality" implies auditing every per-date full-universe endpoint's max rows vs its
cap, not only the ones you named. Verified max concurrent listed stocks = **5528** (stock_basic, as of
2026-07-01):
- **adj_factor** `single_page → offset_paged 5000`: doc 28 cap 5000 **< 5528** → single call truncates
  recent dates. (Slam-dunk; verified.)
- **stk_limit** `single_page → offset_paged 5800`: doc 183 cap 5800; the endpoint covers 全市场 A/B股+基金,
  so per-date rows exceed the 5528 A-share count and can pass 5800.
- **block_trade** `single_page → offset_paged 1000`: doc 161 cap 1000; a busy day's market-wide block
  trades can exceed 1000. (Conservative — one extra empty terminal call when under.)
daily/daily_basic/moneyflow (cap 6000 > 5528), margin_detail (~2500), hk_hold (~2600), top_list/top_inst,
index_daily (per-code ~4500 < 8000), cyq_perf (per-stock) stay single_page.

## One honest caveat (tracked follow-up, not a silent gap)
B2/M2 move the DENSITY guarantee from the request level to a per-date/per-period OUTPUT check "after
repartition/consolidation" — exactly your prescription. That consolidation-phase output-density check is
a REQUIREMENT for the adapter/consolidation phase and is **not yet code** (adapters aren't built). So
today the recovery would fetch these families sparsely-correct at the request level; the compensating
"every trading day 2018+ / every reported period is non-empty in the OUTPUT" assertion must be
implemented before promotion. Flagging it as a tracked precondition, not claiming it exists.

## State
31 signed (`contract_errors == []` from generator AND re-loaded from disk); `--plan`: 30 families
`BLOCKED(UNBOUND callable)` + `A07/indicators BLOCKED(contract:fina_indicator_vip)`. Full recovery
battery **171 passed** (coordinator 78 / ledger 41 / promotion 40 / broker 9 / aux-dedup 3). No Tushare
call; fetch exits 3.

## Questions
1. Do B1 (unsign vs a machine waiver) and the M4/MINOR tests fully discharge your findings?
2. Are the 3 invariant-class additions (adj_factor/stk_limit/block_trade) correct, or over-paginated?
3. Is deferring B2/M2 output-density to the consolidation phase acceptable for sign-off, given it's
   flagged as a tracked precondition to promotion?
4. Any remaining proxy-for-the-fact where a signed fact still stands in for the vendor's reality?

Return per finding: severity, whether it blocks adapters, and a reproducing probe where applicable.
