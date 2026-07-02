# GPT-5.5 Pro §10 re-review #6 (Phase-2 v3, clearing pass) — text pipeline + two-tier LLM

复制分隔线以下全部发给 GPT-5.5 Pro。`PHASE2_TEXT_PIPELINE.md` v3 全文已内嵌(GPT 沙盒无法 fetch),pinned `a159ada`。你的 re-review #5 = REVISE(3 Blocker + 5 Major + 3 Minor)**全部已应用**;本轮确认闭合或指出残留。

---

ROLE
You are a senior reviewer for an A-share quant research system where RESEARCH VALIDITY outranks code that runs. This is **§10 re-review #6 (clearing pass)** of the Phase-2 text-pipeline DESIGN (`PHASE2_TEXT_PIPELINE.md` v3). Your re-review #5 verdict was REVISE with 3 Blocker (B1 `earliest`→`max` PIT bug; B2 cutoff must cover all learned components; B3 deterministic aggregation ≠ alpha firewall / LLM games 0-5 sub-scores), 5 Major (M1 explicit multiple-testing; M2 full-path injection isolation; M3 PIT Stock Mapper; M4 deterministic modules not agents; M5 frozen parser provenance), 3 Minor (m1 telemetry; m2 Claude sanitized; m3 tests-must-fail-first). **ALL were accepted and applied** — your exact replacement text was used. The v3 doc also proposes two NEW contracts: C15 (anti-manipulation/injection) and C16 (LLM-score containment). Confirm closure or surface any remaining Blocker. Do not rubber-stamp.

REPO: https://github.com/henrydan111/quant-system  (branch trading-agents-design, pinned `a159ada`)

NOTE on B1: the `earliest`→`max` bug you found existed in the already-SHIP'd CONTRACTS C1 (you missed it in rounds #1–#4); it has now been corrected in CONTRACTS.md C1 AND in the v3 doc §6.

CURRENT C1 / C2 (post-fix, for reference):
> **C1.** `visible_at = max(verified source publication, first ingestion)` — NOT earliest (info actionable only once BOTH published AND ingested). Fail-closed to first_ingested when source time absent/nominal/date-only/ambiguous/revised/backfilled. Loader includes object at T only if `decision_visible_at ≤ T ∧ retrieved_at ≤ T ∧ content_hash version known at T`. anns_d PDF text has its own pdf_visible_at; monetary_policy.pub_date is date-level.
> **C2.** `clean_llm_text_factor` requires `decision_date > max(cutoff/release/freeze of EVERY learned component that affects inclusion/extraction/entity-linking/retrieval/dedup/clustering/rerank/OCR/summarization/scoring/analysis)` — incl. Qwen, Claude, embedding, reranker, entity-linker, OCR/layout, prompt_freeze, schema_freeze, data_snapshot_freeze. Unknown/mutable/post-decision → historical_* only. Historical sealed-OOS only deterministic non-learned parsers frozen before the window.

SELF-REVIEW PREFLIGHT (done): verdict = clean for GPT. Each of your 11 findings applied with your exact replacement language (see the v3 §0 banner + §3/§4/§6/§6b/§8/§10 + the CONTRACTS C1 edit). Critical self-checks: B1 now `max` everywhere incl. the live contract; B2 enumerates embedding/reranker/entity-linker/OCR; B3 = §3 six-point containment (LLM sub-score = candidate factor through C2 + pre-register + marginal contribution + FDR/DSR/PSR/PBO; scorer blind to returns/labels/action; invalid→no-score; C7-bounded deterministic action); M3 Stock Mapper as-of visible_at via the existing PIT survivorship infra. No leverage, explicit cost, four-layer all honored. Residual concern I want you to attack: Q1 below (is B3 truly closed, or can the LLM still drive alpha within the registered sub-score families?).

EMBEDDED DESIGN DOC v3 (authoritative; pinned `a159ada`) follows:


--- PHASE2_TEXT_PIPELINE.md v3 (pinned a159ada) ---

# Phase 2 · 多源文本管线 + 两层 LLM 分析师层 — 详细设计 (v3)

**Date:** 2026-06-30
**Status:** DESIGN — details [ROADMAP.md](ROADMAP.md) Phase 2; **binds to** [CONTRACTS.md](CONTRACTS.md)
(C1/C2/C3/C6/C7/C8/C12 + 提议新增 C15 反操纵/C16 LLM-分数遏制);**§10 re-review #5 = REVISE → 全部应用,
re-review #6 pending**. All `design_only` (C14).
**Evidence base:** 我方 deep-research `wf_903e4a9f`(21/25 三票)+ GPT deep-research(合并,带核实滤网)
+ §6.1 读 8 接口 + [SERENITY_SKILL_DISSECTION.md](SERENITY_SKILL_DISSECTION.md)。✅me 新证据:KTD-Fin
[2605.28359](https://arxiv.org/abs/2605.28359)·Bias-Consideration [2602.14233](https://arxiv.org/abs/2602.14233)
·Fin-Bias [ACL-F2026.279](https://aclanthology.org/2026.findings-acl.279/)·Glasserman-Lin [2309.17322](https://arxiv.org/abs/2309.17322)。
标注:✅=核实 / 🔧=设计主张(无实证) / ⚠️=陷阱。

> **§10 re-review #5 (REVISE) 全部应用:** B1 visible_at=`max` 非 earliest(并修 SHIP 的 C1)· B2 cutoff 覆盖全部学习组件 ·
> B3 LLM 子分数=候选因子(确定性聚合非 alpha 防火墙)· M1 文本多重检验显式 · M2 注入隔离覆盖全路径 · M3 Stock Mapper 必须 PIT ·
> M4 治理角色=确定性模块(非 agent)· M5 sealed-OOS 解析器 provenance 冻结 · m1 成本=遥测 · m2 Claude 只读消毒 dossier · m3 测试须先红。

---

## 0. TL;DR(五条定调)

1. **两层 LLM = TradingAgents 原生 config(✅)**:Qwen=quick_think(读/抽取/摘要)+ Claude=deep_think(分析),provider-agnostic,手配跨厂商。
2. **能力边界(✅)**:抽取/摘要/结构化→交 AI;具名股票判断/择时当 alpha→不交(KTD-Fin:去泄漏后收益≈风格暴露)。
3. **确定性聚合 ≠ alpha 防火墙(B3 修正)**:**LLM 的 0-5 子分数本身就是候选因子**;`final=clamp(Σ·w−Σpenalty·2)` 只把决策"洗"成可复现数字——**每个子分数族须过 C2 + 预注册 + 边际贡献 + FDR/DSR/PSR/PBO,行动映射 C7-bounded 且确定性**。LLM 绝不直接吐 final/买卖。
4. **历史文本基本不可验 alpha**(权限 1y + 回填)→ 干净=前向;**成本显式**(✅ 14/30 + 摩擦压缩)。
5. **起步最简**(CPH 未验证):v1 单轮聚合,不堆辩论;复杂度用前向评测证明再加。

---

## 1. 八源(§6.1;visible_at 见 §6/C1)

| 接口 | 粒度 | ts_code | 时间锚 | 源信任 |
|---|---|---|---|---|
| `research_report` | 仅摘要 abstr | ✅个股/行业 | ⚠️`trade_date` 名义日(report_rc 回填陷阱) | 中 |
| `irm_qa_sz/sh` | 全文 q+a | ✅ | `pub_time` | 强 |
| `anns_d` | **仅标题+PDF URL** | ✅ | `rec_time`(仅 gate 标题记录;**PDF 文本需自己的 `pdf_visible_at`**,B1) | 强 |
| `news`/`major_news` | 全文 | ❌**firehose** | `datetime`/`pub_time` | 中 |
| `npr` | 全文 html | ❌(ptype) | `pubtime` | 强 |
| `monetary_policy` | 全文 html+PDF | ❌宏观 | ⚠️`pub_date` **仅日级**(无戳→fail-closed first_ingested,B1) | 强 |

---

## 2. 架构 + 治理角色(M4:多数是确定性模块,不是 agent)

```
8源 ─①摄入─► 原始库 ─②Qwen 抽取─► PIT 实体映射 ─► 证据图谱 ─③Claude 评分 ─④确定性聚合 ─⑤闸门
```
**确定性模块(非 LLM,M4):** Ingest Governor(visible_at/版本锁/去重/源信任)· **Stock Mapper**(M3)· Dossier 组装 · 确定性聚合器(C16)· Validation Gate · 成本/可交易引擎 · C7 行动映射 · 硬风险限额。
**LLM 只填 typed 标注:** Qwen=抽取/摘要/实体&事件候选;Claude=typed 论点/反论点/证据评估 + 受 C16 约束的有界子分数。Risk Judge 可用 LLM 定性 flag 当输入,但**执行确定性、fail-closed**。
- **Stock Mapper(M3,确定性 PIT)**:只用带 `effective_from/to` 的 **PIT 证券主数据**(代码/名称/别名/行业/上市退市/改名/合并/概念标签),**按 text.visible_at 与 decision_time 的 as-of 解析**;**禁回填当前名称/行业/在市 universe**(否则=幸存者+前视)。歧义→no-map,不生成个股分数。走现成 `provider_metadata`/`namechange`/`all_stocks`/`st_stocks`。
- **纪律(serenity)**:层级/主题排序 ⟂ 具名公司排序分离 → 防 AI 跳到票。

---

## 3. C16 · LLM-分数遏制(B3 — 确定性聚合不够)

**LLM 子分数本身=模型输出=候选因子;确定性 final 公式不把 LLM 子分数变成干净 alpha 证据。** 任一 factor_score/penalty/persona 分数要影响 因子/tilt/veto,须**全部满足**:
1. 分数名/评分细则/允许证据类型/源信任规则/horizon/universe/聚合窗/`prompt_hash`/`model_id`/权重 = **预注册 immutable**。
2. 历史证据须 **C2-clean**;否则 forward/paper-live only。
3. 进**文本候选因子注册表**,过对纯量化基线的**边际正交贡献(净成本)+ DSR/PSR/FDR/PBO**。
4. **LLM 评分者不得看**:已实现收益、目标标签、期望交易动作、未来组合结果、或"为某 tilt 辩护"的指令。量化 rank 暴露仅在预注册的有界叠加测试中允许。
5. 每个 0-5 须带 `evidence_spans` 并过确定性 schema/源信任/时间戳/证据跨度校验;**无效/无支撑分数 → no-score,不是 neutral-positive**。
6. final tilt/veto/action 映射确定性、C7-bounded,**不可由 LLM 直接选**;任一 guard 失败 → 该对象无 AI tilt/veto。

schema(C12 typed)= serenity scorecard 形状:`{factor_scores:[{name,score_0_5,evidence_spans}], penalty_scores, risk_flags, what_could_weaken}`;Qwen 低温+冻结 prompt → 可重放。

---

## 4. C15 · 反操纵 / 注入隔离(M2 — 覆盖全路径,不只 Qwen)

- **三级证据梯(serenity→Tushare)**:强=公告/互动易/政策 · 中=研报/财媒 · 弱=社媒(未接)。**弱源仅线索,需强源确认。**
- **红旗惩罚(serenity,可编码)**:应收/存货增速>收入 · 称稀缺但毛利不改善 · 股价靠社媒热度 · 单一未具名客户 · 转收入前先融资 · 管理层主题语言但分部不动 → penalty_scores。
- **注入隔离边界(M2,全栈)**:外部文本在**每一阶段**(Qwen/Dossier/Claude/Risk Judge/审计回放工具)都是**不可信数据**;只作引用/转义字段传递,**绝不**拼进系统/开发者指令或可执行 prompt。**任何外部文本不得触发** tool call / URL 抓取 / PDF 抓取 / 下单 / 写文件 / 改配置 / 改 prompt-schema。**PDF 抽取在沙箱**。指令样文本 → `risk_flags=[injection]`,只能降信任/阻断,不能驱动动作。
- **反从众(✅ Fin-Bias)**:LLM 会 herd 上下文人类偏见 → 券商/KOL 意见结构化成"证据"而非"结论"喂入。
- ⚠️ A 股专属反操纵实证仍缺 → 🔧,前向校准(GPT 同意:边界须契约完整,但 A 股证据缺口不构成 Blocker)。

---

## 5. AI 能力边界(证据)

接收/抽取、理解/摘要 → ✅ Qwen(FiNER/FinEntity 基准);分析(出评分+证据)→ 🟡 Claude,受 C16 约束(Kim-Muhn-Nikolaev:匿名报表盈利**方向**尚可,非可交易 alpha);决策(具名 alpha/择时)→ ❌(KTD-Fin 去泄漏后≈风格暴露 ✅me;StockBench/FinMem 反转 ✅)。

---

## 6. 契约细化(回写 CONTRACTS)

- **C1(B1)**:`decision_visible_at = max(verified_source_published, first_ingested)`,**非 earliest**;源时间缺/名义/日级/歧义/回填 → =`first_ingested` 且历史仅 fixture(除非决策前 live 捕获)。Loader:仅当 `decision_visible_at≤T ∧ retrieved_at≤T ∧ content_hash 版本在 T 已知` 才纳入,否则 fail closed。`anns_d` PDF 文本独立 `pdf_retrieved_at/pdf_hash/pdf_visible_at`;`monetary_policy.pub_date` 日级。**(已同步修 SHIP 的 CONTRACTS C1。)**
- **C2(B2)**:`clean` 须 `decision_date > max(全部能影响 文档纳入/实体抽取/实体链接/检索/去重/聚类/重排/OCR-版面/摘要/评分/分析 的学习组件的 cutoff∨release∨freeze)` —— 含 embedding/reranker/entity-linker/OCR/版面 模型。任一未知/可变/晚于决策 → `historical_*` only。历史 sealed-OOS 只许**冻结的非学习解析器**。
- **(新 C15)** 反操纵/注入隔离(§4 全栈)。**(新 C16)** LLM-分数遏制(§3)。

---

## 6b. 文本多重检验(M1,显式,不靠隐含继承)

每个文本候选注册 `CandidateID = source_type × parser/model_id × prompt_hash × schema_version × scorecard_factor × persona/role × entity_scope × horizon × universe × aggregation_window`。**所有探索过的变体/弃用 prompt/分数名/阈值/persona/源过滤/聚合窗都计入有效试验数。** 选择须对现有因子集+纯量化基线有边际正交贡献(净成本);通过者进 `FrozenSelectionSet` 再 OOS/前向。**冻结周期内禁事后合并/改名/移阈值。**

---

## 7. 成本/吞吐(m1:遥测,非设计证据)

每次运行持久化 provider/model_id/token/批量/延迟/重试/成本/事件卡产出率/丢弃数。Qwen 覆盖 100%、只产高显著事件卡,Claude 只看事件卡+冲突+top-N dossier——**这些产出率/预算假设在前向实测前不是证据**。两 provider(百炼 Qwen / Anthropic Claude)。回测前向显式记成本走事件驱动引擎。

---

## 8. 验证闸门(双轨 + 5 偏差 + 解析器 provenance)

- **历史 sealed-OOS** ← **仅非学习确定性解析器,且 code/词典/正则/阈值/universe/源过滤/聚合窗/选择理由在 OOS 窗前冻结**(M5)。**post-cutoff LLM 生成或挑选的词典/正则/阈值/标签 = LLM 衍生物 → forward-only(除非满足 C2)**。Qwen 抽取的语义因子=LLM 产物→前向。
- **前向 paper-live** ← 所有 LLM 判断(评分/tilt/veto/决策);准前向=非证据(C5)。
- **Gate 强制 5 偏差(✅me 2602.14233)**:look-ahead / survivorship / narrative / objective / cost。
- 三方对照走 [HARNESS_FORWARD_AI_TRADER.md](HARNESS_FORWARD_AI_TRADER.md)。

---

## 9. 诚实缺口

A 股专属反操纵实证缺(§4=设计+通用证据)→ 🔧 前向校准;serenity 权重/稀缺层判断无验证(只借脚手架);跨厂商 schema/成本=🔧 前向实测;FinMem/FinCon/FinAgent/FinRobot 自述架构**未采纳为事实**(我那轮 3 票把 FinMem 自述判 0-3)。

---

## 10. test_stub 义务(C14;m3:**任一 2A fetcher/adapter/模型调用/scorecard 代码合入前,测试须已在 CI 存在且对空实现失败**;passing stub / skipped 不算)

- `tests/pit/test_text_decision_visible_at_max.py`(`max` 非 earliest;published>ingested 时 published 不可用;anns_d PDF 独立 visible)
- `tests/governance/test_all_learned_components_cutoff.py`(embedding/reranker/entity-linker/OCR cutoff 都入 max)
- `tests/text/test_llm_subscore_is_candidate_factor.py`(C16:LLM 出 final→fail;子分数未注册/未过多重检验→不可影响 tilt)
- `tests/text/test_injection_isolation_full_path.py`(外部文本不触发 tool/URL/PDF/order;Claude 只读消毒 dossier)
- `tests/universe/test_stock_mapper_pit_asof.py`(M3:as-of visible_at;禁回填当前名称/行业;退市名保留)
- `tests/text/test_sealed_oos_parser_provenance_frozen.py`(M5)
- `tests/text/test_text_candidate_multiplicity_registry.py`(M1 CandidateID + FrozenSelectionSet)

---

**v3 过 §10 re-review #6 = SHIP 后,方动 2A 任何 fetcher/test_stub。**


===== END EMBEDDED DESIGN =====

PRINCIPLES (a violation = Blocker): 1 PIT/no-lookahead (incl. EVERY learned component's parametric memory); 2 OOS sealed single-shot; 3 survivorship; 4 marginal-contribution selection; 5 execution/cost realism (event-driven total-return, 1x); 6 no leverage; 7 no hedge words; 8 four-layer pipeline; 9 multiple testing.

CLEARING-PASS QUESTIONS
1. B3 / C16 — your re-review #5 "single most important residual risk" was that the LLM can become the alpha engine via unvalidated 0-5 sub-scores. The v3 §3 now treats every sub-score family as a candidate factor (C2 + pre-register + marginal orthogonal contribution over the pure-quant baseline after costs + FDR/DSR/PSR/PBO; the scorer is blind to realized returns/labels/desired action; invalid scores → no-score; action mapping is C7-bounded deterministic). Is this now CLOSED, or is there still a path for the LLM to drive alpha within the registered families?
2. B1 — is `decision_visible_at = max(...)` + the loader rule + anns_d pdf_visible_at + monetary_policy date-level now correct and complete (in both the v3 doc and the CONTRACTS C1 edit)?
3. B2 — does the "all learned components" cutoff list now close the leakage path (embedding/reranker/entity-linker/OCR/layout), or is any learned component in the pipeline still unguarded?
4. M1–M5 / m1–m3 — confirm each is closed as written (multiple-testing CandidateID; full-path injection isolation; PIT Stock Mapper; deterministic-modules-not-agents; frozen parser provenance; telemetry; sanitized Claude input; tests-fail-first).
5. C15 / C16 as NEW contracts — are they well-formed enough to enter CONTRACTS.md, or do they need different wording / placement?
6. Any NEW lookahead/leakage/evaluation flaw introduced by the v3 edits? Is "design_only, tests not yet written" acceptable for this clearing pass (C14)?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor — quote the offending clause + exact replacement; map each Blocker to the violated principle. If a category is empty, say so explicitly.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
