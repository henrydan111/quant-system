# GPT 5.5 Pro review — Phase 5-B monthly_calendar_bump driver

Status: ready to send. Branch `calendar-unfreeze` HEAD `d4f3c74`. Raw may cache — embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. Review the Phase 5-B monthly calendar freeze-bump DRIVER — the recurring orchestration that keeps the thawed provider current. It packages the manual thaw Phase 1-4 (which already shipped) with a human sign-off gate. This is orchestration + two new audits, NOT §3-invariant surgery (that was Phase 5-A, SHIP'd). Focus: the new audits' correctness, the readiness/gate logic, and any survivorship/PIT hole.

REPO https://github.com/henrydan111/quant-system (branch calendar-unfreeze, HEAD d4f3c74)
File: scripts/monthly_calendar_bump.py ; tests: tests/data_infra/test_monthly_calendar_bump.py
Design of record: workspace/research/calendar_unfreeze/PHASE5_DESIGN.md §5 (5-B); self-review: PHASE5B_SELF_REVIEW.md

CONTEXT (design invariants the driver must honor):
- D3 §6: spent_oos_end STAYS 2026-02-27 across EVERY bump; only calendar_end advances, so the born-sealed fresh window [2026-02-28, calendar_end] grows monotonically. Releasing aged fresh data to discovery would be a Phase-6 SPEND event, never automatic.
- D1: each publish stamps a NEW append-only policy id; publish is fail-closed on a blank policy id.
- target_end must be the last COMPLETE trading day (endpoint readiness), never wall-clock — a partial day must not enter a formal provider.
- The frozen-prefix audit (bin byte-identity + calendar append-only + sidecar membership) AND a fresh-window survivorship audit both gate; the survivorship audit has NO blanket exceptions.
- Approved exceptions (frozen-prefix audit only) are typed/append-only/trend-reported; a type recurring two bumps in a row must become a permanent migration.
- publish is a §13 human-gated action; NEVER in the automated flow.
- Tushare code form is 000001.SZ; Qlib/provider form is 000001_SZ — a wrong conversion silently returns 0 matches.

WHAT THE DRIVER DOES (authoritative summary)

Modes: --plan (preflight + target_end + plan JSON, no execution) | --execute (catch-up -> new policy YAML -> full rebuild staged -> frozen-prefix audit + fresh-window survivorship audit -> dry-run report, STOPS before publish) | --publish-approved --i-reviewed-the-dryrun (§13 gate; the actual live swap/rebind defer to the proven depth9/sharecap scripts).

Key helpers (all unit-tested):
1. determine_target_end(now_cst, probe_daily): the latest open trading day (from trade_cal) that is past the LATEST required endpoint update hour (ENDPOINT_UPDATE_HOUR_CST = daily 16 / cyq_perf 19 / report_rc 22 / moneyflow 19) AND, if probe_daily is supplied, whose daily row count >= MIN_PLAUSIBLE_DAILY_ROWS (4000). Rolls back to the previous open day otherwise. Returns (target_end, evidence).
2. generate_thaw_policy(target_end, parent_build_id, write): append-only new policy id frozen_<target_end>_thaw_step<N> (N auto-increments from existing files); calendar_end/data_end = target_end; spent_oos_end = 2026-02-27 and fresh_holdout_start = 2026-02-28 are FROZEN constants; never edits an existing file.
3. fresh_window_survivorship_audit(provider_dir, fresh_start, target_end): builds the daily all_stocks membership matrix over the fresh window; for each fresh trading day, loads raw daily ts_codes, converts 000001.SZ -> 000001_SZ (.replace('.','_').upper()), and flags any raw-priced code ABSENT from all_stocks that day as a "raw_price_not_in_universe" violation. ok=False on any violation (or a missing raw daily file). NO blanket exceptions.
4. ExceptionRegistry (frozen-prefix audit only): typed append-only rows (exc_type, root_cause, dataset, symbols, date_range, gross/net diff, reviewer, expiry, evidence, diff_hash); forbids wildcard symbols/date_range; recurring_types() flags a type present in >=2 rows.

Tests (9): target_end rolls back pre-update-hour / rejects partial daily via probe / accepts a complete day; policy freezes spent_oos_end + parses via CalendarPolicy + append-only increment; exceptions reject wildcards + flag recurring; survivorship audit flags a missing universe member + passes when complete.

HONEST NOTES (routed to you):
- The publish leg is NOT auto-wired to the live swap/rebind — it enforces the review gate then points to the proven depth9/sharecap scripts. Rationale: auto-mutating the live provider through an execute path never yet run end-to-end is riskier than the proven manual path; wire it after the first --execute validates.
- referenced-build retention scan (the design's M3 retention) is NOT implemented — only a disk-floor check; parent_build_id is recorded in the report + policy notes. The full reference-store scan (approvals / 5 registries / seal / frozen-selection / deployment-gate) is a follow-up.
- The execute/publish heavy paths are code-complete but validated only at the unit level (helpers) + the --plan path; a full live bump would validate end-to-end.

REVIEW QUESTIONS
1. Survivorship audit (M2): is the raw-price-vs-all_stocks-membership check the right survivorship gate? Is the code-form conversion (000001.SZ -> 000001_SZ) complete for all A-share/BSE forms (.BJ, the 8xx/9xx BSE codes)? Does using all_stocks list/delist ranges correctly handle suspended-but-listed names (raw has no price row on a suspended day, so no false violation) vs genuinely-missing delisted names? Any way a real survivorship hole slips through?
2. target_end readiness (M1): is (past-latest-update-hour + daily row count >= 4000) sufficient to authorize a FORMAL target_end, or must each endpoint family be probed non-empty with an expected count? What fails if the daily endpoint is complete but cyq_perf/report_rc for that day is not yet published?
3. D3 freeze: is hardcoding spent_oos_end=2026-02-27 as a driver constant correct given the design freezes it permanently, or should it be read from the parent policy (and asserted equal)? Is the growing born-sealed window handled correctly (nothing in the bump touches [fresh_holdout_start, target_end] as a research surface)?
4. Gates: is the --publish-approved --i-reviewed-the-dryrun gate + deferring the live swap to proven scripts an acceptable §13 posture, or a governance gap? (The frozen-prefix audit now GATES: it runs against the new staged tree via THAW_STAGED_PROVIDER and its non-zero exit blocks the bump; the fresh-window survivorship audit likewise. Confirm this is correct.)
5. Any determinism / correctness / edge defect (the parent-policy end-date parse; empty fresh window; the membership searchsorted; the env-var staged-path plumbing to the audit script).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
