"""AST lint enforcing the no-global-calendar-policy invariant (POLICY001).

UNFREEZE_PLAN.md D1 (GPT Round-1 M2 / Round-2 M7): after the calendar thaw,
no code path may resolve "the" calendar policy globally. Two mechanical rules
over ``src/`` and ``scripts/``:

POLICY001a — the legacy policy id ``frozen_20260227_system_build`` must not
    appear as a STRING LITERAL in executable code (docstrings and comments are
    fine — they are historical references). Legacy fixtures live under
    ``tests/`` which is outside the lint scope by design.

POLICY001b — a function/method parameter named ``calendar_policy_id`` must not
    carry a default that NAMES a policy. ``None`` and ``""`` are permitted
    unset sentinels (the callee records "no policy pinned"); any other default
    silently re-creates the global policy. The policy id is an explicit caller
    decision (prescription pin or manifest-recorded value).

Per-line opt-out: append ``# noqa: global-calendar-policy`` to the line.

Usage::

    venv/Scripts/python.exe scripts/lint_no_global_calendar_policy.py src/ scripts/

Exit codes: 0 — clean; 1 — violations; 2 — usage/parse error.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

LEGACY_POLICY_ID = "frozen_20260227_system_build"
NOQA_TOKEN = "noqa: global-calendar-policy"
SELF_NAME = Path(__file__).name


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Line numbers of every docstring constant (module/class/def first-stmt)."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                start = body[0].value.lineno
                end = getattr(body[0].value, "end_lineno", start)
                lines.update(range(start, end + 1))
    return lines


def lint_file(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno}: POLICY001 parse error: {exc.msg}"]
    src_lines = src.splitlines()

    def _noqa(lineno: int) -> bool:
        return 0 < lineno <= len(src_lines) and NOQA_TOKEN in src_lines[lineno - 1]

    violations: list[str] = []
    doc_lines = _docstring_nodes(tree)

    for node in ast.walk(tree):
        # POLICY001a: legacy id as an executable string literal.
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and LEGACY_POLICY_ID in node.value \
                and node.lineno not in doc_lines and not _noqa(node.lineno):
            violations.append(
                f"{path}:{node.lineno}: POLICY001a legacy policy id "
                f"'{LEGACY_POLICY_ID}' as an executable string literal — pass the "
                "prescription-pinned or manifest-recorded policy id instead."
            )
        # POLICY001b: calendar_policy_id parameter with a non-None default.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            all_args = list(args.posonlyargs) + list(args.args)
            defaults = list(args.defaults)
            offset = len(all_args) - len(defaults)
            pairs = [(all_args[offset + i], d) for i, d in enumerate(defaults)]
            pairs += [
                (a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None
            ]
            for arg, default in pairs:
                if arg.arg == "calendar_policy_id" \
                        and not (isinstance(default, ast.Constant) and default.value in (None, "")) \
                        and not _noqa(node.lineno):
                    violations.append(
                        f"{path}:{node.lineno}: POLICY001b function "
                        f"'{node.name}' gives calendar_policy_id a non-None default — "
                        "the policy id must be an explicit caller decision."
                    )
    return violations


def main(argv: list[str]) -> int:
    roots = [Path(p) for p in (argv or ["src/", "scripts/"])]
    violations: list[str] = []
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for f in files:
            if f.name == SELF_NAME:
                continue
            violations.extend(lint_file(f))
    for v in violations:
        print(v)
    if violations:
        print(f"POLICY001: {len(violations)} violation(s).")
        return 1
    print("POLICY001: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
