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
* **PIT001 — date-column stringify (column-aware severity).** ``.astype(str)`` /
  ``.astype("string")`` / ``.map(str)`` / ``.dt.strftime(...)`` /
  ``np.datetime_as_string(...)`` on a known date column. Severity depends on the
  column: a FUNDAMENTAL date column (``effective_date`` / ``ann_date`` /
  ``f_ann_date`` / ``disclosure_date`` / ``end_date`` / ``pubDate`` /
  ``statDate``) is stored as ``datetime64`` and stringifies to DASHED ISO
  (``"2018-10-30"``), which lexically mis-sorts against compact trade dates —
  this is the exact lookahead vector that produced the val_heavy artifact, so it
  is a **HARD ERROR (exit 1)**. ``trade_date`` is the compact market-date index
  whose stringify is benign → **WARNING (display-only)**. An inline
  ``# noqa: unsafe-pit-dates`` comment suppresses a PIT001 finding when a
  reviewer has confirmed it safe (PIT002 has NO inline escape — allowlist only).

Targets
-------
Both ``.py`` files and Jupyter ``.ipynb`` notebooks (code cells, magics stripped)
are scanned.

Allowlist
---------
PIT002 exemptions live ONLY in ``config/lint/unsafe_pit_dates_allowlist.yaml``
(schema-validated; no inline ``# noqa`` for PIT002). The lint fails on a
malformed / expired entry or one whose path no longer exists.

Exit codes
----------
* 0 — clean: no PIT002 violation and no PIT001 hard error.
* 1 — at least one PIT002 violation OR a PIT001 hard error (fundamental-date stringify).
* 2 — syntax error in a scanned ``.py`` file, or a malformed/expired/dangling allowlist.
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
# Stringifying a FUNDAMENTAL date column is the original lookahead vector: these
# are stored datetime64 → .astype(str) yields DASHED ISO ("2018-10-30"), which
# lexically mis-sorts against compact trade dates. PIT001 treats this as a hard
# ERROR. `trade_date` is the compact market-date index whose stringify is the
# benign side (warning only).
FUNDAMENTAL_DATE_COLS = KNOWN_DATE_COLS - {"trade_date"}
# Inline suppression for PIT001 only (PIT002 has NO inline escape — allowlist only).
_PIT001_NOQA = "noqa: unsafe-pit-dates"
_FSTRING_MIDDLE = getattr(tokenize, "FSTRING_MIDDLE", None)

# Sanctioned frozen-script archive ROOTS skipped during directory recursion.
# Root-specific (NOT "any dir named archive") so a future src/foo/archive/ or
# workspace/research/archive/ cannot silently escape the lint. New sanctioned
# archives must be added here explicitly (reviewed).
ARCHIVE_SKIP_ROOTS = (
    PROJECT_ROOT / "workspace" / "scripts" / "archive" / "pit_lookahead_legacy_2026_05",
    PROJECT_ROOT / "workspace" / "scripts" / "archive" / "p1_jq_g5a2_investigation_2026_05",
)


def _is_skipped_archive(path: Path) -> bool:
    rp = path.resolve()
    for root in ARCHIVE_SKIP_ROOTS:
        try:
            rp.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


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


def _date_col_of(node: ast.AST) -> str | None:
    """If ``node`` is ``X["<date_col>"]``, return the column name, else None."""
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
        v = node.slice.value
        if isinstance(v, str) and v in KNOWN_DATE_COLS:
            return v
    return None


def _pit001_findings(tree: ast.AST, source_lines: list[str]) -> list[tuple[int, str, str]]:
    """Detect date-column stringify. Returns (lineno, snippet, severity) where
    severity is "error" for a FUNDAMENTAL date column (the dashed-ISO lookahead
    vector) or "warning" for trade_date / compact dates. An inline
    ``# noqa: unsafe-pit-dates`` on the line suppresses the finding entirely."""
    out: list[tuple[int, str, str]] = []

    def _emit(lineno: int, col: str | None, kind: str) -> None:
        if col is None:
            return
        line = source_lines[lineno - 1] if 0 <= lineno - 1 < len(source_lines) else ""
        if _PIT001_NOQA in line:
            return  # explicitly suppressed (reason expected in the comment)
        if col in FUNDAMENTAL_DATE_COLS:
            out.append((lineno, f"{kind} on FUNDAMENTAL date column '{col}' (dashed-ISO; lookahead vector)", "error"))
        else:
            out.append((lineno, f"{kind} on date column '{col}' (compact market date)", "warning"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            recv = node.func.value
            if attr in ("astype", "map", "apply") and node.args:
                a0 = node.args[0]
                is_str = (isinstance(a0, ast.Constant) and a0.value in ("str", "string")) or (
                    isinstance(a0, ast.Name) and a0.id == "str"
                )
                if is_str:
                    _emit(node.lineno, _date_col_of(recv), f"{attr}(str)")
            elif attr == "strftime" and isinstance(recv, ast.Attribute) and recv.attr == "dt":
                _emit(node.lineno, _date_col_of(recv.value), "dt.strftime")
            elif attr == "datetime_as_string" and node.args:
                _emit(node.lineno, _date_col_of(node.args[0]), "np.datetime_as_string")
    return out


def _scan_source(source: str) -> tuple[list[tuple[int, str]], list[tuple[int, str, str]]]:
    """Scan a Python source string: (pit002, pit001_findings)."""
    tree = ast.parse(source)
    spans = _docstring_spans(tree)
    source_lines = source.splitlines()
    pit002: list[tuple[int, str]] = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        is_str = tok.type == tokenize.STRING or (
            _FSTRING_MIDDLE is not None and tok.type == _FSTRING_MIDDLE
        )
        if is_str and LEDGER_TOKEN in tok.string:
            row, col = tok.start
            if not _in_spans(row, col, spans):
                pit002.append((row, f"raw {LEDGER_TOKEN!r} string reference"))
    return pit002, _pit001_findings(tree, source_lines)


def scan_file(path: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str, str]]]:
    """Return (pit002_violations, pit001_findings) for a .py file."""
    return _scan_source(path.read_text(encoding="utf-8"))


def scan_notebook(path: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str, str]]]:
    """PIT002/PIT001 scan of a Jupyter .ipynb (parsed as JSON; stdlib only).

    Code cells are scanned individually (after stripping Jupyter magics / shell
    lines). If a cell does not parse as Python (fragments), PIT002 falls back to
    a comment-stripped line scan for the ledger token. ``lineno`` is reported as
    ``cell_index`` since cell line numbers are not globally meaningful."""
    import json as _json

    data = _json.loads(path.read_text(encoding="utf-8"))
    pit002: list[tuple[int, str]] = []
    pit001: list[tuple[int, str, str]] = []
    cells = data.get("cells") if isinstance(data, dict) else None
    if not isinstance(cells, list):
        return pit002, pit001  # not a notebook shape we can scan
    for ci, cell in enumerate(cells):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        src = cell.get("source", "")
        text = "".join(src) if isinstance(src, list) else str(src)
        code_lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(("%", "!", "?"))]
        code = "\n".join(code_lines)
        try:
            cell_pit002, cell_pit001 = _scan_source(code)
            pit002.extend((ci, f"{snip} (cell {ci})") for _, snip in cell_pit002)
            pit001.extend((ci, f"{snip} (cell {ci})", sev) for _, snip, sev in cell_pit001)
        except (SyntaxError, tokenize.TokenError):
            for ln in code_lines:
                if LEDGER_TOKEN in ln.split("#", 1)[0]:
                    pit002.append((ci, f"raw {LEDGER_TOKEN!r} reference (cell {ci}, line-scan)"))
    return pit002, pit001


SCANNED_SUFFIXES = (".py", ".ipynb")


def _iter_target_files(targets: Iterable[Path]) -> Iterable[Path]:
    """Yield every scannable file (``.py`` + ``.ipynb``) under ``targets``."""
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.is_file() and p.suffix in SCANNED_SUFFIXES:
            yield p  # explicit file: scanned even under archive/ (intentional override)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.suffix not in SCANNED_SUFFIXES or not f.is_file():
                    continue
                # Skip ONLY the sanctioned frozen-archive roots (root-specific,
                # NOT any dir named 'archive') so a future src/foo/archive/ or
                # workspace/research/archive/ cannot escape the lint.
                # test_dormant_module_boundaries.py enforces that no live src/ or
                # workspace/ code references the sanctioned archive.
                if _is_skipped_archive(f):
                    continue
                yield f


# Back-compat alias (the predicate name some callers/tests used pre-notebook scan).
_iter_python_files = _iter_target_files


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
    n_pit002 = 0
    n_pit001_err = 0
    for path in _iter_target_files([Path(t) for t in args.targets]):
        try:
            rel = path.resolve().relative_to(PROJECT_ROOT)
        except ValueError:
            rel = path
        rel_posix = str(rel).replace("\\", "/")
        try:
            if path.suffix == ".ipynb":
                pit002, pit001 = scan_notebook(path)
            else:
                pit002, pit001 = scan_file(path)
        except SyntaxError as exc:
            print(f"{rel_posix}: SyntaxError {exc.msg} (line {exc.lineno})", file=sys.stderr)
            exit_code = max(exit_code, 2)
            continue
        except (ValueError, OSError) as exc:  # malformed .ipynb JSON, unreadable file
            print(f"{rel_posix}: could not scan ({exc})", file=sys.stderr)
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
                n_pit002 += 1
                exit_code = max(exit_code, 1)
        for lineno, snippet, severity in pit001:
            if severity == "error":
                print(
                    f"{rel_posix}:{lineno}: PIT001 (error): {snippet} — convert via the PIT loader "
                    f"or wrap intentionally-safe uses with `# noqa: unsafe-pit-dates`.",
                    file=sys.stderr,
                )
                n_pit001_err += 1
                exit_code = max(exit_code, 1)
            elif not args.quiet_warnings:
                print(f"{rel_posix}:{lineno}: PIT001 (warning): {snippet}.", file=sys.stderr)

    if n_pit002 or n_pit001_err:
        print(
            f"\n{n_pit002} PIT002 violation(s), {n_pit001_err} PIT001 error(s).",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
