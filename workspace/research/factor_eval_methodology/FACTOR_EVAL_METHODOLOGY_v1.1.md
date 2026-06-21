# Factor Evaluation Methodology — v1.1 (post GPT 5.5 Pro review)

> **v1.1 changes.** Supersedes v1 (@`1ca2be6`) after GPT 5.5 Pro's *CHANGES REQUIRED* review. The
> stage architecture stood; this version resolves the two blocking issues — the **style-residual
> selection-basis contradiction** and the **open gate-universe decision** — plus 7 required changes.
> Per-finding disposition: [FACTOR_EVAL_METHODOLOGY_v1_cross_review_response.md](FACTOR_EVAL_METHODOLOGY_v1_cross_review_response.md).
> The five edits that change behaviour: (1) selection score is **raw direction-aligned IS quality +
> redundancy penalty**, never generic style residual by default; (2) a hard **dual-scope regime**
> (§A4); (3) Stage 3 emits **machine-binding caps** that Stage 5/6/7 must read; (4) `DeploymentFrozenPlan`
> before any deployment run; (5) cost/turnover diagnostics + cohort pre-registration moved early.
> **Status:** proposal pending final sign-off; nothing changes code until approved.

---

## Part A — First principles

### A1. The one idea: separate the layers.

A **factor** is a cross-sectional signal (a number per stock-date that ranks future returns). A
**strategy** is a *portfolio* of factors on a *specific tradeable universe* with weighting, sizing,
rebalance, and costs. **"Deployable" is a property of the strategy, not the factor.** The status
ladder (`draft → candidate → approved`) certifies the *signal*; **deployability is per-universe
metadata, never a status.** Three questions, kept distinct, answered at distinct cost:

| # | Question | Layer | Cost | Tool |
|---|---|---|---|---|
| Q1 | Real, leak-free signal? | factor | cheap | IS walk-forward IC/ICIR |
| Q2 | **Where** does it work + is it **robust**? | factor | cheap | universe-stratified IC matrix (+ cost diagnostics) |
| Q3 | Adds **deployable value to a book** on a target universe? | **strategy** | expensive | marginal-contribution + frozen event-driven deployment gate |

### A2. Cross-cutting invariants (substrate; CLAUDE.md §3/§7)

No-lookahead (PIT, `Ref`-frames, `is_end` label-realization belt) · single-shot OOS keyed by
`frozen_set_hash` (observing = spending) · resolve-but-label (evidence never auto-drives status) ·
**marginal > standalone** · **scope is explicit** (a status/metric without its (universe, window) is
under-specified) · fail-closed.

### A3. The four-layer backtest pipeline (CLAUDE.md §8.1)

Factor computation (full market) → universe masks → signal (rank within sub-universe) → execution.
Factor-eval lives in Layers 1–3; the deployment gate is Layer 4. **Factors are always computed on
the full market first; universes scope ranking, never the computation.**

### A4. ★ The dual-scope regime (the resolved gate-universe policy)

The decision v1 left open. **There is no single canonical universe for all research, but
target-universe evidence is mandatory for any deployable claim:**

```
research candidate         may be earned on univ_all; MUST be scope-stamped;
                           does NOT imply deployability.
deployment-bound candidate must PASS (or be explicitly accepted on) the declared target
                           investable universe — normally univ_liquid_top300 or a declared
                           ESTU. Liquid evidence is a HARD selection input (Stage 6).
approved[signal, scope]    approved on the SAME universe/scope as the FrozenSelectionSet
                           being validated. full-provider approved ≠ liquid-top300 approved.
```

**Why dual, not single-liquid:** a factor genuinely useful in a broader book (top-800, CSI1000,
market-neutral, capacity-light) must not be rejected by a top-300 gate. **Why mandatory-liquid for
deployment:** E-wave validated a 6-core on `univ_all` (6/6 sealed OOS) that then lost money on
liquid-300 — the exact failure a target-universe gate prevents. The target universe is a field of the
`FrozenSelectionSet` and the `DeploymentFrozenPlan`, so scope is part of every hash.

---

## Part B — Capability map (the methodology is *our* machinery)

- **Factor library** — `get_factor_catalog()`, `operators.py` (`ADJ_*_T1` PIT constants),
  `catalog_composition()`. Status-agnostic for discovery.
- **Field-status registry** — `config/field_registry/field_status.yaml` (formal data gate).
- **Universes** — `factor_eval/universes.py`: 7 `UniverseSpec`s (`univ_all`, `univ_csi300/500/1000`,
  `univ_microcap`=mcap-bottom-400, `univ_growth`=创业板+科创板, **`univ_liquid_top300`**=ADV-top-300
  = *the deployable-liquidity domain*) + CICC screens (ST/*ST·停牌·一字板·上市未满一年).
- **Unified eval** — `unified_eval.py` (`EvalMethodology`, deciles `n_quantiles=10`,
  `STYLE_CONTROLS_V1`, `residual_ic_vs_controls`, `neutralized_rank_icir`) → 7-universe IS matrix
  (`results.jsonl`).
- **IS gate** — `factor_lifecycle` profile; `run_is_walk_forward` + `assign_candidate_status`
  (`|rank_icir|≥0.10 ∧ sign-consistency≥0.70`, IS-only, `is_end`-bounded).
- **Selection + seal** — `FrozenSelectionSet`(`frozen_set_hash`) + `HoldoutSealStore` +
  `reproduce_sealed_oos`/`produce_promotion_evidence` (writer gate: clean git SHA + independent OOS).
- **Deployment** — `EventDrivenBacktester` (T+1, limits, suspension, corporate actions,
  total-return), `CostConfig.realistic_china()`, `ExecutionProfile`.
- **Registry** — `factor_master.parquet` already carries `validation_scope`, `approved_uses`,
  `long_only_viable_provisional`, `latest_oos_rank_icir`, `latest_lo_sharpe_gross`,
  `expected_direction` — the needed fields exist; they are under-populated.

---

## Part C — The staged pipeline

Template per stage: **Purpose · Inputs · Outputs · Tool · Criteria · Why · Prevents.** Stages 0–5,7
validate the *signal*; Stage 6 collapses a *pool*; Stage 8 tests a *strategy* (metadata). Stages 2–4
are the cheap "factor characterization" cluster (one skill, three separate outputs).

### Stage 0 — Pre-registration & economic hypothesis (factor **and** cohort)

- **Purpose.** A-priori, falsifiable rationale before any data is touched.
- **Inputs.** The idea; data sources + their Tushare interface docs (PIT/cadence per §6.1).
- **Outputs.** *Per factor:* economic rationale, **expected direction**, data/PIT, intended scope,
  pass/fail bar. *Per handbook/family expansion:* a **`CohortHypothesis`** —
  ```yaml
  CohortHypothesis: {source_chart, all_formulas, expected_family, direction_policy,
    allowed_variants, dedup_proxy_rules, family_caps, target_universe, no_add_after_results: true}
  ```
- **Tool.** `hypothesis_cli.py`; the cohort manifest (`config/replication/*_cohort_*.yaml` is the
  proto-artifact — generalize it; add the a-priori direction policy + the explicit
  **no-add-after-results** clause).
- **Why.** Per-factor pre-reg defends one factor against sign-chasing; **cohort pre-reg defends a
  whole chart against p-hacking by adding/dropping variants after seeing the matrix.**
- **Prevents.** Post-hoc sign choice (GP/arXiv-north flips) and intra-chart variant-fishing.

### Stage 1 — Definition, PIT-safety, field eligibility → `draft`

- **Purpose / Inputs / Outputs.** Spec → a PIT-safe Qlib expression + a `draft` registry row with
  `definition_hash`, recorded price basis + decay horizon.
- **Tool / Criteria.** `operators.py`, PIT lint, `field_status.yaml`. Every `$field` inside a
  `Ref(...)` frame; fields field-eligible; hash matches catalog algorithm.
- **Why.** `draft` is free (definition, not evidence) → computable everywhere for discovery. The hash
  binding here is what makes a later approval **definition-bound**.
- **Prevents.** Silent PIT leakage (the most corrosive bug class).

### Stage 2 — Universe-stratified IS evaluation + cost diagnostics  ★ cheap insurance

- **Purpose.** The full factor-eval standard **across all 7 universes**, plus cheap cost/turnover
  reads, in sample.
- **Inputs.** `draft` factor; IS window; the 7 `UniverseSpec` masks; `EvalMethodology`.
- **Outputs.** Per **(factor, universe)**: `heldout_rank_icir`, `mean_rank_ic` (+HAC t),
  `neutralized_rank_icir`, **`resid_ic_vs_style_controls_v1` (diagnostic — see note)**,
  `decay_icir_{5,10,20,40}`, `ic_hit_rate`, `mono_shape`, `coverage`/`coverage_tier`,
  `long_leg_excess_ann_*`. **Plus cost diagnostics:** `turnover_ann`, holding-period decay,
  long-leg one-way turnover, **estimated one-way cost drag by universe**, and a limit-up/down
  tradability-hit proxy.
- **Tool.** `unified_eval_universe_matrix.py`; cost diagnostics are cheap proxies (not a backtest).
- **Why.** The stage E-wave proved we must never skip — a single-universe IC hides the microcap
  mirage. The 7 universes span size/style/**liquid (the deployable domain)**. The cost reads make
  the turnover drag that killed E-wave (≈74%/mo) visible **at the factor layer**, not only at
  deployment.
- **⚠ Style-residual note (B1).** `resid_ic_vs_style_controls_v1` is **reference-invariant** and is a
  useful **diagnostic** ("is this distinct from generic size/value/vol/liq styles?"). It is **NOT the
  default selection score**: `STYLE_CONTROLS_V1` contains volatility + liquidity controls, so
  residualizing a vol/liq factor against it removes the signal *by construction* (it nukes a faithful
  low-vol replication because the control set contains a sibling). Use it as the selection score
  **only** when the style book is the explicitly-declared benchmark being tested against.
- **Prevents.** The E-wave failure foreseen cheaply (`flow_xl` ICIR −0.49 on `univ_all` but −0.07 on
  liquid; `liq_vstd` −0.56→+0.18 sign-flip on liquid — visible here, before the OOS).

### Stage 3 — Scope-stamped quality + machine-binding caps

- **Purpose.** Turn the matrix into a *scoped*, *machine-binding* verdict that downstream stages
  MUST obey — not a dashboard read after the mistake.
- **Inputs.** Stage-2 per-(factor, universe) rows + cost diagnostics.
- **Outputs.** A record:
  ```yaml
  quality_flags:
    sign_flip_across_core_universes: bool   # sign differs full vs liquid/large
    liquid_fail: bool                       # weak/absent on univ_liquid_top300
    illiquidity_bound: bool                 # strong on microcap/full, weak on liquid
    coverage_sub: bool                      # sub-universe coverage tier
    short_window: bool
    high_turnover_cost_risk: bool           # turnover + cost-drag proxy adverse
    target_universe_pass: bool
  status_effect:
    candidate_scope: research_only | target_eligible
    oos_eligible: bool
    deployment_bound_selection_allowed: bool
  validation_scope: {universe(s), is_window}
  universe_profile: {univ_all: icir, liquid_top300: icir, microcap: icir, ...}
  ```
- **Tool.** New thin reader over `results.jsonl` (proposed; today done by hand).
- **Why.** Status today is silently global. Sign-stability across universes is a first-class quality
  criterion (a sign that flips by universe is a subpopulation artifact, not an economic signal).
  Making the flags **machine-binding** is the difference between prevention and a post-mortem.
- **Prevents.** A misleading global approval on a microcap-bound or sign-unstable factor; Stage 5/6/7
  proceeding on a factor Stage 3 has capped.

### Stage 4 — Marginal contribution: cohort-redundancy **and** book-marginality (separate)

- **Purpose.** Two distinct questions, two distinct outputs.
- **Inputs.** The factor's panel (IS, on the relevant universe); its cohort/family; the approved book
  and/or the target deployment book.
- **Outputs.**
  ```yaml
  cohort_redundancy: {max_corr_to_same_family, selected_representative_id, marginal_within_pool}
  book_marginality:  {residual_ic_vs_approved_book, residual_ic_vs_target_book, add_to_book_net_ir_proxy}
  ```
- **Tool.** Generalized exposure-corr + greedy machinery (from `select_e_wave_marginal.py`).
- **Why.** A correlated family of 35 vol variants is not 35 discoveries (`cohort_redundancy`); but
  "not redundant within my cohort" ≠ "adds to the deployed book" (`book_marginality`). **Selection
  score = direction-aligned raw IS quality × redundancy penalty** (corr-to-selected + residual-vs-
  book), measured on the universe the decision is *for* (deployable decision → liquid). **Not** the
  generic style residual (B1).
- **Prevents.** Cohort inflation and the v1-selection defect (caps saturated, no redundancy pruned).

### Stage 5 — IS gate → `candidate` (scope-stamped, dual-scope)

- **Purpose.** Leak-proof IS-only audition; "worth spending OOS budget on."
- **Inputs.** `draft`; the `is_end`-bounded panel; field eligibility; **Stage-3 caps**.
- **Outputs.** `candidate` (or stays `draft`) + IS-only evidence (no `oos_*`), `expected_direction`,
  recorded to the file-locked ledger. **Human gate** to write. **Scope-stamped** (§A4): a candidate
  earned on `univ_all` is `candidate_scope: research_only` unless Stage 3 sets `target_universe_pass`.
- **Tool / Criteria.** `factor_lifecycle`; `assign_candidate_status` (`|heldout_rank_icir|≥0.10 ∧
  sign-consistency≥0.70`, fail-closed). **Plus:** must honour Stage-3 `status_effect`.
- **Why.** `candidate` gates the scarce OOS budget; the `is_end` belt on the *label-realization* date
  is the no-lookahead guarantee. **Dual-scope (§A4):** research candidacy may be broad; deployable
  candidacy requires target-universe evidence.
- **Prevents.** Spending OOS / deployment effort on IS-marginal or research-only-scoped factors.

### Stage 6 — Family-aware selection (pool → frozen set), deployment-aware

- **Purpose.** Collapse a correlated **pool** to orthogonal **representatives** for one OOS.
- **Inputs.** The candidate pool; Stage-2 IS quality; Stage-4 `cohort_redundancy`; redundancy
  references; **Stage-3 caps** (a `liquid_fail`/`sign_flip` factor may **not** enter a
  deployment-bound selection — §A4 hard input).
- **Outputs.** A `SelectedSet` (~4–9 reps) + a deterministic rule + full accept/reject trace + family
  caps + the marginal-floor cut + the **declared target universe**.
- **Tool.** Generalized greedy (`quality × (1−maxcorr)`, family-capped), IS-only.
- **Why.** "69 ≠ 69 discoveries." One OOS on the *set* (not a per-variant lottery). Selection is
  IS-only so the OOS stays unburned; the score is raw IS quality + redundancy, **not** style residual.
- **Prevents.** The OOS lottery and freezing a redundant/illiquidity-bound set into the seal.

### Stage 7 — Sealed OOS → `approved` (scope = the FrozenSelectionSet universe)

- **Purpose.** The one independent, fail-closed OOS proof, `candidate → approved`.
- **Inputs.** A `FrozenSelectionSet` (reps + full recipe incl. **target universe**); the sealed window.
- **Outputs.** Per-factor `oos_rank_icir`+`oos_ls_sharpe`; a `HoldoutSealStore` spend keyed by
  `frozen_set_hash`; a `promotion_evidence` artifact (6 canaries + lint + parity + clean git SHA,
  self-verified through the release gate); **`approved` stamped with the OOS scope**.
- **Tool / Criteria.** `reproduce_sealed_oos` + `produce_promotion_evidence`; bar = sign-aligned
  `rank_icir>0 ∧ ls_sharpe>1.0`.
- **§A4 rule (hard).** A **deployment-bound** approval MUST run the sealed OOS on the **declared
  target investable universe** (the FrozenSelectionSet's `universe`). A full-provider OOS yields
  `approved[full_provider, …]`, which **does not** imply `approved[liquid_top300, …]`.
- **⚠ Bar caveat.** `ls_sharpe>1.0` is a **gross 5-day decile registration metric — NOT tradability.**
  Surface the status as **`approved_signal[universe, metric, window]`** (R1: this is display/API
  semantics — the enum value stays `approved`; do not rename it), with `deployable_on_<universe>:
  yes/no/untested` always shown beside it.
- **Prevents.** Multiple-testing / peek-then-tweak; faking a promotion; a full-universe approval being
  misread as liquid-deployable (the E-wave error).

### Stage 8 — Deployment gate (strategy-level; frozen plan; metadata not status)

- **Purpose.** Is a **book** of these factors tradable on the **target investable universe**, net of
  real costs, unlevered?
- **Inputs.** A **`DeploymentFrozenPlan`** (one-shot, hashed) —
  ```yaml
  DeploymentFrozenPlan: {universe, factor_set, directions, weighting, rank_transform, topK,
    rebalance, cost_model, constraints, max_turnover_rule, benchmark, one_shot: true}
  ```
  the (already-spent) OOS window for descriptive characterization.
- **Outputs.** Strategy metrics (CAGR, MDD, Sharpe, Calmar, turnover, capacity) **per target
  universe**, written to **metadata** (`long_only_viable[universe]`, `latest_lo_sharpe_gross`,
  `add_to_book_net_ir`) — **never** to lifecycle status. **Exactly one** run is the canonical gate;
  any later run is labeled `post_oos_exploratory`.
- **Tool.** `EventDrivenBacktester` (1×, T+1, limits, corporate actions, total-return);
  `eval_*_deployment.py` → a standardized `ExecutionProfile`-pinned, universe-parameterized runner.
- **Why a strategy test decided by marginal contribution.** A factor does **not** pass deployment
  *individually*; its value is its marginal net-IR contribution to the book on the target universe. A
  naive standalone equal-weight composite is a **poor** test — E-wave's was polluted by 2
  universe-sign-flipping members, so its −3.6% CAGR understated the 2–3 members with genuinely strong
  liquid IC. The right test: build the actual target book from the **IS-sign-stable** members
  (subset choice justified by IS data, not the spent OOS) and measure each one's marginal net-IR.
- **Why frozen + one-shot.** Without it the obvious temptation after a failure is to fish weights /
  topK / filters / costs until the spent OOS looks good — overfitting the holdout. The
  `DeploymentFrozenPlan` mirrors `FrozenSelectionSet` discipline at the deployment layer.
- **Prevents.** (a) Reading a registration-bar OOS pass as deployable (eps_diffusion +4.5%/−62%).
  (b) Condemning useful factors via a naive standalone composite (the E-wave over-claim we corrected).
  (c) Overfitting the spent OOS by iterating constructions.

---

## Part D — Output contract (scope-stamped, two-axis)

```
factor_id, definition_hash, expected_direction
status            ∈ {draft, candidate, approved, deprecated}          # enum value UNCHANGED (R1)
validation_scope  = {universe, is_window, oos_window?}                # WHERE status was earned
status_effect     = {candidate_scope, oos_eligible, deployment_bound_selection_allowed}  # Stage 3
universe_profile  = {univ_all, liquid_top300, microcap, csi300, ...}  # Stage 2/3
quality_flags     = {sign_flip_across_core_universes, liquid_fail, illiquidity_bound, ...}
marginal          = {cohort_redundancy, book_marginality}            # Stage 4 (two records)
oos               = {frozen_set_hash, universe, oos_rank_icir, oos_ls_sharpe, bar_passed}
deployability     = {<universe>: {plan_hash, lo_viable, cagr, mdd, sharpe, marginal_net_ir}}  # METADATA
```

**Display/API invariant.** Never render a bare `approved`. Always render
**`approved_signal[universe, metric, window]`** with **`deployable_on_<universe>: yes/no/untested`**
beside it. `status` answers "is it a real signal (on what scope)"; `deployability[universe]` answers
"is a book using it tradable there." The two never collapse into one flag. This is the concrete
answer to "should status be bound to universe?": **scope-stamp the single status; bind deployability
per-universe as metadata; do not build a `status × universe` matrix** (it invites per-universe OOS
lotteries).

---

## Part E — E-wave as worked case study (what v1.1 changes)

| Stage | E-wave (as run) | v1.1 |
|---|---|---|
| 0 | per-chart manifest review | + `CohortHypothesis` with no-add-after-results |
| 2 | 7-universe matrix computed | + **cost diagnostics**; style residual is diagnostic-only |
| 3 | done by hand, post-hoc | **machine-binding caps**: `illiquidity_bound` on 4/6, `sign_flip` on 2/6 → `liquid_fail`, set **before** OOS |
| 4 | corr at selection | **cohort_redundancy** + **book_marginality** separated |
| 5 | IS gate on `univ_all` | scope-stamped `research_only` unless liquid passes (§A4) |
| 6 | 69→6-core (raw ICIR + corr) | + **Stage-3 caps as hard input** → the 2 sign-flippers excluded from a deployment-bound set |
| 7 | sealed OOS on full universe → 6/6 | **deployment-bound OOS must be on the target universe** → would not have spent the seal on a full-universe mirage |
| 8 | naive composite → FAILED | **`DeploymentFrozenPlan`** on the IS-sign-stable subset; one-shot; result is metadata |

**Lesson encoded:** the expensive Stages 7–8 told us almost nothing the cheap Stage 2–3 read did not
already contain. v1.1 makes that read **binding** and makes the OOS/deployment **universe-honest** —
without weakening any no-lookahead / single-shot-OOS guarantee.

---

## Part F — Resolved decisions (was: open questions)

| Q | Resolution |
|---|---|
| F1 gate universe | **Dual-scope (§A4).** Research candidacy may be broad/`univ_all` (scope-stamped); OOS/deployment-bound claims require the declared target investable universe; `approved` is on the FrozenSelectionSet universe. Not a single mandatory liquid gate. |
| F2 scope vs matrix | **Scope-stamped single status**, mandatory in display/API. No `status × universe` matrix (invites OOS lotteries). |
| F3 OOS budget | **One OOS per *targeted* FrozenSelectionSet.** Genuinely different bets (liquid vs microcap) = different frozen sets + seals. Never test 7 universes and pick the winner. |
| F4 marginal test | **Two-tier:** cheap pre-OOS orthogonalized IC / exposure-corr on the target universe; expensive post-selection **one** frozen deployment plan. Subset choice IS-only; deployment OOS descriptive unless pre-frozen. |
| F5 sign-stability | **Hard criterion for deployment-bound selection** (a liquid sign-flip cannot enter a liquid deployment set); flag + scope-stamp suffices for research candidacy. |
| F6 deployment status | **Metadata, not a status tier** — but UI/reporting shows deployability beside `approved_signal`. |
| F7 net-of-cost | **Yes, in Stage 2/3** as caps/warnings (not full deployment metrics). |
| F8 skill granularity | Bundle Stages 2–4 as one **"factor characterization"** skill with **three separate outputs** (matrix / quality-flags / marginal). |

---

## Part G — Build list (if approved)

1. **Stage-3 reader** → the machine-binding `quality_flags` + `status_effect` caps (today by hand).
2. **Scope-stamping populated** — write `validation_scope` / `universe_profile` / `quality_flags`
   in the promote flow (fields already in the schema).
3. **Dual-scope wired** into Stage 5/7 (`candidate_scope`, target-universe OOS rule).
4. **Generalized marginal tool** (Stage 4) — `select_e_wave_marginal.py` greedy → a `factor_eval`
   function emitting the two records.
5. **`DeploymentFrozenPlan` + standardized deployment runner** (Stage 8), `ExecutionProfile`-pinned,
   universe-parameterized, one-shot-hashed.
6. **Cost/turnover/capacity diagnostics** as Stage-2 metrics.
7. **`CohortHypothesis`** generalized from the cohort manifest (+ direction policy + no-add clause).
8. **Display/API invariant** — render `approved_signal[scope]` + `deployable_on_<universe>` (no bare
   `approved`).

---

*v1.1 ready for final sign-off. If approved, codify as a Claude Code skill: Stages 0–1 (register),
2–4 (characterize — one skill, three outputs), 5–7 (gate/select/seal), 8 (deploy), each with runnable
steps + templates. The enum value `approved` is unchanged; everything new is additive metadata +
display semantics + binding reads.*
