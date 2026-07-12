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
DAILY_LOCK_TIMEOUT_SEC = 900  # 15min: fail-fast + retry, never block for hours behind a monthly build (m3)
DEFER_EXIT = 75  # EX_TEMPFAIL: lock contention -> RETRYABLE (nonzero so Task Scheduler RestartOnFailure fires)


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
        # RETRYABLE (m3): return a dedicated NONZERO code so Task Scheduler's RestartOnFailure retries in
        # ~30min (a monthly build finishes and releases the lock) instead of waiting a full day. Write a
        # structured deferral record (NOT an alert — this is expected contention, not a failure).
        _atomic_json(LOGS_DIR / "daily_job_deferred.json",
                     {"reason": "raw_maintenance_lock busy (monthly build?)",
                      "timeout_sec": DAILY_LOCK_TIMEOUT_SEC, "at_cst": _cst().strftime("%Y%m%d_%H%M%S")})
        print(f"daily job: raw-maintenance lock busy after {DAILY_LOCK_TIMEOUT_SEC}s (monthly build in "
              f"progress?) — DEFERRED (exit {DEFER_EXIT}, scheduler will retry)", file=sys.stderr)
        return DEFER_EXIT


def _run_locked(updater, ref_dir: str, logs: str) -> int:
    import uuid
    from data_infra.pipeline.update_daily_data import resolve_last_complete_session
    from data_infra.pipeline.daily_ops import (backlog_sessions, contiguous_watermark, manifest_set_digest,
                                               provider_floor, ProviderFloorError, start_attempt,
                                               write_session_status)

    # ONE full-attempt transaction (refresh -> attest floor -> backfill -> QA -> heartbeat) under the
    # held lock: no other writer interleaves and QA reads a consistent raw cut (GPT M3/M4). Refresh the
    # calendar FIRST so a stale stored calendar cannot abort resolution (B2); attest the floor INSIDE via
    # the SHARED helper (same attestation the watchdog uses — GPT REWORK-5 M2.4).
    try:
        floor = provider_floor(PROJECT_ROOT, ref_dir)
    except ProviderFloorError as exc:
        _alert(f"provider floor attestation failed: {exc}")
        return 2
    target = resolve_last_complete_session(ref_dir)
    if floor > target:  # provider calendar extends PAST the last real complete session -> poisoned
        _alert(f"provider floor {floor} is AHEAD of the last complete session {target} — the provider "
               f"calendar extends past reality (poisoned/misbuilt); failing closed")
        return 2

    # Open a NEW attempt + invalidate any prior success certificate BEFORE any mutation (GPT REWORK-5
    # M2): if this run later fails, no stale heartbeat can certify it. (floor==target is handled AFTER
    # this — a post-publish 'nothing to backfill' still supersedes the old attempt.)
    attempt_id = uuid.uuid4().hex
    start_attempt(logs, attempt_id, target)

    if floor == target:  # provider already current -> nothing to backfill; the watchdog greens on
        print(f"daily job: provider floor {floor} == last complete session; nothing to backfill")  # floor==expected
        af = LOGS_DIR / f"daily_job_alert_{_cst().strftime('%Y%m%d')}.flag"
        if af.exists():
            af.unlink()
        return 0

    updater.update_reference_data(_cst().strftime("%Y%m%d"))
    if getattr(updater, "_reference_error", None):
        _alert(f"calendar/reference refresh failed: {updater._reference_error}")
        return 2
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

    # Success certificate ONLY when watermark==target AND QA passed. Bound to THIS attempt_id + the
    # attested provider ids + floor + manifest-set digest, so the watchdog can prove the LATEST attempt
    # was QA-certified — a stale heartbeat (older attempt_id, deleted at start_attempt) cannot green a
    # later failed run (GPT REWORK-5 M2).
    if watermark == target and qa_ok:
        pb = json.loads((PROJECT_ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json")
                        .read_text(encoding="utf-8"))
        _atomic_json(HEARTBEAT, {"attempt_id": attempt_id, "completed_session": watermark, "floor": floor,
                                 "qa_ok": True, "manifest_digest": manifest_set_digest(ref_dir, logs, target, floor),
                                 "provider_build_id": pb.get("provider_build_id"),
                                 "calendar_policy_id": pb.get("calendar_policy_id"),
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
