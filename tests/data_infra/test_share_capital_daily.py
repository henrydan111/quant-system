"""Tests for the effective-date-anchored bare share-capital bins (2026-07-01 fix).

The bug: the balancesheet snapshot family's bare compat alias clobbered ``total_share``
with the REPORT-anchored q0 series (1-2 months late vs real share changes; found in the
果仁 parity battle — BYD 002594's 2025 3× share change was visible in raw daily from
2025-07-30 but in the provider bin only from 2025-11-03, contradicting $total_mv).

Locks three behaviours:
  1. ``share_capital_daily_arrays`` — effective-date anchor, legacy unit multipliers
     (total_share 万股→股 ×1e4; float/free verbatim 万股), ffill across suspension gaps,
     NO back-fill before the first observation.
  2. ``_materialize_snapshot_dataset`` — the bare compat alias SKIPS the share-capital
     names (the report-anchored series stays available as ``{field}_q0..qN``).
  3. ``_materialize_share_capital_daily`` — end-to-end from raw daily parquet: writes the
     three bare bins for symbols with raw rows, leaves index-like symbols untouched.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from data_infra.pit_backend import (
    SHARE_CAPITAL_DAILY_FIELDS,
    StagedQlibBackendBuilder,
    share_capital_daily_arrays,
)

_CAL = pd.DatetimeIndex(pd.bdate_range("2023-01-02", "2023-01-20"))


def _symbol_daily() -> pd.DataFrame:
    # 万股-unit raw rows. Gap on 01-05/01-06 (suspension); share change effective 01-09.
    return pd.DataFrame(
        {
            "ts_code": "000001.SZ",
            "trade_date": pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-09", "2023-01-10"]),
            "total_share": [100.0, 100.0, 300.0, 300.0],
            "float_share": [80.0, 80.0, 240.0, 240.0],
            "free_share": [60.0, 60.0, 180.0, 180.0],
        }
    )


def test_arrays_effective_anchor_and_legacy_units():
    arrays = share_capital_daily_arrays(_symbol_daily(), _CAL)
    pos = {date.strftime("%Y-%m-%d"): i for i, date in enumerate(_CAL)}
    total = arrays["total_share"]
    # 万股 ×1e4 = 股 (legacy bin unit preserved for earn_q_eps)
    assert total[pos["2023-01-03"]] == np.float32(100.0 * 1e4)
    # the step lands ON the raw effective date, not a report date
    assert total[pos["2023-01-06"]] == np.float32(100.0 * 1e4)
    assert total[pos["2023-01-09"]] == np.float32(300.0 * 1e4)
    # float/free stay in 万股 (legacy unit for size_ln_free_float et al.)
    assert arrays["float_share"][pos["2023-01-09"]] == np.float32(240.0)
    assert arrays["free_share"][pos["2023-01-09"]] == np.float32(180.0)


def test_arrays_ffill_gap_but_no_backfill():
    arrays = share_capital_daily_arrays(_symbol_daily(), _CAL)
    pos = {date.strftime("%Y-%m-%d"): i for i, date in enumerate(_CAL)}
    total = arrays["total_share"]
    # before the first observation: NaN (no back-fill)
    assert np.isnan(total[pos["2023-01-02"]])
    # suspension gap 01-05/01-06: carried forward (state variable)
    assert total[pos["2023-01-05"]] == np.float32(100.0 * 1e4)
    # after the last observation: carried to the calendar end (suspended-but-listed)
    assert total[-1] == np.float32(300.0 * 1e4)


def _capture_writes(monkeypatch):
    captured: dict[str, np.ndarray] = {}

    def _capture(self, feature_dir, field_name, values):  # noqa: ANN001
        captured[field_name] = np.asarray(values, dtype=float)

    monkeypatch.setattr(StagedQlibBackendBuilder, "_write_feature_series", _capture, raising=True)
    return captured


def test_snapshot_compat_alias_skips_share_capital(tmp_path, monkeypatch):
    builder = StagedQlibBackendBuilder(
        data_root=str(tmp_path / "data"),
        qlib_dir=str(tmp_path / "qlib"),
        build_id="unit_share_capital_alias",
        slot_depth=2,
        allow_exceptions=True,
    )
    ledger = pd.DataFrame(
        {
            "qlib_code": "000001_sz",
            "end_date": ["2023-03-31", "2023-06-30"],
            "ann_date": ["2023-04-25", "2023-08-25"],
            "effective_date": ["2023-04-26", "2023-08-28"],
            "total_share": [1.0e9, 3.0e9],
            "total_assets": [5.0e9, 6.0e9],
        }
    )
    path = builder.ledger_path("balancesheet")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ledger.to_parquet(path)

    captured = _capture_writes(monkeypatch)
    calendar = pd.DatetimeIndex(pd.bdate_range("2023-04-01", "2023-12-29", freq="W-MON"))
    written = builder._materialize_snapshot_dataset("balancesheet", calendar, {"000001_sz": "/fake/dir"})

    # report-anchored slots still written for BOTH fields
    assert "total_share_q0" in captured and "total_assets_q0" in captured
    # the bare alias is written for a normal field but SKIPPED for share capital
    assert "total_assets" in captured and "total_assets" in written
    assert "total_share" not in captured and "total_share" not in written


def test_materialize_share_capital_daily_from_raw(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    daily_dir = data_root / "market" / "daily" / "2023"
    daily_dir.mkdir(parents=True)
    for date_str, total in [("20230103", 100.0), ("20230104", 100.0), ("20230109", 300.0)]:
        pd.DataFrame(
            {
                "ts_code": ["000001.SZ"],
                "trade_date": [date_str],
                "open": [10.0],
                "close": [10.0],
                "total_share": [total],
                "float_share": [total * 0.8],
                "free_share": [total * 0.6],
            }
        ).to_parquet(daily_dir / f"daily_{date_str}.parquet")

    builder = StagedQlibBackendBuilder(
        data_root=str(data_root),
        qlib_dir=str(tmp_path / "qlib"),
        build_id="unit_share_capital_daily",
        allow_exceptions=True,
    )
    captured = _capture_writes(monkeypatch)
    written = builder._materialize_share_capital_daily(
        _CAL, {"000001_sz": "/fake/dir", "000300_sh": "/fake/index"}
    )

    assert written == sorted(SHARE_CAPITAL_DAILY_FIELDS)
    pos = {date.strftime("%Y-%m-%d"): i for i, date in enumerate(_CAL)}
    assert captured["total_share"][pos["2023-01-04"]] == np.float32(100.0 * 1e4)
    assert captured["total_share"][pos["2023-01-09"]] == np.float32(300.0 * 1e4)
    assert captured["float_share"][pos["2023-01-09"]] == np.float32(240.0)
    assert captured["free_share"][pos["2023-01-09"]] == np.float32(180.0)


def test_materialize_share_capital_respects_field_filter(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    daily_dir = data_root / "market" / "daily" / "2023"
    daily_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "trade_date": ["20230103"],
            "total_share": [100.0],
            "float_share": [80.0],
            "free_share": [60.0],
        }
    ).to_parquet(daily_dir / "daily_20230103.parquet")

    builder = StagedQlibBackendBuilder(
        data_root=str(data_root),
        qlib_dir=str(tmp_path / "qlib"),
        build_id="unit_share_capital_filter",
        field_filter=["total_share"],
        allow_exceptions=True,
    )
    captured = _capture_writes(monkeypatch)
    written = builder._materialize_share_capital_daily(_CAL, {"000001_sz": "/fake/dir"})
    assert written == ["total_share"]
    assert set(captured) == {"total_share"}


def test_materialize_share_capital_force_bypasses_unrelated_field_filter(tmp_path, monkeypatch):
    """GPT cross-review M2: a field-scoped update still re-dumps the kline CSVs (which ignore
    field_filter), so the provider-maintenance call must force the corrective rewrite even
    when field_filter names something else entirely."""
    data_root = tmp_path / "data"
    daily_dir = data_root / "market" / "daily" / "2023"
    daily_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "trade_date": ["20230103"],
            "total_share": [100.0],
            "float_share": [80.0],
            "free_share": [60.0],
        }
    ).to_parquet(daily_dir / "daily_20230103.parquet")

    builder = StagedQlibBackendBuilder(
        data_root=str(data_root),
        qlib_dir=str(tmp_path / "qlib"),
        build_id="unit_share_capital_force",
        field_filter=["report_rc__eps_up"],
        allow_exceptions=True,
    )
    captured = _capture_writes(monkeypatch)
    filtered = builder._materialize_share_capital_daily(_CAL, {"000001_sz": "/fake/dir"})
    assert filtered == []  # non-forced: unrelated filter suppresses the step
    forced = builder._materialize_share_capital_daily(_CAL, {"000001_sz": "/fake/dir"}, force=True)
    assert forced == sorted(SHARE_CAPITAL_DAILY_FIELDS)
    assert set(captured) == set(SHARE_CAPITAL_DAILY_FIELDS)


def test_validate_provider_covers_forced_fields_under_field_filter(tmp_path, monkeypatch):
    """GPT re-review #2 minor m1: a field-scoped build still force-writes the share-capital
    bins, so validate_provider's bin-alignment check must include them even when field_filter
    names something else entirely."""
    import data_infra.pit_backend as pb
    from data_infra.storage.qlib_bin_utils import write_qlib_bin

    builder = StagedQlibBackendBuilder(
        data_root=str(tmp_path / "data"),
        qlib_dir=str(tmp_path / "qlib"),
        build_id="unit_validate_forced",
        field_filter=["report_rc__eps_up"],
        allow_exceptions=True,
    )
    feature_dir = os.path.join(builder.paths.provider_dir, "features", "000001_sz")
    os.makedirs(feature_dir)
    for name in ("close", "total_share", "float_share", "free_share", "pe_ttm"):
        write_qlib_bin(os.path.join(feature_dir, f"{name}.day.bin"), np.array([1.0, 2.0]), start_index=0)

    seen: dict[str, list[str]] = {}

    def _capture(dir_path, field_names, reference_field="close"):  # noqa: ANN001
        seen["fields"] = list(field_names)
        return []

    monkeypatch.setattr(pb, "validate_stock_bins", _capture, raising=True)
    builder.validate_provider({})

    assert set(SHARE_CAPITAL_DAILY_FIELDS) <= set(seen["fields"])  # forced bins validated
    assert "pe_ttm" not in seen["fields"]  # unrelated non-filter fields still excluded
