# Data Architecture — End-to-End Guide

*Promoted from `Knowledge/data_layer_guide_2026-04-23.md` and refreshed
2026-05-26. Assumes zero prior knowledge of this project.*

This guide covers what the data layer is, where things live on disk,
how raw data becomes research-ready, and the invariants you must not
violate. It is the single document a reviewer should read after the
top-level [README.md](../README.md) and [src/system.md](../src/system.md).

---

## 1. What this project is (60-second version)

`量化系统` is a Chinese A-share (Shanghai + Shenzhen) quantitative
trading research system. It:

- **Pulls raw data** from Tushare Pro (a Chinese market-data vendor) into local Parquet files
- **Normalizes** that data (de-duplicate, handle revisions, align codes)
- **Builds a point-in-time (PIT) history** that respects "what could you actually have known on day T?"
- **Publishes a Qlib provider** — a binary columnar format Microsoft Qlib can query fast
- **Runs research** (factor screening, strategy backtests, ML models) against that provider
- **Records every run** in five typed registries with full evidence and audit trail

The whole stack is on one drive (`E:\` on the canonical workstation),
uses Python in a venv at `E:\量化系统\venv\`, and is dated: as of
2026-05-26, the trading calendar is intentionally frozen at 2026-02-27
and the live provider was rebuilt 2026-04-21.

---

## 2. The big picture — five data zones

Data flows through five zones, each in its own directory:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Tushare   │ ──► │  Raw cache   │ ──► │ Normalized  │ ──► │ PIT ledgers  │ ──► │    Qlib     │
│     API     │     │  data/...    │     │ data/       │     │ data/        │     │  provider   │
│             │     │              │     │ normalized/ │     │ pit_ledger/  │     │ data/       │
│             │     │              │     │             │     │              │     │ qlib_data/  │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘     └─────────────┘
  vendor-side       immutable           schema-clean        revision-aware        binary bins,
                    row-level           canonical tables    keyed by disclosure   Qlib queries
                    Parquet                                 dates
```

| Zone | Path | Human-readable? | Overwrite policy |
|---|---|---|---|
| Raw | `data/market/`, `data/fundamentals/`, `data/corporate/`, `data/reference/` | Yes (Parquet) | Append-only; never overwrite in place |
| Normalized | `data/normalized/<dataset>.parquet` | Yes | Overwritten on every rebuild |
| PIT ledger | `data/pit_ledger/<dataset>/<dataset>.parquet` | Yes | Overwritten on every rebuild |
| Staged builds | `data/qlib_builds/<build_id>/provider/` | Binary (Qlib bins) | Written fresh per build |
| Live published | `data/qlib_data/` | Binary (Qlib bins) | Atomically swapped from a staged build |

**Rule of thumb:** read-only access to `data/qlib_data/` via Qlib for
research. Everything else is maintained by the pipeline scripts under
[src/data_infra/pipeline/](../src/data_infra/pipeline/).

> The data itself is NOT in this Git repository. Only the documentation
> describing what lives where is committed. See the root
> [README.md](../README.md#what-this-repo-does-not-contain).

---

## 3. What's in each raw subdirectory

### `data/reference/` — Metadata (always loaded)
- **`stock_basic.parquet`** (5,805 rows) — every A-share that ever listed, including delisted/ST. Has `list_date`, `delist_date`, `industry`.
- **`trade_cal.parquet`** (4,410 rows) — the authoritative trading-day calendar. **Never assume business days = trading days.**
- **`namechange.parquet`** — historical stock name changes, including ST designation events.
- **`stock_st_daily.parquet`** — daily ST stock list (has a 2020-01-02 gap — use `instruments/st_stocks.txt` instead for backtests).

### `data/market/daily/YYYY/` — OHLCV + valuation (the backbone)
One Parquet per trading day. 2008-01-02 → 2026-02-27, 4,410 files, ~5,471 stocks on latest day. Columns: OHLCV, `pe_ttm`, `pb`, `total_mv`, `circ_mv`, `turnover_rate`, `adj_factor`, etc.

### `data/market/index/` — Benchmarks
CSI300 (`000300.SH`), CSI500 (`000905.SH`), CSI1000 (`000852.SH`), SSE Composite, STAR50, ChiNext, SZSE Composite. 2008–2026.

### `data/fundamentals/` — Quarterly statements
| Family | What |
|---|---|
| `income/` | Income statements (cumulative) |
| `income_quarterly/` | Single-quarter income (direct) |
| `balancesheet/` | Balance sheets |
| `cashflow/` / `cashflow_quarterly/` | Cash flow statements |
| `indicators/` | Vendor-reported derived metrics (ROE, ROA, YoY growth, etc.) |

Every row has `ann_date` (announcement date — **THE CRITICAL FIELD FOR PIT**) and `end_date` (fiscal period end).

### `data/corporate/` — Corporate actions
- `dividends/` — cash dividends, stock splits
- `holder_number/` — shareholder counts
- `stk_holdertrade/` — insider buy/sell disclosures (per-holder, per-event)

### `data/market/` — Phase 3 + alpha endpoints
| Sub | Coverage |
|---|---|
| `moneyflow/` | 2008–2026, capital-flow by order size |
| `northbound/` | 2017–2026, Stock Connect holdings |
| `margin/` | 2010–2026, margin trading balances |
| `stk_limit/` | 2008–2026, daily limit-up/limit-down prices |
| `top_list/` | 2008–2026, 龙虎榜 retail-view |
| `top_inst/` | 2008–2026, 龙虎榜 institutional detail |
| `block_trade/` | 2008–2026, 大宗交易 block trades |
| `cyq_perf/` | 2018–2026, 筹码分布 chip distribution |
| `suspension/` | Per `suspend_d` Tushare endpoint (P1-1 bootstrap script available) |

### `data/universe/` — Benchmarks & industry
- `index_weights/` — CSI300/500/1000 monthly constituents
- `industry_sw2021/` — Shenwan 2021 industry classifications (historical PIT membership landed 2026-04-27)

### `data/external/jq_pit_cache/` — JoinQuant PIT mirror
Bidirectional verification between local backtests and JoinQuant
deployment. Mirrors JoinQuant's PIT views for fields Tushare doesn't
expose (e.g. dynamic index membership) or computes differently (e.g.
`valuation.market_cap` ranking ties). See
[data/external/jq_pit_cache/README.md](../data/external/jq_pit_cache/README.md).

For exhaustive column-level documentation, see [data/data_dictionary.md](../data/data_dictionary.md). For
coverage + sync status, see [data/data_tracker.md](../data/data_tracker.md).

---

## 4. What PIT means and why it matters

**Point-in-Time** = "what did the market actually know on day T?" For
fundamentals this is THE central correctness property.

- **Wrong:** "Apple's 2024-Q1 revenue was $100B, so on 2024-04-01 my factor uses $100B."
- **Right:** "Apple announced 2024-Q1 revenue on 2024-05-02, so on any date before 2024-05-02 the factor must not see the $100B value."

The codebase enforces this via several layers:

1. **`ann_date` is the canonical visibility anchor.** Never align
   fundamentals on `end_date` (the fiscal period). For the 5 statement
   families (`income`, `income_quarterly`, `balancesheet`, `cashflow`,
   `cashflow_quarterly`), visibility is `max(ann_date, f_ann_date)`
   where `f_ann_date` is the corrected-announcement date if the filing
   was amended. The 4 event/indicator families (`indicators`,
   `dividends`, `forecast`, `holder_number`) anchor on `ann_date` only
   because the raw Tushare schemas for those endpoints do not carry
   `f_ann_date`.

2. **`strictly_next_open_trade_day()`** — a row disclosed on day T
   becomes visible on the NEXT open trading day (T+1 strictly). This
   is the "effective_date" in the PIT ledger. The invariant
   `effective_date > disclosure_date` is enforced by
   [tests/data_infra/test_pit_backend.py](../tests/data_infra/test_pit_backend.py).

3. **Deterministic tie-break** — when two revisions of the same
   `(stock, period)` exist with identical priority, the system uses
   `_src_file` + `_src_ordinal` columns injected during normalization
   to ensure the rebuild is reproducible across machines.

4. **Cumulative→quarterly late restatement** — when a prior quarter's
   cumulative value is restated AFTER the current quarter has already
   been disclosed, `derive_single_quarter_value` retroactively changes
   the derived current-quarter value at the restatement's effective
   date. This is intentional (use best-known state) but means
   research code that caches quarter values must invalidate on every
   ledger rebuild. See the worked example in
   [src/data_infra/pit_backend.py](../src/data_infra/pit_backend.py).

5. **Delist / IPO-lag guard** is enforced at the instruments sidecar
   layer ([data/qlib_data/instruments/all_stocks.txt](../data/qlib_data/instruments/)) via
   `provider_metadata.build_all_stocks_universe()`. Consumers of
   `D.features()` inherit the guard automatically. Direct PIT-ledger
   consumers MUST apply their own filter via
   `provider_metadata.stock_basic_bounds(ts_code)`.

If you write factor code, **wrap every `$field` reference in
`Ref(..., 1)`** in Qlib expressions — see the operator library at
[src/alpha_research/factor_library/operators.py](../src/alpha_research/factor_library/operators.py) for the pattern.
Enforcement: [tests/alpha_research/test_factor_library_pit_safety.py](../tests/alpha_research/test_factor_library_pit_safety.py).

---

## 5. The published Qlib provider — `data/qlib_data/`

This is what research code queries from Python. Current state
(2026-04-21 republish):

- **5,755 feature directories** (one per stock, e.g. `000001_sz/`)
- **~3,600 binary field files per stock** (`$close.day.bin`, `$pe_ttm.day.bin`, etc.)
- **Calendar sidecar:** `calendars/day.txt` (4,410 trading days)
- **Instruments sidecars:**
  - `instruments/all_stocks.txt` — universe with listing/delisting date ranges + 90-day IPO lag guard
  - `instruments/st_stocks.txt` — authoritative ST date ranges (2,070 entries)
  - `instruments/csi300.txt`, `csi500.txt`, `csi1000.txt` — benchmark constituents
- **Metadata:** `metadata/pit_audit/...` — per-build provenance

### Queryable field families

```python
import qlib
from qlib.data import D
qlib.init(provider_uri='data/qlib_data', kernels=1)

# OHLCV (always available)
D.features(['000001_SZ'], ['$close', '$open', '$high', '$low', '$vol', '$amount'],
           start_time='2024-01-01', end_time='2024-12-31')

# Fundamentals + valuation
['$pe_ttm', '$pb', '$total_mv', '$circ_mv', '$roe', '$eps']

# PIT-derived growth (cleanest for research)
['$pit_or_yoy', '$pit_op_yoy', '$pit_netprofit_yoy', '$pit_q_op_qoq']

# Phase 3 market-flow
['$net_mf_amount', '$buy_lg_amount']            # moneyflow
['$ratio']                                        # northbound
['$rzye', '$rzmre', '$rqye']                     # margin
['$up_limit', '$down_limit']                     # stk_limit

# Alpha endpoints — prefixed to avoid kline collisions (since 2026-04-20)
['$top_list__l_buy', '$top_list__net_rate', '$top_list__l_amount']
['$top_inst__net_buy', '$top_inst__buy_rate']
['$block_trade__price', '$block_trade__vol', '$block_trade__amount']
['$cyq_perf__winner_rate', '$cyq_perf__cost_50pct']

# Shareholder transactions (UNprefixed — custom aggregator)
['$holdertrade_net_vol', '$holdertrade_net_ratio', '$holdertrade_events']
```

---

## 6. Stock code format (the #1 silent bug)

**Tushare uses `000001.SZ` (dot). Qlib uses `000001_SZ` (underscore).**
Failing to convert returns 0 matches with no error.

```python
def tushare_to_qlib(code: str) -> str:
    return code.replace('.', '_')
```

Same for benchmarks — use `'000300_SH'`, never `'SH000300'`.

---

## 7. The five registries (what gets written when)

Every formal research run writes evidence into one of five typed
registries under `data/`. Each follows the same shape: `master.parquet`
+ `evidence.parquet` + `run_index.parquet` + `status_history.parquet`
+ `review.html`. See each registry's README for the exact schema.

| Registry | What it tracks | README |
|---|---|---|
| `factor_registry/` | Formal base + composite factors with grades | [factor_registry/README.md](../data/factor_registry/README.md) |
| `candidate_registry/` | Research candidates (factor, theme component) | [candidate_registry/README.md](../data/candidate_registry/README.md) |
| `signal_registry/` | Signal recipes (theme recipes live here, not candidate_registry) | [signal_registry/README.md](../data/signal_registry/README.md) |
| `model_registry/` | Trained models | [model_registry/README.md](../data/model_registry/README.md) |
| `strategy_registry/` | Strategy candidates | [strategy_registry/README.md](../data/strategy_registry/README.md) |

Current factor registry (as of 2026-04-27): 171 base + composite
factors. Post-PIT-safety-fix grade distribution: 1A / 37B / 75C / 36D
across 149 base catalog factors. The 17 baseline A-grade factors
that lost A status post-fix had been inflated by same-day-leakage; the
sole surviving A-grade is `liq_vol_cv_20d`. See
[project_state.md](../project_state.md) for the full history.

---

## 8. How to rebuild if something breaks

```bash
# Full rebuild (12+ hours — only for schema changes or full backfill)
venv/Scripts/python.exe src/data_infra/pipeline/build_qlib_backend.py \
    --mode all --stage full --build-id prod_rebuild_YYYYMMDD

# Daily incremental update (when trade calendar advances)
venv/Scripts/python.exe src/data_infra/pipeline/update_daily_data.py

# Sanity check the live provider
venv/Scripts/python.exe scripts/run_daily_qa.py                    # 4-in-1 suite
venv/Scripts/python.exe tests/harnesses/qlib_smoke.py              # Qlib smoke
venv/Scripts/python.exe scripts/audit_qlib.py --sample-size 50     # Full audit
```

A full rebuild stages the output under `data/qlib_builds/<build_id>/`
first, then atomically swaps `data/qlib_data/` into a timestamped
backup. `publish()` hard-fails with a `BuildGateError` if the staged
provider and the target `data/qlib_data/` live on different volumes
(`os.replace()` is only atomic within a single drive). Pre-rebuild,
back up the periodic PIT ledgers — they are overwritten in-place.

Full operational runbook: [src/data_infra/pipeline/RUNBOOK.md](../src/data_infra/pipeline/RUNBOOK.md).

---

## 9. Hard invariants you must not break

These have all silently burned the project at least once. Each is
backed by a named regression test.

1. **Never parallelize Tushare fetchers.** Account rate limits make it
   counterproductive; increase `base_sleep=1.5`, don't reduce it.
2. **Always convert `ts_code`** (dot ↔ underscore) before joining
   Tushare data with Qlib output.
3. **Trading-day awareness** — use `trade_cal.parquet`, not business-day
   arithmetic.
4. **PIT on fundamentals** — align on `ann_date`, never `end_date`;
   apply `shift(1)` after `merge_asof`.
5. **Factor library PIT-safety** — every `$field` wrapped in
   `Ref(..., 1)`. Enforced by
   [tests/alpha_research/test_factor_library_pit_safety.py](../tests/alpha_research/test_factor_library_pit_safety.py).
6. **Event-like daily namespacing** — `top_list`, `top_inst`,
   `block_trade`, `cyq_perf` payload columns are written as
   `$<dataset>__<col>` (e.g., `$block_trade__amount`).
   `stk_holdertrade` aggregates stay unprefixed. Enforced by
   [tests/data_infra/test_event_like_daily_namespace.py](../tests/data_infra/test_event_like_daily_namespace.py).
7. **Delist / IPO-lag guard** lives in the `all_stocks.txt` sidecar. If
   you read PIT ledgers directly (bypassing `D.features()`), you MUST
   apply your own guard via `provider_metadata.stock_basic_bounds()`.
   Enforced by
   [tests/data_infra/test_provider_boundary.py](../tests/data_infra/test_provider_boundary.py).
8. **Survivorship** — historical universes include delisted names. Do
   NOT filter to currently-listed stocks only.
9. **Stamp tax / commission / 过户费** all flow through
   `exchange.compute_*_cost_breakdown()` as the single source of truth.
   `CostConfig()` defaults are JoinQuant-aligned;
   `CostConfig.realistic_china()` is the explicit Chinese-exchange
   preset with the 2023-08-28 stamp-tax cut.
10. **Limit prices use round-half-up**, not banker's rounding. Enforced
    by
    [tests/backtest_engine/test_exchange_limits.py](../tests/backtest_engine/test_exchange_limits.py).

Full list and rationale: [CLAUDE.md §3](../CLAUDE.md).

---

## 10. The 5 canonical truth files

When something surprises you, trust these files (in this order) over
what you remember:

1. **[project_state.md](../project_state.md)** — durable system memory; check "Last Updated" for most recent work
2. **[CLAUDE.md](../CLAUDE.md)** — operating contract for agents working on this repo
3. **[src/system.md](../src/system.md)** — top-level src architecture
4. **[data/data_dictionary.md](../data/data_dictionary.md)** — every column in every raw dataset
5. **[data/data_tracker.md](../data/data_tracker.md)** — coverage and sync status

If two of these disagree, `project_state.md` wins — it's the most
recent source of truth.

---

## 11. Current state snapshot (as of 2026-05-26)

- Live provider: `data/qlib_data/` (published 2026-04-21, rebuilt from `20260420_143526` staged build)
- Trading calendar: frozen at 2026-02-27 (intentionally, per `scripts/run_daily_qa.py`)
- Factor registry: 171 factors total (149 base post-fix grades 1A/37B/75C/36D + composites)
- Engine: verified against JoinQuant to within an irreducible cross-stack noise floor; see project_state.md update notes 2026-05-21 through 2026-05-22 for the full attribution
- Daily QA passes: all 4 checks + qlib_smoke
- Health invariant: `$close/$amount/$vol` integrity verified (no collision bug)
- Open debt: see `## Known Issues` in [project_state.md](../project_state.md)

---

That's the whole picture. Next time you need to touch data, re-read
[data/data_tracker.md](../data/data_tracker.md) §7 (Qlib data) and §9 (staged
serving layers), and you'll know what you're working with.
