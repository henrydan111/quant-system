# Data Fetch + Qlib Runbook

This is the operational runbook for the live data platform. Use these commands
for future fetching, verification, staged Qlib builds, publish, and post-publish
acceptance checks.

All commands should use the project interpreter:

```powershell
E:\量化系统\venv\Scripts\python.exe ...
```

## 0. Quick reference — after any data-infra change, run this

```powershell
E:\量化系统\venv\Scripts\python.exe scripts\run_daily_qa.py
```

That one command orchestrates `DataAuditor.audit_daily_files` →
`audit_qlib.py` smoke → `tests/data_infra/test_provider_boundary.py`
(P0-1) → `tests/data_infra/test_pit_live_provider.py` (P0-3) against the
live published provider. Exit-code non-zero on any failure. Report
written to `logs/qa_report_<yyyymmdd_hhmmss>.json`.

Two NEW bootstrap scripts added by the P1 remediation (not wired into
any automation — run manually):

```powershell
# P1-1: Historical suspend_d bootstrap (one-time, ~several hours)
E:\量化系统\venv\Scripts\python.exe scripts\fetch_suspend_d_historical.py

# P1-2: Idempotent namechange refresh
E:\量化系统\venv\Scripts\python.exe scripts\refresh_namechange.py
```

## Publish atomicity (P0-6)

`StagedQlibBackendBuilder.publish()` now hard-fails with a clear
`BuildGateError` if the staged provider and `data/qlib_data/` live on
different volumes. `os.replace()` is only atomic within a single drive.
If you ever see that error, move the staged build onto the target
drive before publishing.

## PIT visibility contract

- `strictly_next_open_trade_day` (renamed from `next_open_trade_day`,
  backward-compat alias retained) has a runtime `assert` that guards
  the `effective_date > disclosure_date` invariant. See
  `CLAUDE.md §3` for the full contract.
- Delist and IPO-lag enforcement lives at the **instruments sidecar
  layer**, NOT inside the PIT ledger. Direct ledger readers under
  `data/pit_ledger/` must apply their own filter using
  `provider_metadata.stock_basic_bounds(ts_code)`.
- The 4 non-statement datasets (`indicators`, `dividends`, `forecast`,
  `holder_number`) anchor on `ann_date` only; the 5 statement families
  (`income`, `income_quarterly`, `balancesheet`, `cashflow`,
  `cashflow_quarterly`) anchor on `max(ann_date, f_ann_date)`.

## 1. Data Layout

The live database is a layered system:

```text
data/
|-- reference/        # trade_cal, stock_basic, ST/reference sidecars, curated exception manifests
|-- market/           # immutable raw daily/index/moneyflow/northbound/margin/stk_limit parquet
|-- fundamentals/     # immutable raw statement/event parquet partitions
|-- corporate/        # immutable raw dividends / holder-number parquet
|-- universe/         # immutable raw index_weights / industry mappings
|-- normalized/       # canonicalized tables used by staged PIT builds
|-- pit_ledger/       # disclosure-aware PIT ledgers
|-- qlib_builds/      # staged provider builds, manifests, metadata audits
`-- qlib_data/        # published provider consumed by research and backtests
```

Rules:

- `data/market`, `data/fundamentals`, `data/corporate`, `data/universe`, and `data/reference` are the raw lake.
- Raw Parquet should stay immutable.
- Repairs belong in curated reference manifests such as `data/reference/daily_price_repair_overrides.csv`, not in ad-hoc raw rewrites.
- `data/normalized` and `data/pit_ledger` are rebuildable serving-prep layers.
- `data/qlib_builds/<build_id>/provider` is the only place a new provider should be validated before publish.

## 2. Supported Entry Points

Primary pipeline scripts:

- `src/data_infra/pipeline/init_market_data.py`
- `src/data_infra/pipeline/init_fundamentals_data.py`
- `src/data_infra/pipeline/init_factor_data.py`
- `src/data_infra/pipeline/refresh_indicator_history.py`
- `src/data_infra/pipeline/update_daily_data.py`
- `src/data_infra/pipeline/build_qlib_backend.py`
- `src/data_infra/pipeline/verify_database.py`

Operational helpers:

- `scripts/fetch_quarterly_statements.py`
- `scripts/build_universe.py`
- `scripts/build_st_universe.py`
- `scripts/audit_qlib.py`
- `tests/harnesses/qlib_smoke.py`
- `scripts/verify_phase2.py`

Compatibility wrappers that remain available but should not be the default starting point:

- `scripts/manual_qlib_dump.py`
- `scripts/build_quarterly_qlib.py`
- `scripts/fetch_quarterly_income.py`

Deprecated / non-standard helpers:

- `scripts/cleanup_close_columns.py`
- `scripts/update_tracker.py`

## 3. Initial Historical Bootstrap

Run these in order on a clean machine or after rebuilding the raw lake.

### Phase 1: Market + Reference

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\init_market_data.py
```

### Phase 2: Fundamentals + Universe

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\init_fundamentals_data.py
```

### Phase 2 Add-on: Historical Indicator VIP Refresh

This clean-replaces the raw `data/fundamentals/indicators/` store from
`fina_indicator_vip` after staging and validation.

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\refresh_indicator_history.py --build-id indicator_vip_refresh_YYYYMMDD
```

### Direct-quarter statement backfills

Currently supported:

- `income_quarterly`
- `cashflow_quarterly`

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\scripts\fetch_quarterly_statements.py --dataset income cashflow
```

Notes:

- `balancesheet_vip(report_type=2/3)` currently returns no usable rows in live testing, so `balancesheet_quarterly` should remain inactive until the source becomes populated.
- Long-running fetches expose visible progress bars.

### Phase 3: Expanded research datasets

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\init_factor_data.py
```

## 4. Routine Daily Maintenance

The standard daily maintenance command is:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\update_daily_data.py
```

Useful options:

- skip fundamentals:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\update_daily_data.py --skip-fundamentals
```

- skip Phase 3:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\update_daily_data.py --skip-phase3
```

- run for a specific date:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\update_daily_data.py --date 20260401
```

What it does:

- updates `stock_basic` and `trade_cal`
- fetches raw daily market data
- refreshes tracked indices
- refreshes Phase 2 statement/indicator data through VIP announcement-window pulls
- refreshes Phase 3 periodic and daily datasets
- updates `index_weights`
- routes changed symbols/datasets through the staged backend

## 5. Raw Integrity Verification

Verify all raw datasets:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\verify_database.py
```

Verify a subset:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\verify_database.py --datasets income,income_quarterly,balancesheet,indicators,cashflow,cashflow_quarterly
```

Phase 2-focused compatibility wrapper:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\scripts\verify_phase2.py
```

## 6. Staged Qlib Builds

### Full rebuild into a staged provider

Use for initial builds, corrected historical backfills, schema changes, or
major PIT logic changes.

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\build_qlib_backend.py --mode all --stage full --build-id full_candidate_YYYYMMDD
```

### Upstream-only rebuild

Use when you want to refresh profiles, normalized tables, and ledgers without
spending time on provider materialization yet.

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\build_qlib_backend.py --mode all --stage upstream-only --datasets indicators,cashflow,cashflow_quarterly --build-id upstream_YYYYMMDD
```

### Provider-only validation build

Use for fast sandbox validation after upstream artifacts already exist.

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\build_qlib_backend.py --mode update --stage provider-only --build-id sandbox_validate_YYYYMMDD --datasets income,income_quarterly,cashflow,cashflow_quarterly,indicators --touched-symbols 000001.SZ,600519.SH,688981.SH --fields revenue,revenue_q,revenue_sq_q0,n_cashflow_act,n_cashflow_act_q,pit_or_yoy,pit_ocf_yoy --allow-exceptions
```

Notes:

- `--mode update` is the normal maintenance mode.
- `--mode all` is for full rebuilds and release candidates.
- `--publish` should only be used after staged validation passes.
- Long-running build stages print progress bars for profiling, normalization, ledger building, price staging, and provider materialization.

## 7. Publish to Production

After a staged candidate passes validation:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\src\data_infra\pipeline\build_qlib_backend.py --mode all --stage full --build-id prod_candidate_YYYYMMDD --publish
```

Publishing promotes the staged provider into `data/qlib_data` and keeps a backup
of the previous live provider.

## 8. Post-publish Acceptance Checks

Audit the staged or live provider:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\scripts\audit_qlib.py --sample-size 50
```

Audit a specific staged build:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\scripts\audit_qlib.py --build-id prod_candidate_YYYYMMDD --sample-size 50
```

Smoke-test live Qlib reads:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\tests\harnesses\qlib_smoke.py
```

## 9. Universe and Metadata Rebuilds

The main provider build already refreshes the derived instrument sidecars.
Use these helpers only when you need to rebuild them directly from local raw
data.

Rebuild all instrument sidecars:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\scripts\build_universe.py
```

Rebuild only `st_stocks.txt`:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\scripts\build_st_universe.py
```

Refetch missing index-weight months:

```powershell
E:\量化系统\venv\Scripts\python.exe E:\量化系统\scripts\refetch_index_weights.py --dry-run
```

## 10. PIT Rules to Preserve

- Visibility starts on the next open trading day.
- `disclosure_date = max(ann_date, f_ann_date)` when both exist.
- Statement families preserve revision versions by `(ts_code, end_date, disclosure_date, report_type)` where relevant.
- Quarter-based factor inputs prefer direct-quarter ledgers when available.
- Cumulative-derived quarter values are fallback only when direct-quarter coverage is absent for that field or period.
- Indicator vendor fields remain reported metrics; recomputed canonical metrics use the `pit_` namespace.
- Raw side anomalies should be handled by curated exception manifests or staged normalization, not manual raw rewrites.
