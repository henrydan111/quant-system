# 果仁 web-validation campaign — DEPLOYED-20 (per-factor)

> One export per factor, deployed-20 first, highest-usage first. **56 web-validatable factors** (5 done / 51 pending). Resumable: status lives in `guorn_web_validation_campaign.json`; re-run `build_guorn_validation_campaign.py` to re-seed (preserves status). NON-FORMAL.

Procedure per factor: 1. 果仁 web: rank-ONLY on this single indicator, universe to match (or a broad universe — factor VALUES are 范围/universe-invariant), 选股日期 ≤ local calendar max. 2. 导出 → rename 果仁_{date}_{universe}_{indicator}.xlsx under Knowledge/果仁验证因子/. 3. derive/confirm the local_expr (validated rows already have it; doable rows: map the 果仁_formula → local qlib expr via guorn_local_field_mapping.md conventions). 4. guorn_factor_parity.py --xlsx <export> --date <date> --local-expr '<expr>' --guorn-col <name> [--kind count] [--min-coverage X w/ reason]. 5. record status/verdict here (re-run this script preserves it).

| # | 果仁 indicator | bucket | local_expr | dep books | status | verdict |
|---|---|---|---|---|---|---|
| 1 | 业绩预告净利润QGr%PYQ_v1 | validated | `$forecast__np_q_yoy` | 8 | ⬜ pending |  |
| 2 | 上市天数 | doable | — derive — | 7 | ⬜ pending |  |
| 3 | EpsExclXorQGr%PY | doable | — derive — | 7 | ⬜ pending |  |
| 4 | GrossProfit%AssetsQ | validated | `($revenue_sq_q0 − $oper_cost_sq_q0) / $ | 5 | ⬜ pending |  |
| 5 | 5日平均成交额 | doable | — derive — | 5 | ⬜ pending |  |
| 6 | 20日平均成交额 | doable | — derive — | 4 | ⬜ pending |  |
| 7 | 真实负债资产率 | doable | — derive — | 4 | ⬜ pending |  |
| 8 | 股价振幅%当日成交额10日 | validated | — derive — | 4 | ⬜ pending |  |
| 9 | 评级调高家数 | doable | — derive — | 4 | ⬜ pending |  |
| 10 | 所得税费用QGr%PY | doable | — derive — | 3 | ⬜ pending |  |
| 11 | SharesAvgGr%PY | doable | — derive — | 3 | ⬜ pending |  |
| 12 | 250日涨幅 | validated | `adjc / adjc.shift(250) − 1` (lag 0) | 3 | ⬜ pending |  |
| 13 | SalesQGr%PY | validated | `($revenue_sq_q0 − $revenue_sq_q4) / abs | 2 | ⬜ pending |  |
| 14 | RnDQGR%PY | validated | `($rd_exp_sq_q0 − $rd_exp_sq_q4) / $rd_e | 2 | ⬜ pending |  |
| 15 | 业绩预告净利润QGr%PYQ | doable | — derive — | 2 | ⬜ pending |  |
| 16 | 历史贝塔 | doable | — derive — | 2 | ⬜ pending |  |
| 17 | DivGrPY% | doable | — derive — | 2 | ⬜ pending |  |
| 18 | 贝塔N日(000001,250) | doable | — derive — | 2 | ⬜ pending |  |
| 19 | 研发销售比率 | doable | — derive — | 2 | ⬜ pending |  |
| 20 | AssetTurnoverDiffPY | doable | — derive — | 2 | ⬜ pending |  |
| 21 | 财报预约公布天数 | doable | — derive — | 1 | ⬜ pending |  |
| 22 | 20日涨幅 | doable | — derive — | 1 | ⬜ pending |  |
| 23 | CoreProfitQ | validated | `$revenue_sq_q0 − $oper_cost_sq_q0 − ($a | 1 | ⬜ pending |  |
| 24 | 20日换手率 | doable | — derive — | 1 | ⬜ pending |  |
| 25 | 10日融资偿还金额 | doable | — derive — | 1 | ⬜ pending |  |
| 26 | 管理层持股比例 | doable | — derive — | 1 | ⬜ pending |  |
| 27 | RND%Assets | validated | `TTM($rd_exp_sq)/mean($total_assets_q0.. | 1 | ⬜ pending |  |
| 28 | 交易天数 | doable | — derive — | 1 | ⬜ pending |  |
| 29 | YieldRfrDiff | doable | — derive — | 1 | ⬜ pending |  |
| 30 | 连续N年分红(3) | doable | — derive — | 1 | ⬜ pending |  |
| 31 | DivOP% | doable | — derive — | 1 | ⬜ pending |  |
| 32 | 波动率_日度指标(分红总金额,720) | doable | — derive — | 1 | ⬜ pending |  |
| 33 | 预期盈利增长率 | doable | — derive — | 1 | ⬜ pending |  |
| 34 | 5日平均溢价率 | doable | — derive — | 1 | ⬜ pending |  |
| 35 | 财报发布天数 | doable | — derive — | 1 | ⬜ pending |  |
| 36 | 机构持股比例 | doable | — derive — | 1 | ⬜ pending |  |
| 37 | RnDTTMGr%PY | doable | — derive — | 1 | ⬜ pending |  |
| 38 | RoeQ | doable | — derive — | 1 | ⬜ pending |  |
| 39 | Div%NetIncY2 | doable | — derive — | 1 | ⬜ pending |  |
| 40 | DivAGrPY% | doable | — derive — | 1 | ⬜ pending |  |
| 41 | 市研率 | doable | — derive — | 1 | ⬜ pending |  |
| 42 | AH股溢价率 | doable | — derive — | 1 | ⬜ pending |  |
| 43 | EpsTTMGr% | doable | — derive — | 1 | ⬜ pending |  |
| 44 | sortinoN日(120) | doable | — derive — | 1 | ⬜ pending |  |
| 45 | sortinoN日(250) | doable | — derive — | 1 | ⬜ pending |  |
| 46 | 120日涨幅 | doable | — derive — | 1 | ⬜ pending |  |
| 47 | ATR%收盘价N日(20) | doable | — derive — | 1 | ⬜ pending |  |
| 48 | 60日波动率 | doable | — derive — | 1 | ⬜ pending |  |
| 49 | 近期评级变化 | doable | — derive — | 1 | ⬜ pending |  |
| 50 | 分析师评级分 | doable | — derive — | 1 | ⬜ pending |  |
| 51 | 评级增持家数 | doable | — derive — | 1 | ⬜ pending |  |
| 52 | CoreProfitQGr%PY | doable | (CoreProfitQ_q0-CoreProfitQ_q4)/Abs(Core | 10 | ✅ done | ✅ penny/display-exact (median 0.0061%, S |
| 53 | ROETTMDiffPQ | doable | 净资产收益率=TTM-ROE (level reproducible 0.96/ | 9 | ✗ diverged | ✗ DIFF fragile at selection (REFINED via |
| 54 | 总市值 | validated | `$total_mv` (万元) | 8 | ✅ done | ✅ penny/display-exact (broad 4397, Spear |
| 55 | 股息率TTM | validated | `$dv_ttm` (lag T−1, scale 100) | 2 | ✅ done | ✅ REPRODUCED via caliber (my earlier 'ir |
| 56 | 评级机构数 | validated | ◑ vendor-approx **rank-faithful** vs 果仁  | 2 | ✅ done | ◑ vendor-approx rank-faithful: exact 70. |