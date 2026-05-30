# Qlib Expression Engine Guide

This guide documents the validated Qlib expression patterns for factor computation in the A-share multi-factor research framework. All operators listed here execute at C/Cython speed and are safe to use in `operators.py`.

## 1. Price Adjustment Rules (CRITICAL)

When writing expressions, you must decide whether to use **adjusted** or **raw** prices based on the factor's mathematical property.

### Use Adjusted Prices (`($close * $adj_factor)`)
**Rule**: Any operation that compares prices across different days must use adjusted prices to prevent artificial jumps from stock splits or dividends.
*   **Returns / Momentum**: `(($close * $adj_factor) / Ref(($close * $adj_factor), 20)) - 1`
*   **Volatility**: `Std(return, 20)`
*   **Moving Average Ratios**: `Ref(($close * $adj_factor), 1) / Mean(($close * $adj_factor), 20)`
*   **Distance to High/Low**: `Ref(($close * $adj_factor), 1) / Max(($high * $adj_factor), 60)`
*   **Important**: Always wrap adjusted-price atoms in parentheses before reusing them inside larger expressions. Without parentheses, Qlib follows normal `*`/`/` precedence and can silently change the formula.

### Use Raw Values (`$close`, `$pe_ttm`, `$turnover_rate`)
**Rule**: Use raw values when the metric is a pre-calculated ratio, when it's evaluated at a single point in time, or when both numerator and denominator share the same adjustment basis.
*   **Valuation Ratios**: `1 / $pe_ttm`, `1 / $pb`
*   **Per-Share Ratios**: `$ocfps / $close` (10:1 split divides both equally, ratio unchanged)
*   **Fundamentals**: `$roe`, `$or_yoy`, `$grossprofit_margin`
*   **Volume Metrics**: `$turnover_rate` (already normalized by float), `$amount` (total turnover in yuan)

---

## 2. Point-in-Time (PIT) Leakage Prevention

All factor expressions **must** use `Ref(..., 1)` to shift data by one day. 

*   `Ref($pe_ttm, 1)` uses yesterday's valuation to predict today's return.
*   `Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 21) - 1` computes 20-day momentum ending yesterday.
*   **Never** use `$close` directly in a predictive factor expression.

---

## 3. Supported Qlib Operators

The following operators have been validated to run correctly.

### Arithmetic & Math
*   `+`, `-`, `*`, `/` (Standard infix arithmetic. Note: adjusted-price subexpressions should be parenthesized when reused)
*   `Abs(x)`
*   `Log(x)`
*   `Power(x, n)`
*   `Sign(x)`

### Logical & Conditional
*   `>`, `<`, `>=`, `<=`, `==`, `!=`
*   `If(condition, true_value, false_value)`

### Time-Series Shifts
*   `Ref(x, n)`: Value of `x` from `n` days ago (use negative `n` for future values).
*   `Delta(x, n)`: Equivalent to `x - Ref(x, n)`.

### Rolling Statistics
*   `Mean(x, n)`
*   `Std(x, n)`
*   `Var(x, n)`
*   `Sum(x, n)`
*   `Max(x, n)`
*   `Min(x, n)`
*   `Med(x, n)`: Rolling median.
*   `Mad(x, n)`: Rolling mean absolute deviation.
*   ~~`Count(condition, n)`~~ — **BROKEN in this Qlib build, do not use in factor
    expressions.** Empirically `Count(cond, N)` returns `N` (the count of non-NaN
    observations) and IGNORES the condition (factor audit 2026-05-30, F1; verified:
    `Count(ret > 0, 5) ≡ 5` for every stock). **Use `Sum(If(condition, 1, 0), n)` instead**
    for conditional counts. The validator at
    `workspace/scripts/validate_factor_candidates.py` now hard-bans `Count(` in factor
    expressions.

### Advanced Rolling Statistics
*   `Skew(x, n)`
*   `Kurt(x, n)`
*   `Rank(x, n)`: Time-series percentile rank [0, 1].
*   `Quantile(x, n, pct)`: e.g., `Quantile(ret, 20, 0.05)` for 5% VaR.

### Moving Averages
*   `EMA(x, n)`: True exponential moving average.
*   `WMA(x, n)`: Weighted moving average (linear weighting).

### Cross-Series Operations
*   `Corr(x, y, n)`: Rolling correlation between `x` and `y`.
*   `Cov(x, y, n)`: Rolling covariance.
*   `Slope(x, n)`: Rolling linear regression slope of `x` against time.
*   `Resi(x, n)`: Residuals from rolling regression.
*   `Rsquare(x, n)`: R-squared of rolling regression.

### Index Positions
*   `IdxMax(x, n)` / `IdxMin(x, n)`: **1-indexed position of the extreme within the trailing
    window, counting from the OLDEST bar** (factor audit 2026-05-30, F2; verified empirically
    against pandas argmax, corr=-1.0 with the naive "days since" reading). A fresh extreme
    (today) returns `n`; an extreme `n-1` bars ago returns `1`.
    *   "Days since extreme" = `n - IdxMax(x, n)` (0 means today is the high).
    *   "Freshness score" = `IdxMax(x, n)` directly (higher = more recent).
    *   Sign of any "age"-style factor must be set against `n - IdxMax(...)`, NOT `0 - IdxMax(...)`.

---

## 4. Known Bugs & Workarounds

### Unary Negation `TypeError`
**Issue**: Qlib's parser fails on unary negation of operator returns, e.g., `-Std($roe, 60)`. It will raise `TypeError: bad operand type for unary -: 'Std'`.
**Fix**: Use `0 - Operator(...)` instead.
```python
# WRONG
return f"-Std($roe, {window})"

# CORRECT
return f"0 - Std($roe, {window})"
```

## 5. Adding Composite Factors

Cross-sectional operations (like ranking across all stocks on a given day) cannot be expressed as Qlib strings. They are computed in Layer 2 (pandas) using `cs_rank(series)`.

To add a new composite factor:
1. Define the components in `operators.py` (Layer 1).
2. Add the composite definition to `get_composite_defs()` in `catalog.py`.
3. Use the `negate` flag if a component needs to be inverted (e.g., lower volatility should get a higher rank, so set `negate=True` for the volatility component).
