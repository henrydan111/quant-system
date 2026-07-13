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


class LockIdentityError(RuntimeError):
    """The shared-store lock identity could not be resolved — data-root-guarding locks
    REFUSE instead of degrading to a per-checkout namespace (GPT re-review #3 P0: two
    independent clones configured onto ONE data root must share one lock; when the
    identity is unknowable the safe action is to not mutate the store at all)."""


def _resolve_account_lock_dir(source_root: Path) -> Path:
    """Lock directory for the ACCOUNT-level lock (api_call_lock + rate-spacing state):
    a stable PER-USER directory keyed by an irreversible fingerprint of the Tushare
    token (GPT re-review #4 Major: repo/checkout-anchored namespaces let two independent
    clones on one machine call the SAME account concurrently). Token resolution: the
    TUSHARE_TOKEN env var, else the checkout's .env file; no token resolves to the
    conservative shared 'no_token' namespace (all no-token processes serialize)."""
    import hashlib
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        env_file = source_root / ".env"
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("TUSHARE_TOKEN=") and not line.startswith("#"):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        except OSError:
            token = ""
    fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if token else "no_token"
    return Path.home() / ".quant_tushare_locks" / fingerprint


def _resolve_data_lock_dir(source_root: Path) -> Path:
    """Lock directory for locks that guard the SHARED DATA STORE (raw maintenance +
    provider publish): derived from the CANONICAL RESOLVED data root in config.yaml, and
    physically located INSIDE it (``<data_root>/.locks``) — so any checkout (worktree,
    independent clone, moved copy) configured onto the same store resolves the same lock
    files (GPT re-review #3 P0: git-common-dir only unifies worktrees of one repo; two
    clones sharing a data root still got two namespaces). FAIL-CLOSED: an unreadable
    config / unresolvable data root raises :class:`LockIdentityError` — a store-mutating
    caller must refuse, never proceed under a private lock namespace."""
    try:
        import yaml
        with open(source_root / "config.yaml", "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        raw = ((cfg.get("storage") or {}).get("data_root"))
        if not raw or not str(raw).strip():
            raise LockIdentityError(
                f"config.yaml under {source_root} declares no storage.data_root — cannot "
                "derive the shared-store lock identity; refusing (fail closed)."
            )
        root = Path(str(raw))
        if not root.is_absolute():
            root = (source_root / root)
        return root.resolve() / ".locks"
    except LockIdentityError:
        raise
    except Exception as exc:  # noqa: BLE001 — unreadable config = unknowable identity
        raise LockIdentityError(
            f"cannot resolve the shared data root from {source_root / 'config.yaml'}: {exc} "
            "— store-mutating locks refuse (fail closed)."
        ) from exc


# Resolved lazily (see the _resolve_* functions). Tests inject isolation by assigning
# these module attributes directly (a Path), never via env.
_ACCOUNT_LOCK_DIR = None
_DATA_LOCK_DIR = None


def _account_lock_dir() -> Path:
    global _ACCOUNT_LOCK_DIR
    if _ACCOUNT_LOCK_DIR is None:
        _ACCOUNT_LOCK_DIR = _resolve_account_lock_dir(_SOURCE_ROOT)
    d = Path(_ACCOUNT_LOCK_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _data_lock_dir() -> Path:
    global _DATA_LOCK_DIR
    if _DATA_LOCK_DIR is None:
        _DATA_LOCK_DIR = _resolve_data_lock_dir(_SOURCE_ROOT)
    d = Path(_DATA_LOCK_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve_provider_lock_path(source_root: Path, qlib_dir=None) -> Path:
    """Lock FILE for the provider-publish lock, keyed by the CANONICAL LIVE PROVIDER
    directory itself (GPT re-review #4 P0: config permits storage.qlib_data_dir to live
    apart from storage.data_root — keying off the raw root gave two checkouts targeting
    ONE provider two different locks). The lock file sits ADJACENT to the provider
    (never inside it — the tree is what gets swapped), named after the provider dir.
    ``qlib_dir`` overrides config resolution (the builder passes the exact tree it
    swaps); an unresolvable identity raises :class:`LockIdentityError`."""
    if qlib_dir is None:
        try:
            import yaml
            with open(source_root / "config.yaml", "r", encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
            raw = ((cfg.get("storage") or {}).get("qlib_data_dir"))
            if not raw or not str(raw).strip():
                raise LockIdentityError(
                    f"config.yaml under {source_root} declares no storage.qlib_data_dir — "
                    "cannot derive the provider lock identity; refusing (fail closed)."
                )
            qlib_dir = Path(str(raw))
            if not qlib_dir.is_absolute():
                qlib_dir = source_root / qlib_dir
        except LockIdentityError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LockIdentityError(
                f"cannot resolve storage.qlib_data_dir from {source_root / 'config.yaml'}: "
                f"{exc} — the provider lock refuses (fail closed)."
            ) from exc
    q = Path(qlib_dir).resolve()
    lock_dir = q.parent / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / f"provider_publish__{q.name}.lock"


@contextmanager
def api_call_lock(timeout: float = 1800.0):
    with FileLock(str(_account_lock_dir() / "tushare_api.lock"), timeout=timeout):
        yield


@contextmanager
def raw_maintenance_lock(timeout: float = 21600.0):  # 6h default — a monthly catch-up can run hours
    """Process-exclusive raw-layer maintenance, held on the REAL kernel lock (no env barrier).
    Lock identity = the SHARED DATA ROOT (``<data_root>/.locks/raw_maintenance.lock``), so any
    checkout configured onto the same store excludes any other; an unresolvable identity
    raises :class:`LockIdentityError` (fail closed). Pass a SHORT timeout in an unattended job
    (the daily raw job) so it fails fast + retries instead of blocking behind a multi-hour
    monthly build until its own task time-limit kills it (GPT m3); on timeout FileLock raises
    `Timeout` (re-exported above)."""
    with FileLock(str(_data_lock_dir() / "raw_maintenance.lock"), timeout=timeout):
        yield


@contextmanager
def provider_publish_lock(timeout: float = 7200.0, qlib_dir=None):
    """Process-exclusive LIVE-provider publish/swap + manifest writes (Phase 5-B B3; GPT
    re-review Blocker 7 made this a GLOBAL publish lock; re-review #4 P0 keyed its identity
    to the CANONICAL LIVE PROVIDER DIRECTORY itself — the lock file sits adjacent to the
    provider (``<qlib_parent>/.locks/provider_publish__<qlib_name>.lock``), so ANY checkout
    targeting the same provider shares ONE lock even when their raw data roots differ; an
    unresolvable identity raises :class:`LockIdentityError` and the publish REFUSES).

    Held at the COMMON CHOKEPOINTS — ``StagedQlibBackendBuilder.publish()`` and the
    ``provider_build.json`` emitters pass the exact ``qlib_dir`` they mutate — so ANY
    sanctioned publisher/manifest writer excludes any other, whichever entrypoint invoked
    it. The monthly transaction additionally holds it across its whole
    verify->swap->rebind scope.

    REENTRANT within a process/thread: the underlying ``FileLock`` is a per-path SINGLETON
    (``is_singleton=True``; verified on filelock 3.25.2 — same instance, counted acquire), so
    the transaction holding the lock can call ``publish()`` which re-acquires without
    deadlocking, while a second process still blocks. LOCK ORDER: any holder that also needs
    ``raw_maintenance_lock`` acquires raw FIRST, then this; publish-lock-only holders (the
    builder/emitters) never take the raw lock afterwards — no reverse-order path exists."""
    lock = FileLock(str(_resolve_provider_lock_path(_SOURCE_ROOT, qlib_dir=qlib_dir)),
                    is_singleton=True)
    lock.acquire(timeout=timeout)
    try:
        yield
    finally:
        lock.release()


# ── global cross-process rate spacing (a shared next-allowed timestamp, held under the API lock;
# lives in the PER-ACCOUNT namespace so independent clones share one spacing state) ──
def _next_allowed_path() -> Path:
    return _account_lock_dir() / "tushare_next_allowed.txt"


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
        d = _account_lock_dir()
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
