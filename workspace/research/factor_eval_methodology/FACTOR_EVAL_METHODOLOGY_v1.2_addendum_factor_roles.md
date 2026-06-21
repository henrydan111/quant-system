# Factor Eval Methodology — v1.2 addendum: factor ROLES (ranking vs filter) + StrategyContext

> **Extends** [v1.1](FACTOR_EVAL_METHODOLOGY_v1.1.md) + [contracts](FACTOR_EVAL_CONTRACTS_v1.md)
> (GPT 5.5 Pro APPROVE WITH CONDITIONS). **Motivation:** v1.1 evaluates a factor only as a
> *cross-sectional ranking signal* (IC/ICIR). But a real deployed strategy — e.g. a 果仁 multi-factor
> strategy — uses factors in **two different jobs**: **排名条件** (ranking/scoring) and **筛选条件**
> (filter/eligibility). A filter often has **near-zero IC** (退市风险 doesn't *rank* returns, it marks
> names that go to zero) and would be **wrongly rejected** by the IS gate's `|icir|≥0.10` bar. This
> addendum adds a **factor-role dimension** + a **`FilterEvaluation`** lens + binds evaluation to the
> **actual strategy** (`StrategyContext`), so the methodology enhances **both** 筛选条件 and 排名条件.
> **Status:** delta for GPT review; nothing changes code until approved.

---

## §H1 — Two roles, two jobs, two evaluations

```
role = ranking : contributes to the cross-sectional SCORE (排名条件).
                 Claim: "higher (direction-aligned) value → higher future return."
                 Evaluated by: IC / RankIC / ICIR / quantile-monotonicity / marginal-IC.  (v1.1 Stages 2-7)
role = filter  : a boolean ELIGIBILITY cut (筛选条件), usually a tail exclusion.
                 Claim: "the excluded tail is TOXIC or UNTRADEABLE — removing it improves the book."
                 Evaluated by: excluded-tail return / marginal strategy Sharpe·MDD·breadth Δ /
                               threshold stability.  (NEW — §H3)
role = both    : a ranking factor ALSO used as a soft tail-filter (果仁: 真实负债资产率 / 乖离率 ranked
                 10%-100% = exclude the bottom decile). Evaluated under BOTH lenses.
```

**Why a filter cannot be judged by IC.** IC measures smooth monotone rank-prediction across the whole
cross-section. A filter's value lives entirely in **one tail** and is often **non-monotone**: 退市风险 /
重大违规 / 解禁 mark a small toxic/untradeable subset whose *exclusion* helps, while the rest of the
distribution carries no signal → IC ≈ 0, filter value high. Judging it by `|icir|≥0.10` is a category
error (exactly the misalignment this addendum fixes).

**Structural consequence — roles live in different stages.** A ranking factor makes a *cross-sectional
alpha* claim → it must survive the **sealed cross-sectional OOS (Stage 7)**. A filter makes a
*risk-reduction* claim about the *strategy* → it is validated by the **strategy A/B inside the frozen
deployment plan (Stage 8)**, NOT a sealed cross-sectional OOS. A filter does **not** consume a
`FrozenSelectionSet` seal; it is part of the `DeploymentFrozenPlan`.

| | role = ranking | role = filter |
|---|---|---|
| Stage 0 pre-reg | "high X → high return" + sign | "bottom tail of X is toxic/untradeable" + threshold |
| Stage 2 characterize | universe-stratified IC matrix | excluded-tail return + exclusion-rate, per universe |
| Stage 3 caps | sign-flip / liquid_fail / illiquidity_bound | `tail_not_toxic` / `breadth_too_costly` / `threshold_fragile` / `redundant_filter` |
| Stage 4 marginal | marginal IC vs the book | marginal strategy Sharpe·MDD Δ vs the existing **filter set** |
| Stage 5 gate | RANKING IS-gate (`|icir|≥0.10 ∧ sign≥0.70`) | **FILTER gate** (§H3 bar) |
| Stage 6/7 | family-aware selection → sealed OOS | — (not a cross-sectional OOS claim) |
| Stage 8 | book in the deployment plan | **filter set in the `DeploymentFrozenPlan`; with/without A/B** |

---

## §H2 — `StrategyContext`: evaluate factors *in the strategy*, not in the abstract

v1.1's Stage 4/8 referenced "the approved book" / "a target universe" abstractly. To enhance a real
strategy, evaluation **binds to the actual strategy under enhancement**:

```yaml
StrategyContext:                       # the 果仁 strategy being enhanced
  universe: declared                   # e.g. all − ST − 科创板 − 停牌, ADV_20 > 0.05亿  ← C3 declaration
  filters:  [{factor, role: filter, rule, threshold}]          # the 筛选条件
  rankers:  [{factor, role: ranking, direction, scope, weight}] # the 排名条件
  combination: weighted_rank_sum       # 果仁's method — NOT z-score
  trade_model: {rebalance, price, position_band, no_buy_at_up_limit, no_sell_at_down_limit/suspended}
  capacity_aum: declared               # small-cap universe → capacity is a first-class output
```

Two corrections this forces, both already latent in v1.1's dual-scope/C3 but now explicit:

1. **The deployable universe is the USER's universe, not a default.** A 果仁 small-cap strategy with a
   5M ADV floor is *investable at retail AUM* even though it would fail a `univ_liquid_top300` gate.
   The target universe in §A4/C3 must be **the declared `StrategyContext.universe`** — so factor
   evaluation + the deployment gate run on the universe the strategy actually trades. (This also means
   the E-wave verdict — failed on `liquid_top300` — does **not** transfer to a small-cap book; that is
   a *different* deployment scope and must be re-evaluated on it, with **capacity reported**.)
2. **The marginal-contribution baseline is the USER's factor set + combination.** "Does this factor add
   value" = marginal contribution to **this `StrategyContext`'s** rank-sum (ranking) or filter set
   (filter), under **weighted-rank** combination — not vs an abstract book under z-score.

---

## §H3 — `FilterEvaluation` (contract C8): the filter lens + gate

- **Purpose.** Decide whether a factor is worth adding/keeping as a **筛选条件** — a tail-exclusion that
  improves the strategy.
- **Inputs.** The factor (PIT-safe); its cut rule + threshold; the `StrategyContext` (universe, ranker
  set, trade model); the IS window.
- **Outputs.**
  ```yaml
  filter_eval:
    mechanism_class: risk_exclusion | tradability | soft_factor_tail
    excluded_tail_fwd_return: {mean, median, left_tail_blowup_rate}   # excluded vs kept vs universe
    exclusion_rate: {of_universe, of_rank_selected_topK}             # breadth cost + where it bites
    marginal_strategy_delta: {d_net_sharpe, d_cagr, d_mdd, d_winrate} # with vs without, on StrategyContext
    threshold_stability: {swept_values, delta_curve, plateau: bool}   # not a single curve-fit point
    redundancy_vs_existing_filters: {max_overlap, marginal_dd_reduction}
  ```
- **Tool.** A with/without strategy A/B (vectorized screen for the cheap read; one event-driven run for
  the frozen verdict) — reuses `EventDrivenBacktester` + the `StrategyContext`.
- **Filter gate (analogue of `|icir|≥0.10`).** PASS as a filter iff:
  ```
  (excluded tail underperforms [risk_exclusion]  OR  excluded set is untradeable [tradability])
  AND marginal_strategy_delta.d_net_sharpe ≥ 0  (and ideally d_mdd improves)
  AND exclusion_rate acceptable (below a declared cap, OR justified by tail toxicity)
  AND threshold_stability.plateau == true
  AND NOT redundant_vs_existing_filters
  ```
- **Why these, not IC.** A filter's worth IS its **marginal effect on the strategy's risk-adjusted
  return** — the same "marginal > standalone" principle as ranking, but the outcome metric is
  strategy Sharpe/MDD, not cross-sectional IC. Mechanism-class routing makes the *deciding* metric
  explicit: a `risk_exclusion` filter is judged by tail-toxicity + ΔMDD (退市/违规/解禁); a `tradability`
  filter by execution feasibility (liquidity floors); a `soft_factor_tail` by *both* tail-underperformance
  *and* "would keeping it as a ranker be better?" (真实负债资产率 / 乖离率).
- **PIT + anti-overfit (load-bearing).** (a) Filters that *sound* forward (果仁 `未来20日新增流通股<1%` =
  the **pre-announced** unlock schedule, knowable at rebalance) MUST be PIT-verified at Stage 1 —
  evaluated using only info known at the rebalance. (b) **Filter thresholds are tuned on IS / pre-
  registered**, never on the spent OOS; the with/without A/B on OOS is a **single descriptive run**
  frozen into the `DeploymentFrozenPlan` (C5) — fishing thresholds until the OOS looks good is the
  same overfit the deployment freeze prevents.
- **Prevents.** (1) Wrongly rejecting a high-value zero-IC filter via the ranking bar. (2) Adding a
  redundant filter (退市风险 ∩ 违规 may overlap) that only costs breadth. (3) A filter that *looks*
  protective but actually hurts net Sharpe (over-screening starves the ranker).

---

## §H4 — Worked example: the user's 果仁 strategy mapped to roles

**筛选条件 → role=filter** (evaluated by `FilterEvaluation`, NOT IC):

| filter | mechanism_class | deciding metric |
|---|---|---|
| 退市风险=0 · 重大违规数量(30)=0 | risk_exclusion | excluded-tail blowup rate + ΔMDD |
| 未来20日新增流通股<1% | risk_exclusion (dilution) | tail return + **PIT-verify pre-announced unlock** |
| 5日/20日成交额>0.05亿 · 上市天数>20 | tradability | execution feasibility (not return) |
| 真实负债资产率 rank 10%-100% · 乖离率(120) rank 10%-100% | **soft_factor_tail** | tail-underperformance **AND** "better kept as a ranker?" |

**排名条件 → role=ranking** (evaluated by the v1.1 IC pipeline + marginal-IC vs the 8-factor set):

| ranker | family | note |
|---|---|---|
| 总市值 (industry-neutral ×2, all ×3) | size | the small-cap tilt — dominant weight; capacity-sensitive |
| CoreProfitQGr · EpsExclXorQGr · ROETTMDiffPQ | growth/quality (fundamental) | PIT on ann_date |
| 振幅%/成交额(10) | illiquidity/amplitude | E-wave-family (liquid-universe IC must be checked) |
| 2× momentum formula (250−20, 120−20, excl 涨停) | path momentum | our E-wave / overnight-momentum family |
| 业绩预告净利润QGr (**从小到大**) | earnings surprise | ⚠ ascending direction — Stage 0 must force the economic rationale (contrarian-on-hype? small offset?) |

The methodology would: characterize each ranker's marginal IC vs the other 8 **on the user's small-cap
universe** (Stage 2-4), evaluate the 6 filters by `FilterEvaluation` (§H3), and validate the whole as a
**single `DeploymentFrozenPlan`** (universe + filters + rankers + weighted-rank + trade model + pass/fail
bar) at Stage 8 — with **capacity reported** (the binding constraint for a small-cap book).

---

## §H5 — Open questions for GPT (the v1.2 delta to review)

1. **Ranking/filter split.** Is "ranking → sealed cross-sectional OOS (Stage 7); filter → strategy A/B
   in the frozen deployment plan (Stage 8), no seal" the right structural separation? Or should a
   high-value filter also earn a sealed claim of some kind?
2. **The filter gate bar (§H3).** Is `tail-toxic ∧ Δnet_sharpe≥0 ∧ breadth-ok ∧ threshold-plateau ∧
   not-redundant` sound, or too lax/strict? Should `d_mdd` improvement be required (not just ideal)?
3. **`soft_factor_tail` double-evaluation.** For a factor used as both ranker and tail-filter
   (真实负债资产率, 乖离率), is "evaluate under both lenses, deploy in the role with higher marginal
   contribution" right — or can a factor legitimately serve both roles at once?
4. **`StrategyContext` binding vs the abstract book.** Is binding marginal-contribution to the user's
   *actual* strategy (factor set + weighted-rank + declared universe) the right generalization of
   v1.1's "approved book", or does it weaken cross-strategy comparability? How to keep both
   (strategy-specific marginal + a strategy-agnostic standalone record)?
5. **Capacity as a first-class output for small-cap universes.** The user's deployable universe is
   small-cap (5M floor), not `liquid_top300`. The dual-scope regime allows this — but what capacity /
   AUM-stress contract should Stage 8 require so a small-cap "deployable" result is not silently
   AUM-capped? (`max_aum_at_target_adv_share`, turnover×ADV headroom, etc.)
6. **Anti-overfit for filters.** Is "thresholds IS-chosen/pre-registered, one descriptive OOS A/B
   frozen in the `DeploymentFrozenPlan`" sufficient, given a strategy can carry 6-8 filters (a large
   joint threshold space)? Does the cohort/threshold multiplicity need a disclosure like C7?

If approved, v1.2 folds into the standing methodology as: a `role` field on every factor; the
`FilterEvaluation` contract (C8); the `StrategyContext` binding for Stage 4/8; and the skill gains a
"filter evaluation" step beside the "ranking characterization" step.
