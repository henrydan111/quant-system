# Codex Operating Rules

This `AGENTS.md` file is the canonical Codex instruction layer for this repository. The files under `.agents/rules/` remain the detailed human-readable reference set and must stay aligned with these rules, but Codex should treat `AGENTS.md` as the always-on contract.

## 1. Mandatory Context Refresh

Before any non-trivial implementation, investigation, refactor, or data operation, read these files in order:

1. `project_state.md`
2. `config.yaml`
3. `src/system.md`
4. `data/data_dictionary.md`
5. `data/data_tracker.md`

Use them to re-establish current architecture, data coverage, known issues, and active priorities before making recommendations or edits.

For formal quantitative research, also follow `.agents/rules/research-integrity.md`, especially Section 10. That section explains the 10-stage lifecycle, the 5 human gates, pre-registration, sealed OOS, and multiple-testing rules.

Operationally, v3.1 formal non-audit runs now insert `gate_evaluation -> gate_concern_scoring -> gate_review` before publication. `gate_concern_scoring` is the `pause_for_input` step and now uses a typed `PauseForInputPayload` in `src/research_orchestrator/dag.py`; `gate_review` is the `pause_for_gate` step that writes the final gate report and accepts `approved`, `rejected`, or `quarantined`; seal-aware backtest execution flows through `src/research_orchestrator/sealed_backtest_runner.py`; the first pre-load date clamp lives in `src/research_orchestrator/window_enforcement.py`; and cache/window safety is then reinforced by `src/research_orchestrator/cache_manifest.py` plus `src/research_orchestrator/qlib_windowed_features.py`. `workspace/scripts/hypothesis_cli.py verify-seal` is now safe for automation: exit `0` means untouched, `1` means OOS already touched, and `2` means malformed design hash. The `--expect-claims N` flag (added 2026-04-28, plan `jolly-seeking-lollipop`) provides exact-count assertion mode (exit 0 only if claim count equals N).

**Discovery vs validation profiles (added 2026-04-28, plan `jolly-seeking-lollipop`):** the orchestrator now has 7 built-in profiles. The original 5 (`factor_screening`, `theme_strategy`, `event_driven_signal_research`, `ml_signal_model_research`, `strategy_improvement`) are **discovery** profiles — they auto-search a recipe space and pick the empirically best variant. The new `hypothesis_validation` profile (the 7th, alongside `benchmark_audit`) is a **validation** profile — it runs a fully-prescribed recipe (universe + components + weights + topk + rebalance + cost model) verbatim through IS+gate+OOS+publish with no auto-search. Use validation when you have a specific recipe to test (e.g., from prior discovery research); use a discovery profile when you want to find the best recipe within a search space. The validation profile requires `hypothesis.prescription` to be set (a `PrescribedRecipe` defined in `src/research_orchestrator/hypothesis.py`); discovery profiles ignore the prescription field. Register validation hypotheses with `hypothesis_cli.py register --profile-id hypothesis_validation` to opt into profile-aware floor validation (default validates against ALL profiles' floors — strategy_improvement is the strictest).

## 2. System Awareness

Always keep the full six-module architecture in mind:

- `src/data_infra/`: Tushare ingestion, Parquet storage, Qlib backend construction, verification
- `src/alpha_research/`: factor operators, catalog, evaluation toolkit, ML models, MLflow tracking
- `src/backtest_engine/`: vectorized screening engine and event-driven A-share simulator
- `src/portfolio_risk/`: portfolio optimization, transaction-cost, and risk-model tooling
- `src/result_analysis/`: standardized performance metrics, trading analysis, and reporting
- `src/research_orchestrator/`: DAG-based formal research entrypoint, built-in research profiles, typed registries, and run-artifact governance

When unsure where logic belongs, prefer the existing module boundary over adding new top-level scripts or ad-hoc helpers. The orchestrator's scope is “data is ready -> results are published”; raw downloads, normalization, and Qlib backend builds remain in `data_infra`.

### 2a. Hard invariants (must not break)

These correspond 1:1 with the `CLAUDE.md §3` hard invariants list. Both contracts agree on substance.

- **Tushare ↔ Qlib code format**: Tushare `000001.SZ` ↔ Qlib `000001_SZ`. Use `ts_code.replace('.', '_')` before every join. Wrong format silently returns 0 matches.
- **Benchmark codes** use the underscore form: `000300_SH`, never `SH000300`.
- **Trading calendar**: `data/reference/trade_cal.parquet` is the single ground truth.
- **ST authoritative source**: `data/qlib_data/instruments/st_stocks.txt`.
- **PIT for fundamentals**: align on `ann_date`, apply `shift(1)` after `merge_asof`, forward-fill across calendar gaps. Use provider-side `pit_*` fields for derived growth metrics.
- **PIT visibility anchor**: `effective_date > disclosure_date` STRICTLY (via `strictly_next_open_trade_day` in `src/data_infra/pit_backend.py`).
- **`f_ann_date` coverage is dataset-specific**: statement families (`income`, `income_quarterly`, `balancesheet`, `cashflow`, `cashflow_quarterly`) use `max(ann_date, f_ann_date)`; event/indicator families (`indicators`, `dividends`, `forecast`, `holder_number`) use `ann_date` only.
- **Delist / IPO-lag contract**: enforced at the instruments sidecar (`all_stocks.txt`) via `provider_metadata.build_all_stocks_universe()`. Direct PIT ledger readers must apply `provider_metadata.stock_basic_bounds(ts_code)` themselves.
- **Cumulative→quarterly late restatement**: `derive_single_quarter_value` retroactively changes derived quarter values when a prior quarter's cumulative is restated. Research code caching quarter values must invalidate on every ledger rebuild.
- **MultiIndex order**: Qlib `D.features()` returns `MultiIndex(instrument, datetime)` — not `(datetime, instrument)`.
- **Negation in Qlib expressions**: `-Operator(...)` does not parse. Use `0 - Operator(...)`.
- **Qlib expressions for predictive factors**: same-day leakage is the most common bug. See below for the factor-library specific enforcement.
- **Factor library PIT-safety (post follow-up plan #1, 2026-04-11)**: every `$field` reference inside every Layer 1 operator in `src/alpha_research/factor_library/operators.py` MUST be wrapped inside a `Ref(...)` frame. The correct pattern is `Mean(Ref($close, 1), 20)`, NOT `Mean($close, 20)`. Use the `ADJ_*_T1` module constants for shifted adjusted prices. `forward_return` is the ONE allowlisted exception. Enforcement lives in `tests/alpha_research/test_factor_library_pit_safety.py` (parser-based static analysis), `test_operator_expressions.py` (per-operator lock tests), and `test_operator_behavioral_pit.py` (tiny-Qlib-fixture behavioral proof).
- **Adjusted vs raw prices**: adjusted prices for cross-day returns/momentum; raw values for PIT accounting ratios. Document the choice in any new factor.
- **Publish atomicity**: `StagedQlibBackendBuilder.publish()` hard-fails on cross-volume rename. Move the staged build onto the target volume before publishing.
- **Deterministic rebuild**: `_normalize_periodic_dataset` injects `_src_file` / `_src_ordinal` hidden columns so `collapse_duplicate_versions` and `canonicalize_report_variants` produce bit-identical output across machines.
- **Exchange cost source of truth (post follow-up plan #2, 2026-04-14)**: stamp tax, commission, and transfer fee flow through `exchange.compute_sell_cost_breakdown()` / `compute_buy_cost_breakdown()`. Do NOT duplicate rate checks in the engine or portfolio. `_STAMP_TAX_CHANGE_DATE` in `exchange.py` is the single boundary.
- **CostConfig defaults are JoinQuant (changed 2026-05-22)**: `CostConfig()` matches JoinQuant `OrderCost` (close_tax 0.001 constant, no 2023 cut, no transfer fee). For realistic Chinese exchange rules use `CostConfig.realistic_china()`. Enforcement: `tests/backtest_engine/test_exchange_costs.py::CostConfigPresetTests`.
- **Exchange default slippage is JoinQuant (changed 2026-05-22)**: `Exchange()` defaults to `FixedSlippage(0.0003)` (matches JoinQuant `FixedSlippage(3/10000)`). The prior 10-bps default is the named constant `CONSERVATIVE_SLIPPAGE_10BPS`. Zero-cost fills still require explicit `NoSlippage()`. `PctSlippage(0.0003)` ≠ `FixedSlippage(0.0003)` — prefer named constants.
- **Limit prices use round-half-up**: `exchange.compute_limit_prices()` uses `Decimal.quantize(ROUND_HALF_UP)`, not Python banker's rounding.
- **Event-driven suspension wiring**: `EventDrivenBacktester` must pass `data/market/suspension/suspension_ranges.parquet` into `Exchange` when the file exists. If absent, it must log the fallback and `Exchange.is_suspended()` uses the legacy `vol == 0` proxy.
- **Event-like daily endpoint namespacing (2026-04-20)**: `_materialize_daily_dataset` in `src/data_infra/pit_backend.py` writes per-column `.day.bin` files AFTER `_run_dump_bin` writes the canonical kline bins (`$open/$high/$low/$close/$vol/$amount`). Some event-like daily endpoints ship payload columns that collide with those names — `top_list` has `close`/`amount`, `block_trade` has `vol`/`amount`. Every dataset in `EVENT_LIKE_DAILY_DATASETS` (`top_list`, `top_inst`, `block_trade`, `cyq_perf`) MUST have an entry in `EVENT_LIKE_DAILY_FIELD_PREFIX`, and its payload columns are written as `{dataset}__{column}.day.bin` (e.g., `$top_list__close`, `$block_trade__amount`, `$cyq_perf__winner_rate`). Enforcement: `tests/data_infra/test_event_like_daily_namespace.py`.
- **No hedge words in quantitative analysis (2026-05-20)**: when analyzing a strategy result, a discrepancy between backtests, or any quantitative claim, do NOT use "likely", "possibly", "probably", "appears to", "seems to", "could be", "might be", or any other epistemic hedge. Either cite the exact data/script/output that establishes the claim with certainty, or explicitly mark the claim "HYPOTHESIS:" with a stated falsification plan and run that test. Banned failure mode: presenting plausible-sounding guesses as conclusions. Mirror lives in `CLAUDE.md` §7 item 10 and `.agents/rules/research-integrity.md` §8a.

## 3. Root, Workspace, and Data Hygiene

- Keep the project root limited to configuration, documentation, and top-level directories. Move ad-hoc outputs to `logs/` or `workspace/outputs/`.
- `workspace/` is the only place for active notebooks, experiments, prototypes, and research-only helper scripts.
- `data/` is for datasets and documentation only. Do not place Python source files inside `data/`.
- Do not use external temp directories such as `%TEMP%`, `AppData`, `/tmp`, or other paths outside `E:\量化系统\` for persistent project artifacts.

## 4. Python Environment and Path Discipline

- Use the project virtual environment at `E:\量化系统\venv\Scripts\python.exe`.
- Install packages with `E:\量化系统\venv\Scripts\pip.exe`.
- Reusable code under `src/` must derive paths from `config.yaml` or project-root-relative configuration, never hardcoded machine-specific paths.
- One-off research scripts under `workspace/scripts/` may use explicit local paths when necessary, but should still prefer config-driven paths when practical.

## 5. Logging and Operational Discipline

- Use `logging`, not `print()`, in reusable modules and production scripts.
- Route operational logs to `logs/` with rotation for long-running or recurring scripts.
- Any future script or pipeline step expected to take substantial time must include a visible progress tracker and regularly print current progress to the console. Prefer `tqdm` or periodic logging with completed/total counts and ETA when practical.
- For meaningful system changes, data syncs, milestone completions, or architecture/rule updates, record the outcome in `project_state.md`.

## 6. State Tracking and Rule-File Maintenance

### 6.1 project_state.md

`project_state.md` is the durable project memory. Update it after significant work, including:

- new datasets or pipeline entry points
- major bug fixes or architecture changes
- backtester behavior changes or new research conventions
- data sync status changes
- rule migrations such as this Codex/AGENTS transition
- **any update to `AGENTS.md`, `CLAUDE.md`, or `.agents/rules/`** — rule changes are themselves significant work

Also keep "Last Updated", active focus, and data sync sections current when they are affected.

### 6.2 Keep AGENTS.md, CLAUDE.md, and .agents/rules/ fresh (standing instruction)

This is non-optional. Stale rule files actively mislead future sessions and are worse than no rule files.

- **At the start of every non-trivial task**, during the §1 context refresh, also skim `AGENTS.md` and `CLAUDE.md` against `project_state.md`. If `project_state.md` describes architecture, entry points, registries, or workflow facts that the rule files contradict or omit, fix the rule files **before** proceeding with the task.
- **At the end of every substantive change** to `src/`, pipeline entry points, registries, research workflow, naming conventions, hard invariants, or anti-patterns, check whether `AGENTS.md`, `CLAUDE.md`, and the matching `.agents/rules/*.md` still describe reality. If not, update them in the same session as the change, not "later".
- **Drift signals to watch for:**
  - A module exists in `src/` but is not listed in `AGENTS.md` / `CLAUDE.md` / `src/system.md` (example: `src/research_orchestrator/` is the 6th top-level module — older copies of `src/system.md` may still describe a five-module layout). New file `src/research_orchestrator/prescription_runtime.py` (added 2026-04-28) is part of the validation profile and must be listed when describing the orchestrator's internals.
  - A pipeline entry point listed in the rule files no longer exists in `src/data_infra/pipeline/`, or a new one exists that is not listed.
  - A "deprecated" name in the rule files has actually been deleted, or a name marked live has been deprecated.
  - A scoped `AGENTS.md` inside a subdirectory contradicts this root contract.
  - A research convention recorded in `project_state.md` is missing from the rule files.
  - A registry was added, removed, or moved across `data/`.
  - A new built-in research profile was added to `src/research_orchestrator/profiles.py` (registered via `engine.py:_register_builtin_profiles`) but is not listed in the rule files. Current count: 7 (factor_screening, theme_strategy, event_driven_signal_research, ml_signal_model_research, strategy_improvement, benchmark_audit, hypothesis_validation).
- **Alignment contract.** `AGENTS.md` and `CLAUDE.md` must agree on substance even though they differ in tone and audience. The §1 context-refresh list, the module list, the hard invariants, the live entry points, the data ops rules, the research integrity rules, the backtest pipeline, the banned anti-patterns, and the venv path must read the same in both files. The Codex-specific subagent matrix in §8 of this file and the Claude-specific tool sections in `CLAUDE.md` are the legitimate places to diverge. If you update a rule in one file, update the matching rule in the other in the same edit pass.
- **Record rule changes in `project_state.md`** so the audit trail of how the agent contract evolved lives next to the audit trail of how the system evolved.

## 7. Scope and Overrides

More specific `AGENTS.md` files inside subdirectories refine these global rules for their subtree. When both apply, follow the more specific scoped file in addition to this root contract.

## 8. Subagent Workflow

- Prefer the repo-local custom agent names defined under `.codex/agents/` when the runtime supports direct custom-agent spawning.
- Treat the files under `.codex/agents/` as the source-of-truth agent definitions for this repository.
- If a restricted integration exposes only built-in agent types, fall back to the matching built-in `explorer` or `worker` and have it follow the corresponding repo-local role brief.
- The root Codex session remains the orchestrator. Do not spawn a child agent whose only job is orchestration.
- Start non-trivial work with `quant_context_mapper` so the affected module, entry points, and validation path are established before edits.
- Prefer parallel fan-out only for read-only work such as context gathering or review. Keep write-heavy work serialized unless file ownership is clearly disjoint.
- Use at most one writing agent per write scope. Parallel writers are acceptable only when they have explicitly disjoint file ownership and the parent agent can integrate the results safely.
- For `quant_impl_worker` and `quant_test_runner`, pass a self-contained assignment with the exact write scope, expected artifacts, and validation target. Do not rely on broad forked conversation context as the task definition for bounded write tasks.
- For `src/data_infra/` or backend/data-sync work, run `quant_data_guardian` before finalizing. Never run parallel Tushare fetchers against the same account.
- For `src/alpha_research/` or substantive `workspace/` research work, run `quant_research_guard` before accepting the result.
- For `src/backtest_engine/`, signal construction, or execution-logic changes, run `quant_backtest_auditor` before accepting the result.
- Treat `quant_test_runner` as the primary validation gate for any behavior-changing work. It may add or strengthen durable test assets and validation scripts, not just run existing checks.
- Any change to calculations, data pipelines, factors, backtests, execution logic, portfolio/risk logic, or result-analysis behavior must go through `quant_test_runner` before sign-off.
- Changes are not considered trusted until that validation `worker` either provides strong evidence of correctness or explicitly reports the remaining validation gap.
- After substantive changes, run `quant_test_runner` before a final read-only `quant_reviewer`; for high-risk numerical or methodology-sensitive work, prefer specialist guard review plus validation worker plus final reviewer.
- Keep `agents.max_depth = 1` unless nested delegation becomes demonstrably necessary. Prefer more precise top-level orchestration over recursive spawning.

### Restricted-Surface Fallback Mapping

| Custom agent | Built-in fallback | Use |
|-----------|-------------------|-----|
| `quant_context_mapper` | `explorer` | Read-only context mapping, entry-point discovery, validation-path discovery |
| `quant_impl_worker` | `worker` | Bounded implementation in an assigned write scope |
| `quant_test_runner` | `worker` | Validation ownership, test creation, and regression checking |
| `quant_data_guardian` | `explorer` | Read-only data-infrastructure safety review |
| `quant_research_guard` | `explorer` | Read-only research-integrity review |
| `quant_backtest_auditor` | `explorer` | Read-only backtest and signal-pipeline review |
| `quant_reviewer` | `explorer` | Final read-only correctness review |

### Default Spawn Matrix

| Task shape | Default spawn path |
|-----------|--------------------|
| Small local task | Stay in the root session unless the area is unfamiliar. |
| Medium single-module code task | `quant_context_mapper` -> optional domain guard -> `quant_impl_worker` -> `quant_test_runner` -> `quant_reviewer` |
| Large or cross-module task | `quant_context_mapper` plus relevant read-only guards in parallel -> one writer per disjoint scope -> `quant_test_runner` -> `quant_reviewer` |
| Data ingestion, storage, or Qlib backend work | Always include `quant_data_guardian` and `quant_test_runner`; never parallelize Tushare fetchers. |
| Factor engineering, labels, experiments, or research scripts | Always include `quant_research_guard` and `quant_test_runner` before sign-off. |
| Signal construction, masks, execution logic, or parity work | Always include `quant_backtest_auditor` and `quant_test_runner` before sign-off. |
| Write-heavy work | Prefer one writer; parallel writers are allowed only when file ownership is clearly disjoint. |
