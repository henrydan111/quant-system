# Research Plan — Next 3-6 Months (Small-Cap Strategy Direction)

*Authored 2026-05-19 by Claude after reading the JoinQuant briefing package at `C:/Users/henry/Desktop/聚宽回测系统/BRIEFING_*.md` and the local engine canonical files at [project_state.md](../project_state.md), [CLAUDE.md](../CLAUDE.md), [src/system.md](../src/system.md), [data/data_dictionary.md](../data/data_dictionary.md), [data/data_tracker.md](../data/data_tracker.md).*

*Source-of-truth references in this document use the local engine's actual current state (post 2026-04-29 update note in `project_state.md`), not the briefing's facts which are stale on several points.*

---

## TL;DR

Your JoinQuant work has produced **one genuinely robust finding** (calendar effects cross-validated across G4/G5/G7), **one structural insight you haven't acted on** (microcap alpha is real but long-only TopK has a -40% drawdown ceiling — confirmed independently by the local engine's growth-GARP arc at -46%), and **one number that probably means nothing** (+234,625% in-sample G5_A2). The next phase should not be more long-only microcap variants.

Four projects, sequenced:

| # | Project | Purpose | Time |
|---|---|---|---|
| P1 | Sealed-OOS replication of G5_A2 | Gates everything | 1-2 weeks |
| P4 | Capacity-realism Pareto curve | Same recipe, different capital | 2-3 weeks |
| P2 | Long-short size factor (with hedge) | Structural fix for drawdown ceiling | 3-8 weeks |
| P3 | Dynamic regime allocator using alternative data | Replace static 1+4月空仓 | 4-6 weeks |

---

## Critical reframing before the projects

### What's actually true vs claimed

**Robust (well-supported by your own ablations):**
- The `market_cap.asc()` sort is doing essentially all alpha work in G1/G2/G4/G5. G2_B1 collapsing 99% is decisive.
- January + April blank-out cross-validated in 3 frameworks (G4/G5/G7_C0). Single most reproducible finding.
- 2015 market trend stop is real event protection; value concentrated in one regime.
- Real fundamental quality alpha (G3) exists but caps at ~21% annual — useful ceiling for "honest non-microcap alpha."

**Suspect (you flagged these yourself in §1.4 but the rest of the briefing reads as if they're solved):**
- The +234,625% headline is dominated by the 2014-2015 microcap windfall (+500% in 18 months). Strip that and remaining annual return is probably 35-50%, not 90%.
- Sharpe 2.995 from in-sample optimization over 50 variants is not 2.995 in OOS — deflated Sharpe (Lo 2002, Bailey & López de Prado 2014) would shrink this by ~30-40%.
- The "1+4月 specifically" was chosen ex-post; post-hoc rationalizations (年报雷月, 春节流动性) are plausible but not pre-registered.
- Zero walk-forward, zero OOS holdout, zero survivorship verification.

### Two things the briefing materially under-weights

**1. The "18 A-grade factors" claim is stale.** After the 2026-04-12 factor library leakage fix at [src/alpha_research/factor_library/operators.py](../src/alpha_research/factor_library/operators.py), 17 of 18 A-grades lost their A status. Current grade distribution on the 171-factor catalog is **1A / 44B / 82C / 44D** — the sole A is `liq_vol_cv_20d`. GPT's recommendation to "add 3 of the 18 A-grade factors" is built on factors that no longer exist as A-grade. The B/C tier is the realistic enhancement space. (See [project_state.md](../project_state.md) Update Note 2026-04-12.)

**2. The local engine has already told you the answer the JoinQuant work is groping toward.** The growth-stock GARP arc terminated 2026-04-29 with rank_icir 0.466 (15× the floor — extremely strong signal) but **untradeable** in the long-only TopK 50 / 10d frame: max_drawdown -46.2%, annual_turnover 11.8×. Three independent attempts hit the same wall. The local engine's explicit conclusion: *"the failure is risk-side not signal-side"* — forward-paths are (a) risk overlay, (b) reframe harvest (longer rebalance / score-weighted), or (c) long-short. The same wall will hit G5_A2 OOS — you're just not seeing it because you have no OOS.

---

## P1 — Sealed-OOS replication of G5_A2 (foundation)

**Hypothesis.** Most of G5_A2's headline performance is (a) the 2014-2015 microcap bull windfall, (b) JoinQuant's optimistic execution model, and (c) curve-fit to your 50-variant search. After realistic event-driven execution, walk-forward training, and a sealed 2024-2026 OOS holdout, surviving OOS Sharpe will be 1.0-1.7, MDD will be -45% to -60%, and the strategy will look like the local engine's `small_cap` theme replay (+92.5% relative excess but -58.9% MDD) — *real but not at JoinQuant-claimed magnitudes*.

**Why this gates everything.** If OOS Sharpe < 1.0, do not build P2/P3/P4 on top of G5_A2 — pivot to non-microcap (G3-style + alternative data) or directly to long-short. If OOS Sharpe ≥ 1.5, you have a base to enhance.

**Platform.** Local engine via `hypothesis_validation` profile (landed 2026-04-28). JoinQuant cannot do sealed OOS or hash-pinned reproducibility.

**Recipe (will be pinned by design_hash, frozen at registration):**
- Universe: small_cap theme, `sc_u3` candidate (broadest small-cap, ~460 stocks/day — closest available proxy for 中小综 ~800 stocks since 中小综 membership is not directly in `data/universe/`). This is the **biggest fidelity caveat** — see [temp_plan/p1_g5a2_sealed_oos_design.md](temp_plan/p1_g5a2_sealed_oos_design.md) for the decision rationale.
- Selection: single component `size_ln_mcap` with `direction = "lower_is_better"`, topk = 12.
- Composite: `rank_weighted` (only one component, weight = 1.0).
- Rebalance: 5 days (weekly).
- Cost model: 10 bps slippage + stamp tax + exchange defaults.
- Portfolio: long-only, equal-weight, max_position_weight = 1/12 = 0.0834.
- **Walk-forward**: IS 2014-01-01 → 2023-12-31; sealed OOS 2024-01-01 → 2026-02-27 (calendar end).
- Train 5y / val 2y / test 1y / step 1y → 4 folds inside IS.

**Out of scope for P1 (handled in follow-up runs after we have the raw baseline):**
- Calendar blackout (`pass_months=[1,4]`) — `PrescribedRecipe` has no native support; would need schema extension.
- Stoploss rules (individual -12% and market 3-day -6%) — same gap.
- Tuesday 10:30 specificity — schema only supports `rebalance_days=N`.

This is actually **methodologically better** than the JoinQuant work because it isolates the "raw size sort" alpha from the protective overlays. Then we measure the overlay contribution as separate research items.

**Expected magnitude.** Conditional on local engine's `small_cap` theme baseline (+92.5% over 14y / -58.9% MDD): I predict OOS Sharpe **1.2-1.7**, MDD **-45% to -55%**, with the 2014-2015 fold dominating IS by 3-4×.

**Validation.** `hypothesis_validation` pins everything via design_hash. Single shot at the seal — if you retune after seeing OOS, the seal is burned. Pre-register rejection criteria before launch:
- `max_drawdown` floor: -50% (force-relaxed; profile floor is -35%)
- `min_deflated_sharpe`: ≥ 1.0
- `min_regime_pass_count`: ≥ 3 / 4 folds
- `max_annual_turnover`: floor 12.0 (force-relaxed; profile floor is 4.0)

The force-relaxed flags will be required (`--force-relaxed-criteria --override-reason "G5_A2 baseline replication; expected to violate profile floors as documented"`). This is honest — we're measuring whether the JoinQuant strategy survives, not promoting it.

**Failure mode.** The 2024-01 → 2026-02 sealed holdout is ~26 months — wide confidence intervals. Mitigations:
- Use family-variance from the testing ledger.
- Bootstrap the 4 train/test folds for 95% CI on stitched OOS Sharpe.
- If 2014-2015 fold dominates so heavily that removing it breaks the strategy, that's the answer — report it as a finding.

**Time to result.** 1-2 weeks (event-driven IS pass runs in ~8 min post 2026-04-29 perf fix).

**First-step deliverables (in flight now):**
- [temp_plan/p1_g5a2_sealed_oos_design.md](temp_plan/p1_g5a2_sealed_oos_design.md) — design doc with mapping decisions and infrastructure gaps
- [temp_plan/p1_hypothesis_g5a2_v0.json](temp_plan/p1_hypothesis_g5a2_v0.json) — DRAFT hypothesis JSON, not yet registered

---

## P2 — Long-short size factor (structural fix for the drawdown ceiling)

**Hypothesis.** The size premium in A-share is real and structural (Liu, Stambaugh & Yuan 2019, JFE — "Size and value in China"), but its long-only expression is dominated by the same beta that produces -40% drawdowns. A market-neutral version — long bottom market-cap quintile of 中小综, short top quintile or hedge via IC futures — could deliver Sharpe 1.5-2.5 with MDD < -25%, capacity ~¥5-10M. The local engine concluded this independently for the growth signal ([project_state.md](../project_state.md) 2026-04-29: "Long-short or sector-neutral — structural fix for both DD and turnover").

**Why this matters more than another long-only variant.** Your G7 (most风格-orthogonal small-cap in your inventory) only adds 0.05 to COMBO Sharpe because all small-cap members share the size beta. Long-short *removes* that beta. This is the only mechanism in your inventory that can plausibly break the Sharpe-vs-MDD frontier you said is exhausted in §8.

**Implementation (research + engineering, not pure research). Two routes:**

- **Route A (lighter):** Long G5-style microcap basket + short IC futures (中证500) sized to neutralize beta to ~0.2 (slight long bias for the long-A-share structure premium). Implementable in JoinQuant for live trading once researched locally.
- **Route B (heavier):** True cross-sectional long-short. Requires extending `hypothesis_validation` profile to support `side="long_short"` (currently v1 is long-only only — explicit limitation per [project_state.md](../project_state.md) 2026-04-28). Engineering cost: ~2 weeks for orchestrator extension + portfolio_construction step + cost model updates for margin trading (融资融券) borrow costs.

**Academic anchors:**
- Liu, Stambaugh & Yuan 2019 (JFE) — A-share size premium dominated by "shell value" of being publicly listed. Post-国九条 enforcement (2024Q1 雪崩), shell premium is empirically decaying. If shell value drove G5_A2, the 2026 YTD drawdown is the leading edge of a structural decay, not noise.
- Asness, Frazzini, Israel, Moskowitz & Pedersen 2015 (FAJ) — "Size matters, if you control your junk" — small-cap excess returns concentrate in quality-controlled microcap. Your G3_A1 ablation keeping 70% of alpha after removing market-cap neutralization is consistent.

**Platform.** Local engine (research). JoinQuant for the final IC futures hedge implementation (Route A) since it has built-in futures contracts.

**Expected magnitude.** Route A: Sharpe 1.5-2.0, MDD -15 to -25%, capacity ¥3-5M. Route B: Sharpe 2.0-2.8, MDD -10 to -20%, capacity higher because the short side absorbs some volume constraint.

**Validation.** Pre-register margin cost sensitivity (4% / 6% / 8% annual borrow). The short universe in A-share is limited (~1,500 names are 融券-eligible) — pre-register the eligibility intersection ratio as a diagnostic. `hypothesis_validation` with cost_model.slippage_bps and explicit borrow cost.

**Failure mode.**
- (a) Short-side borrow cost eats alpha — beta-hedging legs become +40% gross, +6% net after costs, Sharpe < 1.0.
- (b) Size factor so beta-correlated in A-share that long-short still has high vol.
- (c) Short coverage on microcap names is poor — many of G5_A2's holdings are unborrowable. Mitigation: test "long bottom quintile of 中小综 + short top quintile of HS300" — borrow availability is much better on large-caps.

**Time to result.** Route A 3-4 weeks. Route B 6-8 weeks.

---

## P3 — Dynamic regime allocator using alternative data

**Hypothesis.** The 1+4月空仓 rule captures ~50% of G5_A2's alpha and is your most reproducible finding — but it's static. A dynamic regime classifier using alternative data unavailable on JoinQuant could (a) recover the +200%-style 2024 year while (b) cutting 2026 YTD drawdowns by 30-50%. The 2026 YTD drawdown is the cleanest evidence that static [1,4] is incomplete.

**Why this can beat G6 (your last regime detector that failed).** G6 used 扩散指数 only — a single price-based momentum signal. The local engine now has 4 categories of data G6 couldn't access:
1. PIT-safe fundamental dispersion via [src/data_infra/pit_backend.py](../src/data_infra/pit_backend.py)
2. Namespaced alternative-data flow signals (`$alpha_toplist_hit_density_60d`, `$cyq_perf__winner_rate`)
3. Northbound moneyflow at daily granularity
4. Suspension and limit-state cross-section

**Feature set (≤6 to control overfit):**
- 中小综 60-day momentum z-score
- `flow_net_inflow_20d` (B-grade factor)
- Cross-sectional fraction at upper limit in past 10 days (microcap crowding)
- `alpha_toplist_hit_density_60d` aggregated to market level (B-grade short-signal at stock level interpreted as overheating at market level)
- `cyq_perf__winner_rate` cross-sectional dispersion (high dispersion = uncertain regime)
- `liq_vol_cv_20d` market aggregate (sole A-grade factor, repurposed as liquidity stress proxy)

**Architecture.** Rule-based with thresholds tuned on training fold, NOT opaque ML. Two reasons:
- (a) You can port a rule-based output back to JoinQuant for live trading.
- (b) Overfitting risk on 14 years of monthly observations is severe for any non-linear model.

Output: 3-state {aggressive (1.0× exposure) / neutral (0.5×) / defensive (cash + 银华日利 511880)}.

**Acid test before publication:** the regime detector MUST flag defensive in 2024-01 (microcap 雪崩 month). If it can't, it's no better than G6. This is the explicit `regime_pass_count` criterion.

**Platform.** Local engine for training and walk-forward. Once thresholds stabilize, port to JoinQuant for live execution.

**Expected magnitude.** If it works: replace the static [1,4] alpha contribution (~50% of G5_A2 total) with a dynamic contribution worth ~70-80%, *and* cut 2026-style slow drawdowns 30-50%. If it doesn't: provides decisive evidence the static rule is the right approach.

**Validation.** Walk-forward 2014-2020 train, 2021-2025 test, 2026 sealed. Reject if it doesn't beat static [1,4] on the SAME 2021-2025 test windows. Pre-register max_features = 6 and threshold shrinkage (only switch defensive if z-score < -1.5, not -1.0).

**Failure mode.** Regime detection has high Bayes-risk territory. The honest failure case is "detector decorative or net-negative." Beyond G6's lesson, specific failure to watch: over-using `alpha_toplist_hit_density_60d` — the local engine documented this as a strong short-signal that *degraded* long-only TopK performance when used as a stock-picker. Aggregating to market level might or might not work.

**Academic anchor.** Daniel, Hirshleifer & Sun 2020 (RFS) — behavioral factor model with PEAD + FIN factors that exhibit regime dependence. Pesaran & Timmermann 2007 on regime-conditional asset allocation.

**Time to result.** 4-6 weeks.

---

## P4 — Capacity-realism Pareto curve

**Hypothesis.** G5_A2 at your reported assumption (¥100k) is in a different regime than G5_A2 at deployable AUM (¥1M-¥10M). The degradation curve is steep enough that some of the "alpha vs MDD" trade-offs in your §9 dissolve once volume cap and market impact bind.

**Why this isn't just nice-to-have.** Your briefing §11.1 says capacity is "the most important unknown" but you've done no work on it. The local engine is the ONLY platform that can answer this: EventDrivenBacktester has multi-tier limits (ST ±5%, ChiNext ±20%, STAR ±20%, BSE ±30%, Main ±10%, date-aware), T+1 settlement via `Position.closeable_amount`, 25% daily volume cap per order, commission + stamp tax (2023-08-28 boundary), suspension wiring (post 2026-04-24). JoinQuant's `FixedSlippage(3/10000)` is wrong at any AUM > ¥500k.

**Sweep.** Run G5_A2 (or whatever survives P1) at AUM ∈ {¥500k, ¥1M, ¥5M, ¥10M}. For each, decompose:
- Pure alpha (vectorized, zero costs) — the ceiling
- Cost drag from commission + stamp tax + slippage
- Volume-cap impact: count orders hitting the 25% participation ceiling
- Limit-up unreachable: count target positions that closed at upper limit and were excluded

**Test compensating mechanisms.** Once you have the degradation curve, ask:
- Does N=24 (vs current N=12) scale capacity 2× linearly?
- Does adding a ¥500M+ market-cap floor preserve Sharpe at higher AUM (G3-style hybrid)?
- Does T/T+1 split execution relieve volume constraints meaningfully?

**Platform.** Local engine, EventDrivenBacktester exclusively.

**Expected magnitude.** Predicted: G5_A2 Sharpe degrades from 3.0 IS → 1.5-2.0 OOS at ¥1M → 1.0-1.5 at ¥5M → likely unrunnable at ¥10M. If degradation is flatter, you have more capacity. If steeper, ratio-cap real allocation.

**Validation.** Same walk-forward as P1; vary only AUM. Report `participation_cap_hits / total_orders` per fold as a diagnostic.

**Failure mode.** If degradation is steep, all G1-G7 work needs reframing for higher-cap-floor universes — but that's "discovering reality early," not "research failure."

**Time to result.** 2-3 weeks (same code from P1 runs with different `capital` parameters).

---

## Sequencing recommendation

P1 first (gates everything). P4 second (cheap, runs the same recipe). P2 and P3 in parallel after — P2 is structural and engineering-heavy, P3 is dynamic and data-heavy. Both feed back into P1's recipe for a final v2.

## What GPT-5.5 Pro's plan got materially wrong

1. **Cross-platform validation was Phase 5, not Phase 0.** You don't build factor overlay (Phase 1), alternative data (Phase 2), or ML (Phase 3) on top of an unvalidated recipe.
2. **No pushback on +234,625%.** Sharpe 3 from 50-variant in-sample search demands deflated Sharpe analysis (Bailey, Borwein, López de Prado, Zhu 2014).
3. **Recommended 18 A-grade factors that no longer exist.** Only `liq_vol_cv_20d` survived the 2026-04-12 leakage fix.
4. **Missed the long-only ceiling finding.** Local engine's growth-stock arc concluded with "untradeable in current long-only TopK frame, three paths forward: risk overlay / reframe harvest / long-short."
5. **Zero academic citations.** The 4-5 papers cited above are the minimum starting set.
6. **No mention of `hypothesis_validation`, sealed OOS, design_hash, or the gated lifecycle.** These are the local engine's most important methodological tools.
7. **2024-Q1 microcap collapse missing as acceptance criterion** for the regime detector.

## Open questions

- Your real deployable AUM (P4 calibration).
- Whether you're open to long-short engineering (P2 Route B requires ~2 weeks orchestrator extension).
- Whether the goal is "best paper Sharpe" or "deployable strategy at your AUM."

---

## Implementation progress

- 2026-05-19: Plan written, P1 design doc + draft hypothesis JSON in [temp_plan/](temp_plan/).
- 2026-05-19: **P1 ran end-to-end. Verdict: `is_quarantined`.**
  - Hypothesis `hyp_20260519_003`; run dir `workspace/research/alpha_mining/hyp_20260519_003_g5a2_replication/`.
  - IS measurements (10y 2014-2023, sc_u4-equivalent broad universe, top-12 by `size_ln_mcap`, weekly rebalance, 10bps slippage): **Sharpe 0.926** / cost-adjusted Sharpe 0.906 / **MDD 54.3%** / **turnover 25.46×** / rank_icir 0.209 / bootstrap Sharpe 95% CI [0.293, 1.552].
  - 6/8 hard floor rules pass; 2 fail (max_drawdown, max_annual_turnover) → automated verdict `rejected` → human decision `quarantined` to preserve for follow-ups.
  - Sealed OOS holdout (2024-2026) untouched — both registration and runtime design_hashes show `--expect-claims 0` exit 0.
  - **Headline finding**: JoinQuant's +234,625% / Sharpe 2.995 / MDD -41% G5_A2 claim does not survive realistic execution. Sharpe drops 3.2× (2.99 → 0.93), turnover is 2.2× the JoinQuant figure, MDD is 13pp worse — same structural risk-side wall as the growth-GARP arc. The size signal IS real (rank_icir 7× the floor), but the strategy is untradeable in long-only TopK frame at any deployable AUM.
- 2026-05-19: Orchestrator gate_concern_scoring recovery bug fixed in same session (CLI pre-validation in `hypothesis_cli.py` + runtime recovery in `runtime.py` + 9 new tests in `test_hypothesis_workflow.py`). 188-test suite regress clean. See [project_state.md](../project_state.md) 2026-05-19 update note for full detail.

## Next concrete steps (recommended)

Given P1's findings, the master plan's sequencing holds:

- **P1.1 (Calendar overlay marginal contribution)**: register a follow-up hypothesis that adds the 1+4月空仓 rule to P1's recipe (requires schema extension to `PrescribedRecipe` to support `blackout_months`, OR a custom DAG step in a new profile). Measures whether the calendar rule recovers the IS Sharpe gap from 0.93 toward something deployable. Expected: marginal Sharpe lift ~0.3-0.6, MDD compression ~10-15pp.
- **P1.2 (Stoploss overlay marginal contribution)**: same pattern with dual stoploss (-12% individual + 3-day market trend). Expected: 2015-style event protection adds limited Sharpe (low-probability/high-value), MDD compression ~5-10pp in tail regimes.
- **P4 (Capacity Pareto)**: re-run P1 recipe at AUM ∈ {¥500k, ¥1M, ¥5M, ¥10M} with same EventDrivenBacktester. Quick (2-3 weeks) and answers the deployable-AUM question with data we already trust. Run dir / hypothesis pattern: copy P1 v1 JSON, change `inputs.output_dir` per AUM, rerun. Note: cost-adjusted Sharpe in P1 only dropped 2% relative to raw despite 25× turnover (system concern documented as the `priors_on_cost_sensitivity` concern's "PREDICTIONS WRONG" finding) — P4 should explicitly audit whether cost_model.slippage_bps=10 is being applied per-leg or per-rebalance.
- **P2 (Long-short)**: structural fix for the drawdown ceiling P1 just empirically confirmed. Requires orchestrator extension (`PrescribedRecipe.portfolio.side="long_short"`) — 2-week engineering. The IS measurements from P1 give the long-leg baseline; P2 measures whether short-leg neutralization moves the MDD from -54% to <-25% while preserving most of the size alpha.
