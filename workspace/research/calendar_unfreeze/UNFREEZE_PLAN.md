# 日历解冻计划（Calendar Unfreeze Plan）— v3 定稿

*起草 2026-07-01 · GPT 5.5 Pro §10 跨审三轮：Round-1 REVISE（10 findings 全接受→v2）→ Round-2 REVISE（M6/M7+3 附加全接受→v3）→ **Round-3 SHIP**（M6/M7/附加 1-3 全 RESOLVED，0 新 issue；处置表 §6/§7/§8）· 状态：**定稿，可执行***

**⚠ GPT 终审残余风险（实现纪律，执行时必须遵守）**：M6 解析器（D3 条目 8）**不是发布校验器**——它只管钳制；解冻 provider 上线前仍必须同时满足 manifest-政策等值/兼容校验 + Phase 2 无硬编码闸全绿，不得把"解析器能兜底"当作放行理由。
*目标：把冻结在 2026-02-27 的本地数据日历稳定、高效地推进到当前，并建立可持续的更新机制。*

**v2 相对 v1 的两个结构性变化（来自 Blocker）：**
1. **B1**：D3 从"声明封存"升级为**机械封存**——loader 层默认钳制 + seal 强制 + lint/测试，且**必须在解冻 provider 发布之前全部就位**（阶段重排：原 Phase 3 的常量清理工作拆分，闸类工作前移为新 Phase 2"发布前墙"）。
2. **B2**：发布前审计从"bin 字节 + 日历追加"扩展到 **universe/instruments 侧车的成员矩阵前缀等值**（冻结段内每一天的 all_stocks/st_stocks/csi* 成员必须与旧 live 完全一致，漂移即发布阻断）。

---

## 0. 调查结论：冻结到底"冻"在哪里（事实基础，全部已核实）

### 0.1 强制执行点（解冻必须逐一处理）

| # | 执行点 | 位置 | 行为 |
|---|--------|------|------|
| 1 | 冻结政策 YAML（全库唯一政策） | `config/calendar_policies/frozen_20260227_system_build.yaml` | `frozen: true`，policy/manifest/live 三方日历末端必须严格相等 |
| 2 | 正式运行时校验 | `src/backtest_engine/event_driven/__init__.py:218-235` `_validate_provider_at_runtime` | frozen 政策：`policy.calendar_end_date == live == manifest`，不等即 raise |
| 3 | 日常 QA 校验 | `scripts/run_daily_qa.py:161-181` | 与运行时校验同语义 |
| 4 | Approval 证据绑定 | `src/data_infra/approval_evidence.py` + `config/field_registry/approvals/*.yaml`（约 25 个） | 每个 approval 绑定 `provider_build_id` + `calendar_policy_id`，与 live `provider_build.json` 不一致 → daily QA 红 |
| 5 | Manifest 发布默认值 | `src/data_infra/pit_backend.py:4132` | `publish(calendar_policy_id="frozen_20260227_system_build")` 为硬编码默认；`run()`（4326 行）调用 `publish()` 时**不传参**，且 `build_qlib_backend()`/CLI 完全没有暴露该参数 |
| 6 | 正式验证步骤硬编码 | `src/research_orchestrator/validation_steps.py:956, 1112` | IS/OOS 正式回测步骤写死 `calendar_policy_id="frozen_20260227_system_build"` |
| 7 | Promotion 证据 OOS 末端 | `src/research_orchestrator/promotion_evidence.py:39` `OOS_END = "2026-02-27"` | 无泄漏保证依赖 provider calendar_end == OOS_END |
| 8 | 再验证窗口末端 | `src/alpha_research/factor_lifecycle/revalidation.py:29` `END = "2026-02-27"` | 同上性质 |

### 0.2 代码缺口（解冻前必须知道的"没实现"）

- **`max_calendar_lag_days` 是死字段**：`calendar_policy.py:43,77-83` 定义并在 `frozen:false` 时强制要求填写，但**没有任何调用方真正执行 lag 检查**。YAML 注释里"解冻无需改代码"的说法只对了一半。
- **日常增量路径不扩展日历**：`update_daily_data.py` 的 `trigger_qlib_incremental` 传 `touched_symbols` → scoped_update 分支（`pit_backend.py:3904-3926`）**跳过 `_build_price_csvs` + `_run_dump_bin`**，K 线 bin 和 `calendars/day.txt` 永远不会被追加。日历扩展只能走非 scoped 路径（全树 `copytree`）或 mode=all 全量重建。
- **`update_daily_data.py` 只支持单日**，没有多日追赶循环。
- 非 scoped `mode=update` 的全树拷贝 = 已知磁盘隐患（约 241GB / 2300 万文件）。

> **执行期注记（2026-07-02）**：并行的 share-capital 治理会话已把 live provider 身份轮换为 `depth9_20260630_sharecap_reanchor_20260701`（日历/边界不变，仅 3 个股本 bin 修正 + patches sidecar）。**Phase 3 的父 build 与 Phase 4 换绑的"旧 id"以该轮换后身份为准**；冻结段字节审计的基线 = 当前 live（含修正后的股本 bin，与本分支已含的 `_materialize_share_capital_daily` 重建代码一致）。快照 `baseline_snapshots/provider_build_pre_unfreeze_v2_sharecap.json`。

### 0.3 数据现状与缺口体量

- 全部核心数据末端 = 2026-02-27（daily/index/trade_cal 各 4,410 个交易日；`data/data_tracker.md`）。
- 缺口 = 2026-03-02 → target_end，**约 82 个交易日（估计值，Phase 1 刷新 trade_cal 后以实际为准）**。
- ⚠ 缺口正好覆盖**年报季**：FY2025 年报（4-30 截止）+ 2026Q1 季报全横截面 + 6 月分红除权高峰——追赶不是"补几天行情"而是补一整个财报季。
- provider 昨天刚全量重建发布（`depth9_20260630`，2026-07-01T06:00 发布）——**安全发布 + 字节审计 + approval 换绑的完整先例就在昨天**（`workspace/scripts/_depth9_safe_publish.py`、`_rebind_approvals_depth9.py`、`config/field_registry/approvals/2026-07-01_rebind_to_depth9_publish.md`）。⚠ 时长证据：rebind md 记录 depth9 为 `stage=provider-only`，manifest 记录 `stage: full`——两处记录不一致；**已验证的只是 provider 重物化可一夜完成，全链 `stage=full` 真实时长未验证**，Phase 0 实测为准。

---

## 1. 三个设计决策（v2 修订版）

### D1：新政策文件 + "无全局政策"不变量（Round-1 M2 强化）

政策文件是 **append-only 治理文件**：老 `frozen_20260227_system_build.yaml` 永久不动；解冻落地为**新的冻结政策** `frozen_<target_end>_thaw_step1.yaml`。

**"无全局政策"不变量**（安全条件不是"零代码改动"，而是"没有任何代码路径在需要 artifact 级政策时解析全局政策"）：

- 每个正式 artifact / prescription / approval / cache manifest / provider manifest / 验证运行 / promotion 证据 / holdout seal 都**同时绑定** `provider_build_id` + `calendar_policy_id`；
- 历史 artifact 的回放/校验用**其记录的**政策与 provider build，绝不用解冻后的 live 政策替代；
- `load_calendar_policy()` 一律要求显式 id；唯一允许"读 live 政策"的场景是明确限定的 live-provider 检查（daily QA 的 provider_manifest_check，以及 D3 的 loader 钳制——两者的对象本来就是当前 live provider）；
- **CI/lint 新增**：(a) 在 legacy fixture / 显式旧-artifact 测试之外硬编码 `frozen_20260227_system_build` → fail；(b) publish/build/validation API 存在 `calendar_policy_id` 默认值 → fail（参数改为**必填**，`pit_backend.py:4132` 的默认值删除而非改值）；(c) 任何回放路径用 live 政策替代 artifact 记录政策 → fail。

### D2：稳态节奏 = 每日原始层同步 + 每月 provider 重建换绑（含 M3 保留策略修正）

- 每次 publish 必然产生新 `provider_build_id` → 约 25 个 approval 换绑 + 审计。**每日 publish = 每日换绑仪式，不可持续**；月度可承受。
- 原始层与 provider 解耦：**原始层每天追**（便宜、无治理开销、摊平 Tushare 负载），provider 每月集中重建（本地操作，不碰 API）。
- 完整 build-lineage 系统**不作为第一次解冻的前置**，但两件轻量事**现在就做**（M3）：
  - **引用型 build 保留规则**：`.bak` 修剪只允许删除**无引用**的 build。凡出现在 approval 审计记录 / 正式 artifact / promotion 证据 / revalidation 证据 / holdout seal 申领 / frozen selection 记录 / deployment-gate 记录中的 provider build，必须保留完整树，**或**保留不可变回放核验包（`provider_build.json` + 政策 YAML + 日历文件哈希 + bin 前缀哈希 + 侧车成员矩阵哈希 + approval 绑定快照 + 审计脚本哈希）；
  - **父 build 元数据**：月度 driver 每次发布写入 `parent_provider_build_id`、`old/new_calendar_end`、`append_only_calendar_proof_hash`、`frozen_prefix_bin_audit_hash`、`sidecar_membership_audit_hash`、`approval_rebind_audit_hash`。
- 滚动政策（`frozen:false`）作为后续演进，且受 m1 守护规则约束（见 Phase 5.4）。

### D3：新窗口出生即封存 —— **机械闸，且发布前必须就位**（Round-1 B1 重写）

2026-03 → target_end 对**全部注册因子**（含已 spent 2021→2026-02 OOS 的候选）是真正未被观测的新 OOS 资产。"声明封存"不足够——旧保证是**结构性**的（provider 里物理不存在 OOS 末端之后的数据），解冻后该结构消失，防线必须机械重建：

1. **政策字段**：新政策 YAML 增加（additive、可选字段，不动 schema_version 必填集）：
   ```yaml
   spent_oos_end: 2026-02-27        # 已花费 OOS 的末端 = 探索默认上限
   fresh_holdout_start: 2026-02-28  # 新鲜 holdout 起点
   ```
2. **默认钳制（loader 层，fail-closed）**：两扇受认可的门——`pit_research_loader`（沙盒）与 `qlib_windowed_features`（正式）——以及 factor/feature cache、research orchestrator、验证步骤、dashboard 数据投影，默认 `allowed_end ≤ spent_oos_end`（从 **live manifest 声明的政策**读取，这是 D1 允许的 live-provider 检查场景）。
3. **越界访问 fail-closed**：effective end > `spent_oos_end` 的读取必须失败，除非 `ResearchAccessContext` 携带有效的 holdout seal 申领。**钳制实现在 loader/access 层，不只在 promotion_evidence / revalidation 包装层**。
4. **Seal 申领记录**：绑定 candidate/factor id、目的、请求窗口、`allowed_start/end`、`provider_build_id`、`calendar_policy_id`、code/config hash、申领人、时间、one-shot 状态（现有 `HoldoutSealStore` + `frozen_set_hash` 键体系覆盖大部分——差异部分补齐）。同一 post-freeze 窗口不得用于探索性反复测试。
5. **promotion/revalidation 语义**：`OOS_END`/`END` 从模块常量改为政策驱动（`spent_oos_end`），允许 `provider_calendar_end ≥ OOS_END` **仅当**评估窗口显式绑定 seal 或既有 spent-OOS 窗口；**绝不默认取 live provider 末端**。
6. **CI/lint/测试**：新增测试与 lint 覆盖——默认探索读取在 live 末端 > 2026-02-27 时钳到 2026-02-27；无 seal 的越界读取失败；有 seal 的越界读取只在 sealed 窗口内成功；cache manifest 不得跨 `allowed_end`/`provider_build_id`/`calendar_policy_id` 复用；研究域直读 raw/pit_ledger/裸 D.features 继续由既有 lint（PIT002、`lint_no_bare_qlib_features`）封死，白名单仅限基础设施。
7. **次序（硬性）**：**上述闸 + 测试合并且全绿，才允许 Phase 3.4 安全发布**。先发布、后补闸（v1 的次序）不允许。
8. **政策边界解析器（Round-2 M6）**：钳制代码统一调用 `resolve_spent_oos_boundary(policy, calendar)`，解决"闸代码已合并、live 还是不含新字段的老冻结政策"的过渡态：
   - policy 含 `spent_oos_end` → 直接使用（并与 provider 日历互验；`fresh_holdout_start` 同）；
   - policy 缺该字段且 `frozen == true` → `spent_oos_end = policy.calendar_end_date`，`fresh_holdout_start = 其后第一个交易日`；若 provider 日历恰止于 `spent_oos_end`（老冻结态），则不存在新鲜 holdout 窗口，一切 post-spent 读取 fail-closed；
   - `frozen == false` 或字段缺失/非法的其他情形 → fail-closed（直到 `max_calendar_lag_days` 强制检查落地且测试绿）。
   **CI 必测**：老 `frozen_20260227_system_build`（无新字段）默认读钳到 2026-02-27；新 thaw_step1 政策在 `provider_calendar_end > spent_oos_end` 时默认读仍钳到 `spent_oos_end`；解冻政策的 `spent_oos_end` 缺失/非法 → fail-closed，**且该测试必须走 manifest 声明新政策的完整路径（manifest 指向 thaw 政策 id 但 YAML 缺/坏字段），不能只用手工构造的 policy 对象**（Round-3 实现注记，测试标题点名该子情形）。
   **定位注记（Round-3 终审）**：本解析器只负责钳制语义，**不是发布校验器**——"解冻 provider + 老格式政策"的配对必须由 manifest-政策等值校验与 Phase 2 闸在 publish/QA 层拒绝，解析器的钳制兜底不构成对该配对的放行。

---

## 2. 执行计划（六个阶段，v2 重排：闸在发布前）

### Phase 0 — 前置与设计冻结（0.5 天）
1. 本计划 v2 过 GPT re-review 至无 Blocker。
2. 磁盘审计：E: 盘可用 ≥ 1.5× provider 树；按 D2 引用型保留规则修剪历史 `data/qlib_data.bak_*`。
3. 基线：冻结态 `run_daily_qa` 全绿存档；记录当前 `provider_build.json`；解冻工作开独立分支。
4. 敲定 D1-D3（v2 版）。

### Phase 1 — 原始层追赶（1-2 天，绝大部分无人值守串行抓取）
1. **先刷 `trade_cal` + `stock_basic`**。`stock_basic` 明确按 `list_status ∈ {L, D, P}` 全量刷新（m3：绝不过滤到当前上市名单；保留 list_date/delist_date/名称与状态历史，PIT universe 构建依赖）。
2. **确定 target_end（m2）**：追赶目标**不是"今天"**，而是 `target_end` = 最后一个**完整**交易日——收盘后且各必需原始端点通过就绪检查（vendor 已更新）的最近交易日。**新冻结政策的 `calendar_end_date` 必须等于 target_end**；进行中/部分填充的交易日绝不进入正式发布。
3. **行情类（按 trade_date 分区）**：追赶 driver（`workspace/scripts/catchup_daily_range.py`，断点续跑 + 进度 + 日志），逐日循环 `DailyDataUpdater.update_for_date`、跳过 Qlib 转换，覆盖 2026-03-02→target_end：daily OHLCV+估值+adj_factor、指数日线、Phase 3 日频集（moneyflow / hk_hold / margin_detail / stk_limit / top_list / top_inst / block_trade / cyq_perf 等）。**严格串行、单 fetcher、base_sleep=1.5 不降**（§6.1）。`update_reference_data` 提出逐日循环，只跑一次。
4. **基本面（ann_date 锚定）——端点 PIT 追赶合同（M1）**：按 `ann_date` 窗口批量抓取（2026-02-28→target_end，按周/双周分块），**明确不用按报告期抓取**（会漏缺口期内针对更早报告期的 restatement 公告 = PIT 缺口）。在此之上，每个端点先在 `workspace/research/calendar_unfreeze/endpoint_contracts.yaml` 落一条**入库合同**再抓：
   - 字段：`query_date_fields` / `visibility_date_field`（可见性锚）/ `fallback_visibility_rule` / `natural_key` / `version_key` / `revision_fields`（update_flag 等）/ `status_fields`（div_proc 等）/ `max_rows_per_call` / `pagination_or_recursive_split_rule` / `dedup_order` / `completeness_assertions`；
   - **income/balancesheet/cashflow（+quarterly）**：ann_date 与 f_ann_date 都持久化；可见性由既有 `DATASET_SPECS` 合同执行（5 statement families 锚 `max(ann_date, f_ann_date)`，4 event families 锚 ann_date——已是 §3.2 不变量）；**绝不按 ts_code/end_date 去重到"最新"**，保留 report_type/update_flag/修订字段供 ledger 重建；
   - **indicators**：`refresh_indicator_history.py` staged 刷新；显式测试 update_flag 语义——缺口期内对老报告期的更新只能从其可见日起生效，绝不回溯到可见日之前；
   - **dividends**：不得把预案/股东大会/实施折叠成一行终值；按 ann_date + div_proc 状态版本化，晚阶段才知道的字段只从晚阶段公告日可见；
   - **holder_number / forecast / report_rc**：逐端点声明可见性锚（report_rc = 既有 create_time/+2 锚；对旧 create_time 行的修订用重叠窗口扫描兜底）；
   - **分页/完备性**：单块返回行数触到端点上限或可疑边界值 → 递归二分日期区间直至低于上限；**静默截断 = QA 失败**；
   - `verify_database.py` 断言：无端点缺合同、无未解决的截断/重复键/缺可见日警告。
5. **事件/另类端点增量**：stk_holdertrade、suspend_d、namechange、stock_st_daily、index_weights（3-6 月各月）。
6. **完整性闸**：`verify_database.py` + 更新 `data/data_tracker.md`。
7. **运行纪律（Round-2 附加要求）**：**在 Phase 2 闸全绿之前，追平后的原始层不是研究面**——期间禁止任何研究 notebook / dashboard 刷新 / 因子扫描 / 临时 raw·PIT 读取触碰 2026-02-27 之后的新数据；追赶分支仅作运维用途。

### Phase 2 — 发布前墙：D3 机械闸 + 政策贯通 + 耦合审计（新增，B1/M2/M4/M6/M7；1-2 天代码 + 评审）
1. **政策贯通（M2）**：`calendar_policy_id` 参数贯通 `build_qlib_backend()` → `run()` → `publish(...)` + CLI `--calendar-policy`，参数**必填无默认**；新政策 YAML `frozen_<target_end>_thaw_step1.yaml`（含 `spent_oos_end`/`fresh_holdout_start`）。
2. **D3 机械闸落地**（§1-D3 条目 1-6 + 条目 8 解析器的实现 + 测试）。
2a. **可执行硬编码全部在本阶段清除（Round-2 M7）**：`validation_steps.py:956/1112` 的 `calendar_policy_id` 改为从 prescription/配置/artifact 记录流入；`promotion_evidence`/`revalidation` 的窗口末端改为从记录的 `calendar_policy_id`（经条目 8 解析器）或显式 seal 读取。**Phase 2 完成后，不得残留任何可执行的政策/窗口常量**（仅报错文案等非执行文本可留待 Phase 4）。
3. **D3 访问耦合审计（M4）**：对所有能物化/缓存研究数据的路径逐一审计并加测试——`pit_research_loader`、`qlib_windowed_features`、`ResearchAccessContext`、`cache_manifest`/factor cache、`HoldoutSealStore` + seal 校验器、`promotion_evidence`、`revalidation`、`validation_steps`、回测引擎正式运行时、dashboard、workspace 脚本、notebook helper、`.claude` skills 文档、一切直连 qlib provider / raw pit_ledger 的 helper。要求测试：默认探索读钳制；无 seal 越界失败；有 seal 只在窗口内成功；cache manifest 不跨 `allowed_end`/build/policy 复用；直读继续被 lint 封死。
4. **"无全局政策" lint（D1）** 上线。
5. **本阶段全部合并 + 全绿是 Phase 3.4 发布的硬前置。**

### Phase 3 — Ledger + Provider 重建、审计、发布（1 天+，主要机器时间）
1. **全量重建**：`build_qlib_backend.py --stage full --mode all --calendar-policy frozen_<target_end>_thaw_step1`（staged，不立即 publish）。选 mode=all 而非未经演练的非 scoped update：**稳定优先**（provider 重物化一夜有 depth9 实证；全链时长未验证，接受更长机器时间）。ledger 用新 ann_date 重建（P0-4 确定性；⚠ `derive_single_quarter_value` 会因缺口期 restatement 追溯改写派生季值——季值缓存按既有不变量失效重算）。
2. **发布前审计（B2 扩展版）**，全部通过才可发布：
   - **bin 前缀**：每个 bin 文件 ≤2026-02-27 的日期段与旧 live **逐字节一致**（全量 size 审计 + 确定性抽样 SHA；例外仅限单独批准的 provenance-breaking 迁移，本次预期为零）；
   - **日历**：`calendars/day.txt` = 旧 4,410 天 + **仅追加**尾部；
   - **侧车成员矩阵（B2 核心新增）**：对 `all_stocks` / `st_stocks` / `csi300/500/1000` 及一切 universe/tradability 侧车——**侧车集合由 provider 树/manifest 枚举发现，不允许仅按硬编码清单**（Round-2 附加要求）——把区间表物化为旧日历上的**逐日成员矩阵**，断言 ≤2026-02-27 每一天与旧 live 完全相等。行级字节等值不要求（end date 延长属正常），但 **spent 窗口内成员漂移 = 发布阻断**（侧车由刷新后的 raw 再生——`pit_backend.py:3852-3872`——namechange/ST/权重的历史修正必须被显式发现并走批准流程，不允许静默漂移）；
   - **审计工件持久化**：`prefix_bin_hashes`、`calendar_append_proof`、`sidecar_membership_hashes`、新旧 `provider_build_id`/`calendar_policy_id`、`audit_script_hash`。
3. **解冻 dry-run 报告（m4）**：发布前产出并人工过目——计划 target_end、新政策 id、staged build id、磁盘前后估计、将交换的文件、将保留的备份、前缀审计摘要、侧车成员审计摘要、待换绑 approval 清单。
4. **安全发布**：复用 `_depth9_safe_publish.py` 三步原子交换（同卷 `st_dev` 闸内建），旧 live 保留为 `.bak`（受 D2 引用型保留规则管理）。

### Phase 4 — 发布后换绑与验证（验证性质，不再含可执行常量清理；0.5 天）
1. **Approvals 换绑**：约 25 个 YAML 同换 `provider_build_id` + `calendar_policy_id`（driver 照 `_rebind_approvals_depth9.py`），审计 md 的证据 = Phase 3.2 全套审计工件；`evaluate_approval_evidence_bindings()` → 0 drift。
2. **硬编码残留断言（M7 后 Phase 4 仅做验证）**：断言 legacy fixture / 显式旧-artifact 回放测试之外**无任何可执行的** `frozen_20260227_system_build` 残留（可执行清理已全部在 Phase 2 完成）；仅清理非执行文本（如 `event_driven/__init__.py:489` 报错文案）；对**老 artifact 政策**与**新 thaw_step1 政策**各跑一次正式验证 smoke。
3. **测试全扫**：18 个测试文件 132 处钉死日期逐一核（fixture 自包含的预期不红）；`run_daily_qa` / `audit_qlib.py` / `qlib_smoke.py` / `test_pit_live_provider.py` + Phase 2 新增闸测试全绿。
4. **文档同步（§11.2 同批）**：CLAUDE.md §3.4/§6.2a、AGENTS.md、`project_state.md`（含跨审 verdict 记录）、`data_tracker.md`/`data_dictionary.md`。

### Phase 5 — 稳态更新机制
1. **每日**：计划任务收盘后跑 `update_daily_data.py --no-qlib`（原始层 + 日频集）；`run_daily_qa` 随后跑并失败告警（冻结期"故意不调度"注释同步移除）。
2. **每月**：一键 driver（`scripts/monthly_calendar_bump.py`，`--dry-run` 必备）串起：磁盘检查 → 端点就绪检查定 target_end → 全量重建 → 前缀+侧车审计 → dry-run 报告 → 安全发布 → 换绑 → QA → 父 build 元数据 + 文档 stub。
3. **保留策略（M3）**：只修剪**无引用** build；引用型 build 保留全树或回放核验包（见 D2）。**修剪前必须完成对全部引用存储（approvals / 五注册表 evidence / seal store / frozen selection / deployment-gate 记录——此列表是示例不是穷尽白名单，"全部引用存储"按字面执行，未来新增证据存储自动纳入）的完整扫描；扫描无法枚举任一引用源时，修剪 fail-closed**（Round-2 附加要求 + Round-3 实现注记）。
4. **滚动政策守护规则（m1）**：在 `max_calendar_lag_days` 的运行时 + daily QA 强制检查落地并测试全绿之前，**任何 `frozen:false` 政策不得被 live provider / 正式验证 / daily QA / promotion / revalidation / 月度 driver 选用**；QA 增加检查：`active_policy.frozen == false` 时要求 lag 强制测试绿 + `live_calendar_end ≥ last_complete_trade_date − lag`。
5. **后续演进（不在关键路径）**：滚动政策；真·追加式增量物化器（仅当月度全量重建时长不可接受时立项）。

### Phase 6 — 研究面开封（解冻红利，独立后续）
- 2026-03→target_end 登记为新鲜 sealed OOS 窗口资产（此时已有 D3 机械闸保护）；
- 已 spent-OOS 候选（E-wave 6 核、GP、arXiv D 批）可经 seal 申领做一次真正新鲜复验；
- 2026-06-22 标记 STALE 的 deployment-gate 结论（fill-price-aware 开盘闸）借新窗口一并重跑。

---

## 3. 风险与对策（v2）

| 风险 | 对策 |
|------|------|
| **新 OOS 窗口物理暴露于 live provider（Round-1 首要残余风险）** | D3 机械闸（loader 钳制 + seal + lint + cache 绑定）**发布前**就位（Phase 2 硬前置 Phase 3.4） |
| **政策"脑裂"过渡态（Round-2 首要残余风险）：闸读 live 政策但新旧政策字段/硬编码未解析齐** | D3 条目 8 解析器（老政策无新字段 → 钳到其 calendar_end_date；非法即 fail-closed）+ M7 可执行硬编码全部于 Phase 2 清除 + 双政策 smoke（Phase 4.2） |
| Phase 1-2 间隙：raw 已追平、闸未绿、老 provider 仍 live | Phase 1.7 运行纪律：追平后的原始层非研究面（受认可 door 读的仍是老 provider，直读被既有 lint 封死） |
| 侧车再生静默改写冻结段 universe/ST/指数成员 | Phase 3.2 成员矩阵前缀审计，漂移即阻断 |
| Tushare 限流/封锁 | 严格串行单 fetcher；财报季批量放夜间；断点续跑；429 加睡 |
| 抓取静默截断/漏 restatement | M1 端点合同 + 递归二分 + verify_database 断言；ann_date 窗口法 |
| 磁盘（staging+backup ≈ 2× 树） | Phase 0 修剪（引用型保留规则）；同卷发布闸内建 |
| 缺口期 restatement 追溯改写派生季值 | 既有不变量：ledger 重建后季值缓存失效；测试全扫覆盖 |
| 未演练代码路径（非 scoped update） | 第一次解冻不用，走 mode=all |
| 历史 provenance 语义改写 | D1 append-only + 无全局政策 lint + 回放用记录政策 |
| 治理语义变更（OOS_END 等值→绑定）引入漏洞 | D3 条目 5：绝不默认 live 末端；re-review 复核 |
| 一次性 seal 证据因备份修剪不可回放 | M3 引用型保留 + 回放核验包 |
| 与在途分支冲突 | 独立分支；合并次序 Phase 0 定 |

## 4. 工作量估计（v2）

约 **5-6 个工作日**（v1 为 3-4；新增 Phase 2 发布前墙的闸实现 + 测试 + 耦合审计约 1.5-2 天），其中约 2 天为无人值守机器时间 + GPT re-review 往返。关键人工节点：D1-D3 v2 决策确认、Phase 2 闸代码评审、Phase 3.2/3.3 审计与 dry-run 报告确认、Phase 4.1 换绑确认。

## 5. 与既有路线图的关系

`workspace/research/trading_agents_design/ROADMAP.md` 把"解冻日历 + 日度接入"列为其 Phase 3 的闸——本计划是该闸的实现方案；其 Phase 0-2（≤2026-02-27 历史文本 sealed-OOS）不依赖解冻，可并行。

## 6. GPT Round-1 findings 处置表（2026-07-01，verdict = REVISE）

| # | Finding | 处置 | 落点 |
|---|---------|------|------|
| B1 | D3 无机械闸即发布 | **接受**，阶段重排：闸前移为 Phase 2 发布前墙 | §1-D3、Phase 2、Phase 3.4 前置 |
| B2 | 前缀审计缺侧车成员等值 | **接受** | Phase 3.2 |
| M1 | 端点 PIT 合同太松 | **接受（适配）**：合同 YAML + 完备性断言；注明 serving 侧语义已由既有 `DATASET_SPECS`/ledger 机制实现，合同主要约束 fetch 侧完备性与可见性锚声明 | Phase 1.4 |
| M2 | 缺"无全局政策"不变量 | **接受**：政策参数必填无默认 + lint + 回放用记录政策 | §1-D1、Phase 2.1/2.4 |
| M3 | `.bak 只留 1 份`对 sealed 证据不安全 | **接受**：引用型保留 + 回放核验包 + 父 build 元数据 | §1-D2、Phase 5.3 |
| M4 | 耦合审计漏 D3 访问路径 | **接受**，并入发布前墙 | Phase 2.3 |
| m1 | frozen:false 激活守护 | **接受** | Phase 5.4 |
| m2 | "至今"改确定性 target_end | **接受** | Phase 1.2 |
| m3 | stock_basic 显式 L/D/P | **接受** | Phase 1.1 |
| m4 | 解冻 dry-run 报告 | **接受** | Phase 3.3 |

**拒绝项：无。**

## 7. GPT Round-2 findings 处置表（2026-07-01，verdict = REVISE，无新 Blocker）

Round-2 逐条判定：B2/M1/M3/M4/m1/m2/m3/m4 = **RESOLVED**；B1、M2 = PARTIALLY RESOLVED（缺口即新 M6/M7）。

| # | Finding | 处置 | 落点 |
|---|---------|------|------|
| M6 | D3 钳制读 live 政策，但过渡期 live 还是不含 `spent_oos_end` 的老政策——缺失字段的解析器未指定 | **接受**：`resolve_spent_oos_boundary` 三分支解析器（含字段→用之；frozen 无字段→钳到 `calendar_end_date`；其余→fail-closed）+ 三条 CI 必测 | §1-D3 条目 8 |
| M7 | `validation_steps.py:956/1112` 硬编码清理排在发布后，与"发布前无全局政策"墙自相矛盾 | **接受**：可执行硬编码全部前移 Phase 2（2a）；Phase 4 降为纯验证（残留断言 + 双政策 smoke），仅非执行文本可留 Phase 4 | Phase 2.2a、Phase 4.2 |
| 附加 1 | 侧车集合应从 manifest/树枚举发现，不允许仅硬编码清单 | **接受** | Phase 3.2(c) |
| 附加 2 | Phase 1 追平后的 raw 在 Phase 2 绿前不是研究面 | **接受** | Phase 1.7 + 风险表 |
| 附加 3 | 引用扫描无法枚举任一引用源时修剪 fail-closed | **接受** | Phase 5.3 |

**拒绝项：无。**

## 7b. GPT Round-4（Phase 2 实现 diff 审查，2026-07-02，verdict = REVISE）处置表

无 Blocker；6 Major + 2 minor 全部接受，零拒绝。核心批评 = 正式出处链未端到端机械钉死。

| # | Finding | 处置 | 落点 |
|---|---------|------|------|
| M1 | promotion/revalidation 缺显式 seal 分支（D3.5 只实现了 spent-replay 支） | **接受**：守卫三分（短日历拒 / 等值过 / 长日历仅 spent-replay 或 活跃已申领 seal 且窗口覆盖 + provider/policy 绑定匹配）；绝不从 live 末端推断 | promotion_evidence 守卫重写 + 4 分支测试 |
| M2 | `_formal_calendar_policy_id` 回退 live manifest = 用 live 政策顶替 artifact 政策 | **接受**：`PrescribedRecipe.calendar_policy_id` 字段落地；helper 只认 prescription pin，未设/空白 **fail-closed，无 manifest 回退**（manifest 等值由运行时校验器另行执行） | hypothesis.py + validation_steps + 测试 |
| M3 | 进程级 `lru_cache` 跨轮换读旧身份 = 出处/绑定风险 | **接受**（方案 A）：中立模块 `provider_context` 以 manifest 文件 `(mtime_ns,size)` 为缓存键——轮换重写 manifest 即自动失效；另暴露 `refresh_live_provider_context()`（发布仪式 belt）；进程内轮换测试 | src/data_infra/provider_context.py |
| M4 | 缓存世代绑定"传了才校验"≠强制 | **接受**：`record_cache_write`/`assert_cache_reusable` 的两 id **必填非空白**（空白即 raise）；旧空值行失配即拒 = 有意的 legacy 失效路径（月度仪式归档 cache manifest，研究门无静默迁移模式） | cache_manifest + 测试 |
| M5 | 空串政策 id 必须在 legacy 迁移外非法 | **接受**：发布链校验非空白 + **必须解析到已提交政策 YAML**（加载即存在性校验）；formal helper 空白 fail-closed；缓存写空白 fail-closed | pit_backend run() 闸强化 |
| M6 | 测试不足 | **接受**：R4 电池（发布闸 None/空/空白/未知 id；增量 republish 保 manifest 记录政策；formal 出处 fail-closed；进程内轮换失效 + manifest 缺失 fail-closed；promotion 守卫 5 分支；seal 恢复世代绑定 3 例）+ 缓存世代 fail-closed 4 例 | test_r4_wall_hardening.py + permissive 扩展 |
| m1 | 16 点启发式不可成为"最后完整交易日"正式定义 | **接受**：注释明确 TEMPORARY CONSERVATIVE CAP，稳态锚归月度 driver 就绪检查 | run_daily_qa 注释 |
| m2 | 跨模块导入应归中立模块 | **接受**：`provider_context.py`（无副作用，不导入任何 door；两 door 都依赖它） | 新模块 + repoint |

**附带发现**：seal 的 crash-resume（allow_same_run）在 provider 轮换后会静默对不同数据恢复——超出 GPT 清单的自发现洞，已补：申领记录世代绑定 + 恢复路径世代不符即拒（holdout_seal.py）。

## 8. GPT Round-3 终审（2026-07-01，verdict = **SHIP**）

M6 / M7 / 附加 1 / 附加 2 / 附加 3 = **全部 RESOLVED**；新 issue：Blocker / Major / Minor 均为空。三条实现注记已折入正文：

1. M6 的"缺失/非法字段"CI 测试必须走 manifest 声明新政策的完整路径（D3 条目 8）；
2. 解析器不是发布校验器——manifest-政策等值 + Phase 2 闸仍是上线前置（文档头 + D3 条目 8 定位注记）；
3. 引用存储列表按字面"全部"执行、非穷尽白名单（Phase 5.3）。

终审残余风险 = **实现漂移**（把解析器兜底误当发布校验）。跨审 arc：REVISE → REVISE → SHIP，三轮共 15 findings + 3 实现注记，全部接受，**零拒绝项**。计划就此定稿。
