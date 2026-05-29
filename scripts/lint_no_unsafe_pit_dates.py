"""Lint banning unsafe PIT-ledger access / date handling in research code.

Prevention plan v5 §6.3. Mirrors ``scripts/lint_no_bare_qlib_features.py``.

Rules
-----
* **PIT002 — raw ``data/pit_ledger/*`` read (HARD ERROR).** Any code-level
  reference to ``pit_ledger`` as a string literal (e.g.
  ``pd.read_parquet("data/pit_ledger/indicators/indicators.parquet")``,
  ``ROOT / "data" / "pit_ledger"``, ``glob("data/pit_ledger/*")``,
  ``Path("...pit_ledger...")``). Research/sandbox code must instead use
  ``src.data_infra.pit_research_loader.load_pit_*``; formal code uses
  ``qlib_windowed_features``. Detection is **docstring/comment-aware**: a
  ``pit_ledger`` mention inside a docstring or comment (e.g. the safety note in
  ``provider_metadata.stock_basic_bounds``) is NOT flagged.
* **PIT001 — date-column stringify (WARNING, phase 1).** ``.astype(str)`` /
  ``.astype("string")`` / ``.map(str)`` / ``.dt.strftime(...)`` on a known date
  column. Staged: warning now; promoted to a sink-aware hard error after
  fixture tuning (§6.3). Warnings do not affect the exit code.

Allowlist
---------
PIT002 exemptions live ONLY in ``config/lint/unsafe_pit_dates_allowlist.yaml``
(schema-validated; no inline ``# noqa`` for PIT002). The lint fails on a
malformed / expired entry or one whose path no longer exists.

Exit codes
----------
* 0 — no PIT002 violations.
* 1 — at least one PIT002 violation.
* 2 — syntax error in a scanned file, or a malformed/expired/dangling allowlist.
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import io
import sys
import tokenize
from pathlib import Path
from typing import Iterable

import yaml

# v5 §6.3 scope: src + workspace (NOT scripts by default — scripts/ contains
# this linter, whose detection literal is the token itself; scanning scripts/ is
# opt-in via explicit args, and the linter is self-allowlisted besides).
DEFAULT_TARGETS = ("src", "workspace")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = PROJECT_ROOT / "config" / "lint" / "unsafe_pit_dates_allowlist.yaml"
LEDGER_TOKEN = "pit_ledger"
KNOWN_DATE_COLS = {
    "effective_date", "ann_date", "f_ann_date", "disclosure_date",
    "end_date", "trade_date", "pubDate", "statDate",
}
_FSTRING_MIDDLE = getattr(tokenize, "FSTRING_MIDDLE", None)


class AllowlistError(RuntimeError):
    """Malformed, expired, or dangling allowlist entry."""


def load_allowlist(path: Path = ALLOWLIST_PATH) -> set[str]:
    """Return the set of allowlisted relative paths, validating the schema."""
    if not path.exists():
        return set()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return set()
    if not isinstance(raw, list):
        raise AllowlistError(f"{path}: top level must be a list of entries")
    today = _dt.date.today()
    allowed: set[str] = set()
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise AllowlistError(f"{path}[{i}]: entry must be a mapping")
        for key in ("path", "rule", "owner", "reason"):
            if not entry.get(key):
                raise AllowlistError(f"{path}[{i}]: missing required key {key!r}")
        # The allowlist is the ONLY PIT002 escape hatch, so validate strictly.
        if entry["rule"] != "PIT002":
            raise AllowlistError(
                f"{path}[{i}]: unsupported rule {entry['rule']!r} (only 'PIT002' is allowlistable)"
            )
        if "permanent" in entry and not isinstance(entry["permanent"], bool):
            raise AllowlistError(
                f"{path}[{i}] ({entry['path']}): 'permanent' must be a boolean, "
                f"got {type(entry['permanent']).__name__}"
            )
        permanent = bool(entry.get("permanent", False))
        expires = entry.get("expires")
        if not permanent:
            if not expires:
                raise AllowlistError(
                    f"{path}[{i}] ({entry['path']}): non-permanent entry needs an 'expires' date"
                )
            exp = expires if isinstance(expires, _dt.date) else _dt.date.fromisoformat(str(expires))
            if exp < today:
                raise AllowlistError(
                    f"{path}[{i}] ({entry['path']}): allowlist entry expired on {exp}"
                )
        rel = str(entry["path"]).replace("\\", "/")
        if not (PROJECT_ROOT / rel).exists():
            raise AllowlistError(f"{path}[{i}]: allowlisted path does not exist: {rel}")
        allowed.add(rel)
    return allowed


def _docstring_spans(tree: ast.AST) -> list[tuple[int, int, int, int]]:
    spans: list[tuple[int, int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                e = body[0].value
                spans.append((e.lineno, e.col_offset, e.end_lineno or e.lineno, e.end_col_offset or e.col_offset))
    return spans


def _in_spans(row: int, col: int, spans: list[tuple[int, int, int, int]]) -> bool:
    for (sl, sc, el, ec) in spans:
        if (sl, sc) <= (row, col) <= (el, ec):
            return True
    return False


def _pit001_warnings(tree: ast.AST) -> list[tuple[int, str]]:
    """Phase-1 (warning) detection of date-column stringify."""
    out: list[tuple[int, str]] = []

    def _is_date_subscript(node: ast.AST) -> bool:
        # X["<date_col>"]
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            return node.slice.value in KNOWN_DATE_COLS
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            recv = node.func.value
            if attr in ("astype", "map", "apply") and node.args:
                a0 = node.args[0]
                is_str = (isinstance(a0, ast.Constant) and a0.value in ("str", "string")) or (
                    isinstance(a0, ast.Name) and a0.id == "str"
                )
                if is_str and _is_date_subscript(recv):
                    out.append((node.lineno, f"{attr}(str) on a date column"))
            elif attr == "strftime" and isinstance(recv, ast.Attribute) and recv.attr == "dt":
                if _is_date_subscript(recv.value):
                    out.append((node.lineno, "dt.strftime on a date column"))
    return out


def scan_file(path: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """Return (pit002_violations, pit001_warnings) as lists of (lineno, snippet)."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    spans = _docstring_spans(tree)

    pit002: list[tuple[int, str]] = []
    reader = io.StringIO(source).readline
    for tok in tokenize.generate_tokens(reader):
        is_str = tok.type == tokenize.STRING or (
            _FSTRING_MIDDLE is not None and tok.type == _FSTRING_MIDDLE
        )
        if is_str and LEDGER_TOKEN in tok.string:
            row, col = tok.start
            if not _in_spans(row, col, spans):
                pit002.append((row, f"raw {LEDGER_TOKEN!r} string reference"))

    return pit002, _pit001_warnings(tree)


def _iter_python_files(targets: Iterable[Path]) -> Iterable[Path]:
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.is_file() and p.suffix == ".py":
            yield p  # explicit file: scanned even under archive/ (intentional override)
        elif p.is_dir():
            for f in sorted(p.rglob("*.py")):
                # Skip frozen historical archives during directory recursion.
                # Archived scripts are not live code; test_dormant_module_boundaries.py
                # enforces that no live src/ or workspace/ code references them.
                if "archive" in f.parts:
                    continue
                yield f


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", default=list(DEFAULT_TARGETS))
    parser.add_argument("--quiet-warnings", action="store_true", help="suppress PIT001 warnings")
    args = parser.parse_args()

    try:
        allowed = load_allowlist()
    except (AllowlistError, ValueError) as exc:
        print(f"allowlist error: {exc}", file=sys.stderr)
        return 2

    exit_code = 0
    n_viol = 0
    for path in _iter_python_files([Path(t) for t in args.targets]):
        try:
            rel = path.resolve().relative_to(PROJECT_ROOT)
        except ValueError:
            rel = path
        rel_posix = str(rel).replace("\\", "/")
        try:
            pit002, pit001 = scan_file(path)
        except SyntaxError as exc:
            print(f"{rel_posix}: SyntaxError {exc.msg} (line {exc.lineno})", file=sys.stderr)
            exit_code = max(exit_code, 2)
            continue
        if rel_posix not in allowed:
            for lineno, snippet in pit002:
                print(
                    f"{rel_posix}:{lineno}: PIT002: {snippet} — route ledger access through "
                    f"src.data_infra.pit_research_loader.load_pit_* (allowlist: "
                    f"config/lint/unsafe_pit_dates_allowlist.yaml).",
                    file=sys.stderr,
                )
                n_viol += 1
                exit_code = max(exit_code, 1)
        if not args.quiet_warnings:
            for lineno, snippet in pit001:
                print(f"{rel_posix}:{lineno}: PIT001 (warning): {snippet}.", file=sys.stderr)

    if n_viol:
        print(f"\n{n_viol} PIT002 violation(s).", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
