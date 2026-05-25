# Data Pipeline Scripts (`src/data_infra/pipeline/`)

This directory contains the supported orchestration scripts for building, updating, and validating the local data platform.

For the operator-facing step-by-step workflow, see [RUNBOOK.md](E:\量化系统\src\data_infra\pipeline\RUNBOOK.md).

## Pipeline Layout

```text
init_market_data.py        # Phase 1 bootstrap: prices, valuation, reference data
init_fundamentals_data.py  # Phase 2 bootstrap: financials, corporate data, universes
init_factor_data.py        # Phase 3 bootstrap: extra datasets for the 191-factor catalog
refresh_indicator_history.py # Historical VIP indicator refresh with staged raw swap
build_qlib_backend.py      # Compile Parquet data into the Qlib backend
update_daily_data.py       # Routine daily maintenance and incremental Qlib refresh
verify_database.py         # Data audit wrapper
```

## Script Roles

### `init_market_data.py`

- Downloads trade calendar, stock reference, index data, daily OHLCV, valuation, and adjustment factors.
- Intended for one-time bootstrap or large historical rebuilds.

### `init_fundamentals_data.py`

- Downloads financial statements, dividends, industry mappings, and index weights.
- Historical indicators are now refreshed through the same VIP schema family used by daily maintenance, via a staged period-based refresh.
- Historical direct-quarter VIP backfills for statement families now live in `scripts/fetch_quarterly_statements.py`; the bootstrap pipeline remains responsible for the base raw statement families.
- Run after Phase 1 is in place.

### `refresh_indicator_history.py`

- Refreshes `data/fundamentals/indicators/` from `fina_indicator_vip` using period-based all-stock pulls.
- Stages refreshed raw period files first, validates `update_flag` and period alignment, then swaps the live raw directory only after validation passes.
- Supports `--start-period`, `--end-period`, `--build-id`, `--dry-run`, and `--validate-only`.

### `init_factor_data.py`

- Downloads the additional Phase 3 datasets needed for the 191-factor catalog:
  - `cashflow`
  - `forecast`
  - `moneyflow`
  - `hk_hold`
  - `margin_detail`
  - `stk_holdernumber`
  - `stk_limit`
- Supports category-specific runs and resume-safe behavior.

### `build_qlib_backend.py`

- The authoritative staged PIT backend builder.
- Runs the observed-data workflow:
  - profile raw inputs
  - normalize canonical tables
  - build revision-aware ledgers
  - materialize a staged provider under `data/qlib_builds/<build_id>/`
  - validate and optionally publish into `data/qlib_data/`
- Fundamental statement materialization now uses paired family semantics:
  - cumulative ledgers drive cumulative / trailing fields
  - quarterly ledgers drive quarter fields when available
  - cumulative-derived quarter values are fallback only
  - canonical PIT-derived growth fields are exposed under `pit_*`
- Supports stage-scoped execution for sandbox and release workflows:
  - `--stage full`: full upstream + provider build
  - `--stage upstream-only`: audit, normalize, and build PIT ledgers without provider materialization
  - `--stage provider-only`: reuse persisted profile/normalized/ledger artifacts and rerun only provider materialization + validation
- Supports scoped sandbox validation via:
  - `--datasets` for dataset subsets
  - `--fields` for targeted field families
  - `--touched-symbols` for a representative symbol basket even in `--mode all`
  - `--skip-compat-aliases` to skip legacy scalar alias writes in validation builds
- Long-running stages now emit `tqdm` progress bars during:
  - raw profiling
  - normalization
  - ledger building
  - daily price staging
  - provider materialization
- For sandbox validation baskets, prefer `--mode update --stage provider-only` with `--touched-symbols` so the builder creates a minimal staged provider base (`calendars`, `instruments`, and the requested feature directories) instead of copying the full published provider tree.

### `update_daily_data.py`

- Handles routine updates after the market closes.
- Uses Tushare VIP all-stock statement endpoints for announcement-window PIT refreshes.
- Updates reference data, daily market data, Phase 2 fundamentals (`income`, `income_quarterly`, `balancesheet`, `indicators`), Phase 3 periodic/event datasets (`cashflow`, `cashflow_quarterly`, `forecast`, `holder_number`), Phase 3 daily market datasets (`moneyflow`, `northbound`, `margin`, `stk_limit`), universe snapshots, and then routes touched-symbol refreshes through the staged backend.
- Supports `--skip-phase3` for runs that intentionally exclude the Phase 3 refresh path.

### `verify_database.py`

- Profiles datasets and enforces the staged backend's raw integrity gates.

## Operating Notes

- Use staged `mode="update"` flows for ordinary maintenance.
- Reserve full staged rebuilds for schema changes, corrected historical backfills, or provider contract changes.
- Validate major rebuilds with `scripts/audit_qlib.py`, `tests/harnesses/qlib_smoke.py`, and targeted `verify_database.py` / `verify_phase2.py` runs.
- The deprecated legacy init-script names and the removed Airflow stub are not part of the live pipeline anymore.
