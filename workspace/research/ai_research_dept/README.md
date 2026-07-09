# 虚拟 AI 投研部 — 文档索引 · 跨文档 Self-Review 记录 · 合并路线图

**Date:** 2026-07-08 · 全套 DESIGN(§10 GPT 跨审前不动代码)

## 1. 文档索引

| # | 文档 | 内容 | 状态 |
|---|---|---|---|
| 一 | [VIRTUAL_RESEARCH_DEPT_DESIGN_v1.md](VIRTUAL_RESEARCH_DEPT_DESIGN_v1.md) | 分析师层:编制/工作流/反幻觉栈/评分体系/六问总答 | DESIGN |
| 二 | [INTEL_CENTER_DATA_LAYER_v1.md](INTEL_CENTER_DATA_LAYER_v1.md) | 数据层全量盘点 · **§2A 通用信息层·打标·检索** · 七情报产品 · **§6 本地 Web 平台** | DESIGN |
| 三 | [RESEARCH_REPORT_FULLTEXT_PIPELINE_v1.md](RESEARCH_REPORT_FULLTEXT_PIPELINE_v1.md) | 研报全文:PDF 获取/解析 · Pass-A/B 结构抽取 · **Pass-C 研报分析专家** · Pass-R 关系抽取 · 跨篇归纳 | DESIGN |
| 四 | [SYNTHESIS_LAYER_AMENDMENT_v1.md](SYNTHESIS_LAYER_AMENDMENT_v1.md) | Self-review 修正案:关系图谱/检索通道/情境简报/叙事记忆/两类校验+综合研判员 | AMENDMENT(冲突时优先) |
| 五 | [PRICE_VOLUME_INTELLIGENCE_v1.md](PRICE_VOLUME_INTELLIGENCE_v1.md) | 量价情报包五子卡 · 量价事件生成器 · no_news_move · 技术面 6 维 | DESIGN |
| 支撑 | [../ai_chain_observatory/DESIGN.md](../ai_chain_observatory/DESIGN.md) | 202501 试点(数据+机制基座,已建成) | BUILT |
| 契约 | [../trading_agents_design/CONTRACTS.md](../trading_agents_design/CONTRACTS.md) | C1-C16(全套设计的绑定契约) | SHIP |
| 参考 | ../trading_agents_design/{TEXT_REFINERY,PHASE2,BLUEPRINT,INSTITUTIONAL_WORKFLOW,SERENITY_*}.md · Knowledge/蚂蚁投研/ | 方法论与蒸馏源 | 参考 |

**冲突优先级**:CONTRACTS > 第四篇修正案 > 二/三/五篇 > 第一篇。

## 2. 跨文档 Self-Review 记录(2026-07-08d)

**审查角度**:五篇为增量写成,互相打补丁——查计数漂移/输入清单漂移/契约一致性/遗漏。

| # | 发现 | 处置 |
|---|---|---|
| R1 | 产品计数漂移:二篇标题"六大产品",修正案加情境简报=7 | ✅ 统一为七产品(二篇已注) |
| R2 | 第一篇卡片清单陈旧:技术卡+资金卡已被五篇量价包取代,但 §3.2 表头/编制表/§6.1 维度表仍是旧 4 维 | ✅ 已打补丁(编制表/卡表/维度表指向五篇) |
| R3 | 消息面分析师输入散落四篇(事件卡集/检索列表/精读卡/间接节)无一处canonical | ✅ 第一篇编制表改为权威表述:"检索装配的相关信息列表(direct+非direct 分节)+研报精读卡要点" |
| R4 | 第一篇 §5 PIT 窗口表缺新对象(研报全文/关系边/叙事记忆/情境卡) | ✅ 补注:全文 90d 随研报;关系边=累积带过期;记忆卡=12mo 事件;情境卡=日度 |
| R5 | §7 输出 schema 的 cards 字段名滞后 | 记录,实现期以 README 路线图为准(schema 属实现细节) |
| R6 | 五篇各自估 LLM 成本,无合并预算 | ⚠ 待办:§10 评审材料须附合并调用预算表 |
| R7 | v1/v1.5/v2 分期散落五篇 | ✅ 本 README §4 合并路线图为唯一权威 |
| R8 | 概念板块(ths_*)权限未实测 | ⚠ 实施期首日探针(与研报 PDF 死链探针并列) |
| R9 | 通用层信息无人能"看"——缺浏览端 | ✅ **新增二篇 §6 本地 Web 平台**(用户裁定 2026-07-08d) |
| R10 | 契约一致性抽查:红线1(无买卖/目标价/收益预测)× 全五篇输出 schema:通过;C16 遏制 × 综合研判员/情境标签:v1.5 非评分,通过;PIT × 检索画像 as-of:通过 | 通过 |

**判决:五篇合并后自洽(R1-R4/R7/R9 已修),clean for GPT(附 R6/R8 两项待办)。**

## 2b. GPT §10 跨审 #1 = **REVISE**(2026-07-08,全部裁定已应用)

0 Blocker / 2 Major + 1 Major-lite / 5 Minor。核心判断被接受:**"数据层安全≈通过;研究流程治理
≈需补强——最大残余风险是 retrieval+synthesis 形成未注册的隐形研究信号生成器"**。应用清单:
| 裁定 | 落点 |
|---|---|
| Major-1 检索治理:RetrievalConfigCandidateID + C16b one-winner | 二篇横切 #8 |
| Major-2 综合类三级校验(L3: claim_strength ≤ evidence_strength) | 修正案·两类校验表 |
| Major-3 composite 围栏(research_summary,禁入排序/选股除非 C16 注册) | 一篇 §6.2 |
| Minor-1 retrieval_profile_snapshot_id(某日所见不可漂移) | 二篇 2A.3 |
| Minor-2 relation_graph_snapshot(graph_version ≤ decision_time)+ 环形检测 | 修正案·修补① |
| Minor-3 焦点词生命周期(candidate/approved/deprecated,LLM 只铸 candidate) | 二篇 2A.2 |
| Minor-4 golden set 扩到检索相关性标注 | 一篇 §8 |
| Minor-5 平台硬边界(禁触发写路径;进程不得 import 评分/编排模块) | 二篇 §6 |
| Q2 C16 候选面显式清单(Pass-C/story_arc/consensus_core/situation_type/检索精筛/首席) | 修正案·新节 |
| Q4 independent_source_count(报告族聚类去重,同券商复读=1 次确认) | 修正案·修补① |
| Q5 缺 evidence_class 的 artifact 一律拒入 evaluator(fail-closed) | 二篇横切 #9 |
| Q6 综合研判员 v1.5 → **v2**(最难验无幻觉的模块最后上) | 修正案 + 本 §4 |
| Q8-C2 澄清:**v1 全部输出不含 Pass-C 精读卡**(Pass-C=v1.5) | 本 §4 |
待办不变:R6 合并 LLM 预算表(re-review 材料附)。**下一步:re-review #2。**

## 2c. GPT §10 re-review #2 = **SHIP**(2026-07-08)——设计冻结,可进实现

0 Blocker / 0 Major。上一轮核心风险("retrieval+synthesis 隐形研究信号生成器")被确认拆解闭合。
SHIP 附带四项收尾加固,**全部已应用**:
| R2 裁定 | 落点 |
|---|---|
| Minor-1/Q3 **FORWARD_RETRIEVAL_PREREG**(首轮前向前冻结检索配置;C16b 管探索、PREREG 管部署;改动=新 CandidateID+新前向纪元) | 二篇横切 #10(**实施前置,非设计 blocker**) |
| Q2 最低 rubric(3×3 claim×evidence 允许矩阵 + 单源强因果措辞禁令) | 修正案·两类校验表 |
| Minor-A 快照内容寻址去重(不日频复制全图) | 二篇 2A.3 |
| Minor-B candidate 焦点词进 review 队列+浏览页,边界不放松 | 二篇 2A.2 |
| Minor-C replay 管线自动注入 evidence_class=NON_EVIDENTIARY_PILOT | 二篇横切 #9 |
**残余风险(GPT 原话)**:首轮 forward run 前必须冻结 RetrievalConfig,否则探索/生产边界模糊——
已立为实施前置。**评审弧线:#1 REVISE(2M+1Ml+5m+5Q)→ #2 SHIP,全裁定零拒绝。**

## 3. 本地 Web 平台(用户裁定,设计在二篇 §6)

通用层全部信息可浏览:本地只读 Web 服务(localhost),七个页面(今日大事/事件流浏览器/
线索浏览器/热点榜/个股档案/市场情境简报/研报精读库),蚂蚁式筛选排序,全页非证据横幅。

## 4. 合并实施路线图(唯一权威版)

| 期 | 内容 | 来源篇 |
|---|---|---|
| **v1** | 缺口①②③(express/fina_mainbz/fina_audit 进 PIT)· FactTable+唯一事实表 · 通用事件库(十个结构化生成器+anns_d/irm_qa 分型)+五维打标(概念标签除外)· 检索层(倒排+确定性精筛)· 量价包五子卡+量价事件 · 基本面/技术面/消息面/空头/裁判五席 · 研报全文 Pass-A/B(PDF 探针先行)· **Web 平台 MVP(事件流/个股档案/热点榜)** · 202501 重放验证 | 一/二/五 |
| **v1.5** | 政策三源接入(npr/货政/联播)→ 情境简报+L8 · ths 概念标签(权限探针后)· Pass-C 精读卡+Pass-R 关系边+跨篇归纳 · 叙事记忆卡 · L9 检索通道 · news 行业级分类 · **golden set 建库(含检索相关性标注)** · Web 平台全七页 | 二/三/四 |
| **v2** | **综合研判员席(GPT Q6:最难验的模块最后上)** · news/major_news 个股级(L4 实体落码)· 宏观指标端点 · 地缘触发器 · 情景树 · 机构观点卡(report_rc 解禁) | 二/四 |

**Q8-C2 澄清:v1 的全部输出不含 Pass-C 精读卡**(一篇提及的"研究档案综合"在 v1 指五席评分+
空头报告的装配,精读卡自 v1.5 起加入)。

**先决**:五篇+README 过 §10 GPT 跨审;动 Tushare 新端点前按 §6.1 读正文(概念板块三文档已在库)。
