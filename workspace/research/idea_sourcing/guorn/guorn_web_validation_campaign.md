# 果仁 web-validation campaign — DEPLOYED-20 (per-factor)

> One export per factor, deployed-20 first, highest-usage first. **56 web-validatable factors** (15 done / 41 pending). Resumable: status lives in `guorn_web_validation_campaign.json`; re-run `build_guorn_validation_campaign.py` to re-seed (preserves status). NON-FORMAL.

Procedure per factor: 1. 果仁 web: rank-ONLY on this single indicator, universe to match (or a broad universe — factor VALUES are 范围/universe-invariant), 选股日期 ≤ local calendar max. 2. 导出 → rename 果仁_{date}_{universe}_{indicator}.xlsx under Knowledge/果仁验证因子/. 3. derive/confirm the local_expr (validated rows already have it; doable rows: map the 果仁_formula → local qlib expr via guorn_local_field_mapping.md conventions). 4. guorn_factor_parity.py --xlsx <export> --date <date> --local-expr '<expr>' --guorn-col <name> [--kind count] [--min-coverage X w/ reason]. 5. record status/verdict here (re-run this script preserves it).

| # | 果仁 indicator | bucket | local_expr | dep books | status | verdict |
|---|---|---|---|---|---|---|
| 1 | 上市天数 | doable | — derive — | 7 | ⬜ pending |  |
| 2 | EpsExclXorQGr%PY | doable | — derive — | 7 | ⬜ pending |  |
| 3 | 真实负债资产率 | doable | — derive — | 4 | ⬜ pending |  |
| 4 | 股价振幅%当日成交额10日 | validated | — derive — | 4 | ⬜ pending |  |
| 5 | 评级调高家数 | doable | — derive — | 4 | ⬜ pending |  |
| 6 | 所得税费用QGr%PY | doable | — derive — | 3 | ⬜ pending |  |
| 7 | SharesAvgGr%PY | doable | — derive — | 3 | ⬜ pending |  |
| 8 | 业绩预告净利润QGr%PYQ | doable | — derive — | 2 | ⬜ pending |  |
| 9 | 历史贝塔 | doable | — derive — | 2 | ⬜ pending |  |
| 10 | DivGrPY% | doable | — derive — | 2 | ⬜ pending |  |
| 11 | 贝塔N日(000001,250) | doable | — derive — | 2 | ⬜ pending |  |
| 12 | AssetTurnoverDiffPY | doable | — derive — | 2 | ⬜ pending |  |
| 13 | 财报预约公布天数 | doable | — derive — | 1 | ⬜ pending |  |
| 14 | 20日涨幅 | doable | — derive — | 1 | ⬜ pending |  |
| 15 | 管理层持股比例 | doable | — derive — | 1 | ⬜ pending |  |
| 16 | 交易天数 | doable | — derive — | 1 | ⬜ pending |  |
| 17 | 10日融资偿还金额 | doable | — derive — | 1 | ⬜ pending |  |
| 18 | 20日换手率 | doable | — derive — | 1 | ⬜ pending |  |
| 19 | YieldRfrDiff | doable | — derive — | 1 | ⬜ pending |  |
| 20 | 波动率_日度指标(分红总金额,720) | doable | — derive — | 1 | ⬜ pending |  |
| 21 | 连续N年分红(3) | doable | — derive — | 1 | ⬜ pending |  |
| 22 | DivOP% | doable | — derive — | 1 | ⬜ pending |  |
| 23 | 预期盈利增长率 | doable | — derive — | 1 | ⬜ pending |  |
| 24 | 5日平均溢价率 | doable | — derive — | 1 | ⬜ pending |  |
| 25 | 财报发布天数 | doable | — derive — | 1 | ⬜ pending |  |
| 26 | RoeQ | doable | — derive — | 1 | ⬜ pending |  |
| 27 | 机构持股比例 | doable | — derive — | 1 | ⬜ pending |  |
| 28 | RnDTTMGr%PY | doable | — derive — | 1 | ⬜ pending |  |
| 29 | Div%NetIncY2 | doable | — derive — | 1 | ⬜ pending |  |
| 30 | DivAGrPY% | doable | — derive — | 1 | ⬜ pending |  |
| 31 | AH股溢价率 | doable | — derive — | 1 | ⬜ pending |  |
| 32 | 市研率 | doable | — derive — | 1 | ⬜ pending |  |
| 33 | EpsTTMGr% | doable | — derive — | 1 | ⬜ pending |  |
| 34 | sortinoN日(120) | doable | — derive — | 1 | ⬜ pending |  |
| 35 | 60日波动率 | doable | — derive — | 1 | ⬜ pending |  |
| 36 | sortinoN日(250) | doable | — derive — | 1 | ⬜ pending |  |
| 37 | ATR%收盘价N日(20) | doable | — derive — | 1 | ⬜ pending |  |
| 38 | 120日涨幅 | doable | — derive — | 1 | ⬜ pending |  |
| 39 | 分析师评级分 | doable | — derive — | 1 | ⬜ pending |  |
| 40 | 近期评级变化 | doable | — derive — | 1 | ⬜ pending |  |
| 41 | 评级增持家数 | doable | — derive — | 1 | ⬜ pending |  |
| 42 | CoreProfitQGr%PY | doable | (CoreProfitQ_q0-CoreProfitQ_q4)/Abs(Core | 10 | ✅ done | ✅ penny/display-exact (median 0.0061%, S |
| 43 | ROETTMDiffPQ | doable | (TTM归母_q0/eq_q0)-(TTM归母_q1/eq_q1) | 9 | ✗ diverged | ✗ SELECTION-DIVERGED — top-K re-test (20 |
| 44 | 总市值 | validated | `$total_mv` (万元) | 8 | ✅ done | ✅ penny/display-exact (broad 4397, Spear |
| 45 | 业绩预告净利润QGr%PYQ_v1 | validated | `$forecast__np_q_yoy` | 8 | ✅ done | ◑ top-K NOT ASSESSABLE at 2025-12-31 — o |
| 46 | GrossProfit%AssetsQ | validated | `($revenue_sq_q0 − $oper_cost_sq_q0) / $ | 5 | ✅ done | ✅ penny-exact + TOP-K PERFECT (broad 排除S |
| 47 | 5日平均成交额 | doable | Mean($amount,5)/1e5 (lag 0) | 5 | ✅ done | ✅ value penny-exact at LAG-0: median 0.1 |
| 48 | 20日平均成交额 | doable | Mean($amount,20)/1e5 (lag 0) | 4 | ✅ done | ✅ value penny-exact at LAG-0: median 0.1 |
| 49 | 250日涨幅 | validated | `adjc / adjc.shift(250) − 1` (lag 0) | 3 | ✅ done | ✅ penny-exact + TOP-K STRONG: top-5/10/2 |
| 50 | SalesQGr%PY | validated | `($revenue_sq_q0 − $revenue_sq_q4) / abs | 2 | ✅ done | ✅ value penny-exact (median 0.018%, with |
| 51 | RnDQGR%PY | validated | `($rd_exp_sq_q0 − $rd_exp_sq_q4) / $rd_e | 2 | ✅ done | ◑ value structure-exact (Spearman 0.984, |
| 52 | 股息率TTM | validated | `$dv_ttm` (lag T−1, scale 100) | 2 | ✅ done | ✅ REPRODUCED via caliber (my earlier 'ir |
| 53 | 评级机构数 | validated | ◑ vendor-approx **rank-faithful** vs 果仁  | 2 | ✅ done | ◑ vendor-approx rank-faithful + TOP-K CO |
| 54 | 研发销售比率 | doable | (Σrd_exp_sq_q0..3)/(Σrevenue_sq_q0..3) | 2 | ✅ done | ✅ penny-exact + TOP-K STRONG: top-5/10/2 |
| 55 | CoreProfitQ | validated | `$revenue_sq_q0 − $oper_cost_sq_q0 − ($a | 1 | ✅ done | ✅ value penny-exact (Spearman 1.000, Pea |
| 56 | RND%Assets | validated | `TTM($rd_exp_sq)/mean($total_assets_q0.. | 1 | ✅ done | ✅ penny-exact + TOP-K COMPLETE: top-5/10 |