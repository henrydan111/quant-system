# 剩余中金路线图 Cross-Review 裁决(GPT 5.5 Pro → Rev2)

> 2026-06-13。GPT 总判:CHANGES REQUIRED,6 项 minimum-change。本文逐条裁决;路线图据此升 Rev2。
> 结论:**6 项全部 ACCEPT**(2 项是 brief 自曝盲区被坐实,1 项是未内化的尖锐发现)。零方向分歧,
> 仅 1 处程度微调(rebuild 合并)。

| # | GPT 发现 | 裁决 | Rev2 动作 |
|---|---|---|---|
| 1 | handbook 级多重检验:per-(factor,universe) 台账抓不住"复刻 N 个、过 M 个 = 手册有 M 个 alpha"的 garden-of-forking-paths;且"可复刻"本身是隐性筛选器 | **ACCEPT(本轮最强,brief §4.1 自曝)** | 新 §9:`CICCHandbookReplicationCohort` manifest(冻结全部手册因子+排除原因+tier+truth label window+OOS eligibility)+ cohort 级报告(denominator/family error/OOS attempts);"复刻通过率"任何陈述必须带分母;sealed OOS 不能无限替补 |
| 1b | **真值表已泄漏 sealed OOS 标签**:D5 用 2010-2022×3域 truth table 做 parity → 2021-2022 表现已被观察 → 再把 2021-2026 当 sealed OOS 不干净 | **ACCEPT(critical,我未充分内化)** | 每个 truth table 记 `label_window_end`;中金复刻因子 sealed OOS 起点 = `max(system_oos_start, truth_label_end + horizon + embargo)`;价量动量(图表5/7/8/9 已转录到 2022.07)→ 其 OOS 起点 2022-07+embargo,可用窗缩到 ~3.5y |
| 2 | P-OP 算子门太弱:PIT-lint+串锁证明无 lookahead/精确串,但不证明"中金公式正确";错算子静默产出看似对的 alpha(3 个失败场景:OLS off-by-one、影线复权错位、振幅 rank 截面vs时序混淆) | **ACCEPT(brief §4.2 自曝)** | 新 §10A:`OperatorCertification`(golden panel/property test/慢速参考实现对拍/truth parity/对齐+PIT 测试);未认证算子的因子只能 dev evidence(status_power=none),**阻断 formal IS gate**;算子版本变→下游 definition_hash 失效重算 |
| 3 | 排序:不要用旧 univ_all 门做 status-bearing interim(制造 observed-domain taint+污染 lifecycle+算子 de-risk 不该靠 label);用 D-COMP/D4a(无新算子)做 P-GATE canary,E1 等 P-OP 认证 | **ACCEPT** | §6 执行顺序重写:D-COMP+D4a 作 P-GATE 首批 canary;E1 在 P-OP 认证后进门;算子 de-risk 靠 formula oracle/truth parity 不靠 label;**撤回"E1 小批走旧门"选项** |
| 4 | D6 重建一致预期是 derived methodology 非 vendor consensus;重建规则(财年滚动/stale 剔除/券商去重/股本回溯/min-analyst 覆盖)决定因子值;level corr +0.997 必要不充分(因子靠横截面排序与变化,非水平) | **ACCEPT** | §10B:`DerivedConsensusCertification`(method hash+财年/stale/去重/股本/覆盖策略+rank/decile/coverage/delay 敏感性);D6 因子标 `replication_tier=reconstructed_consensus_proxy`;EEChange 财年映射错配失败场景记录 |
| 5 | "~180 可复刻/100% 进 approved"口径过满:多数 truth table 待转录(未认证 exact)、价量/资金流/筹码/北向只能 proxy、北向同族 OOS 已花+2024-08 断点不能进 approved(与"100%"自相矛盾) | **ACCEPT(修内部矛盾)** | §7 重写:"~183 formalization candidates" 按 5 档 `replication_tier`(exact_certified/formula_equivalent_pending/proxy_approx/derived_methodology_proxy/not_replicable);删除"100% 进 approved 链路";OOS 已花/制度断点族单列 evidence/candidate ceiling |
| 6 | 其他:6.1 D4 §3↔§8 文本冲突;6.2 三 rebuild 不该合成不可拆 publish;6.3 D7 PIT 成本低估(持仓三套时间/回填/薄窗);6.4 缺字段覆盖 gate(分析师只覆盖研报股→univ_all 实为 covered-subset);6.5 truth 转录无 QA | **ACCEPT 全部** | 见下 |

## §6 子项裁决

- **6.1**(D4 文本冲突):**ACCEPT**,§3 改为明确 D4a(q0-q4 已存→仅注册)/ D4b(q5-q7 缺→cashflow SLOT_DEPTH rebuild)拆分,与 §8 一致。
- **6.2**(rebuild 合并):**ACCEPT 并修正我的过度优化**——改为"同一 release train 共享一次 final publish,但每 dataset 独立 materializer/parity log/PIT canary/rollback tag";不把未认证 D6 + 新端点 D7 塞进不可拆发布。我原"合并成一次构建"是为省 Windows copytree 时间过度优化了,撤回。
- **6.3**(D7 PIT 成本):**ACCEPT**,D7 重定性为 data-PIT-certification project,排最后 + 默认 droppable;持仓/股东/薪酬类的 报告期/公告期/入库期三时间 + 回填/修订 + 薄 effective window 单独认证。
- **6.4**(覆盖 gate):**ACCEPT**,把 §3.9 有效窗治理推广为通用 `availability_audit`(valid_value_ratio_by_year/effective_universe_size_p10/missingness_corr_with_size+liquidity/stale_ratio/first_usable_date/structural_break_dates);不满足覆盖地板的域只能 evidence-only。这正确推广了北向 2024-08 断点为通用规则。
- **6.5**(truth QA):**ACCEPT**,truth table 转录加 `truth_table_manifest`(chart_id/source_page/reviewed_by/numeric_checksum/units/domain_mapping);无 QA 的因子不能标 exact_certified。

## 无程度分歧

本轮没有"方向对但程度过"的争议(不像 universe review 的 Bonferroni/airtight 两处)。唯一我主动修正的是自己的 rebuild-合并建议(6.2),GPT 更谨慎,采纳其版本。

## Rev2 后的执行顺序(GPT 建议 + 采纳)

```
1. 冻结 CICC manifest + truth-table label_end/OOS taint + replication tier。
2. P-GATE/F4:实装域门 + 导入已有 1,449 行证据 + dashboard 域维度可见。
3. D-COMP + D4a(无新算子/低数据风险)作 P-GATE 首批 canary。
4. P-OP OperatorCertification harness(不跑 status-bearing factor gate)。
5. E1a 算子敏感小批 truth-parity dry-run(status_power=none)。
6. P-CAL 可用后,E1a-h 分批进正式 IS。
7. D6(DerivedConsensusCertification)、D7(data-PIT-cert)作独立认证项,最后进门。
```

**一句话**:数据工程拓扑基本正确,但"统计 cohort 治理"+"算子/方法学认证"未达批量正式评估强度。
Rev2 补齐 6 项后,适合从"工程准备"转入"分批受控正式评估";仍不批准一次性大规模灌入
draft→candidate→sealed OOS。
