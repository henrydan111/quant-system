# GPT 5.5 Pro re-review prompt — Phase 5 design v3.1 (Round 4, one-line clearing pass on M4)

Status: OPTIONAL final clearing pass. M4 was a doc-consistency fix applied verbatim from your R3 replacement text; the substance you already ruled ready. Send only if you want the SHIP on record.

---

```text
ROLE
Senior reviewer, A-share quant system. ROUND 4 — final clearing pass. In R3 you ruled B2 RESOLVED and raised exactly one Major, M4: the §9 implementation-deliverables checklist still carried the obsolete "report_date >= fresh_holdout_start" report_rc instruction, contradicting the already-approved availability-boundary rule in §5.1/§11 and risking reintroduction of the rejected guard during implementation. You gave verbatim replacement text. Confirm M4 is folded; nothing else is in scope.

REPO (raw may cache): https://github.com/henrydan111/quant-system (branch calendar-unfreeze)
Design v3.1: workspace/research/calendar_unfreeze/PHASE5_DESIGN.md (§9 deliverables, §12 R3 disposition)

WHAT CHANGED (the complete R3-fix delta — §9 report_rc bullet, replaced verbatim per your R3 text):
"report_rc fail-closed replay + availability-boundary 锚（B1+B2）: implement the FULL §5.1 step 3 rule, NOT the old report_date>=fresh_holdout_start boundary. Guard applies to any row/revision satisfying ANY of: report_date>=fresh_holdout_start; vendor_create_time>=fresh_holdout_start; raw_fetch_ts>=fresh_holdout_start; computed effective_date / active-carry interval intersects [fresh_holdout_start, target_end]. For those rows disable historical bulk-backfill; effective_date = next_open(max(report_date, vendor_create_time, first_seen_or_revision_seen_ts_floor)); maintain a revision ledger (natural key + payload digest [canonicalized over every field affecting PIT anchoring or materialized report_rc features] + create_time + first_seen + batch_id); no retrograde effective_date; replay halo >= REPORT_RC_ACTIVE_TTL_OPEN_DAYS=120 + vendor-lag/backfill guard; historical bulk-backfill kept ONLY for rows wholly outside the fresh/sealed window. Tests MUST cover 5 cases: pre-boundary report_date with fresh create_time/first-seen; TTL carry into fresh; payload revision; backward create_time; missing create_time quarantine/raw-fetch-floor."
Verified: the stale standalone §9 directive is gone; the remaining report_date>=fresh_holdout_start mentions are only condition 1 of the 4-condition guard and the disposition tables describing what was rejected. Your digest-scope note (canonicalize over feature-relevant fields) was also folded.

QUESTION: Is M4 fully resolved and the Phase-5 DESIGN ready to implement (SHIP)? Any residual only within this §9 delta.

OUTPUT: M4 RESOLVED / NOT; final line SHIP / REVISE / REWORK + single residual risk.
```
