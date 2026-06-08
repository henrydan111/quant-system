"""P1 plumbing tests for the report_rc PIT ledger (15000积分 expansion).

The decisive guardrail: build_ledger must NOT collapse the many analyst×quarter
rows that share a (ts_code, report_date) into one row (the generic
`(ts_code, end_date, disclosure_date)` key would — report_rc has no end_date).
Also pins: exact-duplicate merge, the create_time vendor-lag anchor, and the
analyst-id normalization. No alpha / no screen — plumbing acceptance only.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data_infra.pit_backend import StagedQlibBackendBuilder, normalized_analyst_id  # noqa: E402
from data_infra.storage.qlib_bin_utils import (  # noqa: E402
    read_qlib_bin, write_qlib_bin, validate_stock_bins,
)

RRC_FIELDS = [
    "report_rc__eps_up", "report_rc__eps_dn",
    "report_rc__eps_revision_count", "report_rc__n_active_analysts",
]


def _write_reference_data(base: Path) -> None:
    ref = base / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"exchange": "SSE", "cal_date": "20200101", "is_open": 1, "pretrade_date": "20191231"},
        {"exchange": "SSE", "cal_date": "20200102", "is_open": 1, "pretrade_date": "20200101"},
        {"exchange": "SSE", "cal_date": "20200103", "is_open": 1, "pretrade_date": "20200102"},
    ]).to_parquet(ref / "trade_cal.parquet", index=False)
    pd.DataFrame([
        {"ts_code": "000001.SZ", "symbol": "000001", "exchange": "SZSE", "list_date": "19910101"},
    ]).to_parquet(ref / "stock_basic.parquet", index=False)


def _ct(day_evening: str) -> str:
    return f"{day_evening} 21:00:00"


def _revision_fixture() -> list:
    base = dict(ts_code="000001.SZ")
    return [
        # analyst A 2024Q4: 1.00 (eff 0102, coverage_init) -> 1.20 (eff 0103, UP)
        {**base, "report_date": "20200101", "create_time": _ct("2020-01-01"), "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.00},
        {**base, "report_date": "20200102", "create_time": _ct("2020-01-02"), "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.20},
        # analyst B 2024Q4: 1.00 (init) -> 0.90 (eff 0103, DOWN)
        {**base, "report_date": "20200101", "create_time": _ct("2020-01-01"), "org_name": "BBB证券", "author_name": "乙", "quarter": "2024Q4", "eps": 1.00},
        {**base, "report_date": "20200102", "create_time": _ct("2020-01-02"), "org_name": "BBB证券", "author_name": "乙", "quarter": "2024Q4", "eps": 0.90},
        # FUTURE row: report_date 0103 -> effective beyond the 3-day calendar -> NaT
        # -> must be dropped (no-lookahead canary; the 5.00 revision must not leak).
        {**base, "report_date": "20200103", "create_time": _ct("2020-01-03"), "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 5.00},
    ]


def _write_fixture(data_root: Path) -> None:
    d = data_root / "analyst" / "report_rc"
    d.mkdir(parents=True, exist_ok=True)
    base = dict(ts_code="000001.SZ", report_date="20200101", create_time=_ct("2020-01-01"))
    rows = [
        {**base, "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.0, "rating": "买入"},
        {**base, "org_name": "AAA证券", "author_name": "甲", "quarter": "2025Q4", "eps": 1.2, "rating": "买入"},
        {**base, "org_name": "BBB证券", "author_name": "丙,乙", "quarter": "2024Q4", "eps": 1.1, "rating": "增持"},
        {**base, "org_name": "BBB证券", "author_name": "丙,乙", "quarter": "2025Q4", "eps": 1.3, "rating": "增持"},
        # exact duplicate of row 0 -> must merge via the content-hash tie-break
        {**base, "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.0, "rating": "买入"},
    ]
    pd.DataFrame(rows).to_parquet(d / "report_rc_2020.parquet", index=False)


def _build_ledger(tmp: Path) -> pd.DataFrame:
    data_root = tmp / "data"
    _write_reference_data(data_root)
    _write_fixture(data_root)
    b = StagedQlibBackendBuilder(
        data_root=str(data_root), qlib_dir=str(tmp / "qlib"),
        build_id="unit_report_rc", allow_exceptions=True,
    )
    b.normalize_dataset("report_rc")
    b.build_ledger("report_rc")
    return pd.read_parquet(b.ledger_path("report_rc"))


def test_report_rc_ledger_preserves_multi_analyst_multi_quarter_rows(tmp_path):
    led = _build_ledger(tmp_path)
    # 5 raw rows -> 4 ledger rows: NOT collapsed to 1 (the generic-key bug),
    # NOT 5 (the exact duplicate merged).
    assert len(led) == 4, f"expected 4 ledger rows (2 analysts x 2 quarters), got {len(led)}"
    aids = set(led["normalized_analyst_id"])
    assert len(aids) == 2 and "AAA证券::甲" in aids
    multi = next(a for a in aids if a.startswith("BBB证券::"))
    assert set(multi.split("::", 1)[1].split("+")) == {"乙", "丙"}  # sorted multi-author team
    for aid in aids:
        assert set(led.loc[led["normalized_analyst_id"] == aid, "quarter"]) == {"2024Q4", "2025Q4"}


def test_report_rc_effective_date_uses_create_time_anchor(tmp_path):
    led = _build_ledger(tmp_path)
    eff = pd.to_datetime(led["effective_date"])
    # max(report_date 2020-01-01, create_time 2020-01-01 21:00) -> strictly next open = 2020-01-02
    assert (eff == pd.Timestamp("2020-01-02")).all(), f"effective dates: {sorted(eff.unique())}"


def test_report_rc_ledger_deterministic(tmp_path):
    a = _build_ledger(tmp_path / "a")
    b = _build_ledger(tmp_path / "b")
    key = ["normalized_analyst_id", "quarter"]
    sig_a = sorted(a[key].astype(str).agg("|".join, axis=1))
    sig_b = sorted(b[key].astype(str).agg("|".join, axis=1))
    assert sig_a == sig_b


def _make_builder(tmp: Path, rows: list) -> StagedQlibBackendBuilder:
    data_root = tmp / "data"
    _write_reference_data(data_root)
    d = data_root / "analyst" / "report_rc"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(d / "report_rc_2020.parquet", index=False)
    b = StagedQlibBackendBuilder(
        data_root=str(data_root), qlib_dir=str(tmp / "qlib"),
        build_id="unit_rrc_mat", allow_exceptions=True,
    )
    b.normalize_dataset("report_rc")
    b.build_ledger("report_rc")
    return b


def test_report_rc_materializer_event_flow_primitives(tmp_path):
    b = _make_builder(tmp_path, _revision_fixture())
    calendar = b.open_calendar()  # [2020-01-01, 02, 03]

    captured: dict = {}

    def _capture(feature_dir, field_name, array):
        captured.setdefault(feature_dir, {})[field_name] = np.asarray(array, dtype=float)

    b._write_feature_series = _capture
    feat_dir = str(tmp_path / "feat")
    written = b._materialize_report_rc_consensus(calendar, {"000001_sz": feat_dir})

    assert set(written) >= set(RRC_FIELDS)
    arr = captured[feat_dir]
    nan = -1.0  # sentinel for NaN comparison

    # calendar positions: [0101 (no activity), 0102 (both first->0 revisions), 0103 (A up, B dn)]
    np.testing.assert_array_equal(np.nan_to_num(arr["report_rc__eps_up"], nan=nan), [nan, 0, 1])
    np.testing.assert_array_equal(np.nan_to_num(arr["report_rc__eps_dn"], nan=nan), [nan, 0, 1])
    np.testing.assert_array_equal(np.nan_to_num(arr["report_rc__eps_revision_count"], nan=nan), [nan, 0, 2])
    # n_active: NaN before first coverage (0101), then 2 live analysts on 0102/0103
    np.testing.assert_array_equal(np.nan_to_num(arr["report_rc__n_active_analysts"], nan=nan), [nan, 2, 2])


def test_report_rc_in_build_selection(tmp_path):
    # report_rc must be in the build's selected datasets so materialize_provider's
    # hook fires (and build_ledger runs); excluded when phase-3 is off.
    b = StagedQlibBackendBuilder(
        data_root=str(tmp_path / "d"), qlib_dir=str(tmp_path / "q"),
        build_id="sel", allow_exceptions=True,
    )
    assert "report_rc" in b.selected_datasets()
    b_no3 = StagedQlibBackendBuilder(
        data_root=str(tmp_path / "d"), qlib_dir=str(tmp_path / "q"),
        build_id="sel2", allow_exceptions=True, include_phase3=False,
    )
    assert "report_rc" not in b_no3.selected_datasets()


def _materialize_to_bins(tmp: Path, feat_dir: Path) -> None:
    b = _make_builder(tmp, _revision_fixture())
    calendar = b.open_calendar()
    feat_dir.mkdir(parents=True, exist_ok=True)
    # fabricate the reference close.day.bin the materializer aligns to (real builds
    # write price bins first via _run_dump_bin; here we stand one in).
    write_qlib_bin(str(feat_dir / "close.day.bin"),
                   np.arange(len(calendar), dtype=np.float32), start_index=0)
    b._materialize_report_rc_consensus(calendar, {"000001_sz": str(feat_dir)})


def test_report_rc_bins_roundtrip_and_deterministic(tmp_path):
    feat = tmp_path / "a" / "000001_sz"
    _materialize_to_bins(tmp_path / "a", feat)

    # bins round-trip through the real Qlib writer/reader
    si, up = read_qlib_bin(str(feat / "report_rc__eps_up.day.bin"))
    assert si == 0
    np.testing.assert_array_equal(np.nan_to_num(up, nan=-1.0), [-1, 0, 1])
    _, dn = read_qlib_bin(str(feat / "report_rc__eps_dn.day.bin"))
    np.testing.assert_array_equal(np.nan_to_num(dn, nan=-1.0), [-1, 0, 1])
    _, nact = read_qlib_bin(str(feat / "report_rc__n_active_analysts.day.bin"))
    np.testing.assert_array_equal(np.nan_to_num(nact, nan=-1.0), [-1, 2, 2])

    # every report_rc bin aligns to the reference close bin (Qlib-queryable)
    assert validate_stock_bins(str(feat), RRC_FIELDS) == []

    # deterministic: an independent rebuild produces byte-identical bins
    feat2 = tmp_path / "b" / "000001_sz"
    _materialize_to_bins(tmp_path / "b", feat2)
    for fn in RRC_FIELDS:
        assert (feat / f"{fn}.day.bin").read_bytes() == (feat2 / f"{fn}.day.bin").read_bytes()


def test_normalized_analyst_id_handles_messy_strings():
    org = pd.Series(["AAA证券", "BBB证券", "CCC证券", None])
    author = pd.Series(["甲", "丙,乙", "", "甲"])
    ids = normalized_analyst_id(org, author)
    assert ids.iloc[0] == "AAA证券::甲"
    assert ids.iloc[1].startswith("BBB证券::")
    assert set(ids.iloc[1].split("::", 1)[1].split("+")) == {"乙", "丙"}
    assert ids.iloc[2] == "CCC证券::UNKNOWN_AUTHOR"
    assert ids.iloc[3] == "::甲"
