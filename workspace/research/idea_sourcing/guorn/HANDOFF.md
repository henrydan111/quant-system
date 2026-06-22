# 果仁 slct 策略库 — 交接包 (HANDOFF)

> **给谁**: 正在改造 strategy/book 层 research 的 session。
> **是什么**: 从果仁网 (guorn.com, 账号 leodan) `slct` 标签导出的 **65 个真实、已部署、unlevered 的 A股/基金策略**——每个都带 **完整定义(recipe) + 用到的因子/指标定义 + 2014–2026 回测表现与明细**。可作为 strategy/book 层的**候选 book 输入** + **复刻对照基准**。
> **怎么用**: 先读 `guorn_strategies_master.json`（下面有 schema）。它把四类信息 join 在了一起；其余文件是深挖明细。

---

## ⭐ 单一入口: [guorn_strategies_master.json](guorn_strategies_master.json)

65 个策略对象，每个已 join：解析后的 recipe + 用到的因子 + 回测指标 + 明细文件路径。Schema（每个 strategy 对象）：

```jsonc
{
  "nn": 12,                          // 1..65, 与回测xlsx文件名前缀、bt_queue顺序一致
  "name": "sm_value",
  "category": "A股 | 北证(BJ) | 多资产轮动(基金) | 场内基金/QDII | 策略组件(component)",
  "recipe": {                        // ← 从策略定义解析出的结构化配方 (book 的构造规则)
    "universe":   {"股票池":"全部股票","指数":"全部","板块":"...","行业":"...","ST":"排除ST","科创板":"排除科创板",...},
    "filters":    [{"indicator":"基础过滤_退市风险_v1(3)","op":"等于","scope":"","value":"0"}, ...],   // 选股域(eligibility)
    "rankings":   [{"indicator":"GrossProfit%AssetsQ","direction":"从大到小","scope":"全部","weight":"1"}, ...], // 打分/排序(alpha)
    "trade_model":{"模型":"II","调仓周期":"1","调仓价格":"09:35","个股仓位范围":"...","备选买入股票数":"...",...},
    "buy_limit":[...], "sell_conditions":[...], "hold_keep_conditions":[...],
    "market_timing":"无 | 自定义仓位公式:If(...)"   // 大盘择时(0/1仓位开关)
  },
  "indicators_used": {
    "custom":          [{"token":"GrossProfit%AssetsQ","base":"...","expr":"(营业收入(单季)-营业成本(单季))/资产总计(单季)"}, ...], // 自定义因子+公式
    "builtin_or_field":["总市值","ILLIQ","真实负债资产率",...],   // 果仁内置/行情/事件指标
    "inline_formulas": ["(营业收入(单季)-refq(营业收入(单季),4))/总市值", ...]   // 排名里直接写的公式
  },
  "backtest": {                      // ← 复刻要对齐的目标 (总收益口径, 含分红)
    "total_return_pct","annual_pct","sharpe","max_drawdown_pct","volatility_pct",
    "info_ratio","beta","alpha_pct","benchmark","benchmark_annual_pct","excess_annual_pct",
    "cost_note","period":"2014-01-02..2026-06-18","return_basis":"总收益(含分红再投资)"
  },
  "files": { "backtest_xlsx":"Knowledge/果仁回测结果/12_sm_value.xlsx", "definition_in":"...json" },
  "definition_text": "投资域：\n股票池：全部股票\n..."   // 原始完整定义(逐字)
}
```

**关键 join 键 = `name`**（65 个名字在所有文件里一致；`nn` = 1..65 与回测 xlsx 文件名前缀一一对应）。

快速扫描用 [strategies_overview.csv](strategies_overview.csv)（nn/name/category/#filters/#rankings/#custom因子/#内联公式/年化/夏普/回撤/基准/超额）。

---

## 文件清单

### A. 策略定义 + 因子定义 (本目录 `workspace/research/idea_sourcing/guorn/`)
| 文件 | 内容 |
|---|---|
| **guorn_strategies_master.json** | ⭐ 上述 join 后的主数据 |
| strategies_overview.csv | 65 行速览表 |
| guorn_slct_strategies.md / .json | 65 策略**原始完整定义**(逐字, 校验和验证无误) |
| backtest_summary.csv | 65 策略回测指标汇总(= 主数据 backtest 段) |
| bt_queue.json | 权威 65 名字顺序(= nn 顺序, 与 xlsx 前缀一致) |
| **指标拆解与分析.md** | 因子分析层: 43 函数语义 + 内置指标定义 + 99 自定义因子按族拆解 + 对接本地系统建议 |
| indicator_reference_auto.md | 每个自定义因子的**精确公式 + 依赖树 + 递归展开**(自动生成、与导出库逐字一致) |
| indicator_mapping.md | 194 命名指标 → 自定义/内置/内联 来源映射 |
| 内联公式85条拆解.md | 85 条内联 `公式()` 逐条拆解 |
| guorn_aichat_indicator_defs.md | 帮助文档未收录、经果仁AI助手确认的内置指标定义(中性化族/ILLIQ/朝阳永续预期/评级族等) |
| resolved_indicators.json / indicator_usage.json / inline_formulas_classified.json | 上述分析的结构化原始数据 |

### B. 回测表现 + 明细 (`Knowledge/果仁回测结果/`)
| 文件 | 内容 |
|---|---|
| `01_*.xlsx` … `65_*.xlsx` | 每策略**完整回测导出**, 11 个 sheet: 收益统计/周收益/收益曲线(每日净值)/年度·月度收益/收益分布/最大回撤统计/月度回撤/交易统计/**交易段持仓清单**/**历史交易记录** |
| _汇总_收益统计.csv | = backtest_summary.csv |
| README.md | 回测导出说明 + caveat |

> **校验**: 65/65 文件齐全、编号连续、名字与顺序 0 不匹配、内容去重 0 重复; 抽查 6 个策略本地 xlsx 数字与网页端实时值逐位一致。

---

## 如何对接 strategy/book 层

每个 guorn 策略 = **一个 book recipe**（选股域 + 打分 + 仓位/调仓 + 择时），可映射为一个 StrategyCandidate：

1. **recipe.filters → Layer-2 universe/eligibility mask**（`基础过滤_*` 这类是排雷, 非 alpha）。
2. **recipe.rankings → 打分因子组合**（多因子等权打分; `weight` 是该排名项权重; `scope` 全部/一级行业内 = 截面 vs 行业内排名)。
3. **recipe.trade_model → 调仓/仓位/成本**（调仓周期、调仓价格 09:35、个股仓位范围、备选买入数）。`return_basis=总收益` → 用本地 **EventDriven** 复刻(它 credit 分红), **勿用 Vectorized 价格收益** 直接比(见 CLAUDE.md §3.3)。
4. **recipe.market_timing → 仓位 0/1 开关**（`Timing()` 迟滞; unlevered, 满仓=1×, 不放大)。
5. **indicators_used → 因子映射**: 用 [指标拆解与分析.md §5](指标拆解与分析.md) 的对接表把果仁因子映到本地 catalog —— 中性化模板↔`cs_zscore`/winsorize、成长同比环比族↔`pit_*_yoy`、剔除涨停隔夜路径动量↔本地隔夜动量、预期/评级族↔`report_rc`。**注意 PIT**: 业绩预告/快报/朝阳永续预期族是 PIT 高危, 必须按公告日对齐(见 [feedback_factors_must_go_through_ledger_qlib])。
6. **backtest → 复刻目标**: 年化/夏普/回撤/超额 是要对齐的数; xlsx 的 `历史交易记录`/`交易段持仓清单` 可做持仓级 diff。

---

## 速览统计
- **构成**: A股 39 · 策略组件 11 · 多资产轮动(基金) 8 · 场内基金/QDII 5 · 北证 2。
- **因子复用**: 79 个不同自定义因子 + 85 个内置/字段。高频自定义: `基础过滤_退市风险_v1`(26)、`CoreProfitQGr%PY`(22)、`ROETTMDiffPQ`(20)、`EpsExclXorQGr%PY`(18)、`指标1指标2中性化`(17)、`GrossProfit%AssetsQ`(15) —— 说明这是一套共享因子底座的 GARP+质量+价量+事件 多因子库。
- **回测(2014–2026, 总收益)**: 年化 2.9% / 中位 32.5% / 160%; 夏普 −0.05 / 中位 1.04 / 2.51。
- **夏普 Top5**: sm_BJ_纯市值_v1 (2.51/160%)、sm_BJ_成长均衡_v1 (2.33/130%)、sm_value (2.15/72%)、ST_大市值_v3 (2.0/55%)、sm_01_成长动量_大盘择时 (1.96/62%)。⚠ 高弹性多来自微盘/北证小市值, 容量与可投资性需另判(参考 memory `project_e_wave_selection_mandate`: 果仁式微盘 gross 回测在 liquid universe 上会塌)。

## ⚠ 必读 caveat
1. **成本不统一**: 各策略用其平台默认成本(单边千分之二或千分之五), 复刻须逐个核对该策略的实际成本设置(在 xlsx `交易统计` sheet 或平台页面)。
2. **sm_noc_纯市值正盈利_v4 用千分之三导出**(默认千分之二因 guorn 缓存 bug 不可用; 差异仅成本档)。
3. **收益=总收益口径**(含分红再投资); leverage 全部 1×(unlevered)。
4. **这些是"策略已验证"≠"本地可复刻/可部署"**: 是 idea source + 对照基准, 不是结论。微盘弹性、容量、PIT 对齐都需本地独立验证。
