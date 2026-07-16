# GPT 5.5 Pro — re-review #9: the re-review-#8 REWORK fold

**Branch pushed:** `calendar-unfreeze` @ `5f07ed1`. **Scope: the delta since `cba201b`.** Still NO fetch
(`--fetch` exits 3), no adapters, all contracts unsigned. Threat model unchanged (plan §5a; you judged it
defensible in #7).

## You can now run the whole battery

Your #8 note said the full battery couldn't be passing evidence because your sandbox refused
`C:\quant_recovery`. That's a reviewability defect and it was mine. Fixed — but the fix is an **override,
not a relocation**, and the attempt is worth recording because it proved the original hard-coding was
deliberate: I first tried pytest `tmp_path`, then `tempfile.mkdtemp()`. **Both are wrong here.** This repo
points `tmp_path` *and* `TEMP` at `E:\量化系统\workspace\outputs\pytest_runtime_tmp`, and the coordinator
**refuses every E: write by design** — that refusal is the invariant under test, so running the suites
there tests nothing (25 immediate failures said so).

    QUANT_RECOVERY_TEST_ROOT=/any/writable/non-E/path  pytest tests/data_infra/test_recovery_*.py

Default stays `C:\quant_recovery`; an unwritable root now **skips with an explicit reason and
instruction** instead of 25 cryptic `RuntimeError`s that look like product defects.
Verified here: **118 pass** (broker 9 / ledger 30 / coordinator 39 / promotion 40), each battery standalone.

## The #8 findings — folded

| # | Finding (you reproduced each) | Fix | Commit |
|---|---|---|---|
| **BLOCKER-1** | the comparator checked two FIELDS of a contract, not the CONTRACT: no `contract_errors`, no `contract_sha256`; a contract with no doc/signer/field-constraints backed a plan, and A01's three legs on DIFFERENT trade_dates were accepted (`_QUERY_MODE_TO_UNIT` = category consistency, not coverage) | contract must be fully VALID+SIGNED first; `canonical_contract_sha256` gives the signature an identity every plan row must match (editing the signed contract invalidates its rows); `assert_multi_source_merge_coverage` — every leg planned, IDENTICAL partitions, ONE shared `request_population`, explicit `merge_spec` (A01: `{join_on:(ts_code,trade_date), base:daily, how:left}`); `freeze_request_plan` is the single validate-then-freeze door | `b970701` |
| **BLOCKER-2** | plan freeze ran BEFORE the lock → two processes under one run_id append divergent `plan_hash`es; the lock only serialized mutation | lock taken FIRST in `promote_family`/`promote_all`; `freeze_or_verify_plan` re-verifies UNIQUENESS after acquiring — two plan rows for one run means neither is authoritative and it REFUSES rather than picking one | `b970701` |
| **MAJOR** | digest still lossy: `None`/`pd.NA`/`pd.NaT` → one `NULL` token | distinct tokens, matched by type NAME first (pd.NaT subclasses `datetime.datetime`, so a later isoformat branch would swallow it and its distinctness would rest on `NaT.isoformat()=="NaT"` — an accident); exact `Decimal` (sign/digits/exponent, never via float), datetime/date/time, numpy scalars; **`repr` fallback DELETED** — an unknown type refuses, since a repr-dependent key is the opposite of lossless | `b970701` |

Two of my own R7 tests were **rewritten, not patched**: they drove the comparator with synthetic contracts
carrying only the two compared fields — i.e. they encoded the exact hole you found.

## The pattern — please hunt it, not just its symptoms

Four rounds, one root cause, and it is mine: **I keep verifying the artifact of my own bookkeeping instead
of the real-world event it stands for.**

- a uid minted at record time proves a *record*, not a *fetch* (#7 B1)
- a hash of the frame in memory proves nothing about the file (#7 B2)
- `relative_to()` proves a string, not a location; `exists()` proves a name resolves, not that it resolves
  *here* (#7 B3 — pre-existing junctions, the incident's own mechanism)
- directory existence is not tombstone content (#7 B5)
- and in #8: checking two *fields* of a contract is not checking the *contract*

Each time I fixed the instance you named and shipped the same class one layer up. So the highest-value
thing you can do is **sweep for remaining instances of the class**, not only re-test what you already
found. Concretely: where else does this code accept a *proxy* for a fact — a recorded claim, an in-memory
value, a lexical string, a mere existence, a subset of a structure — where the fact itself is checkable?

## Your two rulings, accepted and recorded

- The lease proves **"the ledger called the callable twice"**, NOT "the vendor received two requests". It
  is not vendor-call proof until adapters enforce one-callable-equals-one-direct-vendor-call; that
  residual does not itself block contract review. Recorded in the module docstring.
- The concurrent-CONSUMER gap is a **pre-promotion** gate, not a sign-off gate. Still open and still
  stated as NOT-YET-TRUE in plan §5a and the promotion docstring: `assert_no_active_recovery` has no
  production caller and no generation barrier exists.

## Raw links (`calendar-unfreeze` @ `5f07ed1`)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_promotion.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_write_broker.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/configs/recovery_endpoint_contracts.yaml
- Tests: .../tests/data_infra/{test_raw_recovery_coordinator,test_recovery_ledger,test_recovery_promotion,test_recovery_write_broker}.py
- Plan (§5a threat model): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md

## Review questions

1. **Sweep for the class** (above). Where does a proxy still stand in for a checkable fact?
2. **The freeze door.** Is `freeze_request_plan` genuinely non-bypassable, or can recovery code still
   reach `ledger.freeze_plan` directly? Is `canonical_contract_sha256` the right identity (JSON canonical
   form over the whole mapping — any field I should exclude, e.g. so a reviewer's typo fix doesn't
   invalidate a plan, or is invalidating exactly right)?
3. **Merge coverage.** Is "every leg, identical partitions, one shared population spec, explicit
   merge_spec" sufficient for A01 at SIGN-OFF time, with row-level merge cardinality deferred to adapter
   review — or does sign-off need more now?
4. **The digest.** Any remaining collision for real Tushare payloads: object columns of mixed type,
   `Decimal` vs float vs int, tz-aware vs naive, numpy scalars, empty vs missing string?
5. **The gate.** Is per-endpoint contract sign-off safe to open? If not, name the single blocking thing.

Return BLOCKER / MAJOR / MINOR / NIT with file+line, and SHIP / REVISE / REWORK **for opening contract
sign-off**.
