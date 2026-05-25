# JoinQuant PIT Cache

**Purpose.** Bidirectional verification between local backtests and JoinQuant deployment:
- Local strategies use this cache to mimic JoinQuant's PIT data sources (`get_index_stocks`, `valuation.market_cap`, `is_st`, `paused`) so a local backtest predicts a JoinQuant backtest of the same strategy.
- JoinQuant strategies imported into the local environment use the `src/data_infra/jqdata_local` shim, which is backed by this cache, so the strategy runs locally without code changes beyond the import.

This cache is the authoritative local mirror of JoinQuant's PIT views for fields Tushare doesn't expose (e.g., dynamic index membership) or computes differently (e.g., `valuation.market_cap` ranking ties).

## Layout

```
data/external/jq_pit_cache/
├── README.md                           # this file
├── manifest.json                       # schema version, coverage, last refresh
├── index_members/
│   └── {index_jq_code}/{YYYY}.parquet  # long format: date, ts_code
├── valuation/
│   └── {YYYY-MM}.parquet               # long format: date, ts_code, market_cap, ...
└── flags/
    └── {YYYY-MM}.parquet               # long format: date, ts_code, is_st, paused
```

All `ts_code` columns store **Tushare format** (`002001.SZ`, `600519.SH`). The original JoinQuant codes (`002001.XSHE`, `600519.XSHG`) are converted on write.

## Refreshing the cache

JoinQuant data is web-only — refresh is manual:

1. Open JoinQuant cloud research → new notebook (Python 3 kernel).
2. Paste the notebook template at `workspace/scripts/templates/jq_pit_cache_refresh.py`.
3. Edit the date range (default: append the last 30 days).
4. Run all cells (~5-15 minutes depending on date range).
5. Right-click each output parquet in the JQ research file tree → download.
6. Copy the downloaded files into the matching folder under `data/external/jq_pit_cache/`.
7. Run `venv/Scripts/python.exe scripts/refresh_jq_pit_cache_manifest.py` to regenerate `manifest.json` from the on-disk coverage.

Cadence: weekly is sufficient for most strategies (index membership and valuation change slowly). Daily is fine if you depend on `is_st` / `paused` flags from the latest day.

## Consumers

- **JoinQuantPITLoader** (`src/data_infra/jq_pit_cache.py`) — the canonical read-only API. Always use this; never read the parquet files directly from strategy code.
- **jqdata_local** (`src/data_infra/jqdata_local.py`) — JoinQuant-API compatibility shim. Lets JoinQuant strategies run locally with minimal porting (change `from jqdata import *` to `from src.data_infra.jqdata_local import *`).

## What is NOT in this cache

- Daily OHLCV (use the existing Tushare/Qlib pipeline; that's the local source of truth).
- Minute-frequency data (deferred; the local stack is daily-only as of 2026-05-22).
- Fundamentals beyond `valuation.*` (use the existing `data/normalized/` parquet files).

## See also

- `src/data_infra/AGENTS.md` §6 — the PIT cache contract.
- `data/data_tracker.md` — refresh status entries.
- `CLAUDE.md` §3 — engine defaults that consume this cache.
