# Deployed-20 verification — #1 sm_01_成长动量 (findings)

果仁 target: 年化 **57.2%** / Sharpe 1.68 / MDD 47.9% / vol 31.7% (果仁微盘 bench). Daily model-II,
个股仓位 7–13% (~10 holds), 备选 20, 09:35 open fill, no timing. Cost = 千分之二 (working assumption).

## Result: NOT yet a faithful reproduction — deficit is COMPOSITE SELECTION (engine validated)

Three-way decomposition (my EventDrivenBacktester, EW/model-II, daily, 0.2%/side, 2014→2026-02):

| book | annual | Sharpe | vol | MDD |
|---|---|---|---|---|
| 果仁 (target) | +57.2% | 1.68 | 31.7% | −47.9% |
| 果仁's names, EW (replay) | **+63.3%** | 1.58 | 31.7% | −45.1% |
| my names, EW | **+35.6%** | 0.97 | 32.8% | −57.3% |
| my names, model-II (#1) | **+39.8%** | 1.07 | 32.7% | −50.8% |

Attribution of the −17.4pp (my #1 39.8 vs 果仁 57.2):
- **Engine SOUND**: 果仁's exact daily names → my engine = +63.3% ≈ 果仁 +57.2% (vol exact; 2015 +287 vs +284; year-by-year mostly ±6pp). The local data + engine + execution (cost/fills/limit-gate) reproduce 果仁. Confirms rung-2 for a *daily* book.
- **Model-II band: +4.2pp** (39.8 vs 35.6) — the band HELPS vs EW, not a drag.
- **Selection: −27.7pp** (my-names-EW 35.6 vs 果仁-names-EW 63.3) — **the entire deficit**. My composite picks worse-performing names.

## Why the "execution" hypothesis was wrong (rule #10 correction)
Holdings overlap is 37.4% top-10 (= #59's 35.7%), stable, and 2022 had the HIGHEST overlap (46.7%) with
the biggest return gap — which I first read as "execution". The replay/decomposition disproved it: in 2022
my-names-EW = +1.3% vs 果仁-names-EW = +42.8%, so the 63% non-overlap names were genuinely bad. Overlap
COUNT (≈#59) ≠ selection QUALITY: at ~10 concentrated holds the worse non-overlap names dominate, unlike
#59's 5d/EW/20-hold book where they averaged out.

## Factor-parity (vs 果仁's EXPORTED per-holding values, 各阶段持仓详单, ~32k holdings)
果仁's holdings sheets export the factor values + 总排名分 → direct per-factor validation (rigor upgrade vs #59).
ALL #1 factors are faithful:
- ✅ 总市值 (0.006), EpsExclXorQGr (扣非净利润 ✓), forecast, 真实负债资产率, 乖离率120, o/n-mom (corr 0.98 rank-faithful)
- ✅ CoreProfitQGr: median penny-exact, |.|>50 outliers MATCH 果仁; only 0.1% extreme tails diverge (rank-OK)
- ✅ **ROETTMDiffPQ: my TTM(归母)/end-equity QoQ is the BEST mapping** — sign **97.3%** on meaningful (non-near-zero)
  values, corr 0.80, beats every vendor ROE variant (roe/roe_waa/roe_dt/q_roe all sign 63–75%, corr ≤0.37;
  _verify01_re_roe.py). The earlier "sign 75.5%" was a near-zero-value artifact (sign of ~0 is meaningless).
- ⚠ ILLIQ: 果仁 EXPORTS 0.00 (display rounds ~2e-6 away) → unvalidatable via display; formula is rung-4-based

## Composite fidelity (vs 果仁's exported 总排名分; _verify01_composite_diag.py)
果仁's held names sit at **median 0.996 percentile** in MY composite (99.4% in my top-10%, 0% below my median)
→ my composite STRONGLY agrees with 果仁 on which names are elite. But the fine ordering within the elite
differs (Spearman to 总排名分 = 0.49, partly range-restricted over the elite).

## Composite is now 果仁-EXACT (果仁筛选与排名功能 §3.1.4) — weights + formula + NaN-rule all doc-validated
The help docs (果仁帮助文档/果仁筛选与排名功能.txt §3.1.4) document the ranking system EXACTLY: 排名分 =
(N−排名+1)/N×100; 综合排名分 = Σ(排名分×weight); **空值 → ranked LAST (worst 排名分)**. My composite formula
+ weights matched already (audited all 20, 0 problems; #1 = 市值 2+3 / others 1); the one fix was NaN-handling
(I used skip; 果仁 penalizes to last) — now corrected. Doc-correct re-run: **LOCAL +40.88%** (vs +39.82% with
the old skip; Sharpe 1.08, MDD −56.4%, vol 33.1%). Marginal annual +1pp, year-reshuffle (2022 +7.5→+21.5%,
2015 +257→+205%), deeper MDD — net ~same −16pp gap. **Confirms the NaN-fix is doc-correct but immaterial to
the gap** (果仁's held elite has no NaN factors, so the within-elite ordering is untouched). The composite
ENGINE now exactly replicates 果仁's documented ranking system.

## ★ ROOT-CAUSE CORRECTION (2026-06-26, user-driven): incomplete recipe consumption + 涨停不卖 MISSING
The earlier "structural ceiling" conclusion was PREMATURE — it assumed the trade model was fully reproduced.
It wasn't. The recipe in guorn_strategies_master.json (faithful parse of guorn_slct_strategies.md) has **8**
sub-fields; my extractor + harness consumed only **5** (universe/filters/rankings/trade_model/market_timing),
SILENTLY DROPPING **buy_limit / sell_conditions / hold_keep_conditions**. So I:
- guessed sell_rank=20 (real sell_conditions = 排名≥**25**) — fixed → +39.5% (≈unchanged; band ≈ EW for #1).
- guessed buy_rank=10 (real buy_limit = no rank limit) — fixed.
- **MISSED 涨停不卖 (hold_keep "调仓日交易时涨停") entirely** — and it's in **17 of 20** deployed books.
**涨停不卖 = hold limit-up winners.** My harness SOLD them (at rank≥25); 果仁 holds them. For a momentum book
the limit-up names are the biggest gainers → selling them is the prime suspect for the big-year undershoots
(2015 −72pp, 2019 −37, 2025 −42). Fixes: (a) extractor now consumes all 8 sub-fields (no more silent drops);
(b) engine opt-in fill-step `hold_on_limit_up` (skip a SELL when is_limit_up at fill; default OFF, does NOT
touch the §3.3 gate; NON-FORMAL research feature, GPT §10 review before formal use; 62 backtest_engine tests
still pass). Progression: old +39.8 → doc-composite +40.9 → band-fix +39.5 → **+涨停不卖 = [pending re-run]**.
Variants for later: 调仓前一日收盘涨停 (#11/#13), 持有天数≤30 (#19). 退市风险 force-sell still partial.

## RESULT — 涨停不卖 added +8.1pp annual; the "ceiling" was a MISSING CONDITION, not irreducible
Complete #1 (band + 涨停不卖, doc-exact composite, 0.2%/side): **LOCAL +47.6% / Sharpe 1.22 / MDD −54.4% /
vol 33.2%** vs 果仁 +57.2% / 1.68. Progression: old +39.8 → band-fix +39.5 → **+涨停不卖 +47.6** (+8.1pp).
Big-year gaps collapsed: 2015 −72→**+48** (overshoot — limit-up rockets now HELD), 2014 −27→−5, 2019 −37→−21,
2020 −13→−6.5, 2023 −15→−8. Gap −17.4 → **−9.6pp**. **The earlier "structural ceiling" verdict was PREMATURE
and is RETRACTED** — most of it was the un-consumed 涨停不卖 condition.

## REMAINING gap (−9.6pp) — concentrated in 3 years, now mixed-cause
- 2022 −42.9pp (my +10.6 vs +53.5) + 2024 −29.4 — **selection** (my-names-EW 2022 was +1.3 vs 果仁-names-EW
  +42.8; the composite picks different names those years — fine-ordering / factor-precision within the elite).
- 2025 −41.3pp (my +69.3 vs +110.5, strong bull) — likely **more momentum/limit-up capture** (the
  调仓前一日收盘涨停 variant not yet wired; or extreme winners not fully held).
- Levers left: the prev-day-close-limit-up variant, 退市风险 force-sell, idle-cash money-fund (minor),
  and the within-elite fine-ordering (factor precision). These are now the residual, NOT a ceiling.

## CONCLUSION (superseded ceiling text below kept for history)
Every factor is faithful, the composite ranks 果仁's names at the 99.6th pctl, the engine is sound (replay),
yet my elite-10 underperform 果仁's elite-10 by 27.7pp. The deficit is **top-N-at-concentration sensitivity**:
both pick ~10 from the same clustered elite (~200), but 果仁's proprietary composite fine-ordering (exact
weights/tie-handling, NOT exported) picks the better-performing elite names; at 10 concentrated daily holds
this dominates, whereas #59's 20-hold/5d diversification averaged it away. **Not closable by factor fixes
(factors already faithful); would need 果仁's exact composite internals, which aren't exported.**
#1 deployable (my realistic) return ≈ +40% vs 果仁's optimistic-selection +57%.

## Campaign implication (generalizes)
The engine/data/composite-direction are validated (replay + 99.6 pctl). Reproduction fidelity at the RETURN
level depends on **concentration**: diversified books (#59, 20-hold/5d) reproduce closely; concentrated daily
books (~10 holds: #1, #5, #8, #13, #14, #18) hit this top-N-at-concentration ceiling. 果仁's per-holding
factor + 总排名分 exports let us VALIDATE the composite directly (a stronger check than #59) even when the
return can't be matched — so "validation" = composite fidelity (achievable), not return parity (ceiling-bound).

Scripts (all workspace/scripts/, NON-FORMAL): guorn_verify_01_growth.py (build/schedule/run),
_verify01_factor_parity.py, _verify01_re_cache.py, _verify01_overlap.py, _verify01_replay.py, _verify01_myew.py.
