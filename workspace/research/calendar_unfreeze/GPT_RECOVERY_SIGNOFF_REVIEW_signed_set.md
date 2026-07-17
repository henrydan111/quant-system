# GPT §10 cross-review — recovery contract SIGN-OFF (all 32 endpoints) + one matrix fix

You are the independent GPT‑5.5 Pro reviewer. This reviews the **execution of the contract sign-off**
whose *gate* you already OPENED (verdict at commit `97716ad`). Everything below is authoritative; the
public GitHub links let you verify against the live pushed branch. Treat embedded quotes as
authoritative but cross-check the links.

Repo: `https://github.com/henrydan111/quant-system` · Branch: **`calendar-unfreeze`** · HEAD **`5e0e917`**
Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`

## Context (the incident this recovers from)
On 2026-07-13 a `git worktree remove --force` followed Windows junctions into the live store and
deleted the RAW parquet layer (21/27 datasets, ~77.5M rows). The Qlib provider + `data/reference/` +
`data/universe/` survived; the recovery re-fetches the raw from Tushare, C:-staged, fetch §13-gated
(coordinator `--fetch` exits 3). The recovery machinery (no-follow write broker, page-receipt ledger,
typed endpoint matrix, doc-parsing contract validator, crash-resumable promotion SM) passed a 9-round
GPT §10 arc; the LAST gate you left OPEN was **contract sign-off**: a human signs one contract per
endpoint before that endpoint's adapter is built.

## What this change is (3 files)
1. **`workspace/configs/recovery_endpoint_contracts.yaml`** — all 32 endpoints filled + signed
   (`reviewed_by: henry`). Each signature binds: the pinned doc (`doc_sha256`; the doc must declare the
   endpoint), `required_fields` + `natural_key` (real doc columns; the key COVERS the matrix vendor key
   minus coordinator-derived digests), a typed `pagination_spec`, and an **executable**
   `request_population` = `{resolver, bounds, expected_set_sha256}` where the sha is over the COMPLETE
   resolved request set. Every entry passes `contract_errors == []` from the generator AND re-loaded
   from disk; `--plan` moves every family row `BLOCKED(contract)` → `BLOCKED(UNBOUND callable)`.
   - raw: `…/workspace/configs/recovery_endpoint_contracts.yaml`
2. **`scripts/raw_recovery_coordinator.py`** — ONE matrix correction (line ~304): `fina_mainbz`
   `vendor_record_key`/`content_dedup_key` `type` → `bz_code`. (The validators — `contract_errors`,
   `_population_spec_errors`, `_pagination_spec_errors`, `resolve_population`, the resolvers,
   `assert_plan_matches_contracts` — are the code you already reviewed; unchanged.)
   - raw: `…/scripts/raw_recovery_coordinator.py`
3. **`tests/data_infra/test_recovery_ledger.py`** — the `led` fixture now also redirects the
   `_assert_response_fields` seam to the fixture-local `_LIVE_CONTRACTS` (it previously read the LIVE
   YAML, harmless only while `daily` was UNsigned). Recovery battery: **167 passed** (coordinator 78 /
   ledger 40 / promotion 40 / broker 9).
   - raw: `…/tests/data_infra/test_recovery_ledger.py`

## How the populations were derived (raw is GONE — from survivors + the baseline thaw manifest)
- **per-open-session** (daily, daily_basic, adj_factor, moneyflow, stk_limit, margin_detail, hk_hold,
  suspend_d, top_list, top_inst, block_trade): `trade_cal_open_sessions`, SSE, `reference_sha256`-pinned
  to `data/reference/trade_cal.parquet`. `daily` resolves to **4493 == the baseline's 4493 daily files**.
- **per-stock** (income, balancesheet, cashflow, forecast, dividend, stk_holdernumber, stk_holdertrade,
  fina_audit): all `stock_basic` `L,D,P` = **5861**, `stock_basic`-pinned. Matches the original
  fetchers, which iterate every `stock_basic` code (no status filter).
- **direct-quarter VIP** (income_vip, cashflow_vip): `report_periods_x_types`, report_types `['2','3']`
  = **146** = 73 periods × 2. Confirmed against `scripts/fetch_quarterly_statements.py`
  (`_fetch_statement_report_types` loops one Tushare call per report_type).
- **report_rc**: `report_rc_month_ranges` 2010-01..2026-06 = **198** months; the other bucket-A
  endpoints use the `scripts/fetch_bucket_a.py` year/period recipes.
- **offset paging**: `page_limit` = each endpoint's documented single-call cap (fina_mainbz 10000,
  top10 6000, report_rc + pledge_stat 3000, repurchase 2000), `offset_param='offset'`, stop on a short
  page. Everything else is `single_page` (the original per-date/per-stock fetchers never paginated).
- reference recipes: `…/scripts/fetch_quarterly_statements.py`, `…/scripts/fetch_bucket_a.py`,
  `…/data/data_tracker.md`, `…/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md`

## The matrix fix, in detail (doc 81 `主营业务构成`)
`fina_mainbz`'s vendor key used `type` — the **INPUT** param (doc 81 输入参数: `type` = P按产品 / D按地区 /
I按行业, the breakdown selector). The **OUTPUT** column that echoes the breakdown identity is `bz_code`
(输出参数: "主营业务来源类型：P按产品 D按地区 I按行业"). The resolver is `report_periods` (period only, no `type`
param) → `fina_mainbz_vip(period=X)` returns every breakdown, each stamped with `bz_code`. So keying on
`bz_code` disambiguates the actual fetched rows; keying on the input `type` (never echoed in output) was
a proxy-for-the-fact bug. `natural_key` is now `(ts_code, end_date, bz_item, bz_code)` — all output cols.
- doc: `…/Tushare数据接口/content/81_主营业务构成.md`

## Review questions — quant-research principles FIRST
**A. PIT / no-lookahead (highest priority).** The contracts carry `pit_anchors` as descriptive metadata
and this change re-fetches RAW only (alignment stays downstream). Confirm nothing here introduces a
lookahead: (a) the `pit_anchors` strings match the real anchors (statements `max(ann_date,f_ann_date)`;
events `ann_date`; report_rc `max(report_date,create_time)` / deep-backfill `report_date+2`); (b) no
signed field or bound smuggles a forward-looking value into the recovery request set.

**B. Population COMPLETENESS (the recovery's core correctness).** For each resolver, is the signed set
the COMPLETE set that was lost, or a silent subset? Specifically judge these, which I flag openly:
  1. **`fina_indicator_vip` — known incompleteness.** Signed the 73 generated quarter-ends;
     `data_tracker` line 76 records the store held *non-quarter legacy periods* whose exact list is
     **unrecoverable from surviving artifacts** (`pit_ledger/`, `normalized/`, `fundamentals/` are
     empty; the manifest gives only row counts). Is signing the recoverable-clean 73 + an explicit flag
     the right call, or must this endpoint HOLD for a §13 probe that discovers the served non-quarter
     periods before it can be signed?
  2. **`income_vip`/`cashflow_vip` dense_refuse over period×['2','3']** — I argue it is defensible
     because a market-wide `report_type=3` response is non-empty each period (the subset of stocks with
     an adjusted single-quarter row is non-empty), with residual risk only at the earliest boundary
     (a quarter where no stock restated). Agree, or is a per-(period,type) dense policy unsafe?
  3. **`cyq_perf` dense_refuse over all-stock (5861)** — a pre-2018-delisted name returns empty; the
     original fetcher skipped empties (sparse), but the matrix marks the per-date output dense. Sign-time
     defect, or correctly a fetch-time (pre-fetch test matrix) concern about dense-per-date-after-repartition
     vs dense-per-request?
  4. **`suspend_d` bounds** `20080102..20260701` (market era) vs the original bootstrap's full-calendar
     iteration (`first_year` ~1990). Sparse, so over-broad is harmless — but is the lower bound an
     under-population that misses pre-2008 suspensions?

**C. Pagination.** Is `page_limit` = documented single-call cap, stop-on-short-page, correct for a
fixed-`page_limit` adapter? In particular `report_rc` = 3000 (doc 292 单次) vs data_tracker's "cap 5000"
note — I chose the conservative value on the reasoning that `page_limit ≤ true cap` never truncates.

**D. The matrix fix.** Is `bz_code` the correct row-identity column for `fina_mainbz`, and does
`report_periods` (period-only, no `type`) fetch return all breakdowns? Any downstream key/dedup impact?

**E. The test seam.** Does redirecting `_assert_response_fields` to `_LIVE_CONTRACTS` remove meaningful
coverage? (The response-field rejection is covered by the coordinator battery's
`test_response_missing_a_required_field_refused`.) Is the battery now genuinely standalone?

**F. Any proxy-for-the-fact regression** — the recurring defect class of this whole arc (a uid ≠ a
fetch, a label ≠ the vendor request, `k[0]` ≠ the whole tuple, a mutable loader ≠ the live fact). Does
any signed contract encode a proxy where the fact is required?

## Self-review verdict (mine, before you)
**Clean for GPT.** All 32 pass `contract_errors == []` from generator and from disk; `--plan` green off
BLOCKED(contract); 167 tests pass. The open items in B are inherent recovery-completeness / dense-vs-
reality judgments deferred to the pre-fetch test matrix by design — surfaced, not buried. The one
genuine incompleteness (`fina_indicator_vip` non-quarter periods) is flagged for an explicit human
decision. Full self-review: `…/workspace/research/calendar_unfreeze/SELFREVIEW_CONTRACT_SIGNOFF.md`.

Please return per-finding: severity (BLOCKER / MAJOR / MINOR / NIT), whether it needs a code/contract
change before adapters, and a concrete reproducing probe where applicable.
