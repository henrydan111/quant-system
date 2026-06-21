# Quantitative Trading System Architecture (`src/`)

This document is the top-level architecture guide for the source tree. It describes the live module boundaries for the local Parquet + Qlib research stack and the current Phase 3 factor-research workflow.

## 0. Canonical Function Map — check before writing new code

This is the antidote to reinventing the wheel. §3 of `CLAUDE.md` says what NOT to break; the sections
below say what each module *is*; **this map says: for this task, call THIS — and never hand-roll THAT.**
Before adding any helper, pipeline, metric, or data read, find your task here first. If it is genuinely
not here, say so explicitly and propose adding a row. (This is a curated list of canonical entry points,
not an exhaustive index — keep it short. The orchestrator-internal `capabilities.py` vocabulary is a
different, unrelated concept.) The guard test `tests/architecture/test_canonical_function_map.py` checks
path/symbol existence + doc↔registry sync only — NOT semantic completeness, so a canonical workflow that
is simply absent won't be flagged; add a row whenever you add one.

### Data access

| I need to… | Call this | Never do this |
|---|---|---|
| Load PIT fundamentals in research/sandbox | `pit_research_loader.load_pit_signal_panel` (lag-1, default) / `load_pit_asof_panel` (lag-0) — `src/data_infra/pit_research_loader.py` | Read `data/pit_ledger/*` directly; hand-roll PIT alignment; string-compare date columns (PIT002 lint = hard error) |
| Read Qlib features in formal research | `qlib_windowed_features(...)` — `src/research_orchestrator/qlib_windowed_features.py` | Call `D.features` directly (AST lint bans it; the wrapper is the only door) |
| Check if a `$field` is allowed at a stage | `FieldStatusRegistry.resolve_field` / `validate_expression`; `extract_qlib_fields` — `src/data_infra/field_registry.py` | Assume a field is usable; reference a quarantined/pending field in a formal expression |
| Trading-day / ST ground truth | `data/reference/trade_cal.parquet` / `data/qlib_data/instruments/st_stocks.txt` | Assume business days == trading days; use `stock_st_daily.parquet` alone |

### Provider / backend ops

| I need to… | Call this | Never do this |
|---|---|---|
| Build / refresh / publish / verify the local Qlib provider | `src/data_infra/pipeline/build_qlib_backend.py` (`--stage full\|upstream-only\|provider-only`), `update_daily_data.py`, `verify_database.py`; publish via `StagedQlibBackendBuilder.publish()` — `src/data_infra/pit_backend.py` | Copy/rename `data/qlib_data/` by hand; bypass staged publish or its `BuildGateError` same-volume guard; run a `mode=all` full rebuild without cause |

### Factors

| I need to… | Call this | Never do this |
|---|---|---|
| Get factor definitions (authoritative, ALL discovery) | `get_factor_catalog()` (+ `get_composite_defs()`, `get_industry_relative_defs()`) — `src/alpha_research/factor_library/` | Re-define a factor expression inline |
| Compute factor values | `compute_factors()`, then `add_composites()` / `add_industry_relative_composites()` | Slow bespoke `groupby().apply()` when a Qlib operator exists |
| Status-filtered factor selection (sandbox only) | `selection.get_factors` / `get_factor_selection` — `src/alpha_research/factor_library/selection.py` (raises at formal stages) | Use these as a formal gate — formal resolves through the orchestrator allow-set |
| Standard factor evaluation / batch screening | `src/alpha_research/factor_eval/` ; `run_batch_screening(engine="batch", horizons=...)` — `src/alpha_research/factor_eval/batch_screening.py` | Reimplement IC/quantile math; hand-roll a screening loop or a wrong-horizon LS-Sharpe |

### Factor lifecycle, selection & sealed OOS

| I need to… | Call this | Never do this |
|---|---|---|
| 7-universe in-sample evaluation matrix | `workspace/scripts/unified_eval_universe_matrix.py` (engine `_evaluate_batch` in `unified_eval_full_run.py`; metrics in `src/alpha_research/factor_eval/unified_eval.py`) → `results.jsonl` | Hand-roll a per-universe IC loop or a second matrix; re-derive `STYLE_CONTROLS_V1` / the residual-vs-controls pipeline |
| Grade a `draft` → `candidate` (IS-only) | `assign_candidate_status` + `run_is_walk_forward` — `src/alpha_research/factor_lifecycle/` (`|rank_icir|≥0.10 ∧ sign≥0.70`, `is_end`-bounded) | Re-implement the thresholds or the IS-only walk-forward; emit any `oos_*` field in the IS gate |
| Replication / availability status-ceiling (P-GATE) | `resolve_replication_ceiling` — `src/alpha_research/factor_registry/replication_governance.py` (`STATUS_CEILINGS` + cap reasons; `coverage_tier=='sub'` → `availability_floor_fail`) | Build a parallel status-ceiling / `status_effect` universe |
| Freeze a selected set + claim the single-shot OOS seal | `FrozenSelectionSet` (`frozen_set_hash`) — `src/research_orchestrator/frozen_selection_set.py` ; `HoldoutSealStore.claim_holdout_access(seal_key=frozen_set_hash)` — `src/research_orchestrator/holdout_seal.py` | Re-roll a seal ledger; key OOS budget by a mutable `design_hash` |
| Run / reproduce a sealed OOS (factor-level) | `reproduce_sealed_oos` (+ `produce_promotion_evidence`) — `src/research_orchestrator/promotion_evidence.py` (`n_quantiles=10`; sign-aligned `rank_icir>0 ∧ ls_sharpe>1.0`) | Hand-roll the OOS leg, a wrong-`n_quantiles` / wrong-horizon LS-Sharpe, or a bare-`D.features` OOS read |
| Marginal / redundancy of a factor vs the book | `compute_marginal_ic` — `src/alpha_research/factor_eval/ic_analysis.py` ; book-marginality = the matrix `resid_ic_vs_approved_stable_*` fields | Recompute residual-vs-book; re-derive the exposure-corr greedy — use `factor_eval_skill.marginal.select_marginal` (the E-wave `select_e_wave_marginal.py` is now a thin caller of it) |

### Factor-eval skill (Part-G contracts/orchestration — `src/alpha_research/factor_eval_skill/`)

Thin contracts/orchestration layer for the factor-evaluation methodology (v1.3). Reuses every engine in the tables above verbatim; build the methodology workflow here, not in a new cohort script.

| I need to… | Call this | Never do this |
|---|---|---|
| Identity objects + the seal identity chain | `TargetUniverseDeclaration` / `SelectedSet` / `FrozenSelectionEnvelope` / `DeploymentFrozenPlan` + `assert_identity_chain` — `src/alpha_research/factor_eval_skill/identity.py` (the envelope WRAPS `frozen_set_hash`, never re-hashes it; deterministic `envelope_hash`) | Add `tud_hash` to the `FrozenSelectionSet` payload (orphans the spent seal); skip `assert_identity_chain` in select/seal/deploy |
| Per-factor provenance / role / Stage-3 / filter sidecars | `FactorProvenanceStore` / `RoleDeclarationStore` / `Stage3QualityRecordStore` / `FilterCharacterizationStore` / `FilterDeploymentGateStore` / `FrozenSelectionEnvelopeStore` — `src/alpha_research/factor_eval_skill/stores.py` (append-only, file-locked) | Add columns to `factor_master`; store target-scoped quality flags per-factor (they are per factor×target×methodology) |
| Stage-3 machine-binding caps (target+role-aware) | `stage3_caps(... governance=Stage3GovernanceInputs.native()/.cohort(...))` — `src/alpha_research/factor_eval_skill/stage3_reader.py` (calls `resolve_replication_ceiling` + `assign_candidate_status`; `MatrixResults.from_jsonl(strict=True)`) | Pass permissive governance defaults for a cohort factor (use `.cohort(...)`); re-implement the ceiling or the IS bar |
| Generic marginal selection / sealed-OOS bar / deployment composite | `select_marginal` / `direction_aligned_pass`+`run_sealed_oos` / `direction_aligned_composite`+`run_deployment` — `src/alpha_research/factor_eval_skill/marginal.py`, `sealed_oos.py`, `deployment.py` | Clone a cohort eval script; treat a non-`long`/`short` value as a held side |
| Run the methodology end-to-end (the two skills) | `workspace/scripts/factor_eval_cli.py` (register\|declare_target\|characterize\|gate\|select\|seal) + `workspace/scripts/strategy_build_cli.py` (deploy); handlers in `src/alpha_research/factor_eval_skill/orchestration.py` (`FactorEvalContext`, `cmd_*`, `resolve_governance`) | Let `factor-eval` deploy or `strategy-build` seal (verb sets are split); infer `native()` on a failed manifest lookup; skip `assert_identity_chain` at seal/deploy |

### Backtesting & execution

| I need to… | Call this | Never do this |
|---|---|---|
| Fast signal screening | `VectorizedBacktester` — `src/backtest_engine/vectorized/` | Use it where execution realism matters |
| Realistic / formal backtest | `EventDrivenBacktester.run(execution_profile=…, calendar_policy_id=…, run_mode=…)` — `src/backtest_engine/event_driven/` | Run formal without preload (100× slower) or without `execution_profile` + `calendar_policy_id` |
| Buy/sell cost breakdown | `Exchange.compute_buy_cost_breakdown` / `compute_sell_cost_breakdown` — `src/backtest_engine/event_driven/exchange.py` | Duplicate tax/commission/过户费 logic in the engine or portfolio |
| Cost / slippage presets | `CostConfig()` (JoinQuant) / `CostConfig.realistic_china()` ; `JOINQUANT_DEFAULT_SLIPPAGE` / `CONSERVATIVE_SLIPPAGE_10BPS` | Inline cost or slippage literals |

### Metrics, reporting, tracking

| I need to… | Call this | Never do this |
|---|---|---|
| Sharpe / MDD / turnover / win-rate | `src/result_analysis/metrics.py` | Reimplement any metric in a notebook (add it to metrics.py) |
| Backtest report | `BacktestReport` — `src/result_analysis/report.py` | Build ad-hoc report objects |
| Log a substantive run | `ExperimentTracker` — `src/alpha_research/mlflow_tracker.py` | Skip MLflow logging on model-training / backtest runs |

### Orchestration, hypotheses, promotion

| I need to… | Call this | Never do this |
|---|---|---|
| Run formal research | orchestrator profiles via `workspace/scripts/research_orchestrator_cli.py` (`plan`/`run`/`resume`); 8 built-in profiles | Write a new top-level research script outside the orchestrator |
| Register / validate a hypothesis | `workspace/scripts/hypothesis_cli.py` | Bypass the gated lifecycle |
| Produce promotion evidence | `produce_promotion_evidence` (self-verifies through the gate) — `src/research_orchestrator/promotion_evidence.py`; canaries `src/data_infra/pit_canaries.py` | Hand-assemble a promotion_evidence dict |
| Promote a factor's status | `FactorRegistryStore.set_status` (writer gate: git_sha + promotion_evidence) | Edit registry master tables outside the publish path |

### Portfolio (⚠ dormant)

`PortfolioOptimizer` (cvxpy) lives at `src/portfolio_risk/optimizer.py`, but the module is **dormant** per
the 2026-05-26 audit: `predict_portfolio_risk()` returns a hardcoded `0.05` and `MultiFactorRiskModel.fit()`
is a no-op. Formal-path modules must NOT import the dormant symbols.

---

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
  - `catalog.py`: central registry of the factor catalog (base + industry-relative + Layer-2 composites). The count is DERIVED — call `catalog_composition()` (the single source of truth); never hard-code it. Adding a factor needs no test/doc count edits (parity is structural in test_factor_registry.py).
  - `qlib_expr_guide.md`: expression syntax rules and edge cases
  - `__init__.py`: public entry points: `get_factor_catalog()`, `catalog_composition()` (live count, single source of truth), `get_composite_defs()`, `get_industry_relative_defs()`, `compute_factors()`, `add_composites()`, `add_industry_relative_composites()`. The two industry-relative APIs added 2026-04-27 expose Layer 2 industry-mean-subtract / size+industry-neutralize composites that consume time-varying SW2021 industry labels from `provider_metadata.build_industry_series_asof`.
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
- `profiles.py`: `ResearchProfile` registration and the 8 built-in profiles (the 8th, `factor_lifecycle`, is the IS-only `draft→candidate` factor gate — start-to-finish guide: [alpha_research/factor_lifecycle/README.md](alpha_research/factor_lifecycle/README.md))
- `factor_lifecycle_steps.py`: the 4 `factor_lifecycle` handlers (resolver / dataset_build / walk_forward / registry_publish)
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
