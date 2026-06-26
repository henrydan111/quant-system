# GPT §10 POST-IMPLEMENTATION review packet — report_rc consensus materializer (P2 + P3)

> The DESIGN passed §10 R1→R4 SHIP. This is the POST-IMPL code review of P2 (registry refactor) + P3
> (materializer + tests) against that SHIP'd design, BEFORE P4 (publish + standing canary). Branch
> `report-rc-registration` pushed (commit ccf1767); all raw links are live. Paste the block into GPT-5.5 Pro.

## What landed (P2 + P3)
- **P2 (commit 9b9bafb):** field_status.yaml report_rc block `field_prefixes: $report_rc__` → EXPLICIT 4
  fields + 5 separate single-field QUARANTINE entries + 3 registry tests (future_probe fail-closed,
  consensus quarantine, no-duplicate). 52 field_registry + 103 governance tests pass.
- **P3 (commit ccf1767):** `_materialize_report_rc_aggregates` + `normalized_org_id` +
  `RATING_CHANGE_WINDOW_OPEN_DAYS` + hook wiring; 10 new tests (FY1 roll/expiry, latest-per-org median +
  missing-value, distinct-org, the supersede rating state machine) + 50 pass with core PIT/ledger (no
  regression). Real-data sandbox: 茅台 np_fy1 ~906亿 / 44 orgs, 平安 ~1431亿 (realistic).

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A lookahead invalidates the result even if every test passes. This is a POST-IMPLEMENTATION review: the design already passed §10 (R1->R4 SHIP). Judge whether the CODE faithfully implements that design and is PIT-correct, BEFORE the data is published. Be skeptical; surface blockers.

REPO (public — fetch any file to verify against live code; branch report-rc-registration)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/<path>

READ:
- The SHIP'd design (v4, authoritative spec):
  .../workspace/research/data_expansion/REPORT_RC_CONSENSUS_RATINGS_PLAN.md
- The materializer + helpers (the implementation under review): src/data_infra/pit_backend.py
  -> normalize_rating_to_ordinal / is_real_rating / normalized_org_id / RATING_CHANGE_WINDOW_OPEN_DAYS (~L175-230);
  -> _materialize_report_rc_aggregates (the new method, search the name); the hook (search "report_rc aggregates").
  -> mirror reference: _materialize_forecast_growth (PIT income _inc_asof) + _materialize_report_rc_consensus (the TTL sweep).
- The registry refactor: config/field_registry/field_status.yaml (report_rc block + 5 report_rc_* quarantine entries)
- The tests: tests/data_infra/test_report_rc_aggregates.py (10) + tests/data_infra/test_field_registry.py (the 3 report_rc tests)
- CLAUDE.md (PIT §3.2, formal-run governance §3.4, research integrity §7)

SELF-REVIEW PREFLIGHT — verdict CLEAN FOR POST-IMPL GPT. Implements the SHIP'd v4 design: FY1=(latest disclosed annual FY)+1 via income searchsorted (strict PIT, mirrors _materialize_forecast_growth._inc_asof); active window 0<=p-effective_pos<=TTL (option-b, matches the existing sweep); per-forecast TTL-EXPIRY recompute events (a stale forecast -> NaN); latest-per-org median, missing-metric excludes the org; UNIFIED per-org supersede walk for coverage + direction (a '无'/blank report ends coverage; unknown-real clears direction but keeps coverage; reaffirm holds prior state to its ORIGINAL expiry; no upgraded-then-X double-count). normalized_org_id strips trailing legal suffixes but NOT (香港). 5 fields QUARANTINE (per-field entries). Reads ledger effective_date only (already create_time/+2 anchored). Tests + real-data sandbox pass. Residual: the standing OUTPUT canary + provenance + formal-gate canary tests are P4 (not in this diff); per-field promotion happens only after the canary.

WHAT TO CHECK (PIT FIRST)
1. NO-LOOKAHEAD: in _materialize_report_rc_aggregates, does any served value at calendar position p use a report/income row not visible as-of p? Specifically: (a) FY1's income searchsorted(effs_tab, cal_arr[p], side='right')-1 — can a future annual leak in? (b) the active mask (a_pos<=p)&(a_pos>=p-ttl); (c) the event-range fill [p, next_event); (d) the org state-machine intervals [pos, min(expiry, next_report_pos)). The factor layer adds Ref(,1) on top.
2. FAITHFUL TO DESIGN: does the code match the SHIP'd v4 spec for FY1 roll, TTL expiry (e+TTL+1), the supersede coverage (n_active_orgs = org's LATEST report within TTL is a real rating), and the no-double-count? Any deviation?
3. CORRECTNESS TRAPS: latest-per-org via chronological pre-sort + dict-last-wins (is the sort key sufficient?); np.median on a python list (NaN already filtered); float32 on ~1e5-1e6 万元; searchsorted side conventions; the reaffirm branch carrying (recs[-1][2], recs[-1][3]); pre-c0 forecasts (a_pos clamped to 0); the interval half-open [a,b) vs the existing inclusive sweep.
4. REGISTRY (P2): does dropping field_prefixes + 5 single-field quarantine entries + the future_probe/no-duplicate tests fully close the wildcard, with the 4 eps_diffusion fields still approved? Is _find_dataset's explicit-over-prefix precedence honored?
5. TESTS: are the 10 aggregates tests sufficient + honest (do they actually exercise the supersede/expiry/roll edges, not just the happy path)? What test is MISSING that you'd require before publish?
6. Anything that should BLOCK P4 publish.

OUTPUT FORMAT
- Issues Blocker / Major / Minor, each mapped to the principle/invariant, with the offending symbol + an exact fix.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
