# Capital-allocation layer — build plan v1

> **Synthesis of two independent senior-analyst reviews** (Claude Code, in-session, 2026-06-22; GPT 5.5 Pro,
> via the public repo). Both converged on the same diagnosis — that convergence is the load-bearing signal:
> the platform is a mature factor-*validation* lab and an underbuilt *capital-allocation* engine. This plan is
> the dependency-ordered path to close that gap, written to the project's standing rules (PIT, sealed-OOS,
> unlevered, registries, governance).

## §0 — The convergent diagnosis (condensed)

The value chain is inverted: enormous rigor proves individual signals are real; the part that turns a signal
into PnL is thin. Public evidence both reviewers cite:

- **~7 approved factors, 0 deployed strategies.** `data/strategy_registry/` exists but has **0 objects**.
- **`portfolio_risk` is dormant:** `MultiFactorRiskModel.predict_portfolio_risk()` returns a hardcoded `0.05`;
  `.fit()` is a `pass`; `PortfolioOptimizer` (real cvxpy mean-variance with bounds) has **zero callers**.
- **Risk = size + industry neutralization only.** No covariance matrix, no factor-risk decomposition, no
  exposure bounds.
- **Combination = equal-weight rank averaging** (15 hand-tuned composites + theme grid-search). ML was tested
  and *correctly rejected* (it rediscovered the high-ICIR lottery cluster → falling knives).
- **Long-only only.** The market-neutral leg (low-corr combo, sim Sharpe ~1.46) is parked.

**Fundamental Law framing** (`IR ≈ IC × √breadth × TC`): IC is validated honestly, but **breadth is low by
design** (~7 trusted factors) and the **transfer coefficient is low** (rank → top-K → equal weight, no
optimizer). The highest-ROI move is not another factor — it is the construction layer that lifts TC on the
signals already trusted.

### Two corrections both reviewers agreed to bake in
1. **Unlevered, always (CLAUDE.md §7.11).** The futures-hedged / market-neutral book is a **Sharpe / drawdown /
   diversification** improvement (unlevered CAGR ~12–15%, Sharpe 1.4–1.8), **NOT** a higher-return target. The
   long-only value book (VQ10, +20.7% CAGR / −26.6% MDD / Sharpe 1.01) remains the higher-CAGR book. Do not
   frame hedging as a route to levered return.
2. **Multiplicity by *effective* trials, not naive 370 × 7 × 4.** Factor families are highly correlated
   (E1b = 35 vol variants, E1c = 19 liquidity, …). Penalize by an estimated effective trial count per
   family/correlation cluster; the right bar is **marginal contribution to ensemble IR**, deflated at the
   correct level, NOT standalone ICIR.

## §1 — Design principles this plan inherits (non-negotiable)

- **Unlevered, gross ≤ 1×** (§7.11). MN books sized at natural 1×.
- **PIT + sealed-OOS extends to the strategy layer.** A deployable *book* is itself a single-shot OOS object —
  reuse `FrozenSelectionSet` / `HoldoutSealStore` keyed by a strategy-level hash.
- **The book is a first-class, hash-bound object** mirroring the factor lifecycle. The investable unit is not a
  factor; it is `{signal recipe, universe, alpha transform, risk model, optimizer, costs, capacity, execution}`.
- **Capacity is a first-class stamped output**, not a binary gate. Microcap alpha is *low-capacity product*,
  not "bad".
- **Two product lanes** (liquid-institutional vs capacity-capped-alpha), NOT one deployment gate.
- **Reuse what exists** (do not rebuild):
  - `src/alpha_research/factor_eval_skill/` strategy-build seam — `DeploymentFrozenPlan` (identity.py),
    `FilterDeploymentGateStore` (stores.py), `run_deployment` (deployment.py). PR3 is *already half-started here*.
  - `src/portfolio_risk/optimizer.py` — the cvxpy `PortfolioOptimizer` skeleton (long-only MV + bounds).
  - `src/backtest_engine/event_driven/` — the realistic T+1 / limits / suspension / corporate-action engine.
  - `src/alpha_research/factor_eval/statistical_tests.py` — `deflated_sharpe_ratio` / `probabilistic_sharpe`
    (exist; wire them upstream).
  - `src/alpha_research/factor_eval_skill/multiplicity.py` — the D6 OOS-window multiplicity pattern (extend it
    to discovery).

### §1.1 — Concentrated vs diversified books, and the factor-eligibility rule

Two coherent book archetypes (a SPECTRUM, not a binary) — they differ on many co-varying dimensions, not just
position count:

| | **Concentrated book** | **Diversified book** |
|---|---|---|
| factors / per-factor weight | few; each **load-bearing** | many; each small, none dominant |
| positions / per-name weight | few (e.g. top-10), ~10% | many (100–300+), ~0.3–1% |
| return source | **conviction** — each signal individually strong | **breadth** — LLN over many weak independent bets |
| Fundamental Law term | IR via **IC** | IR via **√breadth** |
| risk shape | high idiosyncratic, lumpy P&L, larger MDD | averaged-out, smooth P&L, smaller MDD |
| Sharpe vs CAGR | higher CAGR / lower Sharpe | higher Sharpe / lower per-name upside |
| capacity | lower | higher (scalable) |
| this system | VQ10 large-cap value top-10 (deployed) | the breadth-harvesting machine (to build) |

**The factor-eligibility rule is keyed off a component's actual LOAD on the book — `component_load`, NOT a
status label, NOT a book "type" tag, and NOT nominal blend weight alone** (GPT review amendment B: nominal
weight is gameable — split one unapproved idea into ten correlated 1% variants and you slip under a 5% gate):
```
component_load_j = max( |raw_blend_weight_j|,
                        ex_ante_marginal_risk_contribution_j,   # via Σ (PR1)
                        marginal_IR_or_alpha_contribution_j,
                        aggregate_family_contribution_j )        # the anti-stuffing term
```
Load-bearing threshold `w*` is a governance PRIOR (default 0.05; require a sensitivity report at
`w* = 0.02 / 0.05 / 0.10` before finalizing):

- **`component_load ≥ w*` (load-bearing):** must be **`candidate_on_declared_target`** — a `candidate`
  whose Stage-5 evidence is bound to the book's declared target (v1.4 A7; a status-only match refuses
  `candidate_scope_mismatch`) — with the explicit `allow_candidate_components=True` attestation. The old
  "`approved`" clause is **legacy-satisfying only** (the 7 pre-v1.4 rows), not required and not expected —
  the factor-level approved mint is retired (v1.4, 2026-07-03). **`draft` is REFUSED** — a load-bearing
  component must carry a validated, target-scoped solo signal.
- **`component_load < w*` (non-load-bearing):** solo status is **provenance**, not a hard gate — validated via
  the **book's** sealed OOS. The noise floor is NOT "any tiny-weight draft" (amendment C). A sub-`w*` component
  is admissible only if ALL hold: (a) sign is pre-declared / inherited from a documented economic prior; (b) IS
  marginal IC/return contribution ≥ 0 after costs; (c) sign consistency clears a low walk-forward floor; (d) it
  is not a near-duplicate of another admitted draft component (no cluster-stuffing); (e) it passes
  liquidity / missing-data / PIT sanity; (f) **total draft + unapproved risk budget ≤ 25–35%** for
  first-generation diversified books (relax later once PR5 is mature).

**Gating (amendment A):** until PR5 (selection-search deflation) is live, a sealed diversified book may **NOT
admit any draft / sub-`w*` component** — PR3 records the eligibility but **refuses the seal**. This stops the
diversified path from being a temporary backdoor before the multiplicity control exists.

Equivalently: a concentrated book requires *every component individually validated*; a diversified book is
*validated as a whole*, and weak/draft components ride on the ensemble's OOS. This is what dissolves the
breadth↔draft tension — breadth = the diversified path, NOT loosening the draft gate.

**Invariants that hold regardless of archetype (so the diversified path is not a backdoor for unvalidated
factors):**
1. The book itself spends **ONE** sealed OOS (`HoldoutSealStore` keyed by the book's frozen hash); D6
   multiplicity counts it.
2. Component **selection** (which factors + weights) is done on **IS**, and the selection search is **deflated
   by effective trials** (PR5). A diversified book that data-mines its subset from the full catalog pays a heavy
   multiplicity tax → prefer **a-priori-structured composition** (≈ one representative per economic cluster),
   which collapses the search space.
3. A `candidate` included in any sealed book **spends its OOS in the book context** (no separate "fresh" OOS
   afterward).
4. A `draft` admitted to a diversified book does **NOT** become individually `approved` — only the *book* is
   validated.
5. Breadth comes from **a-priori economic diversity** (handbooks, papers, alt-data — pre-registered,
   low-multiplicity), NOT from mining the draft pool.
6. The full component list + weights + transforms + family IDs + the **selection algorithm** are FROZEN before
   the sealed OOS (amendment: no post-OOS recipe edit without a new frozen strategy hash + a new OOS spend).

*Enforced at:* PR3 (the `StrategyCandidate` records each component's `component_load` + `status` + family ID +
the resolved archetype, runs the load-bearing check, and — until PR5 is live — refuses a sealed diversified
book containing draft/sub-`w*` components); PR5 (the selection-search deflation).

## §2 — The build plan (dependency-ordered)

> **GPT design-review R1 folded (2026-06-22): "go for PR1 after amendments A–G."** A — diversified draft/sub-`w*`
> admission GATED on PR5; B — `w*` keys off `component_load` (incl. family-contribution anti-stuffing); C —
> noise-floor spec; D — capacity SCHEMA is a PR3 dependency; E — weighted event-driven seam on PR2's critical
> path; F — formal optimizer fails closed; G — PR1 audit harness. Core ordering (risk model → optimizer →
> strategy object) confirmed correct + grounded in the pinned code.

### Critical path (sequential — each unblocks the next)

#### PR1 — Risk model v1 (highest ROI; unblocks everything)
Replace the `predict→0.05` placeholder with a calibrated A-share statistical risk model that runs daily and
fails closed. **Do not start with a full Barra clone.** Minimum v1:

| Component | v1 implementation |
|---|---|
| Industry | CITIC / Shenwan one-hot |
| Size | ln free-float market cap |
| Beta | rolling beta to CSI300 / CSI500 / CSI1000 (universe-appropriate) |
| Volatility | rolling residual volatility |
| Liquidity | ln ADV / turnover |
| Style | value, momentum/reversal, quality, growth (reuse catalog factors) |
| Factor covariance | EWMA with shrinkage (Ledoit-Wolf or constant-correlation target) |
| Idiosyncratic | diagonal residual variance with a floor |
| Output | **full stock covariance Σ**, not a scalar |

**A-share specifics — censored returns (refined per GPT review):** limit-up/down days + suspension gaps bias a
naive EWMA covariance. Do NOT simply drop limit-locked returns (that understates crash/rebound risk) — **flag +
winsorize** them; never treat stale suspended prices as true low-vol returns; align on the **trading calendar**
(not business days). In the **risk overlay**: add an idio-vol uplift for names with recent suspensions, limit
locks, ST risk, or stale prices; stress-test with carried-forward / delayed-realization returns.

Interface:
```
fit(date, universe, returns, exposures)
predict_covariance(date, universe) -> Σ
predict_risk_attribution(weights) -> {factor_risk, idio_risk, active_exposures}
validate(date_range) -> {ex_ante_vol_vs_realized, PSD_ok, condition_number, nan_audit}
```
**Validation & audit harness (amendment G — do NOT skip):**
1. **Return-input audit** + the censoring policy above; **total-return consistency** with the event-driven
   convention (PIT-safe, all rolling windows lag-1).
2. **PIT exposure audit** — industry / free-float mcap / ADV / style / index-beta inputs must clear
   field-status + PIT eligibility (route through the same governance as factors).
3. **Robust cross-sectional regression** for factor returns (WLS / robust; cap single-name influence).
4. **Conditioning diagnostics** — PSD is not enough: track condition number, eigenvalue clipping, covariance
   forecast stability.
5. **Horizon calibration** — the covariance horizon must match the rebalance / holding period, not just daily
   close-to-close variance.
6. **`risk_model_hash` payload** — config + training window + universe + exposure schema + preprocessing policy
   hash into PR3's `risk_model_hash`.

**Definition of done:** Σ is PSD + well-conditioned; ex-ante vol tracks realized vol within tolerance on a
holdout window; the audit harness (1–6) passes; no lookahead; replaces the dormant symbols.

#### PR2 — Optimizer integration (consumes PR1)
Wire the existing cvxpy optimizer into book construction; replace `rank → top-K → equal weight`:
```
maximize   α'w  −  λ_risk·w'Σw  −  λ_turnover·|w − w_prev|  −  λ_cost·E[cost(w − w_prev)]
s.t.       gross exposure ≤ 1.0            (DEFAULT, §7.11)
           long-only  OR  natural-1× MN
           max single-name weight
           industry active-weight bounds
           beta bounds
           size / liquidity exposure bounds
           ADV participation bounds
           exclude ST / suspended / limit-up-buy / limit-down-sell infeasible names
```
Make `risk.max_leverage` legacy/deprecated in the formal optimizer config (default gross ≤ 1×).

**Three amendments (GPT review):**
- **(E) Weighted event-driven seam.** The current `run_deployment` builds a ranked top-K schedule and runs
  `RankedFallbackStrategy` — it cannot honestly validate optimized WEIGHTS. Add a `WeightedTargetStrategy` /
  `date → {symbol: target_weight}` schedule path in the event-driven engine. Without it, PR2 optimizes in
  pandas but can't event-driven-validate. **This is on PR2's critical path, not optional.**
- **(F) Fail-closed in formal mode.** The existing optimizer falls back to equal weights when all solvers fail.
  That is fine for exploratory scripts but **dangerous for a sealed strategy** — the hash says "optimizer-built"
  while the executed weights are fallback. In formal mode, a failed/infeasible optimization must **fail closed**
  (or hash the fallback decision into the strategy artifact so it is auditable).
- **(alpha calibration)** The optimizer needs `α` in **expected-return units over the holding horizon**, not raw
  z-scores. Define a monotonic rank-to-return mapping estimated **inside IS / walk-forward only**, with shrinkage.

**First target (fail-fast):** reproduce VQ10 (the +20.7% value rule) through the optimizer vs top-K head-to-head
on the event-driven engine. **Definition of done — Pareto non-inferiority (softened per GPT):** the
optimizer-built book is non-inferior — equal-or-higher net Sharpe at equal/lower turnover, OR materially lower
drawdown / concentration / tracking-error at acceptable CAGR degradation — event-driven validated. (A
constrained optimizer may rationally trade a little Sharpe for less drawdown/liquidity risk.)

#### PR3 — StrategyCandidate lifecycle (consumes PR1 + PR2)
Extend the factor-eval skill's strategy-build seam into a first-class object + lifecycle mirroring the factor
lifecycle:
```
hypothesis → strategy_candidate → paper_trading → live_small → approved_live / terminal
```
Required hash-bound artifacts on every `StrategyCandidate` (extends `DeploymentFrozenPlan`):

| Artifact | Why |
|---|---|
| factor_set_hash | prevents silent signal changes |
| signal_transform_hash | winsor / neutralization / z-score / direction |
| risk_model_hash | optimizer assumptions auditable |
| optimizer_config_hash | constraints / risk-aversion / turnover penalty |
| execution_profile_hash | binds backtest assumptions to deployment |
| provider / calendar manifest | no stale-provider reuse |
| capacity_report (PR4) | "tradable at what AUM?" |
| kill_criteria | failure observable before capital loss |
| component_eligibility (§1.1) | per-component `{factor_id, weight, status}` + resolved archetype + load-bearing check |

**Factor-eligibility enforcement (§1.1):** `factor_set_hash` resolves to `{factor_id, component_load, status,
family_id}`. At seal time, run the load-bearing check — any component with `component_load ≥ w*` must be
`approved` or (opt-in) `candidate`; sub-`w*` components ride on the book's OOS down to the noise floor. **Refuse
a sealed book whose load-bearing components include a `draft`, AND — until PR5 is live (amendment A) — refuse any
sealed diversified book that admits a draft/sub-`w*` component at all.**

**Capacity-schema dependency (amendment D):** PR3 defines the `capacity_report` artifact SCHEMA. The first
*internal* `StrategyCandidate` may carry `capacity_report.status = "pending_pr4"`, but **no `approved_live` (or
any "would trade" claim) may omit a completed PR4 capacity report.**

**Build the minimal object first (amendment — no over-engineering):** `StrategyCandidate v0` = the immutable
hash-bound record (the artifacts above + sealed-OOS reference + registry record). `paper_trading → live_small →
approved_live / terminal` exist as enum states, but the FIRST PR3 must NOT require a live-monitoring subsystem
(that is the standing "live decay monitoring" concern, later).

Publish into the (currently empty) `data/strategy_registry/`. **Reuse the seal pattern:** a strategy is sealed
too — key `HoldoutSealStore` on a strategy-level frozen hash so a book's OOS is single-shot, exactly like a
factor's. **Definition of done:** one `StrategyCandidate v0` (the VQ10 book) published end-to-end with all
hashes + a capacity report (or `pending_pr4`) + kill criteria + the component-eligibility check, sealed.

### Parallel tracks (proceed alongside the critical path)

#### PR4 — Capacity curve (depends on the event-driven engine, which exists)
Promote the ad-hoc `eval_*_capacity.py` scripts into a **required** strategy artifact:
```
AUM grid:          1m, 5m, 10m, 30m, 50m, 100m, 300m RMB
participation:     1%, 2.5%, 5%, 10% ADV
impact model:      linear + square-root component
outputs:           net CAGR / Sharpe / MDD / turnover / avg & worst participation /
                   days-to-build / days-to-liquidate /
                   AUM where Sharpe decays 25% / AUM where CAGR halves
```
Stamp on every `StrategyCandidate`. A microcap alpha that fails the liquid gate is **routed to the
capacity-capped lane with a capacity number**, not killed.

#### PR5 — Discovery-stage multiplicity (extends the D6 pattern upstream)
Add to every factor/strategy screening result: `raw_icir, hac_t, bootstrap_ci, family_id,
economic_cluster_id, n_trials_family, n_trials_cluster, effective_n_trials, deflated_sharpe_or_ic,
fdr_q_value, pbo_score`. Wire the testing-ledger family counts into the promotion thresholds. Bar:
```
candidate if:  marginal IC contribution > floor
        AND    sign consistency > floor
        AND    DSR/PSR passes a FAMILY-ADJUSTED threshold
        AND    PBO below threshold
        AND    survives a liquidity/capacity pre-check
```
**Not punitive at the single-factor level** — for diversified books the criterion is marginal contribution to
ensemble IR, consistent with the project's own marginal-orthogonal selection philosophy.

**Scope correction (GPT review):** PR5 must count the **strategy-RECIPE search**, not just the factor-catalog
search — `effective_n_trials` must absorb {factor subset · weights · family caps · universe · horizon ·
rebalance · cost model · risk aversion · turnover penalty · capacity screen · neutralization}. Rule:
```
a-priori composition   → n_eff = # pre-declared economic clusters / recipe variants  (low tax)
data-mined composition → n_eff includes the subset + weight + universe/horizon/config search  (high tax)
optimizer weight-learning → must happen INSIDE IS / walk-forward only
recipe changed after seeing OOS → new frozen strategy hash + new OOS spend (multiplicity++)
```
**Build, don't just call:** the existing `factor_eval_skill/multiplicity.py` is an OOS-window spend *counter +
action emitter* — it does NOT compute discovery effective-trials. PR5 EXTENDS the pattern; it is not a one-line
reuse. `statistical_tests.py` PSR/DSR exist but the DSR is a lightweight `sqrt(2·log(n_trials))` approximation
(a starting helper, not the full framework); **PBO/CSCV does not exist — PR5 implements it NEW.**

#### PR6 — Futures-hedged research (proxy first; sequence AFTER PR2)
Three research modes — long-only active / beta-hedged long / **natural-1× market-neutral**. Start with
**index-return proxy hedging, clearly labeled proxy**. The real IF/IC/IM accounting (contract mapping, roll
schedule, margin/cash, basis, daily mark-to-market, calendar alignment) is a **separate subsystem**, not a
quick add — build it only after the proxy validates the structure. **Unlevered throughout.** Goal: the
Sharpe / drawdown improvement (research already found long-only sleeves 0.52–0.79 correlated = shared beta;
the MN combo decorrelates to Sharpe ~1.46), NOT higher raw CAGR.

### Ongoing concern (not a PR — a standing capability)
**Live decay monitoring / kill triggers.** Post-deployment live IC tracking + a decay/crowding kill trigger,
as the continuation of the deployment gate. A factor *will* die; see it before it costs money.

## §3 — ML scope (constrained, per the project's own finding)

| Allowed | Avoid |
|---|---|
| signal weighting with strong regularization | free-form alpha mining |
| volatility / transaction-cost forecasting | high-dim model selection over many raw factors |
| regime-conditioned risk aversion | black-box strategy search under sealed-OOS reuse pressure |
| missing-data / coverage models | "LightGBM for returns" |

Next ML step is a *regularized IC-weighted ensemble with shrinkage + monotonic constraints + family caps*, not
a return-predicting GBM.

## §4 — Sequencing & definition of done

| PR | Depends on | Unblocks | Effort | Delivers |
|---|---|---|---|---|
| PR1 risk model v1 | — | PR2, PR6 | M | calibrated daily Σ + risk attribution + the audit harness (G) |
| PR2 optimizer **+ weighted-exec seam (E)** | PR1 | PR3 | M | optimizer book Pareto-non-inferior to top-K, event-driven validated; fail-closed (F) |
| PR3 StrategyCandidate v0 | PR2 **+ PR4-schema** | the registry | M | first sealed strategy object; **diversified-draft path GATED on PR5 (A)** |
| PR4 capacity curve | event engine | PR3 schema → `approved_live` | S | capacity report (schema lives in PR3, curve here; required before `approved_live`) |
| PR5 discovery multiplicity | testing ledger | **the diversified-book path** | S–M | effective-trials over the RECIPE search; unblocks diversified draft/sub-`w*` admission |
| PR6 futures proxy → real | PR2 | the MN lane | L (real) | beta-hedged / natural-1× book |

**North-star milestone (the missing bridge):**
> *Given the factors we already trust, the system produces a **risk-aware, unlevered, capacity-stamped,
> event-driven-validated book** — published in `strategy_registry`, sealed — that we would actually trade.*

## §5 — What NOT to do (guardrails)

- Do not lever (gross ≤ 1×; MN at natural 1×). `max_leverage` is legacy.
- Do not deflate multiplicity as if 370 × 7 × 4 were independent — use effective trials.
- Do not force the two product lanes through one deployment gate.
- Do not ML-mine alpha (it overfits the high-ICIR lottery cluster).
- Do not call microcap alpha "bad" — stamp it low-capacity and route it.
- Do not make new raw data research-usable before full PIT promotion (normalize → PIT ledger → Qlib →
  field_status → provider manifest). Add a second PIT vendor / cross-source reconciliation for fragile,
  high-value datasets (the JoinQuant-vs-report_rc cross-check is the template).
- Do not let the formal optimizer silently fall back to equal weights (F) — fail closed or hash the fallback.
- Do not gate `component_load` on nominal weight alone (B) — include marginal-risk + family-contribution.
- Do not admit a draft/sub-`w*` component into a sealed diversified book until PR5 deflation is live (A).
- Do not edit a sealed book's recipe after seeing its OOS — new frozen hash + new spend, always.

---

### Provenance
- **Claude review** — in-session 2026-06-22 (four parallel codebase deep-dives + synthesis).
- **GPT 5.5 Pro review** — via the public repo `github.com/henrydan111/quant-system` (independent).
- **Convergence:** both reach the same diagnosis (value-chain inversion; dormant portfolio_risk; empty
  strategy registry; strong integrity layer). Corrections adopted: no-leverage MN framing (§7.11);
  effective-trials multiplicity; capacity-as-product-lane.
- Aligns with memory `strategy_knowledge_base` ("we're 100% long-only, build a market-neutral leg") and
  `project_factor_eval_methodology` (the factor↔strategy seam).
