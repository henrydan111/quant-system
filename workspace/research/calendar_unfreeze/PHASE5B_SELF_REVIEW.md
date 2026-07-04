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

---

## REWORK round 3（GPT 第 2 轮 REWORK 后修复自审）— 2026-07-04

GPT 复审了正确的 `4cd2fec`（不再是 stale d4f3c74），确认 **B1-path / M1 / m1 RESOLVED**，并给出更锐利的 REWORK（5 项）。逐条修复：

| # | GPT finding | 修复 | 校验 |
|---|---|---|---|
| **B1** endpoint 存在≠完整 | 关键洞察：**cyq_perf 滞后**（活体 07-01 vs daily/moneyflow/stk_limit 07-03，Stage-D 逐股抓，由 bump 自身 catch-up 补齐）→ 存在检查在 catch-up 前无意义。改**两层门**：`endpoint_ready`（**pre**-catch-up，按**行数**卡 daily+moneyflow+stk_limit 这些 daily-fresh 端点，非存在）定 target_end；`assert_endpoints_complete`（**post**-catch-up，卡 cyq_perf 行数）在建 provider 前 fail-closed。northbound（覆盖天然偏+衰减）不设硬门 | 活体：ready(20260703)=True，complete=False（cyq_perf=0，正确阻断）；2 新单测（行数非存在 / 滞后 cyq_perf） |
| **B2** frozen-prefix 审计 blanket 例外 | 审计脚本加 `THAW_MONTHLY_MODE`：monthly 严格模式**禁用** IND_FIELDS/report_rc__* SHA 家族豁免 + sidecar-healing 豁免（settled parent 必须逐字节+成员一致，任何 drift=违规）；report 记 `gross_sha_drift`/`monthly_strict`。driver 已传 THAW_MONTHLY_MODE=1。合法 frozen-prefix 修正=带外迁移（provider-id 轮换），非 monthly | py_compile + 现有审计门路径 |
| **M1** feature-tree 仅查目录 | survivorship 改查**核心价格 bin 齐全**（`REQUIRED_PRICE_BINS`=open/high/low/close/vol/amount/adj_factor.day.bin；活体确认 bin 名 `vol`/`adj_factor` 非 volume/factor）；缺 bin 的目录=feature-incomplete→flag | 新增 partial-bin 单测 + 建树 helper 改写 |
| **M2** report_rc halo 全零记成功 | Stage E 收集 `month_results`；**全窗口零帧→raise**（endpoint 迟到/限流/凭证/schema 坏），除非 `--allow-empty-report-rc`（仅 verified-empty） | Stage-E raise 路径 + 单测（dedup 语义锁） |
| **m1** raw_fetch_ts NaN 理由太窄 | 注释改精确：pre-boundary NaN 行**可**经 TTL carry 影响 fresh，但安全（ledger 隔离缺双时间戳的 fresh-affecting 行；改内容=独立 revision 带今日戳） | 新增 first-seen dedup 回归单测 |

### 我对 GPT B1 建议的修正（split-gate，GPT 未识别的顺序问题）
GPT 的 B1 exact-fix 让 `endpoint_ready` pre-catch-up 就卡 cyq_perf 行数。但**活体证明 cyq_perf 滞后**——pre-catch-up 时它本就缺（由本 bump 的 catch-up 补），若 pre-gate 卡它会把 target_end 误退到 cyq_perf 最后覆盖日（07-01），défeat bump。正确架构是**两层**：daily-fresh 端点定 target_end（pre），滞后端点 post-catch-up 验证。已如此实现并活体验证。

### 额外硬化（GPT #1 残留风险，本轮先落地）
- **审计跑错树防护**：driver 在 frozen-prefix 审计后读 `frozen_prefix_audit.json` 的 `staged` 字段，断言 == 本次 staged_provider（THAW_STAGED_PROVIDER plumbing 回归即阻断）——直接关掉 GPT "audited the wrong staged provider" 的 #1 风险。

### 留 GPT / follow-up
- feature bin **长度** sanity（bin 覆盖到 target_end）未做——presence + 重建完整性覆盖主风险；frozen-prefix 审计已查 prefix bin size。显式留审。
- 审计的历史 first-thaw 例外仍在脚本内（仅 monthly 模式禁用；standalone 保留）——未迁成 typed diff_hash 行（第一次 thaw 已完成，例外为历史记录）。

### 验证汇总
65 绿（14 driver + 6 catchup + 34 report_rc + 11 calendar_policy）；3 脚本 py_compile OK；--plan 活体（target_end 20260703 / next thaw_step2）；split-gate 活体行为正确。

**结论：clean for GPT（re-review 2）。5 findings 全修 + split-gate 顺序修正 + 审计跑错树硬化；2 项显式留审（bin 长度、typed 例外迁移）。**

---

## REWORK round 4（GPT re-review #2 后修复自审）— 2026-07-04

GPT 复审 68b0ee3：确认 **m1 RESOLVED + split-gate 架构正确**，给出更锐 REWORK（2 Blocker + 2 Major + 1 minor）。逐条修复，全部落实（含之前留审的 bin 长度）：

| # | GPT finding | 修复 | 校验 |
|---|---|---|---|
| **B1** 固定行数 floor 非端点级完整性 | 改**覆盖率门**：`coverage = |端点∩daily universe|/|daily|`，per-endpoint floor（moneyflow 0.90 / stk_limit 0.95 / cyq_perf 0.95，由完整日 2026-06-30 实测 0.94/1.0/1.0 设定）；3000 行仅作 corruption/empty guard。活体：ready(20260703)=True（mf 0.9414 / stk 1.0），complete=False（cyq 0.0） | 新增 high-rows-low-coverage 单测（10 行但覆盖 0→拒） |
| **B2** frozen-prefix 审计仍**抽样** SHA（1/50）| monthly 模式 `sample = MONTHLY_MODE or (si%50==0)` → **每根 bin 全哈希**；report 记 `sha_mode=full` + `sha_eligible`；加覆盖断言 `n_sha==n_eligible`（monthly 全哈希无遗漏）。⚠ 运行成本：~5.5M bins 全哈希 ≈ ~1h（月度操作可接受，已 log 进度） | py_compile；断言逻辑 |
| **M1** bin 存在但未证覆盖到 target_end | 解码 Qlib header（`float32[0]=start_index`，`last_pos=start_index+nvalues-1`）——GPT 建议的 `required_len*4` 会误杀所有 2008 后上市（其 start_index>0），故按 header 解码才正确；raw 有价格当日的 code，其 close.day.bin 必须覆盖该日 pos | 活体：000001 last_pos 4492==日历末；新增 short-bins 单测 |
| **M2** halo 月级零仍记成功 | Stage E 收 `month_results`；**任一月零行**（非白名单）→ raise，除非 `--allow-empty-report-rc-month YYYYMM`；whole-window 零仍 raise（除非 `--allow-empty-report-rc`） | 新增 zero-month fail-closed 单测 |
| **m1** Stage-D 零行 cyq 污染 resume | driver 在 `assert_endpoints_complete` 失败时 `_prune_cyq_state(target_end)`：删 `D:cyq*`/`D:cyq_repartition` 键，rerun 重抓（否则零行"done"被跳过，bump 不可恢复） | prune 逻辑 |

### 我对 GPT 建议的 2 处修正
1. **M1 bin 长度**：GPT 的 exact-fix 假设 bin 跨整个日历（`min_bytes=required_len*4`），会误杀所有 2008 后上市（start_index>0，bin 更短）。活体确认 Qlib 格式 = header+values，正确检查是解码 header 得 last_pos（000001 验证 last_pos==日历末）。
2. **B1 覆盖率 floor**：GPT 举例 0.98，但实测 moneyflow 自然覆盖仅 0.94（低流动性名无 flow）→ 0.98 会误杀。按实测设 per-endpoint floor（mf 0.90 留 margin）。

### 留 GPT / 已知成本
- **B2 全哈希运行时**：monthly 全哈希 ~5.5M bins（features 子树）≈ ~1h I/O。月度操作可接受；显式告知，若需更快可后续并行化。非正确性问题。
- northbound 仍不设硬门（覆盖天然偏+衰减；无正式 provider 字段声称其日完整）。

### 验证汇总
68 绿（16 driver + 7 catchup + 34 report_rc + 11 calendar_policy）；3 脚本 py_compile OK；活体：coverage 门（mf 0.94/stk 1.0）、complete 正确阻断（cyq 0.0）、bin 解码（last_pos 4492==日历末）。

**结论：clean for GPT（re-review 3）。2 Blocker + 2 Major + 1 minor 全修，含之前留审的 bin 长度；2 处修正 GPT 建议（bin 格式、覆盖 floor）；唯一已知成本=全哈希 ~1h，显式告知。**

---

## REWORK round 5（GPT re-review #3 后修复自审）— 2026-07-04

GPT 复审 971282a：确认 **B2 / M2 / m1 RESOLVED**，余 2 项 —— Blocker B1（daily 自身可能部分完整）+ Major M1（bin 只查 close）。均已修：

| # | GPT finding | 修复 | 校验 |
|---|---|---|---|
| **B1** daily 作分母不安全（部分 daily >4000 也过；且未验 trade_date）| daily 变成**完整性对象**：`_daily_universe` = (1) 文件 `trade_date==date`（`_read_codes_for_trade_date`，防陈旧/错分区）+ (2) 绝对 floor + (3) **滚动基线**（近 10 完整日 daily 计数中位数 × 0.98；活体计数 5507-5517 波动 <0.3% → 基线极紧，部分 daily 立即被抓）。所有端点覆盖率的分母改为这个**已证完整**的 daily | 活体：daily(20260703) codes 5516 vs 基线 5511 ratio 1.0009 通过；新增 partial-above-floor 单测（12 vs 基线 20→拒）+ stale-trade_date 单测 |
| **M1** bin 只查 close.day.bin | `_bin_span` 返回 (start,last) + `size%4` 守卫；survivorship (c) 对**每根** REQUIRED_PRICE_BIN 查 `start<=pos_d<=last`（vol/amount/adj_factor 截断也抓）| 活体：000001 全 7 根 bin last_pos 均==日历末；短-bin 单测仍中 |

### 我对 GPT B1 建议的选择
GPT 给了两条路：重建 expected universe（list/delist − suspend）或滚动基线。选**滚动基线**——依赖轻（不需 stock_basic/suspend_d 对账，各有 PIT/完整性依赖）、直击失败模式（中断抓取=计数骤降）、活体计数稳定（<0.3% 波动）使 0.98 floor 极紧。**已知界限**（显式留审）：<2% 的轻微部分（~110 名，在自然波动内）不与基线区分；但中断抓取丢大块，非轻微，故 0.98 干净分离。expected-universe 重建更紧但依赖更重——留作 follow-up。trade_date 校验补上 GPT 第二形态（陈旧/错分区文件）。

### 验证汇总
70 绿（18 driver + 7 catchup + 34 report_rc + 11 calendar_policy）；3 脚本 py_compile OK；活体：daily 基线（5516 vs 5511 ratio 1.0009）、覆盖门（mf 0.94/stk 1.0）、complete 阻断（cyq 0.0）、全 7 bin span 到日历末。

**结论：clean for GPT（re-review 4）。B1（daily 完整性对象 + trade_date）+ M1（全 bin span）全修；1 处显式界限（轻微部分 daily，留 follow-up）。**

---

## REWORK round 6（GPT re-review #4 后修复自审）— 2026-07-04

GPT 复审 20e096c：确认 **stale-file guard / endpoint split / all-bin span RESOLVED**，余 2 项 —— Blocker B1（滚动计数基线非集合级完整性证明，<2% 缺名可过且 survivorship 审计看不见）+ Major M1（provider 日历缺 fresh 日被静默跳过）。均修：

| # | GPT finding | 修复 | 校验 |
|---|---|---|---|
| **B1** 计数基线≠完整性证明（<2% 缺名可过）| 加**集合级连续性证明** `_daily_set_continuity`（post-catch-up）：昨日**在交易**（故已上市且未停牌）之名，今日必须交易，除非 delist（stock_basic.delist_date≤date）或**今日新停牌**（suspend_d 当日 S 事件）。关键洞察=昨日在交易者，今日消失的 PIT 理由只可能是 delist 或**当日**新停牌（无需历史停牌状态重建）。无理由消失=survivorship hole → **fail-closed**；suspend_d 缺失→fail-closed。滚动基线降级为廉价早探。code-form=dotted-upper（与 _read_codes 一致，stock_basic/suspend_d 本就带点仅 upper，**不**转下划线）| **活体验证**：continuity(20260703 vs 20260702) ok=True, prior 5517, suspended 18, delisted 333, **missing 0/unexpected 0**（真实完整日零误报）；3 新单测（无理由消失→拒 / delist+IPO / suspend_d 缺失 fail-closed）|
| **M1** provider 日历缺 fresh 日静默跳过 | `pos_d is None` → **violation** `raw_price_day_not_in_provider_calendar` + continue（不再静默跳过）；全 bin span 检查保持 | 新增 day-not-in-calendar 单测 |

### 架构位置
- **pre-catch-up**（endpoint_ready，定 target_end）：trade_date + 滚动基线 + daily-fresh 覆盖率（廉价候选选择）。
- **post-catch-up**（assert_endpoints_complete，建 policy 前的正式门）：daily 基线 + daily-fresh 覆盖 + **集合级连续性证明**（prev daily + stock_basic + suspend_d 均已就绪）+ cyq 覆盖。正式完整性证明落在这里——正是"formal provider 声称完整日"的把关点。

### 为何集合连续性优于全 universe 重建
GPT 建议二选一。选**连续性**：只需 prev-daily + stock_basic + suspend_d(当日 S)——因昨日在交易者今日消失只能 delist/当日新停牌解释，**无需**历史停牌状态重建（多日停牌的中间日名本就不在 prior，故不误判）。活体零误报确认逻辑正确。

### 验证汇总
74 绿（23 driver + 6 catchup + 34 report_rc + 11 calendar_policy）；py_compile OK；活体：连续性证明真实完整日零误报（missing 0/unexpected 0）。

**结论：clean for GPT（re-review 5）。B1（集合级连续性证明，fail-closed）+ M1（日历缺日 fail-closed）全修；活体真实数据零误报验证。**
