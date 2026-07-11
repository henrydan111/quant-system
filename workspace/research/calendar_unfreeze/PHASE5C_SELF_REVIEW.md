# Phase 5-C 自审（日更 + 计划任务 + QA 告警，§10 前置）— 2026-07-04

> ⚠ **round-1 段（下方）部分已被 round-2/3 取代**：close_hour 16→17:30、硬编码 .bat 路径→自相对 ASCII、单命令→orchestrator。最新状态见文末 **REWORK round 2** + **REVISE round 3**。


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

---

## REWORK round 2（GPT §10 实现审查 REWORK 后修复自审）— 2026-07-04

GPT 审 1e6db9a：**REWORK**（2 Blocker + 4 Major + 2 Minor，全部部署级真问题，38 测试没覆盖）。逐条修复：

| # | GPT finding | 修复 | 校验 |
|---|---|---|---|
| **B1** 首日日更截断日历→选择器卡死 | `update_reference_data` 改：抓**前向 horizon**（次年末）+ 按(exchange,cal_date)**合并**（原子 os.replace），永不用 target-bounded 覆写；`resolve_last_complete_session` 加**fail-closed**（日历末 < today→拒） | 新增 merge-not-truncate 连续会话回归（周一跑→周二选择器返周二）+ stale-calendar fail 单测 |
| **B2** .bat 在 cp936 下 `cd E:\量化系统` 乱码→退 1 | 重写 .bat：**纯 ASCII + 自相对** `cd /d "%~dp0.."`（%~dp0 由 OS 运行时编码，不受 cp936 影响）+ 组合退出码 | 结构审 |
| **M1** 更新失败不返退出码给任务计划 | `main()` 返 0/1 + `sys.exit(main())`；交易日缺 daily / suspend_d 错→非零（`is_trading_day`+`errors`）；.bat 传播 update/QA 组合退出码 | is_trading_day/errors 路径 |
| **M2** "18:30 CST" 未真编码（宿主 EST）+ 漏跑不恢复 | register 改**Task Scheduler XML**：StartBoundary 带 **+08:00**（真 CST）+ StartWhenAvailable + RestartOnFailure×3 + IgnoreNew；QA 时间戳/cutoff 改 **Asia/Shanghai**；QA 成功写 **heartbeat**；新增独立 **watchdog**（次晨 10:00 CST 检 heartbeat vs 最后完整会话，漏跑→告警） | register dry-run XML 实测（+08:00/StartWhenAvailable/restart）；watchdog compile |
| **M3** suspend_d writer 可被畸形数据毁掉有效快照 | 写前**校验**：非空须四列齐 + 每行 trade_date==target，否则 **raise**（保留旧快照）；**唯一临时文件** tempfile.mkstemp（定长 .tmp 与月度 job 冲突）+ 原子 replace | 新增 wrong-date-preserves-prior + missing-timing raise 单测 |
| **M4** 下游 suspend 消费者看不到年分区文件 | event_store.py `glob("*.parquet")`→`rglob("suspend_d_*.parquet")`（活体：root 0 → recursive 85） | 1 行修（该文件 git clean，安全） |
| **m1** catchup 双写 suspend_d（两次 API） | run_one_day 删显式 write_suspend_d（update_phase3_daily_market 已写） | 结构审 |
| **m2** close_hour=16 不够（daily_basic 到 17:00）+ 唯一 today-preclose 应 fail | cutoff 改 **17:30**（close_hhmm）；唯一候选是 pre-close today→**raise** | 新增 only-preclose-fail 单测 |

### §3/D 复核（REWORK 后）
- **D1/D2 仍纯 raw**：所有修复不改 `--no-qlib` 语义；日历**合并**仍只写 `data/reference/trade_cal.parquet`（原始参考层），不碰 provider/manifest/ledger。GPT 确认"harmful write 是原始参考日历，非 provider"。
- **B1 是本 REWORK 最危**：日更截断它自己用来选下一会话的日历——单会话即卡死，且 QA 读截断日历误报 PASS。已修（前向合并 + 选择器 fail-closed）。

### 验证汇总
88 绿（11 daily-5c + 7 catchup + 36 monthly + 34 report_rc）；6 文件 py_compile OK；register dry-run XML（+08:00/StartWhenAvailable/restart×3）；event_store rglob 修。

**结论：clean for GPT（re-review）。2 Blocker + 4 Major + 2 Minor 全修（含 XML-CST 任务 + heartbeat/watchdog + 日历合并 + suspend_d 校验）；C-4 注册仍 §13 留用户。**

---

## REVISE round 3（GPT re-review REVISE 后修复自审）— 2026-07-04

GPT 复审 7f1fb1d：**REVISE**（0 Blocker，4 prior fully fixed，4 partial）。逐条修完：

| # | GPT finding | 修复 | 校验 |
|---|---|---|---|
| **M1** heartbeat 未绑定 raw update 成功（QA 单独过就绿）| 新 **orchestrator** `daily_raw_job.py`：跑 update（含 gap 回填）+ QA，**仅两者都 0 才写 heartbeat**；QA 移除 heartbeat（只管 qa_alert）；分离 daily_job_alert；watchdog 改读 `completed_session` + 校验（8 位日期/不未来/有 daily 文件）+ **catch 全异常**（非仅 SystemExit）| 新增 updater-fail-QA-pass 逻辑（orchestrator errors→不写 heartbeat）；watchdog 校验 |
| **M2** 成功/错误合同不全（is_open=1-only 日历把周六当交易日；ref/calendar 错吞）| 交易日判定改**开市日成员制**（日历只含开市日→缺席=非交易；超覆盖=错）；`update_reference_data` 错入 `errors`（_reference_error）；catchup run_one_day suspend_d 失败→**raise**；suspend_refresh 失败入 `failed` | 新增 Saturday-skip + beyond-coverage-error 单测 |
| **M3** 非全无人值守 + 不回填多缺口 | register 加 `--user/--password`（**Password logon**=登出/重启后跑 + 保网络；S4U 无网不适 Tushare）+ 文档；`missing_open_sessions` gap walker（有界 lookback，**oldest-first**）由 orchestrator 处理 | 新增 gap-walker oldest-first + register --user Password XML 单测/实测 |
| **M4** 唯一 temp ≠ 跨进程锁 | `daily_ops.account_lock`（跨进程 Tushare-账号锁，steal stale）绕 update main + orchestrator + catchup main（§6.1 禁并行 fetcher）；`_normalize_trade_cal`（str/int 归一，防 mixed-dtype sort 崩被吞）+ `_atomic_write_parquet`（唯一 temp）用于 calendar/stock_basic | 新增 account_lock serialize/steal 单测 |
| **m1** .bat 非纯 ASCII（15 非 ASCII 字节注释）+ --query 返 0 | .bat 改**纯 ASCII**（实测 0 非 ASCII 字节）+ 调 orchestrator；--query combine schtasks rc | 字节数实测 0 |
| **m2** event_store 读全历史 | 按 `days` 直接构路径，只读请求日期 + 空早返 | 结构审 |
| **m3** 文档/测试陈旧 | data_dictionary.md 加 per-date suspend_d store（timing load-bearing）；self-review round-1 标"部分取代" | 文档更新 |

### §3/D 复核
- **D1/D2 仍纯 raw**：orchestrator 用 `update_for_date`（**从不触发 qlib**，qlib 只在 main() 内），构造即 raw-only；account_lock 只序列化 fetch，不改 provider。
- **§6.1 并行 fetcher**：account_lock 现跨 daily/monthly/manual 三入口序列化——修复 M4 指出的与该规则冲突。
- **heartbeat 绑定（M1 最危）**：现仅 update+QA 双绿写，watchdog 读 completed_session 且校验真有 daily 文件——QA 单过或手动 QA 不再误绿。

### 验证汇总
92 绿（22 daily-5c+catchup [含 Saturday/beyond-coverage/account_lock/gap-walker] + 36 monthly + 34 report_rc）；8 py 文件 compile；.bat 0 非 ASCII；register --user Password XML 实测；account_lock serialize/steal 实测。

**结论：clean for GPT（re-review 2）。4 Major + 3 Minor 全修（orchestrator heartbeat 绑定 + 成员制交易日 + Password-logon/gap-walker + 跨进程账号锁 + 纯 ASCII .bat + 精准读 + 文档）；C-4 注册仍 §13 留用户。**
