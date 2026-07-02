"""Canaries for `aggregate_directional_holdertrade` (stk_holdertrade 高管 directional signals).

Pins the GPT-review M1/m2 contract: amount uses min_count=1 (all-unpriced day → NaN, NOT a false 0;
partial-priced day → priced-event lower bound), vol/ratio/events stay complete, and directional vol
is a positive magnitude. See src/data_infra/pit_backend.py::aggregate_directional_holdertrade.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_infra.pit_backend import aggregate_directional_holdertrade

_DAY = pd.Timestamp("2020-01-02")


def _sub(rows):
    return pd.DataFrame(rows)


def test_all_unpriced_day_amount_is_nan_not_zero():
    # GPT M1: a 高管-IN day where EVERY event lacks avg_price -> amount NaN, not 0.0.
    sub = _sub([
        {"qlib_code": "000001_sz", "effective_date": _DAY, "change_vol": 1000.0, "change_ratio": 0.01, "avg_price": np.nan},
        {"qlib_code": "000001_sz", "effective_date": _DAY, "change_vol": 500.0, "change_ratio": 0.005, "avg_price": np.nan},
    ])
    out, _ = aggregate_directional_holdertrade(sub, "holdertrade_mgr_in")
    row = out.iloc[0]
    assert row["holdertrade_mgr_in_vol"] == 1500.0            # complete
    assert row["holdertrade_mgr_in_ratio"] == pytest.approx(0.015)
    assert row["holdertrade_mgr_in_events"] == 2
    assert np.isnan(row["holdertrade_mgr_in_amount"])          # NOT 0.0 — the whole point


def test_partial_priced_day_amount_is_priced_lower_bound():
    sub = _sub([
        {"qlib_code": "000001_sz", "effective_date": _DAY, "change_vol": 1000.0, "change_ratio": 0.01, "avg_price": 10.0},   # 10000
        {"qlib_code": "000001_sz", "effective_date": _DAY, "change_vol": 500.0, "change_ratio": 0.005, "avg_price": np.nan},  # skipped
    ])
    out, _ = aggregate_directional_holdertrade(sub, "holdertrade_mgr_in")
    row = out.iloc[0]
    assert row["holdertrade_mgr_in_vol"] == 1500.0            # vol still complete
    assert row["holdertrade_mgr_in_events"] == 2             # events still complete
    assert row["holdertrade_mgr_in_amount"] == pytest.approx(10000.0)  # priced-event lower bound


def test_fully_priced_amount_is_full_sum():
    sub = _sub([
        {"qlib_code": "000001_sz", "effective_date": _DAY, "change_vol": 1000.0, "change_ratio": 0.01, "avg_price": 10.0},
        {"qlib_code": "000001_sz", "effective_date": _DAY, "change_vol": 500.0, "change_ratio": 0.005, "avg_price": 20.0},
    ])
    out, _ = aggregate_directional_holdertrade(sub, "holdertrade_mgr_de")
    assert out.iloc[0]["holdertrade_mgr_de_amount"] == pytest.approx(1000 * 10 + 500 * 20)


def test_vol_is_positive_magnitude_even_if_change_vol_negative():
    # m2: directional vol/amount are positive magnitudes regardless of any sign in the feed.
    sub = _sub([
        {"qlib_code": "000001_sz", "effective_date": _DAY, "change_vol": -1000.0, "change_ratio": 0.01, "avg_price": 10.0},
    ])
    out, _ = aggregate_directional_holdertrade(sub, "holdertrade_mgr_de")
    row = out.iloc[0]
    assert row["holdertrade_mgr_de_vol"] == 1000.0
    assert row["holdertrade_mgr_de_amount"] == pytest.approx(10000.0)


def test_groups_by_code_and_date():
    sub = _sub([
        {"qlib_code": "000001_sz", "effective_date": _DAY, "change_vol": 100.0, "change_ratio": 0.001, "avg_price": 5.0},
        {"qlib_code": "000001_sz", "effective_date": pd.Timestamp("2020-03-01"), "change_vol": 200.0, "change_ratio": 0.002, "avg_price": 6.0},
        {"qlib_code": "600519_sh", "effective_date": _DAY, "change_vol": 300.0, "change_ratio": 0.003, "avg_price": 7.0},
    ])
    out, _ = aggregate_directional_holdertrade(sub, "holdertrade_mgr_in")
    assert len(out) == 3
    assert set(out["qlib_code"]) == {"000001_sz", "600519_sh"}


def test_empty_subset_returns_empty_with_field_names():
    cols = ["qlib_code", "effective_date", "change_vol", "change_ratio", "avg_price"]
    out, fields = aggregate_directional_holdertrade(pd.DataFrame(columns=cols), "holdertrade_mgr_in")
    assert out.empty
    assert fields == ["holdertrade_mgr_in_vol", "holdertrade_mgr_in_amount",
                      "holdertrade_mgr_in_ratio", "holdertrade_mgr_in_events"]
