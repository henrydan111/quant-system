# 综合归纳层修正案 v1(虚拟AI投研部·第四篇)—— Self Review 记录 + 五项修补

**Date:** 2026-07-08 · **Status:** DESIGN AMENDMENT(与前三篇一体过 §10)
**触发:** 用户审题——"是否充分发挥 AI 在非结构化文本提取与归纳总结上的优势,尤其是把大量
**非直接相关消息**归纳起来辅佐综合判断?"
**Self-review 判决:前三篇纪律层强(C15/C16/PIT/接地),综合层不足**——AI 被卡片化设计压成
"逐股复读机",跨实体/跨文档/跨时间的归纳优势未被调用。五个缺陷,五项修补如下。
**边界重申:** "AI=最好的交易员"的可信实现 = 信息广度×纪律,经有界影响进账本、前向计量;
**不是**直接预测收益(G1 红线不动)。本修正案抬升的是信息面天花板,不是越界。

---

## 修补① 关系图谱(Entity Relation Store)—— 间接传导的地基

**问题**:间接信息通道为零(缺陷①②)。
**机制**:在研报全文管线加 **Pass-R 关系抽取**(与 Pass-A 同层,quick 模型):

```
输入:研报分节文本 / 互动易问答 / 公告标题
输出 schema:{"relations":[{"subject":"原文实体名","relation":
  "supplier_of|customer_of|competitor_of|same_chain_node|concept_exposure|shareholding",
  "object":"原文实体名","quote":"逐字≤100字","page":n,"asof_hint":"文中时点提示|null"}]}
铁律:实体只出原文名(落码交确定性 PIT Mapper,L4 纪律);无逐字证据不出边。
```

**边库**:`data/relation_store/`,每边 = (src, dst, type, first_visible_at, last_confirmed_at,
**independent_source_count**, source_tier, quotes[])。**PIT 语义**:边只在 first_visible_at 后可用;
边会过期(>365d 无再确认 → stale 降权)。**独立源计数(GPT Q4)**:确认按**报告族聚类**去重——
同一券商对同一关系的 10 篇复读 = 1 次确认(族键=机构×关系×90d 窗);置信升级只认 independent_source_count。
**图快照(GPT Minor-2)**:`relation_graph_snapshot`(日度)——图不是边集合,多跳推理依赖整体结构;
一切关系查询强制 `graph_version ≤ decision_time`(2025 年 A→B、2026 年 B→C,历史查询 A 的传导
不得穿越到 C)。**环形证据检测**:A→B 与 B→A 同源同窗铸边 → 标 circular,不参与传导。
**冷启动**:149 池 × 90d 研报全文一轮 Pass-R ≈ 数百条边;随日常管线增量生长。

## 修补② 间接信息通道(**2026-07-08b 架构修订:传导预分配 → 通用层检索**)

**用户裁定**:数据层为**通用层**——信息入库不归属股票,打满标签(行业/个股/概念/热点/关键词,
蚂蚁式);个股打分时按标签**检索**相关信息。详见 INTEL_CENTER §2A(入库五步流水线 + 检索
六步装配)。本修补的关系边(修补①)相应**降格为检索通道之一**(relevance_channel=relation):
个股检索画像含关系邻居及其行业,邻居的重要事件经检索进入本股 dossier 的"非直接"节,
必附机制链槽位(链距定级:直接>关系一跳>概念>行业,蚂蚁 P8 规则),断链环节明示 unverified。
**L9 间接传导线索**保留:作为通用层之上的挖掘器,读检索结果生成(供应商暴雷→下游风险 /
竞品提价→份额受益,双向),产出回写通用层带标签。
**优于旧设计之处**:一条信息服务任意股票与任意未来池子;关系图谱更新即时生效于下次检索,
无需回补历史"间接事件卡";检索通道可逐通道计量贡献(哪个通道检回的信息被分析师引用最多——
结构指标,进 §8 校准)。

## 修补③ 市场/行业情境简报(情报产品第七席)

**问题**:分析师不看盘面打分(缺陷③)。
**日度市场情境卡**(蚂蚁晨报的可核查版,全输入来自现有数据):指数/风格(大小盘/成长价值
相对收益)、宽度(涨跌家数/新高新低)、成交额分位、行业轮动 TOP/BOTTOM5、涨跌停温度、
政策事件行(npr/货政,v1.5 接入后)→ **确定性数字 + LLM 一段情境归纳**(闭卷,禁预测,
输出 regime 标签:风险偏好扩张/收缩/轮动/无主线 + 依据行)。
**周度行业简报**(池内行业):行业相对收益/估值分位/景气代理(成分股预告净方向)+ **news/major_news
的行业级分类聚合**——新闻→行业分类**不需要个股落码**(比 L4 容易一个量级)→ **firehose 的
行业级利用提前到 v1.5**(缺陷⑤部分,原 v2 整体推迟过于保守)。
**消费方式**:全体分析师 payload 附情境卡;prompt 规定"情境只用于校准 confidence 与
catalyst_timing,不得直接改事实维度分"——情境影响置信度,不影响事实判断(防情境冲刷证据)。

## 修补④ 叙事记忆卡(Narrative Memory)—— 时间纵深

**问题**:故事线与管理层信用被丢(缺陷④)。
**承诺→兑现台账(确定性)**:业绩预告 vs 实际(已有)+ 互动易/公告中的**可核承诺**(产能时点/
订单交付/回购计划——Pass-A 已抽 catalysts,加 `verifiable_by` 字段)→ 到期核销:兑现/延期/落空。
**故事弧归纳(LLM,季度刷新)**:输入 = 该股 12 个月事件卡全集 + 台账 → 输出:
`{story_arc: "≤5句的叙事主线演变", management_credibility: {kept: n, missed: n, 台账引用},
recurring_themes: [], tone_shift: "互动易答复风格变化(具体→回避)及证据", broken_promises: []}`。
**消费**:基本面席(credibility 作 mgmt 维度输入)、空头席(broken_promises 直接弹药)、
精读卡 Pass-C 的 recent_events 升级为 memory+events。PIT:只用 as-of 可见事件构建,台账核销
日=实际披露日。

## 修补⑤ 两类输出校验体系 + 综合研判员席位

**两类输出正式化**(解缺陷⑤的规则张力):
| 类 | 适用 | 校验 |
|---|---|---|
| **转录类** | 维度分证据/数字/评级/关系边 | 逐字单锚命中 + 证据独占(不变,从严) |
| **综合类** | one_line/story_arc/情境归纳/consensus_core/综合研判 | **三级校验(GPT R1 Major-2 升级——"锚存在"不够,须"锚蕴含")**:L1 source_id 存在且 as-of 合法;L2 陈述与锚的类别匹配(claim span maps to source category);**L3 强度不越级**:每陈述带 `claim_strength: fact\|interpretation\|hypothesis` + `evidence_strength: direct_quote\|multi_source\|inference`,**allowed = claim_strength ≤ evidence_strength**——"预计扩产10万吨"(fact/direct_quote)不得生成"进入高速成长周期"(interpretation)除非另有收入/需求/毛利锚;**禁锚外数字**;违级陈述降级为 hypothesis 或进隔离区。**最低 rubric(R2 裁定,代码+critic 可查)**:fact×direct_quote ✓ · fact×multi_source ✓ · **fact×inference ✗** · interpretation×direct_quote ✓ · interpretation×multi_source ✓ · interpretation×inference **限一跳且须明示推理链** · hypothesis×inference ✓ · hypothesis×direct_quote 须显式条件句("若…则…")。**另禁:单源 + 强因果措辞**(将/必然/进入…周期/戴维斯)——强因果词表命中且锚数=1 → 自动降级 hypothesis |

**综合研判员(首席分析师,L2 新席,**v2**——GPT Q6 裁定:全系统"最像人"也最难证明无幻觉的
模块,推迟到 ①-④ 输入面成熟且三级综合校验经 v1.5 实战检验之后)**:唯一**看全图**的 LLM 席位——
输入 = 本股五卡 + 间接事件卡 + 情境卡 + 叙事记忆卡 + 各席位维度分与空头报告。输出(综合类校验):
`{situation_type: "困境反转|景气加速|题材驱动|基本面顶背离|平淡", holistic_thesis: "≤8句综合研判,
每句带锚", strongest_cross_signal: "跨源信号共振点(如:上游扩产+本司毛利假设脆弱=双杀风险)",
contradictions: "各席位结论间的矛盾及裁读", watch_list: [可核查的观察条目]}`。
**C16 落位**:其输出仅进研究档案与看板(人读)+ 空头席二轮弹药;situation_type 若将来要
进任何评分/叠加 = 注册 CandidateID 走 C16b,不得"顺手"接线。

## C16 候选面显式清单(GPT Q2 裁定,一次列全,防"顺手接线")

以下 LLM 产物**全部属候选因子类**——进入任何 score/composite/ranking/selection 前必须注册
CandidateID 走 C16b(golden-set 校准/有效试验计数/one-winner/forward-only):
**Pass-C 精读卡各字段 · story_arc/management_credibility · consensus_core/herding_signal/blind_spots ·
situation_type · 检索边界 LLM 精筛判定 · 综合研判员全部输出 · 情境 regime 标签 ·
RetrievalConfig(横切机制 #8)**;分析师维度分已在第一篇 C16 覆盖。默认状态:全部
`evidence_class=research_summary`,人读专用。

---

## 对前三篇的落点(同步已打补丁的引用)

- 第一篇(分析师层):编制表 +综合研判员(v1.5)· 反幻觉栈 +两类校验 · 各席 payload +情境卡;
- 第二篇(数据层):情报产品 6→**7**(+情境简报)· 线索 L1-L7 → **L1-L9**(+L9 间接传导;
  L8 政策随 v1.5)· 新增 relation_store / narrative_memory 两个派生库;
- 第三篇(研报管线):+Pass-R 关系抽取 · Pass-C 输入升级(memory)· mentioned_stocks 进关系边。

## Self-review 附注(诚实剩余风险)

关系边质量依赖研报口径(卖方夸大合作关系)→ 边带 source_tier 且单源边只到"轻微"级;
间接传导的方向判断(供应商涨价对下游是利空还是转嫁)本质是判断题 → 传导卡只列机制不定方向,
方向留给消息面席位判;情境卡的 regime 标签是 LLM 产物 → C2 前向;综合研判员是全系统最"聪明"
也最难验的席位 → v1.5 才上,且 v1 先积累其输入面(修补①-④)。**本修正案后,"AI 读全市场的
邮件并告诉你哪些与你的股票有关"成立——这是量化结构性做不到、LLM 结构性擅长的那一格。**
