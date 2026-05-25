# Quantitative Trading System — Full Overview

*Snapshot date: 2026-04-10*
*Source: Captured by Claude (claude-opus-4-6) during a thorough workspace review session.*
*Purpose: Version-controlled reference snapshot of the system's architecture, state, and active research focus. When this file disagrees with `project_state.md`, trust `project_state.md` — it is updated continuously, this file is a point-in-time snapshot.*

---

## 1. What This System Is

A **full-stack quantitative trading system** for Chinese A-share stocks, currently in simulation/research mode. The infrastructure for data, factors, backtesting, and research orchestration is production-ready; live-trading broker integration (`portfolio_risk`, XTP broker) remains skeletal. The codebase lives at `E:\量化系统` on Windows 11 with Python 3.12.7.

Research account-size assumption: **2,000,000 RMB**.
Data coverage: **2008-01-02 to 2026-02-27** (4,410 trading days).

---

## 2. Architecture — Six Modules

### Module 1: `src/data_infra/` — Data Infrastructure

**The foundation.** Handles everything from raw API calls to a production Qlib binary backend.

- **Data flow**: Tushare Pro API → rate-limited `TushareFetcher._safe_api_call()` → `StorageManager` writes hierarchical Parquet → `StagedQlibBackendBuilder` profiles, normalizes, builds PIT ledgers, and compiles `.day.bin` binaries
- **PIT backend** (`pit_backend.py`, 2,503 lines): Single most complex file in the codebase. Manages 30+ dataset specs across 3 phases. Statement families (income, cashflow, balancesheet) are served with paired cumulative/quarterly semantics. Revision-aware ledgers resolve duplicate `(ts_code, ann_date, end_date)` groups using `update_flag` and deterministic tie-breaks. Canonical `pit_*` fields (e.g. `pit_or_yoy`, `pit_q_op_qoq`) are derived from the ledgers.
- **Staged build pipeline**: Raw → `data/normalized/` → `data/pit_ledger/` → `data/qlib_builds/<build_id>/` → published to `data/qlib_data/`
- **7 pipeline entry points** under `src/data_infra/pipeline/`: 3 bootstrap phases, daily update, indicator history refresh, staged Qlib build, database verification
- **Production status**: Live PIT provider published `2026-04-01`, build id `prod_candidate_20260401`, backup retained at `data/qlib_data.bak_prod_candidate_20260401`. 5,755 feature directories. Post-publish audit passed on 50 sampled symbols with full alias parity.

### Module 2: `src/alpha_research/` — Factor & Model Research

**The research library.** ~11,687 lines across 26 files.

- **Factor library**: **191 factors across 15 categories** (momentum, reversal, value, quality, growth, liquidity, technical, size, risk, volatility, flow, northbound, margin, composite, mixed). Two-layer design: Layer 1 = Qlib expression strings (C/Cython speed), Layer 2 = pandas cross-sectional transforms (cs_rank, z-score, composites). All factors apply `Ref(..., 1)` to prevent same-day leakage.
- **Factor evaluation toolkit** (9 modules): IC/RankIC/ICIR analysis, quantile returns, monotonicity, decay across horizons, correlation clustering, neutralization, optimized batch screening engine (~33% faster than reference), plotting
- **Model zoo**: LightGBM, XGBoost, ElasticNet — uniform fit/predict/save/load interface
- **Theme strategy framework**: Field-first research flow (theme thesis → field audit → universe search → component diagnostics → recipe search → event-driven confirmation). 3 built-in themes: `small_cap`, `st`, `flow_northbound`. Generates ~20+ component specs per theme using bounded transform families. `AH premium` deferred until H-share pairing data is available.
- **Registries**:
  - **Factor registry** — 149 formal factors (129 base + 20 composite). File-backed master/evidence/run_index/status_history/review.html.
  - **Candidate registry** — 23 theme_component candidates (all `small_cap`).

### Module 3: `src/backtest_engine/` — Dual Backtesting Engines

- **VectorizedBacktester** — Qlib-integrated, fast signal screening. Convenience defaults need explicit override for serious research (`deal_price='open'`, `only_tradable=False`, `forbid_all_trade_at_limit=True`).
- **EventDrivenBacktester** — Realistic A-share simulator with:
  - **Multi-tier price limits** (date-aware): ST ±5%, ChiNext ±20% post-2020, STAR ±20%, BSE ±30%, Main ±10%
  - **T+1 settlement** enforced via `Position.closeable_amount`
  - **Volume constraints**: 25% of daily volume per order
  - **Lot sizes**: 100 shares (all boards)
  - **Cost model**: commission + stamp tax (rate changed 2023-08-28), ¥5 minimum, slippage models
  - **preload_features()**: cuts 1-year backtest from 5+ min to ~24 sec
  - **Parity**: 87.8% buy-overlap with JoinQuant reference

### Module 4: `src/portfolio_risk/` — Portfolio Construction (Skeletal)

- `PortfolioOptimizer` — cvxpy mean-variance with turnover penalty (working but basic)
- `risk_models/`, `cost_models/` — placeholder structure
- Config-driven via `config.yaml`: max_drawdown=15%, max_leverage=1.5, single_stock_max=5%
- **Known gap**: `MultiFactorRiskModel.fit()` needs real factor extraction. `MarketImpactModel` is flat-rate only.

### Module 5: `src/result_analysis/` — Performance Evaluation

- **50+ metric functions**: Sharpe, Sortino, Calmar, Information Ratio, alpha/beta, max drawdown, drawdown duration, win rate, profit factor, tail ratio, skewness, kurtosis, rolling metrics, trading stats
- **BacktestReport** — one-call interface for summary/plot/yearly/monthly/rolling/distribution
- **Plotly-based interactive charts** — equity curve, drawdown, monthly heatmap, rolling metrics, return distribution

### Module 6: `src/research_orchestrator/` — DAG Workflow Engine

*(Added 2026-04-09, V2 fully audited 2026-04-10.)*

- **6 built-in profiles**: `factor_screening`, `theme_strategy`, `event_driven_signal_research`, `ml_signal_model_research`, `strategy_improvement`, `benchmark_audit`
- **21-capability vocabulary** across 3 categories: `core_research` / `diagnostic` / `support`
- **DAG compilation** from profile requests, serial topological execution
- **Strict resume**: `request_hash + plan_hash` must match. `resume_policy` is excluded from hash to allow safely resuming completed runs.
- **5 typed registries**: `factor_registry`, `candidate_registry`, `signal_registry`, `model_registry`, `strategy_registry`
- **Legacy entrypoints** are now compatibility shims routing into the orchestrator (`workspace/scripts/batch_factor_screening.py`, `src/alpha_research/theme_strategy/cli.py`, `workspace/research/alpha_mining/event_driven_strategy_*`, `audit_benchmark_index.py`)
- **CLI**: `workspace/scripts/research_orchestrator_cli.py profiles | plan | run | resume`
- **Run artifacts**: `dag_plan.json`, `dag_state.json`, `run_metadata.json`, `artifact_manifest.json`, `produced_objects.json`, `lineage_links.json`, `review_summary.json`, plus per-step `steps/<step_id>/{step_metadata.json, step_outputs.json, artifact_manifest.json}`

---

## 3. Data Layer

### Current Coverage

| Dataset | Coverage | Status |
|---|---|---|
| Daily OHLCV + valuation + adj_factor | 2008–2026, 4,410 days, ~5,500 stocks/day | Production |
| 7 major indices (SSE, CSI 300/500/1000, SZSE, ChiNext, STAR 50) | 2008–2026 | Production |
| Income statements (cumulative + quarterly) | 82 + 72 period files | PIT served |
| Cashflow (cumulative + quarterly) | Full + 72 quarterly files | PIT served |
| Balance sheets (cumulative only) | 72 files | PIT served — quarterly unavailable from Tushare (confirmed 2026-03-31) |
| Financial indicators (VIP) | 97 partitions, 544,986 rows, 109 cols incl. `update_flag` | PIT served, refreshed 2026-04-01 |
| Moneyflow | 4,405 daily files | PIT served, 5 known-empty dates curated |
| Northbound (Stock Connect) | 2,153 files (2017–2026) | PIT served, 67 non-connect days curated |
| Margin trading | 3,863 files (2010–2026) | PIT served |
| Daily limit prices (up/down) | 4,410 files | PIT served |
| Dividends | 20 annual files | Raw |
| Index weights | 219 monthly snapshots | Raw |
| Industry (Shenwan 2021) | Single file | Static |
| ST stocks — range form `st_stocks.txt` | 1998–2026 | Authoritative |
| ST stocks — daily `stock_st_daily.parquet` | 2016-08-09 to 2026-03-23, 307,696 rows | Secondary (has 2020-01-02 gap) |

### Serving Layers

| Layer | Path | Purpose |
|---|---|---|
| Raw immutable | `data/` | Original Tushare Parquet partitions |
| Canonical normalized | `data/normalized/` | Schema-normalized, code-normalized canonical tables |
| PIT ledger | `data/pit_ledger/` | Revision-aware ledgers keyed by conservative disclosure dates |
| Staged builds | `data/qlib_builds/<build_id>/` | Validated provider builds before publish |
| Published provider | `data/qlib_data/` | Active Qlib backend |

### PIT Fundamental Conventions

- Statement families serve cumulative and quarterly ledgers separately
- Cumulative fields: `field`, `field_cum_q0..q4`
- Quarter fields: `field_q`, `field_sq_q0..q4` (prefer quarterly ledger, fall back to cumulative-derived)
- Snapshot fields: `field`, `field_q0..q4`
- PIT-derived growth fields (canonical): `pit_or_yoy`, `pit_op_yoy`, `pit_netprofit_yoy`, `pit_basic_eps_yoy`, `pit_q_sales_yoy`, `pit_q_op_qoq`, `pit_ocf_yoy`
- Report-type precedence: adjusted single-quarter `report_type=3` preferred over `2`

### Code Format Convention

- **Tushare**: `{code}.{exchange}` — e.g. `000001.SZ`, `000300.SH`
- **Qlib**: `{code}_{exchange}` — e.g. `000001_SZ`, `000300_SH`
- **Convert**: `ts_code.replace('.', '_')`
- **Silent failure mode**: wrong format returns zero matches with no error

---

## 4. Research Progress

### Factor Screening (Complete)

- Full window 2012–2025, horizons 5/10/20 days
- **149 factors screened** (129 base + 20 composite)
- **Grades**: 18 A / 25 B / 72 C / 34 D
- **Top signals**: liquidity (`liq_vol_cv_20d`), turnover-shock, skew/risk, reversal composites
- **Phase 3 strongest new-data factor**: `flow_net_inflow_20d`
- Latest formal run: `workspace/research/alpha_mining/latest_backend_screening_20260401_new_data/`

### Event-Driven Strategy Research (Complete)

- 43 A/B factor studies, 7 walk-forward test folds, holdout diagnostic
- Current baseline: all-market long-only, `C_stability_score` signal, 50 stocks, 10-day rebalance, benchmark CSI 500
- Stitched test-window returns positive but underperformed CSI 500 over the full OOS span
- Formal run: `workspace/research/alpha_mining/event_driven_strategy_research_full_20260401_main/`

### Strategy Improvement (Complete)

- 53 variants across 4 stages (parameter sensitivity, portfolio expression, stability-score upgrades)
- **Best variant**: `C_stability_score`
  - Stitched total return: +82.96%
  - Stitched benchmark (000001.SH) total return: +59.14%
  - Stitched OOS relative excess: **+14.97%**
  - 5/7 positive-excess test folds
  - Holdout relative excess: +3.17%
  - Worst-fold max drawdown: **-31.01%**
- **Not promoted**: missed the -30% drawdown gate by ~1.01 percentage points
- **Key finding**: slowing rebalance from 5 to 10 days was the biggest practical lever
- Stage B (tiered / score-proportional weighting) showed no benefit over Stage A equal-weight
- Formal run: `workspace/research/alpha_mining/event_driven_strategy_improvement_full_20260403_retry_rankfix/`

### ML Research (Complete)

- ElasticNet + LightGBM comparison completed
- Conservative execution defaults: benchmark 000001.SH, label_horizon=10, rebalance=10d, topk=50, adv20≥5M RMB, participation≤2%
- Formal run: `workspace/research/alpha_mining/event_driven_strategy_ml_research_full_20260404_main/`

### Theme Strategy (In Progress)

- Framework operational with 3 themes: `small_cap`, `st`, `flow_northbound`
- **Small-cap universe search**: sc_u1 ~88-93, sc_u2 ~444-453, sc_u3 ~460-470 eligible stocks per day
- 23 theme component candidates registered (all small_cap)
- Markdown reporting expanded with universe rationale, component selection, signal selection, theme review
- Quick event-driven reuse mode: `--recipe-source-run-dir` lets `--stage event_driven` skip recomputing universe/component/recipe

### Research Orchestrator V2 Audit (2026-04-10)

- Full audit completed. Fixes applied:
  - `StepExecutionContext.resumed` propagation
  - `theme_strategy` logging handler cleanup
  - Root/step artifact-manifest completeness
  - `strategy_improvement` capability declaration alignment
- Audit artifacts: `workspace/outputs/orchestrator_audit/20260410_003034/`
- Remaining open risks: semantic `noop` capability gaps, incomplete long-running real `theme_strategy` quick event-driven smoke

---

## 5. Hard Invariants — Never Break

1. **Code format**: Tushare `.` ↔ Qlib `_` — silent zero-match if wrong
2. **Benchmark codes** also use the underscore form: `'000300_SH'`, not `'SH000300'`
3. **Trading calendar**: `data/reference/trade_cal.parquet` is ground truth — business days ≠ trading days
4. **ST source**: `data/qlib_data/instruments/st_stocks.txt` (range form) is authoritative, covers the 2020-01-02 gap
5. **PIT fundamentals**: align on `ann_date`, `shift(1)` after `merge_asof`, forward-fill across calendar gaps, use provider `pit_*` fields as canonical growth
6. **MultiIndex order**: Qlib `D.features()` returns `MultiIndex(instrument, datetime)`, not `(datetime, instrument)`
7. **Qlib expression negation**: `-Operator(...)` doesn't parse — use `0 - Operator(...)`
8. **Next-day factors**: prefer `Ref(..., 1)` over same-day values — same-day leakage is the most common bug
9. **Adjusted vs raw prices**: adjusted for cross-day returns / momentum; raw for PIT accounting ratios
10. **Tushare safety**: never parallel fetchers, always use `_safe_api_call()` with retry/backoff; on 429, increase sleep, don't retry harder

---

## 6. Banned Anti-Patterns (Signal Backtesting)

1. Filtering before factor computation
2. Dropping rows that should remain available for forward-fill
3. Encoding tradability inside the signal
4. Mixing ranking scope with execution filters
5. Omitting signal forward-fill when methodology requires continuity

**Four-layer pipeline (mandatory)**: factor computation → universe selection → signal construction → execution. Keep concerns separated.

---

## 7. Production Research Execution Defaults

For serious vectorized runs, set explicitly (do not rely on convenience defaults):

- `deal_price='open'`
- `only_tradable=False`
- `forbid_all_trade_at_limit=True`
- realistic transaction costs
- `limit_threshold` aligned with the segment mix being tested

---

## 8. What's Skeletal / Not Yet Done

| Area | Current State |
|---|---|
| **Live trading** | Broker config is placeholder only (XTP). No order routing, no real-time feed. |
| **Portfolio optimization** | Basic mean-variance. `MultiFactorRiskModel.fit()` needs real factor extraction. `MarketImpactModel` is flat-rate only. |
| **Daily automated refresh** | `update_daily_data.py` exists but no scheduler is wired (Airflow stub was removed). Data ends at 2026-02-27. |
| **Strategy promotion** | No strategy has cleared the formal promotion gate yet. |
| **Theme strategy completion** | Only `small_cap` has partial real runs (universe search + some components). `st` and `flow_northbound` have not been run on real data. |
| **Model ensemble / hyperparameter tuning** | Listed as next steps in active research focus but not started. |

---

## 9. Active Research Focus (from project_state.md)

1. **Theme opportunity research** — validate `small_cap`, `st`, `flow_northbound` out-of-sample with searched universes and recipes
2. **Monitor corrected small_cap universe rerun** — use winning universes for component → recipe → event-driven stages
3. **Phase 4 preparation** — shortlist 10-15 orthogonal core factors from the 16 graduated + 20 strong-IC backup pool
4. **Staged PIT backend validation** — sandbox provider builds, review remaining raw anomalies, verify `D.features()` access before production publish
5. **Model comparison** — ML notebook on shortlisted factors vs. linear baseline
6. **Next layer** — hyperparameter tuning, ensembles, risk overlays

---

## 10. Environment & Tooling

- **Python**: 3.12.7 at `E:\量化系统\venv\Scripts\python.exe`
- **Key packages**: `pyqlib==0.9.7`, `cvxpy==1.7.5`, `pandas==2.3.3`, `numpy==2.2.6`, `lightgbm==4.6.0`, `xgboost==3.2.0`, `mlflow==3.10.0`, `scikit-learn==1.7.2`, `tushare==1.4.24`
- **Config**: `config.yaml` references `${TUSHARE_TOKEN}` from `.env`
- **MLflow**: `http://localhost:5000`, experiment `alpha_research_v1`
- **Shell**: bash (Git Bash on Windows) — use Unix syntax, `/dev/null` not `NUL`
- **Tests**: `python -m unittest tests.<path>` (not pytest)
- **Harnesses**: 9 smoke/integration harnesses under `tests/harnesses/`
- **Factor screening parity**: independent oracle under `workspace/scripts/validate_factor_screening_parity.py` — 111/111 passed on the broad 2024 window

---

## 11. Canonical Files to Read at Session Start

Per CLAUDE.md §1, read these in order for any non-trivial work:

1. [`project_state.md`](../project_state.md) — durable system memory (check "Last Updated" header)
2. [`CLAUDE.md`](../CLAUDE.md) — operating contract
3. [`src/system.md`](../src/system.md) — module architecture
4. [`data/data_dictionary.md`](../data/data_dictionary.md) — exhaustive column definitions
5. [`data/data_tracker.md`](../data/data_tracker.md) — data coverage and sync status

**When this snapshot disagrees with `project_state.md`, `project_state.md` wins.**
