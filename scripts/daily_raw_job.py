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
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
LOGS_DIR = PROJECT_ROOT / "logs"
HEARTBEAT = LOGS_DIR / "daily_job_heartbeat.json"
PY = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
MAX_SESSIONS_PER_RUN = 10  # bound the backlog per run so a long outage can't blow the task time limit
DAILY_LOCK_TIMEOUT_SEC = 900  # 15min: fail-fast + retry, never block for hours behind a monthly build (m3)


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


def _provider_floor(ref_dir: str) -> str:
    """The monthly-published provider boundary — ATTESTED, not guessed (GPT M4). FAIL CLOSED unless
    day.txt is present, non-empty, syntactically valid, sorted ascending, its tail EQUALS the attested
    provider_build.json `calendar_end_date`, AND that tail is a real open SSE session in trade_cal. A
    poisoned/future/unsorted calendar would otherwise let the job return SUCCESS having checked nothing
    (a future floor > target short-circuits the run)."""
    cal = PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt"
    if not cal.exists():
        raise SystemExit("provider calendar (data/qlib_data/calendars/day.txt) missing — failing closed")
    days = [d.replace("-", "").strip() for d in cal.read_text(encoding="utf-8").split()]
    if not days:
        raise SystemExit("provider calendar is EMPTY — failing closed")
    if not all(re.fullmatch(r"\d{8}", d) for d in days):
        raise SystemExit("provider calendar has malformed (non-8-digit) dates — failing closed")
    if days != sorted(days):
        raise SystemExit("provider calendar is not sorted ascending — failing closed")
    floor = days[-1]
    manifest = PROJECT_ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json"
    if not manifest.exists():
        raise SystemExit("provider_build.json missing — cannot attest the floor; failing closed")
    attested = str(json.loads(manifest.read_text(encoding="utf-8"))
                   .get("provider", {}).get("calendar_end_date", "")).replace("-", "").strip()
    if attested != floor:
        raise SystemExit(f"provider calendar tail {floor} != attested calendar_end_date {attested} "
                         f"(provider_build.json) — unattested/poisoned floor; failing closed")
    tc = pd.read_parquet(os.path.join(ref_dir, "trade_cal.parquet"))
    opens = set(tc.loc[tc["is_open"] == 1, "cal_date"].astype(str).str.replace("-", "", regex=False))
    if floor not in opens:
        raise SystemExit(f"provider floor {floor} is not an open trading session in trade_cal — failing closed")
    return floor


def _run() -> int:
    from data_infra.pipeline.update_daily_data import DailyDataUpdater
    from data_infra.tushare_lock import raw_maintenance_lock, Timeout

    updater = DailyDataUpdater(config_path=str(PROJECT_ROOT / "config.yaml"))
    ref_dir = str(PROJECT_ROOT / "data" / "reference")
    # SHORT lock timeout (m3): an unattended job FAILS FAST + retries instead of blocking for hours
    # behind a multi-hour monthly build until its own 4h task time-limit kills it silently. On
    # contention it soft-skips (return 0); the watermark stays put and the watchdog is the backstop.
    try:
        with raw_maintenance_lock(timeout=DAILY_LOCK_TIMEOUT_SEC):
            return _run_locked(updater, ref_dir, str(LOGS_DIR))
    except Timeout:
        print(f"daily job: raw-maintenance lock busy after {DAILY_LOCK_TIMEOUT_SEC}s (monthly build in "
              f"progress?) — soft-skipping this run; next run retries", file=sys.stderr)
        return 0


def _run_locked(updater, ref_dir: str, logs: str) -> int:
    from data_infra.pipeline.update_daily_data import resolve_last_complete_session
    from data_infra.pipeline.daily_ops import (backlog_sessions, contiguous_watermark,
                                               manifest_set_digest, write_session_status)

    # ONE full-attempt transaction (refresh -> attest floor -> backfill -> QA -> heartbeat) under the
    # held lock: no other writer interleaves and QA reads a consistent raw cut (GPT M3/M4). Refresh the
    # calendar FIRST so a stale stored calendar cannot abort resolution (B2); attest the floor INSIDE.
    updater.update_reference_data(_cst().strftime("%Y%m%d"))
    if getattr(updater, "_reference_error", None):
        _alert(f"calendar/reference refresh failed: {updater._reference_error}")
        return 2
    floor = _provider_floor(ref_dir)  # attested; SystemExit -> caught by main() boundary
    target = resolve_last_complete_session(ref_dir)
    if floor > target:  # provider calendar extends PAST the last real complete session -> poisoned
        _alert(f"provider floor {floor} is AHEAD of the last complete session {target} — the provider "
               f"calendar extends past reality (poisoned/misbuilt); failing closed")
        return 2
    if floor == target:  # provider already current -> nothing to backfill (legit)
        print(f"daily job: provider floor {floor} == last complete session; nothing to backfill")
        return 0
    backlog = backlog_sessions(ref_dir, logs, target, floor, max_n=MAX_SESSIONS_PER_RUN)
    for d in backlog:
        try:
            res = updater.update_for_date(d)
            ok = bool(res.get("is_trading_day") and res.get("market_ok") and not res.get("errors"))
            write_session_status(logs, d, ok, {"date": d, "errors": res.get("errors", []),
                                               "is_trading_day": res.get("is_trading_day"),
                                               "touched": len(res.get("touched_symbols", []) or []),
                                               "datasets": sorted(res.get("affected_datasets", []) or [])})
        except Exception as exc:  # noqa: BLE001 — one bad session must not abort the rest
            write_session_status(logs, d, False, {"date": d, "error": str(exc)})

    qa_ok = subprocess.run([str(PY), str(PROJECT_ROOT / "scripts" / "run_daily_qa.py")]).returncode == 0
    watermark = contiguous_watermark(ref_dir, logs, target, floor)  # recomputed from floor + persisted

    # heartbeat ONLY when the contiguous watermark EXACTLY reaches the target AND QA passed. It is
    # QA-BOUND (qa_ok) + carries the floor + the manifest-set digest, so the watchdog can prove THIS
    # target/floor's completeness set was QA-certified — a bare complete-manifest set is NOT enough
    # (QA can fail while raw+manifests succeed; the watchdog must not green that — GPT M2).
    if watermark == target and qa_ok:
        _atomic_json(HEARTBEAT, {"completed_session": watermark, "floor": floor, "qa_ok": True,
                                 "manifest_digest": manifest_set_digest(ref_dir, logs, target, floor),
                                 "at_cst": _cst().strftime("%Y%m%d_%H%M%S")})
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
