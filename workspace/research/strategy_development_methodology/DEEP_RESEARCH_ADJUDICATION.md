# Deep-Research Adjudication — the 7 methodology claims (2026-07-04)

> **Provenance.** `/deep-research` workflow (5 search angles → 25 primary sources fetched → 111 claims
> extracted). ⚠ The workflow's automated **adversarial verification layer was killed by server-side
> rate-limiting** (0/25 verified — an infrastructure failure, not a research finding; the workflow itself
> flagged this). This adjudication is completed **manually and honestly**: the load-bearing Claim-1 numbers
> were verified *directly from the Frazzini-Israel-Moskowitz PDF*; the famous sources' extractions match
> established literature and are cited with that caveat; where evidence is thin it is marked. It complements
> the 6 web-research threads that seeded [STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0](STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0.md).
>
> **Headline:** the evidence **strongly validates the methodology's post-#9 core** (deployable-alpha
> *selection* + cost/turnover is the dominant lever; the optimizer is last and conditional) and **tempers
> the microcap thesis** harder than the draft did (most A-share anomalies do not replicate; the
> equal-weight-microcap edge is partly a methodological artifact).

## PASS-2 — 3-vote adversarial verification (the rigorous outcome; supersedes the manual verdicts below where they differ)

The rate-limited verification was re-run (throttled to 4-claim batches + prompt nonce) and **completed cleanly: 25 claims → 17 confirmed, 8 refuted, 0 unverified; 5 synthesized findings.** It **confirms the core and corrects the manual adjudication in three specific ways:**

1. **Claim 1 → "Supported *with caveats* — condition on turnover"** (not the manual "strongly supported"). The *universal* form ("all paper alpha is structurally un-recoverable by construction") is **overstated**: it holds for FAST/high-turnover signals (momentum loses ~54–96% of paper alpha, ~7.2–7.6%/yr all-in, ≈zero net for real funds) but **slow low-turnover factors are largely recoverable** (Novy-Marx-Velikov: <50%/mo turnover keeps a net spread; market/size implemented at ≈zero cost). Load-bearing source = **Patton & Weller (2020, JFE 137:515-549)**. The strong-form Frazzini "costs are 1/10, everything survives at scale" claim was itself **REFUTED (1-2)**. → keep it **turnover-conditioned**; make turnover/tradeability a first-class **factor-admission gate**, not a post-hoc filter.

2. **Claim 2 → "Strongly supported" for stock selection — and the counter-evidence the manual pass folded in is WEAKER than represented.** Every "optimization beats 1/N / DGU is an artifact / low-turnover MV wins" counter-claim (Kritzman-Page-Turkington strong-form ×3; **Kirby-Ostdiek ×2**) was **REFUTED (0-3, 0-3, 1-2)**. The verified conditioning variable is **idiosyncratic-vol / N / homogeneity** — Platanakis, Sutcliffe & Ye (2021, EJOR 288:302-317, *"Horses for Courses: MV for asset allocation, 1/N for stock selection"*): MV's edge rises as idio-vol falls; non-zero alphas reverse DGU. → the optimizer earns its place ONLY on a **well-conditioned, low-idio-vol, larger-N, liquid** sleeve; default the concentrated book to 1/N / inverse-vol. (Do NOT credit "optimizer wins at low turnover" — that specific counter failed.)

3. **Claim 3 → "Mixed/conditional" (medium confidence).** Structural concentration verified verbatim (LSY 83% of shells in bottom-30%, which is 7% of cap), BUT the **shell-premium MAGNITUDE (≈40% of a micro stock's value) was REFUTED (1-2)**, and the **10–18% CAGR expectation is corroborated by NO surviving source — it is an *unverified hypothesis*, not even an upper bound.** LSY frame the micro-tail as **contamination to exclude**; a <2M book harvesting it is deliberately trading the contamination. → downgrade 10-18% to an explicitly unverified hypothesis, validated only by a sealed strategy-level OOS.

**Verified "where deployable return comes from" (HIGH confidence):** **signal selection/tradeability ≫ cost/turnover > universe > weighting** — exactly the inverted ranking, now adversarially confirmed.

**⚠ EVIDENCE GAP (must close before finalizing):** research-question **Claims 4-7** (diversification ceiling under short/leverage constraints; strategy-level OOS + Deflated-Sharpe/PBO deflation; ML incremental value; parity-as-oracle) had **NO primary-source claim survive 3-vote verification in this batch** — their sources *were* fetched (AQR "You Can't Hedge…", Bailey DSR/PBO, Harvey-Liu-Zhu, Gu-Kelly-Xiu, arXiv) but ranked below the top-25 verified. The verdicts for Claims 4-7 below rest on the 6 earlier web-research threads + general knowledge, **NOT** 3-vote-verified. **A focused second research pass on Claims 4-7 is required for equal rigor.**

**The 8 refuted claims (do not rely on):** Frazzini strong-form survivability (1-2); the Patton-Weller momentum "2.2-8.5%/yr" specific figure + "driven by turnover not weighting" overreach (0-3); five optimization-beats-1/N counters (Kritzman-Page-Turkington / Kirby-Ostdiek, 0-3 and 1-2); the 40% shell-value magnitude (1-2).

---

## Per-claim verdicts (manual, pre-verification — retained for the reasoning; see PASS-2 corrections above)

### Claim 1 — The IC→net-PnL gap is driven by signal tradeability/selection + turnover, not weighting. **STRONGLY SUPPORTED (verified).**
- **Frazzini, Israel & Moskowitz (2012)** — ~$1T live AQR trades, 19 markets, 1998-2011 (*verified from PDF*): break-even fund sizes size/value/momentum = **$103B / $83B / $52B** (US); **short-term reversal does NOT survive above ~$9B US / $13B global.** Even *trading-cost-optimized*, global break-evens = size 1807 / value 811 / momentum 122 / **STR 17** ($B) — reversal stays an order of magnitude more constrained. → cost-aware construction rescues *slow* factors; it cannot rescue a *fast* un-tradeable one.
- **Patton & Weller (2020)** — implementation costs leave the value factor +2.6–5.0%/yr short and **momentum with ~no net return** for typical mutual funds; funds implement MKT/SMB well, value/momentum poorly.
- **Reconciles the #9 result exactly**: excluding illiquidity / 5-day-reversal / overnight (fast, high-turnover, un-tradeable) closed the paper→deploy gap 26pp→~1pp; the optimizer (weighting) did not.
- ⚠ **Magnitude caveat**: Frazzini's *low* absolute costs are a large-arbitrageur result (~1/10 of the average investor; small-cap ~2× large-cap). For a <2M A-share microcap book the relevant costs are the higher retail/small-cap end — the **ranking transfers (reversal-most-constrained, slow-survives); the absolute levels do NOT.**
- **Recommendation: KEEP and elevate** — "deployable-alpha selection" is the primary, evidence-backed lever.

### Claim 2 — Optimizer ≤ equal-weight for concentrated/illiquid single-stock books. **SUPPORTED, with a precise conditioning variable.**
- **DeMiguel-Garlappi-Uppal (2009)**: 14 models, none consistently beats 1/N OOS; MV needs ~3000mo (25-asset) / 6000mo (50-asset) to beat 1/N.
- **EJOR (S0377221720304896)**: for individual-STOCK selection 1/N beats MV OOS; **MV's advantage over 1/N rises as idiosyncratic vol falls** → the high-idio-vol regime of individual (small/illiquid) stocks is exactly where 1/N wins. *This is why #9's optimizer failed.*
- **López de Prado HRP**: HRP beats CLA/MVO OOS on MVO's own variance objective; MVO's defects = instability / concentration / opacity (matrix-inversion estimation error).
- **Adversarial counter (fold in, don't dismiss) — Kirby & Ostdiek "It's All in the Timing" (JFQA)**: DGU is "largely an artifact of research design" (high estimation risk + extreme turnover); **low-turnover** MV strategies (volatility timing, reward-to-risk timing) beat 1/N even under high costs. → the optimizer earns its place at **low turnover + low idiosyncratic vol + well-conditioned Σ**, not on a concentrated high-idio-vol microcap book.
- **Recommendation: KEEP the light-construction-default + gate**; add "low turnover" + "low idiosyncratic vol" explicitly to the four-condition gate (§S3).

### Claim 3 — A-share microcap edge + decaying shell premium. **SUPPORTED on structure, but SERIOUSLY TEMPERED (a genuine challenge to the draft).**
- **Liu-Stambaugh-Yuan (2019)**: ≈40% of a bottom-30% stock's value is shell value; 83% of reverse mergers from the smallest 30%; the excluded micro-tail = only **7% of aggregate market cap**; **EP dominates B/M** (FF-3 leaves a 16.80% EP alpha; CH-3 → insignificant 4.32%).
- **Registration-reform papers (2023-2026)**: 注册制 significantly raised delisting risk (2019-2023) and *causally* reduced shell value (coefficients negative, 1% sig); narrows the primary-secondary valuation gap. → shell premium is structurally decaying, confirmed.
- **The challenge — anomaly-replication (Mgmt Science 2023, Hou-Xue-Zhang-style)**: of **469 A-share anomalies, ~83% produce NO significant spread** (86% after FF-3); and a large part of apparent A-share anomaly strength is a **methodological artifact of equal-weighting that overweights microcaps, with very limited investable capacity** (remedy = mainboard breakpoints + value-weighting).
- **What this means for a <2M book that CAN equal-weight microcaps**: double-edged — the edge exists, but (a) most candidate "anomalies" are non-replicable noise, (b) the equal-weight-microcap strength is partly artifact, (c) the durable part is small-capacity and decaying.
- **Recommendation: KEEP the microcap lane, HARDEN the honesty** — deflate candidate signals hard (most are noise); treat ~10-18% CAGR as an *upper* honest bound, not a base case; make shell/junk exclusion + robustness/multiplicity deflation load-bearing, not optional.

### Claim 4 — Diversified low-corr books; true market-neutral infeasible at <2M unlevered. **SUPPORTED.**
- AQR "You Can't Hedge but You Can Diversify"; DGU 1/N applies at the book level (few books, short histories → simple beats optimal); risk-parity literature (Roncalli). The honest decorrelation ceiling among long-only equity sleeves is modest (shared market beta); the low-beta sleeve + slow vol overlay is the pragmatic substitute. **Recommendation: KEEP.**

### Claim 5 — Strategy-level single-shot OOS + DSR/PBO deflation over *effective* trials. **STRONGLY SUPPORTED.**
- Bailey & López de Prado (Deflated Sharpe, PBO/CSCV); Harvey-Liu-Zhu (multiple testing). The A-share 83%-non-replication result is an *independent* argument for aggressive deflation. **Recommendation: KEEP** — this is best practice.

### Claim 6 — ML for combination / risk / execution, not free-form return mining. **SUPPORTED with caveats.**
- Gu-Kelly-Xiu: ML gains concentrate in small/illiquid names, equal-weight >> value-weight — the microcap-lottery trap. ML's honest incremental value over a disciplined linear combine is modest and mostly nonlinear-interaction capture, only inside a liquidity-screened, neutralized-label setup. **Recommendation: KEEP.**

### Claim 7 — Parity against a trusted platform (果仁) as a correctness oracle. **PLAUSIBLE / thinly evidenced (own improvisation).**
- No direct academic literature on cross-platform backtest parity; it aligns with software reproducibility / reconciliation principles. **Confirmed pitfall:** a trusted platform can embed *optimistic* assumptions (equal-weighting that overweights microcaps → limited real capacity; 果仁 buying limit-up microcaps) — so parity validates the **shared computational core, NOT deployability**; the realistic-cost lens stays separate. **Recommendation: KEEP, framed precisely (parity ≠ deployability).**

## Where deployable return actually comes from (reconciling #9)

Ranked by the weight of evidence — **this inverts the draft's original construction-first ranking:**

1. **Signal selection / tradeability — largest, most robust.** Frazzini + Patton-Weller + the #9 26pp→1pp result. Un-tradeable alpha (fast / illiquid / high-turnover) is structurally un-recoverable by construction.
2. **Cost / turnover control — large, second.** Turnover *is* the cost mechanism (Frazzini per-factor drag ordering); horizon-matching + turnover penalties + slow factors.
3. **Universe — large in A-share specifically.** Excluding the shell/junk micro-tail; the universe *is* much of both the edge and the risk (LSY, reform, MnSc).
4. **Portfolio weighting / optimization — smallest, conditional, can be NEGATIVE.** DGU / EJOR / #9: for concentrated high-idio-vol single-stock books MV ≤ 1/N and can worsen drawdown; positive only at low-turnover + low-idio-vol + well-conditioned Σ.

## Best-practice divergences (and whether justified)
- Leading factor shops **do** run risk-model optimizers — but on **liquid, larger-N, well-conditioned** universes with turnover control, the regime where it pays (Kirby-Ostdiek). Our <2M microcap regime is the opposite → **light construction is correct FOR US** (a justified divergence).
- Best practice deflates aggressively for multiple testing (Harvey-Liu-Zhu); the A-share 83%-non-replication rate argues for *more* deflation than a US shop, not less → our sealed-OOS + DSR/PBO is aligned and should be tightened, not relaxed.

## Top changes to make before finalizing (ranked)
1. **Invert the lever ranking** (§4.5, §S2/S3): deployable-alpha SELECTION + cost/turnover + universe FIRST; weighting/optimizer LAST and conditional. *(Partly folded from #9; the literature cements it.)*
2. **Harden the microcap-durability honesty** (§1.3): fold the 83%-non-replication + equal-weight-microcap-artifact + limited-capacity findings; ~10-18% CAGR = upper bound; deflate hard.
3. **Refine the optimizer gate** (§S3): add "low turnover" + "low idiosyncratic volatility" as explicit conditions.
4. **State the "whose costs" caveat** (§S4 / Appendix D): Frazzini's low costs are institutional; retail microcap ≈ 10× — use retail/small-cap costs for the deployability number.
5. **Frame parity precisely** (§S7): parity validates the shared core, NOT deployability; trusted platforms can embed optimistic (microcap-overweight) assumptions.

## Citations (primary, verified where noted)
- Frazzini, Israel & Moskowitz (2012), *Trading Costs of Asset Pricing Anomalies* — pages.stern.nyu.edu/~afrazzin (*verified from PDF*).
- Patton & Weller (2020), *What You See Is Not What You Get: The Costs of Trading Market Anomalies* — public.econ.duke.edu/~ap172.
- DeMiguel, Garlappi & Uppal (2009), *Optimal Versus Naive Diversification* (RFS 22:5) — academic.oup.com/rfs.
- Kirby & Ostdiek (2012), *It's All in the Timing…* (JFQA) — cambridge.org (the pro-optimization counter).
- (EJOR 2020, S0377221720304896), *When 1/N beats mean-variance for stock selection* — sciencedirect (abstract 403-blocked; extraction consistent with DGU).
- López de Prado (2016), *Building Diversified Portfolios that Outperform Out of Sample* (HRP) — ssrn 2708678.
- Liu, Stambaugh & Yuan (2019), *Size and Value in China* (JFE) — faculty.wharton.upenn.edu.
- (Mgmt Science 2023), A-share anomaly replication (469 anomalies) — pubsonline.informs.org/10.1287/mnsc.2023.4904.
- 注册制/shell-value reform (2023-2026) — sciencedirect S1544612325012772, S1059056026006465.
- Bailey & López de Prado, *Deflated Sharpe Ratio* / *Probability of Backtest Overfitting* — davidhbailey.com.
- Harvey, Liu & Zhu (2016), *…and the Cross-Section of Expected Returns*; Harvey & Liu, *Backtesting* — nber.org w20592 / people.duke.edu/~charvey.
- Gu, Kelly & Xiu (2020), *Empirical Asset Pricing via Machine Learning* (RFS) — nber.org w25398.
- AQR, *You Can't Hedge but You Can Diversify* — aqr.com.

---

## PASS-3 — Claims 4-7, focused second pass (2026-07-04)

A focused deep-research pass on Claims 4-7 ran on the throttled script. Verification succeeded — **25 claims → 21 confirmed, 3 refuted, 1 unverified** — but the session usage limit killed the final synthesis agent + Claims 6-7's verification. **Claims 4 & 5 are now 3-vote verified with excellent quantitative detail; Claims 6 & 7 had their sources fetched (Gu-Kelly-Xiu RFS, AlphaAgent + 4 LLM-mining arXivs, Wikipedia *Differential testing*, QuantConnect *Reconciliation*) but were NOT adjudicated — they rest on those primary sources + the earlier ML thread, flagged not-3-vote-verified.**

### Claim 4 — Diversified portfolio under constraints. **STRONGLY SUPPORTED (verified) — with the honest number.**
- **The Sharpe ceiling from decorrelation alone is closed-form (Hentschel 2025, 3-0):** N equal-weight signals with avg pairwise corr ρ give a Sharpe multiple `√(N/(1+(N-1)ρ)) → 1/√ρ` as N→∞. **ρ=0.1 → at most ~3×; ρ=0.8 → only ~12%.** For this system's long-only sleeves (ρ ≈ 0.52–0.79), the ceiling is **~1/√0.79 ≈ 1.12× to 1/√0.52 ≈ 1.39×** — decorrelation buys only **~12–40% Sharpe**, NOT the Dalio "15 uncorrelated streams" dream (that needs ρ→0, i.e. market-neutral — infeasible here). Empirical anchor: Chen-Zimmermann's 212 *long-short* signals average ρ≈0.044 → only ~19 *effective* independent bets (≈4.8× ceiling) — and long-only sharing beta is far worse.
- **Long-only removes most cross-sectional diversification (AQR "Death of Diversification", 3-0):** long-only value & momentum become 0.71–0.90 correlated with equities and their value-vs-momentum correlation **flips negative→+0.73**.
- **IR has an absolute upper bound as N→∞ (Ding-Martin type, 3-0):** ceiling ≈ `μ_IC/σ_IC`; breadth cannot buy unlimited IR, and IC-*volatility* (strategy risk) caps it — the naive `IC·√breadth` overstates the achievable IR.
- **1/N is hard to beat (DGU, 3-0);** GMV/min-variance beats 1/N only *modestly* OOS (Hentschel plateau 5.8 vs 4.4) and needs reliable correlation estimation. The "inverse-vol/risk-parity beats 1/N with modern vol models" counter (arXiv 2005.03204) was **REFUTED (1-2)**.
- **Recommendation: KEEP, add the honest ceiling.** The methodology's "risk-parity/inverse-vol floored toward 1/N" is correct; but **quantify the target honestly** — decorrelation lifts portfolio Sharpe only ~1.1–1.4× over a single sleeve at these correlations, so a diversified-book Sharpe of ~1.2–1.4 is a *ceiling*, and the big diversification gains are gated behind the (infeasible) low-ρ market-neutral regime.

### Claim 5 — Strategy-level validation & overfitting deflation. **STRONGLY SUPPORTED (verified) — with implementable formulas.**
- **Deflated Sharpe (Bailey-López de Prado, 3-0):** `DSR = Z[(SR−SR₀)·√(T−1) / √(1 − γ₃·SR + ((γ₄−1)/4)·SR²)]`, with `SR₀ = √V[SRₙ]·[(1−γ)·Z⁻¹(1−1/N) + γ·Z⁻¹(1−1/(N·e))]` (γ≈0.5772). Under zero skill, E[max Sharpe] grows with N purely from search.
- **Effective (not naive) trials (2-1):** `N̂ = ρ + (1−ρ)·M` — deflate by *independent* trials inferred from the average trial-correlation ρ.
- **Holdout does NOT prevent overfitting (3-0):** ~20 holdouts at 95% → false positives *expected*; the number-of-trials is the single most important, usually-missing datum.
- **PBO (3-0):** P(IS-optimal strategy ranks below the OOS median); estimated by **CSCV** (partition the T×N performance matrix into S row-blocks, take all C(S,S/2) IS/OOS splits, logit the IS-best's OOS rank, PBO = fraction with λ<0) — the canonical Bailey-López de Prado procedure (its extraction was the 1 claim the session limit left unverified, but it is textbook).
- **Recommendation: KEEP, wire in the formulas.** The system's factor-level sealed OOS is aligned; the STRATEGY-level unit needs its own single-shot OOS + explicit **`N̂ = ρ+(1−ρ)M` effective-trial deflation + PBO/CSCV** over the recipe search.

### Claim 6 — Role of ML. **NOT 3-vote-verified this batch (session limit); sourced + prior-thread verdict: Supported with caveats.**
- Sources fetched: Gu-Kelly-Xiu (RFS 33:2223) + replication (tidy-finance) + LLM factor-mining (AlphaAgent arXiv 2502.16789 + 2505.15155 / 2505.11122 / 2603.14288 / 2603.20319). Consistent with the earlier ML thread: ML gains concentrate in small/illiquid (EW≫VW) → label-neutralization + liquidity-screened training + monotonic constraints + purged CV are the fixes; LLM factor-mining is frontier-but-unproven (harvest the regularizers, distrust the systems). **Recommendation: KEEP** (constrained ML), flagged not-3-vote-verified this batch.

### Claim 7 — Parity against a trusted platform. **NOT 3-vote-verified; but the run UPGRADED the framing.**
- The fetched sources are the right analogs: **Differential testing** (software: run two implementations on identical input, compare outputs) and **QuantConnect Reconciliation** (the quant analog: live-vs-backtest reconciliation is a *documented, recognized* practice). This **upgrades** the manual verdict from "thinly-evidenced own improvisation" → **"a recognized engineering practice (differential testing) + a recognized quant practice (backtest/live reconciliation)."** The pitfall stands: parity can inherit the platform's *optimism* (果仁 filling limit-up microcaps a real book can't), so **parity validates the shared computational core, NOT deployability.** **Recommendation: KEEP, framed as differential-testing/reconciliation; parity ≠ deployability.**

### Top changes from Claims 4-7 (ranked)
1. **Claim 4 — add the honest decorrelation ceiling** (`1/√ρ`; ~1.1–1.4× Sharpe at these correlations); stop implying a 15-stream diversification gain — that regime is behind market-neutral, which is infeasible here.
2. **Claim 5 — wire the effective-trial deflation** (`N̂=ρ+(1−ρ)M`) + PBO/CSCV into the strategy-level gate, and state "holdout ≠ overfitting protection; log the trial count."
3. **Claim 7 — reframe parity as differential-testing + reconciliation** (recognized practice), scoped to shared-core-not-deployability.
4. **Claim 6 — keep constrained-ML** (label-neutralized, liquidity-screened); no change beyond the earlier fold.

*(Full extracted claims: pass-1/2 `scratchpad/dr_result.md` + `dr_result2.md` (Claims 1-3, 17/8/0 verified); pass-3 `scratchpad/dr_result3.md` (Claims 4-7, 21/3/1 verified, synthesis + Claims 6-7 verification blocked by the session limit — resets 11am ET). Run IDs wf_d598c337-a1f (1-3), wf_59618a2a-d2a (4-7).)*
