"""Tests for scripts/lint_no_unsafe_pit_dates.py (prevention plan v5 §6.3/§6.4).

Offline / public-CI-safe (no ledger or provider needed).
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "lint_no_unsafe_pit_dates", _ROOT / "scripts" / "lint_no_unsafe_pit_dates.py"
)
lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint)


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_pit002_flags_raw_read_and_path(tmp_path):
    p = _write(tmp_path, "bad.py",
               'import pandas as pd\n'
               'df = pd.read_parquet("data/pit_ledger/indicators/indicators.parquet")\n'
               'q = "data/pit_ledger" + "/x"\n')
    pit002, _ = lint.scan_file(p)
    assert len(pit002) == 2


def test_pit002_ignores_docstring_and_comment(tmp_path):
    p = _write(tmp_path, "ok.py",
               'def f():\n'
               '    """Consumers under data/pit_ledger/ must use the loader."""\n'
               '    return 1\n'
               '# comment about data/pit_ledger should not flag\n')
    pit002, _ = lint.scan_file(p)
    assert pit002 == []


def test_provider_metadata_is_not_flagged():
    """Blocking-edit-2 regression: the real safety docstring in
    provider_metadata.stock_basic_bounds mentions data/pit_ledger/ but must NOT
    be flagged (it is a docstring, not a code-level ledger read)."""
    pm = _ROOT / "src" / "data_infra" / "provider_metadata.py"
    pit002, _ = lint.scan_file(pm)
    assert pit002 == []


def test_pit001_warns_on_date_stringify(tmp_path):
    p = _write(tmp_path, "w.py",
               'df["effective_date"] = df["effective_date"].astype(str)\n'
               'df["trade_date"].dt.strftime("%Y%m%d")\n'
               'df["roa"] = df["roa"].astype(str)\n')  # non-date col -> not warned
    _, pit001 = lint.scan_file(p)
    lines = {ln for ln, _ in pit001}
    assert 1 in lines and 2 in lines and 3 not in lines


def test_allowlist_valid(tmp_path):
    al = _write(tmp_path, "al.yaml",
                f'- path: src/data_infra/pit_research_loader.py\n'
                f'  rule: PIT002\n  owner: x\n  reason: blessed\n  permanent: true\n')
    allowed = lint.load_allowlist(al)
    assert "src/data_infra/pit_research_loader.py" in allowed


def test_allowlist_missing_required_key_raises(tmp_path):
    al = _write(tmp_path, "al.yaml", "- path: src/data_infra/pit_backend.py\n  rule: PIT002\n")
    with pytest.raises(lint.AllowlistError):
        lint.load_allowlist(al)


def test_allowlist_expired_raises(tmp_path):
    al = _write(tmp_path, "al.yaml",
                '- path: src/data_infra/pit_backend.py\n  rule: PIT002\n  owner: x\n'
                '  reason: temp\n  expires: "2000-01-01"\n')
    with pytest.raises(lint.AllowlistError):
        lint.load_allowlist(al)


def test_allowlist_dangling_path_raises(tmp_path):
    al = _write(tmp_path, "al.yaml",
                '- path: src/data_infra/does_not_exist.py\n  rule: PIT002\n  owner: x\n'
                '  reason: gone\n  permanent: true\n')
    with pytest.raises(lint.AllowlistError):
        lint.load_allowlist(al)


def test_allowlist_unsupported_rule_raises(tmp_path):
    al = _write(tmp_path, "al.yaml",
                '- path: src/data_infra/pit_backend.py\n  rule: PIT999\n  owner: x\n'
                '  reason: typo rule\n  permanent: true\n')
    with pytest.raises(lint.AllowlistError):
        lint.load_allowlist(al)


def test_allowlist_non_bool_permanent_raises(tmp_path):
    al = _write(tmp_path, "al.yaml",
                '- path: src/data_infra/pit_backend.py\n  rule: PIT002\n  owner: x\n'
                '  reason: x\n  permanent: "yes"\n')
    with pytest.raises(lint.AllowlistError):
        lint.load_allowlist(al)


def test_archive_skip_is_root_specific(tmp_path):
    # A GENERIC 'archive' dir (not a sanctioned root) must NOT be skipped — only
    # the enumerated ARCHIVE_SKIP_ROOTS are. This blocks the broad-skip bypass
    # (src/foo/archive/, workspace/research/archive/, ...).
    (tmp_path / "live.py").write_text("x = 1\n", encoding="utf-8")
    arch = tmp_path / "archive" / "legacy"
    arch.mkdir(parents=True)
    (arch / "dead.py").write_text("x = 1\n", encoding="utf-8")
    found = {p.name for p in lint._iter_python_files([tmp_path])}
    assert "live.py" in found
    assert "dead.py" in found  # generic archive/ is NOT a sanctioned skip root


def test_sanctioned_archive_root_predicate():
    # The predicate skips files under a sanctioned archive root, not elsewhere.
    legacy_root = lint.PROJECT_ROOT / "workspace" / "scripts" / "archive" / "pit_lookahead_legacy_2026_05"
    assert lint._is_skipped_archive(legacy_root / "sandbox_v15o_val_heavy_confirm.py") is True
    assert lint._is_skipped_archive(lint.PROJECT_ROOT / "src" / "data_infra" / "pit_research_loader.py") is False
    assert lint._is_skipped_archive(lint.PROJECT_ROOT / "workspace" / "research" / "archive" / "bad.py") is False


def test_committed_allowlist_loads():
    """The real committed allowlist must satisfy its own schema."""
    allowed = lint.load_allowlist()
    assert "src/data_infra/pit_research_loader.py" in allowed
