# Phase 5 设计方案：解冻后稳态更新机制

*起草 2026-07-04 · UNFREEZE_PLAN.md Phase 5 的详细设计 · 状态：DRAFT，待 GPT §10 跨审*
*前置：Phase 0-4 完成（live provider = `thaw_step1_20260703c` / `frozen_20260701_thaw_step1` / 日历末端 2026-07-01；D3 机械封存在真 provider 上验证生效）*

---

## 1. 目标与非目标

**目标**：把"日历推进"从一次性人工工程变成可持续的稳态机制——原始层每日自动追平，Qlib provider 按月受控重建+发布，全程遵守 D1（无全局政策）/ D2（日更 raw + 月度 bump）/ D3（新窗口出生即封存）三决策与 §13 风险纪律。

**非目标（显式排除，避免 scope 蔓延）**：
- ❌ 滚动政策（`frozen:false` + `max_calendar_lag_days` 强制）——受 m1 守护规则约束，在 lag 强制检查落地前不启用（UNFREEZE_PLAN Phase 5.4）。
- ❌ 真·追加式增量物化器（按天 append bin 而非全量重物化）——仅当月度全量重建时长不可接受时才立项。
- ❌ Phase 6 新鲜窗口研究开封（其门槛清单在 §7c：seal 记录级绑定 + M6-test-2 + m3 快照）。
- ❌ 自动发布：月度 bump 的 publish 腿是 §13 风险动作 + 25 approval 换绑仪式，**必须人工签批**，绝不调度自动执行。

---

## 2. 核心约束（来自代码事实，全部已核实）

| # | 事实 | 位置 | 对设计的含义 |
|---|------|------|-------------|
| C1 | 日常增量 `mode=update`+`touched_symbols` 走 scoped_update：**跳过 kline dump，日历永不追加** | pit_backend.py:3904-3926 | 日历推进**只能**走月度全量重建；日更不碰 provider |
| C2 | 增量路径 publish=True 每次生成新 `build_id` + 重发 manifest | update_daily_data.py:496-506 | 若日更带 provider 发布 = **每日 build_id 轮换 = 每日 25 approval 换绑**，不可持续 |
| C3 | `--no-qlib` = 纯 raw 抓取，不碰 provider/manifest/ledger | update_daily_data.py:543 | 日更用 `--no-qlib` = 零治理开销的便宜路径 |
| C4 | 日更 phase3 覆盖：moneyflow/hk_hold/margin/stk_limit/top_list/top_inst/block_trade + income/bs/cf/indicators + cashflow(_q)/holder_number + forecast/dividends | update_daily_data.py:276-430 | **未覆盖**：suspend_d、cyq_perf、report_rc、stk_holdertrade、namechange、stock_st_daily → 月度 bump 前须补 |
| C5 | publish 政策参数已必填无默认；`_live_calendar_policy_id` 读 manifest 记录值 | pit_backend.py run() + update_daily_data.py | 月度 bump 显式传新政策 id；日更（若发布）读 live 记录值 |
| C6 | 自动化载体 = Windows 计划任务（`QuantDashboardRefresh` 每时精度先例）+ SessionEnd hook | .claude/settings.json + CLAUDE.md §6.2 | 日更 = 新增收盘后计划任务；月度 bump = 人工触发脚本 |
| C7 | `run_daily_qa` 当前**不调度**（冻结期"故意不调度"理由已失效） | scripts/run_daily_qa.py + §6.2a | 解冻后接入日更并加失败告警 |
| C8 | D3 `spent_oos_end` 从 live 政策解析；月度 bump 换新政策 | provider_context.py + calendar_policy.py | **spent_oos_end 跨月度 bump 保持 2026-02-27**，只 calendar_end 前移（新窗口生长，见 §5） |

---

## 3. 两级节奏总览

```
每日（收盘后，计划任务，无人值守）
  └─ update_daily_data.py --no-qlib   # raw 层 + 完整性检查，不碰 provider
  └─ run_daily_qa.py                   # QA，失败告警

每月（月初或按需，人工触发 + 人工签批）
  └─ monthly_calendar_bump.py          # 打包 Phase 1-4 的可复现版本
       ├─ [自动] 端点就绪 → target_end → 补齐日更未覆盖的数据集
       ├─ [自动] 全量重建 → 冻结段审计 + 侧车审计 → dry-run 报告
       ├─ [人工签批门] ← STOP，人读 dry-run 报告
       └─ [授权后] 安全发布 → 25 approval 换绑 → QA → 父 build 元数据 + 文档
```

**设计要点**：raw 层与 provider **解耦**——raw 每天追（便宜、无治理、摊平 Tushare 负载），provider 每月集中前移一次（本地重建，不碰 API）。月内 provider 停在上次 bump 的 calendar_end，研究面读的就是那个末端——完全符合 D3（新窗口本就 born-sealed，月内不前移无损失）。

---

## 4. 每日作业设计

### 4.1 脚本
沿用 `update_daily_data.py --no-qlib`，**不新建脚本**（C3 已提供正确语义）。补两个既有缺口：

1. **target_end 纪律（m2）**：日更默认 `--date` = 今天，但今天收盘后数据才完整。方案：新增 `--last-complete-session` 标志，让日更抓"最后一个完整交易日"而非日历今天——完整定义 = trade_cal `is_open==1` ∧ 收盘后 ∧（可选）daily 端点就绪探针返回非空。避免 m1 flag 的"hour>=16 硬编码"成为长期定义。
2. **日更未覆盖数据集（C4）**：suspend_d 加入日更 phase3（廉价，逐日 trade_date）；namechange/stock_st_daily/report_rc/stk_holdertrade/cyq_perf **不进日更**（cyq_perf 逐股昂贵、report_rc create_time 语义、namechange 低频）→ 归月度 bump 的"补齐"步（§5.1）。

### 4.2 QA + 告警（C7）
日更后串跑 `run_daily_qa.py`；退出非零时告警。告警载体：先用最轻量的——写 `logs/qa_alert_<date>.flag` + 计划任务的"上次运行结果"（Windows 计划任务原生记录退出码）。**不引入邮件/webhook**（超出当前需求；如需要另立）。

### 4.3 载体
Windows 计划任务 `QuantDailyRawUpdate`，触发：每交易日收盘后（建议 18:30 CST，留足 Tushare vendor 更新）。命令：`venv\Scripts\python.exe src\data_infra\pipeline\update_daily_data.py --no-qlib --last-complete-session && venv\Scripts\python.exe scripts\run_daily_qa.py`。非交易日脚本内部 `is_open` 检查自然跳过（update_daily_data.py:125）。

---

## 5. 每月 bump driver 设计（`scripts/monthly_calendar_bump.py`）

打包我刚才**手工**做的 Phase 1-4，成为可复现、可 `--dry-run`、带人工门的驱动。

### 5.1 阶段（`--dry-run` 跑到审计为止；无 flag 跑到 dry-run 报告后 STOP）
1. **前置检查**：磁盘 ≥ 1.5× provider 树；引用型 build 保留规则修剪历史 staged 树（无引用才删）。
2. **端点就绪 → target_end**：确定最后一个完整交易日（同 4.1 定义），作为新政策 `calendar_end`。
3. **补齐日更未覆盖数据集**到 target_end：namechange 刷新、suspend_d/stock_st_daily 边界、report_rc（create_time 增量 + 重叠月）、stk_holdertrade、cyq_perf（逐股增量，最长）、index_weights（各月）——复用已写的 `catchup_fundamentals_range.py` 分阶段（现已支持断点续跑）。
4. **新政策 YAML**：`frozen_<target_end>_thaw_step<N>.yaml`（append-only，老文件永不动）。**关键不变量**：`spent_oos_end` 保持 **2026-02-27**（不随 calendar_end 前移）；`fresh_holdout_start` 保持 2026-02-28。→ 新窗口 `[2026-02-28, target_end]` 生长，全程 born-sealed，只有 Phase-6 book-seal 花费才推进 spent_oos_end。
5. **全量重建**：`build_qlib_backend.py --mode all --stage full --calendar-end <target_end> --build-id <id>`（staged，不发布）。
6. **冻结段审计**：复用 `audit_thaw_frozen_prefix.py`——bin 前缀字节等值 + 日历仅追加 + 侧车逐日成员矩阵（集合从树枚举）。**批准例外机制**：每次 bump 的合法 provenance 变更（新报表期入 serving、停牌愈合）需在 driver 里显式登记为例外并计数，其余一律阻断。
7. **dry-run 报告**：target_end、政策 id、build id、审计摘要（含例外精确数字）、待换绑 approval 清单、磁盘/交换/备份计划。

### 5.2 人工签批门（§13）
driver 在 dry-run 报告后 **STOP**，打印"发布需人工 `--publish-approved` 复跑或独立 publish 脚本"。**publish 腿绝不在同一次自动流里执行**。

### 5.3 发布腿（人工授权后）
安全交换（三步原子，同卷 st_dev 闸）→ 25 approval 双 id 换绑（driver 照先例）→ `evaluate_approval_evidence_bindings()` 0 drift → 发布后 QA 全绿 → 父 build 元数据（`parent_provider_build_id` 等，M3 引用型保留链）+ 文档 stub。

### 5.4 保留策略（M3）
只修剪无引用 build；引用型（出现在 approval/五注册表 evidence/seal/frozen selection/deployment-gate 的）保留全树或回放核验包；引用扫描无法枚举任一源时修剪 fail-closed。

---

## 6. 政策 YAML 生命周期（关键设计判断）

| 字段 | 跨月度 bump 行为 | 理由 |
|------|-----------------|------|
| `calendar_end_date` / `data_end_date` | **每次前移**到新 target_end | 日历推进 = bump 的目的 |
| `spent_oos_end` | **保持 2026-02-27 不动** | 只有 Phase-6 book-seal 实际花费新鲜窗口才推进；bump 是数据操作，不花费 OOS |
| `fresh_holdout_start` | **保持 2026-02-28 不动** | 同上；新窗口 `[2026-02-28, calendar_end]` 随日历生长 |
| `frozen` | 保持 `true` | 滚动政策非本期范围（m1 守护） |
| `policy_id` | 每次新 id（append-only） | D1：老文件永不动，历史 artifact 回放用记录政策 |

**含义**：随月度 bump，born-sealed 的新鲜窗口**单调生长**（2026-02-28→越来越晚），全部受 D3 机械闸保护，直到某本书通过 Phase-6 path 花费其中一段。这是正确的——新鲜 OOS 资产越攒越多，而非被日历前移稀释。

---

## 7. 开放设计判断（送 GPT）

1. **日更是否需要任何 provider 触碰？** 本设计选"日更纯 raw、月度才动 provider"（C1/C2 决定）。替代方案：日更做 scoped provider 更新（PIT 字段前移但日历不动）——但会日轮换 build_id（C2）触发日换绑，故否决。是否有第三条路（如日更 scoped 更新但**不重发 manifest/不轮换 build_id**）？
2. **spent_oos_end 冻结在 2026-02-27 的正确性**：随日历前移到数月后，探索/沙盒默认上限仍是 2026-02-27——研究者能用的"干净"历史窗口不增长，直到 Phase 6。这是有意的（保护新鲜 OOS）。但会不会造成"数据在那儿却半年不能碰"的实践张力？是否需要一个中间态（如 spent_oos_end 随 bump 前移到 `target_end - 1yr` 之类的滚动 IS 窗口，把最老的新鲜数据释放给探索）？——这是 D3 语义的潜在弱化，需 GPT 裁定。
3. **月度 bump 的全量重建时长**（首次实测 upstream ~1.5h + 物化 ~7-15h）长期是否可接受？还是应该现在就为"真·追加式增量物化器"立项（非目标 ❌ 之一，但若月度 8-15h 太痛则重新评估）？
4. **target_end / last-complete-session 的权威定义**：trade_cal `is_open` + 收盘后是否足够？还是必须加 vendor 端点就绪探针（daily 返回非空 + 预期股票数）？后者更稳但更慢。
5. **日更未覆盖数据集在月度补齐是否有 PIT 风险**：cyq_perf/report_rc 等月度一次性补齐 vs 日更逐日——月度补齐会不会漏掉月内的 create_time 晚到行？（report_rc 的 202602 重叠月教训）。

---

## 8. 风险与对策

| 风险 | 对策 |
|------|------|
| 日更漏跑（机器关机/计划任务失败） | 日更幂等（按日期覆盖写）；月度 bump 的补齐步兜底所有缺口；QA 告警暴露连续失败 |
| 月内新 IPO/退市不在 provider | 可接受——月内 provider 停在上次 bump 末端；research 读该末端；下次 bump 纳入 |
| 月度 bump 引入 provenance 漂移 | 冻结段审计 + 批准例外显式登记；未登记差异阻断发布 |
| 日更 raw 被误当研究面 | Phase 1.7 纪律延续：月内新 raw 在下次 bump 发布前非研究面（D3 沙盒门钳制已强制） |
| 全量重建时长增长 | 监控每次 bump 时长；超阈值触发"真·追加式物化器"立项评估 |
| spent_oos_end 冻结引发实践张力 | §7 开放判断 2，送 GPT |

---

## 9. 交付物清单（实现阶段，非本设计）

- `update_daily_data.py` 加 `--last-complete-session` + suspend_d 纳入 phase3
- `scripts/monthly_calendar_bump.py`（新，`--dry-run` / 人工门 / publish 腿分离）
- Windows 计划任务 `QuantDailyRawUpdate`（注册脚本 + 文档，不进 repo 的 task 本身）
- `run_daily_qa` 失败告警轻量化
- CLAUDE.md §6.2/§6.2a 更新（解冻后 QA 调度理由 + 两级节奏）；project_state 记录
- 测试：last-complete-session 边界、月度 bump dry-run 到审计、政策 YAML spent_oos_end 不变量
