from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_infra.pipeline.indicator_history_refresh import (
    IndicatorVipHistoryRefresher,
    discover_indicator_periods,
    filter_periods,
)
from data_infra.storage import StorageManager


class _StubIndicatorFetcher:
    def __init__(self):
        self.calls = []

    def fetch_fina_indicator_vip(self, period: str, fields: str | None = None):
        self.calls.append(period)
        self.last_fields = fields
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "ann_date": "20240425",
                    "end_date": period,
                    "update_flag": 1,
                    "q_roe": 1.23,
                },
                {
                    "ts_code": "000026.SZ",
                    "ann_date": "20240425",
                    "end_date": period,
                    "update_flag": 0,
                    "q_roe": 2.34,
                },
                {
                    "ts_code": "000026.SZ",
                    "ann_date": "20240425",
                    "end_date": period,
                    "update_flag": 1,
                    "q_roe": 2.56,
                },
            ]
        )


def test_discover_and_filter_indicator_periods(tmp_path):
    indicator_dir = tmp_path / "indicators"
    indicator_dir.mkdir()
    for period in ("20240331", "20240630", "20240930"):
        pd.DataFrame({"end_date": [period]}).to_parquet(indicator_dir / f"indicators_{period}.parquet", index=False)

    periods = discover_indicator_periods(indicator_dir)

    assert periods == ["20240331", "20240630", "20240930"]
    assert filter_periods(periods, start_period="20240630") == ["20240630", "20240930"]
    assert filter_periods(periods, end_period="20240630") == ["20240331", "20240630"]


def test_indicator_refresh_stages_validates_and_swaps_live_dir(tmp_path):
    data_root = tmp_path / "data"
    live_dir = data_root / "fundamentals" / "indicators"
    live_dir.mkdir(parents=True)
    pd.DataFrame({"legacy": [1]}).to_parquet(live_dir / "indicators_20240331.parquet", index=False)

    storage = StorageManager(data_root=str(data_root))
    fetcher = _StubIndicatorFetcher()
    refresher = IndicatorVipHistoryRefresher(
        data_root=str(data_root),
        build_id="unit_indicator_refresh",
        output_root=str(tmp_path / "outputs"),
        fetcher=fetcher,
        storage=storage,
    )

    summaries = refresher.run(explicit_periods=["20240331", "20240630"])

    assert [summary.period for summary in summaries] == ["20240331", "20240630"]
    assert fetcher.calls == ["20240331", "20240630"]
    assert (live_dir / "indicators_20240331.parquet").exists()
    assert (live_dir / "indicators_20240630.parquet").exists()
    refreshed = pd.read_parquet(live_dir / "indicators_20240331.parquet")
    assert "update_flag" in refreshed.columns
    assert len(refreshed) == 3
    assert refresher.archive_dir.exists()
    assert (refresher.output_dir / "summary.json").exists()


def test_indicator_refresh_validate_only_checks_live_directory(tmp_path):
    data_root = tmp_path / "data"
    live_dir = data_root / "fundamentals" / "indicators"
    live_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "ann_date": ["20240425"],
            "end_date": ["20240331"],
            "update_flag": [1],
            "q_roe": [1.0],
        }
    ).to_parquet(live_dir / "indicators_20240331.parquet", index=False)

    refresher = IndicatorVipHistoryRefresher(
        data_root=str(data_root),
        build_id="unit_indicator_validate",
        output_root=str(tmp_path / "outputs"),
        fetcher=_StubIndicatorFetcher(),
        storage=StorageManager(data_root=str(data_root)),
    )

    summaries = refresher.run(explicit_periods=["20240331"], validate_only=True)

    assert len(summaries) == 1
    assert summaries[0].has_update_flag is True


def test_partial_refresh_swap_merges_untouched_periods(tmp_path, monkeypatch):
    """2026-07-03 incident regression: a subset-period refresh must CARRY the
    untouched live period files into the promoted store (merge, not amputate)."""
    import pandas as pd

    from src.data_infra.pipeline.indicator_history_refresh import IndicatorVipHistoryRefresher

    refresher = IndicatorVipHistoryRefresher.__new__(IndicatorVipHistoryRefresher)
    refresher.logger = __import__("logging").getLogger("t")
    refresher.live_dir = tmp_path / "indicators"
    refresher.stage_dir = tmp_path / "stage"
    refresher.archive_dir = tmp_path / "_archive" / "indicators_pre_t"
    refresher.storage = type("S", (), {"_record_ingest_manifest": lambda *a, **k: None})()
    refresher.build_id = "t"

    refresher.live_dir.mkdir()
    refresher.stage_dir.mkdir()
    for period in ("20240630", "20240930", "20251231"):
        pd.DataFrame({"ts_code": ["000001.SZ"], "end_date": [period]}).to_parquet(
            refresher.live_dir / f"indicators_{period}.parquet"
        )
    # staged refresh covers ONLY 20251231 (a revised version)
    pd.DataFrame({"ts_code": ["000001.SZ", "000002.SZ"], "end_date": ["20251231"] * 2}).to_parquet(
        refresher.stage_dir / "indicators_20251231.parquet"
    )

    refresher._swap_live_directory(summaries=[])

    live_files = sorted(p.name for p in refresher.live_dir.glob("*.parquet"))
    assert live_files == [
        "indicators_20240630.parquet",
        "indicators_20240930.parquet",
        "indicators_20251231.parquet",
    ]
    # the refreshed version won for the covered period
    assert len(pd.read_parquet(refresher.live_dir / "indicators_20251231.parquet")) == 2
    # the pre-swap store is archived intact
    assert len(list(refresher.archive_dir.glob("*.parquet"))) == 3
