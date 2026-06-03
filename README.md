# 量化系统 — Chinese A-Share Quantitative Research System

A point-in-time, end-to-end research stack for Shanghai + Shenzhen A-shares.
Tushare Pro ingestion → normalized Parquet → PIT ledger → Qlib provider →
factor library, vectorized + event-driven backtesters, MLflow tracking,
and a DAG-based research orchestrator with a hypothesis registry.

This repository is the **system** — the code, tests, rules, schemas, and
documentation that define how data flows in and research flows out. The
raw datasets, the binary Qlib provider, and per-run artifacts are
intentionally excluded; see [What this repo does NOT contain](#what-this-repo-does-not-contain).

> **Status snapshot (2026-05-26):** Live Qlib provider rebuilt 2026-04-21.
> Trading calendar frozen at 2026-02-27 (intentional, while the system
> is under active development). Factor registry has 177 graded factors
> (post-PIT-safety fix: 1A / 37B / 75C / 36D base + composites; +6 Round-6
> sealed-OOS winners onboarded 2026-06-02). Engine
> verified against JoinQuant to within an irreducible cross-stack noise
> floor (see [project_state.md](project_state.md) latest entries).

---

## What this is, in one paragraph

`量化系统` is a Chinese A-share quantitative trading research system built
around six fixed modules. It pulls raw data from Tushare Pro into local
Parquet, normalizes and de-duplicates it, builds a **point-in-time (PIT)
history** that respects "what could you actually have known on day T?",
publishes a Microsoft Qlib provider in binary columnar form for fast
queries, and runs factor research / strategy backtests / ML training
against that provider. Every output flows into one of five typed
registries (factor, candidate, signal, model, strategy), each with a
full audit trail of evidence, runs, and status history. A DAG-based
orchestrator coordinates formal research with five human-approval gates
and a pre-registered hypothesis lifecycle (IS → seal → OOS).

---

## Six-module architecture

| Module | Responsibility |
|---|---|
| [src/data_infra/](src/data_infra/) | Tushare ingestion, Parquet storage, normalization, PIT ledger, Qlib backend builder, verification |
| [src/alpha_research/](src/alpha_research/) | Factor library (177 named factors: 153 base + 4 industry-relative + 20 Layer-2 composites), factor evaluation toolkit, theme strategy framework, model zoo, MLflow tracker, registries |
| [src/backtest_engine/](src/backtest_engine/) | `VectorizedBacktester` (Qlib wrapper for fast screening) and `EventDrivenBacktester` (realistic A-share simulator with T+1, multi-tier limits, corporate actions, JoinQuant-parity defaults) |
| [src/portfolio_risk/](src/portfolio_risk/) | `PortfolioOptimizer` (cvxpy), cost models, risk models |
| [src/result_analysis/](src/result_analysis/) | Canonical metrics, `BacktestReport`, plotters |
| [src/research_orchestrator/](src/research_orchestrator/) | DAG-based workflow scheduler, 7 built-in profiles, 5 typed registries, hypothesis lifecycle, seal-aware OOS runner |

Full architecture map: [src/system.md](src/system.md)

---

## Where to read next

The repository is documentation-first. Different readers will want different entry points.

| Goal | File |
|---|---|
| **System overview, fastest path in** | this README + [src/system.md](src/system.md) |
| **End-to-end data flow** (Tushare → raw → PIT → Qlib → consumers) | [docs/DATA_ARCHITECTURE.md](docs/DATA_ARCHITECTURE.md) |
| **What data is available** (datasets, coverage, sync status) | [data/data_tracker.md](data/data_tracker.md) |
| **Every column in every raw dataset** | [data/data_dictionary.md](data/data_dictionary.md) |
| **Operating contract for AI agents** | [CLAUDE.md](CLAUDE.md) (Claude) / [AGENTS.md](AGENTS.md) (Codex) |
| **Hard invariants and silent failure modes** | [CLAUDE.md §3](CLAUDE.md) — the list of bugs the project has burned on |
| **Current durable system memory** | [project_state.md](project_state.md) — source of truth, check "Last Updated" |
| **Pipeline operational runbook** | [src/data_infra/pipeline/RUNBOOK.md](src/data_infra/pipeline/RUNBOOK.md) |
| **Factor library invariants** | [src/alpha_research/AGENTS.md](src/alpha_research/AGENTS.md) |
| **Backtester invariants** | [src/backtest_engine/AGENTS.md](src/backtest_engine/AGENTS.md) |
| **Research workflow (gated lifecycle, hypothesis CLI)** | [.agents/rules/research-integrity.md](.agents/rules/research-integrity.md) §10 |
| **Data operations rules** (Tushare safety, rebuild discipline) | [.agents/rules/data-operations.md](.agents/rules/data-operations.md) |
| **Signal + backtest pipeline rules** (four-layer pipeline, banned anti-patterns) | [.agents/rules/signal-backtesting.md](.agents/rules/signal-backtesting.md) |
| **Development practices** (logging, naming, module boundaries) | [.agents/rules/development-practices.md](.agents/rules/development-practices.md) |

For each registry's schema and write pathway, see the README inside
that directory:
[factor_registry](data/factor_registry/README.md),
[candidate_registry](data/candidate_registry/README.md),
[signal_registry](data/signal_registry/README.md),
[model_registry](data/model_registry/README.md),
[strategy_registry](data/strategy_registry/README.md).

---

## How a typical research flow works

```
1. Pre-register a hypothesis     workspace/scripts/hypothesis_cli.py register --hypothesis-file ...
                                  → writes to data/hypothesis_registry/ with a sealed design_hash

2. Plan or run the DAG           workspace/scripts/research_orchestrator_cli.py plan|run --request-file ...
                                  → 7 built-in profiles incl. hypothesis_validation
                                  → DAG runs IS leg, pauses at gate_concern_scoring

3. Human gate review             Human edits gate_concern_scores.json, runs:
                                  workspace/scripts/research_orchestrator_cli.py resume --run-dir ...
                                  → second pause at gate_review for approve/reject/quarantine

4. OOS execution (seal-aware)    On approve, OOS leg runs ONCE against the sealed holdout
                                  → sealed_backtest_runner enforces single-use semantics

5. Publish to registry           registry_publish step writes evidence/master/run_index/status_history
                                  → review.html regenerated for the affected registry
```

The seven built-in profiles live in [src/research_orchestrator/profiles.py](src/research_orchestrator/profiles.py):
`factor_screening`, `theme_strategy`, `event_driven_signal_research`,
`ml_signal_model_research`, `strategy_improvement`, `benchmark_audit`,
`hypothesis_validation` (the latter runs a fully-prescribed recipe
verbatim with no auto-search).

---

## Hard invariants you must not break

These are silent-failure bugs the project has already burned on. Tests
enforce each one. See [CLAUDE.md §3](CLAUDE.md) for the full list and
[tests/](tests/) for the regression coverage. A non-exhaustive sample:

- **Tushare uses `000001.SZ`, Qlib uses `000001_SZ`.** Wrong format
  silently returns 0 matches with no error. Convert with
  `ts_code.replace('.', '_')` before any join.
- **PIT visibility for fundamentals** — always align on `ann_date`, never
  `end_date`; apply `shift(1)` after `merge_asof`; `effective_date >
  disclosure_date` STRICTLY via `strictly_next_open_trade_day()`.
- **Factor library PIT-safety** — every `$field` reference inside every
  Layer 1 operator must be wrapped in `Ref(..., 1)`. Enforced by
  [tests/alpha_research/test_factor_library_pit_safety.py](tests/alpha_research/test_factor_library_pit_safety.py).
- **Delist / IPO-lag guard** lives at the instruments sidecar layer
  ([data/qlib_data/instruments/all_stocks.txt](data/qlib_data/instruments/)).
  Direct PIT-ledger consumers MUST apply their own guard via
  `provider_metadata.stock_basic_bounds()`.
- **Event-like daily endpoint namespacing** — `top_list`, `top_inst`,
  `block_trade`, `cyq_perf` payload columns are written under
  `{dataset}__{column}.day.bin` to prevent collision with canonical
  `$close/$amount/$vol`. Enforced by
  [tests/data_infra/test_event_like_daily_namespace.py](tests/data_infra/test_event_like_daily_namespace.py).
- **Survivorship** — historical universes include delisted names.
  Never filter to currently-listed stocks only.
- **Never parallelize Tushare fetchers** — account-level rate limits
  make it counterproductive; raise `base_sleep`, never lower it.

---

## What is in this repo

```
├── README.md                       this file
├── CLAUDE.md                       operating contract — Claude Code
├── AGENTS.md                       operating contract — Codex
├── project_state.md                durable system memory (source of truth)
├── config.yaml                     paths, risk limits, MLflow URI
├── requirements.txt                Python deps (pinned)
├── pytest.ini
├── .env.example                    sanitized credentials template
├── .gitignore
│
├── .agents/rules/                  deep-dive rule files referenced from CLAUDE.md
│   ├── data-operations.md
│   ├── research-integrity.md
│   ├── signal-backtesting.md
│   └── development-practices.md
│
├── docs/                           curated entry-point documentation
│   └── DATA_ARCHITECTURE.md        end-to-end data flow + invariants
│
├── src/                            production code, six modules
│   ├── system.md                   top-level architecture
│   ├── data_infra/
│   ├── alpha_research/
│   ├── backtest_engine/
│   ├── portfolio_risk/
│   ├── result_analysis/
│   └── research_orchestrator/
│
├── tests/                          full pytest suite (incl. invariant regressions)
│   ├── data_infra/
│   ├── alpha_research/
│   ├── backtest_engine/
│   ├── portfolio_risk/
│   ├── research_orchestrator/
│   ├── result_analysis/
│   └── harnesses/
│
├── scripts/                        bootstrap and maintenance utilities
│   ├── run_daily_qa.py
│   ├── audit_qlib.py
│   ├── verify_phase2.py
│   ├── fetch_suspend_d_historical.py
│   ├── refresh_namechange.py
│   ├── refresh_jq_pit_cache_manifest.py
│   └── fetch_new_alpha_endpoints.py
│
├── workspace/                      research scratch space (structure + scripts only)
│   ├── README.md
│   ├── AGENTS.md
│   ├── scripts/                    research_orchestrator_cli.py, hypothesis_cli.py, ...
│   └── configs/
│
├── Knowledge/                      project memos and the source data-layer guide
│   ├── data_layer_guide_2026-04-23.md
│   ├── system_overview_2026-04-10.md
│   └── research_plan_2026-05-19_next_3_to_6_months.md
│
└── data/                           DOCUMENTATION ONLY in this repo
    ├── README.md
    ├── data_dictionary.md          every column in every raw dataset
    ├── data_tracker.md             coverage, sync status, PIT conventions
    ├── factor_registry/README.md
    ├── candidate_registry/README.md
    ├── signal_registry/README.md
    ├── model_registry/README.md
    ├── strategy_registry/README.md
    ├── qlib_data/instruments/README.md
    └── external/jq_pit_cache/README.md
```

## What this repo does NOT contain

By design, the following are excluded via [.gitignore](.gitignore) and
will not appear on GitHub:

- **Raw datasets** under `data/market/`, `data/fundamentals/`,
  `data/corporate/`, `data/reference/`, `data/normalized/`,
  `data/pit_ledger/`, `data/universe/` — these are large Parquet files
  and contain Tushare-licensed content
- **Binary Qlib provider** `data/qlib_data/` — derivable from the raw
  data via the pipeline scripts; only the instruments sidecar README is committed
- **Registry runtime files** (master/evidence/run_index/status_history
  parquet/csv/html for each of the five registries) — only schemas (in
  each registry's README) are committed
- **MLflow runs** under `mlruns/` and `workspace/mlruns/`
- **Logs** under `logs/`
- **Research outputs** under `workspace/outputs/` and
  `workspace/research/**/outputs/`
- **Virtual environment** `venv/`
- **Secrets** `.env`, tokens, keys
- **JoinQuant / 果仁 backtest archives** (`果仁回测明细/`, `聚宽回测明细/`)
- **Factor Catalog/** large reference data

If you need the raw data, you'll need a Tushare Pro subscription and
must run the pipeline yourself. See
[src/data_infra/pipeline/RUNBOOK.md](src/data_infra/pipeline/RUNBOOK.md).

---

## Quick start (read-only inspection)

You can browse and run tests without any of the excluded data.

```bash
# 1. Clone
git clone <repo-url> 量化系统 && cd 量化系统

# 2. Python env (Windows shown; Linux/Mac analogous)
python -m venv venv
venv/Scripts/pip install -r requirements.txt

# 3. Copy the credentials template (leave token blank for read-only use)
cp .env.example .env

# 4. Browse the documentation
#    - Start at this README
#    - Then src/system.md
#    - Then docs/DATA_ARCHITECTURE.md
#    - Then CLAUDE.md §3 (hard invariants)

# 5. Run the test suite (tests that don't need live data will pass;
#    tests that need a Qlib provider will skip or fail predictably)
venv/Scripts/python -m pytest tests/ -q
```

To rebuild the data layer end-to-end (requires Tushare token), follow
[src/data_infra/pipeline/RUNBOOK.md](src/data_infra/pipeline/RUNBOOK.md).

---

## Cross-review note

This repo is structured for an external cross-review pass (e.g. by
GPT-5.5 Pro). A reviewer who reads, in order:

1. This README
2. [src/system.md](src/system.md)
3. [docs/DATA_ARCHITECTURE.md](docs/DATA_ARCHITECTURE.md)
4. [CLAUDE.md](CLAUDE.md) (especially §3 hard invariants)
5. [.agents/rules/research-integrity.md](.agents/rules/research-integrity.md)
6. [data/data_tracker.md](data/data_tracker.md)
7. The `AGENTS.md` files inside `src/data_infra/`, `src/alpha_research/`,
   `src/backtest_engine/`

...has the complete picture of how data flows in, what invariants
protect it, what research workflow runs on top of it, what evidence
each registry retains, and which tests prove each load-bearing rule.

---

## License

This project is provided as-is for research and reference. Add a
license file (`LICENSE`) before publishing if you have a specific
license in mind.

---

## Acknowledgments

Built on top of [Microsoft Qlib](https://github.com/microsoft/qlib),
[Tushare Pro](https://tushare.pro/), [MLflow](https://mlflow.org/),
and [cvxpy](https://www.cvxpy.org/).
