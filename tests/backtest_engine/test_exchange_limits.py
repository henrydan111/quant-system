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
        # Pre-registration main-board IPO-first-day rule: +44% / -36%
        # (ASYMMETRIC, referenced to the issue price). Tushare carries
        # up_limit=20.16 AND down_limit=8.96 off a pre_close of 14.0
        # (real: 002728.SZ 2014-07-31); the ±10% band (15.40 / 12.60) would
        # miss BOTH sides. up_band=20.16/14.0-1=+44%; dn_band=1-8.96/14.0=-36%.
        up_row = self._row(raw_close=20.16, close=20.16,
                           raw_pre_close=14.0, pre_close=14.0,
                           up_limit=20.16, down_limit=8.96)
        self.assertTrue(self.ex.is_limit_up(up_row, "002728.SZ", self.date))
        down_row = self._row(raw_close=8.96, close=8.96,
                             raw_pre_close=14.0, pre_close=14.0,
                             up_limit=20.16, down_limit=8.96)
        self.assertTrue(self.ex.is_limit_down(down_row, "002728.SZ", self.date))
        # Sanity: the computed ±10% band alone would flag NEITHER side.
        band_up, band_down = self.ex.compute_limit_prices(14.0, 0.10)
        self.assertAlmostEqual(band_up, 15.40, places=2)
        self.assertAlmostEqual(band_down, 12.60, places=2)

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

    # ── 2026-06-22: fill-price-aware gate (open-fill tests open, not close) ──
    def test_is_limit_up_fill_price_aware_open_below_close_at(self):
        # Opened BELOW the limit (buyable at 09:35) but CLOSED limit-up. The
        # default/close gate flags it; the OPEN gate does NOT — you could buy at
        # the open. This is the bull-market parity fix (果仁 sm_纯市值01).
        row = self._row(raw_close=13.48, close=13.48, raw_open=12.80, open=12.80,
                        up_limit=13.48, down_limit=11.03)
        self.assertTrue(self.ex.is_limit_up(row, self.code, self.date))                          # default raw_close
        self.assertTrue(self.ex.is_limit_up(row, self.code, self.date, price_field="raw_close"))
        self.assertFalse(self.ex.is_limit_up(row, self.code, self.date, price_field="raw_open"))

    def test_is_limit_up_locked_at_open(self):
        # 一字: opened AT the limit (locked) → still un-buyable on the open gate.
        row = self._row(raw_close=13.48, close=13.48, raw_open=13.48, open=13.48,
                        up_limit=13.48, down_limit=11.03)
        self.assertTrue(self.ex.is_limit_up(row, self.code, self.date, price_field="raw_open"))

    def test_can_buy_open_fill_allows_name_that_closes_limit_up(self):
        # The core fix end-to-end: opens tradeable, closes limit-up → BUYABLE on an
        # open fill, BLOCKED on a close fill.
        row = self._row(raw_close=13.48, close=13.48, raw_open=12.80, open=12.80,
                        up_limit=13.48, down_limit=11.03, vol=100000)
        self.assertTrue(self.ex.can_buy(row, self.code, self.date, price_field="raw_open"))
        self.assertFalse(self.ex.can_buy(row, self.code, self.date, price_field="raw_close"))

    def test_can_sell_open_fill_allows_name_that_closes_limit_down(self):
        # Symmetric: opens tradeable, closes limit-down → SELLABLE on an open fill,
        # BLOCKED on a close fill.
        row = self._row(raw_close=11.03, close=11.03, raw_open=11.80, open=11.80,
                        up_limit=13.48, down_limit=11.03, vol=100000)
        self.assertTrue(self.ex.can_sell(row, self.code, self.date, price_field="raw_open"))
        self.assertFalse(self.ex.can_sell(row, self.code, self.date, price_field="raw_close"))

    # ── 2026-06-22: all_day_lock gate (daily-AVERAGE fill mode) ──
    def test_all_day_lock_buy_blocked_when_yizi(self):
        # 一字涨停: high==low==up_limit -> unbuyable all day on the avg-fill gate.
        row = self._row(raw_close=13.48, close=13.48, raw_high=13.48, raw_low=13.48,
                        up_limit=13.48, down_limit=11.03, vol=100000)
        self.assertTrue(self.ex.is_all_day_limit_up(row, self.code, self.date))
        self.assertFalse(self.ex.can_buy(row, self.code, self.date,
                                         price_field="raw_avg", limit_gate="all_day_lock"))

    def test_all_day_lock_buy_allowed_when_traded(self):
        # Opened AT the limit but traded down (low<up) -> NOT all-day-locked -> buyable.
        row = self._row(raw_close=13.48, close=13.48, raw_open=13.48, raw_high=13.48, raw_low=12.00,
                        up_limit=13.48, down_limit=11.03, vol=100000)
        self.assertFalse(self.ex.is_all_day_limit_up(row, self.code, self.date))
        self.assertTrue(self.ex.can_buy(row, self.code, self.date,
                                        price_field="raw_avg", limit_gate="all_day_lock"))

    def test_all_day_lock_sell_blocked_when_yizi_down(self):
        row = self._row(raw_close=11.03, close=11.03, raw_high=11.03, raw_low=11.03,
                        up_limit=13.48, down_limit=11.03, vol=100000)
        self.assertTrue(self.ex.is_all_day_limit_down(row, self.code, self.date))
        self.assertFalse(self.ex.can_sell(row, self.code, self.date,
                                          price_field="raw_avg", limit_gate="all_day_lock"))

    def test_all_day_lock_sell_allowed_when_traded(self):
        row = self._row(raw_close=11.03, close=11.03, raw_high=12.00, raw_low=11.03,
                        up_limit=13.48, down_limit=11.03, vol=100000)
        self.assertFalse(self.ex.is_all_day_limit_down(row, self.code, self.date))
        self.assertTrue(self.ex.can_sell(row, self.code, self.date,
                                         price_field="raw_avg", limit_gate="all_day_lock"))

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


class _FakeFeeder:
    """Minimal QlibDataFeeder stand-in for is_true_no_limit_day's regime branch.

    Provides only the two methods the predicate calls: get_stock_basic()
    (ts_code -> list_date) and count_trading_days(start, end) inclusive. Trading
    days are approximated by a pure business-day calendar — sufficient because
    every probed window is ≤6 days and the test dates avoid exchange holidays,
    so business-day arithmetic equals the trading-day count exactly.
    """

    def __init__(self, list_dates: dict):
        self._sb = pd.DataFrame(
            [{"ts_code": c, "list_date": pd.Timestamp(d)} for c, d in list_dates.items()]
        )

    def get_stock_basic(self):
        return self._sb

    def count_trading_days(self, start, end):
        if pd.isna(start) or pd.isna(end) or end < start:
            return 0
        return len(pd.bdate_range(start, end))  # inclusive both ends


def _ipo_day(list_date, k):
    """The k-th IPO trading day (k=1 == listing day), business-day basis."""
    return pd.bdate_range(pd.Timestamp(list_date), periods=k)[-1]


class IsTrueNoLimitDayTests(unittest.TestCase):
    """2026-06-22 (GPT cross-review Major-2): can_buy's no-limit bypass now uses
    is_true_no_limit_day, NOT is_ipo_period. is_ipo_period treated EVERY nominal
    IPO-window first day as no-limit — including a pre-registration-reform
    main-board first day capped at the old +44% / −36% rule (a REAL published
    limit). These tests pin the corrected behavior: the sentinel branch, the
    listing-date regime branch, the window boundaries, and the decisive
    old-main-board-+44% case that must remain UN-buyable when locked."""

    # Listing-date regimes spanning every board + reform boundary.
    _LIST_DATES = {
        "002728.SZ": "2014-07-31",  # old main board (pre-注册制) — +44% first day
        "601001.SH": "2023-05-10",  # main board, post-2023-04-10 全面注册制 (no-limit 5d)
        "300999.SZ": "2021-03-15",  # ChiNext, post-2020-08-24 reform (no-limit 5d)
        "300100.SZ": "2019-05-10",  # ChiNext, PRE-reform — +44% first day
        "688981.SH": "2020-07-16",  # STAR — registration-based (no-limit 5d)
        "920690.BJ": "2023-09-01",  # BSE — listing day only
    }

    def setUp(self):
        self.feeder = _FakeFeeder(self._LIST_DATES)
        self.ex = Exchange(slippage_model=NoSlippage(), feeder=self.feeder)
        self.date = pd.Timestamp("2024-01-15")

    def _row(self, **kw):
        base = {"raw_close": 11.0, "close": 11.0,
                "raw_pre_close": 10.0, "pre_close": 10.0, "vol": 100000}
        base.update(kw)
        return pd.Series(base)

    # ── Branch 1: published no-limit sentinel is definitive (no feeder needed) ──
    def test_sentinel_is_no_limit_main_board(self):
        # up_limit≈1e6 / down_limit≈0.01 → no-limit regardless of board/date.
        row = self._row(up_limit=1000000.0, down_limit=0.01)
        self.assertTrue(self.ex.is_true_no_limit_day("601001.SH", self.date, row))

    def test_sentinel_is_no_limit_bse(self):
        # BSE listing-day sentinel is 99999.99 — below the literal 100000 but
        # above any real limit; the 99999.0 floor catches it.
        row = self._row(up_limit=99999.99, down_limit=0.00)
        self.assertTrue(self.ex.is_true_no_limit_day("920690.BJ", self.date, row))

    def test_real_plus44_limit_is_not_sentinel(self):
        # The +44% IPO limit (up_limit 20.16) is a REAL limit, not the sentinel.
        row = self._row(raw_close=20.16, close=20.16, raw_pre_close=14.0,
                        pre_close=14.0, up_limit=20.16, down_limit=8.96)
        self.assertFalse(self.ex.is_true_no_limit_day("002728.SZ", self.date, row))

    # ── REQUIRED CASE 1: old main-board IPO first day at +44% → can_buy False ──
    def test_old_main_board_first_day_plus44_cannot_buy(self):
        date = pd.Timestamp("2014-07-31")  # 002728.SZ listing day (day 1)
        row = self._row(raw_close=20.16, close=20.16, raw_pre_close=14.0,
                        pre_close=14.0, up_limit=20.16, down_limit=8.96)
        # It IS inside the nominal IPO window (the old, buggy bypass said yes)...
        self.assertTrue(self.ex.is_ipo_period("002728.SZ", date))
        # ...but it is NOT a true no-limit day (the +44% cap is a real limit)...
        self.assertFalse(self.ex.is_true_no_limit_day("002728.SZ", date, row))
        # ...and it is locked at the up-limit → un-buyable.
        self.assertTrue(self.ex.is_limit_up(row, "002728.SZ", date))
        self.assertFalse(self.ex.can_buy(row, "002728.SZ", date))

    # ── REQUIRED CASE 2: post-2023 main-board first-5-days no-limit → can_buy True ──
    def test_post_2023_main_board_first5_no_limit_can_buy(self):
        # Day 3, stk_limit coverage hole (no up/down fields). Close sits exactly
        # at the steady-state +10% band, which WOULD flag limit-up — but the
        # registration-regime bypass rescues the buy.
        date = _ipo_day("2023-05-10", 3)
        row = self._row(raw_close=11.0, close=11.0)  # 10.0 × 1.10, no fields
        self.assertTrue(self.ex.is_limit_up(row, "601001.SH", date))      # computed band fires
        self.assertTrue(self.ex.is_true_no_limit_day("601001.SH", date, row))
        self.assertTrue(self.ex.can_buy(row, "601001.SH", date))

    def test_post_2023_main_board_window_closes_day6(self):
        # Day 6 — window expired → a real +10% limit-up is genuinely un-buyable.
        date = _ipo_day("2023-05-10", 6)
        row = self._row(raw_close=11.0, close=11.0)
        self.assertFalse(self.ex.is_true_no_limit_day("601001.SH", date, row))
        self.assertFalse(self.ex.can_buy(row, "601001.SH", date))

    # ── REQUIRED CASE 3: ChiNext post-reform first-5-days → can_buy True ──
    def test_chinext_post_reform_first5_no_limit_can_buy(self):
        date = _ipo_day("2021-03-15", 3)
        row = self._row(raw_close=12.0, close=12.0)  # 10.0 × 1.20 (ChiNext band)
        self.assertTrue(self.ex.is_limit_up(row, "300999.SZ", date))
        self.assertTrue(self.ex.is_true_no_limit_day("300999.SZ", date, row))
        self.assertTrue(self.ex.can_buy(row, "300999.SZ", date))

    def test_chinext_post_reform_window_closes_day6(self):
        date = _ipo_day("2021-03-15", 6)
        row = self._row(raw_close=12.0, close=12.0)
        self.assertFalse(self.ex.is_true_no_limit_day("300999.SZ", date, row))
        self.assertFalse(self.ex.can_buy(row, "300999.SZ", date))

    # ── Pre-reform ChiNext first day is +44% → NOT no-limit ──
    def test_pre_reform_chinext_first_day_not_no_limit(self):
        date = pd.Timestamp("2019-05-10")  # 300100.SZ listing day, pre-reform
        row = self._row(raw_close=20.16, close=20.16, raw_pre_close=14.0,
                        pre_close=14.0, up_limit=20.16, down_limit=8.96)
        self.assertFalse(self.ex.is_true_no_limit_day("300100.SZ", date, row))
        self.assertFalse(self.ex.can_buy(row, "300100.SZ", date))

    # ── STAR first 5 days are no-limit ──
    def test_star_first5_no_limit(self):
        d3 = _ipo_day("2020-07-16", 3)
        self.assertTrue(self.ex.is_true_no_limit_day("688981.SH", d3, self._row()))
        d6 = _ipo_day("2020-07-16", 6)
        self.assertFalse(self.ex.is_true_no_limit_day("688981.SH", d6, self._row()))

    # ── BSE: listing day only ──
    def test_bse_listing_day_only(self):
        d1 = pd.Timestamp("2023-09-01")          # listing day
        d2 = _ipo_day("2023-09-01", 2)
        self.assertTrue(self.ex.is_true_no_limit_day("920690.BJ", d1, self._row()))
        self.assertFalse(self.ex.is_true_no_limit_day("920690.BJ", d2, self._row()))

    # ── No feeder + no sentinel → conservative False (cannot confirm no-limit) ──
    def test_no_feeder_no_sentinel_is_false(self):
        ex = Exchange(slippage_model=NoSlippage())  # feeder=None
        row = self._row(raw_close=20.16, close=20.16, up_limit=20.16, down_limit=8.96)
        self.assertFalse(ex.is_true_no_limit_day("002728.SZ", self.date, row))

    def test_no_feeder_sentinel_still_true(self):
        # Even without a feeder, the published sentinel alone confirms no-limit.
        ex = Exchange(slippage_model=NoSlippage())
        row = self._row(up_limit=1000000.0, down_limit=0.01)
        self.assertTrue(ex.is_true_no_limit_day("601001.SH", self.date, row))


if __name__ == "__main__":
    unittest.main()
