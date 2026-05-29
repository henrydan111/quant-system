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


def test_pit001_flags_date_stringify(tmp_path):
    p = _write(tmp_path, "w.py",
               'df["effective_date"] = df["effective_date"].astype(str)\n'
               'df["trade_date"].dt.strftime("%Y%m%d")\n'
               'df["roa"] = df["roa"].astype(str)\n')  # non-date col -> not flagged
    _, pit001 = lint.scan_file(p)
    lines = {ln for ln, _, _ in pit001}
    assert 1 in lines and 2 in lines and 3 not in lines


def test_pit001_severity_is_column_aware(tmp_path):
    # FUNDAMENTAL date column (dashed-ISO source) -> ERROR; trade_date -> warning.
    p = _write(tmp_path, "sev.py",
               'a = df["effective_date"].astype(str)\n'   # fundamental -> error
               'b = df["ann_date"].map(str)\n'            # fundamental -> error
               'c = df["trade_date"].astype(str)\n'       # market index -> warning
               'd = df["f_ann_date"].dt.strftime("%Y%m%d")\n')  # fundamental -> error
    _, pit001 = lint.scan_file(p)
    sev = {ln: s for ln, _, s in pit001}
    assert sev == {1: "error", 2: "error", 3: "warning", 4: "error"}


def test_pit001_datetime_as_string_flagged(tmp_path):
    p = _write(tmp_path, "npas.py",
               'import numpy as np\n'
               'x = np.datetime_as_string(df["ann_date"])\n')
    _, pit001 = lint.scan_file(p)
    assert any(s == "error" for _, _, s in pit001)


def test_pit001_noqa_suppresses(tmp_path):
    # An inline `# noqa: unsafe-pit-dates` removes the finding entirely.
    p = _write(tmp_path, "noqa.py",
               'a = df["effective_date"].astype(str)  # noqa: unsafe-pit-dates\n'
               'b = df["ann_date"].astype(str)\n')  # still flagged
    _, pit001 = lint.scan_file(p)
    lines = {ln for ln, _, _ in pit001}
    assert lines == {2}


def test_scan_notebook_flags_ledger_read():
    """A code cell that reads the raw ledger is a PIT002 violation; a markdown
    cell or a magic line mentioning the ledger is not."""
    import json as _json
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["see data/pit_ledger/ for the raw tables\n"]},
            {"cell_type": "code", "source": ["%matplotlib inline\n",
                                              "df = pd.read_parquet('data/pit_ledger/indicators/x.parquet')\n"]},
            {"cell_type": "code", "source": ["x = df['effective_date'].astype(str)\n"]},
        ],
        "metadata": {}, "nbformat": 4, "nbformat_minor": 5,
    }
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "nb.ipynb"
        p.write_text(_json.dumps(nb), encoding="utf-8")
        pit002, pit001 = lint.scan_notebook(p)
    assert len(pit002) == 1                       # only the code-cell ledger read
    assert any(s == "error" for _, _, s in pit001)  # fundamental-date stringify in a code cell


def test_scan_notebook_tolerates_non_notebook_json(tmp_path):
    # Valid JSON that is not a notebook shape must not raise (returns empty).
    p = _write(tmp_path, "weird.ipynb", '{"cells": "not-a-list"}')
    assert lint.scan_notebook(p) == ([], [])
    p2 = _write(tmp_path, "weird2.ipynb", '[1, 2, 3]')
    assert lint.scan_notebook(p2) == ([], [])


def test_iter_target_files_includes_notebooks(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "b.ipynb").write_text('{"cells": []}\n', encoding="utf-8")
    (tmp_path / "c.txt").write_text("ignore me\n", encoding="utf-8")
    found = {p.name for p in lint._iter_target_files([tmp_path])}
    assert found == {"a.py", "b.ipynb"}


def _run_main(monkeypatch, *targets, quiet=True):
    argv = ["lint", *[str(t) for t in targets]]
    if quiet:
        argv.append("--quiet-warnings")
    monkeypatch.setattr("sys.argv", argv)
    return lint.main()


def test_main_exits_1_on_fundamental_stringify(tmp_path, monkeypatch):
    _write(tmp_path, "bad.py", 'x = df["ann_date"].astype(str)\n')
    assert _run_main(monkeypatch, tmp_path) == 1


def test_main_exits_0_on_trade_date_only(tmp_path, monkeypatch):
    # trade_date stringify is a WARNING only -> exit 0 (clean).
    _write(tmp_path, "ok.py", 'x = df["trade_date"].astype(str)\n')
    assert _run_main(monkeypatch, tmp_path) == 0


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
