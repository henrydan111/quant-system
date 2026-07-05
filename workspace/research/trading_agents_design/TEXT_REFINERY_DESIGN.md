# TEXT REFINERY · A 股资讯/研报获取+提纯系统 — 深度设计

**Date:** 2026-06-30
**Status:** DESIGN — **细化** [PHASE2_TEXT_PIPELINE.md](PHASE2_TEXT_PIPELINE.md) v3 的摄入+提纯层(2A/2B 的工程学);
binds to [CONTRACTS.md](CONTRACTS.md) C1/C2/C8/C12/C15/C16;**pending §10 review**;all `design_only`(C14)。
**参考三角(全部主源直读/实测):**
- **AIHOT**(卡兹克,[文章本地存档](file:///C:/Users/henry/Desktop/wechatDownload4.5/下载/数字生命卡兹克/) + [站点](https://aihot.virxact.com/)):168 精选信源、T1/T1.5/T2 分级、**11 版评分策略迭代史**。
- **ai-news-radar**([repo](https://github.com/LearnPrompt/ai-news-radar)):**核心管线零 LLM**,热度=多源独立确认+时间衰减+同源惩罚;`backtest_scoring.py` 配置重放。
- **serenity-skill**([解剖](SERENITY_SKILL_DISSECTION.md)):证据梯 + 确定性 scorecard。
标注:✅=已核实 / 🔧=设计主张 / ⚠️=陷阱。

---

## 0. 四方收敛(为什么这个架构可信)

四个独立来源收敛到同一条工程铁律:

| 来源 | 收敛点 |
|---|---|
| 卡兹克 11 版迭代(V1"全交给模型"→崩溃→V8 负优化→**全面回滚**) | **"能用代码处理的,一律不用模型处理"**;LLM 只打 5 维分,权重/最终分/阈值全是代码 |
| ai-news-radar | 更极端:**运行时管线零 LLM**(LLM 只在维护时的"伯乐 Skill"评估信源);热度纯算法 |
| serenity-skill | LLM 出 0-5+证据,Python `clamp(Σ·w−Σpenalty×2)` 算 final |
| 我们的 C16(GPT 六轮跨审) | LLM 子分数=候选因子;确定性聚合;LLM 绝不吐 final/决策 |

> 卡兹克的失败路径尤其宝贵——他把我们契约里**禁止的每一条都真实踩过一遍**:LLM 直接打总分(崩溃)、
> 规则堆进 prompt(300 行,泛化变差)、人类反馈喂回 prompt 持续迭代(V7→V8 纯负优化)。
> **这是 C16 的独立经验验证,记入 evidence_registry(经验级,非学术)。**

---

## 1. 根本差异:媒体热点系统 → 量化信号系统的三个反转 ⚠️

参考项目优化"值得人看";我们优化"携带增量的、PIT 干净的、机器可消费的定价信息"。三个不可照搬的反转:

**反转 1 · 热度 ≠ alpha,甚至常是反指。** AIHOT 的"精选"= 注意力价值;对定价,**热=大概率已 priced-in**
(A 股情绪→价格延迟 + 拥挤,见 memory `research_kol_sentiment_altdata_verdict`)。→ 我们同时产出
**novelty(首见时点)**与 **attention(簇质量)**两路信号,后者预注册时**方向假设=拥挤/反转**,不是动量。

**反转 2 · 产品是面板,不是榜单。** 媒体漏斗终点="人读 20 条";我们的终点=**`{date × ts_code/industry → 数值}`
的稠密对齐 PIT 面板**。精选榜/日报只是免费副产品(卡兹克日报"1 秒生成、无 LLM"证明:**摄入时处理完,
下游装配零模型**——我们的信号装配层同理)。

**反转 3 · 不能对收益调参。** 卡兹克"用量化方式跑上百个数值回测调权重"、radar 的 `backtest_scoring.py`
——他们**可以**自由调,因为 ground truth 是编辑品味;我们**不行**:对收益调 提纯参数 = 因子挖掘绕过
C16b/FrozenSelectionSet。→ **校准两段式**(§5):提纯层对**人工标注**自由调;信号层对**收益**只能走
one-shot 闸门。**这是本设计最重要的一条纪律。**

---

## 2. 八层炼厂架构

```
L0 信源策展 ─► L1 采集(C1) ─► L2 预筛(确定性→廉价LLM) ─► L3 结构化提纯(Qwen)
     │                                                          │
     ▼                                                          ▼
 source_registry                                        typed event card(C12)
     │                                                          │
L4 实体落码(PIT Stock Mapper) ─► L5 事件聚类(簇=单位) ─► L6 评分(C16) ─► L7 信号装配(零LLM)
                                                                              │
                                              ┌───────────────────────────────┤
                                              ▼               ▼               ▼
                                        文本→因子面板    dossier(前向AI)   人读日报(副产品)
```

### L0 · 信源策展(卡兹克:"信源比信息重要",宁缺毋滥)
- **source_registry**(版本化 YAML):`source_id · 接入方式 · cadence · trust_tier(C15 强/中/弱) ·
  精选阈值modifier · health遥测(radar 的 source-status.json 模式:抓取成功率/相关率/时延)`。
- 起步 = **8 个 Tushare 契约源**(已 §6.1 读毕):强=`anns_d/irm_qa/npr/monetary_policy`,中=`research_report/news/major_news`。
- **T1.5 洞察(卡兹克)**:同一主体的不同渠道信任不同(官网 T1 > 官推 T1.5)。映射:**公告 anns_d(T1)>
  互动易承诺(T1.5,管理层口径)> 研报摘要(T2,卖方立场)**——同一家公司的三个口径分层计权。

### L1 · 采集
- 逐源 adapter,C1 全套戳(`visible_at=max(published,ingested)`、`content_hash`、byte-replay);原始不可变落库。
- cadence 按源:news 日内多次(radar:30 分钟级)/研报每天 2 次 / 政策·央行低频。

### L2 · 预筛(三段漏斗,成本核心)
1. **确定性筛(免费,杀掉大头)**:精确去重(content_hash)→ universe/行业关键词粗匹配 → 已知噪声模式过滤。
   卡兹克 563 条/天约半数无关——我们的 news firehose 同理,**大部分该死在这里,不花任何 token**。
2. **廉价 LLM 二分筛(Qwen 小模型,批量 ~20 条/调用)**:"与 universe 内个股/关注行业/宏观主题相关?"
   是→L3;否→落库不再处理(留档可回放)。卡兹克用 DeepSeek 做同角色——**任务简单,小模型智力足够**。
3. 通过率遥测(m1):每日记录各层杀灭率,预算假设前向校准。

### L3 · 结构化提纯(Qwen,typed event card)
- 每条产出 C12 typed 卡:`entities候选 · event_type(业绩/订单/监管/诉讼/回购/减持/政策/传闻…) ·
  direction · evidence_spans · risk_flags(injection/rumor/低信任) · summary_128/512`。
- **低温 + 冻结 prompt + 版本号**;输出 schema 校验失败 → 重试一次 → 仍失败进隔离区(不静默丢弃)。
- 长文(npr/央行报告)走"政策四段式"(主题/适用对象/约束条款/时滞假设),只作行业/宏观上下文变量。

### L4 · 实体落码(确定性 PIT Stock Mapper,M3)
- LLM 只出**实体候选字符串**;落码由确定性模块按 `visible_at` as-of 解析 PIT 证券主数据(别名/曾用名/
  改名/退市),歧义→no-map。**LLM 永不直接写 ts_code。**

### L5 · 事件聚类(簇=分析单位,两参考共同的皇冠件)
- **为什么对量化更关键**:媒体不聚类=体验灾难;我们不聚类=**信号双计**(同一事件 7 篇报道≠7 个事件,
  否则 intensity 类信号全部虚高)。
- 机制:embedding 语义聚类(**冻结 embedding 模型+记录 cutoff——C2 学习组件**)+ 实体/时间窗约束;
  **主条选择=确定性权威规则**(官方公告 > 交易所互动 > 研报 > 财媒;卡兹克同款)。
- **sealed-OOS 可用变体**:提供确定性聚类 fallback(simhash/实体+日期键),供"冻结解析器"类信号走历史
  闸门;embedding 版聚类产物只进前向。
- 簇随时间生长 → 簇级字段:`首见 visible_at · 成员数 · 独立信源数(分 tier) · 时间衰减质量`。

### L6 · 评分(C16 全约束)
- LLM(Qwen 初评/Claude 复评仅对高显著簇)对**簇**打 5 维 0-5 分(如:事件重大性/基本面关联度/
  新颖性/证据质量/可持续性)+ 红旗惩罚(C15)。**不打总分。**
- 确定性公式(预注册权重)算 final;**分类别+分 tier 阈值**(卡兹克:"OpenAI 官网 60 分值得看,
  博主转发 60 分=噪声"→ 我们:公告 60 分≠研报摘要 60 分)。

### L7 · 信号装配(**零 LLM**——所有处理在摄入时完成)
把簇流确定性聚合成面板(见 §3);同时免费产出人读日报(按类分桶+按分排序,1 秒)。

---

## 3. 信号分类学(每族=一个 C16b CandidateID,预注册方向假设)

| 信号族 | 计算(全确定性,来自簇字段) | 预注册方向假设 | 历史可验性 |
|---|---|---|---|
| **event_intensity** | Σ tier 加权簇数 / 股·日 | 事件密度↑→波动↑(风险,非方向) | 冻结解析器版可 sealed-OOS |
| **breadth_confirm** | 簇内**独立强源**数(radar"几个独立信源同时在说的才配叫热点") | 强源广度=事件真实性;**兼反操纵**(水军刷不出 T1 确认) | 同上 |
| **novelty** | 首见 visible_at 距今 / 簇年龄(卡兹克"趋势预测"的可计算版) | 新事件>陈旧复读 | 同上 |
| **direction_balance** | (pos−neg)/(pos+neg),LLM direction 标签聚合 | 净方向→短期漂移(弱假设) | **LLM 产物→C2,前向为主** |
| **severity** | 5 维分的确定性聚合 | 重大性分层 | LLM 产物→C2,前向 |
| **attention_crowding** | 簇总质量(含中弱源) | **反转/拥挤**(反指假设!) | 冻结版可 sealed-OOS |
| **policy_exposure** | npr/央行四段式→行业曝露映射 | 政策受益/受损行业 tilt | LLM 产物→C2,前向 |
| **mgmt_uncertainty** | irm_qa 问答不确定性标签密度 | 管理层含糊↑→负 | LLM 产物→C2,前向 |

**装配的两个时钟(PIT 细节,契约落点):** 面板日 T 的信号 = `f(簇字段 | visible_at ≤ T 日截止)`。
**日截止须显式预注册**(如 T 日 14:30,供收盘决策;或 T+1 08:45,供开盘决策)——截止一变,信号即新
CandidateID。簇的**回溯生长不可回写历史面板**:T 日面板永远用"T 截止时簇的快照"(簇快照按日落盘)。

---

## 4. 反操纵在炼厂里的落位(C15 的机制化)

- **breadth_confirm 按 tier 计**:弱/中源刷屏只增 attention_crowding(反指),**不增 breadth**(需强源确认)
  ——把"防水军"从规则变成**信号结构本身**。
- 红旗探测器(serenity)→ L6 penalty;注入样文本 → L3 risk_flag,全路径不可信数据(C15)。
- 同源惩罚(radar):同一 source 重复发声在簇内只计一次。

---

## 5. 校准纪律(卡兹克 11 版教训的形式化,本设计的灵魂)

**两段式校准边界:**

| 层 | 允许的调参目标 | 机制 |
|---|---|---|
| **提纯层**(L2-L6:prompt/维度/权重/阈值) | **人工标注 golden set**(相关性/方向/严重度对不对) | 自由迭代;**每版配置对 golden set 重放评估**(卡兹克的"重评 500 条" + radar 的 `backtest_scoring.py` ≥14 天报告制) |
| **信号层**(L7 面板→因子) | **收益** | **只能走 C16b**:CandidateID 注册 → 边际贡献 → FrozenSelectionSet → one-shot OOS/前向。**改提纯配置=信号新版本=新 CandidateID,不得"顺手"回滚挑好的** |

- **golden set**:~300-500 条人工标注簇(建库时双标),版本化;每次 prompt/权重变更跑回放,
  报 precision/recall/方向准确率——**这是允许的"回测",因为 target 是标注不是收益**。
- **人类反馈 → eval set,绝不 → prompt 自动迭代**(卡兹克 V7→V8 负优化的直接教训;反馈只扩标注集,
  改 prompt 是人工决策+新版本号)。
- 配置全量版本化:`refinery_config_version = hash(prompt+维度+权重+阈值+截止+聚类参数)`,
  进每条面板记录 → 任意历史信号可归因到产生它的确切配置。

---

## 6. 成本漏斗(百炼 90k/月 ≈ 3k/天,遥测校准)

🔧 设计估算(前向实测前非证据):news+major_news ~1-3k 条/天 → **L2.1 确定性筛杀 ~60-70%**(免费)
→ L2.2 廉价二分(批 20 → ~30-60 调用)→ L3 提纯仅通过者(批 5-10 → ~30-80 调用)→ L6 仅高显著簇
(~20-50 簇/天,Qwen 初评;Claude 只复评 top 簇+决策名单)→ **合计 ~100-200 调用/天,余量充足**。
预算护栏:日调用硬顶+超限降级(只处理强源)。

---

## 7. 信源扩展策略(先契约内,后扩张)

- **v1 = 只做 8 个 Tushare 源**(PIT 已契约化)。
- **v2 扩张候选**(每源=独立接入项目,须 C1 adapter+tier 评估,非配置行):交易所官网公告直抓(降低
  anns_d 时延)、行业协会/部委官网(政策 T1)、券商研报 PDF 全文(重,OCR=C2 学习组件)。
- **明确不接**:社媒/股吧/KOL(C15 弱源;KOL 深研已判 no-go)。
- 卡兹克原则保持:**宁缺毋滥,一手优先**;radar 的"伯乐 Skill"模式可借:**LLM 参与信源评估(维护时),
  不参与运行时管线**。

---

## 8. 参考机制对照表(搬什么/改什么/弃什么)

| 机制 | 来源 | 处置 |
|---|---|---|
| 信源分级 T1/T1.5/T2 + 分级阈值 | AIHOT | ✅ 直接搬(=C15 tier + L6 分层阈值) |
| 廉价模型预筛 | AIHOT | ✅ 直接搬(L2.2) |
| LLM 只打维度分,代码算 final | AIHOT/serenity | ✅ 已是 C16 |
| 事件聚类+权威主条 | AIHOT/radar | ✅ 搬+加固(冻结 embedding+确定性 fallback+簇快照) |
| 多源独立确认=热点 | radar | ✅ 改造成 breadth_confirm 信号(按 tier 计) |
| 时间衰减/同源惩罚 | radar | ✅ 搬(簇质量/去双计) |
| 日报零 LLM | AIHOT | ✅ 搬(L7 装配零 LLM 的特例) |
| 配置回放回测 | radar/AIHOT | ⚠️ **改**:目标只能是 golden set,不能是收益(§5) |
| 人类反馈喂回 prompt | AIHOT(失败) | ❌ 弃(反馈只进 eval set) |
| 热度=价值 | 两者 | ❌ 反转(attention=拥挤反指假设) |
| 对榜单优化 | 两者 | ❌ 反转(对 PIT 面板优化) |

---

## 9. 契约绑定 + test_stub 增量(C14)

绑定:C1(L1 戳/簇快照不回写)· C2(embedding/OCR 冻结;LLM 衍生信号前向)· C8(L4 落码)·
C12(L3 typed 卡)· C15(tier/红旗/注入)· C16/C16b(L6 遏制;信号族=CandidateID)。
新增 test_stub(在 Phase-2 清单上追加):
- `tests/text/test_cluster_snapshot_no_retroactive_rewrite.py`(T 日面板=T 截止簇快照,簇生长不回写)
- `tests/text/test_breadth_requires_strong_tier.py`(弱/中源刷屏不增 breadth)
- `tests/text/test_refinery_config_version_stamped.py`(每条面板记录带 config hash;改配置=新版本)
- `tests/text/test_golden_set_replay_not_returns.py`(校准回放的 target=标注;对收益调参路径 fail-closed)
- `tests/text/test_daily_cutoff_preregistered.py`(日截止显式且不可事后改)

## 10. 诚实缺口

golden set 尚不存在(建库=Phase 2A 首批人工工作量,~2-3 天标注);成本漏斗数字全部 🔧;
attention=反指、direction→漂移等方向假设**全部未验证**(预注册后过闸门);A 股水军对 breadth 的
实际压力未知(强源确认设计上免疫,前向观察)。

---

**本设计与 PHASE2 v3 一起,在动任何 2A fetcher 前过 §10 review。**
