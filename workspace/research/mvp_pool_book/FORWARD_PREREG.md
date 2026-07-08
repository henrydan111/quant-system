# MVP AI re-rank · 前向预注册(FORWARD PRE-REGISTRATION)

**Date:** 2026-07-08 · **Status:** PRE-REGISTERED(前向起跑前锁定;起跑后本文件不可改,改=作废重注册)
**绑定:** [CONTRACTS.md](../trading_agents_design/CONTRACTS.md) C1/C2/C5/C6/C7/C12/C15/C16 ·
config = [rerank_v1.yaml](../../../config/ai_layer/rerank_v1.yaml)(**config_hash `c2aa469d1b0220d9`**)

---

## 1. 实验单元(C6:bounded_overlay 类,独立分账)

- **strategy_id:** `mvp_pool_rerank_v1`
- **模式:** `bounded_overlay_production_candidate`(rank 空间 C7 实例化)——**不是** ai_final_decider_shadow;
  两模式结论永不互通。
- **universe(TUD):** golden_stock_pool(C3 掩码,月度 day-4 激活)。宽基=零 seal 诊断参照腿。

## 2. 三腿定义(全部同一 harness、同一成本口径)

| 腿 | 定义 |
|---|---|
| **AI 账本** | 量化 top-50(floor)→ dossier → quick(lite)digest → deep(pro)维度分 → scorecard final → tilt=0.15·(final−50)/50 → `apply_rank_overlay`(K=25, max_swap≤8, floor=50, 行业≤9, v1 无自动 veto)→ 等权 |
| **量化账本(锚)** | 同一量化复合 top-25 等权(基线:inline-sim 历史 +8.4%/0.46) |
| **池等权** | 当月全池等权 |

调仓:每月 day-4 激活日;决策记录于激活日**开盘前**;成本 0.0016 单边(与基线一致)。

## 3. 判定规则(预注册,不许事后挑)

- **主判据:** 前向 ≥ **6 个自然月**(≥6 次调仓)后,AI 账本相对量化账本的**净成本 Sortino 与最大回撤**均不劣、
  且累计净收益差 > 0 → AI re-rank 有效;续跑至 12 个月确认。
- **证伪线:** 6 个月后 AI 账本累计净收益差 < 0 **且** Sortino 更差 → **AI 降级为解释/风控工具**,
  rerank_v1 作废(计入 C16b 试验台账);不得换 config 立即重试(新 config = 新周期新注册)。
- **中途不看不调:** 前向期间禁止基于已实现收益调整 prompt/权重/上限/模型(M3/C16);
  运维修复(API 换端点等)允许但记入审计日志。

## 4. 不可变项(冻结清单)

`rerank_v1.yaml` 全文(models/weights/tilt_cap/K/max_swap/floor/行业上限)· 两个 prompt 文件 ·
config_hash `c2aa469d1b0220d9` · 判定规则(§3)· 决策日志 append-only(每期:输入快照 hash、
scorecards、overlay audit、最终两本账本)。**改任何一项 = rerank_v2 + 新预注册。**

## 5. 已知缺口(起跑前置,诚实在案)

1. **量化分新鲜度:** provider 冻结于 2026-02-27 → 真前向需解冻主线 **5-C 日更发布**;在此之前只能跑
   "陈旧量化分 + 新鲜文本"的管线演练(= 本次 dry run,`PIPELINE_DRY_RUN_NOT_A_DECISION`),不记入前向战绩。
2. **日度文本任务未挂**(schtasks 待用户授权)——未挂期间人工补跑,4 天回看容错。
3. **Ark 模型 cutoff 未公布**(C2 在案)——与 forward-only 设计一致,无阻塞。
4. v1 无自动 veto(红旗探测器后续版本);行业标签=当前快照(仅护栏)。

## 6. 起跑条件(全部满足才开钟)

**(修订 2026-07-08,前向未起跑故合法;修订原因:查证发现 thaw step 1 已发布,provider 日历至
2026-07-01[policy `frozen_20260701_thaw_step1`, build `thaw_step1_20260703c`]——原条件①"等 5-C"
过严,月度调仓只需月级新鲜度。)**

☐ **数据新鲜度规则:** 决策用因子值 = provider 末日(≤ activation−1);**陈旧度(activation − provider_end)
  ≤ 5 个交易日**,每期记入决策日志;月度 5-B bump 发布覆盖月初即满足(5-C 日更=自动化增强,非硬闸)
☐ 日度文本任务运行中(schtasks 待授权;过渡期人工跑 text_daily_pull.py 并记录)
☐ 本文件 committed 且 hash 引用正确　☐ 首期决策日志目录就绪(workspace/outputs/mvp_forward/)
☐ 实现级 §10 diff-review 通过(text_store/scorecard/overlay/ark_client/runners)

**首个真前向周期 = 2026-08(activation ≈ 2026-08-04 后首个交易日);2026-07 周期决策时点已过,
不可回填(仅可作近真演练,不记战绩)。D3 不变:spent_oos_end 冻结 2026-02-27——解冻延长数据,不延长证据窗。**
