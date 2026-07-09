# AI 链路观察站 — 202501 金股池历史试点(非证据)

**Date:** 2026-07-08 · **Class:** D(workspace 研究工具,非正式路径)
**Status:** BUILD — 用户口径已定(每日重决策 × 全池 149 打分 × 匿名化对照)
**用途:** 链路过程透明化 + 抽取 QA + 直觉建立 + 未来 golden-set 标注底料。
**⚠️ 全站非证据横幅:** 本试点的一切收益/打分数字 = C5 quasi-forward replay,**非 alpha 证据**,
不得用于验证"AI 是否加 alpha"(那是 202608+ 前向 paper-live 的工作),不得反推调
prompt/权重/阈值(C16b 多重检验绕过通道)。

---

## 1. 三个硬事实(定位的由来)

1. **PIT 不可恢复(C1)**:2025-01 文本今天才入库 → 真实 `decision_visible_at`=2026-07。
   试点用**模拟可见性** `sim_visible_at`(见 §3),每行带 `visibility_basis` 标签。
2. **LLM 训练记忆污染(C2)**:doubao cutoff > 2025-01,模型可能"记得"个股 2025 年结局。
   → 打分结果只作过程展示;**匿名化对照腿**(去公司名/代码重打)量化污染幅度。
3. **存储隔离(本试点最高红线)**:历史文本**绝不进生产 `data/text_store/`**——前向 dossier
   过滤只看 `decision_visible_at ≥ T−30d`,回填行会以"新文本"身份涌进 202608 真决策。
   → 独立库 `data/text_store_hist_pilot/`(同一 C1 machinery,`store_dir` 覆写)。

## 2. 范围与口径

- **池**:`broker_recommend_202501.parquet` = 201 条推荐 / **149 只**去重名。
- **决策日**:202501 池 C3 激活日 → 2025-01 月末的每个交易日(**每日重决策**=链路观察模式);
  **day-4 那天的决策单独标注为"协议腿"**(等价月度前向协议)。
- **打分范围**:全池 149 打分卡(展示);**换股仍只在量化 top-50 floor 内**(协议一致);
  floor 外分数**不进任何决策**。
- **文本窗**:每名 1 年档案(2024-01-01..2025-01-31)入库展示;LLM dossier 仍按冻结链路
  30d/20条/倒序(与 rerank_v2 一致)。
- **链路复用**:`build_dossier` / `prompt_render` / `scorecard` / `ark_client` /
  `apply_rank_overlay` **同一代码路径**;试点 config 独立(`pilot_v1`,自带哈希,不动冻结的 v2)。

## 3. 模拟可见性(sim_visible_at)

| 源 | 真实时间戳 | sim_visible_at | visibility_basis |
|---|---|---|---|
| anns_d | `rec_time`(发布时间) | rec_time | `real_timestamp`(缺失→ann_date+1d 09:00,`nominal_plus_lag`) |
| irm_qa_sh/sz | `pub_time` | pub_time | `real_timestamp` |
| research_report | 无(`trade_date` 名义日) | trade_date **+2 开盘日** 09:00 | `nominal_date_plus_2open`(report_rc 已验锚精度先例) |

生产 C1 戳照常打(`decision_visible_at`=真实入库时刻,诚实);试点重放 loader 只认
`sim_visible_at ≤ 决策时点`,并在看板上明示两者差异(这本身是 PIT 教学素材)。

## 4. 每名每决策日的 LLM 调用(≤5 次,内容哈希缓存)

1. extract(quick=doubao-lite):dossier → digest
2. text-score(deep=doubao-pro):5 维 + 罚分 + 逐字证据(C16 遏制,同 v2)
3. **fund-score(deep)**:基本面卡片(pit_research_loader as-of,lag-1)→ 4 维
   (盈利质量/成长动能/资产负债风险/估值贴现)——BLUEPRINT Layer-3 基本面分析师的最简实现
4-5. anon-extract + anon-text-score:确定性脱敏(公司名/代码/简称→"公司X")后重打
   → `Δfinal = named − anon` = 污染诊断指标

**确定性合成(LLM 永不合成):** `final_combined = 0.6·final_text + 0.4·final_fund`(预注册于
pilot config);tilt = `0.15·(final_combined − cohort均值)/50`;覆盖率<80% → 当日叠加禁用。

## 5. 产出与看板

产物目录 `workspace/outputs/ai_chain_observatory/`:
`daily/<date>/names/<code>/`(与前向 attempt 同构的逐名工件)+ `nav/` + `board/`。
看板(自包含静态 HTML):①流程视图(原始→保留/丢弃→digest→维度分+证据→final→tilt→进出账本)
②决策视图(换股审计/护栏/floor)③日度 NAV 四腿(池EW/量化日度/AI日度/AI-day4协议腿)
④个股 1 年文本档案 ⑤匿名化 Δfinal 分布。每页非证据横幅。

## 6. 升级路径(出试点须过的门)

任何组件(基本面 persona/prompt/权重)要进 202608+ 真前向链 = 新 config 版本(rerank_v3)+
FORWARD_PREREG 修订 + §10 GPT 跨审。试点结果**不构成**该评审的证据(至多是工程可行性演示)。
