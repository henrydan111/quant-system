# GPT-5.5 Pro §10 re-review #5 (Phase-2 increment, v2 merged) — text pipeline + two-tier LLM

复制分隔线以下全部发给 GPT-5.5 Pro。新设计 `PHASE2_TEXT_PIPELINE.md` (v2) 全文已内嵌(GPT 沙盒无法 fetch),pinned `7d09c81`。CONTRACTS C1-C14 已于 re-review #4 = SHIP(`95daaff`);本轮**只评 Phase-2 增量 + 它提议的 C1/C2 细化 + 新增 C15(反操纵)/C16(确定性聚合)**。

---

ROLE
You are a senior reviewer for an A-share quant research system where RESEARCH VALIDITY outranks code that merely runs. This is **§10 re-review #5, Phase-2 increment (v2, now merged with a second independent GPT deep-research + a direct dissection of the serenity-skill repo)**. The DESIGN doc `PHASE2_TEXT_PIPELINE.md` details ROADMAP Phase 2 and PROPOSES: refinements to the SHIP'd C1/C2, plus **two NEW contracts — C15 (anti-manipulation / source-trust) and C16 (deterministic aggregation)**. C1–C14 you cleared at re-review #4 (SHIP, `95daaff`) are UNCHANGED except the C1/C2 refinements in §6. Judge whether building to this honors the contract, whether the refinements + new C15/C16 are correct/complete, and whether any NEW lookahead/leakage/evaluation flaw is introduced. Do not rubber-stamp.

REPO: https://github.com/henrydan111/quant-system  (branch trading-agents-design, pinned `7d09c81`)

CURRENT C1 / C2 (SHIP'd text the doc refines — judge §6 against these):
> **C1 · Text visibility PIT — gates Phase 2A.** Nominal dates (`trade_date/ann_date/...`) NEVER accepted as visibility; immutable `visible_at = earliest(verified source publication, first ingestion)`; loader fails closed on missing/ambiguous/revised/after-decision; historical re-downloads = fixtures only. Source-adapter returns `source_published_at, source_updated_at, retrieved_at, content_hash, query_hash, asof_decision_time`; byte-replay via `raw_payload_hash`.
> **C2 · LLM text-factor evidence labels — gates Phase 2B.** `historical_llm_text_factor` = plumbing only, NOT alpha evidence if the decision model's cutoff is after any evaluated decision date. `clean_llm_text_factor` requires `decision_date > max(model_training_cutoff, model_release_date, prompt_freeze, data_snapshot_freeze)`, via pre-registered forward or post-cutoff OOS. Historical sealed-OOS validates only deterministic NON-LLM parsers or frozen pre-cutoff models — NOT current LLM semantic factor generation. Mechanism audit necessary, never sufficient.

SELF-REVIEW PREFLIGHT (done): verdict = clean for GPT. The v2 merge folded a SECOND GPT deep-research, but **every GPT-surfaced source was independently fetched + verified by me before adoption** — and GPT's specifics drifted twice (it mis-stated 2602.14233's 5-bias taxonomy and over-read 2309.17322's thesis; both corrected in the doc/registry). I did NOT adopt FinMem/FinCon/FinAgent/FinRobot self-described architectures as fact (my own 3-vote run killed FinMem's self-description 0-3). Verified-✅me additions: KTD-Fin (returns≈style exposure), the 5-bias checklist, Fin-Bias (herding), Glasserman-Lin (lookahead). PIT/no-lookahead, no-leverage, explicit-cost, four-layer all honored. Residual concerns flagged in Q3–Q6 below.

EMBEDDED DESIGN DOC v2 (authoritative; pinned `7d09c81`) follows:


--- PHASE2_TEXT_PIPELINE.md v2 (pinned 7d09c81) ---

# Phase 2 · 多源文本管线 + 两层 LLM 分析师层 — 详细设计 (v2, merged)

**Date:** 2026-06-30
**Status:** DESIGN — details [ROADMAP.md](ROADMAP.md) Phase 2; **binds to** [CONTRACTS.md](CONTRACTS.md)
(C1/C2/C6/C7/C8/C12 + 提议新增 C15 反操纵/C16 确定性聚合);**pending §10 re-review**. All `design_only` (C14).
**Evidence base:** 我方 deep-research `wf_903e4a9f`(21/25 三票核实)+ GPT deep-research(合并,带核实滤网)
+ §6.1 读 8 接口 + [SERENITY_SKILL_DISSECTION.md](SERENITY_SKILL_DISSECTION.md)(主源直读)。
**我独立核实的新证据(✅me):** KTD-Fin [2605.28359](https://arxiv.org/abs/2605.28359)(去泄漏后收益≈风格暴露,几无选股 alpha)·
Bias-Consideration [2602.14233](https://arxiv.org/abs/2602.14233)(5 偏差=look-ahead/survivorship/narrative/objective/cost)·
Fin-Bias [ACL-F 2026.279](https://aclanthology.org/2026.findings-acl.279/)(LLM herd 上下文里的人类偏见)·
Glasserman-Lin [2309.17322](https://arxiv.org/abs/2309.17322)(GPT 情绪前视偏差)。
标注:✅=三票/我核实 / 📄=一手 / 🔧=设计主张(无直接实证) / ⚠️=陷阱。

---

## 0. TL;DR(五条定调)

1. **两层 LLM = TradingAgents 原生范式(✅)**:`quick_think_llm`(读/抽取/摘要)+ `deep_think_llm`(分析/决策),provider-agnostic → **Qwen(quick)+ Claude-Opus(deep)是其支持的 config**(非默认,手配)。不自造。
2. **能力边界(✅)**:抽取/摘要/结构化 → 交 AI;**对具名股票的判断/择时/预测当 alpha → 不交**(记忆泄漏;KTD-Fin:去泄漏后收益≈风格暴露)。
3. **确定性聚合(serenity 皇冠件,🔧 设计纪律)**:**LLM 只出 0-5 评分 + 证据,最终分/tilt 由确定性 Python 算;LLM 绝不直接吐最终数字或决策。** 一举三得:AI 关在"判断输入"位、便宜层可审计可复现、证据强度烤进分数。
4. **历史文本基本不可验 alpha**(权限 1y + 回填陷阱)→ 干净路径=前向;**成本必须显式**(✅ 14/30 + 摩擦压缩收益且改排序)。
5. **起步最简编排**——CPH(协调>模型)是**未验证假说**;v1=单轮聚合,不先堆多空辩论;复杂度用前向评测证明再加。

---

## 1. 八个文本源(§6.1 已读,见 [data_dictionary] 待写入)

| 接口 | 粒度 | ts_code | visible_at 锚(C1) | 历史/限量 | 喂给谁 / 源信任 |
|---|---|---|---|---|---|
| `research_report` 研报 | **仅摘要 abstr** | ✅个股/行业 | ⚠️`trade_date`(名义日,非戳;每天2更新=**report_rc 同款回填陷阱**) | 2017+(权1y),1000/call | 基本面/行业(**中**信任,卖方) |
| `irm_qa_sz/sh` 互动易 | **全文 q+a**(+行业) | ✅ | `pub_time`(好) | 2010+/2023+,3000 | 个股(**强**,交易所平台) |
| `anns_d` 公告 | **仅标题+PDF URL** | ✅ | `rec_time`(datetime) | 2000/call | 个股事件(**强**,官方) |
| `news` 快讯 | **全文** | ❌**firehose** | `datetime`(好) | 9源,1500 | 实体抽取(**中**,财媒) |
| `major_news` 长篇 | 全文(需 fields) | ❌**firehose** | `pub_time`(好) | 400 | 实体抽取(**中**) |
| `npr` 政策库 | **全文 html** | ❌(ptype 110类) | `pubtime`(好) | 500 | 宏观/政策(**强**,监管) |
| `monetary_policy` 央行 | 全文 html+PDF | ❌宏观 | `pub_date`(好) | 季度,一次拉全 | 宏观(**强**) |

驱动设计的两事实:(a) `news/major_news` 无码=firehose → 必须 Qwen 抽实体;(b) `anns_d/research_report` 只给标题/摘要,**v1 不解析 PDF**。**你没接社媒**(天然避开最差的"弱"信任层)。

---

## 2. 架构 + 治理化角色(借 TradingAgents 骨架,但角色整体"下沉为治理")

```
 8源 ─①摄入(C1)─► 原始库 ─②Qwen 抽取─► 证据图谱 ─③Claude 分析─► ④确定性聚合 ─⑤验证闸门
  visible_at        parquet+hash    stock/industry/   只读图谱不读       LLM出分→Python算    sealed-OOS
  +源信任分层        +注入隔离        macro dossier     firehose          tilt/veto/factor    或前向
```

**角色拆分(GPT 治理化版,优于直接照搬 TradingAgents 角色):**
- **Ingest Governor** — visible_at / 版本锁 / 去重 / **源信任分层**(§4)。
- **Qwen Event Extractor** — 实体/事件/证据句/**风险标记**(注入/谣言/低信任)。
- **Stock Mapper** — firehose → 公司/行业/宏观对象(静态证券主数据,**非 LLM**;防 vendor-code 漂移)。
- **Dossier Builder** — stock / industry / macro dossier + **跨源矛盾边**。
- **Claude Thesis Analyst** — **只读 dossier、不读原始 firehose** → 假设/反假设/冲突点/待验证(typed)。
- **Quant Overlay Judge** — 只允许 tilt/veto(C7 数值上限),不直接生成自由交易。
- **Risk & Governance Judge** — 源可信度/注入/风格暴露/交易约束。
- **Validation Gate** — sealed-OOS 或前向(§8)。
- **关键纪律(serenity)**:**层级/主题排序 ⟂ 具名公司排序分离** → 防 AI 直接跳到票。**v1 单轮聚合,不做多空辩论。**

---

## 3. 中间产物 = 确定性 Scorecard(serenity 皇冠件 + C12 typed)

**LLM(Qwen 抽取 + Claude 评估)只产出 0-5 评分 + 证据,最终分由 Python 确定性算**(serenity_scorecard 形状):
```
{ doc_id, source_type, source_trust_tier(强|中|弱),         # C1+§4
  visible_at, raw_payload_hash, model_id, model_cutoff, prompt_hash,  # C1重放+C2双模cutoff
  entities:[{ts_code|industry|macro, salience}],            # firehose 抽实体(Stock Mapper 落码)
  event_type, scope(stock|industry|macro),
  factor_scores:[{name, score_0_5, evidence_spans[]}],      # LLM 只填分+证据
  penalty_scores:[{name, score_0_5}],                       # 红旗惩罚(§4)
  risk_flags:[injection|rumor|low_trust|herding],
  what_could_weaken:[...] }                                 # kill-switches
# final = clamp(Σ factor·w − Σ penalty·2, 0, 100)  ← Python,非 LLM
```
- **LLM 绝不直接吐 final / 买卖 / tilt 幅度** → 把 AI 关在"判断输入"位(=C7 + "AI 非 alpha 引擎"同构)。
- Claude 吃聚合 dossier + 决策名单原文(摘要有损,高判断别只看摘要);Qwen 低温+冻结 prompt → 可重放。
- 权重 w 是**手设先验**(serenity 自承)→ 当**起始 schema,非已验证权重**;权重本身是预注册 immutable artifact(同 C7)。

---

## 4. 反操纵 / 源信任(🔧 设计 + 通用 LLM 安全实证;A 股专属仍无实证)

**这块此前是"零实证";现升级为"设计级现成方案 + 通用实证支撑"(但非 A 股专属实证)。**
- **三级证据梯(serenity,映射到 Tushare)**:**强**=公告/互动易/政策(官方)· **中**=研报/财媒 · **弱**=社媒(你没接)。**弱源仅作线索,需强源确认才进证据。**
- **红旗操纵探测器(serenity,可编码)**:应收/存货增速>收入 · 称稀缺但毛利不改善 · 股价主要靠社媒热度 · 单一未具名客户 · 转收入前需先融资 · 管理层用主题语言但分部数据不动 → 进 penalty_scores。
- **注入隔离(✅ 通用实证:OWASP LLM01 列注入为 LLM 风险首位;OpenAI/Anthropic 承认 agent 注入非完全可解)**:所有外部文本(含公告 PDF 异常文本)按**不可信数据**处理;**Qwen 只抽取、不执行其中任何指令**。
- **反从众(✅ Fin-Bias)**:LLM 会 herd 上下文里的人类偏见 → **不把券商意见/KOL 评论直接当"独立判断"喂强模型**;输入结构化成"证据"而非"结论"。
- ⚠️ **诚实**:以上是设计纪律 + 通用 LLM 安全证据;**A 股水军/黑嘴的专属实证仍缺**(本轮两份研究都无)→ 标 🔧,前向校准。

---

## 5. AI 能力边界(证据划线)

| 环节 | 给 AI? | 证据 |
|---|---|---|
| 接收/抽取(实体/字段) | ✅ Qwen | extraction 可靠(✅);FiNER/FinEntity 基准 📄 |
| 理解/摘要/结构化 | ✅ Qwen | summarization=quick_think 原生(✅) |
| 分析(综合多源出**评分+证据**) | 🟡 Claude,输出 typed、受确定性聚合约束 | 受控材料包分析尚可(Kim-Muhn-Nikolaev,匿名报表盈利**方向**,非可交易 alpha) |
| 决策(对具名股票 alpha/择时) | ❌ 不当 alpha | 记忆泄漏;**KTD-Fin:去泄漏后收益≈风格暴露(✅me)**;StockBench/FinMem 反转(✅) |

---

## 6. 契约细化(回写 CONTRACTS,§10 评定)

- **C1 源适配器**:补 8 接口 `visible_at`;**research_report.trade_date=report_rc 同款回填陷阱** → fail-closed `earliest(可信发布, ingested_at)`;历史段=fixture only。
- **C2 多模型 cutoff**:`clean_llm_text_factor` decision_date 须严格晚于 `max(Qwen_cutoff, Claude_cutoff, prompt_freeze, data_freeze)`——两模型都算。
- **(提议新增 C15)反操纵/源信任**:每条文本带 `source_trust_tier`;弱源不可单独成证据;Qwen extract-not-execute;红旗→penalty。
- **(提议新增 C16)确定性聚合**:LLM 只出 0-5+证据;final 由确定性代码算;LLM 直接吐 final/决策 → fail closed。权重=预注册 immutable。

---

## 7. 成本/吞吐(百炼 90k/月 ≈ 3k/天)

- firehose 不能一条一调:① 批量(~20/调用)② **先按金股池/关注行业预筛再喂 Qwen**。
- **Qwen 覆盖 100% 流入,只产 ~3-8% 高显著性事件卡(🔧 假设);Claude 只看事件卡+冲突+top-N dossier,永不扫全量 firehose**。
- 两 provider:百炼=Qwen,Anthropic=Claude;"兼容 Claude Code" ≠ 百炼能跑 Claude。
- 回测/前向**显式记成本**(✅ 14/30 + 摩擦压缩)→ 走事件驱动总收益引擎。

---

## 8. 验证闸门(双轨 + 5 偏差清单)

- **历史 sealed-OOS** ← 只接**非 LLM 可复算的确定性抽取因子**(正则/词典计数,如"研报覆盖数""负面公告密度");**Qwen 抽取的语义因子 = LLM 产物 → 走前向(C2)**。
- **前向 paper-live** ← 所有 LLM 判断类(评分综合/tilt/veto/决策);准前向=非证据(C5)。
- **Gate 强制查 5 偏差(✅me 2602.14233)**:look-ahead / survivorship / narrative / objective / cost——每条产出过这张清单。
- 三方对照(AI vs 纯量化 vs 等权)走 [HARNESS_FORWARD_AI_TRADER.md](HARNESS_FORWARD_AI_TRADER.md)。

---

## 9. 诚实缺口(更新)

1. **A 股专属反操纵实证**仍缺(§4 是设计+通用证据,非 A 股实证)→ 🔧,前向校准。
2. **serenity-skill 已解剖**([SERENITY_SKILL_DISSECTION.md](SERENITY_SKILL_DISSECTION.md));其权重/稀缺层判断**无验证**,只借脚手架(证据梯/确定性打分/风险边界),信号仍过你的闸门。
3. **跨厂商 Qwen+Claude 中间 schema/成本数字**无一手来源 → §3/§7 是 🔧,前向实测校准。
4. **未采纳为事实**:FinMem/FinCon/FinAgent/FinRobot/FinVerse 的自述架构(GPT 照单全收,我那轮 3 票把 FinMem 自述判 0-3)→ 仅作灵感,标 vendor-self-described/unverified。

---

## 10. test_stub 义务(C14;build 前须 CI failing 测试)

- `tests/pit/test_text_visible_time_gate.py`(8 源;research_report trade_date≤decision 但 ingested>decision→排除)
- `tests/governance/test_two_model_cutoff_blocks_historical_alpha.py`(Qwen+Claude 双 cutoff)
- `tests/text/test_deterministic_scorecard_llm_no_final.py`(LLM 出 final → fail closed;权重=预注册)
- `tests/text/test_source_trust_tier_and_injection.py`(弱源不单独成证据;Qwen extract-not-execute)
- `tests/text/test_firehose_entity_extraction_prefilter.py`(预筛到 universe + 批量;Stock Mapper 非 LLM 落码)
- 成本显式 → 复用事件驱动成本测试。

---

**本 v2 设计 + C1/C2 细化 + 提议 C15/C16,过 §10 re-review 后,方动 2A 任何 fetcher/test_stub。**


===== END EMBEDDED DESIGN =====

PRINCIPLES (a violation = Blocker): 1 PIT / no-lookahead — incl. BOTH the Qwen and Claude model's parametric memory; 2 OOS sealed, single-shot; 3 survivorship; 4 factor selection by MARGINAL orthogonal contribution; 5 execution/cost realism (event-driven total-return, 1x); 6 NO leverage; 7 NO hedge words; 8 four-layer pipeline (tradability ONLY in execution); 9 multiple testing (effective trials; DSR/PSR/FDR/PBO).

REVIEW QUESTIONS (Phase-2 increment, v2)
1. C1 refinement (8 source adapters + research_report.trade_date = report_rc backfill trap → fail-closed to earliest(source, ingested_at)): correct and complete? Any of the 8 sources whose visible_at handling is unsafe (e.g. anns_d gives only title+PDF-URL; news/major_news have no ts_code)?
2. C2 refinement: clean_llm_text_factor requires decision_date strictly after max(Qwen_cutoff, Claude_cutoff, prompt_freeze, data_freeze) — BOTH models. Correct? Any remaining model in the pipeline whose cutoff is unguarded (e.g. an embedding model used for dedup/retrieval, the entity-linking model)?
3. §8 states: a Qwen-EXTRACTED semantic factor is an LLM artifact → forward-only (C2); ONLY non-LLM-reproducible parsing (regex/dictionary counts) may enter historical sealed-OOS. Is this boundary now correct and sharp enough, or still exploitable?
4. NEW C16 (deterministic aggregation): "LLM emits only 0-5 scores + evidence; deterministic code computes final = clamp(Σfactor·w − Σpenalty·2); LLM never emits the final number/decision; weights are a pre-registered immutable artifact." Is this a sound governance contract? Key risk to rule on: can the LLM still effectively become the alpha engine by gaming the 0-5 sub-scores (i.e. the determinism is cosmetic if the LLM controls all inputs)? What guard closes that?
5. NEW C15 (anti-manipulation / source-trust): 3-tier evidence ladder (强 official / 中 media+broker / 弱 social-not-ingested) + red-flag penalties + Qwen extract-not-execute (injection isolation) + anti-herding (don't feed broker/KOL opinion as independent judgment). The A-share-specific empirical is ABSENT (only general LLM-security + Fin-Bias herding evidence). Is this sufficient as a design_only stance, or a Blocker until forward-validated? Any gap in the injection-isolation boundary?
6. MULTIPLE TESTING: text can spawn many candidate factors (per-source × per-persona × per-scorecard-factor). Does the doc adequately inherit the factor pipeline's deflated-Sharpe/FDR + marginal-contribution selection + FrozenSelectionSet, or must that be made explicit?
7. Governance role decomposition (Ingest Governor / Qwen Extractor / Stock Mapper [non-LLM] / Dossier Builder / Claude Thesis Analyst [reads dossier not firehose] / Quant Overlay Judge / Risk Judge / Validation Gate): sound and load-bearing, or over-engineered for a solo operator? Any role that should NOT be an LLM?
8. Any NEW lookahead/leakage/evaluation flaw introduced? Is "design_only, tests not yet written" acceptable (C14) given the listed test_stub obligations?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor — quote the offending clause + an exact replacement; map each Blocker to the violated principle. If a category is empty, say so explicitly.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
