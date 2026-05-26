"""PR 6 negative-test suite — AST lint for bare D.features calls."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

LINT_SCRIPT = Path("scripts/lint_no_bare_qlib_features.py").resolve()


def _run_lint(target_dir: Path, *extra_args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(LINT_SCRIPT), str(target_dir), "--no-default-allowlist", *extra_args]
    return subprocess.run(cmd, capture_output=True, text=True)


def _write(tmp_path: Path, name: str, body: str) -> Path:
    f = tmp_path / name
    f.write_text(body, encoding="utf-8")
    return f


class TestLintDetection:
    def test_plain_d_features_is_caught(self, tmp_path: Path) -> None:
        _write(tmp_path, "bad.py", """
from qlib.data import D
def go():
    return D.features(['000001_SZ'], ['$close'])
""")
        result = _run_lint(tmp_path)
        assert result.returncode == 1
        assert "bad.py" in result.stderr
        assert "D.features" in result.stderr

    def test_aliased_import_is_caught(self, tmp_path: Path) -> None:
        _write(tmp_path, "aliased.py", """
from qlib.data import D as QD
def go():
    return QD.features([], [])
""")
        result = _run_lint(tmp_path)
        assert result.returncode == 1
        assert "aliased.py" in result.stderr

    def test_qlib_data_as_alias_is_caught(self, tmp_path: Path) -> None:
        _write(tmp_path, "module.py", """
import qlib.data as q
def go():
    return q.D.features([], [])
""")
        result = _run_lint(tmp_path)
        assert result.returncode == 1
        assert "module.py" in result.stderr

    def test_full_qlib_import_chain_is_caught(self, tmp_path: Path) -> None:
        _write(tmp_path, "fullimport.py", """
import qlib
def go():
    return qlib.data.D.features([], [])
""")
        result = _run_lint(tmp_path)
        assert result.returncode == 1
        assert "fullimport.py" in result.stderr

    def test_getattr_trick_is_caught(self, tmp_path: Path) -> None:
        _write(tmp_path, "getattrtrick.py", """
from qlib.data import D
def go():
    fn = getattr(D, 'features')
    return fn([], [])
""")
        result = _run_lint(tmp_path)
        assert result.returncode == 1
        assert "getattrtrick.py" in result.stderr


class TestLintAllowlist:
    def test_noqa_comment_suppresses(self, tmp_path: Path) -> None:
        _write(tmp_path, "allowed.py", """
from qlib.data import D
def go():
    return D.features([], [])  # noqa: bare-qlib-features
""")
        result = _run_lint(tmp_path)
        assert result.returncode == 0, result.stderr

    def test_allow_flag_skips_file(self, tmp_path: Path) -> None:
        _write(tmp_path, "skip_me.py", """
from qlib.data import D
def go():
    return D.features([], [])
""")
        # Pass the file path as both target and allow glob. The script
        # computes paths relative to the project root, so use an absolute
        # glob via fnmatch.
        result = _run_lint(tmp_path, "--allow", "**/skip_me.py")
        assert result.returncode == 0, result.stderr


class TestLintCleanModules:
    def test_no_qlib_import_returns_zero(self, tmp_path: Path) -> None:
        _write(tmp_path, "clean.py", """
import pandas as pd
def go():
    return pd.DataFrame()
""")
        result = _run_lint(tmp_path)
        assert result.returncode == 0

    def test_qlib_calendar_is_not_features(self, tmp_path: Path) -> None:
        # D.calendar, D.instruments, D.list_instruments are allowed.
        _write(tmp_path, "calendar.py", """
from qlib.data import D
def go():
    return D.calendar(start_time='2020-01-01', end_time='2024-12-31')
""")
        result = _run_lint(tmp_path)
        assert result.returncode == 0


class TestLintSyntaxError:
    def test_syntax_error_is_exit_2(self, tmp_path: Path) -> None:
        _write(tmp_path, "broken.py", "def go(:\n    pass\n")
        result = _run_lint(tmp_path)
        assert result.returncode == 2
        assert "SyntaxError" in result.stderr


class TestLintAgainstLiveSrc:
    """End-to-end smoke: src/ must be clean under the lint."""

    def test_src_passes(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        cmd = [sys.executable, str(project_root / "scripts" / "lint_no_bare_qlib_features.py"), "src/"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))
        assert result.returncode == 0, f"src/ lint violations: {result.stderr}"
