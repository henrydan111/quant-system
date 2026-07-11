# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 5-C: daily raw-job orchestrator
"""Phase 5-C daily raw-job orchestrator (GPT 5-C M1 + M3).

Backfills every INCOMPLETE open session (per the completion manifest, oldest-first, bounded per run)
under the raw-maintenance lock, runs QA, and advances a CONTIGUOUS completed-session watermark. The
heartbeat is bound to (watermark reached the target session AND QA passed) — a session with daily
OHLCV but a failed required endpoint is NOT complete, so the heartbeat can never jump past it. Every
selected session must be a real trading day with no required errors, else it is marked incomplete and
the run exits BACKLOGGED. A top-level boundary always writes daily_job_alert on any crash.

Raw-only by construction: it calls update_for_date, which never triggers a Qlib rebuild (D1/D2).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
LOGS_DIR = PROJECT_ROOT / "logs"
HEARTBEAT = LOGS_DIR / "daily_job_heartbeat.json"
PY = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
MAX_SESSIONS_PER_RUN = 10  # bound the backlog per run so a long outage can't blow the task time limit


def _cst() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:  # pragma: no cover
        return datetime.now()


def _atomic_json(path: Path, obj) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    tmp = path.parent / f"{path.name}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _alert(msg: str) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    (LOGS_DIR / f"daily_job_alert_{_cst().strftime('%Y%m%d')}.flag").write_text(msg + "\n", encoding="utf-8")
    print(msg, file=sys.stderr)


def _provider_floor() -> str:
    """The monthly-published provider boundary — the daily job maintains sessions AFTER it. FAIL
    CLOSED if the provider calendar is missing/empty (no bounded fallback that recreates a blind
    horizon — GPT M2/M3): a formal build boundary must be an attested value, not a guess."""
    cal = PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt"
    if not cal.exists():
        raise SystemExit("provider calendar (data/qlib_data/calendars/day.txt) missing — cannot "
                         "establish the daily-job floor; failing closed")
    days = cal.read_text(encoding="utf-8").split()
    if not days:
        raise SystemExit("provider calendar is EMPTY — failing closed")
    return days[-1].replace("-", "")


def _run() -> int:
    from data_infra.pipeline.update_daily_data import DailyDataUpdater, resolve_last_complete_session
    from data_infra.pipeline.daily_ops import (backlog_sessions, contiguous_watermark, write_session_status)
    from data_infra.tushare_lock import raw_maintenance_lock

    logs = str(LOGS_DIR)
    ref_dir = str(PROJECT_ROOT / "data" / "reference")
    floor = _provider_floor()  # fail-closed if the provider attestation is missing
    updater = DailyDataUpdater(config_path=str(PROJECT_ROOT / "config.yaml"))

    # ONE full-attempt barrier from calendar refresh through heartbeat: no other daily/monthly/manual
    # writer can interleave, and QA reads a consistent raw cut (GPT M3). The monthly bump holds the
    # same lock, so the two never overlap.
    with raw_maintenance_lock():
        # refresh the calendar FIRST so a stale stored calendar cannot abort resolution (GPT B2).
        updater.update_reference_data(_cst().strftime("%Y%m%d"))
        if getattr(updater, "_reference_error", None):
            _alert(f"calendar/reference refresh failed: {updater._reference_error}")
            return 2
        target = resolve_last_complete_session(ref_dir)  # SystemExit -> caught by main() boundary
        if floor > target:  # provider already at/ahead of the last complete session -> nothing to do
            print(f"daily job: provider floor {floor} >= target {target}; nothing to backfill")
            return 0
        backlog = backlog_sessions(ref_dir, logs, target, floor, max_n=MAX_SESSIONS_PER_RUN)
        for d in backlog:
            try:
                res = updater.update_for_date(d)
                ok = bool(res.get("is_trading_day") and res.get("market_ok") and not res.get("errors"))
                write_session_status(logs, d, ok, {"date": d, "errors": res.get("errors", []),
                                                   "is_trading_day": res.get("is_trading_day")})
            except Exception as exc:  # noqa: BLE001 — one bad session must not abort the rest
                write_session_status(logs, d, False, {"date": d, "error": str(exc)})

        qa_ok = subprocess.run([str(PY), str(PROJECT_ROOT / "scripts" / "run_daily_qa.py")]).returncode == 0
        watermark = contiguous_watermark(ref_dir, logs, target, floor)  # recomputed from floor

        # heartbeat ONLY when the contiguous watermark EXACTLY reaches the target AND QA passed.
        if watermark == target and qa_ok:
            _atomic_json(HEARTBEAT, {"completed_session": watermark, "at_cst": _cst().strftime("%Y%m%d_%H%M%S")})
            af = LOGS_DIR / f"daily_job_alert_{_cst().strftime('%Y%m%d')}.flag"
            if af.exists():
                af.unlink()
            print(f"daily job OK: watermark {watermark} == target, QA pass ({len(backlog)} sessions)")
            return 0
        _alert(f"daily job BACKLOGGED/FAILED: watermark={watermark} target={target} qa_ok={qa_ok} "
               f"backlog_this_run={backlog}")
        return 1


def main() -> int:
    try:
        return _run()
    except SystemExit as exc:  # stale/absent calendar etc.
        _alert(f"daily job aborted: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 — top-level boundary always alerts (GPT minor 1)
        _alert(f"daily job CRASHED: {exc!r}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
