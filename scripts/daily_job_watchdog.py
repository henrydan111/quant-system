# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 5-C: independent missed-run watchdog
"""Phase 5-C watchdog (GPT M2): detect a SILENTLY-MISSED daily raw job.

The main QuantDailyRawUpdate task cannot report that it never launched — a sleeping/offline machine
produces no flag at all. This independent morning task (QuantDailyRawWatchdog, ~10:00 CST) reads the
daily-job heartbeat and, if the last QA success is OLDER than the last complete trading session
(CST), writes logs/qa_alert_<date>.flag and exits non-zero — surfacing the missed run.
"""
from __future__ import annotations

import json
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
    (LOGS_DIR / f"qa_alert_{_cst_date()}.flag").write_text(msg + "\n", encoding="utf-8")
    print(msg, file=sys.stderr)


def main() -> int:
    from data_infra.pipeline.update_daily_data import resolve_last_complete_session
    ref_dir = str(PROJECT_ROOT / "data" / "reference")
    try:
        expected = resolve_last_complete_session(ref_dir)
    except SystemExit as exc:  # calendar not future-aware / no session — itself alert-worthy
        _alert(f"watchdog: cannot resolve last complete session: {exc}")
        return 1

    last_success = None
    if HEARTBEAT.exists():
        try:
            last_success = str(json.loads(HEARTBEAT.read_text(encoding="utf-8")).get("last_success_cst", ""))[:8]
        except Exception:  # noqa: BLE001 — corrupt heartbeat -> treat as missing
            last_success = None

    if not last_success or last_success < expected:
        _alert(f"watchdog: daily job STALE - last QA success {last_success or 'NEVER'} < last complete "
               f"session {expected} (missed run?)")
        return 1
    print(f"watchdog OK: last QA success {last_success} covers last complete session {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
