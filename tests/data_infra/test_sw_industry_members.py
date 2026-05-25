"""Tests for SW2021 historical industry membership data + lookup helpers.

Plan ref: vast-exploring-rabbit v8 phase C1.

Fails loudly if `data/universe/industry_sw2021_members/industry_sw2021_members.parquet`
is missing — no `pytest.skip`. Tests must prove acquisition AND lookup correctness.
"""
from __future__ import annotations

import time
import unittest
from pathlib import Path

import pandas as pd

from src.data_infra.provider_metadata import (
    build_industry_series_asof,
    industry_as_of,
    load_sw_members,
    _normalize_ts_code,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMBERS_PATH = (
    PROJECT_ROOT
    / "data"
    / "universe"
    / "industry_sw2021_members"
    / "industry_sw2021_members.parquet"
)


class SWIndustryBootstrapTests(unittest.TestCase):
    """Acquisition + schema + coverage tests."""

    @classmethod
    def setUpClass(cls):
        if not MEMBERS_PATH.exists():
            raise FileNotFoundError(
                f"SW2021 members missing at {MEMBERS_PATH}. "
                "Run scripts/fetch_sw_industry_members.py before running this suite."
            )
        cls.members = load_sw_members()

    def test_bootstrap_file_exists(self):
        self.assertTrue(MEMBERS_PATH.exists(), f"Missing: {MEMBERS_PATH}")
        self.assertGreater(MEMBERS_PATH.stat().st_size, 50_000, "File suspiciously small")

    def test_endpoint_schema_locked(self):
        """The 11 columns from Tushare's index_member_all + our normalizations."""
        required = {
            "ts_code", "l1_code", "l1_name", "l2_code", "l2_name",
            "l3_code", "l3_name", "in_date", "out_date", "is_new",
        }
        missing = required - set(self.members.columns)
        self.assertEqual(missing, set(), f"Missing required columns: {missing}")
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(self.members["in_date"]))
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(self.members["out_date"]))

    def test_coverage_2008_baseline(self):
        """Every Monday in 2008 should have >= 94% L1 coverage of the daily universe.

        Threshold matches the empirical floor from the 2026-04-27 audit
        (94.68% on 2008-01-02). Survivorship analysis at
        workspace/outputs/sw_industry_coverage_audit_20260427.md showed the
        gap is uniform Tushare backfill thinness, not survivorship bias.
        """
        mondays = pd.date_range("2008-01-07", "2008-12-29", freq="W-MON")
        coverages = []
        for d in mondays:
            yyyymmdd = d.strftime("%Y%m%d")
            daily_path = (
                PROJECT_ROOT / "data" / "market" / "daily" / "2008"
                / f"daily_{yyyymmdd}.parquet"
            )
            if not daily_path.exists():
                continue
            basket = set(pd.read_parquet(daily_path, columns=["ts_code"])["ts_code"].unique())
            if not basket:
                continue
            classified = set(
                self.members[
                    (self.members["in_date"] <= d) & (self.members["out_date"] >= d)
                ]["ts_code"].unique()
            )
            coverage = len(basket & classified) / len(basket)
            coverages.append(coverage)
        self.assertGreater(len(coverages), 30, "Need at least 30 Mondays sampled")
        avg = sum(coverages) / len(coverages)
        # Empirical floor 94.68% on 2008-01-02; allow 94% as a safety buffer
        self.assertGreaterEqual(avg, 0.94, f"2008 average coverage {avg*100:.2f}% below 94% floor")

    def test_coverage_2020_baseline(self):
        """2020 monthly coverage must average >= 96.5% (audit measured 96.80%)."""
        sample_dates = pd.date_range("2020-01-31", "2020-12-31", freq="ME")
        coverages = []
        for d in sample_dates:
            yyyymmdd = d.strftime("%Y%m%d")
            daily_path = (
                PROJECT_ROOT / "data" / "market" / "daily" / "2020"
                / f"daily_{yyyymmdd}.parquet"
            )
            if not daily_path.exists():
                continue
            basket = set(pd.read_parquet(daily_path, columns=["ts_code"])["ts_code"].unique())
            classified = set(
                self.members[
                    (self.members["in_date"] <= d) & (self.members["out_date"] >= d)
                ]["ts_code"].unique()
            )
            coverages.append(len(basket & classified) / len(basket))
        self.assertGreater(len(coverages), 5)
        avg = sum(coverages) / len(coverages)
        self.assertGreaterEqual(avg, 0.965, f"2020 average coverage {avg*100:.2f}% below 96.5% floor")


class IndustryAsOfTests(unittest.TestCase):
    """Pinned-fact + format-agnostic tests for the per-stock lookup."""

    def test_known_classifications_kweichow_moutai(self):
        # 贵州茅台 → 食品饮料 (801120.SI)
        result = industry_as_of("600519.SH", pd.Timestamp("2024-01-01"), "L1")
        self.assertEqual(result, "801120.SI")

    def test_known_classifications_pingan_bank(self):
        # 平安银行 → 银行 (801780.SI)
        result = industry_as_of("000001.SZ", pd.Timestamp("2024-01-01"), "L1")
        self.assertEqual(result, "801780.SI")

    def test_known_classifications_pre_2014(self):
        # 平安银行 deep history — banking has stable membership
        result = industry_as_of("000001.SZ", pd.Timestamp("2008-12-31"), "L1")
        self.assertEqual(result, "801780.SI")

    def test_ts_code_format_all_three(self):
        """Tushare dot-form, uppercase Qlib, lowercase Qlib must all return same result."""
        as_of = pd.Timestamp("2024-01-01")
        a = industry_as_of("600519.SH", as_of, "L1")
        b = industry_as_of("600519_SH", as_of, "L1")
        c = industry_as_of("600519_sh", as_of, "L1")
        self.assertEqual(a, b)
        self.assertEqual(b, c)
        self.assertEqual(a, "801120.SI")

    def test_unclassified_returns_none(self):
        """Stocks with no SW2021 membership return None (not raise, not silent default)."""
        # Pick a date wildly out of range
        result = industry_as_of("000001.SZ", pd.Timestamp("1980-01-01"), "L1")
        self.assertIsNone(result)

    def test_normalize_ts_code(self):
        self.assertEqual(_normalize_ts_code("600519.SH"), "600519.SH")
        self.assertEqual(_normalize_ts_code("600519_SH"), "600519.SH")
        self.assertEqual(_normalize_ts_code("600519_sh"), "600519.SH")
        self.assertEqual(_normalize_ts_code("  000001.SZ  "), "000001.SZ")


class TimeVaryingTests(unittest.TestCase):
    """Prove time-varying membership is actually captured (the whole point)."""

    def test_at_least_one_stock_has_multiple_l1_memberships(self):
        members = load_sw_members()
        per_stock_l1_counts = members.groupby("ts_code")["l1_code"].nunique()
        multi_industry = per_stock_l1_counts[per_stock_l1_counts >= 2]
        self.assertGreater(
            len(multi_industry), 5,
            "Time-varying assumption broken: <6 stocks have multiple L1 memberships. "
            "If this fails, check that the bootstrap fetched is_new='N' (historical) "
            "branch — currently the data has 1,940 historical (is_new='N') rows."
        )

    def test_time_varying_lookup_returns_different_codes(self):
        """For a stock with ≥2 L1 memberships, pre-/post-move dates differ."""
        members = load_sw_members()
        per_stock_l1_counts = members.groupby("ts_code")["l1_code"].nunique()
        multi = per_stock_l1_counts[per_stock_l1_counts >= 2]
        if multi.empty:
            self.skipTest("No multi-industry stock in data")

        ts_code = multi.index[0]
        rows = members[members["ts_code"] == ts_code].sort_values("in_date")
        if len(rows) < 2:
            self.skipTest("Not enough rows for first multi stock")

        # Pick a date right after the first in_date and another right after the second
        first_in = rows.iloc[0]["in_date"] + pd.Timedelta(days=10)
        second_in = rows.iloc[1]["in_date"] + pd.Timedelta(days=10)
        # Skip if the second_in is past the first row's out_date (overlapping is fine, just sample mid-window)
        first_l1 = industry_as_of(ts_code, first_in, "L1")
        second_l1 = industry_as_of(ts_code, second_in, "L1")
        self.assertIsNotNone(first_l1)
        self.assertIsNotNone(second_l1)
        # If the stock genuinely moved L1 the codes should differ at SOME point;
        # this tests one such transition.
        self.assertNotEqual(
            first_l1, second_l1,
            f"Time-varying lookup test: {ts_code} returned same L1 ({first_l1}) "
            f"on {first_in.date()} and {second_in.date()} — expected difference."
        )


class IndustrySeriesAsOfTests(unittest.TestCase):
    """Vectorized helper tests + performance gate."""

    def test_datetime_instrument_ordering(self):
        idx = pd.MultiIndex.from_product(
            [pd.date_range("2024-01-01", "2024-01-10"), ["000001.SZ", "600519.SH"]],
            names=["datetime", "instrument"],
        )
        out = build_industry_series_asof(idx, "L1")
        self.assertEqual(len(out), len(idx))
        # 000001 → 801780, 600519 → 801120 throughout 2024-01
        self.assertEqual(out.notna().sum(), len(idx))

    def test_instrument_datetime_ordering(self):
        idx = pd.MultiIndex.from_product(
            [["000001.SZ", "600519.SH"], pd.date_range("2024-01-01", "2024-01-10")],
            names=["instrument", "datetime"],
        )
        out = build_industry_series_asof(idx, "L1")
        self.assertEqual(len(out), len(idx))
        self.assertEqual(out.notna().sum(), len(idx))

    def test_performance_gate_1y_panel(self):
        """1-year × 5,000 stocks must complete in < 2 seconds."""
        dates = pd.date_range("2023-01-01", "2023-12-31", freq="B")[:250]
        stocks = [f"{i:06d}.SZ" for i in range(5000)]
        idx = pd.MultiIndex.from_product([dates, stocks], names=["datetime", "instrument"])

        t0 = time.time()
        out = build_industry_series_asof(idx, "L1")
        elapsed = time.time() - t0

        self.assertEqual(len(out), len(idx))
        self.assertLess(
            elapsed, 2.0,
            f"Performance gate failed: 1.25M rows took {elapsed:.2f}s, expected <2s"
        )


if __name__ == "__main__":
    unittest.main()
