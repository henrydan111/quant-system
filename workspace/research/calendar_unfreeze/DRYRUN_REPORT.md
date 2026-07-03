# 解冻发布 Dry-Run 报告（Phase 3.3，等待人工签批）

*生成：2026-07-03 · UNFREEZE_PLAN.md Phase 3.3（Round-1 m4 要求）· **签批后才执行 Phase 3.4 安全发布***

## 1. 发布对象

| 项 | 值 |
|---|---|
| staged build | `data/qlib_builds/thaw_step1_20260703c/provider`（build C，`--calendar-end 20260701` 钉死） |
| 新政策 | `frozen_20260701_thaw_step1`（calendar_end 2026-07-01；spent_oos_end 2026-02-27 / fresh_holdout_start 2026-02-28） |
| 新 provider_build_id | `thaw_step1_20260703c` |
| 父 build（当前 live） | `depth9_20260630_sharecap_reanchor_20260701` / `frozen_20260227_system_build` |
| 日历 | 4,410 → **4,493 天**（+82 追赶 + 0701；前缀逐行相等，仅追加） |

## 2. 冻结段审计终版（AUDIT3，`frozen_prefix_audit.json`）

- **ok: True，0 违规**；38,051,814 个 bin：缺失 0、缩水 0
- 760,267 抽样（1/50 符号全字段）前缀 SHA：**未解释失配 0**
- **批准例外 81 处 = report_rc 族补全**（冻结时抓取漏掉的 2 月中下旬报告，由端点合同预设的 202602 重叠月重抓补齐，按真实 create_time 可见日落位，差异日期实证 2026-02-12/13）——indicators 族例外 **0**（恢复 store 后逐字节一致）
- **侧车例外 = all.txt/all_stocks.txt 各 57 格纯增量**（12 只代码：10 只冻结边界停牌股复牌区间愈合 + 2 只缺口期退市补记 delist_date；§3.3 语义下新状态更正确；csi300/500/1000、st_stocks 零差异）

## 3. 发布动作（签批后执行）

1. **安全交换**（depth9 三步原子次序，同卷 `st_dev` 闸内建）：staged→adjacent → live→`data/qlib_data.bak_thaw_step1_20260703c` → adjacent→live；manifest 以 `--calendar-policy frozen_20260701_thaw_step1` 语义重发（publish 政策参数必填已强制）
2. **approvals 换绑**：**25 个 YAML** 双 id 同换（`depth9_20260630_sharecap_reanchor_20260701`→`thaw_step1_20260703c`；`frozen_20260227_system_build`→`frozen_20260701_thaw_step1`），照 sharecap/depth9 先例出换绑审计 md，证据 = 本报告 + AUDIT3 工件；`evaluate_approval_evidence_bindings()` → 0 drift
3. **cache manifest 归档**（M4 世代绑定的预期动作：旧世代缓存行换代后按设计失效）
4. **发布后 QA**：`run_daily_qa` 全绿（provider_manifest_check 将按新政策等值校验 4,493 天）+ 墙电池抽跑（D3 钳制在新 live 下：默认读钳 2026-02-27、新鲜窗口无 seal 拒绝）
5. **文档**：project_state 发布记录 + CLAUDE/AGENTS §3.4 政策引用更新 + data_tracker provider 段

## 4. 磁盘与保留

- 可用 392GB；发布 = 纯 rename（无拷贝开销）
- 发布后修剪：builds A（20260702）/ B（20260702b）两棵**无引用** staged 树（回收 ~560GB）；`.bak_thaw_step1_20260703c`（原 live）保留 = 一次 rename 可回滚
- 事故证据保留：`_archive/indicators_2period_only_20260703_evidence` + `indicators_pre_unfreeze_gap_refresh`

## 5. 残余风险声明

- report_rc 81 处与侧车 57 格为**已诊断、已批准**的 provenance 变更（本报告即批准载体，签批=接受）
- 发布瞬间的 D3 保护已由 R7-M9 测试端到端预演（thaw 政策 + 4,493 日历下边界仍钳 2026-02-27）；发布后任何越界读取需 seal
- 0702/0703 两个交易日不在本 provider（target_end 纪律）；解冻后由 Phase 5 日更机制接管
