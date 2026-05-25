# Scripts Directory (`scripts/`)

This directory contains standalone utility scripts, verification helpers, compatibility wrappers, and maintenance helpers used to maintain the system. Research notebooks and active prototypes should live in `workspace/`, not here.

For the authoritative operational workflow, use [RUNBOOK.md](E:\量化系统\src\data_infra\pipeline\RUNBOOK.md). The `src/data_infra/pipeline/` entrypoints are the primary supported path; several scripts here are compatibility wrappers or one-off maintenance helpers. Runnable test harnesses now live under [tests/README.md](E:\量化系统\tests\README.md).

## Supported Operational Helpers

| Script | Purpose |
|--------|---------|
| `audit_qlib.py` | Sample and validate Qlib feature coverage and PIT behavior |
| `build_universe.py` | Rebuild derived Qlib universe files from local raw data |
| `build_st_universe.py` | Rebuild `st_stocks.txt` from local raw reference data |
| `fetch_quarterly_statements.py` | Generic VIP backfill script for direct-quarter statement datasets (`income`, `cashflow`, `balancesheet`) |
| `refetch_index_weights.py` | Re-fetch monthly index-constituent weights |
| `validate_qlib_nulls.py` | Inspect Qlib features for missing-value issues |
| `verify_phase2.py` | Validate Phase 2 data completeness and schema expectations |

## Compatibility Wrappers

| Script | Status |
|--------|--------|
| `build_quarterly_qlib.py` | Compatibility wrapper over the staged PIT builder for income-quarter feature rebuilds |
| `fetch_quarterly_income.py` | Compatibility wrapper over `fetch_quarterly_statements.py --dataset income` |
| `manual_qlib_dump.py` | Compatibility wrapper over the staged PIT builder; no longer uses the old direct dump path |

## One-off / Maintenance Helpers

| Script | Status |
|--------|--------|
| `cleanup_close_columns.py` | Deprecated; intentionally performs no raw-data edits |
| `generate_data_dictionary.py` | Regenerates `data/data_dictionary.md` from the current local datasets |
| `keep_awake.py` | Prevent Windows sleep during long-running local jobs |
| `start_codex_repo.cmd` | Windows entrypoint for launching Codex with the repo-local ripgrep workaround |
| `start_codex_repo.ps1` | Launch Codex with a repo-local ripgrep path prepended to `PATH` |
| `update_tracker.py` | Deprecated; tracker updates should be deliberate, not canned append operations |
| `use_repo_ripgrep.ps1` | Materialize a repo-local `rg.exe` and prepend it to the current PowerShell session or child command |

## Notes

- Keep durable operational helpers here.
- Remove throwaway debug scripts once they stop providing value.
- If a script becomes part of the core product path, move the reusable logic into `src/`.
- The Codex launcher scripts cache a working `rg.exe` under `.codex/tools/bin/` so repo-local shells do not depend on the blocked MSIX-packaged ripgrep path.
- `fetch_quarterly_income.py` is now a compatibility wrapper over `fetch_quarterly_statements.py --dataset income`.
- `cleanup_close_columns.py` and `update_tracker.py` remain only so old references fail safely instead of mutating project state.
- Test and smoke harnesses live under `tests/harnesses/`, not under `scripts/`.
