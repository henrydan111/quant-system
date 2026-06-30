# 专业投资机构工作流 — AI 增强 A 股系统的制度骨架

**Date:** 2026-06-28
**Status:** DESIGN — GPT §10 review #1 = REVISE (applied; re-review pending)
> **⚠️ GPT §10 review applied (2026-06-28).** 绑定契约见 [CONTRACTS.md](CONTRACTS.md)。本文档应用:C10/M3 单人最小可行治理(独立挑战 agent 只可评论、不可改研究工件/OOS 标签/审批态)。审核确认 separation-of-duties 是 load-bearing,非过度设计。
**Companion:** [BLUEPRINT.md](BLUEPRINT.md) — the AI multi-agent architecture sits *inside* Stage 2 +
Stage 7 of this workflow, it is NOT the whole workflow.

---

## 0. 核心论点(为什么用机构视角)

一家真实的系统化基金,赚钱靠的不是某个聪明信号,而是一套**制度**:

> **职责分离(separation of duties)+ 多道独立闸门(gates)+ 归因反馈(attribution loop)。**

这套制度的全部目的,是系统性地防止一件事——**研究员给自己的研究打分**(self-marking / 过拟合自欺)。
这正是你 sealed-OOS 治理已经在做的事;机构视角只是把它推广到**整条价值链**。

**对单人操盘者的关键含义:** 你雇不起研究团队、PM、交易台、独立风控、投委会。
**AI 多 agent 层真正的价值,是模拟你请不起的那些「台子和委员会」——尤其是独立质疑 / 风控职能。
它的产出是治理与独立挑战,不是 alpha。** 这一句把 TradingAgents 彻底摆正:它不是选股神器,
它是"单人也能拥有的制度分离"。

---

## 1. 四层 / 九阶段的机构流水线

机构把投资流程切成互相独立、各自问责的**台子(desk)与委员会(committee)**,中间用**工件(artifact)**
交接、用**闸门(gate)**把关。两条节奏:**慢环**(研究→资本配置,月/季)与**快环**(预测→执行→风控,日/实时)。

### Layer A — Alpha 工厂(慢环)

**Stage 1 · 数据与 Universe 治理 [Data Desk]**
- 职能:PIT 正确、无幸存者偏差、供应商对账、可投 universe + 容量分层。
- 工件:干净的 PIT 面板 + universe 掩码 + 容量标签。
- 闸门:数据完整性 / PIT 回归(你的 `run_daily_qa`、provider attestation)。
- 谁做:数据工程(你已建)。**AI 不进入**(确定性,绝不能让 LLM 碰原始数据对齐)。

**Stage 2 · Alpha 研究 [Research Desk]**
- 职能:假设→信号→IS 验证;多类分析师视角(基本面/量化/行业/宏观)。
- 工件:候选信号 + IS 证据 + 衰减/容量/正交性文档。
- 闸门:IS-only `factor_lifecycle` gate(draft→candidate)。
- 谁做:量化研究 + **AI 多分析师 persona(blueprint Layer-3)**。
- **制度原则:研究员只能"提议",不能"批准"自己的信号。**

**Stage 3 · 独立验证 / Sealed-OOS [Model Validation]**
- 职能:对 Stage-2 的产物做**独立**的样本外检验(银行里这叫独立的 Model Validation 团队)。
- 工件:sealed-OOS 判决 + promotion evidence。
- 闸门:**sealed-OOS gate**(candidate→approved)——你的皇冠明珠,一次性、封存、不可复测。
- 谁做:治理系统(自动、与研究员物理隔离)。**AI 不在此处拥有批准权。**
- **制度原则:批准信号的主体必须独立于产生信号的主体。**

### Layer B — 组合引擎(桥)

**Stage 4 · 预测合成 + 风险模型 [Strategist]**
- 职能:把多个 approved 信号合成**截面预期收益向量**;构建**风险模型**(因子协方差 + 特异风险)。
- 工件:`E[r]` 向量 + 协方差矩阵。
- 制度原则:**"合成"是独立于"单信号研究"的学科**(组合层的过拟合≠信号层的过拟合)。
- 现状:**你这层是空的**(`portfolio_risk` 休眠,`predict_portfolio_risk→0.05`)。

**Stage 5 · 组合构建 [Portfolio Manager]**
- 职能:`E[r]` + 风险 + 成本 + 约束(持仓/行业/换手/容量,**1× 不加杠杆**)→ 目标组合。
- 工件:目标权重向量。
- 谁做:优化器(cvxpy)。**制度原则:PM 对「账本」问责,研究员对「信号」问责——两者分离。**
- 现状:**未建**(目前是 equal-weight top-K 代替了真正的组合构建)。

### Layer C — 执行与控制(快环)

**Stage 6 · 执行 [Execution Desk]**
- 职能:目标组合 → 订单 → 成交,T+1 / 涨跌停 / 滑点 / 冲击成本感知。
- 工件:成交记录。
- 谁做:你的事件驱动引擎(研究态)/ 实盘券商 API(真实态,你尚无)。
- **制度原则:执行独立于 PM**(避免"为了好看而挑执行价")。

**Stage 7 · 独立风控 + 合规 [Risk Officer, 有否决权]**
- 职能:**事前**限额(单票/行业/集中度/流动性)+ **事中**回撤熔断 + 合规。
- 工件:放行 / 削减 / 否决 决定 + 理由。
- 谁做:风控规则 + **AI 对抗式风控 agent(魔鬼代言人,blueprint 的 veto 角色)**。
- **制度原则:风控独立于 PM 且能否决。这是机构里唯一能压过 PM 的人。**

### Layer D — 反馈与治理

**Stage 8 · 业绩与风险归因 [Performance & Risk Attribution]**
- 职能:收益拆成 因子 vs 特异、哪些 bet 赚/亏;live-vs-backtest 衰减监控;regime 监控。
- 工件:归因报告 + 衰减告警。
- 谁做:`result_analysis`(部分已建;**专门的归因尚弱**)。
- **制度原则:你必须知道「为什么」赚/亏,否则无法区分运气与 edge。** 反馈回 Stage 2 与 Stage 9。

**Stage 9 · 投委会 / 资本配置 [Investment Committee]**
- 职能:哪些策略**拿资本**、跨策略**配重**、paper→live→scale 的晋级、杀掉衰减策略。
- 工件:资本配置决定 + 策略生命周期状态。
- 谁做:`strategy_registry` + 晋级闸门(**目前空的**)。
- **制度原则:资本配置是独立于 alpha 生成的元决策。**(这就是你 [project_state] 里
  `capital_allocation_buildout` 路线图要补的层。)

---

## 2. 两条环路(机构刻意把它们分开)

- **慢环(月/季):** Stage 1→2→3→9 —— Alpha 工厂 + 投委会。研究与资本配置在这里,节奏慢、要封存。
- **快环(日/实时):** Stage 4→5→6→7→8 —— 预测→构建→执行→风控→归因。账本每天在这里跑。
- 把慢环混进快环 = 用市场结果驱动研究迭代 = 样本外污染(§7.3)。**两环之间只能通过 Stage-3 闸门
  和 Stage-9 配置决定单向连接,绝不让快环的盈亏直接回流改写慢环的研究。**

---

## 3. 职责分离矩阵(为什么这些必须独立)

| 必须独立的两个职能 | 若不独立会发生什么(失效模式) |
|---|---|
| 研究(出信号) vs 验证(批信号) | 研究员调参直到 OOS 好看 → 过拟合当成 edge(你已用 sealed-OOS 防住) |
| 单信号研究 vs 信号合成 | 组合层偷偷再挖一遍 → 二次过拟合 |
| PM(管账本) vs 执行(下单) | 挑有利执行价美化业绩 |
| PM vs 风控 | 没人能在 PM 上头喊停 → 回撤失控 |
| Alpha 生成 vs 资本配置 | 把钱押在最近最热的策略 → 追逐衰减 |

**单人困境:** 你一个人同时是这 5 对里的两边。**解法不是"更自律",而是把分离编码进系统边界
(模块/闸门/封存工件)+ 让 AI agent 扮演那个独立的对家。** 这是 multi-agent 在你这儿存在的根本理由。

---

## 4. AI agent 在这条流水线里的确切位置

✅ **该用 AI 的地方(治理与视角,非 alpha):**
- Stage 2:多分析师 persona(基本面/行业/宏观/政策/地缘)——补量化看不见的叙事维度,输出**结构化观点向量**。
- Stage 7:对抗式风控 agent / 魔鬼代言人——专门被 prompt 去**反驳**一个持仓,凑够多数反对则削减/否决。
- Stage 8:归因解释 + 衰减叙事(把数字翻译成人能审计的理由)。
- 横向:研究生产力(idea sourcing、文档结构化抽取、研报/政策正文摘要)。

❌ **绝不能用 AI 的地方:**
- Stage 1 数据对齐(确定性,LLM 记忆 = 泄漏)。
- Stage 3 批准信号(独立验证不能让被验证方的同类主体批)。
- 直接对具名股票做涨跌/择时预测(训练截止日 = lookahead,本次深研 7 源共识)。
- 让 AI 凭空生成量化没surface 的票(它只能 veto / 有界 tilt)。

---

## 5. 映射到你现有系统(什么有、什么缺)

| Stage | 机构职能 | 你的模块 | 状态 |
|---|---|---|---|
| 1 | Data Desk | `data_infra`(PIT 账本/Qlib/QA) | ✅ 成熟 |
| 2 | Research Desk | `alpha_research`(因子库/lifecycle) + **AI 层(新建)** | ✅ 因子成熟 / 🆕 AI 待建 |
| 3 | Model Validation | `research_orchestrator`(sealed-OOS/release_gate) | ✅ 皇冠明珠 |
| 4 | Strategist(预测+风险模型) | `portfolio_risk` | ❌ **休眠** |
| 5 | PM(组合构建) | `portfolio_risk`(优化器) | ❌ **未建**(现为 equal-weight) |
| 6 | Execution | `backtest_engine`(事件驱动) | ✅ 研究态成熟 / 实盘态无 |
| 7 | Risk Officer | — + **AI 对抗风控(新建)** | ❌ 独立风控未建 / 🆕 AI 待建 |
| 8 | Attribution | `result_analysis` | 🟡 部分(专门归因弱) |
| 9 | Investment Committee | `strategy_registry` + 晋级闸门 | ❌ **空** |

> **重要收敛:** 从机构视角独立推导出的缺口(Stage 4/5 组合引擎、Stage 7 独立风控、Stage 9 资本配置),
> **和你 [project_state] 里 `capital_allocation_buildout` 路线图(PR1 风险模型→PR2 优化器→PR3 策略生命周期)
> 完全是同一批**。两条独立推理收敛 = 这就是真正的下一块短板,不是 AI 层。

---

## 6. 具体实例化(把 金股 + 价值 baseline 灌进这条流水线)

1. **Stage 1:** 金股池(PIT day-4 锚)∩ 流动性/容量带 → universe 掩码。
2. **Stage 2:** approved 因子(市值中性、边际贡献)给截面分;AI persona 给行业/政策 tilt + 风险旗。
3. **Stage 3:** 组合信号过 sealed-OOS(就是 Phase-0 母信号测试的延伸)。
4. **Stage 4-5:** 风险模型 + 优化器(待建)→ 目标组合(1×,不加杠杆);**当前先用 equal-weight top-K 占位**。
5. **Stage 6:** 事件驱动引擎执行(总收益口径)。
6. **Stage 7:** 独立风控限额 + AI 魔鬼代言人对每个持仓挑刺。
7. **Stage 8:** 归因——edge 来自因子还是金股池?微盘还是流动域?
8. **Stage 9:** 投委会决定这个策略拿多少资本、是否晋级 paper→live。

---

## 7. 落地次序(与 BLUEPRINT 的 Phase 对齐)

- **现在 = Phase 0**(Stage 1→2量化→3):金股池 + 量化母信号过 sealed-OOS。**不需要 AI,不需要组合引擎。**
- **接着补 Stage 4-5 组合引擎**(= `capital_allocation_buildout` PR1-2):这是比 AI 层更优先的真短板。
- **再上 Stage 2 AI persona + Stage 7 AI 风控**(BLUEPRINT Phase 1-2)。
- **最后 Stage 9 投委会 / 策略生命周期**(= PR3)。

**这份工作流本身在 Phase 1-2 写新基建前,需过 §10 GPT 跨审。**
