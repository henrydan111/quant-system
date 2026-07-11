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
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock

# project-root/logs/locks by default; QUANT_LOCK_DIR overrides it (tests, or a shared-volume deploy).
_DEFAULT_LOCK_DIR = Path(__file__).resolve().parents[2] / "logs" / "locks"


def _filelock(name: str, timeout: float) -> FileLock:
    lock_dir = Path(os.environ.get("QUANT_LOCK_DIR", str(_DEFAULT_LOCK_DIR)))
    lock_dir.mkdir(parents=True, exist_ok=True)
    return FileLock(str(lock_dir / name), timeout=timeout)


@contextmanager
def api_call_lock(timeout: float = 1800.0):
    with _filelock("tushare_api.lock", timeout):
        yield


@contextmanager
def raw_maintenance_lock(timeout: float = 21600.0):  # 6h — a monthly catch-up can legitimately run hours
    with _filelock("raw_maintenance.lock", timeout):
        yield
