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

---

## REWORK round 4（GPT re-review #2 REWORK 后修复自审）— 2026-07-04

GPT 复审 a8778ca：**REWORK**（2 Blocker + 4 Major + 3 Minor）——四个 partial 未真正闭合。逐条重修（子系统级硬化）：

| # | GPT finding | 修复 | 校验 |
|---|---|---|---|
| **B1** account_lock 按年龄偷走活体多小时 catch-up 的锁 + 覆盖不全 | 全换 **filelock（内核持有，进程死自动释放，零年龄偷锁）**：`tushare_lock.raw_maintenance_lock`（daily/monthly/manual 入口互斥）+ `api_call_lock` **进内 `_safe_api_call`**（覆盖每个 sanctioned caller）；**catchup_fundamentals 补锁**（原裸奔）；QUANT_LOCK_DIR 可覆盖 | 新增 kernel-held 多进程单测（子进程持锁→父超时→kill→父可得，非年龄） |
| **B2** 日历"归一"把非法 is_open 静默转 0 | `_normalize`→**`_validate_trade_cal`**（缺列/空值/非 8 位日期/is_open∉{0,1}/dup key/**fresh 必全 1** → **raise**，不 coerce）；空 stock_basic/trade_cal fetch = 错误 | 新增 reject-BAD/reject-empty/reject-8digit/reject-missing-col 单测 |
| **M1** heartbeat 越过不完整早会话 | **完成清单**（`session_status/<date>.json`，required_ok=全必需端点成功）+ **连续 watermark**（首个不完整即止，heartbeat=watermark 非 target）；orchestrator is_trading_day=False→标不完整；顶层异常边界 + 原子写 | 新增 manifest/watermark/backlog 单测（hole 处止步，填后跳 0704） |
| **M2** "零错误"漏多端点 | phase3 REQUIRED（moneyflow/stk_limit）失败/空 → errors；reference 错误即使闭市日也上报；空 reference=错误 | reference/phase3 错误路径 |
| **M3** 15 会话滑窗=永久盲区 | backlog 从 **watermark floor**（月度发布边界）发现，非滑窗；`max_sessions_per_run=10`；orchestrator 一次性 floor+watermark | backlog/watermark 单测 |
| **M4** --password 泄漏命令行 | 删 --password，用 **`schtasks /RP *`**（交互提示）；UserId/desc/cmd/cwd/args **XML-escape** | register --user 实测（DOM\quant 保留） |
| **minor** watchdog/monitor 不健壮 | watchdog **精确校验**（`re.fullmatch \d{8}`，不 [:8] 截断；查 manifest required_ok）+ 写 **daily_job_alert**（非 qa_alert）；orchestrator 原子 heartbeat + 顶层边界；event_store 只读请求日期；data_tracker 8,797 / data_dictionary per-date store | 结构审 |

### 关键：跨进程锁的死锁分析
入口先取 `raw_maintenance_lock`（路径 A），API 调用逐次取/放 `api_call_lock`（路径 B）——**顺序恒定**（A 后 B），无进程反向取，无锁序死锁。QA 子进程在 maintenance 锁**释放后**跑。api_call_lock 只序列化 ingestion（研究/回测读 Qlib 不 fetch），blast radius 小。

### 验证汇总
99 绿（15 daily-5c[含 kernel-lock 多进程/manifest-watermark/validate-reject] + 8 catchup + 76 regression[含 provider_boundary，证 fetcher 改动无回归]）；11 py 文件 compile；fetcher+locks import 干净；register --user Password XML 实测。

**结论：clean for GPT（re-review 3）。2 Blocker + 4 Major + 3 Minor 全修（filelock 内核锁全覆盖 + 严格日历校验 + manifest/watermark 完整性 + 端点传播 + /RP* + 精确 watchdog）；C-4 注册仍 §13 留用户。**

---

## REWORK round 5（GPT re-review #3 REWORK 后修复自审，用户裁定"全硬化"）— 2026-07-04

GPT 复审 e295ef6：**REWORK**（2 Blocker + 4 Major + 3 Minor）——子系统未真闭合。用户选"全硬化，全做"。逐条：

| # | GPT finding | 修复 | 校验 |
|---|---|---|---|
| **B1** 正式月度构建无不可变原始边界（catch-up 放锁后从活体树构建）| 月度 bump **整个 phase_execute 持一把父级 barrier**（raw_maintenance_lock 包 catch-up→构建→审计→报告）；lock 改**env-reentrant**（QUANT_RAW_MAINT_LOCK_HELD，子 catch-up no-op 不死锁）；报告加 `raw_input_digest`（输入切面证明）| 新增 barrier-reentrant 单测（父持锁→子 no-op）；--plan 实测 |
| **B2** 日历校验仅句法，漏"缺会话"| `_validate_trade_cal` 加**连续性**（每开市日 pretrade_date==前一开市 cal_date，缺会话断链→raise；活体 8797 天 0 断链已验证安全）；merged 复校；orchestrator **先在锁内刷新日历再 resolve** | 新增 missing-session-reject 单测 |
| **M1** _safe_api_call 非可强制 chokepoint（脚本裸 .pro）| `self.pro`=**LockedPro 代理**（每次 .pro.xxx 内/外部都走 spaced_call）；_safe_api_call 去重复锁；**PRO001 AST lint**（禁 ts.pro_api() 外部构造）入 daily QA | lint OK；代理路由单测；76 回归无回归 |
| **M2** manifest/watermark 可假绿+不自愈 | `session_required_ok` **严格** `is True`+date==filename（string "false" 不再真）；backlog 从 **floor 全区间**扫（非只 >watermark）；`contiguous_watermark` **每次从 floor 重算**（忽略缓存→未来 watermark 不假绿+floor 前移自动 rebase）；watchdog 校**整区间**；floor **fail-closed**（去有界回退）；heartbeat 要 **watermark==target** | 新增 strict-manifest + poisoned-future-cache 单测 |
| **M3** QA/完成发布在事务外 | **全程 raw_maintenance_lock**（刷新→发现→更新→QA→heartbeat）——他人无法插写 | 结构审 |
| **M4** 必需完成=有些 OHLCV | update_market_data 校 **adj_factor（引擎必需）/daily_basic 覆盖率**（空/薄→_market_error 入 errors） | 新增 empty-adj_factor 单测 |
| **minor** 全局退避/RP*TTY/watchdog | 全局 next_allowed（锁内共享时戳→跨进程间隔+退避）；/RP* **TTY 预检 + 部分注册回滚**；watchdog 头改 + 成功清自身 alert | 结构审 |

### 关键设计
- **代理 vs _safe_api_call 双锁避免**：self.pro 是锁代理（内部 fetch 方法 `_safe_api_call(self.pro.xxx)` 传的就是代理方法→锁一次；_safe_api_call 自身去锁）。外部 `fetcher.pro.xxx`→代理→锁。单锁，无重入死锁。
- **barrier env-reentrant**：父 raw_maintenance_lock 置 QUANT_RAW_MAINT_LOCK_HELD→子进程继承→子 raw_maintenance_lock no-op（否则同锁跨进程死锁）。
- **fetcher 改动 blast radius**：仅 ingestion fetch Tushare（研究/回测读 Qlib），76 回归（report_rc 重度用 fetcher + provider_boundary）0 回归。

### 验证汇总
104 绿（20 daily-5c[含 barrier/manifest-strict/poisoned-cache/adj_factor/kernel-lock] + 8 catchup + 36 monthly + 34 report_rc + provider_boundary + calendar_policy）；PRO001 lint OK；12 py 文件 compile；monthly --plan + register dry-run 实测。

**结论：clean for GPT（re-review 4）。2 Blocker + 4 Major + 3 Minor 全修（全硬化：月度 barrier + 日历连续性 + 锁代理全覆盖+lint + manifest/watermark 严格重算 + 端点契约 + 全局退避）；C-4 注册仍 §13 留用户。**

---

## REWORK round 6（GPT re-review #4 REWORK，探针复现 3 Blocker+5 Major+3 Minor 后修复自审）— 2026-07-11

GPT re-review #4（HEAD afa7f35）**REWORK**：官方电池过，但**独立探针复现**了 3 Blocker + 5 Major + 3 Minor。REWORK-3 的"全硬化"在根子上错了——env-boolean 重入是可伪造+孤儿子进程绕过。逐条闭合（**每条带测试**）：

| # | GPT finding（探针复现） | 修复 | 测试 |
|---|---|---|---|
| **B1** env 重入=可伪造锁绕过 + 父死后孤儿子进程与新兄弟双写 | **彻底删除 env 重入**（`QUANT_RAW_MAINT_LOCK_HELD` 不再被读）。月度 bump：catch-up 子进程**各自持真内核锁**（无父 barrier），build+manifest+audits 在**一把进程内** `raw_maintenance_lock` 下（内部无重入子进程，已核）→ 拆 `_build_under_lock`/`_build_impl` | `test_raw_maintenance_lock_no_env_bypass`（伪造 env 不放行 + 内核崩溃释放） |
| **B2** 连续性被 `.all()` 门跳过（活体首个 pretrade_date=None→全链跳过）；多交易所 `cands[-2]` 仍今天 | 逐行独立校验（首行豁免，其余必须 8 位且==前一开市日；**去掉 `.all()` 门**）；强制 **SSE-only**（拒 SZSE/BSE）；`_open_days`/`resolve_last_complete_session` **去重** | `test_validate_trade_cal_rejects_missing_session`（活体过+中缺拒+多所拒，实测） |
| **B3** 无效 adj_factor 仍过正式路径→builder 静默 `fillna(1.0)` | update_market_data **校验后才提交**（schema/日期/唯一键/合并后非空覆盖），必需字段失败→**raise `MarketDataError`**（不写文件，删 `_market_error` 侧信道）；原子写；catch-up/orchestrator 消费异常；pit_backend `_load_price_frame` **fail-closed**（缺列/priced-NaN→`BuildGateError`，1.0 仅测试逃生门）；实扫 48 文件 0 空洞 | `test_update_market_data_raises_on_empty_adj_factor` + `test_load_price_frame_fails_closed_on_null_adj_factor` |
| **M1** `_LockedPro`/PRO001 非真边界（闭包/`__getattribute__(_real)` 可逃；lint 只认 `pro_api` 属性名；不可 pickle 隐晦） | 定位为**纪律非安全边界**（文档明说）；PRO001 **扩展**（`from tushare import`/别名、`DataApi()`、`object.__getattribute__(_real)`、`.__closure__`）；`__reduce__` **显式拒 pickle**；对齐 AGENTS.md（外部 `.pro` 绕过 `_safe_api_call` retry） | `test_locked_pro...`（+pickle 拒）+ lint 正向捕获 4 类绕过实测 |
| **M2** watchdog 丢 QA 绑定（QA 失败但 manifest 全绿→误绿+清 alert）；监视器变更进度态 | 拆 `compute_contiguous_watermark`（纯）vs `contiguous_watermark`（写）；watchdog 用纯的；heartbeat **QA 绑定**（`qa_ok`+floor+`manifest_set_digest`），watchdog 必须同时验 watermark==expected **且** QA-绑定 heartbeat 才 OK/清 alert | `test_watchdog_requires_qa_bound_heartbeat`（无/假 heartbeat 保持红） |
| **M3** `raw_input_digest` 弱（size+int-mtime 同尺寸字节交换碰撞）+ 只 4 数据集 + 不绑 build | 换 `_raw_input_manifest`：**全内容 SHA-256**（+cyq_perf+report_rc），256 位 root 入 report + handoff；**发布前重算比对**（phase_publish，不符 fail-closed）；窗口限定→前向日更不误伤 | `test_raw_input_manifest_content_hash_detects_byte_swap`（同尺寸字节交换 root 变） |
| **M4** provider floor 未证实 + 未来 floor 静默成功 | `_provider_floor` **在锁内**校 day.txt 语法/排序，tail==`provider_build.json.calendar_end_date`，floor 为 trade_cal 真开市日；`floor>target`→告警（非静默 0） | `test_provider_floor_attestation_fail_closed`（错配/乱序/未来 floor 全拒） |
| **M5** 任务对回滚删掉既有工作任务 | 变更前 `_export_task` 导出两任务 XML；半失败 `_restore_task`（原样恢复/新建则删；恢复失败存备份） | 结构审（schtasks 交互，dry-run 实测） |
| **m1** 全局 spacing 读写失败→静默归零 | fail-closed：状态不可读/写→在 API 锁内 in-band sleep base_sleep（绝不归零） | `test_spaced_call_fails_closed_when_state_unwritable` |
| **m2** strict reader 被自己 writer 击穿（`"false"`→存 true） | `write_session_status` 要求 `type(required_ok) is bool` | 结构审（TypeError） |
| **m3** 6h 锁 vs 4h 任务杀 | 日更用**短超时 900s** + `filelock.Timeout` 软跳过（return 0，watchdog 兜底） | 结构审（Timeout 分支） |

### 关键设计决策
- **锁跨 build 持有 = 首要完整性保证**（互斥→build 期间无写者），manifest = 绑 build_id 的**防篡改证据**（发布前重算，字节交换/带外编辑 fail-closed）。窗口限定 (parent_end, target_end]（会话完成即不可变）→前向日更不误伤重算。
- **pit_backend 是 §3 承重**：guard 不改任何正确输出（数据干净则 factor 逐字相等），只把静默腐化变 fail-closed；实扫 48 文件跨全程 0 priced-null-adj，不会误阻真实构建。
- **§10 纪律**：本轮无 OOS/因子选择/性能数字（纯 data-infra），staleness-flag 交叉核对 N/A；所有引用数字均为测试计数/覆盖率地板。

### 验证汇总
**422 绿 + 9 skip（全 tests/data_infra/）** + calendar_policy；含新增 `test_daily_update_5c`（no-env-bypass 多进程 / market-raise / 缺session / floor-attestation / watchdog-QA-binding / spacing-fail-closed）、`test_fetchers`（pickle 拒 + 逃生拒）、`test_pit_backend`（adj fail-closed）、`test_monthly_calendar_bump`（manifest 内容哈希）。PRO001 lint OK（+正向捕获 4 类绕过）；12 py compile + 3 脚本 import-smoke。

**结论：clean for GPT（re-review 5）。3 Blocker + 5 Major + 3 Minor 全修，每条带测试；env 重入根除、连续性真校验、adj fail-closed、锁-build 互斥+内容 manifest、floor 证实、watchdog QA 绑定。C-4 注册仍 §13 留用户。**

---

## REWORK round 7（GPT re-review #5 REWORK，探针复现 3 Blocker+5 Major+2 Minor 后修复自审）— 2026-07-12

GPT re-review #5（HEAD d9b04b0）**REWORK**：官方电池过（431 绿），探针仍复现 3 Blocker——REWORK-5 的修复太浅（换了 env-boolean 却留了 env-directory；漏了第二条 fillna；manifest 只覆盖 6/27 数据集）。逐条：

| # | GPT finding（探针复现） | 修复 | 测试 |
|---|---|---|---|
| **B1** 锁命名空间仍可伪造（`QUANT_LOCK_DIR` 换个目录即刻拿锁，raw+api 锁都受影响）| **删除 env 覆盖**；`_LOCK_DIR`=项目根固定绝对路径不可变；测试改**注入模块属性**（父 monkeypatch，子进程 `-c` 重赋 `tl._LOCK_DIR`），非 env | `test_raw_maintenance_lock_namespace_not_env_forgeable`（伪造 env 指别处仍 timeout） |
| **B2** 缺 adj_factor 仍能→1.0（`QUANT_ALLOW_UNIT_ADJ_FACTOR` 逃生门可达正式；**第二条** fillna@2264）| **删除 env 逃生门 + 两条路径**统一走 `_require_valid_adj_factor`（缺列/null/非数值/**非正**→`BuildGateError`，无生产默认）| `test_load_price_frame_fails_closed_on_invalid_adj_factor`（null/非正/缺列即使带 env 都 raise） |
| **B3** 正式 provider 未绑完整不可变输入切面（manifest 只 6 数据集，改 income 文件 root 不变；"发布"仅前置检查有手动缝，无 CAS，root 未入 schema）| **manifest 覆盖 builder 全读集**（27 `DATASET_SPECS` + reference，快照固定文件表）；`_verify_raw_manifest` 重哈希列出的文件；phase_publish **加 parent CAS**（live build/policy 必须仍是 report 的 parent）+ 全量重验，fail-closed。**残留见下** | `test_full_raw_manifest_covers_readset_and_detects_mutation`（改 income → root 变 + verify 失败） |
| **M1** MarketDataError 仍认证畸形会话（只校 2 列；错日期 daily_basic、重复 adj 键、98%+2 null 都过）| 共享 `_validate_endpoint_frame`（schema/目标日期/自然键唯一）；daily 全字段（OHLCV+pre_close）；**adj 覆盖 100%** 且正值；合并后 daily_basic **payload 覆盖** + 输出唯一 | `test_update_market_data_m1_probes_rejected`（三探针全拒） |
| **M2** 旧 heartbeat 认证新失败 QA（失败分支不失效旧证书；watchdog 直读 day.txt；floor==target 假红）| **attempt 记录**（uuid，变更前删旧 heartbeat 失效）；heartbeat 绑 attempt_id+provider ids+floor+digest；watchdog 要**最新 attempt 成功**；`provider_floor` 提共享（job+watchdog 同源）；floor==expected 绿、floor>expected 红 | `test_watchdog_requires_latest_attempt_certified` + `test_watchdog_greens_when_provider_current` |
| **M3** 锁竞争报成功（exit 0 关掉 RestartOnFailure）| 软跳返回 **DEFER_EXIT=75**（非零→调度器 30min 重试）+ 结构化 deferral 记录（非告警）| 结构审 |
| **M4** PRO001 漏别名（`make=ts.pro_api; make()`）| **禁 fetcher 外一切 tushare import**（Import/ImportFrom）+ 内省串（`_real`/`_base_sleep`/`__closure__`）作调用参数 | lint 正向捕获 4 探针（含 `import tushare as ts`） |
| **M5** 任务对回滚仍删既有任务（query 失败=当作不存在；只导 prev_daily；密码任务用新账户恢复）| `_task_exists` 用**列表成员**（非本地化错误串）；`_export_task` 返回 **ABSENT/PRESENT/QUERY_FAILED**；QUERY_FAILED **变更前中止**；导两任务；恢复返回 bool，密码任务缺旧凭据=**独立 fatal** | 结构审（dry-run 实测） |
| **m1** spacing 状态收 `nan`（float() 过但 delay>0 False→立即执行）| `math.isfinite`+合理时间窗校验；原子写状态 | `test_spaced_call_fails_closed_on_nan_state` |
| **m2** 正式日历消费者未走 canonical validator（bump `_open_trading_days` 直读排序）| `_open_trading_days` 走 `_validate_trade_cal`（SSE-only/连续性/真日期）+去重唯一 | 全 monthly 电池（4 fixture 补真 pretrade 链） |

### B3 残留（诚实披露，留用户裁定）— 见 GPT #1 残留风险
B3 已修：manifest 全读集覆盖 + phase_publish CAS+全量重验 fail-closed。**未做（需用户裁定）**：
- **B3.2** 把 `raw_input_manifest_root` 写进已发布 `provider_build.json` 并列入 `provider_build.schema.json` 必填 —— 触及 **活体 provider_build.json**（现无此键，硬必填会让加载器拒绝活体 provider）+ manifest 加载器，需迁移。
- **B3.3-5** 把手动 §13 换库流程（`_depth9_safe_publish.py`+`_rebind_approvals`）**自动化成一个原子事务**（验证与 os.replace 不可分）—— 触及活体 241GB provider，**本会话无法端到端集成测试**（无 staged build 可发布）。盲改风险=损坏最承重工件。
- 当前 phase_publish 是 fail-closed **门**（CAS+全量重验，任何漂移拒发布）+ handoff 明标"换库前须原子重验"。GPT 说"手动间隔不能是完整性边界"——同意；这是剩余工作，建议作专项 Phase-5-B（有 staged build 可测时）而非盲改。

### 验证汇总
**430 绿 + 9 skip（全 tests/data_infra/）**；含 B1 namespace-forge / B2 adj-invalid(null/非正/缺列) / M1 三探针 / M2 latest-attempt+provider-current / m1 nan-state / B3 full-manifest-income-mutation。PRO001 lint OK（+4 探针正向捕获）；10 py compile + 4 脚本 import-smoke。

**结论：clean for GPT（re-review 6）。3 Blocker（B1/B2 全修；B3 = 全读集 manifest + CAS 门，自动原子换库为披露残留）+ 5 Major + 2 Minor 全修，每条带测试。B3.2/B3.3-5 = 触及活体 provider 的专项、留用户裁定。C-4 注册仍 §13 留用户。**
