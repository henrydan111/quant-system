# BUILD-0 首个实验 — TC 测量 + 轻构造 PoC(交接说明,自包含)

> **一句话任务:** 在造整个构造栈之前,先**廉价地经验验证方法论的核心前提** —— 量化当前 top-K/等权书的转移系数 TC,再证明**信号比例轻构造(不是 MVO)**能在净收益上打赢 top-K。这是 `STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0`(GPT 已 APPROVE)自己规定的第一个经验任务。IS-only,不花封存 OOS,可逆。

## 0. 先读(必读,别凭记忆)

- [STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0.md](STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0.md) —— 尤其 §1.1(TC 诊断)、§S2(信号构造/α 标定)、§S3(轻构造 vs 优化器 + 4 条件门)、§S5-S6(验证/封存)。
- [DEEP_RESEARCH_ADJUDICATION.md](DEEP_RESEARCH_ADJUDICATION.md) —— Claims 1-5 三票核验的证据(TC 坍缩、1/N 难打败、Hentschel `1/√ρ`)。
- 记忆:`project_strategy_development_methodology`(方法论现状 + APPROVE)、`project_capital_allocation_buildout`(BUILD 计划)、`project_guorn_parity`、`reference_factor_selection_marginal_not_icir`、`feedback_check_concurrent_sessions`。
- 姊妹文档 [../capital_allocation_buildout/STRATEGY_ENHANCEMENT_METHODOLOGY.md](../capital_allocation_buildout/STRATEGY_ENHANCEMENT_METHODOLOGY.md) —— #9 增强方法论(本 PoC 复用它的 harness)。

## 1. 背景(为什么是这个实验)

方法论把过去"因子能验证却造不出可部署策略"诊断为**转移系数(TC)坍缩**:可部署收益来自 **信号选择/可交易性 ≫ 成本/换手 > universe > 权重**(优化器最后且有条件)。但"靠更好的**构造**提升 TC"在本系统里**还只是未测量的先验**,而且平行 果仁 #9 实验已经**证伪了它的一种形式**:MVO 优化器(λ=2…100,pragmatic Ledoit-Wolf Σ)没打赢 naive top-K(Sharpe 0.85–0.91 vs 0.90,MDD 更差)。#9 里**真正起作用的是信号侧**(排除不可交易的快因子把 paper→deploy 差距从 ~26pp 收到 ~1pp),不是权重侧。

**开放问题:** 比 MVO 更轻的构造 —— **信号比例权重(∝ 标定 α,保留 cardinal 信号 vs top-K 的扁平权重)** —— 能不能在净收益上打赢 top-K?这决定要不要投入 BUILD-0 全量构造栈。

## 2. 目标书 & 复用点

- **目标书 = `s3_core`**:#9 会话的"可交易核心"(value+quality+low-vol,top-30,非微盘,快/不可交易因子已排除)。正是方法论说的"可部署 α"书。
- **Harness = [../../scripts/guorn_optimize_09.py](../../scripts/guorn_optimize_09.py)** —— #9 会话("Replication status documentation",已于 2026-07-04 停止)的脚本。**不要改它**;新写 `workspace/scripts/build0_tc_poc.py` **导入/复用**它的函数 + 缓存面板。
  - 组合 `comp` = 各因子定向中性化 z-score 的均值(schedule builder,`guorn_optimize_09.py` 约 285-306 行)。
  - `wmode="signal"`(约 297 行)= **信号比例权重 ∝ (comp − min + eps),归一化** —— 这就是轻构造的核心,**已编码但从没被跑过**。`wmode="equal"` = 等权 top-K(基线,已跑)。
  - `ModelIDivLowVolStrategy(sched, weights_mode="explicit")`(`run_opt` 约 629 行用法)= 用 schedule 里的显式权重跑事件驱动回测。`run()`(313 行)是等权/sqrt_mv 路径。
- **已有缓存**(`workspace/outputs/guorn_parity/optimize09_cache/`):`net_s3_core_sind_k30_is.parquet`(等权 top-K 基线)、`net_s3_core_sind_k30_opt_is.parquet`(MVO,失败)、`sched_s3_core_*.json`、面板 `factor_panel`/`returns.parquet`。
- 指标用 `src/result_analysis/`(CAGR/Sharpe/MDD/Calmar/turnover),别重造。

## 3. 实验(IS-only:2014-2020;**严禁**碰封存 OOS 2021-2026)

**Step 1 — 测 TC。** 对 s3_core 书每个调仓日算截面 **`TC = corr(μ/σ, Δw·σ)`**:
- `μ` = 期望超额收益 α,由 **Grinold `α = IC·σ·z`** 标定(z=comp 的截面 z-score,IC=IS 估计的该组合 rank-IC,σ=下面的 idio-vol);先给出 raw-comp 版和标定版两种。
- `σ` = idio/残差波动估计(trailing 残差 vol,或简单波动代理即可,先粗后精)。
- `Δw` = 主动权重 = 书内权重 − 基准权重(基准取等权-over-eligible 或 CSI300 权重;先用等权-over-eligible)。
- `TC` = 截面 Pearson corr( μ/σ , Δw·σ ) over 持仓+合格名,再对调仓日取均值。
- **对两本书各算一遍**:等权 top-K 书 vs 信号比例书。预期等权 TC 低(丢弃 cardinal 信号),信号比例 TC 更高。

**Step 2 — 跑轻构造变体。** s3_core 用 `wmode="signal"`(信号比例 ∝ 标定 α),`weights_mode="explicit"`,**同 universe/成本/调仓**(0.2%/side、vol_limit 0.10、hold_on_limit_up、Model-I 5d)→ net-of-cost IS。和等权基线比 CAGR/Sharpe/MDD/Calmar/turnover。

**Step 3 — 判决。**
- **前提成立**(信号比例净 Sharpe/收益 > 等权 **且** 实测 TC 更高)→ **放行 BUILD-0**:在 `src/` 建可复用的 combiner + Grinold-α 标定 + `WeightedTargetStrategy` 执行 seam + 轻构造器(长仓/毛敞口盒 + 中性化 + 换手惩罚)。
- **前提不成立**(信号比例不提净收益,像 MVO 一样)→ 可部署杠杆在**信号选择 + universe**,不是权重 → 本尺度上方法论对"构造"的权重过高,调整方向(押 deployable-alpha 选择 + universe,权重当中性)。
- 两种都是诚实、廉价、决定性的结果。**报告 TC 数字 + 净对比 + 判决**。

## 4. 护栏(硬性)

- **IS-only(2014-2020)。绝不** `--window oos` / 花封存 OOS(harness 无 `--i-am-spending-oos` + GPT 设计签核 + 用户 go 会 refuse,§13)—— 保持如此。
- **不改** `guorn_optimize_09.py`;新写 `build0_tc_poc.py` 导入复用。
- 复用面板/回测/指标,别重造(§0 Canonical Function Map)。
- venv:`E:\量化系统\venv\Scripts\python.exe`。长回测用 `run_in_background`。
- 开工先(`feedback_check_concurrent_sessions`):确认 #9 会话仍停止 + 看它最新产出,别重复。
- 实质回测/模型跑 **MLflow logging**(CLAUDE.md §7.6)。
- 走 CLAUDE.md §1 上下文刷新 + 相关 `AGENTS.md`。

## 5. 交付

- `workspace/scripts/build0_tc_poc.py`(TC 测量 + 信号比例变体 + 对比,可复跑)。
- `workspace/research/strategy_development_methodology/BUILD0_TC_POC_FINDINGS.md`(TC 数字[等权 vs 信号比例]+ 净指标对比表 + 判决 + 下一步)。
- 更新记忆 `project_strategy_development_methodology`(PoC 结果 + BUILD-0 放行/调整)。
