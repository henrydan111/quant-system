"""Phase 5-C daily-maintenance ops (data_infra-level, no upward import):

- account_lock(): a cross-process Tushare-account lock. CLAUDE.md §6.1 forbids parallel fetchers
  against the account; this serializes the daily raw job, the monthly bump's catch-up, and any
  manual fetch (GPT 5-C M4). Steals a stale lock (crashed holder) after `stale` seconds.
- missing_open_sessions(): the bounded gap the daily job self-heals oldest-first, so a multi-session
  outage is not silently left for the monthly bump (GPT 5-C M3).
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager

import pandas as pd

_LOCK_NAME = ".tushare_account.lock"


@contextmanager
def account_lock(logs_dir: str, timeout: float = 1800.0, poll: float = 2.0, stale: float = 3600.0):
    os.makedirs(logs_dir, exist_ok=True)
    lock_path = os.path.join(logs_dir, _LOCK_NAME)
    start = time.time()
    fd = None
    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:  # a crashed holder leaves a stale lock — steal it after `stale` seconds
                if time.time() - os.path.getmtime(lock_path) > stale:
                    os.remove(lock_path)
                    continue
            except OSError:
                pass
            if time.time() - start > timeout:
                raise TimeoutError(f"tushare account lock held > {timeout}s at {lock_path}")
            time.sleep(poll)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        try:
            os.remove(lock_path)
        except OSError:
            pass


def missing_open_sessions(ref_dir: str, daily_root: str, upto: str, lookback_days: int = 15) -> list[str]:
    """Open trading days in the last `lookback_days` sessions through `upto` that have NO raw daily
    file, OLDEST first. The daily job backfills these so a multi-session outage self-heals."""
    cal = pd.read_parquet(os.path.join(ref_dir, "trade_cal.parquet"))
    opens = sorted(cal.loc[cal['is_open'] == 1, 'cal_date'].astype(str).tolist())
    window = [d for d in opens if d <= upto][-lookback_days:]
    return [d for d in window
            if not os.path.exists(os.path.join(daily_root, d[:4], f"daily_{d}.parquet"))]
