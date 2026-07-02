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
| **#7 value_红利低波_v2** (nn=19) | **v4** | **+21.45% vs +29.73%** (−8.3pp; REPLAY +26.07% → selection −4.6/execution −3.7 pp/yr) | −25.1 vs −21.0 | in10 0.668 / in20 0.777 / prec 0.585 | guorn_verify_07_divlowvol.py; verify07_result.json / verify07_replay_result.json |

Residual characterization (all diagnosed, diminishing returns):
- #2: 2023/2025 ≈ −34pp each (residual ~9% name mismatch × microcap idiosyncratic returns, net-cancels over 12y).
- #1: 2020/2023/2024 ≈ −20pp (9-term top-20 boundary tie-breaks + proprietary 退市风险 screens) + 2015 +23pp overshoot.
- #6: 2015 −104pp (果仁 +444% TMT extreme year) offset by 2019/2023 overshoots; 2020/21/25/26 within ±4pp.
- #7: gap CONCENTRATED in 2015 −80pp/2017 −36pp/2024 −25pp; 9 of 13 years within ±8pp (2019/20/23/26 local WINS).
  Mechanism (autopsy-pinned, precision-floor class): tight-screen years ride the dy−CGB **2% strict threshold at
  ±10-20bp** (miss margins +0.018-0.020 / extra margins +0.020-0.037 — dps vendor + price-convention floor;
  CGB gap-interpolation adopted, denominator=open(d) tested NOT better); zsfz 银行簇 L2 vintage (农行 rk5/5,
  果仁 2014 taxonomy "其他银行" unreconstructible — Shenwan restated history); beta a non-issue (held-pass
  98.6%; incl-suspended base tested and refuted); 2 proprietary screens omitted (未来20日新增流通股, 退市风险
  non-price legs). Execution −3.7pp/yr = uniform −0.09pp/period (fill-time/果仁-fill-optimism class; NOT
  dividends — engine credits PRE-tax cash_div_tax; NOT cost — 0.2%/side is the LOW platform option) + 2015
  crash / 2024-9·24 limit-lock episodes. This book is intrinsically less reproducible than the 成长簇 (its
  2014-17 selection = whoever crosses a razor-thin macro threshold; 1-4-name periods amplify any flip).

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
| 8 | **sumq(分红总金额,4,k) window** | calendar quarters (q0 = last quarter-end < signal) | **the stock's REPORTED-quarter grid** (q0 = latest disclosed quarter via the cum==sq Q1-identity detector) | 建行@2014-01-08: DivGrPY% 0.133192 = xlsx 0.1332 EXACT (calendar gives −1) | dividend-family sumq factors through-time correct |
| 9 | **annual(x,k) FY anchor** | calendar year−1 | **the stock's latest VISIBLE annual report** (annual slot = (k_Q1+1)%4) | 近三年分红之和 1.79183e11 = xlsx exact; Div%NetIncY2 0.347523 vs 0.3475 | 近三年分红之和/Div%NetIncY2 penny |
| 10 | **组内 排名%最小X% boundary** | rank-pct ≤ X (odd small groups lose a slot) | **rank_asc ≤ ceil(X·N)** | held pcts cluster at 2/3, 4/7, 6/11 = exactly ceil points; zsfz held-pass 84.4%→87.7% | #7 in10 0.632→0.663 |
| — | ILLIQ 2dp quantization (v2) | — | **NEGATIVE result — do not apply**: 果仁's internal tie-break order unobservable; full precision tracks holdings marginally better | in25 0.733→0.727 | factor-standalone fidelity ≠ book fidelity |

## In progress

(none — #7 CLOSED 2026-07-02, moved to the Replicated table; next book = queue #1.)

### #7 build/iteration audit trail (CLOSED 2026-07-02, final v4: LOCAL +21.45% / REPLAY +26.07% vs 果仁 +29.73%)

Harness: `guorn_verify_07_divlowvol.py` (stages: build-base/fin/beta/div/neut/l2/idx → schedule →
factor-parity → run(Model-I) → compare → diag). Cache `verify07_cache/` (591 pdays on the xlsx's own
606-period grid). Div kernels bit-asserted vs `guorn_dividend_caliber` (`--selftest-div` 3 dates OK).

Per-factor value agreement vs the xlsx's own 持仓详单 columns (held names, n≈4200, 564 periods):
| factor | medRel | sign | Spearman | verdict |
|---|---|---|---|---|
| 近三年分红之和 | 0.0000 | 1.000 | 0.996 | ✅ exact (FY-anchor machinery) |
| DivGrPY% | 0.0000 | 0.978 | 0.953 | ✅ penny (after reported-grid fix ↓) |
| Div%NetIncY2 | 0.0001 | 1.000 | 0.941 | ✅ penny (TOTAL n_income, annual slots) |
| 真实负债资产率 | 0.0001 | 1.000 | 0.999 | ✅ penny |
| CoreProfitQGr%PY | 0.0001 | 0.987 | 0.977 | ✅ penny |
| 股息率TTM | 0.0057 | 1.000 | 0.948 | ✅ (ann-date declared caliber) |
| 历史贝塔 | 0.0126 | 0.999 | 0.996 | ✅ 250d slope vs 000300 simple returns |
| BP筹资市值比调整 | 0.0192 | 0.994 | 0.976 | ✅ structure (pctrank-OLS-resid, 范围0, all-A) |
| 250日涨幅 | 0.0825 | 0.971 | 0.994 | ◑ known window-membership residual |
| SharesAvgGr%PY | 0.0000 | 0.889 | 0.762 | ✅ values exact-0 dominate; sign noise on ε |
| ROETTMDiffPQ | — | 0.49* | 0.895 | ◑ *sign stat is an xlsx-2dp-rounding artifact |
| 中性N日换手率(50) | ~1.0 | 0.81 | 0.826 (v2) | ✗ weakest term — v2(全A回归)>v1(L1内)>v3(行业比值); w=1, deferred |

Two NEW registry-grade caliber pins (2026-07-02):
- **`sumq(分红总金额,4,k)` windows anchor on the stock's REPORTED-quarter grid** (latest disclosed quarter
  = q0 via the cum==sq Q1-identity detector), NOT calendar quarters — 建行@2014-01-08 window
  {2013Q3..2012Q4}/{2012Q3..2011Q4} → DivGrPY% 0.133192 = xlsx 0.1332 exact (calendar window gives −1).
- **`annual(分红,k)`/`Annual(净利润,k)` FY anchor = the stock's latest VISIBLE annual report** (最近年报,
  per-stock; annual slot = (k_Q1+1)%4) — 建行@2014-01-08 → FY2012; 近三年分红之和 = 1.79183e11 = xlsx exact.
- ⚠ `$sw2021_l1` is NOT a provider bin (all-NaN read — SECOND recurrence of the verify01 industry_allnan
  bug); industry grouping must come from `industry_sw2021_members.parquet` / provider_metadata (spawned
  cleanup task task_39650a17).

Iteration ladder (one change per round, measured):
- v1 baseline (neutturn_v1): in10 0.632 / in20 0.736 / precision 0.579; count agreement perfect in the
  loose regime (果仁 n=10: 358/374) but scatters in TIGHT years (2015/16/20).
- v2 (+within-L2 ceil boundary): **排名%最小X% in-group cutoff = rank_asc ≤ ceil(X·N)** (held pcts cluster
  at 2/3, 4/7, 6/11 = exactly the odd-group ceil points) → in10 0.663 / in20 0.778; zsfz screen-miss
  691→543. Remaining zsfz misses are **48% 银行** — 果仁's L2 vintage differs (xlsx says 建行=「其他银行」;
  the SW members parquet has NO such L2 — Shenwan RESTATED history, 建行=国有大型银行Ⅱ since 2007) +
  ultra-tight bank leverage cluster (0.5pp spread) → vendor-vintage IRREDUCIBLE class. L1-grouping tested
  WORSE (0.844) — 果仁 really groups at L2.
- v3 (+neutturn v2): 中性N日换手率(50) best variant = **all-A logMV OLS residual of MA50 float-share
  turnover_rate** (per-date Spearman 0.788/median 0.855 vs xlsx; beats L1-grouped v1 0.588 AND the
  官方累计换手率-doc total-share variants v4/v5 0.60-0.61) → in10 0.668 / in20 0.777 / precision 0.585.
Residual structure at plateau: rank-miss 773 (extras displace held names mechanically — precision 0.585),
zsfz 543 (bank vintage), extras near-boundary dy−CGB 244 / beta_nan 63 + the 2 omitted proprietary screens.
Checked extras are NOT data errors (泸州老窖 2014-01 dyttm 9.87% is REAL — dps 1.8 declared 2013-04, post-crash).
**Model-I engine run v1 + REPLAY decomposition (2026-07-02):**
| leg | CAGR | MDD | meaning |
|---|---|---|---|
| 果仁 | +29.73% | −21.0 | benchmark |
| REPLAY (果仁持仓+果仁本期起始仓位权重 → engine) | **+26.07%** | −22.9 | execution/platform residual = −3.7pp/yr |
| LOCAL (my schedule, sqrt市值 weights) | **+21.34%** | −25.1 | + selection residual = −4.7pp/yr |

Execution residual (replay vs 果仁, per-period join vs 调仓详情 本期收益, 591 periods):
- uniform drift −0.09pp/period (≈−4.5pp/yr), all years −2..−5pp — fill-time (open vs 10:00) + 果仁
  fill-optimism class; NOT dividends (engine credits cash_div_tax = PRE-tax — the generous side; its
  "post-tax" comment is mislabeled), NOT cost (my 0.2%/side = the LOW platform option; 果仁's ≥ mine).
- EVENT episodes: 2015 crash/single-name periods (±20%/period — 停牌/涨停 lock the engine out of 果仁's
  trades, both directions; rung-1-documented 果仁 bull-fill optimism) and 2024-09-24..10-15 (−13pp over
  3 periods — the 9·24 rally limit-locks). These two years: replay −24.8pp/−13.8pp vs 果仁.
Selection residual (local vs replay) is CONCENTRATED: 2015 −55.6pp, 2017 −28.4pp, 2024 −11.2pp,
2025 −7.5pp; all other years local≈replay within ~3pp. ⇒ Next lever = tight-year (1-4-name periods)
screen calibration: 空仓期 overlap 15/27, extras displacing 果仁's runners when elig is tiny, zsfz 银行簇.
Harness flags: --run / --replay / --replay-diag; artifacts verify07_result.json / verify07_replay_result.json /
verify07_replay_perperiod.parquet.
NEXT AGENDA: (1) 2015/2017 period-by-period selection autopsy (which of 果仁's 1-4 runners did my screens
kill, per-screen); (2) empty-period mismatch (12 periods I hold when 果仁 sits in bonds); (3) optional
neutturn refinement (per-date sp 0.788 ceiling); (4) M4 cache fix (task_5a0289dc) + $sw2021_l1 cleanup
(task_39650a17).

Original build notes (2026-07-02 morning):
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

## In progress: #8 value_红利低波_央企_v1 (nn=20) — DAY 1 (2026-07-02)

Harness `guorn_verify_08_divlowvol_soe.py` (imports #7 kernels). v2 state:
- **Universe**: 央企 mask = `stock_basic.act_ent_type=='中央国企'` (510; field was ALREADY fetched locally —
  data_dictionary lagged the fetcher) ∪ 142 ever-held (15 exceptions: Tushare marks 交行/新华 '无',
  实控人变更史, 2 创业板 → confirms 板块=全部). 465 insts.
- **Pool macro gates** (SMED/SAVG of STRG_价值红利100): recovered from the xlsx's own formula truth columns
  (per-date dispersion 7.6e-18 = pool-level constants ✓). ⚠ GEOMETRY: anchors exist ONLY on gate-PASS days
  → an interpolated series can NEVER reconstruct a FAIL → gate state INHERITED verbatim from 调仓详情
  股票只数==0 (documented circularity confined to the macro-TIMING layer; stock selection independent).
  Empty-period overlap 137/137/137 exact.
- **Factor panel** (n≈16k): dyttm 0.45%/sp 0.991 · divgr/CoreProfitQGr/div3y penny · bpfin 1.65%/0.973 ·
  expdy 2.0%/0.922 (**after the ×1e4 fix — $report_rc__np_fy1 is 万元**, doc-941; pre-2022-05 rows are
  ifnull→TTM-NI fallback, consensus vendor-approx) · volneut sp 0.870 (neutturn250-v2 / rolling std) ·
  sharesgr exact-0-dominated · ROETTMDiff 2dp-rounding artifact (sp 0.911).
- Tracking: in5 0.566 / in10 0.707 / precision 0.557 (RANK-dominated book: elig med 361, top-5 holds;
  weak years 2014-15 0.37, 2016/2018/2020 ~0.5).
- **Model-II run v1: LOCAL +26.03% / MDD −43.9%** vs 果仁 +32.07% / −21.7.
- **REPLAY (果仁持仓 + RAW 本期起始仓位): CAGR +34.47% / MDD −21.64% vs 果仁 +32.07% / −21.68 — MDD
  exact to 4bp; 8 of 13 years within ±1.4pp** (2014 −0.1, 2016 +1.4, 2017 −0.6, 2018 +0.5, 2023 +0.3,
  2026 −0.3; largest: 2024 +7.3 / 2022 −5.0 / 2015 +4.0). **The strongest execution-path validation of
  the parity program to date** — engine + data (prices/dividends/corporate-actions/suspensions) reproduce
  果仁's equity curve on a DAILY 12y book. ⚠ METHOD LESSON (burned once): **Model-II 本期起始仓位 must NOT
  be normalized** — when few names qualify the book holds partial exposure + CASH (#8 n=1 periods carry
  Σw≈0.19); normalizing to 100% quintupled crash exposure (replay v1 MDD −49.9%, 2016 −32pp artifact).
  The ±1-day paired diffs in per-period joins = 果仁 fill-to-fill accounting boundary (reporting noise,
  cancels annually). ⇒ #8's remaining gap is PURELY the selection layer: LOCAL vs REPLAY = −8.4pp/yr
  (in5 0.566; weakest 2014-15 ~0.37). Next: 2014 selection autopsy (military-SOE rally year).

## Queue (next books, by coverage × caliber reuse)
2. #3 sm_大制造GARP_v3 / #4 GARP_illiq / #15 双创GARP — GARP family, shares CoreProfit/EBITDA composites.
3. #10 AH_GARP — blocked on hk_daily ingest (AH溢价率 w4/21). #19/#20 MultiA — needs fund/ETF data.
