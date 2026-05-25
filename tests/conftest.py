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
