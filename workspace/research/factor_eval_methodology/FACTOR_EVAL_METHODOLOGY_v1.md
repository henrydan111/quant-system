# Factor Evaluation Methodology — v1 (design for GPT 5.5 Pro review)

> **Purpose of this document.** Today every factor evaluation in this system is run ad-hoc — the
> steps exist as machinery (the 7-universe matrix, the `factor_lifecycle` gate, the sealed-OOS
> harness, the event-driven deployment scripts) but there is **no single, written methodology**
> that says *which steps, in what order, with what inputs/outputs, and why*. The E-wave replication
> (8 CICC charts → 69 candidates → a 6-core sealed OOS that passed 6/6 → a deployment gate that
> failed) exposed the cost of that: we spent an irreplaceable single-shot OOS and a full
> event-driven backtest to "discover" something a cheap universe-stratified IC read had shown all
> along. This document proposes the standing methodology, defines every stage's I/O and rationale,
> grounds each stage in the *actual* capability that implements it, and ends with the open design
> questions for review.
>
> **Audience:** GPT 5.5 Pro (adversarial design review) + future sessions. **Status:** proposal,
> pre-approval. Nothing here changes code until reviewed.

---

## Part A — First principles (the "why" before the "how")

### A1. The one idea: separate the layers. Never conflate them.

A **factor** is a cross-sectional signal: a number per (stock, date) that is supposed to rank
future returns. A **strategy** is a *portfolio* built from one or more factors on a *specific
tradeable universe*, with weighting, sizing, rebalance, and costs. **"Deployable" is a property of
a strategy, not of a factor.** The single most expensive mistake we make is letting a factor-level
result (a gross IC, a decile long-short Sharpe) be read as a deployment claim — or letting a
strategy-level failure be read as "the factor is worthless."

The methodology therefore keeps **three distinct questions** separate and answers them with
distinct tools at distinct costs:

| # | Question | Layer | Cost | Tool |
|---|---|---|---|---|
| Q1 | Is it a **real, leak-free signal**? | factor | cheap | IS walk-forward IC/ICIR |
| Q2 | **Where** does it work, and is it **robust**? | factor | cheap | universe-stratified IC matrix |
| Q3 | Does it **add deployable value to a book** on a target universe? | **strategy** | expensive | marginal-contribution + event-driven deployment gate |

The status ladder (`draft → candidate → approved`) answers **Q1/Q2** (signal validation).
**Deployability is Q3 — it is metadata, never a status** (the lifecycle README already states this:
*"long-only viability is Phase-2 METADATA and is NOT an input to either lifecycle rule"*). The
methodology's job is to make that separation operational and impossible to blur.

### A2. The cross-cutting invariants (inherited from CLAUDE.md §3, §7; non-negotiable)

Every stage operates under these. They are not re-litigated per stage; they are the substrate.

1. **No lookahead, ever.** PIT alignment on `ann_date`, `Ref(...)`-framed fields, the
   label-realization `is_end` boundary. A factor evaluated on IS must not see any label that
   realizes after `is_end` (`IsEndLeakageError` belts).
2. **OOS is sacred and single-shot.** The out-of-sample window is observed **once** per frozen
   selection set, keyed by a `frozen_set_hash` and spent through the `HoldoutSealStore`. Observing
   = spending. No re-rolls, no peek-then-tweak.
3. **Resolve-but-label.** Evidence never auto-drives status. A measurement is recorded; a *human
   gate* moves status. (`candidate ≠ approved`, never auto-promotes.)
4. **Marginal > standalone.** A factor's worth is its *orthogonal increment* to the existing set,
   not its standalone strength (empirically: greedy-by-marginal combined ICIR 1.02 vs
   greedy-by-ICIR 0.70). Select and judge by marginal contribution.
5. **Scope is explicit.** A status or metric without its (universe, window) scope is
   under-specified. "approved" must mean "approved *on what*."
6. **Fail-closed governance.** Unknown field, missing manifest, ambiguous scope, skipped check →
   the conservative answer (refuse / stay draft / treat as failed), never the optimistic one.

### A3. The four-layer pipeline these stages sit inside (CLAUDE.md §8.1)

Factor computation (Layer 1, full market) → universe selection (Layer 2, masks) → signal
construction (Layer 3, rank within sub-universe) → execution (Layer 4). The methodology's
factor-eval stages live in Layers 1–3; the deployment gate is Layer 4. **Factors are always
computed on the full market first; universes scope ranking, never the computation.**

---

## Part B — The capability map (so the methodology is *our* system, not a textbook)

The methodology is deliberately a thin orchestration over machinery that already exists. The stages
below reference these by name:

- **Factor library / catalog** — `src/alpha_research/factor_library/` (`get_factor_catalog()`,
  `operators.py`, the `ADJ_*_T1` PIT constants, `catalog_composition()`). Source of truth for
  computable definitions; status-agnostic for discovery.
- **Field-status registry** — `config/field_registry/field_status.yaml` (`FieldStatusRegistry`):
  4 statuses × per-stage flags; the formal data gate.
- **Universe framework** — `src/alpha_research/factor_eval/universes.py` (7 `UniverseSpec`s:
  `univ_all`, `univ_csi300/500/1000`, `univ_microcap` = mcap-bottom-400, `univ_growth` =
  创业板+科创板, **`univ_liquid_top300`** = ADV-top-300 = *the deployable-liquidity domain*) over
  `data_infra/universe_membership.py` (PIT index membership / ST / listing-age) + the **CICC
  exclusion screens** (ST/*ST · 停牌 · 一字板 · 上市未满一年).
- **Unified evaluation** — `src/alpha_research/factor_eval/unified_eval.py` (`EvalMethodology`,
  `n_quantiles=10` deciles, `STYLE_CONTROLS_V1` 14-factor style book, `residual_ic_vs_controls`,
  `neutralized_rank_icir`, `index_forward_returns`) driven by `workspace/scripts/
  unified_eval_universe_matrix.py` → the **7-universe IS matrix** (`results.jsonl`).
- **Factor-lifecycle IS gate** — `factor_lifecycle` orchestrator profile (8th built-in), 4 steps
  `object_resolver → dataset_build → walk_forward → [human gate] → registry_publish`;
  `run_is_walk_forward` + `assign_candidate_status` (`|rank_icir| ≥ 0.10 ∧ sign-consistency ≥
  0.70`, IS-only, `is_end`-bounded).
- **Selection + seal** — `FrozenSelectionSet` (`frozen_set_hash`) + `HoldoutSealStore`
  (single-shot, file-locked) + `reproduce_sealed_oos` / `produce_promotion_evidence` (the
  `draft/candidate → approved` writer gate: clean git SHA + independent PIT-correct OOS).
- **Deployment** — `EventDrivenBacktester` (T+1, multi-tier limits, suspension, corporate actions,
  total-return), `CostConfig.realistic_china()`, `ExecutionProfile`, `univ_liquid_top300`.
- **Registries** — `data/factor_registry/` (`factor_master.parquet` + `evidence.parquet`); the
  master already carries `validation_scope`, `approved_uses`, `long_only_viable_provisional`,
  `latest_oos_rank_icir`, `latest_lo_sharpe_gross`, `expected_direction` — **fields the methodology
  needs are already in the schema; they are simply under-populated today.**

---

## Part C — The staged pipeline

Every stage uses the same rigid template: **Purpose · Inputs · Outputs · Tool · Criteria · Why ·
Failure mode it prevents.** Stages 0–5 + 7 validate the *signal* (status). Stage 6 collapses a
*pool*. Stage 8 tests a *strategy* (deployability metadata). A single factor entering for the first
time walks 0→5; a factor going toward deployment additionally walks 6→8 *as part of a set*.

---

### Stage 0 — Pre-registration & economic hypothesis

- **Purpose.** Force an a-priori, falsifiable rationale *before* any data is touched, so the result
  cannot be a post-hoc story fit to whatever the data showed.
- **Inputs.** The idea (literature, handbook chart, intuition); the intended data sources + their
  Tushare interface docs (PIT/cadence read per CLAUDE.md §6.1).
- **Outputs.** A pre-registration record: economic rationale, **expected direction (sign)**,
  data sources + PIT semantics, intended evaluation scope (universe + window), and the *bar*
  (what would count as pass/fail) — written **before** computing anything. (YAML factor spec /
  `hypothesis_cli.py register`.)
- **Tool.** `workspace/scripts/hypothesis_cli.py`; `.agents/rules/research-integrity.md` §10.
- **Why.** Pre-registration is the only defense against p-hacking and sign-chasing. Recording the
  expected sign a-priori is what makes a later "OOS sign-flip" *meaningful* (it falsifies a stated
  claim) rather than just noise. Without it, every factor "works" with hindsight sign choice.
- **Prevents.** The GP / arXiv-north sign-flip class: factors whose IS sign was a regime artifact.
  Pre-registered sign + sealed OOS is what caught them.

---

### Stage 1 — Definition, PIT-safety, field eligibility → `draft`

- **Purpose.** Turn the hypothesis into a single, PIT-safe, computable definition that the whole
  system can reproduce bit-for-bit, and register it at the floor status.
- **Inputs.** The Stage-0 spec; the factor library operators; the field-status registry.
- **Outputs.** A catalog entry (a Qlib expression) + a registry row at **`draft`** with a
  `definition_hash`; a recorded **price basis** (adjusted for return/momentum, raw for accounting
  ratios) and **decay horizon**.
- **Tool.** `factor_library/operators.py` (`ADJ_CLOSE_T1` etc.), `catalog.py`, the PIT-safety lint
  (`test_factor_library_pit_safety`), `field_status.yaml` / `FieldStatusRegistry`.
- **Criteria.** Every `$field` sits inside a `Ref(...)` frame (no same-day leakage); every field
  resolves `approved` (or the stage policy allows it); `definition_hash` matches the catalog
  algorithm.
- **Why.** `draft` is *free* (earned by definition, not by evidence) — it makes the factor
  computable everywhere for discovery while asserting nothing about quality. Binding the definition
  by hash here is what lets a much later approval be **definition-bound** (the OOS validated *this*
  definition, not a since-edited one).
- **Prevents.** The single most corrosive bug class in this repo: silent PIT leakage (a `$close`
  not wrapped in `Ref` makes factor[T] ⊥ close[T] fail and inflates every downstream metric).

---

### Stage 2 — Universe-stratified IS evaluation (the matrix)  ★ the cheap insurance

- **Purpose.** Measure the full factor-evaluation standard **across all 7 universes at once**, in
  sample, so the factor's *universe-conditional* behaviour is visible before any expensive step.
- **Inputs.** The `draft` factor (field-eligible); the IS window (2010-2020); the 7 `UniverseSpec`
  masks; the `EvalMethodology` (deciles, `STYLE_CONTROLS_V1`, horizon).
- **Outputs.** One row **per (factor, universe)** in `results.jsonl`, each carrying the full metric
  set: `heldout_rank_icir`, `mean_rank_ic` (+ HAC t), `neutralized_rank_icir` (size+industry),
  `resid_ic_vs_style_controls_v1` (the reference-invariant style residual), `decay_icir_{5,10,20,40}`,
  `ic_hit_rate`, quantile monotonicity (`mono_shape`), `turnover_ann`, `coverage`/`coverage_tier`,
  `long_leg_excess_ann_*`, bootstrap CI.
- **Tool.** `unified_eval_universe_matrix.py` over `unified_eval.py`.
- **Why.** **This is the stage the E-wave proved we must never skip.** A single-universe IC hides
  whether the edge is broad or a microcap mirage. The 7 universes are chosen to span the
  deployment-relevant axes: size (`csi300/500/1000`, `microcap`), style (`growth`), and crucially
  **`univ_liquid_top300` — the actual deployable domain**. Measuring all of them costs one matrix
  run; it is the cheapest possible deployment-relevant signal and it is reference-invariant
  (`resid_ic_vs_style_controls` does not depend on the approved book — it is a clean selection
  basis).
- **Prevents.** The E-wave failure *foreseen cheaply*: the 6-core's deployment collapse was already
  visible here — `flow_act_buy_shift_dist_xl` ICIR −0.49 on `univ_all` but **−0.07 / +0.04** on
  `liquid300`/`csi300`; `liq_vstd` **−0.56 → +0.18 (sign-flip)** on liquid. The matrix knew before
  the OOS and the backtest did.

---

### Stage 3 — Scope-stamped quality assessment

- **Purpose.** Read the matrix and produce a *scoped* verdict on the signal's quality and where it
  is real — not a single global number.
- **Inputs.** The Stage-2 per-(factor, universe) rows.
- **Outputs.** A quality record stamped with:
  (a) **validation_scope** — the universe(s)+window on which the factor is genuinely strong;
  (b) **sign-stability flag** — does the sign hold across universes, or flip (a flip = red flag);
  (c) **illiquidity-bound flag** — strong on `microcap`/`univ_all` but weak/absent on
  `liquid_top300` → tag `illiquidity_bound=true`;
  (d) decay profile, turnover, coverage tier, monotonicity.
- **Tool.** New thin reader over `results.jsonl` (proposed; today this read is done by hand).
- **Why.** Status today is silently global ("approved" with no universe). The E-wave + the
  universe-binding discussion concluded: **don't make status a `status × universe` matrix (that
  forces a per-universe OOS lottery), but DO stamp the scope.** Sign-stability across universes is a
  first-class quality criterion because a sign that flips by universe is not a robust economic
  signal — it is a subpopulation artifact.
- **Prevents.** Stamping a single misleading global "approved" on a factor whose edge is microcap-
  bound or universe-sign-unstable (e.g. `liq_vstd`, `flow_act_buy_shift_dist_xl`).

---

### Stage 4 — Marginal-contribution / redundancy assessment

- **Purpose.** Decide what the factor adds *given the factors we already have* — not its standalone
  strength.
- **Inputs.** The factor's panel (IS); the existing book / candidate pool to compare against; the
  evaluation universe (the **deployable** one for a deployment-bound decision).
- **Outputs.** (a) factor-factor **exposure correlation** (month-end Spearman) to the existing set;
  (b) **marginal IC** = IC of the factor orthogonalized against the already-selected set (or the
  cheap proxy `|IC| · (1 − max|ρ|)`); (c) a redundancy/cohort label.
- **Tool.** The exposure-correlation + greedy machinery built for the E-wave selection
  (`workspace/scripts/select_e_wave_marginal.py` — to be generalized); the `marginal>ICIR` memory.
- **Why.** A correlated family of 35 vol variants is not 35 discoveries. Marginal contribution is
  the only honest measure of "should this enter the set," and it is the same principle whether the
  set is "the approved book" (library admission) or "the selected reps" (deployment selection). The
  exposure correlation must be measured on the universe the decision is *for* (deployable decision →
  liquid universe).
- **Prevents.** Cohort inflation (promoting 6 redundant family reps as "6 discoveries") and the
  v1-selection defect (saturating family caps because no redundancy was ever computed).

---

### Stage 5 — IS gate → `candidate`

- **Purpose.** A leak-proof, in-sample-only audition that grades a `draft` as "worth taking
  seriously / worth spending OOS budget on."
- **Inputs.** The `draft` factor; the IS-only windowed panel (`is_end`-bounded); field eligibility.
- **Outputs.** `candidate` (or stays `draft`) + an IS-only evidence row (no `oos_*` field ever),
  `expected_direction`, recorded to the file-locked testing ledger. **Human gate required** to
  write.
- **Tool.** `factor_lifecycle` profile; `run_is_walk_forward` + `assign_candidate_status`.
- **Criteria.** `|heldout_rank_icir| ≥ 0.10 ∧ yearly sign-consistency ≥ 0.70`, field-eligible.
  Fail-closed (missing evidence → `draft`).
- **Why.** `candidate` is the *additive* tier that gates the scarce resource (sealed-OOS budget):
  you do not spend a single-shot OOS on a factor that has not even passed an IS audition. The
  `is_end` belt on the *label-realization* date (not the factor date) is the load-bearing
  no-lookahead guarantee.
- **⚠ Open issue (for review).** This gate today reads the **`univ_all`** matrix row. Given Stage 2,
  should the *gate* read the **investable** universe instead, so `candidate` already means
  "auditioned on tradeable names"? (See Part F, Q1.)
- **Prevents.** Spending OOS budget / deployment effort on IS-marginal factors.

---

### Stage 6 — Family-aware selection (pool → frozen set)

*(Only when a candidate pool is heading toward a single OOS / deployment — not for one factor.)*

- **Purpose.** Collapse a correlated candidate **pool** to a small set of **orthogonal
  representatives**, so the one OOS we spend tests a clean bet, not a redundant lottery.
- **Inputs.** The candidate pool; their Stage-2 IS metrics; the Stage-4 exposure correlation;
  redundancy references (pre-existing related candidates).
- **Outputs.** A `SelectedSet` (~4–9 reps) with a deterministic selection rule + a full accept/
  reject trace; family caps; a documented marginal-floor cut.
- **Tool.** The generalized `select_*_marginal.py` greedy (quality × (1−maxcorr), family-capped).
- **Why.** "69 ≠ 69 discoveries." One sealed OOS on the *set* (not 69 individual OOS = an "OOS
  lottery") is the mandate. Selection must be **IS-only** (no 2021+ touched) so the OOS stays
  unburned; the basis is the reference-invariant style residual / raw strength, **not** a status-
  changing metric.
- **Prevents.** The OOS lottery (testing every correlated variant until one passes by luck) and
  freezing a redundant set into the single irreversible OOS spend.

---

### Stage 7 — Sealed OOS → `approved` (scope-stamped)

- **Purpose.** The one independent, fail-closed out-of-sample proof that promotes
  `candidate → approved`.
- **Inputs.** A `FrozenSelectionSet` (the reps + full recipe: directions, candidate-pool hash,
  selection-rule hash, eval-protocol hash, metric, portfolio side, **universe**, time-split,
  rebalance, neutralization); the sealed holdout window.
- **Outputs.** Per-factor `oos_rank_icir` + `oos_ls_sharpe`; a `HoldoutSealStore` spend keyed by
  `frozen_set_hash`; a `promotion_evidence` artifact (6 PIT canaries + lint + parity + clean git
  SHA, self-verified through the release gate); `approved` for passers **stamped with the OOS
  scope**.
- **Tool.** `reproduce_sealed_oos` + `produce_promotion_evidence` + `HoldoutSealStore`; bar =
  sign-aligned `rank_icir > 0 ∧ ls_sharpe > 1.0`.
- **Why.** The seal makes the OOS un-gameable: keyed by the full frozen identity, spent-on-attempt,
  file-locked, recovery only via the same run. The promotion evidence makes approval impossible to
  fake (independent PIT-correct reproduction, not a self-attested flag).
- **⚠ Critical caveats (E-wave-derived, for review).**
  1. The bar (`ls_sharpe > 1.0`) is a **gross, 5-day, decile long-short, registration metric — NOT
     tradability** (the harness says so). `approved ≠ deployable`.
  2. The OOS today runs on the **full provider universe**. The E-wave passed 6/6 here while being
     microcap-bound. **Should the sealed OOS run on the investable universe** so that "approved" is
     deployment-meaningful? (Part F, Q1 — the single most important open question.)
- **Prevents.** Multiple-testing / peek-then-tweak; faking a promotion; un-scoped approval.

---

### Stage 8 — Deployment gate (strategy-level; produces metadata, NOT status)

- **Purpose.** Answer the *engineering* question: is a **book** built from these factors tradable on
  the **target investable universe**, net of real costs, unlevered?
- **Inputs.** A set of approved/candidate factors **as a book** (weighting / construction); the
  target universe (`univ_liquid_top300` or a defined ESTU); `CostConfig.realistic_china()`; an
  `ExecutionProfile`; the (already-spent) OOS window for descriptive characterization.
- **Outputs.** Strategy metrics (CAGR, MDD, Sharpe, Calmar, turnover, capacity) **per target
  universe**, written to **metadata** (`long_only_viable[universe]`, `latest_lo_sharpe_gross`) —
  **never** to lifecycle status.
- **Tool.** `EventDrivenBacktester` (1×, T+1, limits, corporate actions, total-return),
  `eval_*_deployment.py` pattern.
- **Why this is a *strategy* test, decided by *marginal contribution*.** A factor does **not** need
  to pass deployment *individually*. Its deployment value is its marginal contribution to the
  book's net risk-adjusted return on the target universe. A naive equal-weight standalone composite
  is a *poor* test — the E-wave composite was polluted by 2 universe-sign-flipping factors, so its
  −3.6% CAGR understated the value of the 2–3 members (`corr_ret_turnd` −0.62, `vol_w_downshadow`
  −0.52) that retain genuinely strong liquid IC. **The right deployment test: build the actual
  target book from the IS-sign-stable members, measure each one's marginal net-IR contribution.**
- **Why metadata not status.** Deployability is universe-specific and book-specific and changes as
  the book changes; binding it to a per-factor global status is a category error (and the lifecycle
  README already mandates it stay metadata).
- **Prevents.** (a) Reading a registration-bar OOS pass as deployable (the eps_diffusion +4.5%/−62%
  trap). (b) The inverse error this methodology must also avoid: *condemning a useful factor*
  because a naive standalone composite failed (the correction we made to the E-wave verdict).

---

## Part D — The output contract: what a completed factor eval records

The methodology's deliverable per factor is **not** a single status — it is a scoped record the
schema can already hold:

```
factor_id, definition_hash, expected_direction
status            ∈ {draft, candidate, approved, deprecated}   # signal validation (Q1/Q2)
validation_scope  = {universe, is_window, oos_window?}         # WHERE the status was earned
universe_profile  = { univ_all: icir, liquid_top300: icir, microcap: icir, ... }  # Stage 2/3
flags             = { sign_stable_across_universes, illiquidity_bound }
marginal          = { vs_book_liquid: marginal_ic, exposure_corr_cohort }          # Stage 4
oos               = { frozen_set_hash, oos_rank_icir, oos_ls_sharpe, bar_passed }   # Stage 7
deployability     = { liquid_top300: {lo_viable, cagr, mdd, sharpe, marginal_net_ir} }  # Stage 8 — METADATA
```

`status` answers "is it a real signal (and on what scope)." `deployability[universe]` answers "is a
book using it tradable there." **The two never collapse into one flag.** This is the concrete
resolution of the "should status be bound to universe?" question: **scope-stamp the status; bind
deployability per-universe as metadata; do not build a `status × universe` matrix.**

---

## Part E — Worked case study: the E-wave 6-core through every stage

| Stage | What happened | What the methodology would say |
|---|---|---|
| 0–1 | 8 CICC charts → ~87 PIT-safe drafts | ✅ as run |
| 2 | 7-universe matrix computed | ✅ **but the liquid-universe rows were not read as a gate** |
| 3 | (not done as a stage) | ⚠ would have stamped `illiquidity_bound` on 4/6 and `sign-flip` on 2/6 **before any OOS** |
| 4 | exposure corr only at selection | ✅ 5 orthogonal families confirmed |
| 5 | IS gate on `univ_all` → candidates | ⚠ gate read `univ_all`, not the investable universe |
| 6 | 69 → 6-core (v2, after fixing v1) | ✅ family-aware marginal selection |
| 7 | one sealed OOS → **6/6 PASS** | ✅ method validated, **but on the full universe** → passed while microcap-bound |
| 8 | naive composite deployment → **FAILED** (−3.6% CAGR, −52% MDD) | ⚠ correct verdict for *that book*, but the **naive composite was a poor test** (polluted by 2 sign-flippers); the 2–3 liquid-strong members were never tested as a clean book |

**The lesson the methodology encodes:** the expensive Stages 7–8 told us almost nothing that the
cheap Stage 2–3 read did not already contain. The fix is not "do less governance" — it is "read the
universe-stratified IC as a first-class gate, and make the OOS/deployment universe-honest."

---

## Part F — Open design questions for review (the decisions we want challenged)

1. **Canonical evaluation / gate universe — the big one.** Should the IS gate (Stage 5) and the
   sealed OOS (Stage 7) run on the **investable universe** (`univ_liquid_top300` or a defined ESTU)
   rather than `univ_all`? *For:* makes `candidate`/`approved` automatically deployment-meaningful;
   a microcap-only factor can't earn status; we'd never again spend an OOS on a microcap mirage.
   *Against:* a factor genuinely useful in a *broader* tradeable book (top-800, or as a hedge leg)
   would be rejected by a top-300 gate; "investable" is not unique (depends on AUM / strategy). Is
   the right answer a single canonical gate universe, or *two* gate reads (broad + liquid) with the
   status requiring the liquid one?

2. **Status scope-binding.** We propose: scope-stamp a single status (Part D), **not** a
   `status × universe` matrix (which forces a per-universe OOS lottery and lets "approved-on-
   microcap" badges certify untradeable edges). Is scope-stamping sufficient, or is there a case for
   a small fixed set of status-universes (e.g. status_broad + status_liquid)?

3. **Sealed-OOS budget vs universe-conditionality.** One OOS per frozen set. If a factor is strong
   on liquid but a *different* factor is strong on microcap, do they need separate frozen sets /
   separate seals? How do we avoid the lottery while still validating universe-conditional signals?

4. **Marginal-contribution test design (Stage 4/8).** What is the canonical "does it add to the
   book" test — orthogonalized IC on the liquid universe (cheap) vs add-to-book net-IR increment in
   an event-driven backtest (expensive)? And how do we run it *once* without overfitting the spent
   OOS window (we propose: the *subset choice* must be justified by IS data, the deployment run is
   descriptive on the spent window, and only **one** construction is tried)?

5. **Sign-stability as a hard criterion.** Should universe-sign-instability (Stage 3) **block**
   `candidate`/`approved`, or only flag? The E-wave's 2 sign-flippers passed the full-universe OOS
   but are microcap artifacts — a hard block would have excluded them from the frozen set.

6. **Deployment stays metadata.** We assert deployability is metadata per universe, never status,
   and factors are judged for deployment by marginal contribution to a book — *not* by individual
   deployment. Confirm, or is there a case for a deployable-tier status?

7. **Decay/turnover/cost in the factor stage.** Stage 2 reports `turnover_ann` and `decay_icir`.
   Should a net-of-cost (turnover-adjusted) IC be a Stage-2/3 standard read, so the cost drag that
   killed the E-wave (74%/mo turnover) is visible at the factor layer, not only at deployment?

8. **Where the methodology becomes a Skill.** Once reviewed, this becomes a Claude Code skill with
   per-stage runnable steps + templates. Is the stage decomposition the right granularity, or should
   stages 2–4 (the cheap factor-layer reads) be a single "factor characterization" step?

---

## Part G — What's missing in the current machinery (the build list, if approved)

1. **A Stage-3 reader** that turns `results.jsonl` into the scope-stamped quality record
   (validation_scope, sign-stability, illiquidity-bound) — today done by hand.
2. **Scope-stamping populated** — `validation_scope` / `universe_profile` / `illiquidity_bound`
   exist in the schema but are not written by the promote flow.
3. **A canonical gate-universe decision** wired into Stage 5/7 (pending Q1).
4. **A generalized marginal-contribution tool** (Stage 4) — the E-wave's `select_e_wave_marginal.py`
   greedy promoted to a reusable `factor_eval` function.
5. **A standardized deployment-gate profile** (Stage 8) — today it is ad-hoc `eval_*_deployment.py`
   scripts; it should be an `ExecutionProfile`-pinned, universe-parameterized reusable runner.
6. **Net-of-cost IC** as a Stage-2 metric (pending Q7).

---

*End of v1 proposal. Reviewer: please be adversarial about Part F (esp. Q1) and about whether the
layer separation in Part A actually holds under the system's constraints. The E-wave (Part E) is the
real test case — would this methodology have produced a better outcome, more cheaply, without
weakening the no-lookahead / single-shot-OOS guarantees?*
