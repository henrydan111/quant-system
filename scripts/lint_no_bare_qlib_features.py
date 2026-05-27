"""AST lint banning bare ``D.features(...)`` calls outside the canonical wrapper.

PR 6 of the 2026-05-26 freeze plan. The lint enforces that every Qlib
``D.features`` invocation in ``src/`` goes through
``src/research_orchestrator/qlib_windowed_features.py`` — which carries the
``ResearchAccessContext`` window/seal/field enforcement.

What we catch
-------------

* ``from qlib.data import D; D.features(...)``
* ``from qlib.data import D as X; X.features(...)``
* ``import qlib.data; qlib.data.D.features(...)``
* ``import qlib.data as q; q.D.features(...)``
* ``getattr(D, "features")(...)`` and ``getattr(<D-alias>, "features")(...)``

Allowlist
---------

By default the canonical wrapper is allowed:

* ``src/research_orchestrator/qlib_windowed_features.py``

Per-line opt-out: append ``# noqa: bare-qlib-features`` to the offending line.

Per-file opt-out: pass ``--allow <glob>`` (repeatable). Useful for tests that
deliberately exercise the wrapper, and for legacy workspace scripts pending
PR 7 cleanup.

Usage
-----

::

    venv/Scripts/python.exe scripts/lint_no_bare_qlib_features.py src/

Exit codes
----------

* 0 — no violations.
* 1 — at least one violation (file path + line printed to stderr).
* 2 — syntax error in a scanned file.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_TARGETS = ("src",)
DEFAULT_ALLOWLIST: tuple[str, ...] = (
    "src/research_orchestrator/qlib_windowed_features.py",
)
NOQA_MARKER = "noqa: bare-qlib-features"


class _Visitor(ast.NodeVisitor):
    """Track imports of ``D`` / ``qlib.data`` and flag ``.features`` access."""

    def __init__(self, source_lines: list[str]) -> None:
        self.d_aliases: set[str] = set()         # local names referring to qlib.data.D
        self.qlib_data_aliases: set[str] = set() # local names referring to qlib.data
        self.violations: list[tuple[int, str]] = []  # (lineno, snippet)
        self._source_lines = source_lines

    # ── Import tracking ────────────────────────────────────────────

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module == "qlib.data":
            for alias in node.names:
                if alias.name == "D":
                    self.d_aliases.add(alias.asname or "D")
        elif node.module == "qlib":
            for alias in node.names:
                if alias.name == "data":
                    self.qlib_data_aliases.add(alias.asname or "data")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            if alias.name == "qlib.data":
                self.qlib_data_aliases.add(alias.asname or "qlib.data")
            elif alias.name == "qlib":
                # `import qlib` — then qlib.data.D.features works via attribute chain.
                # We track `qlib` so we can recognize `qlib.data.D.features`.
                self.qlib_data_aliases.add(alias.asname or "qlib")
        self.generic_visit(node)

    # ── Detection ──────────────────────────────────────────────────

    def _line_is_allowlisted(self, lineno: int) -> bool:
        if lineno - 1 >= len(self._source_lines):
            return False
        line = self._source_lines[lineno - 1]
        return NOQA_MARKER in line

    def _record(self, lineno: int, snippet: str) -> None:
        if self._line_is_allowlisted(lineno):
            return
        self.violations.append((lineno, snippet))

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        # Direct: <D-alias>.features
        if (
            isinstance(node.value, ast.Name)
            and node.value.id in self.d_aliases
            and node.attr == "features"
        ):
            self._record(node.lineno, f"{node.value.id}.features")

        # Chained: <qlib_data-alias>.D.features  (e.g. `q.D.features`)
        if node.attr == "features" and isinstance(node.value, ast.Attribute):
            inner = node.value
            if (
                inner.attr == "D"
                and isinstance(inner.value, ast.Name)
                and inner.value.id in self.qlib_data_aliases
            ):
                self._record(
                    node.lineno, f"{inner.value.id}.D.features"
                )
            # Triple-chain: qlib.data.D.features (when `import qlib`)
            if (
                inner.attr == "D"
                and isinstance(inner.value, ast.Attribute)
                and inner.value.attr == "data"
                and isinstance(inner.value.value, ast.Name)
                and inner.value.value.id in self.qlib_data_aliases
            ):
                self._record(
                    node.lineno,
                    f"{inner.value.value.id}.data.D.features",
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        # getattr(<D-alias>, "features")
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
        ):
            arg0, arg1 = node.args[0], node.args[1]
            target_name: str | None = None
            if isinstance(arg0, ast.Name) and arg0.id in self.d_aliases:
                target_name = arg0.id
            elif (
                isinstance(arg0, ast.Attribute)
                and arg0.attr == "D"
                and isinstance(arg0.value, ast.Name)
                and arg0.value.id in self.qlib_data_aliases
            ):
                target_name = f"{arg0.value.id}.D"
            if (
                target_name is not None
                and isinstance(arg1, ast.Constant)
                and isinstance(arg1.value, str)
                and arg1.value == "features"
            ):
                self._record(
                    node.lineno,
                    f"getattr({target_name}, 'features')",
                )
        self.generic_visit(node)


def scan_file(path: Path) -> list[tuple[int, str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    source_lines = source.splitlines()
    visitor = _Visitor(source_lines)
    visitor.visit(tree)
    return visitor.violations


def _iter_python_files(targets: Iterable[Path]) -> Iterable[Path]:
    for t in targets:
        p = Path(t)
        if p.is_file() and p.suffix == ".py":
            yield p
            continue
        if p.is_dir():
            yield from sorted(p.rglob("*.py"))


def _is_allowlisted(path: Path, project_root: Path, allow_patterns: list[str]) -> bool:
    try:
        rel = path.resolve().relative_to(project_root)
    except ValueError:
        rel = path
    rel_posix = str(rel).replace("\\", "/")
    for pat in allow_patterns:
        if fnmatch.fnmatch(rel_posix, pat):
            return True
        if rel_posix == pat:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "targets",
        nargs="*",
        default=list(DEFAULT_TARGETS),
        help="Files / directories to scan (default: src/)",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        help="Glob pattern (path relative to project root) to allowlist. Repeatable.",
    )
    parser.add_argument(
        "--no-default-allowlist",
        action="store_true",
        help="Skip the built-in allowlist (qlib_windowed_features.py).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    allow = list(args.allow)
    if not args.no_default_allowlist:
        allow.extend(DEFAULT_ALLOWLIST)

    target_paths = [Path(t) for t in args.targets]
    if not target_paths:
        print("error: no targets provided", file=sys.stderr)
        return 2

    exit_code = 0
    total_violations = 0
    files_scanned = 0
    for path in _iter_python_files(target_paths):
        if _is_allowlisted(path, project_root, allow):
            continue
        files_scanned += 1
        try:
            violations = scan_file(path)
        except SyntaxError as exc:
            print(
                f"{path}: SyntaxError {exc.msg} (line {exc.lineno})",
                file=sys.stderr,
            )
            exit_code = max(exit_code, 2)
            continue
        for lineno, snippet in violations:
            try:
                rel = path.resolve().relative_to(project_root)
            except ValueError:
                rel = path
            print(
                f"{rel}:{lineno}: bare-qlib-features: {snippet}() — "
                "route through src.research_orchestrator.qlib_windowed_features.",
                file=sys.stderr,
            )
            total_violations += 1
            exit_code = max(exit_code, 1)

    if total_violations:
        print(
            f"\n{total_violations} violation(s) across {files_scanned} file(s) scanned.",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
