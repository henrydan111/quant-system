# Phase 5-B B3 自审（原子发布事务 + raw-input 绑定 + release-gate 强制，§10 前置）— 2026-07-13

*对象：`scripts/monthly_calendar_bump.py`（phase_publish 事务化 + attestation 记录 + execute 前置 CAS）、
`src/data_infra/tushare_lock.py`（provider_publish_lock）、`src/data_infra/provider_manifest.py` +
`schemas/provider_build.schema.json`（raw_input_manifest_root / parent_provider_build_id）、
`src/data_infra/pit_backend.py`（publish() 贯通）、`src/research_orchestrator/calendar_policy.py`
（require_raw_input_attestation）、`src/research_orchestrator/release_gate.py` +
`src/backtest_engine/event_driven/__init__.py`（正式跑强制接线）、+23 测试、CLAUDE/AGENTS §3.4 两条新不变量、
2026-07-04 手动 rebind 收编。分支 `calendar-unfreeze-phase5b-atomic-publish`（基 `calendar-unfreeze` 29a31f5）。
结论见文末。*

## 改动摘要（实现 REWORK-5 留置的 B3.2 + B3.3-5，task_5084e3f7）

| # | 交付 | 实现 |
|---|---|---|
| B3.3-5 | 原子事务 | `phase_publish` = 单锁域（`raw_maintenance_lock`→`provider_publish_lock` 固定锁序）内 verify→swap→bind：parent CAS + 全读集 raw manifest 重哈希 + 审计工件 sha256 + staged attestation + approvals CAS 全部在 swap **前一刻**重验（execute 时把这些钉进 dry-run report；旧版报告缺键=拒）；swap 走被证明的 `StagedQlibBackendBuilder.publish`（三重命名+单败自回滚；OSError 有界重试 3×5s，BuildGateError 不重试）；活体 manifest 回读校验；两阶段字节保持 rebind（逐文件 exact-token 恰一次替换 + 重解析验证 + 原字节留存）；0-drift 断言；rebind 记录 md + publish_record + journal。swap 后任何失败→恢复 approval 原字节 + 反向三重命名回滚（exit 4）；回滚失败 exit 5 + journal 恢复动作；QA（锁外，`run_daily_qa` 不取锁已核）失败 exit 6 不回滚。 |
| B3.2 | 绑定入 manifest | `raw_input_manifest_root`（64-hex，加载器拒畸形/大写）+ `parent_provider_build_id`（拒空白）为 **OPTIONAL** schema/加载器字段（活体 pre-thaw manifest 照常加载；to_dict 不臆造键，legacy 往返字节稳定）；`emit_manifest_at_publish`/`_emit_provider_manifest_at_publish`/`publish()` kwargs 贯通。 |
| B3.2 强制 | policy 旗标 | `CalendarPolicy.require_raw_input_attestation`（严格 `is True`，默认 False）；`generate_thaw_policy` 铸的每个政策置 true；`release_gate.assert_provider_raw_attestation`（duck-typed，无新 import 边）接线在 `_validate_provider_at_runtime`（pr8c 正式跑咽喉，policy+manifest 同在手）。强制随政策**前滚**：现活体 legacy 政策不受影响，下个月度政策起 fail-closed。 |
| 前置 | execute 早期 approvals CAS | 过期/带外 approval 绑定在多小时构建**之前**拒（publish 锁内再验一次）。 |
| 收编 | 2026-07-04 rebind 入库 | 主树遗留未提交的 25-YAML 两 token rebind + `2026-07-04_rebind_to_thaw_step1_publish.md` 以 patch-file 方式收编（PowerShell 管道会毁字节，改 `git diff --output` + `git apply`）；`test_approval_evidence` 活体烟测转绿。 |

## §3 不变量核对

| 项 | 判断 |
|---|---|
| §3.4 provider attestation | ✔ 强化而非削弱：manifest 新字段 OPTIONAL（活体加载不破）；formal 强制走 policy 旗标前滚。schema `additionalProperties:false` 下新键已入 schema。 |
| §3.4 calendar policy | ✔ 事务重验新政策：spent_oos_end/fresh_holdout_start==Phase-5 常量、frozen、calendar_end==target_end、require 旗标 must be true。政策文件 append-only 未动。 |
| §3.4 preload/字段门/研究门 | ✔ 未触。 |
| §3.4 approval-evidence binding | ✔ rebind 走 `load_approval_bindings` 严格加载器（malformed=拒）+ 逐文件 exact-token CAS + 重解析 + 事后 `evaluate_approval_evidence_bindings` 0-drift 断言；exempt 记录不触碰。 |
| §3.2 PIT | ✔ 本改动不产生任何研究数据路径；发布的是既有审计过的 staged build。无新 PIT 对齐代码。 |
| D1/D2/D3（解冻合同） | ✔ spent_oos_end 冻结常量重验；政策铸造逻辑除新增旗标外未变；发布仍是月度 bump 人手触发（§13 双旗标）。 |
| §6.3 publish 原子性 | ✔ 沿用同卷 st_dev 闸内建的 `publish()`；未新造交换原语；回滚=同一组重命名的逆序。 |
| §13 | ✔ 事务仍要求 `--publish-approved --i-reviewed-the-dryrun` 人手触发；本会话**未运行**任何 mode=all 重建、未触活体 provider（全部测试在 tmp + worktree fixture 上）。 |

## 九项量化研究原则核对（canonical template）

1. **PIT/无前视**：不适用于新代码路径（无因子/信号/对齐逻辑）；事务保证的是"发布的 provider == 审计过的那个输入切面"，即 PIT 证据链的完整性。✔
2. **OOS 神圣**：无 OOS 引用。机械追踪：diff 中 "oos" 仅出现在 `spent_oos_end` 常量重验（治理常量，非 OOS 读取/选择）。无 seal 消费。✔
3. **生存者偏差**：不适用（fresh-window survivorship 审计沿用，其 sha256 现被钉进事务）。✔
4. **因子评估标准**：不适用。✔
5. **执行/成本真实性**：不适用。✔
6. **无杠杆**：不适用。✔
7. **无对冲词**：所有验证数字为实测测试计数（37/23/1049/141 等，命令可复现）；环境失败逐文件归类且以 main-树复跑证明（`test_pre_open_isolation` 2 例 main 树同败=既有问题，spawn task_741b05c9）。§3 staleness 交叉核对：本文引用的唯一历史结论是 REWORK-5 的 B3 残留描述，未引用任何带 staleness 旗标的业绩数字。✔
8. **四层管线**：不适用。✔
9. **多重检验**：不适用。✔

## 自查中发现并已修的问题

- `_sub_binding_token` 的 `\r?` 在捕获组外→CRLF 文件替换会静默丢 CR。修：`([ \t]*\r?)$` 入组。
- QA-fail 分支多余地重新构造 builder。修：复用作用域内 builder。
- swap 重试最初把 BuildGateError（决定性失败）也重试。修：仅 OSError 重试，活体缺失即停。
- `_approvals_all_bound_to` 会让 `ApprovalEvidenceConfigError` 裸抛。修：捕获→干净拒绝消息。
- **测试地雷（组合运行 9 败的根因）**：`tests/research_orchestrator/__init__.py` 使 pytest 以包形式导入该目录→`sys.modules['research_orchestrator']`=测试包，毒化裸命名空间导入。修：bump 脚本 research_orchestrator 导入改 `src.` 前缀（+ROOT 入 sys.path），与 pit_backend 同例。**遗留仓级隐患**（`backtest_engine`/`architecture` 测试目录同险；既有 `_phase_execute_impl` 裸导入同险已一并改）——留 GPT 裁是否需要仓级修复。
- PowerShell 文本管道毁 patch 字节→rebind 收编改 patch-file 路径。

## 已知限制（诚实披露，留 GPT 裁定）

1. **staged attestation 深度**：只覆盖身份小文件（calendars/day.txt + instruments/*.txt + build manifest.json 全内容 sha + features 顶层目录数）。241GB features 二进制在 execute→publish 窗口内的带外变异不被重哈希捕获（重哈希≈重建时长，不可行）；其内容由 execute 时冻结前缀审计+fresh-window 审计背书，且 staged 目录是 build-id 限定路径。
2. **报告自洽篡改**：dry-run report 是操作员自己的评审载体；一个把 report+工件一起改的人不被锁/CAS 阻止（威胁模型=带外进程/漂移，非恶意操作员）。
3. **端到端真发布未测**：事务全链在合成 staged/live 树上以真重命名/真 manifest 发射/真 YAML 重写驱动（23 测试），但 241GB 真树的首次执行留待下次月度 bump（§13 用户确认 + 真 staged build），与 REWORK-5 留置时的裁定一致。
4. **exit 6（QA 失败不回滚）**：QA 在锁外、发布一致之后；失败=告警+人工裁断（QA 失败可能与发布无关）。若 GPT 认为应回滚可改，但回滚一个一致发布引入的新风险（句柄锁、二次交换）大于保留。
5. **UNFREEZE_PLAN.md 未改**：其 §137"复用 _depth9_safe_publish.py"的描述被本事务取代（同一交换原语，自动化了）。计划文档是已 SHIP 的设计记录，实质修订应随 GPT 终审一并处置。

## 验证汇总

37 monthly 电池全绿（11 新事务测试含对抗性排序首位）；+4 provider_manifest 往返/fail-closed、+7 attestation gate/接线、+1 政策铸造旗标；组合四套件（data_infra+research_orchestrator+backtest_engine+architecture 单次 pytest）**1049 绿 + 16 skip**，39 败全数归类环境失败（worktree 无 gitignored 活体数据；每类以 FileNotFoundError 证据 + main-树全数据复跑绿证明；`test_pre_open_isolation` 2 例为 main 树同败的既有缺基准文件问题→task_741b05c9）。7 触及文件 py_compile 干净。**本会话零次触碰活体 provider/数据。**

**结论：clean for GPT。** B3.2 + B3.3-5 全部落地且每条有测试；验证与交换在同一锁域不可分（GPT REWORK-5 的裁定语义）；5 项已知限制显式留审。

---

## REWORK round 2（GPT 首审 REWORK：7 Blocker + 3 Major，独立故障注入全数复现）— 2026-07-13

GPT 审 `0525cc1`：**REWORK**。7 个探针全部是真缺陷——首版的"原子"只覆盖了 verify↔swap，没有覆盖 swap 之后的完整域，且多个 attestation 有 fail-open 洞。逐条闭合（每条带把 GPT 探针变成回归测试）：

| # | GPT finding（探针复现） | 修复 | 探针测试 |
|---|---|---|---|
| **B1** swap 成功后首个 `j("swap","ok")` 在回滚 try 之前——journal 写盘失败=新树 live+approval 旧+裸抛不回滚 | `_write_journal` 改**非抛出**（内吞+log，面包屑非闸门）；且 swap 成功起 journal/manifest 校验/换绑/状态/记录**全部**进单一 `try` 保护域 | `test_publish_survives_journal_write_failure_after_swap`（journal 路径指向目录=永远写失败→事务照常完成 exit 0） |
| **B2** exit-4 可为假：`_rebind_approval_files` 内部恢复失败时 originals 不外传（调用者拿空 dict 误判已恢复）；record 写序留假"成功换绑"md | 换绑拆为 **swap 前纯 planner**（`_plan_rebind` 零写入，originals 在任何写之前就在调用者手里）；恢复=`_restore_approval_files(written, originals)` **逐文件重读核验**并返回失败清单；回滚域删除本事务全部工件（publish_record、rebind md、新树 post-swap 文件）+回滚后 `live_provider_ids()==parent` 复核；**exit 4 仅当 problems 为空，否则 exit 5 + journal 点名**；提交型 md 改最后写 | `test_publish_rolls_back_when_rebind_write_fails_midway`（中途故障→字节全恢复+parent live）；`test_publish_reports_5_when_restore_also_fails`（a1 已换绑+恢复也失败→exit 5+journal 点名 a1.yaml）；`test_publish_rolls_back_when_record_write_fails`（record 故障→无假 md 残留） |
| **B3** approvals CAS 对删除 fail-open（loader 空目录返 []→删光仍发布 rebound:0） | execute 钉 `_approvals_attestation`（排序 *.yaml 文件名+逐文件 sha256+bound 数）；publish 要求**完全相等且 bound≥1**（增/删/改任一 YAML 拒发） | `test_publish_refuses_deleted_approvals`（删一个/删光都拒）+`test_publish_refuses_added_approval` |
| **B4（L1 被拒）** feature bin 字节变异仍原样发布 | `_staged_content_attestation`：staged 全树**每文件全内容 sha256**（线程池抗 open 延迟；按 features/<code> 分组 sidecar 定位漂移；execute 钉根→publish swap 前**全量重哈希**）。代价=每侧读全树一遍（月度可承受），sidecar 按 build-id 持久化 | `test_publish_refuses_feature_bin_mutation`（同尺寸字节变异→拒） |
| **B5** 门只接 event-driven；正式 Qlib 读取门（`qlib_windowed_features`→`provider_context`）未覆盖 | 双门（attestation+publish-state）接线 **`provider_context._resolve`**——两个 sanctioned data door 的共同咽喉；状态文件 digest 并入轮换安全缓存键（`--finalize-qa` 翻转→缓存键变→重验，不吃陈旧判定） | `test_provider_context_enforces_attestation_and_state` + `_legacy_policy_still_resolves` |
| **B6（L4 被拒）** QA 失败无机械隔离（正式 runtime 验证照过） | `publish_state.json` 标记：swap 域内写 `pending_qa`→QA 过绿翻 `ready`/失败 `qa_failed`+exit 6；`release_gate.assert_provider_publish_state` 双咽喉强制（**present 非 ready 连 legacy 政策也隔离**；required 时 absent 拒；foreign build 标记拒）；新增 **`--finalize-qa`** 恢复腿（崩溃后/QA 修复后续接，live build 必须==report staged build） | `test_publish_qa_failure_returns_6_and_quarantines`（qa_failed→门拒→finalize 翻 ready）+`test_publish_state_gate_quarantines_until_ready`+`test_formal_runtime_validation_refuses_quarantined_provider` |
| **B7** publish 锁非全局（裸 `builder.publish()` 可在 parent CAS 后插入） | 锁下沉公共咽喉：`StagedQlibBackendBuilder.publish()`+`provider_manifest` 两个发射器**自持** `provider_publish_lock`；锁改 **per-path singleton FileLock**（filelock 3.25.2 `is_singleton=True` 实测：同实例+计数可重入）→事务嵌套不死锁、跨进程互斥；**相对导入**（`from .tushare_lock`）解决 src./plain 双命名空间——singleton 按锁文件路径注册，两命名空间共享同一实例 | `test_builder_publish_acquires_global_lock`（裸 publish 必取锁）+happy-path 实测嵌套可重入 |
| **M1** "严格 bool"实为 fail-open（字符串 "true"→False，测试还钉死了该行为） | 非 bool 值**拒加载**（`CalendarPolicyError`）；铸造政策**整文件 sha256** 入 report，publish 重验 | `test_policy_flag_non_bool_fails_closed`（"true"/1/"yes" 全拒）+`test_publish_refuses_policy_file_drift` |
| **M2** provenance 不绑真实构建（publish 时 rev-parse；固定名 sidecar 被覆盖） | execute 捕 `_git_state()`（HEAD+dirty digest）入 report；publish 要求相等（漂移=拒）；`publish(source_git_commit=...)` 贯通发射 **execute-time** commit 并回读核验；raw manifest 三份持久化（固定名+per-build+**staged metadata/ 随 provider 出版**，在 content attestation 之前写入故被证明覆盖） | `test_publish_refuses_git_state_drift`+happy-path 断言 manifest 带 execute-time sha |
| **M3（L5 被拒）** UNFREEZE_PLAN 仍指手工流程 | Phase 3.4/4.1/5.2 已改（划线+«2026-07-13 Phase 5-B B3 取代»注记，指向新事务与 CLAUDE §3.4 不变量） | 文档 diff |

### L1-L5 裁定内化
L1 不接受→B4 全内容重哈希；L2 接受（保持可信操作员威胁模型）；L3 有条件接受→**修完后首个真实 241GB 运行仍需单独 §13 授权**（未变）；L4 原则接受但须机械隔离→B6；L5 不接受→已更新。

### 本轮自查发现并已修
- 我的双故障探针初版设计错误（fail a2 的写与恢复——但 a2 从未被写入无需恢复→verified exit 4 是**正确**行为）；改为"a1 已写+a1 恢复失败"才是真双故障。
- `provider_manifest`/`pit_backend` 内取锁的导入必须**相对**（双命名空间下 `src.` 前缀在部分脚本上下文不可解析；singleton 按路径注册使两命名空间共享同一锁实例）。

### 验证汇总（本轮）
焦点电池 **156 绿**（monthly 53 + gate 22 + manifest/policy/pit_backend/approval_evidence）；四套件组合 **1064 绿+16 skip**，39 败=与首版完全相同的 8 个环境文件（缺活体数据；main 树+全数据复核仍绿；`test_pre_open_isolation` 2 例=既有 main 树失败→task_741b05c9 处理中）；provider_context/pr8 消费者隔离复跑 81 绿；8 文件 py_compile 干净。**本会话仍零次触碰活体 provider。**

**结论：clean for GPT（re-review）。** 7 Blocker + 3 Major 全闭且每条有探针复刻测试；exit-4 现在是被证明的声明；attestation 覆盖全部发布字节与治理集合；隔离与锁均为机械強制。真实 staged tree 首跑（§13）与 GPT 复审仍是 final 前置。

---

## REWORK round 3（GPT 复审 #2 再 REWORK：6 P0 + 1 P1，跨 worktree/中断/TOCTOU 探针）— 2026-07-13

GPT 对 `e4ceeea` 再判 REWORK。全部有效——上一轮的"原子"只对 Exception 成立、只对本 checkout 成立、只到 pre-swap 哈希为止。逐条：

| # | GPT finding（探针复现） | 修复 | 探针测试 |
|---|---|---|---|
| **P0-1** 锁按 checkout 分隔（两个 worktree 可并发发布同一数据目录） | 锁身份锚定 **git common dir 父目录**（`_resolve_lock_root(source_root)`；全部 worktree → `E:\量化系统\logs\locks` 一套命名空间；主 checkout 路径不变=生产日更零迁移；git 不可用→降级本 checkout+响亮告警，绝不 env）。**测试当场抓到真 bug**：git 输出 UTF-8 而 `text=True` 按 cp936 解码→中文仓库路径 mojibake→显式 `.decode("utf-8")` | `test_lock_root_is_shared_across_worktrees`（真 git repo+worktree 双向解析等值）+ worktree 实测 `_LOCK_DIR` 与主库精确相等 |
| **P0-2** `KeyboardInterrupt`/`SystemExit` 绕过回滚（中断在第二个审批写后=半换绑+新树 live+无标记可恢复） | 保护域 **`except BaseException`**；**SIGINT 跨 swap+bind 区段延迟**（`_defer_sigint`：记录信号→一致状态后重抛；非主线程 no-op，由 BaseException 兜底）；swap 循环并入域内（`swap_completed` 区分原语自回滚 vs 需撤销）；中断→verified 回滚→重抛（journal `interrupted_rolled_back`/`interrupted_rollback_incomplete`） | `test_publish_interrupt_mid_rebind_rolls_back_then_reraises`（第二个审批写注入 Ctrl-C→字节全恢复+parent live+无 md/record→重抛）+ SystemExit 变体 |
| **P0-3** 哈希→交换 TOCTOU（attestation 返回后改 bin 仍发布并 ready） | 与 P0-4 合并解：**READY 门 = TOCTOU 边界**。`ready` 唯一出口 `_finalize_ready`：锁内对 **LIVE 树**全量重验（manifest CAS + 政策文件哈希 + 换绑后 approvals 集合 vs `approvals_post_rebind_root` + 树内 raw 自洽 + **全量 live 内容根**，排除恰两个发布自加文件、build manifest 显式路径）——预交换哈希之后任何时点的字节变更都到不了 ready（exit 5，隔离持续） | `test_ready_gate_refuses_bytes_changed_after_swap`（QA 期间改 live bin→exit 5+journal 点名 content root+状态停 pending_qa） |
| **P0-4** finalize 可把改过的 provider 标 ready（只查 build id+state 就跑 QA） | `phase_finalize_qa`：QA 前锁内 manifest CAS（build/policy/root/parent/commit）+ 报告钉齐检；QA 后走同一 `_finalize_ready` 全门。**QA=抽样，READY 门=证明** | `test_finalize_qa_cannot_green_changed_bytes`（qa_failed→改 bin→QA 放行仍 exit 5 停 qa_failed；复原字节→ready） |
| **P0-5** 裸 `{"state":"ready"}` 放行（build 绑定条件式） | 标记必须携带**非空 `provider_build_id`**（缺失/空白/非串=拒）；有 manifest 时强制相等 | gate 测试新增 unbound-ready 拒绝分支 |
| **P0-6** raw 来源读可变固定路径 sidecar（可声称 R2 实为 R1 构建） | 发布以 **staged 树内 `metadata/raw_input_manifest.json`**（已被内容证明覆盖）为唯一事实源：自检 root、与 report/sidecar 强等、`_verify_raw_manifest` 用它的文件表、发射入 provider_build.json 的 root 取自它；READY 门再验树内自洽 | `test_publish_refuses_raw_provenance_mismatch`（report+sidecar 一致伪造 R2、staged 副本 R1→拒） |
| **P1** 全量哈希 23M 路径+digest+行同时驻留（月度必 OOM） | `_staged_content_attestation` **按组流式**：逐 features/<code> 组哈希→组摘要→释放；全程只保 ~5.8k 组摘要；`exclude`/`build_manifest_path` 参数化供 READY 门复用 | 结构审（组语义与行格式不变；全电池根等值通过） |

### 本轮自查发现并已修
- cp936 解码毁中文路径（上表 P0-1）——若无该单测，生产锁目录会静默变成 mojibake 新目录=锁分裂。
- 成本披露更新：全内容哈希现为 **execute + pre-swap + READY 三读全树**（月度操作，每读数十分钟量级）；保留 pre-swap 读作 fail-early（可在复审裁剪）。

### 验证汇总（本轮）
焦点电池 **189 绿**（+7 新探针）；四套件组合 **1070 绿+16 skip**（环境失败集与基线逐文件一致）；worktree 下 `_LOCK_DIR == E:\量化系统\logs\locks` 精确等值实测。**本会话仍零次触碰活体 provider。**

**结论：clean for GPT（re-review #3）。** 6 P0+1 P1 全闭且每条有探针复刻测试；ready 是被完整重验过的声明；锁、回滚、隔离对中断与跨 worktree 均机械成立。真实 241GB 首跑（§13）与 GPT 复审 #3 仍是 final 前置。

---

## REWORK round 4（GPT 复审 #3 再 REWORK：3 P0 + 3 Major，布尔 vs 磁盘事实 / 哈希→ready 窗口 / 数据根锁）— 2026-07-13

GPT 确认前七探针全过，但新探针再破三处。逐条：

| # | GPT finding（探针复现） | 修复 | 探针测试 |
|---|---|---|---|
| **P0-A** publish() 返回→`swap_completed=True` 之间的异常把 child 留 live 且被误判 pre-swap（真 publish 后立刻 SystemExit：child live、审批旧、无 marker、不回滚）| 处理器改**磁盘事实分类** `_disk_swap_state`（live manifest build + backup 目录；child_live→完整 verified 撤销；parent_live→原语已自回滚；unknown→exit 5 留 journal）；**持久 intent journal**（`publish_intent.json`，首次 rename 前必须写成功；swapping→committed_core/aborted/rollback_incomplete；未决 intent 阻断任何新 publish）| `test_publish_systemexit_right_after_swap_rolls_back_via_disk_truth`（真 publish 完成后 SystemExit→磁盘分类→全恢复→intent aborted→重抛）+ `test_unresolved_intent_blocks_new_publish` |
| **P0-B** 最后一次哈希→写 ready 之间仍可改写（锁只约束守锁者；"再加一次哈希"关不掉）| READY 门顺序改为：lease CAS → cheap pins → **封存 generation 只读**（`_seal_tree_readonly`，除控制面 marker 外每文件 +R）→ 对**已封存**内容全量哈希 → 写 ready。认证后的字节对任何守属性写者不可写。tamper 类失败 → **`suspect`**（publish+finalize 全阻断），恢复唯一路径=显式验证型 **`--restore-parent`**（反向换绑→.bak parent 换回→parent ids+0 drift 证明；绝不静默自动恢复——按 GPT 处置意见）| `test_ready_seal_blocks_later_writes`（ready 后写 bin=PermissionError）+ `test_ready_gate_refuses_bytes_changed_after_swap`（→suspect+finalize 阻断）+ `test_finalize_qa_cannot_green_changed_bytes_then_restore_parent`（suspect→restore-parent 全演练：parent 回 live、审批回绑、0 drift、child 归位）|
| **P0-C** 锁仍非共享数据根全局（两个独立 clone 同数据根≠同锁；git 失败退化每检出一把）| 存储锁（raw+publish）身份=**规范化 `storage.data_root`**→`<data_root>/.locks/`（任何检出同店同锁）；身份不可解析→**`LockIdentityError` 拒绝**（绝不警告后继续）；账号级 api_call_lock 保留 repo 锚（账号是机器资源非店资源）| `test_data_lock_identity_shared_across_checkouts`（两独立 clone 绝对同店→同锁；相对 ./data→各自店各自锁=正确语义）+ `test_data_lock_identity_unresolvable_refuses` |
| **Major-D** 真实 SIGINT 语义与文档/测试不符（defer=core 提交后才抛）| 按 GPT 选项 1：**诚实文档化**——真信号=一致 core 提交+`pending_qa` 隔离，`--finalize-qa` 续接（\_defer_sigint/CLAUDE §3.4 措辞重写）；in-flow 抛出的异常（SystemExit/注入 KeyboardInterrupt=崩溃类）仍走 verified 回滚后重抛；**真信号测试**用 `signal.raise_signal(SIGINT)` 钉死两种语义的分界 | `test_real_sigint_defers_commits_core_then_finalize` |
| **Major-E** 并发 QA 把已 ready 的同代覆盖回 qa_failed | **QA attempt lease**：`_begin_qa_attempt`（同锁内 last-starter-wins 写 active_qa_attempt）；fail/ready 写前同锁 CAS（lease+build+state）；过期 worker 记 `superseded`（exit 7）什么都不改 | `test_stale_qa_worker_cannot_overwrite_ready` |
| **Major-F** 回滚可遗留假 publish_record（原子写成功→布尔置位前中断）| **每事务记录** `publish_record_<txid>.json`（canonical；固定名仅便览副本）；marker 携带 `transaction_id` 供 finalize 定位；回滚清理**按 txid 磁盘驱动**（per-tx 记录+md 按既定路径 unlink；固定名副本读出 transaction_id 匹配才删）——不再依赖任何进程内布尔 | 既有 record-fault/中断探针在新机制下全绿（清理断言不变）|
| 文档偏差 | READY 门 raw manifest 只比 root 不算 files 自洽根 | 补 `_manifest_root(files)==root` 重算；表述改为 root+file-list 自洽 | ready 门电池 |

### GPT 首跑前置清单（照单全收，进 runbook）
1. ✔ 本轮 P0 修复+回归（post-swap SystemExit / ready 前篡改（封存化解）/ 独立 clone 共享数据根）。
2. ☐ 操作员在**同卷一次性数据副本**上完整演练：publish→rollback→qa_failed→finalize→并发 QA lease→suspect→restore-parent（驱动即本 driver，路径由副本 config 决定）。
3. ☐ 实测三次全树哈希耗时/峰值内存/可用磁盘并留档（`--execute` 与 READY 门各自打印 file_count/bytes；操作员记录墙钟）。
4. ✔ 正式读取门三态拒绝（pending_qa/qa_failed/suspect）已由 gate 电池覆盖。
5. ☐ 以上全过后另行 §13 申请 live 首跑。

### 验证汇总（本轮）
焦点电池 **200 绿**（monthly 62 + gate 25 + daily-5c/fetchers 锁迁移 + 其余）；四套件 **1076 绿+16 skip**（环境失败集逐文件同基线）。封存产生的只读残留由测试级 autouse unseal 清理。**本会话仍零次触碰活体 provider。**

**结论：clean for GPT（re-review #4）。** 3 P0+3 Major 全闭且每条探针复刻；"已发布字节可在认证后被改写"这一最重残余风险由**封存只读 generation** 机械关闭；suspect/restore-parent 给出了被验证的恢复路径。真实 241GB 首跑（§13+前置清单 2/3/5）与 GPT 复审 #4 仍是 final 前置。

---

## REWORK round 5（GPT 复审 #4 再 REWORK：5 P0 + 1 Major，跨 checkout/伪造/锁资源/封存范围）— 2026-07-13

GPT 确认前七 + disk-truth + 普通篡改 + 真 SIGINT + QA lease 探针全过，新对抗探针再破五处（+1 Major）。逐条：

| # | GPT finding（探针复现） | 修复 | 探针测试 |
|---|---|---|---|
| **P0-A** 事务态 checkout-local（A 崩溃后 B 看不到 A 的 intent→把 A 未 QA 的 child 当 parent 发布，B 返 6）| intent + 每事务 record + **报告快照**迁到**共享 store 事务目录** `_tx_dir()`=`<data_root>/qlib_transactions/`；marker 绑 transaction_id；finalize/restore 走 `_load_tx_report()` 从快照读 pin（任何 checkout 可续接）；未决 intent 阻断每个 checkout | `test_unresolved_intent_blocks_new_publish_cross_checkout`（断言 intent 在共享 store 内 + 阻断）|
| **P0-B** --restore-parent 中断半重绑（两反向审批间 KeyboardInterrupt→child live+审批不统一+内建恢复拒）| restore 整体进 `_defer_sigint`+`except BaseException` 域；中断→`_restore_approval_files` 撤销已写反向审批（byte-verified 回统一 child-bound）+intent `restore_interrupted`+重抛；可直接重跑 | `test_restore_parent_interrupt_rolls_back_partial_rebind`（中断→撤销→重跑 exit 0→parent live）|
| **P0-C** finalize 审批 CAS 可由可变 record 伪造（改审批到 forged_build + 改 record 的 approvals_root→ready，绑定检查仍报 1 drift）| marker 钉 **record_sha256**（publish 时；record 改写即破）+核对 record 全字段（txid/build/policy/parent/raw/content/commit）+**直接跑 `evaluate_approval_evidence_bindings` 语义绑定**（伪造 root 骗不过；任何 binding drift=tamper→suspect）| `test_finalize_refuses_forged_record`（digest 破）+ `test_finalize_refuses_binding_drift_even_with_consistent_forge`（连 digest 一起重钉→语义绑定仍抓）|
| **P0-D** provider 锁按 data_root 但 config 允许 qlib_data_dir 分离（两 raw root 同 provider→两锁）+driver 硬编码 `PROJECT_ROOT/data` | `provider_publish_lock(qlib_dir=…)` 按**规范 live provider 目录**取锁（`<qlib_parent>/.locks/provider_publish__<name>.lock`）；builder/emitter 传各自 qlib_dir；driver 全 live/raw 路径走单一 `_live_paths()`（BuildPaths）+`_tx_dir()`；非标准/分离布局 `_assert_standard_layout()` **开始前拒** | `test_provider_lock_keyed_by_qlib_dir_not_raw_root`（两 raw root 同 provider→同锁）+ `test_publish_refuses_nonstandard_layout` |
| **P0-E** 封存按 basename 豁免（嵌套 `metadata/audit_payload/publish_state.json` ready 后可改）| `_seal_tree_readonly` 改**精确 tree-relative** 豁免（仅 `metadata/publish_state.json`）；外部 build manifest（在内容根内）一并 chmod 只读 | `test_seal_covers_nested_control_plane_basename_and_build_manifest`（嵌套同名 + build manifest ready 后 PermissionError；真 marker 仍可写）|
| **Major-F** Tushare API 锁 repo-anchored（两 clone 同 token 并发抓）| 账号锁 + rate-spacing 迁 **per-user token 指纹目录** `~/.quant_tushare_locks/<fp>/`（TUSHARE_TOKEN env/.env→sha256[:16]；token 只作不可逆指纹）| `test_account_lock_is_per_token_not_per_checkout`（同 token 跨 checkout 同目录、跨 token 不同、明文不出现）|

### 本轮自查发现并已修
- `_write_publish_state` 状态转移会丢 `record_sha256`/`parent_build_id`（marker 每次重写只带 transaction_id/active_qa_attempt）→ 补进 carried-forward 集合（否则 pending_qa→lease 重写就把 digest 绑定丢了，happy-path 直接踩 suspect——自测当场抓到）。
- 锁模块拆分：`_LOCK_DIR`→`_ACCOUNT_LOCK_DIR`（账号）+`_DATA_LOCK_DIR`（raw）+`_resolve_provider_lock_path`（provider，按 qlib_dir）；三处测试注入点同步迁移。

### 已知残余（诚实披露，留 GPT 裁 — 均在 re-review #4 prompt 的开放问题里提过，本轮 GPT 未升级为 P0）
- **封存只挡改/删既有文件，不挡在已封存目录内新建文件**（新增 bin 不改既有认证字节但可加一列 provider 会serve）——L2 可信操作员/意外威胁模型下的残余，是否 in-scope 留 GPT。
- **.bak 树现带只读文件**，D2 修剪工具须先清属性（`_unseal_tree` 可复用；已在文档注记）。
- **QA lease 活性**：worker 在另一 worker 的 QA-pass 与其 `_finalize_ready` 取锁之间抢 lease→finalize 见外来 lease 返 7 留 pending_qa（需再 finalize）——正确性安全、活性可接受。

### 验证汇总（本轮）
焦点电池 **207 绿**（+9 新探针）；四套件 **1083 绿+16 skip**（环境失败集逐文件同基线）；provider_context 门接线消费者（cache/r4/d3/spent-oos）隔离复跑 **55 绿**。封存只读残留由 autouse unseal fixture 清理。**本会话仍零次触碰活体 provider。**

**结论：clean for GPT（re-review #5）。** 5 P0+1 Major 全闭且每条探针复刻；"跨 checkout 硬崩溃后未 QA child 被静默继承"这一最重残余风险由**共享 store 事务目录 + 未决 intent 全 checkout 阻断**关闭；伪造 record 由 digest+语义绑定双闭；锁按真实资源取值。真实 241GB 首跑（§13+前置清单）与 GPT 复审 #5 仍是 final 前置。
