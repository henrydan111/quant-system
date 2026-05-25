"""P1-1: SuspensionLookup unit tests."""

from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_infra.provider_metadata import SuspensionLookup


def test_suspension_lookup_from_empty_ranges(tmp_path):
    """Missing file -> empty lookup -> all queries return None (fallback)."""
    lookup = SuspensionLookup.from_ranges_file(str(tmp_path / "does_not_exist.parquet"))
    assert lookup.is_suspended("000001.SZ", pd.Timestamp("2024-06-15")) is None


def test_suspension_lookup_detects_in_range(tmp_path):
    """A query date within a suspension range returns True."""
    ranges_path = tmp_path / "ranges.parquet"
    pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "suspend_start": pd.Timestamp("2024-06-01"),
                "suspend_end": pd.Timestamp("2024-06-10"),
                "suspend_reason": "announcement",
            }
        ]
    ).to_parquet(ranges_path, index=False)

    lookup = SuspensionLookup.from_ranges_file(str(ranges_path))

    assert lookup.is_suspended("000001.SZ", pd.Timestamp("2024-06-01")) is True
    assert lookup.is_suspended("000001.SZ", pd.Timestamp("2024-06-05")) is True
    assert lookup.is_suspended("000001.SZ", pd.Timestamp("2024-06-10")) is True


def test_suspension_lookup_out_of_range_returns_false(tmp_path):
    """A query date outside the known ranges returns False (not None)."""
    ranges_path = tmp_path / "ranges.parquet"
    pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "suspend_start": pd.Timestamp("2024-06-01"),
                "suspend_end": pd.Timestamp("2024-06-10"),
                "suspend_reason": "announcement",
            }
        ]
    ).to_parquet(ranges_path, index=False)

    lookup = SuspensionLookup.from_ranges_file(str(ranges_path))

    assert lookup.is_suspended("000001.SZ", pd.Timestamp("2024-05-01")) is False
    assert lookup.is_suspended("000001.SZ", pd.Timestamp("2024-07-01")) is False


def test_suspension_lookup_unknown_ts_code_returns_none(tmp_path):
    """Unknown ts_code returns None so the backtester falls back to vol==0."""
    ranges_path = tmp_path / "ranges.parquet"
    pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "suspend_start": pd.Timestamp("2024-06-01"),
                "suspend_end": pd.Timestamp("2024-06-10"),
                "suspend_reason": "announcement",
            }
        ]
    ).to_parquet(ranges_path, index=False)

    lookup = SuspensionLookup.from_ranges_file(str(ranges_path))
    assert lookup.is_suspended("600519.SH", pd.Timestamp("2024-06-05")) is None


def test_suspension_lookup_multiple_ranges_per_symbol(tmp_path):
    """A symbol with multiple suspension events: each range is honored."""
    ranges_path = tmp_path / "ranges.parquet"
    pd.DataFrame(
        [
            {
                "ts_code": "600001.SH",
                "suspend_start": pd.Timestamp("2024-01-15"),
                "suspend_end": pd.Timestamp("2024-01-20"),
                "suspend_reason": "r1",
            },
            {
                "ts_code": "600001.SH",
                "suspend_start": pd.Timestamp("2024-06-01"),
                "suspend_end": pd.Timestamp("2024-06-05"),
                "suspend_reason": "r2",
            },
        ]
    ).to_parquet(ranges_path, index=False)

    lookup = SuspensionLookup.from_ranges_file(str(ranges_path))

    assert lookup.is_suspended("600001.SH", pd.Timestamp("2024-01-17")) is True
    assert lookup.is_suspended("600001.SH", pd.Timestamp("2024-03-01")) is False
    assert lookup.is_suspended("600001.SH", pd.Timestamp("2024-06-03")) is True


def test_suspension_lookup_accepts_qlib_format(tmp_path):
    """Query with Qlib-format code works even though ranges store Tushare format."""
    ranges_path = tmp_path / "ranges.parquet"
    pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "suspend_start": pd.Timestamp("2024-06-01"),
                "suspend_end": pd.Timestamp("2024-06-10"),
                "suspend_reason": "r",
            }
        ]
    ).to_parquet(ranges_path, index=False)

    lookup = SuspensionLookup.from_ranges_file(str(ranges_path))
    assert lookup.is_suspended("000001_SZ", pd.Timestamp("2024-06-05")) is True
    assert lookup.is_suspended("000001_sz", pd.Timestamp("2024-06-05")) is True
