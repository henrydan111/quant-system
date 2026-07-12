from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_infra.pit_backend import (
    BuildGateError,
    DatasetProfile,
    DerivedMetricSpec,
    StagedQlibBackendBuilder,
    arrays_from_flow_segments,
    arrays_from_metric_segments,
    arrays_from_snapshot_segments,
    canonicalize_report_variants,
    collapse_duplicate_versions,
    materialize_canonical_quarter_segments,
    materialize_visibility_segments,
    strictly_next_open_trade_day,
)


def _write_reference_data(base: Path) -> None:
    reference_dir = base / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"exchange": "SSE", "cal_date": "20200101", "is_open": 1, "pretrade_date": "20191231"},
            {"exchange": "SSE", "cal_date": "20200102", "is_open": 1, "pretrade_date": "20200101"},
            {"exchange": "SSE", "cal_date": "20200103", "is_open": 1, "pretrade_date": "20200102"},
        ]
    ).to_parquet(reference_dir / "trade_cal.parquet", index=False)
    pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "symbol": "000001", "exchange": "SZSE", "list_date": "19910101"},
            {"ts_code": "600519.SH", "symbol": "600519", "exchange": "SSE", "list_date": "20010827"},
        ]
    ).to_parquet(reference_dir / "stock_basic.parquet", index=False)


def test_collapse_duplicate_versions_prefers_update_flag_and_backfills_missing_cells():
    df = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "end_date": pd.Timestamp("2024-12-31"),
                "disclosure_date": pd.Timestamp("2025-03-15"),
                "update_flag": 0,
                "field_a": 1.0,
                "field_b": np.nan,
            },
            {
                "ts_code": "000001.SZ",
                "end_date": pd.Timestamp("2024-12-31"),
                "disclosure_date": pd.Timestamp("2025-03-15"),
                "update_flag": 1,
                "field_a": 2.0,
                "field_b": 3.0,
            },
        ]
    )

    collapsed, conflicts = collapse_duplicate_versions(df, ["ts_code", "end_date", "disclosure_date"])

    assert len(collapsed) == 1
    assert collapsed.iloc[0]["field_a"] == 2.0
    assert collapsed.iloc[0]["field_b"] == 3.0
    assert conflicts


def test_revision_updates_q1_without_overwriting_q0():
    calendar = pd.DatetimeIndex(
        [
            "2024-05-06",
            "2024-08-02",
            "2024-09-02",
        ]
    )
    df = pd.DataFrame(
        [
            {"effective_date": "2024-05-06", "end_date": "2024-03-31", "metric": 10.0},
            {"effective_date": "2024-08-02", "end_date": "2024-06-30", "metric": 20.0},
            {"effective_date": "2024-09-02", "end_date": "2024-03-31", "metric": 12.0},
        ]
    )
    segments = materialize_visibility_segments(df, calendar, slot_depth=2)
    arrays = arrays_from_snapshot_segments(segments, ["metric"], len(calendar), 2)

    assert arrays["metric_q0"][1] == 20.0
    assert arrays["metric_q1"][1] == 10.0
    assert arrays["metric_q0"][2] == 20.0
    assert arrays["metric_q1"][2] == 12.0


def test_flow_single_quarter_derivation_tracks_late_revision():
    calendar = pd.DatetimeIndex(
        [
            "2024-05-06",
            "2024-08-02",
            "2024-09-02",
        ]
    )
    df = pd.DataFrame(
        [
            {"effective_date": "2024-05-06", "end_date": "2024-03-31", "metric": 10.0},
            {"effective_date": "2024-08-02", "end_date": "2024-06-30", "metric": 25.0},
            {"effective_date": "2024-09-02", "end_date": "2024-03-31", "metric": 12.0},
        ]
    )
    segments = materialize_visibility_segments(df, calendar, slot_depth=2)
    cumulative, single_quarter = arrays_from_flow_segments(segments, ["metric"], len(calendar), 2)

    assert cumulative["metric_cum_q0"][1] == 25.0
    assert cumulative["metric_cum_q1"][1] == 10.0
    assert single_quarter["metric_sq_q0"][1] == 15.0
    assert single_quarter["metric_sq_q1"][1] == 10.0

    assert cumulative["metric_cum_q0"][2] == 25.0
    assert cumulative["metric_cum_q1"][2] == 12.0
    assert single_quarter["metric_sq_q0"][2] == 13.0
    assert single_quarter["metric_sq_q1"][2] == 12.0


def test_canonical_quarter_segments_prefer_direct_quarter_and_fallback_per_field():
    calendar = pd.DatetimeIndex(["2024-05-06", "2024-08-02", "2024-09-02"])
    cumulative = pd.DataFrame(
        [
            {"effective_date": "2024-05-06", "end_date": "2024-03-31", "revenue": 100.0, "operate_profit": 10.0},
            {"effective_date": "2024-08-02", "end_date": "2024-06-30", "revenue": 220.0, "operate_profit": 25.0},
            {"effective_date": "2024-09-02", "end_date": "2024-03-31", "revenue": 110.0, "operate_profit": 12.0},
        ]
    )
    quarterly = pd.DataFrame(
        [
            {"effective_date": "2024-05-06", "end_date": "2024-03-31", "revenue": 100.0, "operate_profit": 10.0},
            {"effective_date": "2024-08-02", "end_date": "2024-06-30", "revenue": 120.0, "operate_profit": np.nan},
            {"effective_date": "2024-09-02", "end_date": "2024-03-31", "revenue": 110.0, "operate_profit": 12.0},
        ]
    )

    segments = materialize_canonical_quarter_segments(
        cumulative_df=cumulative,
        quarterly_df=quarterly,
        calendar=calendar,
        quarter_fields=["revenue", "operate_profit"],
        slot_depth=2,
    )
    arrays = arrays_from_snapshot_segments(segments, ["revenue", "operate_profit"], len(calendar), 2)

    assert arrays["revenue_q0"][1] == 120.0
    assert arrays["revenue_q1"][1] == 100.0
    assert arrays["operate_profit_q0"][1] == 15.0
    assert arrays["operate_profit_q1"][1] == 10.0

    assert arrays["revenue_q0"][2] == 120.0
    assert arrays["revenue_q1"][2] == 110.0
    assert arrays["operate_profit_q0"][2] == 13.0
    assert arrays["operate_profit_q1"][2] == 12.0


def test_canonical_report_variants_prefer_adjusted_single_quarter_and_backfill_missing_cells():
    df = pd.DataFrame(
        [
            {
                "effective_date": "2024-04-29",
                "end_date": "2024-03-31",
                "report_type": "2",
                "revenue": 100.0,
                "operate_profit": 10.0,
            },
            {
                "effective_date": "2024-04-29",
                "end_date": "2024-03-31",
                "report_type": "3",
                "revenue": np.nan,
                "operate_profit": 12.0,
            },
        ]
    )

    canonical = canonicalize_report_variants(df, "quarterly")

    assert len(canonical) == 1
    assert canonical.iloc[0]["report_type"] == "3"
    assert canonical.iloc[0]["revenue"] == 100.0
    assert canonical.iloc[0]["operate_profit"] == 12.0


def test_metric_arrays_follow_yoy_and_qoq_from_visible_period_state():
    calendar = pd.DatetimeIndex(["2024-05-06", "2024-08-02", "2024-09-02"])
    quarter_df = pd.DataFrame(
        [
            {"effective_date": "2023-08-01", "end_date": "2023-06-30", "revenue": 80.0, "operate_profit": 12.0},
            {"effective_date": "2024-05-06", "end_date": "2024-03-31", "revenue": 100.0, "operate_profit": 10.0},
            {"effective_date": "2024-08-02", "end_date": "2024-06-30", "revenue": 120.0, "operate_profit": 15.0},
            {"effective_date": "2024-09-02", "end_date": "2024-03-31", "revenue": 110.0, "operate_profit": 12.0},
        ]
    )

    segments = materialize_visibility_segments(quarter_df, calendar, slot_depth=2)
    arrays = arrays_from_metric_segments(
        segments,
        [
            DerivedMetricSpec("pit_q_sales_yoy", "revenue", "yoy"),
            DerivedMetricSpec("pit_q_op_qoq", "operate_profit", "qoq"),
        ],
        len(calendar),
        2,
    )

    assert arrays["pit_q_sales_yoy_q0"][1] == 50.0
    assert arrays["pit_q_op_qoq_q0"][1] == 50.0
    assert arrays["pit_q_sales_yoy_q0"][2] == 50.0
    assert arrays["pit_q_op_qoq_q0"][2] == 25.0
    assert np.isnan(arrays["pit_q_op_qoq_q1"][2])


def test_provider_only_stage_reuses_upstream_artifacts(tmp_path, monkeypatch):
    builder = StagedQlibBackendBuilder(
        data_root=str(tmp_path / "data"),
        qlib_dir=str(tmp_path / "qlib"),
        build_id="unit_provider_only",
        allow_exceptions=True,
    )

    def should_not_run(*args, **kwargs):
        raise AssertionError("Upstream rebuild should be skipped in provider-only stage")

    monkeypatch.setattr(builder, "profile_datasets", should_not_run)
    monkeypatch.setattr(builder, "normalize_datasets", should_not_run)
    monkeypatch.setattr(builder, "build_ledgers", should_not_run)
    monkeypatch.setattr(
        builder,
        "collect_profiles",
        lambda datasets=None, use_persisted=False: {"daily": DatasetProfile(name="daily", build_id=builder.build_id)},
    )
    monkeypatch.setattr(builder, "collect_normalized_outputs", lambda datasets=None: {"daily": ["normalized.parquet"]})
    monkeypatch.setattr(builder, "collect_ledger_outputs", lambda datasets=None: {"income": {"exists": True}})
    monkeypatch.setattr(
        builder,
        "materialize_provider",
        lambda mode="all", touched_symbols=None, datasets=None: {"written_fields": {"income": ["n_income_q"]}},
    )
    monkeypatch.setattr(builder, "validate_provider", lambda profiled, touched_symbols=None: ([], ["warning"]))
    monkeypatch.setattr(builder, "_write_manifest", lambda *args, **kwargs: None)

    result = builder.run(stage="provider-only", datasets=["daily"])

    assert result.profiled_datasets == ["daily"]
    assert result.normalized_datasets == ["daily"]
    assert result.ledgers_built == ["income"]
    assert result.validation_warnings == ["warning"]


def test_upstream_only_stage_skips_provider_and_blocks_publish(tmp_path, monkeypatch):
    builder = StagedQlibBackendBuilder(
        data_root=str(tmp_path / "data"),
        qlib_dir=str(tmp_path / "qlib"),
        build_id="unit_upstream_only",
        allow_exceptions=True,
    )

    monkeypatch.setattr(
        builder,
        "profile_datasets",
        lambda datasets=None: {"daily": DatasetProfile(name="daily", build_id=builder.build_id)},
    )
    monkeypatch.setattr(builder, "normalize_datasets", lambda datasets=None: {"daily": ["normalized.parquet"]})
    monkeypatch.setattr(builder, "build_ledgers", lambda datasets=None: {"income": {"exists": True}})
    monkeypatch.setattr(
        builder,
        "materialize_provider",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Provider stage should be skipped")),
    )
    monkeypatch.setattr(builder, "_write_manifest", lambda *args, **kwargs: None)

    result = builder.run(stage="upstream-only", datasets=["daily"])

    assert result.profiled_datasets == ["daily"]
    assert result.validation_errors == []
    assert result.validation_warnings == []

    try:
        builder.run(stage="upstream-only", datasets=["daily"], publish=True)
    except BuildGateError:
        pass
    else:
        raise AssertionError("Publishing an upstream-only build should fail")


def test_profile_dataset_ignores_confirmed_expected_empty_dates(tmp_path):
    data_root = tmp_path / "data"
    _write_reference_data(data_root)

    market_dir = data_root / "market" / "moneyflow" / "2020"
    market_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "trade_date": "20200101", "net_mf_amount": 1.0},
        ]
    ).to_parquet(market_dir / "moneyflow_20200101.parquet", index=False)
    pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "trade_date": "20200103", "net_mf_amount": 2.0},
        ]
    ).to_parquet(market_dir / "moneyflow_20200103.parquet", index=False)
    (data_root / "reference" / "moneyflow_known_empty_dates.txt").write_text("20200102\n", encoding="utf-8")

    builder = StagedQlibBackendBuilder(
        data_root=str(data_root),
        qlib_dir=str(tmp_path / "qlib"),
        build_id="unit_expected_empty",
        allow_exceptions=True,
    )

    profile = builder.profile_dataset("moneyflow")

    assert profile.unexpected_missing_dates == []
    assert profile.meta["expected_empty_reference"] == "moneyflow_known_empty_dates.txt"
    assert profile.meta["expected_empty_dates_applied"] == ["20200102"]


def test_normalize_northbound_recovers_valid_a_share_code_from_code_and_exchange(tmp_path):
    data_root = tmp_path / "data"
    _write_reference_data(data_root)

    builder = StagedQlibBackendBuilder(
        data_root=str(data_root),
        qlib_dir=str(tmp_path / "qlib"),
        build_id="unit_northbound_remap",
        allow_exceptions=True,
    )

    normalized, warnings = builder._normalize_daily_partition(
        "northbound",
        pd.DataFrame(
            [
                {
                    "ts_code": "000001.HK",
                    "code": "1",
                    "exchange": "SZ",
                    "trade_date": "20200102",
                    "vol": 100.0,
                    "ratio": 1.5,
                },
                {
                    "ts_code": "00700.HK",
                    "code": "700",
                    "exchange": "HK",
                    "trade_date": "20200102",
                    "vol": 50.0,
                    "ratio": 0.4,
                },
            ]
        ),
    )

    assert normalized["ts_code"].tolist() == ["000001.SZ"]
    assert normalized["qlib_code"].tolist() == ["000001_sz"]
    assert "north_hold_vol" in normalized.columns
    assert any("Recovered 1 northbound rows" in warning for warning in warnings)
    assert any("Dropped 1 non-equity or unmapped northbound rows" in warning for warning in warnings)


# ═══════════════════════════════════════════════════════════════════════════
# P0-2: strictly_next_open_trade_day invariant tests
#
# These tests lock the load-bearing PIT visibility anchor invariant: for any
# disclosure date x, the function must return a trading day y such that
# y > x (strictly). Violating this invariant would allow same-day leakage
# through the entire PIT pipeline. See CLAUDE.md §3 and the docstring on
# strictly_next_open_trade_day for the full contract.
# ═══════════════════════════════════════════════════════════════════════════


def _build_sample_calendar() -> pd.DatetimeIndex:
    """Build a small trading calendar covering a few open days with gaps."""
    return pd.DatetimeIndex(
        [
            # Friday 2024-01-05 (trading day)
            "2024-01-05",
            # Weekend 01-06, 01-07 skipped
            # Monday 01-08, Tuesday 01-09
            "2024-01-08",
            "2024-01-09",
            # Skip a "holiday" on 01-10, resume 01-11
            "2024-01-11",
            # Lunar New Year gap: skip 01-12 through 01-15
            "2024-01-16",
        ]
    )


def test_strictly_next_open_trade_day_on_trading_day_returns_next_trading_day():
    calendar = _build_sample_calendar()
    result = strictly_next_open_trade_day(
        pd.Series([pd.Timestamp("2024-01-05")]),
        calendar,
    )
    # Input is a trading day — must return the strictly NEXT trading day
    assert result.iloc[0] == pd.Timestamp("2024-01-08")


def test_strictly_next_open_trade_day_on_saturday_returns_monday():
    calendar = _build_sample_calendar()
    result = strictly_next_open_trade_day(
        pd.Series([pd.Timestamp("2024-01-06")]),
        calendar,
    )
    assert result.iloc[0] == pd.Timestamp("2024-01-08")


def test_strictly_next_open_trade_day_on_sunday_returns_monday():
    calendar = _build_sample_calendar()
    result = strictly_next_open_trade_day(
        pd.Series([pd.Timestamp("2024-01-07")]),
        calendar,
    )
    assert result.iloc[0] == pd.Timestamp("2024-01-08")


def test_strictly_next_open_trade_day_on_holiday_returns_next_open():
    calendar = _build_sample_calendar()
    # 2024-01-10 is a "holiday" in our sample calendar (between 01-09 and 01-11)
    result = strictly_next_open_trade_day(
        pd.Series([pd.Timestamp("2024-01-10")]),
        calendar,
    )
    assert result.iloc[0] == pd.Timestamp("2024-01-11")


def test_strictly_next_open_trade_day_past_calendar_end_returns_nat():
    calendar = _build_sample_calendar()
    # Anything past the last calendar day has no strictly-next trading day
    result = strictly_next_open_trade_day(
        pd.Series([pd.Timestamp("2024-01-16")]),
        calendar,
    )
    assert pd.isna(result.iloc[0])


def test_strictly_next_open_trade_day_on_last_calendar_day_returns_nat():
    calendar = _build_sample_calendar()
    # Input equals calendar end — there is no strictly-later day in the calendar
    result = strictly_next_open_trade_day(
        pd.Series([pd.Timestamp("2024-01-16")]),
        calendar,
    )
    assert pd.isna(result.iloc[0])


def test_strictly_next_open_trade_day_handles_nat_input():
    calendar = _build_sample_calendar()
    result = strictly_next_open_trade_day(
        pd.Series([pd.NaT, pd.Timestamp("2024-01-05")]),
        calendar,
    )
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pd.Timestamp("2024-01-08")


def test_strictly_next_open_trade_day_preserves_strict_inequality_across_all_inputs():
    """Exhaustive check: for every input within the calendar range, the
    result (when not NaT) must be strictly greater than the input.

    This is the load-bearing PIT invariant expressed as a property test.
    """
    calendar = _build_sample_calendar()
    # Test every day in the range [first_cal_day - 1, last_cal_day + 1]
    test_dates = pd.date_range(
        calendar[0] - pd.Timedelta(days=1),
        calendar[-1] + pd.Timedelta(days=1),
        freq="D",
    )
    result = strictly_next_open_trade_day(pd.Series(test_dates), calendar)
    for source, output in zip(test_dates, result):
        if pd.isna(output):
            # NaT is allowed for dates past the last calendar day
            continue
        assert output > source, (
            f"PIT invariant violated for input {source}: got {output}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# P0-4: Deterministic tie-break regression tests
#
# These tests lock the behavior that when two rows share the same (ts_code,
# end_date, disclosure_date, report_type) group AND fully tie on all primary
# priority keys (update_flag, max_date, non_null_count), the winner is
# determined by _src_file alphabetically then _src_ordinal numerically.
# Without this, the ledger depends on file glob order — unreproducible.
# ═══════════════════════════════════════════════════════════════════════════


def _make_tied_duplicate_rows(src_files: list[str], ordinals: list[int]) -> pd.DataFrame:
    """Build N rows that fully tie on all primary priority keys but differ
    only in _src_file / _src_ordinal.
    """
    assert len(src_files) == len(ordinals)
    rows = []
    for src, ordinal in zip(src_files, ordinals):
        rows.append(
            {
                "ts_code": "000001.SZ",
                "end_date": pd.Timestamp("2024-03-31"),
                "disclosure_date": pd.Timestamp("2024-04-15"),
                "report_type": "1",
                "update_flag": 1,
                "ann_date": pd.Timestamp("2024-04-15"),
                "f_ann_date": pd.Timestamp("2024-04-15"),
                # Payload: intentionally same to force full tie
                "revenue": 100.0,
                "net_income": 10.0,
                "_src_file": src,
                "_src_ordinal": ordinal,
            }
        )
    return pd.DataFrame(rows)


def test_collapse_tie_break_prefers_alphabetically_earlier_src_file():
    """Two rows, fully tied on primary keys, different _src_file: earlier wins."""
    df = _make_tied_duplicate_rows(
        src_files=["income_20240630.parquet", "income_20240331.parquet"],
        ordinals=[5, 5],
    )
    key_columns = ("ts_code", "end_date", "disclosure_date", "report_type")
    result, _ = collapse_duplicate_versions(df, key_columns)
    assert len(result) == 1
    # _src_file is dropped from the output — we verify winner by payload identity
    # is impossible (same payload), so verify by running again and confirming
    # the same winner regardless of input order.
    reversed_df = df.iloc[::-1].reset_index(drop=True)
    result_reversed, _ = collapse_duplicate_versions(reversed_df, key_columns)
    assert len(result_reversed) == 1
    # Row content must be identical across the two runs (reproducibility).
    pd.testing.assert_frame_equal(
        result.drop(columns=["_src_file", "_src_ordinal"], errors="ignore"),
        result_reversed.drop(columns=["_src_file", "_src_ordinal"], errors="ignore"),
    )


def test_collapse_tie_break_uses_src_ordinal_when_src_file_is_identical():
    """Two rows, same _src_file, different _src_ordinal: smaller ordinal wins."""
    df = _make_tied_duplicate_rows(
        src_files=["income_20240331.parquet", "income_20240331.parquet"],
        ordinals=[10, 3],
    )
    # Make payloads differ so we can detect which row won
    df.loc[df["_src_ordinal"] == 10, "revenue"] = 999.0
    df.loc[df["_src_ordinal"] == 3, "revenue"] = 111.0

    key_columns = ("ts_code", "end_date", "disclosure_date", "report_type")
    result, _ = collapse_duplicate_versions(df, key_columns)
    assert len(result) == 1
    # Smaller ordinal wins → revenue should be 111.0
    assert result.iloc[0]["revenue"] == 111.0


def test_collapse_reproducibility_across_shuffled_input():
    """Building the same ledger twice with shuffled input must produce
    identical output. This is the load-bearing P0-4 reproducibility check.
    """
    import hashlib

    # 10 tied rows with distinct _src_file / _src_ordinal combinations
    src_files = [f"income_2024{m:02d}31.parquet" for m in range(1, 11)]
    ordinals = list(range(10))
    df = _make_tied_duplicate_rows(src_files, ordinals)

    key_columns = ("ts_code", "end_date", "disclosure_date", "report_type")

    # Build 5 times with different shuffled orders
    hashes = set()
    for seed in range(5):
        shuffled = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        result, _ = collapse_duplicate_versions(shuffled, key_columns)
        content = result.drop(columns=["_src_file", "_src_ordinal"], errors="ignore").to_csv(index=False)
        hashes.add(hashlib.sha256(content.encode("utf-8")).hexdigest())

    # All 5 runs must produce identical content
    assert len(hashes) == 1, f"Reproducibility violated: got {len(hashes)} distinct outputs across 5 shuffles"


def test_canonicalize_report_variants_tie_break_is_deterministic():
    """canonicalize_report_variants must also be reproducible across shuffled input."""
    import hashlib

    # 4 rows, all with report_type=1 (same priority), same primary keys, but
    # different _src_file. Full ties on all 4 priority keys → tail decides.
    rows = []
    for i, src in enumerate(["income_d.parquet", "income_a.parquet", "income_c.parquet", "income_b.parquet"]):
        rows.append(
            {
                "ts_code": "000001.SZ",
                "effective_date": pd.Timestamp("2024-04-16"),
                "end_date": pd.Timestamp("2024-03-31"),
                "report_type": "1",
                "update_flag": 1,
                "ann_date": pd.Timestamp("2024-04-15"),
                "f_ann_date": pd.Timestamp("2024-04-15"),
                "disclosure_date": pd.Timestamp("2024-04-15"),
                "revenue": 100.0 + i,  # distinct payloads to detect winner
                "_src_file": src,
                "_src_ordinal": 0,
            }
        )
    df = pd.DataFrame(rows)

    hashes = set()
    for seed in range(5):
        shuffled = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        result = canonicalize_report_variants(shuffled, "cumulative")
        content = result.drop(columns=["_src_file", "_src_ordinal"], errors="ignore").to_csv(index=False)
        hashes.add(hashlib.sha256(content.encode("utf-8")).hexdigest())

    assert len(hashes) == 1, f"canonicalize_report_variants reproducibility violated: {len(hashes)} distinct outputs"


def test_publish_refuses_cross_volume_atomic_replace():
    """P0-6: publish() must hard-fail when the staged provider and target
    qlib_dir live on different volumes. os.replace() is NOT atomic across
    volumes and cross-drive publish would leave the backend in an
    inconsistent state mid-copy.
    """
    import os as os_module
    from unittest.mock import patch

    from data_infra.pit_backend import BuildGateError, StagedQlibBackendBuilder

    # Build a minimal in-memory builder instance. We only need the publish()
    # method's os.stat call to return different device IDs. The actual
    # filesystem paths don't need to exist for the stat mock to trigger.
    builder = StagedQlibBackendBuilder.__new__(StagedQlibBackendBuilder)
    # Create a tmp directory with a fake "provider" subdir so isdir passes
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "staged_provider"
        target = Path(tmp) / "target_qlib"
        staged.mkdir()

        class _FakePaths:
            provider_dir = str(staged)
            qlib_dir = str(target)
            build_root = str(Path(tmp) / "build_test_cross_volume")

        builder.paths = _FakePaths()

        # Mock os.stat so staged and target return different st_dev values
        real_stat = os_module.stat

        def _fake_stat(path, *args, **kwargs):
            result = real_stat(path, *args, **kwargs)
            # Wrap in a namedtuple-like object we can mutate
            class _StatMock:
                def __init__(self, orig, dev):
                    self.st_dev = dev
                    # Pass through everything else
                    for attr in dir(orig):
                        if not attr.startswith("_") and attr != "st_dev":
                            try:
                                setattr(self, attr, getattr(orig, attr))
                            except (AttributeError, TypeError):
                                pass

            if "staged_provider" in str(path):
                return _StatMock(result, dev=1001)
            return _StatMock(result, dev=2002)

        with patch("data_infra.pit_backend.os.stat", side_effect=_fake_stat):
            try:
                builder.publish(calendar_policy_id="frozen_20260227_system_build")
            except BuildGateError as exc:
                message = str(exc)
                assert "cross-volume" in message.lower()
                assert "1001" in message
                assert "2002" in message
                return
            raise AssertionError("publish() should have raised BuildGateError for cross-volume")


def test_load_price_frame_fails_closed_on_null_adj_factor():
    """GPT 5-C Blocker 3: a NaN adj_factor on a priced raw row (or a missing adj_factor column) must
    RAISE BuildGateError, never be silently coerced to 1.0 (which treats raw prices as adjusted and
    corrupts every cross-day return). The 1.0 default is permitted ONLY under the test escape hatch."""
    import os as _os
    import pytest
    from data_infra.pit_backend import BuildGateError, StagedQlibBackendBuilder

    b = StagedQlibBackendBuilder.__new__(StagedQlibBackendBuilder)
    b.raw_files = lambda ds: ["f1"]
    b._apply_price_repair_overrides = lambda ds, raw, source_name=None: (raw, None)
    b._standardize_common_columns = lambda x: x

    # priced row with a NaN adj_factor -> fail closed
    df = pd.DataFrame({"ts_code": ["A", "A"], "trade_date": ["20260701", "20260702"],
                       "close": [1.0, 2.0], "adj_factor": [1.0, np.nan]})
    b._read_raw_file = lambda ds, p: df.copy()
    with pytest.raises(BuildGateError, match="null.*adj_factor|adjustment-history hole"):
        b._load_price_frame()

    # missing adj_factor column, no escape -> fail closed
    b._read_raw_file = lambda ds, p: df.drop(columns=["adj_factor"]).copy()
    _os.environ.pop("QUANT_ALLOW_UNIT_ADJ_FACTOR", None)
    with pytest.raises(BuildGateError, match="missing the adj_factor"):
        b._load_price_frame()

    # missing column WITH the explicit test escape -> defaults to 1.0
    _os.environ["QUANT_ALLOW_UNIT_ADJ_FACTOR"] = "1"
    try:
        out = b._load_price_frame()
        assert (out["factor"] == 1.0).all()
    finally:
        _os.environ.pop("QUANT_ALLOW_UNIT_ADJ_FACTOR", None)

    # clean adj_factor -> passed through verbatim (no coercion)
    clean = pd.DataFrame({"ts_code": ["A"], "trade_date": ["20260701"], "close": [1.0], "adj_factor": [1.5]})
    b._read_raw_file = lambda ds, p: clean.copy()
    assert list(b._load_price_frame()["factor"]) == [1.5]


def test_publish_staged_first_swap_success(tmp_path):
    """Staged-first publish success: staged provider is promoted into qlib_dir and
    the old live provider is moved to the backup dir."""
    from data_infra.pit_backend import StagedQlibBackendBuilder

    builder = StagedQlibBackendBuilder.__new__(StagedQlibBackendBuilder)
    staged = tmp_path / "swaptest" / "provider"  # build_id = basename(build_root) = "swaptest"
    target = tmp_path / "qlib_data"
    staged.mkdir(parents=True)
    (staged / "marker.txt").write_text("NEW", encoding="utf-8")
    target.mkdir()
    (target / "marker.txt").write_text("OLD", encoding="utf-8")

    class _P:
        provider_dir = str(staged)
        qlib_dir = str(target)
        build_root = str(tmp_path / "swaptest")

    builder.paths = _P()
    builder.publish(calendar_policy_id="frozen_20260227_system_build", emit_manifest=False)

    assert (target / "marker.txt").read_text(encoding="utf-8") == "NEW"  # staged promoted
    backup = tmp_path / "qlib_data.bak_swaptest"
    assert backup.is_dir() and (backup / "marker.txt").read_text(encoding="utf-8") == "OLD"  # old live backed up
    assert not staged.exists()  # staged source consumed


def test_publish_staged_first_no_broken_window(tmp_path):
    """Regression (depth9_20260630 incident): if the FIRST rename (staged->adjacent)
    fails — e.g. a Windows directory handle on the freshly-built staged tree — qlib_dir
    MUST remain the live provider, untouched. No broken window."""
    import os as _os
    from unittest.mock import patch

    import pytest as _pytest

    from data_infra.pit_backend import StagedQlibBackendBuilder

    builder = StagedQlibBackendBuilder.__new__(StagedQlibBackendBuilder)
    staged = tmp_path / "lockedtest" / "provider"  # build_id = basename(build_root) = "lockedtest"
    target = tmp_path / "qlib_data"
    staged.mkdir(parents=True)
    (staged / "marker.txt").write_text("NEW", encoding="utf-8")
    target.mkdir()
    (target / "marker.txt").write_text("OLD", encoding="utf-8")

    class _P:
        provider_dir = str(staged)
        qlib_dir = str(target)
        build_root = str(tmp_path / "lockedtest")

    builder.paths = _P()
    real_replace = _os.replace

    def _fail_staged_move(src, dst, *a, **k):
        if str(dst).endswith(".new_lockedtest"):  # the staged->adjacent step
            raise PermissionError("WinError 5 simulated: staged tree locked")
        return real_replace(src, dst, *a, **k)

    with patch("data_infra.pit_backend.os.replace", side_effect=_fail_staged_move):
        with _pytest.raises(PermissionError):
            builder.publish(calendar_policy_id="frozen_20260227_system_build", emit_manifest=False)

    # broken-window check: live provider still present + unchanged
    assert target.is_dir() and (target / "marker.txt").read_text(encoding="utf-8") == "OLD"
    assert staged.is_dir() and (staged / "marker.txt").read_text(encoding="utf-8") == "NEW"  # staged untouched
    assert not (tmp_path / "qlib_data.bak_lockedtest").exists()  # never reached the backup step


def test_publish_staged_first_step3_failure_full_rollback(tmp_path):
    """GPT R1 P2a: a step-3 (staged->live) failure must FULLY roll back — live restored to qlib_dir AND
    staged restored to provider_dir — so a same-build retry is clean."""
    import os as _os
    from unittest.mock import patch

    import pytest as _pytest

    from data_infra.pit_backend import StagedQlibBackendBuilder

    builder = StagedQlibBackendBuilder.__new__(StagedQlibBackendBuilder)
    staged = tmp_path / "step3test" / "provider"
    target = tmp_path / "qlib_data"
    staged.mkdir(parents=True); (staged / "m.txt").write_text("NEW", encoding="utf-8")
    target.mkdir(); (target / "m.txt").write_text("OLD", encoding="utf-8")

    class _P:
        provider_dir = str(staged); qlib_dir = str(target); build_root = str(tmp_path / "step3test")

    builder.paths = _P()
    real_replace = _os.replace

    def _fail_step3(src, dst, *a, **k):
        if str(src).endswith(".new_step3test") and str(dst) == str(target):  # staged->live only
            raise OSError("simulated step-3 failure")
        return real_replace(src, dst, *a, **k)

    with patch("data_infra.pit_backend.os.replace", side_effect=_fail_step3):
        with _pytest.raises(OSError):
            builder.publish(calendar_policy_id="frozen_20260227_system_build", emit_manifest=False)

    assert target.is_dir() and (target / "m.txt").read_text(encoding="utf-8") == "OLD"   # live restored
    assert staged.is_dir() and (staged / "m.txt").read_text(encoding="utf-8") == "NEW"   # staged restored (clean retry)
    assert not (tmp_path / "qlib_data.bak_step3test").exists()                           # backup consumed by restore


def test_publish_staged_first_double_failure_loud_recoverable(tmp_path):
    """GPT R1 P1: step-3 failure AND the live-restore failure must raise a LOUD BuildGateError naming the
    manual recovery, leaving state RECOVERABLE (backup + staging present) — never silently missing."""
    import os as _os
    from unittest.mock import patch

    import pytest as _pytest

    from data_infra.pit_backend import BuildGateError, StagedQlibBackendBuilder

    builder = StagedQlibBackendBuilder.__new__(StagedQlibBackendBuilder)
    staged = tmp_path / "doubletest" / "provider"
    target = tmp_path / "qlib_data"
    staged.mkdir(parents=True); (staged / "m.txt").write_text("NEW", encoding="utf-8")
    target.mkdir(); (target / "m.txt").write_text("OLD", encoding="utf-8")

    class _P:
        provider_dir = str(staged); qlib_dir = str(target); build_root = str(tmp_path / "doubletest")

    builder.paths = _P()
    real_replace = _os.replace

    def _fail_into_qlib(src, dst, *a, **k):
        if str(dst) == str(target):  # both step-3 (staged->live) and restore (backup->live)
            raise OSError("simulated failure moving into qlib_dir")
        return real_replace(src, dst, *a, **k)

    with patch("data_infra.pit_backend.os.replace", side_effect=_fail_into_qlib):
        with _pytest.raises(BuildGateError) as exc:
            builder.publish(calendar_policy_id="frozen_20260227_system_build", emit_manifest=False)

    assert "MISSING" in str(exc.value) and "recover manually" in str(exc.value).lower()
    assert not target.exists()                                # qlib_dir missing (double failure)
    assert (tmp_path / "qlib_data.bak_doubletest").is_dir()   # old live recoverable
    assert (tmp_path / "qlib_data.new_doubletest").is_dir()   # new provider recoverable


def test_collapse_duplicate_versions_populates_provenance_buffer_on_backfill():
    """P0-5: when a backfill event occurs, the provenance buffer must receive
    a dict with the target row identity and the source row's metadata.
    """
    df = pd.DataFrame(
        [
            {
                # Primary (winner): has update_flag=1 but missing field_b
                "ts_code": "000001.SZ",
                "end_date": pd.Timestamp("2024-03-31"),
                "disclosure_date": pd.Timestamp("2024-04-15"),
                "update_flag": 1,
                "field_a": 2.0,
                "field_b": np.nan,
            },
            {
                # Candidate: has field_b that will be backfilled into the winner
                "ts_code": "000001.SZ",
                "end_date": pd.Timestamp("2024-03-31"),
                "disclosure_date": pd.Timestamp("2024-04-15"),
                "update_flag": 0,
                "field_a": 1.0,
                "field_b": 3.0,
            },
        ]
    )
    buffer: list[dict] = []
    result, _ = collapse_duplicate_versions(
        df,
        ("ts_code", "end_date", "disclosure_date"),
        provenance_buffer=buffer,
    )
    assert len(result) == 1
    # Field_b backfilled from the candidate
    assert result.iloc[0]["field_b"] == 3.0
    # Provenance buffer records the backfill event
    assert len(buffer) == 1
    event = buffer[0]
    assert event["ts_code"] == "000001.SZ"
    assert event["field"] == "field_b"
    assert event["source_update_flag"] == 0


def test_collapse_duplicate_versions_provenance_buffer_is_optional():
    """Backward-compat: callers that don't pass a provenance_buffer must still work."""
    df = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "end_date": pd.Timestamp("2024-03-31"),
                "disclosure_date": pd.Timestamp("2024-04-15"),
                "update_flag": 1,
                "field_a": 2.0,
                "field_b": np.nan,
            },
            {
                "ts_code": "000001.SZ",
                "end_date": pd.Timestamp("2024-03-31"),
                "disclosure_date": pd.Timestamp("2024-04-15"),
                "update_flag": 0,
                "field_a": 1.0,
                "field_b": 3.0,
            },
        ]
    )
    # No provenance_buffer arg — should work exactly as before
    result, conflicts = collapse_duplicate_versions(
        df,
        ("ts_code", "end_date", "disclosure_date"),
    )
    assert len(result) == 1
    assert result.iloc[0]["field_b"] == 3.0


def test_canonicalize_tie_break_fallback_to_content_hash_when_src_columns_absent():
    """When _src_file / _src_ordinal columns are absent (e.g., re-read from
    disk), canonicalize_report_variants must fall back to content-hash tail
    and still be deterministic.
    """
    import hashlib

    rows = []
    for i in range(4):
        rows.append(
            {
                "ts_code": "000001.SZ",
                "effective_date": pd.Timestamp("2024-04-16"),
                "end_date": pd.Timestamp("2024-03-31"),
                "report_type": "1",
                "update_flag": 1,
                "ann_date": pd.Timestamp("2024-04-15"),
                "f_ann_date": pd.Timestamp("2024-04-15"),
                "disclosure_date": pd.Timestamp("2024-04-15"),
                "revenue": 100.0 + i,
            }
        )
    df = pd.DataFrame(rows)

    hashes = set()
    for seed in range(5):
        shuffled = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        result = canonicalize_report_variants(shuffled, "cumulative")
        content = result.to_csv(index=False)
        hashes.add(hashlib.sha256(content.encode("utf-8")).hexdigest())

    assert len(hashes) == 1, (
        f"canonicalize_report_variants fallback hash tie-break reproducibility "
        f"violated: {len(hashes)} distinct outputs"
    )


def _cut_builder(tmp_path, cut):
    """Calendar-unfreeze target_end determinism fixture (synthetic price frame)."""
    from data_infra.pit_backend import StagedQlibBackendBuilder

    builder = StagedQlibBackendBuilder(
        data_root=str(tmp_path / "data"), qlib_dir=str(tmp_path / "qlib"),
        build_id="cut_test", calendar_end_cut=cut,
    )
    frame = pd.DataFrame({
        "ts_code": ["000001.SZ"] * 3,
        "symbol": ["000001.SZ"] * 3,
        "date": pd.to_datetime(["2026-06-30", "2026-07-01", "2026-07-02"]),
        "close": [1.0, 2.0, 3.0],
    })
    builder._load_price_frame = lambda: frame.copy()
    builder._load_index_frame = lambda: pd.DataFrame()
    return builder


def test_calendar_end_cut_excludes_newer_bars(tmp_path):
    builder = _cut_builder(tmp_path, "20260701")
    ranges = builder._build_price_csvs(str(tmp_path / "csv"))
    assert str(ranges["price_end"].max().date()) == "2026-07-01"
    csv = pd.read_csv(tmp_path / "csv" / "000001_sz.csv")
    assert csv["date"].max() == "2026-07-01"


def test_no_calendar_end_cut_keeps_all_bars(tmp_path):
    builder = _cut_builder(tmp_path, None)
    ranges = builder._build_price_csvs(str(tmp_path / "csv"))
    assert str(ranges["price_end"].max().date()) == "2026-07-02"
