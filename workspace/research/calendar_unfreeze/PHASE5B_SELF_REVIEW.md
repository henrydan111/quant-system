# Phase 5-B 自审（monthly_calendar_bump driver，§10 前置）— 2026-07-04

*对象：`scripts/monthly_calendar_bump.py`（commit `d4f3c74`）+ 9 单测 · 结论：clean for GPT*

## 改动摘要

新 driver 打包手工 thaw Phase 1-4，三模式（--plan / --execute / --publish-approved），四个 PIT-相关新 helper + 两个新审计。

## §3 不变量 / D1-D3 核对

| 项 | 判断 |
|---|---|
| D1 无全局政策 | ✔ generate_thaw_policy 每次新 append-only id；rebuild 显式传 policy_id（不用默认） |
| D3 spent_oos_end 冻结 | ✔ generate_thaw_policy 硬编码 SPENT_OOS_END=2026-02-27 常量，只 calendar_end 前移；单测 resolve_spent_oos_boundary 验证 boundary 仍 2026-02-27 |
| 3.1 trade_cal 唯一真值 | ✔ target_end 以 trade_cal is_open 为准 |
| 3.1 生存者偏差（幸存） | ✔ **M2 fresh-window survivorship audit 是核心新增**：fresh 窗口内 raw 有价格行的每只 symbol 必在 all_stocks，否则 bump FAIL（无 blanket 例外）——保护未来 holdout |
| §13 风险动作 | ✔ publish 腿拒绝自动运行 live-mutation；需 --i-reviewed-the-dryrun + 报告存在；实际 swap 指向已验证的 depth9/sharecap 脚本 |

## 跨审 9 原则

1. PIT/无前视：target_end 只收完整交易日（M1 端点就绪，非 wall-clock）；partial daily→回退。
3. 生存者偏差：M2 审计正是防它。
7. 无对冲：--plan 实测 target_end=20260703；所有 helper 有单测。
其余不适用（orchestration，不改引擎/因子）。

## 留 GPT 的点（诚实）

- **M2 audit 的 code-form 转换**：raw ts_code `000001.SZ` → provider `000001_SZ`（§3.1 铁律）；audit 里做了 `.replace(".","_").upper()`。是否覆盖所有 code 形式（BSE .BJ 等）。
- **M2 的 list/delist bounds**：membership 用 all_stocks 的 range（list/delist），searchsorted。是否正确处理停牌（停牌 name 仍在 universe，raw 无价格行→不触发；反之 raw 有价格但 all_stocks 排除=违规）。
- **publish 腿未自动 wire live swap**：故意——首次 --execute 未端到端验证前，自动 mutate live 比指向已验证脚本更险。是否可接受此 scope（execute 路径 code-complete 但仅单元级 + --plan 验证）。
- **referenced-build 保留扫描（M3 design）未实现**：仅 disk floor 检查；parent_build_id 记入报告/政策 notes。完整引用扫描（approvals/五注册表/seal/frozen-selection/deployment-gate）留 follow-up。
- **target_end 端点就绪合同**：ENDPOINT_UPDATE_HOUR_CST（daily16/cyq19/report_rc22）+ MIN_PLAUSIBLE_DAILY_ROWS=4000。够不够严（是否需真探针每端点非空 + 期望数），还是 clock+daily-probe 足够授权正式 target_end。

## 验证

9 单测（M1 target_end 三例、policy 冻结+append-only、M3 exceptions wildcard/recurring、M2 survivorship flag/pass）+ --plan 实测 + parse + mode/publish gate 拒绝。

**结论：clean for GPT。核心 PIT 新增（M2 survivorship audit + M1 target_end + D3 冻结 policy）已实现+测试；4 个 scope/严格性判断显式留审。**

---

## REWORK round 2（GPT REWORK 后修复自审）— 2026-07-04

GPT 首审判 **REWORK**（7 findings：B1-B4 / M1 / M2 / m1）。逐条修复 + 复审如下。对象现为 `scripts/monthly_calendar_bump.py` + `workspace/scripts/catchup_fundamentals_range.py` + 16 单测。

| # | GPT finding | 修复 | 校验 |
|---|---|---|---|
| B1 | frozen-prefix 审计以 check=False 运行（忽略 exit）+ 硬编码路径 | 已在 e2153a6 修（THAW_STAGED_PROVIDER 参数化 + `fp.returncode != 0` 阻断）；本轮补 report 里 `staged_provider_dir` + `frozen_prefix_audit_ok` + artifact 名 | --plan 实测 |
| B2 | 端点就绪不完整 / --target-end 绕过 / datetime.now() 非 CST | `now_cst()`（ZoneInfo Asia/Shanghai）；`endpoint_ready()` 探每 per-day 端点文件存在 + daily≥4000；`determine_target_end(probe_ready=...)`；`--target-end` 经 endpoint_ready + 不得晚于 ready_target 校验 | 3 target_end 单测（probe_ready 签名） |
| B3 | catch-up 非 range-safe / report_rc halo 缺失 | driver 传 `--report-rc-start/-end`（TTL halo）+`--state-suffix`；catchup_fundamentals **Stage E 按窗口月份迭代跨年 + 按 report_date 年分文件 + range-scoped key**；Stage C 按 ann_date 年分文件；Stage F 月份由窗口派生；state 文件按 suffix 隔离；cyq buffer 按 suffix 隔离。catchup_daily 本就 per-date-key（天然 range-safe） | 5 range-safety 单测 + halo=20250712（跨年确认） |
| B4 | survivorship 审计缺 feature-tree 检查 | `fresh_window_survivorship_audit` 增 `raw_price_not_in_feature_tree`（raw 有价格但 `features/<code>/` 缺） | 新增 feature-tree flag 单测 + pass/flag 单测更新建树 |
| M1 | `json.loads` 读 YAML = 崩溃 | 改用 typed `load_calendar_policy(parent_policy)`（含 D3 regime 断言）**并顺带修我自己引入的 date-object bug**：`yaml.safe_load` 把 `spent_oos_end: 2026-02-27` 解析成 `datetime.date`，裸串比较会**永远误判 regression**；typed loader `str(...)` 归一 | 新增 parent-policy-normalize 单测（打活体政策） |
| M2 | 复发例外未 gate | recurring type → 阻断 bump，除非 `--allow-migration-exception`（复发必须转永久迁移 note+tests） | recurring 单测（已有）+ gate 代码 |
| m1 | `--publish-approved` 空操作返 0 | 写 `publish_handoff.json`（staged/policy/parent + required_manual_steps）+ **返 3（非零）**，scheduler 不会误判已发布 | mode/gate 拒绝路径 |

### 本轮我额外发现并修的 2 个正确性问题（非 GPT 提出）
1. **M1 date-object 误判**（见上）——`yaml.safe_load` 的 ISO 日期自动转 `datetime.date`，我最初的裸 `!= SPENT_OOS_END` 会让 execute 在真实政策文件上永远 return 2。经活体政策 roundtrip 证实（`repr` = `datetime.date(2026, 2, 27)`），改走 typed loader。
2. **report_rc first-seen 语义**（halo 跨到预 instrumentation 年文件）——2010-2025 年文件无 `raw_fetch_ts` 列，halo 重取时 concat 产生 NaN 戳。原 dedup（`na_position` 默认 last + keep first）会给 bootstrap 行盖上"今天"的戳（无 PIT 危害——预-fresh 行不吃 floor——但语义错）。改 `na_position="first"`：pre-instrumentation = 可能最早观测，NaN 应胜出。对 2026 文件（全有戳）零影响。

### §3 不变量 / D1-D3 复核（REWORK 后）
- **D3 spent_oos_end 冻结**：generate_thaw_policy 仍硬编码常量；**新增** phase_execute 对 parent 政策的 regime 断言（spent_oos_end/fresh_holdout_start 必须 == 常量，否则拒绝——防 Phase-6 release 政策被静默回退成 bump 父）。
- **§3.1 code-form**：survivorship 审计 `.replace(".","_").upper()` 覆盖 .SZ/.SH/.BJ；BSE 8xx/9xx 数字段无点，upper 无害。
- **§3.2 PIT**：report_rc halo = fresh_holdout_start −(TTL 120 交易日 + backfill 45 日历日)=20250712，跨年，Stage E 按 report_date 年正确分文件；first-seen 戳单调（earliest 胜）。
- **§13**：publish 仍手工 handoff，返非零，never auto-mutate live。

### 遗留（显式留 GPT / follow-up，未变）
- publish 腿仍不自动 wire live swap（指向 depth9/sharecap 已验证脚本）——首次 --execute 端到端验证前的有意 scope。
- referenced-build 保留扫描仍仅 disk-floor（M3 design 完整扫描留 follow-up）。
- halo 每 bump 重取 ~9 月 report_rc（含已结算历史）——正确性优先于效率的有意选择（抓 restatement），非缺陷。

### 验证汇总
16 单测全绿（11 driver + 5 catchup range-safety）；report_rc ledger 34 + calendar_policy 11 无回归（合计 61 绿）；--plan 活体实测（target_end=20260703，next=thaw_step2）；两脚本 import 干净；halo 跨年确认。

**结论：clean for GPT（re-review）。7 findings 全修 + 2 个自查正确性 bug 修复 + 归一走 typed loader；无阻断残留。**
