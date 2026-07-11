# SCRIPT_STATUS: ACTIVE — Phase 5-C: ban raw Tushare-client construction that bypasses the locked proxy
"""AST lint (GPT 5-C Major 1): forbid `ts.pro_api(...)` / `tushare.pro_api(...)` outside the fetcher.

Every sanctioned Tushare call must flow through `TushareFetcher.pro`, which is a locked proxy that
serializes + rate-spaces calls across processes (CLAUDE.md §6.1). Constructing a RAW client directly
(`ts.pro_api(token)`) creates an UNLOCKED handle that bypasses the account lock. The one allowed
construction site is data_infra/fetchers/__init__.py (which wraps it in the proxy). Exit 1 on any
other. Wired into run_daily_qa.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {ROOT / "src" / "data_infra" / "fetchers" / "__init__.py"}
SCAN_DIRS = [ROOT / "src", ROOT / "scripts", ROOT / "workspace" / "scripts"]


def _violations(path: Path) -> list[int]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "pro_api":
            out.append(node.lineno)
    return out


def main() -> int:
    bad = []
    for d in SCAN_DIRS:
        for py in d.rglob("*.py"):
            if py.resolve() in ALLOWED or "archive" in py.parts:
                continue
            for ln in _violations(py):
                bad.append(f"{py.relative_to(ROOT)}:{ln}: bare pro_api() bypasses the locked proxy")
    if bad:
        print("PRO001 lint FAILED — construct Tushare via TushareFetcher(...).pro (locked proxy), "
              "not a raw ts.pro_api():", file=sys.stderr)
        for b in bad:
            print("  " + b, file=sys.stderr)
        return 1
    print("PRO001 lint OK: no bare pro_api() construction outside the fetcher")
    return 0


if __name__ == "__main__":
    sys.exit(main())
