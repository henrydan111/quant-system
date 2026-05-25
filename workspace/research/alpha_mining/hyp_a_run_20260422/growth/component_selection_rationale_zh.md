# growth Component 选择说明

- 主题：growth
- 进入本阶段的 Universe：gr_u5, gr_u1
- 硬门槛：覆盖率至少 25%，样本外方向不能明显反着来；高相关 component 必须证明自己有增量信息。
- 目标：先形成可解释的 component 白名单，再交给 recipe search 做组合比较。
- 当前进入 recipe 白名单的 component 数量：13

## gr_u5

- 候选 component 数：13
- 进入白名单数：7
- 角色分布：核心 3，确认 4，执行约束 0

| component | 角色 | coverage | rank_ic | rank_icir | cluster | 说明 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| growth_grow_opprofit_yoy | 确认 | 100.00% | 4.61% | 0.00 | cluster_03 | Operating profit YoY — Phase 1 LS Sharpe +1.58. |
| growth_grow_netprofit_yoy | 核心 | 100.00% | 4.50% | 0.00 | cluster_03 | Net profit YoY growth — Phase 1 LS Sharpe +1.43. Also Hypothesis B core component. |
| growth_qual_roe | 核心 | 100.00% | 3.13% | 0.00 | cluster_08 | ROE level — anchors GARP quality leg. |
| growth_grow_opprofit_qoq | 确认 | 100.00% | 1.32% | 0.00 | cluster_04 | Quarterly operating profit QoQ — Phase 1 LS Sharpe +1.43. |
| growth_grow_eps_yoy | 确认 | 99.97% | 4.38% | 0.00 | cluster_03 | EPS YoY — Phase 1 LS Sharpe +1.51. |
| growth_grow_roe_yoy | 核心 | 99.95% | 4.26% | 0.00 | cluster_03 | ROE YoY growth — Phase 1 LS Sharpe +1.89, highest among growth fundamentals. |
| growth_qual_margin_trend | 确认 | 97.89% | 2.03% | 0.00 | cluster_07 | 4-quarter gross-margin trend slope. |

- 主要淘汰原因：
- 样本外方向稳定性不足。（5 个）
- 覆盖率低于 25%。（1 个）

## gr_u1

- 候选 component 数：13
- 进入白名单数：6
- 角色分布：核心 2，确认 4，执行约束 0

| component | 角色 | coverage | rank_ic | rank_icir | cluster | 说明 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| growth_grow_opprofit_yoy | 确认 | 100.00% | 2.90% | 0.00 | cluster_03 | Operating profit YoY — Phase 1 LS Sharpe +1.58. |
| growth_grow_opprofit_qoq | 确认 | 100.00% | 0.59% | 0.00 | cluster_04 | Quarterly operating profit QoQ — Phase 1 LS Sharpe +1.43. |
| growth_qual_roe | 核心 | 99.98% | 3.56% | 0.00 | cluster_08 | ROE level — anchors GARP quality leg. |
| growth_grow_eps_yoy | 确认 | 99.92% | 2.91% | 0.00 | cluster_03 | EPS YoY — Phase 1 LS Sharpe +1.51. |
| growth_qual_margin_trend | 确认 | 96.40% | 1.18% | 0.00 | cluster_07 | 4-quarter gross-margin trend slope. |
| growth_val_ep_ttm | 核心 | 95.46% | 1.96% | 0.00 | cluster_10 | Earnings yield (1/PE_TTM) — anchors GARP value leg. |

- 主要淘汰原因：
- 样本外方向稳定性不足。（4 个）
- 与更强 component 高相关，且 marginal ICIR 不足 (0.013)。（1 个）
- 与更强 component 高相关，且 marginal ICIR 不足 (-0.122)。（1 个）