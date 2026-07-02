# 果仁 indicator → local field mapping + parity status (validated ledger)

> **Purpose.** The hard-won layer the raw-formula docs do NOT have: which LOCAL provider field/
> expression reproduces each 果仁 indicator, its **validated** parity status, the **corrections** to
> the auto-generated formula docs, and the reusable **conventions**. Built from the 果仁-parity ladder
> (rungs 1–4, 2026-06-22..23). Machine-readable sidecar: [guorn_local_field_mapping.json](guorn_local_field_mapping.json).
>
> **This file is CANONICAL; the JSON is a derived snapshot — keep them in sync.**
>
> **Canonical for penny/structure-exact mappings (§1).** VENDOR-APPROXIMATE (rank-faithful, RANKING-USE-ONLY)
> mappings — e.g. 评级机构数 → `$report_rc__n_active_orgs` — live in **§1c**; they are NOT penny/threshold-exact.
>
> **Raw 果仁 formulas (do NOT duplicate here):** [indicator_reference_auto.md](indicator_reference_auto.md)
> (99 custom + 14 builtin), [guorn_aichat_indicator_defs.md](guorn_aichat_indicator_defs.md) (builtins:
> ILLIQ / 中性化 / 朝阳永续 / 评级), [内联公式85条拆解.md](内联公式85条拆解.md) (85 inline).
>
> **Scope discipline (rule #10).** Only indicators ACTUALLY validated against 果仁 holdings get a
> `status` + parity. Mappable-but-unvalidated ones are listed separately and explicitly marked. The
> ~75 redundant/irreducible indicators are NOT mapped (see §5). NON-FORMAL parity diagnostics; not a
> formal artifact.

---

> **⚠ Top-K completion gate (2026-06-28, per the guorn-verification skill).** A ✅ below means the per-stock
> VALUE is validated — **necessary but NOT sufficient**. A factor is verification-COMPLETE only with a reported
> 果仁-web **top-5/10/20** selection overlap that clears the bar (净资产收益率: value Spearman 0.991 yet **top-5
> 0%**). Most §1 rows were validated at the HOLDING/value level (rungs 1–6) WITHOUT a standalone 果仁-web top-K →
> they are **value-validated, top-K-PENDING** (re-run through the campaign comparator, which now auto-prints top-K).
> Top-K-COMPLETE today: 总市值 · CoreProfitQGr%PY · 股息率TTM (all 100%); ROETTMDiffPQ / 净资产收益率 are
> top-K-measured but **selection-DIVERGED**. Pure FILTER factors (BP · 市盈率 · 负债资产率) are threshold-tested,
> not top-K-ranked.

## 0. Reusable conventions (apply to EVERY indicator)

| convention | value | evidence |
|---|---|---|
| **Display lag** | 果仁 shows each factor as of the **SIGNAL date = T−1** (the trading day BEFORE the holding 开始日期), NOT the buy date. | 4-way: 总市值 lag1 0.52% vs lag0 0.98%; BP/乖离率/ILLIQ all prefer lag1 |
| **成交额 (亿元)** | `$amount` is in 千元 → 成交额(亿元) = `$amount / 1e5` | ILLIQ unit reconciliation |
| **总市值 unit** | `$total_mv` is in 万元; 果仁 `总市值(亿) × 1e4` = 万元 | 总市值 decomp 0.52% |
| **BP scale** | equity(元) / total_mv(万元) ⇒ ×1e4 to land on 果仁's displayed BP | scale-detect = 10000 |
| **后复权** | `adjc = $close × $adj_factor`. For a price **RATIO** (e.g. 250日涨幅) this is 复权-base-INVARIANT (后复权-present ≡ 前复权-as-of). raw close is wrong. | raw 26% vs adj 5.5% |
| **single-quarter** | `$<field>_sq_q0` = latest single quarter; `_sq_q1.._q4` = prior quarters; **TTM = Σ(_sq_q0.._q3)**, 去年同期 single quarter = `_sq_q4`. Provider-materialized bins, read via `D.features` (factor-library path), NOT raw `pit_ledger` columns. | rung-2/4 |
| **PIT gate timing** | gate the fundamental **as-of the rebalance day (lag-0)** — effective_date-safe because the provider anchors `effective_date > disclosure` STRICTLY (§3.2), matching 果仁's 公告日 selection. | rung-2 GPT R1 (0 flips) |

---

## 1. Validated mapping (penny-exact / structure-exact)

All parity = holding-level value vs 果仁's displayed factor across the 65 books, at the signal-date lag.

| 果仁 indicator | 果仁 formula | local expression | status (parity, n) | rung |
|---|---|---|---|---|
| **总市值** | 总市值 | `$total_mv` (万元) | ✅ display-precision (0.52% med, 97% w/5%, n=97k) | 1,4 |
| **流通市值** | 流通市值 | `$circ_mv` | ✅ (rung-1 portfolio reproduction) | 1 |
| **净利润(单季)** | 净利润(单季) | `$n_income_sq_q0` ÷1e4=万元 | ✅ **penny-exact** (96.1% w/0.1%, med 0.0000, n=14.7k) | 2 |
| **业绩预告净利润QGr%PYQ_v1** | mid=(预告净利min+max)/2; single_q_fc=mid−income_cum[FY,Q−1]; growth vs py_single | `$forecast__np_q_yoy` | ✅ (4.37e-05 med, 92.9% w/1%, 98.2% sign, n=38.4k) | 3 |
| **GrossProfit%AssetsQ** | (营收单季−营业成本单季)/资产总计单季 | `($revenue_sq_q0 − $oper_cost_sq_q0) / $total_assets_q0` | ✅ penny-exact (96.3% w/1%, 99.98% sign, n=262k) | 4 |
| **SalesQGr%PY** | (营收单季[0]−营收单季[4])/abs(营收单季[0]) | `($revenue_sq_q0 − $revenue_sq_q4) / abs($revenue_sq_q0)` | ✅ penny-exact (95.8% w/1%, 99.3% sign, n=124k) | 4 |
| **负债资产率** | 总负债/总资产 | `$total_liab_q0 / $total_assets_q0` | ✅ penny-exact (98.0% w/1%, 100% sign, n=48k) | 4 |
| **OPCFNPDiff%NP** | (经营现金流TTM−净利润TTM)/净利润TTM | `(Σ$n_cashflow_act_sq_q[0..3] − Σ$n_income_sq_q[0..3]) / Σ$n_income_sq_q[0..3]` | ✅ penny-exact (92.0% w/1%, 99.6% sign, n=63k) | 4 |
| **BP** | 归属母公司股东权益合计/总市值 | `$total_hldr_eqy_exc_min_int_q0 / $total_mv` (×1e4, lag T−1) | ✅ 0.66% med (66% w/1%, 96% w/5%, n=97k) — residual = 总市值 2-dec display-round + equity PIT-boundary | 4 |
| **市盈率** | 市盈率TTM | `$pe_ttm` (lag T−1) | ✅ 0.9% med (54% w/1%, 92% w/5%, n=19k) — residual = price signal-day | 4 |
| **ILLIQ(5)** | MA(股价振幅/成交额(亿元), 5) | `MA( ((high−low)/prev_close) / ($amount/1e5), 5 )` (lag T−1, avg-of-ratios) | ◑ structure-exact (12.5% w/0.1%); residual ~0.86× = undocumented platform sub-detail | 4 |
| **股息率TTM** | Σ declared cash div (税前, **ann-date** TTM) / 收盘价 | **bulk:** `$dv_ttm` (lag T−1, ×100); **selection tail:** ann-date declared caliber → [guorn_dividend_caliber.py](../../../scripts/guorn_dividend_caliber.py) `dividend_yield_ttm()` | ✅ bulk 0.70% med (n=51k). ⚠ **caliber split (2026-06-28):** `$dv_ttm`=ex-date REALIZED diverges at the high-yield TAIL (the selection zone — top-5 **60%**) because 果仁=ann-date **DECLARED**: it counts announced-not-yet-ex divs (600329 2.450 ann 2025-10-31/ex 2026-02-12) and drops ex'd-but-old-announcement divs (603167 0.220). Ann-date caliber → top-5 **100%**, med 0.52% isolated | 5 |
| **净资产收益率** (RoeTTM) | **TTM归母净利 / 加权平均净资产** (CSRC-standard ROE; TTM, NOT reported-YTD) | `(Σ$n_income_attr_p_sq_q[0..3]) / 加权平均净资产` ; best quarterly proxy = TTM归母 / time-weighted eq `(0.5·$total_hldr_eqy_exc_min_int_q4+_q3+_q2+_q1+0.5·_q0)/4` (lag 0) | ✅ **definition PINNED (2026-06-28 level+implied-equity reverse-engineer):** numerator=**归母 TTM**, denominator=**加权平均净资产** (implied-eq solves to the TTM-AVERAGE, NOT period-end). Positive-equity subset: end-eq 0.39pp → weighted-eq **0.22pp med, 82% w/1pp, Spearman 0.991**. ⚠ **NOT 100%-reproducible from quarterly statements** — the CSRC 加权平均 weights equity by the MONTHLY timing of capital changes (div/issuance/buyback); balance-sheet SNAPSHOTS give only the quarter endpoints → ~0.2pp floor. NOT a data error (income+equity are penny-exact); a derived-metric weighting. <0.1pp needs a daily-equity reconstruction (begin-eq + accrued NP − dividends@ex-date + 增发). NOT `$roe`/`$roe_waa` (reported cumulative-YTD, 2.2pp). ⚠ **top-K NOT reproducible standalone (2026-06-28):** value Spearman 0.988 + top-5/10/20 SELECTION overlap = **40%/60%/75% on 排除ST** (the strategy-relevant universe; weighted-eq, 2026-06-28). ⚠ **UNIVERSE-ALIGNMENT FIX:** an earlier 0%/0%/5% was a **包含ST contamination ARTIFACT** — that export carried 169 ST names (tiny/distressed equity) that swamped the high-ROE zone; on 排除ST (matching ROETTMDiffPQ + the deployed books, authoritative `st_stocks.txt`) the top-K recovers to 40/60/75. Residual at top-5 = the 加权平均-at-small-equity caliber; the strategies' 筛选条件 (真实负债资产率/乖离率 rank-%, 退市风险…) are NOT yet applied and would likely lift it further. Still not a clean top-5 pass. The highest-ROE zone is a dense cluster of small-equity names (eq 0.4–145亿 at 50–270% ROE) where the 加权平均 gap reshuffles the order; 果仁 top-12 all land in my top-30 (set overlaps, order doesn't). In deployed books 净资产收益率 is BLENDED/中性化 (not a standalone top-K selector), so this matters less than ROETTMDiffPQ. **Reusable for RoeQ #38** | 5 |
| **ROETTMDiffPQ** | REFQ(净资产收益率,0)−REFQ(净资产收益率,1) | RefQ diff of RoeTTM above | ✗ **DIFF fragile at selection (NOT a data gap):** level reproducible (0.96) but 果仁 median \|val\|=**0.01 (1pp)** → the QoQ diff is a tiny signal swamped by per-leg level residual + **negative-equity instability** (果仁 #1=000692 eq −1.29亿). ALL builds give top-5 0-20% / top-20 ≤40%. Factor-design fragility | — |
| **RnDQGR%PY** | (研发费用单季−refq(,4))/refq(研发费用单季,4) | `($rd_exp_sq_q0 − $rd_exp_sq_q4) / $rd_exp_sq_q4` (lag 0) | ✅ 0.63% med (85% w/5%, sign 97.9%, n=67k) | 5 |
| **CoreProfitQ** | 营收单季−营业成本单季−(管理+销售+财务费用)单季−营业税金及附加单季 | `$revenue_sq_q0 − $oper_cost_sq_q0 − ($admin_exp_sq_q0+$sell_exp_sq_q0+$fin_exp_sq_q0) − $biz_tax_surchg_sq_q0` (lag 0) | ✅ **penny-exact** (med 0.0, 93.8% w/1%, sign 99%, n=18k) — validates ALL expense lines at once | 5 |
| **每股收益** (财务指标--每股指标) | 每股收益 TTM (滚动 4 单季) | `Σ$basic_eps_sq_q[0..3]` (lag 0) | ◑ structure-exact (1.39% med, Spearman 0.9975, sign 98.7%, n=4.4k @2025-12-31; value-confirmed 茅台 71.75 vs 果仁 71.89, 万科A −5.02 vs −4.99); residual = TTM 单季求和 vs 累计差分 + 重述时点 | field-probe 2026-07-01 |
| **基本每股收益(单季)** (财报条目--收益利润) | 基本每股收益 单季 | `$basic_eps_sq_q0` (lag 0) | ✅ penny-exact (0.00% med, Spearman 0.9996, n=4.4k @2025-12-31) | field-probe 2026-07-01 |
| **总股本(亿)** (行情--股本和市值) | 总股本 | `$total_share / 1e8` (lag 0) | ✅ penny/display-exact (0.037% med, Spearman/Pearson 1.000, top-K 100%, n=4.4k @2025-12-31); residual = 亿 2-dec display-round | T1-decomp 2026-07-01 |
| **营业利润TTM(万)** (财务指标--最近一年合计TTM) | TTM(营业利润,0) | `Σ$operate_profit_sq_q[0..3] / 1e4` (lag 0) | ✅ penny-exact (0.0000% med, Pearson 1.000, Spearman 0.997, n=4.4k @2025-12-31) | T1-decomp 2026-07-01 |

> **⚠ 分红总金额 caliber — REPORT-PERIOD, not ann-date (pinned 2026-07-01, T1 raw-primitive decomposition).** 果仁's
> `分红总金额` is a **季报指标** attributed to the dividend's REPORT PERIOD (`end_date` fiscal quarter); `sumq(分红总金额,4,0)`
> sums the last **4 FISCAL QUARTERS** (`{2024Q4,2025Q1,Q2,Q3}` as-of 2025-12-31), and `annual(分红总金额,k)` = FY(end_date year).
> This is **NOT** the ann-date trailing-365-day window (`declared_dividend_ttm`, which is the **股息率TTM** caliber): a 2024-interim
> dividend (end_date 2024Q3, announced 2025-01) is *inside* a 365-day ann-window but *outside* the last-4 fiscal quarters. Using the
> wrong window silently breaks `sumq(分红)`-based factors (建发股份: ann-window 0.7 vs report-period 0.3 → DivOP% 0.235 vs 果仁 0.102).
> **Helpers:** `guorn_dividend_caliber.declared_dividend_by_quarter` (report-period, for 分红总金额 sumq) · `declared_dividend_by_fy`
> (per-FY, for `annual(分红)`) · `declared_dividend_ttm` (ann-date-365d, for **股息率TTM only**). After the fix DivOP% top-5 = 100%
> (was 40%), Pearson 1.000 — the earlier "top-K fragile" was a caliber artifact, not an unstable denominator.
>
> **⚠ Three more dividend-family calibers (pinned 2026-07-01 v4, raw-primitive decomposition round 2):**
> 1. **Stale-预案 phantoms** — Tushare keeps superseded plan rows: 正丹股份's FY2024 interim was 预案'd at end_date 20240630
>    (0.4, never implemented) then re-dated + 实施'd at 20240930 (0.4). Summing both gave 1.10 vs 果仁 0.70 (DivAGrPY% 54 vs 34).
>    Rule (in `_declared_events`, default on): drop an event whose best state ≠ 实施 AND latest ann > **240 days** before signal;
>    keep recently-declared pending 预案 (果仁 counts those, cf. 股息率 600329). Fixed DivAGrPY% top-K to **100/100/100**, left
>    DivOP% intact (100/90/95). 实施-only is WRONG (drops pending declareds; broke DivOP%).
> 2. **Div%NetIncY2** = `ifnull((A0/N0+A1/N1)/2, A0/N0)`: **净利润 = TOTAL `n_income`** (incl minority — the formula says
>    净利润(单季), NOT 归母); **A=0-fill semantics** — a no-dividend FY contributes 0/N (HALVES the average), null only when the
>    FY's NI is missing (悦达投资 22.05→11.03 = 果仁 exact). NI_FY via `$n_income_cum_q3` (FY2024) / `_q7` (FY2023). Was the
>    family's weakest (Spearman 0.877, top-5 1/5) → **verified** (0.985, top-5 100%).
> 3. **连续N年分红(3)** = `annual(分红,0/1/2)>0` on **FY{2024,2023,2022}** (FY{25,24,23} scores 62.5% — ruled out) + a
>    **whole-FY listing gate** (`list_date ≤ 2021-12-31`, i.e. listed for ALL of FY2022; Dec-2022 IPOs paying an FY2022
>    dividend are NOT counted by 果仁) → 95.97% exact; residual ~4% undecoded (boolean filter, top-K degenerate).

### 1b. #59 Comp_Core_Quality batch (rung-6, 2026-06-24) — strategy-harness factor sweep

Validated at holding level (signal-date lag, scale-detect) for the first formal StrategyCandidate.

| 果仁 indicator | 果仁 formula | local expression | status (parity, n) | rung |
|---|---|---|---|---|
| **RnDTTM%营业收入TTM** | TTM(研发费用)/TTM(营业收入) | `TTM($rd_exp_sq)/TTM($revenue_sq)` | ✅ penny-exact (3.7e-04 med, 93.8% w/1%, sign 100%, n=6.7k) | 6 |
| **RND%Assets** | TTM(研发费用)/AvgQ(资产总计,4) | `TTM($rd_exp_sq)/mean($total_assets_q0..q3)` | ✅ penny-exact (4.6e-04 med, 94.0% w/1%, sign 100%, n=16.6k) | 6 |
| **销售毛利率Q−销售毛利率** | 单季毛利率 − TTM毛利率 | `(rev_sq0−cost_sq0)/rev_sq0 − (TTMrev−TTMcost)/TTMrev` | ✅ penny-exact (5.5e-04 med, 89.7% w/1%, sign 98.2%, n=11.7k) | 6 |
| **应收账款周转率** | TTM(营收)/(AvgQ(应收账款,4)+AvgQ(应收票据,4)−AvgQ(预收账款,4)) | `TTM($revenue_sq)/(avg4($accounts_receiv)+avg4($notes_receiv)−avg4($adv_receipts))` | ✅ penny-exact (3.2e-04 med, 92.4% w/1%, sign 99.6%, n=6.0k) | 6 |
| **RoeCoreQ** | CoreProfitQ/归属母公司股东权益合计(单季) | `CoreProfitQ/$total_hldr_eqy_exc_min_int_q0` (q0=end is BEST; avg/begin worse) | ◑ rank-faithful (3.9% med, 59% w/5%, **sign 99.5%**); residual = core-profit/equity PIT-boundary, not chased (rank preserved) | 6 |
| **HAVG(指标,1)** | 申万L1 行业截面均值 (`hAvg`=horizontal/group avg; 范围=1=一级行业) | `cs_mean($factor grouped by $sw2021_l1)` per date | ⊙ semantics RESOLVED (template `{0}<HAvg({0},{1})*{2}` 参数=指标,范围,倍数); reproducible, validate during build | 6 |
| **扣非市盈率** (filter) | 总市值/扣非净利润TTM | `$total_mv/($dtprofit_to_profit×TTM($n_income_sq))` | ◑ 5.7% med, sign 99.7% — OK for coarse (0,60) gate; residual = dtp-ratio approx + price signal-day | 6 |

**Stability factors `STDEVQ(RoeCoreQ,12)` / `STDEVQ(SalesQGr%PY,12)` — VALIDATED 2026-06-25 (scoped deep-slot
materialization).** Need 12-quarter depth (live provider has q0..q4 only). Built a SCOPED slot_depth=16 staged
provider (7 fields × 4817 universe via `--touched-symbols`+`field_filter`, ~182GB transient, deleted;
`_build_deepslot_scoped.py` + `guorn_parity_rung6_quality59.py build_stability`) → both computed (RoeCoreQ:
`CoreProfit(t)/equity(t)`, SalesGr: `(rev[t]−rev[t+4])/|rev[t]|`, t=0..11, stdev ≥8/12, ~72% cov). **DECISIVE:
the faithful 11-factor composite lifts #59 overlap 21.6%→35.9% (+14.3pp) AND converges the backtest (annual
+25.3→+21.4% vs 果仁 +22.6%; vol 27.1→25.7% vs 26.7%; Sharpe 0.82→0.73 vs 0.69) — the 2 STDEVQ were the dominant
parity-gap cause, PROVEN.** NON-FORMAL (staged provider deleted; a formal book needs them in the LIVE provider +
registered). `中性ROE` stays omitted — **inert** (0.0000 for 98.5% of #59 holdings), irreducible §5. ⚠ ALWAYS
scope a slot_depth build (`--touched-symbols`+`field_filter`) — the unscoped first try hit 1TB (memory
`feedback_provider_build_disk_hazard`).

Legend: ✅ penny/structure-exact (residual = display/PIT-boundary) · ◑ structure confirmed, sub-detail residual · ⊙ semantics resolved, reproduction pending.

### 1c. Vendor-approximate (rank-faithful — RANKING-USE ONLY, not penny/threshold-exact)

These reproduce 果仁's **ranking** but come from a DIFFERENT vendor than 果仁's 朝阳永续, so they are NOT
penny-exact and MUST NOT be used as a threshold filter or an exact data audit. Validated vs 果仁's web export
(`guorn_factor_parity.py --kind count`), not just JoinQuant.

| 果仁 indicator | local expression | status (parity, n) | allowed use |
|---|---|---|---|
| **评级机构数** | `$report_rc__n_active_orgs` | ◑ vendor-approx **rank-faithful** vs 果仁 web (Tushare 卖方研报 ≠ 朝阳永续): exact 70.8%, corr-on-non-zero 0.990, Spearman 0.982 @2025-12-31 (broad univ, 92% coverage → `--min-coverage 0.90`) | a RANKING factor / composite term only — NOT a threshold filter or value audit |

---

## 2. Data-validated, residual = reconstruction convention (NOT a data error)

The underlying close/市值 data is penny-exact (via 总市值); the residual is 果仁's long-window
counting convention, proven NOT to be data / 复权 / corporate-action.

| 果仁 indicator | local expression | residual | proof it's not a data fault |
|---|---|---|---|
| **250日涨幅** | `adjc / adjc.shift(250) − 1` (lag 0) | ~5.5% med, signs 97% | window N=250 is a sharp confirmed min; ratio 复权-invariant; **no-corp-action subset EQUALLY off (5.45%)** → residual = N-day lookback window-MEMBERSHIP counting (果仁 suspension/calendar vs `.shift(250)`) |
| **N日乖离率(120)** | `(adjc − MA(adjc,120)) / MA(adjc,120)` (lag 1) | ~6.8% med, signs 95% | **no-corp-action subset EQUALLY off (8.2%, n=80k)** → same root cause (MA window-membership counting) |
| **股东数下降率** (rung-5; ✅ RESOLVED 2026-06-25) | `$holder_num_q1/$holder_num_q0 − 1` (CONSECUTIVE-disclosure change; was `_q4` — a depth error) | ✅ **value path validated on non-zero EVENT rows** (provider-read 0.14% med / 93% sign, lag-0); NOT a full bit-exact factor (62% within-5%) | The `_q4` (4 disclosures back) was a DEPTH error — depth-1 wins (0.24% ≫ depth-4 137%); 报告期-grid variants (QEND/ASOF) are WORSE (3.2×) → **NOT a 报告期-grid/materialization gap.** 果仁's factor is a near-inert **DISCLOSURE-EVENT signal** (non-zero only ~2d post-disclosure [median 2d vs 53d], 92% zero between events); its exact zero/event-window serving is a 果仁 convention (unreproduced), but the data path + value mapping ARE validated. Full detail in §6. |

---

## 3. Un-validatable from the holdings display

| 果仁 indicator | why | note |
|---|---|---|
| **股价振幅%当日成交额10日** | 果仁 **displays 0.00** for every holding (true value ~2e-6 rounds to zero at 2 decimals) | local formula `MA((high−low)/prev_close / $amount, 10)` is provably CORRECT (matches 果仁's published formula), but parity is meaningless at 2-dec display. ⚠ Earlier "2.4e-05 penny-exact" claim was WRONG (it was a degenerate near-zero match). |

---

## 4. Corrections to the auto-generated formula docs (errors that would mis-build a factor)

| doc | says | actually | impact if trusted |
|---|---|---|---|
| guorn_aichat_indicator_defs.md | ILLIQ = `Sum(\|1日涨幅\|/成交额(亿元),N)/N` | numerator is **股价振幅 (high−low)/prev_close**, NOT `\|1日涨幅\|` (the desc "每亿元成交额引起的股价振幅" is literal) | \|return\| gives gf/mine 1.85 (IQR 1.5–2.3); 振幅 gives 0.86 (IQR 0.81–0.94) + 12.5% within 0.1% |
| indicator_reference_auto.md (builtin BP) | `归属母公司股东权益合计/总市值` (correct) | the field is **exc_min_int** (parent-only), trivially mis-mapped to inc_min_int (total) | inc_min_int → 5.9% vs exc_min_int → 0.66% |
| (rung-2 finding) | plain `净利润(单季)` | = **TOTAL** single-quarter net profit (`$n_income_sq_q0`), NOT 归母 (`$n_income_attr_p_sq_q0`) | 归母 gave only 45.8% within 0.1% |

---

## 5. NOT mapped (by design) — redundant / irreducible / out-of-scope

- **Redundant** (reuse already-validated fields; path proven): CoreProfitQ & its `%PY`/`%PQ` growths,
  EPCoreProfitQ, EBITDAQ, all revenue/profit/asset growth-rate transforms, ROETTMDiffPQ, etc.
- **Irreducible** (cannot penny-match 果仁): 中性化 family (`HNeutralize`/`HNeutralizeMI` — 果仁's exact
  industry regression), 壳价值 (`SSlopeXY` AH-premium regression), 退市风险 screens (预期ST2021 / 风险预警25版
  / 重大违规 / 国九条 — no local data), 朝阳永续 预期净利润 (report_rc; vendor-approximate, not penny-mappable —
  Tushare 卖方研报 ≠ 朝阳永续) [⚠ **评级机构数 is NOT here — it is now mapped vendor-approximate, see §1c**, web-
  validated rank-faithful vs 果仁], 大盘择时 (涨停/跌停家数比例 — market-aggregate), ETF selectors
  (`TICKER()=...`), 未来20日新增流通股 (PIT lockup schedule, no clean feed — realized shares = lookahead).

---

## 6. Coverage tracker (data paths)

| data path | status | via |
|---|---|---|
| 市值 (total/circ) | ✅ validated | 总市值/流通市值 |
| income statement (营收/营业成本/净利润 single-q + TTM) | ✅ penny-exact | rung-2/4 |
| balance sheet (总资产/总负债/归母权益) | ✅ penny-exact | rung-4 |
| cashflow (经营现金流净额) | ✅ penny-exact | OPCFNPDiff%NP |
| valuation (pe_ttm) | ✅ validated | 市盈率 |
| forecast 业绩预告 (event-PIT) | ✅ validated | rung-3 |
| price/volume (close/high/low/amount/adj) | ✅ validated | 总市值 + momentum |
| 分红 / 股息 (dividends) | ✅ validated (rung-5 bulk) + ⚠ CALIBER split (2026-06-28) | 股息率TTM → `$dv_ttm` 0.70% med **bulk** BUT ex-date≠ann-date at the high-yield **selection tail**; use ann-date DECLARED caliber [guorn_dividend_caliber.py](../../../scripts/guorn_dividend_caliber.py) for tail/selection (top-5 100%). **Applies to ALL dividend factors** (DivGrPY%, Div%NetIncY2, 近三年分红之和, 预期股息率) |
| 研发费用 ($rd_exp) | ✅ validated (rung-5) | RnDQGR%PY (0.63% med) |
| expense lines (管理/销售/财务费用 + 营业税金) | ✅ penny-exact (rung-5) | CoreProfitQ (med 0.0) |
| 总股本 (share count) | ✅ validated (implicit) | 总市值 = close × total_share (both penny-exact) |
| **股东数 (holder_number)** | ✅ RESOLVED (2026-06-25) — DATA SOUND, NOT a materialization gap | 股东数下降率 = **`$holder_num_q1/$holder_num_q0 − 1`** (CONSECUTIVE-disclosure change, EXISTING fields). **PROVIDER-READ** (D.features, lag-0) reproduces 果仁's non-zero subset at **0.14% med rel-err / 93% sign** (airtight, [_holder_provider_check.py](../../../scripts/_holder_provider_check.py)); ledger-probe REF-depth sweep: depth-1 wins (0.24% ≫ depth-4 137%). The rung-5 "needs 报告期-grid resampling" diagnosis was **WRONG** (rule #10): QEND/ASOF 报告期-grid variants are WORSE (3.2× vs 1.37×); the failure was a **DEPTH error** (used `_q4` ≈ 4 disclosures, should be `_q1`). 果仁's factor is a **DISCLOSURE-EVENT signal**: non-zero only ~2 days after a new 股东数 disclosure (median 2d vs 53d for the zero rows), **92% zero between events** — near-inert (cf. #59 中性ROE, rung-4 振幅%成交额). No materializer/build warranted. Probe: [_holder_grid_probe.py](../../../scripts/_holder_grid_probe.py). |
| **折旧摊销 (D&A)** | ◑ MATERIALIZED (cum only); single-q NaN by cadence | `$depr_fa_coga_dpba_cum_q0`/`$amort_intang_assets_cum_q0` ARE materialized (22.5% populated). `_sq_q0` is 0.91% non-NaN — NaN because D&A is disclosed only **semi-annually** (H1+FY cumulative, never Q1/Q3) so single-quarter differencing has no prior quarter. EBITDAQ/FCFQ single-q unreproducible **by reporting cadence**, NOT a materialization gap. `recp_disp_fiolta` (FCFQ disposal term) genuinely never fetched. |

**rung-5 (2026-06-23)** closed 4 of the 6 OPEN paths (分红/研发/费用明细 validated, 总股本 implicit).
**股东数: RESOLVED 2026-06-25** — all 6 rung-4 OPEN paths now RESOLVED: **5 validated** (分红/研发/费用明细/总股本/股东数) + **折旧摊销 (D&A) = materialized-cum-only** (single-quarter unreproducible by SEMI-ANNUAL disclosure cadence — proven NOT an actionable materialization gap; it remains in the JSON `coverage_open` tagged `materialized_cum_only`, not as a fixable gap). The "needs 报告期-grid reconstruction"
remaining-item was a MISDIAGNOSIS (rule #10): the data is sound; 股东数下降率 = consecutive-disclosure
change `q1/q0−1` (existing fields, 0.24% med on the non-zero subset), a near-inert DISCLOSURE-EVENT factor
(non-zero only ~2d post-disclosure, 92% zero). No 报告期 grid / no materializer needed (QEND/ASOF tested WORSE).
**折旧摊销 (D&A): CORRECTED
2026-06-23** — the earlier "not materialized" claim was a FALSE INFERENCE (from a 3-stock `notna().any()`
probe). D&A cumulative IS materialized; the single-quarter is NaN by semi-annual disclosure cadence —
no build fixes it (proven by the 茅台 cum-vs-sq trace + the 0.0091 vs 0.225 breadth fractions).

## 7. Provider materialization audit (2026-06-23) — downloaded-but-unmaterialized fields

Diff of every raw ledger numeric column vs the live provider bins ([_rung5_materialization_audit.py](../../../scripts/_rung5_materialization_audit.py)).
**100% materialized:** income, balancesheet, cashflow, cashflow_quarterly, dividends, forecast,
holder_number, income_quarterly. **Real gaps (ledger-populated, absent from provider — verified by
ledger coverage + `D.features` probe, not just the base-name diff):**

| dataset | unmaterialized | ledger coverage | note |
|---|---|---|---|
| **indicators** | 25 `q_*` single-quarter metrics (q_eps, q_netprofit_yoy, q_op_yoy, q_gr_yoy, q_dtprofit, q_sales_qoq, q_netprofit_margin, margins, qoq/yoy growths…) | ~83–89% (= materialized sibling `q_roe` 87.7%) | curated indicators list omits these 25; **highest-value materialization candidate** |
| **report_rc** | 8 analyst fields (np 97%, op_rt 74%, tp 65%, ev_ebitda 49%, min_price 30%, rd 20%, op_pr 9%, max_price 1%) | as shown | only the eps_diffusion primitives were materialized (selective by design) |
| **stk_holdertrade** | 5 (change_vol 100%, change_ratio 100%, after_share 88%, after_ratio 84%, avg_price 71%) | as shown | only the count was materialized (selective by design) |

Materializing any of these needs a staged build + publish + field-registry registration + GPT review.

---

*Sources (all NON-FORMAL, workspace/scripts/): `_rung4_field_parity.py` (BP→exc_min_int),
`_rung4_reverse_engineer.py`, `_rung4_decompose.py`, `_rung4_illiq_bp_final.py`,
`_rung4_momentum_diag.py`; rung-2 `_validate_pit_netprofit_vs_guorn.py`; rung-3
`_provider_read_audit_forecast.py`. Full history: memory `project_guorn_parity` + project_state.md.*
