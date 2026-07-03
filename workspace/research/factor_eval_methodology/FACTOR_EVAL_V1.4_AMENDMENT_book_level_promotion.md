# v1.4 AMENDMENT PROPOSAL — retire the factor-level `approved` mint; one seal per book

> **Status: DESIGN SHIPPED — round-4 GPT 5.5 Pro verdict SHIP (2026-07-03; all four wording fixes
> CONFIRMED; N2 fully RESOLVED). 4-round arc REVISE×3→SHIP; 18 findings, all accepted, none
> declined. Round-4 residual risk for implementation pass 1: wiring the ledger/seal API against
> `book_plan_hash` instead of the derived `book_seal_key`, especially in resume/backstop paths.
> ⚠ NOT YET OPERATIVE — the governance takes effect only when implementation pass 1 (§5) lands
> with its acceptance tests + the burned-window dry-run pilot; until then CLAUDE.md §3.5 remains
> the live contract.**
> Amends [FACTOR_EVAL_METHODOLOGY_v1.3.md](FACTOR_EVAL_METHODOLOGY_v1.3.md) (the operative methodology)
> and [STRATEGY_LAYER_BUILD_PLAN_v1.md](../capital_allocation_buildout/STRATEGY_LAYER_BUILD_PLAN_v1.md) §1.1.
> If approved, folds into a consolidated v1.4 per the v1.3 precedence discipline.
>
> **中文摘要:** 因子状态阶梯改为 `candidate` 封顶(因子层不再新铸 `approved`);sealed-OOS 预算收敛为
> **每个策略(book)恰好一次**,seal 以派生 `book_seal_key` 为键(A2),一次消费同时产出账本级判定 +
> 成分因子 OOS 诊断(无第二次 claim)。第 1 轮 GPT 跨审 12 条意见全部采纳:candidate 准入必须目标域匹配、
> 诊断腿禁止默认 claim、遗留 approved 行需要专门 revalidation 通道、处女窗口 book 级多重性预算
> warn 3 / hard 5。第 2 轮 3 条新意见亦全部采纳:N1 迁移别名必须绑定完整 TUD 载荷(仅
> universe-id 相等永远不够)、N2 seal 键改为包含全部区分字段的派生 `book_seal_key`、N3 诊断腿
> 只准走专用 helper(裸 `claim_seal=False` 在现行上下文下会 fail-closed,不是复用通道)。

---

## §0 — The change in one paragraph

The factor status ladder becomes **`draft → candidate` (terminal)**. No new factor-level `approved`
status is minted. The single sealed-OOS spend per strategy moves to the **book level**: freeze the
complete `DeploymentFrozenPlan` (which chains the `FrozenSelectionSet` per the v1.3 §2.1 identity
model) **before any OOS observation**, then spend **exactly one** holdout seal keyed by the derived
`book_seal_key` (A2), whose artifact reports both (a) the book-level event-driven total-return deployment
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

**A2. One seal per book, keyed by `book_seal_key`; the spend reports two layers.**
  - **Seal identity — hash material, not audit-only payload (round-1 M1 + round-2 N2).**
    `book_plan_hash = DeploymentFrozenPlan.plan_hash` names the plan; the **seal key** is the derived
    `book_seal_key = hash_canonical({plan_hash, frozen_set_hash, selected_set_hash,
    target_universe_declaration_hash, execution_envelope_hash, eval_protocol_hash, oos_window_id,
    pre_declared_bar_hash})`. **Every field that differentiates a sealed spend is part of the key; no
    spend-differentiating field may be payload-only.** Rationale (verified): the live
    `DeploymentFrozenPlan._payload()`
    ([identity.py:200-210](../../../src/alpha_research/factor_eval_skill/identity.py#L200-L210))
    hashes frozen_set_hash / envelope_hash / TUD hash / deployment_universe / portfolio_side /
    construction / pre_declared_bar but NOT `selected_set_hash`, the execution-profile identity, the
    `EvalProtocolSpec` hash
    ([identity.py:218](../../../src/alpha_research/factor_eval_skill/identity.py#L218) — the protocol
    identity object exists but is not chained into `plan_hash`), or `oos_window_id` — so keying by
    bare `plan_hash` could let two materially different sealed evaluations share a key. For book
    seals, `HoldoutSealStore` and every backstop/resume path key by `book_seal_key`, with **no
    fallback to `design_hash` or `frozen_set_hash`** (the current
    [validation_steps.py](../../../src/research_orchestrator/validation_steps.py) OOS handler derives
    the holdout context from `hypothesis.design_hash()`, and the sealed-OOS reproduction keys by
    `frozen_set.frozen_set_hash` — both migrated for book runs). **Changes to construction, execution
    envelope, evaluation protocol, OOS window, or pass/fail bar each produce a distinct seal key**
    (asserted by test, §5) and count as distinct spends against the A6 budget. Spend-on-attempt and
    same-run-resume semantics (`run_dir` + `step_id` + matching request hash + `book_seal_key`) are
    unchanged.
  - **(a) the book verdict** — event-driven **total-return**, realistic costs
    (`CostConfig.realistic_china()` or the declared formal profile), 1× gross, declared target
    universe, fill-price-aware limit gating, against the **pre-declared** `pass_fail_bar` (C5). This is
    the promotion-driving result.
  - **(b) component diagnostics are no-seal diagnostics inside the already-claimed book seal
    (round-1 B2 + round-2 N3).** They are computed by
    `run_component_diagnostics_in_book_context(...)` — the ONLY sanctioned path. A direct call to
    `run_sealed_oos(..., claim_seal=False)` is **disallowed** unless that function is explicitly
    refactored to accept and REUSE an active `BookHoldoutSealContext` / `ResearchAccessContext` with
    `holdout_seal_claimed=True` and `seal_key=book_seal_key`, and to refuse installing a nested
    no-seal OOS context. Rationale (verified): the live reproduction path installs
    `ResearchAccessContext(holdout_seal_claimed=bool(claim_seal), seal_key=frozen_set_hash)`
    ([promotion_evidence.py:286](../../../src/research_orchestrator/promotion_evidence.py#L286);
    default `claim_seal=True` at
    [sealed_oos.py:116](../../../src/alpha_research/factor_eval_skill/sealed_oos.py#L116)), so a bare
    `claim_seal=False` call fails closed on real OOS reads (`HoldoutSealViolation`) — it is NOT a
    seal-reuse path, and casually patching it would open a second implicit context door. The
    diagnostics helper **refuses if no active book seal exists**, reuses the same OOS
    window/panel/cache as the book verdict, never calls `HoldoutSealStore.claim` again, never emits
    promotion evidence, and
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
count, per OOS window: distinct `book_seal_key` spends (grouped by `book_plan_hash` for disclosure),
recipe families, overlapping component sets, and A5 component-study spends — not merely distinct
frozen sets (the current counter's unit). Default
budget for virgin windows: **warn at 3 distinct `book_seal_key` spends per OOS window, hard stop at 5
distinct `book_seal_key` spends per OOS window**, with `book_plan_hash` used only for disclosure
grouping, unless a user-signed multiplicity override is recorded **before** the spend and the
artifact reports adjusted max-stat/FDR/DSR/PSR where applicable. PR5 recipe-search deflation is required but is **not a
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
*Migration note (round-2 N1 — universe-id equality alone is NEVER sufficient):* pre-v1.4 candidates
that lack `target_universe_declaration_hash` may use a TUD-equivalence alias only if the alias is
explicitly versioned, recorded before Stage-7 freeze, and hash-bound to a canonical payload
containing: `alias_id`, `alias_version`, `created_at`, `recorded_before_stage7_freeze=True`,
`factor_id`, `factor_version`, `definition_hash`, `source_evidence_id/run_id`, the Stage-5
methodology/protocol hash, the evidence window, `target_universe_id`, canonicalized
`universe_definition_filters`, `eligibility_policy`, `asof_policy`, and the data/calendar policy
identifiers needed to reproduce the Stage-5 panel. Alias acceptance requires **exact equality**
between the alias payload and the current TUD for `target_universe_id`,
`universe_definition_filters`, `eligibility_policy`, and `asof_policy` (the full live TUD identity —
[identity.py:52-72](../../../src/alpha_research/factor_eval_skill/identity.py#L52-L72)). If any
required field is absent, stale, non-canonical, or mismatched, the resolver refuses
`candidate_scope_mismatch` before dataset build and before holdout access; the candidate must then
pass a **target-scoped IS re-audition under the current TUD** (cheap, IS-only, no OOS access) before
load-bearing admission. The 7-universe Stage-2 matrix yields per-universe IC evidence but does NOT by
itself establish filter/as-of/eligibility equality — it feeds the re-audition, never the alias. Legacy `approved` rows continue to resolve as
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
- A6: D6 extension (book_seal_key counting grouped by book_plan_hash / recipe-family / A5-overlap +
  virgin-window budget).
- B3 residual: `workspace/scripts/rederive_marginal_vs_standalone.py` (re-derive the greedy
  comparison numbers before they may be quoted again).

**Required acceptance tests (round-1 answer 5 — implementation pass 1 is not accepted without
these):**
- `test_candidate_scope_gate` — mismatched TUD/universe candidate refused before dataset build and
  before seal access; matching target-scoped candidate passes only with
  `allow_candidate_components=True`.
- `test_book_seal_key_distinctness` (round-2 N2; supersedes round-1's `test_book_seal_key_is_plan_hash`)
  — changes to construction, execution envelope, evaluation protocol, OOS window, or pass/fail bar
  each produce a distinct `book_seal_key`; two plans sharing a frozen set cannot reuse a seal;
  same-run resume only with matching `run_dir`, `step_id`, request hash, and `book_seal_key`.
- `test_component_diagnostics_no_second_seal` — A2(b) writes component evidence without a second seal
  claim; rows carry `spent_in_book_context=True`, `fresh_oos_eligible=False`,
  `promotion_eligible=False`.
- `test_component_diagnostics_preserves_active_book_research_access_context` (round-2 N3) — the
  diagnostics leg runs under the book's already-claimed context (`holdout_seal_claimed=True`,
  `seal_key=book_seal_key`) and never installs a nested no-seal OOS context.
- `test_component_diagnostics_refuses_bare_claim_false_without_book_context` (round-2 N3) — a bare
  `run_sealed_oos(..., claim_seal=False)` outside an active book seal context is refused.
- `test_a3_writer_gate_matrix` — `candidate→approved` refused; `approved→candidate` and
  `approved→deprecated` allowed; legacy revalidation via the dedicated evidence-gated path only; no
  string-argument escape can mint approved.
- `test_book_multiplicity_budget` — D6 counts `book_seal_key` spends (grouped by `book_plan_hash`),
  recipe family, and A5 overlaps; virgin-window warn/hard-stop enforced.
- Plus the whole driving test files re-run (`test_promotion_gate.py`, `test_factor_registry.py`,
  `test_pr9_validation_field_gate.py`) per standing feedback.

**Required pilot (before the first live book seal):** a dry-run book seal on an **already-burned**
window producing the full A2 artifact — book event-driven 1× total-return verdict, component
diagnostics, multiplicity report, strategy-registry promotion-evidence shape — with **no live virgin
seal consumed**.

**Code (lands with PR3 — plan unchanged, semantics per A2/A8):** `StrategyCandidate` v0 carries the
single `book_seal_key` seal; the deployment runner embeds the component-diagnostics leg inside the
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
  virgin windows get `book_seal_key` spend counting, grouped by `book_plan_hash` only for disclosure,
  with warn 3 / hard 5 + recipe-family and A5-overlap accounting (M3 adopted, unit per round-2 N2).

## §7a — Round-2 resolutions

- **Adaptation (a) — A7 migration alias:** REJECTED as written in revision 2 (universe-id equality
  understates TUD identity, which also hashes `universe_definition_filters` / `eligibility_policy` /
  `asof_policy`) → replaced with the full hash-bound alias payload + exact 4-field TUD equality (N1).
- **Adaptation (b) — A8 virgin-window block:** CONFIRMED correct — not over-blocking; the §5 dry-run
  pilot on an already-burned window remains allowed and required.
- **A6 warn-3/hard-5 vs D6 warn-5/hard-10:** confirmed no defect — the module's existing defaults
  govern the current frozen-set ledger; A6 is the virgin-window policy delivered by the D6 extension.

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
9. **Multiple testing:** materially strengthened — `book_seal_key` spend counting grouped by
   `book_plan_hash` for disclosure, virgin-window warn-3/hard-5, A5 spends folded into the same
   budget. PASS.

Verification performed for this revision (against live code): sealed_oos.py:116 default
`claim_seal=True` (B2 confirmed); store.py:1582 `set_approval_validity` refusal + store.py:801
auto-`requires_revalidation` (M2 trap confirmed — the dedicated revalidation path is necessary, not
optional); validation_steps.py:1093/1107 design-hash-keyed holdout context + :1378 marker-only
strategy publish (M1/M5 confirmed); release_gate.py:447 privileged set = {"approved"} (downgrade
safety confirmed). Artifact anchors resolved for §1.2 (both JSONs read, exact values quoted);
§1.3 primary artifact NOT found → marked unverified-at-source per B3.
Residual concerns for the reviewer: none beyond confirming the round-1 replacements are faithfully
folded. **Verdict (revision 2): clean for GPT round-2.**

**Revision-3 additions (round-2 findings folded):** verified the `DeploymentFrozenPlan._payload()`
field inventory at identity.py:200-210 and `EvalProtocolSpec` at :218 (N2 confirmed — `plan_hash`
lacks selected-set / protocol / window / execution-profile identity → adopted the derived
`book_seal_key` with a distinctness test); verified promotion_evidence.py:286 installs
`holdout_seal_claimed=bool(claim_seal)` and the sealed-OOS reproduction keys by
`frozen_set.frozen_set_hash` (:248) (N3 confirmed — bare `claim_seal=False` fails closed and is not a
reuse path → diagnostics constrained to the dedicated helper + 2 new tests); replaced the A7 alias
with the full TUD-payload binding and exact 4-field equality (N1 — the TUD identity fields verified
at identity.py:52-72). **Verdict: clean for GPT round-3.**

**Revision-4 additions (round-3 findings folded):** the four stale-wording fixes (R3-M1 heading,
R3-M2 threshold unit, R3-m1 two summaries) applied verbatim; grep sweep confirms the only remaining
"book plans"/"plan-hash counting" strings are the §9 historical disposition rows describing the
defects themselves. No normative content changed in revision 4 — wording alignment only.
**Verdict: clean for GPT round-4 (confirmation).**

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

### Round-2 disposition (verdict REVISE; 9/12 RESOLVED, B1/B2/M1 PARTIAL → N1/N2/N3; ALL ACCEPTED, none declined)

| # | Finding | Disposition |
|---|---|---|
| N1 (Blocker) | A7 migration alias understated TUD identity (universe-id equality admits evidence produced under different filters/as-of/eligibility) | ACCEPTED → full hash-bound alias payload; exact equality on `target_universe_id` + `universe_definition_filters` + `eligibility_policy` + `asof_policy`; anything less → `candidate_scope_mismatch` + IS re-audition |
| N2 (Major) | `plan_hash` payload lacks spend-differentiating fields (verified identity.py:200-210) | ACCEPTED → derived `book_seal_key` over {plan, frozen set, selected set, TUD, execution envelope, eval protocol, OOS window, bar}; no field payload-only; `test_book_seal_key_distinctness` |
| N3 (Major) | bare `run_sealed_oos(claim_seal=False)` is not a seal-reuse path under live context behavior (verified promotion_evidence.py:286) | ACCEPTED → `run_component_diagnostics_in_book_context(...)` is the only sanctioned path; bare call disallowed unless refactored to reuse the active book context; 2 new tests |

### Round-3 disposition (verdict REVISE; N1/N3 RESOLVED, N2 PARTIAL on wording; ALL APPLIED)

| # | Finding | Disposition |
|---|---|---|
| R3-M1 (Major) | A2 heading still said "keyed by `book_plan_hash`" | APPLIED → heading now "keyed by `book_seal_key`" |
| R3-M2 (Major) | A6 threshold sentence said "3/5 book plans" (unit confusion) | APPLIED → "3/5 distinct `book_seal_key` spends per OOS window, `book_plan_hash` for disclosure grouping only" |
| R3-m1 (Minor) | §7 Q5 + §8 summaries said "plan-hash counting" | APPLIED → both rewritten to the `book_seal_key` spend unit |

Round-3 completeness statement (reviewer): after these wording corrections, no guardrail remains
merely implicit — A7 target-scope admission, A2 derived seal key, A2(b) active-context diagnostics,
A6 multiplicity budget, and A8 no-virgin-spend-before-strategy-registry are all normative.
