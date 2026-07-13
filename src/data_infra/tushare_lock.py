"""Cross-process locks for Tushare-account safety + raw-layer maintenance exclusivity.

Uses `filelock` (a KERNEL-held lock: the OS releases it automatically when the holding process dies,
so there is NO age-based stealing — the previous O_EXCL+mtime scheme wrongly stole a live multi-hour
monthly catch-up's lock, GPT 5-C Blocker 1). A leaf module (no data_infra imports) so both the
fetcher and the pipeline can use it without a cycle.

- api_call_lock(): serializes EVERY sanctioned Tushare API call across processes (CLAUDE.md §6.1:
  never parallel fetchers against the account). Held per-call inside TushareFetcher._safe_api_call.
- raw_maintenance_lock(): process-exclusive raw-layer maintenance — the daily job, the monthly
  catch-up (multi-hour), and any manual raw fetch acquire it so their read-merge-write cannot race.

There is NO env-boolean "already held" barrier (the GPT 5-C REWORK-4 removed it): a boolean env var
is not tied to the process holding the kernel lock, so (a) any process could forge it and enter raw
maintenance while a real holder is active, and (b) after a parent that set it dies, an inheriting
ORPHAN child keeps running inside a no-op "lock" while a new sibling acquires the released kernel lock
— two raw writers overlap, defeating the very crash-safety FileLock provides. Every process that needs
exclusivity acquires the REAL kernel lock. Callers that would otherwise nest (the monthly bump around
its catch-up subprocesses) are restructured so the parent does NOT hold the lock across a child that
re-acquires it (see scripts/monthly_calendar_bump.py).
"""
from __future__ import annotations

import math
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout  # noqa: F401 — Timeout re-exported for callers' soft-skip

# ONE immutable lock identity for this REPOSITORY (all worktrees), NOT overridable by an ambient
# environment variable. A per-process `QUANT_LOCK_DIR` override previously let a second process
# select a DIFFERENT namespace and acquire immediately while a real holder was live (GPT REWORK-5
# Blocker 1). Phase 5-B re-review P0: deriving the path from THIS source file's checkout is ALSO a
# forgeable-by-accident namespace — two git WORKTREES of the same repo resolved different lock dirs
# and could publish/fetch concurrently against the same shared store. The identity is therefore
# anchored to the GIT COMMON DIRECTORY's parent (identical for every worktree of a repo; equal to
# the checkout root for a plain clone, so the production daily job's lock path is unchanged).
# Degraded fallback (git unavailable): the source checkout root, with a loud warning — never env.
# Tests INJECT isolation by monkeypatching the module attribute in-process, never via env.
_SOURCE_ROOT = Path(__file__).resolve().parents[2]


def _resolve_lock_root(source_root: Path) -> Path:
    import logging
    import subprocess
    try:
        # git emits UTF-8 bytes; text=True would decode with the locale codepage (cp936 on
        # this host) and MANGLE non-ASCII path components (the real repo root contains
        # Chinese characters) — decode explicitly.
        out = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(source_root), stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        common = Path(out)
        if not common.is_absolute():
            common = (source_root / common).resolve()
        return common.parent
    except Exception:  # noqa: BLE001 — degraded per-checkout namespace, loudly
        logging.getLogger(__name__).warning(
            "git common-dir resolution failed under %s — lock namespace degrades to this "
            "checkout only (cross-worktree publishers would NOT exclude each other).",
            source_root,
        )
        return source_root


_LOCK_DIR = _resolve_lock_root(_SOURCE_ROOT) / "logs" / "locks"


def _lock_dir() -> Path:
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    return _LOCK_DIR


def _filelock(name: str, timeout: float) -> FileLock:
    return FileLock(str(_lock_dir() / name), timeout=timeout)


@contextmanager
def api_call_lock(timeout: float = 1800.0):
    with _filelock("tushare_api.lock", timeout):
        yield


@contextmanager
def raw_maintenance_lock(timeout: float = 21600.0):  # 6h default — a monthly catch-up can run hours
    """Process-exclusive raw-layer maintenance, held on the REAL kernel lock (no env barrier). Pass a
    SHORT timeout in an unattended job (the daily raw job) so it fails fast + retries instead of
    blocking behind a multi-hour monthly build until its own task time-limit kills it (GPT m3); on
    timeout FileLock raises `Timeout` (re-exported above)."""
    with _filelock("raw_maintenance.lock", timeout):
        yield


@contextmanager
def provider_publish_lock(timeout: float = 7200.0):
    """Process-exclusive LIVE-provider publish/swap + manifest writes (Phase 5-B B3; GPT
    re-review Blocker 7 made this a GLOBAL publish lock, not a driver-private one).

    Held at the COMMON CHOKEPOINTS — ``StagedQlibBackendBuilder.publish()`` and the
    ``provider_build.json`` emitters in ``provider_manifest`` acquire it themselves — so ANY
    sanctioned publisher/manifest writer excludes any other, whichever entrypoint invoked it.
    The monthly transaction additionally holds it across its whole verify->swap->rebind scope.

    REENTRANT within a process/thread: the underlying ``FileLock`` is a per-path SINGLETON
    (``is_singleton=True``; verified on filelock 3.25.2 — same instance, counted acquire), so
    the transaction holding the lock can call ``publish()`` which re-acquires without
    deadlocking, while a second process still blocks. LOCK ORDER: any holder that also needs
    ``raw_maintenance_lock`` acquires raw FIRST, then this; publish-lock-only holders (the
    builder/emitters) never take the raw lock afterwards — no reverse-order path exists."""
    lock = FileLock(str(_lock_dir() / "provider_publish.lock"), is_singleton=True)
    lock.acquire(timeout=timeout)
    try:
        yield
    finally:
        lock.release()


# ── global cross-process rate spacing (a shared next-allowed timestamp, held under the API lock) ──
def _next_allowed_path() -> Path:
    return _lock_dir() / "tushare_next_allowed.txt"


def _read_next_allowed() -> tuple[float | None, bool]:
    """(value, ok). ABSENT -> (None, True): legitimately the first call, no wait. EXISTS-but-unreadable
    OR a non-finite / out-of-range value -> (None, False): the caller must be CONSERVATIVE (fail closed),
    not skip spacing. A state file containing `nan` parses via float() but makes `delay>0` False and lets
    the call fire immediately — so require math.isfinite and a sane timestamp window (GPT minor 1)."""
    p = _next_allowed_path()
    if not p.exists():
        return None, True
    try:
        v = float(p.read_text())
    except Exception:  # noqa: BLE001 — corrupt/locked -> unreadable, force conservative spacing
        return None, False
    now = time.time()
    if not math.isfinite(v) or v < 0 or v > now + 86400:  # NaN/inf/negative/absurd-future -> conservative
        return None, False
    return v, True


def _set_next_allowed(delta: float) -> bool:
    """Record the next-allowed timestamp ATOMICALLY (temp + replace). Returns False if it could not be
    persisted, so the caller enforces the spacing IN-BAND (sleep while holding the API lock) rather than
    silently dropping it (GPT minor 1)."""
    try:
        d = _lock_dir()
        fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".next_allowed.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(str(time.time() + max(0.0, delta)))
            os.replace(tmp, str(_next_allowed_path()))
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return True
    except Exception:  # noqa: BLE001
        return False


def _is_rate_limit(exc: Exception) -> bool:
    m = str(exc).lower()
    return any(k in m for k in ("daily request", "frequent", "limit", "每分钟", "每天"))


def spaced_call(fn, base_sleep: float, *args, rate_limit_backoff: float = 30.0, **kwargs):
    """Call `fn` under the cross-process account lock, enforcing a GLOBAL minimum spacing between calls
    (and a longer cooldown after a rate-limit error). Spacing is FAIL-CLOSED (GPT minor 1): the shared
    next-allowed timestamp is an optimization; whenever it can't be read or written, the spacing is
    enforced in-band by sleeping WHILE HOLDING api_call_lock (which serializes callers), so the account
    rate limit can never silently drop to zero."""
    with api_call_lock():
        nxt, ok = _read_next_allowed()
        if not ok:
            time.sleep(max(0.0, base_sleep))  # corrupt state -> conservative in-band spacing
        elif nxt is not None:
            delay = nxt - time.time()
            if delay > 0:
                time.sleep(min(delay, 120.0))  # cap so a poisoned value can't hang forever
        try:
            r = fn(*args, **kwargs)
        except Exception as exc:
            if _is_rate_limit(exc) and not _set_next_allowed(rate_limit_backoff):
                time.sleep(rate_limit_backoff)  # fail-closed cooldown when it can't be persisted
            raise
        if not _set_next_allowed(base_sleep):
            time.sleep(max(0.0, base_sleep))  # can't persist -> hold the lock so the next caller waits
        return r
