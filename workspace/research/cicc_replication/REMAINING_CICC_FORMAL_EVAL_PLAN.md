# 剩余中金因子 → 正式评估 全量路线图(2026-06-13)

> 目标:把三本中金手册里**所有可复刻**的剩余因子带进正式评估链路
> (draft → 入目录即 7 域矩阵 → IS 门 → candidate → sealed OOS → approved)。
> 排序按**约束就绪度**(数据/字段/算子),不按因子数——约束才是瓶颈。
> 全部新因子按 universe 方案 Draft-7 走:入 draft 自动 7 域体检;凡其中金真值表已被观察的
> 域,claim 按 `tainted_post_hoc_max_stat` 记账(与 D5 同,无特例)。

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
| **合计** | **~183** | | | 中金可复刻因子全部进入正式评估 |

终态:目录从 208 → ~390;全目录 × 7 域矩阵 ~2,730 单元;中金三本手册里日频可复刻的因子
100% 进入 draft→candidate→approved 链路;高频 68 显式存档不做。
