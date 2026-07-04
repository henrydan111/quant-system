# GPT 5.5 Pro re-review — Phase 5-A report_rc guard (Round 2, after REWORK)

Status: ready to send. Branch `calendar-unfreeze` HEAD `c917414`. Raw may cache — embedded delta authoritative.

---

```text
ROLE
Senior reviewer, A-share quant system, research validity > code that runs. This is ROUND 2 of the Phase 5-A implementation review. In Round 1 you returned REWORK: B1 (affects_fresh omitted the active/carry-forward TTL intersection — a pre-boundary row whose 120-open-day carried state reaches the sealed window escaped the guard); B2 (no-retrograde scoped only on NEW effective/report_date, missing a prior-fresh key re-dated back before the boundary); M1 (the leak guard floor was always-on max(create_time, raw_fetch_ts), so a normal stamped row with raw_fetch_ts later than create_time tripped it and made the monthly build unpublishable); M2 (the revision baseline was the collapsed 4-key ledger, not an append-only revision-identity store — a quarantined-then-reappearing key lost its baseline); M3 (REPORT_RC_FRESH_HOLDOUT_START was a bare constant despite "MUST equal policy fresh_holdout_start"). All 5 accepted. Verify the fixes; nothing else in scope.

REPO https://github.com/henrydan111/quant-system (branch calendar-unfreeze, HEAD c917414)
Touched: src/data_infra/pit_backend.py, tests/data_infra/test_report_rc_ledger.py
Self-review (Round-2 preflight): workspace/research/calendar_unfreeze/PHASE5A_SELF_REVIEW.md

SELF-REVIEW PREFLIGHT (Round 2): all 5 findings verified real (M1: a normal stamped row DID trip the guard; B1: TTL=120 carry is real) and fixed. Two items I scoped explicitly and route to you (did NOT unilaterally expand): (a) M2 payload_digest/vendor_create_time/first_seen/ingest_batch_id full revision-identity keying is NOT implemented — I implemented a per-natural-key min-effective append-only baseline; my argument: the PIT-critical invariant is fresh-key effective_date monotonicity surviving drops (done); a payload revision that CHANGES effective is caught by that monotonicity; a payload revision that does NOT change effective is not a lookahead (visibility unchanged); so payload_digest is provenance/audit, not PIT-critical. (b) the replay halo (fetch from fresh-120) stays in the 5-B fetch step per your Round-1 Q5 ruling.

WHAT CHANGED (the complete REWORK delta)

--- B1: affects_fresh condition 4 (active/carry) ---
open_cal = self.open_calendar(); calendar_end = open_cal.max(); fresh_pos = searchsorted(open_cal, fresh, "left")
boundary_in_calendar = len(open_cal) and (fresh <= calendar_end)   # NEW GUARD: providers not spanning the boundary have no fresh window
if boundary_in_calendar:
    pre_eff = strictly_next_open(observed).normalize()             # pre-override anchor (historical logic)
    pre_pos = open_cal.get_indexer(pre_eff)
    effective_intersects_fresh = pre_eff.notna() & (pre_eff >= fresh) & (pre_eff <= calendar_end)
    active_carry_intersects_fresh = pre_eff.notna() & pre_pos>=0 & (pre_eff<=calendar_end) & ((pre_pos + REPORT_RC_ACTIVE_TTL_OPEN_DAYS) >= fresh_pos)
else: both = False
affects_fresh = (report>=fresh) | (create present & create>=fresh) | (raw_fetch present & raw_fetch>=fresh) | effective_intersects_fresh | active_carry_intersects_fresh

--- M1: single per-row visibility_floor for BOTH anchor and guard ---
has_ct = create_dt.notna()
fresh_with_ct = affects_fresh & has_ct; fresh_no_ct = affects_fresh & ~has_ct
fresh_no_ct_floored = fresh_no_ct & raw_fetch.notna(); fresh_quarantine = fresh_no_ct & raw_fetch.isna()
visibility_floor = NaT series; visibility_floor[fresh_with_ct] = max(report, create); visibility_floor[fresh_no_ct_floored] = raw_fetch
served_fresh = fresh_with_ct | fresh_no_ct_floored
observed[served_fresh] = visibility_floor[served_fresh]          # anchor at the floor (disable backfill fallback)
effective_date = strictly_next_open(observed)
# guard uses the SAME per-row floor (NOT max(create,fetch)):
leak = served_fresh & visibility_floor.notna() & (effective_date.norm < visibility_floor.norm); if leak.any(): raise BuildGateError
# fresh rows with neither create_time nor raw_fetch_ts -> quarantined (dropped)

--- B2 + M2: append-only min-effective baseline sidecar ---
_report_rc_baseline_path() = ledger dir / report_rc.revision_baseline.parquet  (schema: 4-key + min_effective_date)
_report_rc_assert_no_retrograde(new_ledger):
  new_df = new_ledger[4key + effective_date].normalize().dropna(effective_date)
  if baseline exists:
     merged = new_df.merge(baseline, on 4-key, inner)
     _affects_fresh(eff) = (eff >= fresh) | (carry: open_cal.get_indexer(eff)+TTL >= fresh_pos)   # when calendar spans boundary
     fresh_scope = _affects_fresh(new_eff) | _affects_fresh(baseline_min_eff) | (report_date >= fresh)
     retrograde = fresh_scope & baseline_min.notna() & (new_eff < baseline_min); if any: raise BuildGateError
  # then update append-only: baseline = groupby(4-key).min(effective) over old-baseline UNION new  (never drops keys)
Called in build_ledger before ledger.to_parquet.

--- M3: boundary == policy assertion ---
_assert_report_rc_boundary_matches_policy(policy, id): if policy.fresh_holdout_start present and != REPORT_RC_FRESH_HOLDOUT_START -> BuildGateError. Called in run() right after the publish-time load_calendar_policy, BEFORE build_ledgers. Legacy frozen policy (no field) skips.

--- Tests (26 total, 9 new) ---
carry_into_fresh_forces_availability_anchor (report 2026-01-05 + create 2026-02-20 gap46 + carry -> anchored 2026-02-23 not Jan); deep_history_no_carry_keeps_backfill_anchor (report 2025-06-02, carry doesn't reach -> report+lag); fresh_late_arrival; fresh_contemporaneous; fresh_missing_ct_quarantined; fresh_missing_ct_rescued_by_raw_fetch_ts; no_retrograde_blocks_earlier / allows_later / historical_not_blocked; no_retrograde_blocks_fresh_to_prefresh; no_retrograde_survives_disappear_reappear; boundary_policy_mismatch_raises. Regression: 336 data_infra pass, PIT002 clean, all 14 pre-existing historical (2020/2022) tests green.

RE-REVIEW QUESTIONS
1. B1: does condition 4 (effective + active-carry intersection, guarded on fresh<=calendar_end) fully close the carry-into-sealed-window leak? Is the fresh<=calendar_end guard correct (a provider not spanning the boundary has no fresh window), or does it hide a case? Is pre_pos+TTL>=fresh_pos the right carry test (vs also needing pre_pos<=fresh_pos, which effective_intersects already covers via the OR)?
2. M1: is the single per-row visibility_floor (create_time for ct rows; raw_fetch only when create absent) correct and consistent anchor<->guard? Any row where the floor is wrong?
3. B2+M2: does the append-only min-effective baseline + (new OR baseline OR carry) fresh scope close both the fresh-to-pre-fresh retrograde AND the disappear-reappear case? Is min-effective (vs last-served) the right monotone floor? Is my scoping of the full payload_digest revision-identity ledger to "provenance, not PIT-critical" (argument in the preflight) acceptable, or is there a lookahead that only the payload-digest keying catches?
4. M3: assertion placement (before build_ledgers, publish-time only) adequate? Should non-publish staged builds also assert?
5. Any NEW defect introduced by the rework (determinism, NaN-comparison masking, the baseline sidecar write path, get_indexer on non-open dates).

OUTPUT FORMAT
- Per finding (B1, B2, M1, M2, M3): RESOLVED / PARTIALLY / NOT with the exact gap.
- New issues Blocker/Major/Minor with quoted code + exact fix.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
