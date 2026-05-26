# Claude Operating Rules

This file is the always-on contract for Claude Code working in this repository. It mirrors `AGENTS.md` (the Codex contract) and condenses the detailed rule set under [.agents/rules/](.agents/rules/) into Claude-specific guidance.

When the two contracts disagree, this file wins for Claude sessions and `AGENTS.md` wins for Codex sessions. The rule files under `.agents/rules/` remain the authoritative human-readable reference; if you need depth on a topic, read the matching file there.

---

## 1. Mandatory Context Refresh

Before any non-trivial implementation, investigation, refactor, or data operation, read these files in order:

1. [project_state.md](project_state.md) — durable system memory; "Last Updated" tells you what changed most recently
2. [config.yaml](config.yaml) — paths, risk limits, MLflow URI, broker placeholders
3. [src/system.md](src/system.md) — top-level src architecture
4. [data/data_dictionary.md](data/data_dictionary.md) — every column in every raw dataset
5. [data/data_tracker.md](data/data_tracker.md) — coverage, sync status, PIT serving conventions

These five files are the source of truth. Do not reason about architecture, factor coverage, data shapes, or PIT semantics from memory — re-read.

For scoped work, also read the matching `AGENTS.md` if one exists in the subtree (e.g. [src/data_infra/AGENTS.md](src/data_infra/AGENTS.md), [src/alpha_research/AGENTS.md](src/alpha_research/AGENTS.md), [src/backtest_engine/AGENTS.md](src/backtest_engine/AGENTS.md), [workspace/AGENTS.md](workspace/AGENTS.md)).

While you are refreshing context, also skim this file and [AGENTS.md](AGENTS.md) against `project_state.md` for drift. If the rule files contradict or omit something `project_state.md` describes, fix the rule files before proceeding (see §11.2).

---

## 2. System Architecture You Must Keep In Mind

Six modules, each with a fixed responsibility. Do not invent alternate boundaries.

- [src/data_infra/](src/data_infra/) — Tushare ingestion, Parquet storage, normalized canonical tables, PIT ledger, Qlib backend, verification
- [src/alpha_research/](src/alpha_research/) — factor library (191 catalog + composites), factor evaluation toolkit, theme strategy framework, model zoo, MLflow tracker, factor/candidate registries
- [src/backtest_engine/](src/backtest_engine/) — `VectorizedBacktester` (Qlib wrapper, fast screening) and `EventDrivenBacktester` (realistic A-share simulator with T+1, multi-tier limits, corporate actions)
- [src/portfolio_risk/](src/portfolio_risk/) — `PortfolioOptimizer` (cvxpy), cost models, risk models
- [src/result_analysis/](src/result_analysis/) — canonical metrics, `BacktestReport`, plotters
- [src/research_orchestrator/](src/research_orchestrator/) — DAG-based workflow scheduler, the 7 built-in profiles, the 5 typed registries

When unsure where logic belongs, prefer the existing module boundary over adding new top-level scripts or ad-hoc helpers. The orchestrator's scope is "data is ready → results are published"; raw downloads, normalization, and Qlib backend builds remain in `data_infra`.

---

## 3. Hard Invariants You Must Never Break

These are silent failures that have already burned the project. Treat them as load-bearing.

- **Tushare ↔ Qlib code format**: Tushare uses `000001.SZ`; Qlib uses `000001_SZ`. Convert with `ts_code.replace('.', '_')` before any join. Wrong format silently returns 0 matches with no error.
- **Benchmark codes** also use the underscore form: `'000300_SH'`, never `'SH000300'`. Qlib's built-in `CSI300_BENCH` only works with official Qlib downloads, not this project's custom backend.
- **Trading calendar**: [data/reference/trade_cal.parquet](data/reference/trade_cal.parquet) is the single ground truth. Never assume business days equal trading days.
- **ST authoritative source**: [data/qlib_data/instruments/st_stocks.txt](data/qlib_data/instruments/st_stocks.txt) (range form, covers the 2020-01-02 gap in `stock_st_daily.parquet`). Use this for any ST detection in backtests.
- **PIT for fundamentals**: always align on `ann_date`, never `end_date`; apply `shift(1)` after `merge_asof` to prevent same-day leakage; forward-fill across calendar gaps. Provider-side `pit_*` fields (`pit_or_yoy`, `pit_netprofit_yoy`, `pit_q_op_qoq`, …) are the canonical PIT-derived growth fields.
- **PIT visibility anchor** (`strictly_next_open_trade_day` invariant): `effective_date > disclosure_date` STRICTLY. The entire PIT guarantee depends on `next_open_trade_day` / `strictly_next_open_trade_day` returning a trading day that is strictly later than the disclosure date. Do NOT change that function without updating `tests/data_infra/test_pit_backend.py` invariant tests. Ref: `src/data_infra/pit_backend.py:strictly_next_open_trade_day`.
- **`f_ann_date` coverage is dataset-specific**: the 5 statement families (`income`, `income_quarterly`, `balancesheet`, `cashflow`, `cashflow_quarterly`) anchor visibility on `max(ann_date, f_ann_date)`. The 4 event/indicator families (`indicators`, `dividends`, `forecast`, `holder_number`) anchor on `ann_date` only because the raw Tushare schemas for those endpoints do not carry an `f_ann_date` column. If a future Tushare schema change adds `f_ann_date` to any of those 4 families, set `f_ann_date_column` in the corresponding `DATASET_SPECS` entry.
- **Delist / IPO-lag contract**: delisting and the 90-day IPO lag are enforced at the **instruments sidecar layer** (`data/qlib_data/instruments/all_stocks.txt`) via `provider_metadata.build_all_stocks_universe()`. Consumers of `D.features()` inherit the guard automatically. Consumers that read `data/pit_ledger/*.parquet` directly BYPASS the guard and MUST apply their own filter using `provider_metadata.stock_basic_bounds(ts_code)`. Regression test: `tests/data_infra/test_provider_boundary.py`.
- **Cumulative→quarterly late restatement**: when a prior quarter's cumulative value is restated AFTER the current quarter has already been disclosed, `derive_single_quarter_value` retroactively changes the derived current-quarter value at the restatement's effective date. This is intentional (use best-known state) but means research code that caches quarter values must invalidate on every ledger rebuild. See the worked example in the function docstring at `src/data_infra/pit_backend.py:derive_single_quarter_value`.
- **MultiIndex order**: Qlib `D.features()` returns `MultiIndex(instrument, datetime)` — *not* `(datetime, instrument)`. The factor_eval helpers normalize either order, but raw pandas code must be explicit. Use `groupby(level=0)` for per-instrument operations only when you have not swapped levels.
- **Negation in Qlib expressions**: `-Operator(...)` does not parse. Use `0 - Operator(...)`.
- **Qlib expressions for predictive factors**: prefer `Ref(..., 1)` over same-day values when the signal is used for next-day trading. Same-day leakage is the most common bug.
- **Factor library PIT-safety (post follow-up plan #1, 2026-04-11)**: every `$field` reference inside every Layer 1 operator in [src/alpha_research/factor_library/operators.py](src/alpha_research/factor_library/operators.py) MUST be wrapped inside a `Ref(...)` frame. The correct pattern is `Mean(Ref($close, 1), 20)`, NOT `Mean($close, 20)`. Use the `ADJ_*_T1` module constants for shifted adjusted prices. `forward_return` is the ONE allowlisted exception (prediction target, not a signal). Enforcement lives in [tests/alpha_research/test_factor_library_pit_safety.py](tests/alpha_research/test_factor_library_pit_safety.py) — a parser-based stack walk that fails if any `$field` lacks a `Ref` ancestor in its parenthesis stack. Per-operator expression lock tests at [tests/alpha_research/test_operator_expressions.py](tests/alpha_research/test_operator_expressions.py) pin exact post-fix strings. A behavioral test at [tests/alpha_research/test_operator_behavioral_pit.py](tests/alpha_research/test_operator_behavioral_pit.py) confirms factor[T] does not depend on close[T] using a tiny synthetic Qlib fixture.
- **Adjusted vs raw prices**: use adjusted prices for cross-day return / momentum computations; use raw values for PIT accounting ratios. Document the choice in any new factor.
- **Exchange cost source of truth (post follow-up plan #2, 2026-04-14)**: stamp tax, commission, and transfer fee (过户费) all flow through `exchange.compute_sell_cost_breakdown()` / `compute_buy_cost_breakdown()` as the single source of truth. The engine passes `breakdown.total` to `portfolio.sell()` / `portfolio.buy()`. Do NOT duplicate rate checks or date boundaries in the engine or portfolio. The `_STAMP_TAX_CHANGE_DATE` module constant in `exchange.py` is the only place the 2023-08-28 boundary lives. Enforcement: `tests/backtest_engine/test_exchange_costs.py`.
- **CostConfig defaults are JoinQuant (changed 2026-05-22)**: `CostConfig()` returns the JoinQuant `OrderCost` equivalent — `close_tax=0.001` constant (no 2023-08-28 cut), `open/close_commission=2.5/10000`, `min_commission=5`, `transfer_fee=0`. This is the deployment-medium default because all production strategies are verified on JoinQuant. To model the ACTUAL Chinese exchange (with the 2023-08-28 stamp-tax cut from 0.1% → 0.05% AND the 0.2 bps 过户费), use `CostConfig.realistic_china()` explicitly. Both presets must round-trip through `compute_*_cost_breakdown`. Enforcement: `tests/backtest_engine/test_exchange_costs.py::CostConfigPresetTests`.
- **Exchange default slippage is JoinQuant (changed 2026-05-22)**: `Exchange()` constructor defaults to `FixedSlippage(0.0003)` = 0.0003 ¥/share (≈ 0.3 bps on a ¥10 stock) — matching JoinQuant's standard `set_slippage(FixedSlippage(3/10000))`. The previous conservative default `PctSlippage(0.001)` (10 bps) is preserved as the named constant `CONSERVATIVE_SLIPPAGE_10BPS` for research that needs it explicitly: `Exchange(slippage_model=CONSERVATIVE_SLIPPAGE_10BPS)`. **Documentation-error protection**: `PctSlippage(0.0003)` ≠ `FixedSlippage(0.0003)` — they differ by ~10× for microcap prices. Always prefer the named constants `JOINQUANT_DEFAULT_SLIPPAGE` and `CONSERVATIVE_SLIPPAGE_10BPS` over inlining literals. Enforcement: `tests/backtest_engine/test_exchange_slippage.py::ExchangeDefaultSlippageTests`.
- **Limit prices use round-half-up**: `exchange.compute_limit_prices()` uses `Decimal.quantize(ROUND_HALF_UP)`, NOT Python's default banker's rounding. Enforcement: `tests/backtest_engine/test_exchange_limits.py`.
- **Event-driven suspension wiring (2026-04-24)**: `EventDrivenBacktester` must pass `data/market/suspension/suspension_ranges.parquet` into `Exchange` when the file exists. If absent, it must log the fallback and `Exchange.is_suspended()` uses the legacy `vol == 0` proxy. Enforcement: `tests/backtest_engine/test_event_driven_backtester_wiring.py`.
- **Event-like daily endpoint namespacing (2026-04-20)**: `_materialize_daily_dataset` in [src/data_infra/pit_backend.py](src/data_infra/pit_backend.py) writes one `.day.bin` per numeric column using the column name verbatim, AFTER `_run_dump_bin` has already written the canonical `$open/$high/$low/$close/$vol/$amount` bins from kline data. Several event-like daily endpoints ship numeric columns that collide with those canonical names — e.g., `top_list` has `close` and `amount`, `block_trade` has `vol` and `amount`. Without a namespace prefix, any event-day row would silently overwrite the canonical kline bin for that stock/date. Every dataset in `EVENT_LIKE_DAILY_DATASETS` (`top_list`, `top_inst`, `block_trade`, `cyq_perf`) MUST also appear in `EVENT_LIKE_DAILY_FIELD_PREFIX`, and its payload columns are written under `{dataset}__{column}.day.bin` (e.g., `top_list__close.day.bin`). Consumers access these via Qlib expressions like `$top_list__close`, `$block_trade__amount`, `$cyq_perf__winner_rate`. Enforcement: [tests/data_infra/test_event_like_daily_namespace.py](tests/data_infra/test_event_like_daily_namespace.py). When adding a new event-like daily endpoint: add it to `EVENT_LIKE_DAILY_DATASETS`, add a matching `EVENT_LIKE_DAILY_FIELD_PREFIX` entry, and extend `_SYNTHETIC_PAYLOADS` in the test so the rename-fires assertion exercises it.
- **Provider self-attestation (PR 1 of 2026-05-26 freeze plan)**: every host that publishes a Qlib provider MUST also emit `data/qlib_data/metadata/provider_build.json` — this file is the single source of truth for `provider_build_id`, `calendar_policy_id`, `event_endpoint_namespacing.status`, and calendar bounds. The Qlib provider tree itself is gitignored, so this manifest is what lets formal artifacts prove which provider produced them. Schema lives at [schemas/provider_build.schema.json](schemas/provider_build.schema.json); loader at [src/data_infra/provider_manifest.py](src/data_infra/provider_manifest.py); builder emission is wired into `StagedQlibBackendBuilder.publish()` in [src/data_infra/pit_backend.py](src/data_infra/pit_backend.py). The current 2026-04-21 build has a `retroactive_manifest=true` manifest with an evidence array; future builds emit non-retroactive manifests automatically. **Hard rule for formal runs**: missing manifest → fail; namespacing != enforced → fail; calendar mismatch → fail unless the calendar policy explicitly allows it. Enforcement: [tests/data_infra/test_provider_manifest.py](tests/data_infra/test_provider_manifest.py).
- **Artifact provenance contract (PR 1)**: every formal `BacktestResult.config`, validation-step output, and registry artifact MUST carry an `artifact_provenance` block (PR 1 = `provider_build_id` + `calendar_policy_id`; PR 3 will extend with `execution_profile_*`). Older artifacts missing this block are read back as `legacy_artifact=true` — they remain viewable for historical comparison but cannot pass the formal release gate. Schema: [schemas/artifact_provenance.schema.json](schemas/artifact_provenance.schema.json). Reader: [src/research_orchestrator/artifact_provenance.py](src/research_orchestrator/artifact_provenance.py). Gate: `evaluate_artifact_provenance` / `assert_formal_artifact_eligible` in [src/research_orchestrator/release_gate.py](src/research_orchestrator/release_gate.py). Enforcement: [tests/research_orchestrator/test_artifact_provenance.py](tests/research_orchestrator/test_artifact_provenance.py).
- **Calendar policy contract (PR 1)**: the 2026-02-27 trading-calendar freeze is recorded as an explicit policy YAML at [config/calendar_policies/frozen_20260227_system_build.yaml](config/calendar_policies/frozen_20260227_system_build.yaml). Formal runs that operate against a frozen calendar must pass `calendar_policy_id` explicitly (default sandbox behavior is `legacy_artifact=true`). When the freeze ends, flipping `frozen: false` and adding `max_calendar_lag_days` in the same YAML is the only change required — the loader at [src/research_orchestrator/calendar_policy.py](src/research_orchestrator/calendar_policy.py) already branches on `frozen`. Enforcement: [tests/research_orchestrator/test_calendar_policy.py](tests/research_orchestrator/test_calendar_policy.py).
- **Governance file home rule (PR 1)**: governance registries (calendar policies, field-status registry, execution profiles) live under `config/` and committed schemas under `schemas/`. Do NOT place governance files under `data/` — that directory is gitignored, so a registry placed there would silently become un-versioned. Runtime artifacts (the actual `provider_build.json`, registry status caches) DO live under `data/` because they are local per-host state, not shared governance.
- **ENGINE_REQUIRED_FIELDS contract (PR 2 of 2026-05-26 freeze plan)**: the canonical 8-field tuple (`$open`, `$close`, `$high`, `$low`, `$vol`, `$amount`, `$pre_close`, `$adj_factor`) lives at [src/backtest_engine/event_driven/constants.py](src/backtest_engine/event_driven/constants.py). `EventDrivenBacktester.run()` ALWAYS unions caller-supplied `preload_fields` with this tuple when `should_preload` is True, so the engine path never falls back to per-day `D.features` for OHLCV. Adding a new engine-required field means adding it here, not in `engine._fetch_day_data` alone.
- **`should_preload` condition (PR 2)**: `EventDrivenBacktester.run()` preloads when ANY of `preload_required=True`, `preload_fields is not None`, or `run_mode in FORMAL_RUN_MODES` ({`formal`, `oos_test`, `joinquant_replication`}). Passing `run_mode='formal'` auto-enables both `strict=True` and `require_preloaded=True`. The old `if preload_fields:` condition silently skipped preload when a formal run had no strategy-specific factor fields — that bug is fixed. Reference: the PR 2 negative-test suite at [tests/backtest_engine/test_preload_hardening.py](tests/backtest_engine/test_preload_hardening.py).
- **No-op preload removed (PR 2)**: `QlibDataFeeder.preload(start, end)` was a silent no-op that left `_cache_df=None` and forced the engine into a per-day fallback (the ~100x slowdown discovered in plan `snappy-buzzing-meerkat` v5). The method now raises `NotImplementedError`; the previous `BacktestEngine.run()` call site has been removed. Use `preload_features(index_name, fields, start_time, end_time, strict=True)` exclusively.
- **`require_preloaded` engine contract (PR 2)**: `BacktestEngine(require_preloaded=True)` makes the engine call `feeder.assert_preloaded(required_fields=ENGINE_REQUIRED_FIELDS, start=prev_trading_day(backtest_start), end=backtest_end, require_zero_fallback=True)` before the day loop starts. Auto-set to True when `EventDrivenBacktester.run(run_mode='formal'|'oos_test'|'joinquant_replication')`. Formal runs cannot silently degrade into per-day fallback.

---

## 4. Python Environment & Path Discipline

- Interpreter: `E:\量化系统\venv\Scripts\python.exe`
- Pip: `E:\量化系统\venv\Scripts\pip.exe`
- Pin exact versions in [requirements.txt](requirements.txt); align it with actual imports.
- Code in `src/` must derive paths from [config.yaml](config.yaml) or project-root-relative references. Hardcoded absolute paths are acceptable only in one-off `workspace/scripts/` or `scripts/` utilities.
- Use `pathlib` or `os.path.join`, not string concatenation, for paths.
- Never write persistent project artifacts to `%TEMP%`, `AppData`, `/tmp`, or any path outside `E:\量化系统\`.

---

## 5. Directory Hygiene

- **Project root** is for configuration, documentation, and top-level directories only. Do not accumulate ad-hoc logs, exports, audit dumps, or temporary guides at root — move them to `logs/` or `workspace/outputs/`.
- **`data/`** is for datasets and documentation only. No `.py` files. Raw and intermediate datasets are Parquet unless an existing subsystem requires another format.
- **`workspace/`** is the only place for active notebooks, prototypes, experiment scripts, and generated research artifacts. Organize as:
  - notebooks under `workspace/research/{topic}/`
  - helper scripts under `workspace/scripts/`
  - research configs under `workspace/configs/`
  - generated outputs under `workspace/outputs/`
- **`scripts/`** is for bootstrap and maintenance utilities that operate on durable datasets, not ad-hoc one-offs.
- **`logs/`** receives rotated console output from long-running pipelines.

Do not move or rename files in `data/qlib_data/` by hand — those are derived artifacts. Regenerate via the proper builder scripts.

---

## 6. Data Operations (read [.agents/rules/data-operations.md](.agents/rules/data-operations.md) for depth)

### 6.1 Tushare Safety (the rule that has bitten us most)

- **Never run parallel fetchers against Tushare Pro** under any circumstance. Account-level rate limits make it counterproductive and risk lockouts.
- All API calls must go through `TushareFetcher._safe_api_call()` with the built-in retry/backoff. Do not bypass it.
- If you hit repeated 429s or timeouts, **increase the sleep interval** instead of retrying more aggressively. The default `base_sleep=1.5` should not be reduced without evidence.
- Prefer `StorageManager.insert_*` helpers over manual Parquet writes.

### 6.2 Live Pipeline Entry Points

These are the supported entry points. Do not reintroduce or document deprecated legacy script names or the removed Airflow stub.

- [src/data_infra/pipeline/init_market_data.py](src/data_infra/pipeline/init_market_data.py) — Phase 1 bootstrap (prices, valuation, reference)
- [src/data_infra/pipeline/init_fundamentals_data.py](src/data_infra/pipeline/init_fundamentals_data.py) — Phase 2 bootstrap (statements, dividends, industry, index weights)
- [src/data_infra/pipeline/init_factor_data.py](src/data_infra/pipeline/init_factor_data.py) — Phase 3 (cashflow, forecast, moneyflow, hk_hold, margin_detail, holder, stk_limit)
- [src/data_infra/pipeline/refresh_indicator_history.py](src/data_infra/pipeline/refresh_indicator_history.py) — staged historical VIP indicator refresh
- [src/data_infra/pipeline/build_qlib_backend.py](src/data_infra/pipeline/build_qlib_backend.py) — staged PIT backend builder, supports `--stage full | upstream-only | provider-only`
- [src/data_infra/pipeline/update_daily_data.py](src/data_infra/pipeline/update_daily_data.py) — daily routine maintenance + incremental Qlib refresh
- [src/data_infra/pipeline/verify_database.py](src/data_infra/pipeline/verify_database.py) — raw integrity gate (now also runs the PIT live regression harness as a publish gate)
- [scripts/fetch_suspend_d_historical.py](scripts/fetch_suspend_d_historical.py) — one-time `suspend_d` historical bootstrap (P1-1; not wired into automation)
- [scripts/refresh_namechange.py](scripts/refresh_namechange.py) — idempotent refresh of `data/reference/namechange.parquet` (P1-2; not wired into automation)
- [scripts/run_daily_qa.py](scripts/run_daily_qa.py) — manual QA orchestrator (see §6.2a below)
- [scripts/fetch_new_alpha_endpoints.py](scripts/fetch_new_alpha_endpoints.py) — one-time bootstrap for 5 new alpha endpoints (top_list, top_inst, block_trade, stk_holdertrade, cyq_perf); not wired into automation

### 6.2a Daily QA Runner (manual)

Before any serious research session or after any data-infra change, run:

```bash
venv/Scripts/python.exe scripts/run_daily_qa.py
```

This orchestrates `DataAuditor.audit_daily_files` → `audit_qlib.py` smoke →
`tests/data_infra/test_provider_boundary.py` → `tests/data_infra/test_pit_live_provider.py`.
It writes a structured report to `logs/qa_report_<ts>.json` and exits
non-zero on any failure. It is intentionally NOT a scheduler / alerter
at this stage (because the trade calendar is intentionally frozen at
2026-02-27 while the system is being built).

### 6.3 Backend Rebuild Discipline

- A full Qlib rebuild (`mode="all"`) is expensive — use only for initial loads, corrected backfills, or schema-level changes.
- For daily updates use `mode="update"`.
- For sandbox validation baskets, prefer `--mode update --stage provider-only --touched-symbols <basket>` so the builder creates a minimal staged provider instead of copying the full published tree.
- After any rebuild, verify with [scripts/audit_qlib.py](scripts/audit_qlib.py), [tests/harnesses/qlib_smoke.py](tests/harnesses/qlib_smoke.py), [scripts/verify_phase2.py](scripts/verify_phase2.py), or targeted `D.features()` spot checks.
- **Publish atomicity (P0-6)**: `StagedQlibBackendBuilder.publish()` uses `os.replace()`, which is atomic ONLY when the staged provider and the target `data/qlib_data/` live on the same volume. `publish()` now hard-fails with a `BuildGateError` if the two paths have different `os.stat().st_dev` values. If you ever see that error, move the staged build onto the same drive as `data/qlib_data/` before publishing.
- **Deterministic rebuild (P0-4)**: `_normalize_periodic_dataset` injects `_src_file` and `_src_ordinal` hidden columns during raw ingest so the tie-break in `collapse_duplicate_versions` and `canonicalize_report_variants` is reproducible across machines. These columns are stripped before writing normalized parquet to disk, so the on-disk schema is unchanged. A WARNING log fires whenever the tail tie-break is actually needed.

### 6.4 Mutation Safety

- Scripts that modify existing `data/` Parquet files must log which files will be touched **before** they start.
- Support a `--dry-run` flag when practical.
- Never overwrite raw data in place without a backup path or a deduplication guarantee.
- After any bulk operation, update [data/data_tracker.md](data/data_tracker.md).

---

## 7. Research Integrity (read [.agents/rules/research-integrity.md](.agents/rules/research-integrity.md) for depth; the hypothesis workflow now lives in Section 10 of that same rule file)

These rules are non-negotiable. Violating them invalidates the research even if the code runs.

The detailed gated lifecycle now lives in Section 10 of `.agents/rules/research-integrity.md`. Use that section for the 10-stage workflow, the 5 human gates, pre-registration, sealed OOS, multiple-testing, and the pointers to `src/research_orchestrator/hypothesis.py`, `workspace/scripts/hypothesis_cli.py`, and the YAML factor spec schema.

Operationally, v3.1 formal non-audit runs now insert `gate_evaluation -> gate_concern_scoring -> gate_review` before publication. `gate_concern_scoring` is the `pause_for_input` step and now uses a typed `PauseForInputPayload` from `src/research_orchestrator/dag.py`; `gate_review` is the `pause_for_gate` step that writes the final gate report and accepts `approved`, `rejected`, or `quarantined`; seal-aware backtest execution flows through `src/research_orchestrator/sealed_backtest_runner.py`; the first pre-load window clamp now lives in `src/research_orchestrator/window_enforcement.py`; and cache/window safety is then reinforced through `src/research_orchestrator/cache_manifest.py` plus `src/research_orchestrator/qlib_windowed_features.py`. `workspace/scripts/hypothesis_cli.py verify-seal` now uses exit codes `0=untouched`, `1=OOS already touched`, `2=malformed hash`.

1. **No lookahead, ever.** Use PIT data, align fundamentals on `ann_date`, apply `shift(1)`, document PIT compliance for any new pipeline.
2. **Temporal splits only.** Never random splits. Walk-forward (`5y train / 2y validation / 1y test, step 1y`) is the project standard, used by [event_driven_strategy_research.py](workspace/research/alpha_mining/event_driven_strategy_research.py).
3. **Out-of-sample is sacred.** The final test set is run **once** per strategy variant. If iteration is driven by test results, that is no longer OOS — disclose it explicitly. Log the first test result before any follow-up adjustments.
4. **Factor evaluation standard**: IC, RankIC, ICIR, quantile spread, monotonicity, decay, and turnover before any factor is promoted.
5. **Factor documentation**: every factor in [src/alpha_research/factor_library/](src/alpha_research/factor_library/) should state its formula, data source, decay horizon, price basis (adjusted/raw/reported), and whether it is raw or neutralized.
6. **MLflow logging is mandatory** for substantive model-training or backtest runs. Use `ExperimentTracker` from [mlflow_tracker.py](src/alpha_research/mlflow_tracker.py).
7. **Survivorship bias**: use historical universes that include delisted names. Do not filter to currently listed stocks only.
8. **Centralized performance analysis**: all serious backtest evaluation must use [src/result_analysis/](src/result_analysis/). Do not reimplement Sharpe / MDD / turnover / win rate in a notebook. If a metric is missing, add it to [metrics.py](src/result_analysis/metrics.py).
9. **Phase 3 factor framework**: prefer `get_factor_catalog()`, `compute_factors()`, and `add_composites()` over bespoke factor pipelines. Prefer Qlib expressions over slow `groupby().apply()` whenever an operator exists.
10. **No hedge words in quantitative analysis.** When analyzing a strategy result, a discrepancy between two backtests, or any quantitative claim, do NOT use "likely", "possibly", "probably", "I think", "appears to", "seems to", "could be", "might be", or any other epistemic hedge. Either you have run the data and can state the exact cause with certainty, or you must explicitly mark the claim as unverified and propose the specific test that would resolve it. The unacceptable failure mode is presenting a plausible-sounding guess as if it were an answer. The acceptable failure mode is: "I have not verified X yet. The test that would resolve it is Y. Running it now." Quantitative finance does not allow plausibility — it requires the actual data or an explicit "I do not know, here is how I will find out". Reference the diagnostic in `Knowledge/temp_plan/` whenever a divergence is attributed to a specific mechanism: name the dataset/script/output that proves it. Suggestions are fine *only* when explicitly labeled as hypotheses with a stated falsification plan.

---

## 8. Signal Construction & Backtesting (read [.agents/rules/signal-backtesting.md](.agents/rules/signal-backtesting.md) for depth)

### 8.1 The four-layer pipeline (mandatory)

Every backtest follows: **factor computation → universe selection → signal construction → execution.** Keep concerns separated. Factor values in Layer 1, eligibility in Layer 2, desirability in Layer 3, tradability in Layer 4.

- **Layer 1 (factor)**: compute factors on the full market *before* sub-universe filtering. Lookbacks need full coverage.
- **Layer 2 (universe)**: represent membership as boolean masks, not row drops. Do not filter on tradability here — suspended names still need ranking context.
- **Layer 3 (signal)**: rank within the intended sub-universe, not the full market. Forward-fill within membership when continuity is required.
- **Layer 4 (execution)**: never encode tradability inside the signal.

### 8.2 Engine choice

- [VectorizedBacktester](src/backtest_engine/vectorized/) for rapid signal screening and multi-signal comparison.
- [EventDrivenBacktester](src/backtest_engine/event_driven/) for realistic execution, JoinQuant parity, corporate-action sensitivity. Use `preload_features()` — without it, a 1-year backtest is 5+ minutes; with it, ~24 seconds.

### 8.3 Production research execution defaults

For serious vectorized runs, set these explicitly. Do not rely on the convenience defaults:

- `deal_price='open'`
- `only_tradable=False`
- `forbid_all_trade_at_limit=True`
- realistic transaction costs
- `limit_threshold` aligned with the segment mix being tested

### 8.4 Banned anti-patterns

1. Filtering before factor computation
2. Dropping rows that should remain available for forward-fill
3. Encoding tradability inside the signal
4. Mixing ranking scope with execution filters
5. Omitting signal forward-fill when methodology requires continuity

---

## 9. Research Orchestrator Workflow

The orchestrator at [src/research_orchestrator/](src/research_orchestrator/) is the preferred way to run formal research. The 7 built-in profiles are: `factor_screening`, `theme_strategy`, `event_driven_signal_research`, `ml_signal_model_research`, `strategy_improvement`, `benchmark_audit`, **`hypothesis_validation`**.

**Discovery vs validation (added 2026-04-28, plan `jolly-seeking-lollipop`):** the first 5 profiles are **discovery** profiles — they auto-search a recipe space and pick the empirically best variant. `hypothesis_validation` is the **validation** profile — it runs a fully-prescribed recipe (universe + components + weights + topk + rebalance + cost model) verbatim through IS+gate+OOS+publish with no auto-search. Use validation when you have a specific recipe to test (e.g., from prior discovery research); use a discovery profile when you want to find the best recipe within a search space. The validation profile requires `hypothesis.prescription` to be set (a `PrescribedRecipe` defined in `src/research_orchestrator/hypothesis.py`); discovery profiles ignore the prescription field. Register validation hypotheses with `hypothesis_cli.py register --profile-id hypothesis_validation` to opt into profile-aware floor validation (default validates against ALL profiles).

CLI entry: [workspace/scripts/research_orchestrator_cli.py](workspace/scripts/research_orchestrator_cli.py)

```
research_orchestrator_cli.py profiles                   # list profiles
research_orchestrator_cli.py plan --request-file ...    # compile DAG only
research_orchestrator_cli.py run  --request-file ...    # execute
research_orchestrator_cli.py resume --run-dir ...       # safe resume
```

Resume is intentionally strict: same `run_dir` + matching `request_hash` + matching `plan_hash`. If the plan changed, resume is refused. Do not work around this — fix the request or start a new run.

Run artifacts live under the run directory: `dag_plan.json`, `dag_state.json`, `run_metadata.json`, `artifact_manifest.json`, `produced_objects.json`, `review_summary.json`, plus per-step subdirectories under `steps/<step_id>/`.

The five typed registries that the orchestrator publishes into:
- [data/factor_registry/](data/factor_registry/) — formal base + composite factors
- [data/candidate_registry/](data/candidate_registry/) — research candidates (factor, theme component)
- [data/signal_registry/](data/signal_registry/) — signal recipes (theme recipes live here, not in candidate_registry)
- [data/model_registry/](data/model_registry/) — trained models
- [data/strategy_registry/](data/strategy_registry/) — strategy candidates

Each is `master.parquet` + `evidence.parquet` + `run_index.parquet` + `status_history.parquet` + `review.html`.

---

## 10. Development Practices (read [.agents/rules/development-practices.md](.agents/rules/development-practices.md) for depth)

- **Logging, not print()**: use Python's `logging` module in any reusable code. Long-running scripts write to `logs/` with rotation.
- **Visible progress**: any script expected to run for a substantial time must show a progress tracker (`tqdm` or periodic log lines with completed/total/ETA). Operators should be able to tell from the console what stage is running.
- **Naming**: `snake_case.py`, `PascalCase` classes, `snake_case` functions, `UPPER_SNAKE_CASE` constants, factor names `{category}_{name}_{lookback}` when horizon-specific.
- **Module boundaries**: import through public interfaces, not by reaching into another module's internals. Finalized reusable logic belongs in `src/`, not `workspace/`.
- **Reuse before reinvent**: before adding a helper or dependency, check whether Qlib, MLflow, the factor library, factor_eval, or `result_analysis` already provides the capability.
- **Secrets**: `.env` for credentials. Never commit real tokens. Tushare token is loaded from `.env` via `${TUSHARE_TOKEN}` in [config.yaml](config.yaml).
- **Version control**: never commit `venv/`, `data/`, `mlruns/`, `logs/`, `*.log`, `*.pyc`, `__pycache__/`, `.env`, Parquet, Qlib bins, or large model artifacts.

---

## 11. Durable Memory & Rule-File Maintenance

### 11.1 project_state.md

[project_state.md](project_state.md) is durable system memory. Update it after meaningful work, including:

- new datasets, pipeline entry points, or coverage extensions
- major bug fixes or architecture changes
- backtester behavior changes or new research conventions
- data sync status changes
- rule migrations and registry-governance changes
- significant research milestones (formal screening completions, formal event-driven runs, etc.)
- **any update to [CLAUDE.md](CLAUDE.md), [AGENTS.md](AGENTS.md), or [.agents/rules/](.agents/rules/)** (rule changes are themselves significant work)

Keep "Last Updated", "Active Research Focus" / current priority, and data sync sections current when affected. Treat project_state.md as the canonical answer to "what is the system right now?" — if it disagrees with code, fix one of them rather than working around the gap.

### 11.2 Keep CLAUDE.md, AGENTS.md, and .agents/rules/ fresh (standing instruction)

This is non-optional. Stale rule files are worse than no rule files because they actively mislead future sessions.

**Revisit at the start of every non-trivial task.** During the §1 context refresh, also skim [CLAUDE.md](CLAUDE.md) and [AGENTS.md](AGENTS.md) against [project_state.md](project_state.md). If `project_state.md` describes architecture, entry points, registries, or workflow facts that the rule files contradict or omit, **fix the rule files before proceeding** with the task.

**Revisit at the end of every substantive change.** After any work that touches `src/`, pipeline entry points, registry layout, research workflow, naming conventions, hard invariants, or anti-patterns, check whether CLAUDE.md, AGENTS.md, and the matching `.agents/rules/*.md` still describe reality. If not, update them in the same session as the change — not "later".

**Drift signals to watch for:**

- A module exists in `src/` but is not listed in CLAUDE.md / AGENTS.md / [src/system.md](src/system.md). (Example: `src/research_orchestrator/` is the 6th top-level module; older copies of `src/system.md` and the rule docs may still describe a five-module layout.)
- A pipeline entry point listed in §6.2 no longer exists, or a new one in [src/data_infra/pipeline/](src/data_infra/pipeline/) is missing from the list.
- A "deprecated" name in the rule files has actually been deleted, or a name marked live has been deprecated.
- A scoped `AGENTS.md` inside a subdirectory contradicts this contract.
- A research convention recorded in `project_state.md` (e.g. PIT lag patches, factor framework changes) is not reflected in the rule files.
- A registry was added, removed, or moved (`candidate_registry`, `factor_registry`, `signal_registry`, `model_registry`, `strategy_registry`).
- A new built-in research profile was added to [src/research_orchestrator/profiles.py](src/research_orchestrator/profiles.py) but is not listed in §9.

**Alignment contract.** CLAUDE.md and AGENTS.md must agree on substance even though they differ in tone and audience. The §1 context-refresh list, the module list, the hard invariants, the live entry points, the data ops rules, the research integrity rules, the four-layer backtest pipeline, the banned anti-patterns, and the venv path must read the same in both files. The Claude-specific tool sections (§12) and the Codex-specific subagent matrix in `AGENTS.md` are the legitimate places to diverge. **If you update a rule in one file, update the matching rule in the other in the same edit pass.**

**Record rule changes in project_state.md** (see §11.1) so the audit trail of "how the agent contract evolved" lives next to the audit trail of "how the system evolved".

---

## 12. Tool Use Discipline (Claude-specific)

Claude Code has dedicated tools that supersede shell commands. Always prefer them — they provide the user a better review experience and respect permission boundaries.

| Use this | Not this |
|---|---|
| `Read` | `cat` / `head` / `tail` / `sed -n` |
| `Edit` / `Write` | `sed` / `awk` / `echo >` / heredoc |
| `Glob` | `find` / `ls -R` |
| `Grep` | `grep` / `rg` from Bash |
| `TodoWrite` | mental tracking for any task with 3+ steps |
| `Bash` | only for genuine system commands and script execution |

Specific to this repo:
- Use `venv/Scripts/python.exe` for any Python execution. Do not invoke system Python.
- Long-running scripts: launch with `run_in_background: true` and read output later. Do not block.
- This is a Windows machine — use forward-slash paths and bash-style redirects (`/dev/null`, not `NUL`).

### When to delegate to a subagent

- **`Explore` subagent** — for codebase exploration that will clearly need more than 3 search rounds, or when scanning for naming conventions across multiple module conventions. For directed lookups of a known symbol, use `Grep` directly.
- **`Plan` subagent** — when a non-trivial implementation task needs an explicit step-by-step plan before edits.
- **`general-purpose` subagent** — for multi-step research tasks that should not pollute the main conversation context with raw tool output. Always brief it as a smart colleague who has not seen the conversation.

Match subagent use to the spirit of the Codex `quant_*` agents in [AGENTS.md](AGENTS.md): use read-only exploration before write work, do not parallelize Tushare fetchers, and use validation gates after substantive changes.

### File references in Claude responses

When mentioning files or code locations, use markdown link syntax — never backticks for file names:

- File: `[file.py](src/file.py)`
- Line: `[file.py:42](src/file.py#L42)`
- Range: `[file.py:42-51](src/file.py#L42-L51)`
- Folder: `[src/utils/](src/utils/)`

Paths should be relative to the workspace root.

---

## 13. Risky-Action Discipline

Before any of the following, pause and confirm with the user (unless they have explicitly authorized it for the current task):

- `git push`, force-push, branch deletion, `git reset --hard`, amending published commits
- Removing or downgrading dependencies in `requirements.txt`
- Touching CI/CD configuration
- Running data-mutation scripts without `--dry-run` against production `data/`
- Full Qlib rebuilds (`mode="all"`)
- Anything that would modify a registry's master tables outside the orchestrator's normal publish path
- Any operation that touches Tushare while another fetch is suspected to be in flight

For everything else (local file edits, reading data, running tests, sandbox builds in `data/qlib_builds/`), proceed normally and report what you did.

---

## 14. Scope Override

More specific `AGENTS.md` files inside subdirectories refine these global rules for their subtree. When both apply, follow the more specific scoped file in addition to this root contract.

If you find a conflict between this file and the rule files under [.agents/rules/](.agents/rules/), the rule files are the deeper reference — bring it to the user's attention and propose a reconciliation rather than picking silently.
