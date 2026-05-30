"""Follow-up Plan #1 — Per-operator expression lock tests.

These tests are brittle-on-purpose: they assert the EXACT post-fix
expression string for each rewritten operator. Any future edit that
changes an expression becomes a visible diff in this file, forcing the
author to update the lock tests alongside the operator.

This complements ``test_factor_library_pit_safety.py`` (which is a
policy check) by locking the specific shape of the rewrite. Both are
needed: the policy check guarantees no `$field` leak, the lock tests
guarantee a specific approved rewrite.

Ref: plan file ``C:\\Users\\henry\\.claude\\plans\\vast-exploring-rabbit.md``
Step 3.
"""

from __future__ import annotations

import re
import unittest

from src.alpha_research.factor_library import operators
from src.alpha_research.factor_library.catalog import get_factor_catalog


class OperatorAtomsTests(unittest.TestCase):
    """Module-level constants (DAILY_RET, ADJ_*_T1)."""

    def test_adj_close_unchanged(self):
        self.assertEqual(operators.ADJ_CLOSE, "($close * $adj_factor)")

    def test_adj_open_unchanged(self):
        self.assertEqual(operators.ADJ_OPEN, "($open * $adj_factor)")

    def test_adj_high_unchanged(self):
        self.assertEqual(operators.ADJ_HIGH, "($high * $adj_factor)")

    def test_adj_low_unchanged(self):
        self.assertEqual(operators.ADJ_LOW, "($low * $adj_factor)")

    def test_adj_close_t1(self):
        self.assertEqual(operators.ADJ_CLOSE_T1, "Ref(($close * $adj_factor), 1)")

    def test_adj_open_t1(self):
        self.assertEqual(operators.ADJ_OPEN_T1, "Ref(($open * $adj_factor), 1)")

    def test_adj_high_t1(self):
        self.assertEqual(operators.ADJ_HIGH_T1, "Ref(($high * $adj_factor), 1)")

    def test_adj_low_t1(self):
        self.assertEqual(operators.ADJ_LOW_T1, "Ref(($low * $adj_factor), 1)")

    def test_daily_ret_post_fix(self):
        """DAILY_RET at time t must be (close_{t-1} / close_{t-2}) - 1."""
        self.assertEqual(
            operators.DAILY_RET,
            "(Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1)",
        )


class MomentumReversalOperatorTests(unittest.TestCase):

    def test_momentum_uses_ref_1_and_ref_window_plus_1(self):
        self.assertEqual(
            operators.momentum(20),
            "Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 21) - 1",
        )

    def test_skip_momentum_uses_ref_skip_plus_1_and_total_plus_1(self):
        self.assertEqual(
            operators.skip_momentum(21, 252),
            "Ref(($close * $adj_factor), 22) / Ref(($close * $adj_factor), 253) - 1",
        )

    def test_short_reversal(self):
        self.assertEqual(
            operators.short_reversal(5),
            "0 - (Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 6) - 1)",
        )

    def test_ema_return_uses_fixed_daily_ret(self):
        self.assertEqual(
            operators.ema_return(20),
            f"EMA({operators.DAILY_RET}, 20)",
        )

    def test_wma_return_uses_fixed_daily_ret(self):
        self.assertEqual(
            operators.wma_return(120),
            f"WMA({operators.DAILY_RET}, 120)",
        )

    def test_overnight_return_uses_t1_open_and_ref_close_2(self):
        self.assertEqual(
            operators.overnight_return(20),
            "Mean(Ref(($open * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1, 20)",
        )

    def test_intraday_return_uses_t1_close_and_t1_open(self):
        self.assertEqual(
            operators.intraday_return(20),
            "Mean(Ref(($close * $adj_factor), 1) / Ref(($open * $adj_factor), 1) - 1, 20)",
        )

    def test_high_moment_uses_t1_high_and_t1_open(self):
        self.assertEqual(
            operators.high_moment(20),
            "Mean((Ref(($high * $adj_factor), 1) - Ref(($open * $adj_factor), 1)) / Ref(($open * $adj_factor), 1), 20)",
        )

    def test_low_moment_uses_t1_low_and_t1_open(self):
        self.assertEqual(
            operators.low_moment(20),
            "Mean((Ref(($low * $adj_factor), 1) - Ref(($open * $adj_factor), 1)) / Ref(($open * $adj_factor), 1), 20)",
        )

    def test_max_single_return_uses_fixed_daily_ret(self):
        self.assertEqual(
            operators.max_single_return(20),
            f"Max({operators.DAILY_RET}, 20)",
        )

    def test_up_down_ratio_uses_fixed_daily_ret(self):
        # Factor audit 2026-05-30 (F1/F4): switched Count → Sum(If(...,1,0))
        # because Qlib Count(cond, N) in this build returns N (ignores the
        # condition). GPT 5.5 Pro Round-5 mandatory fix.
        self.assertEqual(
            operators.up_down_ratio(20),
            f"Sum(If({operators.DAILY_RET} > 0, 1, 0), 20) / 20",
        )


class FundamentalOperatorTests(unittest.TestCase):

    def test_fundamental_unchanged(self):
        self.assertEqual(operators.fundamental("roe"), "Ref($roe, 1)")

    def test_fundamental_delta_unchanged(self):
        self.assertEqual(operators.fundamental_delta("roe", 1), "Ref($roe, 1) - Ref($roe, 2)")

    def test_fundamental_ratio_unchanged(self):
        self.assertEqual(
            operators.fundamental_ratio("ocfps", "eps"),
            "Ref($ocfps, 1) / Ref($eps, 1)",
        )

    def test_relative_valuation_inner_ref(self):
        self.assertEqual(
            operators.relative_valuation("pe_ttm", 750),
            "Ref($pe_ttm, 1) / Mean(Ref($pe_ttm, 1), 750)",
        )

    def test_fundamental_slope_inner_ref(self):
        self.assertEqual(
            operators.fundamental_slope("roe", 4),
            "Slope(Ref($roe, 1), 4)",
        )

    def test_fundamental_stability_inner_ref(self):
        self.assertEqual(
            operators.fundamental_stability("roe", 60),
            "0 - Std(Ref($roe, 1), 60)",
        )


class VolatilityRiskOperatorTests(unittest.TestCase):

    def test_rolling_vol_uses_fixed_daily_ret(self):
        self.assertEqual(
            operators.rolling_vol(20),
            f"Std({operators.DAILY_RET}, 20)",
        )

    def test_downside_vol_uses_fixed_daily_ret(self):
        expected = f"Std(If({operators.DAILY_RET} < 0, {operators.DAILY_RET}, 0), 20)"
        self.assertEqual(operators.downside_vol(20), expected)

    def test_max_drawdown_proxy_uses_t1_atoms(self):
        self.assertEqual(
            operators.max_drawdown_proxy(60),
            "Ref(($close * $adj_factor), 1) / Max(Ref(($high * $adj_factor), 1), 60) - 1",
        )

    def test_range_ratio_wraps_inner_in_ref(self):
        self.assertEqual(
            operators.range_ratio(20),
            "Mean(Ref(($high - $low) / $close, 1), 20)",
        )


class LiquidityOperatorTests(unittest.TestCase):

    def test_avg_turnover_wraps_field(self):
        self.assertEqual(
            operators.avg_turnover(20),
            "Mean(Ref($turnover_rate, 1), 20)",
        )

    def test_avg_turnover_free_float_wraps_field(self):
        self.assertEqual(
            operators.avg_turnover(20, free_float=True),
            "Mean(Ref($turnover_rate_f, 1), 20)",
        )

    def test_turnover_ratio_wraps_both_sides(self):
        self.assertEqual(
            operators.turnover_ratio(5, 60),
            "Mean(Ref($turnover_rate, 1), 5) / Mean(Ref($turnover_rate, 1), 60)",
        )

    def test_amihud_illiquidity_wraps_amount(self):
        self.assertEqual(
            operators.amihud_illiquidity(20),
            f"Mean(Abs({operators.DAILY_RET}) / Ref($amount, 1), 20)",
        )

    def test_volume_cv_wraps_vol(self):
        self.assertEqual(
            operators.volume_cv(20),
            "Std(Ref($vol, 1), 20) / Mean(Ref($vol, 1), 20)",
        )

    def test_log_dollar_volume_wraps_amount(self):
        self.assertEqual(
            operators.log_dollar_volume(20),
            "Log(Mean(Ref($amount, 1) * 1000, 20))",
        )

    def test_volume_surge_wraps_vol(self):
        self.assertEqual(
            operators.volume_surge(5, 60),
            "Mean(Ref($vol, 1), 5) / Mean(Ref($vol, 1), 60)",
        )

    def test_volume_ratio_smoothed_wraps_field(self):
        self.assertEqual(
            operators.volume_ratio_smoothed(5),
            "Mean(Ref($volume_ratio, 1), 5)",
        )

    def test_turnover_skew_wraps_field(self):
        self.assertEqual(
            operators.turnover_skew(20),
            "Skew(Ref($turnover_rate, 1), 20)",
        )

    def test_zero_trade_pct_wraps_vol(self):
        # Factor audit 2026-05-30 (F1/F4): switched Count → Sum(If(...,1,0))
        # (Qlib Count is broken in this build). GPT 5.5 Pro Round-5.
        self.assertEqual(
            operators.zero_trade_pct(20),
            "Sum(If(Ref($vol, 1) < 1, 1, 0), 20) / 20",
        )

    def test_spread_proxy_wraps_inner_in_ref(self):
        self.assertEqual(
            operators.spread_proxy(20),
            "Mean(Ref(($high - $low) / (($high + $low) / 2), 1), 20)",
        )


class TechnicalOperatorTests(unittest.TestCase):

    def test_price_to_ma_uses_t1_close(self):
        self.assertEqual(
            operators.price_to_ma(20),
            "Ref(($close * $adj_factor), 1) / Mean(Ref(($close * $adj_factor), 1), 20) - 1",
        )

    def test_ma_ratio_uses_t1_close_both_sides(self):
        self.assertEqual(
            operators.ma_ratio(5, 20),
            "Mean(Ref(($close * $adj_factor), 1), 5) / Mean(Ref(($close * $adj_factor), 1), 20)",
        )

    def test_macd_dif_uses_t1_close(self):
        self.assertEqual(
            operators.macd_dif(12, 26),
            "(EMA(Ref(($close * $adj_factor), 1), 12) - EMA(Ref(($close * $adj_factor), 1), 26)) / Ref(($close * $adj_factor), 1)",
        )

    def test_distance_from_high_uses_t1_atoms(self):
        self.assertEqual(
            operators.distance_from_high(20),
            "Ref(($close * $adj_factor), 1) / Max(Ref(($high * $adj_factor), 1), 20) - 1",
        )

    def test_distance_from_low_uses_t1_atoms(self):
        self.assertEqual(
            operators.distance_from_low(20),
            "Ref(($close * $adj_factor), 1) / Min(Ref(($low * $adj_factor), 1), 20) - 1",
        )

    def test_range_position_uses_t1_atoms(self):
        self.assertEqual(
            operators.range_position(20),
            "(Ref(($close * $adj_factor), 1) - Min(Ref(($low * $adj_factor), 1), 20)) / (Max(Ref(($high * $adj_factor), 1), 20) - Min(Ref(($low * $adj_factor), 1), 20))",
        )

    def test_bb_width_uses_t1_close(self):
        self.assertEqual(
            operators.bb_width(20),
            "2 * Std(Ref(($close * $adj_factor), 1), 20) / Mean(Ref(($close * $adj_factor), 1), 20)",
        )

    def test_williams_r_uses_t1_atoms(self):
        self.assertEqual(
            operators.williams_r(14),
            "0 - 100 * (Max(Ref(($high * $adj_factor), 1), 14) - Ref(($close * $adj_factor), 1)) / (Max(Ref(($high * $adj_factor), 1), 14) - Min(Ref(($low * $adj_factor), 1), 14))",
        )

    def test_intraday_intensity_uses_t1_atoms(self):
        self.assertEqual(
            operators.intraday_intensity(20),
            "Mean((2 * Ref(($close * $adj_factor), 1) - Ref(($high * $adj_factor), 1) - Ref(($low * $adj_factor), 1)) / (Ref(($high * $adj_factor), 1) - Ref(($low * $adj_factor), 1)), 20)",
        )


class LabelOperatorTests(unittest.TestCase):
    """forward_return is an allowlisted forward-looking label; it must stay unshifted."""

    def test_forward_return_unchanged(self):
        # This is the prediction target. Must use TODAY'S close as denominator
        # and close[t+horizon] as numerator. Any change here breaks the label.
        self.assertEqual(
            operators.forward_return(5),
            "Ref(($close * $adj_factor), 0 - 5) / ($close * $adj_factor) - 1",
        )


# Match a `Count(` call token (word boundary so it does not match e.g. a
# hypothetical `DiscountFoo(`). Whitespace between Count and ( is tolerated.
_COUNT_CALL_RE = re.compile(r"\bCount\s*\(")


class CountOperatorBanTests(unittest.TestCase):
    """Guard the PRODUCTION factor library against the broken Qlib ``Count``.

    Factor audit 2026-05-30 (F1): in this Qlib build (0.9.7), ``Count(cond, N)``
    counts non-null observations and IGNORES the boolean condition — verified
    empirically (``Count(ret>0,5) ≡ 5`` for every stock). Any factor using it is
    silently degenerate (constant cross-section). The fix is ``Sum(If(cond, 1, 0), N)``.

    The candidate-pipeline validator (``workspace/scripts/validate_factor_candidates.py``)
    already lints ``Count(`` out of candidate CSVs. These tests extend that guard
    to the PRODUCTION library (``operators.py`` + ``catalog.py``) so a future
    hand-written operator or catalog entry that reintroduces ``Count`` fails in
    CI (this module is in the offline-pit-checks set), not just in the candidate
    tooling.
    """

    def _assert_no_count(self, label: str, expr: str) -> None:
        self.assertIsNotNone(expr, f"{label}: expression is None")
        self.assertNotRegex(
            expr,
            _COUNT_CALL_RE,
            f"{label} uses the broken Qlib Count() operator (counts non-null obs, "
            f"ignores the condition in this build). Use Sum(If(cond, 1, 0), N) "
            f"instead. Expression: {expr!r}",
        )

    def test_count_call_regex_sanity(self):
        # The matcher catches real Count calls but not substrings of other names.
        self.assertRegex("Count(x > 0, 20)", _COUNT_CALL_RE)
        self.assertRegex("Sum(Count(x > 0, 5), 20)", _COUNT_CALL_RE)
        self.assertNotRegex("Sum(If(x > 0, 1, 0), 20)", _COUNT_CALL_RE)
        self.assertNotRegex("DiscountRate(x, 5)", _COUNT_CALL_RE)

    def test_known_count_operators_are_fixed(self):
        # The two operators the F1/F4 fix rewrote must no longer emit Count.
        self._assert_no_count("up_down_ratio(20)", operators.up_down_ratio(20))
        self._assert_no_count("zero_trade_pct(20)", operators.zero_trade_pct(20))

    def test_no_count_in_base_catalog(self):
        for name, expr in get_factor_catalog(include_new_data=False).items():
            self._assert_no_count(f"catalog[{name}]", expr)

    def test_no_count_in_full_catalog_with_new_data(self):
        # include_new_data=True adds the flow/north/margin/earn/alpha-endpoint
        # factors — the ones most likely to want a conditional count.
        for name, expr in get_factor_catalog(include_new_data=True).items():
            self._assert_no_count(f"catalog+new[{name}]", expr)


if __name__ == "__main__":
    unittest.main()
