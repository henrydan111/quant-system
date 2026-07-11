"""Cross-process locks for Tushare-account safety + raw-layer maintenance exclusivity.

Uses `filelock` (a KERNEL-held lock: the OS releases it automatically when the holding process dies,
so there is NO age-based stealing — the previous O_EXCL+mtime scheme wrongly stole a live multi-hour
monthly catch-up's lock, GPT 5-C Blocker 1). A leaf module (no data_infra imports) so both the
fetcher and the pipeline can use it without a cycle.

- api_call_lock(): serializes EVERY sanctioned Tushare API call across processes (CLAUDE.md §6.1:
  never parallel fetchers against the account). Held per-call inside TushareFetcher._safe_api_call.
- raw_maintenance_lock(): process-exclusive raw-layer maintenance — the daily job, the monthly
  catch-up (multi-hour), and any manual raw fetch acquire it so their read-merge-write cannot race.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock

# project-root/logs/locks by default; QUANT_LOCK_DIR overrides it (tests, or a shared-volume deploy).
_DEFAULT_LOCK_DIR = Path(__file__).resolve().parents[2] / "logs" / "locks"
_HELD_ENV = "QUANT_RAW_MAINT_LOCK_HELD"  # set for subprocesses under a parent-owned maintenance barrier


def _lock_dir() -> Path:
    d = Path(os.environ.get("QUANT_LOCK_DIR", str(_DEFAULT_LOCK_DIR)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _filelock(name: str, timeout: float) -> FileLock:
    return FileLock(str(_lock_dir() / name), timeout=timeout)


@contextmanager
def api_call_lock(timeout: float = 1800.0):
    with _filelock("tushare_api.lock", timeout):
        yield


@contextmanager
def raw_maintenance_lock(timeout: float = 21600.0):  # 6h — a monthly catch-up can legitimately run hours
    """Process-exclusive raw-layer maintenance. If an ANCESTOR process already holds it (a parent-owned
    barrier signalled via QUANT_RAW_MAINT_LOCK_HELD), this is a NO-OP so a child catch-up subprocess
    does not deadlock re-acquiring the same cross-process lock (GPT 5-C Blocker 1 barrier)."""
    if os.environ.get(_HELD_ENV):
        yield
        return
    with _filelock("raw_maintenance.lock", timeout):
        os.environ[_HELD_ENV] = "1"  # inherited by subprocesses we spawn -> they don't re-acquire
        try:
            yield
        finally:
            os.environ.pop(_HELD_ENV, None)


# ── global cross-process rate spacing (a shared next-allowed timestamp, held under the API lock) ──
def _next_allowed_path() -> Path:
    return _lock_dir() / "tushare_next_allowed.txt"


def _wait_until_allowed() -> None:
    try:
        nxt = float(_next_allowed_path().read_text())
    except Exception:  # noqa: BLE001 — absent/corrupt -> no wait
        return
    delay = nxt - time.time()
    if delay > 0:
        time.sleep(min(delay, 120.0))  # cap so a poisoned value can't hang forever


def _set_next_allowed(delta: float) -> None:
    try:
        _next_allowed_path().write_text(str(time.time() + max(0.0, delta)))
    except Exception:  # noqa: BLE001
        pass


def _is_rate_limit(exc: Exception) -> bool:
    m = str(exc).lower()
    return any(k in m for k in ("daily request", "frequent", "limit", "每分钟", "每天"))


def spaced_call(fn, base_sleep: float, *args, rate_limit_backoff: float = 30.0, **kwargs):
    """Call `fn` under the cross-process account lock, enforcing a GLOBAL minimum spacing between calls
    (and a longer cooldown after a rate-limit error) via the shared next-allowed timestamp — so the
    account rate limit holds ACROSS processes, not just within one (GPT 5-C Major 1 + backoff minor)."""
    with api_call_lock():
        _wait_until_allowed()
        try:
            r = fn(*args, **kwargs)
        except Exception as exc:
            if _is_rate_limit(exc):
                _set_next_allowed(rate_limit_backoff)
            raise
        _set_next_allowed(base_sleep)
        return r
