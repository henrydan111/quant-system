# Data Infrastructure (`src/data_infra/`)

The Data Infrastructure module owns ingestion from Tushare, Parquet storage, Qlib backend construction, and dataset verification. It is the foundation for both research and backtesting.

## Architecture

```text
data_infra/
|-- fetchers/         # Tushare API client with throttling, retries, pagination
|-- storage/          # Parquet layout helpers, Qlib export, qlib_bin_utils.py
|-- pipeline/         # Supported entry-point scripts
|-- cleaners/         # DataCleaner and related preprocessing
`-- verification/     # DataAuditor and integrity checks
```

## Key Components

### `TushareFetcher`

`fetchers/__init__.py` wraps the Tushare Pro API with rate limiting, retries, and pagination.

Important rules:

- Route API calls through `_safe_api_call()`.
- Do not run parallel fetchers against the same Tushare quota.
- Keep throttling conservative unless quota evidence supports a change.

### `StorageManager`

`storage/__init__.py` manages the local Parquet hierarchy and Qlib export.

Key responsibilities:

- write daily market data to `data/market/daily/YYYY/`
- write fundamentals and corporate data using documented partition schemes
- update universe/reference datasets
- export Parquet data to the Qlib backend

Prefer `StorageManager.insert_*` helpers over direct Parquet writes so deduplication and layout rules remain consistent.

### `qlib_bin_utils.py`

Use `src/data_infra/storage/qlib_bin_utils.py` for manual `.day.bin` inspection or writes. Do not hand-roll Qlib binary readers or writers outside that shared utility.

### `DataCleaner` and `DataAuditor`

- `cleaners/__init__.py`: daily-data cleaning and price-adjustment helpers
- `verification/data_auditor.py`: integrity checks for missing dates, nulls, and stock-coverage anomalies

## Supported Pipeline Entry Points

The live pipeline scripts are:

- `src/data_infra/pipeline/init_market_data.py`
- `src/data_infra/pipeline/init_fundamentals_data.py`
- `src/data_infra/pipeline/init_factor_data.py`
- `src/data_infra/pipeline/update_daily_data.py`
- `src/data_infra/pipeline/build_qlib_backend.py`
- `src/data_infra/pipeline/verify_database.py`

Do not document or revive the deprecated legacy pipeline names or the removed Airflow stub.

## Configuration

This module reads from `config.yaml`. The current token pattern is environment-based:

```yaml
data:
  provider: "tushare_pro"
  tushare_token: "${TUSHARE_TOKEN}"
  start_date: "2010-01-01"
```

## Usage

```bash
# Read the operator runbook first
type src\data_infra\pipeline\RUNBOOK.md
```

Key commands are documented in `src/data_infra/pipeline/RUNBOOK.md`, including:

- initial historical bootstrap
- quarterly VIP backfills
- indicator VIP refresh
- daily maintenance
- staged upstream-only / provider-only builds
- production publish
- post-publish Qlib acceptance checks

## Conventions

- The trading calendar in `data/reference/trade_cal.parquet` is the source of truth for open days.
- `D.features()` returns `MultiIndex(instrument, datetime)`.
- Use `mode="update"` for ordinary Qlib maintenance and reserve `mode="all"` for rebuilds.
- Update `data/data_tracker.md` after material syncs or partition changes.
