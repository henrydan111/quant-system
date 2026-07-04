# Phase 5 设计方案：解冻后稳态更新机制 — v3.1 定稿

*起草 2026-07-04 · GPT §10 跨审四轮：R1 REVISE（1B+3M+1m）→ R2 REVISE（B2 可见性边界守卫）→ R3 REVISE（M4 §9 一致性）→ **R4 SHIP**（零拒绝项）· 状态：**定稿，可进入实现***

**⚠ GPT SHIP 残余风险（实现纪律）**：实现必须精确保持修订台账的**无后退 effective_date** 语义 + canonical digest 覆盖所有影响 PIT 锚/materialized 特征的字段——report_rc availability-boundary 守卫的 load-bearing 保证；实现后须跑完整 report_rc 测试族 + PIT canary。
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

1. **target_end 纪律（m2）**：日更默认 `--date` = 今天，但今天收盘后数据才完整。方案：新增 `--last-complete-session` 标志，抓"最后一个完整交易日"而非日历今天。**日更的就绪定义可宽松**（trade_cal `is_open==1` ∧ 收盘后，日更幂等+不发布，容错重试即可）；**但正式 provider bump 的 target_end 必须走强制端点就绪合同**（GPT Major M1，见 §5.1 步 2）——clock+calendar 单独可调度 raw 抓取，**不可授权正式 target_end**（Tushare 各端点更新窗不同：daily 15-16 点、cyq_perf 18-19 点、report_rc 19-22 点）。
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
2. **端点就绪 → target_end（强制合同，GPT M1；探针是 publish 阻断非 warning）**：`target_end` = 通过端点就绪合同的最晚 open trading day。合同至少含：trade_cal `is_open==1`；每个必需端点族的 post-vendor-update clock；`daily` 对 D 非空；市场级 daily 端点的期望数/稳定数校验；cyq_perf 的逐股/期望覆盖校验；report_rc 过其文档更新窗**或**显式排除同日完整性要求。任一探针失败 → **bump 阻断**，target_end 回退到全绿的最近 open day。作为新政策 `calendar_end`。
3. **补齐日更未覆盖数据集**到 target_end：namechange 刷新、suspend_d/stock_st_daily 边界、stk_holdertrade、cyq_perf（逐股增量，最长）、index_weights（各月）——复用 `catchup_fundamentals_range.py` 分阶段（断点续跑）。
   - **cyq_perf 月度补齐 PIT-等价**（GPT Q3 裁定）：逐股按 trade_date 事实数据集，只要 bump 探端点就绪 + 抓全 symbol/date 范围到 target_end + 覆盖数校验 + 发布前端点完整即可，可留月度。
   - **⚠ report_rc 必须 fail-closed replay，且守卫键为"可见性/生效"而非 report_date**（GPT Blocker B1+B2，已核实 [pit_backend.py:2461-2486](src/data_infra/pit_backend.py#L2461) + `REPORT_RC_ACTIVE_TTL_OPEN_DAYS=120` [pit_backend.py:192](src/data_infra/pit_backend.py#L192)）：`create_time` 是**输出**可见性字段、非 server-side 游标；现有 `gap_days <= 45` 规则会把新鲜窗口内 create_time 晚到 >45 天的真实晚到行误判 bulk-backfill、锚 `report_date+2`（早于真实可见=前视，代码自己只 WARN）。**sealed 边界是可见性边界，不是 report_date 边界**——report_date 2026-02-26 但 create_time/首见 2026-03-05 的行是 report_date-pre-boundary 却 availability-fresh；且 forecast 按 TTL=120 交易日 carry，report_date 早于边界 ~120 天的行仍可 carry 进新鲜窗口。修正规则：
     - report_rc 按 **report_date replay** 抓取（非假想 create_time 游标）；存 `vendor_create_time` / `raw_fetch_ts` / ingest batch id / provider `as_of_cutoff`。
     - **新鲜 PIT 守卫适用于满足以下任一的行或行修订**（B2 加宽，非仅 report_date）：① `report_date >= fresh_holdout_start`；② `vendor_create_time >= fresh_holdout_start`；③ `raw_fetch_ts >= fresh_holdout_start`；④ 该行计算出的 `effective_date` 或 active/carry-forward 区间与 `[fresh_holdout_start, target_end]` 相交。
     - 对所有此类行，**禁用历史 bulk-backfill 回退**，生效日下限：`effective_date = next_open(max(report_date, vendor_create_time, first_seen_or_revision_seen_ts_floor))`——其中 `first_seen_or_revision_seen_ts_floor` 在（行/修订不在上次合格 raw 快照 / create_time 缺失 / create_time 后退 / payload digest 变化而无可信更晚 vendor 戳）时必填。
     - **修订台账**：bump 维护 report_rc raw-row 修订台账，键 = 稳定自然键 + payload digest + vendor_create_time + first_seen_raw_fetch_ts + ingest_batch_id。replay 可加新修订，**绝不移动既有修订的 effective_date 变早**；任何 effective_date 后退移动 = build 阻断 PIT 错误。
     - **pre-boundary halo**：replay 范围须含足够 halo 以捕获 report_date 早于 fresh_holdout_start 但可见性/active 区间相交新鲜窗口的行——至少 `fresh_holdout_start − (REPORT_RC_ACTIVE_TTL_OPEN_DAYS=120 + vendor-lag/backfill guard)` 到 target_end。含糊的"文档化重叠窗"不足够。
     - **历史 2010-2021 bulk-backfill 行为保留**：历史回退仅对 report_date、create_time/首见、effective_date、active 区间**全部**在新鲜/sealed 窗口之外的行允许——fresh_holdout_start 不是干净分隔符，"能否影响新鲜/sealed 窗口"才是。
     - 若上述规则不实现，则 report_rc 移到**每日 22:00 CST 后**的**纯 raw** 作业（`--no-qlib` 语义，绝不走 `mode=update,publish=True` 增量发布路径——否则日轮换 build_id）+ 同一 fail-closed 锚规则 + 修订台账。
4. **新政策 YAML**：`frozen_<target_end>_thaw_step<N>.yaml`（append-only，老文件永不动）。**关键不变量**：`spent_oos_end` 保持 **2026-02-27**（不随 calendar_end 前移）；`fresh_holdout_start` 保持 2026-02-28。→ 新窗口 `[2026-02-28, target_end]` 生长，全程 born-sealed，只有 Phase-6 book-seal 花费才推进 spent_oos_end。
5. **全量重建**：`build_qlib_backend.py --mode all --stage full --calendar-end <target_end> --build-id <id>`（staged，不发布）。
6. **两道审计**：
   - **(a) 冻结段审计**（复用 `audit_thaw_frozen_prefix.py`）：bin 前缀字节等值 + 日历仅追加 + 侧车逐日成员矩阵（集合从树枚举）——保护 pre-2026-02-27 回放。
   - **(b) 新鲜窗口 universe 审计（GPT Major M2，新增）**：冻结段审计**不足以**证明新生 sealed 窗口 `[2026-02-28, target_end]` 无生存者偏差——而这正是未来 Phase-6 holdout 资产，若缺退市/停牌名则 holdout 有偏。对 `[fresh_holdout_start, target_end]`：raw `daily` 有任何价格行的每只 symbol 必须在 provider feature 树 + `all_stocks` 的 **list/delist 边界**（§3.1 delist/IPO-lag 合同）内所有合格交易日出现，否则 bump 失败；另审 stock_basic list/delist/pause + namechange + stock_st_daily + suspend_d + index-weight 侧车对再生 instruments。**实现精度（GPT）：stock_basic 与 raw 价格证据冲突时不得信 stock_basic——raw 有价格行但 list/delist 侧车排除该 symbol/日 → bump 作为 universe-contract 不一致失败，绝非批准例外。新鲜窗口审计是完整性+无生存者偏差闸，无任何 blanket 例外。**
   - **批准例外机制（GPT Major M3，强化——防漂移洗白）**：例外是 append-only、per-bump、typed 记录，含：exception id / root cause / dataset·field / symbol set / date range / gross diff / net diff / reviewer / **expiry condition** / evidence path。dry-run 报告须同时显示 **gross 漂移 + 例外调整后漂移 + 按类型的累计趋势**。同一例外类型连续两次 bump 出现 → 要么永久 migration note + 测试，要么阻断，**不得仅凭计数静默再批**。禁通配 date range、禁 "all symbols"、无新 diff hash 不得复用批准。（只对冻结段审计；新鲜窗口审计无例外。）
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

**含义**：随月度 bump，born-sealed 的新鲜窗口**单调生长**（2026-02-28→越来越晚），全部受 D3 机械闸保护，直到某本书通过 Phase-6 path 花费其中一段。这是正确的——新鲜 OOS 资产越攒越多，而非被日历前移稀释。**GPT Q2 裁定：正确且安全，data bump 绝不推进 spent_oos_end。**

**"数据在那儿却几个月不能碰"的张力**（GPT Q2 裁定 = 运维摩擦，非研究有效性缺陷）：若将来要把最老的新鲜数据释放给探索，**必须作为 spend 事件处理，绝非按年龄自动老化释放**（自动老化会把生长的新鲜窗口变成反复测试集，弱化 D3）。正确的中间路径 = 单独的 "research-window release seal"：盖新政策、记录释放的日期切片、为该政策推进 spent_oos_end、绑定消费该切片的 book/artifact 血缘、并保留更晚的未触碰 holdout。**此机制归 Phase 6，非 Phase 5。**

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
| 全量重建时长增长 | **go/no-go 阈值（GPT m1）**：全量重建保持默认，条件 = bump 在批准维护窗内完成 ∧ 冻结/新鲜审计可从头重跑无需手工补丁；每次 bump 记录 upstream/物化/审计时长 + 峰值磁盘 + 文件数 + 重试数；**仅当连续两次 bump 突破维护窗/磁盘余量，或 provider 无法在下次发布前重建+审计完**才立项真·追加物化器。不提前建。 |
| report_rc 新鲜窗口 create_time 晚到行被回锚（前视） | B1 fail-closed replay + 锚规则；build 阻断非 warning |
| 新鲜窗口生存者偏差污染未来 holdout | M2 新鲜窗口 universe 审计（无例外） |
| 批准例外累月洗白冻结段漂移 | M3 typed/bounded/趋势化例外 + 连续两 bump 同类型即阻断 |
| spent_oos_end 冻结引发实践张力 | §7 开放判断 2，送 GPT |

---

## 9. 交付物清单（实现阶段，非本设计）

- `update_daily_data.py` 加 `--last-complete-session` + suspend_d 纳入 phase3
- **report_rc fail-closed replay + availability-boundary 锚（B1+B2）**：实现 §5.1 step 3 的**完整**规则，**不是** `report_date >= fresh_holdout_start` 的旧边界。守卫适用于任一条件成立的行或修订：`report_date >= fresh_holdout_start`、`vendor_create_time >= fresh_holdout_start`、`raw_fetch_ts >= fresh_holdout_start`、或 computed `effective_date` / active-carry interval intersects `[fresh_holdout_start, target_end]`。对这些行禁用历史 bulk-backfill 回退；`effective_date = next_open(max(report_date, vendor_create_time, first_seen_or_revision_seen_ts_floor))`；维护 revision ledger（自然键+payload digest[须 canonicalize 覆盖所有影响 PIT 锚/materialized 特征的字段]+create_time+first_seen+batch_id）；禁 existing revision 的 effective_date 后退；replay halo 至少覆盖 `REPORT_RC_ACTIVE_TTL_OPEN_DAYS=120 + vendor-lag/backfill guard`；历史 bulk-backfill 仅对完全不影响 fresh/sealed window 的行保留。（改 pit_backend.py report_rc 锚逻辑 + report_date replay 抓取器）。**测试必须覆盖 5 类**：pre-boundary `report_date` 但 fresh `create_time`/first-seen、TTL carry into fresh、payload revision、backward `create_time`、missing `create_time` quarantine/raw-fetch-floor。
- `scripts/monthly_calendar_bump.py`（新，`--dry-run` / 人工门 / publish 腿分离 / **强制端点就绪 target_end** M1 / **新鲜窗口 universe 审计** M2 / **typed 例外注册表** M3 / **时长-磁盘 instrumentation** m1）
- Windows 计划任务 `QuantDailyRawUpdate`（注册脚本 + 文档，不进 repo 的 task 本身）
- `run_daily_qa` 失败告警轻量化
- CLAUDE.md §6.2/§6.2a 更新（解冻后 QA 调度理由 + 两级节奏 + report_rc 新鲜窗口锚不变量）；project_state 记录
- 测试：last-complete-session 边界、月度 bump dry-run 到审计、政策 YAML spent_oos_end 不变量、**report_rc 新鲜窗口晚到行 fail-closed（B1 回归）**、**新鲜窗口 universe 审计抓退市洞（M2）**、**例外注册表连续两 bump 同类型阻断（M3）**

## 10. GPT Round-1 findings 处置表（2026-07-04，verdict = REVISE；GPT fetch 真实 repo+Tushare 文档）

| # | Finding | 处置 | 落点 |
|---|---------|------|------|
| **B1** | report_rc 月度补齐非 fail-closed：>45d create_time 晚到行被回锚 report_date+2（早于真实可见 = 前视）——**已核实 pit_backend.py:2461-2486 代码自己只 WARN** | **接受**：report_date replay + 新鲜窗口禁 bulk-backfill 回退 + 缺 create_time 隔离 + 回锚早于 create_time = build 阻断；不实现则 report_rc 移日更 | §5.1 步 3 + §9 |
| **M1** | target_end 就绪对正式发布不足（各端点更新窗不同） | **接受**：正式 bump 强制端点就绪合同；clock+calendar 仅授权 raw 抓取不授权正式 target_end | §4.1 + §5.1 步 2 |
| **M2** | 冻结段审计不证新鲜 sealed 窗口无生存者偏差（未来 holdout 有偏风险） | **接受**：新增新鲜窗口 universe 审计（完整性+无生存者偏差，无例外） | §5.1 步 6(b) |
| **M3** | 批准例外可累月洗白漂移 | **接受**：typed/bounded/趋势化例外 + gross vs 调整后漂移 + 连续两 bump 同类型阻断 + 禁通配 | §5.1 步 6 例外机制 |
| **m1** | 全量重建时长阈值 | **接受**（GPT 裁定：不提前建追加物化器）：instrumentation + go/no-go 阈值 | §8 风险表 |

**GPT 裁定确认**：Q1 日更纯 raw 正确（无安全的"日更 scoped 不轮换 build_id"路径）；**Q2 spent_oos_end 冻结正确且安全**（自动老化释放会弱化 D3，释放须作为 spend 事件=Phase 6）；Q3 cyq_perf 可留月度、report_rc 须 B1;Q4 端点就绪探针对正式 bump 强制;Q5 月度全量重建可接受、不提前建追加物化器;Q6 人工门结构正确、弱点是例外疲劳（M3）。

**拒绝项：无。** 残余风险（GPT R1）= report_rc 晚到行处理。

## 11. GPT Round-2 findings 处置表（2026-07-04，verdict = REVISE）

R2 逐条：B1 = PARTIALLY（守卫边界，非锚公式）→ 具体化为 B2；M1/M2/M3/m1 = RESOLVED（M1/M2 附实现精度要求，已折入）。

| # | Finding | 处置 | 落点 |
|---|---------|------|------|
| **B2**（新 Blocker） | report_rc 守卫键 `report_date >= fresh_holdout_start` 太窄——sealed 是**可见性边界**：report_date pre-boundary 但 create_time/首见/carry(TTL=120)-fresh 的行仍漏；+ 已见键的 create_time/payload 后退修订未拦 | **接受并已实施**（B2 已核实 REPORT_RC_ACTIVE_TTL_OPEN_DAYS=120 真实）：守卫加宽为 4 条件任一（report_date/create_time/raw_fetch_ts/effective-or-active 相交）+ 修订台账（禁 effective 后退）+ pre-boundary halo ≥ 120+guard + effective 下限含 first_seen floor + 历史 backfill 仅对全部字段在窗外的行保留 | §5.1 步 3 |
| M1 实现精度 | 就绪探针须是 publish 阻断非 warning | **接受** | §5.1 步 2 |
| M2 实现精度 | all_stocks 须用 list/delist 边界；raw 价格 vs 侧车矛盾 = 失败非例外 | **接受** | §5.1 步 6(b) |
| m2（Minor） | 公共分支仍显 R1 文本 | **裁定=GitHub raw 缓存伪报**（已核实 pushed HEAD `e897424`==origin 含 v2 文本 6 处匹配）；采纳其流程守卫：实现 ticket 引用 v3 commit hash，不从缓存文本实现 | 流程 |

**GPT R2 确认**：M1/M2/M3/m1 folding 充分；B1 核心晚到泄漏对 report_date>=boundary 行已闭合，但须 B2 加宽；report_rc 日更 fallback 纯 raw **不**引入 build_id 轮换（须绝不走 mode=update,publish=True）。**拒绝项：无。**

## 12. GPT Round-3 findings 处置表（2026-07-04，verdict = REVISE→实质 SHIP）

**B2 = RESOLVED**（4 条件守卫 + 无后退修订台账 + first_seen floor + TTL halo 关闭可见性边界泄漏；条件 4 捕获 TTL carry；历史分隔符正确）。唯一新 issue：

| # | Finding | 处置 | 落点 |
|---|---------|------|------|
| **M4**（Major，文档一致性） | §9 交付清单仍含旧 `report_date >= fresh_holdout_start` 指令，与已批准 §5.1/§11 的 B2 规则矛盾——可能让实现回到被否决的守卫边界 | **接受并 verbatim 修正**：§9 bullet 替换为完整 B1+B2 规则 + 5 类必测用例 | §9 |

**GPT R3 裁定**：B2 实质 resolved、历史分隔符正确、delta 无其他新 Blocker/Major；"substance is ready，仅 §9 冲突清单须先修"。M4 已 verbatim 应用（纯文档自洽，无逻辑变更）。**拒绝项：无。** 残余风险（GPT R3）= §9 陈旧文本——已修。
