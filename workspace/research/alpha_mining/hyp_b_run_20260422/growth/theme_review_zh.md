# growth 主题复盘

- 主题假设：A 股成长股策略：单因子成长信号在 leakage-fix 后普遍偏弱（Phase 1 quick-kill 显示无 A/B 级），但通过(1)机构席位确认 + 多源利润增长 + 质量/动量验证 (Hyp A) 或 (2) GARP 多元复合 (Hyp B) 仍可能挖掘出可交易的成长溢价。Layer 2 用 mainboard + 市值/流动性/盈利门槛过滤，Layer 3 让 signal_search 在 8 个 Hyp A 组件 + 5 个 Hyp B 组件中搜索结构变体（equal-weight + 1core+Nconfirmation）。
- Universe 入围：gr_u5, gr_u1
- Component 白名单数量：13
- Recipe 候选数：180
- Event-driven 确认数：2

## 最优向量化结果

- 最优 Universe / Recipe：`gr_u5` / `auto_growth_01`
- 组件：`growth_grow_netprofit_yoy` + `growth_grow_opprofit_qoq`
- 样本外相对超额：35.83%
- holdout 相对超额：-
- 最差回撤：-20.26%
- 平均换手：19.35%

## Event-Driven 确认

- 最优事件驱动组合：`auto_growth_19`（gr_u5）
- 相对超额：106.00%
- 最大回撤：-59.80%
- 平均换手：4.19%
- 交易笔数：4203