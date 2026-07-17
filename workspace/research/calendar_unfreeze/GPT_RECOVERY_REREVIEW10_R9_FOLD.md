# GPT 5.5 Pro — re-review #10: the re-review-#9 REWORK fold

**Branch pushed:** `calendar-unfreeze` @ `e8d72cd`. **Scope: the delta since `5f07ed1`.** Still NO fetch
(`--fetch` exits 3), no adapters, all contracts unsigned. Threat model unchanged (plan §5a).

Batteries: **127** — broker 9 / ledger 34 / coordinator 44 / promotion 40, each verified standalone.
You can run all of them: `QUANT_RECOVERY_TEST_ROOT=/writable/non-E/path pytest tests/data_infra/test_recovery_*.py`

## The class sweep worked — please keep doing it

Asking you to hunt the **class** instead of the symptoms was worth more than any individual finding: both
#9 blockers were the same error one layer up — **a proxy standing in for the fact**. A hash proves a
contract is *unchanged*, not that the plan *implements* it. A `partition` label is a string the planner
writes, not the request it claims to describe.

**One thing I want to report honestly:** I nearly shipped BLOCKER-1's fix with the identical defect. My
first draft installed `contract_loader = lambda: snapshot` — a copy captured *at freeze*. It would have
been re-verified against my own frozen copy and could never have detected the edit it exists to catch. I
caught it before applying and switched to reading the live YAML. First time this arc I've caught the
pattern in myself rather than having you catch it — but "nearly" is the operative word, so **please keep
sweeping for the class**, not just re-testing what you named.

## The #9 findings — folded

| # | Finding (you reproduced each) | Fix | 
|---|---|---|
| **BLOCKER-1** | the hash bound the plan to a contract IDENTITY but nothing compared the plan's own execution fields to its CONTENT (`empty_policy`, `natural_key`, `doc_sha256` all divergeable); validation ran once at freeze so a post-freeze contract edit still allowed `fetch_page`; `freeze_plan` remained a public bypass | every contract-derived plan field must AGREE with the signed contract, every matrix-derived field with the matrix row; `fetch_page` calls `_assert_contract_binding` before **every** call against the **LIVE** contract (edited / deleted / no-loader all refuse); `freeze_plan` → `_freeze_plan_unvalidated`, with `freeze_request_plan` its only production caller, installing `load_signed_contracts` (reads the YAML, never a snapshot) |
| **BLOCKER-2** | coverage grouped legs on the `partition` LABEL — all legs claiming `20260702` while `daily_basic` requested `20260703` was accepted | `_request_population_key` reads the value from the request's own `params` via `_UNIT_PARAM`; refuses a label that misdescribes its request; refuses a params-less request; legs compared on what they ACTUALLY ask for |
| **MAJOR** | `Decimal("Infinity") == Decimal("-Infinity")`, `NaN123 == NaN456` at the digest layer (the special-value branch returned only the exponent tag) | sign and digits are part of a special value's identity and are now encoded |
| **MINOR** | `QUANT_RECOVERY_TEST_ROOT` accepted relative/E: paths and wrote before validating | validated before use |
| **NIT** | digest docstring still advertised the `repr` fallback deleted in #8 | corrected |

Confirmed closed by you this round and not re-litigated here: promotion lock precedes plan freeze;
duplicate same-run plan rows refuse; the full battery ran 118/118 under a non-E: override.

## Standing, unchanged

- **Concurrent CONSUMERS** are not defended: `assert_no_active_recovery` has no production caller and no
  generation barrier exists. Stated as NOT-YET-TRUE in plan §5a and the promotion docstring. Your ruling
  that this is a **pre-promotion** gate, not a sign-off gate, is recorded and accepted.
- **The lease** proves the ledger called the callable, NOT that the vendor received a request. Not
  vendor-call proof until adapters enforce one-callable-equals-one-direct-vendor-call. Recorded in the
  module docstring; your ruling that it doesn't block contract review is accepted.

## Raw links (`calendar-unfreeze` @ `e8d72cd`)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_promotion.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_write_broker.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/configs/recovery_endpoint_contracts.yaml
- Tests: .../tests/data_infra/{test_raw_recovery_coordinator,test_recovery_ledger,test_recovery_promotion,test_recovery_write_broker}.py
- Plan (§5a threat model): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md

## Review questions

1. **Keep sweeping the class.** Where does a proxy still stand in for a checkable fact — a recorded
   claim, a cached copy, an in-memory value, a lexical string, a mere existence, a subset of a structure,
   a label, an identity-hash — where the fact itself is reachable?
2. **The fetch-time binding.** Is `_assert_contract_binding` in the right place (before the lease opens)?
   It re-reads the YAML on every page — is that the right cost/correctness trade, and can it be defeated
   (loader swapped post-freeze, YAML edited between the check and the call, endpoint renamed)? Is
   refusing when `contract_loader is None` genuinely fail-closed for every path that can reach
   `fetch_page`?
3. **Population keys.** Is `_UNIT_PARAM` right for every unit — especially `index_range` (a range, keyed
   on `ts_code`) and `period_report_type` (which needs `period` AND `report_type`)? Should the key be a
   tuple of *all* population-determining params rather than one?
4. **The `_freeze_plan_unvalidated` rename.** It's a naming convention, not an enforcement. Is that
   sufficient given the ledger battery legitimately calls it, or does the door need a real token?
5. **The digest.** Any remaining collision: `Decimal` vs `float` vs `int` for equal values, numpy
   datetime64 units (`[ns]` vs `[s]`), empty string vs missing, mixed-type object columns?
6. **The gate.** Is per-endpoint contract sign-off safe to open? If not, name the single blocking thing.

Return BLOCKER / MAJOR / MINOR / NIT with file+line, and SHIP / REVISE / REWORK **for opening contract
sign-off**.
