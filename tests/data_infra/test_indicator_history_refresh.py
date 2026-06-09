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
