ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is a DESIGN-STAGE review of a research PLAN (no code yet). The deliverable being designed is a fund-of-funds capital-allocation study: re-weight 20 already-deployed, unlevered 果仁 (guorn.com) equity/fund strategies — currently equal-weighted ~5% each — to beat equal-weight out-of-sample. The "assets" are 20 precomputed daily TOTAL-RETURN strategy NAV series (2014-01-02..2026-06-18, dividends reinvested, 1x). Be skeptical, surface blockers, do not rubber-stamp. The single most dangerous failure here is NOT raw-data PIT (the inputs are precomputed NAVs) but (i) LOOKAHEAD inside the walk-forward weight estimation, and (ii) IN-SAMPLE WEIGHT OVERFITTING laundered as "out-of-sample" via insufficient multiple-testing discipline.

REPO (public — fetch to verify the contract the plan must honor)
https://github.com/henrydan111/quant-system   (branch: report-rc-registration)
Raw file form — replace <path> with any repo path, e.g. https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/result_analysis/metrics.py :
https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/<path>
NOTE: this branch is pushed; the contract files (CLAUDE.md, metrics.py) are reachable at the CONTEXT links below. The design doc under review is ALSO embedded IN FULL below — treat the embedded text as authoritative; the links only cross-check the surrounding contract.

CONTEXT — read to judge the plan against the contract:
- CLAUDE.md (hard invariants §3, execution/cost realism §3.3, research integrity §7, no-hedge §7.10, no-leverage §7.11)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/CLAUDE.md
- src/result_analysis/metrics.py (the canonical metric library the plan commits to reuse — CAGR/MDD/Calmar/Sharpe/Sortino etc.)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/result_analysis/metrics.py
- (background only; may be on a feature branch, not on main) the 果仁 strategy library handoff describing the 65 books, their recipes, and the microcap-optimism caveat — workspace/research/idea_sourcing/guorn/HANDOFF.md

RE-REVIEW (R4) — your R3 verdict was REVISE with NO Blocker (R1+R2 already confirmed folded). All R3 findings are now folded into the embedded v4 plan. Please verify each is resolved:
- R3-Major-1 (full-sample diagnostics in design packet) -> §2 rewritten to QUALITATIVE structure only; ALL 2014-2026 full-sample EW/correlation/risk-contribution numbers relocated to §9 Appendix A (post-holdout, explicitly NON-design-input); §0 EW figures tagged as background; §4.4 keeps design diagnostics <=2023-05-31.
- R3-Major-2 (binary pass too lenient) -> §4.0 step 3 is now THREE-state: pass requires point ΔMDD<0 AND point ΔCalmar>=+0.10 AND ΔCAGR lower-CI>=-3pp AND bootstrap P(ΔCalmar>0)>=80%; signs-pass-but-weak-confidence = inconclusive; else fail.
- R3-Major-3 (bootstrap params unfrozen) -> §4.1: stationary paired block bootstrap, expected block length 21 trading days, 10,000 resamples, fixed seed in frozen_candidate.json; sensitivity at block lengths 10 & 63; if pass/fail flips across them -> inconclusive.
- R3-Major-4 (subperiod windows overlapped holdout) -> §4.3 + §3.5: fixed pre-holdout windows 2014-01-02..2016-12-30 / 2017-01-03..2019-12-31 / 2020-01-02..2023-05-31, >=2/3 ΔMDD<0; holdout 2023-06-01..2026-06-18 reported separately.
- R3-Minor-1 max-Sharpe removed from the deployable tie-break list (§4.0); R3-Minor-2 any data-driven clustering variant must be a separately-named scheme, computed <=2023-05-31, included in the trial family / N_eff (§4.4).

SELF-REVIEW PREFLIGHT (v4): Verdict "clean for GPT R4"; no finding declined across R1+R2+R3. Your R3 'minimum effect size + inconclusive band' concern is itself now folded (§4.0 three-state). The acknowledged irreducible residual (your R3 final line): one A-share market + one ~3-year holdout regime cannot prove deployability -> §5 mandates paper/live-small before real money, and pre-holdout single-market overfit is disclosed (§8), not claimed away.
Residual concerns for R4: (1) Are +0.10 ΔCalmar and 80% P(ΔCalmar>0) the right magnitudes, or should they scale with estimated CI width? (2) Given the strict three-state rule, the honest outcome may well be 'inconclusive' not 'pass' — the plan should (and now does, §0/§8) treat 'inconclusive -> stay at EW' as an acceptable, expected result so a null is not pressured into a pass; is that framing sufficient? (3) Is anything still blocking implementation as-is?

WHAT CHANGED (authoritative — treat the embedded plan as the source of truth; links cross-check the contract)
The full design document follows under the marker below. Review IT.

QUANTITATIVE-RESEARCH PRINCIPLES — check the plan against EACH; a violation is a Blocker
1. NO-LOOKAHEAD (cardinal, adapted to this study). Every weight at rebalance t must use ONLY returns/cov/vol estimated from data strictly before t, applied to the forward holding period. No full-sample covariance, no full-sample vol, no peeking at the realized frontier. Ask: does any weight use information not knowable at its decision date?
2. OUT-OF-SAMPLE IS SACRED. Temporal walk-forward only, never random. The final ~3-year confirmation window is single-look. No scheme/parameter chosen BECAUSE it won the OOS — selection must be by robustness across the pre-registered grid, not by max OOS metric.
3. MULTIPLE TESTING / OVERFITTING. 8 schemes x (lookback {126,252,504}) x (cadence {M,Q}) x (cap {none,10%,15%}) is a large effective trial count of CORRELATED configs. Is the deflated-Sharpe / block-bootstrap / PBO treatment adequate to avoid declaring a lucky cell the winner? Are effective (not naive) trials counted?
4. EXECUTION & COST REALISM. The top-level rebalancing of capital between books incurs real cost on |Δw| turnover; results must be net of a plausible cost and turnover reported. The underlying books' own costs are already in the NAVs.
5. NO LEVERAGE. gross <= 1x, long-only, sum(w)=1; the headline is the 1x number.
6. NO HEDGE WORDS. Every quantitative claim is backed by a named dataset/script/output or explicitly marked "unverified — test Y resolves it".
7. INHERITED BIAS HONESTY. The underlying 果仁 NAVs may be optimistic (microcap limit-up assumed buyable); absolute levels are suspect, relative weighting conclusions more robust. Is this disclosed and is its DIRECTION on the conclusion argued correctly?
8. REUSE NOT REINVENT. Metrics via result_analysis.metrics; do not reinvent Sharpe/MDD; do not import the dormant portfolio_risk module into any path.

REVIEW QUESTIONS
1. Validity — Is the walk-forward protocol airtight against lookahead? Is the EW baseline a fair control? Is the objective (Calmar-max + MDD<EW + CAGR>=EW-3%) well-posed and free of OOS selection? Name any way overfitting could still leak in.
2. Method — Given high correlation (0.54 mean; 0.66-0.83 within groups A/B/D) and ~150 monthly points, is the candidate scheme set the right one? Anything essential missing (e.g. shrinkage targets, Bayesian/Black-Litterman with a risk-only prior, turnover penalty in-objective, regime/subperiod weighting) or anything included that's a known overfit trap? Is HRP/two-stage grouping (5 style families) the right structure given the cluster diagnosis?
3. Statistics — Is the robustness suite (subperiod stability >=2/3, block-bootstrap of scheme-minus-EW, deflated Sharpe, leave-one-book-out, cost & param sensitivity) sufficient to claim a real improvement rather than luck? What's the right significance treatment for "scheme beats EW on Calmar"?
4. Honesty of the framing — The plan argues a strict Pareto improvement (higher CAGR AND lower MDD) is unlikely and frames the realistic win as better Calmar/drawdown at similar CAGR. Is that the correct expectation given the diagnosed return/risk/correlation structure, or is there a credible path to genuine Pareto dominance the plan underweights?
5. Evidence — What specific test/output would you require before trusting the recommended weights for real-money deployment?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each quoting the offending plan section and giving an exact suggested replacement. Map every Blocker to the principle it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.

============================================================
===== DESIGN DOC: GUORN20_REWEIGHT_PLAN.md (authoritative) =====
============================================================

# 果仁 20-策略组合再加权研究计划 (GUORN20 Re-weight)

> **目标**: 对当前等权(各 ~5%)运行的 20 个已部署果仁策略, 寻找一个**样本外稳健**的资本配置方案,
> 在**长期收益与回撤**上优于等权。
> **数据**: `Knowledge/果仁回测结果/` 已下载的 65 个策略回测导出 (其中 20 个为实盘组合), 2014-01-02..2026-06-18,
> 日频净值曲线, **总收益口径(含分红再投资), unlevered 1×**。
> **状态**: 设计稿 **v4** (GPT-5.5 Pro R1+R2+R3 的 finding **已全部折入**; R3 = **无 Blocker** → 待 R4 确认)。NON-FORMAL research artifact。
> **Last updated**: 2026-06-24

---

## 0. 一句话结论 (先讲清楚这件事有多难)

等权(EW)**本身已经是一个很强的基准**(以下全样本数字为**背景动机, 非设计输入** —— 见 §9 附录; 设计/判定一律用 ≤2023-05-31 + holdout): 实测 EW(月度再平衡) 夏普 **1.82**、最大回撤 **−32%**、年化 **~45%(日历口径)/47%(252口径)**。
EW 的夏普**高于 20 个策略中的 19 个**(只有 ST_大市值 1.90 略高), 因为它已经吃掉了绝大部分分散化收益(分散比 1.30)。
所以"在收益和回撤上都严格优于 EW(Pareto 占优)"是一个**高门槛**目标, 不能假设一定能达到。

机会判断 (以下均为**待检验假设 H, 各绑定一个具名输出**, 非结论 — §7 量化研究原则 6/7):
- **H1 (回撤/Calmar)**: 风险型加权相对 EW **降低回撤、提高 Calmar/Sharpe**(依据: EW 把过多*风险*而非资本押在高波成长/微盘上, 诊断 3)。**检验**: `guorn20_walkforward.py` → `paired_delta_metrics.csv`(配对 bootstrap ΔMDD/ΔCalmar + §4 多重检验校正)。
- **H2 (年化两全)**: 能否在压低回撤的同时**年化经济非劣于 EW**(高波成长券同时是高夏普券, 压低会牺牲收益; 两全须靠低相关分散券 + 高 Calmar 券)。**检验**: 同表 ΔCAGR 配对 bootstrap 下界 ≥ −3pp。
- **H3 (严格 Pareto)**: 是否存在**收益↑且回撤↓**的稳健方案(高门槛, 不预设)。**检验**: 同表 (ΔCAGR>0 ∧ ΔMDD<0) 标记 + §4.0 封存复审。
- 判定口径 = **样本外 Calmar/回撤为主目标, 年化经济非劣 (≥EW−3pp); 严格 Pareto 仅作附带检验**(§7 D1 已锁)。绝对水平受果仁微盘乐观偏差影响 → §4.2 具名 haircut 检验; 相对加权结论更稳健。
- **预期管理 (R3)**: 三态裁决(§4.0)下, 诚实结果很可能是 **inconclusive**; **inconclusive / fail → 维持等权(EW)** 是**可接受且预期**的结论 —— **绝不把 null 结果硬凑成 pass**。

---

## 1. 这 20 个策略分别是什么 (经济逻辑 + 投资逻辑)

数据来源: `guorn_strategies_master.json` 解析出的 recipe (选股域/打分因子/调仓/择时) + 果仁回测指标。
下表年化/回撤/夏普为**果仁官方口径**(已验证为 ground truth)。

### 分组 A — 微盘·成长·动量 (高波高收益引擎, 基准=果仁微盘)
共同逻辑: **小市值(总市值从小到大, 含行业内+全市场双重)** 是最大权重的打分项, 叠加**成长**(核心利润同比 `CoreProfitQGr%PY`、扣非EPS同比 `EpsExclXorQGr%PY`、ROE环比改善 `ROETTMDiffPQ`)、**剔除涨停的路径动量**(250d−20d、120d−20d 对数收益, IF(涨停,0,...))与**业绩预告**。日调仓、09:35 调仓价、备选 5~20 只。这是组合的"进攻核心"。

| nn | 策略 | 年化% | 回撤% | 夏普 | 经济逻辑要点 |
|---|---|---|---|---|---|
| 1 | sm_01_成长动量 | 57.2 | 47.9 | 1.68 | 小市值×成长×剔除涨停路径动量×业绩预告(从小到大=反转保护) |
| 5 | sm_01_成长_v1 | 58.2 | 50.0 | 1.58 | 同上, 把预告换成业绩快报归母净利同比 |
| 6 | sm_01_成长高贝塔@TMT_v1 | 60.3 | 51.9 | 1.44 | 限定 TMT(传媒/电子/计算机/通信)+高 beta(250d), 高弹性 |
| 10 | sm_双创研发强度_v1 | 62.7 | **61.0** | 1.54 | 创业板/科创, 研发强度(RND%Assets, 研发同比)×机构/管理层持股, 仓位 14~26% 更集中 → 回撤最高 |

### 分组 B — GARP·质量 (制造业/全市场, 中波, 基准=果仁微盘)
共同逻辑: **GARP(合理价格成长)** —— BP(带壳/筹资调整)、核心利润/EV、EBITDA/EV、毛利/资产, 叠加成长与中性化因子。比 A 组更看重估值与质量, 回撤略低。

| nn | 策略 | 年化% | 回撤% | 夏普 | 经济逻辑要点 |
|---|---|---|---|---|---|
| 7 | sm_大制造GARP_v3 | 62.0 | **38.8** | **1.71** | 限定先进制造(机械/电子/电气/计算机/通信), 多估值锚+财报后漂移, Calmar 最优之一 |
| 9 | sm_GARP_illiq | 49.6 | 42.5 | 1.54 | ILLIQ 流动性过滤(取低流动性溢价)+23 个 GARP/质量因子全家桶 |

### 分组 C — 价值·红利·低波 (防守分散券, 低波低收益, 基准=中证红利/现金流/创业板)
共同逻辑: **高股息(股息率TTM、预期股息、分红增长)+低波动+低 beta+稳定分红**, 主板/央企/重股息为主。这是组合的"防守端", 与成长端相关性最低。value_创业板/AH/FCF 偏价值成长, 弹性略高。

| nn | 策略 | 年化% | 回撤% | 夏普 | 经济逻辑要点 |
|---|---|---|---|---|---|
| 19 | value_红利低波_v2 | 29.7 | **21.0** | 1.32 | 主板高股息×低 beta×低波×股息率−10Y国债>2%, 回撤最低 |
| 20 | value_红利低波_央企_v1 | 32.1 | 21.7 | 1.27 | 央企高股息, 相对国债利差择券 |
| 21 | value_红利低波_重股息_v1 | 33.2 | 33.0 | 1.27 | 连续分红+分红/净利占比, 重股息稳定性 |
| 22 | value_AH_低溢价GARP_v1 | 30.4 | 37.3 | 1.06 | AH 两地上市, AH 溢价低(权重×4)+GARP+股息 |
| 23 | value_FCF_非金sm_v2 | 29.0 | 44.2 | 1.05 | 非金融自由现金流(FCF>0、FCF/市值、FCF稳定性) |
| 24 | value_创业板sm_v1 | 41.8 | 43.1 | 1.14 | 创业板价值(EV/EBITDA、营收/市值、BP、FCF)+小市值 |

### 分组 D — 成长@周期·分析师·盈余惊喜 (创业板/全市场, 高波, 基准=创业板/沪深300)
共同逻辑: **分析师预期**(预期营收/盈利 2 年复合增长、评级调高/增持、评级机构数中性化)+**盈余惊喜/净利润断层**(实际−预期、预告−预期)/总市值或/|预期|, 叠加行业景气与周期动量。捕捉 PEAD(盈余公告后漂移)与机构关注度。

| nn | 策略 | 年化% | 回撤% | 夏普 | 经济逻辑要点 |
|---|---|---|---|---|---|
| 42 | 成长_机构预期@周期_v1 | 54.1 | 46.6 | 1.27 | 24 因子: 预期增长×评级动量×行业均值(HAVG)中性化, 3 日调仓 |
| 43 | 成长_净利润断层_v2 | 48.4 | **28.3** | **1.62** | 纯盈余惊喜(净利润断层): (实际−预期)/|预期|+预告超预期, 含 ST, Calmar 优 |
| 44 | 成长_双创_GARP@周期_v2 | 43.4 | 46.5 | 1.13 | 创业板版的 B 组 22 因子 GARP |
| 45 | 成长_隔夜动量@周期 | 27.8 | 54.0 | 0.81 | 剔除涨停路径动量(权重大)+评级变化+行业动量, 20 日调仓; **偏弱** |
| 48 | 成长_高波@周期 | 29.5 | **65.5** | **0.72** | 低 beta 过滤+评级/盈余惊喜+行业景气, 5 日调仓; **最弱, 回撤最高** |

### 分组 E — 特殊驱动 (低相关分散券)
共同逻辑各异, 关键是**与成长端低相关**, 是真正的分散来源。

| nn | 策略 | 年化% | 回撤% | 夏普 | 经济逻辑要点 |
|---|---|---|---|---|---|
| 53 | ST_大市值_v3 | 55.5 | 43.5 | **2.00** | **仅 ST 股**, 大市值+有营收+核心利润+评级, 博弈摘帽/重组, beta 仅 0.54, 收益驱动独立 |
| 31 | MultiA_风险平价_v1 | 13.8 | 22.8 | 0.60 | **场内基金/ETF/QDII 多资产**风险平价(低波+动量+sortino), beta 0.40 最低, **波动 16.4% 最低** |
| 29 | MultiA_动量18 | 32.5 | 22.8 | 1.14 | 基金 20 日动量轮动, beta 0.45, 跨资产分散 |

---

## 2. 数据诊断 (定性结构; 全样本数值见 §9 附录, 非设计输入)

> **⚠ 无泄漏边界 (R3-Major-1)**: 设计包(pre-holdout)只基于 **≤2023-05-31** 的诊断。本节给出**定性结构**(供人类理解, 由 a priori recipe 分组支撑); 所有 **2014-2026 全样本数值**(EW 基线 / 相关系数 / 风险贡献)= **背景动机, 非设计输入**, 移入 **§9 附录 A**(holdout 后随报告生成权威版); 冻结流程实际消费的诊断按 §4.4 仅用 ≤2023-05-31。数据完整性: 重建总收益/最大回撤与果仁官方逐位一致(年化差异仅日历 vs 252 口径)。

- **诊断 1 — EW 已经很强, 门槛高**(定性): EW(月度再平衡)夏普高于 20 券中的 19 个、波动显著低于单券平均 → 已实现可观分散, 两全很难。[数值 §9]
- **诊断 2 — 相关性高但有结构**(定性): A/B/D(成长/微盘/GARP/周期)互相高度相关(大量冗余); C(价值红利低波)中度; **E(ST+基金)是真分散券**(与成长端最低相关)。分组按 recipe 经济逻辑 **a priori** 固定。[相关数值 §9]
- **诊断 3 — EW"资本等权"实为"风险不等权", 风险压成长端**(定性): 成长系(A+B+D)资本约半却扛大部分风险; 分散券(E)资本不低却贡献小部分风险 → **杠杆点**: 风险型加权把资本从高波成长移向 C/E 压回撤。[风险贡献表 §9]
- **诊断 4 — 核心张力**: 高波成长券**本身也是高夏普**, 单纯压波动会牺牲收益; 两全须靠低相关分散券(E)+ 高 Calmar 券(净利润断层/大制造 GARP/ST)—— min-var/max-div/HRP/风险预算的用武之地, 须**样本外**证明。

---

## 3. 研究框架与方法 (How)

把这看作一个 **fund-of-funds 资本配置(book 层)问题**: 不动各策略内部选股, 只决定"给每个 book 多少钱、何时再平衡"。被优化的"资产"= 20 条策略级日收益。

### 3.1 顶层模型与约束
- 权重 `w_i ≥ 0`, `Σw_i = 1`, **unlevered(gross = 1×, 满仓或留极小现金, 禁止杠杆 — CLAUDE.md §7.11)**。
- 每个再平衡日用**截至该日的历史数据**算目标权重 → 持有至下个再平衡日 → 期间权重随收益漂移 → 再平衡回目标。
- **顶层再平衡成本(精确口径, Major-2)**: 每个再平衡日先算 *pre-trade 漂移权重 `w_drift`* → *目标权重 `w_target`*; 单边买入名义 `buy = Σ max(w_target−w_drift, 0)`、单边卖出 `sell = Σ max(w_drift−w_target, 0)`; `cost = buy×buy_bps + sell×sell_bps`, 直接扣净值。报告**年化换手 + 累计成本拖累**, 并在 **0 / 5 / 10 / 20 bps 单边**做敏感性。

### 3.2 基准 (Baseline)
- **S0 = EW (cadence-matched 控制, Major-1)**: 对**每个候选再平衡频率**都用**同频率、同顶层成本模型**的 EW 作对照 → 分别报告 **EW-月度 / EW-季度 / EW-buy&hold(不再平衡漂移)**, 以**隔离再平衡 alpha**("再平衡本身"的收益 vs 加权方案的收益)。主基准 = EW-月度(= 用户当前实盘形态)。

### 3.3 候选加权方案 (**事前锁定清单**, 全部只用历史数据)
风险型(不预测收益, 稳健):
- **S1 逆波动率** (trailing σ, 倒数归一)
- **S2 风险平价/ERC** (等风险贡献, 收缩协方差)
- **S3 最小方差** (long-only, Ledoit-Wolf 收缩协方差, 权重上限)
- **S4 最大分散度** (Choueifaty max-diversification)
- **S5 层次风险平价 HRP** (López de Prado; 天然契合诊断 2 的 5 簇结构, 免协方差求逆)
- **S6 两段式**: 先在 5 个风格组间做风险平价, 组内等权 (可解释、低换手、稳健)

收益感知型(更易过拟合, 须重正则化 + 样本外严控):
- **S7 风险调整倾斜**: 逆波动率 × trailing Calmar/Sharpe 评分 (温和倾向高 Calmar 券)
- **S8 最大夏普 MV** (Ledoit-Wolf 收缩 + 权重上限) —— **作为"过拟合对照组", 预期样本外不胜出**, 用来证明"复杂均值方差不是答案"

协方差: Ledoit-Wolf 收缩(20 资产稳健); 波动: trailing/EWMA。约束(**D2 已锁定 = 保留全部 20 券**): `floor ≤ w_i ≤ cap`, `Σw=1`, long-only; floor ∈ {1%, 2.5%}, cap ∈ {10%, 15%}。**floor/cap 落地(Major-4, 避免事后归一扭曲优化)**: **S2/S3/S4/S8(凸优化族)直接把 floor/cap 写进 optimizer 约束**; **S1/S7/HRP/两段式** 用**一次确定性的 bounded-simplex 投影**(并在输出标注投影方法), 不做"截断后反复再归一"。**"允许置零 / cluster-collapsed 版"仅作 diagnostics**, 非推荐输出。

### 3.4 样本外(walk-forward)协议 —— **这是整个研究成立的关键**
- **预热**: 前 L 天仅用于估计第一组权重(不计入业绩)。
- **再平衡频率**: 月度(基准), 季度(变体)。
- 在每个再平衡日 t: 仅用窗口 `[t−L, t)` (或扩张窗口) 估计输入 → 解权重 → 应用于 `(t, t+频率]` → 记录**已实现**收益。**任何权重都不使用其持有期及之后的数据。**
- 拼接 → 每个方案/配置一条**结构上即样本外**的日收益曲线。任何权重不使用其持有期及之后数据(实现须单测 `weight_t ⊥ returns_{≥t}`)。
- **★ 设计冻结日 = 2023-05-31 (Blocker-1 封存)**: **所有**方案/参数/"稳健性"判定**只用 ≤2023-05-31 的 walk-forward 数据**完成; **holdout = 2023-06-01..2026-06-18** 在选择完成、冻结**唯一**候选后才打开, 且**只能 accept/reject 该唯一候选、看后不得再改任何参数**。冻结的确定性选择规则见 **§4.0**。

### 3.5 评估指标 (全部经 `src/result_analysis/metrics.py`, 全部样本外)
**CAGR 同时报告 252-口径与日历-口径**(Minor-2; `metrics.py` 默认 252 年化, 日历口径对齐果仁)、波动、夏普(rf 对齐果仁 ~3%)、Sortino、最大回撤、Calmar、最差滚动 12 月、月度跑赢 EW 比率、**年化换手 + 累计成本拖累**、扣成本后 CAGR。按 **§4.3 锁定的 pre-holdout 子区间**分报(holdout 2023-06..2026-06 **单列**, 不混入)。所有"相对 EW"指标(ΔCAGR/ΔMDD/ΔCalmar)以 **path-correct 配对 bootstrap(分别重建两条净值路径再求差, §4.1)分布 + CI** 报告。

---

## 4. 反过拟合与证伪 (Research Integrity — 不可妥协)

对照 CLAUDE.md §7。组合权重在 12 年历史上优化是**经典过拟合陷阱**。GPT R1 的三个 Blocker 全部落地为以下**可执行**协议。

### 4.0 封存式 OOS 选择协议 (Blocker-1 — 防 post-hoc 赢家挑选)
1. **设计冻结日 2023-05-31**: 配置网格 = 方案 × (L∈{126,252,504}) × (频率∈{月,季}) × (cap∈{10%,15%}) × (floor∈{1%,2.5%}); **每个配置只在 ≤2023-05-31 的 walk-forward OOS 上算指标**。
2. **冻结唯一确定性选择规则**(打开 holdout 之前写死, 不可改):
   - a. 过滤: 仅保留 **pre-holdout ΔMDD<0** 且 **ΔCAGR 配对 bootstrap 下界 ≥ −3pp** 的配置;
   - b. 排序: 按 **pre-holdout 配对 bootstrap ΔCalmar 中位数** 降序;
   - c. tie-break: 先**低换手**, 再**低复杂度**(EW < 逆波动 < 两段式 < HRP < ERC < min-var/max-div); **S8 max-Sharpe 不在可部署 tie-break 列内(R3-Minor-1; §5 仅诊断)**;
   - d. 取 rank-1 = **唯一冻结候选**。
3. **打开 holdout (2023-06-01..2026-06-18)**: **只计算冻结候选 vs cadence-matched EW**(绝不读其余配置的 holdout 收益, 否则 = 为全网格打开 holdout, Blocker-2), 用**单候选 path-correct 配对 bootstrap(§4.1)**。**三态裁决(R3-Major-2, 防"微弱正 ΔCalmar+宽 CI"被当通过)**:
   - **pass** = 点估计 ΔMDD<0 **且** 点估计 **ΔCalmar≥+0.10** **且** ΔCAGR 下界≥−3pp **且** bootstrap **P(ΔCalmar>0)≥80%**;
   - **inconclusive** = 符号对但置信不足(未达上述阈值);
   - **fail** = 符号错(ΔMDD≥0 或 ΔCalmar≤0 或 ΔCAGR 下界<−3pp)。
   family-wise 校正只用于 **pre-holdout 选择 claim**, 不在 holdout 阶段使用。**看 holdout 后不得再调任何参数**(任何回调 = OOS 失效, 须重新声明并消耗一次新 holdout)。

### 4.1 多重检验与显著性 (Blocker-2 + R2-Blocker-1 修正 bootstrap 对象)
- **测试账本 `testing_ledger.csv`**: 记录**每一个**配置(scheme/L/cadence/cap/floor)逐日的**两列** `strategy_return` 与 `ew_return`(cadence-matched EW), **不存"收益差"单列**。试验族 = 全网格, 不止 8 个方案。
- **★ path-correct 配对 block-bootstrap (R2-Blocker-1)**: Calmar/MDD/CAGR 是**路径指标** —— ΔMDD ≠ "超额收益路径的 MDD"。故对**成对两列收益**抽连续块 → **分别重建 strategy 与 EW 两条净值路径** → 各自算 CAGR/MDD/Calmar → **再求 Δ**。**绝不**从"仅超额收益"路径算 ΔMDD/ΔCalmar。得 Δ 指标分布与 CI。
- **★ 冻结 bootstrap 参数 (R3-Major-3, 保证 p/CI 可复现)**: **stationary paired block bootstrap**, 期望块长 **21 交易日**, **10,000** 次重抽, **固定 seed 记入 `frozen_candidate.json`**; 并在块长 **10 / 63** 报敏感性 —— **若 pass/fail 在三个块长间翻转 → 裁决 = inconclusive**。
- **有效试验数 N_eff**: 由配置间"收益差序列"相关矩阵特征值算 participation ratio `N_eff=(Σλ)²/Σλ²`, clamp 到 `[8, 配置总数]`。
- **★ family-wise 校正 = max-stat, 仅用于 pre-holdout 选择 claim (R2-Blocker-2)**: 零假设"全族无一胜 EW"下, 在 **≤2023-05-31** 数据上 bootstrap 跨全配置族的 max ΔCalmar 分布, 给"选出的候选在 pre-holdout 显著优于 EW"一个 family-wise 校正 p/CI。**holdout 阶段绝不读全网格** —— 只对冻结候选做**单候选** path-correct 配对 bootstrap(§4.0)。deflated/PSR-Sharpe 仅辅助, 不作为 Calmar 胜出证明。

### 4.2 继承性乐观偏差 = 具名 haircut 检验 (Blocker-3 — 不只叙述)
- **假设**: 下调微盘成长券(A/D 组)在果仁"涨停可买"乐观下是保守的(memory `project_guorn_parity`)。
- **检验 `haircut_sensitivity.csv`**: 对 A/D 组 NAV 施加 **5/10/20% 年化 haircut** 后**重跑整条封存流程**, 报告**冻结候选权重是否变化、ΔCalmar 是否存活**。偏差方向(利空高波券)对"下调高波券"结论是安全垫 —— 须由该表证实, 非断言。
- **注意(Minor-2)**: NAV 层年化 haircut 是 **stress test, 非"涨停可买性"的真实证明**(无法在 book 净值层施加真正的 limit-up-buyability 惩罚); 真正验证需 book 层逐笔交易/持仓 replay(若数据可得)。

### 4.3 稳健性套件 (其余 Major/Minor)
- **参数敏感性而非寻优**: 全网格报告; 推荐 = §4.0 冻结规则选出的唯一候选, **非"最优格"**。
- **子区间稳定性 (R3-Major-4, 固定窗口避开 holdout)**: pre-holdout 三窗 = **2014-01-02..2016-12-30 / 2017-01-03..2019-12-31 / 2020-01-02..2023-05-31**; 候选须在 **≥2/3** 窗 ΔMDD<0。holdout **2023-06-01..2026-06-18 单列报告**, 不参与选择。
- **留一 book + 留一风格族(Minor-1)**: 逐一剔除单 book **以及**整组(尤其 E=ST/MultiA 分散族、A 微盘族), 确认结论不被单券或单一风格族主导。
- **成本敏感性**: §3.1 的 0/5/10/20 bps 单边全报告。
- **全样本最优**: 仅作"事后天花板"参考, 明确标注**不可投资**, 绝不当结论。

### 4.4 设计诊断的无泄漏边界 (R2-Major-1)
任何**影响设计选择**的收益型诊断 —— HRP 距离/聚类、§4.0 复杂度排序的经验依据、haircut 的 A/D 分组、候选纳入 —— **只用 ≤2023-05-31 数据计算**。§2 的全样本相关/风险贡献是**描述性背景, 不进入选择**; 风格分组(A–E)按 recipe 经济逻辑 **a priori** 固定(非按收益数据聚类), 故 leakage-safe。全样本诊断仅在 holdout 报告**之后**(§9 附录)呈现并标注"描述性"。
- **数据驱动聚类的守护 (R3-Minor-2)**: HRP/两段式默认用 a priori A–E 分组。**任何数据驱动聚类的变体**必须 (i) 作为**独立 scheme** 命名、(ii) 仅用 ≤2023-05-31 计算聚类、(iii) **纳入 pre-holdout 试验族**(计入 §4.1 N_eff)。

---

## 5. 交付物
1. ✅ 提取脚本 `_guorn20_extract_recipes.py` + 特征刻画 `_guorn20_characterize.py` (已完成)。
2. ✅ 对齐日收益矩阵 `guorn20_daily_returns.parquet` + 元数据 `guorn20_meta.csv` (已生成)。
3. ⏳ **walk-forward 引擎 `guorn20_walkforward.py`** (workspace; 复用 `result_analysis.metrics`; 协方差/优化用 cvxpy/numpy, **不**依赖 dormant `src/portfolio_risk`, §3.4)。具名输出:
   - **`testing_ledger.csv`**: 全配置逐日**两列** `strategy_return`/`ew_return`(§4.1 path-correct bootstrap 用)+ N_eff + pre-holdout max-stat 校正 p。
   - **`paired_delta_metrics.csv`**: 每配置 vs cadence-matched EW 的 ΔCAGR/ΔMDD/ΔCalmar + path-correct 配对 bootstrap CI。
   - **`selection_trace.csv`(R2-Minor-1)**: 每配置的 **pre-2023-05-31** 换手、复杂度 rank、各 filter/rank 值 —— tie-break 可审计。
   - **`haircut_sensitivity.csv`**(§4.2)、**`frozen_candidate.json`**(§4.0 冻结候选 + holdout **单候选** accept/reject)。
4. ⏳ 结果报告 (markdown): 全配置对比表 + 样本外净值曲线 + 子区间/敏感性/bootstrap/haircut + **推荐权重**及理由 + caveat。
5. ⏳ 可选: MLflow 记录本次对比实验; dashboard 提及。

> **S8 max-Sharpe = 永久 negative control(R2-Major-2)**: **排除在冻结可部署选择规则之外**, 只作过拟合对照诊断, **在本研究中永不可能成为推荐配置**(即便偶然过 family-wise 校正)。
> **部署 caveat(R2-Minor-3)**: 即便 holdout 通过, holdout(2023-06..2026-06)仍是**单一 regime** → 实盘前须经 paper / 小额实盘验证。

## 6. 里程碑
- M1 数据 & 诊断 (✅ 本文 §1–§2)。
- M2 计划 self-review + GPT cross-review + 用户确认 (← **当前所处阶段**)。
- M3 实现 walk-forward 引擎 + 8 方案 + EW 基准。
- M4 敏感性/子区间/bootstrap/留一 稳健性套件。
- M5 推荐权重 + 报告 + (self-review → GPT 实现审查)。

---

## 7. 决策项 (D1/D2 已由用户拍板 — 2026-06-24)

| # | 决策 | **锁定结果** |
|---|---|---|
| D1 | **主目标** | ✅ **(b) 最大化样本外 Calmar / 压回撤, 年化经济非劣于 EW**; (a) 严格 Pareto 占优作附带检验。判定阈值(holdout): **单候选 path-correct 配对 bootstrap 的 ΔCalmar>0 ∧ ΔMDD<0 ∧ ΔCAGR 下界 ≥ −3pp**(family-wise 校正仅用于 pre-holdout 选择 claim, holdout 不读全网格 — Blocker-2)。**−3pp 是事前声明的经济非劣边际(non-inferiority margin), 非统计结果**(Major-3): 用 bootstrap 下界(非点估计)守门。 |
| D2 | **权重约束** | ✅ **(a) 保留全部 20 券 + 上下限**: 权重下限 `w_i ≥ floor`(候选 floor=1% 或 0.5×EW=2.5%)、上限 `w_i ≤ cap`(候选 10%/15%=2×/3×EW)。"允许置零/集中版"**仅作对照**展示, 不作为推荐输出。 |
| D3 | **顶层再平衡频率/成本** | 默认**月度 + 季度变体**, 成本做敏感性 (无需单独拍板)。 |
| D4 | **范围** | 默认**仅再加权**(保留 20 券, 无择时叠加层) —— 符合"对这 20 个再加权"原意。 |

> floor/cap/cadence/L 的具体数值 = §4.0 封存网格的维度, 由冻结的确定性规则(§4.0)选出唯一候选(**非"最优格"**); −3pp 为 §4.0 的经济非劣边际。

---

## 8. 自审 (Self-review, 对照 §3 硬不变量 + §7 量化研究原则; v4 = GPT R1+R2+R3 折入后)

- **无前视 (§7.1)**: walk-forward 每权重仅用 `[t−L,t)`; 实现须单测 `weight_t ⊥ returns_{≥t}`。✅
- **OOS 神圣 + 封存 (§7.2/3)**: ★ R1-Blocker-1 折入 —— 设计冻结日 2023-05-31 + 唯一确定性选择规则 + holdout 单次 accept/reject(§4.0); 全样本最优仅作标注天花板。✅
- **多重检验 (§7.3)**: ★ R1-Blocker-2 折入 —— testing ledger + N_eff(participation ratio) + 配对 block-bootstrap 重算净值路径 + max-stat family-wise 校正(§4.1); deflated-Sharpe 降为辅助。✅
- **禁对冲词 / 证据 (§7.10)**: ★ R1-Blocker-3 折入 —— §0 改为 H1/H2/H3 假设 + 具名输出; 继承偏差改为 haircut 具名检验(§4.2)。✅
- **EW 对照公平 (Major-1)**: cadence-matched EW(月/季/buy&hold)隔离再平衡 alpha(§3.2)。✅
- **成本真实 (Major-2)**: 买卖单边名义 × bps, 0/5/10/20bps 敏感性(§3.1)。✅
- **非劣边际 (Major-3)**: −3pp 声明为经济 non-inferiority margin, bootstrap 下界守门(§7 D1)。✅
- **floor/cap 不扭曲 (Major-4)**: 凸族写进 optimizer 约束, 非凸族确定性 simplex 投影(§3.3)。✅
- **留一族 (Minor-1) / 双 CAGR 口径 (Minor-2) / max-Sharpe negative control (Minor-3)**: 全折入(§4.3 / §3.5 / §5)。✅
- **禁杠杆 (§7.11) / 复用 metrics (§7.8) / 总收益口径一致 (§3.3) / PIT 不直接适用(消费预计算净值)**: ✅
- **★ R2 折入 (5 项)**: **B1 path-metric bootstrap** = testing_ledger 存两列 strategy/ew、配对 bootstrap 分别重建两条净值路径再求 Δ, 绝不从超额收益路径算路径指标(§4.1); **B2 holdout 不读全网格** = holdout 只算冻结候选单候选 bootstrap, family-wise 仅 pre-holdout(§4.0/§4.1/§7 D1); **M1 诊断无泄漏** = 设计型收益诊断仅 ≤2023-05-31, §2 全样本数为描述性、分组 a priori 按 recipe(§2 caveat+§4.4); **M2 S8 真负控** = 排除在可部署选择规则外、永不可推荐(§5); **m1/m2/m3** = selection_trace.csv 审计 / haircut 是 stress-test 非真实证明(真验需 book replay)/ holdout 过后仍需 paper-小额实盘(§5)。✅
- **★ R3 折入 (4 Major + 2 Minor)**: **M1 全样本数移出设计包** = §2 改定性、数值入 §9 附录(post-holdout, 非设计输入); **M2 三态裁决** = holdout pass/inconclusive/fail, pass 须 ΔCalmar≥+0.10 ∧ P(ΔCalmar>0)≥80% ∧ ΔMDD<0 ∧ ΔCAGR 下界≥−3pp(§4.0); **M3 冻结 bootstrap 参数** = stationary block、期望块长 21、10000 抽、固定 seed 入 frozen_candidate.json、块长 10/63 敏感翻转→inconclusive(§4.1); **M4 固定 pre-holdout 三窗** 14-16/17-19/20-23.05(§4.3/§3.5); **m1** tie-break 去 max-Sharpe(§4.0); **m2** 数据驱动聚类须独立 scheme + ≤2023-05-31 + 入试验族(§4.4)。✅
- **残留开放风险 (GPT R3 标注的首要残留, 不可由设计消除, 只能披露)**: **单一 A 股市场 + 单一 ~3 年 holdout regime 无法证明可部署性** → §5 已要求实盘前 paper/小额实盘验证; 且 (ii) ~150 月度观测协方差噪声大 → 偏稳健族(S1/S2/S5/S6)、S3 重收缩、S8 永负控; (iii) E 组分散收益可能主导 → §4.3 留一族检验; (iv) pre-holdout 仍是单一市场 ~9 年, 残余单市场过拟合只能披露。

**自审结论**: **clean for GPT R4** —— R1(3B+4M+3m)+ R2(2B+2M+3m)+ R3(**0 Blocker** + 4M+2m)全部折入为可执行协议, 0 finding 婉拒; 残留=单一市场/单一 holdout regime 的不可消除风险(已披露 + 实盘前 paper 验证)。**预期管理: inconclusive/fail → 维持 EW 是可接受且预期的结论(§0/§4.0), 不把 null 硬凑成 pass。**

---

## 9. 附录 A — 全样本描述性诊断 (post-holdout / 非设计输入)

> **状态 = 占位 + 背景快照**。下列 **2014-2026 全样本**数字是**背景上下文, 不进入任何设计/选择决策**(§4.4); **权威版在 `frozen_candidate.json` 锁定 + holdout 记录后**随最终报告重生成。设计/判定实际消费的诊断一律仅用 ≤2023-05-31。当前(初始刻画 `_guorn20_characterize.py`)快照仅供阅读:
>
> - **EW(月度再平衡)**: CAGR 47.2%(252)/~45%(日历), 波动 22.7%, 夏普 1.82, 回撤 −32.0%, Calmar 1.47, Sortino 2.21; 分散比 1.30(组合 vol 22.7% vs 单券均 29.5%)。
> - **相关**: 全样本平均两两相关 0.539; 组内 A/B/D 0.66–0.83; E 组内 0.29、与他组 0.36–0.40; 最低相关券 MultiA_动量18 0.29 / MultiA_风险平价 0.36 / value_红利低波_v2 0.38 / ST_大市值 0.45。
> - **风险贡献(资本→风险)**: D 25%→29.3% / A 20%→27.2% / C 30%→23.4% / B 10%→12.5% / E 15%→7.7%(成长系 A+B+D 55% 资本扛 69% 风险; E 15% 资本仅 7.7% 风险)。
> - **§1 表中各策略的年化/回撤/夏普** = 果仁官方**全周期已发布**指标(基准 factsheet, 非本研究在全样本上为设计而算), 作为标的背景保留。
