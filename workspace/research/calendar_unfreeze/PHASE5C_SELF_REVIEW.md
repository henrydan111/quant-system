# Phase 5-C 自审（日更 + 计划任务 + QA 告警，§10 前置）— 2026-07-04

*对象：`update_daily_data.py`（C-1 `--last-complete-session` + C-2 suspend_d）、`run_daily_qa.py`（C-3 告警）、`register_daily_raw_task.py`+`daily_raw_update.bat`（C-4）、CLAUDE.md §6.2a/§6.2b。结论：clean for GPT*

## 改动摘要（实现 PHASE5_DESIGN.md 已 SHIP 的 §5-C 设计）

| # | 交付 | 实现 |
|---|---|---|
| C-1 | `--last-complete-session` | `resolve_last_complete_session(ref_dir, close_hour=16, now=None)`：CST 收盘感知——过 16:00 取今日，否则回退上一交易日；周末/非交易日取 ≤today 最后 is_open 日。日更就绪**宽松**（幂等+不发布+容错），正式 bump 的 target_end 走**严格**多端点合同（5-B），两者分离。 |
| C-2 | suspend_d 进日更 phase3 | `DailyDataUpdater.write_suspend_d`（**canonical**，原子覆写保 suspend_timing）在 `update_phase3_daily_market` 末调用；catchup_daily_range 的同名函数改**委托**它（单一真值 + src/ 边界）。 |
| C-3 | QA 失败告警 | `run_daily_qa.py` 非零→写 `logs/qa_alert_<date>.flag`（失败 checks + report 路径）；恢复的同日运行清旗。轻量，无邮件/webhook（设计明示）。 |
| C-4 | 计划任务 | `daily_raw_update.bat`（cd + `--no-qlib --last-complete-session` + QA）+ `register_daily_raw_task.py`（DAILY 18:30 CST，dry-run 默认，`--register`/`--delete`=§13）。任务本身不进 repo。 |

## §3 不变量 / D1-D3 核对

| 项 | 判断 |
|---|---|
| D1/D2 日更纯 raw | ✔ `--no-qlib`（line 543 `if not args.no_qlib` 跳 qlib 转换）→ 日更**不碰** provider/calendar/manifest/ledger，不轮换 build_id；日历只由月度 bump 前移 |
| D3 spent_oos_end 冻结 | ✔ 日更不触 provider→不影响封存；沙盒门仍钳制新窗口 |
| 3.1 trade_cal 唯一真值 | ✔ resolve 读 trade_cal is_open；非交易日 update_for_date line 125-131 早退 |
| suspend_d 覆写 PIT | ✔ 同日完整快照，覆写=替换（re-fetch 权威），保全行+加 suspend_timing；GPT 5-B re-review #7 已裁"无 PIT 洞" |
| §13 机器变更 | ✔ 注册任务=dry-run 默认，`--register` 显式；未执行注册（留用户） |
| §4 路径 | ✔ .bat 硬编码 `E:\量化系统`=one-off launcher（CLAUDE.md §4 允许）；src/ 代码用 self.data_dir |
| 模块边界 | ✔ canonical writer 在 src/（DailyDataUpdater）；workspace/catchup 委托它，不反向 import |

## 跨审原则

1. PIT/无前视：日更纯 raw 不物化 PIT 面；suspend_d 是原始层；--last-complete-session 只收 CST-完整日。
3. 生存者偏差：不适用（日更不建 provider；生存者审计在月度 bump/5-B）。
7. 无对冲：resolve/write_suspend_d/needs_refetch 有单测；register dry-run 实测。

## 留 GPT（诚实）

- **--last-complete-session 宽松度**：close_hour=16 固定；日更幂等+容错，晚到端点下次运行/月度补齐兜底。是否够？（设计已裁日更可宽松，正式 bump 严格）。
- **suspend_d 在日更 phase3 仅 market_ok 时跑**（line 152 gate）：交易日 market 空（vendor lag）时 suspend_d 不抓→下次/月度兜底。可接受？
- **schtasks DAILY 触发**（非"仅交易日"）：Windows 原生无交易日触发；靠脚本内 is_open 跳过。是否有更优（如 bump 前置就绪）？
- **QA 告警仅 flag 文件 + 任务退出码**：无邮件/webhook（设计明示超范围）。够不够？
- **daily_raw_update.bat 两命令无条件跑**（非设计的 `&&`）：QA 总跑（更安全，抓 update 失败）。是否可接受此微偏离？

## 验证

38 单测绿（5 新 5-C daily + 24 monthly + 8 catchup range-safety + 1 needs_refetch）；4 文件 py_compile OK；register `--dry-run` 实测打印正确 schtasks 命令；resolve 三例（收盘前回退/收盘后今日/周末回退）+ write_suspend_d 保 timing+覆写+空快照。

**结论：clean for GPT。5-C 实现 PHASE5_DESIGN.md 已 SHIP 的设计；不触 §3 load-bearing（日更纯 raw）；C-4 注册=§13 留用户；5 个宽松度/范围判断显式留审。**
