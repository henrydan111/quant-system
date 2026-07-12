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
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    os.replace(tmp, path)


def write_session_status(logs_dir: str, date: str, required_ok: bool, detail=None) -> None:
    """Atomic per-session manifest. required_ok = every declared-required endpoint for `date` OK.
    STRICT: required_ok must be a real bool (a caller passing the string "false" — truthy — would else
    be stored as JSON true and the strict reader would accept it, GPT minor 2). `detail` should carry
    per-endpoint evidence (row counts / datasets), not just a boolean, so a manifest is auditable."""
    if not isinstance(required_ok, bool):
        raise TypeError(f"required_ok must be bool, got {type(required_ok).__name__} {required_ok!r}")
    _atomic_json(os.path.join(_status_dir(logs_dir), f"{date}.json"),
                 {"date": date, "required_ok": required_ok, "detail": detail or {}})


def session_required_ok(logs_dir: str, date: str) -> bool:
    """Strict: required_ok must be the JSON boolean True (a string "false" is truthy — GPT M2) AND the
    embedded date must match the filename (a mislabelled manifest is not evidence)."""
    path = os.path.join(_status_dir(logs_dir), f"{date}.json")
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except Exception:  # noqa: BLE001 — corrupt manifest -> not complete
        return False
    return obj.get("required_ok") is True and str(obj.get("date")) == date


def _open_days(ref_dir: str, upto: str) -> list[str]:
    # DEDUP via set: if trade_cal ever carries >1 exchange (SSE+SZSE), the same open date appears twice
    # and every consumer double-counts — a duplicated tail makes `cands[-2]` still-today in the pre-close
    # selector (GPT B2). trade_cal is enforced SSE-only upstream, but dedup here defensively.
    cal = pd.read_parquet(os.path.join(ref_dir, "trade_cal.parquet"))
    return sorted({d for d in cal.loc[cal['is_open'] == 1, 'cal_date'].astype(str) if d <= upto})


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
    """Open sessions in the WHOLE (floor, target] interval whose manifest is NOT required_ok, OLDEST
    first — scanned from the provider floor, NOT only after the cached watermark (a bad/rebased
    watermark must not hide an earlier incomplete session — GPT M2/M3). `floor` = the monthly-published
    provider boundary; below it the monthly bump is responsible. Capped at max_n per run."""
    todo = [d for d in _open_days(ref_dir, target) if d > floor and not session_required_ok(logs_dir, d)]
    return todo[:max_n] if max_n else todo


def compute_contiguous_watermark(ref_dir: str, logs_dir: str, target: str, floor: str) -> str:
    """PURE (no persistence): recompute the watermark FROM THE FLOOR — the LATEST session W such that
    every open session in (floor, W] is required_ok (the first incomplete stops it). Never trusts a
    cached value, so a poisoned future watermark can't false-green and it rebases when the provider
    floor advances. A MONITOR (the watchdog) must use this and NOT mutate progress state (GPT M2)."""
    new = floor
    for d in _open_days(ref_dir, target):
        if d <= floor:
            continue
        if session_required_ok(logs_dir, d):
            new = d
        else:
            break
    return new


def contiguous_watermark(ref_dir: str, logs_dir: str, target: str, floor: str) -> str:
    """The WRITER path (orchestrator): compute + PERSIST the contiguous watermark. Returns W."""
    new = compute_contiguous_watermark(ref_dir, logs_dir, target, floor)
    save_watermark(logs_dir, new)
    return new


def manifest_set_digest(ref_dir: str, logs_dir: str, target: str, floor: str) -> str:
    """A digest over the (date, required_ok) completeness set for every open session in (floor, target].
    Binds a heartbeat to the EXACT manifest set it certified, so a stale heartbeat can't green a later
    run whose completeness set differs (GPT M2)."""
    import hashlib
    h = hashlib.sha256()
    for d in _open_days(ref_dir, target):
        if d <= floor:
            continue
        h.update(f"{d}:{session_required_ok(logs_dir, d)}\n".encode())
    return h.hexdigest()[:16]


# retained name for callers/tests; recompute-from-floor is the only supported semantics now.
advance_watermark = contiguous_watermark
