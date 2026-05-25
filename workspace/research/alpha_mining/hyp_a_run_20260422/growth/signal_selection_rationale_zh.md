# growth Signal 选择说明

- 主题：growth
- 规则：每个 recipe 至少包含 1 个核心 component，可再叠加确认项和执行约束，第一版统一等权。
- topk 搜索范围：[20, 50]
- 调仓频率搜索范围：[5, 10]

## 最优结果

- 当前最优组合：`auto_growth_01`，来自 `gr_u5`。
- 组件：`growth_grow_netprofit_yoy` + `growth_grow_opprofit_qoq`
- 参数：topk = 20，rebalance_days = 10
- 中位样本外相对超额：35.83%
- 中位 holdout 相对超额：-
- 最差 fold 回撤：-20.26%
- 平均换手：19.35%
- 设计说明：自动组合：1 个核心 component + 1 个确认 component。

## 前十名配方

| 排名 | Universe | Recipe | 组件 | topk | 调仓天数 | 样本外相对超额 | holdout 相对超额 | 最差回撤 | 换手 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | gr_u5 | auto_growth_01 | growth_grow_netprofit_yoy + growth_grow_opprofit_qoq | 20 | 10 | 35.83% | - | -20.26% | 19.35% |
| 2 | gr_u5 | auto_growth_19 | growth_grow_opprofit_qoq + growth_grow_roe_yoy | 20 | 10 | 32.82% | - | -19.08% | 19.13% |
| 3 | gr_u5 | auto_growth_25 | growth_grow_opprofit_qoq + growth_grow_roe_yoy + growth_qual_margin_trend | 20 | 5 | 32.50% | - | -20.68% | 17.98% |
| 4 | gr_u5 | auto_growth_07 | growth_grow_netprofit_yoy + growth_grow_opprofit_qoq + growth_qual_margin_trend | 20 | 5 | 30.62% | - | -20.81% | 17.82% |
| 5 | gr_u5 | auto_growth_01 | growth_grow_netprofit_yoy + growth_grow_opprofit_qoq | 20 | 5 | 29.23% | - | -21.65% | 11.91% |
| 6 | gr_u5 | auto_growth_06 | growth_grow_eps_yoy + growth_grow_netprofit_yoy + growth_grow_opprofit_qoq | 20 | 5 | 29.07% | - | -25.86% | 11.06% |
| 7 | gr_u5 | auto_growth_06 | growth_grow_eps_yoy + growth_grow_netprofit_yoy + growth_grow_opprofit_qoq | 20 | 10 | 26.58% | - | -25.46% | 18.70% |
| 8 | gr_u5 | auto_growth_05 | growth_grow_netprofit_yoy + growth_grow_opprofit_qoq + growth_grow_opprofit_yoy | 20 | 10 | 26.27% | - | -22.88% | 20.00% |
| 9 | gr_u5 | auto_growth_19 | growth_grow_opprofit_qoq + growth_grow_roe_yoy | 20 | 5 | 25.75% | - | -20.59% | 11.38% |
| 10 | gr_u5 | auto_growth_05 | growth_grow_netprofit_yoy + growth_grow_opprofit_qoq + growth_grow_opprofit_yoy | 20 | 5 | 25.42% | - | -24.01% | 11.91% |

## 按 Universe 看最优 Recipe

- `gr_u5`：最佳 recipe 是 `auto_growth_01`，样本外相对超额 35.83%，holdout 相对超额 -。
- `gr_u1`：最佳 recipe 是 `auto_growth_16`，样本外相对超额 8.99%，holdout 相对超额 -。