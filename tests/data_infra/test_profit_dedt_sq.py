"""Canary tests for `_materialize_profit_dedt_sq` (Phase-C, 扣非净利润 single-quarter).

`profit_dedt` (扣非净利润, indicators ledger) is reported as a fiscal-YTD **cumulative**, so the
single-quarter value is derived `profit_dedt[Q] - profit_dedt[Q-1]` through the SAME proven kernel
the income/cashflow families use (`materialize_canonical_quarter_segments` +
`arrays_from_snapshot_segments`, restatement-safe via `derive_single_quarter_value`).

That kernel is ALREADY canaried in `test_pit_backend.py`:
  - normal Q3-Q2 single-q + slot-order  -> `test_canonical_quarter_segments_prefer_direct_quarter_and_fallback_per_field`
  - late restatement (best-known state) -> `test_flow_single_quarter_derivation_tracks_late_revision`
So this file does NOT re-test the kernel. It locks the behaviour UNIQUE to `_materialize_profit_dedt_sq`:
  1. the standard-fiscal-end **prefilter** (only 03-31/06-30/09-30/12-31 ends feed the kernel; a
     synthetic 03-30 / irregular end is dropped BEFORE derivation)  [GPT Plan-C Major-3]
  2. Q1 single-q == cumulative
  3. missing-prior-quarter -> NaN (no fabricated single-q)
  4. slot ordering (q0 = newest visible quarter) + the field plumbing (profit_dedt -> profit_dedt_sq_q*)

Plan-canary -> coverage map (9 items):
  normal Q3-Q2 ............... kernel canary + this::test_single_quarter_and_slot_order
  late-Q2-restatement ........ kernel canary (test_flow_single_quarter_derivation_tracks_late_revision)
  missing-prior -> NaN ....... this::test_missing_prior_quarter_is_nan
  Q1 == cum .................. this::test_q1_equals_cumulative
  irregular end -> excluded .. this::test_irregular_fiscal_end_excluded
  synthetic 03-30 -> excluded  this::test_irregular_fiscal_end_excluded (9999 sentinel)
  slot-order ................. this::test_single_quarter_and_slot_order
  provider-read exact-date ... sandbox build (profit_dedt_sq_q0 == vendor q_dtprofit_q0, med_rel 0)
  coverage-vs-vendor ......... coverage audit (_phasec_profit_dedt_coverage_audit.py)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_infra.pit_backend import StagedQlibBackendBuilder


# Synthetic 元-scale cumulative ledger for ONE stock. 2023 = full 4 quarters; a phantom 03-30
# irregular end (sentinel 9999) that MUST be dropped by the prefilter; 2024 = Q1-only (Q1==cum).
_FAKE_CODE = "000001_sz"  # lowercase = the production Qlib code format (Tushare 000001.SZ -> Qlib 000001_sz)
_LEDGER_ROWS = [
    # end_date,      effective_date,  ann_date,     profit_dedt (cumulative YTD)
    ("2023-03-31", "2023-04-25", "2023-04-25", 100.0),  # Q1  cum -> single 100
    ("2023-06-30", "2023-08-25", "2023-08-25", 250.0),  # H1  cum -> Q2 single 150
    ("2023-09-30", "2023-10-25", "2023-10-25", 360.0),  # Q3  cum -> Q3 single 110
    ("2023-12-31", "2024-03-25", "2024-03-25", 500.0),  # FY  cum -> Q4 single 140
    ("2023-03-30", "2023-04-26", "2023-04-26", 9999.0),  # IRREGULAR end -> must be excluded
    ("2024-03-31", "2024-04-25", "2024-04-25", 120.0),  # Q1-2024 cum -> single 120
]


def _build(tmp_path) -> StagedQlibBackendBuilder:
    builder = StagedQlibBackendBuilder(
        data_root=str(tmp_path / "data"),
        qlib_dir=str(tmp_path / "qlib"),
        build_id="unit_profit_dedt",
        slot_depth=5,
        allow_exceptions=True,
    )
    ledger = pd.DataFrame(
        _LEDGER_ROWS, columns=["end_date", "effective_date", "ann_date", "profit_dedt"]
    )
    ledger.insert(0, "qlib_code", _FAKE_CODE)
    path = builder.ledger_path("indicators")
    import os

    os.makedirs(os.path.dirname(path), exist_ok=True)
    ledger.to_parquet(path)
    return builder


def _run_capture(tmp_path, monkeypatch):
    """Drive the REAL method; capture `_write_feature_series` arrays (no close.day.bin needed)."""
    builder = _build(tmp_path)
    calendar = pd.DatetimeIndex(
        pd.bdate_range("2023-04-01", "2024-06-30", freq="W-MON")  # weekly Mondays span all effective dates
    )
    captured: dict[str, np.ndarray] = {}

    def _capture(self, feature_dir, field_name, values):  # noqa: ANN001
        captured[field_name] = np.asarray(values, dtype=float)

    monkeypatch.setattr(StagedQlibBackendBuilder, "_write_feature_series", _capture, raising=True)
    written = builder._materialize_profit_dedt_sq(calendar, {_FAKE_CODE: "/fake/dir"})
    return calendar, captured, written


def _pos_after(calendar: pd.DatetimeIndex, date: str) -> int:
    """First calendar index strictly after `date` (where that disclosure is visible)."""
    return int(np.searchsorted(calendar.values, np.datetime64(date), side="right"))


def test_all_five_slots_written(tmp_path, monkeypatch):
    _, captured, written = _run_capture(tmp_path, monkeypatch)
    assert written == [f"profit_dedt_sq_q{s}" for s in range(5)]
    for s in range(5):
        assert f"profit_dedt_sq_q{s}" in captured


def test_irregular_fiscal_end_excluded(tmp_path, monkeypatch):
    """The synthetic 03-30 end (sentinel 9999) must NEVER surface in any slot at any date."""
    _, captured, _ = _run_capture(tmp_path, monkeypatch)
    for s in range(5):
        arr = captured[f"profit_dedt_sq_q{s}"]
        assert not np.any(np.isclose(arr[np.isfinite(arr)], 9999.0)), f"phantom 03-30 leaked into q{s}"
        # and no single-q derived AGAINST the phantom (250-9999 etc.)
        assert not np.any(arr[np.isfinite(arr)] < -100.0), f"negative single-q from phantom in q{s}"


def test_q1_equals_cumulative(tmp_path, monkeypatch):
    """Q1 single-q == the cumulative itself (no prior quarter to subtract)."""
    calendar, captured, _ = _run_capture(tmp_path, monkeypatch)
    i = _pos_after(calendar, "2023-04-25")  # only Q1-2023 visible
    assert captured["profit_dedt_sq_q0"][i] == 100.0


def test_missing_prior_quarter_is_nan(tmp_path, monkeypatch):
    """At first Q1 visibility there is no prior quarter -> deeper slots are NaN, never fabricated."""
    calendar, captured, _ = _run_capture(tmp_path, monkeypatch)
    i = _pos_after(calendar, "2023-04-25")
    for s in range(1, 5):
        assert np.isnan(captured[f"profit_dedt_sq_q{s}"][i]), f"q{s} should be NaN with no prior quarter"


def test_single_quarter_and_slot_order(tmp_path, monkeypatch):
    """Full 2023 stack: q0 newest. Q2=150, Q3=110, Q4=140 derived; slots ordered newest->oldest."""
    calendar, captured, _ = _run_capture(tmp_path, monkeypatch)
    # after FY-2023 visible (2024-03-25), before Q1-2024 visible (2024-04-25)
    i = _pos_after(calendar, "2024-03-26")
    assert captured["profit_dedt_sq_q0"][i] == 140.0  # Q4 = 500-360
    assert captured["profit_dedt_sq_q1"][i] == 110.0  # Q3 = 360-250
    assert captured["profit_dedt_sq_q2"][i] == 150.0  # Q2 = 250-100
    assert captured["profit_dedt_sq_q3"][i] == 100.0  # Q1 = cum
    # after Q1-2024 visible: newest quarter rolls into q0, 2023 stack shifts down one slot
    j = _pos_after(calendar, "2024-04-26")
    assert captured["profit_dedt_sq_q0"][j] == 120.0  # Q1-2024 = cum
    assert captured["profit_dedt_sq_q1"][j] == 140.0  # Q4-2023
    assert captured["profit_dedt_sq_q2"][j] == 110.0  # Q3-2023
