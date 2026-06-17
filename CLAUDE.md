# Claude Operating Rules

This file is the always-on contract for Claude Code working in this repository. It mirrors `AGENTS.md` (the Codex contract) and condenses the detailed rule set under [.agents/rules/](.agents/rules/) into Claude-specific guidance.

When the two contracts disagree, this file wins for Claude sessions and `AGENTS.md` wins for Codex sessions. The rule files under `.agents/rules/` remain the authoritative human-readable reference; if you need depth on a topic, read the matching file there.

---

## 1. Mandatory Context Refresh

Before any non-trivial implementation, investigation, refactor, or data operation, read these files in order:

1. [project_state.md](project_state.md) — durable system memory; "Last Updated" tells you what changed most recently
2. [config.yaml](config.yaml) — paths, risk limits, MLflow URI, broker placeholders
3. [src/system.md](src/system.md) — top-level src architecture; **§0 Canonical Function Map** lists the verified function for each task — consult it before writing new code, to reuse instead of reinventing
4. [data/data_dictionary.md](data/data_dictionary.md) — every column in every raw dataset
5. [data/data_tracker.md](data/data_tracker.md) — coverage, sync status, PIT serving conventions

These five files are the source of truth. Do not reason about architecture, factor coverage, data shapes, or PIT semantics from memory — re-read.

For scoped work, also read the matching `AGENTS.md` if one exists in the subtree (e.g. [src/data_infra/AGENTS.md](src/data_infra/AGENTS.md), [src/alpha_research/AGENTS.md](src/alpha_research/AGENTS.md), [src/backtest_engine/AGENTS.md](src/backtest_engine/AGENTS.md), [workspace/AGENTS.md](workspace/AGENTS.md)).

While you are refreshing context, also skim this file and [AGENTS.md](AGENTS.md) against `project_state.md` for drift. If the rule files contradict or omit something `project_state.md` describes, fix the rule files before proceeding (see §11.2).

---

## 2. System Architecture You Must Keep In Mind

Six modules, each with a fixed responsibility. Do not invent alternate boundaries.

- [src/data_infra/](src/data_infra/) — Tushare ingestion, Parquet storage, normalized canonical tables, PIT ledger, Qlib backend, verification
- [src/alpha_research/](src/alpha_research/) — factor library (catalog = base factors + industry-relative + Layer-2 composites; the live count is DERIVED via `catalog_composition()`, never hard-coded — it grows as factors are added), factor evaluation toolkit, theme strategy framework, model zoo, MLflow tracker, factor/candidate registries
- [src/backtest_engine/](src/backtest_engine/) — `VectorizedBacktester` (Qlib wrapper, fast screening) and `EventDrivenBacktester` (realistic A-share simulator with T+1, multi-tier limits, corporate actions)
- [src/portfolio_risk/](src/portfolio_risk/) — `PortfolioOptimizer` (cvxpy), cost models, risk models
- [src/result_analysis/](src/result_analysis/) — canonical metrics, `BacktestReport`, plotters
- [src/research_orchestrator/](src/research_orchestrator/) — DAG-based workflow scheduler, the 8 built-in profiles, the 5 typed registries

> Auxiliary (NOT a 7th research module): [src/dashboard/](src/dashboard/) is a **read-only reporting tool** that projects the whole system into a centralized HTML board at the project root (`index.html`). It only *reads* the other modules' outputs/registries/governance + Claude session transcripts; it must never be imported into any formal research/data path. See §6.2.

When unsure where logic belongs, prefer the existing module boundary over adding new top-level scripts or ad-hoc helpers. The orchestrator's scope is "data is ready → results are published"; raw downloads, normalization, and Qlib backend builds remain in `data_infra`.

---

## 3. Hard Invariants You Must Never Break

These are silent failures that have already burned the project. Each entry is **the rule that holds
now** + **where it is enforced** (the executable source of truth). The full implementation and review
history — every "PR N", "Blocker", "round-N review", commit SHA, and test tally — lives in
[project_state.md](project_state.md); search the PR/Phase id there. Do **not** re-narrate history in
this file. When you change a rule, change its enforcing test and mirror the entry into
[AGENTS.md](AGENTS.md) §2a in the same edit pass (§11.2).

### 3.1 Data & code-format invariants (corrupt silently if violated)

- **Tushare ↔ Qlib code format**: Tushare `000001.SZ`; Qlib `000001_SZ`. Convert with `ts_code.replace('.', '_')` before any join. Wrong format silently returns 0 matches with no error.
- **Benchmark codes** use the underscore form: `'000300_SH'`, never `'SH000300'`. Qlib's built-in `CSI300_BENCH` does not work with this project's custom backend.
- **Trading calendar**: [data/reference/trade_cal.parquet](data/reference/trade_cal.parquet) is the single ground truth. Business days ≠ trading days.
- **ST authoritative source**: [data/qlib_data/instruments/st_stocks.txt](data/qlib_data/instruments/st_stocks.txt) (range form; covers the 2020-01-02 gap in `stock_st_daily.parquet`). Use it for any ST detection in backtests.
- **Delist / IPO-lag contract**: enforced at the instruments sidecar layer (`all_stocks.txt` via `provider_metadata.build_all_stocks_universe()`). Consumers of `D.features()` inherit the guard. Code that reads `data/pit_ledger/*.parquet` directly BYPASSES it and MUST filter via `provider_metadata.stock_basic_bounds(ts_code)`. *Enforced:* `tests/data_infra/test_provider_boundary.py`.
- **MultiIndex order**: `D.features()` returns `MultiIndex(instrument, datetime)`, NOT `(datetime, instrument)`. factor_eval helpers normalize either order; raw pandas must be explicit. `groupby(level=0)` is per-instrument only when levels are not swapped.

### 3.2 PIT correctness (any lookahead invalidates the research)

- **PIT for fundamentals**: align on `ann_date`, never `end_date`; apply `shift(1)` after `merge_asof`; forward-fill across calendar gaps. The `pit_*` provider fields (`pit_or_yoy`, `pit_netprofit_yoy`, `pit_q_op_qoq`, …) are the canonical PIT-derived growth fields.
- **PIT visibility anchor**: `effective_date > disclosure_date` STRICTLY. The whole guarantee rests on `next_open_trade_day` / `strictly_next_open_trade_day` returning a trading day strictly later than disclosure. *Enforced:* `tests/data_infra/test_pit_backend.py` invariant tests — do not change the function without updating them. Ref: `src/data_infra/pit_backend.py`.
- **`f_ann_date` is dataset-specific**: the 5 statement families anchor on `max(ann_date, f_ann_date)`; the 4 event/indicator families (`indicators`, `dividends`, `forecast`, `holder_number`) anchor on `ann_date` only (no `f_ann_date` column in those raw schemas). If a future schema adds it, set `f_ann_date_column` in the `DATASET_SPECS` entry.
- **Cumulative→quarterly late restatement**: `derive_single_quarter_value` retroactively changes a derived current-quarter value at a restatement's effective date (intentional — best-known state). Research code that caches quarter values must invalidate on every ledger rebuild. Worked example in the function docstring.
- **Factor-library PIT-safety**: every `$field` inside every Layer-1 operator in [operators.py](src/alpha_research/factor_library/operators.py) MUST sit inside a `Ref(...)` frame (`Mean(Ref($close, 1), 20)`, not `Mean($close, 20)`); use the `ADJ_*_T1` constants. `forward_return` is the one allowlisted exception (prediction target). *Enforced:* [tests/alpha_research/test_factor_library_pit_safety.py](tests/alpha_research/test_factor_library_pit_safety.py) (parser stack-walk), `test_operator_expressions.py` (exact-string locks), `test_operator_behavioral_pit.py` (factor[T] ⊥ close[T]).
- **Predictive expressions**: prefer `Ref(..., 1)` over same-day values for next-day trading; `-Operator(...)` does not parse — use `0 - Operator(...)`.
- **Adjusted vs raw prices**: adjusted for cross-day return/momentum; raw for PIT accounting ratios. Document the choice in any new factor.
- **PIT research access — two sanctioned front doors only**: research/sandbox reads PIT fundamentals through [pit_research_loader.py](src/data_infra/pit_research_loader.py) (`load_pit_signal_panel` lag-1 default / `load_pit_asof_panel` lag-0); formal code through [qlib_windowed_features](src/research_orchestrator/qlib_windowed_features.py). Both share the stateful-q0 kernel [pit_alignment_core.py](src/data_infra/pit_alignment_core.py). NEVER hand-roll PIT alignment, read `pit_ledger/*` outside the loader/builder, or string-compare date columns. The loader is fail-closed (unknown/quarantined fields refused; provider bounds applied) and bound to the production provider (the oracle). *Enforced:* PIT002 lint [lint_no_unsafe_pit_dates.py](scripts/lint_no_unsafe_pit_dates.py) (raw-ledger-read = hard error) + parity test [test_pit_loader_provider_parity.py](tests/data_infra/test_pit_loader_provider_parity.py), both in `run_daily_qa`. History (the 2026-05-29 sandbox lookahead that inflated v31/v32/val_heavy): project_state.md.

### 3.3 Execution & cost realism (backtest fidelity)

- **Exchange cost source of truth**: stamp tax, commission, and 过户费 all flow through `exchange.compute_sell_cost_breakdown()` / `compute_buy_cost_breakdown()`; the engine passes `breakdown.total` to `portfolio.sell/buy`. Do NOT duplicate rate checks or date boundaries. The 2023-08-28 stamp-tax boundary lives only in `_STAMP_TAX_CHANGE_DATE`. *Enforced:* `tests/backtest_engine/test_exchange_costs.py`.
- **CostConfig defaults are JoinQuant**: `CostConfig()` = JoinQuant OrderCost equivalent (`close_tax=0.001` constant, `2.5/10000` commission, `min 5`, `transfer_fee=0`). For the real exchange (2023-08-28 cut + 过户费) use `CostConfig.realistic_china()`. *Enforced:* `test_exchange_costs.py::CostConfigPresetTests`.
- **Exchange default slippage is JoinQuant**: `Exchange()` defaults to `FixedSlippage(0.0003)`. The conservative 10 bps default is the named constant `CONSERVATIVE_SLIPPAGE_10BPS`. Always use the named constants `JOINQUANT_DEFAULT_SLIPPAGE` / `CONSERVATIVE_SLIPPAGE_10BPS`, never inline literals (`PctSlippage(0.0003)` ≠ `FixedSlippage(0.0003)`, ~10× apart for microcaps). *Enforced:* `test_exchange_slippage.py`.
- **Limit prices use round-half-up**: `compute_limit_prices()` uses `Decimal.quantize(ROUND_HALF_UP)`, not banker's rounding. *Enforced:* `test_exchange_limits.py`.
- **Limit detection**: `Exchange.resolve_limit_prices()` prefers Tushare published `$up_limit`/`$down_limit` (bare-name day bins), falls back to `compute_limit_prices(pre_close, band)` only when absent/NaN. The published field carries fen-rounding, ex-rights adjustment, the pre-2023 +44%/−36% IPO-first-day rule, and post-2023 no-limit windows. `$up_limit`/`$down_limit` are in `ENGINE_REQUIRED_FIELDS`; `stk_limit` is `approved` (these are session-open-knowable execution fields, no `Ref` lag). *Enforced:* `test_exchange_limits.py::ResolveLimitPricesTests`, `test_field_registry.py::...stk_limit_bare_fields_approved_for_formal`.
- **Event-driven suspension wiring**: `EventDrivenBacktester` passes `suspension_ranges.parquet` into `Exchange` when present; else logs the fallback to the `vol == 0` proxy. *Enforced:* `test_event_driven_backtester_wiring.py`.
- **Event-like daily endpoint namespacing**: `_materialize_daily_dataset` writes `{dataset}__{column}.day.bin` for every dataset in `EVENT_LIKE_DAILY_DATASETS` (`top_list`, `top_inst`, `block_trade`, `cyq_perf`) to avoid overwriting canonical `$close/$amount/$vol` kline bins. Each such dataset MUST also appear in `EVENT_LIKE_DAILY_FIELD_PREFIX`. Access via `$top_list__close`, `$block_trade__amount`, etc. *Enforced:* `test_event_like_daily_namespace.py`.
- **ENGINE_REQUIRED_FIELDS**: the canonical 10-field tuple (`$open $close $high $low $vol $amount $pre_close $adj_factor $up_limit $down_limit`) lives in [event_driven/constants.py](src/backtest_engine/event_driven/constants.py) (`$up_limit`/`$down_limit` added with the stk_limit promotion so formal runs preload the limit fields). `EventDrivenBacktester.run()` unions caller `preload_fields` with it whenever preloading. Add an engine-required field there, not in `_fetch_day_data`.
- **Price-return (vectorized) vs total-return (event-driven) — NOT comparable for dividend-paying books**: `VectorizedBacktester` defaults to `deal_price='close'` and computes returns from the provider's RAW `$close`, so a dividend/bonus ex-date drops the price WITHOUT crediting the distribution → it reports a **price return** that understates a yield-bearing book by ~its dividend yield. `EventDrivenBacktester` credits post-tax cash dividends + bonus shares on the ex-date via [corporate_actions.py](src/backtest_engine/event_driven/corporate_actions.py) `CorporateActionHandler.process` (`cash_div_tax * shares` → `portfolio.credit_cash`; `stk_div * shares` into the position) → **total return** (PIT-correct; the correct deployment figure). Never compare a vectorized price-return screen against an event-driven total-return run for a dividend-paying strategy without accounting for the gap. *Verified — long_only value book, 2021-26:* EventDriven +11.64% vs vectorized +6.17% CAGR; no-op'ing `CorporateActionHandler.process` collapses EventDriven to +6.59% ≈ vectorized → dividends+bonus = +5.05% CAGR (phase6d isolation; not a leak/bug). *Enforced:* `tests/backtest_engine/test_corporate_actions.py` pins the dividend/bonus crediting (the total-return mechanism — fails if `process` stops crediting); the +5.05% empirical decomposition is in `workspace/research/long_only_50cagr/FINDINGS.md` + project_state 2026-06-04.
- **Suspension vs delisting — universe-boundary separation, force-close never NaN, NO delisting haircut**: a suspended-but-listed name stays in the PIT `all` universe (`all_stocks.txt`) and `D.features` returns a **NaN-OHLCV row** → it's in `today_codes` → carried, NOT force-closed (trading blocked by the `vol==0`/NaN `is_suspended` proxy + the engine's `pd.isna(price)` fill guards). A **delisted** name drops out of the universe → absent from `day_data` → `BacktestEngine._handle_delistings` force-closes it. The pre-delisting collapse (退市整理期 / consecutive limit-downs) is ALREADY marked day-by-day in the daily `$close` path (verified: 300280.SZ 6.99→0.33 = −95%, 000851.SZ 2.95→0.38 = −87%), so the force-close prices at the **carried-forward last KNOWN real close** (`self._last_valid_price`, updated in `_record_day`; resolver `_resolve_delist_price`: cache → prev close → `avg_cost` → `0.0`) — do NOT add a delisting haircut (it would double-count a loss already booked) and do NOT fall back to the optimistic `avg_cost` when a real price exists. `Portfolio.force_close` floors a NaN/negative price to `0.0` (total loss) so a NaN last-bar can never poison cash. Delist dates come from `stock_basic.delist_date` (Tushare `list_status='L,D,P'`, refreshed every `update_daily_data.py` run). *Enforced:* [tests/backtest_engine/test_delisting_force_close.py](tests/backtest_engine/test_delisting_force_close.py).

### 3.4 Formal-run governance (the 2026-05-26 freeze plan, PRs 1–10c)

Full per-PR history: [project_state.md](project_state.md). The standing contract that makes a run
"formal" and reproducible:

- **Provider attestation**: every host publishing a Qlib provider emits `data/qlib_data/metadata/provider_build.json` (the single source of truth for `provider_build_id`, `calendar_policy_id`, namespacing status, calendar bounds). Formal runs: missing manifest → fail; namespacing not enforced → fail; calendar mismatch → fail unless the policy allows. Schema [schemas/provider_build.schema.json](schemas/provider_build.schema.json); loader [provider_manifest.py](src/data_infra/provider_manifest.py). *Enforced:* `test_provider_manifest.py`.
- **Artifact provenance (schema v2)**: every formal artifact carries `provider_build_id` + `calendar_policy_id` + `execution_profile_id` + `execution_profile_hash` (+ `override_reason`/`override_diff` when overridden). Older artifacts read back `legacy_artifact=true` — viewable, not formal-eligible. The release gate cross-checks profile id + hash against the registry (unknown / `allowed_for_formal=False` / hash-mismatch → fail). Schema [schemas/artifact_provenance.schema.json](schemas/artifact_provenance.schema.json); gate [release_gate.py](src/research_orchestrator/release_gate.py). *Enforced:* `test_artifact_provenance.py`, `test_pr8_runtime_enforcement.py`.
- **ExecutionProfile is the formal contract**: every formal backtest passes `execution_profile=<id>` (frozen dataclass in [execution_profiles.py](src/backtest_engine/execution_profiles.py); built-ins `joinquant_daily_sim`, `joinquant_open_close_replica`, `realistic_china_stress` (not formal), `vectorized_screening_close`). `profile_hash` is a computed self-excluding property. A formal profile + explicit `fill_mode`/`slippage`/`exchange_config`/`volume_limit` override requires `override_reason` (else `OverrideRequiresReasonError`). *Enforced:* `test_execution_profiles.py`.
- **Calendar policy**: formal runs MUST pass `calendar_policy_id` (else `EventDrivenBacktester.run()` raises before any work). The 2026-02-27 freeze is [frozen_20260227_system_build.yaml](config/calendar_policies/frozen_20260227_system_build.yaml); for a frozen policy, observed Qlib calendar end MUST equal both policy and manifest end dates, run_mode must be in `allowed_modes`, and the manifest's own `calendar_policy_id` must match. Validation reads `calendars/day.txt` directly (no `qlib.init` dependency) and fires BEFORE feeder/preload. *Enforced:* `calendar_policy.py`, `test_pr8b_ordering_modes.py`, `test_pr8c_validation_wiring.py`; daily QA enforces frozen-policy calendar equality.
- **Preload hardening**: formal runs (`run_mode ∈ {formal, oos_test, joinquant_replication}` OR a formal profile) auto-enable `strict=True` + `require_preloaded=True` + `require_provider_manifest=True`. `assert_preloaded(...)` runs before the day loop; `strict_cache_only` then raises `PreloadCoverageError` on the FIRST cache miss (incl. partial/all-missing instruments) instead of per-day `D.features` fallback. Strict mode is enabled before warmup + `strategy.initialize`, restored in `finally`. `QlibDataFeeder.preload()` is removed (raises `NotImplementedError`) — use `preload_features(...)`. *Enforced:* `test_preload_hardening.py`, `test_pr8_runtime_enforcement.py`, `test_pr8b_ordering_modes.py`.
- **Field-status registry is the formal data gate**: every `$field` resolves through [field_status.yaml](config/field_registry/field_status.yaml) (committed governance) via `FieldStatusRegistry`. 4 statuses × per-stage flags. Unknown field → `unknown_field_policy[stage]` (warn in sandbox, fail in formal). The YAML is the LIVE source of truth for which datasets are usable — never enumerate it from memory. As of 2026-06-05 the ONLY non-`approved` registered dataset is `margin_detail_repayment` (quarantine — repayment fields `$rzche`/`$rqchl`, held for `.BJ`/BSE negatives); `hk_hold` was promoted to `approved` (2026-06-04, ingestion mis-diagnosis corrected); `pending_review` is empty. Everything else registered is `approved` (incl. moneyflow, the margin_detail balance/buy fields, stk_holdertrade, top_list, top_inst, block_trade, cyq_perf, and the income/balancesheet/cashflow statement families). Newly-approved daily/event endpoints are same-day outcomes → predictive factors MUST wrap every field in `Ref(...,1)` (§3.2). Transitions need an append-only [field_approval_log.jsonl](config/field_registry/field_approval_log.jsonl) entry + a per-promotion YAML under [approvals/](config/field_registry/approvals/). The release gate (`assert_field_dependencies_eligible`) and the validation resolver/dataset-build gates refuse formal artifacts touching disallowed fields, BEFORE the IS leg. *Enforced:* `test_field_registry.py`, `test_field_dependency_gate.py`, `test_pr9_validation_field_gate.py`.
- **Research-access chokepoint**: `qlib_windowed_features` is the mandatory formal `D.features` door; it validates reads against the `ResearchAccessContext` (`run_id, stage, design_hash, window, seal, allowed_fields`) — violations raise `HoldoutWindowViolation` / `HoldoutSealViolation` / `FieldAccessViolation`. `SealedBacktestRunner.run_workspace_pipeline` builds the context (required `time_split` + `pipeline_args`). Formal stages must `require_research_access_context(stage)`. AST lint [lint_no_bare_qlib_features.py](scripts/lint_no_bare_qlib_features.py) bans bare `D.features` outside the wrapper (in `run_daily_qa`). *Enforced:* `research_access_context.py`, `test_lint_no_bare_qlib_features.py`.
- **Cache + seal file-locking**: `HoldoutSealStore.claim_holdout_access`, `CacheManifestStore.record_cache_write`, and `TestingLedgerStore.record_event`/`record_verdict` wrap their ENTIRE read-check-write in `file_lock`. *Enforced:* `test_lock_concurrency.py`.
- **OOS seal spend-on-attempt (fail-closed holdout protection)**: formal OOS handlers (`handle_validation_event_backtest_oos`) claim the holdout seal at handler entry — after the IS-gate decision, BEFORE reading the prescription schedule or doing any provider/data work. Any post-claim failure CONSUMES the seal slot; recovery REQUIRES the same `run_dir` + `step_id` (`allow_same_run=context.resumed`, via `research_orchestrator_cli.py resume`), NEVER a fresh run with the same key — this makes multiple-OOS-attempt overfitting impossible across crash-resume boundaries. *Enforced:* `test_pr9_validation_field_gate.py::TestOOSHandlerSealClaimBehavior`.
- **Module boundaries**: workspace scripts carry a `SCRIPT_STATUS` header; 14 Class-D JoinQuant-mimic scripts are archived under [workspace/scripts/archive/](workspace/scripts/archive/) and must not be referenced from `src/`; `portfolio_risk` is dormant (`predict_portfolio_risk()` → `0.05`, `fit()` no-op) and its symbols must not be imported into any formal path. Governance files live under `config/` + `schemas/`, never `data/` (gitignored). *Enforced:* `tests/architecture/test_dormant_module_boundaries.py`.
- **Approval-evidence binding**: every approval YAML with a `provider_build_id`+`calendar_policy_id` binding is machine-validated against the live `provider_build.json` in daily QA (`approval_evidence_binding` block). A record with neither key needs `binding_exempt: true` + a non-empty reason (strict bool; both-present + exempt = contradiction → raise); exactly one key, null/blank values, or malformed YAML → `ApprovalEvidenceConfigError`. *Enforced:* [approval_evidence.py](src/data_infra/approval_evidence.py), `test_approval_evidence.py`.

### 3.5 Factor lifecycle & promotion gates (draft → candidate → approved)

Full phase history (Phases 1–7 + promotion harness): [project_state.md](project_state.md) and the
followable guide [src/alpha_research/factor_lifecycle/README.md](src/alpha_research/factor_lifecycle/README.md).
The standing gates:

- **Status ladder & boundary**: `draft` (discovery-usable) → `candidate` (passed the IS-only gate) → `approved` (passed the promotion gate). `get_factor_catalog()` is authoritative for ALL discovery/sandbox and IGNORES status (the 42 call sites do not change). Registry status gates ONLY formal `hypothesis_validation` components. `candidate` is additive and never auto-becomes `approved`.
- **Writer gate**: `FactorRegistryStore.set_status('approved')` and `StrategyRegistryStore.set_status('approved')` require a MANDATORY `current_git_sha` + a `promotion_evidence` artifact passing `assert_promotion_artifact_eligible` (clean tree, independent PIT-correct reproduction source, lint passed, parity ok), else `PromotionGateError`. Evidence `promotion_status` is force-set (can't be downgraded by a caller). *Enforced:* `test_promotion_gate.py`, `test_factor_registry.py`.
- **Reader gate (resolve-but-label)**: the resolver resolves every current registry row but LABELS `source_layer` by status+validity; the SOLE formal-permission point is the allow-set in `handle_validation_object_resolver` (`formal`, + `factor_registry_candidate` iff `prescription.allow_candidate_components`). A requested `definition_hash` is a real match filter (closes same-name shadowing). *Enforced:* `test_pr9_validation_field_gate.py::TestPR12FormalAllowSet`.
- **Definition-binding gate**: before any compute, every resolved formal factor's stored `definition_hash` must equal the current catalog hash (`current_catalog_definition_hashes()`, same algorithm as `sync_catalog`); mismatch / missing hash → `FactorDefinitionDriftError` (fail-closed). *Enforced:* `test_pr9_validation_field_gate.py::TestPR13DefinitionBindingGate`.
- **IS-only leakage boundary** (the `factor_lifecycle` profile, 8th built-in): the IS validator (`run_is_walk_forward`) is structurally bounded to `is_end` — factor date AND label-realization date (`r(t) = open_days[pos(t)+h]`, exact calendar) both ≤ `is_end`, enforced by `IsWindowedPanel.__post_init__` (`IsEndLeakageError`). No `oos_*` in IS evidence. Cross-sectional helpers (`cs_rank`/`cs_zscore`/`cs_demean`/`winsorize`) use a name-based date-level resolver (fail-closed, no positional fallback) to avoid ranking a stock across time. *Enforced:* `test_factor_lifecycle_walk_forward.py`, `test_cross_sectional_helpers.py`.
- **Promotion evidence producer**: `produce_promotion_evidence` (self-verifies through the gate) assembles 6 PIT canaries ([pit_canaries.py](src/data_infra/pit_canaries.py)) + an independent OOS reproduction that MUST re-run the screening's exact path (`run_batch_screening(engine="batch", horizons=(5,10,20))`, reading `rank_icir_20d` + 5d `ls_sharpe` — the metric the registration bar was defined against; a wrong-horizon LS-Sharpe is a false positive). Leak-freedom guaranteed by `provider calendar_end == OOS_END` + a `ResearchAccessContext` over the OOS window. *Enforced:* `test_pit_canaries.py`, `test_promotion_evidence.py`.
- **Unified 10-group standard (2026-06-11)**: ALL quantile-group evaluation paths use **10 groups (deciles)** — `batch_screening` (`DEFAULT_SCREENING_QUANTILES=10`, wired through `run_batch_screening(n_quantiles=…)`), `quantile_analysis` (default 10; thin-bucket WARNING below 20 names/bucket, group count never silently degraded), `unified_eval.EvalMethodology.n_quantiles=10`, `promotion_evidence` (parameter now actually wired into the screening call — it was dead before), `validation_steps`/`event_signal_steps`, matching `factor_lifecycle.DEFAULT_N_QUANTILES=10` and the CICC手册 protocol. ⚠ Evidence registered BEFORE 2026-06-11 (Round-6 winners, GP, arXiv D1-D4, eps_diffusion) was quintile-based — pass `n_quantiles=5` to reproduce it bit-for-bit; decile `ls_sharpe` (Q10−Q1) is NOT comparable to the historical quintile bar. The 10-group oriented-heldout profile is persisted per formal-evidence row (`quantile_profile` inside `unified_metrics_json`) and rendered on the dashboard. **"refresh" label RETIRED (2026-06-11 user directive)**: external taxonomy is discovery / formal ONLY; automated formal rows write `run_type='factor_lifecycle_auto'` / `evidence_class='formal_auto'` (legacy rows keep the old strings, dashboard merges both); the load-bearing governance flag `formal_evidence_eligible` (only human-signed rows can back a status change) is UNCHANGED. `EvalMethodology.top_q=0.2` (long-leg deployable proxy) is deliberately NOT tied to the group count. Universe framework for multi-domain eval: [universes.py](src/alpha_research/factor_eval/universes.py) (7 named `UniverseSpec`s + CICC exclusion screens) over [universe_membership.py](src/data_infra/universe_membership.py) (PIT as-of index membership / ST / listing-age reference masks). *Enforced:* `test_universes.py`, `test_universe_membership.py`.
- **Holdout-seal identity (promotion/OOS)**: a `FrozenSelectionSet`-driven OOS or promotion run claims `HoldoutSealStore` with `seal_key = FrozenSelectionSet.frozen_set_hash` (sha256 over the frozen selection identity — factor ids/versions/definition-hashes/expected-directions, candidate-pool, selection-rule, eval-protocol, metric, portfolio-side, universe, time-split, rebalance, neutralization; EXCLUDES prose labels and provider/calendar build ids), recorded in the promotion evidence. `design_hash` is legacy fallback only — NEVER key sealed-OOS budget by a mutable `design_hash` (a renamed hypothesis could otherwise re-test the same selected set). Live since the 2026-06-02 promotion harness (the frozen-13 set spent 2021-2026). *Enforced:* `test_frozen_selection_set.py`, `test_promotion_evidence.py`.
- **Live registry state (2026-06-17)**: `data/factor_registry/factor_master.parquet` current set = **260** (156 `draft` / 97 `candidate` / **7 `approved`**). **E1b (2026-06-17):** +36 CICC volatility (图表16) `draft`s (`vol_down/up_std`, `vol_highlow_avg/std`, 4 shadow families avg/std × {20,60,120}d) backed by the certified `sign_conditional_std` operator (true subset std, limit-excluded via the materialized `$limit_status` field) + inline `Greater`/`Less` shadows; `vol_std`≡`risk_vol` exact dedup skipped; GPT factor-logic APPROVE. See project_state 2026-06-17. **E1a IS-gate (2026-06-17):** the 3 reversal passers `mmt_route_20d`/`mmt_route_250d`/`mmt_discrete_20d` were promoted `draft→candidate` via matrix-reuse (the 2010-2020 univ_all walk-forward, bit-identical to the orchestrator gate; GPT 2-round review), `expected_direction=inverse`, `a_priori` (2021+ sealed) — `mmt_discrete_20d` carries a non-independence caveat vs the already-candidate `rev_up_down_ratio_20d`. See project_state 2026-06-17. ⚠ The eps_diffusion narrative later in THIS bullet (2026-06-09/10) is **SUPERSEDED**: `earn_eps_diffusion_60`/`_120` were **REVOKED `approved`→`candidate` on 2026-06-14** (restatement-canary contingency fired — see project_state + memory `project_tushare_15000_expansion`), so approved is **7** (the 6 Round-6 winners + `earn_sue_ni_assets`), not 8/9. **E1a (2026-06-15)** added 6 CICC price-volume momentum `draft`s — `mmt_route_20d/_250d`, `mmt_discrete_20d/_250d`, `mmt_time_rank_20d`, `mmt_highest_days_250d` — backed by W∈{20,250}-certified operators (`path_adjusted_momentum`/`up_down_day_share`/`days_since_high`/`ts_rank`) and linked into the **v2** PV cohort manifest ([cicc_price_volume_cohort_v2.yaml](config/replication/cicc_price_volume_cohort_v2.yaml), sha `3e07e048b35cdd87`; v1 archived). mmt_range deferred (true operator `amplitude_top_bottom_20pct_return_spread` pending; the 4%-threshold worked-example operator was renamed `amplitude_threshold_4pct_conditional_sum`, old id now fail-closed `blocked`). See project_state 2026-06-15. **[Historical snapshot below, 2026-06-10 — eps_diffusion status superseded as noted above:]** current set = **190** (89 `draft` + 92 `candidate` + **9 `approved`**). **arXiv D1-D4 batch (2026-06-10, full arc same day)**: the knowledge-framework exploration ([D1_D4_SCREEN_RESULTS.md](workspace/research/idea_sourcing/knowledge/D1_D4_SCREEN_RESULTS.md)) added 5 catalog drafts; ALL 5 passed the IS `factor_lifecycle` gate (heldout ICIR 0.34-0.60) → `candidate`; then the user-directed **single-shot sealed OOS (2021-01-01..2026-02-27, one FrozenSelectionSet `092524eb…`, real seal spent at `5a946c13e724`) PASSED ONLY 1 OF 5**: `earn_sue_ni_assets` **approved** (OOS rank_icir **+0.026**, LS Sharpe **1.06** — scraped the bar; ~93% decay from IS 0.35 → a WEAK, growth-adjacent surprise factor; `approved` ≠ deployable, deployment gate untested). The other 4 stay `candidate` with **2021-2026 OOS SPENT — never re-test as fresh**: `alpha_chip_cgo_smooth_20d` **sign-FLIPPED** (OOS −0.265/LS −0.63 — GP-style collapse; the exploration's +0.047 marginal increment was an IS artifact of the 2018-2020 quality rally, exactly as the pre-registered qual_roa-confound concern predicted), `north_hold_change_20d_cov`/`_60d_cov` sign-flipped (−0.066/−0.114; foreign-accumulation→continuation reversed in the 2021+ outflow era), `earn_sue_ni_mcap` LS 0.77 < bar. Selection class was **a_priori IS-only** (literature-informed caveat recorded). D2 (moneyflow informed-large-order) was explored and **REJECTED at the IS stage** (REDUNDANT; negative result recorded — do not re-mine). **Sealed-OOS gate scorecard: 4/5 IS-strong factors stopped** (GP precedent repeated). Provenance: [arxiv_d1d4_selection_provenance.json](workspace/research/idea_sourcing/arxiv_d1d4_selection_provenance.json) + [arxiv_d1d4_sealed_oos_promotion.json](workspace/research/idea_sourcing/arxiv_d1d4_sealed_oos_promotion.json); driver `workspace/scripts/promote_arxiv_d1d4_sealed_oos.py`. The 9 approved = the 6 Round-6 winners + the 2 provisional eps_diffusion + `earn_sue_ni_assets`. Earlier history: `qual_gross_profitability` (OSAP-sourced) was added 2026-06-08 and promoted `draft→candidate` (IS-only `factor_lifecycle`, heldout RankICIR 0.138). Its single-shot **sealed-OOS approval test then FAILED** (2026-06-08, deterministic reproduction via the sanctioned OOS path): OOS RankICIR **−0.12** (sign-FLIPPED vs IS +0.14), LS Sharpe **−0.66** (bar: >1.0) → **GP stays `candidate`, NOT approved**; its 2021-2026 OOS is now observed/spent (must NOT be re-tested as "fresh"). Textbook IS-strong / OOS-collapse — the sealed-OOS gate working as designed (IS evidence ≠ deployable). No real seal was claimed (the verdict is from the deterministic dryrun reproduction; live spend skipped as the FAIL is foregone). Two more OSAP Tier-1 drafts added 2026-06-08 — `qual_cash_to_assets`, `qual_rd_to_assets` (asset-composition / R&D; modest +marginal increment +0.019/+0.017, below the clean-orthogonal bar). Initially field-ineligible (used bare `$money_cap`/`$total_assets`/`$rd_exp` aliases); on 2026-06-08 **REPOINTED to the registered PIT statement fields** — `$money_cap_q0`/`$total_assets_q0` (already approved) + `$rd_exp_sq_q0` (promoted into the `income` family, parity 0-mismatch; see [approvals/2026-06-08_income_rd_exp_sq_q0_to_approved.yaml](config/field_registry/approvals/2026-06-08_income_rd_exp_sq_q0_to_approved.yaml)) — so both are now **formal-eligible drafts (version 2)**, removed from `KNOWN_NON_FORMAL_FACTORS`. `rd_to_assets` is a sub-universe factor (cov ~0.31, R&D-reporters only). NOTE: `$rd_exp` had been deliberately excluded from the 2026-05-31 income promotion for sparse coverage — re-introduced now (cov 0.83 clears the ≥50% gate + a factor consumes it). **`report_rc` (analyst forecasts) integrated + approved 2026-06-09** (4 `$report_rc__*` event-flow primitives) → 2 more **candidates** `earn_eps_diffusion_60` / `earn_eps_diffusion_120` (analyst EPS-revision breadth = net % of analysts raising FY1 EPS) — the **FIRST genuinely-new-dimension idea-sourced factor**: compliant size-neutralized IS ICIR ~0.55 (60d) / 0.46 (120d), **SURVIVES orthogonalization to ROE/growth** (residual retains ~100%), reproduces the prior untrusted hand-rolled WAVE1A pilot through the sanctioned path. PASSED the IS `factor_lifecycle` gate (draft→candidate; heldout RankICIR 0.42/0.34, sign-consistency 1.00/0.86), then the single-shot sealed-OOS — **APPROVED 2026-06-09 via EXPLICIT user CANARY OVERRIDE**: OOS RankICIR +0.131 (60d, sign-stable vs IS +0.42) / +0.070 (120d), LS Sharpe **7.24 / 2.59** (>1.0 bar) → both PASS (the OOS was genuinely UNBURNED, selected on IS only — unlike the 87 `oos_informed_backfill` candidates). ⚠⚠ **THE APPROVAL IS PROVISIONAL / CONTINGENT: the 2026-06-15 breadth-restatement canary was OVERRIDDEN (not yet run); if it FAILS, report_rc re-quarantines and these 2 approvals MUST be REVOKED** (`set_status` → candidate). The LS Sharpe is **gross / 5d / sub-universe — NOT a deployable number, and suspiciously high** (a "too-good" breadth result is exactly what the canary validates against contamination). Provenance: [eps_diffusion_sealed_oos_promotion.json](workspace/research/idea_sourcing/eps_diffusion_sealed_oos_promotion.json) (`canary_overridden=true`); driver `workspace/scripts/promote_eps_diffusion_sealed_oos.py`. **DEPLOYMENT GATE — NOT a deployable strategy (2026-06-09):** `approved` (factor-level cross-sectional IC) ≠ tradable. Event-driven long-only top-K, 1×, realistic costs, OOS 2021-2026: on the BROAD analyst-covered universe top30 = +20.8% CAGR / −34.5% MDD / Sharpe 0.87, BUT that depends on less-liquid mid-caps; restrict to the deployable LIQUID universe (top-300 by 20d $-vol) and it COLLAPSES to **+4.5% (monthly) / +9.8% (quarterly) CAGR with −62 to −65% MDD** (the liquid-mega-cap form = the crowded 赛道 momentum trade that crashed 2021-24). Capacity within liquid is fine (¥10M≈¥100M) but the return is uninvestable. **eps_diffusion is a genuine alpha factor but NOT a deployable long-only strategy at size — do NOT treat the `approved` status as production-ready.** Scripts: `build/eval_eps_diffusion_deployment.py` + `build/eval_eps_diffusion_capacity.py`. The 8 approved = the 6 Round-6 sealed-OOS winners (`liq_zero_ret_days_10d`, `rev_turnover_spike_5d`, the 3 `grow_*_yoy_accel_q`, `qual_piotroski_fscore_9pt`) + the 2 `earn_eps_diffusion_60`/`_120` (canary-OVERRIDDEN, **provisional** — revoke if the 2026-06-15 canary fails; see above). The phase-6/7 candidates are an `oos_informed_backfill` (2021-2026 is BURNED for them; the candidate→approved gate must use a genuinely-sealed window). Factor `approved` ≠ tradable-strategy validated — strategy deployment is a separate downstream gate. Provenance: the JSONs under [workspace/research/factor_expansion/](workspace/research/factor_expansion/).
- **Catalog count is DERIVED, never hard-coded**: composition = base factors + industry-relative + Layer-2 composites. `catalog_composition()` (in [catalog.py](src/alpha_research/factor_library/catalog.py)) is the single source of truth — call it, do not pin a number anywhere. Catalog↔registry parity (sync output == composition, no duplicate ids, idempotent re-sync) is enforced STRUCTURALLY by [test_factor_registry.py](tests/alpha_research/test_factor_registry.py), so adding a factor needs no count-assertion edits. `TestFormalFactorCompatibility` separately proves every live-catalog factor resolves at formal_validation.

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

- **Read the interface doc BEFORE fetching (MANDATORY).** Before writing or running ANY code that fetches a Tushare endpoint — new ingest OR re-pull — you MUST first consult that interface's official documentation and understand it in detail. The full document/2 doc set is mirrored offline at [Tushare数据接口/](Tushare数据接口/): start at [INDEX.md](Tushare数据接口/INDEX.md), open the interface's `content/<doc_id>_<名称>.md`, and read its field list, 积分/限量, **update cadence**, and **PIT/backfill semantics**. Any ★-flagged date field (`create_time`/`ann_date`/`f_ann_date`/`pub_date`/`update_flag`) means **nominal date ≠ visible date** → PIT must anchor on that field (§3.2). Record the field list + cadence + PIT note into [data/data_dictionary.md](data/data_dictionary.md) before writing the fetcher (then route through the ledger/provider, never hand-rolled). If the endpoint is new/changed and absent from the corpus, re-fetch the doc per [Tushare数据接口/README.md](Tushare数据接口/README.md). **Skipping this is the documented root cause of the report_rc PIT saga.**
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
- [src/dashboard/build_dashboard.py](src/dashboard/build_dashboard.py) — rebuild the centralized HTML dashboard: a **read-only projection** of the registries / field governance / factor catalog / research artifacts / `project_state.md`, plus a full collection of Claude Code session transcripts, into **`index.html` at the project root** (self-contained, gitignored; `data.json` + session cache under `workspace/outputs/dashboard/`). Code is the auxiliary package [src/dashboard/](src/dashboard/) (a read-only reporting tool, NOT one of the six research modules — do not import it from any formal path). Auto-rebuilt by a `SessionEnd` hook (`.claude/settings.json`) + the hourly `QuantDashboardRefresh` scheduled task; human-curated overlay in [workspace/configs/dashboard_board.yaml](workspace/configs/dashboard_board.yaml). Never mutates project data. Full design: [src/dashboard/README.md](src/dashboard/README.md).

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
11. **No leverage in strategy research (added 2026-06-08).** Leverage is NOT a viable option — research, evaluate, and report every strategy **unlevered** (gross exposure ≤ 1× capital; no margin financing / borrowing to exceed 100% invested). Never propose leverage as a path to a return target, and never quote a levered CAGR as the headline result; the deployable number is the **1× number**. A long-only book is fully-invested-or-cash; a market-neutral book is sized at its natural 1× (funded long/short, gross ≤ ~1×) — do not scale it up. Rationale: leverage manufactures return only by multiplying volatility and drawdown (it adds no edge), and our deployment context does not assume access to it — CAGR must be earned via Sharpe at native volatility, not borrowed. (Note: `config.yaml risk.max_leverage` is a legacy field; do not treat it as license to lever in research.)

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
- **Return basis differs (see §3.3)**: vectorized reports **price return** (raw `$close`, no dividend credit); event-driven reports **total return** (credits dividends + bonus shares on the ex-date). For a dividend-paying book they diverge by ~the yield (≈+5% CAGR on the long_only value book) — the event-driven total-return figure is the deployment number, and a vectorized vs event-driven gap is expected, not a bug.

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

The orchestrator at [src/research_orchestrator/](src/research_orchestrator/) is the preferred way to run formal research. The 8 built-in profiles are: `factor_screening`, `theme_strategy`, `event_driven_signal_research`, `ml_signal_model_research`, `strategy_improvement`, `benchmark_audit`, **`hypothesis_validation`**, **`factor_lifecycle`** (the IS-only `draft→candidate` factor gate — Phase 5).

**Factor lifecycle (start-to-finish overview):** for how a factor moves `draft → candidate → approved` — the status ladder, the no-lookahead label boundary, the 4-step IS-only gate, the phase map (1–7), the current registry state, and the non-negotiable invariants — read **[src/alpha_research/factor_lifecycle/README.md](src/alpha_research/factor_lifecycle/README.md)** (the followable guide; per-phase "what changed" lives in [project_state.md](project_state.md), enforced invariants in §3 above).

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
