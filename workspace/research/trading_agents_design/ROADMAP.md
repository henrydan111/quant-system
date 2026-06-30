# ROADMAP — AI 增强 A 股系统(plan of record)

**Date:** 2026-06-28
**Status:** DESIGN / 计划基准 — GPT §10 review #1 = **REVISE**(所有 finding 已接受并应用 → [CONTRACTS.md](CONTRACTS.md));re-review pending
**⚠️ 绑定契约**:[CONTRACTS.md](CONTRACTS.md)(C1–C13)在冲突时**优先于**本路线图;文献引用受 [evidence_registry.md](evidence_registry.md) 约束。
**Sequences:** [BLUEPRINT.md](BLUEPRINT.md) · [INSTITUTIONAL_WORKFLOW.md](INSTITUTIONAL_WORKFLOW.md) ·
[HARNESS_FORWARD_AI_TRADER.md](HARNESS_FORWARD_AI_TRADER.md) ·
[INTEGRATION_RDAGENT.md](INTEGRATION_RDAGENT.md)(**PARKED** — 见下)

---

## 0. 组织逻辑(决定顺序的三条原则)

1. **地基先行**:三条路共用一个量化地基(Phase 0,无 AI),先跑出可信证据。
2. **真短板优先于 AI**:机构视角 + `capital_allocation_buildout` 两条独立推理都指向**组合引擎**是比 AI 更大的缺口 → Phase 1 排在所有 AI 之前。
3. **AI 按 ROI 排序、按证据设闸**;治理(sealed-OOS / no-leverage / §10 / §6.1 / MLflow)贯穿。

**本轮对计划的两处修订:**
- ❌ **删除 RD-Agent AI 因子挖掘**(原 Phase 2)→ 文档 [INTEGRATION_RDAGENT.md](INTEGRATION_RDAGENT.md) **保留为 PARKED**(未来可复活,当前不在主线)。
- ⬆️ **AI 分析师层提为重头戏并深化**(原 Phase 3 → 现 Phase 2),**引入多源外部文本**(Tushare 新闻 + 研报 + 公告 + 政策),不再只依赖本地结构化数据。

---

## 1. 分阶段(目标 · 闸门 · 依赖 · AI/收益)

### Phase 0 · 量化母信号(地基,无 AI)
- **目标**:金股池 ∩ 流动带 → approved 因子(市值中性、边际贡献)→ 月度 top-K,事件驱动总收益、真实成本、**1×**,对比宽基 + 等权金股。
- **闸门(金股生死)**:券商预筛若对量化零增量(打不过 quant-on-broad)→ 弃金股池,改 universe。
- **C3(B3)金股 PIT universe**:`golden_stock_universe(date)` = PIT 布尔掩码,只含 `published_at ≤ decision_time` 的推荐事件,**保留退市/停牌/改名/ST/合并**名;走现成 survivorship 基建,**不从当前 vendor 表重建**;可交易性只在执行层。
- **C9(M7)报告纪律**:Phase 0 只报 IC/RankIC/ICIR/单调/换手/分位 = 研究诊断;**Phase 1 事件驱动总收益(T+1/涨跌停/停牌/分红/成本/1×)之前不得声称可部署收益**。
- **依赖**:无(现成机器)。
- **AI/收益**:无 AI。**高置信 · 地基**。

### Phase 1 · 组合引擎(真短板,无 AI)
- **目标**:唤醒 `portfolio_risk` —— 风险模型(因子协方差+特异风险)+ 优化器(cvxpy,1× gross,换手/持仓/行业约束,成本内生)。= `capital_allocation_buildout` PR1-2。
- **闸门**:优化构建净换手后是否跑赢同信号 equal-weight top-K(Sharpe/回撤)?
- **依赖**:Phase 0 信号。
- **AI/收益**:无 AI。**高置信 · 最高杠杆**(信号→可部署账本)。

### Phase 2 · 多源文本 + AI 多分析师层(重头戏,深化)
两个子项目,数据基建先于 agent。**兑现最初愿景**(收集消息源 → AI 总结 → 模拟多类分析师 → 辅佐决策)。
> **绑定契约**:C1 文本可见时点(`visible_at`,trade_date 不算)+ C5 源适配器 · C2 LLM 文本因子两类证据标签(historical=仅管道 / clean=严格晚于模型 cutoff,前向/post-cutoff)· C7 叠加上限 · C8 代码/面板契约 · C12 分析师 typed 输出。**历史文本基本不可做 alpha 验证(无 PIT 存档)→ 干净路径是前向。**

**2A · 多源文本数据基建(§6.1 治理,无 AI)**
- **硬前置 ⚠️**:**Tushare 文本数据需额外权限/积分**(doc-142「大模型语料专题」:`research_report` / `news` / `major_news` / `npr` / `anns_d` 等)——**先取得访问权,且每个接口接入前按 §6.1 读接口正文**(字段/限量/可见时点),记入 data_dictionary。
- **源**(层级):研报 `research_report`(个股+行业,★trade_date)· 公告 `anns_d`(个股,★ann_date+rec_time)· 长新闻 `major_news`(★pub_time)· 快讯 `news` · 政策库 `npr`(宏观,★pubtime)· 货币政策 `monetary_policy` · 新闻联播 `cctv_news` · 互动易 `irm_qa_sh/sz`。本地已有:`report_rc`/`forecast`。
- **核心难点——文本可见时点 PIT**(新 PIT 类型):每条文本带 `visible_time`(=★字段),**AI 只能消费 visible_time ≤ 决策日的文本**(文本版 `Ref(...,1)`);研报的 `trade_date` 是否真可见日**须读正文核**。
- **新存储**:文本不进 Qlib 数值 provider → 独立文本/文档库(parquet + 可选 embedding 索引),按 (ts_code/板块/宏观, visible_time, source) 组织。当前零文本存储。
- **反操纵**(承接 KOL 深研 memory `research_kol_sentiment_altdata_verdict`):研报/分析师 > 新闻 > 论坛;A 股水军/黑嘴 + 情绪→价格延迟;**edge 在抽取方法**;预期 net/流动域会塌。

**2B · AI 多分析师层(agent)**
- 2A 的 PIT 文本 → 按个股/行业/宏观检索 → persona agent(基本面/行业/宏观/政策/地缘/情绪),**各出结构化观点(分数+方向+证据+信心)**;"AI 收集+总结"压成**个股摘要 + 行业摘要**(分行业级/个股级)。
- **两条产出路径**:① **文本→因子**(可历史验证)→ 走 factor_lifecycle **sealed-OOS**(From-Text-to-Alpha 范式,验正交);② **有界叠加** tilt+veto(BLUEPRINT Layer-3)。
- **PIT 防火墙**:AI 只对给定的、visible_time 受控文本做**抽取/摘要**(安全),不靠记忆;AI **判断**部分受训练截止重叠困扰 → 纯抽取因子走 sealed-OOS,判断走前向(Phase 3);冻结 prompt+模型+检索配置哈希。
- **闸门**:文本因子过 sealed-OOS 且对 approved 集有边际贡献;叠加层净成本后改善回撤/Sortino。
- **依赖**:Phase 0(叠加的基)+ 2A 数据权限 + §10 跨审。**历史文本(≤2026-02-27)即可做 sealed-OOS,不需解冻日历。**
- **AI/收益**:用 AI。**中(治理/解释)· 低-中(alpha)**;目标先定为"产出能过 sealed-OOS 的文本因子 + 可解释观点",**不是"AI 选股 alpha"**。
- **规模诚实**:这是全规划最大单块工程(百万行级文本接入 + 多 agent + LLM 成本 + 验证难)。

### Phase 3 · AI 交易员前向 harness(最速、最慢、最不确定)
- **目标**:量化初筛 → AI 决策层(AlphaAgents 辩论 + FinMem 记忆)→ 前向纸面实盘(StockBench 无污染协议)。详见 [HARNESS_FORWARD_AI_TRADER.md](HARNESS_FORWARD_AI_TRADER.md)。
- **硬前置 ⚠️**:**解除日历冻结**(恢复 Tushare 日度接入,跑过 2026-02-27)+ 实时文本。
- **C5(B6)**:**准前向回放 = 非证据**(仅接口/延迟/审计/执行模拟测试);AI 最终决策唯一证据 = 预注册前向 paper-live(不可变决策日志 + 冻结 prompt/模型/工具哈希 + 决策前快照)。
- **闸门**:AI-on-shortlist vs 纯量化 vs 等权买入持有,前向 ≥6-12 月;AI ≤ 纯量化 → 降级为解释器。
- **依赖**:Phase 0/1/2 + 实时数据 + §10。
- **AI/收益**:用 AI。**低 · 慢**——唯一诚实验证 AI 最终决策的路。

### PARKED · RD-Agent AI 因子挖掘
- 文档 [INTEGRATION_RDAGENT.md](INTEGRATION_RDAGENT.md) 保留;当前**不在主线**(用户本轮决定先不做 AI 因子挖掘)。未来若 Phase 2 受阻或需更多候选因子可复活。
- **IPO(即将上市公司,Option B)= `PARKED_NON_EVIDENTIARY`(C4/M2)**:任何文档/README/CLI/报告**不得**把 IPO alpha 描述为 active;解封需 C4 申报人 ledger(含被拒/撤回/延迟申报人 + 上市后执行约束)。

---

## 2. 横切前置与治理

- **数据前置**:① **Tushare 文本权限/积分**(Phase 2A 闸)② **解冻日历 + 日度接入**(Phase 3 闸)。
- **治理**:§10 GPT 跨审(新基建前)· sealed-OOS 一次性 · **no-leverage(1×)** · §6.1 先读接口正文再 fetch · MLflow 全程 · project_state 更新。
- **m2 烟雾测试**:每阶段推进前跑 `make validate-research-governance`(执行该目标阶段相关的 PIT / universe / OOS / 面板契约 / 源适配器 / 契约矩阵 测试)。

---

## 3. 决策点 / 下车口

- **Phase 0 后**:金股无增量 → 改 universe(非失败)。
- **Phase 1 后**:已有**完整、可部署、零 AI 的个人量化系统**——**可在此停**,AI 当可选探索。
- **Phase 2 数据权限拿不到 / 文本因子全军覆没**:Phase 2 降级或暂停,0/1 不受影响。
- **Phase 3 任一闸门不过**:AI 降级为解释/风控工具,诚实接受"AI 不加 alpha"。

---

## 4. 诚实的价值排序

| | 置信 | 杠杆 | 用 AI |
|---|---|---|---|
| **Phase 0 母信号** | 高 | 地基 | 否 |
| **Phase 1 组合引擎** | 高 | **最高** | 否 |
| Phase 2 文本+AI 分析师 | 低(alpha)/ 中(治理) | 低-中 | 是 |
| Phase 3 交易员 harness | 低 | 低 | 是 |

> **最该听进去:下一步最大价值增量在 Phase 0-1(零 AI)。** Phase 2-3 是证据驱动的探索;跑出来顺带成为将来窄版平台(Path 2)的差异化故事,跑不出你也已有 Phase 1 的可部署系统。

---

## 5. 护栏(不会做)

不加杠杆(headline 永远 1×)· 不把 AI 当主信号 · 不让 AI 碰 sealed-OOS 批准 · 不用历史回测验 AI 最终决策 · 不在 Phase 1 出证据前谈对外平台/卖 alpha · 不跳闸门 / 不复用 OOS / 不手搓 PIT 对齐 / 不在读接口正文前 fetch Tushare。

---

**本路线图 + 4 份设计文档,一并过 §10 GPT 跨审后,方动 Phase 1+ 新基建。**
