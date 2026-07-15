"""Cross-platform exclusive file lock for critical-section writes."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LockTimeoutError(TimeoutError):
    """Raised when a file lock cannot be acquired within the timeout."""


@contextmanager
def file_lock(lock_path: Path, timeout_seconds: float | None = 30.0) -> Iterator[None]:
    """Exclusive cross-process lock. ``timeout_seconds=None`` waits indefinitely —
    used by locks that must span a long computation (e.g. the A5 execution lock),
    where a second contender should WAIT for completion and then load the persisted
    result rather than time out (PR3 R6 Minor)."""
    lock_path = Path(lock_path).resolve()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    start = time.time()
    try:
        try:
            import portalocker  # type: ignore

            while True:
                try:
                    portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
                    break
                except portalocker.exceptions.LockException as exc:  # type: ignore[attr-defined]
                    if timeout_seconds is not None and time.time() - start >= timeout_seconds:
                        raise LockTimeoutError(f"Timed out waiting for lock: {lock_path}") from exc
                    time.sleep(0.05)
            yield
            portalocker.unlock(handle)
            return
        except ImportError:
            pass

        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if timeout_seconds is not None and time.time() - start >= timeout_seconds:
                        raise LockTimeoutError(f"Timed out waiting for lock: {lock_path}") from exc
                    time.sleep(0.05)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        if os.name == "posix":
            import fcntl

            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if timeout_seconds is not None and time.time() - start >= timeout_seconds:
                        raise LockTimeoutError(f"Timed out waiting for lock: {lock_path}") from exc
                    time.sleep(0.05)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return

        raise RuntimeError(f"Unsupported platform for file_lock: os.name={os.name}")
    finally:
        handle.close()
