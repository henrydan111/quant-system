# GPT §10 review — adapter FAN-OUT (29 families) + the two §13 preconditions

Independent GPT‑5.5 Pro reviewer. You discharged **Gate B** at re-review #9 against the frozen §6a
threat model and unlocked fan-out. This is the work that followed. It is the **last review before the
user is asked for the §13 fetch authorization**, i.e. the last gate before real vendor traffic — so
the thing to hunt is anything that would be wrong *at 104k requests* or would make a live run
unrecoverable.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · commits
**`9de9c18`** (fan-out 1) → **`d402c78`** (fan-out 2) → **`b8e8cba`** (§13 preconditions).
Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
(Interleaved commits on this branch are a concurrent unrelated workstream — nf-wave — that does not
touch the recovery files.)

Files: `scripts/recovery_adapters.py`, `scripts/recovery_ledger.py`,
`scripts/raw_recovery_coordinator.py`, `tests/data_infra/test_recovery_quartet.py` (89 tests),
`tests/data_infra/test_recovery_live_construction.py` (NEW, F10).
**Suite: 257 passed.** `--fetch` exits 3; no Tushare call anywhere in this work.

## State
| | |
|---|---|
| executable families | **29** (every matrix owner) |
| planned requests | **104,176** built from the SIGNED contracts, zero request_id / receipt_output collisions |
| of which offset-paged | 32,450 |
| of which sparse_canary | 82,054 |
| deferred | **A07 indicators only** — `fina_indicator_vip` UNSIGNED (98 recorded partitions vs 73 reconstructible quarter-ends), held at BLOCKED(contract) for a §13 period-discovery probe |
| adapter bundle | `ef6b7429f6aa…` |

A completeness test asserts every matrix owner is **bound, deferred-with-a-reason, or a declared
second layout** — nothing can be silently absent.

## Fan-out batch 1 (`9de9c18`) — 22 families, mechanical mapping + 2 corrections it forced
Layouts are **not guessed**: each `ConsolidationSpec` follows its own matrix row's
`consolidation_group` (`*_per_date`→trade_date, `*_period`→end_date, `*_per_code`→ts_code,
`*_weekly`→the Friday end_date). Two signature-preserving corrections the fan-out exposed:
- **`response_scope_of` is now an EXPLICIT per-endpoint rule table, fail-closed.** The old heuristic
  guessed scope from the request's *shape* and would have silently MIS-SCOPED the new families: a
  `period` request whose rows carry `end_date`; a year range that must match `ann_date`, not
  `report_date`. It also raised outright for `{period}`, `{end_date}` and `(period, report_type)`.
- **`partition_of` accepts a COMPOSITE key.** The direct-quarter VIP families send
  `(period, report_type)`: distinct params (so distinct request_ids) but a single key collapsed both
  to one partition → one `receipt_output` → freeze refusal.

## Fan-out batch 2 (`d402c78`) — 2 interface additions, made as their own unit
- **`ConsolidationSpec.partition_transform`** (`identity`|`year`): the matrix's `*_yearly` groups as
  declarative data (report_rc folds 12 MONTHLY requests into one YEARLY file — a genuine many-to-one).
- **`FamilySpec.consolidations`**: one fetch may feed several **labelled** layouts. The matrix forced
  this — it declares BOTH `market/suspend_d` (per-date) and `market/suspension` (yearly) over the SAME
  `suspend_d` population, so planning them as two families would mint an IDENTICAL request_id per
  session. Fetch once, consolidate twice; `consolidate_family` returns a `layouts` list.
- **report_rc digest producer registered** — and it **reuses `pit_backend.report_rc_payload_digest`**
  rather than restating the field list. That function is the one guarded by
  `test_report_rc_payload_digest_covers_materialized_fields`, so a future `report_rc__*` feature
  widens the recovery digest too; a restated list could drift from the SERVING identity and collapse a
  genuine analyst revision. A test asserts the two agree bit-for-bit.

## The §13 preconditions (`b8e8cba`) — your "before §13, not before fan-out" items
- **`authorize-fetch` CLI**: `--authorize-fetch --actor <human> --hours <=24 --endpoints a,b` writes
  the hash-chained `fetch_authorized` event bound to actor / bounded expiry / scope / **frozen plan
  hash** / **adapter bundle hash**. A lint asserts `cmd_fetch`'s executable body names neither
  `cmd_authorize_fetch` nor `record_fetch_authorization` — a fetch cannot authorize itself. `cmd_fetch`
  still exits 3: authorization alone does not enable fetching (the LiveExecutor is deliberately
  unwired, pending the user's go-ahead).
- **F10 live-construction write proof** (new file). The synthetic battery structurally cannot prove
  this — it never constructs the fetcher. So: fresh SUBPROCESS, write monitor installed BEFORE the
  fetcher import, socket guard (any `connect()` fails), the REAL tushare imported with only `pro_api`
  stubbed, `ts.set_token` turned into a violation, `avoid_token_cache=True`. Result: `constructed=True`,
  one page through the real `LiveExecutor`→`fetch_page_once`→LOCKED proxy,
  `vendor_call == ('daily', {'trade_date':'20260702'})` — exactly the recipe's rendering with **no
  paging kwargs**, independently proving the single_page `0` sentinel never reaches the vendor — and
  **zero** writes outside the allowlist.
  It earned its keep on run 1 by flagging writes to `C:\ProgramData\quant_system_locks`; I verified
  against `tushare_lock._api_lock_dir()` rather than assuming — that IS the sanctioned machine-global
  §6.1 api-lock namespace, and the allowlist is now DERIVED from that function so it cannot drift.

## What I most want you to attack
1. **Layout correctness.** I read each family's physical layout off its matrix `consolidation_group`.
   If any of those group names does NOT mean what I took it to mean, the consolidated store will be
   mis-partitioned — and that is exactly the class of error that survives testing (my synthetic
   fixtures agree with my own reading). `fina_audit_stock` → per-STOCK and `index_per_code` → per-CODE
   are the two I am least certain of.
2. **Scale.** 104,176 requests, 82k of them sparse. The sparse lifecycle needs a verified nonempty
   same-endpoint canary per endpoint; is there a family where NO request can ever be nonempty (so every
   request parks at `WAIT_FOR_CANARY` forever)? Also: is the run-execution lock — held across
   dispatch→call→close — going to serialize a 104k-request run into something unusable, and is that
   the right trade?
3. **Recipes vs the real vendor API.** `express`→`express_vip`, `fina_mainbz`→`fina_mainbz_vip`, and
   the paged/single-page choices per endpoint come from the signed contracts + the original callers.
   A wrong `vendor_method` or a wrong paging binding is not detectable synthetically.
4. **The two interface additions** — are `partition_transform` and multi-layout `consolidations` the
   right shape, or do they encode a layout the matrix did not intend?
5. **Anything that makes a live run UNRECOVERABLE** rather than merely wrong: a state a crash could
   leave that `claim_next_fetch` cannot resume from, or a partial consolidation that a re-run would
   double-count.

Out of scope per §6a (user-frozen 2026-07-20): mid-operation active local adversary; the accepted
hard-link residual.

Standing preconditions after this review: `update_daily_data`→`merge_daily_legs` (before A01 live
release), the output-density gate (before promotion), the A07 §13 period-discovery probe. Wiring
`cmd_fetch` to the LiveExecutor is deliberately NOT done and awaits the user's explicit §13 go-ahead.
