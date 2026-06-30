# 量化初筛 → AI 交易员 → 前向纸面实盘 验证 harness

**Date:** 2026-06-28
**Status:** DESIGN — GPT §10 review #1 = REVISE (applied; re-review pending)
> **⚠️ GPT §10 review applied (2026-06-28).** 绑定契约见 [CONTRACTS.md](CONTRACTS.md)。本文档应用:C5/B6 准前向回放=非证据(下文已改) · C6/M2 `ai_final_decider_shadow` 独立分账(与 bounded_overlay 不共享 OOS/prompt/阈值) · C1/M5 源适配器契约(每条文本带 source_published_at/updated_at/retrieved_at/content_hash,fail-closed)。
**Companion:** [BLUEPRINT.md](BLUEPRINT.md)(有界 veto/tilt 那一端)· 本 harness 是"给 AI 更大决策权"那一端

---

## 0. TL;DR

这个思路成立与否,**全押在验证范式上**。AI 的最终决策**无法用历史回测干净验证**(训练截止日前视)。所以
harness = **量化初筛(历史可验证)+ AI 决策层(模板已有)+ 前向纸面实盘(唯一诚实的验证)**。

核心比较(决定 AI 这一层值不值得留):

> **AI-交易员-on-shortlist　vs　纯量化-on-shortlist　vs　等权 buy-and-hold(shortlist)**
> 若 AI ≤ 纯量化 → AI 不加 alpha(只是解释器)。这是诚实的检验,任何历史回测都给不了。

---

## 1. 三个已核实模板(及各自的污染警告)

- **AlphaAgents** [2508.11152](https://arxiv.org/abs/2508.11152)(BlackRock)✅ 核实 — **决策层模板**:
  - 三 agent:**Fundamental**(10-K/Q + RAG)、**Sentiment**(新闻+评级变动,reflection 提示)、**Valuation**(OHLCV,年化收益/波动)。
  - **辩论**:AutoGen round-robin group chat,每个 agent 至少发言两次,辩到共识,发 `TERMINATE`。
  - **风险偏好**:纯靠 prompt(risk-averse vs risk-neutral;risk-seeking 与 neutral 几乎无异被剔)。
  - ⚠️ **它自己的回测是被污染的**:2024-02 起 4 个月、15 只科技股、同一池既当选股池又当基准,**落在 GPT-4o 训练知识内**,无 OOS 讨论。架构好,验证弱——正是本 harness 要修的。
- **FinMem** [2311.13743](https://arxiv.org/abs/2311.13743)(开源 github pipiku915)🔎 检索级 — **记忆模板**:
  - Profile(角色+风险性格)+ **分层 Memory**(短/中/长,带衰减,按 recency×relevance×importance 检索,可调"认知跨度")+ Decision→buy/sell/hold。
  - 可迁移的关键点:**让 agent 在前向运行中累积"决策→结果"经验**(在前向跑里"学习",而非靠记历史)。
- **StockBench** [2510.02209](https://arxiv.org/abs/2510.02209)(清华)✅ 核实 — **干净的前向评测协议**(本 harness 的核)。

---

## 2. StockBench 协议(照抄它的无污染做法)

- **无污染窗口**:评测期 **2025-03-03 ~ 06-30**,明确"落在主流 LLM 训练截止之后";作者声明"持续更新交易环境以避开当代 LLM 语料"。
- **每日输入**(PIT):组合概览 + 持仓 + 过去 7 天历史动作 + 开盘价;选中标的再给基本面(市值/PE/股息/52周高低);**新闻=过去 48 小时内、最多 5 条**,经带时间限制的搜索 API。**四步强制时序:概览→深析→决策→执行。**
- **动作空间**:每日开盘,increase / decrease / hold;按开盘价把美元目标换算成股数;超流动性则报错要求修正。
- **指标**:最终收益、最大回撤、Sortino;**基线=等权 buy-and-hold**。
- **结果(诚实)**:14 模型,基线 +0.4% / −15.2%DD;最佳 Kimi-K2 +1.9%,最差 −2.8%。**短窗、近平、离散大——弱证据。**

---

## 3. Harness 架构(三段)

### Part 1 · 量化初筛(历史可验证,走你现成机器)
- 金股池 ∩ 流动带 → approved 因子(市值中性、边际贡献)→ 每期 top-K 候选 + 量化分。
- **这一段照旧过 sealed-OOS**(历史能验)。产出 PIT shortlist `{date → [(code, quant_score)]}`。

### Part 2 · AI 决策层(AlphaAgents/FINCON 模板)
- 对 shortlist 每只:Fundamental / 分析师-revision(用你已有 report_rc)/ Valuation / 宏观-政策 各出**结构化观点**(PIT 输入)。
- round-robin 辩论 → 共识 → **BUY/SELL/HOLD + 信心 + 理由**(可叠 risk persona)。
- 叠 FinMem 式 **Memory**:前向跑里累积"决策→结果",按 recency×relevance×importance 检索。
- 输出:对量化 shortlist 的**逐名决策 + sizing tilt + veto**。**prompt+模型版本冻结并哈希。**

### Part 3 · 前向纸面实盘验证(命门)
- **两种模式**:
  - (a) **准前向回放 = 非证据(C5/B6)**:仅用于接口/延迟/审计/执行模拟测试,**绝不**作为 alpha/OOS/AI 交易员业绩;干净证据只有 (b)。
  - (b) **真前向 paper-live**:从**当下边缘**起,t 时刻记录决策、t+h 实现结果,**决策一经记录不可重跑**(StockBench"持续更新"、Autonomous Market Intelligence"时间边缘"的做法)。
- **执行**:用你的**事件驱动引擎**当纸面账户(真实 A 股成本、T+1、涨跌停)。
- **三方比较(决定去留)**:AI-on-shortlist　vs　纯量化-on-shortlist　vs　等权买入持有(shortlist)。
- **指标**:最终收益 / 最大回撤 / Sortino(StockBench 集)+ 你的标准指标。

---

## 4. 反前视铁律(harness 的合法性全靠这几条)

1. **数据 feed 严格 PIT**:任何新闻/分析师数据按**发布时间 ≤ 决策时间**过滤(报 published-time,非事件时间)。
2. **决策模型 cutoff 记录在案**;准前向窗必须晚于它;真前向天然晚于任何模型。
3. **决策不可变**:t 记录后绝不回改、不重跑(否则就成了拟合)。
4. **冻结 prompt+模型哈希**(prompt/模型漂移 = 策略漂移,要重新预注册)。
5. **预注册**(像你的 sealed-OOS):跑之前先注册决策规则 + shortlist 构造 + 指标 + 证伪线。**前向日志就是 OOS,实时一次性花掉。**
6. MLflow 全程记录:每次决策的输入快照、prompt/模型版本、结果。

---

## 5. 你系统的实操约束(必须先解决的)

- ⚠️ **日历冻结在 2026-02-27**(CLAUDE.md),今天 2026-06-29 → **真前向 paper-live 需要先恢复日度数据接入**(Tushare 跑过冻结点)。否则只能跑"准前向",而你的数据止于 2026-02-27,窗口很短。**这是上线前的硬前置。**
- 事件驱动引擎 = 现成的纸面执行器(总收益、T+1、涨跌停),直接复用。
- 成本:K 名 × agent 数 × 调仓次数的 LLM 调用。月频 ~30 名 × 4 agent × 辩论 = 可控。
- 这是一个**新的 orchestrator profile / harness**,**与你 sealed-OOS-on-history 的 profile 并列但分开**——因为它前向验证,不在历史上验。

---

## 6. 预注册的证伪线(跑之前写死)

- **主判据**:前向 N 期后,AI-on-shortlist 的 Sortino / 回撤**显著优于纯量化-on-shortlist**,净成本后。
- **若 AI ≤ 纯量化** → AI 决策层降级为"解释/风控工具",**不作为 alpha 源**(诚实接受)。
- **窗口**:前向证据天然慢——预设最短观察期(如 ≥6-12 月真前向 或 ≥1 个完整 regime),不到不下结论。

---

## 7. 分步落地

1. **Part 1** 先跑通(= Phase 0 金股池量化母信号,你已在路上)。
2. **恢复日度数据接入**(解除冻结前置),否则前向无从谈起。
3. **Part 2** 决策层:先 3 个 agent(fundamental / 分析师-revision / valuation)+ 简单辩论,prompt+模型冻结。
4. **Part 3** 前向 harness:预注册 → 准前向**仅管道 sanity(非证据)** → 真 paper-live 起跑(唯一证据)→ 三方比较。
5. 固化成 `ai_trader_forward` profile + MLflow。

---

## 8. 诚实的预期

- StockBench 的无污染窗(近平、82 天)= 弱混合证据(最佳 +1.9%、有亏损者)。**预期 AI 这一层独立 alpha 很少**,价值大概率在风控/解释/叙事,而非超额。
- **前向证据慢**:要等真实时间累积,几个月起。
- **harness 的价值不是保证赚钱,而是让你诚实地知道答案**——这是任何历史回测都给不了的。

**本 harness 在写 Part 2/3 新基建前,过 §10 GPT 跨审。**
