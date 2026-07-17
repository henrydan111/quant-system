# GPT 5.5 Pro — confirm ONE thing: is the contract sign-off gate now open?

**Branch pushed:** `calendar-unfreeze` @ `72c6535`. **Narrow scope: re-review #10's BLOCKER-1 only** — the
population schema, which you identified as *the single sign-off-specific blocker* ("signing now would
require re-signing after the schema is corrected").

**This is not a full re-review.** Your other #10 findings are NOT folded and I am not claiming they are;
they gate **fetch**, not signing, per your own split. They are listed at the bottom so nothing looks
quietly closed.

Batteries: **136** — broker 9 / ledger 34 / coordinator 53 / promotion 40, each standalone.
`QUANT_RECOVERY_TEST_ROOT=/writable/non-E/path pytest tests/data_infra/test_recovery_*.py`

## What you found, and what changed

You reproduced: **all A01 legs using a Sunday passed** while the contract claimed "trade_cal open
sessions"; `period_report_type` ignored `report_type`; `index_range` ignored its range bounds;
`request_population.source` was unenforced prose; and `year` for `suspend_d` is not an official vendor
input. Your diagnosis — *"coverage proves agreement, not correctness"* — was exactly right, and it is the
proxy-for-the-fact class again: leg-agreement was my proxy; the real open-session set was the fact, and
it was reachable the whole time (`data/reference/trade_cal.parquet` **survived** the incident).

The signed contract now declares an **executable** population instead of describing one:

```yaml
request_population:
  resolver: trade_cal_open_sessions | stock_basic_codes | calendar_months | report_periods | index_codes
  bounds:   {start, end, exchange} | {list_status} | {codes: [...]}
  expected_set_sha256: <sha256 of the sorted resolved set>
```

- `resolve_population` **runs** the resolver against the real reference data. `_resolve_open_sessions`
  reads the surviving `trade_cal`: 20260704/05 are a genuine weekend and are simply **not in the set**.
- `expected_set_sha256` pins the population the human actually signed. Widening the bounds without
  re-signing refuses; if the reference data moves, the contract no longer describes it and must be
  re-signed.
- The declared resolver must match the matrix row's `query_mode` (a contract resolving MONTHS under a
  trading-day row is a coverage lie); an empty resolution refuses.
- `assert_population_is_correct` compares the frozen plan to the resolved set **exactly**: a MISSING item
  is an incomplete recovery; an EXTRA item is a request the signed population does not contain (a
  weekend, a delisted code). Merge legs must share **one** snapshot — same resolver AND bounds AND hash.
- `_UNIT_PARAM` (one param per unit) → `_POPULATION_PARAMS`, the **complete tuple**: `period_report_type`
  needs `period` AND `report_type`; `index_range` needs `ts_code` AND `start_date` AND `end_date`. A
  request missing any determining parameter refuses instead of silently keying on a narrower one.
- **The `year` fiction is deleted** (`72c6535`). Verified against pinned doc 214: `suspend_d`'s inputs are
  `ts_code`/`trade_date`/`start_date`/`end_date`/`suspend_type` — no `year`. A10a was its only user; the
  yearly `suspension_<yr>.parquet` files are an **output partitioning** (already `consolidation_group`),
  not a request unit. A10a is now `per_open_trade_date`, and the `year` unit + `years` resolver are
  **removed** rather than documented — a unit no endpoint can legitimately request is dead surface a
  future reviewer might sign against.

Probes: the Sunday plan (every leg agreeing, still wrong), a missing session, a drifted/unsigned set
hash, prose-instead-of-resolver (including the old `unit`/`source` schema), an empty population, both
multi-param key shapes, and the resolvers against the real calendar.

**Disclosure:** mid-fold I broke the file with a span-slice (`_population_spec_errors` ..
`assert_plan_matches_contracts`) that silently swallowed the resolvers and merge-coverage between them. I
caught it, reverted, and redid it with exact anchors plus a post-edit assertion that every function
survives. Flagging it because a silent deletion is exactly the kind of thing a diff review should catch.

## The only question I'm asking

**Is the contract sign-off gate now open?** Sign-off = a human reads the pinned Tushare doc and fills the
YAML; no fetch, no adapters, no mutation. Specifically:

1. **Is the population schema now sufficient to sign against** — i.e. would a contract signed today
   survive the remaining work without needing to be re-signed? That was your stated reason for holding
   the gate.
2. **Is the executable resolver the right shape?** Are `bounds` expressive enough for the real legs
   (per-stock over `stock_basic` incl. delisted; `index_codes` as an explicit signed list; report periods
   for the statement families)? Is pinning `expected_set_sha256` against *live* reference data right, or
   does it make contracts too brittle to sign (every calendar refresh invalidates them)?
3. **Is exact-set equality the right rule**, or is there a legitimate case for a plan that is a strict
   subset of the signed population (a resumed/partial recovery)?
4. **Did removing `year` rather than fixing it lose anything?** Is `per_open_trade_date` right for A10a
   given the yearly output files?
5. **Any remaining proxy in the population path specifically** — does anything here still stand in for a
   fact it doesn't establish?

## Explicitly NOT folded (gating FETCH, not sign-off — your split)

- **BLOCKER** contract loader is publicly replaceable (`ledger.contract_loader`), and
  `_assert_contract_binding` never re-checks `doc_sha256` — editing the referenced doc doesn't stop a fetch.
- **BLOCKER** the frozen plan self-authenticates: `_plan` checks only its embedded hash, so a rewritten
  plan with a recomputed hash is accepted, and a crash between writing the plan and appending
  `plan_frozen` leaves an orphan plan that is still consumed — inside the stated crash threat model.
- **BLOCKER** matrix/response facts partially bound (endpoint ownership, sparse-vs-dense, narrower-than-
  vendor natural key, and signed `required_fields` never checked against fetched responses).
- **MAJOR** `receipt_output` can escape `staging_data` via `../`.
- **MINOR** digest doc overclaims physical losslessness for mixed object columns; test-root validated
  after creation.

Standing and unchanged: concurrent CONSUMERS undefended (pre-promotion gate); the lease proves the ledger
called the callable, not that the vendor was reached.

## Raw links (`calendar-unfreeze` @ `72c6535`)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/configs/recovery_endpoint_contracts.yaml
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_raw_recovery_coordinator.py
- Plan (§5a threat model): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md

Return: **OPEN / HOLD** for per-endpoint contract sign-off, plus any BLOCKER/MAJOR/MINOR **within the
population path** (file+line). If HOLD, name the single thing that must change.
