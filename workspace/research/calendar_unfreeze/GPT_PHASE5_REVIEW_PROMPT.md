# GPT 5.5 Pro cross-review prompt — Phase 5 steady-state update mechanism (design stage)

Status: ready to send AFTER `git push` of branch `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, do not rubber-stamp.

CONTEXT — the calendar unfreeze is DONE through Phase 4:
The trading calendar was frozen at 2026-02-27 during system construction. A 3-round-SHIP design plan + a 5-round-SHIP implementation of a "pre-publish wall" thawed it: the live Qlib provider now runs to 2026-07-01 under policy frozen_20260701_thaw_step1. The wall's core is D3 "born-sealed": post-2026-02-27 data physically EXISTS in the provider, but both sanctioned research doors (pit_research_loader sandbox, qlib_windowed_features formal) mechanically clamp default reads to the spent-OOS boundary spent_oos_end=2026-02-27 — a read past it fails closed unless a holdout seal is claimed. This was verified live. The three design decisions the whole effort rests on:
  D1 no-global-policy: each publish stamps a NEW append-only policy id; historical artifacts replay against their recorded policy; publish's calendar_policy_id param is required with no default.
  D2 cadence: daily raw-layer sync + monthly controlled provider rebuild/publish (because every publish rotates provider_build_id and forces a 25-approval rebind ceremony — daily publish is unsustainable).
  D3 born-sealed: the post-2026-02-27 window is reachable only via a holdout seal; spent_oos_end is the mechanical clamp.

REPO (public — raw fetch may fail; the embedded design is authoritative)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Design doc: workspace/research/calendar_unfreeze/PHASE5_DESIGN.md
Self-review: workspace/research/calendar_unfreeze/PHASE5_SELF_REVIEW.md
Parent plan: workspace/research/calendar_unfreeze/UNFREEZE_PLAN.md

SELF-REVIEW PREFLIGHT — verdict "clean for GPT"; checked §3 invariants + all 9 quantitative-research principles. No invariant violated (data-ops design, no engine/strategy change). The two items I did NOT decide unilaterally and explicitly route to you: (a) whether freezing spent_oos_end at 2026-02-27 across monthly bumps creates an unacceptable "data present but unusable for months" tension (§7 Q2 — a potential D3-semantics weakening); (b) whether monthly catch-up of the daily-uncovered datasets (cyq_perf, report_rc) risks missing create_time/update_flag late-arriving rows vs daily ingest (§7 Q5 — the only PIT concern). Fixes made during self-review: folded the daily-updater coverage gap (suspend_d/cyq_perf/report_rc/stk_holdertrade/namechange/stock_st_daily NOT in the daily path) into the dataset assignment; vetoed "daily touches provider" after confirming the incremental path rotates build_id every run.

WHAT CHANGED (authoritative — design doc, treat embedded text as source of truth)

This is a DESIGN-STAGE review of Phase 5: the steady-state update mechanism. No implementation diff.

Two-tier cadence:
  DAILY (post-close, Windows Scheduled Task, unattended):
    update_daily_data.py --no-qlib   # raw layer only, NEVER touches provider/manifest/ledger
    run_daily_qa.py                   # QA with failure alert
    Rationale: the incremental provider path (mode=update + touched_symbols) SKIPS kline dump / never advances the calendar (pit_backend.py:3904-3926) AND rotates build_id every run (update_daily_data.py:496) → daily publish = daily 25-approval rebind. So daily = pure raw, zero governance cost. --no-qlib gives exactly that.
  MONTHLY (human-triggered + human-approved, packaging the manual Phase 1-4 I just ran):
    scripts/monthly_calendar_bump.py --dry-run   # runs to the audit + dry-run report, then STOPS
      1. disk check + referenced-build-retention prune
      2. endpoint readiness → target_end (last COMPLETE trading day)
      3. catch up the daily-uncovered datasets to target_end (namechange/suspend_d/stock_st_daily/report_rc[create_time+overlap]/stk_holdertrade/cyq_perf[per-symbol]/index_weights)
      4. new append-only policy YAML frozen_<target_end>_thaw_step<N>.yaml
      5. mode=all full rebuild (staged, no publish)
      6. frozen-prefix audit (bin byte-identity + calendar append-only + sidecar membership matrix, set discovered from tree) with an APPROVED-EXCEPTIONS registry per bump
      7. dry-run report
    [HUMAN SIGN-OFF GATE — §13: publish + rebind is a risk action, NEVER in the automated flow]
    publish leg (after explicit authorization):
      safe 3-step atomic swap → 25-approval dual-id rebind → evaluate_approval_evidence_bindings()==0 drift → post-publish QA green → parent-build metadata + docs

THE CENTRAL POLICY-YAML LIFECYCLE DECISION (§6 of the design):
  calendar_end_date / data_end_date: ADVANCE each bump (the point of a bump)
  spent_oos_end: STAYS 2026-02-27 across ALL bumps (only advances when a Phase-6 book-seal actually SPENDS the fresh window; a bump is a data op, spends no OOS)
  fresh_holdout_start: STAYS 2026-02-28
  frozen: stays true (rolling policy is out of scope, m1 guard)
  policy_id: new append-only id each bump
  → the born-sealed fresh window [2026-02-28, calendar_end] MONOTONICALLY GROWS with the calendar, fully D3-protected, until a book spends a slice. Design claim: this is correct — fresh OOS assets accumulate rather than being diluted by calendar advance.

EXPLICITLY OUT OF SCOPE: rolling policy (frozen:false + max_calendar_lag_days enforcement; blocked by the m1 guard until lag enforcement lands); true-append incremental materializer (only if monthly full-rebuild time becomes unacceptable); Phase 6 fresh-window research unsealing (gated on seal-record binding + M6-test-2 + m3 snapshot).

QUANTITATIVE-RESEARCH PRINCIPLES — check EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD. Does any step let a value at time t use info not knowable at t? Specifically: monthly catch-up of cyq_perf/report_rc vs daily ingest — can a create_time/update_flag late-arriving row for an already-passed date be missed or, worse, back-dated?
2. OUT-OF-SAMPLE SACRED & SEALED. Is freezing spent_oos_end at 2026-02-27 across bumps correct? Does the growing born-sealed window stay protected, or does any monthly-bump step (rebuild, sidecar regen, catch-up) touch the fresh window in a way that constitutes a peek?
3. SURVIVORSHIP. Monthly rebuild refreshes stock_basic L/D/P + regenerates sidecars + frozen-prefix sidecar audit (the exact gate that caught a 93-delisted-stock hole during this thaw). Sufficient going forward?
4-6 (factor-eval / execution-cost / leverage): flag only if the design accidentally touches them.
7. NO HEDGE WORDS. Every quantitative claim backed or marked unverified.
8. FOUR-LAYER PIPELINE: n/a.
9. MULTIPLE TESTING: does the frozen spent_oos_end prevent the growing fresh window from becoming a de-facto repeated test set?

REVIEW QUESTIONS
1. The daily/monthly split (§3): is "daily pure-raw, monthly provider-bump" the right decomposition, or is there a safe third path (daily scoped provider update that advances PIT fields WITHOUT rotating build_id / re-emitting the manifest)? Is anything lost by the provider lagging up to a month behind raw?
2. The spent_oos_end freeze (§6, §7 Q2) — THE key judgment: is "born-sealed window grows monotonically, spent_oos_end never moves on a bump" correct and safe? Or does it create a real research-operations problem (data present but unusable for months), and if so what is the correct middle path — e.g. a rolling IS boundary that releases the OLDEST fresh data to discovery as it ages past some horizon — WITHOUT weakening D3? Rule on whether such a release is ever sound.
3. Monthly catch-up PIT completeness (§7 Q5): for create_time-anchored (report_rc) and per-symbol (cyq_perf) datasets, is once-a-month catch-up PIT-equivalent to daily ingest, or must these move to the daily path despite cost? What's the exact failure mode if a create_time-late row lands mid-month?
4. target_end / "last complete session" authority (§7 Q4): is trade_cal is_open + post-close enough, or is a vendor endpoint-readiness probe mandatory to avoid ingesting a partial day into a formal provider?
5. Monthly full-rebuild time (§7 Q3): first thaw measured ~1.5h upstream + ~7-15h materialization. Acceptable as a monthly routine, or provision the true-append materializer now?
6. Anything in the human-sign-off gate / publish-leg separation that should be structured differently for a RECURRING (vs one-time) bump — e.g. does the approved-exceptions registry risk becoming a rubber stamp that launders real drift over many bumps?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending design text quoted and an exact suggested replacement. Map every Blocker to the principle/invariant it violates.
- Explicit rulings on the 6 review questions (esp. Q2 and Q3).
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
