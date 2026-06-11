"""Tests for data_infra.universe_membership — PIT daily masks from reference data."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_infra import universe_membership as um  # noqa: E402

DATES = pd.DatetimeIndex(
    ["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-27", "2020-02-28", "2020-03-02"]
)
INSTS = ["000001_SZ", "000002_SZ", "600000_SH"]


def _snapshots(rows):
    return pd.DataFrame(rows, columns=["snapshot_date", "instrument"]).assign(
        snapshot_date=lambda d: pd.to_datetime(d["snapshot_date"])
    )


class TestIndexMembershipMask:
    def test_asof_carry_forward_and_flip(self):
        # 000001 member at Jan snapshot; replaced by 600000 at Feb-28 snapshot
        snaps = _snapshots([
            ("2020-01-31", "000001_SZ"),
            ("2020-01-31", "000002_SZ"),
            ("2020-02-28", "000002_SZ"),
            ("2020-02-28", "600000_SH"),
        ])
        mask = um.index_membership_mask("X", DATES, INSTS, snapshots=snaps)
        # before first snapshot: all False
        assert not mask.loc["2020-01-30"].any()
        # Jan-31 .. Feb-27 use the Jan snapshot
        for d in ["2020-01-31", "2020-02-03", "2020-02-27"]:
            assert mask.loc[d, "000001_SZ"] and mask.loc[d, "000002_SZ"]
            assert not mask.loc[d, "600000_SH"]
        # Feb-28 onward uses the Feb snapshot
        for d in ["2020-02-28", "2020-03-02"]:
            assert not mask.loc[d, "000001_SZ"]
            assert mask.loc[d, "000002_SZ"] and mask.loc[d, "600000_SH"]

    def test_unknown_instrument_in_snapshot_ignored(self):
        snaps = _snapshots([("2020-01-31", "999999_SZ"), ("2020-01-31", "000001_SZ")])
        mask = um.index_membership_mask("X", DATES, INSTS, snapshots=snaps)
        assert mask.loc["2020-02-03", "000001_SZ"]
        assert mask.to_numpy().sum() == 5  # 000001 only, from Jan-31 onward

    def test_empty_snapshots_all_false(self):
        mask = um.index_membership_mask(
            "X", DATES, INSTS, snapshots=pd.DataFrame(columns=["snapshot_date", "instrument"])
        )
        assert not mask.to_numpy().any()


class TestStMask:
    def test_interval_inclusive_bounds(self):
        intervals = pd.DataFrame({
            "instrument": ["000001_SZ"],
            "start": [pd.Timestamp("2020-01-31")],
            "end": [pd.Timestamp("2020-02-27")],
        })
        mask = um.st_mask(DATES, INSTS, intervals=intervals)
        assert not mask.loc["2020-01-30", "000001_SZ"]
        assert mask.loc["2020-01-31", "000001_SZ"]       # start inclusive
        assert mask.loc["2020-02-27", "000001_SZ"]       # end inclusive
        assert not mask.loc["2020-02-28", "000001_SZ"]
        assert not mask["600000_SH"].any()

    def test_multiple_intervals_same_instrument(self):
        intervals = pd.DataFrame({
            "instrument": ["000002_SZ", "000002_SZ"],
            "start": pd.to_datetime(["2020-01-30", "2020-03-02"]),
            "end": pd.to_datetime(["2020-01-31", "2020-03-02"]),
        })
        mask = um.st_mask(DATES, INSTS, intervals=intervals)
        got = mask["000002_SZ"]
        assert got.loc["2020-01-30"] and got.loc["2020-01-31"] and got.loc["2020-03-02"]
        assert not got.loc["2020-02-03"]


class TestListingStatusMasks:
    def _stock_basic(self):
        return pd.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ", "600000.SH"],
            "list_date": ["20190201", "20200201", "19991110"],
            "delist_date": [None, None, "20200228"],
        })

    def test_young_boundary_365_days(self):
        masks = um.listing_status_masks(DATES, INSTS, stock_basic=self._stock_basic())
        young = masks["young"]
        # young = listed & (t < list_date + 365d); 000001 listed 2019-02-01, so the
        # first NON-young day is 2019-02-01 + 365d = 2020-02-01.
        assert young.loc["2020-01-31", "000001_SZ"]      # 364 days: still young
        assert not young.loc["2020-02-03", "000001_SZ"]  # >=365 days: no longer young
        # 000002 listed 2020-02-01: young through the whole window after listing
        assert not young.loc["2020-01-31", "000002_SZ"]  # not listed yet -> not young
        assert young.loc["2020-02-03", "000002_SZ"]

    def test_listed_and_delisted(self):
        masks = um.listing_status_masks(DATES, INSTS, stock_basic=self._stock_basic())
        listed = masks["listed"]
        assert not listed.loc["2020-01-31", "000002_SZ"]  # pre-list
        assert listed.loc["2020-02-03", "000002_SZ"]
        assert listed.loc["2020-02-27", "600000_SH"]
        assert not listed.loc["2020-02-28", "600000_SH"]  # delist day excluded
        assert not listed.loc["2020-03-02", "600000_SH"]

    def test_missing_instrument_fail_closed(self):
        masks = um.listing_status_masks(DATES, ["999999_SZ"], stock_basic=self._stock_basic())
        assert not masks["listed"].to_numpy().any()
        assert not masks["young"].to_numpy().any()


@pytest.mark.skipif(not um.DEFAULT_INDEX_WEIGHTS_DIR.exists(), reason="real data absent")
class TestRealDataSmoke:
    def test_csi500_loads_and_has_2010_coverage(self):
        snaps = um.load_index_snapshots("000905.SH")
        assert not snaps.empty
        assert snaps["snapshot_date"].min() <= pd.Timestamp("2010-01-31")
        # one as-of day: exactly ~500 members
        d = pd.DatetimeIndex([pd.Timestamp("2015-06-15")])
        insts = sorted(snaps["instrument"].unique())
        mask = um.index_membership_mask("000905.SH", d, insts, snapshots=snaps)
        n = int(mask.iloc[0].sum())
        assert 480 <= n <= 520, n
