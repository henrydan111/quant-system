---
trigger: always_on
---

# Global System Rules

This file is the detailed human-readable reference for repo-wide operating rules. The canonical instruction layer for Codex now lives in the root `AGENTS.md` plus scoped `AGENTS.md` files in active subtrees. Keep this file aligned with those Codex-facing instructions.

## 1. Mandatory Context Refresh

Before non-trivial work, read these files in order:

1. `project_state.md`
2. `config.yaml`
3. `src/system.md`
4. `data/data_dictionary.md`
5. `data/data_tracker.md`

These documents are the source of truth for architecture, current implementation status, data coverage, and active research priorities.

## 2. System Context & Architecture

This repository is a full quantitative investment research system. Always maintain awareness of its six core modules:

- **Data Acquisition (`src/data_infra/`)**: Tushare fetching, ETL, storage, PIT backend, Qlib backend, verification
- **Factor Research (`src/alpha_research/`)**: Two-layer factor operators, factor catalog, evaluation toolkit, ML models, theme strategy framework, factor / candidate registries, MLflow tracking
- **Strategy Backtesting (`src/backtest_engine/`)**: Vectorized screening engine and event-driven A-share simulator
- **Risk Analysis (`src/portfolio_risk/`)**: Portfolio optimization, cost models, risk management
- **Result Analysis (`src/result_analysis/`)**: Performance metrics, trading analysis, visualization
- **Research Orchestrator (`src/research_orchestrator/`)**: DAG-based universal research workflow runner, 6 built-in profiles, typed signal / model / strategy registries; scope is "data is ready → results are published" (raw data, normalization, and Qlib backend builds remain in `data_infra`)

Do not invent alternate module boundaries when an existing one already fits the task.

## 3. Data Structure & Storage Rules

- All quantitative datasets live under `data/`.
- No Python source files should be stored in `data/`; keep only datasets, derived backend artifacts, and documentation there.
- Raw and intermediate datasets should be stored in Parquet unless an existing subsystem requires another format.
- `data/qlib_data/` is reserved for Qlib backend artifacts such as calendar, instrument files, and feature bins.

## 4. Workspace Constraints

- `workspace/` is the only place for active research notebooks, prototypes, experiment scripts, and generated research artifacts.
- Organize work as follows:
  - notebooks in `workspace/research/{topic}/`
  - helper scripts in `workspace/scripts/`
  - research configs in `workspace/configs/`
  - generated outputs in `workspace/outputs/`
- The `workspace/` root should stay minimal; `README.md` and `AGENTS.md` are the only stable top-level files that should normally live there.

## 5. Root Directory Hygiene

- Keep the project root limited to configuration, documentation, and top-level directories.
- Do not accumulate ad-hoc logs, exports, temporary guides, or audit dumps in the root. Move them to `logs/` or `workspace/outputs/`.

## 6. Python Environment and Path Discipline

- Use the project virtual environment at `E:\量化系统\venv\Scripts\python.exe`.
- Install packages with `E:\量化系统\venv\Scripts\pip.exe`.
- Reusable library code in `src/` must derive paths from `config.yaml` or project-root-relative configuration rather than hardcoded machine-specific paths.
- Keep persistent temporary files inside the repository tree, not in `%TEMP%`, `AppData`, `/tmp`, or any other external path.

## 7. Durable Memory & State Tracking

`project_state.md` is the durable memory file for Codex and any other repo-aware agent working in this system.

- Update it whenever significant work lands.
- Significant work includes new datasets, pipeline changes, major bug fixes, research milestones, backtester convention changes, and architecture or rule migrations.
- Keep the "Last Updated", "Active Research Focus", and "Data Sync Status" sections current whenever the relevant facts change.

## 7.1 Long-Running Execution Visibility

- Any future script or pipeline step expected to run for a substantial amount of time must show a visible progress tracker and keep reporting current progress to the console.
- Prefer `tqdm` or periodic logging with completed/total counts, current stage, and ETA when practical.
- Operators should be able to tell from the console which stage is running and whether the job is still making forward progress.

## 8. Subagent Handoff Discipline

- Prefer the repo-local custom agent names defined under `.codex/agents/` when the runtime supports direct custom-agent spawning; fall back to the matching built-in `explorer` or `worker` only when custom names are unavailable.
- Start non-trivial work with `quant_context_mapper` so the affected module, entry points, and validation path are mapped before edits.
- Prefer parallel fan-out only for read-only work such as context gathering or review. Keep write-heavy work serialized unless file ownership is clearly disjoint.
- Use at most one writing agent per write scope.
- For bounded write tasks owned by `quant_impl_worker` or `quant_test_runner`, the parent agent should pass a self-contained assignment that names the exact write scope, expected artifacts, and validation target.
- Do not rely on broad forked conversation context as the task definition for bounded write tasks.
- A writing child should treat the latest parent message as the active assignment, stay inside the declared scope, and report a concrete blocker when no files are changed.
- Use the specialist guard before finalizing when the task touches its domain:
  - `quant_data_guardian` for `src/data_infra/` or backend/data-sync work
  - `quant_research_guard` for `src/alpha_research/` or substantive `workspace/` research work
  - `quant_backtest_auditor` for `src/backtest_engine/`, signal construction, or execution-logic work
- Treat `quant_test_runner` as the primary validation gate for behavior-changing work, and do not treat changes as trusted until that validation step provides strong evidence or explicitly states the remaining gap.
- After substantive changes, run `quant_reviewer` as the final read-only correctness review.

## 9. Strict Adherence

- Do not hallucinate architecture details; check `src/system.md` when placement is unclear.
- Before proposing new frameworks or utilities, verify whether Qlib, MLflow, the factor library, or `result_analysis` already provides the needed capability.
- Follow scoped `AGENTS.md` files for more specific subtree rules when working inside their directories.
