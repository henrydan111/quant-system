# FINDINGS — JQ-derived modules toward 50% CAGR / <40% MDD (clean PIT)

Date: 2026-06-08. Autonomous /goal. Source idea bank: the JoinQuant clone-strategy
audit (`聚宽克隆策略/克隆策略优缺点与因子库.md`). Splits/tooling per [PLAN.md](PLAN.md).

## Verdict (data-backed, no hedge)

**50% CAGR with <40% MDD is NOT achievable on clean, PIT-safe, realistic-cost
A-share LONG-ONLY data — with any JoinQuant-derived module, alone or combined.**
The best honest IS (2014-2020) construction reaches **~13% CAGR at <40% MDD**, and
that one is the prior effort's value+low-vol + trend-overlay which is **already
known to FAIL out-of-sample**. This confirms and extends the prior `long_only_50cagr`
finding (≈16% ceiling) across the genuinely-new JQ levers, and empirically confirms
the JQ audit's own thesis: the "X倍/无惧牛熊" claims rest on microcap beta +
zero-slippage + handpicked pools + multiple-comparison — none survive clean testing.

## What was tested (all IS 2014-01→2020-12, monthly, realistic costs 5/15 bps, survivorship-safe)

| Module | Idea (JQ source) | Best result | Conclusion |
|---|---|---|---|
| **M0 C/P value** | `val_cftp`=OCF/P concentrated value (大市值价值/价值低波) | ungated C/P k10 +8.5%/−37% | weaker than value composite; no edge |
| **M0 authenticity gate** | pb<1 + OCF>0 + ROA>θ + npy>0, "选不出票即空仓" | **−60% to −83% MDD** (all variants) | **HARMFUL** — pb<1 picks distressed value-traps; natural-timing does NOT rescue |
| **M1 C/P ∩ low-vol** | orthogonal value∩low-vol intersection | k20 +11.3%/−44%/Shrp 0.57 | decent Sharpe, MDD>40%, <prior value |
| **M2 slope×R² momentum** | 加权对数回归动量×R² (T-1, PIT-safe) | rankICIR **−0.17 to −0.36** | **reversal** — ×R² does NOT flip sign; long-high top-K −17% to −47% CAGR / −89% to −99% MDD (falling knives) |
| **M3 regime rotation** | 大小盘轮动: small↔large↔cash on index-MA | best +3.1%/−61% | **FAILS** — MA filter dodges 2018 but whipsaws away rebounds (turned smallQV's +23% 2019 into −7%/−23%) |
| **M3b relative-strength** | rotate to relatively-stronger style (000852/000300) | best +4.9%/−66% | **FAILS** — worse than standalone largeVL |
| **M3b broad de-risk** | largeVL + 000300<MA→cash | **+13.3%/−36.7%/Shrp 0.84** | best IS, but = prior overlay **already OOS-REJECTED** (whipsaws OOS) |
| **M6 microcap (the engine)** | true bottom-decile 微盘 (the actual source of the JQ 50%+ claims) | **+26.9% CAGR / −53.2% MDD** (optimistic 5/15bps) | highest CAGR in the study, but **fails BOTH** targets; nothing fixes the MDD |

Sanity anchor: prior `value@core k20` reproduced at +13.4%/−41.7% (prior reported ~+13%/−44%).

### M6 detail — why microcap settles the question (measured, not asserted)

Pure bottom-decile microcap, IS 2014-2020, at OPTIMISTIC 5/15bps costs (real microcap
slippage is 0.5-2%, so CAGR is overstated / MDD understated): **+26.9% CAGR / −53.2% MDD /
Sharpe 0.99** (yearly: 2014 +68.7%, **2015 +170.6%**, 2016 +16.7%, 2017 −25.2%, 2018 −16.8%,
2019 +40.9%, 2020 +7.7%). Quality-screen → +13.1%/−57.3% (kills the junk-rally beta).
Liquidity-floor (tradeable) → +18.8%/−51.5%. **Regime-gating (MA200) → +16.5%/−50.8%** — the
trend filter does NOT cut the microcap MDD (the 2015 crash is faster than any MA cross) and
slashes CAGR. **Structural impossibility, proven by measurement:** the only lever that reaches
high CAGR (microcap) inherently carries >50% MDD; every MDD-reduction technique (quality
screen, liquidity floor, regime gate, trend overlay) *reduces* CAGR. There is no point in the
clean-PIT long-only space at 50% CAGR AND <40% MDD. Closing 27%→50% needs precisely the
audit-named biases: sub-bps slippage, limit-up gaming, handpicked survivor pools, even-smaller
untradeable names. The two goal requirements are jointly infeasible here.

## Why 50% is structurally out of reach (clean, long-only, this data)

1. **The factor premium is small and one-year-dominated.** Every value/quality book's
   entire IS CAGR comes from 2014 (+55% to +80%); 2015-2020 is roughly flat-to-negative.
   A no-2014-equivalent window (e.g. OOS) collapses to single digits. (JQ audit §四.6:
   "one good year = high risk.")
2. **A-share short-horizon momentum is reversal** (negative rankICIR), so long-only
   momentum/trend chasing = falling knives. The ×R² smoothness gate does not change this.
3. **PIT-safe regime timing whipsaws.** MA trend filters on choppy indices give back
   rebounds faster than they dodge bears → net-negative. (Same failure the prior overlay
   hit OOS.)
4. **The only paths to 50% are biased/unavailable:** microcap beta (untradeable + 2024
   crash; prior found it hurts even regime-gated), zero slippage (we charged real costs),
   handpicked ETF/stock pools (pure lookahead), leverage (no clean retail instrument; would
   breach MDD anyway), long-short / market-neutral (no shorting / index-futures data — parked).

## Untestable JQ families (no data) — documented, not dismissed

ETF-momentum rotation (五福/四季/七星), foreign/gold/Nasdaq defensive legs, and any
sector-ETF rotation are **untestable on this backend (stock-only, no ETF/fund/foreign data)**.
Their reported returns also depend on the audit-flagged 盘中 `last_price` soft-lookahead +
handpicked pools, so they would not transfer to clean daily-decision execution regardless.

## Best honestly-deployable strategy (the realistic answer)

The prior effort's **RAW value + low-vol, top-40, monthly, long-only, no overlay** remains
the deployable book: sealed-OOS (2021-26) **+11.6% total return (event-driven, dividends
credited) / −14.5% MDD / Sharpe 0.80**, beating CSI300/500/1000 (which fell −42% to −47%).
This effort confirms **no JoinQuant-derived module beats it** on clean PIT. Realistic
expectation: low-to-mid teens CAGR in normal/bull regimes, single digits in bears, MDD <20%.

## Research-integrity notes

- No new OOS was spent: the only IS-attractive construction (broad de-risk overlay) is the
  prior effort's design whose OOS is already spent (and failed). Regime rotation FAILED on IS,
  so there was nothing to confirm OOS. Spending the contaminated 2021-26 window on a failed-IS
  design would be both pointless and an anti-overfit violation.
- Small economically-motivated parameter grids only (MA∈{60,120,200}; k∈{5,10,20,40}); no
  config dredging for an IS-lucky regime setting (the "数百次回测挑最好" trap).
- All factor access via the sanctioned PIT-safe `compute_factors` door; slope×R² built with
  `Ref(...,1)` (ADJ_CLOSE_T1). Regime signals use `shift=1` index closes (causal).

Artifacts: `workspace/outputs/jq_regime_50cagr/{m0_m1,m2,m3,m3b}_results.json`,
`m3_base_books.parquet`, `mom_slope_r2_is.parquet`. Scripts: `m0_m1_value_books.py`,
`m2_momentum.py`, `m3_regime.py`, `m3b_rotation_variants.py`, `jq_utils.py`.
