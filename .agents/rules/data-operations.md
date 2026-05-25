---
trigger: model_decision
description: apply the rules when user's prompt is associated with data acquisition, data updating, or data verification
---

# Data Operations

Safety rules and operational guidelines for interacting with the data pipeline, Tushare API, and Qlib backend.

## 1. Tushare API Rate Limits

- Never run parallel fetchers against Tushare Pro.
- All API calls must go through `TushareFetcher._safe_api_call()` with the built-in retry logic and backoff.
- Batch operations should preserve throttling, and the default `base_sleep=1.5` should not be reduced without evidence.
- If you encounter repeated 429s or timeouts, increase the sleep interval instead of retrying more aggressively.

## 2. Data Mutation Safety

- Scripts that modify existing `data/` Parquet files should log which files will be touched before they start.
- Support a `--dry-run` flag when practical.
- Do not overwrite raw data in place without either a backup path or a deduplication guarantee.
- Prefer `StorageManager.insert_*` helpers rather than manual Parquet writes.

## 3. Current Pipeline Entry Points

Treat these as the live supported entry points:

- `src/data_infra/pipeline/init_market_data.py`
- `src/data_infra/pipeline/init_fundamentals_data.py`
- `src/data_infra/pipeline/init_factor_data.py`
- `src/data_infra/pipeline/update_daily_data.py`
- `src/data_infra/pipeline/build_qlib_backend.py`
- `src/data_infra/pipeline/verify_database.py`

Do not reintroduce or document the deprecated legacy pipeline names or the removed Airflow stub.

## 4. Qlib Backend Rebuild

- A full Qlib rebuild (`export_to_qlib(mode="all")`) is expensive. Use it only for initial loads, corrected historical backfills, or schema-level changes.
- For daily updates, use `mode="update"`, not `mode="all"`.
- After rebuilds, verify the backend with `scripts/audit_qlib.py`, `tests/harnesses/qlib_smoke.py`, `scripts/verify_phase2.py`, or targeted `D.features()` spot checks.
- Any long-running data or backend script should expose a visible progress tracker and keep reporting its current progress in the console so an operator can tell which stage is active and roughly how much work is left.

## 5. Parquet File Conventions

- Daily market data: `data/market/daily/YYYY/daily_YYYYMMDD.parquet`
- Index data: `data/market/index/{index_code}.parquet`
- Fundamentals: `data/fundamentals/{category}/{end_date}.parquet`
- Corporate actions: `data/corporate/{category}/{partition}.parquet`
- Universe data: `data/universe/{category}/`
- Never introduce a new partitioning scheme without updating `data/data_tracker.md`.

## 6. Qlib Universe and Instrument Files

- Qlib universe files live in `data/qlib_data/instruments/*.txt`.
- Regenerate universe files whenever constituent data changes and use the designated builder scripts.
- Treat these files as derived artifacts; never hand-edit them.
- After regeneration, verify instrument counts and date ranges with Qlib.

## 7. Data Integrity Verification

- After any bulk data operation, run the relevant verification:
  - `scripts/audit_qlib.py`
  - `scripts/verify_phase2.py`
  - `tests/harnesses/qlib_smoke.py`
  - `DataAuditor.audit_daily_files()`
- Update `data/data_tracker.md` after any material synchronization.

## 8. Trading Calendar as Ground Truth

- `data/reference/trade_cal.parquet` is the single source of truth for market-open dates.
- Never assume business days equal trading days.
- When iterating over dates, filter against the open-day calendar.

## 9. Qlib Bin and MultiIndex Conventions

- Manual `.day.bin` inspection or writes must go through `src/data_infra/storage/qlib_bin_utils.py`.
- `D.features()` returns `MultiIndex(instrument, datetime)`, not the more common `(datetime, instrument)` order.
- In raw pandas code, use `groupby(level=0)` for per-instrument operations unless you have explicitly swapped levels.
- The `factor_eval` toolkit can normalize either index order, but new code should still document which convention it assumes.
