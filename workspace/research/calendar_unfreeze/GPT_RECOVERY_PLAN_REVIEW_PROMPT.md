# GPT 5.5 Pro RE-review #3 — raw-store RECOVERY design (plan v4 + coordinator v3, post re-review #2 REWORK)

Status: ready to send. Branch `calendar-unfreeze`, artifacts pinned to commit `49573f3`. Still NO fetch executed; adapters still deliberately unbuilt (your M3 sequencing: contracts first).

**Self-review (§10, done):** your `..\escape` / `..\..\Users\...` probes reproduced locally against v2, then pinned as tests against v3 (both refuse at the run_id regex); the junction probe initially PASSED against my v3 draft — the guard never inspected the leaf component it was handed (`_lex_components` built ancestors only) — fixed and now pinned (`test_reparse_point_in_ancestry_refused` creates a real `_winapi.CreateJunction` inside the run root). Driver facts re-verified before encoding (dividends inside `download_fundamentals` per-stock — grep L207; `FactorDataInitializer` has zero dividend refs; per-stock swallow at `fetch_new_alpha_endpoints` L143; cashflow/forecast/holder scope = init_factor per CLAUDE §6.2). 13-test coordinator battery (was zero at the last pin) + 47 green total; no Tushare call. Verdict: clean for GPT.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. Recovery
context: the operator's `git worktree remove --force` deleted 21/27 raw provider-input datasets
(~77.5M rows) through junctions; live provider + reference/ + universe/ intact; recovery = C:-staged
re-fetch. Your re-review #2 (commit ee94dc5) returned REWORK: B1 run-root escape (../ probes accepted,
resolve-before-scan erased junction evidence), B2 spec/driver mismatches, B3 unchecked ledger, B4
placeholder-passable doc gate, B5 unrecoverable window between the two promotion renames, M1 builder
containment, M2 loose first-seen evidence, M3 contracts-before-adapters, minors (non-finite throttle,
physical-disk identity). This RE-REVIEW #3 verifies the fold. Fetch remains REFUSED; adapters remain
unbuilt pending your verdict + signed contracts.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, commit 49573f3)
- Plan v4:        https://raw.githubusercontent.com/henrydan111/quant-system/49573f3/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md
- Coordinator v3: https://raw.githubusercontent.com/henrydan111/quant-system/49573f3/scripts/raw_recovery_coordinator.py
- NEW test battery (13): https://raw.githubusercontent.com/henrydan111/quant-system/49573f3/tests/data_infra/test_raw_recovery_coordinator.py
- Throttle (isfinite + central floor): https://raw.githubusercontent.com/henrydan111/quant-system/49573f3/src/data_infra/tushare_lock.py
  + https://raw.githubusercontent.com/henrydan111/quant-system/49573f3/src/data_infra/fetchers/__init__.py
- Contracts scaffold (unreviewed, gate blocks): https://raw.githubusercontent.com/henrydan111/quant-system/49573f3/workspace/configs/recovery_endpoint_contracts.yaml

HOW EACH FINDING WAS FOLDED

B1: run_id must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ (separators/UNC/device/ADS/traversal refuse
before any path exists — your two escape probes are pinned tests); the run-root candidate is checked
LEXICALLY against RECOVERY_ROOT before anything resolves; _reject_reparse_lexical inspects every
component INCLUDING THE LEAF with lstat semantics (no resolve first — resolve() following the junction
was exactly how evidence got erased), inspection failure refuses; assert_write = lexical normpath ->
relative_to(run root) -> reparse scan -> realpath cross-check belt; root creation, temp files and the
ledger .lock all route through the authority; resume requires the original run_created ledger record
matching run id + the pinned baseline hash (tamper test pinned). Honest disclosure: my first v3 draft
FAILED the junction test because the guard inspected only ancestors, not the handed leaf — fixed, test
pinned. The fresh-subprocess ALLOWLIST write monitor (run-root + api-lock namespace only, incl. the
ts.set_token token-cache write) is specified in plan §2 as an adapter-gating test.
B2: ENDPOINT_MATRIX replaces prose — one machine-readable row per endpoint/output family with
callable, physical outputs, partition enumerator, pagination rule, natural key, empty policy,
consolidation rule, tail rule, UNIQUE owner (test-enforced), and sidecars. Corrections encoded:
dividends are fetched INSIDE FundamentalsInitializer.download_fundamentals per stock (A03 owns
income+balancesheet+dividends together); cashflow/forecast/holder_number are init_factor scope (A05/
A06/A09); index_daily is per-index RANGE (A02); stk_holdertrade (A12) and cyq_perf (A13) are per-stock
with explicit consolidation/repartition rules and the swallow-at-line-143 gap noted; indicators have
ONE owner (A07 refresh_indicator_history); generic L9 is GONE — every row carries its own tail_rule;
known-empty sidecars (moneyflow/northbound) + raw_cache ingest manifests are FIRST-CLASS outputs.
Exact method binding happens at adapter build AFTER that endpoint's contract is signed (M3).
B3: RecoveryLedger — freeze_plan writes a hashed request_plan.json ONCE (tamper -> everything
refuses); typed kinds (lifecycle/attempt/verdict) schema-checked on load; stable request ids
(sha256 over endpoint+canonical params+partition); transitions planned->fetched|failed->
verified|confirmed_empty enforced under the file lock with read-check-append; 'verified' requires a
CONTAINED output whose sha256 matches + schema fingerprint + key stats (a verdict for a missing file
refuses — your exact probe); dense datasets can NEVER be confirmed_empty; sparse confirmed_empty
requires a same-session nonempty canary request id AND repeat confirmation; torn/malformed tails fail
closed; consolidation_allowed(dataset) requires every planned constituent terminal-valid. All pinned
by tests (invalid transition, unplanned request, plan tamper, torn tail, dense-empty, canary,
consolidation).
B4: contract_errors validates structure: doc_path resolved under the offline mirror with traversal +
reparse rejection, doc_sha256 recomputed against the actual file, required_fields/natural_key as real
lists, empty_policy enum, reviewed_by length + placeholder set rejection, reviewed_at ISO-parsed and
not in the future. Your "eight x values" probe is a pinned negative test alongside wrong-hash,
path-escape and future-timestamp cases.
B5 (plan §6): per-family state machine COPYING -> PREPARED -> OLD_MOVED -> NEW_INSTALLED ->
LIVE_VERIFIED -> SWAPPED, journal fsync'd before each transition, resume inspects all three paths +
hashes for deterministic roll-forward/rollback; durable E:-side RECOVERY_IN_PROGRESS sentinel written
BEFORE the first swap with all raw readers/jobs/builders failing closed on it; pre-existing
incoming/tombstone destinations refused; recursive reparse scans on C: source AND E: incoming BEFORE
and AFTER copying (an /XJ skip is not success); incoming + tombstones at the data\ top level outside
every dataset glob; crash injection around every rename/transition is a pre-promotion test gate.
M1 (plan §5): the pinned C-side build runs from a hash-verified `git archive` of f93cb9d2 extracted
under the immutable run root (no worktree/junction; E:-checkout execution banned because of its
data_profiles + import-time log writes); tree hash, dependencies, command recorded; a path-injection
patch, if unavoidable, gets its own recorded diff hash separate from the semantic pin; the oracle
holds the provider-publish lock (or hashes the live provider before AND after) and covers calendars,
instruments, and EVERY feature bin.
M2 (plan §5): prior first-seen admissible ONLY with retained evidence cryptographically binding
natural key + CONTENT HASH to a timestamp; aggregate state flags/log lines inadmissible; default =
recovery-time floor; quarantine when even the floor is ambiguous (collision/prefix mismatch); a proven
vendor restatement never auto-authorizes rewriting sealed provider output.
M3 (plan §8): contracts are reviewed + signed BEFORE that endpoint's partitioning/fetch logic exists;
only generic containment/ledger infra proceeds in parallel. Your 9-step sequence + minimum pre-fetch
test matrix are adopted verbatim in §8.
Minors: spaced_call + TushareFetcher validate float()+isfinite before flooring (nan/inf/negative/None
-> MIN_BASE_SLEEP; max(nan,1.5) noted as the trap; pinned across all five inputs); backup destination
must be verified by Windows volume + physical-disk identity, not asserted (plan §7).

VERIFICATION AT THIS PIN
13-test coordinator battery (traversal probes, sibling-prefix escape, junction-in-run-root via real
CreateJunction, resume tamper, plan freeze/tamper, unplanned request, verified-without-file,
dense-empty/canary, torn tail, consolidation gate, contract placeholders/hash/escape/future-ts,
unique-owner matrix, non-finite throttle floor) + lock/fetcher/5-C batteries = 47 green. Coordinator
smoke on the real tree: inventory + preflight + plan (all rows contract-BLOCKED) + fetch refusal
(exit 3). No Tushare call. E: writes remain plan/code/test text only.

RE-REVIEW QUESTIONS
1. B1: is the lexical-first + leaf-inclusive reparse inspection + realpath belt now sound? Remaining
   races you'd require the adapter-phase monitor to catch (TOCTOU between scan and write) — is the
   allowlist-monitor spec sufficient for that, or do you want open-handle-relative writes
   (dirfd-style) mandated?
2. B2: any remaining factual error in ENDPOINT_MATRIX rows vs the drivers at this pin? Is deferring
   exact method binding to post-contract adapter build acceptable, or must the callable be pinned now?
3. B3: is the ledger now sufficient as the restoration-proof substrate (with the profiler comparison
   from §4)? Anything missing in the transition set (e.g. an explicit 'skipped' terminal for
   plan-superseded requests)?
4. B4/M3: does the contract gate + contracts-first sequencing satisfy the repo's doc-before-fetch
   rule as you intended?
5. B5: any hole left in the promotion state machine or its resume semantics?
6. Are we ready to START the two §8 steps that need no fetch authorization — (a) the 30 endpoint
   contract reviews, (b) generic containment/ledger test infrastructure hardening — while the user
   considers the fetch gate? If not, what blocks them?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending text/code quoted + exact fix.
- Answer the 6 questions explicitly.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk before contract review
  + adapter construction begin.
```
