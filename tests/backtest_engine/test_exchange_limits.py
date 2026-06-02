"""Follow-up Plan #2 — Limit price + IPO period regression tests (P1-1, P1-2)."""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest_engine.event_driven.exchange import (
    Exchange,
    NoSlippage,
    _round_half_up_2dp,
)


class RoundHalfUpTests(unittest.TestCase):
    """P1-1: verify the rounding helper uses round-half-up, not banker's."""

    def test_round_half_up_exact(self):
        self.assertEqual(_round_half_up_2dp(10.125), 10.13)  # banker's would give 10.12

    def test_round_half_up_down(self):
        self.assertEqual(_round_half_up_2dp(10.124), 10.12)

    def test_round_half_up_up(self):
        self.assertEqual(_round_half_up_2dp(10.126), 10.13)

    def test_round_half_up_negative(self):
        # Decimal ROUND_HALF_UP rounds .5 AWAY from zero, so -10.125 -> -10.13
        # This is correct for the mathematical definition; limit prices are
        # always positive in A-shares so the negative case doesn't arise.
        self.assertEqual(_round_half_up_2dp(-10.125), -10.13)

    def test_round_half_up_whole_number(self):
        self.assertEqual(_round_half_up_2dp(10.00), 10.00)


class LimitPriceTests(unittest.TestCase):
    def setUp(self):
        self.ex = Exchange(slippage_model=NoSlippage())

    def test_main_board_limit_10pct(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("000001.SZ", False, pd.Timestamp("2024-01-15")),
            0.10,
        )

    def test_st_limit_5pct(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("000001.SZ", True, pd.Timestamp("2024-01-15")),
            0.05,
        )

    def test_chinext_pre_2020_reform(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("300001.SZ", False, pd.Timestamp("2020-08-23")),
            0.10,
        )

    def test_chinext_post_2020_reform(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("300001.SZ", False, pd.Timestamp("2020-08-24")),
            0.20,
        )

    def test_star_limit_20pct(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("688001.SH", False, pd.Timestamp("2024-01-15")),
            0.20,
        )

    def test_bse_limit_30pct(self):
        self.assertAlmostEqual(
            self.ex.get_limit_pct("830001.BJ", False, pd.Timestamp("2024-01-15")),
            0.30,
        )

    def test_limit_price_rounding_half_up_boundary(self):
        """A pre_close that produces .xx5 midpoint should round up."""
        # pre_close=10.05, limit_pct=0.10
        # limit_up = 10.05 * 1.10 = 11.055 -> round-half-up -> 11.06
        # (banker's would give 11.06 here too, so use a trickier case)
        # pre_close=10.25, limit_pct=0.10
        # limit_up = 10.25 * 1.10 = 11.275 -> round-half-up -> 11.28
        # (banker's round(11.275, 2) -> 11.28 also, hmm)
        # Better: pre_close=10.15, limit_pct=0.10
        # limit_up = 10.15 * 1.10 = 11.165 -> round-half-up -> 11.17
        # banker's: round(11.165, 2) -> 11.16  (half-to-even rounds DOWN)
        limit_up, _ = self.ex.compute_limit_prices(10.15, 0.10)
        self.assertAlmostEqual(limit_up, 11.17, places=2)


class ResolveLimitPricesTests(unittest.TestCase):
    """2026-06-02: the engine now uses Tushare's published stk_limit prices
    ($up_limit/$down_limit) as the PRIMARY limit source, with the computed
    round-half-up band as the FALLBACK. These tests pin both paths."""

    def setUp(self):
        self.ex = Exchange(slippage_model=NoSlippage())
        self.code = "000001.SZ"
        self.date = pd.Timestamp("2024-01-15")

    def _row(self, **kw):
        base = {"raw_close": 13.48, "close": 13.48,
                "raw_pre_close": 12.25, "pre_close": 12.25}
        base.update(kw)
        return pd.Series(base)

    # ── Primary path: Tushare fields present ──────────────────────────
    def test_primary_uses_tushare_fields_verbatim(self):
        row = self._row(up_limit=13.48, down_limit=11.03)
        up, down = self.ex.resolve_limit_prices(row, self.code, self.date)
        self.assertAlmostEqual(up, 13.48, places=2)
        self.assertAlmostEqual(down, 11.03, places=2)

    def test_primary_beats_computed_band(self):
        # IPO-first-day ±44% rule: Tushare carries up_limit=20.16 off a
        # pre_close of 14.0, which the ±10% band formula (→15.40) would miss.
        row = self._row(raw_close=20.16, close=20.16,
                        raw_pre_close=14.0, pre_close=14.0,
                        up_limit=20.16, down_limit=7.84)
        self.assertTrue(self.ex.is_limit_up(row, "002728.SZ", self.date))
        # Sanity: the computed band alone would NOT flag this as limit-up.
        band_up, _ = self.ex.compute_limit_prices(14.0, 0.10)
        self.assertAlmostEqual(band_up, 15.40, places=2)

    def test_is_limit_up_via_tushare(self):
        row = self._row(raw_close=13.48, close=13.48, up_limit=13.48, down_limit=11.03)
        self.assertTrue(self.ex.is_limit_up(row, self.code, self.date))

    def test_is_limit_down_via_tushare(self):
        row = self._row(raw_close=11.03, close=11.03, up_limit=13.48, down_limit=11.03)
        self.assertTrue(self.ex.is_limit_down(row, self.code, self.date))

    def test_not_at_limit_via_tushare(self):
        row = self._row(raw_close=12.50, close=12.50, up_limit=13.48, down_limit=11.03)
        self.assertFalse(self.ex.is_limit_up(row, self.code, self.date))
        self.assertFalse(self.ex.is_limit_down(row, self.code, self.date))

    # ── Fallback path: Tushare fields absent / NaN ────────────────────
    def test_fallback_when_fields_absent(self):
        # No up_limit/down_limit keys → compute from pre_close × band.
        row = self._row()
        up, down = self.ex.resolve_limit_prices(row, self.code, self.date)
        self.assertAlmostEqual(up, 13.48, places=2)   # 12.25 × 1.10 = 13.475 → 13.48
        self.assertAlmostEqual(down, 11.03, places=2)  # 12.25 × 0.90 = 11.025 → 11.03

    def test_fallback_when_fields_nan(self):
        row = self._row(up_limit=float("nan"), down_limit=float("nan"))
        up, down = self.ex.resolve_limit_prices(row, self.code, self.date)
        self.assertAlmostEqual(up, 13.48, places=2)
        self.assertAlmostEqual(down, 11.03, places=2)

    def test_fallback_is_limit_up_detects(self):
        row = self._row(raw_close=13.48, close=13.48)  # no Tushare fields
        self.assertTrue(self.ex.is_limit_up(row, self.code, self.date))

    def test_computed_alone_misses_ipo44_without_field(self):
        # The decisive corner case: an IPO-first-day ±44% close that the
        # computed band cannot detect. Without the Tushare field the engine
        # would WRONGLY think the stock is freely buyable.
        row = self._row(raw_close=20.16, close=20.16,
                        raw_pre_close=14.0, pre_close=14.0)  # no fields
        self.assertFalse(self.ex.is_limit_up(row, "002728.SZ", self.date))

    # ── One-field-present is treated as a (defensive) fallback ─────────
    def test_one_field_present_falls_back_for_both(self):
        # Tushare ships up/down as a pair (verified: gaps are always both-NaN).
        # If only one side is present, resolve falls back to the computed band
        # for BOTH so we never mix a real limit with a stale/unknown one.
        row_up_only = self._row(up_limit=99.99, down_limit=float("nan"))
        up, down = self.ex.resolve_limit_prices(row_up_only, self.code, self.date)
        self.assertAlmostEqual(up, 13.48, places=2)   # computed, NOT 99.99
        self.assertAlmostEqual(down, 11.03, places=2)

        row_down_only = self._row(down_limit=0.01)  # up_limit key absent
        up2, down2 = self.ex.resolve_limit_prices(row_down_only, self.code, self.date)
        self.assertAlmostEqual(up2, 13.48, places=2)
        self.assertAlmostEqual(down2, 11.03, places=2)  # computed, NOT 0.01

    def test_none_valued_fields_fall_back(self):
        row = self._row(up_limit=None, down_limit=None)
        up, down = self.ex.resolve_limit_prices(row, self.code, self.date)
        self.assertAlmostEqual(up, 13.48, places=2)
        self.assertAlmostEqual(down, 11.03, places=2)

    # ── Detection tolerance (±0.005, half a 分) ───────────────────────
    def test_tolerance_just_inside(self):
        # close 0.004 below the Tushare up_limit → still flagged limit-up.
        row = self._row(raw_close=13.476, close=13.476, up_limit=13.48, down_limit=11.03)
        self.assertTrue(self.ex.is_limit_up(row, self.code, self.date))

    def test_tolerance_just_outside(self):
        # close 0.006 below the Tushare up_limit → NOT limit-up.
        row = self._row(raw_close=13.474, close=13.474, up_limit=13.48, down_limit=11.03)
        self.assertFalse(self.ex.is_limit_up(row, self.code, self.date))

    # ── Fallback respects the multi-tier board bands ──────────────────
    def test_fallback_respects_chinext_20pct_tier(self):
        # ChiNext (300xxx) post-reform, no Tushare field → computed ±20%.
        row = self._row(raw_close=24.0, close=24.0, raw_pre_close=20.0, pre_close=20.0)
        up, down = self.ex.resolve_limit_prices(row, "300001.SZ", self.date)
        self.assertAlmostEqual(up, 24.0, places=2)   # 20.0 × 1.20
        self.assertAlmostEqual(down, 16.0, places=2)  # 20.0 × 0.80
        self.assertTrue(self.ex.is_limit_up(row, "300001.SZ", self.date))

    def test_fallback_respects_bse_30pct_tier(self):
        # BSE (83xxxx) — the real 2021-launch gap case → computed ±30%.
        row = self._row(raw_close=13.0, close=13.0, raw_pre_close=10.0, pre_close=10.0)
        up, down = self.ex.resolve_limit_prices(row, "832317.BJ", self.date)
        self.assertAlmostEqual(up, 13.0, places=2)   # 10.0 × 1.30
        self.assertAlmostEqual(down, 7.0, places=2)   # 10.0 × 0.70

    # ── Tushare value overrides a DIFFERENT computed band ─────────────
    # ── No-limit IPO days: Tushare uses a wide-open SENTINEL, not NaN ──
    def test_no_limit_day_sentinel_is_not_a_limit(self):
        # ChiNext/STAR/main-board first-5-days (post-2023 全面注册制) carry
        # up_limit≈1e6 and down_limit≈0.01 — verified on real 2024 IPOs
        # (300784.SZ, 688717.SH, 603325.SH). The stock is freely tradable:
        # close can be +300% and is neither limit-up nor limit-down.
        row = self._row(raw_close=127.00, close=127.00,
                        raw_pre_close=28.30, pre_close=28.30,
                        up_limit=1000000.0, down_limit=0.01)
        self.assertFalse(self.ex.is_limit_up(row, "300784.SZ", self.date))
        self.assertFalse(self.ex.is_limit_down(row, "300784.SZ", self.date))
        # The sentinel is used verbatim (primary path), NOT the ±20% fallback.
        up, down = self.ex.resolve_limit_prices(row, "300784.SZ", self.date)
        self.assertAlmostEqual(up, 1000000.0, places=2)
        self.assertAlmostEqual(down, 0.01, places=2)

    def test_no_limit_day_bse_sentinel(self):
        # BSE listing day: up_limit≈99999.99, down_limit≈0.00 (920690.BJ).
        row = self._row(raw_close=21.01, close=21.01,
                        raw_pre_close=9.34, pre_close=9.34,
                        up_limit=99999.99, down_limit=0.00)
        self.assertFalse(self.ex.is_limit_up(row, "920690.BJ", self.date))
        self.assertFalse(self.ex.is_limit_down(row, "920690.BJ", self.date))

    def test_tushare_value_overrides_divergent_computed(self):
        # Penny-stock fen-rounding: pre_close 0.95, Tushare up_limit 1.05
        # (implied 10.5% due to 0.01 tick rounding). The computed ±10% band
        # would give 0.95×1.10=1.045 → 1.05 here too, so use an ST mismatch:
        # a non-ST main-board stock where Tushare says ±5%-style 1.00 — prove
        # resolve returns the Tushare number verbatim, not the ±10% computed.
        row = self._row(raw_close=1.00, close=1.00, raw_pre_close=0.95, pre_close=0.95,
                        up_limit=1.00, down_limit=0.90)
        up, down = self.ex.resolve_limit_prices(row, self.code, self.date)
        self.assertAlmostEqual(up, 1.00, places=2)   # Tushare, not 0.95×1.10=1.05
        self.assertAlmostEqual(down, 0.90, places=2)


if __name__ == "__main__":
    unittest.main()
