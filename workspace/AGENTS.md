# Workspace Rules

These rules apply to everything under `workspace/`.

## 1. Layout

- Keep notebooks in `workspace/research/`.
- Keep helper scripts in `workspace/scripts/`.
- Keep experiment configs in `workspace/configs/`.
- Keep generated artifacts in `workspace/outputs/`.
- Keep the `workspace/` root minimal; `README.md` and this `AGENTS.md` should be the only stable top-level files there.

## 2. Research-Only Code

- `workspace/` is for active research, prototypes, diagnostics, and notebooks.
- Finalized reusable library code belongs in `src/`, not `workspace/`.
- Raw data does not belong in `workspace/`.

## 3. Preferred Research Workflow

- Default to the Qlib backend for research unless the task specifically requires raw Parquet verification.
- For factor screening and batch evaluation, prefer the Phase 3 operator workflow and `workspace/scripts/batch_factor_screening.py`.
- Avoid slow ad-hoc `groupby().apply()` pipelines when an existing Qlib expression or factor-library helper can do the work.

## 4. Backtesting and Reporting

- Follow `workspace/research/signal_backtesting_guide.md` for research backtests.
- In research scripts, set `VectorizedBacktester.run()` parameters explicitly instead of relying on convenience defaults.
- Use `BacktestReport`, `generate_trading_stats()`, and other `src/result_analysis/` helpers for evaluation.
- Log substantive experiments with MLflow when the run is intended to inform strategy decisions.

## 5. Documentation and Cleanup

- Save durable diagnostics, exports, and plots under `workspace/outputs/` or `logs/`.
- Document meaningful findings or milestones in the root `project_state.md`, not in a workspace-local state file.
- Remove or consolidate throwaway research artifacts once they are no longer useful.
