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
