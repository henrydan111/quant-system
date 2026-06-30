# 果仁 web-validation campaign — DEPLOYED-20 (per-factor)

> One export per factor, deployed-20 first, highest-usage first. **56 web-validatable factors** (21 done / 35 pending). Resumable: status lives in `guorn_web_validation_campaign.json`; re-run `build_guorn_validation_campaign.py` to re-seed (preserves status). NON-FORMAL.

Procedure per factor: 1. 果仁 web: rank-ONLY on this single indicator, universe to match (or a broad universe — factor VALUES are 范围/universe-invariant), 选股日期 ≤ local calendar max. 2. 导出 → rename 果仁_{date}_{universe}_{indicator}.xlsx under Knowledge/果仁验证因子/. 3. derive/confirm the local_expr (validated rows already have it; doable rows: map the 果仁_formula → local qlib expr via guorn_local_field_mapping.md conventions). 4. guorn_factor_parity.py --xlsx <export> --date <date> --local-expr '<expr>' --guorn-col <name> [--kind count] [--min-coverage X w/ reason]. 5. record status/verdict here (re-run this script preserves it).

| # | 果仁 indicator | bucket | local_expr | dep books | status | verdict |
|---|---|---|---|---|---|---|
| 1 | 评级调高家数 | doable | — derive — | 4 | ⬜ pending |  |
| 2 | 所得税费用QGr%PY | doable | — derive — | 3 | ⬜ pending |  |
| 3 | 20日换手率 | doable | — derive — | 1 | ⬜ pending |  |
| 4 | 交易天数 | doable | — derive — | 1 | ⬜ pending |  |
| 5 | 市研率 | doable | — derive — | 1 | ⬜ pending |  |
| 6 | sortinoN日(250) | doable | — derive — | 1 | ⬜ pending |  |
| 7 | sortinoN日(120) | doable | — derive — | 1 | ⬜ pending |  |
| 8 | 分析师评级分 | doable | — derive — | 1 | ⬜ pending |  |
| 9 | CoreProfitQGr%PY | doable | (CoreProfitQ_q0-CoreProfitQ_q4)/Abs(Core | 10 | ✅ done | ✅ penny/display-exact (median 0.0061%, S |
| 10 | ROETTMDiffPQ | doable | (TTM归母_q0/eq_q0)-(TTM归母_q1/eq_q1) | 9 | ✗ diverged | ✗ SELECTION-DIVERGED — top-K re-test (20 |
| 11 | 总市值 | validated | `$total_mv` (万元) | 8 | ✅ done | ✅ penny/display-exact (broad 4397, Spear |
| 12 | 业绩预告净利润QGr%PYQ_v1 | validated | `$forecast__np_q_yoy` | 8 | ✅ done | ◑ top-K NOT ASSESSABLE at 2025-12-31 — o |
| 13 | 上市天数 | doable | — derive — | 7 | 🔴 blocked | 🔴 BLOCKED — today−list_date is a stock_b |
| 14 | EpsExclXorQGr%PY | doable | ($profit_dedt_sq_q0-$profit_dedt_sq_q4)/ | 7 | ✅ done | ✅ penny-exact + TOP-K CLEAN: top-5/10/20 |
| 15 | GrossProfit%AssetsQ | validated | `($revenue_sq_q0 − $oper_cost_sq_q0) / $ | 5 | ✅ done | ✅ penny-exact + TOP-K PERFECT (broad 排除S |
| 16 | 5日平均成交额 | doable | Mean($amount,5)/1e5 (lag 0) | 5 | ✅ done | ✅ value penny-exact at LAG-0: median 0.1 |
| 17 | 20日平均成交额 | doable | Mean($amount,20)/1e5 (lag 0) | 4 | ✅ done | ✅ value penny-exact at LAG-0: median 0.1 |
| 18 | 真实负债资产率 | doable | — derive — | 4 | 🔴 blocked | 🔴 BLOCKED — 果仁 proprietary '真实' (adjuste |
| 19 | 股价振幅%当日成交额10日 | validated | — derive — | 4 | 🔴 blocked | 🔴 BLOCKED — 果仁 DISPLAYS 0.00 for every h |
| 20 | SharesAvgGr%PY | doable | — derive — | 3 | 🔴 blocked | 🔴 BLOCKED — needs 总股本 8-quarter avg (q0. |
| 21 | 250日涨幅 | validated | `adjc / adjc.shift(250) − 1` (lag 0) | 3 | ✅ done | ✅ penny-exact + TOP-K STRONG: top-5/10/2 |
| 22 | SalesQGr%PY | validated | `($revenue_sq_q0 − $revenue_sq_q4) / abs | 2 | ✅ done | ✅ value penny-exact (median 0.018%, with |
| 23 | RnDQGR%PY | validated | `($rd_exp_sq_q0 − $rd_exp_sq_q4) / $rd_e | 2 | ✅ done | ◑ value structure-exact (Spearman 0.984, |
| 24 | 业绩预告净利润QGr%PYQ | doable | — derive — | 2 | ✅ done | ◑ top-K N/A at 2025-12-31 — same sparsit |
| 25 | 历史贝塔 | doable | — derive — | 2 | 🔴 blocked | 🔴 BLOCKED — beta vs index needs a Cov/Va |
| 26 | 股息率TTM | validated | `$dv_ttm` (lag T−1, scale 100) | 2 | ✅ done | ✅ REPRODUCED via caliber (my earlier 'ir |
| 27 | DivGrPY% | doable | — derive — | 2 | 🔴 blocked | 🔴 BLOCKED(comparator) — sumq(分红总金额,4,0)/ |
| 28 | 评级机构数 | validated | ◑ vendor-approx **rank-faithful** vs 果仁  | 2 | ✅ done | ◑ vendor-approx rank-faithful + TOP-K CO |
| 29 | 贝塔N日(000001,250) | doable | — derive — | 2 | 🔴 blocked | 🔴 BLOCKED — SlopeXY(1日涨幅, 指数涨幅(000001),  |
| 30 | 研发销售比率 | doable | (Σrd_exp_sq_q0..3)/(Σrevenue_sq_q0..3) | 2 | ✅ done | ✅ penny-exact + TOP-K STRONG: top-5/10/2 |
| 31 | AssetTurnoverDiffPY | doable | — derive — | 2 | 🔴 blocked | 🔴 BLOCKED — 总资产周转率 at q4 = TTM(revenue)  |
| 32 | 财报预约公布天数 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — 预约披露 disclosure-schedule cal |
| 33 | 20日涨幅 | doable | ($close*$adj_factor)/Ref(,20)-1 | 1 | ✅ done | ✅ 后复权 ratio (close*adj)/Ref(,20)-1, lag- |
| 34 | CoreProfitQ | validated | `$revenue_sq_q0 − $oper_cost_sq_q0 − ($a | 1 | ✅ done | ✅ value penny-exact (Spearman 1.000, Pea |
| 35 | 管理层持股比例 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — management holding % NOT mat |
| 36 | 10日融资偿还金额 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — margin repayment $rzche is Q |
| 37 | RND%Assets | validated | `TTM($rd_exp_sq)/mean($total_assets_q0.. | 1 | ✅ done | ✅ penny-exact + TOP-K COMPLETE: top-5/10 |
| 38 | 连续N年分红(3) | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED(comparator) — min(股息率,250*N)>0 |
| 39 | YieldRfrDiff | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — needs 10年国债收益率 (treasury); n |
| 40 | DivOP% | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED(comparator) — sumq(分红,4)/TTM(营 |
| 41 | 波动率_日度指标(分红总金额,720) | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — 720d stdev of DAILY 分红总金额; d |
| 42 | 预期盈利增长率 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED(comparator) — consensus expect |
| 43 | 5日平均溢价率 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — 溢价率 (fund/ETF premium); not  |
| 44 | 财报发布天数 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — 财报发布-date schedule NOT inges |
| 45 | RoeQ | doable | ifnull($profit_dedt_sq_q0,$n_income_sq_q | 1 | ✅ done | ✅ 扣非单季/总资产(ROA-like, stable denom). top5 |
| 46 | 机构持股比例 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — institution holding % NOT ma |
| 47 | RnDTTMGr%PY | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — needs rd_exp q4..q7 (8 quart |
| 48 | Div%NetIncY2 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED(comparator) — annual(分红)/annua |
| 49 | DivAGrPY% | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED(comparator) — annual(分红 0)/ann |
| 50 | EpsTTMGr% | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — (每股收益 q0 − q4) needs reporte |
| 51 | AH股溢价率 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — needs H-share price; no HK d |
| 52 | 60日波动率 | doable | Std($pct_chg,60) (lag-0; 果仁 annualizes × | 1 | ✅ done | ✅ low-vol selection (从小到大, the actual us |
| 53 | 120日涨幅 | doable | ($close*$adj_factor)/Ref(,120)-1 | 1 | ✅ done | ✅ 后复权 ratio (close*adj)/Ref(,120)-1, lag |
| 54 | ATR%收盘价N日(20) | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — ATR (avg true-range) has no  |
| 55 | 近期评级变化 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — recent rating-change field N |
| 56 | 评级增持家数 | doable | — derive — | 1 | 🔴 blocked | 🔴 BLOCKED — $report_rc__rating_buy NOT m |