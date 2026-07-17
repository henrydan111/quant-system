# GPT 5.5 Pro — sign-off gate, take 3: endpoint-aware contracts + report_rc's real request

**Branch pushed:** `calendar-unfreeze` @ `5a02891`. **Narrow scope: your sign-off HOLD #2 only.** Same
question: **is the contract sign-off gate open?**

Batteries: **149** — broker 9 / ledger 34 / coordinator 66 / promotion 40, each standalone.
`QUANT_RECOVERY_TEST_ROOT=/writable/non-E/path pytest tests/data_infra/test_recovery_*.py`

## You found my class in the exact corner I asked you to check

I flagged `report_rc` because I was unsure of it. It was wrong in precisely the way everything else has
been: `_resolve_report_date_months` emitted `{"report_date": "202607"}`, while the pinned doc's
`report_date` is an **exact report date** and the real recipe is
`report_rc(start_date=YYYYMM01, end_date=<month end>)` (`fetch_bucket_a.py`). **The monthly partition
label was standing in for the vendor request.** Seventh instance, same substitution.

| Your finding | Fix |
|---|---|
| `report_rc` signs `{report_date: YYYYMM}`; real recipe is a monthly RANGE | `report_rc_month_ranges` emits `{start_date,end_date}` per calendar month (real month ends via `calendar.monthrange` — Feb → 28th/29th). `report_date` is no longer a request parameter at all. |
| the monthly label stands in for the request | the label is now **derived** from the request, not read off it: `_UNIT_LABEL_PARAM` → `_UNIT_LABEL_FROM_REQUEST` (per-unit derivers; report_rc's label = `start_date[:6]`). A label is not always a parameter, so deriving it is the only honest way to check one. |
| **`contract_errors` accepts any known resolver** — a valid `daily` contract using `calendar_months` returned ZERO errors; caught only once an adapter supplied a plan, too late for a human signing | `endpoint_expected_resolvers(endpoint)` derives the admissible resolver(s) from that endpoint's own matrix rows; a foreign one refuses **at sign-off** ("would bind the wrong request recipe"). `daily`→`trade_cal_open_sessions`, `report_rc`→`report_rc_month_ranges`, `cyq_perf`→`stock_basic_ranges`, `income_vip`→`report_periods_x_types`. |
| **MAJOR** `assert_plan_matches_contracts([], {})` and `freeze_request_plan(..., [], {})` both succeed; an omitted family is invisible | a plan must **declare its scope**. `assert_plan_scope_is_complete(plan, declared_families)` refuses an empty plan, an absent scope, a declared family with no requests, requests outside the scope, a family the matrix doesn't own, and a declared family missing a source leg. `freeze_request_plan` requires `declared_families`; the comparator refuses an empty plan outright. Nothing can verify a request that was never planned — only a declaration makes absence detectable. |

Your answers accepted and recorded: **per-stock `{ts_code}` is correct** — you verified against the
actual callers (they pass only `ts_code` and repartition locally), so no period Cartesian; my worry was
unfounded. **`reference_sha256`** is the right sign-off-time pin — *"a later preflight snapshot cannot
retroactively define what was signed."* If adapters later adopt announcement windows, those range params
must be signed.

## The question

**OPEN or HOLD for per-endpoint contract sign-off?** Sign-off = a human reads the pinned doc and fills
the YAML; no fetch, no adapters, no mutation.

1. **Would a contract signed today survive without re-signing?** Your bar, three times now.
2. **Is every endpoint's resolver now its real recipe?** I fixed `report_rc` because you named it. The
   other 31 I mapped from the matrix's `query_mode`, not from reading each fetcher — which is exactly
   how `report_rc` got it wrong. The ones I'd most expect to be wrong the same way: `index_daily`
   (per-index range — bounds signed as `codes` + one shared range: is a per-code range right?),
   `suspend_d` (I set both its families to `per_open_trade_date`; the doc also allows
   `start_date`/`end_date` — is per-session the real recipe or did I just move the fiction?),
   `margin_detail`/`hk_hold`/`moneyflow` (per-date, but do the live fetchers pass anything else?),
   `broker_recommend` (`per_month` → `calendar_months` → `{month}` — is `month` even its parameter?).
3. **Is `declared_families` the right scope unit**, or should the declaration be the request count / a
   signed plan manifest?
4. **Any remaining proxy in the population path**, or is the class closed *here*?

## Explicitly NOT folded (gating FETCH, not sign-off — your split)

Replaceable contract loader + `doc_sha256` never re-checked at fetch; the frozen plan self-authenticates
(orphan plan after a crash consumed); matrix/response facts partially bound (response-level endpoint
ownership, sparse-vs-dense, narrower-than-vendor natural key, `required_fields` never checked against
responses); `receipt_output` escapes `staging_data` via `../`; digest doc overclaims for mixed object
columns; test-root validated after creation. Standing: consumers undefended (pre-promotion); the lease
proves the ledger called the callable, not that the vendor was reached.

## Raw links (`calendar-unfreeze` @ `5a02891`)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/configs/recovery_endpoint_contracts.yaml
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_raw_recovery_coordinator.py
- The live fetchers the recipes must match: .../src/data_infra/fetchers/__init__.py ·
  .../src/data_infra/pipeline/init_market_data.py · .../scripts/fetch_bucket_a.py ·
  .../scripts/fetch_quarterly_statements.py · .../scripts/fetch_new_alpha_endpoints.py

Return **OPEN / HOLD**, plus any BLOCKER/MAJOR/MINOR **within the population path** (file+line). If HOLD,
name the single thing that must change.
