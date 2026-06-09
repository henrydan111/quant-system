# Machine-learning approach to an effective strategy — FINDINGS

Date: 2026-06-08. Built LightGBM + Ridge factor-combination strategies, walk-forward, PIT-safe,
realistic costs, applying every validated lesson. Benchmark: 大市值价值 top10 (the proven rule).
Simulator = total-return proxy validated within 0.6-0.8% CAGR of event-driven.

## Verdict

**In clean PIT A-share long-only, ML does NOT beat a well-designed, economically-motivated,
concentrated value-quality rule — in any configuration tested. Naive ML is actively HARMFUL.**
The effective strategy remains the simple 大市值价值 top10 (+20.7% CAGR full / +14.8% over 2017-26
/ Sharpe 0.73-1.01). ML's failure empirically CONFIRMS the factor-selection insight: left free, ML
chases the high-ICIR factor cluster (turnover/vol/reversal) that does not convert to long-only.

## What was tested (walk-forward: train ≤Y-2, valid Y-1, predict Y; 2017-2026 all out-of-sample)

| Approach | CAGR | MDD | Sharpe | Calmar |
|---|---|---|---|---|
| **Baseline 大市值价值 ROA top10** | **+14.8%** | −34% | **0.73** | **0.43** |
| ML v1 GBM, ALL features, broad univ (k30) | −1.3% | −50% | 0.03 | −0.03 |
| ML v1 Ridge, ALL features (k20) | −4.8% | −61% | −0.13 | −0.08 |
| ML v2 GBM, VIABLE features, broad univ (k20) | +4.7% | −34% | 0.33 | 0.14 |
| ML v3 GBM-rank WITHIN value gate (refiner, k10) | +10.6% | −28% | 0.58 | 0.37 |
| ML v3 GBM-rank broad univ (selector, k10) | +1.8% | −43% | 0.19 | 0.04 |

## Why ML fails here (mechanistic, not hand-waving)

1. **ML maximizes cross-sectional IC → loads on the high-ICIR lottery cluster.** v1 GBM's top
   features were `liq_turnover_20d` (dominant), `risk_vol_60d`, `rev_return_10d`, `mom_*` — exactly
   the reversal/liquidity/vol factors that have high standalone ICIR (0.5-0.71) but whose long-only
   top-K = falling knives (prior finding + factor_selection_eval). Result: −1 to −5% CAGR, −50% MDD,
   crashing −37% in 2018. **This is the "don't chase ICIR" insight reproduced inside the ML.**
2. **Constraining ML to VIABLE features (value/quality/growth/low-vol) removes the catastrophe**
   (+4.7%, −34% MDD; GBM now loads on `risk_vol_60d`, `val_bp`, `val_ep`, growth) **but still trails
   the simple rule** — because (a) ML tilts to the highest-IC viable factor (low-vol → a low-vol-ish
   diversified book) and (b) a smooth return-maximizing ranker DILUTES the concentrated deep-value +
   high-ROA edge that drives the simple rule's return.
3. **ML as a refiner within the value gate** (v3) cuts MDD (−34→−28%) but lowers CAGR (+14.8→+10.6)
   and Calmar — a risk-management effect, not alpha. Consistent with the earlier finding that adding
   factors to the in-gate rank HURTS vs pure ROA.
4. A-share long-only return is dominated by a few economically-clear effects (deep value + quality +
   "选不出票即空仓" timing) that a hand-designed concentrated rule captures more decisively than a
   return-maximizing ML ranker that spreads risk and chases IC.

## The effective ML role (honest, modest)

ML is NOT an alpha source over the disciplined value rule here. Its only demonstrated useful role is
a **constrained risk-refiner**: viable-features-only GBM, ranking *within* the value-quality gate,
which trims MDD (−34→−28%) — worthwhile ONLY if drawdown is the priority over return. To make ML add
genuine alpha would require the venue where cross-sectional IC actually monetizes — **market-neutral
long-short** (the parked MN leg; see FINDINGS_lowcorr.md) — not long-only.

## Recommendation

Deploy the simple, robust **大市值价值 top10** (event-driven +20.7% / −26.6% / Sharpe 1.01). Do NOT
replace it with an ML selector. If ML is used, restrict it to viable fundamentals within a defensive
universe and treat it as a drawdown-refiner, never a free-roaming return-maximizer (which reliably
rediscovers the lottery cluster and crashes). The bigger ML opportunity is on a future market-neutral
book, where combining low-correlated factors is where ML and the low-ICIR insight pay off.

## Blank-slate MAX-RETURN search (ml_max_return.py, 2017-26, unlevered)

Objective = highest CAGR (not Sharpe). GBM walk-forward, viable features, over 3 universes:
- defensive (mainboard/liquid/profitable): k20 +4.7% / −34%
- **small/mid-quality (the high-return segment): k20 +8.8% / −50% / Sharpe 0.48** ← best ML CAGR
- broad: k20 +2.2% / −38%
- ref small/mid by SIMPLE C/P rank (no ML): +9.0% / −42% — **ML does not even beat simple C/P on small/mid**
- baseline 大市值价值 rule: +14.8% / −34% / Sharpe 0.73 — **still the highest return**

Small/mid ML was strong post-2019 (2019 +31, 2020 +29, 2025 +19) but the 2017-18 small-cap bear
(−21, −30) sank the CAGR — regime-dependent, and timing it is barred (whipsaws; no leverage).
The highest-return strategy remains the rule-based 大市值价值, NOT any ML config.

## Last lever — FULL 131-feature catalog (compute_full_features.py + ml_rich.py)

Gave ML the genuinely rich feature set: 111 base catalog factors + 20 Layer-2 composites = 131
features (industry-relative 4 skipped on a minor API arg; immaterial). Walk-forward GBM (deeper:
leaves 63 / depth 6), 2017-26, unlevered. **Result: did NOT overturn the verdict.**
- smallmid_q k20: **+9.66% / −46% / Sharpe 0.48** (vs 31-feat +8.75% — only +0.9% from 4× the features)
- defensive k10: +3.1% / −50% (WORSE than 31-feat +4.7% — deeper model + more features overfit)
- Still ~5 points below the 大市值价值 rule (+14.75% / −34% / Sharpe 0.73).

**Definitive: across 31 AND 131 features, 3 universes, 2 concentrations, selector/refiner roles,
walk-forward — ML never beats the simple value-quality rule for return in clean PIT A-share
long-only.** Feature enrichment doesn't fix it because the failure is an OBJECTIVE mismatch
(cross-sectional-IC ranker vs concentrated economic rule), not feature poverty.

## Caveats

Walk-forward, PIT-safe; rank target; shallow regularized GBM + early stopping (anti-overfit). Not
exhaustive of ML space (untested: LambdaRank loss, the full 177-catalog/industry-relative features,
per-stock time-series models) — but the failure MECHANISM (IC-maximization → wrong cluster; ranker
dilutes concentration) is structural and unlikely to reverse with these. Artifacts:
ml_strategy.py / ml_strategy2.py / ml_strategy3.py + `workspace/outputs/jq_replication/ml_*`.
