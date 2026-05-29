"""Tests for the sandbox PIT research loader (prevention plan v5 §6.2).

Pure-logic tests run offline. Real-data tests (provider-value reproduction,
bounds mask, field governance) need the gitignored ledger/reference data and
``pytest.skip`` when it is absent — consistent with the plan's offline-CI vs
live-local-QA split.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data_infra import pit_research_loader as L
from src.data_infra.field_registry import FieldApprovalError
from src.data_infra.pit_research_loader import (
    PitResearchLoaderError,
    load_pit_asof_panel,
    load_pit_signal_panel,
)

_REF = L._data_root() / "reference" / "trade_cal.parquet"
_LEDGER = L._ledger_path("indicators")
_needs_ref = pytest.mark.skipif(not _REF.exists(), reason="trade_cal reference absent")
_needs_ledger = pytest.mark.skipif(not _LEDGER.exists(), reason="indicators ledger absent")


def test_signal_panel_requires_lag_ge_1():
    # The research-signal default must never silently allow same-day (lag 0) use.
    with pytest.raises(PitResearchLoaderError):
        load_pit_signal_panel(["roa"], ["20180102"], signal_lag_bars=0)


@_needs_ref
def test_sim_dates_validation():
    cal = L._trading_calendar()
    good = [d.strftime("%Y%m%d") for d in cal[(cal.year == 2018)]][:5]
    with pytest.raises(PitResearchLoaderError):  # unsorted
        load_pit_asof_panel(["roa"], list(reversed(good)), instruments=["600519.SH"])
    with pytest.raises(PitResearchLoaderError):  # non-compact
        load_pit_asof_panel(["roa"], ["2018-01-02"], instruments=["600519.SH"])
    with pytest.raises(PitResearchLoaderError):  # non-trading day (Jan 1 holiday)
        load_pit_asof_panel(["roa"], ["20180101"], instruments=["600519.SH"])


@_needs_ledger
def test_asof_reproduces_provider_pit_values_600519():
    cal = L._trading_calendar()
    sim = [d.strftime("%Y%m%d") for d in cal if 20180101 <= int(d.strftime("%Y%m%d")) <= 20181231]
    asof = load_pit_asof_panel(["roa"], sim, instruments=["600519.SH"])["roa"]
    assert float(asof.loc["20180108", "600519.SH"]) == pytest.approx(23.64, abs=0.01)  # 2017Q3
    assert float(asof.loc["20180607", "600519.SH"]) == pytest.approx(9.05, abs=0.01)   # 2018Q1, NOT 25.25
    assert float(asof.loc["20180903", "600519.SH"]) == pytest.approx(17.17, abs=0.01)  # 2018Q2
    assert float(asof.loc["20181101", "600519.SH"]) == pytest.approx(25.25, abs=0.01)  # 2018Q3


@_needs_ledger
def test_provider_bounds_mask_unlisted_stock():
    cal = L._trading_calendar()
    sim = [d.strftime("%Y%m%d") for d in cal if 20180101 <= int(d.strftime("%Y%m%d")) <= 20181231]
    # 688981.SH (SMIC) listed 2020 — must be masked to NaN throughout 2018.
    panel = load_pit_asof_panel(["roa"], sim, instruments=["688981.SH"])["roa"]
    if panel.shape[1]:
        assert np.isnan(float(panel.loc["20180607", panel.columns[0]]))


@_needs_ledger
def test_field_governance_blocks_quarantined_field_at_formal_stage():
    cal = L._trading_calendar()
    sim = [d.strftime("%Y%m%d") for d in cal if 20180101 <= int(d.strftime("%Y%m%d")) <= 20180201]
    # $net_mf_amount (moneyflow) is quarantined → blocked at a formal stage,
    # and the bare 'net_mf_amount' cannot bypass governance by dropping '$'.
    with pytest.raises(FieldApprovalError):
        load_pit_asof_panel(["net_mf_amount"], sim, instruments=["600519.SH"], stage="formal_validation")


@_needs_ref
def test_loader_rejects_unknown_field_even_at_sandbox():
    # GPT PR#18 blocking-1: the sanctioned loader must fail closed on a
    # registry-unknown field even at sandbox_screening (where the general
    # unknown_field_policy merely warns).
    cal = L._trading_calendar()
    sim = [d.strftime("%Y%m%d") for d in cal if 20180101 <= int(d.strftime("%Y%m%d")) <= 20180201]
    with pytest.raises(FieldApprovalError):
        load_pit_asof_panel(["totally_fake_xyz"], sim, instruments=["600519.SH"])


@_needs_ref
def test_loader_rejects_quarantine_field_at_sandbox():
    cal = L._trading_calendar()
    sim = [d.strftime("%Y%m%d") for d in cal if 20180101 <= int(d.strftime("%Y%m%d")) <= 20180201]
    with pytest.raises(FieldApprovalError):
        load_pit_asof_panel(["net_mf_amount"], sim, instruments=["600519.SH"])


@_needs_ledger
def test_dollar_prefix_normalized_same_as_bare():
    # GPT PR#18 smaller-note: "$roa" must behave identically to "roa" (no "$$roa").
    cal = L._trading_calendar()
    sim = [d.strftime("%Y%m%d") for d in cal if 20180101 <= int(d.strftime("%Y%m%d")) <= 20181231]
    bare = load_pit_asof_panel(["roa"], sim, instruments=["600519.SH"])
    dollar = load_pit_asof_panel(["$roa"], sim, instruments=["600519.SH"])
    assert "roa" in bare and "roa" in dollar  # $-prefix normalized to bare key
    b = bare["roa"]["600519.SH"].to_numpy()
    d = dollar["roa"]["600519.SH"].to_numpy()
    assert np.allclose(b, d, equal_nan=True)


@_needs_ledger
def test_vectorized_bounds_match_canonical_helper():
    # The loader's precomputed bounds map must equal provider_metadata.stock_basic_bounds
    # (the single source of truth) for a sample of ts_codes.
    from src.data_infra import provider_metadata as pm

    sb = pd.read_parquet(L._data_root() / "reference" / "stock_basic.parquet")
    bmap = L._bounds_map()
    sample = ["600519.SH", "000001.SZ", "688981.SH", "000002.SZ"]
    for ts in sample:
        want_lo, want_hi = pm.stock_basic_bounds(sb, ts)
        got_lo, got_hi = bmap.get(ts.upper(), (pd.NaT, pd.NaT))
        assert pd.to_datetime(got_lo) == (pd.NaT if want_lo is None else want_lo) or (
            pd.isna(got_lo) and want_lo is None
        )
        assert (pd.isna(got_hi) and want_hi is None) or pd.to_datetime(got_hi) == want_hi
