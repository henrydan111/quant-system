from pathlib import Path
from unittest.mock import MagicMock, patch

from src.backtest_engine.event_driven import EventDrivenBacktester


def _run_with_mocked_components(data_dir: Path):
    strategy = MagicMock()
    with patch("src.backtest_engine.event_driven.QlibDataFeeder") as feeder_cls, patch(
        "src.backtest_engine.event_driven.Exchange"
    ) as exchange_cls, patch("src.backtest_engine.event_driven.BacktestEngine") as engine_cls:
        engine = engine_cls.return_value
        expected_result = object()
        engine.run.return_value = expected_result

        result = EventDrivenBacktester(data_dir=str(data_dir)).run(
            strategy=strategy,
            start_time="2024-01-02",
            end_time="2024-01-31",
        )

    return result, feeder_cls, exchange_cls, engine_cls, expected_result


def test_event_driven_backtester_passes_suspension_ranges_when_present(tmp_path):
    ranges_path = tmp_path / "market" / "suspension" / "suspension_ranges.parquet"
    ranges_path.parent.mkdir(parents=True)
    ranges_path.write_bytes(b"placeholder")

    result, _feeder_cls, exchange_cls, _engine_cls, expected_result = _run_with_mocked_components(tmp_path)

    assert result is expected_result
    assert exchange_cls.call_args.kwargs["suspension_ranges_path"] == str(ranges_path)


def test_event_driven_backtester_falls_back_when_suspension_ranges_missing(tmp_path, caplog):
    result, _feeder_cls, exchange_cls, _engine_cls, expected_result = _run_with_mocked_components(tmp_path)

    assert result is expected_result
    assert exchange_cls.call_args.kwargs["suspension_ranges_path"] is None
    assert "fall back to vol==0 suspension detection" in caplog.text
