# arXiv Research-Direction Map

*Generated 2026-06-10 from the top 80 value-ranked papers (`ranked_papers.parquet`). This is the knowledge framework's deliverable: the arXiv firehose organized into actionable directions, clustered by OUR research-frontier taxonomy and tagged with whether each is buildable on data we have.*

**How to read:** dimensions are ordered by where deployable alpha lives for our book. `FRONTIER_OPEN` = we have the data and have barely mined it (build now). `METHOD` = improves how we combine what we have. `FRONTIER_BLOCKED` = great direction, needs data we lack. `SATURATED` = the 182-book already spans it. The score is a triage prior; the abstract snippet + your read is the verdict.

> A paper is a **hypothesis source, never evidence**. Any factor it inspires still runs the full IS-only → sealed-OOS lifecycle, and must pass the size/industry-neutralized **marginal-contribution** test vs the catalog (CLAUDE.md §3.5, §7).

## Directions summary

| Dimension | Our status | Build? | # in top | Top score | Coverage note |
|---|---|---|---|---|---|
| Earnings events & drift | FRONTIER_OPEN | ✅ | 5 | 0.800 | forecast/express + statement disclosure dates available; not mined |
| Behavioral & chip-distribution | FRONTIER_OPEN | ✅ | 5 | 0.733 | cyq_perf (筹码 cost-basis) approved — disposition/overhang directly buildable |
| Informed order flow & positioning | FRONTIER_OPEN | ✅ | 4 | 0.668 | moneyflow/lhb/margin/hk_hold/block_trade all approved, ~0 factors built |
| Ownership & insider activity | FRONTIER_OPEN | ✅ | 3 | 0.523 | holder_number + stk_holdertrade approved, unmined |
| Seasonality & calendar | FRONTIER_OPEN | ✅ | 1 | 0.370 | buildable on price+dates; lightly covered |
| Machine-learning methodology | METHOD | ✅ | 34 | 0.611 | improves how we COMBINE existing factors; model_zoo target |
| Factor-zoo / multiple-testing stats | METHOD | · | 6 | 0.534 | directly informs our promotion gates / marginal-contribution rule |
| Macro & factor timing | METHOD | ✅ | 4 | 0.546 | index series only; equity-factor-timing angle is usable |
| Portfolio construction & costs | METHOD | ✅ | 3 | 0.354 | portfolio_risk module + execution; deployment-side value |
| Text / NLP / LLM signals | FRONTIER_BLOCKED | ⛔ | 11 | 0.508 | HIGH-VALUE build target — no text corpus yet |
| Microstructure / high-frequency | FRONTIER_BLOCKED | ⛔ | 3 | 0.319 | only daily bars — blocked (but overnight/intraday-from-daily partial) |
| Momentum & reversal | SATURATED | ✅ | 1 | 0.300 | mom_/rev_ prefixes already span this |

# FRONTIER_OPEN

*We HAVE the data, have barely mined it — the highest-value target. A new factor here can reach formal eligibility today.*

## Earnings events & drift  ·  5 papers

- **Our coverage:** forecast/express + statement disclosure dates available; not mined
- **Data:** `earnings_preannounce`→forecast/express; `fundamentals`→income/balancesheet/cashflow/pit_fundamentals/indicators
- **Buildable now:** yes

### [1] Which Voices Move Markets? Speaker Identity and the Cross-Section of Post-Earnings Returns  *(score 0.800, 2026 · 0 cites)*
We utilize FinBERT, a domain-specific transformer model, to parse 6.5 million sentences from 16,428 S&P 500 quarterly earnings call transcripts (2015-2025) and demonstrate that post-earnings stock returns are not equally affected by all speakers in a conference call. Our section-weighted sentiment, with empirically der…
[https://arxiv.org/abs/2604.13260v1](https://arxiv.org/abs/2604.13260v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [5] Sequential Cauchy Combination Test for Multiple Testing Problems with Financial Applications  *(score 0.624, 2023)*
We introduce a simple tool to control for false discoveries and identify individual signals in scenarios involving many tests, dependent test statistics, and potentially sparse signals. The tool applies the Cauchy combination test recursively on a sequence of expanding subsets of $p$-values and is referred to as the se…
[https://arxiv.org/abs/2303.13406v2](https://arxiv.org/abs/2303.13406v2)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [9] Customer Momentum  *(score 0.570, 2023)*
This paper examines customer momentum, defined as a positive relationship between a firm's returns and past returns of its customers. I confirm previous evidence (Cohen and Frazzini 2008) that customer momentum is both statistically and economically significant. Long-short equally-weighted (value-weighted) decile portf…
[https://arxiv.org/abs/2301.11394v1](https://arxiv.org/abs/2301.11394v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [30] Capturing dynamics of post-earnings-announcement drift using genetic algorithm-optimised supervised learning  *(score 0.383, 2020 · 1 cites)*
While Post-Earnings-Announcement Drift (PEAD) is one of the most studied stock market anomalies, the current literature is often limited in explaining this phenomenon by a small number of factors using simpler regression methods. In this paper, we use a machine learning based approach instead, and aim to capture the PE…
[https://arxiv.org/abs/2009.03094v1](https://arxiv.org/abs/2009.03094v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [43] Portfolio optimization when expected stock returns are determined by exposure to risk  *(score 0.350, 2009 · 4 cites)*
It is widely recognized that when classical optimal strategies are applied with parameters estimated from data, the resulting portfolio weights are remarkably volatile and unstable over time. The predominant explanation for this is the difficulty of estimating expected returns accurately. In this paper, we modify the $…
[https://arxiv.org/abs/0906.2271v1](https://arxiv.org/abs/0906.2271v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

## Behavioral & chip-distribution  ·  5 papers

- **Our coverage:** cyq_perf (筹码 cost-basis) approved — disposition/overhang directly buildable
- **Data:** `chip_distribution`→cyq_perf; `price_ohlcv`→market_daily
- **Buildable now:** yes

### [2] Replication of Reference-Dependent Preferences and the Risk-Return Trade-Off in the Chinese Market  *(score 0.733, 2025)*
This study replicates the findings of Wang et al. (2017) on reference-dependent preferences and their impact on the risk-return trade-off in the Chinese stock market, a unique context characterized by high retail investor participation, speculative trading behavior, and regulatory complexities. Capital Gains Overhang (…
[https://arxiv.org/abs/2505.20608v1](https://arxiv.org/abs/2505.20608v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [4] Sentiment Feedback in Equity Markets: Asymmetries, Retail Heterogeneity, and Structural Calibration  *(score 0.653, 2025 · 0 cites)*
We study how sentiment shocks propagate through equity returns and investor clientele using four independent proxies with sign-aligned kappa-rho parameters. A structural calibration links a one standard deviation innovation in sentiment to a pricing impact of 1.06 basis points with persistence parameter rho = 0.940, yi…
[https://arxiv.org/abs/2509.11970v1](https://arxiv.org/abs/2509.11970v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [27] High-Throughput Asset Pricing  *(score 0.414, 2023 · 2 cites)*
We apply empirical Bayes (EB) to mine data on 136,000 long-short strategies constructed from accounting ratios, past returns, and ticker symbols. This ``high-throughput asset pricing'' matches the out-of-sample performance of top journals while eliminating look-ahead bias. Naively mining for the largest Sharpe ratios l…
[https://arxiv.org/abs/2311.10685v3](https://arxiv.org/abs/2311.10685v3)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [66] A Security Price Volatile Trading Conditioning Model  *(score 0.300, 2010)*
We develop a theoretical trading conditioning model subject to price volatility and return information in terms of market psychological behavior, based on analytical transaction volume-price probability wave distributions in which we use transaction volume probability to describe price volatility uncertainty and intens…
[https://arxiv.org/abs/1001.0656v2](https://arxiv.org/abs/1001.0656v2)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [67] Positive skewness, anti-leverage, reverse volatility asymmetry, and short sale constraints: Evidence from the Chinese markets  *(score 0.300, 2015 · 0 cites)*
There are some statistical anomalies in the Chinese stock market, i.e., positive return skewness, anti-leverage effect (positive returns induce higher volatility than negative returns); and reverse volatility asymmetry (contemporaneous return-volatility correlation is positive). In this paper, we first confirm the exis…
[https://arxiv.org/abs/1511.01824v1](https://arxiv.org/abs/1511.01824v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

## Informed order flow & positioning  ·  4 papers

- **Our coverage:** moneyflow/lhb/margin/hk_hold/block_trade all approved, ~0 factors built
- **Data:** `moneyflow`→moneyflow; `lhb`→top_list/top_inst; `margin`→margin_detail; `northbound`→hk_hold; `block_trade`→block_trade
- **Buildable now:** yes

### [3] Information Propagation Across Investor Types: Transfer Entropy Networks in the Korean Equity Market  *(score 0.668, 2026 · 0 cites)*
Whether heterogeneous investor flows transmit private information across stocks or merely reflect coordinated responses to public signals remains an open question in market microstructure. We construct Transfer Entropy (TE) networks from investor-type flows -- foreign, institutional, and individual -- for \numNStocks{}…
[https://arxiv.org/abs/2603.20271v1](https://arxiv.org/abs/2603.20271v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [7] An Infinite-Dimensional Insider Trading Game  *(score 0.580, 2026 · 0 cites)*
We generalize the seminal framework of Kyle (1985) to a many-asset setting, bridging the gap between informed-trading theory and modern trading practices. Specifically, we formulate an infinite-dimensional Bayesian trading game in which the informed trader's private information may concern arbitrary aspects of the cros…
[https://arxiv.org/abs/2602.21125v3](https://arxiv.org/abs/2602.21125v3)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [23] Market Microstructure During Financial Crisis: Dynamics of Informed and Heuristic-Driven Trading  *(score 0.466, 2016 · 21 cites)*
We implement a market microstructure model including informed, uninformed and heuristic-driven investors, which latter behave in line with loss-aversion and mental accounting. We show that the probability of informed trading (PIN) varies significantly during 2008. In contrast, the probability of heuristic-driven tradin…
[https://arxiv.org/abs/1606.03590v1](https://arxiv.org/abs/1606.03590v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [44] Residual Supply and the Price of Risk Absorption  *(score 0.348, 2026)*
When redeeming open-end funds sell and natural buyers do not step in at once, some limited-capital investor must take the other side and carry the inventory until prices recover. This paper asks what return that investor requires. A continuous-time market-clearing model delivers an expected-return restriction in which …
[https://arxiv.org/abs/2605.30672v1](https://arxiv.org/abs/2605.30672v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

## Ownership & insider activity  ·  3 papers

- **Our coverage:** holder_number + stk_holdertrade approved, unmined
- **Data:** `holder_number`→holder_number; `insider_holder`→stk_holdertrade
- **Buildable now:** yes

### [15] Foreign Signal Radar  *(score 0.523, 2025)*
We introduce a new machine learning approach to detect value-relevant foreign information for both domestic and multinational companies. Candidate foreign signals include lagged returns of stock markets and individual stocks across 47 foreign markets. By training over 100,000 models, we capture stock-specific, time-var…
[https://arxiv.org/abs/2504.07855v1](https://arxiv.org/abs/2504.07855v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [47] Incorporating Interactive Facts for Stock Selection via Neural Recursive ODEs  *(score 0.340, 2022 · 0 cites)*
Stock selection attempts to rank a list of stocks for optimizing investment decision making, aiming at minimizing investment risks while maximizing profit returns. Recently, researchers have developed various (recurrent) neural network-based methods to tackle this problem. Without exceptions, they primarily leverage hi…
[https://arxiv.org/abs/2210.15925v1](https://arxiv.org/abs/2210.15925v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [58] Asset Prices with Investor Protection and Past Information  *(score 0.313, 2019)*
In this paper, we consider a dynamic asset pricing model in an approximate fractional economy to address empirical regularities related to both investor protection and past information. Our newly developed model features not only in terms with a controlling shareholder who diverts a fraction of the output, but also goo…
[https://arxiv.org/abs/1911.00281v2](https://arxiv.org/abs/1911.00281v2)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

## Seasonality & calendar  ·  1 papers

- **Our coverage:** buildable on price+dates; lightly covered
- **Data:** `price_ohlcv`→market_daily
- **Buildable now:** yes

### [32] An Empirical Study on the Holiday Effect of China's Time-Honored Companies  *(score 0.370, 2023)*
The stock segment of China's time-honored brand enterprises has an important position in our securities stock market. The holiday effect is one of the market anomalies that occur in the securities market, which refers to the phenomenon that the stock market has significantly different returns than other trading days ar…
[https://arxiv.org/abs/2308.00702v1](https://arxiv.org/abs/2308.00702v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

# METHOD

*Cross-cutting methodology — improves how we COMBINE existing factors / construct portfolios, not a new raw signal. Feeds model_zoo / portfolio_risk / the gates.*

## Machine-learning methodology  ·  34 papers

- **Our coverage:** improves how we COMBINE existing factors; model_zoo target
- **Data:** `price_ohlcv`→market_daily; `fundamentals`→income/balancesheet/cashflow/pit_fundamentals/indicators
- **Buildable now:** yes

### [6] Constructing long-short stock portfolio with a new listwise learn-to-rank algorithm  *(score 0.611, 2021 · 1 cites)*
Factor strategies have gained growing popularity in industry with the fast development of machine learning. Usually, multi-factors are fed to an algorithm for some cross-sectional return predictions, which are further used to construct a long-short portfolio. Instead of predicting the value of the stock return, emergin…
[https://arxiv.org/abs/2104.12484v1](https://arxiv.org/abs/2104.12484v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [8] Empirical Asset Pricing via Ensemble Gaussian Process Regression  *(score 0.572, 2022 · 7 cites)*
We introduce an ensemble learning method based on Gaussian Process Regression (GPR) for predicting conditional expected stock returns given stock-level and macro-economic information. Our ensemble learning approach significantly reduces the computational complexity inherent in GPR inference and lends itself to general …
[https://arxiv.org/abs/2212.01048v3](https://arxiv.org/abs/2212.01048v3)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [10] Deep Learning Enhanced Multi-Day Turnover Quantitative Trading Algorithm for Chinese A-Share Market  *(score 0.567, 2025)*
This paper presents a sophisticated multi-day turnover quantitative trading algorithm that integrates advanced deep learning techniques with comprehensive cross-sectional stock prediction for the Chinese A-share market. Our framework combines five interconnected modules: initial stock selection through deep cross-secti…
[https://arxiv.org/abs/2506.06356v1](https://arxiv.org/abs/2506.06356v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [16] Semiparametric Conditional Factor Models in Asset Pricing  *(score 0.517, 2021)*
We introduce a simple and tractable methodology for estimating semiparametric conditional latent factor models. Our approach disentangles the roles of characteristics in capturing factor betas of asset returns from ``alpha.'' We construct factors by extracting principal components from Fama-MacBeth managed portfolios. …
[https://arxiv.org/abs/2112.07121v5](https://arxiv.org/abs/2112.07121v5)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [17] Cyber risk and the cross-section of stock returns  *(score 0.510, 2024 · 6 cites)*
We extract firms' cyber risk with a machine learning algorithm measuring the proximity between their disclosures and a dedicated cyber corpus. Our approach outperforms dictionary methods, uses full disclosure and not devoted-only sections, and generates a cyber risk measure uncorrelated with other firms' characteristic…
[https://arxiv.org/abs/2402.04775v2](https://arxiv.org/abs/2402.04775v2)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [19] ReSGA: A Large Tail Risk Model for Learning Value-at-Risk and Expected Shortfall  *(score 0.502, 2026 · 0 cites)*
Learning Value-at-Risk (VaR) and Expected Shortfall (ES) is important for managing financial risks effectively. Existing approaches with limited parameters are vulnerable to model misspecification in the era of big data. To address this limitation, we propose a large tail risk model, the retrieval-enhanced self-groupin…
[https://arxiv.org/abs/2606.04576v1](https://arxiv.org/abs/2606.04576v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [21] Machine Learning Enhanced Multi-Factor Quantitative Trading: A Cross-Sectional Portfolio Optimization Approach with Bias Correction  *(score 0.479, 2025)*
Rolling-window factor pipelines for Chinese A-share markets contain a subtle but costly flaw: daily price-move limits (+/-10% main-board, +/-20% STAR/ChiNext) render a fraction of closing prices non-executable, yet standard implementations ingest these values before any row-filtering runs. The contaminated aggregates p…
[https://arxiv.org/abs/2507.07107v2](https://arxiv.org/abs/2507.07107v2)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [22] KAN based Autoencoders for Factor Models  *(score 0.473, 2024)*
Inspired by recent advances in Kolmogorov-Arnold Networks (KANs), we introduce a novel approach to latent factor conditional asset pricing models. While previous machine learning applications in asset pricing have predominantly used Multilayer Perceptrons with ReLU activation functions to model latent factor exposures,…
[https://arxiv.org/abs/2408.02694v1](https://arxiv.org/abs/2408.02694v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

## Factor-zoo / multiple-testing stats  ·  6 papers

- **Our coverage:** directly informs our promotion gates / marginal-contribution rule
- **Data:** —
- **Buildable now:** n/a

### [12] Labor Income Risk and the Cross-Section of Expected Returns  *(score 0.534, 2023 · 2034 cites)*
This paper explores asset pricing implications of unemployment risk from sectoral shifts. I proxy for this risk using cross-industry dispersion (CID), defined as a mean absolute deviation of returns of 49 industry portfolios. CID peaks during periods of accelerated sectoral reallocation and heightened uncertainty. I fi…
[https://arxiv.org/abs/2301.09173v1](https://arxiv.org/abs/2301.09173v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [14] Publication Bias in Asset Pricing Research  *(score 0.525, 2022 · 6 cites)*
Researchers are more likely to share notable findings. As a result, published findings tend to overstate the magnitude of real-world phenomena. This bias is a natural concern for asset pricing research, which has found hundreds of return predictors and little consensus on their origins. Empirical evidence on publicatio…
[https://arxiv.org/abs/2209.13623v3](https://arxiv.org/abs/2209.13623v3)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [45] Controlling False Discovery Rates under Cross-Sectional Correlations  *(score 0.341, 2021)*
We consider controlling the false discovery rate for testing many time series with an unknown cross-sectional correlation structure. Given a large number of hypotheses, false and missing discoveries can plague an analysis. While many procedures have been proposed to control false discovery, most of them either assume i…
[https://arxiv.org/abs/2102.07826v2](https://arxiv.org/abs/2102.07826v2)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [48] Forking paths in financial economics  *(score 0.328, 2023)*
We argue that spanning large numbers of degrees of freedom in empirical analysis allows better characterizations of effects and thus improves the trustworthiness of conclusions. Our ideas are illustrated in three studies: equity premium prediction, asset pricing anomalies and risk premia estimation. In the first, we fi…
[https://arxiv.org/abs/2401.08606v1](https://arxiv.org/abs/2401.08606v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [73] A New Spatiotemporal Correlation Anomaly Detection Method that Integrates Contrastive Learning and Few-Shot Learning in Wireless Sensor Networks  *(score 0.284, 2025)*
Detecting anomalies in the data collected by WSNs can provide crucial evidence for assessing the reliability and stability of WSNs. Existing methods for WSN anomaly detection often face challenges such as the limited extraction of spatiotemporal correlation features, the absence of sample labels, few anomaly samples, a…
[https://arxiv.org/abs/2506.00420v1](https://arxiv.org/abs/2506.00420v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [77] The Cross-section of Expected Returns on Penny Stocks: Are Low-hanging Fruits Not-so Sweet?  *(score 0.282, 2016 · 1 cites)*
In this paper, we study the determinants of expected returns on the listed penny stocks from two perspectives. Traditionally financial economics literature has been devoted to study the macro and micro determinants of expected returns on stocks (Subrahmanyam, 2010). Very few research has been carried out on penny stock…
[https://arxiv.org/abs/1610.01338v1](https://arxiv.org/abs/1610.01338v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

## Macro & factor timing  ·  4 papers

- **Our coverage:** index series only; equity-factor-timing angle is usable
- **Data:** `index_membership`→reference/index_weight
- **Buildable now:** yes

### [11] Skewness Dispersion and Stock Market Returns  *(score 0.546, 2026)*
Cross-sectional dispersion in firm-level realized skewness is significantly and negatively related to future stock market returns. The predictive power of skewness dispersion is robust to in-sample and out-of-sample estimation and is incremental over a broad set of existing predictors, with only a few alternatives reta…
[https://arxiv.org/abs/2604.07870v1](https://arxiv.org/abs/2604.07870v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [13] Deep Learning for Conditional Asset Pricing Models  *(score 0.531, 2025)*
We propose a new pseudo-Siamese Network for Asset Pricing (SNAP) model, based on deep learning approaches, for conditional asset pricing. Our model allows for the deep alpha, deep beta and deep factor risk premia conditional on high dimensional observable information of financial characteristics and macroeconomic state…
[https://arxiv.org/abs/2509.04812v1](https://arxiv.org/abs/2509.04812v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [50] Generalized Dynamic Factor Models and Volatilities: Consistency, rates, and prediction intervals  *(score 0.326, 2018 · 41 cites)*
Volatilities, in high-dimensional panels of economic time series with a dynamic factor structure on the levels or returns, typically also admit a dynamic factor decomposition. We consider a two-stage dynamic factor model method recovering the common and idiosyncratic components of both levels and log-volatilities. Spec…
[https://arxiv.org/abs/1811.10045v2](https://arxiv.org/abs/1811.10045v2)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [79] A new decomposition approach to modeling financial returns: Conditioning sign on magnitude  *(score 0.275, 2026 · 0 cites)*
Changes in volatility contain valuable information about the likelihood of positive versus negative returns. We propose a new approach to modeling financial returns that exploits this insight by decomposing returns into sign and magnitude (absolute value) components, with magnitude closely related to volatility. The jo…
[https://arxiv.org/abs/2606.04153v1](https://arxiv.org/abs/2606.04153v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

## Portfolio construction & costs  ·  3 papers

- **Our coverage:** portfolio_risk module + execution; deployment-side value
- **Data:** `price_ohlcv`→market_daily
- **Buildable now:** yes

### [41] Isotropic Correlation Models for the Cross-Section of Equity Returns  *(score 0.354, 2024 · 1 cites)*
This note discusses some of the aspects of a model for the covariance of equity returns based on a simple "isotropic" structure in which all pairwise correlations are taken to be the same value. The effect of the structure on feasible values for the common correlation of returns and on the "effective degrees of freedom…
[https://arxiv.org/abs/2411.08864v4](https://arxiv.org/abs/2411.08864v4)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [46] Fundamental properties of linear factor models  *(score 0.341, 2024)*
We study conditional linear factor models in the context of asset pricing panels. Our analysis focuses on conditional means and covariances to characterize the cross-sectional and inter-temporal properties of returns and factors as well as their interrelationships. We also review the conditions outlined in Kozak and Na…
[https://arxiv.org/abs/2409.02521v3](https://arxiv.org/abs/2409.02521v3)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [76] DSPO: An End-to-End Framework for Direct Sorted Portfolio Construction  *(score 0.283, 2024 · 1 cites)*
In quantitative investment, constructing characteristic-sorted portfolios is a crucial strategy for asset allocation. Traditional methods transform raw stock data of varying frequencies into predictive characteristic factors for asset sorting, often requiring extensive manual design and misalignment between prediction …
[https://arxiv.org/abs/2405.15833v1](https://arxiv.org/abs/2405.15833v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

# FRONTIER_BLOCKED

*Promising dimension but we LACK the data — value is as a DATA-ACQUISITION direction, not buildable today.*

## Text / NLP / LLM signals  ·  11 papers

- **Our coverage:** HIGH-VALUE build target — no text corpus yet
- **Data:** `news_text`→—
- **Buildable now:** NO — need news_text

### [18] Structured Event Representation and Stock Return Predictability  *(score 0.508, 2025)*
We find that event features extracted by large language models (LLMs) are effective for text-based stock return prediction. Using a pre-trained LLM to extract event features from news articles, we propose a novel deep learning model based on structured event representation (SER) and attention mechanisms to predict stoc…
[https://arxiv.org/abs/2512.19484v1](https://arxiv.org/abs/2512.19484v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [20] Autonomous Market Intelligence: Agentic AI Nowcasting Predicts Stock Returns  *(score 0.489, 2026 · 0 cites)*
Can fully agentic AI nowcast stock returns? We deploy a state-of-the-art Large Language Model to evaluate the attractiveness of each Russell 1000 stock daily, starting from April 2025 when AI web interfaces enabled real-time search. Our data contribution is unique along three dimensions. First, the nowcasting framework…
[https://arxiv.org/abs/2601.11958v1](https://arxiv.org/abs/2601.11958v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [25] Generating long-horizon stock "buy" signals with a neural language model  *(score 0.450, 2024)*
This paper describes experiments on fine-tuning a small language model to generate forecasts of long-horizon stock price movements. Inputs to the model are narrative text from 10-K reports of large market capitalization companies in the S&P 500 index; the output is a forward-looking buy or sell decision. Price directio…
[https://arxiv.org/abs/2410.18988v1](https://arxiv.org/abs/2410.18988v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [29] Sentiment trading with large language models  *(score 0.391, 2024 · 73 cites)*
We investigate the efficacy of large language models (LLMs) in sentiment analysis of U.S. financial news and their potential in predicting stock market returns. We analyze a dataset comprising 965,375 news articles that span from January 1, 2010, to June 30, 2023; we focus on the performance of various LLMs, including …
[https://arxiv.org/abs/2412.19245v1](https://arxiv.org/abs/2412.19245v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [31] From Knowing to Doing: A Memory-Controlled Benchmark for LLM Trading Agents on Stock Markets  *(score 0.377, 2026 · 0 cites)*
Evaluating whether large language model (LLM) agents can profit in capital markets is increasingly framed as end-to-end trading: place an agent in a historical market, let it trade, and measure portfolio returns. This setup is vulnerable to two evaluation failures. First, long backtests often overlap with the knowledge…
[https://arxiv.org/abs/2605.28359v1](https://arxiv.org/abs/2605.28359v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [53] What Does ChatGPT Make of Historical Stock Returns? Extrapolation and Miscalibration in LLM Stock Return Forecasts  *(score 0.320, 2024 · 6 cites)*
We examine how large language models (LLMs) interpret historical stock returns and compare their forecasts with estimates from a crowd-sourced platform for ranking stocks. While stock returns exhibit short-term reversals, LLM forecasts over-extrapolate, placing excessive weight on recent performance similar to humans. …
[https://arxiv.org/abs/2409.11540v1](https://arxiv.org/abs/2409.11540v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [62] Can ChatGPT Forecast Stock Price Movements? Return Predictability and Large Language Models  *(score 0.303, 2023 · 362 cites)*
We document the capability of large language models (LLMs) like ChatGPT to predict stock market reactions from news headlines without direct financial training. Using post-knowledge-cutoff headlines, GPT-4 captures initial market responses, achieving approximately 90% portfolio-day hit rates for the non-tradable initia…
[https://arxiv.org/abs/2304.07619v6](https://arxiv.org/abs/2304.07619v6)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [64] Chronologically Consistent Large Language Models  *(score 0.301, 2025 · 6 cites)*
Large language models are increasingly used in social sciences, but their training data can introduce lookahead bias and training leakage. A good chronologically consistent language model requires efficient use of training data to maintain accuracy despite time-restricted data. Here, we overcome this challenge by train…
[https://arxiv.org/abs/2502.21206v3](https://arxiv.org/abs/2502.21206v3)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

## Microstructure / high-frequency  ·  3 papers

- **Our coverage:** only daily bars — blocked (but overnight/intraday-from-daily partial)
- **Data:** `intraday_tick`→—; `order_book_lob`→—
- **Buildable now:** NO — need intraday_tick, order_book_lob

### [54] The Power of Trading Polarity: Evidence from China Stock Market Crash  *(score 0.319, 2018 · 0 cites)*
The imbalance of buying and selling functions profoundly in the formation of market trends, however, a fine-granularity investigation of the imbalance is still missing. This paper investigates a unique transaction dataset that enables us to inspect the imbalance of buying and selling on the man-times level at high freq…
[https://arxiv.org/abs/1802.01143v1](https://arxiv.org/abs/1802.01143v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [55] Forecasting of Jump Arrivals in Stock Prices: New Attention-based Network Architecture using Limit Order Book Data  *(score 0.318, 2018 · 57 cites)*
The existing literature provides evidence that limit order book data can be used to predict short-term price movements in stock markets. This paper proposes a new neural network architecture for predicting return jump arrivals in equity markets with high-frequency limit order book data. This new architecture, based on …
[https://arxiv.org/abs/1810.10845v1](https://arxiv.org/abs/1810.10845v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

### [63] Intraday Patterns in the Cross-section of Stock Returns  *(score 0.302, 2010 · 207 cites)*
Motivated by the literature on investment flows and optimal trading, we examine intraday predictability in the cross-section of stock returns. We find a striking pattern of return continuation at half-hour intervals that are exact multiples of a trading day, and this effect lasts for at least 40 trading days. Volume, o…
[https://arxiv.org/abs/1005.3535v1](https://arxiv.org/abs/1005.3535v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_

# SATURATED

*Our 182-factor book already spans this; OSAP US-anomaly ports came back redundant. Only a genuinely new variant is worth a marginal-contribution test.*

## Momentum & reversal  ·  1 papers

- **Our coverage:** mom_/rev_ prefixes already span this
- **Data:** `price_ohlcv`→market_daily
- **Buildable now:** yes

### [65] Wax and wane of the cross-sectional momentum and contrarian effects: Evidence from the Chinese stock markets  *(score 0.300, 2017 · 25 cites)*
This paper investigates the time-varying risk-premium relation of the Chinese stock markets within the framework of cross-sectional momentum and contrarian effects by adopting the Capital Asset Pricing Model and the French-Fama three factor model. The evolving arbitrage opportunities are also studied by quantifying the…
[https://arxiv.org/abs/1707.05552v1](https://arxiv.org/abs/1707.05552v1)
→ **A-share direction:** _[extract: what factor would this become on our data? orthogonal to catalog? which fields?]_
