# GPT 5.5 Pro re-review — Phase 5-A report_rc guard (Round 3, after B3 full fix)

Status: ready to send. Branch `calendar-unfreeze` HEAD `aef26c6`. Raw may cache — embedded delta authoritative.

---

```text
ROLE
Senior reviewer, A-share quant system, research validity > code that runs. ROUND 3 of the Phase 5-A implementation review. Round 1 REWORK (B1 carry, B2 fresh-to-prefresh, M1 guard floor, M2 baseline, M3 boundary) — all fixed, you confirmed B1/B2/M1 RESOLVED in Round 2. Round 2 REWORK raised B3 (value lookahead: a same-4-key payload revision keeps the same effective and backdates the new value; the min-effective baseline missed it because effective didn't move) and M4 (policy assertion publish-only). I CONCEDED my Round-2 preflight argument was wrong (I conflated date-visibility with value-visibility). The user chose the FULL revision-preserving fix (not the conservative fail-closed floor alone). Verify B3 and M4; nothing else in scope.

REPO https://github.com/henrydan111/quant-system (branch calendar-unfreeze, HEAD aef26c6)
Touched: src/data_infra/pit_backend.py, tests/data_infra/test_report_rc_ledger.py
Self-review (Round-3 preflight): workspace/research/calendar_unfreeze/PHASE5A_SELF_REVIEW.md

BACKGROUND: report_rc ledger key WAS (ts_code, report_date, normalized_analyst_id, quarter); collapse_duplicate_versions picks one winner per key (later disclosure), so a same-key value restatement (eps 1.00 -> 1.40) collapsed to one row and backdated the new value. The materializer _materialize_report_rc_consensus sequences per (qlib_code, normalized_analyst_id, quarter) sorted by effective_date, computing eps_up/eps_dn via shift(1), and carries n_active for REPORT_RC_ACTIVE_TTL_OPEN_DAYS=120 open days.

WHAT CHANGED (the complete B3+M4 delta)

--- 1. first-seen floor (anchor + guard) ---
served_fresh = affects_fresh & (create_dt.notna() | raw_fetch_dt.notna())
fresh_quarantine = affects_fresh & create_dt.isna() & raw_fetch_dt.isna()   # dropped fail-closed
visibility_floor[served_fresh] = max(report_dt, create_dt, raw_fetch_dt)     # NaT-safe max
observed[served_fresh] = visibility_floor
effective_date = strictly_next_open(observed)
# raw_fetch_ts is the FIRST-SEEN stamp (stage-E keeps EARLIEST per content), NOT the current fetch -> a stable row (first-seen ~ create) is not inflated (M1 stays fixed); a late-observed row / value revision (changed payload = distinct content = its own later first-seen) is floored at first-seen.
# guard: leak = served_fresh & vfloor.notna() & (effective_date < vfloor) -> BuildGateError (same per-row floor as the anchor).

--- 2. payload_digest in the ledger key (revision preservation) ---
work["report_rc_payload_digest"] = to_numeric(eps).round(6) -> "%.6f" (or "nan")   # covers every field materialized into a report_rc__* feature (currently eps; comment says expand when a new field becomes a feature)
key_columns = (ts_code, report_date, normalized_analyst_id, quarter, report_rc_payload_digest)
work = work.sort_values("effective_date").drop_duplicates(subset=key_columns, keep="first")   # MIN first-seen per revision identity: re-observing the SAME value never delays it; a CHANGED value is a distinct identity at its own later first-seen
# collapse_duplicate_versions then runs on the (now-unique) key -> no-op; exact-duplicate rows share the digest and still merge (the 5->4 test stays green).

--- 3. no-retrograde baseline re-keyed to the revision identity ---
key = (ts_code, report_date, normalized_analyst_id, quarter, report_rc_payload_digest)   # a changed value is a NEW identity (own first-seen); the old value's min-effective is preserved; a same-identity re-date earlier is caught. append-only min-effective baseline + (new | baseline | carry) fresh scope unchanged.

--- 4. M4 policy assertion for staged builds ---
The load_calendar_policy + _assert_report_rc_boundary_matches_policy now runs for ANY build given a non-blank calendar_policy_id (staged/dry-run too), before build_ledgers — not only publish. publish still requires a non-blank id.

--- 5. Tests (31 total; this round +5) ---
fresh_late_first_seen_floors_value_at_raw_fetch; fresh_stable_row_not_inflated_by_first_seen; staged_build_asserts_policy_boundary; value_restatement_preserved_as_distinct_revision (eps 1.00 seen March + eps 1.40 seen July -> 2 ledger rows at distinct effectives, restated value NOT backdated); restatement_materializes_up_event_at_first_seen (the eps_up feature fires at July first-seen, NOT March). Regression: 341 data_infra pass, PIT002 clean, the 14 pre-existing historical (2020/2022) tests + the 5->4 exact-dup-merge test all green.

HONEST NOTES (route to you, not unilaterally decided):
- The current live provider's fresh report_rc was fetched WITHOUT raw_fetch_ts stamping, so those rows floor at max(report, create) (the residual) until the next bump re-fetches with stamping (D3-sealed meanwhile; your Round-1 Q5 ruling).
- payload_digest covers eps (the only currently-materialized value); the comment mandates expanding the set when a new report_rc__* feature field is added.

RE-REVIEW QUESTIONS
1. B3: does (first-seen floor) + (payload_digest revision key + min-first-seen dedup) + (revision-identity no-retrograde) fully close the value-lookahead, end to end through the materializer? Is min-first-seen (keep earliest effective per revision identity) correct, or is there a case where the LATER observation should win? Is digesting over eps only (with the "expand when materialized" comment) acceptable, or must the digest cover fields not yet materialized?
2. Determinism/correctness: the sort_values+drop_duplicates(keep=first) min-first-seen dedup — stable and deterministic? Any interaction with collapse_duplicate_versions running afterward (now a no-op on unique keys) that could reorder or drop? The digest format ("%.6f") — any float-canonicalization hazard (e.g. -0.0, rounding at 6dp merging genuinely different forecasts)?
3. M4: is asserting on any calendar_policy_id (staged + publish) the right scope? Any build path that should NOT assert?
4. Any NEW defect from the revision-preserving change (materializer double-counting n_active across the two revisions of the same analyst/quarter; the extra ledger column breaking a downstream consumer; the 5->4 dedup semantics).

OUTPUT FORMAT
- Per finding (B3, M4): RESOLVED / PARTIALLY / NOT with the exact gap.
- New issues Blocker/Major/Minor with quoted code + exact fix.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
