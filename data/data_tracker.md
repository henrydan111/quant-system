# Quantitative Data Infrastructure Tracker

*Last Updated: 2026-06-08 (added §11 Bucket A 15000积分 expansion: 8 new raw endpoints downloaded — report_rc analyst forecasts + express/disclosure_date/fina_mainbz/fina_audit fundamentals + repurchase/pledge_stat/top10_floatholders governance; ~10M rows, RAW-only pending normalize→PIT→provider→registry. ALSO: field-parity audit vs official Tushare specs (`workspace/research/data_audit/`) + 3 fixes — stock_basic now 5,852 rows / 17 cols (+act_name/act_ent_type), income_quarterly dropped 100%-null ebit/ebitda → 21 cols, fina_indicator re-fetched with ALL 167 fields (raw 109→167 cols, 58 indicators backfilled; RAW-ONLY, pending ledger/provider/field-registry))*

This document tracks all the data currently downloaded from Tushare into the local Parquet cache (`e:\量化系统\data\`). It should be regularly updated after mass data acquisitions.

**Note:** For detailed column definitions (in both English and Chinese), please refer to the [Data Dictionary](data_dictionary.md) (`data_dictionary.md`).

---

## 1. Reference Data (`data/reference/`)
Contains basic metadata and trading calendars for the market.

| File | Rows | Description | Required Columns Available |
|------|------|-------------|----------------------------|
| `stock_basic.parquet` | 5,852 | Contains all historical listed A-shares, including delisted and ST stocks. (2026-06-08: re-fetched with `act_name`/`act_ent_type` → 17 cols.) | `ts_code`, `list_date`, `delist_date`, `industry`, `exchange`, `act_name`, `act_ent_type` |
| `trade_cal.parquet` | 4,410 | Core trading calendar representing every day the market was explicitly open or closed. | `cal_date`, `is_open`, `pretrade_date` |
| `namechange.parquet` | 18,237 | All historical stock name changes, including ST designation/removal events. | `ts_code`, `name`, `start_date`, `end_date`, `ann_date`, `change_reason` |
| `stock_st_daily.parquet` | 307,696 | Daily ST stock list (2016-08-09 to 2026-03-23). Each row = one stock being ST on that trading day. **⚠ Known gap: 2020-01-02 missing (Tushare server-side issue, confirmed on re-download).** | `ts_code`, `name`, `trade_date`, `type`, `type_name` |
| `moneyflow_known_empty_dates.txt` | 5 dates | Curated source-empty moneyflow trading dates confirmed against the live API. Used by the staged PIT integrity gate. | `YYYYMMDD` line-delimited |
| `northbound_nonconnect_days.txt` | 67 dates | Curated non-connect / source-empty northbound dates confirmed against the live API. Used for both integrity gating and connect-closed forward-fill handling. | `YYYYMMDD` line-delimited |
| `daily_price_repair_overrides.csv` | 2 rows | Curated row-level market-bar repair manifest for persistent source anomalies that cannot be corrected by re-fetch. Currently repairs the `low` field for two `920489.BJ` daily bars where Tushare returns `close < low` but `close == pre_close + change`. Applied only in normalization and staged price export; raw Parquet remains unchanged. | `dataset`, `file_name`, `ts_code`, `trade_date`, `column`, `repaired_value`, `reason` |

---

## 2. Market Daily Data (`data/market/daily/YYYY/`)
The core daily historical records for quantitative analysis. Each file represents one trading day containing OHLCV, valuation metrics, and adjustment factors.

- **Start Date:** `2008-01-02`
- **End Date:** `2026-02-27`
- **Total Trading Days:** 4,410
- **Daily Stock Count Progression:**
  - *2008-01-02*: 1,371 stocks
  - *2026-02-27*: 5,471 stocks

### Available Columns per Record
| Category | Columns |
|----------|---------|
| **Identification** | `ts_code`, `trade_date` |
| **Price Data** | `open`, `high`, `low`, `close`, `pre_close`, `change`, `pct_chg` |
| **Volume Data** | `vol`, `amount`, `turnover_rate`, `turnover_rate_f`, `volume_ratio` |
| **Valuation** | `pe`, `pe_ttm`, `pb`, `ps`, `ps_ttm`, `dv_ratio`, `dv_ttm` |
| **Capitalization** | `total_share`, `float_share`, `free_share`, `total_mv`, `circ_mv` |
| **Adjustments** | `adj_factor` |

## 3. Index Data (`data/market/index/`)
Historical tracking for major market indices.

| Index Name | Code | Start Date | End Date | Rows |
|------------|------|------------|----------|------|
| 上证指数 (SSE Comp) | `000001.SH` | 2008-01-02 | 2026-02-27 | 4,410 |
| 沪深300 (CSI 300) | `000300.SH` | 2008-01-02 | 2026-02-27 | 4,410 |
| 中证500 (CSI 500) | `000905.SH` | 2008-01-02 | 2026-02-27 | 4,410 |
| 中证1000 (CSI 1000) | `000852.SH` | 2008-01-02 | 2026-02-27 | 4,410 |
| 深证成指 (SZSE Comp) | `399001.SZ` | 2008-01-02 | 2026-02-27 | 4,410 |
| 创业板指 (ChiNext) | `399006.SZ` | 2010-06-01 | 2026-02-27 | 3,821 |
| 科创50 (STAR 50) | `000688.SH` | 2019-12-31 | 2026-02-27 | 1,490 |

---

## 4. Fundamentals Data (`data/fundamentals/`)
Quarterly financial reports explicitly tracked by announcement dates to prevent lookahead biases. Total files remain consistent up through latest available filings.

| Sub-Folder | Files | Partition Strategy | Type | Description | Key Columns Available |
|------------|-------|--------------------|------|-------------|-----------------------|
| `income/` | 82 | By `end_date` | Financials | Income Statements. | `ts_code`, `ann_date`, `end_date`, `total_revenue`, `n_income`, etc. (88 cols total) |
| `income_quarterly/` | 72 | By `end_date` | Financials | Single-quarter income statements (`income_vip` / direct-quarter semantics). | `ts_code`, `ann_date`, `end_date`, `revenue`, `operate_profit`, `n_income_attr_p`, `basic_eps`, etc. (21 cols; `ebit`/`ebitda` were 100% null — single-quarter endpoint doesn't populate them — dropped 2026-06-08) |
| `balancesheet/` | 72 | By `end_date` | Financials | Balance Sheets. | `ts_code`, `ann_date`, `end_date`, `total_assets`, `total_liab`, etc. (152 cols total) |
| `indicators/` | 97 | By reported `end_date` period | Vendor-reported metrics; VIP-refreshed raw + PIT serving | Historical raw store was clean-replaced from `fina_indicator_vip` on 2026-04-01. Current status: **raw re-fetched 2026-06-08 with ALL 167 fields (per the field-parity audit) → `550,537` rows, `167` columns** (was 109; 58 non-default indicators backfilled — `rd_exp`/`roe_avg`/`q_*`/turnover-days/coverage ratios; old archived to `_archive/indicators_pre_20260608_230015`). **RAW-ONLY: the PIT ledger + Qlib provider were NOT rebuilt, so the 58 new fields are NOT yet served — pending ledger/provider rebuild + `field_status.yaml` governance per field.** The prior 109-col staged PIT backend resolved `239,008` same-key duplicate `(ts_code, ann_date, end_date)` groups via `update_flag` and deterministic tie-breaks (unchanged until rebuild). The historical period set still includes a small number of non-quarter-end periods already present in legacy Tushare history, so this feed should still be treated as vendor-reported rather than a paired quarterly statement family. | `ts_code`, `ann_date`, `end_date`, `update_flag`, `eps`, `roe`, `roa`, `q_op_qoq`, `roe_avg`, `ebit_to_interest`, `inv_turn`, etc. (167 cols raw; provider `indicators_fields_20260609` published 2026-06-09 serving 109 original + 33 new LEVEL indicators = 142 fields; the 25 `q_*` single-quarter fields intentionally NOT served — self-computed PIT `pit_*` preferred) |

> Quarterly VIP backfill support is now available for `income`, `cashflow`, and `balancesheet` via `scripts/fetch_quarterly_statements.py`. `cashflow_quarterly/` has now been historically backfilled through `2025-12-31`; direct-quarter cashflow files are written only for non-empty periods so future empty fiscal periods do not create schema-less raw partitions. A live 2026-03-31 audit found `balancesheet(report_type=2/3)` and `balancesheet_vip(report_type=2/3)` returning zero rows on sampled periods and names, so `balancesheet_quarterly/` is intentionally not backfilled yet. Historical indicator refreshes now use `src/data_infra/pipeline/refresh_indicator_history.py`, which stages refreshed VIP period files and swaps them into `data/fundamentals/indicators/` only after validation.

---

## 5. Corporate Actions (`data/corporate/`)
Crucial events affecting stock prices directly.

| Sub-Folder | Files | Partition Strategy | Category | Description | Key Columns Available |
|------------|-------|--------------------|----------|-------------|-----------------------|
| `dividends/` | 20 | By `end_date` (Year) | Payouts | Cash dividends, stock splits, etc. | `ts_code`, `ann_date`, `div_proc`, `stk_div`, `cash_div`, `record_date`, `ex_date` |

---

## 6. Universe & Reference (`data/universe/`)
Static or low-frequency mappings required for neutralizations and benchmarking.

| Sub-Folder / File | Files | Partition Strategy | Frequency | Description | Key Columns Available |
|-------------------|-------|--------------------|-----------|-------------|-----------------------|
| `index_weights/` | 219 | By `trade_date` (Month) | Monthly | Index constituents and weights. CSI300 2008-01..2015-12 backfilled 2026-06-11 via mirror code `399300.SZ` (relabeled `000300.SH`; daily snapshots pre-2016 — see data_dictionary §5). CSI300/CSI500 complete from 2008-01; CSI1000 from 2014-10 (index launch). Instruments sidecars (csi300/500/1000.txt) regenerated same day. | `index_code`, `con_code`, `trade_date`, `weight` |
| `industry_sw2021/industry_sw2021.parquet` | 1 | Single File | Static | Shenwan 2021 Classifications (catalog: 31 L1 + 134 L2 + 346 L3 = 511 industries; no per-stock mapping). | `index_code`, `industry_name`, `industry_code` |
| `industry_sw2021_members/industry_sw2021_members.parquet` | 1 | Single File | Time-varying historical | **SW2021 stock-to-industry membership** with full historical in_date/out_date intervals. 7,787 rows / 5,847 stocks / 31 L1 industries (1,940 historical `is_new='N'` + 5,847 current `is_new='Y'`). 1,603 pre-2008 in_date entries; coverage 94-97% pre-2014 and ≥99.91% from 2024+ (Shenwan backfill thinness, NOT survivorship — empirical verification at `workspace/outputs/sw_industry_coverage_audit_20260427.md`). Loaded via `provider_metadata.load_sw_members()`; queried via `industry_as_of()` / `build_industry_series_asof()`. Bootstrap: `scripts/fetch_sw_industry_members.py`. | `ts_code`, `l1_code`, `l1_name`, `l2_code`, `l2_name`, `l3_code`, `l3_name`, `in_date`, `out_date`, `is_new` |

---

## 7. Qlib Data (`data/qlib_data/`)
Binary data converted from Parquet for Qlib's backtesting and factor research engine.

- **Live publish date:** `2026-04-20`
- **Live production build id:** `prod_rebuild_20260416`
- **Publish backup:** `data/qlib_data.bak_prod_rebuild_20260416` (prior live was `prod_candidate_20260401`)
- **Feature directories:** `5,755`
- **Acceptance status:** post-publish `scripts/audit_qlib.py` passed on `50` sampled symbols with zero filesystem errors, zero retrieval errors, and full alias parity on the audited PIT compatibility fields; `scripts/run_daily_qa.py` all 4 checks PASS; `tests/data_infra/test_pit_live_provider.py` 22 passed; `tests/harnesses/qlib_smoke.py` PASS
- **New fields materialized (2026-04-20; reconciled 2026-04-24):** 5 alpha endpoints now queryable via `D.features()`. Event-like daily endpoints are namespaced as `{dataset}__{column}` to prevent their payload fields from shadowing canonical OHLCV bins:
  - `top_list` (龙虎榜 per-stock): `$top_list__close`, `$top_list__pct_change`, `$top_list__turnover_rate`, `$top_list__amount`, `$top_list__l_sell`, `$top_list__l_buy`, `$top_list__l_amount`, `$top_list__net_amount`, `$top_list__net_rate`, `$top_list__amount_rate`, `$top_list__float_values`
  - `top_inst` (龙虎榜机构明细): `$top_inst__buy`, `$top_inst__buy_rate`, `$top_inst__sell`, `$top_inst__sell_rate`, `$top_inst__net_buy`
  - `block_trade` (大宗交易): `$block_trade__price`, `$block_trade__vol`, `$block_trade__amount` — sparse by design (event-driven, only exists on days with actual block trades)
  - `cyq_perf` (筹码分布): `$cyq_perf__his_low`, `$cyq_perf__his_high`, `$cyq_perf__cost_5pct`, `$cyq_perf__cost_15pct`, `$cyq_perf__cost_50pct`, `$cyq_perf__cost_85pct`, `$cyq_perf__cost_95pct`, `$cyq_perf__weight_avg`, `$cyq_perf__winner_rate` — dense daily coverage
  - `stk_holdertrade` (股东增减持) aggregates — custom per-day materializer: `$holdertrade_net_vol` (signed, IN positive / DE negative), `$holdertrade_gross_vol` (absolute), `$holdertrade_net_ratio`, `$holdertrade_events`. Per-holder detail remains at `data/pit_ledger/stk_holdertrade/stk_holdertrade.parquet` (168,024 rows)
- **Deterministic tie-break:** this rebuild is the first live provider built with the P0-4 `_src_file` + `_src_ordinal` deterministic tie-break actualized end-to-end. SHA-256 diff across all 9 periodic ledgers (income, income_quarterly, balancesheet, cashflow, cashflow_quarterly, indicators, forecast, holder_number, dividends) showed IDENTICAL hashes pre-/post-rebuild on this machine — rebuild is reproducible.

### Instrument Files (`data/qlib_data/instruments/`)

| File | Entries | Format | Coverage | Description |
|------|---------|--------|----------|-------------|
| `all_stocks.txt` | ~5,800 | `{code}_{exchange}  start_date  end_date` | 1990–2025 | All tradeable stocks with listing/delisting dates |
| `st_stocks.txt` | 2,070 | `{code}_{exchange}  start_date  end_date` | **1998–2026** | Time-varying ST date ranges. A stock is ST during `[start, end]`. Multiple entries per stock if it entered/exited ST multiple times. **Authoritative source for backtester ST detection.** Covers the 2020-01-02 gap in `stock_st_daily.parquet` via range interpolation. |
| `st_stocks_namechange_backup.txt` | – | Same as above | – | Backup of ST ranges derived from namechange data |

**Usage for backtesting**: `st_stocks.txt` is the **primary ST source** — it covers 1998–2025 with date ranges, making `is_st(code, date)` a simple range lookup. Cross-validated with `stock_st_daily.parquet` (perfect 138/138 match on 2019-12-31).

---

## 8. Phase 3: Factor Research Data (audited 2026-03-30)

Additional data sources downloaded via `init_factor_data.py` for the 177-factor research catalog.

### Per-Stock Data (Fundamental)

| Sub-Folder | API | Partition | Status | Description |
|------------|-----|-----------|--------|-------------|
| `fundamentals/cashflow/` | `cashflow` | By `end_date` | Complete raw, PIT normalization required | Cash flow statements (OCF, CapEx, FCF); duplicate PIT keys observed and handled in the staged backend |
| `fundamentals/cashflow_quarterly/` | `cashflow_vip` | By `end_date` | Historically backfilled through `2025-12-31` | Direct single-quarter cashflow statements (`report_type=2/3`); currently `72` non-empty partitions / `455,972` raw rows, feeding the quarter-canonical cashflow PIT ledger |
| `fundamentals/forecast/` | `forecast` | By `end_date` | Complete raw, PIT normalization required | Earnings pre-announcements; duplicate canonical groups observed and handled in the staged backend |
| `corporate/holder_number/` | `stk_holdernumber` | By year | Complete raw, legacy null-ann rows quarantined for PIT | Shareholder count data; `47` legacy rows with null `ann_date` are written to `pit_ledger/holder_number/holder_number_unusable_pit.parquet`, while `107` calendar-end rows plus `4,608` future disclosures remain pending until market/calendar coverage extends |

### Per-Date Data (Market)

| Sub-Folder | API | Partition | Status | Date Range | Description |
|------------|-----|-----------|--------|------------|-------------|
| `market/moneyflow/` | `moneyflow` | `YYYY/moneyflow_YYYYMMDD.parquet` | Complete raw, 5 source-empty dates documented | `2008-01-02` to `2026-02-27` (`4,405` files) | Capital flow (large/small/medium orders); do not synthetic-fill historical gaps; expected-empty dates are tracked in `reference/moneyflow_known_empty_dates.txt` |
| `market/northbound/` | `hk_hold` | `YYYY/northbound_YYYYMMDD.parquet` | Complete raw, exception calendar added | `2017-01-03` to `2026-02-27` (`2,153` files) | Stock Connect daily holdings; source-empty non-connect dates are tracked in `reference/northbound_nonconnect_days.txt`; raw `.HK` / contaminated suffix counts are preserved in profiling metadata, while the normalized backend recovers valid A-share codes from raw `code + exchange` and hard-fails materialization if any invalid rows remain |
| `market/margin/` | `margin_detail` | `YYYY/margin_YYYYMMDD.parquet` | Complete raw | `2010-03-31` to `2026-02-27` (`3,863` files) | Margin trading details; true coverage starts at `2010-03-31` |
| `market/stk_limit/` | `stk_limit` | `YYYY/stk_limit_YYYYMMDD.parquet` | Complete raw | `2008-01-02` to `2026-02-27` (`4,410` files) | Daily limit-up/down prices; observed raw schema is `trade_date`, `ts_code`, `up_limit`, `down_limit` |
| `market/suspension/` | `suspend_d` | `suspension_YYYY.parquet` + consolidated `suspension_ranges.parquet` | **P1-1: NOT YET BOOTSTRAPPED.** Run `scripts/fetch_suspend_d_historical.py` to populate. | TBD after bootstrap | Authoritative Tushare 停复牌 table. `EventDrivenBacktester` now passes `suspension_ranges.parquet` into `Exchange` automatically when the file exists; if it is missing, the high-level runner logs the fallback and `Exchange.is_suspended()` uses the legacy `vol == 0` proxy. |

> **Script**: `python src/data_infra/pipeline/init_factor_data.py [--category ...]`
> All APIs require ≤ 2000 积分 (except `share_float` at 3000). 5000 积分 provides full access + higher rate limits.

## 9. Staged PIT Backend Serving Layers

| Layer | Path | Purpose |
|------|------|---------|
| Raw immutable store | `data/` | Original Tushare Parquet partitions |
| Canonical normalized zone | `data/normalized/` | Schema-normalized, code-normalized canonical tables |
| PIT ledger zone | `data/pit_ledger/` | Revision-aware ledgers keyed by conservative disclosure dates |
| Staged provider builds | `data/qlib_builds/<build_id>/` | Validated provider builds before publish |
| Published provider | `data/qlib_data/` | Active Qlib backend consumed by research and backtests |

### Fundamental PIT serving conventions

- Statement families are now served with paired semantics where available:
  - cumulative ledger is canonical for cumulative and trailing metrics
  - quarterly ledger is canonical for quarter-based metrics
  - cumulative-derived quarter values are fallback only when quarterly coverage is missing
- Statement ledgers now preserve `report_type` in canonical PIT keys for statement datasets.
- Quarter-canonical serving is report-type aware:
  - adjusted single-quarter `report_type=3` is preferred over `2` when both are visible at the same disclosure time
  - missing payload cells on the preferred row are backfilled from lower-priority same-disclosure variants
- Current family coverage:
  - `income` + `income_quarterly`
  - `cashflow` + optional `cashflow_quarterly`
  - `balancesheet` (snapshot)
- Canonical provider field families:
  - cumulative: `field`, `field_cum_q0..q4`
  - quarterly: `field_q`, `field_sq_q0..q4`
  - snapshot: `field`, `field_q0..q4`
- Canonical PIT-derived indicator fields are additive and use the `pit_` prefix, including:
  - `pit_or_yoy`, `pit_op_yoy`, `pit_netprofit_yoy`, `pit_basic_eps_yoy`, `pit_q_sales_yoy`, `pit_q_op_qoq`, `pit_ocf_yoy`
- Provider audit sidecars now include quarterly-vs-cumulative parity summaries under `data/qlib_builds/<build_id>/provider/metadata/pit_audit/`.

---

## 10. JoinQuant PIT Cache (`data/external/jq_pit_cache/`) — added 2026-05-22

Local mirror of JoinQuant's point-in-time views for fields Tushare doesn't expose (dynamic index membership) or computes differently (`valuation.market_cap` ranking ties, `is_st` / `paused` flags). Powers bidirectional verification: local strategies ↔ JoinQuant deployment.

| Subdir | Layout | Source |
|---|---|---|
| `index_members/{index_jq_code}/{YYYY}.parquet` | long format: `date`, `ts_code` (Tushare format). | `get_index_stocks(index, date=d)` per trading day |
| `valuation/{YYYY-MM}.parquet` | long format: `date`, `ts_code`, `market_cap`, `circulating_market_cap`, `pe`, `pb`. | `get_fundamentals(query(valuation.*), date=d)` |
| `flags/{YYYY-MM}.parquet` | long format: `date`, `ts_code`, `is_st`, `paused`. | `get_extras('is_st', ...)` + `get_price(paused=True)` |
| `manifest.json` | schema_version, last_refresh_utc, coverage per data type/index. | Generated by `scripts/refresh_jq_pit_cache_manifest.py` |

**Coverage as of 2026-05-22** (initial migration only — valuation + flags not yet exported):
- `index_members/399101.XSHE/` — 597 Tuesday snapshots from 2014-01-07 → 2026-02-24 (migrated from `Knowledge/zxz_399101_pit_membership_tuesdays.csv`, the P1 G5_A2 investigation export).

**Refresh** (manual; JoinQuant is web-only):
1. Open JoinQuant cloud research → paste `workspace/scripts/templates/jq_pit_cache_refresh.py`.
2. Edit date range, run all cells, download the output parquet files.
3. Copy into the matching folder under `data/external/jq_pit_cache/`.
4. Run `venv/Scripts/python.exe scripts/refresh_jq_pit_cache_manifest.py` to regenerate the manifest.

**Consumers**:
- `src/data_infra/jq_pit_cache.JoinQuantPITLoader` — read-only API. Always use this; never read the parquet files directly from strategy code.
- `src/data_infra/jqdata_local` — JoinQuant-API compatibility shim for porting JoinQuant strategies to run locally.
- Backtest-engine deployment-parity defaults consume the cache transparently when a strategy uses the `JoinQuantParityStrategy` template.

**Enforcement**: `tests/data_infra/test_jq_pit_cache.py` locks the loader API and shim contract (18 tests).

---

## 11. Bucket A — 15000积分 Expansion (raw bootstrap, downloaded 2026-06-08)

Eight new deep-history endpoints unlocked by the Tushare 5000→15000积分 upgrade, downloaded via
[scripts/fetch_bucket_a.py](../scripts/fetch_bucket_a.py) (sequential, `_safe_api_call`, cap-aware
pagination, idempotent). **Status: RAW only** — NOT yet normalized, NOT in the PIT ledger, NOT in the
Qlib provider, NOT in `field_status.yaml`. These are not research-usable until they go through
normalize → PIT ledger → Qlib materialization → field-registry promotion. Provenance + design:
[workspace/research/data_expansion/](../workspace/research/data_expansion/) (plan + GPT cross-review).

| Dataset | Path | API / bulk mode | Files | Rows | Stocks | Span | Size |
|---|---|---|---|---|---|---|---|
| `report_rc` ⭐ | `data/analyst/report_rc/report_rc_{YYYY}.parquet` | `report_rc`, report_date month-chunked + paginated (cap 5000) | 17 | 2,869,998 | 5,648 | 2010-01..2026-06 | 123 MB |
| `express` | `data/fundamentals/express/express_{period}.parquet` | `express_vip` by quarterly period | 73 | 28,646 | 4,543 | 2008..2026 | 2.9 MB |
| `disclosure_date` | `data/fundamentals/disclosure_date/disclosure_date_{period}.parquet` | `disclosure_date` by quarterly end_date (all-market) | 73 | 266,225 | 6,044 | 2008..2026 | 2.2 MB |
| `fina_mainbz` | `data/fundamentals/fina_mainbz/fina_mainbz_{period}.parquet` | `fina_mainbz_vip` by period, paginated (cap 10000) | 65 | 1,901,403 | 6,942 | 2010..2026 | 53 MB |
| `repurchase` | `data/corporate/repurchase/repurchase_{YYYY}.parquet` | `repurchase` by ann_date year range, paginated | 17 | 101,874 | 3,781 | 2010..2026 | 1.7 MB |
| `pledge_stat` | `data/corporate/pledge_stat/pledge_stat_{YYYY}.parquet` | `pledge_stat` by weekly Friday end_date, paginated (HARD cap 3000) | 13 | 2,073,664 | 4,444 | 2014-03..2026-06 | 18.6 MB |
| `top10_floatholders` | `data/corporate/top10_floatholders/top10_floatholders_{period}.parquet` | `top10_floatholders` by period, paginated (cap 6000) | 77 | 2,635,091 | 6,021 | 2007..2026 | 89 MB |
| `fina_audit` | `data/fundamentals/fina_audit/fina_audit.parquet` | `fina_audit` PER-STOCK (ts_code required), checkpointed | 1 | 95,825 | 5,803 | 1997..2025 | 1.0 MB |

**PIT notes (must be honored before any formal use):**
- `report_rc` is analyst forecast data, **PIT-anchored (resolved 2026-06-08)** at ledger `effective_date` = a CONTEMPORANEOUS `create_time` (gap ≤ 45 cal days → `max(report_date, create_time)`) else `report_date + 2 open days` — validated market-wide vs the JoinQuant 朝阳永续 oracle (Spearman 0.94); the breadth restatement canary RAN 2026-06-14 (`scripts/report_rc_backfill_canary.py`). **Materialized** into the PIT ledger + Qlib provider: 4 `$report_rc__eps_*` primitives (approved) + 5 consensus/rating aggregates `$report_rc__{np_fy1, op_rt_fy1, n_active_orgs, rating_up, rating_dn}` (quarantine until the bound standing OUTPUT canary passes; `_materialize_report_rc_aggregates`). **Coverage is strongly size-tilted** (large-cap ~95% vs small-cap ~22–53%) — rank within-coverage + size-neutralize.
- `pledge_stat` carries ONLY `end_date` (a weekly exchange statistic date, NOT a disclosure date) → visibility-date semantics + publication-lag need a check before formal use.
- `express` / `disclosure_date` / `fina_audit` / `repurchase` / `top10_floatholders` carry `ann_date` → disclosure-anchored (standard `max(ann_date, f_ann_date)` / `ann_date` handling).
- `fina_mainbz` segment rows anchor on the owning report's disclosure (join `ann_date` from the statement).

---

## ⚠️ Stock Code Format Convention (CRITICAL)

Tushare and Qlib use **different `ts_code` formats**. Failing to convert between them causes silent lookup failures (0% match, no error raised).

| System | Format | Example |
|--------|--------|---------|
| **Tushare** (all Parquet files in `data/`) | `{code}.{exchange}` | `000001.SZ` |
| **Qlib** (instruments in `data/qlib_data/`, MultiIndex from `D.features()`) | `{code}_{exchange}` | `000001_SZ` |

**Conversion**: `ts_code.replace('.', '_')` — simply swap the dot for an underscore.

When joining Tushare reference data (e.g., `stock_basic.parquet`, `industry_sw2021.parquet`) with Qlib-loaded DataFrames, **always convert `ts_code` to Qlib format first**:

```python
def tushare_to_qlib(ts_code: str) -> str:
    return ts_code.replace('.', '_')
```

**Benchmark/Index Codes**: The same underscore format applies to benchmark indices in `backtest()`:
- ✅ `benchmark='000300_SH'` — works with custom Qlib databases
- ❌ `benchmark='SH000300'` — Qlib's built-in `CSI300_BENCH` only works with official Qlib data downloads

