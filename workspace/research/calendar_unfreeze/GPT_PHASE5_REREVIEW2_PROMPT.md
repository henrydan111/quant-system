# GPT 5.5 Pro re-review prompt — Phase 5 design v3 (Round 3, clearing pass on B2)

Status: ready to send AFTER `git push` of branch `calendar-unfreeze`. NOTE: GitHub raw/web caches — if you see Round-1/2 text, use the embedded delta below as authoritative (Round-2 minor m2 was exactly a raw-cache false alarm; the pushed HEAD already carried v2).

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is ROUND 3 — a narrow clearing pass on the Phase-5 design. History: R1 REVISE (1B+3M+1m, all folded) → R2 REVISE. In R2 you ruled M1/M2/M3/m1 RESOLVED (M1/M2 with implementation-precision notes, folded), B1 PARTIALLY RESOLVED — the anchor formula was right but the GUARD BOUNDARY was keyed too narrowly to report_date — and raised Blocker B2: the sealed boundary is an AVAILABILITY boundary, so a report_rc row with report_date < fresh_holdout_start but create_time/first-seen inside the sealed window (or carried in via the 120-trading-day active TTL) still slips through; plus retrograde create_time/payload revisions on already-seen keys. You also raised minor m2 (public branch still showed R1 text — this was GitHub raw caching; the pushed HEAD already had v2, verified). Your job now: verify B2 is fully folded and scan the delta for new issues. Do not re-litigate M1/M2/M3/m1/Q2.

REPO (public — raw MAY be cached; embedded delta authoritative)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Design v3: workspace/research/calendar_unfreeze/PHASE5_DESIGN.md (§11 = R2 disposition)
Self-review incl. Round-3 preflight: .../PHASE5_SELF_REVIEW.md
report_rc code: src/data_infra/pit_backend.py — REPORT_RC_ACTIVE_TTL_OPEN_DAYS=120 (L192, "a forecast counts as live for this many trading days", carried daily at L2888/2970/3117), REPORT_RC_BACKFILL_GAP_DAYS=45 (L286), the contemporaneous/backfill split + earlier-than-create_time WARNING (L2461-2486).

SELF-REVIEW PREFLIGHT (Round 3) — verdict "clean". I independently confirmed your B2: REPORT_RC_ACTIVE_TTL_OPEN_DAYS=120 is real (pit_backend.py:192) — a forecast dated ~120 trading days before the boundary is still carried INTO the fresh window, so the halo requirement is materializer-grounded; my R1 fix genuinely missed the availability-boundary semantics. I also confirmed m2 was a raw-cache false alarm: `git show HEAD:PHASE5_DESIGN.md | grep -c "report_date replay"` = 6 and HEAD == origin. All B2 fixes fold your exact replacement text.

WHAT CHANGED (authoritative — the complete R2-fix delta, §5.1 step 3 report_rc rule)

report_rc fresh-window guard WIDENED from "report_date >= fresh_holdout_start" to affects-the-fresh/sealed-window via ANY of:
  1. report_date >= fresh_holdout_start
  2. vendor_create_time >= fresh_holdout_start
  3. raw_fetch_ts >= fresh_holdout_start
  4. the row's computed effective_date OR active/carry-forward interval intersects [fresh_holdout_start, target_end]
For all such rows the historical bulk-backfill fallback is DISABLED; effective-date floor:
  effective_date = next_open(max(report_date, vendor_create_time, first_seen_or_revision_seen_ts_floor))
  where first_seen_or_revision_seen_ts_floor is required when the row/revision was absent from the prior eligible raw snapshot, create_time is missing, create_time moves backward, or the payload digest changes without a trustworthy later vendor timestamp.
REVISION LEDGER: keyed by stable natural key + payload digest + vendor_create_time + first_seen_raw_fetch_ts + ingest_batch_id. A replay may add a new revision but may NEVER move an existing revision's effective_date earlier; any retrograde effective-date movement is a build-blocking PIT error.
PRE-BOUNDARY HALO: replay from fresh_holdout_start - (REPORT_RC_ACTIVE_TTL_OPEN_DAYS=120 + vendor-lag/backfill guard) through target_end; a vague "documented overlap window" is insufficient.
HISTORICAL PRESERVED: the 2010-2021 bulk-backfill fallback is allowed ONLY for rows whose report_date, create_time/first-seen, effective_date, and active interval are ALL outside the fresh/sealed window; fresh_holdout_start is NOT the separator — "can this row/revision affect the fresh/sealed window" is.
DAILY FALLBACK: if the replay rule is not implemented, report_rc moves to a daily post-22:00 CST PURE-RAW job (--no-qlib semantics; NEVER the mode=update,publish=True incremental path → no build_id rotation) + the same fail-closed anchor + revision ledger.
Also folded (implementation-precision, R2): M1 readiness probe is a publish-BLOCKER not a warning; M2 fresh-window audit uses the §3.1 delist/IPO-lag list/delist bounds and FAILS on raw-price-vs-sidecar contradiction (not an approved exception).

RE-REVIEW QUESTIONS (Round 3)
1. B2: does the 4-condition availability guard + revision ledger (no retrograde effective_date) + halo>=TTL(120)+guard + first_seen floor fully close the availability-boundary leak? Any residual — e.g. a row whose active/carry interval intersects the fresh window but all four scalar conditions are individually pre-boundary (does condition 4 catch it), or a payload revision that keeps the same digest?
2. Historical separator: is "all of {report_date, create_time/first-seen, effective_date, active interval} outside the fresh/sealed window" the correct clean separator that preserves 2010-2021 behavior without leaking?
3. New-issue scan on the delta only.
4. Ready to implement (SHIP)?

OUTPUT FORMAT
- B2: RESOLVED / PARTIALLY RESOLVED / NOT RESOLVED with the exact remaining gap.
- New issues ranked Blocker / Major / Minor with offending text quoted + exact replacement.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
