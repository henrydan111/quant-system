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
    daily_root = PROJECT_ROOT / "data" / "market" / "daily"
    try:
        expected = resolve_last_complete_session(ref_dir)
    except (SystemExit, Exception) as exc:  # noqa: BLE001 — a missing/corrupt calendar is alert-worthy
        _alert(f"watchdog: cannot resolve last complete session: {exc}")
        return 1

    # the heartbeat's completed_session is bound to a SUCCESSFUL raw update + QA (orchestrator M1).
    completed = None
    if HEARTBEAT.exists():
        try:
            completed = str(json.loads(HEARTBEAT.read_text(encoding="utf-8")).get("completed_session", ""))[:8]
        except Exception:  # noqa: BLE001 — corrupt heartbeat -> treat as missing
            completed = None
    # validate: a plausible 8-digit date, not in the future, and a real raw daily file exists for it
    valid = bool(completed) and completed.isdigit() and len(completed) == 8 and completed <= expected \
        and (daily_root / completed[:4] / f"daily_{completed}.parquet").exists()

    if not valid or completed < expected:
        _alert(f"watchdog: daily job STALE - last completed session {completed or 'NEVER'} vs expected "
               f"{expected} (missed/failed run?)")
        return 1
    print(f"watchdog OK: completed session {completed} covers last complete session {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
