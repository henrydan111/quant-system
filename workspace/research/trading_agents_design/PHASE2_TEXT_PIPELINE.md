# Phase 2 · 多源文本管线 + 两层 LLM 分析师层 — 详细设计

**Date:** 2026-06-30
**Status:** DESIGN — details [ROADMAP.md](ROADMAP.md) Phase 2; **binds to** [CONTRACTS.md](CONTRACTS.md)
(C1/C2/C6/C7/C8/C12); **pending §10 re-review (Phase-2 increment)**. All `design_only` (C14).
**Evidence base:** deep-research `wf_903e4a9f` (21/25 claims 3-vote-confirmed) + §6.1 reads of 8 Tushare
text endpoints + prior evidence baseline (Profit Mirage / StockBench / Look-Ahead-Bench / 项目 0/8 新数据战绩).
标注:✅=3票核实 / 📄=一手论文 / 🔧=工程设计主张(无直接实证) / ⚠️=陷阱。

---

## 0. TL;DR(四条定调)

1. **两层 LLM = TradingAgents 原生范式(✅ 核实)**:`quick_think_llm`(读/检索/摘要/表格转文本)+ `deep_think_llm`(决策/证据写作/分析),**provider-agnostic** → **Qwen(quick)+ Claude-Opus(deep)是它支持的 config**(非默认,要手配)。这一层不自造。
2. **能力边界(✅ 证据)**:extraction / summarization / 结构化 → 交 AI;**对具名股票的 judgment / 择时 / 预测当 alpha → 不交**(训练截止记忆泄漏,历史回测验不了)。
3. **历史文本基本不可验 alpha**(权限仅 1 年 + research_report 回填陷阱)→ **干净路径=前向实时摄入**;**成本必须显式**(✅ 14/30 是最弱维度;摩擦显式化压缩收益且改排序)。
4. **起步用最简编排,别先堆多空辩论**——"协调比模型更重要"是**未验证假说**(CPH,✅ 标记为假说);先最简,前向测了"辩论是否真比简单聚合好"再加复杂度。

---

## 1. 八个文本源(§6.1 已读,见 [data_dictionary.md] 待写入)

| 接口 | 粒度 | ts_code | visible_at 锚(C1) | 历史/限量 | 喂给谁 |
|---|---|---|---|---|---|
| `research_report` 研报 | **仅摘要 abstr**+元数据 | ✅个股 / ind_name | ⚠️`trade_date`(名义日,非戳;每天2更新=**report_rc 同款回填陷阱**) | 2017+(权限1y),1000/call | 基本面/行业分析师(主源) |
| `irm_qa_sz` 深证互动 | **全文 q+a**+industry | ✅+行业 | `pub_time`(好) | 2010+,3000/call | 个股+行业分析师 |
| `irm_qa_sh` 上证互动 | 全文 q+a | ✅ | `pub_time`(好) | 个股分析师 |
| `anns_d` 公告 | **仅标题+PDF URL** | ✅ | `rec_time`(datetime,好) | 2000/call | 个股事件触发 |
| `news` 快讯 | **全文 content** | ❌**firehose** | `datetime`(好) | 9源,1500/call | 实体抽取→个股/行业/情绪 |
| `major_news` 长篇 | 全文(需 fields) | ❌**firehose** | `pub_time`(好) | 400/call | 实体抽取→深度 |
| `npr` 政策库 | **全文 content_html** | ❌(ptype 110类) | `pubtime`(好) | 500/call | 宏观/政策分析师 |
| `monetary_policy` 央行 | 全文 content_html+PDF | ❌宏观 | `pub_date`(好) | 季度,一次拉全 | 宏观分析师 |

**两个结构性事实驱动设计**:(a) `news/major_news` **无代码=firehose → 必须 Qwen 抽实体**;(b) `anns_d/research_report` 只给标题/摘要,**v1 不解析 PDF**(用 abstr/title)。

---

## 2. 两层架构(把 TradingAgents config 范式实例化到你的栈)

```
 8 文本源 ──①摄入(C1)──► 原始文本库 ──②Qwen quick_think──► typed digest(C12) ──③Claude deep_think──► 决策
  visible_at             parquet+content_hash    抽实体/摘要/结构化         个股/行业/宏观分析师 persona
  (实时,往后累积)        (raw 不可变,可重放)      低温+冻结prompt+可审计       ↓
                                                                          ④ 有界叠加 tilt/veto(C7) ┃ AI最终决策(C5前向)
```

- **Qwen 层(百炼,高吞吐/低判断)**:firehose 实体抽取(news→哪只票/行业)+ 批量摘要 + 长文(npr/央行)结构化。**这是 AI 相对可靠的活(✅)。**
- **Claude-Opus 层(Anthropic,低吞吐/高判断)**:吃 typed digest + 带码数据(研报摘要/互动)→ 多分析师 persona 综合 → ④ 两条出口。**判断权受约束(C7);对具名股票的 alpha 判断走前向(C5)。**
- **角色骨架(借 TradingAgents,起步最简)**:`结构化文档向下流 + 自然语言只用于必要的 agent 辩论`(✅ 关键工程模式)。**v1 = 单轮聚合(分析师各出 typed 观点 → Claude 综合),不做多空辩论**;辩论作为 v2 选项,前向证明有增量再加(CPH 未验证)。

---

## 3. Qwen→Claude 中间 schema(typed,满足 C12,可审计可重放)

每条 Qwen 抽取产出一条 **typed digest record**(非散文):
```
{ source, source_doc_id, visible_at,                 # C1:可见时点,fail-closed
  entities: [{ts_code|industry|macro_theme, salience}],   # firehose 抽实体
  claim, direction(+/0/-), evidence_span,            # C12:观点+证据跨度
  confidence_bucket, risk_type, expiry,
  raw_payload_hash, model_id, model_cutoff, prompt_hash }  # C1字节重放 + C2双模cutoff
```
- **Claude 吃聚合 digest(按个股/行业/宏观)+ 决策名单那几只的原文**(摘要是有损压缩,高判断别只看摘要,🔧)。
- **Qwen 调用低温 + 冻结 prompt + 记录输入快照** → 可复现(C1 字节重放)。Qwen 输出**结构化非散文** → Claude 吃可审计字段,不吃 Qwen 散文(防幻觉传导)。

---

## 4. AI 能力边界(证据划线,直接来自本轮研究)

| 环节 | 给 AI? | 证据 |
|---|---|---|
| 信息**接收/抽取**(实体、字段) | ✅ Qwen | extraction 相对可靠(✅) |
| 信息**理解/摘要/结构化** | ✅ Qwen | summarization 是 quick_think 原生任务(✅) |
| **分析**(综合多源出观点) | 🟡 Claude,但输出 typed、受 C7 约束 | 多 agent 协作范式成熟(✅),但裁决=LLM 判断需警惕 |
| **决策**(对具名股票 alpha/择时) | ❌ 不当 alpha 引擎 | 记忆泄漏:FinMem MSFT +23%→−22%、AlphaAgents 4月单发、no system 满足5项(✅) |

---

## 5. 契约细化(要回写 CONTRACTS,§10 评定是改条款还是新增)

- **C1 源适配器**:补 8 接口的 `visible_at` 规格;**research_report.trade_date 显式列为"名义日≠可见日"陷阱**(report_rc 同款),fail-closed 到 `earliest(可信发布, ingested_at)`;历史段(权限前)= fixture only。
- **C2 升级为多模型 cutoff**:`clean_llm_text_factor` 的 decision_date 须 **严格晚于 max(Qwen_cutoff, Claude_cutoff, prompt_freeze, data_freeze)`**——两个模型都算(此前 C2 只写"决策模型")。
- **(候选新条款)两层模型 provenance**:每条 AI 产物记 `model_id/version/role(quick|deep)/cutoff/prompt_hash`,冻结。可并入 C2/C12,留 §10 定。

---

## 6. 成本/吞吐预算(百炼 Coding Plan 90k/月 ≈ 3k/天)

- **firehose 不能一条一调**:① 批量(~20 条/Qwen 调用)② **先按金股池/关注行业预筛再喂 Qwen**(否则月额度秒爆)。
- **Claude 只吃蒸馏后的 digest + shortlist 原文** → token 可控(Claude 贵)。
- **两 provider**:百炼=Qwen(quick),Anthropic=Claude-Opus(deep)。"兼容 Claude Code" ≠ 百炼能跑 Claude。
- **回测/前向必须显式记成本**(✅ 14/30 + 摩擦压缩收益且改排序)→ 走你的事件驱动总收益引擎,不另造。

---

## 7. 验证闸门(双轨,接 C2/C5)

- **历史 sealed-OOS** ← 只接**确定性抽取因子**(如"研报覆盖数/语调计数"等可被非 LLM 复算的),且受 C2 限定。
- **前向 paper-live** ← **所有 LLM 判断类**(persona 综合、tilt/veto、最终决策);准前向=非证据(C5)。
- **成本显式 + 三方对照**(AI vs 纯量化 vs 等权)走 [HARNESS_FORWARD_AI_TRADER.md](HARNESS_FORWARD_AI_TRADER.md)。

---

## 8. 诚实缺口(🔧 设计主张,无直接实证——研究明确未覆盖)

1. **A 股反操纵(水军/黑嘴/prompt 注入)**:本轮 21 条已证 claim **全是美股/英文**;A 股文本反操纵设计**目前只能是工程主张**。缓解(🔧):可信源分层(研报/互动易 > 快讯 > 论坛)、跨源印证、prompt 注入隔离(Qwen 只抽取不执行指令)。
2. **serenity-skill 的 evidence-ladder 模式**未被研究解剖(只知其为供应链投研 skill);若要借其证据分级,需单独定向检索。
3. **跨厂商 Qwen+Claude 的中间 schema/成本数字**无一手来源 → **本设计的 schema(§3)+ 预算(§6)是 🔧,必须前向实测校准**。

---

## 9. test_stub 义务(C14;build 前须 CI failing 测试)

- `tests/pit/test_text_visible_time_gate.py`(8 源 visible_at;含 research_report trade_date≤decision 但 ingested>decision → 排除)
- `tests/governance/test_two_model_cutoff_blocks_historical_alpha.py`(Qwen+Claude 双 cutoff)
- `tests/text/test_qwen_digest_schema_typed.py`(digest 必为 typed,非散文;含 model/prompt hash)
- `tests/text/test_firehose_entity_extraction_prefilter.py`(news 预筛到 universe + 批量)
- 成本显式 → 复用现有事件驱动成本测试。

---

**本设计 + C1/C2 细化,过 §10 re-review(Phase-2 增量)后,方动 2A 任何 fetcher/test_stub。**
