# Phase 5 设计自审（§10 前置，GPT 跨审前）

*2026-07-04 · 对象：PHASE5_DESIGN.md（设计阶段，无实现 diff）·结论：clean for GPT*

## 一、§3 硬不变量核对（设计是否会触犯）

| 不变量 | 判断 |
|---|---|
| 3.1 trade_cal 唯一地面真值 | ✔ target_end 定义以 trade_cal `is_open` 为准（§4.1/§7 判断 4） |
| 3.1 ST 权威 st_stocks.txt / delist 合同 | ✔ 月度 bump 重建自动再生侧车（已在 Phase 3 验证）；日更不碰侧车 |
| 3.2 PIT / ann_date 锚定 | ✔ 复用既有 catchup_fundamentals（ann_date 窗口法，已过 Phase 1）；§7 判断 5 显式提出"月度补齐是否漏 create_time 晚到行"送 GPT——这是唯一 PIT 关注点，已标注 |
| 3.2 report_rc create_time 锚 | ✔ §5.1 步 3 明确 report_rc 走 create_time 增量 + 重叠月（202602 教训延续） |
| 3.4 provider attestation / 政策 / approval 绑定 | ✔ 月度 bump 复用 Phase 2-4 全部治理机制（必填政策参数、审计、换绑、QA）；日更 `--no-qlib` 不产生任何 attestation 变更 |
| 3.4 publish 政策参数必填 | ✔ C5 已核实；月度 bump 显式传新政策 id |
| 3.4 D1 无全局政策 | ✔ 每次 bump 新政策 id（append-only）；回放用记录政策 |
| 3.5 factor lifecycle / sealed OOS | ✔ Phase 6 显式排除；spent_oos_end 冻结 2026-02-27 保护新鲜 OOS（§6） |
| D3 出生即封存 | ✔ 核心设计：spent_oos_end 不随日历前移（§6 表），新窗口生长且全程 born-sealed；日更 raw 非研究面纪律延续 |

## 二、按跨审 9 原则核对

1. **PIT/无前视**：唯一实质关注点 = 月度补齐 vs 日更逐日是否漏 create_time/update_flag 晚到行（§7 判断 5，已送 GPT）。其余复用已验证路径。
2. **OOS 神圣且封存**：设计**加强**而非削弱——spent_oos_end 冻结使新鲜 OOS 资产单调生长（§6）。潜在张力（数据在那儿半年不能碰）已作为 §7 判断 2 显式送 GPT，未擅自弱化。
3. **幸存者偏差**：月度重建 stock_basic 全量刷新（L/D/P）+ 侧车再生 + 冻结段侧车审计——正是本次解冻抓到 93-退市股洞的同一道闸。
4-6. 因子评估/执行成本/杠杆：不适用（数据运维，不改引擎/策略）。
7. **无对冲措辞**：§2 全部约束带 file:line；时长估计（upstream ~1.5h / 物化 ~7-15h）标注为"首次实测"；未把估计当承诺。
8. 四层管线：不适用。
9. 多重检验：不适用；spent_oos_end 冻结与该原则同向（防新窗口变反复测试集）。

## 三、自审发现并已处理

1. **[已纳入] 日更覆盖缺口**：核实日更 phase3 不含 suspend_d/cyq_perf/report_rc/stk_holdertrade/namechange/stock_st_daily（Grep 确认），已在 C4 + §4.1 + §5.1 步 3 分派（廉价的 suspend_d 进日更，昂贵/特殊的归月度补齐）。
2. **[已纳入] C2 日轮换陷阱**：核实增量 publish 每次新 build_id（代码事实），据此否决"日更动 provider"方案，选纯 raw 日更。
3. **[已送 GPT] spent_oos_end 冻结的实践张力**：未擅自决定，作为 §7 判断 2 交 GPT——这是 D3 语义的潜在弱化点，最需要独立视角。
4. **[已送 GPT] 全量重建时长**：§7 判断 3，若月度 8-15h 太痛是否现在就上真·追加物化器。

## 四、留给 GPT 的核心问题（§7 五判断）

日更是否需碰 provider（1）· spent_oos_end 冻结的张力与是否需滚动 IS 释放（2，最重要）· 重建时长与追加物化器立项时机（3）· target_end 权威定义（4）· 月度补齐的 PIT 完整性（5）。

**结论：clean for GPT。设计未触犯任何 §3 不变量；唯一 PIT 关注点与唯一 D3 语义判断均已显式标注送审，未擅自决定。**
