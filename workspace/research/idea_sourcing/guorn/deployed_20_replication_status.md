# Deployed-20 book replication status (策略级台账)

> Book-level replication ledger for the 20 deployed 果仁 books. Per-factor parity lives in
> [guorn_web_validation_campaign.md](guorn_web_validation_campaign.md); calibers/semantics in
> [guorn_local_field_mapping.md](guorn_local_field_mapping.md) (§ platform semantics). NON-FORMAL parity work.
> Method (validated on the 成长簇): replay 果仁 holdings through the engine (splits selection vs execution) →
> miss-diagnosis vs 持仓详单 (screen-miss vs rank-miss) → held-name percentile distributions (pin screen
> semantics) → per-factor value agreement vs the xlsx's own factor columns. One change per iteration,
> keep only measured improvements.

## Replicated (成长簇, 2026-07-02)

| book | final | CAGR (local vs 果仁) | MDD | in25 tracking | harness / artifacts |
|---|---|---|---|---|---|
| **#2 sm_01_成长_v1** (nn=5) | **v4** | **+58.59% vs +58.20%** ✅ | −50.4 vs −50.0 | 0.733→**0.906** | guorn_verify_02b_calibers.py (--schedule-v4/--run-v4); verify02_result.json |
| **#1 sm_01_成长动量** (nn=1) | **v5** | **+54.73% vs +57.21%** (−2.5pp) | −51.0 vs −47.9 | 0.639→**0.888** | _verify_v3_propagate.py --book 1 --variant v5; verify01_result.json |
| **#6 成长高贝塔@TMT** (nn=6) | **v3** | **+57.78% vs +60.32%** (−2.5pp) | −50.6 vs −51.9 | — | _verify_v3_propagate.py --book 6; verify06_result.json |
| #18 ST_大市值_v3 | done 2026-06 | validated earlier (yearly + holdings overlap) | — | — | guorn_verify_18_stbigcap.py |

Residual characterization (all diagnosed, diminishing returns):
- #2: 2023/2025 ≈ −34pp each (residual ~9% name mismatch × microcap idiosyncratic returns, net-cancels over 12y).
- #1: 2020/2023/2024 ≈ −20pp (9-term top-20 boundary tie-breaks + proprietary 退市风险 screens) + 2015 +23pp overshoot.
- #6: 2015 −104pp (果仁 +444% TMT extreme year) offset by 2019/2023 overshoots; 2020/21/25/26 within ±4pp.

## Fixed-factor registry (what was wrong → the validated fix)

| # | construction element | wrong version | validated fix | evidence | effect |
|---|---|---|---|---|---|
| 1 | **排名%区间 X%-100% screens** (真实负债资产率, 乖离率60/120) | dropped the BOTTOM decile | **drop the TOP (100−X)%** — 果仁 ranks 从大到小 | held names sit in my bottom decile 11-16%, top decile 0-5% (p99≈0.86-0.92) | #2 in25 0.733→0.893; 2018 −30pp→−3.8pp |
| 2 | **筛选 上市天数>N** | 20 local bars | **calendar days** (verified 上市天数 caliber) | 359 次新 misses in 2015 alone | part of fix-1's jump |
| 3 | **真实负债资产率** screen factor | plain 负债/资产 | 负债/(资产−商誉−无形−开发支出), NaN→0 | campaign penny+top-K 100% | boundary shift 52 names/day |
| 4 | **ROETTMDiffPQ** | period-END equity legs | **加权平均净资产** time-weighted proxy (0.5·q4+q3+q2+q1+0.5·q0)/4 | end-eq version vs 果仁 xlsx: sign 57-65% | #2 in25 0.893→0.906 |
| 5 | **onmom (SUM window funcs)** | min_periods 120/60 (NaN for 次新) | **min_periods=1** — 果仁 SUM sums available bars | value agreement 2-13% (after log10 descale) all eras | #1 2015 −56pp→−5pp |
| 6 | **forecast/预告 event terms** | infinite ffill | **alive window [event ann, report pub)** — dies when the real report lands | monthly coverage: Feb-Mar 81% → May-Jun 15% → Jul-Aug 42% → Sep 17%; coverage agreement 44%→91.5% | #1 CAGR +51.5→+54.7; 2025 −34.6pp→−1.3pp |
| 7 | 果仁 **LOG() = log10** (ours ln) | — | descale ÷ln(10)=2.3026 for VALUE comparisons (rank-invariant) | constant 130% rel err, sign 97% | diagnosis tool, no selection effect |
| — | ILLIQ 2dp quantization (v2) | — | **NEGATIVE result — do not apply**: 果仁's internal tie-break order unobservable; full precision tracks holdings marginally better | in25 0.733→0.727 | factor-standalone fidelity ≠ book fidelity |

## In progress

**#7 value_红利低波_v2 (nn=19, xlsx 19) — STARTED 2026-07-02.** Recipe read; key facts for the build:
- 投资域: **主板 ONLY** (no 创业板 — differs from 成长簇), 申万**2021**, 排除ST/科创.
- 9 screens incl 3 NEW semantics: `排名%最小 X%` (keep the smallest X% — a DIFFERENT operator from 排名%区间),
  one **二级行业内** grouped screen (真实负债资产率, needs $sw2021_l2), and 公式(股息率TTM−10年国债收益率)>0.02.
- **The treasury screen is UNBLOCKED without any ingest**: yc_cb is permission-denied (separate-tier endpoint), but
  the xlsx 持仓详单 carries BOTH 股息率TTM and the formula column → 果仁's own 10Y yield series RECOVERED by
  subtraction (per-date cross-stock dispersion ≤7e-05 — one macro number/date; 578 dates 2014-2026, yearly means
  = the real CGB history 4.15%→1.74%). Saved: workspace/outputs/guorn_parity/guorn_cgb10y_recovered.parquet.
- rankings (8, w=11): 股息率TTM w3 (ann-date declared caliber ✅) · CoreProfitQGr%PY w2 ✅ · 总市值 w1 **从大到小**
  (large-cap!) · ROETTMDiffPQ w1 (use v2 weighted-eq) · 中性N日换手率(50) w1 (industry-neutralized turnover — new)
  · BP筹资市值比调整 w1 (cross-sectional composite) · Div%NetIncY2 w1 ✅ · 近三年分红之和 w1 (annual atoms ✅).
- trade model: **Model I** (NOT II): 5-day rebalance, 10:00 fill, max 10 holds, weights = **sqrt(总市值)**.
- The xlsx carries ground-truth values for ALL ranking factors → per-factor validation from day one.
- Build TODOs: dividend-family DAILY frames (vectorize declared_dividend_* over ~590 rebalance dates), beta frame
  (rolling 250d vs 000300), $sw2021_l2 fetch, 中性换手率 + BP筹资 composites, Model-I runner. 未来20日新增流通股
  omitted (share_float not ingested — same documented omission as the 成长簇).

## Queue (next books, by coverage × caliber reuse)

1. **#7 value_红利低波_v2 / #8 央企** — reuse the campaign-validated declared-dividend calibers (股息率TTM ann-date,
   连续N年分红 98.9% decode, DivGrPY% report-period); watch 近三年分红之和 = annual atoms (bit-verified).
2. #3 sm_大制造GARP_v3 / #4 GARP_illiq / #15 双创GARP — GARP family, shares CoreProfit/EBITDA composites.
3. #10 AH_GARP — blocked on hk_daily ingest (AH溢价率 w4/21). #19/#20 MultiA — needs fund/ETF data.
