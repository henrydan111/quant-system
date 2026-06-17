"""
Factor Operator Library (因子算子库)

Two-layer operator system for A-share multi-factor research:

Layer 1 — Qlib Expression Operators:
    Functions that return Qlib expression strings. These are computed at
    C/Cython speed by Qlib's expression engine via D.features().

Layer 2 — DataFrame Operators:
    Functions that take a pandas Series/DataFrame and return a Series.
    Used for cross-sectional operations (ranking, z-scoring, composites)
    that cannot be expressed as per-stock time-series formulas.

Price Type Convention:
    - ADJUSTED price ($close * $adj_factor) for cross-day comparisons
      (returns, rolling stats, MA ratios, trends)
    - RAW values ($pe_ttm, $roe, $turnover_rate, $ocfps/$close) for
      point-in-time ratios and fundamentals

PIT Leakage Prevention:
    All factors must wrap every $field reference inside a Ref(...) frame
    so the factor value at time t uses data only up to t-1. The only
    allowed exception is ``forward_return``, which is a label (prediction
    target), not a signal.

    Enforcement: ``tests/alpha_research/test_factor_library_pit_safety.py``
    runs a parser-based static-analysis check over every factor in
    ``get_factor_catalog(include_new_data=True)`` AND every public operator
    function in this module. Any new operator that fails the check will
    fail CI before it can be merged.

    Fix pattern: put Ref inside the rolling operator, not outside.
        WRONG:  Mean($close, 20)
        RIGHT:  Mean(Ref($close, 1), 20)
    For price-based operators that touch multiple raw fields (close, open,
    high, low, adj_factor), use the ``ADJ_*_T1`` constants below.

Negation Workaround:
    Qlib does not support unary negation on operator results.
    Use ``0 - Std(...)`` instead of ``-Std(...)``.
"""

import logging
import os
import threading
import time

import numpy as np
import pandas as pd
from src.research_orchestrator.cache_manifest import CacheContext
from src.research_orchestrator.qlib_windowed_features import qlib_windowed_features

logger = logging.getLogger(__name__)


def _start_progress_heartbeat(task_name, interval):
    """Start a lightweight progress heartbeat for long-running steps."""
    if interval is None or interval <= 0:
        return None, None

    stop_event = threading.Event()
    start_time = time.time()

    def _heartbeat():
        while not stop_event.wait(interval):
            elapsed = time.time() - start_time
            logger.info(f"{task_name} still running... elapsed {elapsed:.1f}s")

    thread = threading.Thread(
        target=_heartbeat,
        name=f"{task_name}-heartbeat",
        daemon=True,
    )
    thread.start()
    return stop_event, thread


def _kernel_label(kernels):
    return "qlib default" if kernels is None else str(kernels)


def _is_worker_permission_error(exc):
    if isinstance(exc, PermissionError):
        return True

    winerror = getattr(exc, "winerror", None)
    if winerror == 5:
        return True

    message = str(exc).lower()
    return (
        "access is denied" in message
        and any(token in message for token in ("pipe", "multiprocessing", "joblib"))
    )

# ═══════════════════════════════════════════════════════════════════════
#  BUILDING BLOCKS
# ═══════════════════════════════════════════════════════════════════════

# Adjusted price components (for cross-day comparisons).
# Keep the multiplication parenthesized so downstream expressions like
# ADJ_CLOSE / ADJ_OPEN parse as (close*adj)/(open*adj) instead of the
# left-associative ((close*adj)/open)*adj form.
#
# The unshifted atoms below are RESERVED for ``forward_return`` (and other
# future forward-looking labels). Do NOT reference them directly in any
# signal operator — use the ``_T1`` variants further down which wrap the
# atom in Ref(..., 1). The PIT-safety static-analysis test at
# ``tests/alpha_research/test_factor_library_pit_safety.py`` enforces this.
ADJ_CLOSE = "($close * $adj_factor)"
ADJ_OPEN = "($open * $adj_factor)"
ADJ_HIGH = "($high * $adj_factor)"
ADJ_LOW = "($low * $adj_factor)"

# PIT-safe shifted atoms. Every signal operator that reads adjusted price
# must use these, NOT the unshifted versions above. At time t they expand
# to the t-1 adjusted price value.
ADJ_CLOSE_T1 = f"Ref({ADJ_CLOSE}, 1)"
ADJ_OPEN_T1 = f"Ref({ADJ_OPEN}, 1)"
ADJ_HIGH_T1 = f"Ref({ADJ_HIGH}, 1)"
ADJ_LOW_T1 = f"Ref({ADJ_LOW}, 1)"

# Daily return (PIT-safe): yesterday's close-to-close return.
# = (close_{t-1} / close_{t-2}) - 1
# Every operator built on DAILY_RET inherits this PIT-safe base.
DAILY_RET = f"({ADJ_CLOSE_T1} / Ref({ADJ_CLOSE}, 2) - 1)"

# PIT-safe limit-day flag (the materialized, basis-certified $limit_status field; approved 2026-06-17):
# +1 close-at-up-limit, -1 close-at-down-limit, 0 normal, NaN suspended/no-limit. Ref(...,1) aligns it
# with DAILY_RET (both reference the t-1 bar). Single certified source for 剔除涨跌停日 exclusion.
LIMIT_STATUS_T1 = "Ref($limit_status, 1)"


# ═══════════════════════════════════════════════════════════════════════
#  LAYER 1: QLIB EXPRESSION OPERATORS
#
#  Each function returns a Qlib expression string.
#  All price-based factors include Ref(..., 1) for PIT safety.
# ═══════════════════════════════════════════════════════════════════════

# ─────────────────────── Momentum / Reversal ───────────────────────

def momentum(window):
    """N-day price momentum (adjusted).

    Formula: P(t-1) / P(t-1-window) - 1

    Args:
        window: Lookback window in trading days.

    Returns:
        Qlib expression string.
    """
    return f"Ref({ADJ_CLOSE}, 1) / Ref({ADJ_CLOSE}, {window + 1}) - 1"


def skip_momentum(skip, total):
    """Skip-N momentum: return from (t-skip) to (t-total).

    Commonly used for skip-1-month (skip=21, total=252) or
    skip-1-week (skip=5, total=20) momentum.

    Args:
        skip: Days to skip from current date.
        total: Total lookback window.

    Returns:
        Qlib expression string.
    """
    return f"Ref({ADJ_CLOSE}, {skip + 1}) / Ref({ADJ_CLOSE}, {total + 1}) - 1"


def ema_return(span):
    """Exponential moving average of daily returns.

    Uses Qlib's native EMA operator (true exponential weighting).

    Args:
        span: EMA span parameter.

    Returns:
        Qlib expression string.
    """
    return f"EMA({DAILY_RET}, {span})"


def wma_return(window):
    """Weighted moving average of daily returns.

    Linearly weighted: more recent days have higher weight.

    Args:
        window: Rolling window size.

    Returns:
        Qlib expression string.
    """
    return f"WMA({DAILY_RET}, {window})"


def overnight_return(window):
    """Average overnight gap return over N days.

    Formula (PIT-safe): Mean((Open_{t-1} / Prev_Close_{t-2}) - 1, window)

    Args:
        window: Averaging window.

    Returns:
        Qlib expression string.
    """
    return f"Mean({ADJ_OPEN_T1} / Ref({ADJ_CLOSE}, 2) - 1, {window})"


def intraday_return(window):
    """Average intraday return over N days.

    Formula (PIT-safe): Mean((Close_{t-1} / Open_{t-1}) - 1, window)

    Args:
        window: Averaging window.

    Returns:
        Qlib expression string.
    """
    return f"Mean({ADJ_CLOSE_T1} / {ADJ_OPEN_T1} - 1, {window})"


def high_moment(window):
    """Average bullish pressure over N days.

    Formula (PIT-safe): Mean((High_{t-1} - Open_{t-1}) / Open_{t-1}, window)

    Args:
        window: Averaging window.

    Returns:
        Qlib expression string.
    """
    return f"Mean(({ADJ_HIGH_T1} - {ADJ_OPEN_T1}) / {ADJ_OPEN_T1}, {window})"


def low_moment(window):
    """Average bearish pressure over N days.

    Formula (PIT-safe): Mean((Low_{t-1} - Open_{t-1}) / Open_{t-1}, window)

    Args:
        window: Averaging window.

    Returns:
        Qlib expression string.
    """
    return f"Mean(({ADJ_LOW_T1} - {ADJ_OPEN_T1}) / {ADJ_OPEN_T1}, {window})"


def return_acceleration(window):
    """Momentum acceleration (second derivative).

    Formula: mom(t, window) - mom(t-window, window)

    Args:
        window: Lookback window for each momentum leg.

    Returns:
        Qlib expression string.
    """
    mom_now = f"(Ref({ADJ_CLOSE}, 1) / Ref({ADJ_CLOSE}, {window + 1}) - 1)"
    mom_prev = f"(Ref({ADJ_CLOSE}, {window + 1}) / Ref({ADJ_CLOSE}, {2 * window + 1}) - 1)"
    return f"{mom_now} - {mom_prev}"


def short_reversal(window):
    """Short-term reversal (negative momentum).

    Args:
        window: Lookback window.

    Returns:
        Qlib expression string.
    """
    return f"0 - (Ref({ADJ_CLOSE}, 1) / Ref({ADJ_CLOSE}, {window + 1}) - 1)"


def max_single_return(window):
    """Maximum single-day return over N days (lottery effect).

    Args:
        window: Lookback window.

    Returns:
        Qlib expression string.
    """
    return f"Max({DAILY_RET}, {window})"


def min_single_return(window):
    """Minimum single-day return over N days.

    Args:
        window: Lookback window.

    Returns:
        Qlib expression string.
    """
    return f"Min({DAILY_RET}, {window})"


def up_down_ratio(window):
    """Ratio of up-days to total days over N days.

    Uses ``Sum(If(ret > 0, 1, 0), window) / window``.

    Implementation note (factor audit 2026-05-30, F1/F4):
        The prior implementation used ``Count(ret > 0, window) / window``. In
        this Qlib build, ``Count(cond, N)`` returns the count of non-NaN
        observations (i.e. N), IGNORING the condition — verified empirically
        (``Count(ret>0,5)≡5`` for every stock). That collapsed
        ``rev_up_down_ratio_20d`` to a cross-sectional constant (1.0) → zero
        rank dispersion → silently dead production factor. Fixed via the
        equivalent ``Sum(If(cond, 1, 0), N)`` idiom (GPT 5.5 Pro Round-5
        verdict: mandatory). Always use Sum(If()) for conditional counts.

    Args:
        window: Lookback window.

    Returns:
        Qlib expression string.
    """
    return f"Sum(If({DAILY_RET} > 0, 1, 0), {window}) / {window}"


# ─────────── CICC price-volume 系列7 图表4 — momentum (E1a, P-OP certified) ───────────
# Each builder below has its operator SEMANTICS certified through the OperatorCertification
# harness (workspace/scripts/certify_e1a_operators.py) BEFORE any factor using it may enter
# the formal IS gate (§10A). The certified pandas reference was verified to match the Qlib
# primitives used here (Sum/Abs, Sign+Mean, IdxMax, Rank) — see the operators they compile to.

def path_adjusted_momentum(window):
    """Path-adjusted momentum over N days — CICC mmt_route (路径调整动量).

    Formula (PIT-safe, literal handbook transcription): period_return(N) / Sum(|daily_ret|, N),
    i.e. the N-day PERIOD return (adj_close_{t-1}/adj_close_{t-N-1} - 1) divided by the total
    path length Sum(|daily_ret|, N), guarded to 0 over a fully flat / suspended window. NOT the
    Kaufman efficiency ratio Sum(ret)/Sum(|ret|) — the handbook numerator "过去N内收益率" is the
    period return (the same reading op.momentum uses for "收益率"; GPT 5.5 Pro E1a cross-review
    Q1). So the value is NOT bounded by +-1 (compounding lifts a pure uptrend slightly above 1).
    Numerator + denominator are both Ref(...,1)-wrapped via ADJ_CLOSE / DAILY_RET.

    Price basis: adjusted close. Decay: short (1M) to medium (1Y). Operator semantics certified
    via the P-OP harness at W in {20, 250} (operator_id=path_adjusted_momentum).

    Args:
        window: Lookback in trading days (20 = 1M, 250 = 1Y per the handbook).

    Returns:
        Qlib expression string.
    """
    period_ret = f"({ADJ_CLOSE_T1} / Ref({ADJ_CLOSE}, {window + 1}) - 1)"
    den = f"Sum(Abs({DAILY_RET}), {window})"
    return f"If({den} > 0, {period_ret} / {den}, 0)"


def up_down_day_share(window):
    """Up-minus-down day share over N days — CICC mmt_discrete (信息离散度动量).

    Formula (PIT-safe): Mean(Sign(daily_ret), N) = (#up - #down)/N, range [-1, 1]. Flat days
    (ret == 0) contribute 0 (sign(0)=0) — the ONLY thing distinguishing it from the up-day
    fraction ``up_down_ratio`` (rank-equivalent to it modulo flat-day handling).

    Price basis: adjusted close-to-close daily returns. Decay: short to medium.
    Operator semantics certified via the P-OP harness (operator_id=up_down_day_share).

    Args:
        window: Lookback in trading days.

    Returns:
        Qlib expression string.
    """
    return f"Mean(Sign({DAILY_RET}), {window})"


def days_since_high(window):
    """Trading days since the rolling-N high — CICC mmt_highest_days.

    Formula (PIT-safe): N - IdxMax(adj_high_{t-1}, N). Qlib IdxMax is 1-indexed (today=N), so
    N - IdxMax == (N-1) - argmax0: 0 = the high is the most recent (t-1) bar, N-1 = the oldest
    bar in the window. First-occurrence tie-break. Higher = price has fallen further from its
    peak (weaker / more reverted).

    Price basis: adjusted high — used because cross-day high comparisons must be on a comparable
    adjusted-price basis. NOTE: an ex-rights adjustment CAN change which date is the window max,
    so the adjusted-high argmax may differ from the raw-high argmax around splits/dividends; that
    is the REASON adjusted is correct here, not an accident to work around (GPT 5.5 Pro E1a
    cross-review Q4). Decay: medium (1Y form). Operator semantics certified via the P-OP harness
    at W in {20, 250} (operator_id=days_since_high). Warmup: Qlib uses min_periods=1 so the first
    N-1 bars carry partial-window values (dropped by the eval warmup buffer).

    Args:
        window: Lookback in trading days (250 = 1Y per the handbook).

    Returns:
        Qlib expression string.
    """
    return f"{window} - IdxMax({ADJ_HIGH_T1}, {window})"


def ts_rank(window, field=None):
    """Rolling time-series percentile rank of the current value within trailing N — the
    building block of CICC mmt_time_rank (时序rank动量).

    Formula (PIT-safe): Rank(field_{t-1}, N) in [0, 1] (1 = current value is the window max;
    average-tie percentile). Defaults to the adjusted close. Compose with an outer Mean for
    the handbook factor: ``Mean(ts_rank(250), 20)``.

    Price basis: adjusted close (default). Operator semantics certified via the P-OP harness
    (operator_id=ts_rank).

    Args:
        window: Rolling window over which the current value is ranked.
        field: PIT-safe Qlib sub-expression to rank (defaults to ADJ_CLOSE_T1).

    Returns:
        Qlib expression string.
    """
    base = ADJ_CLOSE_T1 if field is None else field
    return f"Rank({base}, {window})"


# ─────────────────────── Volatility (CICC 价量 图表16, Wave E1b) ───────────────────────
# Shadow lines are RATIOS, so the price-adjustment factor cancels (adjusted ≡ raw) — adjusted _T1
# atoms are used for basis consistency. ``Greater``/``Less`` are Qlib ELEMENTWISE max/min (first use
# in this catalog; verified). All per-day quantities are Ref(...,1)-wrapped (PIT-safe), aggregated by
# an outer Mean/Std over the window.

def sign_conditional_std(sign, window):
    """Subset standard deviation of daily returns over only the SIGN-matching, LIMIT-EXCLUDED days in
    the window — CICC 下行/上行波动率 (vol_down_std / vol_up_std, 图表16).

    Handbook: std of adjusted daily returns on days with 涨跌幅<0 (down) or >0 (up), EXCLUDING 涨跌停日.
    This is a TRUE subset std (only the matching days enter the statistic), NOT the zero-fill proxy
    ``Std(If(ret<0, ret, 0), N)`` that ``risk_downvol`` uses (zero-fill keeps non-matching days at 0,
    changing both the mean and the count). Limit exclusion reads the materialized ``$limit_status``
    field (basis-certified) — never an inline raw/adjusted comparison (GPT E1b review B1/B2).

    Construction (ddof=1, to match Qlib ``Std``): with the selection indicator
    ``sel = [ret<0] * (1 - [|limit_status|>=0.5])`` (down; ``ret>0`` for up), and ``m = sel*ret`` (0 on
    non-selected, NaN-safe via ``If``), the sample variance is ``(Σm² - (Σm)²/n) / (n-1)`` where
    ``n = Σsel``. This form yields NaN automatically when ``n < 2`` (0/0), so the handbook's
    "min 2 observations" floor needs no separate guard. NaN ``limit_status`` (no published limit) →
    ``[|·|>=0.5]`` is 0 → the day is INCLUDED (we exclude only KNOWN limit days). NaN ``ret``
    (suspended) → ``[ret<0]`` is 0 → not selected. ``Std = Power(var, 0.5)`` (Qlib has no ``Sqrt``).

    Operator semantics certified via the P-OP harness (operator_id=sign_conditional_std). Args:
        sign: ``"down"`` (ret<0) or ``"up"`` (ret>0).
        window: lookback in trading days (20/60/120 = 1M/3M/6M).
    Returns: Qlib expression string.
    """
    cmp = "Lt" if sign == "down" else "Gt"
    is_signed = f"{cmp}({DAILY_RET}, 0)"
    sel = f"({is_signed} * (1 - Ge(Abs({LIMIT_STATUS_T1}), 0.5)))"
    masked = f"If({sel} > 0.5, {DAILY_RET}, 0)"
    n = f"Sum({sel}, {window})"
    s1 = f"Sum({masked}, {window})"
    s2 = f"Sum(({masked} * {masked}), {window})"
    var = f"(({s2} - {s1} * {s1} / {n}) / ({n} - 1))"
    # Greater(var, 0) clamps a tiny-NEGATIVE float (sum-of-squares cancellation when the selected
    # returns are ~equal -> zero variance) up to 0 before the root. The n<2 -> NaN floor can't rely on
    # the 0/0 in var (rolling-sum float error makes the numerator tiny-nonzero -> +-inf, and the clamp
    # would mask -inf as 0), so it is enforced explicitly by the mask Ge(n,2)/Ge(n,2) = 1 for n>=2 and
    # 0/0 = NaN for n<2 (anything * NaN = NaN). Qlib Ge returns a BOOL array and bool/bool raises,
    # so cast to float (* 1.0) before the division: 1.0/1.0=1 (n>=2), 0.0/0.0=NaN (n<2).
    mask = f"((Ge({n}, 2) * 1.0) / (Ge({n}, 2) * 1.0))"
    return f"Power(Greater({var}, 0), 0.5) * {mask}"


def norm_upper_shadow():
    """Standardized upper shadow (上影线), per-day: (high - max(open, close)) / high. CICC 图表16."""
    return f"(({ADJ_HIGH_T1} - Greater({ADJ_OPEN_T1}, {ADJ_CLOSE_T1})) / {ADJ_HIGH_T1})"


def norm_lower_shadow():
    """Standardized lower shadow (下影线), per-day: (min(open, close) - low) / low. CICC 图表16."""
    return f"((Less({ADJ_OPEN_T1}, {ADJ_CLOSE_T1}) - {ADJ_LOW_T1}) / {ADJ_LOW_T1})"


def williams_upper_shadow():
    """Williams upper shadow (威廉上影线), per-day: (high - close) / high. CICC 图表16."""
    return f"(({ADJ_HIGH_T1} - {ADJ_CLOSE_T1}) / {ADJ_HIGH_T1})"


def williams_lower_shadow():
    """Williams lower shadow (威廉下影线), per-day: (close - low) / low. CICC 图表16."""
    return f"(({ADJ_CLOSE_T1} - {ADJ_LOW_T1}) / {ADJ_LOW_T1})"


def intraday_highlow():
    """Intraday amplitude (日内振幅), per-day: high / low. CICC 图表16 (distinct from
    risk_range_ratio = (high-low)/close)."""
    return f"({ADJ_HIGH_T1} / {ADJ_LOW_T1})"


# ─────────────────────── Value ───────────────────────

def earnings_yield(kind="ttm"):
    """Earnings yield (E/P ratio).

    Args:
        kind: 'ttm' for trailing twelve months, 'static' for latest period.

    Returns:
        Qlib expression string.
    """
    field = "$pe_ttm" if kind == "ttm" else "$pe"
    return f"1.0 / Ref({field}, 1)"


def book_yield():
    """Book-to-price ratio (B/P).

    Returns:
        Qlib expression string.
    """
    return "1.0 / Ref($pb, 1)"


def sales_yield(kind="ttm"):
    """Sales yield (S/P ratio).

    Args:
        kind: 'ttm' or 'static'.

    Returns:
        Qlib expression string.
    """
    field = "$ps_ttm" if kind == "ttm" else "$ps"
    return f"1.0 / Ref({field}, 1)"


def dividend_yield():
    """Dividend yield (trailing twelve months).

    Returns:
        Qlib expression string.
    """
    return "Ref($dv_ttm, 1) / 100.0"


def dividend_ratio():
    """Dividend ratio (latest period).

    Returns:
        Qlib expression string.
    """
    return "Ref($dv_ratio, 1) / 100.0"


def ocf_yield():
    """Operating cash flow yield (OCF per share / price).

    Both OCFPS and close are in the same adjustment basis,
    so no adj_factor needed.

    Returns:
        Qlib expression string.
    """
    return "Ref($ocfps, 1) / Ref($close, 1)"


def bps_to_price():
    """Book value per share to price ratio.

    Returns:
        Qlib expression string.
    """
    return "Ref($bps, 1) / Ref($close, 1)"


def valuation_change(field, window):
    """Valuation ratio momentum (change over window).

    Args:
        field: Valuation field name without $ (e.g. 'pb', 'pe_ttm').
        window: Lookback for change calculation.

    Returns:
        Qlib expression string.
    """
    return f"Ref(${field}, 1) / Ref(${field}, {window + 1}) - 1"


def relative_valuation(field, window):
    """Current valuation vs its rolling average.

    Args:
        field: Valuation field (e.g. 'pe_ttm').
        window: Rolling average window (e.g. 750 for 3-year).

    Returns:
        Qlib expression string.
    """
    return f"Ref(${field}, 1) / Mean(Ref(${field}, 1), {window})"


# ─────────────────────── Fundamental (Quality / Growth) ───────────────────────

def fundamental(field):
    """Raw fundamental field with 1-day PIT shift.

    Args:
        field: Field name without $ (e.g. 'roe', 'roa', 'or_yoy').

    Returns:
        Qlib expression string.
    """
    return f"Ref(${field}, 1)"


def fundamental_delta(field, lag=1):
    """Change in a fundamental field over lag periods.

    Args:
        field: Field name without $.
        lag: Number of periods to look back.

    Returns:
        Qlib expression string.
    """
    return f"Ref(${field}, 1) - Ref(${field}, {lag + 1})"


def fundamental_slope(field, window):
    """Rolling linear regression slope of a fundamental field.

    Uses Qlib's native Slope operator (C speed).
    Replaces slow ``rolling().apply(polyfit)``.

    Args:
        field: Field name without $.
        window: Rolling window (e.g. 4 for 4-quarter trend).

    Returns:
        Qlib expression string.
    """
    return f"Slope(Ref(${field}, 1), {window})"


def fundamental_stability(field, window):
    """Stability of a fundamental metric (lower vol = better).

    Returns negative std so that higher value = more stable.

    Args:
        field: Field name without $.
        window: Rolling window for std computation.

    Returns:
        Qlib expression string.
    """
    return f"0 - Std(Ref(${field}, 1), {window})"


def fundamental_ratio(numerator, denominator):
    """Ratio of two fundamental fields.

    Args:
        numerator: Field name without $ (e.g. 'ocfps').
        denominator: Field name without $ (e.g. 'eps').

    Returns:
        Qlib expression string.
    """
    return f"Ref(${numerator}, 1) / Ref(${denominator}, 1)"


# ─────────────────────── Volatility / Risk ───────────────────────

def rolling_vol(window):
    """Rolling return volatility (standard deviation).

    Args:
        window: Rolling window in trading days.

    Returns:
        Qlib expression string.
    """
    return f"Std({DAILY_RET}, {window})"


def downside_vol(window):
    """Downside-only return volatility.

    Only considers negative returns.

    Args:
        window: Rolling window.

    Returns:
        Qlib expression string.
    """
    return f"Std(If({DAILY_RET} < 0, {DAILY_RET}, 0), {window})"


def vol_of_vol(inner_window, outer_window):
    """Volatility of volatility.

    Args:
        inner_window: Window for return vol calculation.
        outer_window: Window for vol-of-vol calculation.

    Returns:
        Qlib expression string.
    """
    return f"Std(Std({DAILY_RET}, {inner_window}), {outer_window})"


def rolling_skew(window):
    """Rolling return skewness.

    Args:
        window: Rolling window.

    Returns:
        Qlib expression string.
    """
    return f"Skew({DAILY_RET}, {window})"


def rolling_kurt(window):
    """Rolling return kurtosis.

    Args:
        window: Rolling window.

    Returns:
        Qlib expression string.
    """
    return f"Kurt({DAILY_RET}, {window})"


def tail_risk(window, percentile=0.05):
    """Tail risk measured by return quantile.

    Args:
        window: Rolling window.
        percentile: Quantile level (e.g. 0.05 for VaR 95%).

    Returns:
        Qlib expression string.
    """
    return f"Quantile({DAILY_RET}, {window}, {percentile})"


def max_drawdown_proxy(window):
    """Max drawdown proxy: distance from rolling high.

    Not exact MDD but a fast C-speed approximation.

    Args:
        window: Rolling window for high calculation.

    Returns:
        Qlib expression string.
    """
    return f"{ADJ_CLOSE_T1} / Max({ADJ_HIGH_T1}, {window}) - 1"


def range_ratio(window):
    """Average (High-Low)/Close ratio.

    Measures intraday price range as a % of close.

    Args:
        window: Averaging window.

    Returns:
        Qlib expression string.
    """
    return f"Mean(Ref(($high - $low) / $close, 1), {window})"


def price_slope_normalized(window):
    """Normalized price trend (Slope / Price).

    Uses Qlib's Slope operator for rolling linear regression.

    Args:
        window: Rolling window.

    Returns:
        Qlib expression string.
    """
    return f"Slope({ADJ_CLOSE_T1}, {window}) / {ADJ_CLOSE_T1}"


# ─────────────────────── Liquidity ───────────────────────

def avg_turnover(window, free_float=False):
    """Average turnover rate over N days.

    Args:
        window: Rolling window.
        free_float: If True, use free-float turnover.

    Returns:
        Qlib expression string.
    """
    field = "turnover_rate_f" if free_float else "turnover_rate"
    return f"Mean(Ref(${field}, 1), {window})"


def turnover_ratio(short_window, long_window):
    """Short-term / long-term turnover ratio.

    Values > 1 indicate increasing activity.

    Args:
        short_window: Short-term window (e.g. 5).
        long_window: Long-term window (e.g. 60).

    Returns:
        Qlib expression string.
    """
    return (
        f"Mean(Ref($turnover_rate, 1), {short_window}) / "
        f"Mean(Ref($turnover_rate, 1), {long_window})"
    )


def amihud_illiquidity(window):
    """Amihud illiquidity ratio (|return| / dollar volume).

    Higher values = less liquid.

    Args:
        window: Averaging window.

    Returns:
        Qlib expression string.
    """
    return f"Mean(Abs({DAILY_RET}) / Ref($amount, 1), {window})"


def volume_cv(window):
    """Volume coefficient of variation (std / mean).

    Measures volume predictability.

    Args:
        window: Rolling window.

    Returns:
        Qlib expression string.
    """
    return f"Std(Ref($vol, 1), {window}) / Mean(Ref($vol, 1), {window})"


def log_dollar_volume(window):
    """Log of average daily dollar volume.

    Args:
        window: Averaging window.

    Returns:
        Qlib expression string.
    """
    return f"Log(Mean(Ref($amount, 1) * 1000, {window}))"


def volume_surge(short_window, long_window):
    """Volume surge ratio (short avg / long avg).

    Args:
        short_window: Short-term window (e.g. 5).
        long_window: Long-term window (e.g. 60).

    Returns:
        Qlib expression string.
    """
    return f"Mean(Ref($vol, 1), {short_window}) / Mean(Ref($vol, 1), {long_window})"


def volume_ratio_smoothed(window):
    """Smoothed volume ratio.

    Args:
        window: Smoothing window.

    Returns:
        Qlib expression string.
    """
    return f"Mean(Ref($volume_ratio, 1), {window})"


def turnover_skew(window):
    """Skewness of turnover rate distribution.

    Args:
        window: Rolling window.

    Returns:
        Qlib expression string.
    """
    return f"Skew(Ref($turnover_rate, 1), {window})"


def zero_trade_pct(window):
    """Percentage of zero-volume days over N days.

    Uses ``Sum(If(vol < 1, 1, 0), window) / window``.

    Implementation note: see ``up_down_ratio`` — Qlib ``Count`` is broken in
    this build (ignores the condition, returns N). All conditional counts must
    use ``Sum(If())`` (factor audit 2026-05-30, F1/F4; GPT Round-5).

    Args:
        window: Lookback window.

    Returns:
        Qlib expression string.
    """
    return f"Sum(If(Ref($vol, 1) < 1, 1, 0), {window}) / {window}"


def spread_proxy(window):
    """Bid-ask spread proxy using (High-Low)/Mid.

    Args:
        window: Averaging window.

    Returns:
        Qlib expression string.
    """
    return f"Mean(Ref(($high - $low) / (($high + $low) / 2), 1), {window})"


# ─────────────────────── Technical ───────────────────────

def rsi(window):
    """Relative Strength Index.

    Formula: RSI = 100 - 100 / (1 + avg_gain / avg_loss)

    Args:
        window: RSI period (commonly 6, 14, or 28).

    Returns:
        Qlib expression string.
    """
    gain = f"If({DAILY_RET} > 0, {DAILY_RET}, 0)"
    loss = f"If({DAILY_RET} < 0, 0 - {DAILY_RET}, 0)"
    return f"100 - 100 / (1 + Mean({gain}, {window}) / Mean({loss}, {window}))"


def price_to_ma(window):
    """Price-to-moving-average ratio (with PIT shift).

    Args:
        window: MA window.

    Returns:
        Qlib expression string.
    """
    return f"{ADJ_CLOSE_T1} / Mean({ADJ_CLOSE_T1}, {window}) - 1"


def ma_ratio(short_window, long_window):
    """Moving average ratio (golden/death cross indicator).

    Args:
        short_window: Short MA window (e.g. 5).
        long_window: Long MA window (e.g. 20).

    Returns:
        Qlib expression string.
    """
    return f"Mean({ADJ_CLOSE_T1}, {short_window}) / Mean({ADJ_CLOSE_T1}, {long_window})"


def macd_dif(fast=12, slow=26):
    """MACD DIF line, normalized by price.

    Formula: (EMA(P, fast) - EMA(P, slow)) / P

    Args:
        fast: Fast EMA period.
        slow: Slow EMA period.

    Returns:
        Qlib expression string.
    """
    return (
        f"(EMA({ADJ_CLOSE_T1}, {fast}) - EMA({ADJ_CLOSE_T1}, {slow})) / "
        f"{ADJ_CLOSE_T1}"
    )


def macd_hist(fast=12, slow=26, signal=9):
    """MACD histogram (DIF - DEA), normalized by price.

    Args:
        fast: Fast EMA period.
        slow: Slow EMA period.
        signal: Signal line EMA period.

    Returns:
        Qlib expression string.
    """
    dif = f"(EMA({ADJ_CLOSE_T1}, {fast}) - EMA({ADJ_CLOSE_T1}, {slow}))"
    dea = f"EMA({dif}, {signal})"
    return f"({dif} - {dea}) / {ADJ_CLOSE_T1}"


def distance_from_high(window):
    """Distance from rolling high (negative = below high).

    Args:
        window: Rolling window for high.

    Returns:
        Qlib expression string.
    """
    return f"{ADJ_CLOSE_T1} / Max({ADJ_HIGH_T1}, {window}) - 1"


def distance_from_low(window):
    """Distance from rolling low (positive = above low).

    Args:
        window: Rolling window for low.

    Returns:
        Qlib expression string.
    """
    return f"{ADJ_CLOSE_T1} / Min({ADJ_LOW_T1}, {window}) - 1"


def range_position(window):
    """Position within rolling high-low range [0, 1].

    Args:
        window: Rolling window.

    Returns:
        Qlib expression string.
    """
    return (
        f"({ADJ_CLOSE_T1} - Min({ADJ_LOW_T1}, {window})) / "
        f"(Max({ADJ_HIGH_T1}, {window}) - Min({ADJ_LOW_T1}, {window}))"
    )


def atr_normalized(window=14):
    """Normalized Average True Range.

    Formula: Mean(TrueRange, window) / Price

    Args:
        window: ATR period.

    Returns:
        Qlib expression string.
    """
    # TR = max(H-L, |H-PrevC|, |L-PrevC|)
    # Using _T1 atoms so the TR at time t only looks at data up to t-1,
    # and the "previous close" term is Ref(close, 2) (the close before the
    # shifted "today" used in the other TR legs).
    hl = f"({ADJ_HIGH_T1} - {ADJ_LOW_T1})"
    prev_close_t2 = f"Ref({ADJ_CLOSE}, 2)"
    hpc = f"Abs({ADJ_HIGH_T1} - {prev_close_t2})"
    lpc = f"Abs({ADJ_LOW_T1} - {prev_close_t2})"
    tr = f"If({hl} > {hpc}, If({hl} > {lpc}, {hl}, {lpc}), If({hpc} > {lpc}, {hpc}, {lpc}))"
    return f"Mean({tr}, {window}) / {ADJ_CLOSE_T1}"


def bb_width(window=20):
    """Bollinger Band width (normalized).

    Formula: 2 * Std(P, window) / Mean(P, window)

    Args:
        window: BB period.

    Returns:
        Qlib expression string.
    """
    return f"2 * Std({ADJ_CLOSE_T1}, {window}) / Mean({ADJ_CLOSE_T1}, {window})"


def williams_r(window=14):
    """Williams %R oscillator.

    Formula: (Highest_High - Close) / (Highest_High - Lowest_Low) * -100

    Args:
        window: Lookback window.

    Returns:
        Qlib expression string.
    """
    return (
        f"0 - 100 * (Max({ADJ_HIGH_T1}, {window}) - {ADJ_CLOSE_T1}) / "
        f"(Max({ADJ_HIGH_T1}, {window}) - Min({ADJ_LOW_T1}, {window}))"
    )


def price_vol_corr(window):
    """Price-volume correlation.

    Measures divergence between returns and volume changes.

    Args:
        window: Correlation window.

    Returns:
        Qlib expression string.
    """
    return f"Corr({DAILY_RET}, Ref($vol, 1) / Ref($vol, 2) - 1, {window})"


def obv_slope(window):
    """On-Balance Volume trend (normalized slope).

    Uses signed volume accumulated via Slope as proxy.

    Args:
        window: Rolling window.

    Returns:
        Qlib expression string.
    """
    signed_vol = f"If({DAILY_RET} > 0, Ref($vol, 1), 0 - Ref($vol, 1))"
    return f"Slope(Sum({signed_vol}, {window}), {window})"


def intraday_intensity(window):
    """Intraday intensity index: (2C - H - L) / (H - L).

    Args:
        window: Averaging window.

    Returns:
        Qlib expression string.
    """
    return (
        f"Mean((2 * {ADJ_CLOSE_T1} - {ADJ_HIGH_T1} - {ADJ_LOW_T1}) / "
        f"({ADJ_HIGH_T1} - {ADJ_LOW_T1}), {window})"
    )


# ─────────────────────── Size ───────────────────────

def log_size(field="total_mv"):
    """Log market capitalization.

    Args:
        field: Size field ('total_mv', 'circ_mv', 'float_share', 'free_share').

    Returns:
        Qlib expression string.
    """
    multiplier = " * 10000" if field in ("total_mv", "circ_mv") else ""
    return f"Log(Ref(${field}, 1){multiplier})"


def log_size_squared():
    """Non-linear size (log_mcap²).

    Captures non-linearity in size premium.

    Returns:
        Qlib expression string.
    """
    base = log_size("total_mv")
    return f"Power({base}, 2)"


# ─────────────────────── Leverage ───────────────────────

def leverage_field(field):
    """Leverage / solvency fundamental field with PIT shift.

    Args:
        field: Field name without $ (e.g. 'debt_to_assets', 'current_ratio').

    Returns:
        Qlib expression string.
    """
    return f"Ref(${field}, 1)"


def deleverage(field, lag=1):
    """Deleveraging signal (declining leverage = positive).

    Args:
        field: Leverage field without $.
        lag: Periods for change calculation.

    Returns:
        Qlib expression string.
    """
    return f"0 - (Ref(${field}, 1) - Ref(${field}, {lag + 1}))"


# ─────────────────────── Forward Returns (for evaluation) ───────────────────────

def forward_return(horizon):
    """Forward return for factor evaluation.

    Uses adjusted close to compute forward N-day return.

    Args:
        horizon: Forward horizon in days.

    Returns:
        Qlib expression string.
    """
    return f"Ref({ADJ_CLOSE}, 0 - {horizon}) / {ADJ_CLOSE} - 1"


# ═══════════════════════════════════════════════════════════════════════
#  LAYER 2: DATAFRAME OPERATORS
#
#  Functions that take pandas Series/DataFrame and return Series.
#  Used for cross-sectional operations.
# ═══════════════════════════════════════════════════════════════════════

def _date_level_key(series):
    """The groupby key for a per-DATE cross-section.

    PIT-safety hardening (Phase 7, GPT review): cross-sectional helpers MUST group by the
    DATE level, not positional level 0. A positional ``groupby(level=0)`` on an
    ``(instrument, datetime)`` panel silently ranks each stock ACROSS TIME — so the value at
    factor date ``t`` would absorb that stock's values at ``t+1 … end``, INCLUDING dates after
    that row's label-realization ``r(t)`` → a lookahead leak inside the IS window (same
    MultiIndex-order class as the Phase-6 ``build_is_windowed_panel`` bug).

    Prefer the level NAMED ``datetime`` (robust to either index order); else the
    datetime-TYPED level by dtype; else FAIL CLOSED. A positional level-0 fallback is the leak
    path and is intentionally NOT provided (GPT review: do not re-introduce it).
    """
    names = list(series.index.names)
    if "datetime" in names:
        return "datetime"
    for i in range(series.index.nlevels):
        if pd.api.types.is_datetime64_any_dtype(series.index.get_level_values(i)):
            return i
    raise ValueError(
        "cross-sectional op requires a 'datetime' MultiIndex level; none found "
        f"(index names={names})"
    )


def cs_rank(series):
    """Cross-sectional percentile rank per date.

    Ranks values across all stocks on the same date, returning
    a value in [0, 1].

    Args:
        series: pd.Series with MultiIndex(datetime, instrument) or (instrument, datetime).

    Returns:
        pd.Series with percentile ranks.
    """
    return series.groupby(level=_date_level_key(series)).rank(pct=True)


def cs_zscore(series):
    """Cross-sectional z-score per date.

    Standardizes values to zero mean, unit variance across stocks
    on the same date.

    Args:
        series: pd.Series with MultiIndex(datetime, instrument).

    Returns:
        pd.Series with z-scores.
    """
    key = _date_level_key(series)
    mean = series.groupby(level=key).transform('mean')
    std = series.groupby(level=key).transform('std')
    return (series - mean) / std.replace(0, np.nan)


def cs_demean(series):
    """Cross-sectional demeaning (remove daily mean).

    Args:
        series: pd.Series with MultiIndex(datetime, instrument).

    Returns:
        pd.Series, demeaned.
    """
    return series - series.groupby(level=_date_level_key(series)).transform('mean')


def composite(df, factor_names, weights=None):
    """Weighted rank composite factor.

    Combines multiple factors by computing cross-sectional rank
    of each and then averaging with specified weights.

    Args:
        df: DataFrame with factor columns.
        factor_names: List of column names to combine.
        weights: List of weights (default: equal weight).

    Returns:
        pd.Series with composite score.
    """
    if weights is None:
        weights = [1.0 / len(factor_names)] * len(factor_names)

    result = pd.Series(0.0, index=df.index)
    for name, w in zip(factor_names, weights):
        result = result + w * cs_rank(df[name])
    return result


def neutralize(factor, controls):
    """Neutralize a factor by regressing out control variables.

    Performs cross-sectional OLS regression per date and returns
    the residuals.

    Args:
        factor: pd.Series to neutralize.
        controls: pd.DataFrame of control variables (e.g. size, industry dummies).

    Returns:
        pd.Series of residuals.
    """
    from numpy.linalg import lstsq

    result = factor.copy()
    result[:] = np.nan

    for date in factor.index.get_level_values(0).unique():
        y = factor.loc[date].dropna()
        X = controls.loc[date].reindex(y.index).dropna()
        common = y.index.intersection(X.index)
        if len(common) < 10:
            continue
        y_c = y.loc[common].values
        X_c = X.loc[common].values
        X_c = np.column_stack([X_c, np.ones(len(X_c))])
        try:
            beta, _, _, _ = lstsq(X_c, y_c, rcond=None)
            residual = y_c - X_c @ beta
            result.loc[(date, common)] = residual
        except Exception:
            continue

    return result


def rolling_beta(returns, market_returns, window):
    """Rolling CAPM beta.

    Computes beta = Cov(stock, market) / Var(market) using
    rolling window.

    Args:
        returns: pd.Series of stock returns with MultiIndex.
        market_returns: pd.Series of market returns indexed by datetime.
        window: Rolling window.

    Returns:
        pd.Series of beta values.
    """
    mkt = market_returns.reindex(returns.index, level=0)
    cov = (returns * mkt).groupby(level=1).transform(
        lambda x: x.rolling(window).mean()
    ) - returns.groupby(level=1).transform(
        lambda x: x.rolling(window).mean()
    ) * mkt.groupby(level=1).transform(
        lambda x: x.rolling(window).mean()
    )
    var_mkt = mkt.groupby(level=1).transform(
        lambda x: x.rolling(window).var()
    )
    return cov / var_mkt.replace(0, np.nan)


def winsorize(series, lower=0.01, upper=0.99):
    """Cross-sectional winsorization per date.

    Clips values at the specified percentiles on each date.

    Args:
        series: pd.Series with MultiIndex(datetime, instrument).
        lower: Lower percentile cutoff.
        upper: Upper percentile cutoff.

    Returns:
        pd.Series, winsorized.
    """
    def _clip_group(group):
        lo = group.quantile(lower)
        hi = group.quantile(upper)
        return group.clip(lo, hi)
    return series.groupby(level=_date_level_key(series)).transform(_clip_group)


# ═══════════════════════════════════════════════════════════════════════
#  CONVENIENCE: Batch Compute via Qlib
# ═══════════════════════════════════════════════════════════════════════

def compute_factors(catalog, start_date, end_date, horizons=None,
                    qlib_dir=None, kernels=1, progress_interval=60,
                    stage="is_only"):
    """Batch-compute all Layer 1 factors via Qlib's expression engine.

    Passes all expression strings to a single D.features() call for
    maximum performance (Qlib's DAG optimizer deduplicates shared
    sub-expressions like Ref($close, 1)).

    Args:
        catalog: Dict of {factor_name: qlib_expression_string}.
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).
        horizons: Optional list of forward return horizons (e.g. [5, 10, 20]).
        qlib_dir: Optional path to Qlib data directory.
        kernels: Optional Qlib worker count. Defaults to ``1`` on this
            Windows setup to avoid joblib worker-pipe permission failures.
            When a caller explicitly requests Qlib's default worker behavior
            (for example by passing ``None``), PermissionError-based worker
            startup failures on Windows will be retried automatically with
            ``kernels=1``.
        progress_interval: Heartbeat interval in seconds for the long-running
            Qlib compute step. Set <= 0 to disable.
        stage: Either ``"is_only"`` (default, backward compat) or
            ``"oos_test"``. Threaded into ``qlib_windowed_features`` so that
            cache_manifest enforcement and window safety are correctly
            stage-tagged. Plan ref: jolly-seeking-lollipop Gate 0 (fix for
            pre-existing OOS leak where stage was hardcoded to ``"is_only"``
            regardless of actual run window).

    Returns:
        Tuple of (factors_df, fwd_df) both with MultiIndex(datetime, instrument).
        If horizons is None, fwd_df is an empty DataFrame.
    """
    import qlib
    from qlib.data import D
    from qlib.config import REG_CN

    if qlib_dir is None:
        project_root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        qlib_dir = os.path.join(project_root, 'data', 'qlib_data')

    # Build merged field list
    fields = []
    names = []
    for name, expr in catalog.items():
        fields.append(expr)
        names.append(name)

    # Add forward returns if requested
    if horizons:
        for h in horizons:
            fields.append(forward_return(h))
            names.append(f'fwd_{h}d')

    logger.info(f"Computing {len(catalog)} factors"
                f"{f' + {len(horizons)} forward returns' if horizons else ''} "
                f"via Qlib expression engine...")
    requested_kernels = kernels
    attempted_kernels = [kernels]
    if kernels is None:
        attempted_kernels.append(1)

    df = None
    effective_kernels = None
    last_exc = None
    heartbeat_name = f"Factor computation ({len(fields)} fields)"

    for attempt_idx, current_kernels in enumerate(attempted_kernels, start=1):
        init_kwargs = {"provider_uri": qlib_dir, "region": REG_CN}
        if current_kernels is not None:
            init_kwargs["kernels"] = current_kernels
        kernel_label = _kernel_label(current_kernels)
        t0 = time.time()
        stop_event, heartbeat_thread = _start_progress_heartbeat(
            heartbeat_name, progress_interval
        )
        try:
            qlib.init(**init_kwargs)
            logger.info(
                f"Qlib initialized for factor computation (kernels={kernel_label}, "
                f"attempt={attempt_idx}/{len(attempted_kernels)})"
            )
            instruments = D.instruments(market='all_stocks')
            df = qlib_windowed_features(
                instruments=instruments,
                fields=fields,
                start_time=start_date,
                end_time=end_date,
                cache_context=CacheContext(),
                stage=stage,
            )
            effective_kernels = current_kernels
            break
        except Exception as exc:
            last_exc = exc
            if current_kernels is not None or not _is_worker_permission_error(exc):
                raise
            logger.warning(
                "Qlib parallel worker startup failed with %s (%s). "
                "Retrying factor computation with kernels=1.",
                kernel_label,
                exc,
            )
        finally:
            if stop_event is not None:
                stop_event.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join()

    if df is None:
        raise last_exc

    df.columns = names
    df = df.swaplevel().sort_index()

    elapsed = time.time() - t0
    n_stocks = df.index.get_level_values(1).nunique()
    n_dates = df.index.get_level_values(0).nunique()
    logger.info(f"Computed {df.shape[1]} columns × {df.shape[0]:,} rows "
                f"({n_stocks} stocks × {n_dates} dates) in {elapsed:.1f}s")

    # Split factors and forward returns
    fwd_cols = [c for c in df.columns if c.startswith('fwd_')]
    factor_cols = [c for c in df.columns if not c.startswith('fwd_')]

    factors_df = df[factor_cols]
    fwd_df = df[fwd_cols] if fwd_cols else pd.DataFrame(index=df.index)
    factors_df.attrs["qlib_requested_kernels"] = _kernel_label(requested_kernels)
    factors_df.attrs["qlib_effective_kernels"] = _kernel_label(effective_kernels)
    fwd_df.attrs["qlib_requested_kernels"] = _kernel_label(requested_kernels)
    fwd_df.attrs["qlib_effective_kernels"] = _kernel_label(effective_kernels)

    return factors_df, fwd_df


def add_composites(factors_df, composite_defs=None, progress_every=5):
    """Add Layer 2 composite factors using cross-sectional ranking.

    Args:
        factors_df: DataFrame from compute_factors().
        composite_defs: Optional list of composite definitions.
            Each is a dict with 'name', 'components', 'weights', 'negate' keys.
            If None, uses the default composite definitions.
        progress_every: Log progress every N composites.

    Returns:
        DataFrame with additional composite columns.
    """
    if composite_defs is None:
        from .catalog import get_composite_defs
        composite_defs = get_composite_defs()

    logger.info(f"Computing {len(composite_defs)} composite factors...")
    df = factors_df
    total = len(composite_defs)
    start_time = time.time()
    rank_cache = {}
    composite_columns = {}

    for i, cdef in enumerate(composite_defs, start=1):
        name = cdef['name']
        components = cdef['components']
        weights = cdef.get('weights', None)
        negates = cdef.get('negate', [False] * len(components))

        # Check all components exist
        missing = [c for c in components if c not in df.columns]
        if missing:
            logger.warning(f"  Skipping {name}: missing {missing}")
            continue

        # Build composite via rank averaging
        if weights is None:
            weights = [1.0 / len(components)] * len(components)

        result = pd.Series(0.0, index=df.index)
        for comp, w, neg in zip(components, weights, negates):
            cache_key = (comp, neg)
            ranked = rank_cache.get(cache_key)
            if ranked is None:
                vals = df[comp]
                if neg:
                    vals = 0 - vals
                ranked = cs_rank(vals)
                rank_cache[cache_key] = ranked
            result = result + w * ranked

        composite_columns[name] = result

        should_log = (
            i == 1 or
            i == total or
            (progress_every and progress_every > 0 and i % progress_every == 0)
        )
        if should_log:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else float("nan")
            logger.info(
                f"  Composite {i}/{total}: {name} "
                f"(elapsed {elapsed:.1f}s, ETA {eta:.1f}s)"
            )

    if composite_columns:
        df = pd.concat([df, pd.DataFrame(composite_columns, index=df.index)], axis=1)

    comp_count = sum(1 for c in df.columns if c.startswith('comp_'))
    logger.info(f"  Added {comp_count} composite factors")
    return df


def add_industry_relative_composites(
    factors_df: pd.DataFrame,
    industry_series: pd.Series,
    market_cap: pd.Series | None = None,
    defs: list[dict] | None = None,
    *,
    progress_every: int = 5,
) -> pd.DataFrame:
    """Append industry-relative composite factors that require external
    industry labels (outside the pure-Qlib-expression composite path).

    Each def in ``defs`` (default: ``catalog.get_industry_relative_defs()``)
    references a ``base`` factor that must already be present in
    ``factors_df``. Two transform kinds:

    * ``industry_mean_subtract`` — ``base - groupby((date, industry)).mean()``
      within the ``industry_series.notna()`` mask. Stocks with NaN industry
      get NaN output (no silent reference-category misclassification —
      Codex review-3 finding I4).
    * ``size_industry_neutralize`` — uses
      ``factor_eval.neutralization.neutralize_size_industry`` which
      regresses base on log(market_cap) + industry dummies and returns
      residuals. ``market_cap`` must be passed (Codex review-3 finding B2:
      use ``neutralize_size_industry``, not ``neutralize_industry``, for
      size+industry).

    PIT safety: this is Layer 2 post-processing. No new ``$field``
    references are introduced — base factors come from the catalog and
    are already PIT-validated by the static parser. Industry labels are
    sourced from the SW2021 membership file via
    ``provider_metadata.build_industry_series_asof`` (also PIT-safe by
    construction — uses ``in_date`` ≤ as_of < ``out_date``).

    Args:
        factors_df: DataFrame with MultiIndex(datetime, instrument) or
            (instrument, datetime). All ``base`` columns from ``defs``
            must already be present.
        industry_series: Aligned Series of industry codes. Same index as
            ``factors_df``. NaN for stocks without an SW2021 mapping on
            the date.
        market_cap: Aligned Series of market caps. Required if any def
            has ``kind='size_industry_neutralize'``.
        defs: Override registry. Default: catalog.get_industry_relative_defs().
        progress_every: Log progress every N factors.

    Returns:
        ``factors_df`` extended with one column per def. Columns are
        ``np.float32``.

    Plan ref: vast-exploring-rabbit v8 phase B3.2.
    """
    from .catalog import get_industry_relative_defs

    if defs is None:
        defs = get_industry_relative_defs()
    if not defs:
        return factors_df

    # Align inputs to factors_df.index
    industry_aligned = industry_series.reindex(factors_df.index)
    if market_cap is not None:
        mcap_aligned = market_cap.reindex(factors_df.index)
    else:
        mcap_aligned = None

    new_columns: dict[str, pd.Series] = {}
    total = len(defs)
    start_time = time.time()

    for i, d in enumerate(defs, start=1):
        name = d["name"]
        base = d["base"]
        kind = d["kind"]
        if base not in factors_df.columns:
            logger.warning(
                "  Skipping %s: base factor %s not in factors_df columns", name, base
            )
            continue

        base_series = factors_df[base]

        if kind == "industry_mean_subtract":
            # Find the datetime level position
            names = list(factors_df.index.names)
            if "datetime" in names:
                dt_level = names.index("datetime")
            else:
                # Heuristic: datetime is the level whose values are datetime-like
                lvl0 = factors_df.index.get_level_values(0)
                dt_level = 0 if pd.api.types.is_datetime64_any_dtype(lvl0) else 1
            # Group by (date, industry) and subtract mean within each group
            mask = industry_aligned.notna()
            grouped = base_series.where(mask).groupby(
                [factors_df.index.get_level_values(dt_level), industry_aligned]
            )
            industry_mean = grouped.transform("mean")
            relative = base_series - industry_mean
            relative = relative.where(mask)  # null industry → NaN output
            new_columns[name] = relative.astype(np.float32)

        elif kind == "size_industry_neutralize":
            if mcap_aligned is None:
                logger.warning(
                    "  Skipping %s: requires market_cap (size_industry_neutralize)",
                    name,
                )
                continue
            from src.alpha_research.factor_eval.neutralization import (
                neutralize_size_industry,
            )
            mask = industry_aligned.notna() & mcap_aligned.notna()
            base_masked = base_series.where(mask)
            mcap_masked = mcap_aligned.where(mask)
            ind_masked = industry_aligned.where(mask)
            try:
                residual = neutralize_size_industry(
                    base_masked, mcap_masked, ind_masked
                )
                new_columns[name] = residual.astype(np.float32)
            except Exception as e:
                logger.warning(
                    "  Skipping %s: size_industry_neutralize failed (%s)",
                    name,
                    e,
                )
                continue

        else:
            logger.warning(
                "  Skipping %s: unknown kind=%r", name, kind
            )
            continue

        should_log = (
            i == 1
            or i == total
            or (progress_every and progress_every > 0 and i % progress_every == 0)
        )
        if should_log:
            elapsed = time.time() - start_time
            logger.info(
                f"  Industry-rel {i}/{total}: {name} ({kind}, elapsed {elapsed:.1f}s)"
            )

    if new_columns:
        df_out = pd.concat(
            [factors_df, pd.DataFrame(new_columns, index=factors_df.index)],
            axis=1,
        )
        logger.info(
            "  Added %d industry-relative factors", len(new_columns)
        )
        return df_out
    return factors_df
