# `data/` — Documentation Only in This Repo

This directory is the physical home of every raw and derived dataset
in the system on the local workstation. **None of the actual data is
committed to this Git repository** — the files here are large
(hundreds of GB), Tushare-licensed, and derivable from the pipeline.

What IS committed: the documentation files that describe the data
system so a reader of this repo can understand the architecture
without having the data.

## What you'll find in this directory ON DISK (local workstation)

```
data/
├── reference/                  trade calendar, stock_basic, namechange, ST history
├── market/                     OHLCV, valuation, indexes, moneyflow, northbound,
│                               margin, stk_limit, top_list/inst, block_trade,
│                               cyq_perf, suspension
├── fundamentals/               income, income_quarterly, balancesheet,
│                               cashflow, cashflow_quarterly, indicators
├── corporate/                  dividends, holder_number, stk_holdertrade
├── universe/                   index_weights (CSI300/500/1000), industry_sw2021
├── normalized/                 schema-clean canonical tables (rebuilt on demand)
├── pit_ledger/                 revision-aware PIT tables keyed by disclosure dates
├── qlib_builds/                staged Qlib provider builds (per build_id)
├── qlib_data/                  the published binary Qlib provider (read by research)
├── external/jq_pit_cache/      JoinQuant PIT mirror for local↔JQ bidirectional verify
├── raw_cache/                  upstream raw caches
├── quarantine/                 rows held back by validation
├── factor_registry/            formal factor catalog with grades + evidence
├── candidate_registry/         research candidates
├── signal_registry/            signal recipes (including theme recipes)
├── model_registry/             trained models
├── strategy_registry/          strategy candidates
├── hypothesis_registry/        pre-registered hypotheses (sealed design_hashes)
├── holdout_seals/              OOS seal manifests
├── hypothesis_cache_manifest/  manifest store for cache reuse across hypotheses
└── testing_ledger/             multiple-testing accounting
```

## What IS committed to Git (the documentation)

| File | Purpose |
|---|---|
| [data_dictionary.md](data_dictionary.md) | Every column in every raw dataset, with semantics, units, and source endpoint |
| [data_tracker.md](data_tracker.md) | Coverage, sync status, last-refreshed timestamps, PIT serving conventions |
| [factor_registry/README.md](factor_registry/README.md) | Schema and write pathway for the formal factor registry |
| [candidate_registry/README.md](candidate_registry/README.md) | Schema for research candidates |
| [signal_registry/README.md](signal_registry/README.md) | Schema for signal recipes |
| [model_registry/README.md](model_registry/README.md) | Schema for trained models |
| [strategy_registry/README.md](strategy_registry/README.md) | Schema for strategy candidates |
| [qlib_data/instruments/README.md](qlib_data/instruments/README.md) | Universe sidecars (all_stocks, ST, CSI300/500/1000) |
| [external/jq_pit_cache/README.md](external/jq_pit_cache/README.md) | JoinQuant PIT cache layout and refresh procedure |

For the end-to-end data flow, see [../docs/DATA_ARCHITECTURE.md](../docs/DATA_ARCHITECTURE.md).

For the rebuild runbook, see
[../src/data_infra/pipeline/RUNBOOK.md](../src/data_infra/pipeline/RUNBOOK.md).

For the rules that govern data operations (Tushare safety, mutation
discipline, rebuild policy), see
[../.agents/rules/data-operations.md](../.agents/rules/data-operations.md).

## Why the data is not in this repo

1. **Size.** The published Qlib provider alone is tens of GB; the full
   data tree is hundreds of GB.
2. **Licensing.** Tushare Pro data is subscription-licensed and cannot
   be redistributed.
3. **Derivability.** Everything except the raw Tushare pull is
   reproducible from the pipeline. If you have a Tushare token and run
   [../src/data_infra/pipeline/](../src/data_infra/pipeline/) in order
   ([init_market_data.py](../src/data_infra/pipeline/init_market_data.py)
   → [init_fundamentals_data.py](../src/data_infra/pipeline/init_fundamentals_data.py)
   → [init_factor_data.py](../src/data_infra/pipeline/init_factor_data.py)
   → [build_qlib_backend.py](../src/data_infra/pipeline/build_qlib_backend.py)),
   you can recreate the exact stack.

If you need the raw data, follow
[../src/data_infra/pipeline/RUNBOOK.md](../src/data_infra/pipeline/RUNBOOK.md).
