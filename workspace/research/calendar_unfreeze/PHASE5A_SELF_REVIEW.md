# Phase 5-A 实现自审（report_rc availability-boundary 守卫，§10 前置）

*2026-07-04 · 对象：commits `861477d`（锚守卫）+ `993f80e`（无后退台账 + raw_fetch_ts）· 结论：clean for GPT*

## 一、改动摘要（3 文件，+305/−17）

1. **pit_backend.py**：`REPORT_RC_FRESH_HOLDOUT_START=2026-02-28` 常量；`build_ledger` report_rc 锚块重写（4 条件 affects_fresh 守卫 + 禁 backfill 回退 + 缺 ct 隔离/raw_fetch_ts floor + build 阻断守卫）；`_report_rc_assert_no_retrograde` 方法 + build_ledger 调用。
2. **test_report_rc_ledger.py**：8 新测试（4 锚守卫 + 2 无后退 + 1 历史豁免 + 1 raw_fetch_ts 救回）。
3. **catchup_fundamentals_range.py** stage E：raw_fetch_ts 首见打戳 + content-dedupe。

## 二、§3 硬不变量核对

| 不变量 | 判断 |
|---|---|
| 3.2 PIT/ann_date 锚定 | ✔ 核心目的；改动**收紧**（fresh 行不再锚早于可见），历史路径 byte 不变（14 历史测试全绿回归证明） |
| 3.2 report_rc create_time 锚 | ✔ 保留 contemporaneous(≤45)→max、历史 backfill(>45)→report_date+2；**仅对 fresh 窗口**加严 |
| 3.2 pit_research_loader/qlib door | ✔ 未触碰 door；改的是 ledger 物化层（provider 侧），研究读仍经既有门 |
| 3.4 formal-run governance | ✔ 未改 provider attestation/政策/审计；build 阻断守卫用既有 `BuildGateError`（allow_exceptions 不绕过——它是 raise，materialize 前） |
| 3.5 factor lifecycle | ✔ 不改因子；report_rc 字段状态不变 |
| D3 出生即封存 | ✔ 直接强化：fresh 窗口 report_rc 不再有回锚泄漏；no-retrograde 防修订回填 |

## 三、跨审 9 原则

1. **PIT/无前视**：核心。三层防线——锚守卫（fresh 行锚真实可见）、no-retrograde（修订不回填）、build 阻断（回锚早于 floor 即拒）。历史路径不放松（豁免 + 14 回归测试）。
2. **OOS 神圣**：fresh 窗口是未来 holdout，本改动堵住它的 report_rc 泄漏面 = 保护 OOS。
3. 幸存者偏差：不适用（report_rc 锚定，非 universe）。
4-6：不适用（数据物化，不改引擎/因子/杠杆）。
7. **无对冲**：所有断言有测试；raw_fetch_ts 打戳时间语义已诚实标注（transition 期 old 行保守 over-estimate）。
8. 四层管线：不适用。
9. 多重检验：no-retrograde 防 fresh 窗口被反复修订回填成"新数据"。

## 四、自审发现/已处理 + 留给 GPT 的点

- **[已处理] 历史豁免正确性**：no-retrograde 仅对 fresh key（effective 或 report_date ≥ 边界），历史 key 豁免——因深史 best-known-state re-dating 是既有 intentional 行为（restatement）。测试 `test_report_rc_historical_retrograde_not_blocked` 锁定。
- **[已处理] build 阻断 vs allow_exceptions**：守卫是 `raise BuildGateError`，在 materialize 前，`allow_exceptions` 是 validate 后的软化开关，不绕过 raise。
- **[留 GPT] raw_fetch_ts transition 语义**：当前 live provider 的 fresh report_rc 无 raw_fetch_ts（catch-up 时未打戳）；重跑 stage E 会给它们打 NOW 戳（保守 over-estimate first-seen，非泄漏）。是否需要一次性重物化 fresh report_rc 以应用新锚（当前 live 仍带旧锚，但 D3-sealed 无泄漏，下次 bump 修正）——GPT 裁定。
- **[留 GPT] 边界常量 vs 政策驱动**：`REPORT_RC_FRESH_HOLDOUT_START` 是模块常量（frozen per design §6），未从政策 YAML 读。设计冻结它=2026-02-28 永久，但与 fresh_holdout_start 政策字段有耦合风险（若将来两者漂移）。是否需要 build-time 断言 constant==policy.fresh_holdout_start。
- **[留 GPT] content-dedupe 的 content_cols 范围**：stage E 按"除 raw_fetch_ts 外全列"dedupe——是否稳健（若 vendor 加列/改列名），以及 payload-digest 是否应显式 canonicalize 而非隐式全列。

## 五、验证

- 22 report_rc ledger 测试（8 新）+ 130 backend/canary/registry/share-capital regression green；PIT002 lint clean；driver parses。
- 14 历史测试全绿 = 深史路径 byte 不变的回归证明。

**结论：clean for GPT 实现 diff 审查。核心泄漏（B1/B2）+ 无后退（B2 台账）双闭合，历史路径证明不变；4 个判断点显式留审。**

---

# Round-2 自审（GPT REWORK 修订后，`c917414`）— 2026-07-04

**背景**：GPT 实现审查 = REWORK（2 Blocker B1/B2 + 3 Major M1/M2/M3）。全部核实为真（M1 亲证：normal stamped 行会 trip guard；B1 亲证：TTL=120 carry 真实）。全部接受。

## 修订忠实性（逐条 vs GPT 替换文本）

- **B1（condition 4）**：`affects_fresh` 加 effective_intersects + active_carry(pre_pos+120>=fresh_pos)；**加 `fresh<=calendar_end` 守卫**（GPT 未提但必需——否则 fresh 超出测试日历时 fresh_pos=len 致误判；2020/2022 历史测试证明修好）。测试：carry-into-fresh 锚 create_time、deep-no-carry 保 backfill。
- **M1（per-row floor）**：单一 `visibility_floor`（ct 行=max(report,create)；缺 ct=raw_fetch）同时用于 anchor + guard；raw_fetch 绝不 inflate 有 create_time 的行。normal stamped 行不再 trip。
- **B2+M2（append-only 基线）**：`report_rc.revision_baseline.parquet` 存 per-key min-effective，never drop key；fresh_scope 含 new **或** baseline effective + carry。测试：fresh-to-prefresh、disappear-reappear。
- **M3**：`_assert_report_rc_boundary_matches_policy` 在 build_ledgers 前（publish 政策加载处）；测试 mismatch/match/legacy。

## 有意 scope（留 GPT 裁定，未擅自扩）

- **M2 payload_digest/vendor_create_time/first_seen/ingest_batch_id 完整修订身份键未实现**：我实现的是 per-natural-key min-effective 单调基线。论据：PIT-critical 不变量 = fresh key 的 effective_date 单调不后退（+存活 drop），已闭合；payload 修订**若改 effective** → 被 effective 单调捕获；payload 修订**不改 effective** → 非前视（可见性不变）。故 payload_digest 是 provenance/audit 非 PIT-critical。是否可接受此 scope，留 GPT。
- **replay halo（fresh−120 抓取）**仍归 5-B 抓取步（GPT Q5 已裁"可接受，只要无 bump 在 halo 抓取前 claim corrected fresh report_rc"）。

## 验证

26 report_rc 测试（9 新）+ 336 data_infra pass + PIT002 clean。历史 2020/2022 测试全绿 = 深史路径不变。

**Round-2 结论：5 findings 全修，2 项有意 scope 显式留审。clean for GPT re-review。**

---

# Round-3 自审（GPT REWORK#2 修订后 — B3 完整修 + M4）— 2026-07-04

**背景**：GPT 实现审查 Round-2 = REWORK（B3 value-lookahead 新 Blocker + M4）。B3 我 preflight 的"payload 修订不改 effective 非前视"论据**错误并已认**（混淆日期可见性与值可见性）。**用户选 (b) 完整修**（非保守 fail-closed）。

## B3 完整修（revision-preserving，`bc6669f`+`aef26c6`）

- **first-seen floor**（`bc6669f`）：served fresh 行锚 `max(report, create, first_seen_raw_fetch)`；raw_fetch=stage-E 最早戳 → 稳定行不膨胀（M1 保持）、晚见/修订值 floor 在首见。
- **payload_digest 入 ledger key**（`aef26c6`）：同-(analyst, report_date, quarter) 的值修订（eps 变）作为**独立 revision** 存活于各自首见 effective，不再 collapse 回填回锚；min-first-seen dedup（同值再见不延迟，改值=新身份新首见）；no-retrograde 基线改键 (natural+digest)。
- **materializer 无需改**：既有 per-(analyst,quarter) sort-by-effective + shift(1) 逻辑直接把修订渲染成正确 PIT 日期的 eps_up/dn 事件。
- **决定性测试**：eps 1.00(3月见)+1.40(7月见) → 2 ledger 行不同 effective；materializer 在 **7 月**（非回锚 3 月）出 eps_up。

## M4（`bc6669f`）

政策边界断言现对**任何带 calendar_policy_id 的 build**（staged/dry-run，非仅 publish）执行——dry-run 证据不能用 stale 常量。

## 有意注记（诚实）

- **current live provider 的 fresh report_rc 无 raw_fetch 戳**（catch-up 时未打）→ floor 退化为 max(report, create) 残留；D3-sealed，下次 bump 重抓带戳修正（GPT Q5 已裁可接受）。
- digest 覆盖当前唯一 materialized 值字段 eps；注释明确"新字段成 feature 时扩此集"。

## 验证

31 report_rc 测试（本轮 +5：late-first-seen floor、stable-not-inflated、staged-policy、restatement-preserved、restatement-materializes-up）+ 341 data_infra + PIT002 clean。5→4 exact-dup-merge 仍绿（digest 键保留同行 dedup）。

**Round-3 结论：B3 完整修（revision-preserving，端到端测试）+ M4。clean for GPT re-review。**
