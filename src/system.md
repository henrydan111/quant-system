# Quantitative Trading System Architecture (`src/`)

This document is the top-level architecture guide for the source tree. It describes the live module boundaries for the local Parquet + Qlib research stack and the current Phase 3 factor-research workflow.

## Directory Overview

```text
src/
|-- data_infra/             # Data acquisition, storage, PIT backend, Qlib backend, verification
|-- alpha_research/         # Factor operators, catalog, evaluation toolkit, ML models, MLflow, registries
|-- backtest_engine/        # Vectorized screening engine and event-driven simulator
|-- portfolio_risk/         # Portfolio construction, cost models, risk modeling
|-- result_analysis/        # Performance metrics, trading stats, and reporting
`-- research_orchestrator/  # DAG-based universal research workflow runner (added 2026-04-09)
```

## 1. Data Infrastructure (`src/data_infra/`)

`data_infra` owns ingestion, storage, PIT backend assembly, and Qlib backend construction.

- `fetchers/`: Tushare client and rate-limited API wrappers
- `storage/`: Parquet layout management, Qlib export helpers, `qlib_bin_utils.py`
- `pipeline/`: supported entry points
  - `init_market_data.py`
  - `init_fundamentals_data.py`
  - `init_factor_data.py`
  - `refresh_indicator_history.py` (staged historical VIP indicator refresh)
  - `update_daily_data.py`
  - `build_qlib_backend.py` (supports `--stage full | upstream-only | provider-only`)
  - `verify_database.py`
- `cleaners/`: daily-data cleaning and adjustment helpers
- `verification/`: audit utilities such as `DataAuditor`
- `pit_backend.py`: production PIT-aware Qlib provider plumbing
- `provider_metadata.py`: provider-side metadata used by the PIT backend

Notes:

- The legacy Phase 1/Phase 2 init-script names and the removed Airflow stub are deprecated and should not be referenced as live architecture.
- The trading calendar in `data/reference/trade_cal.parquet` is the ground truth for open dates.
- `data_infra` owns everything up to "data is ready for research". Workflow scheduling on top of that lives in `research_orchestrator` (§6).

## 2. Alpha Research (`src/alpha_research/`)

`alpha_research` is the factor and model research library.

- `factor_library/`: Phase 3 two-layer factor framework
  - `hypothesis_factors.py`: immutable hypothesis YAML factor specs
  - `operators.py`: Layer 1 Qlib expression operators plus Layer 2 pandas transforms
  - `catalog.py`: central registry of the 191-factor catalog
  - `qlib_expr_guide.md`: expression syntax rules and edge cases
  - `__init__.py`: public entry points: `get_factor_catalog()`, `get_composite_defs()`, `get_industry_relative_defs()`, `compute_factors()`, `add_composites()`, `add_industry_relative_composites()`. The two industry-relative APIs added 2026-04-27 expose Layer 2 industry-mean-subtract / size+industry-neutralize composites that consume time-varying SW2021 industry labels from `provider_metadata.build_industry_series_asof`.
- `factor_eval/`: IC, quantile, neutralization, decay, correlation, plotting, statistical tests, cost-aware evaluation, and regime diagnostics
- `model_zoo/`: ML model wrappers such as LightGBM, XGBoost, and ElasticNet
- `mlflow_tracker.py`: experiment logging through MLflow
- `theme_strategy/`: theme-driven field-first strategy research framework (small_cap, st, flow_northbound)
- `factor_registry/`: file-backed formal factor registry (master / evidence / run_index / status_history / review.html)
- `candidate_registry/`: file-backed research candidate registry (currently theme_component candidates)
- `hypothesis_registry/`: formal hypothesis registry and gate-history store
- `testing_ledger.py`: append-only formal testing ledger for multiple-testing accounting
- `walk_forward.py`: shared walk-forward split primitives

Notes:

- Prefer Qlib expressions over slow ad-hoc pandas `groupby().apply()` factor pipelines whenever an operator already exists.
- Keep point-in-time safety explicit by using lagged expressions such as `Ref(..., 1)` where appropriate.

## 3. Backtest Engine (`src/backtest_engine/`)

`backtest_engine` provides two complementary execution environments.

- `vectorized/`: fast Qlib-integrated signal screening and benchmarked backtests
- `event_driven/`: realistic A-share simulator for JoinQuant parity, T+1, limits, taxes, and corporate actions

Recommended usage:

- Use `VectorizedBacktester` for broad factor and model screening.
- Use `EventDrivenBacktester` when execution realism matters, especially for corporate actions or JoinQuant comparisons.
- `EventDrivenBacktester` automatically wires `data/market/suspension/suspension_ranges.parquet` into `Exchange` when the file exists; otherwise it logs that suspension detection falls back to the legacy `vol == 0` proxy.

## 4. Portfolio and Risk (`src/portfolio_risk/`)

`portfolio_risk` translates signals into target weights while controlling exposure and costs.

- `optimizer.py`: portfolio-construction routines
- `risk_models/`: covariance and factor-risk estimation
- `cost_models/`: transaction-cost and market-impact modeling

## 5. Result Analysis (`src/result_analysis/`)

`result_analysis` is the standardized evaluation layer for both backtest engines.

- `metrics.py`: return, risk, and trading-stat functions
- `report.py`: `BacktestReport`
- `plotters.py`: dashboard and chart generation

Rule:

- Backtest metrics should be implemented here rather than duplicated in notebooks or one-off scripts.

## 6. Research Orchestrator (`src/research_orchestrator/`)

`research_orchestrator` is the unified DAG-based research workflow runner. It does not reinvent factors, signals, or backtests — it organizes existing research capabilities into a standard pipeline so different research types use the same request format, the same step structure, the same resume rules, and the same metadata / lineage / publication artifacts.

Scope boundary: **from "data is ready, research can start" to "research result is recorded and published".** Raw downloads, normalization, PIT ledger construction, and Qlib backend builds remain in `data_infra` (§1).

- `schema.py`: `ResearchRequest`, `ResearchRunResult`, typed asset specs
- `hypothesis.py`: typed hypotheses, success criteria, and split commitments
- `gate_report.py`: gate-report rendering helpers
- `window_enforcement.py`: first-layer hypothesis time-window clamp before orchestrator-owned data loading
- `holdout_seal.py`: mechanical OOS seal log
- `sealed_backtest_runner.py`: seal-aware backtest choke point for orchestrator-owned execution
- `profiles.py`: `ResearchProfile` registration and the 7 built-in profiles
- `capabilities.py`: layered 21-capability vocabulary (`core_research` / `diagnostic` / `support`)
- `dag.py` + `steps.py`: profile-to-DAG compilation, typed pause payloads, and step handler registry
- `runtime.py`: serial topological execution, per-step state, `pause_for_input` / `pause_for_gate`, strict resume gating on `request_hash + plan_hash`
- `engine.py`: built-in profile registration, request builders, runner dispatch
- `resolver.py`: formal-first asset resolution against the typed registries
- `cache_manifest.py` + `qlib_windowed_features.py`: deterministic window-aware Qlib cache guards for formal research
- `registries/`: typed `signal_registry`, `model_registry`, `strategy_registry` adapters
- `theme_strategy_steps.py`, `event_signal_steps.py`, `validation_steps.py`: profile-specific step handlers
- `prescription_runtime.py` (added 2026-04-28, plan `jolly-seeking-lollipop`): pure functions translating a `PrescribedRecipe` into universe + factor frame + composite score + target-weights schedule for the validation profile

Built-in research profiles (V2 — added `hypothesis_validation` 2026-04-28):

- `factor_screening` — discovery (auto-search factor IC + quantiles)
- `theme_strategy` — discovery (auto-search universe × component × recipe space)
- `event_driven_signal_research` — discovery (auto-search recipe space + event-driven backtest)
- `ml_signal_model_research` — discovery (ML model grid)
- `strategy_improvement` — discovery (risk overlay + stress test)
- `benchmark_audit` — diagnostic
- **`hypothesis_validation`** — validation (run a fully-prescribed recipe verbatim through IS+gate+OOS+publish; requires `hypothesis.prescription` to be set; the prescription field is ignored by all discovery profiles for backward compatibility)

CLI: `workspace/scripts/research_orchestrator_cli.py` exposes `profiles`, `plan`, `run`, and `resume`.

Operational release gate: `workspace/scripts/research_orchestrator_release_gate.py` wraps the formal orchestrator audit and returns a non-zero exit code unless `findings.csv` is empty and every row in `coverage_matrix.csv` is `passed`. Gate runs are written under `workspace/outputs/orchestrator_release_gate/`.

Run artifacts under each run directory: `dag_plan.json`, `dag_state.json`, `run_metadata.json`, `artifact_manifest.json`, `produced_objects.json`, `lineage_links.json`, `review_summary.json`, plus `steps/<step_id>/{step_metadata.json, step_outputs.json, artifact_manifest.json}`.

Resume is intentionally strict: same `run_dir`, matching `request_hash`, matching `plan_hash`. If the plan has changed, resume is refused — fix the request or start a new run.

Human gate decisions are tri-state: `approved`, `rejected`, or `quarantined`. `rejected` blocks publication; `quarantined` keeps downstream publication metadata in an `under_review` state and is preserved explicitly in the hypothesis registry.

Legacy formal entrypoints (`workspace/scripts/batch_factor_screening.py`, `src/alpha_research/theme_strategy/cli.py`, the `workspace/research/alpha_mining/event_driven_strategy_*` scripts, `audit_benchmark_index.py`) are now compatibility shims that route into the orchestrator.

## System-Wide Conventions

- Qlib `D.features()` returns `MultiIndex(instrument, datetime)`; be explicit about index order in raw pandas code.
- Research notebooks and prototypes belong in `workspace/`, not under `src/`.
- The root `AGENTS.md` and `CLAUDE.md` plus scoped `AGENTS.md` files define the agent operating contract; `project_state.md` is the durable system-memory file that should be updated after significant milestones, including any rule-file change.
