# GPT 5.5 Pro implementation-diff review — Phase 5-A report_rc availability-boundary guard

Status: ready to send. Branch `calendar-unfreeze` pushed (HEAD `993f80e`). Raw may cache — the embedded diff is authoritative.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead invalidates the research even if every test passes. This is an IMPLEMENTATION-DIFF review of Phase 5-A, which implements the report_rc availability-boundary guard whose DESIGN you already SHIP'd over 4 rounds (R1 B1 report_rc 45-day re-anchor lookahead; R2 B2 the guard key must be availability not report_date, verified REPORT_RC_ACTIVE_TTL_OPEN_DAYS=120 real; R3/R4 §9 consistency; SHIP). Now verify the CODE faithfully implements that design and introduces no new lookahead/determinism defect.

REPO (public; raw may cache — embedded diff authoritative)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze, HEAD 993f80e)
Touched: src/data_infra/pit_backend.py, tests/data_infra/test_report_rc_ledger.py, workspace/scripts/catchup_fundamentals_range.py
Design of record: workspace/research/calendar_unfreeze/PHASE5_DESIGN.md §5.1 step 3 + §9
Self-review: workspace/research/calendar_unfreeze/PHASE5A_SELF_REVIEW.md

BACKGROUND (the existing anchor, pit_backend.py build_ledger report_rc branch):
report_dt = report_date; create_dt = create_time (or NaT). gap = create - report (calendar days).
contemporaneous = create present AND 0<=gap<=REPORT_RC_BACKFILL_GAP_DAYS(45).
observed(default) = report_date + REPORT_RC_VENDOR_LAG_OPEN_DAYS(2) open days; contemporaneous rows -> max(report_date, create_time).
effective_date = strictly_next_open_trade_day(observed). key = (ts_code, report_date, normalized_analyst_id, quarter). Deep history (2010-2021, create_time=2022-05 bulk stamp, gap>>45) was VALIDATED PIT at report_date+2 vs the JoinQuant oracle — must stay unchanged.

WHAT CHANGED (authoritative diff)

--- 1. New constant ---
REPORT_RC_FRESH_HOLDOUT_START = "2026-02-28"  # frozen per design §6; MUST equal the live policy fresh_holdout_start

--- 2. Anchor block (build_ledger report_rc branch), added AFTER the existing contemporaneous logic ---
raw_fetch_dt = normalize_date_series(work["raw_fetch_ts"]) if "raw_fetch_ts" in work.columns else Series(NaT)
fresh = Timestamp(REPORT_RC_FRESH_HOLDOUT_START); create_norm = create_dt.dt.normalize(); fetch_norm = raw_fetch_dt.dt.normalize()
affects_fresh = (report_dt.norm >= fresh) | (create_dt.notna() & (create_norm >= fresh)) | (raw_fetch_dt.notna() & (fetch_norm >= fresh))
fresh_with_ct = affects_fresh & create_dt.notna()
  -> observed[fresh_with_ct] = max(report_date, create_time)          # disable backfill fallback for fresh rows
fresh_no_ct = affects_fresh & create_dt.isna()
fresh_no_ct_floored = fresh_no_ct & raw_fetch_dt.notna()
  -> observed[fresh_no_ct_floored] = raw_fetch_dt                      # first-seen floor
fresh_quarantine = fresh_no_ct & raw_fetch_dt.isna(); n_quarantined = fresh_quarantine.sum()
clean_era_large_gap now excludes affects_fresh (the pre-fresh 2023..boundary monitor is unchanged in spirit).
work["disclosure_date"]=observed; work["effective_date"]=strictly_next_open(observed)
# Build-BLOCKING guard:
served_fresh = fresh_with_ct | fresh_no_ct_floored
floor = max(create_norm, fetch_norm)
leak = served_fresh & floor.notna() & (effective_date.norm < floor)
if leak.any(): raise BuildGateError("... anchored earlier than visibility floor ...")
if n_quarantined: work = work.loc[~fresh_quarantine]   # drop quarantined fresh-no-ct rows

--- 3. New method _report_rc_assert_no_retrograde(new_ledger, output_path), called in build_ledger right before ledger.to_parquet, gated dataset=="report_rc" ---
If prior ledger file exists and carries [ts_code, report_date, normalized_analyst_id, quarter, effective_date]:
  merge new vs prior on the 4-key; for keys in both, fresh_scope = (new effective_date >= fresh) | (report_date >= fresh);
  retrograde = fresh_scope & (new effective_date < prior effective_date); if any -> raise BuildGateError("retrograde revision = sealed-window lookahead").
First build / pre-guard prior schema -> no-op. Historical keys (both dates pre-boundary) exempt.

--- 4. catchup_fundamentals_range.py stage E (report_rc fetch) ---
Stamp new["raw_fetch_ts"] = wall-clock now; merge old+new; dedupe on CONTENT (every column except raw_fetch_ts) keeping the EARLIEST raw_fetch_ts (sort ascending, NaN last, keep=first). So a changed payload OR create_time is a distinct revision keeping its own first-seen stamp; a re-fetch never moves an existing content row's stamp later.

--- 5. Tests (8 new in test_report_rc_ledger.py; 14 existing historical tests unchanged & green) ---
fresh_late_arrival_anchors_on_create_time_not_report_date (THE B2 leak: report_date 2026-01-05 + create_time 2026-03-10 gap 64 -> anchored 2026-03-11 NOT 2026-01); fresh_contemporaneous_anchors_normally; fresh_missing_create_time_quarantined; historical_backfill_unchanged_by_fresh_guard; no_retrograde_blocks_earlier_effective; no_retrograde_allows_later_effective; historical_retrograde_not_blocked; fresh_missing_ct_rescued_by_raw_fetch_ts. Regression: 130 backend/canary/registry/share-capital green; PIT002 lint clean.

REVIEW QUESTIONS
1. PIT correctness: does the anchor block close the B1/B2 leak for EVERY fresh-affecting case, and does it leave the validated deep-history path (2010-2021 backfill, and 2023..2026-02-27 pre-fresh clean era) byte-unchanged? Any row that could still be anchored earlier than its true first-visibility?
2. No-retrograde guard: is "prior ledger = first-seen baseline, block earlier effective_date on fresh keys, exempt historical keys" sound? Edge cases: a key that legitimately disappears then reappears; a key present in prior with NaT effective; report_date parse for the fresh_scope; a full rebuild vs incremental.
3. raw_fetch_ts: (a) is consuming it in the ledger while it is written only forward (historical rows lack it) safe and non-lookahead? (b) the stage-E content-dedupe keeping earliest stamp — correct first-seen semantics, or a hole (e.g. NaN handling for pre-stamp rows, or a vendor column change breaking content_cols)? (c) should REPORT_RC_FRESH_HOLDOUT_START assert-equal the live policy fresh_holdout_start at build time rather than being a bare constant?
4. Determinism / correctness: any nondeterminism (sort stability, NaN comparisons producing False silently masking a leak), the quarantine drop reindexing, or the build-blocking guard being reachable/unreachable.
5. Scope: is deferring the pre-boundary replay HALO (fetch from fresh - 120 open days) to the monthly-bump fetch step (5-B) acceptable, given the anchor guard + no-retrograde are in the ledger now? The current live provider's fresh report_rc still carries the OLD anchor but is D3-sealed — is "correct at next bump" the right call, or must the fresh report_rc be re-materialized now?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
