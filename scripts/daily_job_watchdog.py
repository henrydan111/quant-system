# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 5-C: independent missed-run watchdog
"""Phase 5-C watchdog: detect a SILENTLY-MISSED-or-INCOMPLETE daily raw job.

The main QuantDailyRawUpdate task cannot report that it never launched — a sleeping/offline machine
produces no flag at all. This independent morning task (QuantDailyRawWatchdog, ~10:00 CST) RECOMPUTES
the contiguous completed-session watermark from the per-session manifests (validating the WHOLE
(provider_floor, target] interval, not just one date's heartbeat — GPT M2) and, if it does not reach
the last complete trading session (CST), writes logs/daily_job_alert_<date>.flag and exits non-zero.
Clears its own alert on success.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
LOGS_DIR = PROJECT_ROOT / "logs"
HEARTBEAT = LOGS_DIR / "daily_job_heartbeat.json"


def _cst_date() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
    except Exception:  # pragma: no cover
        return datetime.now().strftime("%Y%m%d")


def _alert(msg: str) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    # own the daily_job_alert (NOT qa_alert, which a manual QA run would clear — GPT minor 1)
    (LOGS_DIR / f"daily_job_alert_{_cst_date()}.flag").write_text(msg + "\n", encoding="utf-8")
    print(msg, file=sys.stderr)


def main() -> int:
    from data_infra.pipeline.update_daily_data import resolve_last_complete_session
    from data_infra.pipeline.daily_ops import contiguous_watermark
    ref_dir = str(PROJECT_ROOT / "data" / "reference")
    cal = PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt"
    if not cal.exists() or not cal.read_text(encoding="utf-8").split():
        _alert("watchdog: provider calendar missing/empty — cannot establish floor")
        return 1
    floor = cal.read_text(encoding="utf-8").split()[-1].replace("-", "")
    try:
        expected = resolve_last_complete_session(ref_dir)
    except (SystemExit, Exception) as exc:  # noqa: BLE001 — a missing/corrupt calendar is alert-worthy
        _alert(f"watchdog: cannot resolve last complete session: {exc}")
        return 1

    # recompute the contiguous watermark from the manifests (validates every session in the interval,
    # not just the heartbeat's single date). Reaching `expected` means the whole interval is complete.
    watermark = contiguous_watermark(ref_dir, str(LOGS_DIR), expected, floor)
    if watermark != expected:
        _alert(f"watchdog: daily job STALE/INCOMPLETE - contiguous watermark {watermark} != expected "
               f"{expected} (missed/failed/gap in (provider_floor {floor}, {expected}])")
        return 1
    af = LOGS_DIR / f"daily_job_alert_{_cst_date()}.flag"  # clear our own alert on recovery
    if af.exists():
        af.unlink()
    print(f"watchdog OK: contiguous watermark {watermark} == expected {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
