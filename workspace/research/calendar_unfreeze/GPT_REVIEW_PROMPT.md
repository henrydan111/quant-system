# GPT 5.5 Pro cross-review prompt — Calendar Unfreeze Plan (design stage)

Status: ready to send AFTER `git push` of branch `trading-agents-design` (CLAUDE.md §10 — links must resolve against the pushed branch).

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, and do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: trading-agents-design)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/<path>

CONTEXT — read these to judge the change against the contract:
- CLAUDE.md (hard invariants §3, PIT §3.2, formal-run governance §3.4, research integrity §7, no-hedge §7.10)
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/CLAUDE.md
- The plan under review (authoritative copy also embedded below):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/calendar_unfreeze/UNFREEZE_PLAN.md
- Self-review record:
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/calendar_unfreeze/SELF_REVIEW.md
- The frozen calendar policy being thawed:
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/config/calendar_policies/frozen_20260227_system_build.yaml
- Policy loader (note: max_calendar_lag_days is defined but never enforced by any caller):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/research_orchestrator/calendar_policy.py
- Formal-runtime validator (frozen equality check, _validate_provider_at_runtime ~L152-239):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/backtest_engine/event_driven/__init__.py
- Daily QA (same semantics, provider_manifest_check ~L120-201; approval-evidence binding check below it):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/scripts/run_daily_qa.py
- Approval-evidence binding contract (per-publish drift check against provider_build.json):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/data_infra/approval_evidence.py
- Staged PIT builder (publish() calendar_policy_id hard default ~L4132; run() calls publish() with no args ~L4326; scoped-update path skips kline dump / never extends the calendar ~L3896-3926; instruments sidecars regenerated ~L3852-3872):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/data_infra/pit_backend.py
- Daily updater (single-date only; incremental trigger passes touched_symbols → scoped update):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/data_infra/pipeline/update_daily_data.py
- OOS_END = "2026-02-27" module constant (leak-freedom anchor to be re-designed per decision D3):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/research_orchestrator/promotion_evidence.py
- Hard-coded calendar_policy_id in formal IS/OOS steps (L956, L1112):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/research_orchestrator/validation_steps.py
- Revalidation window END constant:
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/alpha_research/factor_lifecycle/revalidation.py
- Yesterday's precedent for rebuild → safe publish → byte audit → approvals rebind (depth9):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/config/field_registry/approvals/2026-07-01_rebind_to_depth9_publish.md
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/scripts/_rebind_approvals_depth9.py

SELF-REVIEW PREFLIGHT — completed before this GPT request: verdict "clean for GPT"; checked §3 invariants + each quantitative-research principle in the canonical template. Fixes made:
- [Blocker, self-caught] fundamentals catch-up switched from report-period bulk fetch to ann_date-window bulk fetch (period-based would miss gap-period restatement announcements for OLDER periods — a PIT hole);
- [Major] the depth9 "overnight rebuild" duration evidence is contradictory (rebind md says stage=provider-only, manifest says stage:full) — plan now states only provider re-materialization duration is verified, full-chain stage=full duration is unverified and will be measured in Phase 0;
- [Minor] verified instruments sidecars (all_stocks/st_stocks/csi*) auto-regenerate in mode=all builds (pit_backend.py:3852-3872), precondition = raw stock_st_daily/namechange/index_weights caught up first;
- [Minor] catch-up driver hoists update_reference_data out of the per-day loop (avoids ~82 redundant full stock_basic pulls).
Residual concerns for reviewer: (a) decision D3's weakening of the structural leak-freedom guarantee (see Question 2); (b) sustainability of the per-publish approvals-rebind ceremony (Question 4).

WHAT CHANGED (authoritative — treat the embedded text as the source of truth; the links cross-check the surrounding code)

This is a DESIGN-STAGE review of a plan document (no implementation diff yet). The system's trading calendar has been intentionally frozen at 2026-02-27 since 2026-05-26 ("system construction" freeze). The plan proposes how to thaw it — bring data current (~82 trading days behind, spanning the FY2025 annual + 2026Q1 report season) and establish a sustainable update cadence — without breaking PIT correctness, formal-run governance, sealed-OOS discipline, or historical artifact provenance.

The full plan document (workspace/research/calendar_unfreeze/UNFREEZE_PLAN.md) is embedded verbatim below between the ===PLAN=== markers. Its §0 is a code-level audit of every freeze enforcement point (with file:line references you can verify via the raw links); §1 contains the three key design decisions (D1: new policy id instead of in-place frozen:false flip; D2: daily raw-layer sync + monthly provider rebuild/rebind cadence; D3: post-2026-02-27 window is born-sealed, OOS_END equality semantics replaced by config-driven binding); §2 is the five-phase execution plan; §3 risks; §4 effort.

===PLAN===
# 日历解冻计划（Calendar Unfreeze Plan）

*起草日期：2026-07-01 · 状态：DRAFT，待 GPT 5.5 Pro 跨审（CLAUDE.md §10 强制门）*
*目标：把冻结在 2026-02-27 的本地数据日历稳定、高效地推进到当前，并建立可持续的更新机制。*

## 0. 调查结论：冻结到底"冻"在哪里（事实基础，全部已核实）

### 0.1 强制执行点（解冻必须逐一处理）

| # | 执行点 | 位置 | 行为 |
|---|--------|------|------|
| 1 | 冻结政策 YAML（全库唯一政策） | config/calendar_policies/frozen_20260227_system_build.yaml | frozen: true，policy/manifest/live 三方日历末端必须严格相等 |
| 2 | 正式运行时校验 | src/backtest_engine/event_driven/__init__.py:218-235 _validate_provider_at_runtime | frozen 政策：policy.calendar_end_date == live == manifest，不等即 raise |
| 3 | 日常 QA 校验 | scripts/run_daily_qa.py:161-181 | 与运行时校验同语义 |
| 4 | Approval 证据绑定 | src/data_infra/approval_evidence.py + config/field_registry/approvals/*.yaml（约 25 个） | 每个 approval 绑定 provider_build_id + calendar_policy_id，与 live provider_build.json 不一致 → daily QA 红 |
| 5 | Manifest 发布默认值 | src/data_infra/pit_backend.py:4132 | publish(calendar_policy_id="frozen_20260227_system_build") 为硬编码默认；run()（4326 行）调用 publish() 时**不传参**，且 build_qlib_backend()/CLI 完全没有暴露该参数 |
| 6 | 正式验证步骤硬编码 | src/research_orchestrator/validation_steps.py:956, 1112 | IS/OOS 正式回测步骤写死 calendar_policy_id="frozen_20260227_system_build" |
| 7 | Promotion 证据 OOS 末端 | src/research_orchestrator/promotion_evidence.py:39 OOS_END = "2026-02-27" | 无泄漏保证依赖 provider calendar_end == OOS_END |
| 8 | 再验证窗口末端 | src/alpha_research/factor_lifecycle/revalidation.py:29 END = "2026-02-27" | 同上性质 |

### 0.2 代码缺口（解冻前必须知道的"没实现"）

- **max_calendar_lag_days 是死字段**：calendar_policy.py:43,77-83 定义并在 frozen:false 时强制要求填写，但**没有任何调用方真正执行 lag 检查**（运行时校验和 daily QA 的非冻结分支都只做 manifest == live 等值检查，不做"日历是否太旧"检查）。YAML 注释里"解冻无需改代码"的说法**只对了一半**。
- **日常增量路径不扩展日历**：update_daily_data.py 的 trigger_qlib_incremental 传 touched_symbols → pit_backend.materialize_provider 走 scoped_update 分支（pit_backend.py:3904-3926），该分支**跳过 _build_price_csvs + _run_dump_bin**，即只在现有日历上重写 PIT 字段，K 线 bin 和 calendars/day.txt 永远不会被追加。日历扩展只能走非 scoped 路径（mode=update 无 touched_symbols = 全树 copytree，或 mode=all 全量重建）。
- **update_daily_data.py 只支持单日**（--date 一天），没有多日追赶循环。
- 非 scoped mode=update 的全树拷贝 = 已知磁盘隐患（约 241GB / 2300 万文件）。

### 0.3 数据现状与缺口体量

- 全部核心数据末端 = 2026-02-27（daily/index/trade_cal 各 4,410 个交易日；data/data_tracker.md）。
- 缺口 = 2026-03-02 → 至今，**约 82 个交易日（估计值，Phase 1 刷新 trade_cal 后以实际为准）**。
- ⚠ 缺口正好覆盖**年报季**：FY2025 年报（4-30 截止）+ 2026Q1 季报全横截面 + 6 月的分红除权高峰——这是全年基本面数据量最大的窗口，追赶不是"补几天行情"而是补一整个财报季。
- provider 昨天刚全量重建发布（depth9_20260630，2026-07-01T06:00 发布）——ledger 全新、且**安全发布 + 字节审计 + approval 换绑的完整先例就在昨天**（workspace/scripts/_depth9_safe_publish.py、_rebind_approvals_depth9.py、config/field_registry/approvals/2026-07-01_rebind_to_depth9_publish.md）。⚠ 时长证据注意：rebind md 记录 depth9 为 stage=provider-only，而 manifest 记录 stage: full——两处记录不一致；**已验证的只是 provider 重物化可在一夜内完成，含 upstream（profile/normalize/ledger）的全链 stage=full 真实时长未验证**，Phase 0 以实测为准。

## 1. 三个设计决策（执行前必须敲定，建议如下）

### D1：新政策文件，而不是原地改 frozen: false —— **建议：新建政策 id**

YAML 注释建议原地翻转，但这会**改写历史出处的语义**：约 25 个 approval YAML 和全部正式 artifact 记录的 calendar_policy_id=frozen_20260227_system_build 含义是"冻结在 2026-02-27"；原地改动后，历史 provenance 指向的政策文件说的是另一回事。政策文件应视为 append-only 治理文件（与 approvals 同类）。

**建议**：老文件永久不动；解冻第一步落地为**新的冻结政策** frozen_20260630_thaw_step1.yaml（末端 = 追赶后最后一个完整交易日，命名以实际为准）。好处：所有 frozen 等值校验路径**零代码改动**直接工作（最稳）；把"滚动日历"这个更大的工程（D2/lag 检查）解耦到第二阶段。

### D2：稳态节奏 = 每日原始层同步 + 每月 provider 重建换绑 —— **建议：月度冻结跳升（monthly freeze bump）**

约束推导：每次 publish 必然产生新 provider_build_id → 约 25 个 approval 必须换绑 + 审计记录。**每日 publish = 每日换绑仪式，不可持续**。全量重建可承受月度频率。原始层（parquet）与 provider 解耦：**原始层每天追（便宜、无治理开销、把 Tushare 负载摊平）**，provider 每月集中重建一次（本地操作，不碰 API）。

**建议**：每日计划任务跑 update_daily_data.py --no-qlib；每月 provider 全量重建到新末端 + 新冻结政策 YAML + 脚本化换绑 + QA，一个 driver 一键完成。滚动政策（frozen:false + 真正实现 max_calendar_lag_days 检查）作为**后续演进**，不在本计划关键路径上。

### D3：新窗口默认封存 —— **建议：2026-02-28 起的数据出生即 sealed**

2026-03 → 至今这约 4 个月对**全部注册因子**（包括已花掉 2021→2026-02 OOS 的 E-wave 6 核、GP、arXiv D 批）是**真正未被观测的新 OOS 资产**，必须防止被日常研究无意烧掉：

- 探索/沙盒工作默认窗口上限仍为 2026-02-27（研究习惯不变）；
- 新窗口只能通过 sealed-OOS 机制（holdout seal 申领）触碰；
- promotion_evidence.OOS_END 与 revalidation.END 从模块常量改为**由政策/配置驱动**（单一来源），并把"provider calendar_end ≥ OOS_END + 窗口显式绑定"替代原来的严格等值语义——这一条是治理语义变更，**必须在 GPT 跨审中重点审**。

## 2. 执行计划（五个阶段）

### Phase 0 — 前置与设计冻结（0.5 天）
1. 本计划过 GPT 5.5 Pro 跨审（先做结构化自审，含 §3 不变量核对）。
2. 磁盘审计：E: 盘可用空间 ≥ 1.5× provider 树（staging + 保留一份 backup）；先修剪历史 data/qlib_data.bak_*。
3. 基线：当前冻结态 run_daily_qa 全绿存档；记录当前 provider_build.json；解冻工作开独立分支。
4. 敲定 D1-D3。

### Phase 1 — 原始层追赶（1-2 天，绝大部分是无人值守串行抓取）
1. **先刷 trade_cal + stock_basic**（日历是唯一地面真值；新 IPO/退市边界）。
2. **行情类（按 trade_date 分区的数据集）**：写一个小的追赶 driver（workspace/scripts/catchup_daily_range.py，带断点续跑 + 进度条 + 日志），逐日循环 DailyDataUpdater.update_for_date(date, ...)、跳过 Qlib 转换，覆盖 2026-03-02→至今每个交易日：daily OHLCV+估值+adj_factor、指数日线、Phase 3 日频集（moneyflow / hk_hold / margin_detail / stk_limit / top_list / top_inst / block_trade / cyq_perf 等）。**严格串行、单 fetcher、base_sleep=1.5 不降**（§6.1）。效率细节：update_reference_data（stock_basic+trade_cal 全量重拉）从逐日循环中提出，只在追赶开始时跑一次（否则 82 天循环重复拉 82 次 stock_basic）。
3. **基本面（按 ann_date 锚定的数据集）**：**按 ann_date 窗口批量抓取**（2026-02-28→至今，按周/双周分块以控制单次响应体量），复用 update_fundamentals 已用的 VIP fetcher ann_date-range 语义——income / balancesheet / cashflow（+quarterly 变体）/ dividends / forecast / holder_number。**明确不用"按报告期（20251231/20260331）抓取"方案：按期抓会漏掉缺口期内公告的、针对更早报告期的 restatement/更正公告，构成 PIT 缺口**；ann_date 窗口法同时覆盖新报告期与历史期 restatement。indicators 走 refresh_indicator_history.py 的 staged 刷新（update_flag 语义）。**每个端点重拉前先读 Tushare数据接口/ 官方文档**（§6.1 强制，尤其 update_flag/★ 日期字段语义）。
4. **事件/另类端点增量**：report_rc（create_time 锚定增量）、stk_holdertrade、suspend_d、namechange、stock_st_daily、index_weights（3-6 月各月）。
5. **完整性闸**：verify_database.py 原始层闸 + 更新 data/data_tracker.md。

### Phase 2 — Ledger + Provider 重建到新末端（1 天，主要是机器时间）
1. **小代码改动（先行、单独评审）**：calendar_policy_id 参数贯通：build_qlib_backend() → builder.run() → publish(calendar_policy_id=...) + CLI --calendar-policy（消灭 pit_backend.py:4132 硬默认依赖）；新政策 YAML frozen_<新末端>_thaw_step1.yaml。
2. **全量重建**：build_qlib_backend.py --stage full --mode all --calendar-policy <新政策>（staged，不立即 publish）。选 mode=all 而不是未经大规模演练的非 scoped update：**稳定优先**（provider 重物化段一夜可完成有 depth9 实证；含 upstream 的全链时长未验证，接受更长机器时间或 Phase 0 实测分段估时）。ledger 用新 ann_date 重建（P0-4 确定性重建保证可复现；⚠ derive_single_quarter_value 会因缺口期 restatement 追溯改写派生季值——任何缓存季值的研究代码按既有不变量失效重算）。
3. **发布前审计（复用 depth9 方法论）**：冻结段字节校验：所有 bin 的前 4,410 天与旧 live 逐字节一致（全量 size 审计 + 确定性抽样 SHA）；calendars/day.txt = 旧 4,410 天 + 仅追加尾部；instruments 侧车已随重建更新到新末端（已核实：mode=all 构建自动再生 all_stocks/st_stocks/csi* —— pit_backend.py:3852-3872 分别经 build_all_stocks_universe/build_st_universe/build_index_universes，validation 断言其存在（pit_backend.py:4062-4064）；**前提是 Phase 1 已把 stock_st_daily / namechange / index_weights 原始层追平**）。
4. **安全发布**：复用 _depth9_safe_publish.py 的三步原子交换次序（staged→adjacent、live→backup、staged→live；同卷 st_dev 闸已内建），旧 live 保留为 .bak。

### Phase 3 — 治理换绑与全面验证（0.5 天）
1. **Approvals 换绑**：约 25 个 YAML 同时换 provider_build_id + calendar_policy_id（照 _rebind_approvals_depth9.py 写 driver），附换绑审计 md（证据 = Phase 2.3 的冻结段字节审计）；evaluate_approval_evidence_bindings() → 0 drift。
2. **src 常量清理**：validation_steps.py:956,1112（政策 id 从配置/prescription 流入，不再写死）、event_driven/__init__.py:489 报错文案、promotion_evidence.OOS_END / revalidation.END 按 D3 改为配置驱动。
3. **测试全扫**：18 个测试文件含 132 处 2026-02-27/20260227（多为自带 fixture，预期不红；凡耦合 live provider 的钉死日期逐一修）；run_daily_qa / audit_qlib.py / qlib_smoke.py / test_pit_live_provider.py 全绿。
4. **文档同步（§11.2 同一编辑批次）**：CLAUDE.md §3.4/§6.2a、AGENTS.md 对应条目、project_state.md、data_tracker.md/data_dictionary.md。

### Phase 4 — 稳态更新机制
1. **每日**：Windows 计划任务收盘后跑 update_daily_data.py --no-qlib（原始层 + 日频集）；run_daily_qa 随后跑并在失败时告警（冻结期"故意不调度"的注释同步移除）。
2. **每月**：一个一键 driver（scripts/monthly_calendar_bump.py，支持 --dry-run）串起：磁盘检查 → 全量重建到新末端 → 冻结段字节审计 → 安全发布 → approvals 换绑 → QA → 文档 stub。
3. **备份保留策略**：.bak 只留最近 1 份，driver 内置修剪。
4. **后续演进（不在关键路径）**：(a) 滚动政策 + 真正实现 max_calendar_lag_days 检查；(b) 真·追加式增量物化器（按天 append bin 而非全量重物化），仅当月度全量重建时长不可接受时才立项。

### Phase 5 — 研究面开封（解冻红利，独立后续）
- 把 2026-03→至今登记为新鲜 sealed OOS 窗口资产；已 spent-OOS 的候选（E-wave 6 核、GP、arXiv D 批）可在新窗口做一次真正的新鲜复验；2026-06-22 标记为 STALE 的 deployment-gate 结论（fill-price-aware 开盘闸下需重跑的）借新窗口一并重跑。

## 3. 风险与对策

| 风险 | 对策 |
|------|------|
| Tushare 限流/封锁 | 严格串行单 fetcher；财报季批量抓取放夜间；driver 断点续跑；429 加睡不加激进重试 |
| 磁盘（staging+backup ≈ 2× 树） | Phase 0 先修剪 .bak；同卷发布闸已内建（BuildGateError） |
| 缺口期 restatement 追溯改写派生季值 | 既有不变量：ledger 重建后所有季值缓存失效；Phase 3 测试全扫覆盖 |
| 未经演练的代码路径（非 scoped update） | 第一次解冻不用它，走 mode=all 全量路径 |
| 历史 provenance 语义被改写 | D1：老政策文件永久不动，新政策新 id |
| 新 OOS 窗口被日常研究烧掉 | D3：出生即封存；只有 seal 申领可触碰 |
| 治理语义变更引入漏洞（OOS_END 等值→绑定） | GPT 跨审重点问题；改动前后 promotion gate 测试全跑 |
| 与在途分支冲突 | 解冻独立分支；合并次序在 Phase 0 定 |

## 4. 工作量估计

约 **3-4 个工作日**（其中约 2 天是无人值守的抓取/重建机器时间）+ GPT 跨审往返。关键人工节点：D1-D3 决策、Phase 2.1 小代码改动评审、Phase 2.3 审计报告确认、Phase 3 换绑确认。
===END PLAN===

QUANTITATIVE-RESEARCH PRINCIPLES — check the change against EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (the cardinal rule). Fundamentals align on ann_date (NOT end_date), shift(1), forward-fill. Research PIT reads go ONLY through pit_research_loader / qlib_windowed_features — never raw data/pit_ledger/* and never hand-rolled alignment. Ask: does any step of the catch-up or rebuild let a value at time t use information not knowable at t?
2. OUT-OF-SAMPLE IS SACRED & SEALED. The 2021-01-01..2026-02-27 window is spent for many candidates; the newly exposed 2026-03..now window is genuinely fresh for ALL registry factors and must not be burnable by casual research. Never re-run a sealed OOS to "verify".
3. SURVIVORSHIP. Universes include delisted + suspended names; stock_basic refresh must keep L,D,P.
4. FACTOR-EVAL STANDARD. (Not directly touched — flag if the plan accidentally touches it.)
5. EXECUTION & COST REALISM. Execution-domain datasets (stk_limit, suspend_d, ST ranges) must be extended in lockstep with the calendar or backtests on the new window silently degrade.
6. NO LEVERAGE. (Not touched.)
7. NO HEDGE WORDS. Every quantitative claim in the plan is either backed by a named file/line or explicitly marked as an estimate to be measured (e.g. the ~82 trading-day gap, the stage=full rebuild duration).
8. FOUR-LAYER PIPELINE. (Not touched.)
9. MULTIPLE TESTING. The born-sealed new window must not become a de-facto repeated test set via governance loopholes.

REVIEW QUESTIONS
1. D1 (new policy id, old YAML immutable): does replacing the in-place `frozen: false` flip with a NEW frozen policy at the new end date leave any governance hole? In particular: historical artifacts record calendar_policy_id=frozen_20260227_system_build — after the thaw, can they still be replayed/validated correctly against the retained old policy file, and is there any code path that resolves "the" policy globally instead of per-artifact?
2. D3 is the riskiest governance change: today leak-freedom of promotion evidence is STRUCTURAL (provider calendar_end == OOS_END means no post-OOS data exists in the provider at all). After the thaw, post-OOS_END data EXISTS and protection retreats to ResearchAccessContext window clamps + holdout seals. Is that acceptable? What CONCRETE compensating guard would you require before implementation (e.g., mandatory allowed_end ≤ recorded OOS_END assertion at seal-claim time, loader-level default end-clamp at 2026-02-27 for discovery stages, a lint)? Is "born-sealed by declaration" sufficient, or must there be a mechanical clamp?
3. PIT of the catch-up itself: the plan fetches ann_date-anchored families by ann_date windows (2026-02-28→now, chunked) instead of by report period, to capture gap-period restatements of older periods. Any remaining traps you see (update_flag dedup semantics, f_ann_date families vs ann_date-only families, in-window ordering, VIP endpoint pagination, report_rc create_time anchoring, dividends div_proc states)?
4. D2 cadence: monthly freeze-bump means EVERY publish changes provider_build_id and therefore requires rebinding ~25 approval YAMLs + a byte-parity audit of the frozen range (depth9 precedent). Is this per-publish ceremony sound AND sustainable as a monthly routine? Would you instead require a build-lineage mechanism (parent_build_id chain with additive-only proofs) now, or is deferring that acceptable?
5. The `max_calendar_lag_days` check is defined but enforced nowhere. The plan defers implementing it until the later rolling-policy phase (because step-1 stays frozen-semantics). Acceptable, or must thaw-step-1 land the lag check?
6. Coupling-audit completeness: §0.1 lists 8 enforcement points and §Phase-3 lists 18 test files / 132 pinned-date occurrences. From your reading of the repo, what did the audit MISS (candidates: cache_manifest window checks, qlib_windowed_features clamps, holdout seal stores, dashboard, workspace skill docs, .claude skills)?
7. Execution order and risk: anything in Phases 0-4 you would re-order, gate differently, or add a --dry-run/rollback step to? Is the choice of mode=all full rebuild (over the never-exercised non-scoped mode=update path) right for step 1?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending plan text quoted and an exact suggested replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
