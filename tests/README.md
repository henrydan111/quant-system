# Tests Directory

This directory is the dedicated home for automated tests and runnable smoke or
integration harnesses.

## Layout

- `tests/data_infra/`
  - durable automated tests for the staged PIT backend, fetchers, and refresh flows
- `tests/alpha_research/`
  - durable automated tests for factor-library and research-runtime behaviors
- `tests/harnesses/`
  - runnable smoke, integration, and manual-check scripts that used to live under `scripts/`
  - these are not the primary production entrypoints; they are verification helpers
  - scratch artifacts should go under `workspace/outputs/`, not under top-level `data_test*` folders

## Usage

Examples:

```powershell
E:\量化系统\venv\Scripts\python.exe -m pytest -q
E:\量化系统\venv\Scripts\python.exe -m unittest discover -s E:\量化系统\tests\alpha_research -p test_compute_factors.py -v
E:\量化系统\venv\Scripts\python.exe E:\量化系统\tests\harnesses\qlib_smoke.py
E:\量化系统\venv\Scripts\python.exe E:\量化系统\tests\harnesses\backtester_smoke.py
```

## Notes

- Root-level pytest is intentionally constrained by `pytest.ini` to collect only `tests/`.
  This avoids treating generated artifacts under `logs/` or `workspace/outputs/` as tests.
- Pytest temporary files are routed to `workspace/outputs/pytest_runtime_tmp` so test runs do not depend on
  external `%TEMP%` / `AppData` directories.
- Production data-fetching and Qlib-build entrypoints still live under `src/data_infra/pipeline/`.
- Operational utilities still live under `scripts/`.
- New test assets should go here rather than back into `scripts/`.
