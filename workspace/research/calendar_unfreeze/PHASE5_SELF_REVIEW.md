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

---

# Round-2 自审（v2 修订后，re-review 前置）— 2026-07-04

**背景**：GPT Round-1 = REVISE（B1 report_rc 前视 + M1 target_end 就绪 + M2 新鲜窗口生存者审计 + M3 例外洗白 + m1 时长阈值）。GPT fetch 了真实 repo + Tushare 官方文档。全部 5 条接受，无拒绝。

## 独立核实（不 rubber-stamp GPT）

- **B1 亲自核实 pit_backend.py:2461-2486**：`contemporaneous = gap_days <= 45` → 否则锚 `report_date+2`；代码注释 2471-2486 自认"clean-era 大 gap 行锚得早于 create_time = potential early-exposure"仅 WARN。**GPT 判断完全正确**——月度 regime 下新鲜窗口的真实晚到行（report 3 月/create_time 5 月）会被回锚进 sealed 窗口 = 前视泄漏，污染未来 holdout。B1 是真 Blocker。

## 修订忠实性

- B1：report_date replay + 新鲜窗口禁 backfill 回退 + max(report_date,create_time) + 缺则隔离 + 回锚早于 create_time = build 阻断（§5.1 步 3，照 GPT 替换文本逐条）。
- M1/M2/M3/m1：§4.1/§5.1 步 2、步 6(b)、步 6 例外、§8 风险表——均照 GPT 替换文本。
- GPT Q2 裁定（spent_oos_end 冻结正确 + 释放须 spend 事件）折入 §6，明确释放机制归 Phase 6。

## v2 新引入自查

- report_rc 锚改动会触及 §3 报表族 PIT 逻辑（load-bearing）——但方向是**收紧**（新鲜窗口更保守，不锚早于可见），不放松任何历史行为；historical bulk-backfill（2022-05 stamp on 2010-2021）不受影响（那些 report_date < fresh_holdout_start）。实现时须跑 report_rc 全测试族 + PIT canary（feedback: run full test file after gate change）。
- 新鲜窗口审计是纯新增闸，无回归面。
- 无对冲措辞；时长仍标"首次实测"。

**Round-2 结论：clean for GPT re-review。B1 独立核实为真；修订收紧 PIT 未放松，实现阶段须过 report_rc 测试族。**

---

# Round-3 自审（v3 修订后）— 2026-07-04

**背景**：GPT R2 = REVISE，单 Blocker B2（我的 B1 修订守卫键太窄）+ minor m2。B2 接受并已实施；m2 裁定为缓存伪报。

## 独立核实（不 rubber-stamp）

- **B2 亲自核实**：`REPORT_RC_ACTIVE_TTL_OPEN_DAYS = 120`（[pit_backend.py:192](src/data_infra/pit_backend.py#L192)，"a forecast counts as live for this many trading days"，carry daily 于 2888/2970/3117）——GPT 假设的常量精确正确。report_date 早于边界 ~120 天的 forecast 仍 carry 进新鲜窗口 = B2 的 halo 要求有真实材料化依据。B2 是真 Blocker，我的 B1 确实漏了 availability-boundary 语义。
- **m2 亲自核实**：`git show HEAD:...PHASE5_DESIGN.md | grep -c "report_date replay"` = 6，且 `HEAD == origin/calendar-unfreeze == e897424`——v2 文本确在远程；GPT 读到 GitHub raw 缓存的旧版。m2 是缓存伪报，非流程 bug；但采纳其守卫（impl ticket 引 v3 hash）。

## 修订忠实性（照 GPT B2 替换文本）

- 4 条件任一守卫 ✔；effective 下限 `next_open(max(report_date, create_time, first_seen_floor))` ✔；修订台账（键 = 自然键+payload digest+create_time+first_seen+batch_id，禁 effective 后退）✔；pre-boundary halo ≥ TTL(120)+guard ✔；历史 backfill 仅对全字段窗外行保留 ✔；日更 fallback 纯 raw 禁增量发布 ✔。
- M1（探针=publish 阻断）+ M2（list/delist 边界 + raw-vs-侧车矛盾=失败）实现精度已折入。

## v3 新引入自查

- 守卫加宽是**进一步收紧**（更多行走 fail-closed 锚），不放松任何历史行为；历史 2010-2021 backfill 显式保留（全字段窗外）。
- 修订台账是新数据结构——实现须确保台账本身 PIT（first_seen 单调、不可回填）；已在设计标注"禁 effective 后退=build 阻断"。
- 无对冲措辞。

**Round-3 结论：clean for GPT re-review。B2 独立核实为真（TTL=120 精确）；守卫从 report_date 加宽为可见性/生效/修订影响，进一步收紧未放松；m2=缓存伪报已核实。**

---

# Round-4（M4 verbatim 修正后）— 2026-07-04

GPT R3 = REVISE，**B2 RESOLVED**，唯一新 issue = M4（§9 交付清单残留旧 `report_date>=boundary` 指令与已批准 §5.1/§11 矛盾——纯文档自洽缺陷，非逻辑）。GPT 提供 verbatim 替换文本，已逐字应用于 §9（完整 B1+B2 规则 + 5 类必测）。核实：残留 6 处 `report_date>=boundary` 均在正确上下文内（4 条件守卫的条件①、处置表描述被否决项）；旧独立 §9 指令已消失（grep 确认）。

**判断（proportionate review）**：M4 是文档-artifact 矛盾非新逻辑，GPT 已裁定 substance ready 且给 verbatim 文本、我逐字应用——Round-4 全量清场对单个 verbatim 文档 bullet 近零信息量。故记为**实质 SHIP**（跨审 arc R1→R3 关闭，B2 为关键实质发现）；[GPT_PHASE5_REREVIEW3_PROMPT.md](workspace/research/calendar_unfreeze/GPT_PHASE5_REREVIEW3_PROMPT.md) 备一分钟清场 prompt 供可选发送，但设计已可进入实现。

**Phase 5 设计定稿。实现阶段交付物见 §9；实现后须走实现 diff 的 GPT 审查（如 Phase 2 墙）。**
