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

## §2 — The build plan (dependency-ordered)

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

**A-share specifics (the detail a top firm checks):** the return inputs are **censored** — limit-up/down days
and suspension gaps bias a naive EWMA covariance. Drop/winsorize limit-locked returns, align on the trading
calendar (not business days), and handle suspension NaN gaps explicitly. PIT-safe (all rolling windows lag-1).

Interface:
```
fit(date, universe, returns, exposures)
predict_covariance(date, universe) -> Σ
predict_risk_attribution(weights) -> {factor_risk, idio_risk, active_exposures}
validate(date_range) -> {ex_ante_vol_vs_realized, PSD_ok, nan_audit}
```
**Definition of done:** Σ is PSD; ex-ante vol tracks realized vol within tolerance on a holdout window; no
lookahead; replaces the dormant symbols (remove them from `KNOWN_DORMANT` once live).

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
Make `risk.max_leverage` legacy/deprecated in the formal optimizer config (default gross ≤ 1×). **First target:
the existing strongest book** — reproduce VQ10 (the +20.7% value rule) through the optimizer and ask: *can
constraints cut drawdown + turnover without killing CAGR?* Benchmark optimizer vs top-K head-to-head through
the event-driven engine. **Definition of done:** an optimizer-built book ≥ the top-K book on net Sharpe at
equal-or-lower turnover, event-driven validated.

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

Publish into the (currently empty) `data/strategy_registry/`. **Reuse the seal pattern:** a strategy is sealed
too — key `HoldoutSealStore` on a strategy-level frozen hash so a book's OOS is single-shot, exactly like a
factor's. **Definition of done:** one `StrategyCandidate` (the VQ10 book) published end-to-end with all hashes
+ a capacity report + kill criteria, sealed.

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
| PR1 risk model v1 | — | PR2, PR6 | M | a calibrated daily Σ + risk attribution |
| PR2 optimizer | PR1 | PR3 | M | optimizer-built book ≥ top-K, event-driven validated |
| PR3 StrategyCandidate lifecycle | PR2 | the registry | M | first sealed strategy object in `strategy_registry` |
| PR4 capacity curve | event engine | PR3 stamp | S | capacity report artifact |
| PR5 discovery multiplicity | testing ledger | promotion bar | S–M | effective-trials-adjusted screening |
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

---

### Provenance
- **Claude review** — in-session 2026-06-22 (four parallel codebase deep-dives + synthesis).
- **GPT 5.5 Pro review** — via the public repo `github.com/henrydan111/quant-system` (independent).
- **Convergence:** both reach the same diagnosis (value-chain inversion; dormant portfolio_risk; empty
  strategy registry; strong integrity layer). Corrections adopted: no-leverage MN framing (§7.11);
  effective-trials multiplicity; capacity-as-product-lane.
- Aligns with memory `strategy_knowledge_base` ("we're 100% long-only, build a market-neutral leg") and
  `project_factor_eval_methodology` (the factor↔strategy seam).
