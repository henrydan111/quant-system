# GPT 5.5 Pro — consolidated IMPLEMENTATION re-review: recovery foundations 1–5

**Branch pushed for live cross-check:** `calendar-unfreeze` @ `8ddd399` (raw links below point here).
**What this is:** GPT recovery re-review #4 declared the DESIGN converged and endorsed building the 5
corrective foundations. All 5 are now implemented + tested (47-test batteries, network-free). This asks
for an **implementation** re-review — not the design again. **NO Tushare fetch has run; the coordinator's
`--fetch` exits 3.** Adapters are NOT built. Contracts are all UNSIGNED. This review gates whether the
foundations are sound enough to proceed to per-endpoint contract sign-off → adapters → pre-fetch matrix →
the user's §13 fetch authorization.

---

## Self-review verdict (§10 prerequisite): clean for GPT

I reviewed the diff, the four test batteries, and the evidence against the CLAUDE.md §3 hard invariants
and the §7 quantitative-research principles before writing this. Findings:

- **§3.2 PIT / no-lookahead** — the typed matrix's `pit_version_key` anchors the 5 statement families on
  `ann_date`/`f_ann_date`/`update_flag` (a restatement is a NEW row, never a dup), and event/indicator
  families on `ann_date` only — consistent with §3.2's dataset-specific `f_ann_date` rule. The matrix is
  a fetch/partition plan only; it does not itself align or serve PIT data (that stays in the ledger +
  `pit_backend`, untouched). report_rc identity uses the normalized-analyst + payload-digest key, matching
  the current provider PIT logic (memory `project_tushare_15000_expansion`); the recovery is a NEW raw
  generation and the live provider bins are preserved as legacy (leave-as-is decision).
- **§3.3 execution realism / §6.1 Tushare safety** — throttle floor stays central (`MIN_BASE_SLEEP=1.5`),
  not re-introduced here; no parallel-fetch path exists (no fetch path at all). No change to exchange/
  cost/limit code.
- **Containment** — the promotion state machine is the ONE authorized E: write; it is same-volume-rename
  only for the atomic steps, cross-volume copy is re-runnable + manifest-verified + walked NO-FOLLOW
  (reuses Foundation 1). Everything else stays C:-staged.
- **Fixes made during self-review:** (a) `recovery_action` initially required a PRESENT live dir for a
  fresh family — wrong, since the incident DELETED 21/27 families, so live-absent is the normal start;
  corrected + test `test_lost_family_no_live_dir_still_installs`. (b) The typed dataclass failed to import
  under `spec_from_file_location` (module not in `sys.modules` for annotation resolution); fixed in the
  test loaders. (c) The contract scaffold said `forecast_vip`; the live path is `pro.forecast` per-stock —
  the new matrix↔contract reconciliation caught it, corrected to `forecast`.

Verdict: **clean for GPT**. No §3 invariant is violated; the one behavioral risk (promotion touching E:)
is bounded by the crash-injection battery + the sentinel + the untouched-provider guarantee.

---

## The 5 foundations (each closes a re-review #4 blocker)

### Foundation 1 — no-follow write broker (`scripts/recovery_write_broker.py`), re-review #4 B3
The incident's mechanism: `git worktree remove --force` followed Windows JUNCTIONS into live `data\`. The
broker makes every recovery write reparse-safe: `validate_ancestry` opens each path component with a
handle (`CreateFileW` + `FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS`), rejects any
component that is a reparse point, and confirms `GetFinalPathNameByHandleW` containment — closing the
scan→write TOCTOU and the **broken-junction bypass** (`Path.exists()` returns False for a broken junction
and would skip it; `os.lstat`/handle sees the reparse tag). `walk_no_follow` refuses a reparse point in a
source tree. Fails closed off-Windows.

### Foundation 2 — page-receipt ledger (`scripts/recovery_ledger.py`), re-review #4 B2
Removes GPT's three demonstrated false-success paths: the COORDINATOR persists each fetched page as an
immutable receipt parquet and computes its rowcount + sha256 ITSELF (adapter claims never trusted). A
frozen hashed request plan binds each request to its OWN `receipt_output` (two requests can't verify one
shared file). `verify_request` proves CONTIGUOUS pages 1..N (retries supersede), an endpoint-correct
TERMINAL (an exact-`page_limit` last page demands a trailing EMPTY page), reconciles pre/post-dedup +
excess-dup counts, and REJECTS null semantic keys + unexpected duplicates (`baseline_dups` allows the
event families). A `prev_record_hash`/`record_hash` chain anchored in a SEPARATE `ledger_chain_head.json`
catches a truncated/edited JSONL tail on load. `confirmed_empty` needs ≥2 DISTINCT empty receipts + a
verified nonempty same-endpoint canary.

### Foundation 3 — typed matrix (`ENDPOINT_MATRIX`/`EndpointRow`), re-review #4 M1
One typed row per physical `output_family`, owned by EXACTLY one row (`assert_unique_output_owner`).
Declares `source_endpoints` (A01 `market/daily` draws `daily`+`daily_basic`+`adj_factor`),
`vendor_record_key`, `pit_version_key` (ann_date/f_ann_date/update_flag), `content_dedup_key`,
`profile_key`, `allowed_baseline_dups`, `consolidation_group`, and an UNBOUND `callable`. GPT-specified
identity fixes folded: `suspend_d` → TWO families (`market/suspension` yearly + `market/suspend_d`
per-date); `stk_holdertrade` key INCLUDES `change_vol`; `report_rc` identity = normalized analyst +
`report_rc_payload_digest`, NOT `author_name` alone; event families carry `allowed_baseline_dups`; A15
bucket-A siblings wholly UNBOUND. `matrix_source_endpoints()` (32) MUST equal the contract-YAML key set —
`cmd_plan` BLOCKS on any gap/orphan (this caught the `forecast_vip`→`forecast` drift).

### Foundation 4 — doc-parsing contract validator (`parse_doc_field_vocabulary` + `contract_errors`), re-review #4 M2
The gate no longer accepts a FABRICATED field list. It parses the pinned Tushare doc's markdown field
tables (`| 名称 | 类型 | … |`, input AND output) into the declared vocabulary; every `required_fields`
entry MUST be a real doc column, every `natural_key` column MUST be a doc field or a coordinator-DERIVED
column (`report_rc_payload_digest`/`raw_fetch_ts`/`_src_file`/`_src_ordinal`); a doc with NO field table
(wrong doc cited — e.g. the generic pro_bar doc that only points to sub-docs) refuses. This runs on top of
the existing structural checks (hash/traversal/reparse/ISO-non-future timestamp/non-placeholder reviewer).

### Foundation 5 — crash-resumable promotion state machine (`scripts/recovery_promotion.py`), re-review #4 M3
Per-family `COPYING → COPY_VERIFIED → MOVE_OLD_INTENT → OLD_MOVED|OLD_ABSENT → INSTALL_NEW_INTENT →
NEW_INSTALLED → LIVE_VERIFIED → SWAPPED`. `recovery_action(state, live?, incoming?, tomb?)` is a TOTAL
table — a write-ahead `*_INTENT` is resolved by FACTS (rename done-before-crash vs not), an unmapped tuple
RAISES (never guesses). `PromotionJournal` fsync's each row to the E: volume BEFORE its mutation. Only
same-volume renames are trusted atomic; the cross-volume C:→incoming copy is re-runnable + manifest-
verified + NO-FOLLOW. Live-ABSENT is the normal start (incident deleted most families). Owned-resume
refuses a foreign incoming/tombstone. `assert_no_active_recovery` is the consumer fail-closed hook
(`RECOVERY_IN_PROGRESS` sentinel). Crash injection at ALL 11 checkpoints resumes to `SWAPPED` with
byte-identical live content.

---

## Raw links (branch `calendar-unfreeze` @ `8ddd399`)

- Broker: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_write_broker.py
- Ledger: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py
- Coordinator (matrix + contract gate): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py
- Promotion SM: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_promotion.py
- Contract YAML: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/configs/recovery_endpoint_contracts.yaml
- Tests: .../tests/data_infra/test_recovery_write_broker.py · test_recovery_ledger.py · test_raw_recovery_coordinator.py · test_recovery_promotion.py
- Plan: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md
- Contract you must hold it to — CLAUDE.md §3 (invariants) / §6 (data ops) / §13 (risky-action): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/CLAUDE.md

---

## Review questions (please be adversarial — try to break each foundation)

1. **Promotion state machine (highest stakes — it writes E:).** Is `recovery_action` TOTAL and correct
   for every reachable (state, live, incoming, tomb) tuple? Find a crash sequence (crash → resume →
   crash → resume) that lands in a state the table mis-handles, double-installs, clobbers live, or loses
   the tombstone. Is resolving a `*_INTENT` by on-disk FACTS safe given `os.replace` is atomic but the
   journal write is a separate fsync? Is the owned-resume rule (refuse foreign incoming/tombstone unless
   the journal owns it) sufficient, given the journal itself is the only ownership proof?
2. **Ledger.** Can an adapter still fabricate a "complete" request — wrong terminal, a gap masked as a
   dup, a null key slipped through — given the coordinator owns the receipts? Does the external
   chain-head actually make a truncated/edited tail non-recoverable-as-valid? Any TOCTOU between
   `_load` replay and `record_page`?
3. **Typed matrix.** Are the `vendor_record_key` / `pit_version_key` / `content_dedup_key` choices
   correct per Tushare semantics for each family (esp. the statement families, `top_inst`/`block_trade`
   event dups, `dividend` proc stages, `stk_holdertrade`)? Is one-row-per-`output_family` the right
   ownership grain? Does A01 merging 3 source endpoints into `market/daily` hide any per-endpoint
   pagination/coverage risk?
4. **Contract validator.** Does `parse_doc_field_vocabulary` correctly extract the field list from the
   real mirror docs, or can a malformed table make it under- or over-permit (accept a fabricated field,
   or reject a real one)? Is the derived-key allowlist right, or does it create a hole? Should the matrix
   `vendor_record_key` ALSO be checked ⊆ the doc vocabulary (currently only the contract's fields are)?
5. **Broker.** Any residual reparse/junction bypass on Windows (e.g. a component swapped between the
   handle open and the write; hardlink/`\\?\` device-path forms; a race on the incoming dir during
   promotion)?
6. **Cross-cutting.** Given all 5, is the sequencing (contracts signed → adapters → pre-fetch matrix →
   §13) still the right gate order? What is the single highest-risk remaining gap before any real fetch?

Return per-foundation: BLOCKER / MAJOR / MINOR / NIT with the exact file+line, and an overall
SHIP / REVISE / REWORK verdict for proceeding to contract sign-off.
