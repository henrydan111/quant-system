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

LOCK IDENTITIES (GPT REWORK-6 Blocker 1 — a checkout-relative dir split the namespace per clone/
worktree while both talk to the SAME Tushare account / raw store):
- API lock: MACHINE-GLOBAL, at a fixed well-known literal path independent of the checkout — every
  clone/worktree on this machine serializes against the same single Tushare account (§6.1).
- Raw-maintenance lock: COLOCATED with the canonical resolved data store (``<data_root>/.locks``,
  data_root from the checkout's config.yaml) — every writer of the SAME store shares the lock; a
  different store is a different (correctly independent) lock.
Both paths are COMPUTED FRESH on every acquisition by module-level functions; there is no mutable
module path variable as a sanctioned override. Tests isolate by monkeypatching the path FUNCTIONS
(_api_lock_dir/_raw_lock_dir) — an explicit test seam, not a production knob.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout  # noqa: F401 — Timeout re-exported for callers' soft-skip

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _api_lock_dir() -> Path:
    """Machine-global fixed literal location (NOT checkout-relative, NOT env-derived): the Tushare
    account is machine-wide, so its serialization must be too. Single-account setup — if a second
    account is ever added, key the lock file name by an account hash."""
    if sys.platform == "win32":
        d = Path("C:/ProgramData/quant_system_locks")
    else:
        d = Path("/var/tmp/quant_system_locks")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve_data_root() -> Path:
    """The canonical raw data store this checkout operates on (config.yaml data.data_root, resolved
    against the project root when relative). Falls back to <project_root>/data — same default the
    pipeline uses — if config is unreadable."""
    try:
        import yaml
        with open(_PROJECT_ROOT / "config.yaml", encoding="utf-8") as fh:
            root = str(yaml.safe_load(fh)["data"]["data_root"])
        p = Path(root)
        return (p if p.is_absolute() else (_PROJECT_ROOT / p)).resolve()
    except Exception:  # noqa: BLE001 — missing/odd config -> the pipeline default
        return (_PROJECT_ROOT / "data").resolve()


def _raw_lock_dir() -> Path:
    """Colocated with the resolved data store so every writer of the SAME store — from any clone or
    worktree — contends on the SAME lock (a checkout-relative logs/ dir gave each worktree its own
    namespace over one shared store)."""
    d = _resolve_data_root() / ".locks"
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def api_call_lock(timeout: float = 1800.0):
    with FileLock(str(_api_lock_dir() / "tushare_api.lock"), timeout=timeout):
        yield


@contextmanager
def raw_maintenance_lock(timeout: float = 21600.0):  # 6h default — a monthly catch-up can run hours
    """Process-exclusive raw-layer maintenance, held on the REAL kernel lock (no env barrier). Pass a
    SHORT timeout in an unattended job (the daily raw job) so it fails fast + retries instead of
    blocking behind a multi-hour monthly build until its own task time-limit kills it (GPT m3); on
    timeout FileLock raises `Timeout` (re-exported above)."""
    with FileLock(str(_raw_lock_dir() / "raw_maintenance.lock"), timeout=timeout):
        yield


# ── global cross-process rate spacing (a shared next-allowed timestamp, held under the API lock) ──
def _next_allowed_path() -> Path:
    # lives with the API lock: the spacing is an ACCOUNT property, so it must be machine-global too.
    return _api_lock_dir() / "tushare_next_allowed.txt"


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
        d = _api_lock_dir()
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


# §6.1 floor, enforced CENTRALLY at the account chokepoint (GPT recovery-review B3: a dataclass
# metadata check protects nothing — four drivers constructed their own base_sleep=1.0 fetchers and the
# lock serialized calls at the CALLER's delay). Every spaced_call floors its spacing here; a caller
# cannot lower it. There is no env/test escape — tests pay the 1.5s where they exercise real spacing.
MIN_BASE_SLEEP = 1.5


def spaced_call(fn, base_sleep: float, *args, rate_limit_backoff: float = 30.0, **kwargs):
    """Call `fn` under the cross-process account lock, enforcing a GLOBAL minimum spacing between calls
    (and a longer cooldown after a rate-limit error). Spacing is FAIL-CLOSED (GPT minor 1): the shared
    next-allowed timestamp is an optimization; whenever it can't be read or written, the spacing is
    enforced in-band by sleeping WHILE HOLDING api_call_lock (which serializes callers), so the account
    rate limit can never silently drop to zero. base_sleep is FLOORED to MIN_BASE_SLEEP centrally —
    callers cannot reduce the account-wide spacing below §6.1 (GPT recovery B3)."""
    base_sleep = max(base_sleep, MIN_BASE_SLEEP)
    with api_call_lock():
        nxt, ok = _read_next_allowed()
        if not ok:
            time.sleep(max(0.0, base_sleep))  # corrupt state -> conservative in-band spacing
        elif nxt is not None:
            delay = nxt - time.time()
            if delay > 0:
                time.sleep(min(delay, 120.0))  # cap so a poisoned value can't hang forever
        # cooldown is recorded after EVERY attempted call — success, rate-limit, AND any other
        # exception (a timeout/parse error still consumed an account request; without this a failed
        # call let the next process fire immediately — GPT REWORK-6 M6). Rate-limit gets the longer
        # backoff; persist failure -> enforce IN-BAND by sleeping while still holding the API lock.
        delta = max(0.0, base_sleep)
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if _is_rate_limit(exc):
                delta = max(delta, rate_limit_backoff)
            raise
        finally:
            if not _set_next_allowed(delta):
                time.sleep(min(delta, 120.0))
