# GPT 5.5 Pro re-review — Phase 5-A report_rc guard (Round 4, after M5+m6)

Status: ready to send. Branch `calendar-unfreeze` HEAD `6d43005`. Raw may cache — embedded delta authoritative.

---

```text
ROLE
Senior reviewer, A-share quant system, research validity > code that runs. ROUND 4 (clearing pass) of the Phase 5-A implementation review. Prior: R1 REWORK (B1/B2/M1/M2/M3, fixed, confirmed); R2 REWORK (B3 value-lookahead, M4) — B3 fixed via first-seen floor + payload-digest revision-preserving ledger, M4 RESOLVED; R3 REVISE ruled B3 PARTIALLY RESOLVED (M5: the digest covered only eps, but the provider ALSO materializes report_rc__np_fy1/op_rt_fy1/n_active_orgs/rating_up/rating_dn from np/op_rt/rating) + m6 (baseline sidecar written before the ledger). Both accepted. Verify M5 and m6; nothing else in scope.

REPO https://github.com/henrydan111/quant-system (branch calendar-unfreeze, HEAD 6d43005)
Touched: src/data_infra/pit_backend.py, tests/data_infra/test_report_rc_ledger.py

BACKGROUND: report_rc has TWO materializers — (1) eps event-flow (eps_up/dn/revision_count/n_active_analysts) and (2) rating/np/op_rt aggregate (np_fy1/op_rt_fy1/n_active_orgs/rating_up/rating_dn). Both sequence per (analyst/org, quarter) by effective_date. The revision-preserving ledger key = (ts_code, report_date, normalized_analyst_id, quarter, report_rc_payload_digest); org identity is already in the natural key via normalized_analyst_id = org::author.

WHAT CHANGED (the complete M5+m6 delta)

--- M5: digest covers every materialized value field ---
REPORT_RC_DIGEST_NUMERIC_COLS = ("eps", "np", "op_rt")
REPORT_RC_DIGEST_STRING_COLS = ("rating",)
def report_rc_payload_digest(work) -> Series:
    # numerics: to_numeric.round(6) -> format(float(v)+0.0, ".6f")  (+0.0 normalizes -0.0->0.0; NaN->"nan")
    # strings:  astype(string).fillna("").str.strip()
    # join with "|"; fillna("")
work["report_rc_payload_digest"] = report_rc_payload_digest(work)   # replaces the eps-only digest
# a comment + module constants mandate: add a field here in the same change that materializes a new report_rc__* feature from it.
# no-retrograde baseline key already includes report_rc_payload_digest (so a changed value = new revision identity = own first-seen; old value's min-effective preserved).

--- m6: baseline committed only after the ledger write ---
_report_rc_assert_no_retrograde(new_ledger) -> planned_baseline (checks retrograde, RETURNS the planned min-effective baseline; NO write; None on no-op)
_report_rc_commit_baseline(planned) -> atomic write (None -> skip)
# build_ledger:
planned = self._report_rc_assert_no_retrograde(ledger)   # report_rc only
ledger.to_parquet(output_path)                            # main ledger FIRST
self._report_rc_commit_baseline(planned)                 # baseline AFTER
# so a ledger-write failure cannot leave the baseline recording an unserved effective (a false future retrograde).

--- Tests (36 total; this round +5) ---
non_eps_revision_preserved[np|op_rt|rating] (same 4-key + same eps + changed np/op_rt/rating -> 2 distinct revisions, 2 digests); payload_digest_covers_materialized_fields (asserts {eps,np,op_rt,rating} <= digest cols — fails if a materialized field is added without extending the digest); digest_normalizes_negative_zero (-0.0 == 0.0 digest). Regression: 346 data_infra pass, PIT002 clean, all historical + 5->4 exact-dup-merge + the R3 restatement/materializer tests green.

HONEST NOTE (unchanged, routed to you): the current live provider's fresh report_rc was fetched WITHOUT raw_fetch_ts stamping, so those rows floor at max(report, create) until the next bump re-fetches with stamping (D3-sealed meanwhile; your R1 Q5 ruling). rating is digested as the stripped raw string (a synonym mapping to the same ordinal would be a spurious-but-conservative distinct revision) — is that acceptable or must the digest use normalize_rating_to_ordinal?

RE-REVIEW QUESTIONS
1. M5: does digesting {eps, np, op_rt, rating} (org already in the natural key) cover every field materialized into a report_rc__* feature? Is the coverage-guard test sufficient, or is there a materialized input I still miss (e.g. a field the n_active_orgs / rating direction logic reads)?
2. m6: does plan-then-commit-after-ledger-write close the ordering hazard? Any remaining window (e.g. the baseline read at check-time vs commit-time, or a partial ledger write)?
3. rating digest as stripped raw string vs normalized ordinal — acceptable (conservative) or a defect?
4. Any NEW defect from the M5/m6 delta.

OUTPUT FORMAT
- Per finding (M5, m6): RESOLVED / PARTIALLY / NOT with the exact gap.
- New issues Blocker/Major/Minor with quoted code + exact fix.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
