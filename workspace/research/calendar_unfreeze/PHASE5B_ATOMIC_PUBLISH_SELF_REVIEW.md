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
