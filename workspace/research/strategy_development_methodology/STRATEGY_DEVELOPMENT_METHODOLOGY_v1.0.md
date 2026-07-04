# Strategy Development Methodology — v1.0 (DRAFT — pending self-review + GPT 5.5 Pro cross-review, §10)

> **What this is.** The system's ground-truth process for turning trusted factors into deployable
> strategies and composing strategies into a diversified portfolio. It is the *strategy-level* umbrella
> above [FACTOR_EVAL_METHODOLOGY_v1.4](../factor_eval_methodology/FACTOR_EVAL_METHODOLOGY_v1.4.md)
> (which governs the *factor* half, draft→candidate, and the book-seal identity chain). It subsumes and
> re-sequences the [STRATEGY_LAYER_BUILD_PLAN_v1](../capital_allocation_buildout/STRATEGY_LAYER_BUILD_PLAN_v1.md)
> for the current operating reality. It also absorbs the empirical findings and operational playbook of
> its sibling [STRATEGY_ENHANCEMENT_METHODOLOGY](../capital_allocation_buildout/STRATEGY_ENHANCEMENT_METHODOLOGY.md)
> — the 果仁 #9 (`divheavy`) worked case, which *measured* this document's central thesis (2026-07-04).
>
> **Precedence.** On factor-lifecycle / seal-identity mechanics, factor-eval v1.4 wins. On strategy
> construction, validation, composition, and the local↔果仁 loop, **this document is the source of
> truth.** It obeys, and never relaxes, the CLAUDE.md §3 hard invariants and §7 research-integrity rules.
>
> **Status:** design-stage. Grounded in seven deep-research threads + an internal machinery audit + a
> **two-pass adversarial deep-research adjudication of the 7 load-bearing claims** (2026-07-04;
> [DEEP_RESEARCH_ADJUDICATION.md](DEEP_RESEARCH_ADJUDICATION.md) — Claims 1–5 three-vote-verified, 6–7
> primary-sourced). The adjudication **validated the spine** (deployable return = signal-selection /
> tradeability ≫ cost/turnover > universe > weighting; 1/N is hard to beat; sealed-OOS + DSR/PBO) and
> **tightened it**: tradeability is turnover-*conditioned* and belongs as a factor-*admission* gate; the
> "optimizer-beats-1/N" counters were *refuted* (conditioning variable = idio-vol / N / homogeneity,
> Platanakis "Horses for Courses"); the microcap 10–18% CAGR is an *unverified hypothesis*; the
> decorrelation Sharpe ceiling is closed-form `1/√ρ`; effective trials deflate as `N̂ = ρ+(1−ρ)M`; parity =
> differential-testing + backtest reconciliation. **Self-reviewed 2026-07-04 (§10); pending GPT
> cross-review.** Not yet implemented. Appendix E lists the external sources.
>
> **Operating context this is written to (do not silently generalize past it):** solo developer,
> A-share equities, **< 2M CNY capital → microcaps are tradable**, **unlevered (gross ≤ 1×)**,
> single-name shorting restricted, **果仁/guorn is the trusted benchmark + deployment venue and the
> correctness oracle**; the local system has **never traded real capital**. North star = a **diversified
> portfolio of low-return-correlation books**, with the emphasized unit of work being **one individually
> robust, risk-adjusted book**.

---

## Part I — Foundations & Diagnosis

### §1.1 The one-sentence diagnosis: a transfer-coefficient collapse, not a factor shortage

The system has proven, with unusual rigor, that individual signals are real. It has never proven that a
*book* built from them makes money. The reason is structural and has a name.

The generalized **Fundamental Law of Active Management** (Grinold–Kahn, extended by Clarke–de Silva–Thorley):

```
IR  ≈  TC · IC · √breadth
```

- **IC** — the cross-sectional forecasting skill (RankIC/ICIR). *This the system validates honestly.*
- **breadth** — the number of independent bets per year. *Low by design (~a handful of trusted factors).*
- **TC (transfer coefficient)** = `corr(μᵢ/σᵢ, Δwᵢ·σᵢ)` — the fraction of forecasting skill that survives
  portfolio construction. TC ∈ [0,1]; an unconstrained optimal book has TC = 1; real constrained books
  run **TC ≈ 0.3–0.6**. *The system's TC is near the floor.*

`rank → top-K → equal-weight` is close to the **minimum-TC construction possible**: it throws away the
*cardinal* signal (rank 1 and rank K get identical weight), ignores risk (`σ`), and ignores covariance
(correlated top-K names collapse into one bet). Two validated factors run through it can only deliver a
fraction of their IC as IR.

**This reframes every past "strategy failure" in the record.** E-wave passed sealed OOS 6/6 then deployed
at −3.6% CAGR / −52% MDD; eps_diffusion reached `approved` then delivered +4.5% / −62% on the liquid
universe. Those were **not factor failures** — the factors' IC was real. They were (a) a TC collapse and
(b) a universe/capacity mis-scope. *Exceptional strategies are made by raising TC and composing breadth —
not by finding more factors.* The value chain is inverted; the highest-ROI work is the construction and
validation layer, on the factors already trusted.

### §1.2 The three leaks between a good factor and a good strategy

Every past failure is one (or more) of exactly three leaks. The methodology is organized to close each:

1. **TC leak — construction *and* signal-tradeability (two sub-leaks, both measured).** (a) *Construction:*
   cardinal signal, risk-scaling, and covariance are discarded at the `top-K/EW` step. (b) *Signal
   tradeability:* part of the composite's gross IC lives in names you **cannot buy at the open** —
   limit-up gappers, illiquid / short-reversal / overnight signals — real IC that is structurally
   un-capturable. *Closed by §S2 (deployable-alpha-only) + §S3 (construction) + §S4 (fill-price-aware
   execution).*
2. **Universe / capacity mis-scope.** The alpha lives in illiquid microcaps; validated on a liquid
   universe it vanishes, validated gross it is un-tradeable. *Closed by §S1 (declare the investable
   universe first) + §S8 (capacity stamp).*
3. **Signal-vs-strategy validation gap.** A signal passes *cost-free, capacity-free, cross-sectional* IC
   OOS; the *net, path-dependent, capacity-bounded* book still dies. *Closed by §S5 (robustness) + §S6
   (strategy-level sealed OOS on net/liquid PnL, never IC).*

> **The measured case — 果仁 #9 (`divheavy`), 2026-07-04 (parallel session; the sibling enhancement
> methodology).** All three leaks, demonstrated *in this system*, not theorized. A strong cross-style
> composite (IS rank-IC **+0.071 / 5d, +0.108 / 20d, monotonic across 10 deciles, non-microcap**) had a
> **paper** top-K return of **+39–55%** but a **deployed** event-driven return of only **~1/4–1/3 of that**
> (top-K +8–14% CAGR, −40%+ MDD, Sharpe < 0.75) — a 26–46pp gap costs alone cannot explain, on an engine
> that reproduces #9's real book at +26%. **The decomposition is the punchline:** dropping the three
> *un-tradeable* fast factors (`liq_amihud`, `rev_return_5d`, `grn_onmom`) shrank the paper→deployed gap
> from **~26pp to ~1pp** — the slow tradeable core (value + quality + low-vol) deploys **almost
> losslessly**; the high-IC fast factors *are* the leak. The naive first fix (cross-style top-K, sqrt-市值
> weight) scored **+22.9% / −40% / Sharpe 0.90 — worse on every axis** than the #9 replay bar (**+30.0% /
> −33.9% / 1.18**). This is the transfer-coefficient thesis, measured; the risk-aware-construction fix has since
> been tested and did **not** help — an MV optimizer over a pragmatic Σ (λ = 2…100 sweep) failed to beat
> naive top-K on #9 (Sharpe 0.85–0.91 vs 0.90; **MDD worse**, −40 to −47% vs −40%; none beat #9's own
> +30% / −33.9% / 1.18). The *measured* deployable lever is the **signal side** (exclude un-tradeable
> alpha), **not** the weighting/optimizer (§S3; first-cut, pragmatic-Σ, parallel session iterating).

### §1.3 The A-share structural truth — the microcap "problem" is the market, and your size is the edge

The system's recurring finding — *"cross-sectional alpha only lives in illiquid microcaps"* — is not a
bug in the research. It is the **documented structure of the Chinese cross-section.** Liu, Stambaugh &
Yuan (*Size and Value in China*, JFE 2019) show the smallest ~30% of A-shares are priced as
**reverse-merger shells (壳价值)**, not operating businesses, leaving a ~17%/yr E/P alpha a naive model
can't explain; their fix is to *drop the smallest 30%* and use **E/P, not B/M**. The cross-sectional
premium structurally concentrates in the micro-tail.

This inverts the institutional diagnosis for *this* operator:

- **< 2M capital is a rare, genuine capacity edge.** You can hold the 30–50 illiquid names the ¥1.5tn
  quant industry is *forced out of* by capacity and crowding. The thing that killed the "liquid-universe"
  deployments is precisely what you — and almost no fund — can harvest.
- **But the shell premium is decaying, not dead.** 注册制 (market-wide 2023), stricter 退市, and the
  2024 国九条 (loss-making delisting-revenue threshold ¥100M→¥300M, explicitly "降低壳资源价值") are
  structurally impairing the shell-option component. The Wind Micro-Cap Index's ~51%/yr (2009–2023) is
  gone. The regime carries **mechanical −33%-in-5-weeks tail risk** (CSI 2000, Jan–Feb 2024: 雪球
  knock-ins → DMA basis blowout → quant deleveraging → stampede).
- **Harvest the durable liquidity/attention premium; exclude the dying shell/junk; govern the tail.**
- **Honest cross-cycle expectation, unlevered, net of the real 0.5‰ stamp + slippage + T+1 drag:
  ~10–18% CAGR / Sharpe ~0.8–1.1**, with −30% to −50% drawdown *capacity* and multi-year regime risk.
  Not the 40%+ backtest folklore. *The one number never to quote is the gross backtested microcap CAGR.*
- **Deep-research tempering (2026-07-04, [adjudication](DEEP_RESEARCH_ADJUDICATION.md) Claim 3):** treat
  ~10–18% as an **unverified hypothesis — not even an upper bound**: the shell-premium magnitude was
  *refuted* in 3-vote verification and the figure has no surviving primary source; validate it only via a
  sealed strategy-level OOS. In A-shares **~83% of 469 tested anomalies do NOT
  replicate** (Mgmt Science 2023), and a large part of apparent microcap alpha is a **methodological
  artifact of equal-weighting that overweights microcaps, with very limited investable capacity**. The
  micro-tail edge is real-but-fragile-and-shrinking → **deflate candidate signals hard (most are noise);
  make the shell/junk exclusion + multiplicity deflation load-bearing, not optional.**

### §1.4 First principles (non-negotiable; inherited by every stage below)

1. **Unlevered, always** (gross ≤ 1×; §7.11). The deployable number is the 1× number.
2. **The investable unit is the BOOK**, a hash-bound `{factor set, universe, alpha transform, construction,
   costs, capacity, execution}` — not a factor. `approved` factors do not exist (v1.4: candidate is
   terminal); books are the promotion unit.
3. **PIT + single-shot sealed OOS extends to the strategy level.** One `book_seal_key` spend per book,
   ever; observing the OOS *is* spending it.
4. **Validate the STRATEGY, not the signal** — net-of-cost, path-dependent, capacity-aware PnL on the
   *deployable* universe. IC is a factor property; it is never the strategy verdict.
5. **果仁 is the correctness oracle.** The local system has never traded. A locally-developed book must be
   *reproducible on 果仁 under 果仁's own rules* before it is trusted — parity validates the shared
   core (data / PIT / factor formulas / equal-weight execution / limit-suspension handling).
6. **Diversify on realized returns**, not factor exposures; compose low-return-correlation books.
7. **Honesty (§7.10).** No hedge words in a quantitative claim; either the data is run and the cause is
   stated, or the claim is marked unverified with the test that would resolve it.

### §1.5 Two archetypes and the north star

A book sits on a spectrum between two poles (both legitimate; they differ on co-varying dimensions):

| | **Concentrated book** | **Diversified book** |
|---|---|---|
| factors / weight | few, each load-bearing | many, each small |
| return source | conviction (IR via **IC**) | breadth (IR via **√breadth**) |
| P&L shape | lumpy, larger MDD | averaged-out, smoother |
| Sharpe vs CAGR | higher CAGR / lower Sharpe | higher Sharpe / lower per-name upside |
| capacity | lower | higher |
| example | VQ10 large-cap value top-10 (best deployable to date) | the breadth-harvesting machine (to build) |

**North star:** a *diversified portfolio of low-return-correlation books* (Part V). **Emphasis / unit of
work:** *one individually robust, risk-adjusted book* (Part III) — because the system cannot yet reliably
produce even one, and a portfolio of un-robust books is not a portfolio.

---

## Part II — Finding & Building Factors (for strategy use)

The factor lifecycle itself is governed by **factor-eval v1.4** (Stages 0–8: pre-reg → define/PIT →
7-universe matrix → caps → marginal → IS gate → select → freeze → sealed book). *Do not re-derive it
here.* This Part adds only the **strategy-oriented lens**: what makes a factor useful *to a book*, which
is not the same as high IC.

### §2.1 A factor is an input, not a strategy

High standalone ICIR is necessary but not sufficient, and often actively misleading. The system's own
highest-ICIR factors *are* the reversal/liquidity/low-vol microcap-lottery cluster — mutually correlated
and un-tradeable long-only. Chasing ICIR over-picks one redundant, un-deployable cluster.

### §2.2 What makes a factor *strategy-useful* (the five properties to score, beyond IC)

1. **Marginal orthogonal contribution** — IC × (1 − correlation to the existing set), not standalone
   ICIR. Empirically decisive here: greedy-by-marginal reached combined ICIR 1.02 vs 0.70 for
   greedy-by-ICIR; the marginal gain *flattens after ~5 factors*. Use
   `factor_eval_skill.marginal.select_marginal`.
2. **Breadth** — does it generate many independent bets (feeding √breadth), or one concentrated one?
3. **Capacity** — does the IC survive in *tradeable* names and at *your* scale, or only in the illiquid
   tail? (Answered concretely at §S8, but screened here.)
4. **Robustness** — sign-stable across regimes (2015/2018/2021–24), and slow-enough decay that turnover
   cost doesn't eat it (Qian information-horizon: match rebalance to half-life).
5. **A-priori economic diversity** — breadth must come from *pre-registered economic clusters*
   (handbooks, papers, alt-data), **not** from mining the draft pool. Draft-pool mining pays a punishing
   multiplicity tax (§4.3) and manufactures false breadth.

### §2.3 The A-share factor menu that actually carries

Prioritize the families with repeatedly-documented cross-sectional return, and build them the way the
Chinese sell-side standard does (`去极值 → 行业中位数填充 → 标准化 → 行业+市值中性化 → 单因子检验` — which
is already this system's pipeline):

- **Short-horizon reversal** (A股最强; retail-overreaction-driven). *Momentum in the US sense fails.*
  Prefer **residual / industry-neutral reversal** and VWAP-based forms over raw reversal.
- **Liquidity / turnover** (low-turnover premium), **low-volatility / idiosyncratic-vol**.
- **Value via E/P** (E/P dominates B/M in China per LSY), **quality**, **analyst-revision breadth**.
- **Neutralize industry + size *before* combining** (§S2). This is both the Chinese standard and the fix
  that stops a composite from secretly becoming a size bet.

### §2.4 The factor→strategy handoff

The output of factor-eval (a library of `candidate` factors, each with provenance, expected direction,
role, and per-universe IC profile) is the *input* to strategy development. The seam is the
**TargetUniverseDeclaration** (§S1): a factor's candidacy may be earned broadly (`univ_all`,
scope-stamped), but a book binds it to a *declared investable universe*, and that binding — not the
factor's status — is what gates its use in a book (v1.4 A7 `candidate_on_declared_target`).

---

## Part III — Developing ONE Individual Strategy (the core)

A strategy is a **book**: a hash-bound recipe run through nine stages (S0–S8). The order is not
decorative — **the universe is declared before any diagnostic is interpreted** (the single most important
sequencing fix, from the E-wave post-mortem), and **the OOS is not touched until every non-OOS source of
conviction is exhausted.** Stages S0–S5 spend no seal; S6 spends the one seal; S7–S8 gate deployment.

> The four-layer discipline (CLAUDE.md §8) is inside this: **Layer 1 factor** = S2, computed on the full
> market; **Layer 2 universe** = S1, boolean masks not row-drops; **Layer 3 signal** = S2 ranked within
> the sub-universe; **Layer 4 execution** = S3–S4, tradability never encoded in the signal.

### §S0 — Strategy thesis & the pre-declared bar

Before any compute, write the **economic thesis** as falsifiable prose:

- **What is the edge?** (e.g., retail overreaction → short-horizon reversal; capacity-constrained
  institutions forced out of the micro-tail → a liquidity/attention premium you can uniquely hold.)
- **Why does it persist?** Who is on the other side of the trade, and why don't they arbitrage it away?
- **What kills it?** Crowding (the 500指增 excess fell ~7× in four years), a regime break (国九条 on
  shell value), decay. Name the failure mode now.
- **Archetype** (concentrated vs diversified, §1.5) and **evidence_tier**
  (`theory_a_priori / a_priori_is_informed / oos_informed`; an IS-informed hypothesis may *generate* the
  idea but may never be *cited as its own confirmation*).
- **Pre-declared pass/fail bar** — the net-of-cost metric and threshold the sealed OOS (S6) will be judged
  against, frozen *now*, before any OOS observation. This is the `pre_declared_bar` on the
  `DeploymentFrozenPlan`.

### §S1 — Declare the investable universe FIRST

Emit a **TargetUniverseDeclaration** (`factor_eval_skill/identity.py`) *before interpreting S2/S3
diagnostics*. Declaring the universe after seeing which universe the signal wins on is the exact
lookahead that produced the E-wave "wins on microcap → declare small-cap" fork (v1.4 §2.3
`post_hoc_target_choice`).

- **Choose the product lane** (Part V has two): the **capacity-capped micro-tail lane** (your structural
  edge at < 2M) or a **liquid lane**. A book lives in one; they are validated and deployed differently.
- **For the micro-tail lane, bake the 国九条 shell/junk exclusion into the universe-definition filters**
  (hashed into the TUD, frozen thereafter): exclude ST/*ST, revenue < ¥300M with losses, negative
  equity, and explicit delisting-risk names — this is exactly what "应退尽退" now targets, and it removes
  the *dying* half of the shell premium while keeping the durable liquidity premium.
- Universe membership is a **boolean mask over the full market** (Layer 2). Factors are still computed on
  the full market (Layer 1, §S2) so lookbacks and cross-sectional ranks have full context; suspended
  names keep ranking context and are excluded only at execution (Layer 4).

### §S2 — Signal construction: the alpha model (the missing step)

This is the first half of the TC fix. Turn the selected factors into **one calibrated expected-return
vector**, in two sub-steps. *Never feed ranks or raw z-scores to a constructor.*

**(0) Deployable alpha only — measured, not optional (the 果仁 #9 lesson).** Screen tradeability *before*
combining. Include only factors whose edge **survives open-fill execution** — value + quality + low-vol
deploy near-losslessly; **exclude** illiquidity (`liq_amihud`), short-horizon reversal (`rev_return_5d`),
and overnight-momentum (`grn_onmom`)-type factors: their gross IC is real but structurally un-capturable
at the open, and their inclusion is the *measured* cause of the #9 paper→deploy collapse (§1.2). **A
high-IC composite that includes un-tradeable factors is a worse book than a lower-IC composite that
excludes them.** (This is not the same as size-neutralizing — a composite can be non-microcap and still
leak through fast/limit-up-gapping names.)

**(a) Combine into one cross-sectional score.**
- **Neutralize each factor before combining** — demean within industry, residualize on standardized
  ln(market-cap), keep the residual, winsorize (MAD), z-score. Neutralizing *before* the blend stops a
  size/industry bet leaking in through the combiner (and empirically lifts mean IC materially).
- **Default combiner = shrunk / equal-risk composite of the neutralized z-scores.** With noisy annual ICs,
  aggressive IC- or ICIR-weighting is an *error-maximizer* (it overweights the luckiest in-sample factor);
  DeMiguel–Garlappi–Uppal's 1/N result applies to *factor weighting* directly. Start equal-weight on the
  **marginally-selected ~5–15 representatives** (§2.2); add shrinkage-toward-equal only after IS
  calibration; use cross-sectional-regression / IC-shrinkage weighting only with heavy shrinkage.
- **Optional ML combiner** — a *shallow, strongly-regularized* GBDT/ridge/stacking **over the factor
  scores** (not raw prices), the one setting where ML reliably helps (~+3%/yr in the literature). Guard it
  the way §4.6 mandates: **neutralized labels**, liquidity-screened training universe, monotonic
  constraints, purged+embargoed CV, seed-averaged. This is combination, not alpha mining.

**(b) Calibrate to expected-return units.** Apply **Grinold's identity** `α = IC · σ · score` (residual
vol × shrunk IC × standardized score, winsorized), estimated **IS/walk-forward only**. Output is a
per-name expected excess return over the holding horizon — the correct constructor input, and the step
that (with S3) rebuilds TC.

**Horizon-match.** Rebalance to the composite's information half-life; for a < 2M cost-sensitive book,
tilt the blend toward slow-decay families (value/quality) where turnover cost is survivable, and treat
fast reversal as a small, cost-gated overlay rather than the core.

### §S3 — Portfolio construction (the transfer-coefficient layer)

The second half of the TC fix — **and the stage most likely to be built wrong.** The two research threads
appear to disagree; they do not, once you see that **TC is lost at *both* ends:**

- a crude `top-K / equal-weight` loses TC by *discarding* the cardinal signal (thread 1);
- a **naive mean-variance optimizer on a noisy microcap Σ *also* loses TC** by *mistranslating* α through
  estimation error (thread 2: Michaud's "error-maximization"; DGU shows 1/N beats 14 optimizers OOS;
  mean-estimate errors are ~22× as damaging as covariance errors).

The resolution is **principled light construction by default, a covariance optimizer only when it earns
its place.**

**Default = light construction (and the right answer for the micro-tail lane):**
```
target_wᵢ  ∝  calibrated αᵢ            # preserve the cardinal signal (raise TC vs top-K/EW)
   subject to  size / industry neutrality        # no unintended style bet
               max single-name weight            # concentration cap
               industry active-weight bounds
               ADV participation cap              # capacity / impact
               turnover / cost penalty            # match to half-life; survive cost
               capacity ceiling                   # micro-tail = low-capacity product
   optional:   HRP / inverse-vol risk balancing   # no Σ inversion; tolerates singular Σ
```
This preserves breadth *and* cardinal signal without trusting a noisy covariance. HRP (López de Prado) is
the preferred risk-balancer when used at all: it needs no matrix inversion and tolerates the
ill-conditioned Σ that suspensions and limit-censoring produce.

**Graduate to a full MV optimizer only when ALL four hold** (else light construction wins — encode as a
governance gate):
1. the risk model's **bias statistic** `std(realized/predicted) ∈ 1 ± √(2/T)` out-of-sample;
2. the **quality ratio** (independent bets ÷ #names) is materially **> ~0.1** — for a single-factor-
   dominated micro-tail book it usually is *not*, which is itself the answer. *(Deep-research verified: the
   conditioning variable is idiosyncratic-vol / N / homogeneity — Platanakis-Sutcliffe-Ye "Horses for
   Courses"; MV's edge over 1/N rises only as idio-vol falls, and the "optimizer wins at low turnover"
   counter was refuted 0-3);*
3. Σ is real, **shrunk (Ledoit–Wolf), PSD, and well-conditioned**;
4. the optimized book **beats light construction net-of-cost in the sealed OOS**.

> **Reconciliation with the 果仁 #9 enhancement (sibling doc), and the one open validation.** #9
> (`divheavy`) is a *non-microcap* dividend/value book (top-10 median size-pct 0.65), so its Σ is
> comparatively well-conditioned and the MV optimizer plausibly *earns its place* — which is why the
> enhancement methodology goes straight to the optimizer for #9, and why that is correct *for that book*.
> This document's four-condition gate is the general rule for *when* the optimizer is right (light
> construction for the micro-tail lane; the optimizer for a well-conditioned liquid/value book); the
> enhancement's **control experiment** (s3_core top-K vs the *same alpha through the optimizer*) is
> literally a test of gate-condition (4). **Measured verdict (2026-07-04, first-cut):** that control
> experiment has now RUN — and the optimizer **did not earn its place even on #9.** Across a λ = 2…100 MVO
> sweep on a pragmatic Σ, Sharpe stayed flat (0.85–0.91 vs top-K 0.90) and **MDD got *worse*** (−40 to
> −47% vs −40%); nothing beat #9's own +30% / −33.9% / 1.18. This **vindicates the light-construction
> default and gate-condition (4)** (the optimizer must *beat* light construction — here it did not) and
> **refutes the earlier guess that a non-microcap book guarantees the optimizer earns its place.** The
> real, *confirmed* lever is the **signal side** (deployable-alpha selection, gap 26pp→~1pp), not the
> weighting. Caveat: a pragmatic Ledoit–Wolf Σ, not the full factor model, and the parallel session is
> iterating — so treat "raise TC via *optimized* construction" as **challenged, not proven**, and "raise
> TC via *deployable-alpha selection*" as **measured**.

**The risk model (replacing `predict→0.05`) is worth building even if you never optimize** — for risk
*reporting, neutralization, and attribution*. Minimum-viable: `Σ = X F Xᵀ + Δ` with industry one-hot +
size + beta + residual-vol + liquidity; EWMA `F` with Ledoit–Wolf constant-correlation shrinkage; a
**floored** idiosyncratic `Δ` with **uplift** for suspension / limit / ST risk. Handle A-share censoring
explicitly: **winsorize** limit-locked returns (do *not* drop them — dropping hides crash risk), Dimson-
correct / window-exclude stale suspended stretches (they bias correlations toward zero), align strictly to
`trade_cal.parquet`. Validate with the bias statistic, condition number + eigenfactor adjustment, and
covariance-horizon = rebalance-horizon. *Constraints are the cheapest robustness: they cap the damage a
bad estimate can do.*

### §S4 — Execution realism

Reuse the engine as-is (this is a system strength): `EventDrivenBacktester.run(execution_profile=…,
calendar_policy_id=…, run_mode=…)` with `CostConfig.realistic_china()` (0.5‰ sell-side stamp post
2023-08-28, commission, 过户费, named slippage constants), fill-price-aware limit gating (a name locked
限-up at the open is unbuyable; can't-sell on 一字 limit-down), T+1, suspension/delisting handling, and
**total-return corporate actions**.

- **Weighted-target execution already exists (code-map correction, verified 2026-07-04).** The guorn
  enhancement harness runs optimized/explicit weights *today* via
  `ModelIDivLowVolStrategy(weights_mode="explicit")` on a `date → {code: weight}` schedule
  ([guorn_optimize_09.py](../../scripts/guorn_optimize_09.py); order-level primitive
  `_emit_rebalance_orders(target_weights)` in
  [strategies.py](../../../src/backtest_engine/event_driven/strategies.py)). The earlier machinery audit's
  claim that "only `RankedFallbackStrategy` exists → weighted weights can't be validated" was **wrong.**
  BUILD-0c is therefore *not* a from-scratch build — it is to **generalize this guorn-harness-local path
  into a reusable, first-class `WeightedTargetStrategy`** (a much smaller task; the working example and the
  primitive both exist).
- Assume you **cannot exit a limit-down cascade** and **cannot buy a 涨停 lock at the open.** The
  deployable number is the limit-gated, T+1-constrained, cost-laden number.

### §S5 — Robustness battery (build conviction WITHOUT spending the seal)

Everything here runs on **IS / validation folds only** — it is how you earn confidence *before* the
one-shot OOS, so the seal is spent on a book you already believe in:

- **Parameter-sensitivity surface** — Sharpe must be a **plateau, not a spike**; a metric that only
  survives at one parameter value is overfit.
- **Subperiod / regime stability** — sign-consistency across 2015 crash / 2018 bear / 2021–24 micro-cap
  crash; a book that only works in one regime is a regime bet, not an edge.
- **Cost-sensitivity** — sweep commission/slippage/impact; find the cost at which Sharpe → 0. If that
  cost is near your real cost, the edge is cost-fragile.
- **Universe-sensitivity** — liquid vs full-tail (the *known killer*). Quantify how much of the edge is
  micro-tail-bound; that number is the honest capacity story, declared now not discovered later.
- **Perturbation / noise** — jitter returns, drop random names, shift the rebalance date ±k days; the edge
  must survive.
- **Beat the control** — the Qlib **`GBDT-on-Alpha158`** baseline (CSI300 IC ≈ 0.045, IR ≈ 1.0,
  seed-averaged) is a cheap, standardized bar. A hand-built book that can't beat it *net-of-cost on the
  same universe/period* isn't earning its complexity.
- **Overfitting quantification** — build the T×N return matrix over the *recipe* trials and compute
  **PBO via CSCV** and the **Deflated Sharpe** on the max, using **effective N** (cluster correlated
  trials — a re-tuned weight is not a new trial).

**Pre-seal gate (all on IS):** promote to the seal only if **DSR > 0.95 AND PBO < 0.10** on family-
adjusted effective-N, the robustness surfaces are plateaus, and the book beats the baseline net-of-cost.
Check **MinBTL** — the deployable window must be long enough that the expected max-Sharpe under true-zero
across the recipe search stays below the observed Sharpe.

### §S6 — Strategy-level sealed OOS (the one spend)

Freeze the **entire recipe** — factor set + combination weights + calibration + universe + construction +
costs + rebalance + capacity screen — into a **`DeploymentFrozenPlan`**, deriving the **`book_seal_key`**
(v1.4 A2; all spend-differentiating fields are hash material, no `design_hash` fallback). Claim
`HoldoutSealStore` **once**.

- **The verdict metric is net-of-cost CAGR / Sharpe / MDD / turnover / realized capacity on the DEPLOYABLE
  universe — never IC.** This is the precise fix for the E-wave / eps_diffusion failure mode: those passed
  a *cost-free cross-sectional IC* OOS and died on *net / liquid* PnL. Bake the deployable universe and
  realistic costs **into the sealed test itself.**
- Judge against the S0 `pre_declared_bar`. Deflate by effective trials; disclose multiplicity
  (`oos_window_multiplicity`), respecting the virgin-window budget (warn 3 / hard 5 distinct
  `book_seal_key` per window).
- **A8 hard block:** no virgin post-2026-02-27 window may be spent until the strategy-registry promotion
  path exists (roadmap BUILD-3). Until then S6 runs on already-open windows or as a marked dry-run only.
- **Any recipe edit after seeing the OOS = a new hash + a new spend.** There is no "just one tweak."

### §S7 — 果仁 parity verification (the correctness oracle)

**The step that makes locally-developed strategies trustworthy despite the system never having traded.**
果仁 is the trusted benchmark and the deployment venue; the local system is the thing under test. A book
that passes S6 must be **reproducible on 果仁 under 果仁's own rules** before it is deploy-ready.

- **Purpose = end-to-end system-integrity check, not re-grading the strategy.** A metric-and-holdings
  match proves the *shared core* — data, PIT alignment, factor formulas, equal-weight execution,
  limit/suspension handling — is sound. A **divergence localizes a *local* bug.** ("You validate the
  system with trusted strategies, not trusted strategies with an unproven system.")
- **Reproduce under 果仁's cost/PIT model, not the realistic one.** 果仁 uses flat 0.2%/side, no
  slippage, 一字板-only limit block, 公告日 PIT, 后复权. Matching 果仁 under *realistic microcap cost*
  would be a *bug*, not a success — realistic cost is a **separate downstream deployment lens** (§S4),
  not part of parity.
- **Compare both levels:** metric-level (annual / Sharpe / MDD) **and** holdings-level (交易段持仓清单
  diff, membership overlap, rank correlation), reusing `generate_trading_stats` and the guorn-verification
  skill / `guorn_web_validation_campaign` tooling.
- **Known, expected divergence points** (where local bugs hide, and where legitimate design gaps sit):
  PIT visibility (果仁 usable *on* 公告日 vs local strictly-next-open = 公告 + 1 trading day — a real,
  intentional gap that parity *quantifies*), 后复权 adj_factor, custom-factor formula translation, 一字板
  config, cost-on-delta, 09:35 open fill, universe / ST / 北证 scope.
- **Graduated parity ladder** — climb it so the first failure localizes the bug to one subsystem:
  `纯市值 → value/statement → forecast/快报 → momentum/overnight → +大盘择时`. Each rung adds exactly one
  subsystem.
- **Make it a first-class gate (roadmap BUILD-2).** Today parity is offline/scripted; a deploy-ready
  verdict must require parity within a declared tolerance (metric within X%, holdings overlap > Y%),
  wired into the deployment decision — not a manual afterthought.

### §S8 — Capacity stamp, deployment decision, and kill criteria

- **Capacity curve** (roadmap BUILD-5, generalizing the one-off `eval_*_capacity.py`): sweep AUM ×
  ADV-participation with a linear+square-root impact model → net CAGR/Sharpe/MDD, worst-participation,
  days-to-build/liquidate, and **the AUM at which Sharpe decays 25% / CAGR halves.** For < 2M this is an
  *informational ceiling*, not a gate: a micro-tail book is a **low-capacity product**, routed to its lane
  with a number stamped, **not killed.**
- **Deployment decision:** passes S6 (net/liquid/deflated) **and** S7 (parity within tolerance) **and**
  carries a capacity stamp → publish a **`StrategyCandidate v0`** into the (currently empty)
  `strategy_registry`, sealed and hash-bound (factor_set_hash / signal_transform_hash / risk_model_hash /
  optimizer_config_hash / execution_profile_hash / provider+calendar manifest / capacity_report /
  kill_criteria).
- **Kill criteria (pre-declared, S0):** live IC decay past a floor, drawdown breaching the tolerance band,
  crowding (rising co-movement with known factor baskets), or a regime break (e.g., a small-cap liquidity-
  stress circuit-breaker: cut micro-tail adds when small-cap turnover share collapses / index basis
  widens / ST-sector stress spikes). **Adjust the risk layer before rewriting the signal.** A factor will
  die; the job is to see it before it costs money — *not* a macro-timing "alpha" (that is overfit
  folklore; timing is a drawdown-control overlay, never a return engine).

---

## Part IV — Optimizing / Improving Strategies (without overfitting)

Improvement is where most systematic edges are *destroyed*, not created. The rules:

### §4.1 The improvement loop is IS-only; the OOS is spent once

You improve on IS / validation folds. **The sealed OOS is observed exactly once, and any change made after
seeing it requires a new frozen hash and a new spend.** This is the single most-violated discipline in the
system's history (the val_heavy lookahead, the temptation to "re-engineer the E-wave composite after the
deployment number"). "Iterating until the test passes" *is* overfitting the test — the test is no longer
out-of-sample. Log the first OOS result before any follow-up, always.

### §4.2 Prefer robust plateaus to fragile peaks

An improvement that only works at one parameter value, one universe, or one subperiod is curve-fitting.
Optimize toward a **broad plateau** on the §S5 sensitivity surface; a book you can perturb and it survives
is worth ten that show a taller in-sample spike.

### §4.3 Deflate every improvement by the recipe-search multiplicity

Each "improvement" trial is a comparison and must count. Over the *recipe* search space
`{factor subset · weights · universe · horizon · rebalance · cost model · risk aversion · neutralization}`:
compute **effective N** (cluster correlated trials — ONC / hierarchical / eigenvalue; a re-tuned weight is
not a new trial), then apply the **Deflated Sharpe** (SR deflated against the expected max under N
true-zero trials) and a **Harvey–Liu-style haircut / t ≥ 3** hurdle. Use **FWER (Holm)** for a small
curated recipe set ("must not deploy a fluke") and **FDR (Benjamini–Hochberg)** when scanning many
("rank the promising few"). *A-priori-structured composition pays a low tax; data-mined subset search pays
a high one* — which is why breadth must come from economic priors (§2.2), not draft-pool mining.

### §4.4 The discipline of NOT improving

When marginal contribution flattens and DSR stops rising, **stop.** Further tuning is manufacturing
in-sample fit. The right next move is usually not "improve this book" but "add an *orthogonal* book"
(Part V) — that raises portfolio IR without over-fitting a single recipe.

### §4.5 The legitimate improvement levers (that don't overfit)

Ranked by expected ROI for this system, tie each back to the Fundamental Law:

1. **Raise TC — deployable-alpha *selection* first, weighting second.** The measured #9 result (§S3):
   excluding un-tradeable alpha closed the deployment gap (26pp→~1pp), while the MV optimizer did *not*
   beat top-K. So the large *confirmed* gain is signal-side (which factors survive open-fill execution);
   the weighting-optimizer gain materializes only when it clears the §S3 gate (on #9 it did not).
   Neutralization + cost/turnover control still apply.
2. **Raise breadth** — more independent, economically-distinct bets; more names in the book (LLN).
3. **Lower cost** — slower rebalance, slower-decay factors, turnover penalty, capacity-aware sizing.
4. **Add an orthogonal book** — Part V; raises portfolio IR by decorrelation, not by re-tuning.

Note what is *not* on the list: leverage (banned), more correlated factors (redundant), or re-tuning the
recipe on the same window (overfitting).

**Enhancing a strong concentrated book is usually a *risk-axis* win, not a return domination — say so.**
When the baseline is a high-CAGR concentrated bet (e.g. #9's +30% in a value-favourable window), a
risk-aware constructor typically *holds or slightly reduces CAGR while cutting MDD and lifting Sharpe* —
strict Pareto *dominance* of the return may be infeasible, but a strictly better *risk-adjusted* book is
the win (the build plan's "Pareto non-inferiority" bar). Declare up front (§S0) which you are claiming —
return domination or a risk-axis improvement — report the full frontier, and never quietly reframe a
lower-CAGR-but-safer book as "better" without naming the axis (§7.10).

### §4.6 The constrained ML role

ML is allowed for **signal combination** (§S2a), **volatility / transaction-cost forecasting** (feeding
the constructor), and **regime detection** — **never free-form alpha mining** (the system already proved
free ML rediscovers the high-ICIR microcap-lottery cluster: Gu–Kelly–Xiu's equal-weight Sharpe 2.45 vs
value-weight 1.35 is that trap quantified). The mandatory guards, all cheap and all provable: **neutralize
the label** (train on size/liquidity/industry-*residualized* forward returns, so "predict returns" cannot
collapse into "predict smallness"), **liquidity-screen the training universe** *before* fitting,
**cost-aware labels**, **monotonic constraints** on signed factors, **purged + embargoed CV**, and
**seed-averaged after-cost reporting** (single-seed IC is near-meaningless — QuantBench). Pilot **DDG-DA**
(Qlib's in-repo concept-drift meta-learner) as a *stability* wrapper on existing signals under the sealed
rules, not as a new alpha. Harvest the LLM-factor-mining *regularizers* (AST-originality-vs-alpha-zoo,
hypothesis→formula consistency) into factor governance; distrust the LLM-mined factors themselves until
they clear the same PIT + sealed-OOS + cost gates.

---

## Part V — Assembling the Diversified Portfolio of Books

The north star. Once §III can reliably produce *one* robust book, the portfolio is where the durable
risk-adjusted return is actually made — through **decorrelation, not leverage and not (feasibly) hedging.**

### §5.1 The prize is decorrelation

AQR: pushing average pairwise correlation from ~0.4 to ~0 roughly *halves* portfolio vol and *doubles*
Sharpe (toward ~1.4). Dalio's "Holy Grail": ~15 genuinely uncorrelated return streams cut portfolio vol
~80% at constant return. For an unlevered book that cannot manufacture return with leverage, **correlation
is the only free lunch left** — and the system has never used it.

**But the free lunch is small at the correlations you actually have (deep-research verified, 2026-07-04).**
The Sharpe gain from decorrelation alone is closed-form (Hentschel 2025): an equal-weight book of signals
with average pairwise correlation ρ lifts Sharpe by at most **`1/√ρ`**. At this system's long-only sleeve
correlations (**ρ ≈ 0.52–0.79**, §5.2) that ceiling is only **~1.1–1.4×** a single sleeve — the AQR/Dalio
"halve-vol / 15-uncorrelated-streams" gains require **ρ→0**, i.e. a market-neutral book (infeasible here,
§5.3). And **IR has an absolute upper bound as breadth→∞** (`≈ μ_IC/σ_IC`): breadth cannot buy unlimited
IR, and IC-*volatility* (strategy instability) caps it. So decorrelation is the right lever — but frame the
payoff honestly as a *modest* Sharpe lift, not a transformation.

### §5.2 Diversify on realized RETURNS, not factor exposures

The system already learned this empirically and painfully: its long-only style sleeves are mutually
correlated **0.52–0.79** despite *low factor correlation*, because every sleeve is net-long the same market
beta. **Low factor correlation does not imply low return correlation.** Recruit books by deliberately
breaking the beta link along orthogonal *axes*:

- **holding horizon** (intraday/weekly reversal vs multi-month value/trend — the cleanest decorrelator);
- **universe** (micro-tail vs mega-cap vs sector sleeves);
- **signal sign** (mean-reversion vs trend);
- **style regime** (defensive vs cyclical);
- **an explicit lower-beta leg** (§5.3).

Measure candidate books on **realized return correlation and drawdown co-occurrence**, never on the
factor-IC correlation matrix.

### §5.3 The honest China low-beta answer: substitute diversification for hedging

**A true market-neutral book is infeasible at < 2M, unlevered.** State this plainly and stop chasing it:

- **Index futures are lumpy and carry a tax.** One IM (中证1000) ≈ ¥1.18M notional — a *single* contract
  is 60%+ of capital and cannot be sized to a small sleeve; China has no mini/micro contracts; and the
  short pays a persistent **IC/IM basis discount (−5% to −19% annualized)** as locked-in carry that can
  exceed the alpha it protects.
- **单券融券 shorting** is limited, expensive, and was *further* restricted in 2024; **130/30** needs
  reliable shorting you don't have.

Per AQR ("You can't hedge, but you *can* diversify — you merely need a correlation that isn't highly
positive"), the pragmatic low-beta leg is: a **sector/beta-neutral defensive long-only sleeve (β ≈
0.5–0.7)** + a **cash / short-duration-bond overlay** (documented to cut MDD materially, e.g. −34% → −18%
in one study) + optional **50ETF/300ETF option collars** as a *tail* cap on the mega-cap sleeve
(understanding collars bleed premium and neutralize tails, not beta). **Threshold rule:** below ~¥3–4M,
do not use futures at all; above it, *one* IC/IM short becomes usable to beta-hedge the *aggregate* book
(not per-sleeve), and only when the basis discount is shallow.

### §5.4 Meta-allocation across books

With few books and short live histories, **simple beats optimal** (DGU again — none of 14 optimizers beats
1/N OOS with realistic sample sizes):

- **Default:** **risk parity / inverse-vol on a *shrunk* correlation matrix, floored toward 1/N.**
  **Never raw MVO across books.** **½-Kelly at most** if you ever tilt by conviction (full Kelly ≈ 50%
  ruin risk under estimation error; half-Kelly ≈ 90% ruin-avoidance).
- **HRP** enters only once you have **5+ books** (and even then, 1/N often matches it — use HRP for sizing
  *sanity*, not as an oracle).
- **Capacity is a binding cap:** `book_weight = min(risk-parity weight, capacity ceiling)`. The high-
  capacity value core carries scale; micro-tail sleeves are capped small *regardless of paper Sharpe* —
  the discipline that would have prevented treating gross micro-tail LS Sharpe as deployable.

### §5.5 Portfolio-level risk overlay

A **slow** portfolio-level **vol-target + coarse market-trend brake** is the pragmatic risk-off mechanism
and a better use of capital than a lumpy single-futures hedge. Two honest limits: unlevered it can only
scale *down* (you sit in cash in calm regimes, giving up some upside), and a *fast* trigger churns and
whipsaws — exactly the MA-timing failure the system already found. Keep the trigger **deliberately slow**;
expect it to cut MDD and cost a little CAGR. It is drawdown control, not a return engine.

### §5.6 Portfolio governance

- **Rebalance book weights slowly** (quarterly); the underlying books keep their own faster cadence.
  Rebalancing book weights fast just trades estimation noise.
- **Add a book only on evidence of a *unique, low-return-correlation* source** (marginal contribution to
  portfolio IR), never a near-duplicate. **Actively refuse correlated near-duplicates** — they unbalance
  risk and add cost without diversification.
- **Retire a book** on correlation drift into the existing set, or on decayed live IR past its kill floor.

### §5.7 The realistic portfolio target

A **value core + a sector/beta-neutral defensive sleeve + a cash/bond overlay + one or two
orthogonal-*horizon* books**, allocated risk-parity-floored-to-1/N and vol-managed slowly at the top. The
goal is to shave the value book's standalone −27% MDD and lift **portfolio Sharpe toward ~1.2–1.4 via
decorrelation** — earned through correlation structure, not leverage, not (infeasible) hedging. That, at
this capital and these constraints, is what "exceptional" honestly looks like.

---

## Part VI — Build Roadmap (what to build, sequenced to this reality)

Grounded in the 2026-07-04 machinery audit. This **re-sequences** the existing
[STRATEGY_LAYER_BUILD_PLAN_v1](../capital_allocation_buildout/STRATEGY_LAYER_BUILD_PLAN_v1.md) (PR1–PR6):
at < 2M on the micro-tail with 果仁 as the oracle, the binding constraints are **TC and validation**, not
a covariance optimizer — so the TC-raising *signal→weight→execution spine* and the *validation + parity
gates* move to the front, and the full risk-model/MV-optimizer is **demoted** (light construction wins on
the micro-tail; §S3). Consistent with the 2026-06-22 < 2M re-think and the parity reframe.

| Current state (audit) | Build item | Unblocks | Priority |
|---|---|---|---|
| combination = equal-weight rank (`composite()`); no calibration | **BUILD-0a** marginal/shrinkage combiner + **Grinold α = IC·σ·score** calibration (IS-only) | §S2 (alpha model) | **P0** |
| light constructor absent | **BUILD-0b** signal-proportional weights + caps + neutralize + turnover/ADV + optional HRP | §S3 (raise TC) | **P0** |
| weighted execution EXISTS but guorn-harness-local (`ModelIDivLowVolStrategy(weights_mode="explicit")`) | **BUILD-0c** *generalize* it into a reusable first-class `WeightedTargetStrategy` (small; not from scratch) | §S3–S4 weighted-weight validation | **P0** |
| PSR + crude DSR exist; **PBO/CSCV missing**; strategy-OOS metric is factor-IC | **BUILD-1** strategy validation harness: real **DSR** + **PBO/CSCV** + **effective-N** + robustness battery + **net/liquid/deflated** book-OOS metric | §S5–S6 | **P0** |
| 果仁 parity is offline/scripted | **BUILD-2** promote to a **first-class, tolerance-bounded parity gate** wired into the deploy decision | §S7 (the correctness oracle) | **P0** |
| identity chain + `book_seal_key` exist; `cmd_deploy` live **raises**; registry empty | **BUILD-3** wire `run_deployment` (live) + `run_component_diagnostics_in_book_context` + publish `StrategyCandidate v0` | §S6/§S8; **unblocks A8 virgin OOS spend** | **P1** |
| risk model `predict→0.05` | **BUILD-4** risk model v1 (`Σ=XFXᵀ+Δ`, shrinkage, censoring, bias-stat validation) — **attribution/neutralization LENS first, optimizer input later** | §S3 optimizer-vs-light gate | **P1** |
| capacity = one-off `eval_*_capacity.py` | **BUILD-5** reusable AUM-sweep capacity harness (linear+√ impact) | §S8 stamp | **P2** |
| no multi-book layer | **BUILD-6** meta-allocation (risk-parity-floored-1/N) + slow vol/trend overlay + defensive/low-beta sleeve | Part V | **P2** |
| ML unconstrained/distrusted | **BUILD-7** constrained ML combiner (neutralized labels, monotonic, purged CV) + **DDG-DA pilot** + **Qlib GBDT-Alpha158 control** | §S2a / §S5 baseline | **P3** |
| — | **LATER (> ¥3–4M only)** index-futures hedge subsystem (contract map, roll, basis, margin) | §5.3 aggregate hedge | deferred |

**The north-star milestone (unchanged from the build plan):** *given the factors already trusted, the
system produces a risk-aware, unlevered, capacity-stamped, event-driven-validated, 果仁-parity-verified,
sealed book — published in `strategy_registry` — that we would actually trade.* BUILD-0→3 is the minimum
path to it.

---

## Part VII — Governance Integration & Invariants

### §7.1 How this plugs into existing machinery

- **factor-eval v1.4** owns the factor half (Stages 0–8) and the seal-identity chain
  (`TargetUniverseDeclaration → SelectedSet → FrozenSelectionEnvelope → DeploymentFrozenPlan →
  book_seal_key`). This doc consumes that chain; it does not fork it.
- **Sealed-OOS / `HoldoutSealStore`** — the book seal is keyed by `book_seal_key`; the same single-shot
  discipline, one level up.
- **Field-status / PIT / calendar-unfreeze** — unchanged and inherited; post-2026-02-27 windows are born
  sealed (D3); the pre-declared bar and A8 block apply.
- **Registries** — `strategy_registry` is the book home (BUILD-3); metrics via `result_analysis`
  (reuse, never reimplement).

### §7.2 The strategy-level invariants (the non-negotiables)

1. **Universe declared before any diagnostic is interpreted** (no `post_hoc_target_choice`).
2. **Validate the STRATEGY net/liquid/deflated — never IC alone** as the verdict.
3. **One sealed OOS per book** (`book_seal_key`); any post-OOS recipe edit = a new hash + a new spend.
4. **Light construction is the default; the MV optimizer only past the four-condition gate** (§S3).
5. **Unlevered, gross ≤ 1×; no market-neutral *claim* at < 2M** (it is infeasible — say so).
6. **果仁 parity within tolerance before a book is deploy-ready** (the correctness oracle).
7. **`DSR > 0.95 ∧ PBO < 0.10` on effective-N** before the seal; MinBTL respected.
8. **Diversify on realized returns; capacity is a binding weight cap.**
9. **No hedge words; the deployable number is the 1×, net, limit-gated, tail-survived number.**
10. **ML only for combination / risk / execution — never free-form alpha mining.**

### §7.3 Banned strategy-level anti-patterns

Tuning on the OOS window · quoting a gross backtested micro-tail CAGR · equating factor `candidate`/legacy-
`approved` with strategy viability · running MVO on a noisy micro-tail Σ · asserting market-neutrality at
< 2M · adding correlated near-duplicate books · improving a recipe after seeing its OOS · encoding
tradability inside the signal · comparing a vectorized price-return screen to an event-driven total-return
book without accounting for the dividend gap.

---

## Appendix A — Formulas & procedures (implementable)

- **Transfer coefficient:** `TC = corr( μᵢ/σᵢ , Δwᵢ·σᵢ )` across names; realized `IR = TC · IC · √breadth`.
- **Grinold alpha (score→return):** `αᵢ = ICₖ · σᵢ · zᵢ` (residual vol × shrunk IC × winsorized z-score;
  IS-calibrated).
- **PSR:** `PSR(SR₀) = Φ( (ŜR − SR₀)·√(T−1) / √(1 − γ̂₃·ŜR + ((γ̂₄−1)/4)·ŜR²) )` (ŜR non-annualized;
  γ̂₃ skew, γ̂₄ kurtosis).
- **Deflated Sharpe:** PSR evaluated at `SR₀ = √Var[ŜRₙ] · [ (1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)) ]`,
  γ ≈ 0.5772, N = **effective** trials. Deploy-gate `DSR > 0.95`. *(Current code has the crude
  `√(2·ln N)` approximation — BUILD-1 upgrades it to this.)*
- **Effective trials (deep-research verified):** `N̂ = ρ + (1−ρ)·M` — deflate by the *independent* trial
  count inferred from the average trial-correlation ρ (ρ→1 ⇒ N̂→1; ρ→0 ⇒ N̂→M), never the naive M. **Holdout
  is NOT overfitting protection** (≈20 holdouts at 95% ⇒ false positives are *expected*); **log the trial
  count** — Bailey-López de Prado's single most important, usually-missing datum.
- **PBO via CSCV:** build a T×N per-period return matrix over recipe trials → split rows into S disjoint
  blocks → over all C(S, S/2) IS/OOS partitions pick IS-best n\*, take its OOS relative rank ω, form
  logit `λ = ln(ω/(1−ω))` → **PBO = fraction of partitions with λ < 0.** Gate `PBO < 0.10`.
- **Risk-model bias statistic:** `b = std( r_{p,t} / σ̂_{p,t−1} )`; calibrated if `b ∈ 1 ± √(2/T)`.
- **MinBTL (years):** `≈ [ (1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(N·e)) ]² / SR_annual²` — the backtest must lengthen
  as N grows.
- **Effective N:** cluster the trial return matrix (ONC / hierarchical / eigenvalue) — correlated re-tunes
  are *not* independent trials.

## Appendix B — The optimizer-vs-light-construction gate (§S3)

Use **light construction** (signal-proportional + caps + neutralize + turnover + HRP option) **unless ALL**
hold: (1) risk-model bias statistic ∈ `1 ± √(2/T)` OOS; (2) quality ratio (independent bets ÷ #names)
materially > ~0.1; (3) Σ real, Ledoit–Wolf-shrunk, PSD, well-conditioned; (4) optimized book beats light
construction net-of-cost in the sealed OOS. For a single-factor-dominated micro-tail book, (2) typically
fails → light construction is correct.

## Appendix C — 果仁 parity checklist

Reproduce under **果仁's own rules** (flat 0.2%/side, no slippage, 一字板-only block, 公告日 PIT,
后复权, equal-weight). Compare **metrics** (annual / Sharpe / MDD) **and holdings** (交易段持仓清单 diff,
overlap, rank corr). Climb the ladder — `纯市值 → value/statement → forecast/快报 → momentum → +择时` —
so the first divergence localizes to one subsystem. Expected legitimate gaps: PIT +1-trading-day vs 公告日;
后复权 adj; formula translation; 一字板 config; cost-on-delta; 09:35 fill; universe/ST/北证.
Realistic-cost matching is a *separate* lens, **not** parity.

## Appendix D — Honest return expectations (priors to falsify, not targets)

Unlevered, net, cross-cycle: **micro-tail book ~10–18% CAGR / Sharpe ~0.8–1.1** with −30% to −50%
drawdown *capacity* and multi-year regime risk; **large-cap value core ~ +20% CAGR / −27% MDD / Sharpe
~1.0** (the VQ10 benchmark already found); **diversified portfolio target Sharpe ~1.2–1.4** via
decorrelation. **50%+ CAGR is infeasible on clean-PIT unlevered A-share long-only** (confirmed
exhaustively). These are *priors to test on your own sealed OOS*, never targets to reverse-engineer.

## Appendix E — External sources (deep-research, 2026-07-04)

**Fundamental Law / transfer coefficient / combination:** Clarke–de Silva–Thorley, *Portfolio Constraints
and the Fundamental Law* (SSRN 290322); Grinold (1994) via MSCI, *Converting Scores Into Alphas*; Qian &
Hua, *Information Horizon, Portfolio Turnover, and Optimal Alpha Models*; DeMiguel–Garlappi–Uppal, *Optimal
vs Naive Diversification (1/N)* (RFS 2009); Gu–Kelly–Xiu, *Empirical Asset Pricing via ML* (RFS 2020).
**Risk models / construction:** MSCI Barra USE4 + Eigenfactor-Adjusted Covariance notes; Ledoit–Wolf,
*Honey, I Shrunk the Sample Covariance Matrix*; Michaud, *Estimation Error and Portfolio Optimization*;
López de Prado, *Building Diversified Portfolios that Outperform OOS* (HRP); Roncalli, *Introduction to
Risk Parity and Budgeting*; ReSolve, *Portfolio Optimization: Simple vs Optimal* (quality ratio).
**Overfitting / validation:** Bailey & López de Prado, *Deflated Sharpe Ratio*; Bailey–Borwein–López de
Prado–Zhu, *Probability of Backtest Overfitting* (CSCV) & *Pseudo-Mathematics and Financial Charlatanism*
(MinBTL); López de Prado, *Advances in Financial Machine Learning* (purged/embargoed CV, CPCV);
Harvey–Liu–Zhu, *…and the Cross-Section of Expected Returns* & Harvey–Liu, *Backtesting* (haircut Sharpe).
**China A-share:** Liu–Stambaugh–Yuan, *Size and Value in China* (JFE 2019); 复旦发展研究院 微盘股
"冰与火之歌" (CSI 2000 Jan–Feb 2024); 新国九条 / 退市 tightening; 中国基金报 500/1000 指增 excess-return
decay; 华泰金工 因子合成 (BigQuant); 中信证券 印花税减半 (2023-08-28). **Qlib / ML:** Yang et al.,
*Qlib: An AI-oriented Quantitative Investment Platform* (arXiv 2009.11189) + benchmarks; Yao et al.,
*DDG-DA* (AAAI 2022); *QuantBench* (arXiv 2504.18600); *AlphaAgent* (arXiv 2502.16789).
**Multi-strategy / hedging:** AQR, *You Can't Hedge but You Can Diversify* & *Death of Diversification*;
Dalio "Holy Grail"; Man Group, *Impact of Volatility Targeting*; China index-futures basis/contract-size &
2024 融券 restriction notices. *(Full URLs in the seven research-thread transcripts archived with this
effort.)*

---

*End of v1.0 draft. Next: structured self-review against CLAUDE.md §3 invariants + §7 principles, then GPT
5.5 Pro cross-review per §10 (push branch first; commit-pinned public raw links), fold findings, record the
verdict in project_state.md — before any of Part VI is treated as load-bearing.*
