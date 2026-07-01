# ──────────────────────────────────────────────────────────────────────
# SCRIPT_STATUS header block.
# script_status: class_d_research_tooling
# formal_research_allowed: false
# touches_formal_data_plane: false
# pr2_audit_class: D
# notes: |
#   Knowledge backbone for the arXiv idea-sourcing framework. PURE DATA +
#   helpers (no deps, no I/O, no network). Encodes three things the value
#   scorer needs and nothing else can supply:
#     1. OUR_DATA      — what datasets/capabilities this system HAS vs LACKS
#                        (the authoritative list mirrors config/field_registry
#                        approved families: market_daily, daily_basic,
#                        pit_fundamentals, indicators, moneyflow, hk_hold,
#                        margin_detail, stk_holdertrade, top_list/top_inst,
#                        block_trade, cyq_perf, report_rc, income/balance/cashflow).
#     2. DIMENSIONS    — the equity-factor research taxonomy, each dimension
#                        tagged with OUR saturation status (the hard-won OSAP
#                        lesson: price/accounting is SATURATED for our 182-book;
#                        analyst/event/ownership/flow/behavioral is the OPEN
#                        frontier; text/microstructure/options are BLOCKED for
#                        lack of data) + a scoring lexicon.
#     3. signal lexicons — relevance / out-of-scope / empirical-strength / China.
#   This module is the single source of truth for "what we already know about
#   our own frontier", against which an arXiv paper is scored. A paper sourced
#   here is a HYPOTHESIS source, never evidence (CLAUDE.md §3.5, §7).
# ──────────────────────────────────────────────────────────────────────
"""
Research-dimension taxonomy + our-data inventory + scoring lexicons.

Why a taxonomy at all?  arXiv q-fin is a firehose (~18k matches). Ranking by
recency (the existing fetcher) or by citations (OpenAlex) both miss the point:
the *value* of a paper to THIS system is P(it yields a new, orthogonal,
DEPLOYABLE A-share factor). That probability is high only when a paper (a)
proposes a cross-sectional equity signal, (b) is computable on data we HAVE,
and (c) lives in a dimension we have NOT already saturated. This module encodes
(a)/(b)/(c) as lexicons + a status map so the scorer can estimate that prior
deterministically. The human/LLM read is the precision verdict on top of it.

No external dependencies — stdlib + regex only. Safe to import anywhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────────────
# 1. OUR DATA INVENTORY
#    capability tag -> (HAVE?, dataset/source, one-line note)
#    The scorer maps a paper's required-data tags onto this to decide
#    feasibility. HAVE=True means a factor using it can reach formal
#    eligibility today; HAVE=False is a data-acquisition target (the paper
#    is still valuable as a direction, but flagged BLOCKED).
# ─────────────────────────────────────────────────────────────────────
HAVE = True
LACK = False

OUR_DATA: dict[str, tuple[bool, str, str]] = {
    # ---- HAVE (approved field-registry families) ----
    "price_ohlcv":      (HAVE, "market_daily", "open/high/low/close/vol/amount/pre_close/adj_factor/up_down_limit"),
    "valuation":        (HAVE, "daily_basic", "pe/pb/ps/dv_ttm/turnover/total_mv/circ_mv/free_share"),
    "fundamentals":     (HAVE, "income/balancesheet/cashflow/pit_fundamentals/indicators", "PIT statements + fina_indicator-derived ratios"),
    "dividends":        (HAVE, "dividends", "cash/stock dividend, ex-date (corporate actions)"),
    "earnings_preannounce": (HAVE, "forecast/express", "earnings preannouncement + flash report w/ disclosure dates"),
    "analyst_forecast": (HAVE, "report_rc", "sell-side FY1/FY2 EPS, target price, ratings — revision flows (eps_up/dn/count, n_active)"),
    "moneyflow":        (HAVE, "moneyflow", "buy/sell by order-size bucket (sm/md/lg/elg) — order-flow proxy"),
    "northbound":       (HAVE, "hk_hold", "Stock-Connect northbound holdings (foreign/institutional flow proxy)"),
    "margin":           (HAVE, "margin_detail", "margin financing balance/buy (rzye/rzmre) — leveraged-retail sentiment"),
    "insider_holder":   (HAVE, "stk_holdertrade", "insider / large-holder increase-decrease transactions"),
    "lhb":              (HAVE, "top_list/top_inst", "Dragon-Tiger list: institutional & hot-money seat activity"),
    "block_trade":      (HAVE, "block_trade", "block (大宗) trades — discount/premium, institutional repositioning"),
    "chip_distribution":(HAVE, "cyq_perf", "cost-basis / chip distribution (筹码) — winner%, avg cost, concentration"),
    "holder_number":    (HAVE, "holder_number", "number of shareholders (retail crowding / ownership breadth)"),
    "index_membership": (HAVE, "reference/index_weight", "index weights + membership (CSI300/500, additions/deletions)"),
    "industry":         (HAVE, "reference", "SW industry classification (neutralization + lead-lag)"),
    # ---- LACK (data-acquisition targets; a paper needing these is BLOCKED) ----
    "intraday_tick":    (LACK, "—", "no tick / minute bars ingested (only daily)"),
    "order_book_lob":   (LACK, "—", "no limit-order-book / quote depth"),
    "options":          (LACK, "—", "no equity-options chain (IV surface, greeks, put-call)"),
    "news_text":        (LACK, "—", "no news / filing full-text corpus (BUILD TARGET — high value)"),
    "social_text":      (LACK, "—", "no social-media / forum text (东方财富股吧, etc.)"),
    "esg":              (LACK, "—", "no ESG / sustainability data"),
    "supply_chain":     (LACK, "—", "no customer-supplier / inter-firm network graph"),
    "satellite_alt":    (LACK, "—", "no satellite / card / web-traffic alt-data"),
    "bond_credit":      (LACK, "—", "no bond / CDS / credit-spread data"),
    "short_interest":   (LACK, "—", "A-share shorting heavily restricted; no short-interest series"),
    "patent":           (LACK, "—", "no patent / innovation-output data"),
    "macro":            (LACK, "—", "only index series; no broad macro panel ingested"),
}


# ─────────────────────────────────────────────────────────────────────
# 2. RESEARCH-DIMENSION TAXONOMY
#    The status field is the heart of the framework — it is OUR judgement of
#    where alpha still lives FOR THIS BOOK, learned empirically:
#      SATURATED       the 182-catalog already spans this; OSAP ports came back
#                      redundant (price/accounting/vol/size/liquidity).
#      FRONTIER_OPEN   we now HAVE the data but have barely mined it -> the
#                      highest-value target (analyst/event/flow/ownership/chips).
#      FRONTIER_BLOCKED promising but we LACK the data -> valuable as an
#                      acquisition direction, not buildable today.
#      METHOD          cross-cutting methodology (ML/portfolio/factor-stats) —
#                      valuable as HOW to combine what we have, not a new factor.
#      NOT_PORTABLE    A-share structural mismatch (options-only, short-sale).
# ─────────────────────────────────────────────────────────────────────
SATURATED        = "SATURATED"
FRONTIER_OPEN    = "FRONTIER_OPEN"
FRONTIER_BLOCKED = "FRONTIER_BLOCKED"
METHOD           = "METHOD"
NOT_PORTABLE     = "NOT_PORTABLE"

# value weight per status (frontier-leaning default — see score_papers.py)
STATUS_VALUE: dict[str, float] = {
    FRONTIER_OPEN:    1.00,   # we have the data, haven't mined it — best
    FRONTIER_BLOCKED: 0.55,   # great idea, need data first
    METHOD:           0.50,   # improves combination of what we have
    SATURATED:        0.20,   # book already spans it
    NOT_PORTABLE:     0.05,   # structurally can't
}


@dataclass(frozen=True)
class Dimension:
    key: str
    label: str
    status: str
    data_tags: tuple[str, ...]      # keys into OUR_DATA
    keywords: tuple[str, ...]       # lexicon for scoring title+abstract
    note: str = ""

    @property
    def buildable(self) -> bool:
        """True iff every required data tag is something we HAVE."""
        return all(OUR_DATA.get(t, (LACK, "", ""))[0] for t in self.data_tags) if self.data_tags else False


DIMENSIONS: tuple[Dimension, ...] = (
    # ---------------- SATURATED (price / accounting style space) ----------------
    Dimension("momentum_reversal", "Momentum & reversal", SATURATED, ("price_ohlcv",),
              ("momentum", "reversal", "trend following", "time series momentum", "cross-sectional momentum",
               "52-week high", "52 week high", "price trend", "relative strength", "contrarian",
               "mean reversion", "short-term reversal", "long-term reversal", "industry momentum"),
              "mom_/rev_ prefixes already span this"),
    Dimension("value_accounting", "Value & accounting quality", SATURATED, ("fundamentals", "valuation"),
              ("book-to-market", "book to market", "value premium", "earnings yield", "cash flow yield",
               "valuation ratio", "accruals", "asset growth", "investment factor", "gross profitability",
               "operating profitability", "quality minus junk", "piotroski", "f-score", "net stock issuance",
               "external financing", "earnings quality", "fundamental analysis"),
              "val_/qual_/grow_/lev_ prefixes; OSAP ports came back redundant"),
    Dimension("volatility_risk", "Volatility & higher moments", SATURATED, ("price_ohlcv", "index_membership"),
              ("idiosyncratic volatility", "realized volatility", "low volatility anomaly", "betting against beta",
               "downside risk", "tail risk", "value at risk", "volatility of volatility", "skewness", "coskewness",
               "kurtosis", "semivariance", "beta anomaly", "low-risk anomaly"),
              "risk_ prefix; idiovol/beta/skew tested → redundant"),
    Dimension("liquidity", "Liquidity", SATURATED, ("price_ohlcv", "valuation"),
              ("illiquidity", "amihud", "liquidity premium", "bid-ask spread", "turnover", "trading volume",
               "market impact", "zero-return days", "liquidity risk", "price impact"),
              "liq_ prefix covers Amihud/turnover/spread-proxy"),
    Dimension("size", "Size", SATURATED, ("valuation",),
              ("size effect", "size premium", "market capitalization", "small-cap", "micro-cap", "microcap",
               "small minus big"),
              "size_ prefix"),

    # ---------------- FRONTIER_OPEN (have the data, barely mined) ----------------
    Dimension("analyst_expectations", "Analyst expectations & revisions", FRONTIER_OPEN, ("analyst_forecast",),
              ("analyst forecast", "earnings forecast", "analyst recommendation", "target price",
               "forecast revision", "earnings revision", "forecast dispersion", "analyst coverage",
               "consensus estimate", "forecast accuracy", "eps revision", "recommendation change",
               "revision breadth", "forecast diffusion", "sell-side", "analyst optimism", "forecast error",
               "implied cost of capital"),
              "report_rc just integrated; eps_diffusion is the ONLY factor here so far"),
    Dimension("earnings_events", "Earnings events & drift", FRONTIER_OPEN, ("earnings_preannounce", "fundamentals"),
              ("post-earnings-announcement drift", "post earnings announcement drift", "pead", "earnings surprise",
               "standardized unexpected earnings", "earnings momentum", "earnings announcement",
               "earnings preannouncement", "management guidance", "earnings call", "earnings response",
               "drift", "preannouncement", "profit warning"),
              "forecast/express + statement disclosure dates available; not mined"),
    Dimension("informed_flow", "Informed order flow & positioning", FRONTIER_OPEN,
              ("moneyflow", "lhb", "margin", "northbound", "block_trade"),
              ("order flow", "order imbalance", "informed trading", "smart money", "institutional trading",
               "retail trading", "retail investor", "fund flow", "money flow", "trading activity",
               "margin trading", "margin debt", "leverage trading", "northbound", "connect flow",
               "foreign investor", "block trade", "large trade", "abnormal volume", "net buying",
               "buy-sell imbalance", "trade size"),
              "moneyflow/lhb/margin/hk_hold/block_trade all approved, ~0 factors built"),
    Dimension("ownership_holders", "Ownership & insider activity", FRONTIER_OPEN,
              ("holder_number", "insider_holder"),
              ("insider trading", "insider transaction", "institutional ownership", "ownership breadth",
               "breadth of ownership", "shareholder", "blockholder", "ownership concentration",
               "number of shareholders", "holdings change", "insider purchase", "share pledge", "equity pledge"),
              "holder_number + stk_holdertrade approved, unmined"),
    Dimension("behavioral_chips", "Behavioral & chip-distribution", FRONTIER_OPEN, ("chip_distribution", "price_ohlcv"),
              # NOTE: bare "attention"/"sentiment" were REMOVED — they fire on neural-net
              # "attention" mechanisms and generic sentiment-ML, not investor behavior. Kept
              # only the disambiguated multiword forms.
              ("disposition effect", "capital gains overhang", "reference price", "reference-dependent",
               "anchoring", "prospect theory", "unrealized gains", "unrealized capital gains", "cost basis",
               "lottery demand", "lottery-like", "gambling preference", "max effect", "salience theory",
               "limited attention", "investor attention", "overreaction", "underreaction",
               "investor sentiment", "retail sentiment", "sentiment feedback", "behavioral bias"),
              "cyq_perf (筹码 cost-basis) approved — disposition/overhang directly buildable"),
    Dimension("seasonality_calendar", "Seasonality & calendar", FRONTIER_OPEN, ("price_ohlcv",),
              ("seasonality", "calendar effect", "turn-of-month", "turn of the month", "holiday effect",
               "january effect", "day-of-week", "intra-month", "seasonal", "same-month", "earnings seasonality"),
              "buildable on price+dates; lightly covered"),

    # ---------------- FRONTIER_BLOCKED (need data we lack) ----------------
    Dimension("text_nlp", "Text / NLP / LLM signals", FRONTIER_BLOCKED, ("news_text",),
              ("news sentiment", "textual analysis", "natural language", "nlp", "large language model",
               "language model", "llm", "chatgpt", "gpt", "social media", "sentiment analysis", "text mining",
               "readability", "tone", "financial text", "annual report text", "md&a", "earnings call transcript",
               "word embedding", "bert", "topic model", "10-k", "filing text", "news flow"),
              "HIGH-VALUE build target — no text corpus yet"),
    Dimension("microstructure_hf", "Microstructure / high-frequency", FRONTIER_BLOCKED, ("intraday_tick", "order_book_lob"),
              ("limit order book", "high-frequency", "high frequency", "intraday", "tick data", "market microstructure",
               "order book", "quote", "microsecond", "realized spread", "vpin", "price discovery", "kyle's lambda",
               "effective spread", "intraday momentum", "overnight return", "opening auction"),
              "only daily bars — blocked (but overnight/intraday-from-daily partial)"),
    Dimension("options_derived", "Option-implied signals", NOT_PORTABLE, ("options",),
              ("implied volatility", "option-implied", "variance risk premium", "options market", "put-call ratio",
               "risk-neutral", "implied skew", "straddle", "vix", "option volume", "implied correlation"),
              "no equity options ingested + A-share options thin"),
    Dimension("network_supplychain", "Network & supply-chain", FRONTIER_BLOCKED, ("supply_chain",),
              ("supply chain", "customer-supplier", "economic links", "industry network", "interfirm",
               "complex network", "peer firms", "peer effect", "graph neural network", "firm network",
               "production network", "input-output"),
              "no inter-firm graph — blocked"),
    Dimension("patent_innovation", "Innovation / patents", FRONTIER_BLOCKED, ("patent",),
              ("patent", "innovation output", "innovative efficiency", "r&d productivity", "technological",
               "intangible capital", "knowledge capital"),
              "R&D expense we have; patent counts we don't"),

    # ---------------- METHOD (cross-cutting; applies to data we have) ----------------
    Dimension("ml_method", "Machine-learning methodology", METHOD, ("price_ohlcv", "fundamentals"),
              ("machine learning", "deep learning", "neural network", "gradient boosting", "random forest",
               "transformer", "reinforcement learning", "feature importance", "autoencoder", "empirical asset pricing",
               "return prediction", "lstm", "attention mechanism", "ensemble", "shrinkage", "regularization",
               "lasso", "elastic net", "conditional factor model", "ipca", "instrumented principal component"),
              "improves how we COMBINE existing factors; model_zoo target"),
    Dimension("portfolio_construction", "Portfolio construction & costs", METHOD, ("price_ohlcv",),
              ("portfolio optimization", "mean-variance", "risk parity", "transaction cost", "portfolio construction",
               "factor investing", "parametric portfolio", "covariance estimation", "shrinkage covariance",
               "hierarchical risk parity", "turnover control", "optimal rebalancing", "factor timing",
               "portfolio choice", "robust optimization"),
              "portfolio_risk module + execution; deployment-side value"),
    Dimension("factor_methodology", "Factor-zoo / multiple-testing stats", METHOD, (),
              ("factor zoo", "multiple testing", "p-hacking", "data snooping", "false discovery", "replication",
               "deflated sharpe", "factor selection", "dimensionality reduction", "principal component",
               "cross-section of expected returns", "characteristic", "anomaly", "out-of-sample predictability",
               "horse race", "model selection", "spanning test"),
              "directly informs our promotion gates / marginal-contribution rule"),
    Dimension("macro_timing", "Macro & factor timing", METHOD, ("index_membership",),
              ("macroeconomic", "business cycle", "factor timing", "regime", "recession", "monetary policy",
               "inflation", "market timing", "predictable returns", "conditional", "state variable", "term spread"),
              "index series only; equity-factor-timing angle is usable"),
)

DIM_BY_KEY: dict[str, Dimension] = {d.key: d for d in DIMENSIONS}


# ─────────────────────────────────────────────────────────────────────
# 3. SIGNAL LEXICONS (cross-cutting, not dimension-specific)
# ─────────────────────────────────────────────────────────────────────
# Positive anchors: the paper is about the cross-section of equity returns.
RELEVANCE_POS: tuple[str, ...] = (
    "cross-section", "cross section", "cross-sectional", "stock returns", "equity returns",
    "expected returns", "return predictability", "predict returns", "anomaly", "anomalies",
    "asset pricing", "factor model", "stock selection", "alpha", "characteristic", "firm characteristics",
    "portfolio sort", "long-short", "decile", "quintile", "trading strategy", "stock market",
    "equity market", "return forecast", "factor investing",
)
# Negative anchors: out of scope for cross-sectional EQUITY factor mining.
RELEVANCE_NEG: tuple[str, ...] = (
    "option pricing", "derivative pricing", "optimal execution", "market making", "rough volatility",
    "stochastic volatility model", "interest rate model", "term structure model", "credit risk pricing",
    "cryptocurrency", "bitcoin", "crypto", "foreign exchange", "exchange rate", "fx market",
    "commodity futures", "electricity price", "energy market", "insurance", "actuarial",
    "optimal control", "mean field game", "systemic risk", "banking", "central bank", "default probability model",
    "portfolio insurance", "american option", "european option", "hedging strategy", "calibration of",
    "limit theorem", "stochastic differential", "rough path", "deep hedging", "order execution",
)
# HARD vetoes — a different asset class entirely. Their presence caps the
# relevance gate near the floor regardless of incidental equity-factor vocabulary
# (a "Crypto Pricing with Hidden Factors" paper still says factor/cross-section).
RELEVANCE_HARD_NEG: tuple[str, ...] = (
    "cryptocurrency", "crypto", "bitcoin", "ethereum", "token", "blockchain",
    "carry trade", "cross-sectional currency", "currency strategies", "currency portfolio",
    "foreign exchange", "exchange rate", "commodity futures", "treasury bond", "corporate bond",
)
# China specificity — a meaningful bonus (directly our market).
CHINA_TERMS: tuple[str, ...] = (
    "china", "chinese", "a-share", "a share", "a-shares", "shanghai stock", "shenzhen stock",
    "shanghai exchange", "shenzhen exchange", "sse", "szse", "csi 300", "csi300", "csi 500", "csi500",
    "chinese equity", "chinese stock", "china's stock", "mainland china", "stock connect",
)
# Empirical-strength signals — the abstract reports real, OOS-aware results.
EMPIRICAL_TERMS: tuple[str, ...] = (
    "sharpe ratio", "out-of-sample", "out of sample", "information coefficient", "information ratio",
    "statistically significant", "t-statistic", "t-stat", "annualized return", "risk-adjusted",
    "long-short portfolio", "long short portfolio", "decile portfolio", "quintile portfolio",
    "hedge portfolio", "predictive power", "economically significant", "we document", "we find",
    "we show", "outperform", "abnormal return", "alpha of", "robust to", "after transaction costs",
    "net of costs", "fama-macbeth", "fama macbeth",
)


# ─────────────────────────────────────────────────────────────────────
# 4. MATCHING HELPERS  (deterministic, stdlib regex)
# ─────────────────────────────────────────────────────────────────────
_WORD_RE_CACHE: dict[str, re.Pattern] = {}


def _term_pattern(term: str) -> re.Pattern:
    """Word-boundary-ish regex for a term. Multi-word/punct terms match as a
    loose phrase (whitespace-insensitive); single alnum tokens get \b guards
    so 'beta' doesn't fire inside 'alphabet'."""
    p = _WORD_RE_CACHE.get(term)
    if p is None:
        t = term.lower().strip()
        if re.fullmatch(r"[a-z0-9]+", t):
            pat = rf"\b{re.escape(t)}\b"
        else:
            # split on non-alnum, join with flexible separators
            parts = [re.escape(x) for x in re.split(r"[^a-z0-9&]+", t) if x]
            pat = r"[^a-z0-9]+".join(parts) if parts else re.escape(t)
        p = re.compile(pat, re.IGNORECASE)
        _WORD_RE_CACHE[term] = p
    return p


def lexicon_hits(text: str, lexicon) -> list[str]:
    """Return the subset of `lexicon` terms that occur in `text`."""
    if not text:
        return []
    low = text.lower()
    out = []
    for term in lexicon:
        if _term_pattern(term).search(low):
            out.append(term)
    return out


def score_dimensions(text: str) -> dict[str, list[str]]:
    """Per-dimension matched keywords. Empty lists omitted."""
    res: dict[str, list[str]] = {}
    for d in DIMENSIONS:
        hits = lexicon_hits(text, d.keywords)
        if hits:
            res[d.key] = hits
    return res


def best_dimension(dim_hits: dict[str, list[str]]) -> str | None:
    """The dimension with the most keyword hits (ties -> higher STATUS_VALUE,
    then FRONTIER_OPEN before SATURATED). None if no dimension matched."""
    if not dim_hits:
        return None
    def keyf(item):
        k, hits = item
        return (len(hits), STATUS_VALUE.get(DIM_BY_KEY[k].status, 0.0))
    return max(dim_hits.items(), key=keyf)[0]


def feasibility_for_dimension(dim_key: str) -> tuple[bool, list[str]]:
    """(buildable_now?, list of LACKED data tags) for a dimension."""
    d = DIM_BY_KEY.get(dim_key)
    if d is None:
        return (False, [])
    lacked = [t for t in d.data_tags if not OUR_DATA.get(t, (LACK, "", ""))[0]]
    return (len(lacked) == 0 and len(d.data_tags) > 0, lacked)


# convenience for external callers / docs
DIMENSION_TABLE = [
    {"key": d.key, "label": d.label, "status": d.status,
     "buildable_now": d.buildable, "data_tags": list(d.data_tags), "note": d.note}
    for d in DIMENSIONS
]


if __name__ == "__main__":  # tiny self-check / human glance
    import json
    print(f"OUR_DATA: {sum(v[0] for v in OUR_DATA.values())} HAVE / "
          f"{sum(not v[0] for v in OUR_DATA.values())} LACK")
    by_status: dict[str, list[str]] = {}
    for d in DIMENSIONS:
        by_status.setdefault(d.status, []).append(d.key)
    print(json.dumps(by_status, indent=2))
    demo = ("We construct a measure of analyst forecast revision breadth and show it "
            "predicts the cross-section of Chinese A-share stock returns with a Sharpe ratio "
            "of 1.4 out-of-sample after transaction costs.")
    dh = score_dimensions(demo)
    print("demo dims:", {k: v for k, v in dh.items()})
    print("best:", best_dimension(dh), "| china:", lexicon_hits(demo, CHINA_TERMS),
          "| empirical:", len(lexicon_hits(demo, EMPIRICAL_TERMS)))
