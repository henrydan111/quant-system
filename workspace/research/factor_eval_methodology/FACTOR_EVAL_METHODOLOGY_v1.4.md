# Factor Evaluation Methodology — v1.4 (consolidated single source of truth)

> **v1.4 is THE operative methodology.** It supersedes the incremental docs (which remain the design
> history/audit trail). A runnable skill reads **only this file**. v1.4 = v1.3 (GPT 5.5 Pro
> 4-round-converged) + the **book-level-promotion amendment** (its own 4-round GPT arc
> REVISE×3→**SHIP**, 2026-07-03): **the factor-level `approved` mint is RETIRED — `candidate` is the
> terminal factor-level status; Stage 7 is freeze-only (no OOS observation); Stage 8 is the SOLE
> sealed evaluation, one holdout seal per book keyed by the derived `book_seal_key`.** Full rationale
> + the round-by-round dispositions:
> [FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md](FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md).
>
> **Precedence (machine-readable).** On any conflict, v1.4 wins.
> ```
> FACTOR_EVAL_METHODOLOGY_v1.4 (this)         SUPERSEDES ALL below
>   ← FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion (A1-A8; folded here)
>   ← FACTOR_EVAL_METHODOLOGY_v1.3 (the prior consolidated doc)
>   ← FACTOR_EVAL_FILTER_CONTRACTS_v1 (FC1-FC8; incl. the v1.2 §H1/§H3 amendments)
>   ← FACTOR_EVAL_METHODOLOGY_v1.2_addendum (roles, FilterEvaluation, StrategyContext)
>   ← FACTOR_EVAL_CONTRACTS_v1 (C1-C7)        [C1 sign-flip cap AMENDED at §3.3]
>   ← FACTOR_EVAL_METHODOLOGY_v1.1 (architecture, dual-scope)
> ```
>
> **v1.4 normative deltas at a glance (A1–A8):** A1 candidate-terminal + explicit stage labels
> ("Stage 7 — freeze-only, no OOS observation" / "Stage 8 — sole sealed book evaluation"); A2 one
> seal per book keyed `book_seal_key` (all spend-differentiating fields are hash material) + no-seal
> component diagnostics inside the claimed book seal; A3 writer gate (`set_status('approved')`
> refused; audited `legacy_factor_approval_override` + `revalidate_legacy_approved`); A4/A7
> target-scoped candidate admission (`candidate_on_declared_target`, `candidate_scope_mismatch`
> refusal, TUD-equivalence alias with exact 4-field equality); A5 statusless signal-replication
> studies (fresh windows only via pre-recorded override); A6 virgin-window budget (warn 3 / hard 5
> distinct `book_seal_key` spends per window); A8 no virgin spend before the strategy-registry
> promotion path exists.

## R4 must-fix disposition (all ACCEPTED)

| # | Must-fix | Resolved in |
|---|---|---|
| 1 | Single source of truth / precedence | this doc + precedence table above |
| 2 | Target-universe identity hash across the 3 freeze objects | §2 (freeze-object identity model) |
| 3 | Target-universe declared BEFORE Stage 2/3 interpretation (deployment-bound) | §2.3 |
| 4 | Role-aware display/status | §5 |
| 5 | Role-aware cap resolver (C1 sign-flip over-blocks small-cap) | §3.3 |
| 6 | C3↔FC4 equality (universe-def filters in identity, not FilterEvaluation) | §2.2 |
| 7 | DeploymentFrozenPlan must reference the ranking seal + target-universe hash | §2.1 |
| 8 | Revalidation / retirement cadence | §6.1 |
| 9 | Selected-set interaction check (beyond pairwise marginal) | §6.2 |

---

## §1 — Principles (unchanged, condensed)

1. **Layer separation.** Factor = cross-sectional signal; strategy = a book on a universe.
   **Deployable is a strategy property, NOT a factor status.**
2. **Roles.** Every factor *usage* has a role ∈ `{ranking, filter, both}`. Ranking → contributes to the
   score (排名条件), evaluated by IC. Filter → eligibility tail-cut (筛选条件), evaluated by strategy
   impact, **never IC** (a zero-IC filter like 退市风险 is high-value).
3. **Dual-scope.** No single canonical universe. Research candidacy may be broad (`univ_all`,
   scope-stamped); **deployment-bound claims require the DECLARED target investable universe**;
   the sealed verdict (v1.4: the BOOK verdict) is on the declared target.
4. **Scope explicit** · **single-shot OOS** (observing = spending; v1.4: ONE spend per book, keyed
   by `book_seal_key`) · **marginal > standalone** · **fail-closed** · **no lookahead** (PIT,
   `is_end` label belt).
5. **Candidate is terminal (v1.4).** No factor-level `approved` is minted; the promotion unit is
   the sealed book (`DeploymentFrozenPlan`/`StrategyCandidate` → `strategy_registry`). The 7
   pre-v1.4 approved rows are legacy evidence (`revalidate_legacy_approved` for validity).

---

## §2 — The freeze-object identity model (the integration spine; resolves S1/S2/S3/S6/S7)

Three freeze objects, **chained by one shared hash** so a universe/selection cannot be silently
represented differently across them.

### §2.1 The chain + equality rule (must-fix #2, #7)

```yaml
TargetUniverseDeclaration (TUD):           # WHO is the investable set
  target_universe_id:
  universe_definition_filters: [ADV floor, listing-age, board/ST/suspension exclude]   # FC4
  eligibility_policy: ; asof_policy: ; declared_at:
  target_universe_declaration_hash:        # sha256 over the above

SelectedSet:                               # WHICH factors (ranking) — Stage 6, IS-only, hash-bound
  target_universe_declaration_hash:        # MUST equal TUD's
  pool_hash: ; selected_representatives: ; selection_code_hash:

FrozenSelectionSet:                        # the frozen ranking identity — Stage 7 (freeze-only, v1.4)
  target_universe_declaration_hash:        # MUST equal TUD's
  universe:                                # = TUD.target_universe_id
  frozen_set_hash:

DeploymentFrozenPlan:                      # the strategy — Stage 8
  frozen_set_hash:                         # references the sealed ranking set (must-fix #7)
  target_universe_declaration_hash:        # MUST equal TUD's (must-fix #7)
  filters: [risk_exclusion, tradability, soft_factor_tail]   # NOT universe-def (those are in TUD)
  combination: ; trade_model: ; capacity: ; pass_fail_bar:
  plan_hash:
```

**Hard skill rule (no equality, no run):**
```
DeploymentFrozenPlan.target_universe_declaration_hash
  == FrozenSelectionSet.target_universe_declaration_hash
  == SelectedSet.target_universe_declaration_hash
  == TUD.target_universe_declaration_hash
AND DeploymentFrozenPlan.frozen_set_hash == FrozenSelectionSet.frozen_set_hash
```
A deployment plan may NOT use a different factor set, universe, or universe-definition filters than the
sealed selection without generating a new TUD + new seal.

### §2.2 Universe-definition filters live in identity, not FilterEvaluation (must-fix #6, FC4)

`filter_role_subtype ∈ {universe_definition, tradability, risk_exclusion, soft_factor_tail}`.
**`universe_definition`** (ADV floor / listing-age / board / ST / suspension) is part of `TUD`
(hashed into `target_universe_declaration_hash`), **excluded from FilterEvaluation**, and — for deployment-bound runs — **declared in the TUD before
Stage 2/3 interpretation (§2.3), then carried unchanged into Stage 6/7/8**. Changing it after results = a new TUD = a new seal. Only the other three subtypes go through
FilterEvaluation (§4 FC2).

### §2.3 Declaration timing — before Stage 2/3 interpretation (must-fix #3)

```
Deployment-bound TUD MUST be declared before Stage-2/3 diagnostics are INTERPRETED for that run.
If Stage 2/3 were viewed first, the declaration is labeled `post_hoc_target_choice` and CANNOT back a
clean deployment-bound FrozenSelectionSet without a signed TargetUniverseOverride (§4 C2).
```
*Why:* `declared_before: stage_6` (the old C3) still allowed "run the 7-universe matrix → see it wins on
microcap → declare small-cap → claim compliance." For a real user strategy the universe is a-priori
(natural); for exploratory runs this prevents the late universe-fork.

---

## §3 — The 8 stages (role-aware, condensed)

Cluster 2–4 = "factor characterization" (one skill step, three outputs). Ranking factors walk 2→7;
filters walk 2–3 → 8; `both` walks both, as **one frozen design** (FC3).

| Stage | Inputs → Outputs | Operative rule |
|---|---|---|
| **0** pre-reg | idea → factor spec + `CohortHypothesis` + `RoleDeclaration` + **`evidence_tier`** (§9) | rationale, expected direction, role+threshold frozen before Stage 6; `evidence_tier ∈ {theory_a_priori, a_priori_is_informed, oos_informed}` |
| **1** define/PIT | spec → `draft` + `definition_hash` | every `$field` in `Ref(...)`; forward-looking filters carry PIT proof (FC7) |
| **2** matrix | draft → per-(factor,universe) IC + cost diagnostics | 7-universe IC + turnover/decay/cost-drag/limit-hit proxies |
| **3** caps | matrix → `quality_flags` + `status_effect` (machine-binding) | **role-aware caps §3.3**; Stage 5/6/7 MUST obey |
| **4** marginal | factor + book → `cohort_redundancy` + `book_marginality` (separate) | selection score = raw direction-aligned IS quality × redundancy penalty (NOT style residual) |
| **5** gate | draft → `candidate` / `filter_candidate` | ranking: `\|icir\|≥0.10 ∧ sign≥0.70` on the **declared target**; **filter: `FilterCharacterization_v1` → `filter_candidate` (NO strategy A/B claim — pass/fail is Stage 8)** |
| **6** select | pool → `SelectedSet` (hash-bound, IS-only) | family caps; Stage-3 caps as hard input; TUD frozen (§2.3) |
| **7 — freeze-only, no OOS observation (v1.4)** | SelectedSet → `FrozenSelectionSet` + `DeploymentFrozenPlan` assembled, §2.1 chain asserted | **NO seal claim, NO OOS access, NO status mint** — everything that differentiates the spend freezes HERE (any unqualified "Stage 7 OOS" reference is invalid) |
| **8 — sole sealed book evaluation (v1.4)** | frozen plan → ONE `HoldoutSealStore` claim keyed by the derived `book_seal_key` → the book verdict + component diagnostics | verdict = event-driven 1× total-return vs the pre-declared `pass_fail_bar` (C5); component diagnostics run INSIDE the same claimed seal (no second claim, no status; `spent_in_book_context=True`, `fresh_oos_eligible=False`, `promotion_eligible=False`); filter pass/fail via `FilterDeploymentGate_v1` (FC1 — same one-shot); CapacityContract (FC5); multiplicity disclosed (FC6/C7 + the A6 virgin budget) |

### §3.3 Role-aware cap resolver (must-fix #5 — the biggest fix; AMENDS C1)

The old C1 `target_universe_pass = NOT liquid_fail ∧ NOT sign_flip_across_core_universes ∧ NOT
coverage_sub` **over-blocks**: it fails a factor that sign-flips in CSI300 even when it is strong and
stable in the **declared** small-cap target. That contradicts dual-scope. Replace with:

> **Layer-separation amendment (2026-06-21):** `liquid_fail` (and `illiquidity_bound`) are **removed
> from factor evaluation entirely** — they were deployment/tradability judgments, which belong to the
> Stage-8 strategy-build deployment gate, not to Stage 3. `target_universe_pass` below depends ONLY on
> the factor signal on the **declared** target (IC / sign / coverage), never on a hardcoded liquid-universe
> verdict. Factor evaluation characterizes the signal; the deployment gate measures tradability.

```yaml
# evaluated ON THE DECLARED TARGET UNIVERSE (not a fixed core set)
target_universe_pass:                       # hard cap for deployment-bound RANKING selection
  require:
    - abs_icir_on_target        >= 0.10      # = CAND_HELDOUT_ICIR_MIN
    - sign_consistency_on_target>= 0.70
    - sign_matches_declared_direction_on_target
    - coverage_ok_on_target     (>= 0.50)   # default; versioned + overridable per target-universe contract
cross_universe_sign_divergence:             # DIAGNOSTIC, not a hard block
  computed_over: [univ_all, liquid_top300, csi300, csi500, csi1000, microcap, growth]   # all 7 Stage-2 domains
  effect: scope_warning (record on the factor)
  hard_block_ONLY_if:
    - a divergent universe is REQUIRED by the TUD, OR
    - the DeploymentFrozenPlan claims cross-universe generality

role routing:
  ranking : obeys target_universe_pass (hard) + cross_universe_sign_divergence (warning)
  filter  : C1/IC caps DO NOT APPLY. factor-eval emits `filter_candidate` via FilterCharacterization_v1
            (PIT / tail / coverage / baseline — NO A/B claim); strategy-build runs FilterDeploymentGate_v1
            (the A/B pass/fail) inside the DeploymentFrozenPlan. + FC4/FC7/FC8
  both    : ranking component obeys target_universe_pass; filter component obeys FC2;
            the StrategyContext includes ONLY the role-components that pass.
```
*Effect:* a declared small-cap strategy is no longer invalidated because a ranker disagrees in CSI300,
unless the strategy actually claims CSI300. Cross-universe divergence becomes a recorded scope warning.

---

## §4 — Contracts (the operative set; condensed, with R4 amendments)

**Identity & scope:** C2 `TargetUniverseOverride` (signed/audited; cannot override a sign-flip on the
target) · C3 `TargetUniverseDeclaration` (now §2; timing per §2.3) · the §2.1 equality chain.
**Stage gates:** C1 `Stage3Thresholds_v1` **as amended by §3.3** (role-aware). **Filters are split into
two contracts across the skill boundary (R1) — the old single `FilterGate_v1`/FC2 is superseded:**
- `FilterCharacterization_v1` (**factor-eval**, Stage 2–5): mechanism subtype + PIT proof + excluded-tail
  return + coverage + threshold + simple-baseline → emits **`filter_candidate`**. **No strategy A/B claim;
  a filter cannot "pass" outside a StrategyContext.**
- `FilterDeploymentGate_v1` (**strategy-build**, Stage 8): the with/without A/B in the frozen plan —
  `risk_exclusion` requires `d_mdd≤0` unless waived; `tradability` = execution feasibility; `soft_factor_tail`
  = tail-underperform + role discipline; all `d_net_sharpe≥min`; joint-filter-set + capacity + baseline-delta
  → **`deployment_component` pass/fail**.
**Selection/seal:** C4 `SelectedSet` · `FrozenSelectionSet` (seal) · FC1 (filters consume the one-shot
`DeploymentFrozenPlan` seal — NOT free/repeatable/tunable on OOS) · C7+FC6 multiplicity disclosure
(ranking pool denominator; filter joint-set-only OOS).
**Deployment:** C5 `DeploymentFrozenPlan` + pre-declared `pass_fail_bar` · FC5 `CapacityContract_v1`
(numeric pass/fail) · FC8 simple-baseline (a complex filter must beat a dumb ADV/age/ST screen).
**Cross-cutting:** FC3 `RoleDeclaration` (role+threshold frozen pre-Stage-6) · FC7 forward-filter PIT
proof · C6/§5 display invariant.

---

## §5 — Role-aware status & display (must-fix #4; AMENDS C6)

Enum value `status ∈ {draft, candidate, approved, deprecated}` is **unchanged** (no rename); the
**display/API is role- and scope-aware**. Never render a bare status, and **never render a filter as
`approved_signal`** (a filter is a strategy-scoped deployment component, not a cross-sectional signal):

```
ranking:  candidate_signal[role=ranking, scope=univ_all, 2010-2020]
          candidate_on_declared_target[role=ranking, tud_hash, IS_window]     (v1.4 terminal)
          approved_signal[LEGACY_per_factor_gate, universe, metric, window]   (pre-v1.4 rows ONLY —
                          never minted again; book membership + verdicts live on strategy_registry)
filter:   filter_candidate[role=filter, strategy_context_hash, IS_window]
          deployment_component[role=filter, plan_hash, pass/fail]
book:     book_verdict[book_seal_key, plan_hash, pass/fail, window]           (the v1.4 promotion object)
both:     <signal_status> AND <filter_status> shown SEPARATELY (two claims, one frozen design)
```

---

## §6 — Lifecycle completeness (must-fix #8, #9)

### §6.1 Revalidation / retirement cadence (#8) — the methodology is no longer one-way

```yaml
RevalidationCadence:
  triggers: [provider_methodology_change, major_universe_regime_change,
             deployment_live_drawdown_breach, scheduled_annual_review,
             pit_canary_failure]                  # e.g. the eps_diffusion restatement-canary revoke
  outcomes: [keep, downgrade approved->candidate (LEGACY factor rows only — v1.4),
             mark deprecated, revoke/downgrade the STRATEGY row (the v1.4 promotion object),
             require new frozen plan + new book seal]
```
A factor/book can decay/retire by rule, not only ad hoc. (The eps_diffusion `approved→candidate`
revocation was exactly this event happening informally; now it has a home. v1.4: legacy-row validity
re-affirmation goes ONLY through `revalidate_legacy_approved(...)` — `set_approval_validity` refuses
'valid' on approved rows and the old `set_status('approved')` escape is retired.)

### §6.2 Selected-set interaction check (#9) — beyond pairwise marginal, IS-only

Before the Stage-7 freeze (and hence before the Stage-8 spend), on the SelectedSet (IS only):
```yaml
interaction_check:
  remove_one: marginal IS effect of dropping each rep
  add_one:    marginal IS effect of each near-miss candidate
  pair_flag:  flag highly-correlated OR sign-opposed pairs that are jointly destructive under
              the StrategyContext's weighted-rank combination
```
Guards against two individually-useful factors that cancel jointly under rank-sum.

---

## §7 — End-to-end (assembled, both cases)

- **E-wave 6-core.** Stage 2 matrix + Stage 3 (role-aware, **signal-only**) flags sign-divergence +
  emits the per-universe IC profile (NO liquid/illiquidity deployment verdict). Stage 6 **selecting on
  the declared liquid target** naturally down-weights liquid-weak reps (their IC on the liquid target is
  weak — no Stage-3 deployment flag needed); Stage 7 freezes the set+plan on the **declared** target
  (v1.4: no OOS observation here — the E-wave's separate factor-level OOS spend is exactly what v1.4
  retires); **Stage 8** (the
  strategy-build deployment gate) is where "fails on liquid_top300" is actually measured — via the
  event-driven backtest, not a factor-eval flag. **Note §3.3:** on a *small-cap* target the same factors
  are NOT over-blocked by CSI300 divergence — scope-specific, not universal.
- **果仁 small-cap strategy.** ADV/listing/ST/suspension → `universe_definition` in TUD (§2.2). 退市/
  违规/解禁 → `risk_exclusion` (FC2 + FC7 PIT proof). 负债率/乖离率 → `soft_factor_tail` (FC3 pre-reg).
  9 rankers → marginal IC vs each other on the declared small-cap universe (§4), with §6.2 interaction
  check. Whole = one DeploymentFrozenPlan with FC5 capacity pass/fail. TUD declared a-priori (§2.3,
  natural for a real strategy).

---

## §8 — Skill decomposition: TWO skills (split at the factor↔strategy boundary)

**`factor-eval` skill = Stages 0–7** (register → freeze): strategy-agnostic factor certification +
characterization → produces the factor library. **`strategy-build` skill = Stage 8**: strategy-specific
construction/optimization + the deployment gate → consumes the library. **Seam:** the
`TargetUniverseDeclaration` (declared before deployment-bound factor work) + the factor-library hand-off
(`strategy-build` receives `{target_universe_declaration_hash, frozen_set_hash, selected_set_hash, candidate_refs}` — v1.4: candidate/characterization refs, never `approved_signal_refs` (retired) — +
`filter_candidate`s + the library, and **refuses to run on any hash mismatch — §2.1 equality chain**).
`maintain` (§6.1) is a standing cross-cutting process, not a step of either skill. Filters get cheap
tail-characterization in `factor-eval` (Stage 2–3) but their pass/fail A/B is in `strategy-build` (Stage 8).

```
# ══ factor-eval skill (Stages 0–7, strategy-agnostic) ══
register      : Stage 0-1  + CohortHypothesis + RoleDeclaration + PIT proof
declare_target : TargetUniverseDeclaration builder+checker → target_universe_declaration_hash
                 (deployment-bound: REQUIRED before characterize interpretation — §2.3)
characterize   : Stage 2-4  (matrix / role-aware caps / marginal — 3 outputs)
gate          : Stage 5    role-aware cap resolver (ranking target caps | FilterCharacterization_v1 | both)
select         : Stage 6    SelectedSet (hash-bound) + §6.2 interaction_check (IS-only, PRE-freeze)
freeze         : Stage 7 — freeze-only, no OOS observation (v1.4): FrozenSelectionSet +
                 DeploymentFrozenPlan assembled, §2.1 chain asserted; NO seal, NO OOS, NO status
# ══ strategy-build skill (Stage 8, strategy-specific; consumes the factor library) ══
evaluate_book : Stage 8 — sole sealed book evaluation (v1.4): ONE HoldoutSealStore claim keyed by
                 the derived book_seal_key → book event-driven 1× total-return verdict vs the
                 pre-declared bar + component diagnostics inside the SAME seal
                 (run_component_diagnostics_in_book_context; no second claim) → promotion writes to
                 strategy_registry (StrategyCandidate; A8: unavailable until that path is
                 implemented+tested — no virgin spend before it)
maintain       : §6.1 RevalidationCadence ONLY  (interaction_check is PRE-freeze, in `select`, NOT maintenance;
                 "downgrade approved->candidate" applies to LEGACY factor rows + the strategy-row equivalent)

skill_mode:
  deployment_bound     : register → declare_target → characterize → gate → select(+interaction) → freeze → evaluate_book → maintain
                         declare_target REQUIRED before characterize interpretation (§2.3); §2.1 equality chain enforced before select/freeze/evaluate_book.
  exploratory_research : register → characterize → optional declare_target. A target declared AFTER characterize =
                         post_hoc_target_choice → NO clean deployment-bound FrozenSelectionSet without a signed TargetUniverseOverride (§4 C2).
  a5_replication_study : a statusless factor-level sealed-OOS study (arXiv-batch shape) — seal-accounted in the
                         D6 ledger, mints NO status, taints overlapping downstream books on that window; a FRESH
                         (virgin) window requires a pre-recorded fresh_window_signal_replication_override_id and
                         counts against the A6 budget.
```
The 4 first-class new steps GPT named (TUD builder, RoleDeclaration resolver, role-aware cap resolver,
DeploymentFrozenPlan assembler) are explicit above. Part-G new code: the Stage-3 machine-binding reader
+ the generalized marginal-contribution tool + these 4 steps.

---

## §9 — Evidence provenance tiers (minimal load-bearing; full spec in the provenance patch)

Every Stage-0 pre-reg carries `evidence_tier ∈ {theory_a_priori, a_priori_is_informed, oos_informed}`
(GPT-approved minimal form; v1.3 self-contained — schema inlined; the patch
[FACTOR_EVAL_STAGE0_EVIDENCE_PROVENANCE_v1.md](FACTOR_EVAL_STAGE0_EVIDENCE_PROVENANCE_v1.md) is the rationale).
```yaml
Stage0EvidenceProvenance_v1:
  evidence_tier: theory_a_priori | a_priori_is_informed | oos_informed
  direction_source: external_theory | literature | mechanism | IS_aggregate | OOS_observed | mixed
  is_seen_before_direction: bool ; oos_seen_before_claim: bool ; prior_contradicted_by_is: bool
  may_cite_is_as_confirmation:  # derived: theory_a_priori -> true ; else -> false
  fresh_oos_eligible:           # derived: oos_informed -> false ; else -> true
  multiplicity_scope_id:        # required if evidence_tier != theory_a_priori OR cohort/family expansion
```

**Core rule:** for `a_priori_is_informed`, IS may GENERATE the hypothesis/direction but may NOT be cited
as confirming evidence ("OOS-clean, IS-spent"). **The IS candidate bar is UNCHANGED by tier** — only what
an IS pass is allowed to MEAN changes.

**4 hard wiring points (a runnable skill must read all four, else the tier is inert):**
1. **reports** read `may_cite_is_as_confirmation` → forbid "IS confirmed the prior" wording for `a_priori_is_informed`.
2. **Stage 6/7 OOS report** reads `multiplicity_scope_id` → discloses the screened-pool denominator; labels the OOS "first independent confirmation" for `a_priori_is_informed`; FDR/max-stat at the selected-set/family level.
3. **deployment / revalidation (§6.1)** read `evidence_tier` → tighter monitoring + faster post-approval downgrade for `a_priori_is_informed` (not a fake-precision sizing formula).
4. **seal logic** reads `fresh_oos_eligible` → `oos_informed` makes no fresh-OOS approval claim.

Sign-flip vs a committed prior → `prior_contradicted_by_is=true` + downgrade `theory_a_priori →
a_priori_is_informed`, never a silent flip. It is a **field inside the provenance/multiplicity object,
not a parallel status universe**, and **not redundant** with multiplicity disclosure (it triggers + classifies it).

---

## §10 — Execution binding (exact machinery per step; resolves the adaptation-audit ambiguities)

A runnable skill binds each step to a NAMED tool. `call` = existing, reuse verbatim. `build` = Part-G new
code (then call). The 9 audit ambiguities are resolved inline (⊕). (Detail: `FACTOR_EVAL_SYSTEM_ADAPTATION_AUDIT.md`.)

- **Stage 0 register** — `build` a `Stage0EvidenceProvenance` store. ⊕#7 **no existing home**:
  `hypothesis_cli`/`Hypothesis` is a strategy+OOS object (mandatory universe + sealed window) — do NOT
  overload it. The factor *spec* goes in the catalog (Stage 1); the pre-reg record (rationale /
  expected_direction / role / evidence_tier / cohort) is the new store.
- **Stage 1 define→draft** — `call`: edit `factor_library/catalog.py:get_factor_catalog` (use `ADJ_*_T1`)
  → `factor_library/selection.py:sync_catalog_to_registry()` writes status `draft`; hash via
  `current_catalog_definition_hashes()`. ⊕#2 **PIT = TWO checks**: `pytest
  tests/alpha_research/test_factor_library_pit_safety.py` (Ref-wrapping) **AND** `python
  scripts/lint_no_unsafe_pit_dates.py` (ledger/date). Field eligibility: `FieldStatusRegistry.validate_expression`
  vs `config/field_registry/field_status.yaml`. ⊕#3 **PIT anchor for statement fundamentals is NOT in
  `data_dictionary.md`** → use CLAUDE.md §3.2 / `pit_backend.py` (`max(ann_date,f_ann_date)+shift(1)`).
- **Stage 2 matrix** — `call`: `venv/Scripts/python.exe workspace/scripts/unified_eval_universe_matrix.py
  [--factors <ids>]` → `workspace/outputs/unified_eval_matrix/results.jsonl` (7 universes;
  `resid_ic_vs_style_controls_v1_*`, `resid_ic_vs_approved_stable_*`, `decay_icir_*`, `turnover_ann`).
  ⊕#8 turnover-normalized IC = `|heldout_rank_icir|/turnover_ann`; cost-drag = `turnover_ann × 25bps`
  (eval cost default) — **derive (not emitted)**; `long_leg_excess_ann_*` are NET, CSI300/500-only.
  `build` the limit-hit proxy (genuine gap).
- **Stage 3 caps** — `call` the lattice `factor_registry/replication_governance.py:resolve_replication_ceiling`
  (`coverage_sub` ≡ `coverage_tier=='sub'` → `availability_floor_fail`); map `status_effect` onto
  `STATUS_CEILINGS` (no parallel universe). `build` the cross-universe FACTOR-SIGNAL flag
  (`sign_flip_across_core_universes`) + the per-universe IC profile over the 7 rows. **NO deployment
  judgments**: `liquid_fail` / `illiquidity_bound` were REMOVED (2026-06-21) — deployability is the
  Stage-8 strategy-build gate's job, never factor evaluation's.
- **Stage 4 marginal** — `build` (parameterize `select_e_wave_marginal.py`'s greedy); `book_marginality`
  = `call` the matrix `resid_ic_vs_approved_stable_*` (read, don't recompute); primitive
  `ic_analysis.py:compute_marginal_ic`.
- **Stage 5 gate** — `call` rule `factor_lifecycle/status_rules.py:assign_candidate_status`
  (|icir|≥0.10 ∧ sign≥0.70). ⊕#1 **PATH RULE:** factor with a matrix run → generalized matrix-reuse
  promote (`build`, parameterized — NEVER clone `promote_e1x`); no matrix → orchestrator
  (`research_orchestrator_cli.py run` + `phase6_setup_request.py` + `phase6_drive_gates.py`).
  `set_status('candidate')` ungated; human gate publishes.
- **Stage 6 select** — `build` the `SelectedSet` schema + `target_universe_declaration_hash` (only
  `FrozenSelectionSet` exists); `build` `interaction_check`.
- **Stage 7 — freeze-only (v1.4; the old "Stage 7 seal" binding is RETIRED)** — `call`:
  `identity.py` `FrozenSelectionSet`/`FrozenSelectionEnvelope` + `DeploymentFrozenPlan` assembly +
  `assert_identity_chain`. **NO `claim_holdout_access`, NO `reproduce_sealed_oos`, NO
  `set_status('approved')`** — `FactorRegistryStore.set_status('approved')` now raises
  `FactorLevelApprovedRetiredError` unconditionally (A3; the audited doors are
  `legacy_factor_approval_override` / `revalidate_legacy_approved`).
- **Stage 8 — the sole sealed evaluation (v1.4)** — `call`: derive
  `identity.py:BookSealIdentity.from_plan(...)` → ONE
  `holdout_seal.py:HoldoutSealStore.claim_holdout_access(seal_key=book_seal_key)` (no
  `design_hash`/`frozen_set_hash` fallback) → the book event-driven leg (`EventDrivenBacktester` +
  the declared formal profile, 1× total return, vs the pre-declared bar) + component diagnostics
  via `run_component_diagnostics_in_book_context(...)` INSIDE the same claimed context (PR3 `build`;
  a bare `run_sealed_oos(..., claim_seal=False)` fails closed and is NOT a reuse path — round-2 N3)
  → `OosWindowLedgerStore.record_book_spend(...)` + `virgin_window_multiplicity(...)` enforced
  BEFORE the claim on virgin windows (A6) → promotion via `StrategyRegistryStore` (A8 readiness).
  ⊕#4 **pin `n_quantiles=10`** (decile) for the diagnostics leg. ⊕#5 **OOS spend ≠ auto-promote**:
  the run spends+records the verdict; the strategy-registry write is a SEPARATE authorized step.
  ⊕#6 the old factor bar (sign-aligned `rank_icir>0 ∧ ls_sharpe>1.0`) survives only as a diagnostic
  reference line, never a gate. ⊕#9 the OOS leg runs `stage='oos_test'` + the seal-claimed
  `ResearchAccessContext` (`holdout_seal_claimed=True`, `seal_key=book_seal_key`), NEVER
  `compute_factors`' default `CacheContext`.
- **Stage 8 engine bindings (unchanged mechanics under the v1.4 seal rule above)** — `call`
  `EventDrivenBacktester` + `CostConfig.realistic_china()` (or the declared formal profile) +
  `RankedFallbackStrategy` / the PR2 `WeightedTargetStrategy` seam + `long_only_50cagr/research_utils.py`;
  `build` the `DeploymentFrozenPlan` assembler + `CapacityContract_v1` + `FilterDeploymentGate_v1` A/B
  + `run_component_diagnostics_in_book_context` (PR3).
- **qlib compute (all stages)** — `call` `operators.py:compute_factors(catalog, start, end, …, stage=)`
  (→ `qlib_windowed_features`); NEVER bare `D.features` (`lint_no_bare_qlib_features.py`). `stage='oos_test'` for OOS.
- **provider pre-flight (formal/OOS)** — `call` `provider_manifest.py:load_provider_manifest` +
  `validate_provider_manifest_against_qlib`: namespacing `enforced`, calendar_end == `2026-02-27`,
  run_mode ∈ policy `allowed_modes`.

## §11 — Future-applicability self-review (works for NEW factors, not just past)

The CORE (matrix, IS-gate rule, seal spine, backtester, qlib compute, provider gates) is **generic** — it
scores/gates/seals ANY catalog factor → future-applicable. Four forward-looking constraints the skill MUST honour:

1. **Build Part-G GENERIC; prove on a NON-E-wave factor.** The existing wrappers (`promote_e1*`,
   `select_e_wave_*`, `eval_e_wave_*`) are hard-bound to the CICC cohort (prefix / pool-size / caps /
   refs). The Part-G generalization MUST be parameterized (factor-set-agnostic, universe-declared) and its
   **acceptance test MUST run a non-E-wave factor end-to-end** — else it reincarnates the clone-per-cohort
   anti-pattern under a new name.
2. **New-data factors need the data-infra pipeline FIRST.** factor-eval ASSUMES the `$fields` exist
   (ingest → PIT ledger → provider → field registry → data dictionary, CLAUDE.md §6). A future factor on a
   NEW field is blocked at Stage 1 until data-infra lands it. **Boundary: factor-eval is not a data-ingestion skill.**
3. **Shared, bounded OOS windows — MITIGATED by v1.4 (was "the sharpest forward-looking gap").**
   (a) a genuinely-forward OOS still requires **advancing the provider/calendar**; the post-2026-02-27
   accrual (calendar unfreeze) is the only virgin window the current candidate pool will ever have.
   (b) v1.4 attacks the multiplicity accumulation directly: per-factor spends are RETIRED (one spend
   per BOOK, `book_seal_key`-keyed), the Stage-7→Stage-8 sequential double-observation is gone
   (freeze before observe), the D6 ledger counts spend-unit keys, and virgin windows carry a HARD
   budget (warn 3 / hard 5 distinct `book_seal_key` spends per window, `virgin_window_multiplicity`,
   refuse-without-pre-recorded-override). Residual (PR5): recipe-search effective-trials deflation —
   required, and NOT a substitute for the hard budget.
4. **`evidence_tier` is the forward-looking honesty hook.** As the same IS/OOS windows get re-used across
   future factors, the tier (theory_a_priori vs a_priori_is_informed) + the cross-factor spend count keep a
   future factor's evidence from being over-claimed. Wire them, or future evaluations silently inflate confidence.

---

*v1.3 history: round-5 residual fixes applied in-place (§8 reordered; §3.3 added `growth`; §2.2
wording aligned). v1.4 (2026-07-03): the book-level-promotion amendment folded — its own 4-round GPT
arc (REVISE×3→SHIP, 18+3+3 findings all accepted, none declined) is recorded in
[FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md](FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md) §9.*

*v1.4 is the single source of truth. v1.3 + the 4 earlier docs + responses are the design history.
Implementation status: A3 writer gate / A7 scope gate / A6 D6 extension / `BookSealIdentity` are
LIVE (tests green, see the amendment §5 matrix); the book-seal wiring + component-diagnostics helper
land with PR3 (A8: no virgin spend before then).*
