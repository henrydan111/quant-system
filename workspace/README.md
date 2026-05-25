# Research Workspace (`workspace/`)

The `workspace/` directory is the home for active research, experiments, diagnostics, and notebooks. Keep exploratory work here rather than in `src/` or the repository root.

## Directory Structure

```text
workspace/
|-- AGENTS.md               # Scoped Codex instructions for research work
|-- README.md               # This guide
|-- research/               # Notebooks and interactive analysis
|-- scripts/                # Research-only helper scripts
|-- configs/                # Experiment configs and overrides
`-- outputs/                # Generated plots, reports, exports
```

## Recommended Workflow

1. Start a notebook or prototype under `workspace/research/`.
2. Load data through the Qlib backend unless the task specifically requires raw-Parquet verification.
3. Prefer the Phase 3 factor workflow:
   - `src/alpha_research/factor_library/get_factor_catalog()`
   - `src/alpha_research/factor_library/compute_factors()`
   - `src/alpha_research/factor_library/add_composites()`
   - `workspace/scripts/batch_factor_screening.py`
   - Run screening from the project venv at `E:\量化系统\venv\Scripts\python.exe`; the script now defaults to the validated `batch` engine and supports resumable caches via `--cache-mode {off,resume,refresh}` plus live progress logging.
4. Run backtests with explicit parameters and evaluate them through `src/result_analysis/`.
5. Save artifacts to `workspace/outputs/` and record durable findings in the root `project_state.md`.

## Rules

- Finalized reusable library code belongs in `src/`, not `workspace/`.
- Raw data belongs in `data/`, not `workspace/`.
- Use MLflow via `ExperimentTracker` for substantive experiments that influence research decisions.
- Keep the `workspace/` root minimal. New top-level files should be rare and intentional.
