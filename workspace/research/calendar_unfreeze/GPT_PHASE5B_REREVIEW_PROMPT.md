# GPT 5.5 Pro RE-review #2 — Phase 5-B monthly_calendar_bump driver (post-REWORK-2)

Status: ready to send. Branch `calendar-unfreeze` HEAD `68b0ee3`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You
reviewed this monthly calendar freeze-bump DRIVER twice. Round 1 you REWORK'd (7 findings, all
fixed). Round 2 you reviewed the correct commit 4cd2fec, confirmed B1-path / M1 (parent-policy
YAML) / m1 (publish handoff) RESOLVED, and returned a sharper REWORK with 5 findings. This is
RE-REVIEW #2: verify those 5 are real, complete, and hole-free. One of them I fixed DIFFERENTLY
than you suggested (endpoint readiness) for a concrete data reason — scrutinize that most.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 68b0ee3)
Files (raw, pinned):
- driver:  https://raw.githubusercontent.com/henrydan111/quant-system/68b0ee3/scripts/monthly_calendar_bump.py
- catchup: https://raw.githubusercontent.com/henrydan111/quant-system/68b0ee3/workspace/scripts/catchup_fundamentals_range.py
- audit:   https://raw.githubusercontent.com/henrydan111/quant-system/68b0ee3/workspace/scripts/audit_thaw_frozen_prefix.py
- tests:   https://raw.githubusercontent.com/henrydan111/quant-system/68b0ee3/tests/data_infra/test_monthly_calendar_bump.py
           https://raw.githubusercontent.com/henrydan111/quant-system/68b0ee3/tests/data_infra/test_catchup_range_safety.py
Self-review (round 3): workspace/research/calendar_unfreeze/PHASE5B_SELF_REVIEW.md

CONTEXT (unchanged invariants): D3 spent_oos_end frozen at 2026-02-27 across every bump (fresh
window grows monotonically); D1 append-only policy id, fail-closed on blank; target_end = last
COMPLETE trading day; frozen-prefix audit + fresh-window survivorship audit both GATE; publish is
§13 human-gated. Tushare 000001.SZ / provider 000001_SZ. report_rc raw has report_date (YYYYMMDD)
+ create_time; per-year files report_rc_<year>.parquet (2010..2026), only 2026 has raw_fetch_ts.

HOW EACH ROUND-2 FINDING WAS FIXED (verify real + complete + no new hole)

B1 (endpoint existence != completeness): FIXED, but NOT the way you suggested — and here is why.
Your exact-fix put per-endpoint row-count checks (incl. cyq_perf) inside the PRE-catch-up
target_end probe. Live data shows cyq_perf LAGS: on 2026-07-04, daily/moneyflow/stk_limit were
current through 07-03 but cyq_perf only through 07-01, because cyq_perf is a per-SYMBOL Stage-D
fetch that the MONTHLY CATCH-UP ITSELF brings current. If the pre-catch-up probe required cyq_perf,
target_end would wrongly roll back to cyq_perf's STALE coverage (07-01) and defeat the bump. So I
split the gate into two tiers:
  - endpoint_ready(date)  [PRE-catch-up, gates target_end]: daily row count >= 4000 AND each
    DAILY-FRESH endpoint (moneyflow, stk_limit) row count >= MIN_ENDPOINT_ROWS=3000. ROW COUNT,
    not existence. northbound is NOT a hard gate (inherently partial + declining coverage).
  - assert_endpoints_complete(date) [POST-catch-up, before minting policy / building provider]:
    re-verify daily-fresh AND the LAGGING cyq_perf row count. Fail-closed (return 2) — a partial
    cyq_perf/moneyflow/stk_limit never enters a formal calendar_end.
  Verified live: endpoint_ready('20260703') -> (True, {daily 5516, moneyflow 5193, stk_limit
  7677}); assert_endpoints_complete('20260703') -> (False, cyq_perf=0) — correctly blocks until
  the catch-up's Stage D fills cyq_perf. report_rc completeness is enforced inside the catch-up
  (Stage E fails closed on an all-zero halo — see M2). --target-end override is validated by
  endpoint_ready AND must not exceed the computed ready target.

B2 (frozen-prefix audit blanket exceptions): FIXED. The audit script now honors THAW_MONTHLY_MODE
(the driver sets =1). In monthly mode the one-time first-thaw exceptions are DISABLED: the
IND_FIELDS/report_rc__* SHA-family approval branch and the sidecar suspension-healing approval
branch are both gated on `not MONTHLY_MODE`, so a recurring bump against the SETTLED parent must be
byte-identical (SHA) and membership-identical (sidecars) — any drift is a real regression, counted
in gross_sha_drift. Rationale: those exceptions were the first-thaw indicator-refetch + suspension
healing, already baked into the settled parent; a monthly rebuild re-materializes identical bytes.
A LEGITIMATE approved frozen-prefix correction (e.g. a provider-id-rotation like the share-capital
fix) is an out-of-band migration with its own gate, NEVER an automatic monthly bump. (I did NOT
build the full typed-diff_hash exception registry you sketched — for the monthly path, ZERO
exceptions is stricter and simpler than typed laundering; the historical exceptions remain only for
the standalone first-thaw run.)

M1 (feature-tree directory-only): FIXED. fresh_window_survivorship_audit now counts a code as
present only if features/<code>/ carries the FULL core price-bin set
REQUIRED_PRICE_BINS = open/high/low/close/vol/amount/adj_factor.day.bin (verified live: the
provider uses `vol`/`adj_factor`, not `volume`/`factor`). A dir missing any core bin is flagged
raw_price_not_in_feature_tree. (Bin LENGTH sanity — that each bin covers through target_end — is
NOT implemented; the frozen-prefix audit already checks prefix bin sizes and the rebuild
materializes full-calendar bins. Flagged as follow-up — tell me if you consider it blocking.)

M2 (report_rc halo can mark all-zero as done): FIXED. Stage E collects per-month row counts
(month_results) and, if the ENTIRE halo returns zero frames, RAISES RuntimeError (which fails the
catch-up subprocess -> the driver's check=True aborts the bump) unless --allow-empty-report-rc is
passed (for a verified-empty window only). A single legitimately-empty month within a non-empty
halo is fine.

m1 (raw_fetch_ts NaN-first rationale too narrow): FIXED. The dedup keeps na_position="first" (a
pre-instrumentation bootstrap row's NaN is the earliest-possible first-seen and wins over a today
re-fetch of IDENTICAL content). The comment now states precisely that such a NaN row CAN be
fresh-affecting via TTL carry, and why that is safe: the ledger quarantines a fresh-affecting row
missing BOTH create_time and raw_fetch_ts, and a CHANGED payload/create_time is a DISTINCT content
row that keeps its own (today) stamp. Added a regression test locking the dedup semantic.

EXTRA hardening (your round-2 stated #1 residual risk = "audited the wrong staged provider"): the
driver now, after the frozen-prefix audit, reads the audit artifact's `staged` field and asserts
it resolves to the SAME path as this bump's staged_provider — a passing audit against a stale
default tree is now impossible (THAW_STAGED_PROVIDER plumbing regression -> return 1).

RE-REVIEW QUESTIONS
1. Is the SPLIT endpoint gate (daily-fresh pre / cyq_perf + report_rc post) the correct resolution
   of B1 given cyq_perf's per-symbol lag, or do you still want cyq_perf probed pre-catch-up? Is
   MIN_ENDPOINT_ROWS=3000 (vs ~5000 normal) the right empty/partial floor, and is dropping
   northbound from the hard gate acceptable?
2. B2 strict monthly mode: is DISABLING all first-thaw exceptions (byte+membership identity) the
   right monthly contract, or do you require the full typed-diff_hash exception registry even for
   the recurring path? Any legitimate frozen-prefix change a monthly rebuild could produce that
   this would false-block? (My claim: a 2026 restatement's effective date lands in the fresh
   window, not the frozen prefix, so frozen-prefix bins stay byte-identical — is that right?)
3. M1: is the required-core-bin-set check sufficient, or is the bin-length-covers-target_end check
   load-bearing enough to block on now?
4. M2: is "raise iff the ENTIRE halo is zero frames" the right fail-closed threshold, or should a
   per-month zero (within a non-empty halo) also be suspicious? Is --allow-empty-report-rc a safe
   escape?
5. Any NEW hole from this round: the post-catch-up gate ordering (policy minted only after
   completeness passes); the audit-artifact staged-path assertion; the pyarrow row-count read;
   the THAW_MONTHLY_MODE plumbing.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
