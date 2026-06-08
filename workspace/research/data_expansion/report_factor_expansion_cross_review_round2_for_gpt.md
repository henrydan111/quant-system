# Cross-Review ROUND 2 for GPT 5.5 Pro — Report-Factor Expansion DESIGN **v2**

**Date:** 2026-06-08.
**Repository:** https://github.com/henrydan111/quant-system (public).
**Scope:** RE-REVIEW the design after your Round-1 "GO-with-conditions" was actioned. Your round-1
review was excellent and is fully accepted: **all four repo-specific traps you flagged were verified
true against the live code** (line cites below), and the plan was rewritten to **v2** to incorporate
every condition. We want you to (A) confirm each fix landed *correctly*, (B) adjudicate the design
decisions v2 now commits to, and (C) catch anything v2 got wrong or newly introduced.

**Read first (raw):**
- **v2 plan (under review):**
  https://raw.githubusercontent.com/henrydan111/quant-system/report-factor-expansion-review/workspace/research/data_expansion/report_factor_expansion_plan.md
- Backend precedent (`_materialize_stk_holdertrade` ~L2340, hook ~L2829; `PERIODIC_LEDGER_DATASETS` L88):
  https://raw.githubusercontent.com/henrydan111/quant-system/main/src/data_infra/pit_backend.py
- Namespace test (the constraint that blocks reusing the prefix map):
  https://raw.githubusercontent.com/henrydan111/quant-system/main/tests/data_infra/test_event_like_daily_namespace.py
- Browse any other file in the public repo to verify against real code.

---

## Part A — confirm the Round-1 conditions were resolved correctly
| R1 condition | v2 resolution (verify it's right) |
|---|---|
| A2′ not A1; declare event-flow vs active-latest | v2 **commits to EVENT-FLOW EPS-revision breadth**, renames the field accordingly, and defers active-latest (needs backend state/cancellation primitives or A1). §3. |
| Fix the broken A2 formula (`Sum(active,W)` denom; no per-analyst dedup) | v2 factor = `Ref((Sum($eps_up,W) − Sum($eps_dn,W)) / Max(Sum($eps_revision_count,W), MIN_N), 1)` + min-evidence gate. §3. |
| `Count` is broken → `Sum(If)` | adopted in §3 + the catalog rule. |
| Wiring: add to `PHASE3_DATASETS` + `PERIODIC_LEDGER_DATASETS`, explicit `materialize_provider` hook | §1 T1/T3 + §2 + §9-P1. |
| Don't reuse `EVENT_LIKE_DAILY_FIELD_PREFIX`; write `report_rc__*` directly + register `$report_rc__` quarantine | §1 T2 + §2. |
| FY1 = first-visible annual ACTUAL from PIT statement ledgers, roll on first-visible; FY-roll ≠ revision | §4. |
| Anchor = `max(next_open(report_date), vendor-lag)`; quarantine until canary | §5. |
| 3-layer parity + negative PIT canaries (not parity alone) | §6 + the 3-analyst adversarial fixture. |
| Pre-registered kill manifest + anti-mining gates | §7. |
| Per-event primitives, NaN not zero-fill, min-count gates; defer tp/rating | §3 + §8. |
| Plumbing-PR-first, acceptance = canaries+parity not IC | §9-P1. |

**Q-A1:** does any fix above only *appear* resolved but is still wrong/incomplete as written in v2?

## Part B — adjudicate v2's committed decisions
1. **Event-flow as the primary signal.** v2 abandons "consensus" and ships event-flow revision breadth.
   Is that the right primary, or is event-flow so dominated by high-coverage names / double-counting
   prolific analysts that it's not worth shipping without the active-latest (one-vote) version? If the
   latter, is the right move to build the backend state/cancellation primitives now rather than defer?
2. **`MIN_N` and the min-evidence gates** (`Sum(revision_count,W) ≥ 3`, `n_active ≥ 2`). Right values /
   right place (factor expression vs screen filter)? Does gating inside the Qlib expression interact
   badly with cross-sectional ranking (e.g., gated-out names become NaN and silently shrink the universe)?
3. **FY1 first-visible coupling.** §4 makes report_rc factors depend on the income/indicators PIT ledgers'
   first-visible annual-actual dates. Is that cross-dataset coupling sound, or does it import those
   ledgers' own edge cases (restatements, missing annuals, non-Dec fiscal ends) into the analyst field?
4. **`normalized_analyst_id` (new open item §10.3).** The per-analyst state machine hinges on a stable
   identity from messy `org_name`/`author_name` (multi-author rows, name variants). How much does the
   signal's validity depend on getting this right, and what's the minimum defensible normalization for P1?
5. **Anchor `max(...)` when vendor ingestion-time is absent.** If `report_rc` rows carry no obtainable-at
   timestamp, v2 falls back to a "predeclared conservative lag." What lag, and decided how, without it
   becoming a tunable that contaminates the screen?

## Part C — new issues?
Anything v2 introduced or still misses: leakage in the event-flow primitives, the `coverage_init`
classification boundary, determinism of the state machine under same-day duplicates, the
`eps_fy1_dispersion` definition (std/|mean| blows up near zero EPS), or the parity oracle now spanning
two ledgers. Flag any.

## Consolidated questions
1. (A1) Any R1 fix that's only superficially resolved in v2?
2. (B1) Event-flow as primary — ship it, or build active-latest state primitives first?
3. (B2) `MIN_N`/min-evidence gates — values, placement, NaN-universe-shrink risk?
4. (B3) FY1 first-visible cross-ledger coupling — sound, or importing statement-ledger edge cases?
5. (B4) Minimum defensible `normalized_analyst_id` for P1; how load-bearing is it?
6. (B5) Conservative-lag choice when vendor time is absent — how to set it non-tunably?
7. (C) Any new leakage / determinism / definitional defect in v2?
8. Overall: GO / GO-with-conditions / NO-GO on the **P1 plumbing slice** as specified in §9.

*Round-1 verification note for your confidence: T1 confirmed (`build_ledgers` gates on
`PERIODIC_LEDGER_DATASETS` L2105; `stk_holdertrade` ∈ both sets L86/L101); T2 confirmed (namespace test
forces prefix-keys == dataset-set, L49-66); T3 confirmed (`materialize_provider` hard-calls
`_materialize_stk_holdertrade` L2829); T4 (`Count` broken) matches the repo's prior production fix.*
