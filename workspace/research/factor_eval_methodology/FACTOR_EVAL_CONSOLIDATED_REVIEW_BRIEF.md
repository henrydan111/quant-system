# Factor Eval Methodology — consolidated review brief (final holistic pass before skill codification)

> **For GPT 5.5 Pro.** Three incremental rounds each approved a *delta* (R1→v1.1, R2→C1–C7,
> R3→v1.2 roles). This is the **first review of the assembled whole** — plus a confirmation that
> **FC1–FC8** (my response to round-3, not yet GPT-seen) actually closes round-3's conditions. Two
> asks: **(1)** do FC1–FC8 adequately close round-3? **(2)** is the *assembled* methodology
> internally coherent, complete, and ready to codify as a runnable skill — or do the seams between
> the 4 documents contradict each other? Be adversarial about the seams, not the already-approved
> parts.

## The complete methodology in one map

```
LAYERS (never conflated):  factor-signal-validation  |  strategy-deployability
ROLES:                     ranking (排名条件)         |  filter (筛选条件)  |  both

STAGES (each: Inputs/Outputs/Why; bound to real machinery):
 0 pre-reg (+ CohortHypothesis, RoleDeclaration[FC3])
 1 definition / PIT-safety / field-eligibility → draft        (+ FC7 PIT proof for forward filters)
 2 universe-stratified IC matrix + cost diagnostics  ← cheap insurance
 3 scope-stamped MACHINE-BINDING caps (Stage3Thresholds_v1[C1])  → Stage 5/6/7 MUST obey
 4 marginal: cohort_redundancy  vs  book_marginality (separate)
 5 IS gate → candidate     [ranking: |icir|≥0.10 ∧ sign≥0.70]   [filter: FilterGate_v1 / FC2]
 6 family-aware selection → SelectedSet[C4] (hash-bound, IS-only)
 7 sealed OOS → approved   [ranking only; HoldoutSeal keyed by frozen_set_hash, on the target universe]
 8 deployment gate         [DeploymentFrozenPlan[C5]+pass/fail bar; FILTERS validated here via strategy A/B]

DUAL-SCOPE (§A4): research candidate (univ_all, scope-stamped) ≠ deployment-bound (target investable
                  universe, e.g. univ_liquid_top300 OR a declared small-cap ESTU) ≠ approved[scope].
STATUS MODEL: scope-stamped single enum (display: approved_signal[universe,metric,window] +
              deployable_on_<u>: yes/no/untested); NEVER a status×universe matrix. Deployability = metadata.
STRATEGYCONTEXT: evaluation binds to the ACTUAL strategy (universe + factor set + weighted-rank
                 combination + trade model + capacity), not an abstract book.
```

Contracts: **C1–C7** (Stage-3 thresholds, target-universe override+declaration, SelectedSet,
DeploymentFrozenPlan pass/fail, display invariant, multiplicity disclosure). **FC1–FC8** (filter OOS
budget, FilterGate_v1, RoleDeclaration, universe-definition-filter separation→C3, CapacityContract_v1,
filter multiplicity, forward-filter PIT proof, simple-baseline).

## The 6 source documents (permalinks @ `9d2e8f9`)

| doc | what |
|---|---|
| [v1.1](https://github.com/henrydan111/quant-system/blob/9d2e8f9934bc6575bf65465fef579647b5b75328/workspace/research/factor_eval_methodology/FACTOR_EVAL_METHODOLOGY_v1.1.md) | architecture: 8 stages, dual-scope, layer separation |
| [CONTRACTS_v1](https://github.com/henrydan111/quant-system/blob/9d2e8f9934bc6575bf65465fef579647b5b75328/workspace/research/factor_eval_methodology/FACTOR_EVAL_CONTRACTS_v1.md) | C1–C7 (round-2 conditions) |
| [v1.2 addendum](https://github.com/henrydan111/quant-system/blob/9d2e8f9934bc6575bf65465fef579647b5b75328/workspace/research/factor_eval_methodology/FACTOR_EVAL_METHODOLOGY_v1.2_addendum_factor_roles.md) | factor roles + FilterEvaluation + StrategyContext |
| [FILTER_CONTRACTS_v1](https://github.com/henrydan111/quant-system/blob/9d2e8f9934bc6575bf65465fef579647b5b75328/workspace/research/factor_eval_methodology/FACTOR_EVAL_FILTER_CONTRACTS_v1.md) | **FC1–FC8 (round-3 conditions — confirm these close it)** |
| [response r1](https://github.com/henrydan111/quant-system/blob/9d2e8f9934bc6575bf65465fef579647b5b75328/workspace/research/factor_eval_methodology/FACTOR_EVAL_METHODOLOGY_v1_cross_review_response.md) | r1 dispositions |

(raw: swap `/blob/` → `/raw/`.)

## The seams to scrutinize (where assembled contradictions would hide)

1. **Three "freeze" objects — one discipline?** `FrozenSelectionSet` (Stage 7 ranking seal),
   `DeploymentFrozenPlan` (Stage 8 strategy, incl. filters via FC1), `TargetUniverseDeclaration`
   (C3, incl. universe-definition filters via FC4). Do their universe/seal/identity fields compose
   without overlap or gap? Can a factor's universe be declared inconsistently across the three?
2. **Role × scope × seal.** A `both`-role factor (FC3) is a ranking signal (→ Stage 7 seal on the
   target universe) AND a filter (→ Stage 8 plan). Is its OOS budget double-counted or coherent?
3. **C3 vs FC4.** Universe-definition filters now live in `TargetUniverseDeclaration` (C3) and are
   excluded from `FilterEvaluation`. Does any earlier text still route them through the filter gate?
4. **Stage-3 caps (C1) vs the dual-scope (§A4) vs FC2.** `target_universe_pass` (C1) gates
   `oos_eligible`; FilterGate_v1 (FC2) is separate. For a `both` factor, which caps apply to which
   role, and can they conflict (ranker-eligible but filter-failed, or vice-versa)?
5. **Display invariant (C6) vs the role dimension.** Should the rendered label also carry role
   (`approved_signal[ranking, liquid_top300, …]` vs a filter's strategy-scoped status)? Is there a
   coherent display for a `both` factor?

## Holistic questions

- **A. Does FC1–FC8 close round-3?** Especially: FC1 (filters consume the one-shot deployment OOS),
  FC4 (universe-definition filters frozen at C3, not Stage 8), FC2 (mechanism-specific bars). Gaps?
- **B. Internal coherence.** Walk the 5 seams above. Any contradiction, double-count, or gap between
  the 4 documents when assembled?
- **C. Completeness.** Can a factor go idea → deployed strategy component end-to-end with no
  orphaned stage/role/contract? Is anything still missing (e.g., factor *retirement*/deprecation,
  re-validation cadence, multi-factor *interaction* effects beyond pairwise marginal)?
- **D. Skill-readiness.** Is each stage's I/O + contract concrete enough to become runnable skill
  steps? Is the Part-G build list (Stage-3 machine-binding reader; generalized marginal-contribution
  tool; display invariant) the correct minimal new code, or is more required before it can run?
- **E. End-to-end stress.** Trace BOTH worked cases through the *assembled* methodology: (i) the
  E-wave 6-core (would Stage 3 have stopped it pre-OOS?); (ii) the user's 果仁 small-cap multi-factor
  strategy (9 rankers + 6 filters split by role/subtype, on a declared small-cap universe with
  capacity). Does either expose a missing rule?
- **F. Emergent concerns.** Anything that is only visible now that the whole is assembled — not
  caught in the per-delta reviews.

## Decision requested

Either **"FC1–FC8 closes round-3 AND the assembled methodology is coherent + skill-ready"** (→ we
codify the skill), or a final consolidated list of must-fix coherence/completeness items before it
becomes the standing skill.
