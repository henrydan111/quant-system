# growth 字段审计

- 主题假设：A 股成长股策略：单因子成长信号在 leakage-fix 后普遍偏弱（Phase 1 quick-kill 显示无 A/B 级），但通过(1)机构席位确认 + 多源利润增长 + 质量/动量验证 (Hyp A) 或 (2) GARP 多元复合 (Hyp B) 仍可能挖掘出可交易的成长溢价。Layer 2 用 mainboard + 市值/流动性/盈利门槛过滤，Layer 3 让 signal_search 在 8 个 Hyp A 组件 + 5 个 Hyp B 组件中搜索结构变体（equal-weight + 1core+Nconfirmation）。
- 可用字段数：26

| 字段 | 家族 | 来源 | 覆盖率 | 起始 | 结束 |
| --- | --- | --- | ---: | --- | --- |
| n_income_attr_p | financial_snapshot | income | 100.0% | 2014-01-02 | 2021-12-31 |
| g_alpha_inst_net_buy_20d | growth_signal | alpha_endpoint | 100.0% | 2014-01-02 | 2021-12-31 |
| g_amount_adv20 | growth_signal | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| g_grow_eps_yoy | growth_signal | fina_indicator | 100.0% | 2014-01-02 | 2021-12-31 |
| g_grow_netprofit_yoy | growth_signal | fina_indicator | 100.0% | 2014-01-02 | 2021-12-31 |
| g_grow_opprofit_qoq | growth_signal | fina_indicator | 100.0% | 2014-01-02 | 2021-12-31 |
| g_grow_opprofit_yoy | growth_signal | fina_indicator | 100.0% | 2014-01-02 | 2021-12-31 |
| g_grow_rev_trend | growth_signal | fina_indicator | 100.0% | 2014-01-02 | 2021-12-31 |
| g_grow_roe_yoy | growth_signal | fina_indicator | 100.0% | 2014-01-02 | 2021-12-31 |
| g_mom_return_60d | growth_signal | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| g_qual_margin_trend | growth_signal | fina_indicator | 100.0% | 2014-01-02 | 2021-12-31 |
| g_qual_roe | growth_signal | fina_indicator | 100.0% | 2014-01-02 | 2021-12-31 |
| g_qual_roe_stability | growth_signal | fina_indicator | 100.0% | 2014-01-02 | 2021-12-31 |
| g_val_ep_ttm | growth_signal | daily_basic | 100.0% | 2014-01-02 | 2021-12-31 |
| adj_factor | market_daily | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| amount | market_daily | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| close | market_daily | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| high | market_daily | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| low | market_daily | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| open | market_daily | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| pct_chg | market_daily | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| pre_close | market_daily | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| vol | market_daily | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| volume_ratio | market_daily | market_daily | 100.0% | 2014-01-02 | 2021-12-31 |
| circ_mv | valuation_size | daily_basic | 100.0% | 2014-01-02 | 2021-12-31 |
| total_mv | valuation_size | daily_basic | 100.0% | 2014-01-02 | 2021-12-31 |