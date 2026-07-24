# Signed-contract defects exposed by the live recovery fetch (2026-07-23)

Three defect classes, all found by **fetching real data** — none was visible at contract sign-off,
because sign-off could verify a field's *presence in the doc* but not whether it is *populated in
practice*. Each is recorded with the measurement that proves it and a candidate fix tested against the
captured responses.

Status: the affected families are **excluded from run `recover03`**; the amendment is a governed action
(it changes `contract_sha256` → the plan hash → a NEW run) and has not been made.

---

## Class 1 — a NULLABLE field in the natural key

`ann_date`/`record_date`/`ex_date`/`pay_date` and `end_date` are legitimately empty for records in a
proposal stage. A natural key containing them can never hold, so the ledger refuses every page.

### `corporate/dividends` — 100% failure (83/83 before it was stopped)

Signed: `[ts_code, ann_date, end_date, record_date, ex_date, pay_date, div_proc]`

Measured, one representative response (29 rows):

| `div_proc` | rows | `record_date` null |
|---|---|---|
| 实施 (implemented) | 4 | 0 |
| 股东大会通过 (approved) | 9 | 9 |
| 预案 (proposal) | 16 | 16 |

Only an **implemented** dividend has a record/ex/pay date. Across 138 captured responses / 4,034 rows,
`ann_date` is null in 136.

### `corporate/repurchase` — 100% failure (17/17)

Signed: `[ts_code, ann_date, end_date, proc]`. `end_date` (截止日期) is null for 513/2000 rows in the
first response — the `proc='预案'` ones. Doc `124_股票回购.md` lists `end_date` as an output field, not
a guaranteed-populated one.

### Candidate fix — tested, and no field combination works

Every field-only candidate still leaves duplicates:

```
dividend    [ts_code, end_date, ann_date, div_proc]              nulls(ann_date)=136, dup rows=56
            [ts_code, end_date, div_proc]                        dup rows=62
            [+ stk_div, cash_div_tax]                            nulls, dup rows=32
repurchase  [ts_code, ann_date, proc]                            dup rows=5,741
            [+ exp_date]                                         nulls=56,878, dup rows=5,527
            [+ vol, amount]                                      nulls, dup rows=822
```

**These endpoints need `row_payload_digest` in the natural key** — the mechanism already used by
`top_list` / `top_inst` / `block_trade` / `report_rc`, produced inside the ledger boundary by
`PageReceiptLedger.add_row_payload_digest`.

Verified against the captured data: with `core + row_payload_digest`, the residual duplicates are
**exactly** the fully byte-identical rows —

```
dividend    4,034 rows   key+digest duplicates = 32    fully-identical rows = 32
repurchase 62,216 rows   key+digest duplicates = 761   fully-identical rows = 761
```

— i.e. the digest resolves everything except genuine vendor duplicate rows, which is what
`content_dedup_key` + `max_content_dups` exist to absorb. The amendment must therefore set a
`max_content_dups` these can satisfy, or the same refusal returns in a new form.

---

## Class 2 — a natural key that is NOT UNIQUE

Tushare returns one report under **multiple company-type templates**, so rows sharing every signed key
field differ in `comp_type`:

```
income/002961.SZ        comp_type 2 vs 7,  end_type 2 vs None,  continued_net_profit 228,787,181.26 vs nan
balancesheet/600927.SH  comp_type differs, plus accounts_receiv / oth_receiv / prepayment
```

Sporadic — 6 failures across ~11,700 statement requests (~0.1%) — but the class affects **8 signed
endpoints whose natural key omits `comp_type`**: `income`, `income_vip`, `balancesheet`, `cashflow`,
`cashflow_vip`, `fina_audit`, `express`, `forecast`.

### Candidate fix — tested, and it DIFFERS BY ENDPOINT SHAPE

**Per-stock endpoints** (`income`, `balancesheet`, `cashflow`, …) — add `comp_type` only:

```
income        28,714 rows   [signed... + comp_type]              OK  (no nulls, no duplicates)
                            [signed... + comp_type + end_type]   nulls(end_type)=14
balancesheet  27,844 rows   [signed... + comp_type]              OK
                            [signed... + comp_type + end_type]   nulls(end_type)=64
```

Adding `end_type` reintroduces Class 1 (it is nullable).

**Per-period VIP endpoints** (`income_vip`, `cashflow_vip`) — `comp_type` is NOT enough. Their signed
key omits `ann_date`, which the per-stock variant includes, so two rows for the same
company/period/report_type/f_ann_date/update_flag can differ in announcement date alone. Measured over
391,453 rows:

```
income_vip    SIGNED                       28 duplicate rows
              + comp_type                  26      <- barely helps
              + ann_date                    2
              + comp_type + ann_date        0      OK  (no nulls)
```

**A single uniform amendment would therefore have failed a second time.** Per-stock needs
`+comp_type`; per-period VIP needs `+comp_type, +ann_date`.

`comp_type` must also be added to `required_fields`, where it is currently absent for all 8 endpoints.

**`forecast` — a THIRD sub-shape (high incidence: 3,779 / 5,861 ≈ 64%).** Earnings pre-announcements are
frequently revised, and each revision shares the signed key `[ts_code, ann_date, end_date, type]` while
differing in `update_flag`. Measured over 6,606 rows:

```
forecast   SIGNED                 992 duplicate rows
           + update_flag            0   OK  (no nulls)
```

Add `update_flag` only — clean. (Adding `summary` reintroduces Class 1: 4 nulls.) So the Class-2 fix is
now three-shaped: per-stock statements `+comp_type`; per-period VIP `+comp_type,+ann_date`; forecast
`+update_flag`. Each was derived from the real response, not assumed — a single uniform rule would have
failed three times.

---

## What this does NOT change

`market/daily` is already recovered, reconciled to the pre-incident baseline and promoted; it is
unaffected. The other 26 families in `recover03` are fetching normally.

## Operational consequence for the amendment

Amending a contract changes `contract_sha256`, which changes the frozen plan hash, which requires a
**new run**. A new run has its own staging area and will **not** reuse `recover03`'s page receipts, so
`dividends` and `repurchase` must be **re-fetched** after the amendment (~5,878 requests ≈ 3h). That is
why `dividends` was stopped at 83 rather than allowed to run to 5,861: those receipts could never have
been used.
