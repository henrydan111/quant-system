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

SELF-REVIEW PREFLIGHT — completed before this GPT request:
Verdict: "clean for GPT". Checked CLAUDE.md §3 hard invariants + each quantitative-research principle below.
Key points self-checked: (a) no-lookahead lives ENTIRELY in the walk-forward weight step (weights at rebalance t use only data in [t-L, t)) — flagged as the #1 must-unit-test item ("weight_t ⊥ returns_{>=t}"); (b) total-return basis is consistent across all 20 series (no vectorized price-return mixing, §3.3); (c) unlevered gross=1x, long-only (§7.11); (d) all metrics route through result_analysis.metrics (§7.8), and the dormant src/portfolio_risk is NOT used (§3.4); (e) data integrity verified — reconstructed total-return and MDD match 果仁's exported summary to the penny; the CAGR delta is purely calendar-year vs 252-day annualization and cancels in relative comparison; (f) 8 schemes are pre-registered and ALL reported, with block-bootstrap + deflated-Sharpe for multiple testing.
Residual concerns for the reviewer: (1) Is the chosen objective (maximize OOS Calmar / cut MDD, with CAGR >= EW - 3% absolute tolerance) sound, and is a -3% CAGR tolerance defensible or arbitrary? (2) Given the EW baseline is rebalanced-to-target monthly, is forcing the SAME rebalance convention on EW the correct apples-to-apples control, or does monthly rebalancing itself inject a "rebalancing alpha" that should be isolated? (3) With only ~150 monthly observations and 20 highly-correlated assets (mean pairwise corr 0.54), is the candidate set correctly biased toward robust risk-based schemes (inverse-vol / ERC / HRP / two-stage) over covariance-inversion schemes (min-var / max-Sharpe), and is Ledoit-Wolf shrinkage sufficient? (4) Is keeping all 20 books with a floor (vs allowing zeros) the right anti-overfit choice, or does the floor merely hide that several A/B/D-group books are near-redundant (intra-group corr 0.66-0.83)?

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
> **状态**: 设计稿 (待 self-review → GPT cross-review → 用户确认后实施)。NON-FORMAL research artifact。
> **Last updated**: 2026-06-24

---

## 0. 一句话结论 (先讲清楚这件事有多难)

等权(EW)**本身已经是一个很强的基准**: 实测 EW(月度再平衡) 夏普 **1.82**、最大回撤 **−32%**、年化 **~45%(日历口径)/47%(252口径)**。
EW 的夏普**高于 20 个策略中的 19 个**(只有 ST_大市值 1.90 略高), 因为它已经吃掉了绝大部分分散化收益(分散比 1.30)。
所以"在收益和回撤上都严格优于 EW(Pareto 占优)"是一个**高门槛**目标, 不能假设一定能达到。

诚实的机会判断 (下文用数据论证):
- **几乎确定能改善**的是 **回撤 + 风险调整后收益(Calmar/Sharpe)**: EW 把过多*风险*(而非资本)押在了高波成长/微盘上 —— 风险型加权能把回撤从 −32% 压到更低。
- **不确定、需样本外证明**的是 **能否在压低回撤的同时不损失(甚至提高)年化**: 因为高波动的成长/微盘策略恰恰也是**高夏普**的, 压低它们会牺牲收益。能否两全取决于能否用低相关分散券(ST、基金轮动、红利低波)和高 Calmar 券(净利润断层、大制造 GARP)做出"风险换得起的收益"。
- 本计划的**判定口径**因此定为: **以样本外 Calmar/回撤为主目标, 年化不显著低于 EW; 并独立检验是否存在稳健的 Pareto 占优方案**。是否改为"严格 Pareto 占优"或"最大化夏普", 见 §7 待决策项。

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

## 2. 数据诊断 (为什么"机会"主要在风险端, 用实测数据说话)

> 全部基于已对齐的 20×3028 日收益矩阵 (`guorn20_daily_returns.parquet`)。**数据完整性已校验**:
> 重建的总收益与最大回撤与果仁官方逐位一致(年化差异仅来自日历 vs 252 年化口径, 在相对比较中抵消)。

**诊断 1 — EW 已经很强, 门槛高。** EW(月度再平衡) 实测: CAGR 47.2%(252口径)/~45%(日历), 波动 22.7%, **夏普 1.82**, 回撤 **−32.0%**, Calmar 1.47, Sortino 2.21。EW 波动 22.7% < 单券平均波动 29.5% (分散比 1.30) —— 已实现可观分散。

**诊断 2 — 相关性高但有结构 (分散有限但非零)。** 全样本平均两两相关 **0.539**。块状结构清晰:
- A/B/D(成长/微盘/GARP/周期) 互相高度相关 (组内 0.66–0.83, 组间 0.63–0.83) —— 大量冗余。
- C(价值红利低波) 与成长端相关 ~0.53, 组内 0.59。
- **E(ST+基金) 是真分散券**: 组内仅 0.29, 与他组 0.36–0.40。最低相关券: MultiA_动量18 (0.29)、MultiA_风险平价 (0.36)、value_红利低波_v2 (0.38)、ST_大市值 (0.45)。

**诊断 3 — EW 的"资本等权"其实是"风险不等权", 风险压在成长端。** 风险贡献分解(全样本年化协方差):

| 风格组 | 资本权重 | 风险贡献 |
|---|---|---|
| D 成长周期分析师 | 25% | **29.3%** |
| A 微盘成长动量 | 20% | **27.2%** |
| C 价值红利低波 | 30% | 23.4% |
| B GARP质量 | 10% | 12.5% |
| E 特殊(ST/基金) | 15% | **7.7%** |

→ 成长系(A+B+D)= 55% 资本但 **69% 风险**; 分散券(E)= 15% 资本却只贡献 **7.7% 风险**。**这就是杠杆点**: 风险型加权会把资本从高波成长端移向 C/E, 压低回撤。

**诊断 4 — 核心张力(为什么 Pareto 占优难)。** 高波券(A/B sm_01* 夏普 1.5–1.7、大制造 GARP 1.64、ST 1.90)**本身也是高夏普**; 低波价值券夏普反而低(果仁口径 1.06–1.32)。**单纯按波动压低高波券 = 牺牲收益甚至牺牲夏普。** 能两全的唯一路径是利用 (a) 低相关分散券(E 组虽然 standalone 夏普低, 但相关 0.36, 分散价值大) 与 (b) 高 Calmar 券(净利润断层、大制造 GARP、ST) —— 这正是 min-var / max-diversification / HRP / 风险预算类方法的用武之地, 也是必须**样本外**证明而非假设的部分。

---

## 3. 研究框架与方法 (How)

把这看作一个 **fund-of-funds 资本配置(book 层)问题**: 不动各策略内部选股, 只决定"给每个 book 多少钱、何时再平衡"。被优化的"资产"= 20 条策略级日收益。

### 3.1 顶层模型与约束
- 权重 `w_i ≥ 0`, `Σw_i = 1`, **unlevered(gross = 1×, 满仓或留极小现金, 禁止杠杆 — CLAUDE.md §7.11)**。
- 每个再平衡日用**截至该日的历史数据**算目标权重 → 持有至下个再平衡日 → 期间权重随收益漂移 → 再平衡回目标。
- 顶层再平衡的**交易成本**按 |Δw| 计提(book 间挪资金), 用保守 bps(并做敏感性), 直接进净值。

### 3.2 基准 (Baseline)
- **S0 = EW**: 1/20, 月度再平衡回 1/N (主基准, = 用户当前实盘形态)。附 buy-&-hold 漂移变体。

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

协方差: Ledoit-Wolf 收缩(20 资产稳健); 波动: trailing/EWMA。约束(**D2 已锁定 = 保留全部 20 券**): `floor ≤ w_i ≤ cap`, `Σw=1`, long-only; floor ∈ {1%, 2.5%}, cap ∈ {10%, 15%}。"允许置零/集中版"仅作对照。所有方案输出后再统一施加 floor/cap 重归一(或在凸优化中直接作为约束)。

### 3.4 样本外(walk-forward)协议 —— **这是整个研究成立的关键**
- **预热**: 前 L 天仅用于估计第一组权重(不计入业绩)。
- **再平衡频率**: 月度(基准), 季度(变体)。
- 在每个再平衡日 t: 仅用窗口 `[t−L, t)` (或扩张窗口) 估计输入 → 解权重 → 应用于 `(t, t+频率]` → 记录**已实现**收益。**任何权重都不使用其持有期及之后的数据。**
- 拼接 → 每个方案一条**结构上即样本外**的日收益曲线。
- **末段独立确认**: 另把最后 ~3 年(2023-06..2026-06)单列, 作为"只看一次"的新鲜样本复核。

### 3.5 评估指标 (全部经 `src/result_analysis/metrics.py`, 全部样本外)
CAGR(日历口径以对齐果仁)、波动、夏普(rf 对齐果仁 ~3%)、Sortino、最大回撤、Calmar、最差滚动 12 月、月度跑赢 EW 比率、**年化权重换手(→成本)**、扣成本后 CAGR。并按 3 个子区间(2014-18 / 19-22 / 23-26)分别报告。

---

## 4. 反过拟合与证伪 (Research Integrity — 不可妥协)

对照 CLAUDE.md §7 (无前视、仅时序切分、OOS 神圣、多重检验、禁对冲词)。组合权重在 12 年历史上优化是**经典过拟合陷阱**, 必须:

1. **绝不**把全样本最优权重当结论。全样本有效前沿仅作"事后天花板"参考并明确标注**不可投资**。
2. **事前锁定方案清单**(§3.3); 报告**全部**方案, 不只赢家(§7.3 多重检验诚实)。
3. **参数敏感性而非参数寻优**: 在 (L ∈ {126,252,504}) × (频率 ∈ {月,季}) × (cap ∈ {无,10%,15%}) 网格上展示稳健性; 推荐方案按**稳健性**(跨格一致)而非最优格挑选。
4. **子区间稳定性**: 赢家须在 ≥2/3 子区间跑赢 EW, 而非仅靠某一段。
5. **Block-bootstrap**(分块自助) 检验 (方案−EW) 的 Calmar/Sharpe 差是否在"试了 ~8 个方案"后仍可与运气区分 (deflated Sharpe / 多重检验校正)。
6. **留一策略法**: 逐一剔除单个 book 重跑, 确认结论不是单券(尤其 ST_大市值 / MultiA)假象。
7. **成本敏感性**: 所有结论在合理顶层再平衡成本下复核。
8. **继承性乐观偏差 caveat** (memory `project_guorn_parity`): 底层果仁净值可能因"微盘涨停可买"而偏乐观, 故**绝对水平存疑**; **相对加权结论更稳健**但仍继承该偏差。注意: 受此偏差影响最大的正是高波成长券 → 任何**下调**它们权重的方案反而更保守, 这对结论方向是有利的安全垫。

---

## 5. 交付物
1. ✅ 提取脚本 `_guorn20_extract_recipes.py` + 特征刻画 `_guorn20_characterize.py` (已完成)。
2. ✅ 对齐日收益矩阵 `guorn20_daily_returns.parquet` + 元数据 `guorn20_meta.csv` (已生成)。
3. ⏳ 加权/回测模块 (workspace; 复用 `result_analysis.metrics`; 协方差/优化用 cvxpy/numpy 直接写 —— **不**依赖 dormant 的 `src/portfolio_risk`, §3.4)。
4. ⏳ 结果报告 (markdown): 全方案对比表 + 样本外净值曲线 + 子区间/敏感性/bootstrap + **推荐权重**及理由 + caveat。
5. ⏳ 可选: MLflow 记录本次对比实验; dashboard 提及。

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
| D1 | **主目标** | ✅ **(b) 最大化样本外 Calmar / 压回撤, 年化不显著低于 EW**; 同时把 (a) 严格 Pareto 占优作为附带检验报告。判定阈值: 推荐方案须样本外 **Calmar > EW 且 MDD < EW**, 且 **CAGR ≥ EW − 3%(绝对)**(容差待 GPT 复核是否合理)。 |
| D2 | **权重约束** | ✅ **(a) 保留全部 20 券 + 上下限**: 权重下限 `w_i ≥ floor`(候选 floor=1% 或 0.5×EW=2.5%)、上限 `w_i ≤ cap`(候选 10%/15%=2×/3×EW)。"允许置零/集中版"**仅作对照**展示, 不作为推荐输出。 |
| D3 | **顶层再平衡频率/成本** | 默认**月度 + 季度变体**, 成本做敏感性 (无需单独拍板)。 |
| D4 | **范围** | 默认**仅再加权**(保留 20 券, 无择时叠加层) —— 符合"对这 20 个再加权"原意。 |

> floor/cap 的具体数值与 CAGR 容差作为 §4.3 敏感性网格的一部分, 按稳健性而非最优格选定; 推荐方案给出一个主用配置 + 敏感带。

---

## 8. 自审 (Self-review, 对照 §3 硬不变量 + §7 量化研究原则)

- **无前视 (§7.1)**: walk-forward 每个权重仅用 `[t−L,t)` 历史, 应用于未来期; 协方差/波动/Calmar 全 trailing。✅ 设计满足; 实现时须单测"权重_t ⊥ 收益_{≥t}"。
- **仅时序切分、OOS 神圣 (§7.2–7.3)**: 无随机切分; 末段 3 年只看一次; 全样本最优仅作标注的天花板。✅
- **总收益口径一致 (§3.3)**: 20 条曲线均为果仁总收益(含分红), 互相可比; 不与 Vectorized 价格收益混用。✅
- **禁杠杆 (§7.11)**: gross=1×, long-only, 不放大市场中性。✅
- **复用而非重造 (§7.8)**: 全部指标走 `result_analysis.metrics`; 不碰 dormant `portfolio_risk`。✅
- **多重检验诚实 (§7.3/§7.10)**: 事前锁定 8 方案, 全报告, bootstrap + deflated-Sharpe 校正; 不挑赢家格。✅
- **禁对冲词 (§7.10)**: 报告结论须给确定口径或明确标"未验证 + 证伪方案"。✅ (本文 §0 已对"能否两全"明确标为待样本外验证)
- **PIT/ledger (§3.2)**: 本研究消费的是**预计算策略净值**, 不直接读 PIT 字段, 故 PIT-ledger 不变量不直接适用; 唯一前视风险在 walk-forward 实现, 已列为必测项。✅
- **继承偏差已披露 (§4.8)**: 果仁微盘乐观偏差已声明, 且方向对"下调高波券"结论有利。✅
- **开放风险**: (i) 月度再平衡的"再平衡回目标"会引入与 EW 不同的隐含再平衡 alpha, 须对 EW 用同口径再平衡以公平对比; (ii) 12 年仅 ~150 个月度观测, 协方差估计噪声大 → 偏向 S1/S2/S5/S6 等稳健法, 对 S3/S8 重收缩; (iii) 子区间 2014-15 含微盘极端行情, 须确认结论不被单一 regime 主导。

**自审结论**: **clean for GPT** —— 方法学满足 §3/§7; 待用户就 D1/D2 拍板后, 即可定稿送 GPT cross-review 再进入 M3 实现。
