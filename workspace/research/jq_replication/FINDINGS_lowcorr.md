# Low-correlated-factor strategy, striving for 50% CAGR — FINDINGS

Date: 2026-06-08. Goal: "based on validated insights, research a strategy of low-correlated factors,
strive for 50%+ CAGR." Built on the validated 大市值价值 top10 (+20.7% ED) + the marginal-orthogonal-
contribution insight. Simulator = total-return proxy validated within 0.6-0.8% CAGR of event-driven.

## Bottom line

The low-correlation insight is CORRECT and VALUABLE, but its high-CAGR payoff lives in
MARKET-NEUTRAL space, not long-only. **CAGR ≈ Sharpe × vol** is the binding identity: low correlation
maximizes Sharpe (efficiency), but reaching 50% CAGR still requires ~33-50% vol → ~50% drawdown,
regardless of factor cleverness. 50% CAGR is a risk-tolerance statement, not a factor-selection one.

- **Deployable today (long-only): 大市值价值 top10 = +20.7% CAGR / −26.6% MDD / Sharpe 1.01** (event-driven).
  Multi-sleeve combination raises Sharpe but worsens MDD — not better on a drawdown-constrained mandate.
- **Best low-correlated MARKET-NEUTRAL design (needs shorting+leverage — NOT deployable here):**
  {value_bp, growth, reversal} risk-parity → Sharpe 1.46; 1.9× → +23%/−24%, 3.1× → +40%/−37%,
  4.1× → +50%/−55%.
- **50% CAGR honest verdict: only via leveraged market-neutral at ~−55% MDD** + single-name shorting
  (restricted in A-shares) + ~4× leverage. Not reachable at controlled drawdown.

## Step 1 — long-only sleeves are all correlated ~0.6 (shared beta)

Built 6 long-only-viable sleeves (main-board, ex-ST, monthly, realistic costs). FULL 2014-26:
value_quality(大市值价值) +21.5%/−34%/Sh0.89; value_cp +16.0%/−39%; lowvol +13.7%/−51%;
growth +9.0%/−60%; quality(no value gate) +1.6%/−67%; rev_liquid −6.8%/−90%.
**Sleeve return-correlation matrix: every pair 0.52-0.79.** No genuinely low-correlated viable
long-only sleeves exist — each carries full market beta, so all crash together (2015/2018), and the
"diversifiers" (lowvol/growth) crash HARDER. The signal-level orthogonality does NOT show in
long-only returns.

## Step 2 — multi-sleeve union books: Sharpe up, MDD worse

Union of sleeve top-Ns into one EW book. FULL: VQ10 baseline +21.5%/−34%/Sh0.89/Calmar0.63;
VQ10+LV10 +23.4%/−43.6%/Sh1.14/Calmar0.54; VQ7+LV7 +22.8%/−43.4%/Sh1.05. Adding low-vol lifts
Sharpe (0.89→1.14, real vol-diversification) but WORSENS MDD (−34→−44, the lowvol sleeve's 2015
crash) → lower Calmar. Concentration (VQ3+LV3) blew MDD to −82%. **For a drawdown-constrained
mandate, VQ10 alone stays best.** Long-only low-correlation buys vol-diversification (Sharpe), not
tail-diversification (MDD).

## Step 3 — market-neutral: where low correlation actually pays off

Dollar-neutral long-short legs (top-decile long − bottom-decile short, liquid universe, monthly).
FULL 2014-26: reversal Sh1.15 (best — useless long-only at −6.8%, unlocked by removing beta!),
growth Sh0.71, value_bp Sh0.57, lowvol Sh0.57, value_cp Sh0.43, quality Sh0.19.
**MN return correlations collapse: avg |off-diag| 0.37 (vs ~0.6 long-only); reversal ≈ 0 to all
fundamentals; growth vs value_bp −0.09.** Risk-parity combo of the 5 fundamentals = Sharpe 0.94 /
vol 8.8% / MDD −18.8%. Best low-corr trio {value_bp, growth, reversal} = **Sharpe 1.46** / +12.1% /
vol 8.0% / MDD −13.3% — the diversification of orthogonal MN factors realized.

## Step 4 — the CAGR = Sharpe × vol frontier (why 50% needs ~50% MDD)

Best MN book Sharpe 1.46: +23% at −24% MDD (1.9×, 15% vol); +40% at −37% (3.1×, 25% vol);
**50% CAGR needs 4.1× leverage → 33% vol → ~−55% MDD.** Even at Sharpe 1.5, 50% CAGR ⇒ vol ~34% ⇒
MDD ~−56%. No realistic clean-A-share Sharpe (best single MN factor 1.15; best combo 1.46, and these
are OPTIMISTIC — gross of borrow cost, shorting impact, 融券 availability) reaches 50% CAGR at
acceptable drawdown.

## Caveats / integrity

MN Sharpes are total-return, simulator-proxy, and gross of realistic shorting frictions (borrow,
impact, 融券 list limits) and ~3-4× leverage costs → real MN Sharpe lower (≈1.0-1.2), making 50%
even harder. Reversal MN is high-turnover + capacity-limited. PIT-safe throughout (cached Ref(...,1)
factors). Long-only numbers cross-validated vs event-driven (VQ10 = +20.7% ED).

## Recommendation

1. **Deploy long-only: 大市值价值 top10** (+20.7%/−26.6%/Sh1.01) — the honest deployable ceiling.
2. **The strongest case yet for building the parked MARKET-NEUTRAL leg**: a low-correlated MN book
   (value_bp + growth + reversal) at Sharpe ~1.46 → modest leverage gives +23%/−24% (1.9×) to
   +40%/−37% (3.1×). This needs index-futures/single-name-short instruments + a clean unspent OOS.
3. **Reframe the 50% target around risk:** CAGR = Sharpe × vol. Decide the tolerable MDD first; at the
   best clean Sharpe (~1.0 long-only / ~1.2-1.5 MN), 50% CAGR ⇒ ~50% MDD. Pick the point on the
   frontier you can live with — ~20% long-only at −27% is the deployable sweet spot today.

Artifacts: sleeves.py, combine_sleeves.py, market_neutral.py + `workspace/outputs/jq_replication/
{sleeve_returns,combine_sleeves_results,mn_factor_returns}*`.

## ADDENDUM (market_neutral_v2.py) — striving for 50%: the leverage frontier + the vol-drag ceiling

Pushed both levers hard. **Reframe that unlocks the most:** the high-IC factors that FAIL long-only
(short-reversal, turnover, amihud, momentum) are STRONG market-neutral — so the max-Sharpe low-corr MN
book is built FROM them. IS-selected risk-parity subset {rev(mom20), grow_npy, rev(mom60), turnover,
amihud}: **IS Sharpe 2.33 / OOS 1.39 / FULL 1.82, vol just 7.6%, MDD −9.9%** (OOS<IS = honest
IS-selection degradation; ~1.4-1.8 is the credible Sharpe).

**(A) Leveraged low-corr MARKET-NEUTRAL (needs shorting/futures = parked MN leg), net 6% borrow:**
2×→+23%/−20%MDD, 3×→+31%/−29%, 4×→+38.6%/−37%, ~5×→~50% (~40% vol, ~−48% MDD). 50% is *reachable*
here ONLY because base vol is 7.6% — low vol = leverage headroom.

**(B) Leveraged LONG-ONLY VQ10 via 融资 (deployable, no shorting), net 6% borrow — CANNOT reach 50%:**
1.5×→+27%/−50%, 2×→+30%/−63%, **2.5×→+31%/−74% (CAGR PEAK), 3×→+29%/−84%.** Levered CAGR PEAKS at
~31% then DECLINES — the 26% base vol means vol-drag + borrow cap it; leverage on a high-vol long-only
book is self-defeating. **50% is unreachable long-only at ANY leverage.**

**THE deep result:** the low-correlation insight's real payoff is LOW VOLATILITY (7.6% MN vs 26%
long-only); low vol is what makes leverage viable. So the ONLY honest path that *strives for 50%* is a
**leveraged low-vol low-correlated MARKET-NEUTRAL book** (~Sharpe 1.4-1.8 × ~5× leverage → ~50% at
~−48% MDD), which needs the parked MN leg (single-name shorting / index futures + a clean OOS). On
clean long-only — even with margin — the ceiling is ~31% CAGR (at −74% MDD) / ~20% at sane drawdown.
50% remains a high-leverage, market-neutral, ~−50%-drawdown target. Artifact: market_neutral_v2.py.
