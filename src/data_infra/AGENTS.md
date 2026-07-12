# Data Infrastructure Rules

These rules apply to everything under `src/data_infra/`.

## 1. API Safety

- Never run parallel Tushare fetchers against the same account.
- All Tushare requests must flow through `TushareFetcher.pro`, which is the `_LockedPro` proxy: EVERY
  `.pro.<endpoint>(...)` call — internal or from an ad-hoc script — is serialized + globally rate-spaced
  across processes via the cross-process account lock (`data_infra/tushare_lock.spaced_call`). The
  `PRO001` lint (`scripts/lint_no_bare_pro.py`, in daily QA) fails any raw-client construction/aliasing
  that would bypass it. NOTE: the proxy guarantees the account lock + spacing but NOT retry — the retry
  lives in `_safe_api_call`, so prefer the `fetch_*` methods (which call `_safe_api_call`) for reads;
  a bare external `.pro.<endpoint>` is locked + spaced but not retried.
- Do not reduce the default `base_sleep=1.5` without evidence that the endpoint and quota can handle it safely.
- On repeated 429s or timeouts, slow down instead of retrying aggressively.

## 2. Storage Discipline

- Prefer `StorageManager.insert_*` helpers over manual Parquet writes so deduplication and path conventions stay consistent.
- Treat `data/market/`, `data/fundamentals/`, `data/corporate/`, `data/universe/`, and `data/reference/` as structured stores with documented partition schemes.
- Update `data/data_tracker.md` when bulk syncs, rebuilds, or partition changes occur.

## 3. Qlib Backend Safety

- Use `export_to_qlib(mode="update")` for ordinary daily maintenance.
- Reserve full rebuilds (`mode="all"`) for initial loads, schema fixes, or corrected historical backfills.
- After rebuilds, verify with `scripts/audit_qlib.py`, `scripts/verify_phase2.py`, or targeted `D.features()` spot checks.
- For any manual `.day.bin` inspection or write, use `src/data_infra/storage/qlib_bin_utils.py`.

## 4. Calendar and Index Conventions

- The trading calendar in `data/reference/trade_cal.parquet` is the ground truth for open days.
- Qlib `D.features()` returns `MultiIndex(instrument, datetime)`. Be explicit about index order in new code.
- Universe files under `data/qlib_data/instruments/` are derived artifacts. Regenerate them with the designated scripts; never hand-edit them.

## 5. Current Pipeline Entry Points

Treat these as the live supported entry points:

- `src/data_infra/pipeline/init_market_data.py`
- `src/data_infra/pipeline/init_fundamentals_data.py`
- `src/data_infra/pipeline/init_factor_data.py`
- `src/data_infra/pipeline/update_daily_data.py`
- `src/data_infra/pipeline/build_qlib_backend.py`
- `src/data_infra/pipeline/verify_database.py`

Do not reintroduce deprecated legacy pipeline references or the removed Airflow stub.

## 6. JoinQuant PIT Cache (added 2026-05-22)

`data/external/jq_pit_cache/` is the local mirror of JoinQuant's PIT views — index membership, `valuation.market_cap`, `is_st`, `paused` — for fields Tushare doesn't expose or computes differently. Powers bidirectional verification (local strategy → JoinQuant deployment, JoinQuant strategy → local verification).

- **Read** via `src/data_infra/jq_pit_cache.JoinQuantPITLoader` (read-only API). Never read the parquet files directly from strategy code.
- **Compatibility shim** for ported JoinQuant strategies: `src/data_infra/jqdata_local` exposes `get_index_stocks`, `get_fundamentals(valuation.*)`, `get_current_data()` backed by the cache. Change `from jqdata import *` → `from src.data_infra.jqdata_local import *` to run a JoinQuant strategy locally.
- **Refresh** is manual (JoinQuant is web-only): run `workspace/scripts/templates/jq_pit_cache_refresh.py` in JoinQuant cloud research, download the output parquet files, copy under `data/external/jq_pit_cache/`, then run `scripts/refresh_jq_pit_cache_manifest.py`. Cadence: weekly.
- **Schema** is locked at `schema_version=1` in `manifest.json`. Any layout change must bump the version and update both the loader and the refresh template in the same PR.
- **CacheMissError** is the canonical "data not available" signal. Strategy code MUST catch it explicitly and either skip the date or fall back to a documented local approximation — never substitute silently.
- Enforcement: `tests/data_infra/test_jq_pit_cache.py` (18 tests).
