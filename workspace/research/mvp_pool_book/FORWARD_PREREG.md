# MVP AI re-rank · 前向预注册(FORWARD PRE-REGISTRATION)

**Date:** 2026-07-08(v2 修订同日;前向未起跑,修订合法)· **Status:** PRE-REGISTERED(起跑后本文件不可改,改=作废重注册)
**绑定:** [CONTRACTS.md](../trading_agents_design/CONTRACTS.md) C1/C2/C5/C6/C7/C12/C15/C16 ·
config = [rerank_v2.yaml](../../../config/ai_layer/rerank_v2.yaml)

config_hash_v2: `5c8a462e1c5500b3`

> **v1→v2 修订记录(2026-07-08,起跑前):** GPT 实现级 §10 review #1(REVISE)裁定 7 Blocker,
> 其中 B1(payload 渲染+证据落地)、B3(tilt 改 cohort 均值中心化 + 覆盖率闸门)、M4(组合上限)
> 直接改变 config/prompt 内容 → 按 §4 规则升版 `mvp_pool_rerank_v1` → **`mvp_pool_rerank_v2`**,
> 旧 hash `c2aa469d1b0220d9` 作废(v1 从未产生前向决策,无战绩可污染)。
> **review #2(REVISE)追加修订(2026-07-08,仍在起跑前):** R2-Blocker-1 罚分证据强制(score_v2
> penalty schema 带 evidence_spans,无逐字证据的罚分只入 risk_flags 不入 final)→ hash 由
> `12724e20f1f78b55` 更新为 `5c8a462e1c5500b3`;决策产出改为 **attempt 台账制**(见 §4)。

---

## 1. 实验单元(C6:bounded_overlay 类,独立分账)

- **strategy_id:** `mvp_pool_rerank_v2`
- **模式:** `bounded_overlay_production_candidate`(rank 空间 C7 实例化)——**不是** ai_final_decider_shadow;
  两模式结论永不互通。
- **universe(TUD):** golden_stock_pool(C3 掩码,月度 day-4 激活)。宽基=零 seal 诊断参照腿。

## 2. 三腿定义(全部同一 harness、同一成本口径)

| 腿 | 定义 |
|---|---|
| **AI 账本** | 量化 top-50(floor)→ dossier → quick(lite)digest(JSON payload 渲染,C15/B1)→ deep(pro)维度分 → scorecard final(证据须逐字落地于 **dossier 原文**——digest 概括句不算证据,B1+)→ **tilt=0.15·(final−scored_cycle_mean)/50(B3 cohort 中心化)** → 覆盖率闸门(scored<80% → 本期 overlay 停用,回退纯量化账本)→ `apply_rank_overlay`(K=25, max_swap≤8, floor=50, 行业≤9, v2 无自动 veto)→ 等权 |
| **量化账本(锚)** | 同一量化复合 top-25 等权(基线:inline-sim 历史 +8.4%/0.46) |
| **池等权** | 当月全池等权 |

调仓:每月 day-4 激活日;决策记录于激活日**开盘前**(runner 硬闸 09:25);成本 0.0016 单边(与基线一致)。
组合上限(M4,记录并断言):单票权重 ≤0.04 · AI 单边换手 ≤0.32 · AI 主动权重 L1 ≤0.64 · 单行业 ≤0.36。

## 3. 判定规则(预注册,不许事后挑)

- **主判据:** 前向 ≥ **6 个自然月**(≥6 次调仓)后,AI 账本相对量化账本的**净成本 Sortino 与最大回撤**均不劣、
  且累计净收益差 > 0 → AI re-rank 有效;续跑至 12 个月确认。
- **证伪线:** 6 个月后 AI 账本累计净收益差 < 0 **且** Sortino 更差 → **AI 降级为解释/风控工具**,
  rerank_v2 作废(计入 C16b 试验台账);不得换 config 立即重试(新 config = 新周期新注册)。
- **中途不看不调:** 前向期间禁止基于已实现收益调整 prompt/权重/上限/模型(M3/C16);
  运维修复(API 换端点等)允许但记入审计日志。
- **覆盖率停用期计法:** overlay 停用的月份,AI 账本=量化账本(差=0),计入分母(不剔除)。

## 4. 不可变项(冻结清单)

`rerank_v2.yaml` 全文(models/weights/tilt 映射/覆盖率闸门/K/max_swap/floor/行业与组合上限)·
extract_v2/score_v2 两个 prompt · config_hash_v2 `5c8a462e1c5500b3` · 判定规则(§3)·
**attempt 台账制决策日志(R2-Blocker-2)**:LLM 花费前必先落不可变
`cycles/<cycle>/attempt_<decision_id>/`(attempts_ledger.jsonl 计数);逐名 LLM
request/response/validated-scorecard 边跑边落盘;失败 attempt 永不删除、同 cycle 重跑必须显式
`--new-attempt <reason>`;已 published 的 cycle 永不可再决策;manifest 按 `REQUIRED_MANIFEST_FIELDS`
钉住全部输入与产物 hash(含逐名 dossier/raw-LLM/scorecard hash、quant_scores_hash、prompt/model id、
`git_worktree_clean` 硬闸);fill_record.json 事后补录,同样 append-only。
**改任何一项 = rerank_v3 + 新预注册。**

## 5. 已知缺口(起跑前置,诚实在案)

1. **量化分新鲜度:** 月度 5-B bump 满足月级新鲜度(§6 规则);5-C 日更=自动化增强,非硬闸。
   provider as-of 上界硬闸:provider 末日必须 ≤ 成交日前一开市日(R2-Blocker-4)。
2. **日度文本任务未挂**(schtasks 待用户授权)——未挂期间人工补跑;runner 硬闸拒绝 >48h 陈旧拉取、
   任一 required source 无 ok 状态、store 文件缺失(R2-Blocker-6)。
3. **Ark 模型 cutoff 未公布**(C2 在案)——与 forward-only 设计一致,无阻塞。
4. v2 无自动 veto(红旗探测器后续版本);行业标签=当前快照(仅护栏)。
5. **过渡持仓账本缺口(R2-Major-3,第二周期前必补):** `--record-fills` 目前只记录目标账本的
   买入可执行性;从第 2 期起必须落完整 transition fill ledger(旧仓→新仓 sell/buy delta、
   跌停/停牌无法卖出、现金滞留、部分成交 carry),否则 6 个月对比会把不可卖出旧仓当作已顺利切换。
6. **时区语义:** Asia/Shanghai 为唯一决策时区(R2-Blocker-5);text_store 全部时间戳=CN 墙钟。

## 6. 起跑条件(全部满足才开钟)

☐ **数据新鲜度规则:** 决策用因子值 = provider 末日(≤ activation−1);**陈旧度(activation − provider_end)
  ≤ 5 个交易日**(runner 硬闸),每期记入 manifest;月度 5-B bump 发布覆盖月初即满足
☐ 日度文本任务运行中(schtasks 待授权;过渡期人工跑 text_daily_pull.py;runner 校验最新 pull manifest ok+新鲜)
☐ 本文件 committed 且 config_hash_v2 与 runner 重算一致(runner 硬闸)
☐ 首期决策产出目录 append-only(workspace/outputs/mvp_forward/cycles/;runner 硬闸)
☑ 实现级 §10 diff-review #1 裁定已全部应用(7B+5M+4m,2026-07-08);re-review #2 待发

**首个真前向周期 = 2026-08(activation ≈ 2026-08-04 后首个交易日);2026-07 周期决策时点已过,
不可回填(仅可作近真演练,不记战绩)。D3 不变:spent_oos_end 冻结 2026-02-27——解冻延长数据,不延长证据窗。**
**入口:`run_forward_cycle.py --cycle 202608`(决策,开盘前)→ 月度 bump 后 `--record-fills`(补录成交可行性)。**
