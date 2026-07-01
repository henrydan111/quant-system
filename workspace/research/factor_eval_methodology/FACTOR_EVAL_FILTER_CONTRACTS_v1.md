# Factor Eval — Filter Contracts v1 (closes GPT 5.5 Pro round-3 conditions on v1.2)

> **GPT 5.5 Pro round-3 verdict: APPROVE WITH CONDITIONS** (against the v1.2 addendum @ `46d96cc`).
> The role/filter extension is sound; 8 governance contracts must be added/amended before v1.2 folds
> into the standing methodology. **Disposition: ALL ACCEPTED** — they tighten exactly where filter
> overfit concentrates. This doc is those contracts (FC1–FC8). It **amends** the v1.2 addendum where
> noted (the addendum stays the reviewed artifact; corrections live here). Builds on the round-2
> contracts `C1–C7` ([FACTOR_EVAL_CONTRACTS_v1.md](FACTOR_EVAL_CONTRACTS_v1.md)).

## Disposition

| Round-3 condition | FC | Note |
|---|---|---|
| Filter OOS budget (filters are NOT OOS-free) | **FC1** | amends the v1.2 "does not consume a seal" wording |
| `FilterGate_v1` mechanism-specific bars (MDD required for risk-exclusion) | **FC2** | strengthens §H3 (`Δsharpe≥0` was too weak) |
| `RoleDeclaration` pre-registered; no post-OOS role selection | **FC3** | closes the soft_factor_tail p-hacking surface |
| Universe-definition filters separated + bound to C3 | **FC4** | the sharpest catch — some "filters" define the universe |
| `CapacityContract_v1` numeric pass/fail | **FC5** | "capacity reported" → a verdict field |
| `FilterMultiplicityDisclosure` + joint-set-only OOS | **FC6** | the C7 analogue for the 6–8-filter threshold space |
| PIT proof for forward-looking filters | **FC7** | 未来流通股 must prove known-at-rebalance |
| Simple-baseline comparison | **FC8** | a fancy filter must beat a dumb ADV/age/ST screen |

---

## FC1 — Filter OOS budget (amends v1.2 §H1)

**Replace** the v1.2 sentence *"A filter does not consume a `FrozenSelectionSet` seal; it is part of
the `DeploymentFrozenPlan`"* with:

```
A filter gets NO separate cross-sectional ranking-factor OOS seal. BUT any OOS A/B that evaluates a
filter IS part of the ONE-SHOT DeploymentFrozenPlan seal for that StrategyContext. Filters are not
OOS-free, repeatable, or threshold-tunable after seeing OOS. You may NOT test 6 filters one-by-one on
the deployment OOS and claim none "spent a seal" — that is OOS fishing at the strategy layer. The
canonical OOS evaluates the JOINT final filter set as part of the single DeploymentFrozenPlan run
(FC6); any per-filter A/B is post_oos_exploratory.
```

*Why.* The seal discipline must hold at the strategy layer too. "It's only a filter" cannot become a
loophole for repeated OOS touches.

## FC2 — `FilterGate_v1` (mechanism-specific pass/fail; supersedes the §H3 single bar)

```yaml
FilterGate_v1:
  _min_delta_sharpe: 0.03           # a filter must move net Sharpe materially, not 0.610->0.611
  risk_exclusion:
    require:
      - excluded_tail_underperforms_kept OR excluded_blowup_rate_high
      - d_mdd <= 0                  # MDD improves or at least does NOT worsen (REQUIRED, was "ideal")
      - d_net_sharpe >= _min_delta_sharpe
      - exclusion_rate <= cap OR tail_toxicity_strong   # toxicity may justify a larger cut
    waiver: {reviewer_signed, reason} # d_mdd<=0 waivable ONLY with overwhelming tail-toxicity evidence
  tradability:
    require:
      - execution_feasibility_improves      # the actual target (cost / failed-trade rate down)
      - d_net_sharpe >= -_small_tolerance   # Sharpe may be neutral; feasibility is the point
      - no_severe_breadth_collapse
  soft_factor_tail:
    require:
      - excluded_tail_underperforms_kept
      - filter_role_beats_ranker_role OR combined_role_pre_registered   # FC3
      - d_net_sharpe >= _min_delta_sharpe
      - threshold_plateau
```

*Why.* A filter's worth is its *marginal effect on the strategy's risk-adjusted return*, and the
deciding metric differs by mechanism: risk-exclusion → drawdown; tradability → execution feasibility;
soft-factor-tail → does the tail truly underperform AND is "filter" the better role. `Δsharpe≥0` alone
let a breadth-destroying near-noop pass.

## FC3 — `RoleDeclaration` (pre-registered; no post-OOS role selection)

```yaml
RoleDeclaration:                    # frozen BEFORE Stage 6 / DeploymentFrozenPlan
  factor_id:
  allowed_roles: [ranking, filter, both]
  chosen_role_for_this_StrategyContext:
  if role == both: {rank_weight, filter_rule, filter_threshold, interaction_policy}
  declared_before: stage_6_or_deployment_freeze
rule: |
  Compare ranker-vs-filter-vs-both (and thresholds, directions) in IS ONLY. The CHOSEN role +
  threshold go into the DeploymentFrozenPlan. The OOS run evaluates ONLY that frozen role. A factor
  may serve both roles, but only as ONE frozen design — never as three OOS alternatives picked after.
```

*Why.* `soft_factor_tail` (果仁 真实负债资产率 / 乖离率) is where overfit risk is highest: ranker/filter/both
× thresholds × directions, picked after OOS, is a p-hacking machine. Pre-registration closes it.

## FC4 — `filter_role_subtype`: universe-definition filters are NOT alpha/risk filters

```yaml
filter_role_subtype: universe_definition | tradability_filter | risk_exclusion | soft_factor_tail
```
```
universe_definition filters DEFINE the investable set (ADV floor, listing-age, 科创板/ST exclude,
suspension). They are part of TargetUniverseDeclaration (C3) / FrozenSelectionSet.universe — FROZEN at
Stage 6, never discovered/tuned at Stage 8. Only tradability_filter / risk_exclusion / soft_factor_tail
go through FilterEvaluation (C8 / FC2). Changing a universe_definition filter after results = a NEW
TargetUniverseDeclaration = a NEW seal (C3).
```

*果仁 re-mapping (corrects the v1.2 worked example):*

| filter | subtype | gate |
|---|---|---|
| 5日/20日成交额>0.05亿 · 上市天数>20 · 科创板 exclude · ST exclude · 过滤停牌 | **universe_definition** | C3 (frozen at Stage 6) |
| 退市风险=0 · 重大违规数量=0 · 未来流通股<1% | **risk_exclusion** | FC2 + FC7 |
| 真实负债资产率 rank10-100% · 乖离率(120) rank10-100% | **soft_factor_tail** | FC2 + FC3 |

*Why.* Otherwise "tuning filters" silently changes the target universe after seeing results — the exact
late universe-selection fork C3 was built to stop, re-entering through the filter door.

## FC5 — `CapacityContract_v1` (numeric pass/fail in the DeploymentFrozenPlan)

```yaml
CapacityContract_v1:
  declared_aum:
  max_aum_at_target_adv_share:
  participation_rate: {median, p90, p99}
  turnover_x_adv_headroom:
  pct_orders_over_participation_cap:
  pct_orders_blocked_by_limit_or_suspension:
  capacity_pass:
    require:
      - declared_aum <= max_aum_at_target_adv_share
      - participation_rate.p90 <= cap
      - failed_trade_rate <= cap
```

*Why.* A small-cap StrategyContext (果仁 5M ADV floor) can be deployable at retail AUM yet fail
`liquid_top300` — but only if capacity is a **verdict**, not a footnote. For small-caps the binding
constraint is capacity; it must pass/fail, not just print.

## FC6 — `FilterMultiplicityDisclosure` (the C7 analogue; joint-set-only OOS)

```yaml
FilterMultiplicityDisclosure:
  candidate_filters_considered:
  thresholds_swept_per_filter:
  joint_filter_sets_tested:        # in IS
  final_filter_set_size:
  IS_selection_metric:
  threshold_plateau_evidence:
  oos_bar: one frozen JOINT filter set only
```
```
Canonical OOS tests the JOINT final filter set (inside the one DeploymentFrozenPlan run, FC1), NOT each
filter independently. Per-filter OOS A/Bs are allowed AFTER, labeled post_oos_exploratory.
```

*Why.* 6–8 filters × thresholds is a large joint space; even IS-chosen, the denominator must be
disclosed (same principle as C7's ranking-pool multiplicity), and the OOS must not be touched per-filter.

## FC7 — PIT proof for forward-looking filters

```
Any filter whose definition references future / forward / schedule (e.g. 果仁 未来20日新增流通股) MUST
store: data_release_timestamp, known_at_rebalance proof, source_calendar_hash. Verified at Stage 1.
A "future unlock" filter must provably mean the PRE-ANNOUNCED schedule knowable at the rebalance, never
hindsight realized data.
```

*Why.* These filters are the highest lookahead risk; the name alone (未来) demands an explicit PIT proof.

## FC8 — Simple-baseline comparison

```yaml
FilterEvaluation.simple_baseline_filter: {rule, marginal_delta_vs_baseline}
```
```
A complex factor-filter must BEAT (or explicitly justify vs) a simple, cheap, stable baseline
(ADV floor / listing-age / ST-suspension exclude). If it does not beat the dumb screen, it is a noisy
proxy for liquidity/size and should not pass.
```

*Why.* The filter-side Occam's razor — the mirror of the ranking-side "marginal vs the book".

---

## Net

v1.2 (role/filter architecture) + FC1–FC8 closes the strategy-layer overfit surface: filters consume
the one-shot deployment OOS (FC1), pass mechanism-specific bars (FC2), have pre-registered roles (FC3),
cannot smuggle a universe change (FC4), report numeric capacity (FC5), disclose joint-set multiplicity
(FC6), prove PIT for forward-looking screens (FC7), and beat a dumb baseline (FC8). **The full standing
methodology = v1.1 + C1–C7 + v1.2 roles + FC1–FC8.** Ready to fold in and codify as the `factor-eval`
skill.
