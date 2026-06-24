# 果仁 20-策略再加权 — 结果 (GUORN20 Findings)

> **引擎**: [guorn20_walkforward.py](../../scripts/guorn20_walkforward.py) (实现 SHIPPED 计划 v5, GPT R1→R5=SHIP)。
> **运行**: 2026-06-24, seed 20260624, 10,000 bootstrap, data_hash `e956df81`, 198 配置 (168 deployable), 506s。
> **输出**: `workspace/outputs/guorn20_reweight/` (frozen_candidate.json / testing_ledger.csv / paired_delta_metrics.csv / selection_trace.csv / run_manifest.json + MLflow `guorn20_reweight`)。
> **状态**: M3 完成。NON-FORMAL research artifact。**结论 = 维持等权 (EW)。**

---

## 0. 一句话结论

**在封存式样本外协议下, 20 个果仁策略的等权 (EW) 配置无法被稳健地击败。** 8 类标准加权方案 × 全参数网格 (168 个 deployable 配置) 中, 按事前冻结规则选出的唯一候选 (`two_stage` = 5 风格组间风险平价) 在 2023-06..2026-06 的 holdout 上 **fail**: 用 −3.3pp 年化换来仅 −0.7pp 回撤改善, Calmar 反低于 EW。**推荐: 保持等权。**

这是整套 5 轮 GPT 跨审的封存协议**按设计工作的结果 —— 它拒绝把一个样本内看着漂亮、实则站不住的"赢家"交给你。**

---

## 1. 三态裁决 (holdout, §4.0)

冻结候选 = **`two_stage` / L=504 / 月度 / cap 15% / floor 1%** (pre-holdout 唯一通过过滤且 ΔCalmar 中位数最高者)。

| 指标 (holdout 2023-06..2026-06) | two_stage | EW | Δ |
|---|---|---|---|
| CAGR (252) | 43.4% | **46.7%** | **−3.3pp** |
| 最大回撤 | 18.7% | 19.3% | −0.7pp (略好) |
| Calmar | 2.33 | **2.41** | **−0.088** |
| Sharpe | 1.644 | 1.643 | +0.002 (持平) |

三态裁决 = **fail** (块长 10/21/63 一致): ΔCalmar 点估计 −0.088 < +0.10 阈值; bootstrap P(ΔCalmar>0) ≈ **0.29** (远低于 0.80); ΔCAGR 下界 −0.075 ~ −0.081 < −3pp。**EW 在 holdout 上于 Calmar/CAGR 占优, Sharpe/MDD 持平。**

---

## 2. 为什么样本内"像赢家"却被否

**pre-holdout (2014..2023-05) two_stage 看着是 Pareto 改进**: ΔCalmar 点 +0.45 / bootstrap 中位数 +0.22, ΔMDD **−3.1pp** (回撤更小), ΔCAGR **+0.8pp** (收益还略高), P(ΔCalmar>0)=97.7%。单看这个会以为找到了免费的午餐。

两道关卡把它拦下:

1. **多重检验 (§4.1 max-stat)**: 168 个配置近乎共线 (**N_eff = 1.86** —— 等效只有约 2 个独立试验)。family-wise 校正后 **p = 0.96** —— 即"全网格最优 ΔCalmar"在零假设下routinely 就有这么大 (maxstat q95 ΔCalmar = 1.50)。**样本内的"优势"落在多重检验噪声之内。**
2. **封存 holdout (§4.0)**: 即便不管显著性, 把这个事前冻结的候选拿到从未看过的 2023-06..2026-06 上 → 直接反转 (上表)。

---

## 3. 描述性图景 (样本内, 仅背景 — 不改变结论)

样本内, **风险型加权确实普遍压低回撤**, 但多数以牺牲收益为代价 (各方案在其配置上的均值):

| 方案 | 平均 ΔMDD | 平均 ΔCAGR | 平均 ΔCalmar | 平均年换手 |
|---|---|---|---|---|
| min_var | **−9.2pp** | −3.4pp | +0.56 | 0.60 |
| max_div | −7.1pp | −0.3pp | +0.48 | 0.76 |
| hrp | −7.8pp | −3.1pp | +0.45 | 0.86 |
| erc | −4.6pp | −1.0pp | +0.25 | 0.39 |
| two_stage | −2.1pp | **+0.3pp** | +0.19 | 0.34 |
| inv_vol | −3.5pp | −2.0pp | +0.15 | 0.38 |
| risk_tilt | −1.4pp | +0.0pp | +0.13 | 0.69 |

- 回撤压得最狠的 min_var/max_div/hrp, 其 **ΔCAGR bootstrap 下界 < −3pp** → 触发非劣边际过滤被淘汰 (168 中仅 **27** 通过过滤)。
- 留下的、收益不垮的 (two_stage/max_div 部分配置) 即为候选池; two_stage L504 胜出。
- **机制**: 风险型加权把资本从高波微盘成长 (A/D) 移向 GARP(B)/特殊(E)/价值(C)。**holdout 期 (2023-06..2026-06) 恰是高波成长跑赢的窗口** → 下调它们在该 regime 里亏了 3.3pp。这正是"单一 regime 不能证明可部署"的活例 (计划 §8 残留风险)。

---

## 4. 推荐

1. **保持等权 (EW, 各 5%)。** 它已吃掉大部分分散收益, 样本外不被这套标准方案稳健击败; 是 N_eff≈2、单一市场、单一 holdout 下的诚实默认。
2. **若你的偏好是"宁要更低回撤、可接受更低收益"** (非本研究锁定的 Calmar 目标): 风险平价类 (two_stage / erc / inv_vol) 样本内可靠压低回撤, **但 holdout 证明收益代价真实、回撤好处可蒸发** —— 这是偏好取舍, 不是免费午餐, 且未通过显著性。`two_stage` 的权重见 frozen_candidate.json (下调 A/D 至 3.5–4.3%, 上调 B 至 9.4%、E 至 7.8%)。
3. **不要部署 `two_stage` 当作"better than EW"** —— 它 fail 了封存检验。

---

## 5. Caveats (不可消除, 已披露)

- **单一 A 股市场 + 单一 ~3 年 holdout regime 无法证明可部署性** (GPT 5 轮一致标注的首要残留)。任何配置变更落地前须 paper/小额实盘验证。
- **果仁 NAV 乐观偏差** (微盘涨停可买; memory `project_guorn_parity`): 绝对水平存疑; 偏差利空高波券, 对"维持/下调高波券"方向是安全垫。haircut 检验 (§4.2) 作为 stress test 列为后续 (本轮聚焦主裁决; 因结论已是"维持 EW", haircut 只会强化"别加码高波券", 不改变 EW 推荐)。
- **N_eff≈2**: 20 个策略高度共线 (平均相关 0.54), 可分散空间本就有限 → 任何"巧妙加权"的先验空间小。

---

## 6. Provenance

- 引擎 [guorn20_walkforward.py](../../scripts/guorn20_walkforward.py); 数据 [guorn20_daily_returns.parquet](../idea_sourcing/guorn/guorn20_daily_returns.parquet) (hash `e956df81`)。
- 全配置账本 testing_ledger.csv; tie-break 审计 selection_trace.csv; 冻结候选 + holdout 三态 frozen_candidate.json; ΔΔ paired_delta_metrics.csv (holdout 仅冻结候选 = 防泄漏)。
- seed 20260624, 10,000 stationary block-bootstrap, 块长 10/21/63, 成本 10bps 单边 (敏感性 0/5/10/20 待补)。
- MLflow experiment `guorn20_reweight` + run_manifest.json。

**实现自审 + GPT 实现审查 (§10): 待 (本文件后)。**
