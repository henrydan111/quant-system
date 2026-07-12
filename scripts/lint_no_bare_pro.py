# SCRIPT_STATUS: ACTIVE — Phase 5-C: ban raw Tushare-client construction/introspection outside the proxy
"""AST lint (GPT 5-C Major 1): forbid every realistic way to obtain an UNLOCKED Tushare client.

`TushareFetcher.pro` is a locked proxy that serializes + rate-spaces calls across processes (CLAUDE.md
§6.1). Python privacy is DISCIPLINE, not a security boundary (a determined caller can still reach the
raw client via closures/introspection) — this lint makes the bypasses a QA failure. The only allowed
construction site is data_infra/fetchers/__init__.py. Flags, outside it:
  - `ts.pro_api(...)` / `tushare.pro_api(...)` / bare `pro_api(...)` (attribute OR name call)
  - `DataApi(...)` construction (the underlying tushare client class)
  - `from tushare import pro_api|DataApi` (import — catches later aliasing, `pro_api as make; make()`)
  - `.__closure__` access + `object.__getattribute__(x, "_real"|"_base_sleep")` (raw-client introspection)
Exit 1 on any. Wired into run_daily_qa.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {ROOT / "src" / "data_infra" / "fetchers" / "__init__.py"}
SCAN_DIRS = [ROOT / "src", ROOT / "scripts", ROOT / "workspace" / "scripts"]
_RAW_CTORS = {"pro_api", "DataApi"}
_RAW_SLOTS = {"_real", "_base_sleep"}
# raw-slot + closure names that, passed as a string to a getattr-like call, reach the wrapped client
# (object.__getattribute__(x, "_real") / getter(x, "_real") / x.__getattribute__("__closure__"))
_INTROSPECT_STRINGS = _RAW_SLOTS | {"__closure__"}


def _violations(path: Path) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    out = []
    for node in ast.walk(tree):
        # 1. ANY tushare import outside the fetcher. The fetcher is the ONLY legitimate importer, so a
        # blanket ban defeats aliasing the lint can't otherwise follow (`import tushare as ts; make =
        # ts.pro_api; make()`) — GPT REWORK-5 M4.
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tushare" or alias.name.startswith("tushare."):
                    out.append((node.lineno, f"`import {alias.name}` outside the fetcher — Tushare may "
                                             f"only be imported by data_infra/fetchers/__init__.py"))
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "tushare":
            out.append((node.lineno, "`from tushare import ...` outside the fetcher — Tushare may only "
                                     "be imported by data_infra/fetchers/__init__.py"))
        # 2. raw-client construction: pro_api(...) / DataApi(...) as attribute or bare name
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr in _RAW_CTORS:
                out.append((node.lineno, f"{f.attr}() constructs a raw Tushare client (bypasses the proxy)"))
            elif isinstance(f, ast.Name) and f.id in _RAW_CTORS:
                out.append((node.lineno, f"{f.id}() constructs a raw Tushare client (bypasses the proxy)"))
            # 3. a raw-slot / closure string passed to ANY call — catches object.__getattribute__(x,
            # "_real"), an aliased getter(x, "_real"), and x.__getattribute__("__closure__")
            for a in node.args:
                if isinstance(a, ast.Constant) and a.value in _INTROSPECT_STRINGS:
                    out.append((node.lineno, f"a call with the introspection literal {a.value!r} reaches "
                                             f"the raw client behind the proxy"))
        # 4. .__closure__ introspection (reaching the wrapped raw method out of the proxy closure)
        elif isinstance(node, ast.Attribute) and node.attr == "__closure__":
            out.append((node.lineno, ".__closure__ access can extract the raw method from the proxy closure"))
    return out


def main() -> int:
    bad = []
    for d in SCAN_DIRS:
        for py in d.rglob("*.py"):
            if py.resolve() in ALLOWED or "archive" in py.parts:
                continue
            for ln, why in _violations(py):
                bad.append(f"{py.relative_to(ROOT)}:{ln}: {why}")
    if bad:
        print("PRO001 lint FAILED — every Tushare call must flow through TushareFetcher.pro (locked "
              "proxy) / fetch_* methods; do not construct or reach a raw client:", file=sys.stderr)
        for b in bad:
            print("  " + b, file=sys.stderr)
        return 1
    print("PRO001 lint OK: no raw Tushare-client construction/introspection outside the fetcher")
    return 0


if __name__ == "__main__":
    sys.exit(main())
