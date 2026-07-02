# 自审记录 — 日历解冻计划（design-stage self-review，CLAUDE.md §10 前置）

*日期：2026-07-01 · 对象：`UNFREEZE_PLAN.md`（设计阶段，无实现 diff）· 审后状态：**clean for GPT***

## 一、按 §3 硬不变量逐条核对

| 不变量 | 结论 |
|---|---|
| 3.1 trade_cal 唯一地面真值 | ✔ Phase 1.1 先刷 trade_cal/stock_basic，后续一切以其为准 |
| 3.1 ST 权威源 st_stocks.txt | ✔ 已核实 mode=all 构建自动再生（pit_backend.py:3865-3870，输入 = stock_st_daily+namechange+calendar）；Phase 1.4 追平这两个原始层是前提（自审修正 #3 已写入计划） |
| 3.1 delist/IPO 合同（all_stocks 侧车） | ✔ build_all_stocks_universe 随构建再生（pit_backend.py:3852），stock_basic 刷新含 L,D,P |
| 3.2 PIT / ann_date 锚定 | ✖→✔ **发现 Blocker 并已修**：初稿 Phase 1.3 按报告期（20251231/20260331）批量抓基本面，会漏掉缺口期内公告的历史期 restatement → 改为按 ann_date 窗口分块抓（与 update_fundamentals 的 fetcher 语义一致）（自审修正 #1） |
| 3.2 report_rc create_time 锚 | ✔ Phase 1.4 单列，沿用既有 create_time/+2 锚 |
| 3.2 restatement→派生季值追溯改写 | ✔ 计划风险表明确：ledger 重建后季值缓存失效（既有不变量） |
| 3.3 执行域数据（stk_limit/suspend_d） | ✔ 均在 Phase 1 抓取清单 |
| 3.4 provider attestation / calendar policy / approval 绑定 | ✔ 这是计划的主体：新政策 id（D1）+ manifest 参数贯通（Phase 2.1）+ 换绑（Phase 3.1，depth9 先例） |
| 3.4 publish 原子性/同卷闸 | ✔ 复用内建 BuildGateError 闸 + depth9 安全发布次序 |
| 3.5 factor lifecycle / sealed OOS | ✔ D3 出生即封存；OOS_END 语义变更单列为 GPT 重点审查项 |

## 二、按跨审模板 9 条量化研究原则核对

1. **PIT/无前视**：核心风险 = 追赶抓取的完备性（restatement 覆盖）与 provider 重建后冻结段不变——分别由自审修正 #1 和 Phase 2.3 字节审计覆盖。
2. **OOS 神圣且封存**：解冻**扩大**而非侵蚀 OOS 资产（D3 出生即封存；已 spent 窗口的 seal 记录不受影响——seal 键 = frozen_set_hash，含 time_split，不依赖 provider 日历末端）。残留关注：OOS_END 从"等值"改"绑定"是治理语义弱化，已列为 GPT 首要审查问题。
3. **幸存者偏差**：stock_basic 全量刷新（含退市），all_stocks 再生。✔
4. **因子评估标准**：不适用（无因子变更）。
5. **执行/成本真实性**：不适用（数据扩展，不改引擎）。
6. **无杠杆**：不适用。
7. **无对冲措辞**：✖→✔ 初稿把 depth9 "一夜完成"当作 stage=full 全链时长证据，但 rebind md（stage=provider-only）与 manifest（stage: full）记录矛盾 → 改为"仅 provider 重物化时长有实证，全链时长未验证，Phase 0 实测"（自审修正 #2）。缺口交易日数 82 已标注为估计值、以刷新后 trade_cal 为准。
8. **四层管线**：不适用（无信号构建）。
9. **多重检验**：不适用；但 D3 防止新窗口被反复触碰，与该原则同向。

## 三、自审修正清单（已全部写入 UNFREEZE_PLAN.md）

1. **[Blocker] 基本面追赶改为 ann_date 窗口法**，弃报告期法（PIT 缺口：漏历史期 restatement）。
2. **[Major] depth9 时长证据矛盾如实标注**（provider-only vs full 记录不一致；全链时长未验证）。
3. **[Minor] instruments 侧车再生已核实**并写明前提（原始层先追平）。
4. **[Minor] 追赶 driver 把 update_reference_data 提出逐日循环**（避免 82 次重复全量拉 stock_basic）。

## 四、留给 GPT 的残留关注点

- D3 的 `OOS_END` 等值→绑定语义变更：日历延长后"provider 里不存在 OOS 末端之后的数据"这一**结构性**无泄漏保证消失，防线退到 ResearchAccessContext 窗口钳制 + seal——这是否可接受、需要什么补强闸。
- 月度 freeze-bump 的换绑仪式（每次 publish 换 25 个 approval + 字节审计）长期是否过重，有无更优治理结构（如 build lineage）。
- `max_calendar_lag_days` 检查缺失是否可以推迟到滚动政策阶段。
- 耦合面清单（8 个执行点 + 18 个测试文件 132 处日期）是否有遗漏。

**结论：clean for GPT。**

---

# Round-2 自审（v2 修订后，re-review 前置）— 2026-07-01

**背景**：GPT Round-1 verdict = **REVISE**（B1 D3 机械闸缺失且次序颠倒、B2 侧车成员前缀审计缺失、M1-M4、m1-m4）。全部 10 条接受，无拒绝项；处置表 = UNFREEZE_PLAN.md §6。

## 修订忠实性核对（逐条 vs GPT 原文）

- **B1**：D3 重写为 7 条机械闸（政策字段 / loader 默认钳制 / fail-closed / seal 记录 / promotion 绑定语义 / lint+测试 / **发布前次序硬性化**）；新增 Phase 2"发布前墙"，Phase 3.4 安全发布以 Phase 2 全绿为硬前置。✔ 与 GPT 替换文本逐项对应。
- **B2**：Phase 3.2 增加侧车**逐日成员矩阵**前缀等值断言（行字节等值不要求、成员漂移即阻断）+ 审计工件持久化清单。✔
- **M1**：endpoint_contracts.yaml 合同字段照单全收；**适配声明**（已在 §6 注明）：serving 侧可见性语义（`max(ann_date,f_ann_date)` 5 statement families / ann_date-only 4 event families、update_flag 去重）已由既有 `DATASET_SPECS` + ledger 机制实现并有测试锁定——合同的净新增约束是 **fetch 侧**（分页/截断/递归二分/字段保全/逐端点可见性锚显式声明）。该适配不削弱 GPT 要求，只是避免重复实现。
- **M2**：政策参数改**必填无默认**（比 GPT 要求更严：直接删默认值）+ 三类 lint + 回放用记录政策。✔
- **M3**：引用型保留 + 回放核验包 + 父 build 元数据（月度 driver 写入）。✔
- **M4**：并入 Phase 2.3 发布前耦合审计，路径清单与测试要求照单。✔
- **m1-m4**：Phase 5.4 / 1.2 / 1.1 / 3.3 落点。✔

## v2 新引入内容的自查

- loader 钳制读 **live manifest 政策** 与 D1"无全局政策"不变量的张力：已在 D1 显式豁免（live-provider 检查场景——daily QA 与 D3 钳制，其对象本来就是当前 live provider；artifact 回放仍用记录政策）。无矛盾。
- `spent_oos_end`/`fresh_holdout_start` 以 additive 可选字段进政策 YAML：`CalendarPolicy.from_dict` 需扩展 dataclass 可选字段（实现细节，Phase 2.1 覆盖），不动 schema_version=1 必填集。
- 工作量 3-4 → **5-6 工作日**（Phase 2 墙 +1.5-2 天），如实上调。
- 无对冲措辞检查：v2 新增文字中的量化断言均有 file:line 或标注"实现细节/估计"。

**Round-2 结论：clean for GPT re-review。**

---

# Round-3 自审（v3 修订后）— 2026-07-01

**背景**：Round-2 verdict = REVISE，收敛中（8/10 RESOLVED，无新 Blocker；B1/M2 = PARTIALLY，缺口具体化为新 M6/M7 + 3 条附加要求）。5 条全部接受，无拒绝项；处置表 = 计划 §7。

## 修订忠实性核对

- **M6**：D3 新增条目 8 `resolve_spent_oos_boundary` 三分支解析器，与 GPT 替换文本逐分支对应（含字段→用之并与日历互验；frozen 无字段→`calendar_end_date` 回退 + 老冻结态无新鲜窗口全部 fail-closed；`frozen:false`/非法→fail-closed）；三条 CI 必测照单（老政策钳 2026-02-27 / 新政策在 live 末端更长时仍钳 spent_oos_end / 缺失非法 fail-closed）。✔
- **M7**：`validation_steps.py:956/1112` + promotion/revalidation 窗口读取全部前移 Phase 2（新 2a），并加"Phase 2 后不得残留可执行政策/窗口常量"硬规则；Phase 4 降为验证性质（残留断言 + 老/新双政策 smoke + 仅非执行文本清理）。消除次序矛盾。✔
- **附加 1-3**：侧车枚举发现（Phase 3.2c）、Phase 1.7 运行纪律（追平 raw 非研究面）、引用扫描不完整即修剪 fail-closed（Phase 5.3）。✔

## v3 新引入内容自查

- 条目 8 解析器的 frozen-无字段回退（钳到 `calendar_end_date`）与既有 frozen 等值校验语义一致（老政策下 live 末端 == calendar_end_date，回退等价于现状，不放松任何约束）。
- Phase 2.2 引用改为"条目 1-6 + 条目 8"，交叉引用一致；风险表新增"脑裂过渡态"与"Phase 1-2 间隙"两行，对策均指向已定义机制。
- 无新的量化断言；无对冲措辞问题。

**Round-3 结论：clean for GPT re-review（范围：M6/M7 + 3 附加项的解决 + 新引入内容扫描）。**

---

# Round-4 自审（Phase 2 发布前墙**实现** diff）— 2026-07-02

**对象**：`phase2_wall.diff`（23 文件 / +798 −33；提交 81680fb / 3f1cec8 / cb2c8d0）。设计已 SHIP（Round 1-3）；本轮审的是实现忠实性 + 实现引入的新风险。

## 一、§3 不变量核对

- **3.2 PIT**：全部改动只做**收窄**（钳制/拒绝），无任何路径放宽数据可见性。promotion 守卫放宽是唯一"允许更多"的语义变更——但仅接受 `oos_end == 政策记录 spent 边界` 且 Phase-4 belt（`IsEndLeakageError`）保留；`calendar_end < oos_end` 的短日历情形仍走拒绝分支（fail-closed 全覆盖，已逐分支核）。✔
- **3.4 治理**：publish 政策参数必填化没有旁路（`run()` 在 publish 且无 id 时 `BuildGateError`）；manifest-记录 id 的读取点（update_daily_data / validation_steps / 缓存绑定 / 钳制）全部属于 D1 的 live-provider/artifact-记录例外。✔
- **3.5 seal**：正式门钳制与既有 oos_test `validate_read` seal 检查形成双层；沙盒门无 seal 逃逸（设计加严）。✔

## 二、实现自查发现（已知权衡，留给 GPT 裁决）

1. **`lru_cache` 进程级缓存**（`_spent_oos_end_timestamp` / `live_provider_ids`）：进程存活期间 provider 轮换会读到旧边界/旧 id。权衡理由：研究/正式运行都是每-run 进程；轮换发生在发布仪式中（无并存长进程假设）。风险=长驻进程（dashboard？）跨轮换。
2. **缓存世代绑定只在调用方传 id 时执行**：今天唯一调用方是正式门（总传）；未来新调用方漏传则不受绑定。lint 未覆盖该情形。
3. **QA 审计锚 16:00 启发式**：硬编码小时数（非交易日历收盘语义），文档已注明用途（防盘中假红）。
4. **`_formal_calendar_policy_id` 的 prescription 优先**：`PrescribedRecipe` 尚无该字段（getattr→None→manifest 路径）——前向兼容设计，字段落地属后续。
5. **诚实更正已入库**：Phase 1 后 QA "全绿"误报（audit 未来锚点 + echo 链吞退出码）——修正 + 复验（exit=0 + Overall PASS 双检）。

## 三、测试证据

新增 14 测试（9 政策解析器 + 5 正式门行为）；orchestrator 253 全绿、data_infra 全绿（除既有 test_share_capital_daily 收集问题，独立任务处理中）、pr8 系列全绿（pr8c 源文断言更新为新契约）、`run_daily_qa` Overall PASS exit=0（含新 POLICY001 lint）。

**Round-4 结论：clean for GPT（实现 diff 审查）。**

---

# Round-5 自审（R4 findings 应用后）— 2026-07-02

**背景**：Round-4 verdict = REVISE（0 Blocker、M1-M6 + m1-m2，全接受零拒绝；处置表 = 计划 §7b）。

## 应用忠实性

- **M1**：promotion 守卫三分重写（短拒/等过/长=spent-replay 或 sealed 分支）；sealed 分支校验 = 活跃 ctx + `holdout_seal_claimed` + 窗口覆盖 [oos_start,oos_end] + ctx 的 provider/policy 绑定 == 注入的 live provenance。与 GPT 替换文本的差异（诚实披露）：GPT 要求 seal 记录本身绑定 candidate/purpose/code_hash 等——ctx 层绑定已覆盖 provider/policy/窗口三要素；seal 记录级的完整字段绑定（含 code/config/data hash）作为后续项记录，未在本轮实现。
- **M2**：`PrescribedRecipe.calendar_policy_id` 字段落地 + `_formal_calendar_policy_id` 只认 prescription pin、否则 ValueError fail-closed（manifest 回退删除）。**关键设计决策**：新字段**不进** `normalized_dict()`/design_hash（政策 pin = 执行环境绑定，非设计身份；同一设计换政策不换 hash）——既有 design_hash 零漂移（seal 键安全），请 GPT 复核该语义选择。
- **M3**：`provider_context.py` 中立模块（m2 一并解决），缓存键 = manifest 文件 `(mtime_ns, size)`（GPT 方案 A）+ `refresh_live_provider_context()` belt；进程内轮换测试（改写 manifest 后无显式刷新即重解析）+ manifest 缺失 fail-closed 测试。
- **M4**：两处 cache API 的世代 id 必填非空白（空白 raise）；旧空值行拒绝 = 有意 legacy 失效路径（无研究门可达的迁移模式），月度仪式归档 manifest。
- **M5**：发布闸三重校验（非 None/非空白/必须解析到已提交政策 YAML）。
- **M6**：21 个新测试（电池 + 缓存 fail-closed 扩展）。
- **m1/m2**：注释 TEMPORARY CAP + 中立模块。
- **自发现（超出 GPT 清单）**：seal 的 crash-resume（allow_same_run）在 provider 轮换后会静默对不同数据恢复——已补：SEAL_COLUMNS 增 provider/policy 绑定、恢复路径世代不符即拒 + 3 测试。

## 波及修复

- 3 个测试 fixture 迁移（lock_concurrency ×2、permissive 全量、hypothesis_workflow 两处 recipe 加 pin）；collision fixture 的 live_provider_ids 导入 repoint。
- 发现 2 个**既有**问题（非本 diff）：test_share_capital_daily 导入路径、test_direct_d_features 与特权哨兵调用的 noqa 分歧——各挂独立任务芯片，不混入本墙。

**Round-5 结论：clean for GPT re-review（范围：M1-M6/m1-m2 应用 + design_hash 排除决策 + seal-resume 自发现补丁）。**
