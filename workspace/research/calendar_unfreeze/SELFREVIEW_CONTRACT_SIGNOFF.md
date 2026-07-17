# Self-review — recovery contract sign-off (all 32 endpoints) + fina_mainbz matrix fix

Date: 2026-07-17 · Commit: `5e0e917` · Branch: `calendar-unfreeze`
Prerequisite for the §10 GPT cross-review of the same change.

## Scope of the change
1. `workspace/configs/recovery_endpoint_contracts.yaml` — 32 endpoints filled + signed (`reviewed_by: henry`, under the delegation "sign all 32, I'll review the diff").
2. `scripts/raw_recovery_coordinator.py` — one matrix correction: `fina_mainbz` `vendor_record_key`/`content_dedup_key` `type` → `bz_code`.
3. `tests/data_infra/test_recovery_ledger.py` — fixture redirects the `_assert_response_fields` seam to fixture-local `_LIVE_CONTRACTS` (was reading the live YAML).

No production logic changed beyond the one matrix key; the validator/ledger/broker/promotion code is the already-GPT-reviewed foundation.

## §3 invariant checks
- **§3.2 PIT / no-lookahead**: contracts carry `pit_anchors` as *descriptive metadata* (statements `max(ann_date,f_ann_date)`; events `ann_date`; report_rc `max(report_date,create_time)`, deep-backfill `report_date+2`; daily/session `session-open-knowable`). No executable PIT path is introduced here; the anchors match `pit_backend`/§3.2. Recovery re-fetches RAW — PIT alignment stays downstream in the loader/provider. ✅
- **§3.4 governance / fetch gate**: the signed contract IS the human fetch-review gate; `contract_errors` enforces doc-binding (`doc_sha256` + the doc must declare the endpoint), resolver-belongs-to-endpoint, population-set-sha, typed pagination, signer, tz-aware timestamp. `--fetch` still exits 3. No formal-run artifact is produced. ✅
- **§6.1 read-the-doc-before-fetch**: every contract pins its doc bytes; the `fina_mainbz` fix came *from* reading doc 81 (输入 vs 输出 tables). ✅
- **§3.5 / registries / factors**: untouched. N/A.

## OOS / selection-on-holdout trace
No factor research, no seal spend, no OOS window touched. N/A. (Per [[feedback_self_review_before_gpt]] the trace is still run: there is no OOS reference anywhere in this change.)

## Cited-number cross-check (vs §3 staleness flags)
- `daily`/`daily_basic`/`adj_factor` → 4493 requests == baseline manifest's 4493 daily files. ✅
- per-stock → 5861 == `stock_basic` L,D,P (original fetchers iterate every code). ✅
- `income_vip`/`cashflow_vip` → 146 = 73 periods × report_types `['2','3']` (confirmed: `_fetch_statement_report_types` loops one call per report_type). ✅
- `report_rc` → 198 = 16y×12 + 6 months (2010-01..2026-06, matches data_tracker). ✅
- `broker_recommend` → 72 = 6y×12 (2020-07..2026-06). ✅
- No stale-flagged magnitude (E-wave/eps deployment numbers, etc.) is cited. ✅

## Open questions surfaced for GPT (NOT hidden; deferred to the pre-fetch test matrix by design)
These are dense-vs-reality questions that cannot be resolved without the deleted raw data or a §13-gated canary fetch. The sign-off encodes the *matrix's* declared `empty_policy` (which I must match); the **pre-fetch test matrix** (next phase) is the designed place to catch them via a canary.

1. **`fina_indicator_vip` — genuine incompleteness.** Signed the 73 generated quarter-ends. `data_tracker` line 76 records the indicators store held *non-quarter legacy periods*; that exact list is **unrecoverable from surviving artifacts** (`pit_ledger/`, `normalized/`, `fundamentals/` are empty; the thaw manifest gives only row counts). Signing the recoverable-clean set + this flag, rather than silently claiming completeness. **Question:** accept the 73-quarter recovery as the indicator baseline, or hold `fina_indicator_vip` for a §13 probe that discovers which non-quarter periods Tushare still serves? *(This is the one endpoint where I know the population is a strict subset of what was lost.)*

2. **`income_vip`/`cashflow_vip` dense_refuse over period×['2','3'].** Defensible at the VIP full-market level (a market-wide `report_type=3` response is non-empty each period — the subset of stocks with an adjusted single-quarter row is non-empty). Residual risk only at the earliest boundary (a quarter where *no* stock restated → empty type-3 response → dense halt). **Unverified** without data; the resolving test is a canary fetch of the earliest few (period, report_type=3) requests, or the baseline per-period row counts if recoverable. Deferred to the pre-fetch test matrix.

3. **`cyq_perf` dense_refuse over all-stock (5861) population.** A pre-2018-delisted name returns empty `cyq_perf` → dense halt. The original fetcher iterated all stocks and *skipped* empties (sparse behaviour), yet the matrix marks the per-date output dense. **Question for the adapter phase:** is dense applied per-date-after-repartition (correct) or per-stock-request (would halt)? A fetch-time concern.

4. **`suspend_d` bounds** = market era `20080102..20260701`. The original bootstrap iterated the *full* calendar (`first_year` from `open_days[0]`, ~1990). suspend_d is sparse so over-broad is harmless, but under-broad would miss pre-2008 suspensions. **Question:** does the lost suspend_d store start at 2008 (faithful) or earlier?

5. **`report_rc` page_limit = 3000** (doc 292 单次 cap) vs data_tracker's "cap 5000" note. Chose the conservative value: page_limit ≤ true server cap is always correct (a short page reliably signals the end; a too-large limit would truncate). Sanity-check the reasoning.

6. **`fina_mainbz` `type`→`bz_code` fix.** `type` is the input selector (doc 81 输入参数, P/D/I); `bz_code` is the output identity echo (输出参数). The resolver is `report_periods` (period only, no `type` param) — `fina_mainbz_vip(period=X)` returns all breakdowns each stamped with `bz_code`, so the corrected key disambiguates the actual fetched rows. **Confirm** `bz_code` is the right row-identity column and the period-only fetch returns all breakdowns.

## Verdict
**Clean for GPT.** The change is structurally sound (all 32 pass `contract_errors == []` from the generator AND re-loaded from disk; `--plan` moves every row off BLOCKED(contract); full recovery battery 167 passed). The open questions above are inherent recovery-completeness / dense-vs-reality judgments that are correctly deferred to the pre-fetch test matrix — surfaced here, not buried. The one genuine incompleteness (`fina_indicator_vip` non-quarter periods) is flagged for an explicit human decision.
