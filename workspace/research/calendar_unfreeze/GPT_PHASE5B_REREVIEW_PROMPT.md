# GPT 5.5 Pro RE-review #3 — Phase 5-B monthly_calendar_bump driver (post-REWORK-3)

Status: ready to send. Branch `calendar-unfreeze` HEAD `971282a`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You
have reviewed this monthly calendar freeze-bump DRIVER three times (REWORK, REWORK, REWORK) and it
has converged each round. Round 3 (commit 68b0ee3) you confirmed m1 RESOLVED + the split endpoint
gate is the right architecture, and returned 2 Blocker + 2 Major + 1 minor. This RE-REVIEW #3
verifies those are real, complete, and hole-free. I corrected TWO of your suggested fixes for
concrete data reasons (bin-length format; coverage floor) — scrutinize those hardest.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 971282a)
Files (raw, pinned):
- driver:  https://raw.githubusercontent.com/henrydan111/quant-system/971282a/scripts/monthly_calendar_bump.py
- catchup: https://raw.githubusercontent.com/henrydan111/quant-system/971282a/workspace/scripts/catchup_fundamentals_range.py
- audit:   https://raw.githubusercontent.com/henrydan111/quant-system/971282a/workspace/scripts/audit_thaw_frozen_prefix.py
- tests:   https://raw.githubusercontent.com/henrydan111/quant-system/971282a/tests/data_infra/test_monthly_calendar_bump.py
           https://raw.githubusercontent.com/henrydan111/quant-system/971282a/tests/data_infra/test_catchup_range_safety.py
Self-review (round 4): workspace/research/calendar_unfreeze/PHASE5B_SELF_REVIEW.md

CONTEXT (unchanged invariants): D3 spent_oos_end frozen 2026-02-27; D1 append-only policy id;
target_end = last COMPLETE trading day; frozen-prefix audit + fresh-window survivorship audit both
GATE; publish §13 human-gated. Tushare 000001.SZ / provider 000001_SZ. Split endpoint gate:
daily-fresh endpoints (daily/moneyflow/stk_limit, same-day) gate target_end PRE-catch-up; the
LAGGING cyq_perf (per-symbol Stage-D fetch) + the report_rc halo verify POST-catch-up.

HOW EACH ROUND-3 FINDING WAS FIXED (verify real + complete + no new hole)

B1 (fixed row floor != endpoint completeness): FIXED with a COVERAGE ratio, not a row count. For
each endpoint, coverage = |endpoint_ts_codes ∩ daily_ts_codes| / |daily_ts_codes|, and it must
clear a per-endpoint floor. Floors set from a MEASURED complete day (2026-06-30): moneyflow 0.9415
(≈6% of daily names legitimately have no moneyflow) / stk_limit 1.00 / cyq_perf 1.00 -> floors
moneyflow 0.90, stk_limit 0.95, cyq_perf 0.95. MIN_ENDPOINT_ROWS=3000 remains ONLY as a cheap
empty/corruption guard, not the completeness criterion. (I did NOT use your 0.98 example — measured
moneyflow coverage is 0.94, so 0.98 would false-fail a complete day. Floors are below-observed but
far above any partial: an interrupted fetch drops coverage to ~0.5.) endpoint_ready (pre-catch-up)
gates daily-fresh coverage; assert_endpoints_complete (post-catch-up) adds cyq_perf coverage,
fail-closed before minting a policy. Live: endpoint_ready('20260703') -> True (moneyflow 0.9414,
stk_limit 1.0); assert_endpoints_complete -> False (cyq_perf 0.0, blocks until Stage D fills it).
Test added: 10 endpoint rows but DISJOINT names -> coverage 0.0 -> fails (rows-high/coverage-low).

B2 (#1 risk — frozen-prefix audit SAMPLED SHA 1-in-50): FIXED. In THAW_MONTHLY_MODE the audit
hashes EVERY bin's frozen prefix, not a 1-in-50 sample: `sample = MONTHLY_MODE or (si % SAMPLE_EVERY
== 0)`. The report records sha_mode="full" + sha_eligible, and a coverage assertion fires if
n_sha != n_eligible (proves no bin was left on the cheap size-only path). RUNTIME: full-hashing the
features subtree (~5.5M bins) is ~1h of I/O — acceptable for a monthly gate, progress-logged. (I
did NOT build a typed diff_hash exception registry; monthly mode has ZERO exceptions, which is
stricter. A legitimate frozen-prefix correction is an out-of-band migration.)

M1 (bin existence != coverage through target_end): FIXED by DECODING the Qlib bin header, not by a
size-vs-full-calendar check. Qlib .day.bin = float32[0]=start_index (calendar position of the first
value), float32[1:]=values, so a per-code bin spans [listing, last-data], NOT the whole calendar.
last_pos = start_index + nvalues - 1. For each raw-priced code on a fresh day, its close.day.bin
last_pos must be >= that day's provider-calendar position, else raw_price_bins_short_through_day.
(Your suggested fix `min_bytes = required_len*4` assumed bins span the full calendar — it would
false-flag EVERY post-2008 listing, whose start_index>0 makes the bin legitimately shorter than the
calendar. Verified live: 000001 close.day.bin last_pos == calendar end index 4492.)

M2 (halo month-level zero marked done): FIXED. Stage E collects per-month row counts and raises on
ANY zero-row month inside a non-empty halo, unless that month is whitelisted via
--allow-empty-report-rc-month YYYYMM[,YYYYMM]. The whole-window-zero case still raises unless
--allow-empty-report-rc. Test added (202602 throttled -> zero -> Stage E work() raises -> recorded
failed).

m1 (Stage-D zero-row cyq poisons resume state): FIXED. On a post-catch-up completeness failure the
driver calls _prune_cyq_state(target_end), deleting the D:cyq* / D:cyq_repartition keys from
catchup_fund_state_<target_end>.json so a rerun RE-FETCHES cyq_perf (a zero-row fetch from a late
endpoint was being marked 'done' and skipped on rerun, leaving the bump unrecoverable without
manual state deletion).

RE-REVIEW QUESTIONS
1. B1: is coverage-vs-daily with per-endpoint measured floors (mf 0.90 / stk 0.95 / cyq 0.95) the
   right completeness proof? Is comparing cyq_perf to the DAILY universe correct given cyq_perf may
   include recently-delisted names not in daily (over-coverage is fine; under-coverage is the risk)?
2. B2: is `sample = MONTHLY_MODE or (si%50==0)` + the n_sha==n_eligible assertion a complete
   removal of the sampling hole? Is the ~1h full-hash runtime acceptable, or do you want it
   parallelized / scoped to a bin allowlist before SHIP?
3. M1: is the header-decode last_pos check correct (vs your full-calendar-length assumption)? Any
   edge where a legitimately-short bin (a code that delisted mid-fresh-window, or is suspended
   through target_end) would false-flag? (It only checks days the code is RAW-PRICED on, so a
   suspended/delisted day has no raw row -> no check — is that the right scoping?)
4. M2: is "raise on any zero month unless whitelisted" the right threshold, or too strict for a
   sparse historical halo month? Is the per-month whitelist a safe escape?
5. Any NEW hole from this round: the coverage set-intersection (ts_code case/dtype); the
   _prune_cyq_state key match (D:cyq* prefix also catches D:cyq_repartition — intended); the
   full-SHA coverage assertion arithmetic; the bin-header struct unpack.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
