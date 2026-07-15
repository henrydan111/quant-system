"""Shared pytest configuration for repo-local, sandbox-safe test temp paths."""

from pathlib import Path
import os
import shutil
import tempfile
import uuid

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = PROJECT_ROOT / "workspace" / "outputs" / "pytest_runtime_tmp"
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
_ORIGINAL_MKDTEMP = tempfile.mkdtemp

for env_name in ("TMP", "TEMP", "TMPDIR"):
    os.environ[env_name] = str(TEST_TMP_ROOT)

tempfile.tempdir = str(TEST_TMP_ROOT)


def _repo_mkdtemp(suffix=None, prefix=None, dir=None):  # noqa: A002, ARG001
    """Create temp dirs with normal inherited ACLs inside the repo workspace."""
    safe_prefix = "tmp" if prefix is None else str(prefix)
    safe_suffix = "" if suffix is None else str(suffix)
    for _ in range(100):
        path = TEST_TMP_ROOT / f"{safe_prefix}{uuid.uuid4().hex}{safe_suffix}"
        try:
            path.mkdir(parents=True, exist_ok=False)
            return str(path)
        except FileExistsError:
            continue
    return _ORIGINAL_MKDTEMP(suffix=suffix, prefix=prefix, dir=str(TEST_TMP_ROOT))


tempfile.mkdtemp = _repo_mkdtemp


@pytest.fixture
def tmp_path():
    """Repo-local replacement for pytest's tmp_path on this Windows sandbox."""
    path = TEST_TMP_ROOT / f"case_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def pytest_configure(config):  # noqa: ARG001
    """Keep Windows sandbox ACL quirks from turning test results into cleanup errors."""
    try:
        import _pytest.pathlib as pytest_pathlib
        import _pytest.tmpdir as pytest_tmpdir
    except Exception:
        return

    original = pytest_pathlib.cleanup_dead_symlinks

    def _safe_cleanup_dead_symlinks(root):
        try:
            return original(root)
        except PermissionError:
            return None

    pytest_pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
    pytest_tmpdir.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks


# ── PR3 R6/R7 — the REAL canonical holdout store must be UNREACHABLE from tests ──
# Three layers (R7 Major 3):
#   1. an autouse fixture patches the resolver to a per-test scratch dir (below);
#   2. a COLLECTION-TIME write guard wraps every governance-store constructor to refuse
#      the real canonical root outright (covers direct HoldoutSealStore(real_root) and
#      any caller-injected path that bypasses the resolver);
#   3. a session-level hash sentinel over the real store file fails the run loudly if
#      its bytes changed during the session.
_REAL_HOLDOUT_ROOT: str | None = None
_HOLDOUT_SENTINEL: dict = {}


def _real_holdout_file() -> Path | None:
    if _REAL_HOLDOUT_ROOT is None:
        return None
    p = Path(_REAL_HOLDOUT_ROOT) / "holdout_events.parquet"
    return p if p.exists() else None


def _hash_real_holdout() -> str:
    import hashlib

    p = _real_holdout_file()
    if p is None:
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _install_real_holdout_guard() -> None:
    global _REAL_HOLDOUT_ROOT
    try:
        import src.research_orchestrator.holdout_seal as hs_mod
        from src.alpha_research.factor_eval_skill import _store as fes_store
    except Exception:
        return
    try:
        _REAL_HOLDOUT_ROOT = str(hs_mod._resolve_configured_global_holdout_root_uncached())
    except Exception:
        return
    real = _REAL_HOLDOUT_ROOT

    def _guard(root_dir) -> None:
        if str(Path(str(root_dir)).resolve()) == real:
            raise RuntimeError(
                "TEST GUARD: refusing to open the REAL canonical holdout store "
                f"({real}) from inside pytest — tests operate only on scratch roots"
            )

    def _wrap(cls):
        orig = cls.__init__

        def guarded(self, root_dir, *args, **kwargs):
            _guard(root_dir)
            return orig(self, root_dir, *args, **kwargs)

        cls.__init__ = guarded

    _wrap(hs_mod.HoldoutSealStore)
    _wrap(hs_mod.OosExecutionGuardStore)
    _wrap(fes_store.AppendOnlyStore)   # every factor_eval_skill governance store
    _HOLDOUT_SENTINEL["before"] = _hash_real_holdout()


_install_real_holdout_guard()


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """R7 Major 3: fail the run LOUDLY if the real canonical store changed bytes."""
    if _REAL_HOLDOUT_ROOT is None:
        return
    after = _hash_real_holdout()
    if after != _HOLDOUT_SENTINEL.get("before", ""):
        print(
            "\n[FATAL TEST GUARD] the REAL canonical holdout store changed during this "
            f"pytest session (sha256 {_HOLDOUT_SENTINEL.get('before')!r} -> {after!r}). "
            "Investigate + restore from backup immediately.",
        )
        session.exitstatus = 3


@pytest.fixture(autouse=True)
def _quarantine_canonical_holdout_root(request, monkeypatch):
    """PR3 R6 (test-pollution guard, layer 1): patch the resolver to a per-test scratch
    dir so a test that reaches a claim can never write into the real sealed world (this
    happened once on 2026-07-15 — the polluting row was surgically removed with a
    backup). A test that needs a SPECIFIC root re-patches the resolver in its own body
    (that wins over this default). The scratch dir is removed on teardown."""
    try:
        import src.research_orchestrator.holdout_seal as hs_mod
    except Exception:
        yield
        return
    scratch_parent = Path(_repo_mkdtemp(prefix="canonical_holdout_"))
    scratch = scratch_parent / "holdout_seals"
    monkeypatch.setattr(hs_mod, "resolve_configured_global_holdout_root",
                        lambda: scratch)
    try:
        yield
    finally:
        shutil.rmtree(scratch_parent, ignore_errors=True)
