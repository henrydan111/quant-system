# GPT 5.5 Pro re-review prompt — Calendar Unfreeze Plan v2 (Round 2)

Status: ready to send AFTER `git push` of branch `trading-agents-design`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is ROUND 2 (re-review). In Round 1 you reviewed the calendar-unfreeze plan and returned REVISE with 2 Blockers (B1: D3 lacked a mechanical clamp and published before guards; B2: frozen-prefix audit omitted universe/instrument sidecar membership equivalence), 4 Majors (M1 endpoint PIT contracts, M2 no-global-policy invariant, M3 backup retention for referenced builds, M4 D3 access-coupling audit) and 4 Minors (m1 frozen:false guard, m2 deterministic target_end, m3 stock_basic L/D/P, m4 thaw dry-run). All 10 findings were ACCEPTED (none declined) and the plan was revised to v2. Your job now: verify each finding is adequately resolved, and check whether the revision introduced NEW problems. Do not re-litigate what you already approved unless the revision changed it.

REPO (public — fetch any file to verify against the live code; if raw fetch fails, the embedded text below is authoritative)
https://github.com/henrydan111/quant-system   (branch: trading-agents-design)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/<path>

CONTEXT
- CLAUDE.md (hard invariants §3, PIT §3.2, formal-run governance §3.4, research integrity §7):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/CLAUDE.md
- Plan v2 (embedded verbatim below):
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/calendar_unfreeze/UNFREEZE_PLAN.md
- Self-review incl. Round-2 preflight:
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/calendar_unfreeze/SELF_REVIEW.md
- Key code anchors (unchanged since Round 1): calendar_policy.py, event_driven/__init__.py (_validate_provider_at_runtime), run_daily_qa.py, approval_evidence.py, pit_backend.py (publish default L4132, scoped-update skip L3896-3926, sidecar regen L3852-3872), update_daily_data.py, promotion_evidence.py (OOS_END L39), validation_steps.py (L956/L1112), revalidation.py (END L29), and the depth9 precedent (config/field_registry/approvals/2026-07-01_rebind_to_depth9_publish.md).

SELF-REVIEW PREFLIGHT (Round 2) — completed before this request: verdict "clean for GPT re-review". Checked: (a) each of the 10 findings mapped to a concrete plan change (disposition table = plan §6); (b) faithfulness of each change against your exact replacement text; (c) new-content self-check — the loader clamp reads the LIVE manifest policy, which is documented as an explicit exception to the M2 no-global-policy invariant (live-provider checks only: daily QA + D3 clamp; artifact replay still uses the recorded policy); spent_oos_end/fresh_holdout_start enter the policy YAML as additive optional fields; effort estimate raised 3-4 → 5-6 days for the pre-publish wall. One deliberate ADAPTATION to flag: M1's endpoint contract is implemented as fetch-side completeness/visibility-anchor contracts (endpoint_contracts.yaml), while serving-side visibility semantics (max(ann_date,f_ann_date) for the 5 statement families, ann_date-only for the 4 event families, update_flag dedup) are already implemented and test-locked in the existing DATASET_SPECS + PIT-ledger machinery — the contract asserts rather than re-implements them.

WHAT CHANGED (authoritative)
The full revised plan v2 is embedded between the markers. Structural deltas vs Round 1: (1) new Phase 2 "pre-publish wall" — D3 mechanical clamps (policy fields spent_oos_end/fresh_holdout_start; loader-level default clamp in pit_research_loader + qlib_windowed_features + caches; fail-closed post-freeze reads without a holdout seal; promotion/revalidation window binding; lints + tests) must merge and pass BEFORE the thawed provider may publish; (2) Phase 3.2 audit extended with day-by-day sidecar membership-matrix equality over the frozen prefix (drift = publish blocker); (3) D1 gains the no-global-policy invariant (policy id parameter REQUIRED with no default — the hard default at pit_backend.py:4132 is deleted, not re-pointed); (4) D2/Phase 5 gain referenced-build retention + replay-verification bundles + parent-build metadata; (5) Phase 1 gains endpoint_contracts.yaml, deterministic target_end, explicit stock_basic L/D/P; (6) Phase 3.3 thaw dry-run artifact; (7) Phase 5.4 frozen:false activation guard until max_calendar_lag_days enforcement exists.

===PLAN V2===
# 日历解冻计划（Calendar Unfreeze Plan）— v2

*起草 2026-07-01 · v2 修订 2026-07-01：GPT 5.5 Pro Round-1 跨审判定 REVISE（2 Blocker + 4 Major + 4 Minor，全部接受，无拒绝项；处置表见 §6）· 状态：待 re-review*

**v2 相对 v1 的两个结构性变化（来自 Blocker）：**
1. **B1**：D3 从"声明封存"升级为**机械封存**——loader 层默认钳制 + seal 强制 + lint/测试，且**必须在解冻 provider 发布之前全部就位**（阶段重排：闸类工作前移为新 Phase 2"发布前墙"）。
2. **B2**：发布前审计从"bin 字节 + 日历追加"扩展到 **universe/instruments 侧车的成员矩阵前缀等值**（冻结段内每一天的 all_stocks/st_stocks/csi* 成员必须与旧 live 完全一致，漂移即发布阻断）。

## 0. 调查结论：冻结到底"冻"在哪里（事实基础，全部已核实）

### 0.1 强制执行点

| # | 执行点 | 位置 | 行为 |
|---|--------|------|------|
| 1 | 冻结政策 YAML（全库唯一政策） | config/calendar_policies/frozen_20260227_system_build.yaml | frozen: true，policy/manifest/live 三方日历末端必须严格相等 |
| 2 | 正式运行时校验 | src/backtest_engine/event_driven/__init__.py:218-235 _validate_provider_at_runtime | frozen 政策：policy.calendar_end_date == live == manifest，不等即 raise |
| 3 | 日常 QA 校验 | scripts/run_daily_qa.py:161-181 | 与运行时校验同语义 |
| 4 | Approval 证据绑定 | src/data_infra/approval_evidence.py + config/field_registry/approvals/*.yaml（约 25 个） | 每个 approval 绑定 provider_build_id + calendar_policy_id，与 live provider_build.json 不一致 → daily QA 红 |
| 5 | Manifest 发布默认值 | src/data_infra/pit_backend.py:4132 | publish(calendar_policy_id="frozen_20260227_system_build") 硬编码默认；run()（4326）调用 publish() 不传参；build_qlib_backend()/CLI 未暴露该参数 |
| 6 | 正式验证步骤硬编码 | src/research_orchestrator/validation_steps.py:956, 1112 | IS/OOS 正式回测步骤写死政策 id |
| 7 | Promotion 证据 OOS 末端 | src/research_orchestrator/promotion_evidence.py:39 OOS_END = "2026-02-27" | 无泄漏保证依赖 provider calendar_end == OOS_END |
| 8 | 再验证窗口末端 | src/alpha_research/factor_lifecycle/revalidation.py:29 END = "2026-02-27" | 同上性质 |

### 0.2 代码缺口

- **max_calendar_lag_days 是死字段**（calendar_policy.py:43,77-83 定义、frozen:false 时必填，但无任何调用方执行 lag 检查）。
- **日常增量路径不扩展日历**：trigger_qlib_incremental 传 touched_symbols → scoped_update 分支（pit_backend.py:3904-3926）跳过 _build_price_csvs + _run_dump_bin，K 线 bin 与 calendars/day.txt 永不追加。日历扩展只能走非 scoped 全树 copytree 或 mode=all 全量重建。
- **update_daily_data.py 只支持单日**，无多日追赶循环。
- 非 scoped mode=update 全树拷贝 = 已知磁盘隐患（约 241GB / 2300 万文件）。

### 0.3 数据现状与缺口体量

- 全部核心数据末端 = 2026-02-27（daily/index/trade_cal 各 4,410 交易日）。缺口 = 2026-03-02 → target_end，约 82 交易日（估计值，Phase 1 刷新 trade_cal 后以实际为准）。
- ⚠ 缺口覆盖**年报季**：FY2025 年报（4-30 截止）+ 2026Q1 全横截面 + 6 月分红除权高峰。
- provider 昨天刚全量重建发布（depth9_20260630）——安全发布 + 字节审计 + approval 换绑完整先例就在昨天（_depth9_safe_publish.py、_rebind_approvals_depth9.py、2026-07-01_rebind_to_depth9_publish.md）。⚠ 时长证据：rebind md 记录 stage=provider-only，manifest 记录 stage: full，两处不一致；已验证的只是 provider 重物化可一夜完成，全链 stage=full 时长未验证，Phase 0 实测。

## 1. 三个设计决策（v2）

### D1：新政策文件 + "无全局政策"不变量（M2 强化）

政策文件 append-only：老 YAML 永久不动；解冻落地为新冻结政策 frozen_<target_end>_thaw_step1.yaml。

**"无全局政策"不变量**：
- 每个正式 artifact / prescription / approval / cache manifest / provider manifest / 验证运行 / promotion 证据 / holdout seal 同时绑定 provider_build_id + calendar_policy_id；
- 历史 artifact 回放用**其记录的**政策与 build，绝不用解冻后 live 政策替代；
- load_calendar_policy() 一律显式 id；唯一允许读 live 政策的场景 = 明确限定的 live-provider 检查（daily QA 的 provider_manifest_check + D3 loader 钳制——两者对象本来就是当前 live provider）；
- **CI/lint 新增**：(a) legacy fixture / 显式旧-artifact 测试之外硬编码 frozen_20260227_system_build → fail；(b) publish/build/validation API 存在 calendar_policy_id 默认值 → fail（参数改**必填**，pit_backend.py:4132 默认值删除而非改值）；(c) 回放路径用 live 政策替代记录政策 → fail。

### D2：每日原始层同步 + 每月 provider 重建换绑（含 M3 保留策略）

- 每次 publish 产生新 provider_build_id → 25 个 approval 换绑 + 审计；每日 publish 不可持续，月度可承受。原始层每天追（便宜、摊平 Tushare 负载），provider 每月重建（本地操作）。
- 完整 build-lineage 不作第一次解冻前置，但两件轻量事现在做（M3）：
  - **引用型 build 保留规则**：.bak 修剪只删**无引用** build。凡出现在 approval 审计 / 正式 artifact / promotion 证据 / revalidation 证据 / holdout seal 申领 / frozen selection / deployment-gate 记录中的 build，保留全树**或**不可变回放核验包（provider_build.json + 政策 YAML + 日历哈希 + bin 前缀哈希 + 侧车成员矩阵哈希 + approval 绑定快照 + 审计脚本哈希）；
  - **父 build 元数据**：月度 driver 每次发布写 parent_provider_build_id、old/new_calendar_end、append_only_calendar_proof_hash、frozen_prefix_bin_audit_hash、sidecar_membership_audit_hash、approval_rebind_audit_hash。
- 滚动政策（frozen:false）后续演进，受 m1 守护规则约束（Phase 5.4）。

### D3：新窗口出生即封存 —— 机械闸，发布前就位（B1 重写）

2026-03 → target_end 对全部注册因子是真正未观测的新 OOS 资产。旧保证是结构性的（provider 里物理不存在 OOS 末端后的数据），解冻后该结构消失，防线机械重建：

1. **政策字段**（additive 可选字段）：spent_oos_end: 2026-02-27；fresh_holdout_start: 2026-02-28。
2. **默认钳制（loader 层，fail-closed）**：两扇受认可的门——pit_research_loader（沙盒）与 qlib_windowed_features（正式）——及 factor/feature cache、research orchestrator、验证步骤、dashboard 数据投影，默认 allowed_end ≤ spent_oos_end（从 **live manifest 声明的政策**读取，即 D1 允许的 live-provider 检查场景）。
3. **越界 fail-closed**：effective end > spent_oos_end 的读取必须失败，除非 ResearchAccessContext 携带有效 holdout seal 申领。钳制实现在 loader/access 层，不只在 promotion_evidence / revalidation 包装层。
4. **Seal 申领记录**：绑定 candidate/factor id、目的、请求窗口、allowed_start/end、provider_build_id、calendar_policy_id、code/config hash、申领人、时间、one-shot 状态（现有 HoldoutSealStore + frozen_set_hash 键体系覆盖大部分，差异补齐）。同一 post-freeze 窗口不得探索性反复测试。
5. **promotion/revalidation 语义**：OOS_END/END 从模块常量改政策驱动（spent_oos_end），允许 provider_calendar_end ≥ OOS_END **仅当**评估窗口显式绑定 seal 或既有 spent-OOS 窗口；绝不默认取 live provider 末端。
6. **CI/lint/测试**：默认探索读取在 live 末端 > 2026-02-27 时钳到 2026-02-27；无 seal 越界读取失败；有 seal 只在 sealed 窗口内成功；cache manifest 不得跨 allowed_end/provider_build_id/calendar_policy_id 复用；研究域直读 raw/pit_ledger/裸 D.features 由既有 lint（PIT002、lint_no_bare_qlib_features）封死，白名单仅限基础设施。
7. **次序（硬性）**：上述闸 + 测试合并且全绿，才允许 Phase 3.4 安全发布。先发布、后补闸不允许。

## 2. 执行计划（六阶段，闸在发布前）

### Phase 0 — 前置与设计冻结（0.5 天）
1. 计划 v2 过 GPT re-review 至无 Blocker。2. 磁盘审计：可用 ≥ 1.5× provider 树；按引用型保留规则修剪 .bak。3. 冻结态 run_daily_qa 全绿存档；记录当前 provider_build.json；开独立分支。4. 敲定 D1-D3。

### Phase 1 — 原始层追赶（1-2 天，多为无人值守串行抓取）
1. **先刷 trade_cal + stock_basic**，stock_basic 明确 list_status ∈ {L, D, P} 全量（m3：绝不过滤到当前上市；保留 list_date/delist_date/名称状态历史）。
2. **确定 target_end（m2）**：不是"今天"，= 最后一个**完整**交易日（收盘后且各必需原始端点通过就绪检查）。**新冻结政策 calendar_end_date 必须等于 target_end**；进行中/部分填充交易日绝不进正式发布。
3. **行情类**：追赶 driver（catchup_daily_range.py，断点续跑+进度+日志），逐日循环 update_for_date、跳过 Qlib 转换，覆盖 2026-03-02→target_end：daily OHLCV+估值+adj_factor、指数日线、Phase 3 日频集（moneyflow/hk_hold/margin_detail/stk_limit/top_list/top_inst/block_trade/cyq_perf 等）。严格串行、单 fetcher、base_sleep=1.5 不降。update_reference_data 提出循环只跑一次。
4. **基本面（ann_date 锚定）——端点 PIT 追赶合同（M1）**：按 ann_date 窗口批量抓取（2026-02-28→target_end，周/双周分块），明确不用按报告期抓（漏缺口期内对更早报告期的 restatement = PIT 缺口）。每端点先在 endpoint_contracts.yaml 落入库合同再抓：query_date_fields / visibility_date_field / fallback_visibility_rule / natural_key / version_key / revision_fields / status_fields / max_rows_per_call / pagination_or_recursive_split_rule / dedup_order / completeness_assertions。其中：income/balancesheet/cashflow（+quarterly）ann_date 与 f_ann_date 都持久化，可见性由既有 DATASET_SPECS 合同执行（5 statement families 锚 max(ann_date,f_ann_date)，4 event families 锚 ann_date——已是 §3.2 不变量），绝不按 ts_code/end_date 去重到"最新"，保留 report_type/update_flag/修订字段；indicators 走 refresh_indicator_history.py staged 刷新，显式测试 update_flag 语义（老报告期更新只从其可见日起生效）；dividends 不折叠 div_proc 状态，按 ann_date+div_proc 版本化；holder_number/forecast/report_rc 逐端点声明可见性锚（report_rc = create_time/+2 既有锚；旧行修订用重叠窗口扫描）；分页/完备性：单块触到端点上限或可疑边界 → 递归二分日期区间；静默截断 = QA 失败；verify_database.py 断言无端点缺合同、无未解决截断/重复键/缺可见日警告。
5. **事件/另类端点增量**：stk_holdertrade、suspend_d、namechange、stock_st_daily、index_weights（3-6 月）。
6. **完整性闸**：verify_database.py + 更新 data_tracker.md。

### Phase 2 — 发布前墙：D3 机械闸 + 政策贯通 + 耦合审计（新增，B1/M2/M4；1-2 天代码+评审）
1. **政策贯通（M2）**：calendar_policy_id 贯通 build_qlib_backend()→run()→publish() + CLI --calendar-policy，**必填无默认**；新政策 YAML（含 spent_oos_end/fresh_holdout_start）。
2. **D3 机械闸落地**（D3 条目 1-6 实现 + 测试）。
3. **D3 访问耦合审计（M4）**：pit_research_loader、qlib_windowed_features、ResearchAccessContext、cache_manifest/factor cache、HoldoutSealStore+seal 校验器、promotion_evidence、revalidation、validation_steps、回测引擎正式运行时、dashboard、workspace 脚本、notebook helper、.claude skills 文档、一切直连 qlib provider / raw pit_ledger 的 helper。测试：默认探索读钳制；无 seal 越界失败；有 seal 只在窗口内成功；cache manifest 不跨 allowed_end/build/policy 复用；直读被 lint 封死。
4. **"无全局政策" lint 上线（D1）**。
5. **本阶段全部合并 + 全绿是 Phase 3.4 发布的硬前置。**

### Phase 3 — Ledger + Provider 重建、审计、发布（1 天+，主要机器时间）
1. **全量重建**：--stage full --mode all --calendar-policy frozen_<target_end>_thaw_step1（staged，不立即 publish）。稳定优先选 mode=all（provider 重物化一夜有 depth9 实证；全链时长未验证）。⚠ derive_single_quarter_value 因缺口期 restatement 追溯改写派生季值——季值缓存按既有不变量失效重算。
2. **发布前审计（B2 扩展版）**，全过才可发布：(a) **bin 前缀**：每个 bin ≤2026-02-27 段与旧 live 逐字节一致（全量 size + 确定性抽样 SHA；例外仅限单独批准的 provenance-breaking 迁移，本次预期为零）；(b) **日历**：day.txt = 旧 4,410 天 + 仅追加尾部；(c) **侧车成员矩阵（B2 核心）**：all_stocks/st_stocks/csi300/500/1000 及一切 universe/tradability 侧车，把区间表物化为旧日历上的逐日成员矩阵，断言 ≤2026-02-27 每天与旧 live 完全相等。行级字节等值不要求（end date 延长属正常），**spent 窗口内成员漂移 = 发布阻断**（侧车由刷新后 raw 再生——pit_backend.py:3852-3872——namechange/ST/权重历史修正必须显式发现并走批准流程）；(d) **审计工件持久化**：prefix_bin_hashes、calendar_append_proof、sidecar_membership_hashes、新旧 build/policy id、audit_script_hash。
3. **解冻 dry-run 报告（m4）**：发布前产出并人工过目——target_end、新政策 id、staged build id、磁盘前后估计、将交换文件、将保留备份、前缀审计摘要、侧车成员审计摘要、待换绑 approval 清单。
4. **安全发布**：复用 _depth9_safe_publish.py 三步原子交换（同卷 st_dev 闸内建），旧 live 保留 .bak（受引用型保留规则管理）。

### Phase 4 — 发布后换绑与全面验证（0.5 天）
1. **Approvals 换绑**：约 25 个 YAML 同换 provider_build_id + calendar_policy_id（driver 照 _rebind_approvals_depth9.py），审计 md 证据 = Phase 3.2 全套工件；evaluate_approval_evidence_bindings() → 0 drift。
2. **残余常量清理**：validation_steps.py:956,1112（政策 id 从配置/prescription 流入）、event_driven/__init__.py:489 报错文案（OOS_END/END 已在 Phase 2 政策化）。
3. **测试全扫**：18 个测试文件 132 处钉死日期逐一核；run_daily_qa / audit_qlib / qlib_smoke / test_pit_live_provider + Phase 2 新闸测试全绿。
4. **文档同步（§11.2 同批）**：CLAUDE.md §3.4/§6.2a、AGENTS.md、project_state.md（含跨审 verdict 记录）、data_tracker/data_dictionary。

### Phase 5 — 稳态更新机制
1. **每日**：计划任务收盘后 update_daily_data.py --no-qlib；run_daily_qa 随后跑并失败告警。
2. **每月**：一键 driver（monthly_calendar_bump.py，--dry-run 必备）：磁盘检查 → 端点就绪定 target_end → 全量重建 → 前缀+侧车审计 → dry-run 报告 → 安全发布 → 换绑 → QA → 父 build 元数据 + 文档 stub。
3. **保留策略（M3）**：只修剪无引用 build；引用型保留全树或回放核验包。
4. **滚动政策守护（m1）**：max_calendar_lag_days 运行时 + daily QA 强制检查落地并测试全绿前，任何 frozen:false 政策不得被 live provider / 正式验证 / daily QA / promotion / revalidation / 月度 driver 选用；QA 增加：active_policy.frozen == false 时要求 lag 强制测试绿 + live_calendar_end ≥ last_complete_trade_date − lag。
5. **后续演进（非关键路径）**：滚动政策；追加式增量物化器（仅当月度全量重建时长不可接受时立项）。

### Phase 6 — 研究面开封（独立后续）
- 2026-03→target_end 登记为新鲜 sealed OOS 窗口资产（已有 D3 机械闸保护）；已 spent-OOS 候选经 seal 申领做真正新鲜复验；2026-06-22 标 STALE 的 deployment-gate 结论借新窗口重跑。

## 3. 风险与对策（v2）

| 风险 | 对策 |
|------|------|
| 新 OOS 窗口物理暴露于 live provider（Round-1 首要残余风险） | D3 机械闸发布前就位（Phase 2 硬前置 Phase 3.4） |
| 侧车再生静默改写冻结段成员 | Phase 3.2 成员矩阵前缀审计，漂移即阻断 |
| Tushare 限流/封锁 | 严格串行单 fetcher；夜间批量；断点续跑；429 加睡 |
| 抓取静默截断/漏 restatement | M1 端点合同 + 递归二分 + verify_database 断言；ann_date 窗口法 |
| 磁盘 | Phase 0 修剪（引用型保留）；同卷发布闸内建 |
| restatement 追溯改写派生季值 | 既有不变量：ledger 重建后季值缓存失效 |
| 未演练路径（非 scoped update） | 第一次解冻走 mode=all |
| 历史 provenance 语义改写 | D1 append-only + 无全局政策 lint + 回放用记录政策 |
| OOS_END 等值→绑定引入漏洞 | D3 条目 5：绝不默认 live 末端 |
| 一次性 seal 证据因备份修剪不可回放 | M3 引用型保留 + 回放核验包 |
| 在途分支冲突 | 独立分支；合并次序 Phase 0 定 |

## 4. 工作量估计（v2）

约 5-6 个工作日（v1 为 3-4；新增 Phase 2 发布前墙约 1.5-2 天），其中约 2 天无人值守机器时间 + re-review 往返。

## 5. 与既有路线图的关系

trading_agents_design/ROADMAP.md 把"解冻日历 + 日度接入"列为其 Phase 3 的闸——本计划是该闸的实现方案。

## 6. GPT Round-1 findings 处置表（verdict = REVISE）

B1 接受（阶段重排，闸前移 Phase 2）；B2 接受（Phase 3.2 侧车成员矩阵）；M1 接受-适配（fetch 侧合同断言，serving 侧由既有 DATASET_SPECS/ledger 机制实现）；M2 接受（必填无默认 + lint + 回放用记录政策）；M3 接受（引用型保留 + 核验包 + 父 build 元数据）；M4 接受（并入发布前墙）；m1-m4 接受（Phase 5.4 / 1.2 / 1.1 / 3.3）。**拒绝项：无。**
===END PLAN V2===

RE-REVIEW QUESTIONS
1. B1 resolution: does the Phase 2 pre-publish wall + D3's 7-point mechanical contract fully close the "born-sealed by declaration" hole? Specifically judge: (a) clamping at the two sanctioned doors (pit_research_loader / qlib_windowed_features) + cache binding + existing direct-read lints — is any access path still uncovered? (b) the clamp reading the LIVE manifest policy as the source of spent_oos_end — acceptable as the documented exception to the no-global-policy invariant?
2. B2 resolution: is day-by-day membership-matrix equality over the frozen prefix (with row-level byte equality explicitly NOT required for extended end dates) the right assertion? Any sidecar or membership-bearing artifact still missing from the audit list?
3. M1 adaptation: is "fetch-side contracts assert, existing DATASET_SPECS/ledger machinery implements" an acceptable reading of your endpoint-contract requirement, or do you require contract enforcement deeper than the fetch layer?
4. New-issue scan: did v2 introduce any new hole — e.g. the required-no-default policy parameter breaking legitimate callers, the additive policy fields interacting badly with schema_version=1 validation, the Phase re-ordering creating a window where raw data is current but guards are merged yet the OLD frozen provider is still live (is that state safe?), or the referenced-build retention rule being circumventable?
5. Completeness: with v2 as written, list anything you would still require BEFORE the first thawed publish (not deferred-acceptable items).

OUTPUT FORMAT
- Per Round-1 finding: RESOLVED / PARTIALLY RESOLVED / NOT RESOLVED, with the exact remaining gap if not fully resolved.
- New issues ranked Blocker / Major / Minor with offending text quoted and exact suggested replacement.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
