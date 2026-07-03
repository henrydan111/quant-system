# GPT 5.5 Pro cross-review prompt — v1.4 amendment (book-level promotion)

> Design-stage review per CLAUDE.md §10. Copy the block below into GPT 5.5 Pro verbatim.
> Branch `calendar-unfreeze` is pushed; every raw link resolves against live code.

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, and do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

CONTEXT — read these to judge the change against the contract:
- CLAUDE.md  (hard invariants §3, PIT §3.2, sealed-OOS §3.4, factor lifecycle §3.5, research integrity §7, no-hedge §7.10, no-leverage §7.11)
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/CLAUDE.md
- The operative methodology being amended (v1.3, your own 4-round-converged design):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/factor_eval_methodology/FACTOR_EVAL_METHODOLOGY_v1.3.md
- The strategy-layer build plan being amended (§1.1 eligibility; you reviewed it R1, amendments A–G):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/capital_allocation_buildout/STRATEGY_LAYER_BUILD_PLAN_v1.md
- The writer gate the amendment hardens (set_status, line ~1477) + the privileged-status constant (line ~447):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_registry/store.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/release_gate.py
- The formal allow-set + resolve-but-label reader the amendment preserves:
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/validation_steps.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/resolver.py
- The identity chain / sealed-OOS runner / D6 multiplicity ledger the amendment builds on:
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_eval_skill/identity.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_eval_skill/sealed_oos.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_eval_skill/multiplicity.py
- The status-ladder docs that will be rewritten if this ships:
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_lifecycle/factor_status_ladder.md
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_lifecycle/README.md
- The amendment under review (also embedded in full below):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/factor_eval_methodology/FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md

SELF-REVIEW PREFLIGHT — completed before this GPT request: verdict "clean for GPT"; checked §3 invariants + each quantitative-research principle in the canonical template; fixes made: (1) marked both historical deployment-gate figures (eps_diffusion, E-wave) as non-quotable pending the fill-price-aware rerun per CLAUDE.md §3.3/§3.5, (2) added open question Q4 after noticing the component-diagnostics leg needed an explicit contamination-consistency statement, (3) verified PRIVILEGED_REGISTRY_STATUSES == {"approved"} so downgrade/revocation transitions survive the A3 writer-gate refusal; residual concerns for reviewer: the amendment's own Q1–Q5 (§7).

WHAT CHANGED (authoritative — treat the embedded text as the source of truth; the links cross-check the surrounding code). This is a DESIGN-STAGE review: no code has been changed yet; you are reviewing the governance amendment before implementation.

<<<BEGIN AMENDMENT DOC — workspace/research/factor_eval_methodology/FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md>>>

# v1.4 AMENDMENT PROPOSAL — retire the factor-level `approved` mint; one seal per book

> **Status: DESIGN PROPOSAL — pending GPT 5.5 Pro cross-review (CLAUDE.md §10). Not yet operative.**
> Amends FACTOR_EVAL_METHODOLOGY_v1.3.md (the operative methodology) and STRATEGY_LAYER_BUILD_PLAN_v1.md §1.1.
> If approved, folds into a consolidated v1.4 per the v1.3 precedence discipline.

## §0 — The change in one paragraph

The factor status ladder becomes **`draft → candidate` (terminal)**. No new factor-level `approved`
status is minted. The single sealed-OOS spend per strategy moves to the **book level**: freeze the
complete `DeploymentFrozenPlan` (which chains the `FrozenSelectionSet` per the v1.3 §2.1 identity
model) **before any OOS observation**, then spend **exactly one** holdout seal, whose artifact reports
both (a) the book-level event-driven total-return deployment verdict against the pre-declared
`pass_fail_bar` and (b) per-component gross factor-level OOS diagnostics as descriptive sub-metrics of
the same one-shot observation. Promotion writes go to `strategy_registry` (`StrategyCandidate` v0, PR3),
not to factor rows. The 7 legacy `approved` factor rows are preserved as historical evidence under the
existing `approval_validity` machinery.

## §1 — Motivation & evidence (all from this project's own record)

The question that triggered this (user, 2026-07-03): *is the `approved` layer a constraint on
strategy/book research rather than assistance, given single-factor performance does not translate to
strategy performance?* The record says yes, in four specific ways:

1. **The certificate does not certify the thing we need.** Factor-level sealed-OOS PASS has twice failed
   to predict book viability:
   - eps_diffusion: approved via sealed OOS (gross 5d LS Sharpe 7.24/2.59), deployment gate collapsed on
     the liquid universe; later revoked on the restatement-canary contingency.
   - E-wave 6-core: single-shot sealed OOS **6/6 PASS**, deployment gate **FAIL**; the gross OOS LS was
     confirmed microcap-driven (memory `project_e_wave_selection_mandate`, closed 2026-06-21).
   - ⚠ Staleness honesty: both deployment *numbers* (−3.6%/−52%; +4.5%/−62%) were produced under the
     pre-2026-06-22 close-based limit gate and are not quotable without a fill-price-aware rerun
     (CLAUDE.md §3.3/§3.5 flags this). The *structural* facts — factor-OOS pass ≠ book pass; the E-wave
     gross LS microcap decomposition — are confirmed independently of that fix.
2. **Approved can mean weak.** `earn_sue_ni_assets` is `approved` with OOS RankICIR **+0.026** (~93%
   decay from IS 0.35). The status carries no book-level information.
3. **Book performance is combination-driven, and we measured it.** Greedy-by-marginal built combined
   ICIR 1.02 vs 0.70 for greedy-by-standalone-ICIR; the low-correlation quartet beat the
   high-correlation one 2.5× (memory `reference_factor_selection_marginal_not_icir`). Selection for
   books is marginal orthogonal contribution over a pool — a per-factor OOS verdict is nearly
   orthogonal to that question.
4. **Factor-level spends contaminate and double-burn the shared window** — v1.3 §11.3's own "sharpest
   forward-looking gap":
   - *Contamination cascade:* a book assembled from factors that passed OOS on window W is
     selection-biased on W; measuring the book on W afterwards is no longer a clean one-shot. This is
     the same failure class the registry already names `oos_informed_backfill` ("2021–2026 is BURNED").
     The v1.3 Stage 7 → Stage 8 sequence institutionalizes it: Stage 8 runs conditioned on Stage-7
     survivors, on the same window.
   - *Double observation:* per v1.3, each book observes the window twice (Stage-7 ranking-set seal +
     the Stage-8 `DeploymentFrozenPlan` evaluation, FC1). Operationally the eps_diffusion and E-wave
     deployment legs observed the same window after the factor-level spend — whether a distinct plan
     seal was claimed is immaterial; the window's information was consumed twice per book. The D6
     ledger (multiplicity.py) counts spends but cannot un-bias a sequential reuse.
5. **The badge is not a transferable certificate anyway.** Under v1.3 §2.1, `approved[scope]` binds to
   `frozen_set_hash` + `target_universe_declaration_hash`; any different book (different set, universe,
   or universe-definition filters) requires a new TUD + a new seal. So the factor-level badge cannot be
   *reused* by the next book — the reusable library asset is `candidate` + Stage 2–4 characterization,
   exactly as v1.3 §8 already says ("strategy-build consumes the library").

**Timing.** The calendar unfreeze (UNFREEZE_PLAN v3, live) means post-2026-02-27 data is accruing —
the only genuinely virgin OOS the current candidate pool will ever have. The spending unit must be
decided *before* the first post-unfreeze seal is spent.

**What the old gate got right (kept, relocated).** The factor-level sealed-OOS scorecard is real:
4/5 IS-strong arXiv factors stopped (CGO −0.265 sign-flip; both northbound sign-flips), GP sign-flip
(+0.14 IS → −0.12 OOS). IS-only evidence is demonstrably not a final quality bar. The amendment does
not delete OOS discipline — it relocates the one-shot to the unit we deploy, and keeps the factor-level
measurement as diagnostics inside that same spend (§2 A2).

## §2 — The amendment (normative)

**A1. Candidate is the terminal factor-level status.** The ladder for factors is
`draft → candidate` (+ `deprecated`). v1.3 §3 Stage 7 is redefined from "seal + OOS + mint
`approved[scope]`" to **freeze-only**: assemble `FrozenSelectionSet` + `DeploymentFrozenPlan`
(identity.py — unchanged objects, unchanged §2.1 equality chain, unchanged §2.3 TUD timing), with
**no OOS observation**. Stage numbering is kept; semantics change (see A2). The Stage-5 candidate bar
(`|icir|≥0.10 ∧ sign≥0.70` on the declared target, role-aware per §3.3) is unchanged.

**A2. One seal per book; the spend reports two layers.** Stage 8 becomes the single sealed
evaluation: claim `HoldoutSealStore` **once**, keyed by the book identity (`plan_hash`, which chains
`frozen_set_hash` per §2.1). The one-shot artifact contains:
  - **(a) the book verdict** — event-driven **total-return**, realistic costs
    (`CostConfig.realistic_china()` or the declared formal profile), 1× gross, declared target
    universe, fill-price-aware limit gating, against the **pre-declared** `pass_fail_bar` (C5). This is
    the promotion-driving result.
  - **(b) per-component diagnostics** — the old Stage-7 measurement (gross factor-level OOS RankICIR /
    LS on the declared universe, decile protocol, via sealed_oos.py `run_sealed_oos` mechanics)
    computed **inside the same observation**, recorded as evidence rows on the component factors
    (evidence ≠ status; **no status is minted from (b)**). Purpose: attribution — "signal decayed" vs
    "execution ate it" — without a second window observation.
  The old factor-level bar (`rank_icir>0 ∧ ls_sharpe>1.0`) survives only as a *diagnostic reference
  line* inside (b), never a gate.

**A3. Writer gate: no new factor-level `approved`.** `FactorRegistryStore.set_status`
(store.py ~line 1477) refuses `status='approved'` for **new** promotions with a typed error directing
to strategy-level promotion. Explicit escape hatch: `legacy_exception_reason=<str>` + user sign-off
(confirm-first, §13) for the unforeseen case; default fail-closed. **Downgrades keep working
unchanged**: `approved→candidate` (revocations — eps_diffusion precedent), `→deprecated`, and the §6.1
RevalidationCadence outcomes are non-privileged transitions (verified:
`PRIVILEGED_REGISTRY_STATUSES == frozenset({"approved"})`, release_gate.py ~line 447). The
`StrategyRegistryStore` privileged path (same writer-gate machinery, `current_git_sha` + promotion
evidence) becomes the sole promotion door; `produce_promotion_evidence` machinery is reused for the
book artifact.

**A4. Load-bearing eligibility reads `candidate`.** STRATEGY_LAYER_BUILD_PLAN_v1.md §1.1 amended: a
`component_load ≥ w*` component must be **`candidate` (IS-validated on the declared target) with the
explicit `allow_candidate_components=True` attestation** in the prescription; the "`approved`" clause
becomes legacy-satisfying (the 7 rows), not required and not expected. `draft` remains REFUSED for
load-bearing; the diversified draft/sub-`w*` admission stays GATED on PR5 (amendment A there —
unchanged). §1.1 invariants 3 ("a candidate in any sealed book spends its OOS in the book context")
and 4 ("only the book is validated") are already the semantics this amendment generalizes.

**A5. Signal-replication studies survive, statusless.** A pure factor-level sealed-OOS study
(arXiv-batch shape; a legitimate research question with no strategy intent) remains possible: same
seal accounting through the D6 `OosWindowLedgerStore`, evidence recorded on the candidate rows,
**no status minted**. Its spend taints downstream books containing those factors on that window — the
`MultiplicityReport` must disclose the component-overlap. Default posture: run such studies on
already-burned windows; a fresh-window study requires explicit user authorization (confirm-first).

**A6. Virgin-window policy.** Post-2026-02-27 OOS accruals are spendable **only** by book-level seals
(A2) or an explicitly-authorized A5 study. Recorded per-spend in the window ledger with the spending
unit type.

**A7. Formal allow-set default unchanged.** The resolver/allow-set mechanics (validation_steps.py:
`formal` + `factor_registry_candidate` iff `allow_candidate_components`) stay as-is — fail-closed
default, explicit per-prescription attestation. The flag is re-documented as the **standard path** for
book prescriptions, not an escape hatch. Legacy `approved` rows continue to resolve as `formal`
(resolver.py ~line 158, subject to `approval_validity`) so historical artifacts stay reproducible.

## §3 — Deliberately unchanged

IS gate thresholds and the `factor_lifecycle` profile (IS-only; it never wrote `approved`);
P-GATE/replication ceilings; field-status governance; all PIT machinery and lints; the §2.1 identity
chain and §2.3 TUD timing; `evidence_tier` provenance (§9) — Stage-0 tiers now inform the *book's*
multiplicity disclosure; §6.1 RevalidationCadence (applies to legacy factor rows AND to strategy
rows); discovery's status-blindness (`get_factor_catalog()`, 42 call sites); no-leverage (§7.11);
the E1a–h candidate cohort and every existing candidate row. The dashboard keeps rendering legacy
`approved` (display label `approved_signal[legacy_per_factor_gate]` — cosmetic, optional).

## §4 — Steelman: why not keep Stage 7 as a cheap pre-filter?

1. *"It caught the sign-flips (GP, CGO, northbound) before any book was built."* True — and the same
   flip is caught by the book's single spend at the same seal cost (one spend either way; the arXiv
   batch was one set-seal for 5 factors). Under A2(b) the attribution survives: a book that fails
   because one component sign-flipped shows exactly that in the component diagnostics. What changes is
   only that the discovery costs a *book* design instead of a *batch* design — and pays once instead
   of twice.
2. *"Factor-level OOS is a reusable certificate for future books."* Void under v1.3's own §2.1: any
   new book re-seals. See §1.5.
3. *"Without individual OOS, book composition rests on IS-only component evidence."* Correct, and
   intentional: IS-select → one-shot OOS is the textbook design. The alternative — components
   confirmed on W, then the book measured on W — is the selection-bias we are removing. Composition
   quality is protected upstream by the Stage-5 bar, Stage-4 marginal selection, §6.2 interaction
   checks, family caps, and (PR5) effective-trials deflation.
4. *"Two gates give two chances to stop a bad idea."* Two observations of one window are not two
   independent chances — they are one chance plus one biased echo, at double multiplicity cost
   (v1.3 §11.3). The genuinely independent second chance is a *forward* window (post-unfreeze
   accrual), which A6 reserves for exactly this.

## §5 — Change list

**Docs (implementation pass 1, after design approval):** fold into consolidated v1.4; CLAUDE.md §3.5
(status-ladder bullet, writer-gate bullet, live-state note) + AGENTS.md §2a mirrored same pass (§11.2);
factor_status_ladder.md §1/§4 + factor_lifecycle/README.md §2/§7; STRATEGY_LAYER_BUILD_PLAN §1.1 (A4).

**Code (implementation pass 1 — small):** A3 writer-gate refusal in `FactorRegistryStore.set_status` +
typed error; pins extended in test_promotion_gate.py / test_factor_registry.py (incl. downgrade paths
keep working; run the whole driving test files). A6 window-ledger spend-unit tag (additive field).

**Code (lands with PR3 — plan unchanged, semantics per A2):** `StrategyCandidate` v0 carries the
single seal; the deployment runner embeds the component-diagnostics leg (A2(b)) inside the sealed
evaluation. PR2's `WeightedTargetStrategy` seam and PR1's risk model proceed exactly as planned.

**After verdict:** project_state.md entry; memory updates.

## §6 — Migration & compatibility

- The 7 `approved` rows: status preserved; `approval_validity` + §6.1 govern them; no re-litigation of
  their history. Their evidence remains citable as "passed the legacy per-factor sealed-OOS gate".
- Spent-window bookkeeping unchanged: everything already burned (frozen-13, arXiv-5, GP, eps_diffusion,
  E-wave-6) stays recorded; A5 studies on those windows remain cheap.
- No orchestrator profile changes: `hypothesis_validation` prescriptions with
  `allow_candidate_components=True` are already supported end-to-end.
- Historical artifacts referencing `approved` components resolve exactly as before (A7).

## §7 — Open questions for the reviewer

- **Q1 (A3 hardness):** hard writer-gate refusal with `legacy_exception_reason` escape (proposed) vs a
  config-gated policy flag. Is the escape hatch itself a hole worth closing further?
- **Q2 (A5 fresh windows):** should fresh-window signal-replication studies be banned outright rather
  than user-authorizable? (Proposed: authorizable, because e.g. a new data-source validation may
  genuinely need one — but each such spend delays clean book seals on that window.)
- **Q3 (stage numbering):** keep 8 stages with Stage 7 = freeze / Stage 8 = the one sealed evaluation
  (proposed, minimal doc churn) vs renumbering to 7 stages.
- **Q4 (diagnostics contamination):** A2(b) observes component-level OOS metrics inside the book
  spend. Confirm this is consistent: those components' window is spent-by-observation regardless
  (§1.1 invariant 3), evidence rows are labeled `spent_in_book_context`, and no fresh-OOS claim can
  cite them (`fresh_oos_eligible=false` semantics per §9).
- **Q5 (book-level multiplicity):** with factor-level spends gone, iteration pressure moves to book
  designs on the same window. D6 thresholds (warn 5 / hard 10 distinct sets per window) + PR5
  recipe-search deflation are the controls — are they sufficient as stated, or does the book seal need
  a stricter per-window budget from day one?

<<<END AMENDMENT DOC>>>

QUANTITATIVE-RESEARCH PRINCIPLES — check the change against EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (the cardinal rule). Fundamentals align on ann_date (NOT end_date), shift(1), forward-fill. Research PIT reads go ONLY through pit_research_loader / qlib_windowed_features — never raw data/pit_ledger/* and never hand-rolled alignment. Predictive factor fields are wrapped in Ref(...,1). Ask: does any value at time t use information not knowable at t?
2. OUT-OF-SAMPLE IS SACRED & SEALED. Temporal walk-forward splits only, never random. The holdout is single-shot / spend-on-attempt; never re-run a sealed OOS to "verify", and recovery is same-run resume only (run_dir + step_id + matching request_hash/plan_hash). No factor/parameter selected on OOS results.
3. SURVIVORSHIP. Universes include delisted + suspended names; never filter to currently-listed only.
4. FACTOR-EVAL STANDARD. IC, RankIC, ICIR, quantile spread, monotonicity, decay, turnover before promotion. Selection by MARGINAL orthogonal contribution (IC x low correlation to the existing set), not standalone ICIR; keep a min-IC floor.
5. EXECUTION & COST REALISM. T+1, limit up/down, suspension, corporate actions. Vectorized = price return; event-driven = total return — never compare them for a dividend book; the deployable number is the event-driven 1x total-return figure with realistic costs.
6. NO LEVERAGE. Every strategy reported unlevered (gross <= 1x); the headline number is the 1x number.
7. NO HEDGE WORDS. Every quantitative claim is either backed by a named dataset/script/output or explicitly marked "unverified — test Y resolves it". A plausible guess presented as an answer is the cardinal sin.
8. FOUR-LAYER PIPELINE. factor (computed on the full market) -> universe (boolean masks) -> signal (rank within the sub-universe) -> execution (tradability lives ONLY here). No filtering before factor computation; no tradability encoded in the signal.
9. MULTIPLE TESTING. Count effective trials (families / correlated clusters), not naive counts; guard against selection/overfitting (DSR/PSR/FDR/PBO where relevant).

REVIEW QUESTIONS
1. Correctness of the statistical argument — is §1.4 (sequential Stage-7→Stage-8 reuse of one window = selection-biased second observation) right, and is the A2 one-seal design a genuine fix rather than relabeling? Does A2(b) (component diagnostics inside the book spend) reintroduce any leak or OOS-reuse path the doc missed?
2. Governance — does retiring the factor-level approved mint weaken any §3 invariant in a way §4 (steelman) fails to answer? Specifically: is there a scenario where the absence of per-factor OOS certification lets a bad component into a sealed book that the Stage-5 IS bar + marginal selection + §6.2 interaction checks + the book's own one-shot cannot catch at acceptable cost?
3. Design — are the proposed answers to Q1–Q5 (§7) the right defaults? Answer each explicitly. Is keeping the 8-stage numbering with redefined Stage-7/8 semantics (Q3) acceptable, or does it invite doc drift?
4. Consistency — does the amendment contradict anything in v1.3 or STRATEGY_LAYER_BUILD_PLAN_v1 beyond the sections it explicitly amends (v1.3 §3 Stage 7, §5 display, §8 seal step; plan §1.1 eligibility)? Flag any seam it missed (e.g. FC1/FC6 filter-seal wording, C5 pass_fail_bar, §6.1 outcomes referencing "downgrade approved->candidate", the multiplicity module's "approved_signal claim" wording).
5. Evidence — what proof or pilot is missing before implementation? Name the exact test/check you would require (e.g. the A3 writer-gate test matrix; a dry-run book seal on an already-burned window to validate the A2 artifact shape).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
