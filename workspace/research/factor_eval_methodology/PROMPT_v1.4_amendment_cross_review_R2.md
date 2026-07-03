# GPT 5.5 Pro cross-review prompt — v1.4 amendment, ROUND 2 (re-review after REVISE)

> Round-1 verdict was REVISE (3 Blockers / 6 Majors / 3 Minors). All 12 findings were ACCEPTED and
> folded into revision 2 of the amendment. Branch `calendar-unfreeze` is pushed; every raw link
> resolves against live code. Copy the block below into GPT 5.5 Pro verbatim.

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is ROUND 2 of a design-stage review: in round 1 you returned REVISE with findings B1-B3, M1-M6, m1-m3. All were accepted and folded into the revised amendment embedded below. Your job now: verify each finding is faithfully resolved, check the fixes did not introduce new defects, and give a final verdict. Do not rubber-stamp — if a resolution is cosmetic or incomplete, say so.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

CONTEXT (same set as round 1):
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/CLAUDE.md
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/factor_eval_methodology/FACTOR_EVAL_METHODOLOGY_v1.3.md
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/capital_allocation_buildout/STRATEGY_LAYER_BUILD_PLAN_v1.md
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_registry/store.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/release_gate.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/validation_steps.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/research_orchestrator/resolver.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_eval_skill/identity.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_eval_skill/sealed_oos.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_eval_skill/multiplicity.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_lifecycle/factor_status_ladder.md
- Evidence artifacts newly cited in §1 (verify the quoted numbers):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/idea_sourcing/arxiv_d1d4_sealed_oos_promotion.json
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/idea_sourcing/arxiv_d1d4_selection_provenance.json
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/factor_expansion/unified_eval_standard.md
- The revised amendment under review (also embedded in full below):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/factor_eval_methodology/FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md

SELF-REVIEW PREFLIGHT — completed before this round-2 request: verdict "clean for GPT round-2"; every round-1 replacement folded (disposition table §9 of the doc, all 12 ACCEPTED, none declined); fixes verified against live code before writing them in: sealed_oos.py:116 claim_seal=True default (B2), store.py:1582 set_approval_validity refusal + store.py:801 auto-requires_revalidation (M2 — confirmed the trap is real: without the dedicated path, legacy approved rows would decay irreversibly), validation_steps.py:1093/1107 design-hash-keyed holdout + :1378 marker-only strategy publish (M1/M5), release_gate.py:447 privileged set = {"approved"} (downgrade safety); §1.2 numbers re-read from both JSONs (OOS rank_icir 0.02551831…→ quoted 0.0255; IS heldout 0.354); §1.3 greedy primary artifact NOT found → marked unverified-at-source with a named resolving script per your B3 replacement. Residual concerns: none new; your round-1 replacements adopted with two deliberate adaptations flagged in REVIEW QUESTIONS 2–3 below.

ROUND-1 → REVISION-2 DISPOSITION SUMMARY (details in the embedded doc §9):
- B1 → A7 rewritten: candidate_on_declared_target; candidate_scope_mismatch refusal before dataset build and before holdout access; migration via TUD-equivalence alias (evidence.universe == TUD.target_universe_id recorded at freeze) + target-scoped IS re-audition for candidates lacking target evidence.
- B2 → A2(b) rewritten: no-seal diagnostics inside the already-claimed book seal; run_sealed_oos(..., claim_seal=False) or run_component_diagnostics_in_book_context(...); refuses without an active BookHoldoutSealContext(plan_hash); no second claim; no promotion evidence; m3 schema fields.
- B3 → §1.2 exact artifact paths + values; §1.3 greedy numbers marked unverified-at-source, resolving script named (rederive_marginal_vs_standalone.py, implementation pass 1).
- M1 → A2 seal identity: book_plan_hash = DeploymentFrozenPlan.plan_hash; no design_hash/frozen_set_hash fallback for book seals; full payload field list; plans sharing a frozen set but differing in construction/envelope/bar = distinct spends.
- M2 → revalidate_legacy_approved(...) dedicated evidence-gated path (A3).
- M3 → A6: D6 extended to plan-hash/recipe-family/A5-overlap counting; virgin-window budget warn 3 / hard 5 with pre-recorded user-signed override + adjusted-stat reporting.
- M4 → separate audited legacy_factor_approval_override(...) command; no set_status kwarg bypass.
- M5 → A8 readiness clause: no virgin book seal before the StrategyRegistryStore promotion path is implemented/tested/wired; factor registry never a proxy.
- M6 → §5 exhaustive grep-sweep list for v1.4 consolidation.
- m1 → A1 explicit stage labels ("Stage 7 — freeze-only" / "Stage 8 — sole sealed book evaluation").
- m2 → A5 fresh_window_signal_replication_override_id, pre-recorded, counts against the A6 budget.
- m3 → A2(b) evidence schema (run_type='book_component_diagnostic', book_plan_hash, component_factor_id, component_weight/load, oos_window_id, spent_in_book_context=True, fresh_oos_eligible=False, promotion_eligible=False).

WHAT CHANGED (authoritative — the full revised amendment; treat this text as the source of truth):

<<<BEGIN REVISED AMENDMENT DOC (revision 2) — workspace/research/factor_eval_methodology/FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md (byte-identical to the committed file at the raw link above)>>>

# v1.4 AMENDMENT PROPOSAL — retire the factor-level `approved` mint; one seal per book

> **Status: REVISION 2 — round-1 GPT 5.5 Pro cross-review returned REVISE (3 Blockers / 6 Majors /
> 3 Minors, ALL ACCEPTED — disposition table §9); pending round-2 re-review. Not yet operative.**
> Amends [FACTOR_EVAL_METHODOLOGY_v1.3.md](FACTOR_EVAL_METHODOLOGY_v1.3.md) (the operative methodology)
> and [STRATEGY_LAYER_BUILD_PLAN_v1.md](../capital_allocation_buildout/STRATEGY_LAYER_BUILD_PLAN_v1.md) §1.1.
> If approved, folds into a consolidated v1.4 per the v1.3 precedence discipline.
>
> **中文摘要:** 因子状态阶梯改为 `candidate` 封顶(因子层不再新铸 `approved`);sealed-OOS 预算收敛为
> **每个策略(book)恰好一次**,seal 以 `plan_hash` 为键,一次消费同时产出账本级判定 + 成分因子 OOS
> 诊断(无第二次 claim)。第 1 轮 GPT 跨审 12 条意见全部采纳:candidate 准入必须目标域匹配、
> 诊断腿禁止默认 claim、遗留 approved 行需要专门 revalidation 通道、处女窗口 book 级多重性预算
> warn 3 / hard 5。

---

## §0 — The change in one paragraph

The factor status ladder becomes **`draft → candidate` (terminal)**. No new factor-level `approved`
status is minted. The single sealed-OOS spend per strategy moves to the **book level**: freeze the
complete `DeploymentFrozenPlan` (which chains the `FrozenSelectionSet` per the v1.3 §2.1 identity
model) **before any OOS observation**, then spend **exactly one** holdout seal keyed by
`book_plan_hash`, whose artifact reports both (a) the book-level event-driven total-return deployment
verdict against the pre-declared `pass_fail_bar` and (b) per-component gross factor-level OOS
diagnostics computed inside the same claimed seal (never a second claim). Promotion writes go to
`strategy_registry` (`StrategyCandidate` v0, PR3), not to factor rows. The 7 legacy `approved` factor
rows are preserved as historical evidence with a dedicated evidence-gated revalidation path.

## §1 — Motivation & evidence (artifact-anchored per round-1 B3)

The question that triggered this (user, 2026-07-03): *is the `approved` layer a constraint on
strategy/book research rather than assistance, given single-factor performance does not translate to
strategy performance?* The record says yes, in four specific ways:

1. **The certificate does not certify the thing we need.** Factor-level sealed-OOS PASS has twice failed
   to predict book viability:
   - eps_diffusion: approved via sealed OOS (gross 5d LS Sharpe 7.24/2.59, recorded in
     [eps_diffusion_sealed_oos_promotion.json](../idea_sourcing/eps_diffusion_sealed_oos_promotion.json)),
     deployment gate collapsed on the liquid universe
     (`workspace/scripts/build/eval_eps_diffusion_deployment.py`); later revoked on the
     restatement-canary contingency (project_state 2026-06-14).
   - E-wave 6-core: single-shot sealed OOS **6/6 PASS**, deployment gate **FAIL**; the gross OOS LS was
     confirmed microcap-driven (memory `project_e_wave_selection_mandate`, closed 2026-06-21; scripts
     `workspace/scripts/select_e_wave_sealed_oos.py` + the E-wave deployment eval outputs).
   - ⚠ Staleness honesty: both deployment *numbers* (−3.6%/−52%; +4.5%/−62%) were produced under the
     pre-2026-06-22 close-based limit gate and are not quotable without a fill-price-aware rerun
     (CLAUDE.md §3.3/§3.5 flags this). The *structural* facts — factor-OOS pass ≠ book pass; the E-wave
     gross LS microcap decomposition — are confirmed independently of that fix.
2. **Approved can mean weak.** `earn_sue_ni_assets` is `approved` with OOS RankICIR **+0.0255** /
   OOS LS Sharpe **1.063** — exact values at JSON path
   `promotion_evidence.independent_reproduction.per_factor.earn_sue_ni_assets` in
   [arxiv_d1d4_sealed_oos_promotion.json](../idea_sourcing/arxiv_d1d4_sealed_oos_promotion.json) —
   against IS heldout RankICIR **0.354** ([arxiv_d1d4_selection_provenance.json](../idea_sourcing/arxiv_d1d4_selection_provenance.json),
   `is_gate.verdicts.earn_sue_ni_assets`), a **92.8% decay**. The status carries no book-level information.
3. **Book performance is combination-driven.** The project's committed statement of record
   ([unified_eval_standard.md](../factor_expansion/unified_eval_standard.md) Tier-2 §, lines ~404–406,
   backed by memory `reference_factor_selection_marginal_not_icir`) cites greedy-by-marginal combined
   ICIR 1.02 vs greedy-by-ICIR 0.70. **The primary experiment output was not re-located in this
   amendment — those two specific numbers are unverified-at-source here**; the resolving step is a
   re-derivation script (`workspace/scripts/rederive_marginal_vs_standalone.py`, implementation pass 1)
   comparing greedy-by-marginal vs greedy-by-standalone over the current candidate pool. The
   amendment's normative content does not depend on the exact figures: marginal-over-standalone
   selection is already mandated by v1.3 §1.4/Stage 4 independently of them.
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
     ledger ([multiplicity.py](../../../src/alpha_research/factor_eval_skill/multiplicity.py)) counts
     spends but cannot un-bias a sequential reuse.
5. **The badge is not a transferable certificate anyway.** Under v1.3 §2.1, `approved[scope]` binds to
   `frozen_set_hash` + `target_universe_declaration_hash`; any different book (different set, universe,
   or universe-definition filters) requires a new TUD + a new seal. So the factor-level badge cannot be
   *reused* by the next book — the reusable library asset is `candidate` + Stage 2–4 characterization,
   exactly as v1.3 §8 already says ("strategy-build consumes the library").

**Timing.** The calendar unfreeze (UNFREEZE_PLAN v3, live) means post-2026-02-27 data is accruing —
the only genuinely virgin OOS the current candidate pool will ever have. The spending unit must be
decided *before* the first post-unfreeze seal is spent.

**What the old gate got right (kept, relocated).** The factor-level sealed-OOS scorecard is real:
4/5 IS-strong arXiv factors stopped (CGO −0.265 sign-flip; both northbound sign-flips; per-factor
verdicts in [arxiv_d1d4_sealed_oos_promotion.json](../idea_sourcing/arxiv_d1d4_sealed_oos_promotion.json)),
GP sign-flip (+0.14 IS → −0.12 OOS, project_state 2026-06-08). IS-only evidence is demonstrably not a
final quality bar. The amendment does not delete OOS discipline — it relocates the one-shot to the
unit we deploy, and keeps the factor-level measurement as no-seal diagnostics inside that same spend
(§2 A2).

## §2 — The amendment (normative; round-1 replacements folded in)

**A1. Candidate is the terminal factor-level status.** The ladder for factors is
`draft → candidate` (+ `deprecated`). v1.3 §3 Stage 7 is redefined from "seal + OOS + mint
`approved[scope]`" to **freeze-only**: assemble `FrozenSelectionSet` + `DeploymentFrozenPlan`
([identity.py](../../../src/alpha_research/factor_eval_skill/identity.py) — unchanged objects, unchanged
§2.1 equality chain, unchanged §2.3 TUD timing), with **no OOS observation**. The Stage-5 candidate bar
(`|icir|≥0.10 ∧ sign≥0.70` on the declared target, role-aware per §3.3) is unchanged.
**Stage numbering is kept only for migration stability (round-1 m1): every v1.4 table/header must
render `Stage 7 — freeze-only, no OOS observation` and `Stage 8 — sole sealed book evaluation`; any
unqualified "Stage 7 OOS" reference is invalid.**

**A2. One seal per book, keyed by `book_plan_hash`; the spend reports two layers.**
  - **Seal identity (round-1 M1).** Introduce `book_plan_hash = DeploymentFrozenPlan.plan_hash`. For
    book seals, `HoldoutSealStore` and every backstop/resume path key by `book_plan_hash`, with **no
    fallback to `design_hash` or `frozen_set_hash`** (the current
    [validation_steps.py](../../../src/research_orchestrator/validation_steps.py) OOS handler derives
    the holdout context from `hypothesis.design_hash()` — that path is migrated for book runs). The
    seal payload must include `plan_hash`, `frozen_set_hash`, `selected_set_hash`,
    `target_universe_declaration_hash`, `execution_envelope_hash` (execution-profile id + hash),
    `pre_declared_bar`, `oos_window_id`, and `eval_protocol_hash`. **Two plans sharing a frozen set but
    differing in construction, execution envelope, or pass/fail bar are distinct spends** (and count
    against the A6 budget). Spend-on-attempt and same-run-resume semantics
    (`run_dir` + `step_id` + matching request/plan hashes) are unchanged.
  - **(a) the book verdict** — event-driven **total-return**, realistic costs
    (`CostConfig.realistic_china()` or the declared formal profile), 1× gross, declared target
    universe, fill-price-aware limit gating, against the **pre-declared** `pass_fail_bar` (C5). This is
    the promotion-driving result.
  - **(b) component diagnostics are no-seal diagnostics inside the already-claimed book seal
    (round-1 B2).** They are computed by `run_component_diagnostics_in_book_context(...)` or by
    `run_sealed_oos(..., claim_seal=False)` (the live default is `claim_seal=True` —
    [sealed_oos.py:116](../../../src/alpha_research/factor_eval_skill/sealed_oos.py#L116) — so the
    diagnostics call site MUST pass `False`) under an active `BookHoldoutSealContext(plan_hash)`. The
    helper **refuses if no active book seal exists**, reuses the same OOS window/panel/cache as the
    book verdict, never calls `HoldoutSealStore.claim` again, never emits promotion evidence, and
    writes evidence rows with `run_type='book_component_diagnostic'`, `book_plan_hash`,
    `component_factor_id`, `component_weight/load`, `oos_window_id`, `spent_in_book_context=True`,
    `fresh_oos_eligible=False`, `promotion_eligible=False` (round-1 m3). Purpose: attribution —
    "signal decayed" vs "execution ate it" — without a second window observation. The old factor-level
    bar (`rank_icir>0 ∧ ls_sharpe>1.0`) survives only as a *diagnostic reference line* inside (b),
    never a gate.

**A3. Writer gate: no new factor-level `approved`; audited override + legacy revalidation path.**
  - `FactorRegistryStore.set_status`
    ([store.py:1477](../../../src/alpha_research/factor_registry/store.py#L1477)) refuses
    `status='approved'` for factors with a typed error directing to strategy-level promotion. **No
    ordinary `set_status(..., legacy_exception_reason=...)` bypass exists (round-1 M4).** Any
    exception goes through a separate `legacy_factor_approval_override(...)` command requiring: issue
    ID, explicit user sign-off artifact, `current_git_sha`, promotion/revalidation evidence, reviewer
    identity, reason code, expiration/scope, and a machine-readable assertion that this is not a new
    research promotion. The default API path always refuses `candidate→approved`.
  - **Legacy approved revalidation path (round-1 M2).** The live
    [store.py:1582](../../../src/alpha_research/factor_registry/store.py#L1582)
    `set_approval_validity` refuses re-affirming `valid` on an approved row and routes callers to
    `set_status('approved', ...)` — which A3 closes; without a new door, legacy approved rows that
    drift to `requires_revalidation` (which [store.py:801](../../../src/alpha_research/factor_registry/store.py#L801)
    applies automatically) would decay irreversibly. Therefore: rows whose `status='approved'`
    pre-dates v1.4 may receive `approval_validity='valid'` **only** through
    `revalidate_legacy_approved(...)`, which requires `current_git_sha`, revalidation evidence, prior
    approved status, unchanged `definition_hash` (or an explicit migration record), and an audit
    reason. This path does not create a new approved row and cannot be used for `candidate→approved`.
  - **Downgrades keep working unchanged**: `approved→candidate` (revocations — eps_diffusion
    precedent), `→deprecated`, §6.1 RevalidationCadence outcomes — all non-privileged transitions
    (verified: `PRIVILEGED_REGISTRY_STATUSES == frozenset({"approved"})`,
    [release_gate.py:447](../../../src/research_orchestrator/release_gate.py#L447)).

**A4. Load-bearing eligibility reads target-scoped `candidate`.**
[STRATEGY_LAYER_BUILD_PLAN_v1.md](../capital_allocation_buildout/STRATEGY_LAYER_BUILD_PLAN_v1.md) §1.1
amended: a `component_load ≥ w*` component must be **`candidate_on_declared_target` (per A7) with the
explicit `allow_candidate_components=True` attestation**; the "`approved`" clause becomes
legacy-satisfying (the 7 rows), not required and not expected. `draft` remains REFUSED for
load-bearing; the diversified draft/sub-`w*` admission stays GATED on PR5 (amendment A there —
unchanged). §1.1 invariants 3 ("a candidate in any sealed book spends its OOS in the book context")
and 4 ("only the book is validated") are already the semantics this amendment generalizes.

**A5. Signal-replication studies survive, statusless — fresh windows are an exceptional override
(round-1 m2).** A pure factor-level sealed-OOS study (arXiv-batch shape) remains possible on
already-burned windows: same seal accounting through the D6 `OosWindowLedgerStore`, evidence recorded
on the candidate rows, **no status minted**, `MultiplicityReport` disclosing the component-overlap
with any downstream book. A **fresh-window** A5 study requires a
`fresh_window_signal_replication_override_id` recorded **before** access, with an explicit statement
that the window is burned for overlapping downstream books and that the spend **counts against the
A6 book-level multiplicity budget**.

**A6. Virgin-window policy + book-level multiplicity budget (round-1 M3).** Post-2026-02-27 OOS
accruals are spendable **only** by book-level seals (A2) or an A5 override study. D6 is extended to
count, per OOS window: distinct `book_plan_hash` spends, recipe families, overlapping component sets,
and A5 component-study spends — not merely distinct frozen sets (the current counter's unit). Default
budget for virgin windows: **warn at 3 book plans per window, hard stop at 5** unless a user-signed
multiplicity override is recorded **before** the spend and the artifact reports adjusted
max-stat/FDR/DSR/PSR where applicable. PR5 recipe-search deflation is required but is **not a
substitute** for the hard per-window budget. Every spend is recorded in the window ledger with its
spending-unit type.

**A7. Candidate admission is target-scoped (round-1 B1).** The formal allow-set default stays
fail-closed, but `allow_candidate_components=True` admits only **`candidate_on_declared_target`**: the
resolved registry row must be `status='candidate'`, non-deprecated, definition-bound to the current
catalog, field dependencies passing formal validation, **and its latest Stage-5 candidate evidence
must be bound to the current `target_universe_declaration_hash` or to an explicitly versioned
TUD-equivalence alias recorded before Stage-7 freeze**. A status-only candidate match is **REFUSED
with `candidate_scope_mismatch` before dataset build and before any holdout access**. The flag attests
acceptance of target-scoped candidate evidence; it does not waive scope mismatch.
*Migration note:* pre-v1.4 candidates carry no TUD hash; their equivalence alias is the universe
identity recorded in their Stage-5/matrix evidence (`evidence.universe == TUD.target_universe_id`,
recorded at freeze time). The 7-universe Stage-2 matrix already yields per-target IC evidence; a
candidate lacking evidence on the declared target requires a **target-scoped IS re-audition** (cheap,
IS-only, no OOS access) before load-bearing admission. Legacy `approved` rows continue to resolve as
`formal` ([resolver.py:158](../../../src/research_orchestrator/resolver.py#L158), subject to
`approval_validity`) so historical artifacts stay reproducible.

**A8. Strategy promotion readiness (round-1 M5).** Book-level promotion is **unavailable** until
`StrategyRegistryStore.set_status('approved'` or the equivalent strategy-approved status`)` is
implemented, privilege-gated, tested, and wired to the book seal artifact. The current validation
publish step writes only a design-hash **marker**
([validation_steps.py:1378](../../../src/research_orchestrator/validation_steps.py#L1378)) — that is
not a promotion. **Factor-registry status must never be used as a temporary strategy-promotion
proxy.** Until A8 lands, no book seal may be spent on a virgin window (there would be nothing valid to
promote into).

## §3 — Deliberately unchanged

IS gate thresholds and the `factor_lifecycle` profile (IS-only; it never wrote `approved`);
P-GATE/replication ceilings; field-status governance; all PIT machinery and lints; the §2.1 identity
chain and §2.3 TUD timing; `evidence_tier` provenance (§9) — Stage-0 tiers now inform the *book's*
multiplicity disclosure; §6.1 RevalidationCadence (its "downgrade approved→candidate" outcome applies
to legacy factor rows AND, renamed appropriately, to strategy rows); discovery's status-blindness
(`get_factor_catalog()`, 42 call sites); no-leverage (§7.11); the E1a–h candidate cohort and every
existing candidate row. The dashboard keeps rendering legacy `approved` (display label
`approved_signal[legacy_per_factor_gate]` — cosmetic, optional).

## §4 — Steelman: why not keep Stage 7 as a cheap pre-filter?

1. *"It caught the sign-flips (GP, CGO, northbound) before any book was built."* True — and the same
   flip is caught by the book's single spend at the same seal cost (one spend either way; the arXiv
   batch was one set-seal for 5 factors). Under A2(b) the attribution survives: a book that fails
   because one component sign-flipped shows exactly that in the component diagnostics. What changes is
   only that the discovery costs a *book* design instead of a *batch* design — pays once instead of
   twice, and the spend is visible in the A6 budget either way.
2. *"Factor-level OOS is a reusable certificate for future books."* Void under v1.3's own §2.1: any
   new book re-seals. See §1.5.
3. *"Without individual OOS, book composition rests on IS-only component evidence."* Correct, and
   intentional: IS-select → one-shot OOS is the textbook design. The alternative — components
   confirmed on W, then the book measured on W — is the selection-bias we are removing. Composition
   quality is protected upstream by the Stage-5 bar **on the declared target (A7)**, Stage-4 marginal
   selection, §6.2 interaction checks, family caps, and (PR5) effective-trials deflation.
4. *"Two gates give two chances to stop a bad idea."* Two observations of one window are not two
   independent chances — they are one chance plus one biased echo, at double multiplicity cost
   (v1.3 §11.3). The genuinely independent second chance is a *forward* window (post-unfreeze
   accrual), which A6 reserves for exactly this.

## §5 — Change list

**Docs (implementation pass 1, after design approval):**
- Fold this amendment into `FACTOR_EVAL_METHODOLOGY_v1.4` (consolidated; precedence header updated).
- **Exhaustive seam sweep (round-1 M6):** v1.4 consolidation must update every normative reference to
  the old model. Required grep terms across `workspace/research/factor_eval_methodology/`,
  `workspace/research/capital_allocation_buildout/`, `src/alpha_research/factor_lifecycle/`,
  `src/alpha_research/factor_eval_skill/`, CLAUDE.md, AGENTS.md: `approved_signal`,
  `approved[scope]`, `candidate→approved` / `candidate -> approved`, `Stage 7`, `seal step`,
  `pass_fail_bar`, `FC1`, `FC6`, `C5`, `RevalidationCadence`, `fresh_oos_eligible`,
  `approved_signal_refs`. Each hit is rewritten or explicitly marked legacy-historical.
- CLAUDE.md §3.5 (status-ladder bullet, writer-gate bullet, live-state note) + **AGENTS.md §2a
  mirrored in the same edit pass (§11.2)**;
  [factor_status_ladder.md](../../../src/alpha_research/factor_lifecycle/factor_status_ladder.md)
  §1/§4 + [factor_lifecycle/README.md](../../../src/alpha_research/factor_lifecycle/README.md) §2/§7;
  STRATEGY_LAYER_BUILD_PLAN §1.1 (A4).

**Code (implementation pass 1 — small):**
- A3: writer-gate refusal + `legacy_factor_approval_override(...)` + `revalidate_legacy_approved(...)`.
- A7: `candidate_scope_mismatch` refusal in the validation resolver path (before dataset build /
  holdout access).
- A6: D6 extension (book_plan_hash / recipe-family / A5-overlap counting + virgin-window budget).
- B3 residual: `workspace/scripts/rederive_marginal_vs_standalone.py` (re-derive the greedy
  comparison numbers before they may be quoted again).

**Required acceptance tests (round-1 answer 5 — implementation pass 1 is not accepted without
these):**
- `test_candidate_scope_gate` — mismatched TUD/universe candidate refused before dataset build and
  before seal access; matching target-scoped candidate passes only with
  `allow_candidate_components=True`.
- `test_book_seal_key_is_plan_hash` — two plans sharing a frozen set but differing in construction /
  envelope / bar cannot reuse a seal; same-run resume only with matching `run_dir`, `step_id`,
  request hash, and `plan_hash`.
- `test_component_diagnostics_no_second_seal` — A2(b) writes component evidence without a second seal
  claim; rows carry `spent_in_book_context=True`, `fresh_oos_eligible=False`,
  `promotion_eligible=False`.
- `test_a3_writer_gate_matrix` — `candidate→approved` refused; `approved→candidate` and
  `approved→deprecated` allowed; legacy revalidation via the dedicated evidence-gated path only; no
  string-argument escape can mint approved.
- `test_book_multiplicity_budget` — D6 counts `book_plan_hash`, recipe family, and A5 overlaps;
  virgin-window warn/hard-stop enforced.
- Plus the whole driving test files re-run (`test_promotion_gate.py`, `test_factor_registry.py`,
  `test_pr9_validation_field_gate.py`) per standing feedback.

**Required pilot (before the first live book seal):** a dry-run book seal on an **already-burned**
window producing the full A2 artifact — book event-driven 1× total-return verdict, component
diagnostics, multiplicity report, strategy-registry promotion-evidence shape — with **no live virgin
seal consumed**.

**Code (lands with PR3 — plan unchanged, semantics per A2/A8):** `StrategyCandidate` v0 carries the
single `book_plan_hash` seal; the deployment runner embeds the component-diagnostics leg inside the
sealed evaluation. PR2's `WeightedTargetStrategy` seam and PR1's risk model proceed exactly as
planned.

**After verdict:** project_state.md entry; memory updates (`project_factor_eval_methodology`,
`project_capital_allocation_buildout`).

## §6 — Migration & compatibility

- The 7 `approved` rows: status preserved; `approval_validity` + §6.1 govern them; revalidation via
  `revalidate_legacy_approved(...)` (A3); no re-litigation of their history. Their evidence remains
  citable as "passed the legacy per-factor sealed-OOS gate".
- Spent-window bookkeeping unchanged: everything already burned (frozen-13, arXiv-5, GP,
  eps_diffusion, E-wave-6) stays recorded; A5 studies on those windows remain cheap.
- No orchestrator profile changes beyond the A7 scope check and the A2 book-seal key migration;
  `hypothesis_validation` prescriptions with `allow_candidate_components=True` remain the vehicle.
- Historical artifacts referencing `approved` components resolve exactly as before (A7).

## §7 — Round-1 resolutions of the open questions

- **Q1 (A3 hardness):** RESOLVED — hard refusal; the escape is a separate audited
  `legacy_factor_approval_override(...)` command, never a `set_status` argument (M4 adopted).
- **Q2 (A5 fresh windows):** RESOLVED — exceptional override with pre-recorded
  `fresh_window_signal_replication_override_id`, burns/taints overlapping downstream book use, counts
  against the A6 budget (m2 adopted).
- **Q3 (stage numbering):** RESOLVED — keep 8 stages, but every table/header must carry the explicit
  labels "Stage 7 — freeze-only" / "Stage 8 — sole sealed evaluation" (m1 adopted).
- **Q4 (diagnostics contamination):** RESOLVED — consistent iff labeled `spent_in_book_context=True`,
  `fresh_oos_eligible=False`, `promotion_eligible=False`, non-gating, no second claim (B2+m3 adopted).
- **Q5 (book-level multiplicity):** RESOLVED — warn-5/hard-10 frozen-set counting is NOT sufficient;
  virgin windows get plan-hash counting with warn 3 / hard 5 + recipe-family and A5-overlap
  accounting (M3 adopted).

## §8 — Self-review record (revision 2; CLAUDE.md §10 prerequisite)

Checked against §3 hard invariants + the canonical template's quantitative-research principles:

1. **PIT / no-lookahead:** no data-path change; all reads stay behind the sanctioned doors; A2(b)
   runs inside the claimed book seal's `ResearchAccessContext`. PASS.
2. **OOS sacred/sealed:** strengthened further in revision 2 — B2 closes the accidental-second-claim
   path (verified `claim_seal=True` is the live default at sealed_oos.py:116); M1 pins the seal key
   with no weaker fallback; A8 blocks virgin spends before the promotion target exists. PASS.
3. **Survivorship:** untouched. PASS.
4. **Factor-eval standard:** B1 closes the target-scope gap — candidate admission now requires
   evidence on the declared target, matching v1.3 dual-scope. PASS.
5. **Execution & cost realism:** the promotion-driving number is the event-driven total-return 1×
   figure by construction; stale pre-fill-gate numbers remain flagged non-quotable. PASS.
6. **No leverage:** book verdicts at 1× gross. PASS.
7. **No hedge words:** every §1 number now carries an exact artifact path, or is explicitly marked
   unverified-at-source with the named resolving script (the greedy pair). PASS.
8. **Four-layer pipeline:** untouched. PASS.
9. **Multiple testing:** materially strengthened — plan-hash-unit counting, virgin-window warn-3/
   hard-5, A5 spends folded into the same budget. PASS.

Verification performed for this revision (against live code): sealed_oos.py:116 default
`claim_seal=True` (B2 confirmed); store.py:1582 `set_approval_validity` refusal + store.py:801
auto-`requires_revalidation` (M2 trap confirmed — the dedicated revalidation path is necessary, not
optional); validation_steps.py:1093/1107 design-hash-keyed holdout context + :1378 marker-only
strategy publish (M1/M5 confirmed); release_gate.py:447 privileged set = {"approved"} (downgrade
safety confirmed). Artifact anchors resolved for §1.2 (both JSONs read, exact values quoted);
§1.3 primary artifact NOT found → marked unverified-at-source per B3.
Residual concerns for the reviewer: none beyond confirming the round-1 replacements are faithfully
folded. **Verdict: clean for GPT round-2.**

## §9 — Round-1 disposition table (verdict REVISE; all findings ACCEPTED, none declined)

| # | Finding | Disposition |
|---|---|---|
| B1 | allow-set lacks target-scope enforcement | ACCEPTED → A7 rewritten (`candidate_on_declared_target`, `candidate_scope_mismatch`, TUD-equivalence alias + IS re-audition migration) |
| B2 | A2(b) could double-claim via `run_sealed_oos` default | ACCEPTED → A2(b) rewritten (no-seal diagnostics, active-book-seal precondition, `claim_seal=False`) |
| B3 | unanchored quantitative claims | ACCEPTED → §1.2 exact artifact paths/values; §1.3 marked unverified-at-source + resolving script |
| M1 | seal key still frozen-set/design-hash keyed | ACCEPTED → A2 seal-identity clause (`book_plan_hash`, payload fields, no fallback) |
| M2 | legacy approved revalidation dead-ends | ACCEPTED → `revalidate_legacy_approved(...)` (A3); trap verified at store.py:1582+:801 |
| M3 | D6 counts wrong unit / too weak for virgin windows | ACCEPTED → A6 budget (plan-hash unit, warn 3 / hard 5, recipe-family + A5 overlap) |
| M4 | string-arg escape hatch too soft | ACCEPTED → separate audited `legacy_factor_approval_override(...)` |
| M5 | strategy promotion door not yet real | ACCEPTED → A8 readiness clause (no virgin spend before it lands; no factor-registry proxy) |
| M6 | stale v1.3 seams | ACCEPTED → §5 exhaustive grep sweep list |
| m1 | stage labels | ACCEPTED → A1 explicit-label rule |
| m2 | A5 fresh-window override | ACCEPTED → A5 override-id requirement |
| m3 | diagnostics evidence schema | ACCEPTED → A2(b) schema fields |

<<<END REVISED AMENDMENT DOC>>>

QUANTITATIVE-RESEARCH PRINCIPLES — same nine as round 1 (PIT; OOS sacred/sealed; survivorship; factor-eval standard; execution/cost realism; no leverage; no hedge words; four-layer pipeline; multiple testing). A violation is a Blocker.

REVIEW QUESTIONS (round 2)
1. Resolution fidelity — for each of B1, B2, B3, M1, M2, M3, M4, M5, M6, m1, m2, m3: is the revision's resolution faithful to your round-1 replacement text, and is it normatively sufficient (not just aspirational wording)? Flag any that regressed to "implicit guardrail".
2. Deliberate adaptation (a): A7's migration mechanism for pre-v1.4 candidates (TUD-equivalence alias = the universe identity recorded in Stage-5/matrix evidence, recorded at freeze; candidates lacking target evidence require a target-scoped IS-only re-audition before load-bearing admission). Your B1 text allowed "an explicitly versioned TUD-equivalence alias recorded before Stage 7 freeze" — is this concrete alias definition acceptable, or does universe-id equality understate what TUD hashes (eligibility_policy, asof_policy, universe_definition_filters)? If insufficient, state the minimal alias content you would require.
3. Deliberate adaptation (b): A8 adds "Until A8 lands, no book seal may be spent on a virgin window" — stronger than your M5 text. Confirm this is right, or flag if it over-blocks a legitimate interim workflow (e.g. a dry-run book seal on an already-burned window, which §5 explicitly still allows and requires as the pilot).
4. New-defect scan — did revision 2 introduce any new inconsistency (e.g. A6's warn-3/hard-5 vs the D6 module's existing warn-5/hard-10 defaults for non-virgin windows; A2's payload field list vs the live identity.py field set; the §5 test matrix vs existing test file names)?
5. Final — SHIP / REVISE / REWORK, plus the single most important residual risk.

OUTPUT FORMAT
- Per-finding resolution verdict table (B1…m3: RESOLVED / PARTIAL / NOT RESOLVED, one line each).
- Any NEW issues ranked Blocker / Major / Minor with offending line quoted + exact replacement.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
