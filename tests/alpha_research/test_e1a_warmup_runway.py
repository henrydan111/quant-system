"""Regression guard for the E1a (price-volume) warmup prerequisite (#34).

The windowed E1a factors (route/discrete/time_rank/highest_days, up to a 271-day lookback) are NOT
warmed by dropping partial-window rows; they are warmed because the IS evaluation window starts deep
INSIDE the provider calendar, so Qlib's rolling operators warm every window from the pre-IS runway.

This is the STRUCTURAL tripwire: the trading-day runway between the provider calendar start and the IS
window start must stay >= the deepest E1a lookback window. If someone moves the IS start earlier or
registers a deeper-window factor without extending the calendar, this fails — flagging that the
empirical start-date-invariance proof ([verify_e1a_warmup_runway.py](../../workspace/scripts/verify_e1a_warmup_runway.py))
must be re-run. (The empirical max|diff|=0 proof is qlib-dependent and lives in that script.)
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CALENDAR = PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt"

# E1a factor -> max lookback window in trading days (route/discrete period+Ref; time_rank 250+20+1;
# highest_days 250+1). Mirrors workspace/scripts/verify_e1a_warmup_runway.py::E1A_WINDOWS.
E1A_WINDOWS = {
    "mmt_route_20d": 22, "mmt_route_250d": 252,
    "mmt_discrete_20d": 22, "mmt_discrete_250d": 252,
    "mmt_time_rank_20d": 271, "mmt_highest_days_250d": 251,
}


def _is_start() -> str:
    from workspace.scripts.unified_eval_full_run import TIME_SPLIT
    return TIME_SPLIT.is_start


@pytest.mark.skipif(not CALENDAR.exists(), reason="qlib calendar absent (data/ is gitignored)")
def test_pre_is_runway_covers_deepest_e1a_window():
    cal = [l.strip() for l in CALENDAR.read_text().splitlines() if l.strip()]
    is_start = _is_start()
    runway = sum(1 for d in cal if d < is_start)   # trading days strictly before the IS start
    max_win = max(E1A_WINDOWS.values())
    assert runway >= max_win, (
        f"pre-IS runway {runway} trading days (calendar {cal[0]} -> IS start {is_start}) is shorter than "
        f"the deepest E1a window {max_win} — windowed factors would be under-warmed at the IS start. "
        f"Re-run workspace/scripts/verify_e1a_warmup_runway.py and extend the calendar or the runway.")
