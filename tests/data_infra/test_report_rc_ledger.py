"""P1 plumbing tests for the report_rc PIT ledger (15000积分 expansion).

The decisive guardrail: build_ledger must NOT collapse the many analyst×quarter
rows that share a (ts_code, report_date) into one row (the generic
`(ts_code, end_date, disclosure_date)` key would — report_rc has no end_date).
Also pins: exact-duplicate merge, the create_time anchor (contemporaneous honored /
bulk-backfill stamp ignored -> report_date+lag), and the analyst-id normalization.
No alpha / no screen — plumbing acceptance only.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data_infra.pit_backend import (  # noqa: E402
    StagedQlibBackendBuilder, normalized_analyst_id, BuildGateError,
    add_open_day_lag, strictly_next_open_trade_day, REPORT_RC_VENDOR_LAG_OPEN_DAYS,
    REPORT_RC_FRESH_HOLDOUT_START,
)
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


def _write_reference_data_long(base: Path) -> None:
    """6 open days so a 2-open-day lag + next-open stays on-calendar."""
    ref = base / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    days = ["20200101", "20200102", "20200103", "20200106", "20200107", "20200108"]
    pd.DataFrame([
        {"exchange": "SSE", "cal_date": d, "is_open": 1, "pretrade_date": days[max(i - 1, 0)]}
        for i, d in enumerate(days)
    ]).to_parquet(ref / "trade_cal.parquet", index=False)
    pd.DataFrame([
        {"ts_code": "000001.SZ", "symbol": "000001", "exchange": "SZSE", "list_date": "19910101"},
    ]).to_parquet(ref / "stock_basic.parquet", index=False)


def test_report_rc_missing_create_time_uses_fixed_open_day_lag(tmp_path):
    # The decisive PIT canary: a row WITHOUT create_time must NOT be exposed at
    # next_open(report_date); it gets report_date + REPORT_RC_VENDOR_LAG_OPEN_DAYS.
    data_root = tmp_path / "data"
    _write_reference_data_long(data_root)
    d = data_root / "analyst" / "report_rc"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"ts_code": "000001.SZ", "report_date": "20200101", "create_time": _ct("2020-01-01"),
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.0},
        {"ts_code": "000001.SZ", "report_date": "20200101", "create_time": None,
         "org_name": "BBB证券", "author_name": "乙", "quarter": "2024Q4", "eps": 1.0},
    ]).to_parquet(d / "report_rc_2020.parquet", index=False)
    b = StagedQlibBackendBuilder(
        data_root=str(data_root), qlib_dir=str(tmp_path / "q"),
        build_id="lag", allow_exceptions=True,
    )
    b.normalize_dataset("report_rc")
    b.build_ledger("report_rc")
    led = pd.read_parquet(b.ledger_path("report_rc"))
    led["effective_date"] = pd.to_datetime(led["effective_date"])
    with_ct = led.loc[led["normalized_analyst_id"] == "AAA证券::甲", "effective_date"].iloc[0]
    without_ct = led.loc[led["normalized_analyst_id"] == "BBB证券::乙", "effective_date"].iloc[0]
    assert with_ct == pd.Timestamp("2020-01-02")            # next open after report/create
    assert without_ct != pd.Timestamp("2020-01-02")          # NOT exposed at next_open(report_date)
    assert without_ct == pd.Timestamp("2020-01-06")          # 0101 +2 open = 0103 -> next open = 0106


def test_report_rc_backfill_create_time_ignored_anchors_on_report_date(tmp_path):
    # The deep-history reclamation canary (validated 2026-06-08): a create_time that is
    # a vendor BULK-BACKFILL stamp (gap > REPORT_RC_BACKFILL_GAP_DAYS, e.g. the 2022-05
    # stamp on a 2020 report) must be IGNORED — the row anchors at report_date + lag,
    # NOT collapsed to next_open(2022-05-xx). Two analysts, same report_date: one with a
    # contemporaneous create_time, one with a backfill stamp -> identical effective date.
    data_root = tmp_path / "data"
    _write_reference_data_long(data_root)
    d = data_root / "analyst" / "report_rc"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"ts_code": "000001.SZ", "report_date": "20200101", "create_time": _ct("2020-01-01"),
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.0},
        {"ts_code": "000001.SZ", "report_date": "20200101", "create_time": "2022-05-03 08:00:00",
         "org_name": "BBB证券", "author_name": "乙", "quarter": "2024Q4", "eps": 1.0},
    ]).to_parquet(d / "report_rc_2020.parquet", index=False)
    b = StagedQlibBackendBuilder(
        data_root=str(data_root), qlib_dir=str(tmp_path / "q"),
        build_id="backfill", allow_exceptions=True,
    )
    b.normalize_dataset("report_rc")
    b.build_ledger("report_rc")
    led = pd.read_parquet(b.ledger_path("report_rc"))
    led["effective_date"] = pd.to_datetime(led["effective_date"])
    contemporaneous = led.loc[led["normalized_analyst_id"] == "AAA证券::甲", "effective_date"].iloc[0]
    backfilled = led.loc[led["normalized_analyst_id"] == "BBB证券::乙", "effective_date"].iloc[0]
    assert contemporaneous == pd.Timestamp("2020-01-02")     # contemporaneous create_time honored
    # backfill stamp ignored -> report_date + 2 open days (0103) -> next open = 0106,
    # NOT 2022-05 (which would be off this 6-day test calendar and drop the row entirely)
    assert backfilled == pd.Timestamp("2020-01-06")
    assert pd.notna(backfilled), "backfilled row must survive (deep history reclaimed), not drop to NaT"


def _write_business_calendar(base: Path, start: str, end: str) -> pd.DatetimeIndex:
    """trade_cal.parquet with every weekday in [start, end] open. Returns the open index
    (so a test can compute expected anchors via the same helpers the builder uses)."""
    ref = base / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    days = pd.bdate_range(start, end)
    prev = days[0]
    rows = []
    for d in days:
        rows.append({"exchange": "SSE", "cal_date": d.strftime("%Y%m%d"), "is_open": 1,
                     "pretrade_date": prev.strftime("%Y%m%d")})
        prev = d
    pd.DataFrame(rows).to_parquet(ref / "trade_cal.parquet", index=False)
    pd.DataFrame([
        {"ts_code": "000001.SZ", "symbol": "000001", "exchange": "SZSE", "list_date": "19910101"},
    ]).to_parquet(ref / "stock_basic.parquet", index=False)
    return days


def test_report_rc_backfill_gap_boundary_45_trusted_46_ignored(tmp_path):
    # The load-bearing rule now (GPT post-impl review Q6): create_time is trusted iff the
    # calendar-day gap from report_date is <= REPORT_RC_BACKFILL_GAP_DAYS (=45). Pin the
    # boundary with three analysts sharing report_date 2020-01-01 (intraday create_time, to
    # exercise the calendar-day normalize): gap 45 trusts create_time; gap 46 ignores it;
    # gap -1 (pre-dated) falls back. Expectations computed via the real helpers on the same
    # calendar, so the test is robust to the exact holiday layout.
    data_root = tmp_path / "data"
    open_days = _write_business_calendar(data_root, "2019-12-20", "2020-03-02")
    d = data_root / "analyst" / "report_rc"
    d.mkdir(parents=True, exist_ok=True)
    report = "20200101"
    pd.DataFrame([
        {"ts_code": "000001.SZ", "report_date": report, "create_time": "2020-02-15 21:00:00",
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.0},   # gap 45 -> trust
        {"ts_code": "000001.SZ", "report_date": report, "create_time": "2020-02-16 21:00:00",
         "org_name": "BBB证券", "author_name": "乙", "quarter": "2024Q4", "eps": 1.0},   # gap 46 -> ignore
        {"ts_code": "000001.SZ", "report_date": report, "create_time": "2019-12-31 21:00:00",
         "org_name": "CCC证券", "author_name": "丙", "quarter": "2024Q4", "eps": 1.0},   # gap -1 -> fallback
    ]).to_parquet(d / "report_rc_2020.parquet", index=False)
    b = StagedQlibBackendBuilder(data_root=str(data_root), qlib_dir=str(tmp_path / "q"),
                                 build_id="boundary", allow_exceptions=True)
    b.normalize_dataset("report_rc")
    b.build_ledger("report_rc")
    led = pd.read_parquet(b.ledger_path("report_rc"))
    led["effective_date"] = pd.to_datetime(led["effective_date"])
    eff = {a: led.loc[led["normalized_analyst_id"] == a, "effective_date"].iloc[0]
           for a in led["normalized_analyst_id"].unique()}

    exp_trust = strictly_next_open_trade_day(pd.Series([pd.Timestamp("2020-02-15 21:00:00")]), open_days).iloc[0]
    fallback_obs = add_open_day_lag(pd.Series([pd.Timestamp(report)]), open_days, REPORT_RC_VENDOR_LAG_OPEN_DAYS)
    exp_fallback = strictly_next_open_trade_day(fallback_obs, open_days).iloc[0]

    assert exp_trust != exp_fallback                  # the boundary genuinely bifurcates
    assert eff["AAA证券::甲"] == exp_trust            # gap 45 -> create_time honored
    assert eff["BBB证券::乙"] == exp_fallback         # gap 46 -> create_time ignored (backfill)
    assert eff["CCC证券::丙"] == exp_fallback         # gap -1 -> fallback


def test_report_rc_transition_mixed_rows_split_effective_dates(tmp_path):
    # 2022 transition (GPT post-impl review Q3): same ts_code + report_date, one
    # contemporaneous create_time and one 2022-05 bulk-backfill stamp -> two DIFFERENT
    # effective dates, BOTH rows survive (no collapse). Locks the intended asymmetry.
    data_root = tmp_path / "data"
    open_days = _write_business_calendar(data_root, "2022-02-20", "2022-06-01")
    d = data_root / "analyst" / "report_rc"
    d.mkdir(parents=True, exist_ok=True)
    report = "20220301"
    pd.DataFrame([
        {"ts_code": "000001.SZ", "report_date": report, "create_time": "2022-03-02 08:00:00",
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.0},   # contemporaneous (gap 1)
        {"ts_code": "000001.SZ", "report_date": report, "create_time": "2022-05-03 08:00:00",
         "org_name": "BBB证券", "author_name": "乙", "quarter": "2024Q4", "eps": 1.0},   # backfill stamp (gap 63)
    ]).to_parquet(d / "report_rc_2022.parquet", index=False)
    b = StagedQlibBackendBuilder(data_root=str(data_root), qlib_dir=str(tmp_path / "q"),
                                 build_id="transition", allow_exceptions=True)
    b.normalize_dataset("report_rc")
    b.build_ledger("report_rc")
    led = pd.read_parquet(b.ledger_path("report_rc"))
    led["effective_date"] = pd.to_datetime(led["effective_date"])
    assert len(led) == 2, f"both rows must survive (no collapse), got {len(led)}"
    eff = {a: led.loc[led["normalized_analyst_id"] == a, "effective_date"].iloc[0]
           for a in led["normalized_analyst_id"].unique()}

    exp_contemp = strictly_next_open_trade_day(pd.Series([pd.Timestamp("2022-03-02 08:00:00")]), open_days).iloc[0]
    backfill_obs = add_open_day_lag(pd.Series([pd.Timestamp(report)]), open_days, REPORT_RC_VENDOR_LAG_OPEN_DAYS)
    exp_backfill = strictly_next_open_trade_day(backfill_obs, open_days).iloc[0]

    assert exp_contemp != exp_backfill                # the asymmetry GPT analyzed
    assert eff["AAA证券::甲"] == exp_contemp          # contemporaneous create_time honored
    assert eff["BBB证券::乙"] == exp_backfill         # 2022-05 stamp ignored -> report_date+lag


def test_report_rc_same_effective_date_chronological_order(tmp_path):
    # Two forecasts by one analyst/quarter both visible 2020-01-02, written in REVERSE
    # chronological raw order. Must classify by availability (UP), not raw order (DOWN).
    early = {"ts_code": "000001.SZ", "report_date": "20191231", "create_time": "2020-01-01 09:00:00",
             "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.0}
    late = {"ts_code": "000001.SZ", "report_date": "20200101", "create_time": "2020-01-01 21:00:00",
            "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.5}
    b = _make_builder(tmp_path, [late, early])  # reverse-chronological raw order
    cal = b.open_calendar()
    captured: dict = {}
    b._write_feature_series = lambda fd, fn, arr: captured.setdefault(fd, {}).__setitem__(
        fn, np.asarray(arr, dtype=float))
    b._materialize_report_rc_consensus(cal, {"000001_sz": "x"})
    a = captured["x"]
    # day index 1 = 2020-01-02: the later forecast (1.0 -> 1.5) is an UP revision
    assert a["report_rc__eps_up"][1] == 1.0
    assert a["report_rc__eps_dn"][1] == 0.0


def test_report_rc_missing_quarter_excluded(tmp_path):
    # A non-null-EPS forecast with no target quarter must not feed revision OR n_active.
    rows = [
        {"ts_code": "000001.SZ", "report_date": "20200101", "create_time": _ct("2020-01-01"),
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2024Q4", "eps": 1.0},
        {"ts_code": "000001.SZ", "report_date": "20200101", "create_time": _ct("2020-01-01"),
         "org_name": "BBB证券", "author_name": "乙", "quarter": None, "eps": 9.0},
    ]
    b = _make_builder(tmp_path, rows)
    cal = b.open_calendar()
    captured: dict = {}
    b._write_feature_series = lambda fd, fn, arr: captured.setdefault(fd, {}).__setitem__(
        fn, np.asarray(arr, dtype=float))
    b._materialize_report_rc_consensus(cal, {"000001_sz": "x"})
    nact = captured["x"]["report_rc__n_active_analysts"]
    # only the valid-quarter analyst counts (== 1 from 2020-01-02 on), not 2
    assert nact[1] == 1.0


def test_report_rc_absent_quarter_column_fails_closed(tmp_path):
    # A corrupted feed with NO quarter column must fail closed (emit nothing),
    # not KeyError the revision groupby.
    data_root = tmp_path / "data"
    _write_reference_data(data_root)
    d = data_root / "analyst" / "report_rc"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"ts_code": "000001.SZ", "report_date": "20200101", "create_time": _ct("2020-01-01"),
         "org_name": "AAA证券", "author_name": "甲", "eps": 1.0},  # no 'quarter' column
    ]).to_parquet(d / "report_rc_2020.parquet", index=False)
    b = StagedQlibBackendBuilder(
        data_root=str(data_root), qlib_dir=str(tmp_path / "q"),
        build_id="noq", allow_exceptions=True,
    )
    b.normalize_dataset("report_rc")
    b.build_ledger("report_rc")
    written = b._materialize_report_rc_consensus(b.open_calendar(), {"000001_sz": str(tmp_path / "f")})
    assert written == []


def test_normalized_analyst_id_handles_messy_strings():
    org = pd.Series(["AAA证券", "BBB证券", "CCC证券", None])
    author = pd.Series(["甲", "丙,乙", "", "甲"])
    ids = normalized_analyst_id(org, author)
    assert ids.iloc[0] == "AAA证券::甲"
    assert ids.iloc[1].startswith("BBB证券::")
    assert set(ids.iloc[1].split("::", 1)[1].split("+")) == {"乙", "丙"}
    assert ids.iloc[2] == "CCC证券::UNKNOWN_AUTHOR"
    assert ids.iloc[3] == "::甲"


# ── Calendar-unfreeze Phase 5 B1+B2: report_rc availability-boundary anchor guard ──
# The sealed/fresh boundary is an AVAILABILITY boundary. A row affects the fresh
# window when its report_date OR create_time is at/after REPORT_RC_FRESH_HOLDOUT_START;
# for such rows the bulk-backfill fallback is disabled (anchor at the true visibility).
# Historical rows (both dates pre-boundary) keep the validated deep-history path — the
# older tests above (2020/2022 dates) are the regression proof for that half.
# (Revision-ledger cases — retrograde create_time, silent payload revision — land with
# the report_rc revision-ledger commit, not this anchor commit.)

def _build_fresh_ledger(tmp: Path, rows: list) -> pd.DataFrame:
    data_root = tmp / "data"
    _write_business_calendar(data_root, "2026-01-01", "2026-03-31")
    d = data_root / "analyst" / "report_rc"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(d / "report_rc_2026.parquet", index=False)
    b = StagedQlibBackendBuilder(data_root=str(data_root), qlib_dir=str(tmp / "q"),
                                 build_id="fresh_guard", allow_exceptions=True)
    b.normalize_dataset("report_rc")
    b.build_ledger("report_rc")
    return pd.read_parquet(b.ledger_path("report_rc"))


def test_report_rc_fresh_late_arrival_anchors_on_create_time_not_report_date(tmp_path):
    # THE B2 leak: report_date pre-boundary (2026-01-05) but create_time in the fresh
    # window (2026-03-10), gap 64d > 45. The OLD code classified this as backfill and
    # anchored at report_date+lag (Jan) — exposing a row in the sealed window BEFORE it
    # actually arrived (a lookahead). The fresh guard forces max(report_date, create_time).
    open_days = pd.bdate_range("2026-01-01", "2026-03-31")
    led = _build_fresh_ledger(tmp_path, [
        {"ts_code": "000001.SZ", "report_date": "20260105", "create_time": _ct("2026-03-10"),
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.0},
    ])
    assert len(led) == 1
    eff = pd.to_datetime(led["effective_date"]).iloc[0]
    exp_fresh = strictly_next_open_trade_day(pd.Series([pd.Timestamp("2026-03-10 21:00:00")]), open_days).iloc[0]
    old_backfill_obs = add_open_day_lag(pd.Series([pd.Timestamp("20260105")]), open_days, REPORT_RC_VENDOR_LAG_OPEN_DAYS)
    old_backfill_eff = strictly_next_open_trade_day(old_backfill_obs, open_days).iloc[0]
    assert eff == exp_fresh, f"expected create_time anchor {exp_fresh}, got {eff}"
    assert eff != old_backfill_eff              # NOT the old report_date+lag leak
    assert eff >= pd.Timestamp(REPORT_RC_FRESH_HOLDOUT_START)


def test_report_rc_fresh_contemporaneous_anchors_normally(tmp_path):
    open_days = pd.bdate_range("2026-01-01", "2026-03-31")
    led = _build_fresh_ledger(tmp_path, [
        {"ts_code": "000001.SZ", "report_date": "20260302", "create_time": _ct("2026-03-02"),
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.0},
    ])
    eff = pd.to_datetime(led["effective_date"]).iloc[0]
    exp = strictly_next_open_trade_day(pd.Series([pd.Timestamp("2026-03-02 21:00:00")]), open_days).iloc[0]
    assert eff == exp


def test_report_rc_fresh_missing_create_time_quarantined(tmp_path):
    # Fresh-window row with NO create_time: fail-closed QUARANTINE (dropped from the
    # served ledger). A co-located row WITH create_time survives — proves selective drop.
    led = _build_fresh_ledger(tmp_path, [
        {"ts_code": "000001.SZ", "report_date": "20260302", "create_time": None,
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.0},
        {"ts_code": "000001.SZ", "report_date": "20260302", "create_time": _ct("2026-03-02"),
         "org_name": "BBB证券", "author_name": "乙", "quarter": "2026Q4", "eps": 1.1},
    ])
    assert set(led["normalized_analyst_id"]) == {"BBB证券::乙"}, "the no-create_time fresh row must be quarantined"


def test_report_rc_carry_into_fresh_forces_availability_anchor(tmp_path):
    # GPT impl-review B1 (condition 4): a row with BOTH scalar dates pre-boundary
    # (report_date 2026-01-05, create_time 2026-02-20, gap 46 -> old code = backfill ->
    # report_date+lag = January) whose 120-open-day active/carry interval reaches the
    # sealed fresh window MUST anchor at its provable availability max(report,create) =
    # 2026-02-20, not the assumed-backfill January — else its carried state injects into
    # the sealed window from an unproven early date.
    open_days = pd.bdate_range("2026-01-01", "2026-03-31")
    led = _build_fresh_ledger(tmp_path, [
        {"ts_code": "000001.SZ", "report_date": "20260105", "create_time": "2026-02-20 08:00:00",
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.0},
    ])
    eff = pd.to_datetime(led["effective_date"]).iloc[0]
    exp = strictly_next_open_trade_day(pd.Series([pd.Timestamp("2026-02-20 08:00:00")]), open_days).iloc[0]
    assert eff == exp, f"carry-into-fresh must anchor at create_time {exp}, got {eff}"


def test_report_rc_deep_history_no_carry_keeps_backfill_anchor(tmp_path):
    # The regression proof that history is preserved: a row whose active/carry interval
    # does NOT reach the fresh window (report_date 2025-06-02 is >120 open days before
    # 2026-02-28) keeps the validated deep-history path (report_date+lag), untouched by
    # the fresh guard, even with a backfill-gap create_time.
    data_root, qlib = tmp_path / "data", tmp_path / "q"
    open_days = _write_business_calendar(data_root, "2025-06-01", "2026-03-31")
    b = _rebuild_report_rc(data_root, qlib, [
        {"ts_code": "000001.SZ", "report_date": "20250602", "create_time": "2025-09-15 08:00:00",
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2025Q4", "eps": 1.0},
    ], "deep_nocarry")
    led = pd.read_parquet(b.ledger_path("report_rc"))
    eff = pd.to_datetime(led["effective_date"]).iloc[0]
    backfill_obs = add_open_day_lag(pd.Series([pd.Timestamp("20250602")]), open_days, REPORT_RC_VENDOR_LAG_OPEN_DAYS)
    exp = strictly_next_open_trade_day(backfill_obs, open_days).iloc[0]
    assert eff == exp, f"deep row without carry must keep report_date+lag {exp}, got {eff}"
    assert eff < pd.Timestamp(REPORT_RC_FRESH_HOLDOUT_START)



# ── Phase 5 B2: report_rc revision-ledger no-retrograde guard + raw_fetch_ts rescue ──

def _rebuild_report_rc(data_root: Path, qlib: Path, rows: list, build_id: str):
    d = data_root / "analyst" / "report_rc"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(d / "report_rc_2026.parquet", index=False)
    b = StagedQlibBackendBuilder(data_root=str(data_root), qlib_dir=str(qlib),
                                 build_id=build_id, allow_exceptions=True)
    b.normalize_dataset("report_rc")
    b.build_ledger("report_rc")
    return b


def test_report_rc_no_retrograde_blocks_earlier_effective(tmp_path):
    # A rebuild that moves an existing fresh-window key's create_time EARLIER (vendor
    # revised it backward) would move effective_date earlier = a retroactive
    # earlier-visibility into the sealed window. The revision-ledger guard blocks it.
    data_root, qlib = tmp_path / "data", tmp_path / "q"
    _write_business_calendar(data_root, "2026-01-01", "2026-03-31")
    row = {"ts_code": "000001.SZ", "report_date": "20260302",
           "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.0}
    _rebuild_report_rc(data_root, qlib, [{**row, "create_time": _ct("2026-03-10")}], "retro1")
    with pytest.raises(BuildGateError, match="retrograde"):
        _rebuild_report_rc(data_root, qlib, [{**row, "create_time": _ct("2026-03-03")}], "retro2")


def test_report_rc_no_retrograde_allows_later_effective(tmp_path):
    # A later create_time (visibility DELAYED) for the same key is conservative, not a
    # lookahead — allowed.
    data_root, qlib = tmp_path / "data", tmp_path / "q"
    _write_business_calendar(data_root, "2026-01-01", "2026-03-31")
    row = {"ts_code": "000001.SZ", "report_date": "20260302",
           "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.0}
    _rebuild_report_rc(data_root, qlib, [{**row, "create_time": _ct("2026-03-05")}], "fwd1")
    b2 = _rebuild_report_rc(data_root, qlib, [{**row, "create_time": _ct("2026-03-12")}], "fwd2")
    led = pd.read_parquet(b2.ledger_path("report_rc"))
    assert (pd.to_datetime(led["effective_date"]) >= pd.Timestamp("2026-03-05")).all()


def test_report_rc_historical_retrograde_not_blocked(tmp_path):
    # Historical keys (pre-boundary) are exempt: deep-history best-known-state re-dating
    # is intentional. A pre-boundary key whose anchor shifts must NOT trip the guard.
    data_root, qlib = tmp_path / "data", tmp_path / "q"
    _write_business_calendar(data_root, "2019-12-20", "2020-03-31")
    row = {"ts_code": "000001.SZ", "report_date": "20200115",
           "org_name": "AAA证券", "author_name": "甲", "quarter": "2019Q4", "eps": 1.0}
    _rebuild_report_rc(data_root, qlib, [{**row, "create_time": _ct("2020-01-20")}], "hist1")
    # earlier create_time on the same historical key -> no block (exempt)
    b2 = _rebuild_report_rc(data_root, qlib, [{**row, "create_time": _ct("2020-01-16")}], "hist2")
    assert len(pd.read_parquet(b2.ledger_path("report_rc"))) == 1


def test_report_rc_fresh_missing_ct_rescued_by_raw_fetch_ts(tmp_path):
    # A fresh row lacking create_time but carrying our own raw_fetch_ts stamp is NOT
    # quarantined — it anchors at the first-seen floor raw_fetch_ts.
    open_days = pd.bdate_range("2026-01-01", "2026-03-31")
    led = _build_fresh_ledger(tmp_path, [
        {"ts_code": "000001.SZ", "report_date": "20260302", "create_time": None,
         "raw_fetch_ts": "2026-03-05 10:00:00",
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.0},
    ])
    assert len(led) == 1, "raw_fetch_ts must rescue the row from quarantine"
    eff = pd.to_datetime(led["effective_date"]).iloc[0]
    exp = strictly_next_open_trade_day(pd.Series([pd.Timestamp("2026-03-05 10:00:00")]), open_days).iloc[0]
    assert eff == exp


def test_report_rc_no_retrograde_blocks_fresh_to_prefresh(tmp_path):
    # GPT impl-review B2: a key whose PRIOR effective was inside the fresh window
    # (2026-03-11) but a later rebuild re-dates it BEFORE the boundary (report_date and
    # new effective both pre-boundary) must still be caught — the old guard scoped only on
    # the NEW effective/report_date and missed this. The append-only baseline + prior-eff
    # fresh scope catches it.
    data_root, qlib = tmp_path / "data", tmp_path / "q"
    _write_business_calendar(data_root, "2026-01-01", "2026-03-31")
    row = {"ts_code": "000001.SZ", "report_date": "20260105",
           "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.0}
    # Build 1: create_time 2026-03-10 (fresh) -> effective 2026-03-11 (in the fresh window).
    _rebuild_report_rc(data_root, qlib, [{**row, "create_time": _ct("2026-03-10")}], "ftp1")
    # Build 2: create_time REMOVED -> backfill anchor would be report_date+lag (January),
    # i.e. the prior fresh key re-dated back before the boundary. Must raise.
    with pytest.raises(BuildGateError, match="retrograde"):
        _rebuild_report_rc(data_root, qlib, [{**row, "create_time": None,
                                              "raw_fetch_ts": "2026-01-06 08:00:00"}], "ftp2")


def test_report_rc_no_retrograde_survives_disappear_reappear(tmp_path):
    # GPT impl-review M2: a fresh key served then QUARANTINED (dropped from the served
    # ledger) then reappearing EARLIER must still be caught — the append-only baseline
    # retains the dropped key's min-effective, which the collapsed ledger cannot.
    data_root, qlib = tmp_path / "data", tmp_path / "q"
    _write_business_calendar(data_root, "2026-01-01", "2026-03-31")
    row = {"ts_code": "000001.SZ", "report_date": "20260302",
           "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.0}
    _rebuild_report_rc(data_root, qlib, [{**row, "create_time": _ct("2026-03-10")}], "dr1")  # eff 2026-03-11
    # disappear: fresh row with no create_time / no raw_fetch_ts -> quarantined (dropped)
    _rebuild_report_rc(data_root, qlib, [{**row, "create_time": None}], "dr2")
    # reappear EARLIER (create_time 2026-03-03 -> eff 2026-03-04 < baseline 2026-03-11) -> raise
    with pytest.raises(BuildGateError, match="retrograde"):
        _rebuild_report_rc(data_root, qlib, [{**row, "create_time": _ct("2026-03-03")}], "dr3")


def test_report_rc_boundary_policy_mismatch_raises():
    # GPT impl-review M3: a policy whose fresh_holdout_start differs from the code constant
    # must fail the build (a boundary move needs a matching code change). A legacy policy
    # without the field is exempt; a matching policy passes.
    from types import SimpleNamespace
    from data_infra.pit_backend import (
        _assert_report_rc_boundary_matches_policy, REPORT_RC_FRESH_HOLDOUT_START,
    )
    with pytest.raises(BuildGateError, match="boundary mismatch"):
        _assert_report_rc_boundary_matches_policy(SimpleNamespace(fresh_holdout_start="2026-03-15"), "thaw_x")
    # matching + legacy (None) both pass silently
    _assert_report_rc_boundary_matches_policy(SimpleNamespace(fresh_holdout_start=REPORT_RC_FRESH_HOLDOUT_START), "thaw_ok")
    _assert_report_rc_boundary_matches_policy(SimpleNamespace(fresh_holdout_start=None), "legacy")


def test_report_rc_fresh_late_first_seen_floors_value_at_raw_fetch(tmp_path):
    # GPT impl-review B3 (value lookahead): a fresh row with create_time present but a
    # LATE first-seen raw_fetch_ts (a value revision / late-observed row) must anchor at
    # max(report, create, raw_fetch) = raw_fetch, so the value cannot be backdated to the
    # create_time into the sealed window.
    open_days = pd.bdate_range("2026-01-01", "2026-07-31")
    data_root, qlib = tmp_path / "data", tmp_path / "q"
    _write_business_calendar(data_root, "2026-01-01", "2026-07-31")
    b = _rebuild_report_rc(data_root, qlib, [
        {"ts_code": "000001.SZ", "report_date": "20260305", "create_time": _ct("2026-03-10"),
         "raw_fetch_ts": "2026-07-01 09:00:00",  # first observed only in July
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.40},
    ], "b3")
    led = pd.read_parquet(b.ledger_path("report_rc"))
    eff = pd.to_datetime(led["effective_date"]).iloc[0]
    exp = strictly_next_open_trade_day(pd.Series([pd.Timestamp("2026-07-01 09:00:00")]), open_days).iloc[0]
    assert eff == exp, f"late first-seen value must floor at raw_fetch {exp}, got {eff}"
    assert eff > pd.Timestamp("2026-03-11"), "value must NOT be backdated to the create_time"


def test_report_rc_fresh_stable_row_not_inflated_by_first_seen(tmp_path):
    # M1 stays fixed under the B3 floor: a stable row whose first-seen raw_fetch_ts is
    # contemporaneous with its create_time (we had it since its create month) is NOT
    # inflated — floor = max(report, create, raw_fetch) = create.
    open_days = pd.bdate_range("2026-01-01", "2026-07-31")
    data_root, qlib = tmp_path / "data", tmp_path / "q"
    _write_business_calendar(data_root, "2026-01-01", "2026-07-31")
    b = _rebuild_report_rc(data_root, qlib, [
        {"ts_code": "000001.SZ", "report_date": "20260305", "create_time": _ct("2026-03-10"),
         "raw_fetch_ts": "2026-03-11 09:00:00",  # first seen the day after publish (contemporaneous)
         "org_name": "AAA证券", "author_name": "甲", "quarter": "2026Q4", "eps": 1.00},
    ], "stable")
    led = pd.read_parquet(b.ledger_path("report_rc"))
    eff = pd.to_datetime(led["effective_date"]).iloc[0]
    exp = strictly_next_open_trade_day(pd.Series([pd.Timestamp("2026-03-11 09:00:00")]), open_days).iloc[0]
    assert eff == exp  # ~ create_time, not inflated to a far-later fetch
    assert eff < pd.Timestamp("2026-04-01")


def test_report_rc_staged_build_asserts_policy_boundary(tmp_path, monkeypatch):
    # GPT impl-review M4: a non-publish staged build given a calendar_policy_id must ALSO
    # assert the boundary (dry-run evidence must not use a stale constant). Exercised via
    # the extracted helper against a mismatched policy.
    from types import SimpleNamespace
    from data_infra.pit_backend import _assert_report_rc_boundary_matches_policy
    with pytest.raises(BuildGateError, match="boundary mismatch"):
        _assert_report_rc_boundary_matches_policy(SimpleNamespace(fresh_holdout_start="2026-05-01"), "thaw_bad")
