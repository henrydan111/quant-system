# Factor Evaluation Methodology — v1.3 (consolidated single source of truth)

> **v1.3 is THE operative methodology.** It supersedes the incremental docs (which remain the design
> history/audit trail). A runnable skill reads **only this file**. Produced after GPT 5.5 Pro's
> 4-round review converged the design: R1 CHANGES→v1.1 · R2 cond→C1–C7 · R3 cond→v1.2 roles + FC1–FC8
> · **R4 (holistic) FINAL MUST-FIX → this v1.3** (resolves 9 cross-document seam/integration defects).
>
> **Precedence (machine-readable).** On any conflict, v1.3 wins.
> ```
> FACTOR_EVAL_METHODOLOGY_v1.3 (this)         SUPERSEDES ALL below
>   ← FACTOR_EVAL_FILTER_CONTRACTS_v1 (FC1-FC8; incl. the v1.2 §H1/§H3 amendments)
>   ← FACTOR_EVAL_METHODOLOGY_v1.2_addendum (roles, FilterEvaluation, StrategyContext)
>   ← FACTOR_EVAL_CONTRACTS_v1 (C1-C7)        [C1 sign-flip cap AMENDED here — §4/§3.3]
>   ← FACTOR_EVAL_METHODOLOGY_v1.1 (architecture, dual-scope)
> ```

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
   `approved` is on the FrozenSelectionSet universe.
4. **Scope explicit** · **single-shot OOS** (observing = spending, keyed by hashes) ·
   **marginal > standalone** · **fail-closed** · **no lookahead** (PIT, `is_end` label belt).

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

FrozenSelectionSet:                        # the sealed ranking identity — Stage 7
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
| **7** OOS | FrozenSelectionSet → `approved[scope]` | ranking only; seal keyed by `frozen_set_hash` on the **target universe**; multiplicity disclosed (FC6/C7) |
| **8** deploy | DeploymentFrozenPlan → deployability **metadata** | **filter pass/fail via `FilterDeploymentGate_v1`** (A/B inside the one-shot plan, FC1); CapacityContract pass/fail (FC5) |

### §3.3 Role-aware cap resolver (must-fix #5 — the biggest fix; AMENDS C1)

The old C1 `target_universe_pass = NOT liquid_fail ∧ NOT sign_flip_across_core_universes ∧ NOT
coverage_sub` **over-blocks**: it fails a factor that sign-flips in CSI300 even when it is strong and
stable in the **declared** small-cap target. That contradicts dual-scope. Replace with:

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
          approved_signal[role=ranking, universe=liquid_top300, metric=5d_decile_LS, 2021-2026]
                          deployable_on_<u>: yes/no/untested
filter:   filter_candidate[role=filter, strategy_context_hash, IS_window]
          deployment_component[role=filter, plan_hash, pass/fail]
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
  outcomes: [keep, downgrade approved->candidate, mark deprecated, require new FrozenSelectionSet]
```
A factor can decay/retire by rule, not only ad hoc. (The eps_diffusion `approved→candidate` revocation
was exactly this event happening informally; now it has a home.)

### §6.2 Selected-set interaction check (#9) — beyond pairwise marginal, IS-only

Before Stage 7/8, on the SelectedSet (IS only):
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

- **E-wave 6-core.** Stage 2 matrix + Stage 3 (role-aware) flags illiquidity_bound/sign-divergence →
  Stage 6 excludes liquid-failing reps **for a liquid target**; Stage 7 seal on the **declared** target;
  Stage 8 frozen plan (not a naive composite). **Note §3.3:** on a *small-cap* target the same factors
  are NOT over-blocked by CSI300 divergence — the E-wave "failed on liquid_top300" verdict is
  scope-specific, not universal.
- **果仁 small-cap strategy.** ADV/listing/ST/suspension → `universe_definition` in TUD (§2.2). 退市/
  违规/解禁 → `risk_exclusion` (FC2 + FC7 PIT proof). 负债率/乖离率 → `soft_factor_tail` (FC3 pre-reg).
  9 rankers → marginal IC vs each other on the declared small-cap universe (§4), with §6.2 interaction
  check. Whole = one DeploymentFrozenPlan with FC5 capacity pass/fail. TUD declared a-priori (§2.3,
  natural for a real strategy).

---

## §8 — Skill decomposition: TWO skills (split at the factor↔strategy boundary)

**`factor-eval` skill = Stages 0–7** (register → seal): strategy-agnostic factor certification +
characterization → produces the factor library. **`strategy-build` skill = Stage 8**: strategy-specific
construction/optimization + the deployment gate → consumes the library. **Seam:** the
`TargetUniverseDeclaration` (declared before deployment-bound factor work) + the factor-library hand-off
(`strategy-build` receives `{target_universe_declaration_hash, frozen_set_hash, selected_set_hash, approved_signal_refs}` +
`filter_candidate`s + the library, and **refuses to run on any hash mismatch — §2.1 equality chain**).
`maintain` (§6.1) is a standing cross-cutting process, not a step of either skill. Filters get cheap
tail-characterization in `factor-eval` (Stage 2–3) but their pass/fail A/B is in `strategy-build` (Stage 8).

```
# ══ factor-eval skill (Stages 0–7, strategy-agnostic) ══
register      : Stage 0-1  + CohortHypothesis + RoleDeclaration + PIT proof
declare_target : TargetUniverseDeclaration builder+checker → target_universe_declaration_hash
                 (deployment-bound: REQUIRED before characterize interpretation — §2.3)
characterize   : Stage 2-4  (matrix / role-aware caps / marginal — 3 outputs)
gate          : Stage 5    role-aware cap resolver (ranking target caps | FilterGate | both)    [#5 step]
select         : Stage 6    SelectedSet (hash-bound) + §6.2 interaction_check (IS-only, PRE-seal)
seal           : Stage 7    FrozenSelectionSet → sealed OOS
# ══ strategy-build skill (Stage 8, strategy-specific; consumes the factor library) ══
deploy        : Stage 8    StrategyContext/DeploymentFrozenPlan assembler (binds rankers+filters+
                           universe-def filters+trade model+capacity+pass/fail+seal refs)        [assembler step]
maintain       : §6.1 RevalidationCadence ONLY  (interaction_check is PRE-seal, in `select`, NOT maintenance)

skill_mode:
  deployment_bound     : register → declare_target → characterize → gate → select(+interaction) → seal → deploy → maintain
                         declare_target REQUIRED before characterize interpretation (§2.3); §2.1 equality chain enforced before select/seal/deploy.
  exploratory_research : register → characterize → optional declare_target. A target declared AFTER characterize =
                         post_hoc_target_choice → NO clean deployment-bound FrozenSelectionSet without a signed TargetUniverseOverride (§4 C2).
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

*Round-5 residual fixes applied in-place: §8 reordered (declare_target before characterize; interaction_check moved to the pre-seal `select` step), §3.3 added `growth` to the cross-universe divergence domains, §2.2 wording aligned to §2.3. Architecture unchanged — GPT confirmed the core model coherent.*

*v1.3 is the single source of truth. The 4 prior docs + 2 responses are the design history. If GPT's
final confirmation is "coherent + skill-ready," codify §8 as the `factor-eval` skill.*
