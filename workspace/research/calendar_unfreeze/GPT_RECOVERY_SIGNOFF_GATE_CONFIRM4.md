# GPT 5.5 Pro — sign-off gate, take 4: fail-closed bindings + A15's real shapes

**Branch pushed:** `calendar-unfreeze` @ `97716ad`. **Narrow scope: your sign-off HOLD #3 only.** Same
question: **is the contract sign-off gate open?**

Batteries: **154** — broker 9 / ledger 34 / coordinator 71 / promotion 40, each standalone.
`QUANT_RECOVERY_TEST_ROOT=/writable/non-E/path pytest tests/data_infra/test_recovery_*.py`

## What it was

`if allowed and spec.resolver not in allowed` — **a fail-open guard, written by me, in the one place
whose entire job is to refuse.** The seven A15 rows were `UNBOUND`, so `endpoint_expected_resolvers()`
returned an empty set and any known resolver signed clean. Your probe: `disclosure_date +
calendar_months → {month: 202607}`, zero errors, while its real caller sends `end_date`.

You also named why my tests couldn't see it: they **sampled four already-bound endpoints**. That is its
own lesson — a guard's test must cover the inputs that make the guard vacuous, not the ones that make it
fire.

| Your finding | Fix |
|---|---|
| unbound endpoints fail open | the check **fails closed**: no binding = sign-off ERROR ("nothing establishes what a request for it even looks like"). An unbound endpoint must never be signable. |
| the test samples four bound endpoints | the new test asserts over **all 32** — every endpoint has a non-empty binding, every named resolver exists. |
| A15 needs its real shapes | all seven bound, each read from its **actual caller** (`fetch_bucket_a.py`) and cross-checked against the pinned doc's inputs. |
| **MINOR** stale `report_date_months → {report_date}` in the signer instructions | replaced with the four real recipes; the endpoint-aware + fail-closed rule is now stated for the human signer. |

**A15 shapes** (`callable` stays UNBOUND — the shape is known, the adapter is not, so fetch hard-blocks):

| endpoint | real call | resolver → shape |
|---|---|---|
| `disclosure_date` | `disclosure_date(end_date=<quarter end>)` | `quarter_end_dates` → `{end_date}` — the quarter goes in **`end_date`, not `period`** (your exact probe) |
| `repurchase` | `repurchase(start_date=YYYY0101, end_date=YYYY1231)` | `year_ranges` → `{start_date,end_date}` per year |
| `pledge_stat` | `pledge_stat(end_date=<Friday>)` | `weekly_friday_end_dates` → `{end_date}` (probe asserts `weekday()==4`) |
| `fina_audit` | `fina_audit(ts_code=<code>)` | `stock_basic_codes` → `{ts_code}` |
| `express` / `fina_mainbz` / `top10_floatholders` | `…(period=<quarter end>)` | `report_periods` → `{period}` |

Labels stay **derived**, never sent: `repurchase`'s yearly file is named by the year its range covers.

Recorded as accepted: **the other 25 recipes match their real callers**, including every endpoint I
specifically questioned (`index_daily`, `suspend_d`, `margin_detail`, `hk_hold`, `moneyflow`,
`broker_recommend`) — my sampling worry was right in kind but wrong in target; the hole was the seven I
had left unbound and then written a fail-open check around. **`declared_families`** is the correct scope
unit — *"request count alone cannot detect substitutions, while the resolved request-set hash already
pins exact membership."*

## The question

**OPEN or HOLD for per-endpoint contract sign-off?** Sign-off = a human reads the pinned doc and fills
the YAML; no fetch, no adapters, no mutation.

1. **Would a contract signed today survive without re-signing?** Your bar, four times now.
2. **Sweep for the fail-open VARIANT specifically.** This round's defect was not a proxy standing in for
   a fact — it was **a guard that skips its check when its input is empty or absent**. Where else does
   this code do that? (`if allowed and …`, `if spec.get(x) and …`, `for k in seen:` over a set that can
   be empty, an `elif` chain with no terminal `else`, a validator that returns `[]` on an unrecognised
   shape.) I have looked and found none, but I found none last round either.
3. **Are the seven A15 shapes right?** I read each from its caller and cross-checked the doc — the same
   method that produced the 25 you validated — but `report_rc` came from that method too, before I was
   reading callers. The ones I'd least trust: `fina_audit` (`{ts_code}` alone: its caller loops stocks,
   but the doc also takes `period`/`ann_date` — is per-stock the whole recipe?) and `fina_mainbz`
   (`{period}`, but the doc has a `type` input its caller never passes — does an unsent-but-defaulted
   parameter belong in the signed request?).
4. **Is the class closed in the population path**, or is there still a corner?

## Explicitly NOT folded (gating FETCH, not sign-off — your split)

Replaceable contract loader + `doc_sha256` never re-checked at fetch; the frozen plan self-authenticates
(orphan plan after a crash consumed); matrix/response facts partially bound at the RESPONSE level
(sparse-vs-dense, narrower-than-vendor natural key, `required_fields` never checked against responses);
`receipt_output` escapes `staging_data` via `../`; digest doc overclaims for mixed object columns;
test-root validated after creation. Standing: consumers undefended (pre-promotion); the lease proves the
ledger called the callable, not that the vendor was reached.

## Raw links (`calendar-unfreeze` @ `97716ad`)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/configs/recovery_endpoint_contracts.yaml
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_raw_recovery_coordinator.py
- The callers the A15 shapes were read from: .../scripts/fetch_bucket_a.py

Return **OPEN / HOLD**, plus any BLOCKER/MAJOR/MINOR **within the population path** (file+line). If HOLD,
name the single thing that must change.
