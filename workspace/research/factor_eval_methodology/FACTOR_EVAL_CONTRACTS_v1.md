# Factor Eval — Implementation Contracts v1 (closes GPT 5.5 Pro round-2 conditions)

> **GPT 5.5 Pro round-2 verdict: APPROVE WITH CONDITIONS** (against v1.1 @ `ac4c8a6`). The
> architecture is signed off as governing; v1.1 may not drive **live status/OOS decisions** until 6
> implementation contracts + 3 visibility concerns are made explicit. This document is those
> contracts. **Disposition: ALL ACCEPTED** — the conditions are sound and several reuse machinery we
> already have (so they are cheap to wire). Linked from [v1.1](FACTOR_EVAL_METHODOLOGY_v1.1.md).
>
> Grounding note: thresholds reuse existing constants rather than invent parallel numbers —
> `CAND_HELDOUT_ICIR_MIN=0.10` / `CAND_SIGN_CONSISTENCY_MIN=0.70` (`factor_lifecycle/status_rules.py`),
> the P-GATE `coverage_tier=='sub'` / `availability_floor_fail` (seen in E1g/E1h), and the
> `FrozenSelectionSet` hash fields (`candidate_pool_hash`, `selection_rule_hash`, `eval_protocol_hash`,
> `universe`). `EWaveSelectedSet_v2.json` is the proto-`SelectedSet`; `cicc_price_volume_cohort_v2.yaml`
> the proto-`CohortHypothesis`.

## Disposition of round-2 conditions

| # | Condition | Status | Contract |
|---|---|---|---|
| 1 | Stage-3 cap thresholds | ✅ | `Stage3Thresholds_v1` (C1) |
| 2 | "explicitly accepted" override path | ✅ | `TargetUniverseOverride` (C2) |
| 3 | Target universe pre-registered | ✅ | `TargetUniverseDeclaration` (C3) |
| 4 | `SelectedSet` artifact mandatory before OOS | ✅ | `SelectedSet` (C4) |
| 5 | `DeploymentFrozenPlan` pass/fail bar | ✅ | C5 (adds `pass_fail_bar`) |
| 6 | UI/API: no bare status; scope by default | ✅ | C6 (display invariant, **prioritized early**) |
| A | Stage-7 bar multiplicity disclosure | ✅ | C7 (visible, not blocking) |
| B | `candidate` crowding → display is core governance | ✅ | folded into C6 (moved up the build list) |
| C | `DeploymentFrozenPlan` must freeze failure criteria | ✅ | folded into C5 |

---

## C1 — `Stage3Thresholds_v1` (the numeric rules behind the binding caps)

Versioned + hashed; Stage 5/6/7 read the *flags*, not raw thresholds.

```yaml
Stage3Thresholds_v1:
  # reuses the live IS-gate constants (status_rules.py) so a flag agrees with the gate
  _min_abs_icir: 0.10            # = CAND_HELDOUT_ICIR_MIN
  _min_sign_consistency: 0.70    # = CAND_SIGN_CONSISTENCY_MIN
  _core_universes: [univ_all, univ_liquid_top300, univ_csi300, univ_csi500, univ_csi1000]
  _min_coverage_for_judgement: 0.50   # below this an icir is "insufficient coverage", not a fail

  liquid_fail:               # on the declared target universe
    require: {abs_icir >= _min_abs_icir, sign_consistency >= _min_sign_consistency,
              sign matches declared_direction, coverage >= _min_coverage_for_judgement}
    flag_true_if: any requirement unmet
  sign_flip_across_core_universes:
    flag_true_if: in any _core_universe with coverage >= _min_coverage_for_judgement,
                  sign(icir) != declared_direction
  illiquidity_bound:
    flag_true_if: passes (univ_all OR univ_microcap) AND fails univ_liquid_top300
  coverage_sub:
    flag_true_if: coverage_tier == 'sub' OR availability_floor_fail   # the P-GATE reason
  short_window:
    flag_true_if: effective_ic_days < 1000      # ~4y; E1g's 2017-2020 hk_hold tripped this class
  high_turnover_cost_risk:
    flag_true_if: est_one_way_cost_drag_annual > _cost_ratio * abs(gross_long_leg_excess_ann)
    _cost_ratio: 0.50
  target_universe_pass:
    flag_true_if: NOT liquid_fail AND NOT sign_flip_across_core_universes AND NOT coverage_sub

status_effect:               # derived; what Stage 5/6/7 obey
  candidate_scope: target_eligible if target_universe_pass else research_only
  oos_eligible: target_universe_pass OR has_valid TargetUniverseOverride
  deployment_bound_selection_allowed: target_universe_pass OR has_valid TargetUniverseOverride
```

*Why these numbers.* They are the *same* bars the IS gate already uses, so Stage 3 can never
contradict Stage 5. The flags are versioned (`_v1`) and revisable, but they **exist** before any live
read — closing GPT's "binding in name, discretionary in practice" gap.

## C2 — `TargetUniverseOverride` (the constrained, audited escape hatch)

```yaml
TargetUniverseOverride:
  allowed_only_if:
    - reviewer_signed: true
    - reason_code in [capacity_light_strategy, target_not_liquid_top300,
                      hedge_book_specific, data_coverage_exception]
    - alternative_target_universe_declared: true     # you must name the universe it IS for
    - stage3_flags_preserved_in_FrozenSelectionSet: true   # the failure stays visible, never erased
  forbidden_if:                                      # hard — no override can bypass these
    - sign_flip_on_target_universe: true
    - coverage_sub AND no explicit sub-universe strategy declared
  audit: {override_id, timestamp, reviewer, rationale}    # append-only, like field_approval_log.jsonl
```

*Why.* §A4's "or be explicitly accepted" is a necessary escape hatch (a top-800 / hedge book is a
legitimate non-liquid target) but a governance hole if free-text. This makes it **rare, signed,
reason-coded, and unable to override a sign-flip** — the exact failure v1.1 prevents.

## C3 — `TargetUniverseDeclaration` (close the late universe-selection fork)

```yaml
TargetUniverseDeclaration:
  declared_before: stage_6_selection            # MUST predate seeing Stage 6/7/8 results
  recorded_in: SelectedSet.target_universe  ->  FrozenSelectionSet.universe
  change_rule: |
    Changing the target universe after Stage 6/7/8 results creates a NEW FrozenSelectionSet
    (new frozen_set_hash) and spends a NEW seal. You may NOT select on univ_all, inspect
    liquid/top800/csi1000 diagnostics, then declare the universe where the set looks best.
```

*Why.* Without it, the universe-selection fork that caused E-wave just moves one layer later
(select broad → peek at diagnostics → declare the flattering universe). Binding the declaration
*before* Stage 6 and into the `frozen_set_hash` makes the choice pre-committed and immutable.

## C4 — `SelectedSet` (mandatory, hash-bound; no OOS from an informal notebook)

```yaml
SelectedSet:                              # EWaveSelectedSet_v2.json is the proto
  pool_hash:                              # -> FrozenSelectionSet.candidate_pool_hash
  target_universe:                        # -> FrozenSelectionSet.universe (C3)
  eligible_candidates: [...]
  excluded_by_stage3_caps: [{id, flags}]  # who Stage 3 removed and why (auditable)
  family_caps: {...}
  selected_representatives: [{id, family, expected_direction, marginal_score, maxcorr_to_set}]
  weights_or_ranking_rule:
  redundancy_metrics: {cohort_redundancy}        # Stage 4
  book_marginality_metrics: {book_marginality}   # Stage 4
  selection_code_hash:                    # -> FrozenSelectionSet.selection_rule_hash
  oos_touched: false
```

*Why.* Stage 7's seal is single-shot; it must be spent on a **hash-bound, auditable** selection — not
a notebook. `pool_hash` + `selection_code_hash` flow straight into the existing `FrozenSelectionSet`
fields, so this is a formalization, not new machinery. **No Stage 7 OOS runs without a committed
`SelectedSet`.**

## C5 — `DeploymentFrozenPlan` + pre-declared `pass_fail_bar`

```yaml
DeploymentFrozenPlan:
  universe: ; factor_set: ; directions: ; weighting: ; rank_transform: ; topK:
  rebalance: ; cost_model: ; constraints: ; max_turnover_rule: ; benchmark: ; one_shot: true
  pass_fail_bar:                          # PRE-declared — added per condition C / round-2
    min_net_sharpe:
    min_cagr:
    max_mdd:
    max_turnover:
    min_capacity:
  plan_hash:                              # over the whole plan INCLUDING the bar
```

*Why.* The construction hash alone lets you rationalize a failure after the fact ("Sharpe missed but
MDD improved → maybe ok"). Freezing the **bar** with the plan means the canonical gate has a verdict
that was committed before the run. Exactly one run is canonical; later runs are `post_oos_exploratory`.

## C6 — Display/API invariant (core governance — **early in the build list, not last**)

```text
NEVER render a bare status. Always render scope:
  candidate[research_only, univ_all, 2010-2020]
  candidate[target_eligible, liquid_top300, 2010-2020]
  approved_signal[full_provider, 5d_decile_LS, 2021-2026]   deployable_on_liquid_top300 = no
```

*Why.* With 162 `candidate` rows, a bare "candidate" is systematically over-read as "good." The scope
stamp is the governance that stops `approved` being misread as deployable and `candidate` as
validated. GPT round-2: this is **not cosmetic** — prioritize it. (Enum value `approved` stays
unchanged; this is display/API semantics — refinement R1.)

## C7 — Stage-7 multiplicity disclosure (visible, not blocking)

```text
Every Stage-7 OOS report MUST include:
  pool_denominator           # how many variants the selection chose from (e.g. 69)
  variants_screened
  family_caps
  selected_set_size          # the actual OOS denominator (e.g. 6)
  oos_bar: unadjusted | max_stat_calibrated | fdr_adjusted
  multiplicity_control: "family-aware Stage 6 selection collapses the pool to orthogonal reps
                         BEFORE the OOS; the OOS tests the selected_set_size, not the pool."
```

*Why.* The gross `ls_sharpe>1.0` bar can be scraped by chance from a large pool. Stage 6's
family-aware selection IS the primary multiplicity control (you test ~6 reps, not 69) — but that must
be **disclosed with the denominator**, and for very large pools Stage 7 should state whether a
max-stat/FDR adjustment was applied. Visibility, per GPT, is the requirement; the adjustment is
optional but its presence/absence must be stated.

---

## Net effect

With C1–C7 the methodology is operable, not just architecturally sound: Stage-3 flags have numbers
that agree with the live gate, the override hole is closed, the target universe is pre-committed into
the seal hash, no OOS runs from an informal selection, the deployment gate has a frozen verdict, and
no report shows a scope-less status. **v1.1 (architecture) + this contracts doc (implementation) =
the sign-off-ready standing methodology**, ready to codify as a skill.
