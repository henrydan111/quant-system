# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 5-C: daily raw-job orchestrator
"""Phase 5-C daily raw-job orchestrator (GPT M1 + M3).

Runs the raw-only daily update — GAP-BACKFILLING any recently-missed open sessions OLDEST-first so a
multi-session outage self-heals — then QA, and writes the daily-job HEARTBEAT only when BOTH the
update and QA succeed. A generic QA pass must not advance the heartbeat (that let the watchdog go
green after a failed update — GPT M1). Writes a `daily_job_alert_<date>.flag` on failure; the
`qa_alert` flag stays owned by QA. Raw-only by construction: it calls update_for_date, which never
triggers a Qlib rebuild (D1/D2).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
LOGS_DIR = PROJECT_ROOT / "logs"
HEARTBEAT = LOGS_DIR / "daily_job_heartbeat.json"
PY = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"


def _cst() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:  # pragma: no cover
        return datetime.now()


def _alert(msg: str) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    (LOGS_DIR / f"daily_job_alert_{_cst().strftime('%Y%m%d')}.flag").write_text(msg + "\n", encoding="utf-8")
    print(msg, file=sys.stderr)


def main() -> int:
    from data_infra.pipeline.update_daily_data import DailyDataUpdater, resolve_last_complete_session
    from data_infra.pipeline.daily_ops import account_lock, missing_open_sessions

    ref_dir = str(PROJECT_ROOT / "data" / "reference")
    daily_root = str(PROJECT_ROOT / "data" / "market" / "daily")
    try:
        target = resolve_last_complete_session(ref_dir)
    except SystemExit as exc:  # stale/absent calendar — alert-worthy
        _alert(f"orchestrator: cannot resolve last complete session: {exc}")
        return 2

    # bounded gap backfill oldest-first + the target session
    sessions = sorted(set(missing_open_sessions(ref_dir, daily_root, target)) | {target})
    updater = DailyDataUpdater(config_path=str(PROJECT_ROOT / "config.yaml"))
    errors: list[str] = []
    with account_lock(str(LOGS_DIR)):  # §6.1: serialize with the monthly bump / manual fetch
        for d in sessions:
            try:
                res = updater.update_for_date(d)  # raw-only — never triggers a Qlib rebuild
                if res.get("is_trading_day", True) and res.get("errors"):
                    errors.extend(f"{d}: {e}" for e in res["errors"])
            except Exception as exc:  # noqa: BLE001 — one bad session must not abort the rest
                errors.append(f"{d}: {exc}")

    qa = subprocess.run([str(PY), str(PROJECT_ROOT / "scripts" / "run_daily_qa.py")])
    qa_ok = qa.returncode == 0

    if not errors and qa_ok:
        LOGS_DIR.mkdir(exist_ok=True)
        HEARTBEAT.write_text(json.dumps(
            {"completed_session": target, "at_cst": _cst().strftime("%Y%m%d_%H%M%S")},
            ensure_ascii=False), encoding="utf-8")
        af = LOGS_DIR / f"daily_job_alert_{_cst().strftime('%Y%m%d')}.flag"
        if af.exists():
            af.unlink()
        print(f"daily job OK: sessions {sessions} updated + QA pass; heartbeat -> {target}")
        return 0

    _alert(f"daily job FAILED: update_errors={errors}; qa_ok={qa_ok} (heartbeat NOT advanced)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
