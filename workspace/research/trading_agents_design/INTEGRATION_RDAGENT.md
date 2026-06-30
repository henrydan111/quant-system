# RD-Agent(Q) → 你的 factor_lifecycle 集成方案

**Date:** 2026-06-28
**Status:** DESIGN (pending §10 GPT cross-review before any load-bearing build)
**Source paper (verified):** [arXiv 2505.15155](https://arxiv.org/abs/2505.15155) "R&D-Agent-Quant" (MSRA,
NeurIPS 2025) · code [github.com/microsoft/RD-Agent](https://github.com/microsoft/RD-Agent) (MIT)

---

## 0. 核心论点(为什么这俩是天作之合)

RD-Agent(Q) 是一台强力的**因子生成机**,但论文**自己承认它几乎没有治理**。它承认的 5 个缺口,
**恰好就是你这一年建的那一层**:

| RD-Agent(Q) 承认的缺口 | 你系统里对应的能力 |
|---|---|
| 无多重检验校正(无 Bonferroni/FDR/deflated-Sharpe) | deflated Sharpe + 边际贡献选择 + FrozenSelectionSet 一次性 OOS 预算 |
| 验证期 2015-16 跨迭代复用(非真 OOS) | sealed-OOS 一次性封存,spend-on-attempt |
| 无因子级 lookahead/PIT 讨论 | PIT002 lint + operators.py 的 `Ref(...,1)` 强制 + field_status 闸门 |
| 无滑点/冲击/容量(long-short CSI300 gross) | 事件驱动引擎(总收益、T+1、涨跌停、真实成本)+ deployment gate |
| 过拟合控制仅靠 IC≥0.99 去重 | 完整 draft→candidate→approved 阶梯 |

> **结论:RD-Agent 当「沙盒里的草稿工厂」,你的 sealed-OOS 阶梯当「闸门」。它生成,你审判。**
> 这正好落在 [INSTITUTIONAL_WORKFLOW.md](INSTITUTIONAL_WORKFLOW.md) 的 Stage-2(研究台,用 AI 提假设)
> 与 Stage-3(独立验证)之间——RD-Agent 是 Stage-2 的工具,绝不是 Stage-3 的批准者。

**它的 14.21% ARR 不是可部署数字**(gross/无摩擦/大盘 long-short)——是草稿级筛选信号。你的 deployment
gate 才是现实检验。

---

## 1. 集成架构(数据流 + 四道防火墙)

```
            [沙盒 · 仅 IS 窗口]                          [你的治理 · 不可见于 RD-Agent]
  RD-Agent(Q)  ──F1──►  翻译/PIT 闸门  ──F2──►  catalog DRAFT
  fin_factor          (字段合规+Ref安全           │
  (LiteLLM→Claude)     +definition_hash)          ▼
  跑你的 Qlib                              factor_lifecycle IS gate
  (CSI300/500,                              (draft → candidate)
   splits 重设为                                  │
   ≤is_end)                                       ▼  ──F3──► 多重检验:记录挖掘条数
                                            deflated-Sharpe + 边际贡献选择
                                                   │
                                                   ▼  ──F4──► LLM-cutoff 机理审计
                                            FrozenSelectionSet → sealed-OOS (一次性)
                                                   │
                                                   ▼
                                            approved (+ deployment gate 另算)
```

---

## 2. 四道防火墙(RD-Agent 没有、必须由你补上的)

### F1 · 窗口隔离(最重要的一行配置)
- RD-Agent 论文默认 test=2017-2020 / 泛化 test=2024-2025。**把它的 train/valid/test 全部重设到你的
  IS 窗口以内(例如 ≤2018),让它永远看不到你的 sealed-OOS(2021+)。**
- RD-Agent 内部的回测**只是草稿筛选,不是闸门**。它的 IC/ICIR 只当 draft 信号。
- RD-Agent 已有的缓解(LLM 只看 schema、不看原始数据/时间边界)是**必要但不充分**——见 F4。

### F2 · 翻译 / PIT 安全闸门(fail-closed)
- RD-Agent 产出的是 **Python 代码因子**;你的 catalog 是 **Qlib 表达式 + §3.5 catalog-binding
  不变量**(stored `definition_hash` 必须 == 当前 catalog hash)。两者有阻抗失配,必须有翻译层:
  - **首选:约束 RD-Agent 只用你的算子词汇表生成**(把 operators.py 的算子 + `ADJ_*_T1` 常量喂进它的
    prompt)→ 产出能直接表达成 catalog 表达式 → 正常绑定 `definition_hash`、走 §3.5 binding gate。
  - **回退:** 实在新颖、算子表达不了的,走 `signal_registry` 外部信号路径(放弃 catalog-binding,
    换更严的人工审查)。
- 每个候选因子过三检,任一不过即拒:① **field_status 合规**(只能用 approved `$field`)② **PIT 安全**
  (跑现成的 PIT002 lint + operator stack-walk,确认每个 `$field` 在 `Ref(...,1)` 内)③ 计算
  `definition_hash`,登记为 **DRAFT**。

### F3 · 多重检验控制(RD-Agent 完全没有)
- RD-Agent 会**狂挖几百个因子**。沙盒里随便挖(便宜,~$10/cycle),但**晋级**必须:
  - **记录挖掘条数 N**(RD-Agent 的 loop workspace 有)→ 喂给 **deflated Sharpe**,让收缩诚实。
  - **按对现有 approved 集的边际正交贡献选**(IC × 低相关),**不是 standalone IC**
    (你 memory `reference_factor_selection_marginal_not_icir` 的方法)。
  - 最终晋级**一次性花 sealed-OOS 预算**,经 `FrozenSelectionSet`。

### F4 · LLM-cutoff 前视(微妙但致命)
- 两个泄漏源:**(a) 因子本身**用了同日/未来字段 → F2 的 PIT lint 抓;**(b) LLM 凭训练记忆**提因子。
- **关键认识:你的 sealed-OOS 窗口(2021+)有一部分落在 LLM(o3-mini/GPT-4o,cutoff ~2024)的训练知识里。**
  所以一个 LLM 因为"知道 2021-2023 发生了什么"而提出的因子,在你 2021-2026 的 OOS 上验证 = **被污染**。
  → **对 LLM 生成的因子,你的 sealed-OOS 2021+ 是一道比对人工 a-priori 因子更弱的检验。**
- 防御:① 给 RD-Agent 因子打**独立 provenance 类 `llm_generated`**(像你已有的 `oos_informed_backfill`
  那样区别对待)② **机理审计**:晋级前要求因子有 a-priori 经济解释(不只是拟合),GPT 跨审 + 人工签字
  ③ 理想情况:最终批准要一个**晚于 LLM cutoff 的前向窗口**(forward/paper-live),而非只靠 2021+ 的历史 OOS。

---

## 3. 落地步骤(分步,每步可独立验证)

**Step 0 · 起 RD-Agent(沙盒)**
- Docker + Python 3.10 + LiteLLM 后端指向你 `.env` 的 **Claude**(`CHAT_MODEL`/`EMBEDDING_MODEL`)。
- 指向你的 Qlib 数据(CSI300/CSI500)。**把 train/valid/test 全部重设到 ≤is_end(F1)。**
- 跑 `rdagent fin_factor`,拿到一批 draft 因子代码 + loop workspace,人工检视。**先不接你的系统。**

**Step 1 · 翻译/PIT 闸门(F2)**
- 写一个 ingestion adapter:RD-Agent 因子 → 你的 catalog 草稿。先做"算子词汇表约束"版,跑通
  field 合规 + PIT lint + `definition_hash`。拒掉所有越界/同日泄漏因子。

**Step 2 · 接进 factor_lifecycle(你已有 draft→candidate IS gate)**
- 把通过 F2 的因子注册成 draft,跑你现成的 IS-only `factor_lifecycle` gate。**加挖掘条数 N 的记录(F3)。**

**Step 3 · 选择 + 晋级(F3 + F4)**
- 对这批草稿做 deflated-Sharpe(带 N)+ 边际贡献选择 → `FrozenSelectionSet` → sealed-OOS 一次性。
- LLM 因子加机理审计 + `llm_generated` provenance。批准 ≠ 可部署(deployment gate 另算)。

**Step 4 · 固化成 orchestrator profile(可选,重复用)**
- 新 profile `rdagent_factor_mining`:把 Step 0-3 编成 DAG;MLflow 记录 **prompt+模型版本 + 挖掘条数**
  (prompt/模型漂移 = 因子漂移,要可复现)。

---

## 4. 不要做的事

- ❌ 不要信 RD-Agent 的回测当闸门(它的 14% ARR 是 gross/无摩擦/大盘)。
- ❌ 不要让它碰 2021+(F1)。
- ❌ 不要按 standalone IC 晋级(用边际贡献 + deflated Sharpe)。
- ❌ 不要跳过 LLM 因子的机理审计(F4 的 cutoff 重叠问题真实存在)。
- ❌ 不要把 Python-code 因子硬塞进 catalog 而绕过 §3.5 binding(走算子约束或 signal_registry)。

---

## 5. 诚实的预期价值

- RD-Agent **便宜、快、能产出大量看似合理的草稿**(~$10/cycle)。**绝大多数会死在你的闸门上——这正是重点**
  (你的闸门比它的 IC≥0.99 严得多)。
- 现实的赢面:**几个你本来想不到的、真正正交的候选因子,以很低成本拿到**——不是论文那个 14% ARR。
- 战略意义:这把 RD-Agent 的"生成"和你的"独立验证"拼成完整的机构研究环。**你相对论文作者的优势,正是
  那道他们承认自己没有的闸门。**

**本方案在写任何 Step 1+ 的新基建前,过 §10 GPT 跨审。**
