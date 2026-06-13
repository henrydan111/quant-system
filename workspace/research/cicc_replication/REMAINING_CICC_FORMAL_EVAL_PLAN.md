# 剩余中金因子 → 正式评估 全量路线图(Rev2,2026-06-13)

> 目标:把三本中金手册里**所有可复刻**的剩余因子带进正式评估链路
> (draft → 入目录即 7 域矩阵 → IS 门 → candidate → sealed OOS → approved)。
> 排序按**约束就绪度**(数据/字段/算子),不按因子数——约束才是瓶颈。
> 全部新因子按 universe 方案 Draft-7 走:入 draft 自动 7 域体检;凡其中金真值表已被观察的
> 域,claim 按 `tainted_post_hoc_max_stat` 记账(与 D5 同,无特例)。
>
> **Rev2(GPT 5.5 Pro cross-review,6 项 minimum-change 全 ACCEPT,裁决见
> [REMAINING_PLAN_cross_review_response.md](REMAINING_PLAN_cross_review_response.md))**:新增 §9
> handbook-cohort 多重检验治理 + 真值表 OOS 隔离;§10 算子/重建一致预期认证门;§7 口径降为
> 分层 replication_tier(删除"100% 进 approved"过满表述);执行顺序改为 D-COMP/D4a 作 P-GATE
> canary、E1 待算子认证。**当前状态:工程准备阶段,未批准一次性大规模灌入 OOS。**

## 0. 现状基线

| 已完成 | |
|---|---|
| 基本面 exact 档忠实复刻 + 注册 | 18(D5,已入 7 域矩阵) |
| 等价目录因子已覆盖评估 | ~35 |
| 全目录 208 × 7 域矩阵 | 跑完(Layer-2 收尾中) |
| 因子×域 claim/taint 基础设施(F1) | 已落地 |

**剩余可复刻 ≈ 180**(价量 ~145 + 基本面 ~35);高频 68 不可复刻(无分钟/逐笔数据)。

## 1. 三个横向前置(挡住批量正式评估的公共依赖)

这三项不先做,后面所有 wave 的"正式评估"都只能用旧 univ_all 原 bar 跑,享受不到 Draft-7 的域分层治理。

| 前置 | 内容 | 阻挡谁 |
|---|---|---|
| **P-OP 算子库** | 中金多个因子需要新算子:振幅条件滚动和(mmt_range)、路径调整(mmt_route)、信息离散度(mmt_discrete)、截面/时序 rank 动量(mmt_sec_rank/time_rank)、上下影线族(vol_*shadow,威廉影线)、滚动回归残差(OCFA 产能、LPNP 提纯)。先建算子 + PIT 安全测试 + 表达式串锁 | 价量 ~60、基本面 OCFA/LPNP |
| **P-GATE 域门实装(F3)** | 当前 factor_lifecycle 门仍是 univ_all 原 bar;Draft-7 的声明域裁决 + 分层 max-stat 门 + 薄域硬地板 + 时间轴地板尚未接入门。批量正式评估前实装(MVP 顺序见方案 §3.6b) | 全部 wave 的 candidate 裁决 |
| **P-CAL max-stat 校准** | block permutation 经验零分布 + window-matched null(§3.3 校准合同);置换引擎稳定前,tainted/post-hoc claim 用保守上界或 reviewer-block | 所有 tainted claim 的裁决 |

## 2. 数据就绪 wave(零新数据,可立即开工)

### Wave E1 — 价量手册主体(~135,仅需日频 OHLCV + 已批准 cyq_perf/hk_hold/moneyflow/margin)

按类分批注册 → 入目录即 7 域矩阵 → IS 门。每批一个 research_family(防 idea-family 污染串味)。

| 批 | 类(剩余数) | 字段 | 算子需求 | 真值对照 |
|---|---|---|---|---|
| E1a | 动量反转 ~17 | OHLCV | mmt_range/route/discrete/sec_rank/time_rank(P-OP) | 图表5/7/8/9 已转录 4 域 |
| E1b | 波动率 39 | OHLCV | 上下影线/威廉影线族(P-OP) | 图表17/19-21 待转录 |
| E1c | 流动性 21 | OHLCV+amount | 多数现成(liq_*) | 图表29/31-33 待转录 |
| E1d | 量价相关 8 | OHLCV+vol | corr 算子(现成) | 图表 待转录 |
| E1e | 筹码 9 | cyq_perf(approved) | 现成 | 待转录 |
| E1f | 资金流 32 | moneyflow(approved) | 主买卖/大单比族 | 待转录 |
| E1g | 北向 9 | hk_hold(approved) | 北向持股变动族 | 待转录(同族 OOS 已花,见下) |
| E1h | 融资融券 ~10 | margin_detail balance/buy(approved) | 融资余额/买入族 | 待转录;偿还字段隔离的 2 个跳过 |

**E1 已知约束**:北向族(E1g)我方 north_* 同族 2021-2026 OOS 已花 + 2024-08 披露制度变化 → **E1g 因子可入目录评估,但同族不再开新 sealed OOS**(只能停在 candidate / evidence)。

### Wave D-COMP — 基本面复合 + 未建 approx(~13,零新数据)

QQC/Growth/Profit/Safe/Acc 复合(成分已在目录)+ QPT(业绩趋势分层打分)+ NP_SD/OP_SD(稳健加速度)。复合有效窗=成分交集(§3.9)。

## 3. 一轮字段工程解锁的 wave

### Wave D4 — 基本面 D 后缀差分(12,blocked-slots)

CFOAD/ROAD/ROED/ROICD/CCRD/CURD/DAD/DTED/QRD/CSRD/APRD/OCF 同比。
**解锁需求**:一次字段注册——balancesheet 加 q1 槽 + cashflow 加 q4-q7 + income operate_profit/n_income_attr_p 加 q1-q3(走标准批准流程:approval YAML + parity 0-mismatch + append-only log)。注册后 12 个 D 因子 + 修复先前否决的 ATD/INVTD/RATD 近似。

### Wave D6 — 分析师一致预期水平值(~9 + 2,report_rc PIT 2010+ 已验证)

**关键更正(2026-06-13)**:report_rc `report_date+1` 自 2010 即真 PIT(已验证),分析师类是 **blocked-FIELDS 非 blocked-window**。
**解锁需求**:把一致预期**水平值**字段(FY1 一致预期盈利/EPS/营收、预期离散度)从 report_rc 明细按 report_date+1 重建 → 物化进 PIT ledger + provider + 注册(验证脚本里已重建过 E/P,证明可做)。注册后 CAFR/EEP/FORE_Earning/FORE_EPS/FORE_OP/EEChange_1M/3M/EOPChange_1M/3M 可复刻 **2010-2026 全历史**;EINS_75D/RPP_75D 用现有 n_active_analysts/事件计数即可。
**⚠ 边界**:eps_diffusion(breadth/二阶差分)仍受 2026-06-15 restatement 金丝雀硬门约束,水平层 PIT 不解除该门。

## 4. 需新 Tushare 端点的 wave(先读接口文档 §6.1,部分可能不可行)

### Wave D7 — 新端点 blocked-data(~12)

| 因子 | 需要的数据 | 端点(待读文档确认) |
|---|---|---|
| RatingChange_1M/3M、TargetReturn | 评级/目标价 | report_rc 原始 schema 是否含(先核,可能零成本) |
| TOE/TOE_Z/OT_Z/PTCF_Z | 应交税费、缴税现金流 | 现有 balancesheet/cashflow 是否含科目(先核) |
| Comp_opt、TOP_MANA_INCOME | 高管薪酬/持股/处罚/股权激励 | 新端点(stk_rewards 等) |
| IHN_diff、Ln_IH | 机构持仓个数 | 新端点 |
| LHRD | 十大股东明细 | 新端点 |
| EV2EBITDA | EBITDA | income.ebitda 单季 100% 空——需替代源或放弃 |

每个端点严格走:读官方文档(字段/cadence/PIT)→ 入 data_dictionary → ledger → provider → 字段注册 → 因子复刻。先做零成本核查(report_rc 评级列、报表税费科目),再决定新端点优先级。

## 5. 不在计划内

**高频手册 68**:依赖分钟K(2013+)/3s 快照/逐笔(2018+),我方仅日频。需独立的分钟/逐笔数据工程大项目(新数据源+存储+PIT 对齐)才能复刻——**不纳入本路线图,存档待未来数据决策**。

## 6. 执行顺序(依赖拓扑)

```
P-OP 算子库 ─┐
            ├─→ Wave E1(价量 ~135,分 8 批)──┐
P-GATE 域门 ─┤                               ├─→ 全目录扩到 ~378 因子
P-CAL 校准  ─┘                               │   × 7 域矩阵增量补跑
                                             │
Wave D-COMP(复合+approx ~13)───────────────┤
Wave D4(字段注册 → 12 D 后缀)──────────────┤
Wave D6(一致预期水平值物化 → ~11 分析师)────┤
Wave D7(新端点核查 → ~12,部分可能放弃)─────┘
                                             ↓
              逐 wave:draft → 7 域矩阵 → IS 门(域分层) → candidate
                       → 稀疏 sealed OOS(北向/筹码同族不再开)→ approved
```

**建议起点**:P-OP + P-GATE 并行起步(P-OP 是价量复刻的硬前置,P-GATE 是所有正式裁决的硬前置);
其中 P-GATE 之前先把当前矩阵的 1,449 行证据导入注册表 + dashboard 域维度(F4)——
让已有的 208×7 证据先可见可用,再扩量。

## 7. 规模与里程碑

| Wave | 新因子 | 数据前置 | 算子前置 | 里程碑 |
|---|---|---|---|---|
| E1a-h | ~135 | 无(全已批准) | P-OP | 价量手册忠实复刻完成 |
| D-COMP | ~13 | 无 | 无 | 基本面复合齐 |
| D4 | 12 | 字段注册一轮 | 无 | 基本面 D 后缀齐 |
| D6 | ~11 | 一致预期水平值物化 | 无 | 分析师类 2010+ 复刻 |
| D7 | ~12 | 新端点(部分) | 无 | 治理/股东/税费类(能做的) |
| **合计** | **~183 formalization candidates** | | | 见 §7 分层口径(非"全部 approved") |

终态:目录从 208 → ~390;全目录 × 7 域矩阵 ~2,730 单元。**口径(Rev2 更正,删除"100%
approved"过满表述)**:~183 formalization candidates 按 `replication_tier` 分层——
`exact_certified`(公式+字段+窗口+truth rank/IC 均过阈)/ `formula_equivalent_pending`(公式可写,
truth 待转录验)/ `proxy_approx`(字段或构造与中金不完全一致)/ `derived_methodology_proxy`(D6 自建
一致预期)/ `not_replicable`(高频/缺数据)。**只有 exact_certified 计入"忠实复刻"**;北向/筹码等
OOS 已花或制度断点(2024-08)族**封顶在 evidence/candidate,不进 approved 链路**;高频 68 存档不做。

## 8. 数据工作流兼容性核验(2026-06-13,逐 bin 实测)

核验路径:parquet → PIT ledger → qlib provider bins → field_status 注册 → 因子 `$field`。
**每个 wave 的"解锁条件"必须落在这条管线的某个具体操作上,实测如下。**

### 两层解锁成本(原路线图混淆了,现明确区分)

- **(A) bin 已物化,仅需注册**:field_status.yaml + approval YAML + parity 0-mismatch + append-only log。**无 provider rebuild**。
- **(B) bin 未物化,需物化**:扩 pit_backend normalizer/materializer → ledger rebuild → `build_qlib_backend --mode update --datasets X --stage full` → 注册。

### 逐 wave 实测结论

| Wave | 实测 | 成本层 |
|---|---|---|
| **E1 价量主体** | **全部就绪**:动量/波动/流动/相关用 `$open/$high/$low/$close/$vol/$amount/$adj_factor/$up_limit/$down_limit`(servable);筹码=`$cyq_perf__cost_{5,15,50,85,95}pct / __winner_rate / __weight_avg / __his_high/low`(实测 bin 存在,namespaced);资金流=`$buy_{elg,lg,md,sm}_amount/_vol / $net_mf_amount`(存在);北向=`$ratio`(hk_hold,存在);融资融券=`$rzye/$rqye`(存在)。**全部 approved(唯一非 approved 是 margin_detail_repayment 隔离)**。→ **零数据/零 rebuild,只需 P-OP 算子 + 写表达式** | 仅算子 |
| **D-COMP 复合** | 成分皆 servable;`add_composites` 现成 | 零数据 |
| **D4a D 后缀差分(~10)** | **实测 bins 已存在**:`total_assets_q1/q3`、`total_liab_q1`、`inventories_q1`、`money_cap_q1`、`operate_profit_sq_q1/q3`、`n_income_attr_p_sq_q1/q2`、`n_cashflow_act_sq_q0..q4` 全部存在。CFOAD/ROAD/ROED/CCRD/CURD/DAD/DTED/QRD/CSRD/APRD 的当季-上季 TTM 差分**只需 q0-q4 → 已够 → 仅注册**(原计划误判为需 rebuild) | **(A) 仅注册** |
| **D4b OCF 同比族(2)** | OCF_YOY/OCF_Q_YOY 需 TTM vs 去年 TTM = cashflow q0-3 vs **q4-7**;实测 `n_cashflow_act_sq` 只到 **q4**,q5/q6/q7 缺 → 需加深 SLOT_DEPTH 重物化 cashflow | **(B) rebuild** |
| **D6 分析师水平值** | report_rc 当前 `_materialize_report_rc_consensus` 只产 4 个事件流原语 bin;一致预期**水平值**(FY1 盈利/EPS/营收/离散度)需**扩 materializer**(按 report_date+1 重建,验证脚本已证可重建)→ ledger+provider rebuild → 注册。report_rc PIT 2010+ 已验证,路径标准 | **(B) rebuild** |
| **D7 新端点** | 标准 fetch→parquet→ledger→provider→register。**先零成本核查**:report_rc 原始 parquet 是否已含评级/目标价列、报表是否已含应交税费/缴税科目(若含=仅 materializer+注册,免 fetch);EBITDA 单季 100% 空=替代源或放弃;高管薪酬/机构持仓/十大股东=真新端点(读文档 §6.1) | (A) 或 (B) 视核查 |

### 兼容性总结

**路线图与现行数据工作流完全兼容,且比初稿更省**:E1(最大块,~135)是纯算子+表达式工作,
零数据零 rebuild;D4 的大部分(~10 个 D 后缀)从"需 rebuild"更正为"仅注册"(bin 实测已存在)。
真正触发 provider rebuild 的只有三处:D4b(cashflow 加深到 q7)、D6(report_rc materializer 扩
一致预期水平值)、D7 的真新端点——全部落在既有的 `build_qlib_backend --mode update --datasets`
标准路径上,无需新机制。**Rev2 更正(GPT §6.2)**:三处共享同一 release train + 一次 final publish
可以,但**每 dataset 独立 materializer / parity log / PIT canary / rollback tag**——不把未认证的
D6 重建一致预期和 D7 新端点塞进同一个**不可拆**的 provider 发布(否则 D6 方法错会连带污染
cashflow q7 + D7,调试成本更高)。原"合并成一次构建"的提法过度优化 Windows copytree 成本,撤回。

## 9. Handbook-cohort 多重检验治理(Rev2 新增,GPT §1/§1b)

per-(factor, universe) 台账抓不住"批量复刻整本手册"的 garden-of-forking-paths:180 个候选即使全噪声,
单因子 5% 假阳性 → 期望 ~9 个假过 OOS;"复刻 N 过 M = 手册有 M 个 alpha"是无效叙述。且"可复刻"本身
是隐性筛选器(排高频/弃 D7/价量近似混入数据可得性+公式清晰度)。

**9.1 冻结 cohort manifest(任何批量注册前)**:
```yaml
CICCHandbookReplicationCohort:
  source_cohort_id: cicc_{fundamental|price_volume|high_freq}_handbook_v1
  manifest_sha:
  factor_rows:
    - factor_name_original / handbook_id / chart_id / formula_source
      replication_tier_planned: exact|formula_equivalent|proxy_approx|derived_methodology|not_replicable
      exclusion_reason / required_fields / required_operators
      truth_table_domains_available / truth_table_label_end
      primary_claim_universe / oos_eligibility
```

**9.2 两层多重检验**:`FactorDomainClaim` 仍按单因子×域裁决;新增 `CohortClaim` 负责手册级有效性
报告——任何"复刻通过率"陈述**必须带分母 + family error/FDR + OOS attempts**;**sealed OOS 不能无限
替补**(失败一个挑下一个 = 同一 cohort 反复开奖,计入 family);"从 180 里挑 5 做组合"必须生成
cohort-level selection claim(对接方案 §3.4 FactorSetClaim),不能只引 5 个单因子 approved。

**9.3 真值表 OOS 隔离(critical)**:中金 truth table 已展示 2010-2022 表现 → 我方做 parity 即**已观察**
该窗口表现。每张 truth table 记 `label_window_end`;中金复刻因子 sealed OOS 起点 =
`max(system_oos_start, truth_label_end + horizon + embargo)`。**实例**:价量动量(图表5/7/8/9)
已转录到 2022.07 → 其 sealed OOS 起点 ≈ 2022-07 + embargo,可用窗缩到 ~3.5y(2022-07..2026-02);
未转录真值表的因子未被观察,但一旦为 exact-cert 做 parity 即触发同样隔离 → 转录 vs 保全 OOS 窗
是显式权衡。基本面 D5 的 18 因子已观察 2010-2022×3域 → 其域 claim 已是 post-hoc(与既有 taint 一致)。

## 10. 算子与重建一致预期认证门(Rev2 新增,GPT §2/§4)

PIT-safe 只证无未来数据,**不证中金公式正确**;错算子静默产出"看似对实则错"的 alpha 并骗过 IS。

**10A `OperatorCertification`(P-OP 阻断门)**:未认证算子的因子只能 dev evidence(status_power=none),
**不得进 formal IS gate**:
```yaml
OperatorCertification:
  operator_id / spec_source / formula_text / reference_impl_hash / vectorized_impl_hash
  alignment_policy: {window_closed: left|right, min_periods, lag, adjustment_policy}
  tests: {golden_panel, property_based, reference_vs_vectorized_random, truth_table_parity, PIT_alignment}
  status: experimental|certified|blocked
```
最低测试(按算子类型):振幅条件和(条件恒真退化为 rolling sum/恒假为0/rank方向+tie+NaN+停牌+涨跌停 golden)、
路径动量(同端点更曲折惩罚方向、单调路径近普通动量)、信息离散度(集中 vs 平滑排序符定义、尺度不变 rank)、
影线族(**raw/adjusted OHLC 一致性 + 除权日 canary + high≥max(open,close) 异常**)、截面/时序 rank
(**两维不可混** + mask/停牌/缺失固定)、滚动 OLS 残差(y=a+bx 残差≈0、常数x→NaN、**窗口边界+lag toy oracle**)。
每算子必有"慢速参考实现 vs 生产 vectorized"随机面板对拍;算子版本变 → 下游 definition_hash 失效重算。

**10B `DerivedConsensusCertification`(D6 专属)**:重建一致预期是 derived methodology 非 vendor consensus,
重建规则决定因子值(财年滚动/stale 剔除/券商同日去重/股本回溯/min-analyst 覆盖/report_date+1 是否覆盖
盘后发布)。level corr +0.997 **必要不充分**(因子靠横截面 rank 与变化,非水平):
```yaml
DerivedConsensusCertification:
  derived_provider_id: report_rc_consensus_recon_v1
  methodology_hash: {fiscal_year_roll, stale_forecast, broker_dedup, same_day_revision,
                     share_adjustment, availability_lag, min_analyst_count}
  validation: {oracle_corr_level, oracle_rank_corr, decile_membership_overlap,
               coverage_by_year_universe, delay_sensitivity_t0_t1_t2, stale_policy_sensitivity}
```
D6 因子标 `replication_tier: reconstructed_consensus_proxy`;失败场景记录:财年映射错配会让 EEChange
在财报季系统性跳变(IS 看着好,实为 fiscal-year bug);保留 stale forecast 会产生"陈旧度"伪因子。

## 11. 通用覆盖/有效域 gate + 真值表转录 QA(Rev2 新增,GPT §6.3-6.5)

**11.1 覆盖 gate(把 §3.9 有效窗推广为字段覆盖)**:分析师只覆盖研报股、北向/融资融券有起始日+制度断点
→ univ_all claim 实为"覆盖子集"。每 factor×universe gate report 增 `availability_audit`:
`valid_value_ratio_by_year / effective_universe_size_p10 / missingness_corr_with_{size,liquidity} /
stale_value_ratio / first_usable_date / structural_break_dates`;不满足覆盖地板的域只能 evidence-only。

**11.2 D7 重定性为 data-PIT-certification project**(排最后 + 默认 droppable):持仓/股东/薪酬类有
报告期/公告期/入库期三套时间 + 回填修订 + 薄 effective window,PIT 风险高于普通财报字段,逐端点独立认证。

**11.3 truth table 转录 QA**:手工转录错 → 错 oracle 变"忠实复刻"门。每张表加 `truth_table_manifest`
(chart_id/source_page/transcribed_by/reviewed_by/numeric_checksum/units/domain_mapping/metric_definition);
无 QA 的因子不得标 `exact_certified`。
