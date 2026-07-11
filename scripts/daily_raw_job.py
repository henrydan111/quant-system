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


def _provider_floor(ref_dir: str, target: str) -> str:
    """The monthly-published provider boundary — the daily job maintains sessions AFTER it (the
    monthly bump owns everything through it). Falls back to a bounded lookback before target."""
    cal = PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt"
    if cal.exists():
        days = cal.read_text(encoding="utf-8").split()
        if days:
            return days[-1].replace("-", "")
    import pandas as pd
    opens = sorted(pd.read_parquet(Path(ref_dir) / "trade_cal.parquet")
                   .query("is_open == 1")["cal_date"].astype(str))
    opens = [d for d in opens if d <= target]
    return opens[-(MAX_SESSIONS_PER_RUN + 1)] if len(opens) > MAX_SESSIONS_PER_RUN else (opens[0] if opens else target)


def _run() -> int:
    from data_infra.pipeline.update_daily_data import DailyDataUpdater, resolve_last_complete_session
    from data_infra.pipeline.daily_ops import (advance_watermark, backlog_sessions, write_session_status)
    from data_infra.tushare_lock import raw_maintenance_lock

    logs = str(LOGS_DIR)
    ref_dir = str(PROJECT_ROOT / "data" / "reference")
    target = resolve_last_complete_session(ref_dir)  # SystemExit on a stale/absent calendar
    floor = _provider_floor(ref_dir, target)
    backlog = backlog_sessions(ref_dir, logs, target, floor, max_n=MAX_SESSIONS_PER_RUN)

    updater = DailyDataUpdater(config_path=str(PROJECT_ROOT / "config.yaml"))
    with raw_maintenance_lock():  # §6.1: exclusive with the monthly catch-up / any manual fetch
        for d in backlog:
            try:
                res = updater.update_for_date(d)
                ok = bool(res.get("is_trading_day") and res.get("market_ok") and not res.get("errors"))
                write_session_status(logs, d, ok, {"errors": res.get("errors", []),
                                                   "is_trading_day": res.get("is_trading_day")})
            except Exception as exc:  # noqa: BLE001 — one bad session must not abort the rest
                write_session_status(logs, d, False, {"error": str(exc)})

    qa_ok = subprocess.run([str(PY), str(PROJECT_ROOT / "scripts" / "run_daily_qa.py")]).returncode == 0
    watermark = advance_watermark(ref_dir, logs, target, floor)

    # heartbeat ONLY when the CONTIGUOUS watermark reached the target AND QA passed (GPT M1).
    if watermark >= target and qa_ok:
        _atomic_json(HEARTBEAT, {"completed_session": watermark, "at_cst": _cst().strftime("%Y%m%d_%H%M%S")})
        af = LOGS_DIR / f"daily_job_alert_{_cst().strftime('%Y%m%d')}.flag"
        if af.exists():
            af.unlink()
        print(f"daily job OK: watermark {watermark} == target, QA pass ({len(backlog)} sessions processed)")
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
