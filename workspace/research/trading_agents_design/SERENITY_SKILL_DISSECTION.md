# serenity-skill 解剖 — 可迁移的证据纪律 / 确定性打分 / 风险边界

**Date:** 2026-06-30
**Status:** DESIGN reference (NON-FORMAL) — feeds the eventual `PHASE2_TEXT_PIPELINE.md` design
**Method:** 主源直读(不是 web fan-out;上一轮 deep-research 的 openQuestion #2 明确没覆盖它,因为 niche 仓库搜不出内部)。
经 `gh api … -H "Accept: application/vnd.github.raw"` 直读以下文件:`SKILL.md` · `references/evidence-ladder.md` ·
`references/risk-and-compliance.md` · `references/deep-research-workflow.md` · `references/market-source-playbook.md` ·
`scripts/serenity_scorecard.py` · `assets/bottleneck-scorecard.json`。
**Source:** [github.com/muxuuu/serenity-skill](https://github.com/muxuuu/serenity-skill)(MIT,default branch `main`)。

---

## 0. 它是什么(先校准预期)

serenity-skill **不是 TradingAgents 那种交易/决策框架,而是一个"供应链卡点投研工作流"skill**:输入主题/市场 →
输出**排序后的研究优先级 + 证据链 + 风险 + 下一步核查**,SKILL.md 明令 **"Research support only; no trade
execution"**,买卖决定归用户。

> ⚠️ **它没有任何回测、没有 alpha 证据**。价值不在"卡点猎手=超额",而在一套打磨好的**证据纪律 + 确定性打分 +
> 风险边界**。**借脚手架,别借 alpha 主张。**

---

## 1. 架构 / 数据流(逐字核实)

- **请求路由(5 模式):** theme scan / single-company challenge / candidate comparison / research-partner / learning。
- **9 步工作流:** scope → 把市场故事翻成"系统变化"(`demand wave → system pressure → required change → constrained
  layer`)→ 画产业链(8 层 checklist)→ 找稀缺层 → 建 **≥20 候选池** → **分级取证(≥25 源)** → 排序 →
  "什么情况说明判断错了" → 下一步核查。
- **关键纪律:层级排序 ⟂ 公司排序分离** —— 先排"哪层最稀缺"再排"哪家最贴近那层";强制点名一个"热门但被降级"
  方向并解释。**防止 AI 直接跳到票。**
- **跨市场适配:** 经济逻辑不变,只换 source toolkit(A股=年报/问询函/互动易/招投标/环评/海关… 详见 market-source-playbook)。

---

## 2. 三个可直接迁移的"皇冠件"

### ① Evidence Ladder(证据分级)→ 填上"A股可信源分层"空白
(deep-research 那轮明确说 A股反操纵零实证;serenity 给了现成的**设计级**源分级。)

| 强(高置信结论) | 中(佐证/三角) | 弱(仅线索,需更强源确认) |
|---|---|---|
| 交易所文件/公告/问询函、财报、转录、官方订单/中标/产能预定、监管批复、专利标准 | 权威财媒、行业刊物、公司官网、**卖方/专家研报(假设可见时)**、上下游公开交叉验证 | KOL 帖、社媒线程、论坛、来源不明截图、无基本面的价量异动 |

**映射到你解锁的 Tushare 文本源:**
- **强** → `anns_d`(公告)、`irm_qa`(交易所互动平台)、`npr`/`monetary_policy`(官方/监管)
- **中** → `research_report`(卖方)、`news`/`major_news`(财媒)
- **弱** → 你**没接**社媒(符合"弱=仅线索"的判断,天然避开最差层)

**外加可直接编码的"红旗"操纵/炒作探测器**(evidence-ladder + risk-and-compliance):
单一客户传闻撑论点 · 股价主要靠社媒热度 · 转收入前需先融资 · 客户未具名且收入影响含糊 ·
**应收/存货增速快于收入** · **声称稀缺但毛利不改善** · 管理层用主题语言但分部数据不动。
→ **A股反操纵那块缺的、现成的设计启发(非实证,思路扎实)。**

### ② 确定性 Scorecard(LLM 出评分输入,Python 算分)→ 最该抄的工程模式
`serenity_scorecard.py` 机制(逐字核实):

- **8 因子,各 0-5,加权到 100:** `demand_inflection 15` · `architecture_coupling 10` · `chokepoint_severity 15` ·
  `supplier_concentration 12` · `expansion_difficulty 12` · **`evidence_quality 15`** · `valuation_disconnect 11` ·
  `catalyst_timing 10`。
- **8 项惩罚,各 0-5,×2 扣分:** dilution_financing / governance / geopolitics / liquidity / hype_risk /
  accounting_quality / cyclicality / alternative_design_risk。
- `final = clamp(Σ factor_points − Σ penalty×2, 0, 100)` → verdict 档(≥85 Top / ≥70 High / ≥55 Track / else Lead)。
- schema(`bottleneck-scorecard.json`)强制 `evidence:[{claim,source,strength}]` + `what_could_weaken_view:[]`(kill-switches)。

> **可迁移核心纪律:LLM 只填 0-5 评分 + 证据,最终分由确定性 Python 算,LLM 绝不直接吐分数/决策。** 一举三得:
> (a) 把 AI 关在"判断输入"位、出不了"alpha 引擎"圈;(b) 满足"便宜层输出可审计/可复现";
> (c) **`evidence_quality` 是一个 15 分因子**——证据强度被烤进分数。**这就是你 C12 typed-output 的现成模板形状。**

### ③ 风险边界(research-support-only)→ 与"AI 非 alpha 引擎"同构
明禁:保证收益话术 · 直接买卖指令 · 协同拉抬 · 传闻荐股 · MNPI · 编造价格/客户/合同/市值。
高风险加倍审慎清单:微盘/社媒驱动/单一未具名客户/重融资稀释/完美执行估值/政策驱动。→ 直接并进治理护栏。

---

## 3. 对本项目框架的含义(填的缺口)

| 缺口/需求 | serenity 贡献 |
|---|---|
| A股可信源分层 / 反操纵(deep-research 零实证) | evidence-ladder 三级 + 红旗探测器(设计级,现成) |
| C12 AI 分析师 typed 输出 schema | bottleneck-scorecard.json 形状(factors + penalties + evidence + kill-switches) |
| "便宜层输出可审计/可复现" + AI 不当 alpha 引擎 | **LLM 出评分、Python 算分** 的确定性聚合纪律 |
| 防 AI 跳到票 | 层级排序 ⟂ 公司排序 分离 |

---

## 4. 诚实的限制(别抄过头)

- **无验证、无回测:** discretionary 研究流程模板,非可回测信号源;它的"稀缺层"判断正是 deep-research 标的
  "不可靠环节(LLM 判断)"。→ **借脚手架(证据分级/确定性打分/风险边界),但任何由它产生的信号仍要过你的
  sealed-OOS / 前向闸门**——serenity 自己不提供验证。
- **打分权重是手设先验**(demand 15 / chokepoint 15 / evidence 15…),非经验校准 → 当**起始 schema**,别当已验证权重。

---

## 5. serenity vs TradingAgents(互补,各补一块)

- **TradingAgents** = 编排骨架(角色 / 两层 quick-deep 路由 / 多空辩论流水线)。弱点:LLM 不透明裁决、回测被污染。
- **serenity-skill** = 证据纪律 + 确定性打分 + 研究支持边界。弱点:无验证、discretionary、权重手设。
- **合起来:** TradingAgents 骨架(角色 + Qwen/Claude 两层)+ serenity 的 evidence-ladder & 确定性 scorecard
  (让 AI 输出被分级 + 确定性聚合,而非黑箱)+ **本项目的 sealed-OOS / 前向验证**(两者都没有的那道闸门)。

---

**用途:** 本解剖为 Phase-2(多源文本 + AI 多分析师)设计的输入;真正折进 `PHASE2_TEXT_PIPELINE.md` 并改动契约时,
按 §10 走 GPT 跨审。本文件本身为描述性参考,NON-FORMAL。
