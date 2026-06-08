# Post-Implementation RE-CONFIRM (round 2) for GPT 5.5 Pro — report_rc P1 fixes

**Date:** 2026-06-08. **Repository:** https://github.com/henrydan111/quant-system (public).
**Branch:** `report-rc-p1-plumbing` (fixes at commit `2782ac4`).
**Scope:** your round-1 post-implementation review = **CHANGES-REQUIRED** with two must-fixes + one
correctness nit. All three were applied and verified against the live code, and 3 canaries were added.
This is a tight re-confirm: did each fix land correctly, did the fixes introduce anything new, and is it
now MERGE? Do not re-open settled design or the deferred Q5 (see bottom).

**Read (raw):**
- Updated code diff (now includes the fixes):
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-p1-plumbing/workspace/research/data_expansion/p1_report_rc_code.diff
- The module (build_ledger report_rc branch, `add_open_day_lag`, `_materialize_report_rc_consensus`):
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-p1-plumbing/src/data_infra/pit_backend.py
- Tests (10):
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-p1-plumbing/tests/data_infra/test_report_rc_ledger.py

## What changed since your round-1 review
1. **Q3 (PIT gap — create_time fallback).** New module helper `add_open_day_lag(dates, open_calendar,
   n)` (shifts by OPEN trading days via searchsorted, NOT `Timedelta`). The `report_rc` `build_ledger`
   branch now OVERRIDES the generic anchor: `observed = max(report_date, create_time)` row-wise, and for
   rows where `create_time` is null/absent, `observed = add_open_day_lag(report_date,
   REPORT_RC_VENDOR_LAG_OPEN_DAYS=2)`; then `effective_date = strictly_next_open_trade_day(observed)`.
2. **Q1 (event-flow order).** The revision block now `mergesort`s on
   `[qlib_code, normalized_analyst_id, quarter, effective_date, disclosure_date, report_date, create_time]`
   (all date cols `normalize_date_series`-coerced first) before `groupby(...).shift(1)` — so two forecasts
   that map to the same `effective_date` are ordered by true availability, not raw/ledger order.
3. **Q6 (quarter consistency).** Rows with missing/blank `quarter` are now dropped from the materializer
   BEFORE both the revision and the n_active computations (with an audit log line), so they can't be
   counted in `n_active` while excluded from revisions.

New tests (each FAILS on the pre-fix code; 10 report_rc tests total; 123 regression tests green):
- `test_report_rc_missing_create_time_uses_fixed_open_day_lag` — a null-`create_time` row anchors at
  `2020-01-06` (report 0101 + 2 open days → 0103 → next open 0106), NOT `2020-01-02`.
- `test_report_rc_same_effective_date_chronological_order` — two forecasts (1.0→1.5) visible the same day,
  written in REVERSE raw order, classify UP (not DOWN).
- `test_report_rc_missing_quarter_excluded` — `n_active == 1` (the no-quarter row excluded), not 2.

## Re-confirm questions
1. **Q3 fix correct?** Is `add_open_day_lag` right (off-by-one / calendar-end NaT / non-trading-day
   `report_date` rolling forward)? Does overriding `disclosure_date`+`effective_date` inside the branch
   (after the generic computation) cleanly win, and is `max(report_date, create_time)` the intended
   present-case anchor? Any case where `create_time` present-but-stale should still get the lag?
2. **Q1 fix correct + complete?** Do the added sort keys fully determinize the same-`effective_date`
   case? If `effective_date`, `disclosure_date`, `report_date` AND `create_time` all tie for one analyst/
   quarter (contradictory same-instant rows with different eps), order falls back to content order — is
   that residual acceptable for P1, or do you want a final stable content-hash tiebreak?
3. **Q6 fix correct?** Is dropping missing-quarter from both (vs sentinel-bucketing) the right P1 call?
4. **New issues?** Did any of the three fixes introduce a regression, leakage, or determinism gap?
5. **Verdict:** MERGE / MERGE-WITH-NITS / CHANGES-REQUIRED for the P1 plumbing branch.

## Deferred (do NOT re-raise as a P1 blocker)
Q5 (the `collapse_duplicate_versions` singleton-group fast path for full-history scale) is consciously
deferred: it's not P1-merge-blocking, the full provider build that would expose it is separately gated
NO-GO (pending the 2026-06-15 backfill canary), and touching that shared function warrants its own
review. Tracked in the commit message + project memory.
