# DSA 核心机制 × 本地 AI 打分系统 结合方案 v1

**Date:** 2026-07-22 · **Status:** ARBITRATED（用户三项裁定已落，2026-07-22）：
① Track D **不做**；② C1 的 rerank_v2 战绩对比页**允许中途只读查看**（用户裁定，偏离本方案
"锁到判定点"的建议——页面须常驻横幅注明"预注册判定点=2027-02（≥6 次调仓后），中途禁止基于
本页调整任何冻结项"；运维健康视图不受影响）；③ **B1/B2 立即开工**（Tier 3，运维通道，记审计日志）。
其余 Track 按排期表送审。
**来源仓库:** https://github.com/ZhuLinsen/daily_stock_analysis （深读记录见 memory `reference-dsa-comparison`，克隆在会话 scratchpad）
**绑定本地现实:** [README.md](README.md)（v1-v2 路线图）· [INPUT_PROMPT_AUDIT_v1.md](INPUT_PROMPT_AUDIT_v1.md) §6.3a（①b 就绪门,前向强制前置）·
[../mvp_pool_book/FORWARD_PREREG.md](../mvp_pool_book/FORWARD_PREREG.md)（rerank_v2 冻结面）· [../trading_agents_design/CONTRACTS.md](../trading_agents_design/CONTRACTS.md)（C1-C16,红线1）

---

## 0. 结合总原则（为什么不是"移植"）

四条本地约束决定了结合面：

1. **红线1（CONTRACTS）**：投研部输出禁买卖建议/目标价/收益预测 → DSA 的 8 态 action 分类、买卖点位、
   仓位建议**不得进入投研部输出**。DSA 的"决策"层只能作为独立注册单元的参考（Track D，默认不做）。
2. **rerank_v2 预注册冻结**：config/prompt/判定规则改任何一项 = rerank_v3 + 新预注册 → 金股侧的结合
   只能落在 §3 明文允许的**运维修复通道**（记审计日志）与决策面之外的观察层。
3. **链契约治理**：engine/ 任何字节变更 → 契约哈希变 → 必须 bump CHAIN_VERSION + review → 投研部侧
   的采纳项必须**攒批合并进计划内的版本翻转**，且避开在途 NF 波（news_flash_* 单元）。
4. **C16 围栏**：任何观察/评估产物若回流 prompt/权重/选股 = 未注册信号生成器 → 观察层一律
   NON_EVIDENTIARY + 只读，回流需 C16b 注册 + 新前向纪元。

**明确不引入**（本地已更强或方法论不合格）：DSA 的 LLM 裁决 agent（本地裁判=纯代码）、
风险 agent（本地空头席+机械证伪更强）、证据自由引用（本地行 ID 接地+独占更强）、
无成本收盘对收盘的 outcome/回测口径、文本关键词方向推断、手册式阈值（乖离 5% 等）、
其 7 个外部搜索商接入（借"模式"不借"源"）。

---

## Track A — 虚拟AI投研部：链路输出治理增强（落未来 CHAIN_VERSION）

### A1. 输入覆盖包（把既定 ①b 就绪门实现成全输入覆盖契约）★核心项

**本地现状**：①b 就绪门已是前向强制前置（INPUT_PROMPT_AUDIT §6.3a + Q10 已过 GPT 审），但规格只覆盖
①b 三数据源（moneyflow/cyq_perf/top_list），且**没有**聚合的每股每日"输入覆盖状态"落档案。

**DSA 借鉴**（`analysis_context_builder.py` / `analysis_context_pack_prompt.py`）三个设计点：
1. **块级状态枚举**：`available/partial/stale/fallback/missing/fetch_failed`（DSA 8 态裁到本地需要的 6 态）；
2. **块级加权覆盖分 + 四级**（good/usable/limited/poor），权重按卡片重要性（fact/pv 高、news/regime 低）；
3. **元数据只进 payload、绝不复述数值**，附规则句：*"某数据块降级只限制对应维度的置信，
   不得把缺失本身解读为利好或利空"*（DSA `342-349` 行的安全规则，直接对齐我们的反幻觉栈）。

**落点**：
- `engine/input_coverage.py` 新模块：装配期从 fact_table/pv_pack/news 装配处收集各卡 block status
  （①b 三源的 ≤D-1 回退+行内标注按既有规格实现，作为本模块的三个 block）；
- 渲染：各卡尾部或统一"数据可用性"节（行 ID 域新增前缀，如 `Q**`，进渲染器 emit-time 注册表）；
- 封档：`input_coverage` 块进档案 manifest，参与 `input_artifact_fp`（审计可回放"那天模型看到的数据健康度"）；
- prompts：加规则句（证据先行字段序不变）。

**治理**：payload+渲染域变更 → CHAIN_VERSION bump；Tier 2（治理管道，非印章/PIT 内核）；
一个 review unit；评分语义**零变更**（纯 additive）——这是它能和 ①b 前置件并单的原因。

### A2. 结构性失败的补全式重试

**本地现状**：畸形输出 fail-closed 逐条丢弃 + `schema_valid` 标记（正确），v3.0 已修 bear 的
max_tokens 根因；但 `finish_reason=length`/顶层 JSON 损坏这类**结构性失败**仍以空记录/不合格落档，
重跑=全价重花。

**DSA 借鉴**（`analyzer.py:4345 _build_integrity_retry_prompt`）：结构性失败时**基于上一次输出 +
缺失字段清单**做一次补全式重试（比整段重生成省 token 且更收敛），重试耗尽不阻塞、如实落档。

**落点**：`analyst_chain.run_seat/run_bear` 调用层；仅结构性失败触发、上限 1 次；全部尝试照落
`raw/` 审计目录（G5 不变）；档案记 `retry_count`；合格判定标准不变（按最终记录）。

**治理**：改变 LLM 调用序列 → bump；Tier 2；与 A1 合并为同一次版本翻转（避免两次契约哈希翻转），
在 NF 波收口后排期。

### A3. 明确不做（本地已更强，防止倒退）

canonical 评分刻度（ChainContract 冻结评分参数+manifest 复核 > DSA 的共享常量）、确定性裁判、
风险审查席、证据接地、多模型路由治理——全部保持本地实现。

---

## Track B — 金股前向：运维层加固（§3 允许的运维修复通道，全部记审计日志）

> 冻结面零接触：不改 rerank_v2.yaml/prompt/闸门语义/判定规则。8-03 首决策前优先级最高。

### B1. 日度文本拉取多源韧性（DSA `search_service.py` 模式）

- **key 级熔断**：错误计数 ≥3 跳过该 key，全坏重置（DSA `BaseSearchProvider:188-223`）；
- **源级顺序 fallback + 逐次埋点**：每次尝试记 `provider_run`（success/empty/error + fallback_to），
  落进既有 pull manifest 的审计字段（闸门语义不变，仍只认 ok pull manifest）；
- **硬新鲜度窗口**：拉取物带日期界检查（早于窗口/未来日期/无日期即拒），对齐既有 48h 陈旧闸。

目的：提高 ok pull 率 → 降低 30 天覆盖史闸门拒绝周期的概率。属 prereg §3 "API 换端点等运维修复"。

### B2. 覆盖缺口当日告警（预演闸门）

每日 pull 后重算一次"若今天是激活日，文本覆盖史闸门是否通过"，缺口当日写
`logs/qa_alert` 型 flag（复用 run_daily_qa 的告警形状）——把"8-04 决策时才发现被拒"
提前到缺口发生当日。纯读、不改闸门本体。

### B3. transition ledger（§5.5 既定硬前置，非新增）

借 DSA outcome 的 `holding_state` 分桶字段形状（旧仓不可卖/停牌/部分成交/现金滞留）设计 ledger
schema；任务本身已在 prereg 立项，第 2 周期前必须完成。

---

## Track C — 独立观察层（read-only · NON_EVIDENTIARY · 平台展示）

### C1. AI 打分 outcome 分桶统计器（DSA `decision_signal_outcome_service` 的方法论修正版）

- **输入**：投研部档案（composite/席位分/背离旗/A1 覆盖状态）× 本地 qlib provider 前向收益；
- **口径**：1/3/5/10/20 交易日窗口，±2% 中性带 hit/miss/neutral（借 DSA `_classify_signal_outcome`
  的分类形状），**收益从本地 provider 计算**（明标毛收益诊断；账本级净收益走事件驱动引擎）；
- **分桶维度**（借 DSA `get_stats` 的 8 维设计）：分数带 × 席位归因结构 × 输入覆盖状态 ×
  行业 × regime × 背离旗；
- **围栏**：evidence_class=NON_EVIDENTIARY；输出禁止回流 prompt/权重/选股（回流=C16b 注册+新纪元）；
  **rerank_v2 战绩视图默认锁定到 6 个月判定点**（"中途不看不调"的保守解释，放开需用户裁定）；
- **落点**：ai_chain_observatory 工具 + platform 新页（平台硬边界已禁写路径，全页非证据横幅沿用）。

### C2. 个股链评分时间线（DSA `history_comparison_service` 形状）

platform 个股分析 tab 增加该股历史 chain 分数/席位分时间线（排除当次），金股侧配月度换仓
transition 视图（依赖 B3 ledger）。Tier 3。

---

## Track E — 事件库风险覆盖补强（DSA 风险清单当"审计尺"的产出，2026-07-22 追加）

用 DSA risk agent 的 7 项强制风险检查对照本地十个结构化事件生成器（INTEL_CENTER §2.3），审计结果：
减持✓(stk_holdertrade) · 业绩预警✓(forecast) · 龙虎榜/大宗/停复牌/ST/非标审计✓ · 估值极端=状态非事件
（fact 卡已有 PE/PB/PS，不需要生成器）· 技术破位≈量价事件生成器域。**两个实缺口**：

- **E1 质押**：`pledge_stat` 原始数据已入库（data/corporate/pledge_stat，周频 ⚠ 仅 end_date 无
  ann_date——PIT 锚定需按 §6.1 先读 Tushare 文档定可见性口径）但**未接事件生成器**；
- **E2 解禁**：data_dictionary 全文无 share_float/解禁 数据集 → **未入库**。限售解禁是 A 股标准
  风险事件，属事件库覆盖缺口。补法走既有通道：读接口文档 → ledger/provider → 结构化事件生成器
  （重要性基线：解禁市值/流通市值分位）。

两项都是数据层追加（不动链版本），可独立于 Track A 排期；E2 涉及新端点抓取，走 §6.1 流程。

**§6.1 预读结果（2026-07-23，本地镜像三份文档齐全）**：`pledge_detail`（doc 111，**★ ann_date**）
与 `share_float`（doc 160，**★ ann_date**）均有公告日锚 → PIT 可锚定；`pledge_stat`（doc 110，
仅周频 end_date）只作聚合参照。**E1 应以 pledge_detail（ann_date 锚）为事件源**，非 pledge_stat。
两端点均为 ~7-14 列小表，抓取量级小；抓取仍待"无在途 Tushare 拉取"确认。
⚠ 事件生成器接入会改变链输入指纹 → 与 A1/A2 攒同一次 CHAIN_VERSION 翻转，不单独落。

## Track D — ~~DSA 式个人决策仪表盘~~（**用户裁定不做，2026-07-22**）

把投研部分数映射为 watch/hold 类动作的个人投顾面板。触碰红线1，需独立 C16 注册单元。
**用户裁定：不做。** 保留记录仅为防止未来重复提案。

---

## 排期与治理路径

| 项 | 窗口 | 治理 | review unit |
|---|---|---|---|
| B1+B2 | **✅ 已实现 2026-07-22**（40 测试全绿；审计见 [OPS_AUDIT_LOG.md](../mvp_pool_book/OPS_AUDIT_LOG.md)；GPT 一轮待送）。⚠ 首次真实预检发现 07-09 起文本拉取全停，不回填则 202608 周期必被拒——回填命令与授权见审计日志 | 运维通道+审计日志；Tier 3 | 合一单（自评+1 轮 GPT 待送） |
| A1 | NF 波收口后、投研部前向就绪工作流内（=①b 前置件的实现载体） | CHAIN_VERSION bump；Tier 2 | 单独一单 |
| A2 | 与 A1 同一次版本翻转 | 同上 | 与 A1 分开审、同版合并 |
| C1 | **✅ v0 已实现并首跑 2026-07-23**（提前开工吃 202501 测试数据，用户确认）：[outcome_stats.py](../ai_chain_observatory/outcome_stats.py) + 报告 [OUTCOME_STATS_202501.md](../ai_chain_observatory/OUTCOME_STATS_202501.md)。首跑发现：旧链具名文本通道 IC 为负且匿名消融更好（名称先验偏置证据）、fund 卡最强、combined 未跑赢量化输入、无文本名=弱负信号（A1 分桶价值实证）。#10 重放后直接复跑升级 leg-chain | NON_EVIDENTIARY；Tier 3→2（若上平台） | 单独一单 |
| C2/B3 | C1 后 / 第 2 周期前 | Tier 3 / prereg 既定 | — |
| D | 仅用户裁定后 | 新 C16 注册 | — |

**并行会话协调**：NF 归档波（news_flash_* 单元）在途——A1/A2 的 engine/ 变更必须排在其版本收口后，
与其合并规划版本号，避免契约哈希反复翻转。

**16 日重放时机（用户裁定 2026-07-23）**：快讯**有** 202501 历史 → NF P4 落地翻版本后重放输入
会变（news 卡含快讯节）→ **重放等 NF 波收口后再跑**，~18-22k AFP 只花一次，同时覆盖
"现行链验证"与"NF 集成后首次全量"两个目的。读档验收（v3.0 验证日）照常先签；
C1 的 leg-chain 16 日升级随重放顺延。
