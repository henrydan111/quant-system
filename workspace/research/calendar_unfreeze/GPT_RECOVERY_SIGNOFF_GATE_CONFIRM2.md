# GPT 5.5 Pro — sign-off gate, take 2: the first-axis projection is gone

**Branch pushed:** `calendar-unfreeze` @ `41027c6`. **Narrow scope: your sign-off HOLD only** — the
population BLOCKER. Same question as last time: **is the contract sign-off gate open?**

Batteries: **143** — broker 9 / ledger 34 / coordinator 60 / promotion 40, each standalone.
`QUANT_RECOVERY_TEST_ROOT=/writable/non-E/path pytest tests/data_infra/test_recovery_*.py`

## Your finding was exact, and worse than it sounds

*"Complete request tuples are constructed, then discarded."* `_request_population_key` returned every
declared parameter and `assert_population_is_correct` did `k[0]` **on the very next line**. I computed
the fact and threw it away immediately. Sixth round of the same class, and the shortest distance yet
between having the truth and discarding it.

All four of your reproductions now refuse:

| Your probe | Now |
|---|---|
| `income_vip(period=20260331, report_type=999)` accepted (real recipe uses `2`/`3`) | `report_types` must be signed explicitly; `report_periods_x_types` is the Cartesian product; `report_type=999` is simply not in the signed request set |
| signed `000300.SH` accepted unsigned range `20990101..20990102` | `index_code_ranges` emits `{ts_code,start_date,end_date}` — the same code over a different range is a different request |
| 5,861 signed stocks accepted arbitrary 2099 `cyq_perf` ranges | `stock_repartition` → `stock_basic_ranges` → `{ts_code,start_date,end_date}` (the real call takes all three) |
| `report_periods` generated 73 quarter-ends vs 98 baseline indicator partitions | `bounds.periods` accepts an **explicit signed list**; a generated calendar cannot describe vendor-reported non-quarter periods |

## What the schema is now

- `_canon_request(params)` = **every** parameter, sorted — the identity. `request_set_sha256` hashes
  canonical parameter mappings, not member strings.
- Resolvers emit **complete requests**: `trade_cal_open_sessions`→`{trade_date}`;
  `stock_basic_codes`→`{ts_code}`; `stock_basic_ranges`/`index_code_ranges`→`{ts_code,start_date,end_date}`;
  `calendar_months`→`{month}`; `report_date_months`→`{report_date}`; `report_periods`→`{period}`;
  `report_periods_x_types`→`{period,report_type}`.
- `assert_population_is_correct`: **`asked == expected`**, whole requests both sides. `asked_primary` is
  gone. A probe pins that an extra `adj=qfq` on an otherwise-correct request refuses.
- **Reference pinning (your answer 2):** reference-derived axes resolve only at the exact bytes the
  contract signed (`bounds.reference_sha256` over `trade_cal`/`stock_basic`). A refreshed reference
  refuses until deliberately re-signed, so a listing change is a visible decision rather than silent
  drift or forced churn.
- The `partition` label is still checked for honesty against the unit's naming axis, never used as the key.
- MINOR folded: YAML no longer advertises the removed `years`; signer instructions now describe the
  complete-request schema, pinning, explicit period/report_type lists, and (your answer 3) that a resume
  keeps the **original full frozen plan** while the ledger selects pending — a smaller plan must never
  masquerade as a resume.

Your answers 3, 4, 5 are recorded as accepted; (5) — the first-axis projection — is what this closes.

## The question

**OPEN or HOLD for per-endpoint contract sign-off?** Sign-off = a human reads the pinned doc and fills
the YAML; no fetch, no adapters, no mutation. Specifically:

1. **Would a contract signed today survive without re-signing?** That has been your stated bar twice.
2. **Is `reference_sha256` the right pin**, or should it be the preflight survivor snapshot you
   suggested as the alternative? (I chose the sha because sign-off happens before any run exists, so
   there is no snapshot yet — tell me if that reasoning is wrong.)
3. **Are the eight resolvers the right decomposition** for the 32 endpoints — in particular per-stock
   statements (`{ts_code}` alone: the fetchers pass `period`/`ann_date` per call — should those be in
   the signed request, making it a Cartesian over periods?), and `report_rc` (`report_date_months`).
4. **Any remaining proxy in the population path**, or is the class closed *here* specifically?

## Explicitly NOT folded (gating FETCH, not sign-off — your split)

Replaceable contract loader + `doc_sha256` never re-checked at fetch; the frozen plan self-authenticates
(an orphan plan after a crash is consumed); matrix/response facts partially bound (endpoint ownership,
sparse-vs-dense, narrower-than-vendor natural key, `required_fields` never checked against responses);
`receipt_output` escapes `staging_data` via `../`; digest doc overclaims for mixed object columns;
test-root validated after creation. Standing: consumers undefended (pre-promotion); the lease proves the
ledger called the callable, not that the vendor was reached.

## Raw links (`calendar-unfreeze` @ `41027c6`)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/configs/recovery_endpoint_contracts.yaml
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_raw_recovery_coordinator.py

Return **OPEN / HOLD**, plus any BLOCKER/MAJOR/MINOR **within the population path** (file+line). If HOLD,
name the single thing that must change.
