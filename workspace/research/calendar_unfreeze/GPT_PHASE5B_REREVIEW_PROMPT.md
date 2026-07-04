# GPT 5.5 Pro RE-review — Phase 5-B monthly_calendar_bump driver (post-REWORK)

Status: ready to send. Branch `calendar-unfreeze` HEAD `4cd2fec`. Raw links may cache — the embedded delta is authoritative; the raw links are pinned to the commit sha so they resolve exactly.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs.
You previously reviewed the Phase 5-B monthly calendar freeze-bump DRIVER and returned REWORK
with 7 findings (B1-B4 / M1 / M2 / m1). This is the RE-REVIEW: verify each fix is real, complete,
and introduces no new PIT/survivorship/determinism hole. Two additional correctness bugs were
caught and fixed during the rework (flagged below) — scrutinize those too.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 4cd2fec)
Files (raw, pinned to the commit):
- driver:  https://raw.githubusercontent.com/henrydan111/quant-system/4cd2fec/scripts/monthly_calendar_bump.py
- catchup: https://raw.githubusercontent.com/henrydan111/quant-system/4cd2fec/workspace/scripts/catchup_fundamentals_range.py
- frozen-prefix audit: https://raw.githubusercontent.com/henrydan111/quant-system/4cd2fec/workspace/scripts/audit_thaw_frozen_prefix.py
- tests: https://raw.githubusercontent.com/henrydan111/quant-system/4cd2fec/tests/data_infra/test_monthly_calendar_bump.py
         https://raw.githubusercontent.com/henrydan111/quant-system/4cd2fec/tests/data_infra/test_catchup_range_safety.py
Design of record: workspace/research/calendar_unfreeze/PHASE5_DESIGN.md §5 (5-B)
Self-review (REWORK round 2): workspace/research/calendar_unfreeze/PHASE5B_SELF_REVIEW.md

CONTEXT (unchanged design invariants the driver must honor):
- D3: spent_oos_end STAYS 2026-02-27 across EVERY bump; only calendar_end advances, so the
  born-sealed fresh window [2026-02-28, calendar_end] grows monotonically. Aging fresh data into
  discovery is a Phase-6 SPEND event, never automatic.
- D1: each publish stamps a NEW append-only policy id; publish is fail-closed on a blank id.
- target_end = the last COMPLETE trading day (endpoint readiness), never wall-clock.
- BOTH the frozen-prefix audit (bin byte-identity + calendar append-only + sidecar membership)
  AND the fresh-window survivorship audit GATE. The survivorship audit has NO blanket exceptions.
- publish is a §13 human-gated action; NEVER in the automated flow.
- Tushare code 000001.SZ; provider 000001_SZ. report_rc raw has report_date (YYYYMMDD) +
  create_time; per-year files report_rc_<year>.parquet already exist (2010..2026). Only the 2026
  file carries the Phase-5 raw_fetch_ts column; pre-2026 files predate that instrumentation.

HOW EACH REWORK FINDING WAS FIXED (verify real + complete + no new hole)

B1 (frozen-prefix audit ran with check=False + hardcoded path): the audit script is now
parameterized by THAW_STAGED_PROVIDER (points at the NEW staged tree) and exits 1 on any
violation; the driver runs it WITHOUT check and gates on `fp.returncode != 0` -> return 1 (blocks
the bump). Residual added this round: the dry-run report now records staged_provider_dir +
frozen_prefix_audit_ok + the audit artifact name + the report_rc halo start.

B2 (endpoint readiness incomplete / --target-end bypass / datetime.now not CST):
- now_cst() uses zoneinfo Asia/Shanghai (the vendor-update hours are CST).
- endpoint_ready(date) -> (ok, evidence): daily row count >= 4000 AND every per-day endpoint file
  (moneyflow, cyq_perf, northbound, stk_limit) exists for the day. report_rc is a window-anchored
  year-file covered by the past-hour-22 check, deliberately not in the per-day set.
- determine_target_end(now, *, probe_ready): rolls back until a day is past the latest update hour
  AND probe_ready passes. A formal execute REQUIRES probe_ready=endpoint_ready.
- --target-end override is validated: endpoint_ready(override) must pass AND it must not exceed the
  computed ready target (can't skip forward past incomplete days).

B3 (catch-up not range-safe / report_rc halo missing): the driver now passes the catch-up script
--report-rc-start (a PRE-boundary TTL halo = fresh_holdout_start - (120 open days + 45 cal days) =
20250712, which crosses into 2025), --report-rc-end, and --state-suffix=target_end. The catch-up
script (previously a one-time Phase-1 tool hardcoded to 2026 months 2-6 with range-insensitive
Stage C/E keys) is now range- and year-safe:
  - Stage E (report_rc): iterates months_spanned(rc_start, rc_end) clipped per month; partitions
    new rows by report_date year -> report_rc_<year>.parquet; state key E:report_rc:<rc_start>-<rc_end>.
  - Stage C (stk_holdertrade): partitions by ann_date year -> stk_holdertrade_<year>.parquet;
    state key C:stk_holdertrade:<start>-<end>.
  - Stage F (index_weights): months derived from months_spanned(start,end) (full-month snapshot).
  - --state-suffix scopes the resume-state FILE and the cyq buffer dir per bump, so a new window is
    never masked by a prior bump's `done` keys. The OTHER catch-up script (catchup_daily_range) is
    already per-date-keyed -> inherently range-safe, unchanged.

B4 (survivorship audit missing feature-tree check): fresh_window_survivorship_audit now, in
addition to raw-price-vs-all_stocks-membership, flags raw_price_not_in_feature_tree for any
raw-priced code absent from the provider features/<code>/ dir. ok=False on either violation.

M1 (json.loads on a YAML file = crash): the parent-policy regime guard now routes through the
typed load_calendar_policy(parent_policy). This ALSO fixed a bug I introduced when first patching
M1: yaml.safe_load parses `spent_oos_end: 2026-02-27` into a datetime.date, so a bare
`parent_body.get("spent_oos_end") != "2026-02-27"` string compare would ALWAYS be True and
false-refuse EVERY execute on the real policy file. The typed loader normalizes via str(...); the
guard asserts spent_oos_end == 2026-02-27 AND fresh_holdout_start == 2026-02-28 before minting a
child (a Phase-6 release policy must not be silently regressed into a bump parent). A test loads
the LIVE parent policy and asserts the normalized fields equal the constants.

M2 (recurring exceptions not gated): a frozen-prefix exception type present in >=2 rows BLOCKS the
bump (return 1) unless --allow-migration-exception is passed (recurrence must become a permanent
migration = note + tests, not a re-approval by count).

m1 (--publish-approved returned 0 for a no-op): --publish-approved now writes publish_handoff.json
(staged build/provider/policy/parent + the required manual §13 steps) and returns 3 (non-zero), so
no scheduler mistakes the manual handoff for a completed publish. The live swap/rebind/QA stay
deferred to the proven depth9/sharecap scripts (honest note below).

EXTRA correctness fix (not a REWORK finding — flag if you disagree): report_rc first-seen dedup.
The halo reaches pre-instrumentation year files (2010-2025) which have NO raw_fetch_ts column, so
concat yields NaN stamps for bootstrap rows. dedup now sorts na_position="first" + keep="first",
so a pre-instrumentation row (observed before we started stamping = earliest possible first-seen)
wins over a today re-fetch stamp. Zero effect on the 2026 file (all rows already stamped). Claim:
no PIT impact because the per-row raw_fetch_ts visibility floor only applies to FRESH-window rows
(>=2026-02-28), and no fresh row is ever NaN (the 2026 catch-up stamps every row).

HONEST NOTES (unchanged scope, routed to you):
- publish leg still NOT auto-wired to the live swap/rebind — it enforces the review gate + writes a
  handoff, then points to the proven depth9/sharecap scripts. Rationale: auto-mutating the live
  provider through an execute path not yet run end-to-end is riskier than the proven manual path.
- referenced-build retention is still only a disk-floor check; the full reference-store scan
  (approvals / 5 registries / seal / frozen-selection / deployment-gate) is a follow-up.
- execute/publish heavy paths are code-complete but validated only at the unit level + --plan; a
  full live bump is the first end-to-end validation.
- the halo re-fetches ~9 months of report_rc every bump (incl. long-settled history) — a deliberate
  correctness-over-efficiency choice to catch restatements, not a defect.

RE-REVIEW QUESTIONS
1. Are B2/B3/B4/M1/M2/m1 each REAL and COMPLETE fixes, or does any residual of the original finding
   remain? Specifically: does endpoint_ready close the "daily complete but cyq/report_rc not yet
   published" hole (B2)? Is the report_rc per-report_date-year partition correct for a halo crossing
   2025->2026 (B3)? Does the feature-tree check (B4) actually catch a feature-incomplete symbol, or
   is directory-presence too weak (should it check required bins)?
2. M1 date-object bug: is routing through load_calendar_policy the right fix, and is the
   spent_oos_end/fresh_holdout_start == constants regime assertion the correct D3 guard? Any other
   place a yaml.safe_load date-object vs string compare could silently mis-behave?
3. report_rc first-seen na_position="first": is the claim "no PIT impact because the floor only
   applies to fresh-window rows and no fresh row is NaN" correct? Could a carried-forward
   pre-boundary forecast (TTL into the fresh window) ever have its visibility affected by this?
4. New holes introduced by the rework? (the --target-end "not later than ready_target" compare;
   the year-partition groupby on a possibly-NaN report_date/ann_date; the m1 return-3 convention;
   the recurring-exception gate blocking a legitimate first-time exception.)
5. Determinism/edge: months_spanned/month_bounds across year and month-length boundaries;
   state-suffix scoping vs the shipped Phase-1 global state; the endpoint_ready per-day file-path
   convention (data/<sub>/<year>/<ep>_<date>.parquet).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
