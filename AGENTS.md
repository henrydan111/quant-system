# Codex Operating Rules

This `AGENTS.md` file is the canonical Codex instruction layer for this repository. The files under `.agents/rules/` remain the detailed human-readable reference set and must stay aligned with these rules, but Codex should treat `AGENTS.md` as the always-on contract.

## 1. Mandatory Context Refresh

Before any non-trivial implementation, investigation, refactor, or data operation, read these files in order:

1. `project_state.md`
2. `config.yaml`
3. `src/system.md` — top-level src architecture; its **§0 Canonical Function Map** lists the verified function for each task — consult it before writing new code, to reuse instead of reinventing
4. `data/data_dictionary.md`
5. `data/data_tracker.md`

Use them to re-establish current architecture, data coverage, known issues, and active priorities before making recommendations or edits.

For formal quantitative research, also follow `.agents/rules/research-integrity.md`, especially Section 10. That section explains the 10-stage lifecycle, the 5 human gates, pre-registration, sealed OOS, and multiple-testing rules.

Operationally, v3.1 formal non-audit runs now insert `gate_evaluation -> gate_concern_scoring -> gate_review` before publication. `gate_concern_scoring` is the `pause_for_input` step and now uses a typed `PauseForInputPayload` in `src/research_orchestrator/dag.py`; `gate_review` is the `pause_for_gate` step that writes the final gate report and accepts `approved`, `rejected`, or `quarantined`; seal-aware backtest execution flows through `src/research_orchestrator/sealed_backtest_runner.py`; the first pre-load date clamp lives in `src/research_orchestrator/window_enforcement.py`; and cache/window safety is then reinforced by `src/research_orchestrator/cache_manifest.py` plus `src/research_orchestrator/qlib_windowed_features.py`. `workspace/scripts/hypothesis_cli.py verify-seal` is now safe for automation: exit `0` means untouched, `1` means OOS already touched, and `2` means malformed design hash. The `--expect-claims N` flag (added 2026-04-28, plan `jolly-seeking-lollipop`) provides exact-count assertion mode (exit 0 only if claim count equals N).

**Discovery vs validation profiles (added 2026-04-28, plan `jolly-seeking-lollipop`; 8th profile added Phase 5):** the orchestrator now has 8 built-in profiles (the 8th, `factor_lifecycle`, is the IS-only `draft→candidate` factor gate — see §2a Phase-5 entry). The original 5 (`factor_screening`, `theme_strategy`, `event_driven_signal_research`, `ml_signal_model_research`, `strategy_improvement`) are **discovery** profiles — they auto-search a recipe space and pick the empirically best variant. The new `hypothesis_validation` profile (the 7th, alongside `benchmark_audit`) is a **validation** profile — it runs a fully-prescribed recipe (universe + components + weights + topk + rebalance + cost model) verbatim through IS+gate+OOS+publish with no auto-search. Use validation when you have a specific recipe to test (e.g., from prior discovery research); use a discovery profile when you want to find the best recipe within a search space. The validation profile requires `hypothesis.prescription` to be set (a `PrescribedRecipe` defined in `src/research_orchestrator/hypothesis.py`); discovery profiles ignore the prescription field. Register validation hypotheses with `hypothesis_cli.py register --profile-id hypothesis_validation` to opt into profile-aware floor validation (default validates against ALL profiles' floors — strategy_improvement is the strictest). **Factor lifecycle (start-to-finish overview):** how a factor moves `draft → candidate → approved` (status ladder, no-lookahead label boundary, the 4-step IS-only gate, phase map 1–7, current registry state, invariants) — see `src/alpha_research/factor_lifecycle/README.md`.

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

These correspond 1:1 with the `CLAUDE.md §3` hard invariants list — both contracts agree on substance.
Each entry is the rule that holds now + where it is enforced. Full implementation/review history (every
"PR N", "Blocker", "round-N review", commit SHA, test tally) lives in `project_state.md`; search the
PR/Phase id there. Do not re-narrate history here. Change a rule → change its enforcing test → mirror the
edit into `CLAUDE.md §3` in the same pass (§6.2).

#### 2a.1 Data & code-format invariants (corrupt silently if violated)

- **Tushare ↔ Qlib code format**: Tushare `000001.SZ` ↔ Qlib `000001_SZ`. Use `ts_code.replace('.', '_')` before every join. Wrong format silently returns 0 matches.
- **Benchmark codes** use the underscore form: `000300_SH`, never `SH000300`. Qlib's built-in `CSI300_BENCH` does not work with the custom backend.
- **Trading calendar**: `data/reference/trade_cal.parquet` is the single ground truth. Business days ≠ trading days.
- **ST authoritative source**: `data/qlib_data/instruments/st_stocks.txt` (range form; covers the 2020-01-02 gap).
- **Delist / IPO-lag contract**: enforced at the instruments sidecar (`all_stocks.txt` via `provider_metadata.build_all_stocks_universe()`). `D.features()` consumers inherit it; direct `data/pit_ledger/*.parquet` readers MUST filter via `provider_metadata.stock_basic_bounds(ts_code)`. Enforced: `tests/data_infra/test_provider_boundary.py`.
- **MultiIndex order**: `D.features()` returns `MultiIndex(instrument, datetime)`, NOT `(datetime, instrument)`. Be explicit in raw pandas; `groupby(level=0)` is per-instrument only when levels are not swapped.

#### 2a.2 PIT correctness (any lookahead invalidates the research)

- **PIT for fundamentals**: align on `ann_date` (never `end_date`); apply `shift(1)` after `merge_asof`; forward-fill across calendar gaps. `pit_*` provider fields are the canonical PIT-derived growth fields.
- **PIT visibility anchor**: `effective_date > disclosure_date` STRICTLY, via `next_open_trade_day` / `strictly_next_open_trade_day` (`src/data_infra/pit_backend.py`). Enforced: `tests/data_infra/test_pit_backend.py` — do not change the function without updating the invariant tests.
- **`f_ann_date` is dataset-specific**: the 5 statement families use `max(ann_date, f_ann_date)`; the 4 event/indicator families (`indicators`, `dividends`, `forecast`, `holder_number`) use `ann_date` only. A future schema adding it → set `f_ann_date_column` in the `DATASET_SPECS` entry.
- **Cumulative→quarterly late restatement**: `derive_single_quarter_value` retroactively changes a derived current-quarter value at a restatement's effective date (intentional). Cached quarter values must invalidate on every ledger rebuild.
- **Factor-library PIT-safety**: every `$field` in every Layer-1 operator in `src/alpha_research/factor_library/operators.py` MUST sit inside a `Ref(...)` frame (`Mean(Ref($close, 1), 20)`); use the `ADJ_*_T1` constants. `forward_return` is the one allowlisted exception. Enforced: `tests/alpha_research/test_factor_library_pit_safety.py` (+ `test_operator_expressions.py`, `test_operator_behavioral_pit.py`).
- **Predictive expressions**: prefer `Ref(..., 1)` for next-day trading; `-Operator(...)` does not parse — use `0 - Operator(...)`.
- **Adjusted vs raw prices**: adjusted for cross-day return/momentum; raw for PIT accounting ratios. Document the choice in any new factor.
- **PIT research access — two sanctioned front doors only**: research/sandbox via `src/data_infra/pit_research_loader.py` (`load_pit_signal_panel` lag-1 default / `load_pit_asof_panel` lag-0); formal via `src/research_orchestrator/qlib_windowed_features.py`. Both share the stateful-q0 kernel `src/data_infra/pit_alignment_core.py`. NEVER hand-roll PIT alignment, read `pit_ledger/*` outside the loader/builder, or string-compare date columns. Loader is fail-closed + bound to the production provider (the oracle). Enforced: PIT002 lint `scripts/lint_no_unsafe_pit_dates.py` + parity test `tests/data_infra/test_pit_loader_provider_parity.py`, both in `run_daily_qa`.

#### 2a.3 Execution & cost realism (backtest fidelity)

- **Exchange cost source of truth**: tax, commission, 过户费 all flow through `exchange.compute_sell_cost_breakdown()` / `compute_buy_cost_breakdown()`; engine passes `breakdown.total` to `portfolio.sell/buy`. No duplicated rate checks; 2023-08-28 boundary only in `_STAMP_TAX_CHANGE_DATE`. Enforced: `tests/backtest_engine/test_exchange_costs.py`.
- **CostConfig defaults are JoinQuant**: `CostConfig()` = JoinQuant OrderCost equivalent (`close_tax=0.001` constant, `2.5/10000`, `min 5`, `transfer_fee=0`); the real exchange = `CostConfig.realistic_china()`. Enforced: `test_exchange_costs.py::CostConfigPresetTests`.
- **Exchange default slippage is JoinQuant**: `Exchange()` defaults to `FixedSlippage(0.0003)`; the 10 bps conservative default is the named constant `CONSERVATIVE_SLIPPAGE_10BPS`. Use named constants `JOINQUANT_DEFAULT_SLIPPAGE` / `CONSERVATIVE_SLIPPAGE_10BPS`, never inline literals (`PctSlippage(0.0003)` ≠ `FixedSlippage(0.0003)`, ~10× apart for microcaps). Enforced: `test_exchange_slippage.py`.
- **Limit prices use round-half-up**: `compute_limit_prices()` uses `Decimal.quantize(ROUND_HALF_UP)`. Enforced: `test_exchange_limits.py`.
- **Limit detection**: `Exchange.resolve_limit_prices()` prefers Tushare `$up_limit`/`$down_limit` (bare-name day bins), falls back to `compute_limit_prices(pre_close, band)` only when absent/NaN. The published field carries fen-rounding, ex-rights, the pre-2023 +44%/−36% IPO rule, and post-2023 no-limit windows. `$up_limit`/`$down_limit` are in `ENGINE_REQUIRED_FIELDS`; `stk_limit` is `approved` (session-open-knowable, no `Ref` lag). Enforced: `test_exchange_limits.py::ResolveLimitPricesTests`.
- **Event-driven suspension wiring**: `EventDrivenBacktester` passes `suspension_ranges.parquet` into `Exchange` when present; else logs the fallback to `vol == 0`. Enforced: `test_event_driven_backtester_wiring.py`.
- **Event-like daily endpoint namespacing**: `_materialize_daily_dataset` writes `{dataset}__{column}.day.bin` for every dataset in `EVENT_LIKE_DAILY_DATASETS` (`top_list`, `top_inst`, `block_trade`, `cyq_perf`) to avoid clobbering canonical kline bins; each must also be in `EVENT_LIKE_DAILY_FIELD_PREFIX`. Access via `$top_list__close` etc. Enforced: `test_event_like_daily_namespace.py`.
- **ENGINE_REQUIRED_FIELDS**: the 8-field tuple (`$open $close $high $low $vol $amount $pre_close $adj_factor`) in `src/backtest_engine/event_driven/constants.py`; `EventDrivenBacktester.run()` unions caller `preload_fields` with it whenever preloading.
- **Price-return (vectorized) vs total-return (event-driven)**: `VectorizedBacktester` (`deal_price='close'`, RAW `$close`) reports a PRICE return — a dividend/bonus ex-date drops price without crediting the distribution, understating a yield book by ~its yield. `EventDrivenBacktester` credits post-tax cash dividends + bonus shares on the ex-date via `CorporateActionHandler.process` (`src/backtest_engine/event_driven/corporate_actions.py`) → TOTAL return (the deployment figure). Don't compare a vectorized price-return screen against an event-driven total-return run for a dividend-paying book without accounting for the gap. Verified (long_only value book 2021-26): EventDriven +11.64% vs vectorized +6.17% CAGR; no-op'ing `CorporateActionHandler.process` → +6.59% ≈ vectorized (dividends+bonus = +5.05% CAGR, phase6d). Gated by `tests/backtest_engine/test_corporate_actions.py` (pins the crediting); +5.05% decomposition in `long_only_50cagr/FINDINGS.md`.

#### 2a.4 Formal-run governance (the 2026-05-26 freeze plan, PRs 1–10c)

Full per-PR history: `project_state.md`. Standing contract:

- **Provider attestation**: each provider host emits `data/qlib_data/metadata/provider_build.json` (source of truth for `provider_build_id`, `calendar_policy_id`, namespacing status, calendar bounds). Formal: missing manifest / namespacing-not-enforced / calendar-mismatch → fail. Schema `schemas/provider_build.schema.json`; loader `src/data_infra/provider_manifest.py`. Enforced: `test_provider_manifest.py`.
- **Artifact provenance (schema v2)**: every formal artifact carries `provider_build_id` + `calendar_policy_id` + `execution_profile_id` + `execution_profile_hash` (+ `override_reason`/`override_diff` when overridden). Older artifacts read back `legacy_artifact=true`. Release gate cross-checks profile id + hash (unknown / `allowed_for_formal=False` / hash-mismatch → fail). Gate `src/research_orchestrator/release_gate.py`. Enforced: `test_artifact_provenance.py`, `test_pr8_runtime_enforcement.py`.
- **ExecutionProfile is the formal contract**: every formal run passes `execution_profile=<id>` (`src/backtest_engine/execution_profiles.py`; built-ins `joinquant_daily_sim`, `joinquant_open_close_replica`, `realistic_china_stress` (not formal), `vectorized_screening_close`). `profile_hash` is a computed self-excluding property. A formal profile + explicit `fill_mode`/`slippage`/`exchange_config`/`volume_limit` override needs `override_reason` (else `OverrideRequiresReasonError`). Enforced: `test_execution_profiles.py`.
- **Calendar policy**: formal runs MUST pass `calendar_policy_id` (else `EventDrivenBacktester.run()` raises before any work). Frozen policy `config/calendar_policies/frozen_20260227_system_build.yaml`: observed Qlib calendar end must equal policy + manifest end; run_mode in `allowed_modes`; manifest's own `calendar_policy_id` must match. Validation reads `calendars/day.txt` directly, fires BEFORE feeder/preload. Enforced: `test_pr8b_ordering_modes.py`, `test_pr8c_validation_wiring.py`; daily QA enforces frozen-policy calendar equality.
- **Preload hardening**: formal runs (`run_mode ∈ {formal, oos_test, joinquant_replication}` OR a formal profile) auto-enable `strict=True` + `require_preloaded=True` + `require_provider_manifest=True`. `assert_preloaded(...)` runs before the day loop; `strict_cache_only` then raises `PreloadCoverageError` on the FIRST cache miss (incl. partial/all-missing). Strict mode enabled before warmup + `strategy.initialize`, restored in `finally`. `QlibDataFeeder.preload()` removed (raises) — use `preload_features(...)`. Enforced: `test_preload_hardening.py`, `test_pr8_runtime_enforcement.py`, `test_pr8b_ordering_modes.py`.
- **Field-status registry is the formal data gate**: every `$field` resolves through `config/field_registry/field_status.yaml` via `FieldStatusRegistry`. 4 statuses × per-stage flags; unknown field → `unknown_field_policy[stage]` (warn sandbox, fail formal). `config/field_registry/field_status.yaml` is the LIVE source of truth — never enumerate it from memory. As of 2026-06-05 the ONLY non-`approved` registered dataset is `margin_detail_repayment` (quarantine — `$rzche`/`$rqchl` held for `.BJ`/BSE negatives); `hk_hold` was promoted to `approved` (2026-06-04, ingestion mis-diagnosis corrected); `pending_review` is empty. Everything else registered is `approved` (incl. moneyflow, margin_detail balance/buy fields, stk_holdertrade, top_list, top_inst, block_trade, cyq_perf, income/balancesheet/cashflow). Newly-approved daily/event endpoints are same-day outcomes → predictive factors MUST wrap every field in `Ref(...,1)` (§2a.2). Transitions need a `field_approval_log.jsonl` entry + a per-promotion YAML under `config/field_registry/approvals/`. Release gate + validation resolver/dataset-build gates refuse disallowed fields BEFORE the IS leg. Enforced: `test_field_registry.py`, `test_field_dependency_gate.py`, `test_pr9_validation_field_gate.py`.
- **Research-access chokepoint**: `qlib_windowed_features` is the mandatory formal `D.features` door; validates reads against the `ResearchAccessContext` (run_id, stage, design_hash, window, seal, allowed_fields) — violations raise `HoldoutWindowViolation` / `HoldoutSealViolation` / `FieldAccessViolation`. `SealedBacktestRunner.run_workspace_pipeline` builds the context (required `time_split` + `pipeline_args`). Formal stages call `require_research_access_context(stage)`. AST lint `scripts/lint_no_bare_qlib_features.py` bans bare `D.features` (in `run_daily_qa`). Enforced: `research_access_context.py`, `test_lint_no_bare_qlib_features.py`.
- **Cache + seal file-locking**: `HoldoutSealStore.claim_holdout_access`, `CacheManifestStore.record_cache_write`, `TestingLedgerStore.record_event`/`record_verdict` wrap their ENTIRE read-check-write in `file_lock`. Enforced: `test_lock_concurrency.py`.
- **Module boundaries**: workspace scripts carry a `SCRIPT_STATUS` header; 14 Class-D scripts archived under `workspace/scripts/archive/` (not referenced from `src/`); `portfolio_risk` is dormant (`predict_portfolio_risk()` → `0.05`, `fit()` no-op) and its symbols must not enter any formal path. Governance files live under `config/` + `schemas/`, never `data/`. Enforced: `tests/architecture/test_dormant_module_boundaries.py`.
- **Approval-evidence binding**: every approval YAML with a `provider_build_id`+`calendar_policy_id` binding is machine-validated against the live `provider_build.json` in daily QA. A record with neither key needs `binding_exempt: true` + a non-empty reason (strict bool); exactly one key, null/blank values, or malformed YAML → `ApprovalEvidenceConfigError`. Enforced: `src/data_infra/approval_evidence.py`, `test_approval_evidence.py`.

#### 2a.5 Factor lifecycle & promotion gates (draft → candidate → approved)

Full phase history: `project_state.md` + `src/alpha_research/factor_lifecycle/README.md`. Standing gates:

- **Status ladder & boundary**: `draft` (discovery-usable) → `candidate` (passed the IS-only gate) → `approved` (passed the promotion gate). `get_factor_catalog()` is authoritative for ALL discovery and IGNORES status (42 call sites unchanged). Registry status gates ONLY formal `hypothesis_validation` components. `candidate` is additive; never auto-becomes `approved`.
- **Writer gate**: `FactorRegistryStore.set_status('approved')` / `StrategyRegistryStore.set_status('approved')` require a MANDATORY `current_git_sha` + a `promotion_evidence` artifact passing `assert_promotion_artifact_eligible` (clean tree, independent PIT-correct reproduction source, lint passed, parity ok); else `PromotionGateError`. Evidence `promotion_status` is force-set. Enforced: `test_promotion_gate.py`, `test_factor_registry.py`.
- **Reader gate (resolve-but-label)**: the resolver resolves every current row but LABELS `source_layer` by status+validity; the SOLE formal-permission point is the allow-set in `handle_validation_object_resolver` (`formal`, + `factor_registry_candidate` iff `prescription.allow_candidate_components`). A requested `definition_hash` is a real match filter (closes same-name shadowing). Enforced: `test_pr9_validation_field_gate.py::TestPR12FormalAllowSet`.
- **Definition-binding gate**: before any compute, every resolved formal factor's stored `definition_hash` must equal the current catalog hash (`current_catalog_definition_hashes()`); mismatch / missing hash → `FactorDefinitionDriftError`. Enforced: `test_pr9_validation_field_gate.py::TestPR13DefinitionBindingGate`.
- **IS-only leakage boundary** (the `factor_lifecycle` profile, 8th built-in): `run_is_walk_forward` is bounded to `is_end` — factor date AND label-realization date (`r(t) = open_days[pos(t)+h]`, exact calendar) both ≤ `is_end`, enforced by `IsWindowedPanel.__post_init__` (`IsEndLeakageError`). No `oos_*` in IS evidence. Cross-sectional helpers (`cs_rank`/`cs_zscore`/`cs_demean`/`winsorize`) use a name-based date-level resolver (fail-closed). Enforced: `test_factor_lifecycle_walk_forward.py`, `test_cross_sectional_helpers.py`.
- **Promotion evidence producer**: `produce_promotion_evidence` (self-verifies through the gate) assembles 6 PIT canaries (`src/data_infra/pit_canaries.py`) + an independent OOS reproduction that MUST re-run the screening's exact path (`run_batch_screening(engine="batch", horizons=(5,10,20))`, reading `rank_icir_20d` + 5d `ls_sharpe` — the metric the registration bar was defined against; a wrong-horizon LS-Sharpe is a false positive). Leak-freedom via `provider calendar_end == OOS_END` + a `ResearchAccessContext` over the OOS window. Enforced: `test_pit_canaries.py`, `test_promotion_evidence.py`.
- **Live registry state (2026-06-02)**: 87 `candidate` + 84 `draft` + 6 `approved`. The 6 approved are the Round-6 sealed-OOS winners. The phase-6/7 candidates are an `oos_informed_backfill` (2021-2026 is BURNED for them; candidate→approved must use a genuinely-sealed window). Factor `approved` ≠ tradable-strategy validated. Provenance: JSONs under `workspace/research/factor_expansion/`.
- **Catalog count = 177**: 153 base + 4 industry-relative + 20 Layer-2 composites. Live source of truth: `test_pr9_validation_field_gate.py::TestFormalFactorCompatibility`.

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
