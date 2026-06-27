# 深度研究：AI 提取大V/资讯观点作为 A股量化另类数据源 —— Go/No-Go 评估

- **日期**：2026-06-23
- **方法**：多智能体深度研究（deep-research workflow，run `wf_97a7f3b7-786`）—— 5 个检索角度 × 并行 WebSearch → 抓取 24 个来源 → 抽取 106 条可证伪声明 → 取 top 25 做 3 票对抗验证 → 综合。
- **裁定统计**：25 条验证 → **13 confirmed / 12 killed** → 综合为 **8 条发现**。
- **运行说明**：首跑（task `w41gpz70a`）在验证阶段被 Anthropic 服务端**瞬时限流**击穿（75 个验证 agent 齐发 → 全部弃权 → 假性「全部否决」）。修复：把验证阶段改为**顺序分批 + 单次重试**（脚本 `deep-research-wf_97a7f3b7-786.js`），复用已缓存的检索/抓取结果 resume（task `wyr21vghu`）后成功。原始 JSON：见同目录 `deep_research_raw_result.json`。

---

## 0. 结论（Go/No-Go）

**有条件 GO** —— 做一个**小型、门控的研究试点**；**NO** —— 重投入 / 搭资讯平台 / 裸抓大V 当 alpha。

必须做**命题降级**：把「大V/KOL 观点 = alpha」改写为「**文本 / 新闻 / 分析师情感因子**」。最干净、最可辩护的 A股 alpha 车道是：

1. **分析师预期修正情感**（直接对接本系统已建、已撤销的 `earn_eps_diffusion_60/_120`）；
2. **论坛观点离散度（dispersion）** 作风险/反转信号（**不是** bullishness 水平）。

**一句话理由**：edge 在「抽取方法」，不在「文本获取」；而 A股本地最强的证据恰恰是**警告**（散户情感拖慢而非领先价格；股吧被水军/黑嘴结构性污染）。AI 的真正价值在大规模抽取与判断本身 —— 但它在放大 alpha 的同时也**放大污染**（黑嘴已在投毒 LLM）。

---

## 1. 经对抗验证的核心发现

### 1.1 机构在做吗？有效吗？（子问题 1）

- **「方法是 edge」有硬证据 `3-0`**：监督学习、用收益反向调参的情感模型 **SESTM**，在同一条道琼斯新闻流上**同时打败词典法与商用龙头 RavenPack** —— 等权多空 Sharpe **4.29 vs 3.24 (RavenPack) vs 1.71 (Loughran-McDonald)**，OOS 2004-2017，净值口径仍领先。→ [NBER w26186](https://www.nber.org/papers/w26186)
- **机构已产品化 `2-0`**：RavenPack 把新闻情感做成定价因子（"news beta"）。**但是厂商研究 + 2012 年老结论**，快速衰减领域要打折。→ [RavenPack: Constructing a Sentiment Factor](https://www.ravenpack.com/research/constructing-sentiment-factor)
- **有效性是「市场结构特异」的 `1-1✓`**：美国社媒情感领先收益，但英/南非/巴西是新闻情感领先 → **美英社媒结果不能照搬 A股**。→ [Heliyon 2024 (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11076966/)

> ⚠ **两条因限流弃权、未裁定但来自一手来源、决策相关，手动补回**：
> - **成本/容量天花板**：SESTM 在 10bps 日成本下最优净 Sharpe 仅 **2.30（gross 4.26）**，无约束等权策略**日换手 ~95%**，小盘股 15 分钟反应 **52bps**（大盘 11bps）→ **信号住在最难交易的地方**。[NBER w26186]
> - **社媒情感约一半被新闻 confound**：美国 Twitter-收益相关 0.1296，剔除新闻后掉到 **0.0664**。[PMC]

### 1.2 A股端的有效性与失败模式（子问题 4）—— 最重要

- **散户主导市场里情感更像噪音 `2-1✓`**：A股情感↑ → **价格延迟↑** → 信息效率**下降**；对抗性反向检索反而**收敛支持**（个股情感损害价格信息含量；百度/股吧情感预测**反转**、与当期收益负相关）。「跟着情感做多」的朴素因子站不住。→ [JRFM 2026 (MDPI)](https://www.mdpi.com/1911-8074/19/4/257)
- **但「框对了」能提真信息 `3-0`**：股吧观点**离散度低**（一致看多**或**看空）→ **崩盘风险↑**（agridx 对 NCSKEW 系数 **1.531, t=6.981**，1% 显著，14,496 公司-年）。**离散度/分歧度，而非情感水平**，是更稳的构造角度。→ [SZSE CSSCI 证券市场导报 2020](http://docs.static.szse.cn/www/aboutus/research/secuities/daily/W020200407584016405398.pdf)
- **对抗性污染是 Go/No-Go 级结构性风险 `2-1✓`**：同篇 CSSCI 逐字核实 —— 股吧是"模糊信息"，活跃大量**水军、黑嘴**，被用作内幕交易/股价操纵工具，**无真伪发帖门槛、无自我纠错**。叠加 **2025 CSRC：黑嘴已用多账号假帖投毒 AI/LLM** —— 正是 LLM 抽取管线的命门。→ 同上 + CSRC 2025

### 1.3 最干净的 A股车道：分析师预期修正（直接映射 `eps_diffusion`）

- **分析师预期修正仍 OOS 预测相对收益 `2-1✓`**：~6000 只全球票按修正广度/幅度排序，**top-bottom decile 价差 7.6%/年**（15.6% vs 8.0% CAGR），2003 起、指标 2012 才建（过半窗口真 OOS）。→ [Mill Street Research](https://www.millstreetresearch.com/do-analyst-estimate-revisions-still-help-forecast-relative-stock-returns/)
- **这正好对接本系统已审批又被撤销的 `earn_eps_diffusion_60/_120`**（analyst-revision breadth）。这条「另类数据」车道我们其实**已经走在上面**，只需重新激活 + 加固。

### 1.4 开源 repo 与现成框架（子问题 2、3）

- **全链路抽取工具已成熟**：[FinGPT](https://github.com/AI4Finance-Foundation/FinGPT)（MIT；情感/NER/关系抽取/Forecaster）`3-0`；[PIXIU / FinMA](https://github.com/The-FinAI/PIXIU)（MIT, NeurIPS 2023；FinMA LLM + FLARE/FinBen 含 stock-movement）`3-0`。
- **A股数据采集开源存在，但只到 `scrape→DB` `3-0`**：[zcyeee/EastMoney_Crawler](https://github.com/zcyeee/EastMoney_Crawler) 抓全字段，但纯爬虫→MongoDB、有验证码/IP 封锁摩擦。**NLP / 实体链接 / 因子化 / PIT 层全部要自建。**
- **⚠ 关键负面结论 `3-0`**：被调研的开源 forecaster **没有一个给出回测 / Sharpe 证据**；FinGPT-Forecaster 被独立研究（arXiv 2507.08015）发现**系统性看多偏差 + 亏损**。**没有现成 alpha 可借，只有工具可借。**

---

## 2. 不要依赖的说法（验证未通过）

| 声明 | 票数 | 来源 |
|---|---|---|
| 研报情感 RoBERTa 因子 20% 年化 / 7.19% RankIC | `0-3` | [arXiv 2112.11444](https://arxiv.org/pdf/2112.11444) |
| FinGPT v3.3 情感 F1 0.882 全面碾压 GPT-4/BloombergGPT | `0-3` | [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) |
| RavenPack「>70% 顶级量化基金都在用」 | `0-2` | [RavenPack](https://www.ravenpack.com/products/edge/data/news-analytics)（厂商宣称） |
| A股里股吧/雪球情感影响 > 机构指标 | `1-2` | [SZSE 论文](http://docs.static.szse.cn/www/aboutus/research/secuities/daily/W020200407584016405398.pdf)（被过度解读） |
| Twitter 情感预测后「不反转 = 真信息」 | `1-2` | [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0378426620302314) |
| 研报/新闻情感快速衰减的具体数字形态 | `1-2`/`0-2` | NBER / arXiv 2112.11444 |

---

## 3. 对本系统的 Go/No-Go 硬门槛

真正的拦路虎不是「能不能抽取」，而是这四道闸：

1. **PIT 时间戳保真 = 头号门槛（已被同类数据坑过）**。这就是 `report_rc` / `eps_diffusion` saga 的教训：论坛/社媒文本可**编辑、删除、厂商回填**，nominal post time 不可信。必须锚定**可见时间**（scrape-time 或可证伪的 visible-time + buffer），过 `pit_research_loader` + sealed-OOS + **restatement canary**（`eps_diffusion` 当初就因 too-good LS Sharpe + restatement 残差**被撤销过一次**）。
2. **反水军/反操纵层是硬前提**。用**离散度（dispersion-over-level）+ 账号质量加权**，避开最易被操纵的「情感水平」维度。高关注名（恰恰会被交易的名）操纵最猛。
3. **净成本/容量大概率坍塌**。参照本系统 `eps_diffusion`：因子级审批一旦限制到 liquid universe 就塌到 **-3.6% / +4.5% CAGR**（且该结论在 2026-06-22 fill-price-aware gate 后已 stale，需重跑）。所有 headline（SESTM 4.29、Mill Street 7.6%）都是 **gross、多为非中国**。
4. **走既有门控、按边际正交增量选因子**。`draft → candidate(IS gate) → approved(sealed-OOS)`；用 **marginal contribution**（vs 已有 `report_rc`/`eps_diffusion` 的正交增量），别看 standalone ICIR。

---

## 4. 如果做：最小门控试点（不抓裸大V）

- **车道 A（首选，复用已有数据）**：分析师预期修正情感 —— 在 `report_rc`/朝阳永续类数据上扩展 **breadth / magnitude / 分歧度**，重新激活 `eps_diffusion`。
- **车道 B**：股吧/雪球**观点离散度因子**（dispersion，非 level）作**风险/反转**信号。
- **抽取**用 FinGPT / 本地 LLM，但抽出**结构化「立场 + 置信 + 实体」**再自己因子化，不直接吃 LLM 情感分（防幻觉、防投毒）。
- **kill 标准**：net liquid-universe Sharpe 门槛、对抗鲁棒性（水军注入测试）、与现有因子正交性 —— 任一不过 stay draft。

---

## 5. 悬而未决（需本地引擎回答）

1. **净成本/容量**：过本地 PIT/event-driven 引擎、在 A股 liquid universe 后，这些 gross 数字还剩多少？
2. **中文论坛 PIT 时间戳保真度**：股吧/雪球/微博 是否暴露可信 visible-time（含编辑/回填），还是只有 scrape-time 可锚？
3. **反水军层能否在「会被交易的高关注名」里留下残余 alpha**，还是操纵直接主导信号？
4. **大V 个人技能持续性**：本轮**无任何存活 claim** 支持「A股大V 过去胜率→未来胜率」（survivorship 修正后）。验证到的全是离散度/崩盘/操纵，而非可识别的持续技能型 KOL —— **裸大V 路线证据最弱。**

---

## 附录 A：完整来源清单（24 源）

| # | 来源 | 质量 | 角度 | 抽取声明数 |
|---|---|---|---|---|
| 1 | [NBER w26186 (SESTM)](https://www.nber.org/papers/w26186) | primary | 学术/实证 | 5 |
| 2 | [Wiley J.Finance (Tetlock 2007)](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.2007.01232.x) | 抓取失败 | 学术/实证 | 0 |
| 3 | [ScienceDirect (Twitter 情感)](https://www.sciencedirect.com/science/article/abs/pii/S0378426620302314) | primary | 学术/实证 | 5 |
| 4 | [MDPI JRFM 2026 (情感→价格延迟)](https://www.mdpi.com/1911-8074/19/4/257) | primary | 学术/实证 | 4 |
| 5 | [RavenPack: Sentiment Factor](https://www.ravenpack.com/research/constructing-sentiment-factor) | primary | 学术/实证 | 3 |
| 6 | [Heliyon 2024 (PMC, 市场结构)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11076966/) | primary | 学术/实证 | 5 |
| 7 | [RavenPack News Analytics](https://www.ravenpack.com/products/edge/data/news-analytics) | primary | 厂商 | 4 |
| 8 | [BigQuant: 朝阳永续一致预期](https://bigquant.com/wiki/doc/jnnQ2c9fIR) | primary | 厂商 | 3 |
| 9 | [arXiv 2512.11913](https://arxiv.org/pdf/2512.11913) | blog | 厂商 | 5 |
| 10 | [Mill Street (分析师修正)](https://www.millstreetresearch.com/do-analyst-estimate-revisions-still-help-forecast-relative-stock-returns/) | primary | 厂商 | 5 |
| 11 | [RavenPack: quant-fundamental convergence](https://www.ravenpack.com/blog/quant-fundamental-convergence) | blog | 厂商 | 4 |
| 12 | [arXiv 2112.11444 (研报 RoBERTa 情感)](https://arxiv.org/pdf/2112.11444) | primary | 厂商 | 5 |
| 13 | [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | primary | 开源 repo | 5 |
| 14 | [PIXIU / FinMA](https://github.com/The-FinAI/PIXIU) | primary | 开源 repo | 5 |
| 15 | [zcyeee/EastMoney_Crawler](https://github.com/zcyeee/EastMoney_Crawler) | primary | 开源 repo | 5 |
| 16 | [ZJU 研究（雪球/东方财富 KOL）](https://zibs.zju.edu.cn/2026/0615/c81935a3178943/page.htm) | secondary | A股 | 5 |
| 17 | [SZSE CSSCI 证券市场导报 2020（股吧）](http://docs.static.szse.cn/www/aboutus/research/secuities/daily/W020200407584016405398.pdf) | primary | A股 | 5 |
| 18 | [清华 CJIS（影响力加权情感）](https://cjis.sem.tsinghua.edu.cn/vol31-01.pdf) | primary | A股 | 5 |
| 19 | [证券时报网](https://stcn.com/article/detail/938884.html) | secondary | A股 | 4 |
| 20 | [Atlantis Press（Guba LSTM 情感）](https://www.atlantis-press.com/article/125907328.pdf) | primary | A股 | 5 |
| 21 | [SSRN 4586726](https://ssrn.com/abstract=4586726) | primary | LLM/风险 | 4 |
| 22 | [SSRN 4412788](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4412788) | primary | LLM/风险 | 5 |
| 23 | [Renault: market manipulation](https://www.thomas-renault.com/wp/market-manipulation-suspicious.pdf) | primary | LLM/风险 | 5 |
| 24 | [arXiv 2404.12001](https://arxiv.org/pdf/2404.12001) | primary | LLM/风险 | 5 |

---

## 附录 B：运行元数据 / 可复现

- run id：`wf_97a7f3b7-786`（首跑 task `w41gpz70a` 验证阶段限流失败；resume task `wyr21vghu` 成功）
- 脚本：`<session>/workflows/scripts/deep-research-wf_97a7f3b7-786.js`（验证阶段已改为顺序分批 + 单次重试以抗瞬时限流）
- 用量：127 agents / ~7.8M subagent tokens / 749 tool uses / ~30 min（成功跑）
- 原始结果 JSON（全部 25 条验证声明 + 投票 + 来源）：同目录 `deep_research_raw_result.json`
- 相关记忆：`research_kol_sentiment_altdata_verdict`、`project_tushare_15000_expansion`（report_rc/eps_diffusion）、`project_idea_sourcing_pipeline`、`reference_factor_selection_marginal_not_icir`
