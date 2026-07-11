"""Phase 5-C daily-maintenance ops: per-session COMPLETION MANIFESTS + a contiguous completed-session
WATERMARK (GPT 5-C M1/M3).

A session is "complete" only when every DECLARED-required endpoint succeeded — NOT merely when a
`daily_<date>.parquet` file exists (a session can have daily OHLCV but a failed suspend_d). Gap
discovery + the heartbeat therefore key off the manifest, and the watermark advances only over a
CONTIGUOUS run of complete sessions, so the heartbeat can never jump past an incomplete earlier
session. Backlog is discovered from the watermark (a persistent floor), not a blind sliding window
that would permanently miss sessions older than the last N.

(The cross-process Tushare-account / raw-maintenance locks live in data_infra.tushare_lock.)
"""
from __future__ import annotations

import json
import os

import pandas as pd

STATUS_SUBDIR = "session_status"
WATERMARK_FILE = "daily_watermark.json"


def _status_dir(logs_dir: str) -> str:
    d = os.path.join(logs_dir, STATUS_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def _atomic_json(path: str, obj) -> None:
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    os.replace(tmp, path)


def write_session_status(logs_dir: str, date: str, required_ok: bool, detail=None) -> None:
    """Atomic per-session manifest. required_ok = every declared-required endpoint for `date` OK."""
    _atomic_json(os.path.join(_status_dir(logs_dir), f"{date}.json"),
                 {"date": date, "required_ok": bool(required_ok), "detail": detail or {}})


def session_required_ok(logs_dir: str, date: str) -> bool:
    path = os.path.join(_status_dir(logs_dir), f"{date}.json")
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as fh:
            return bool(json.load(fh).get("required_ok"))
    except Exception:  # noqa: BLE001 — corrupt manifest -> not complete
        return False


def _open_days(ref_dir: str, upto: str) -> list[str]:
    cal = pd.read_parquet(os.path.join(ref_dir, "trade_cal.parquet"))
    return sorted(d for d in cal.loc[cal['is_open'] == 1, 'cal_date'].astype(str) if d <= upto)


def load_watermark(logs_dir: str) -> str | None:
    p = os.path.join(logs_dir, WATERMARK_FILE)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            return str(json.load(fh).get("watermark") or "") or None
    except Exception:  # noqa: BLE001
        return None


def save_watermark(logs_dir: str, date: str) -> None:
    _atomic_json(os.path.join(logs_dir, WATERMARK_FILE), {"watermark": date})


def backlog_sessions(ref_dir: str, logs_dir: str, target: str, floor: str, max_n: int | None = None) -> list[str]:
    """Open sessions in (max(floor, watermark), target] whose manifest is NOT required_ok, OLDEST
    first. `floor` = the monthly-published provider boundary (below it the monthly bump is
    responsible). Optionally capped at max_n per run so a large backlog doesn't blow the task's time
    budget — the remainder is picked up on the next run."""
    wm = load_watermark(logs_dir) or floor
    start = max(floor, wm)
    todo = [d for d in _open_days(ref_dir, target) if d > start and not session_required_ok(logs_dir, d)]
    return todo[:max_n] if max_n else todo


def advance_watermark(ref_dir: str, logs_dir: str, target: str, floor: str) -> str:
    """Advance the persistent watermark to the LATEST session W such that every open session in
    (watermark, W] is required_ok (CONTIGUOUS — the first incomplete session stops it). Returns W."""
    wm = load_watermark(logs_dir) or floor
    new = wm
    for d in _open_days(ref_dir, target):
        if d <= wm:
            continue
        if session_required_ok(logs_dir, d):
            new = d
        else:
            break
    if new != wm and new > floor:
        save_watermark(logs_dir, new)
    return new
