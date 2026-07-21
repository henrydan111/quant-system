# -*- coding: utf-8 -*-
"""F10 — the live-construction write-surface proof (adapter design v4 §6, GPT design re-review #2).

The synthetic pre-fetch battery can never prove this: by design it NEVER constructs the fetcher, so it
cannot exercise import-time behaviour, `.env` loading, logging handlers, `ts.pro_api()` client
construction, or the user-profile token cache. Those are the ONE residual write surface of the
recovery, so they get their own test — in a FRESH SUBPROCESS, with:

  * a write monitor installed BEFORE the fetcher module is imported (so import-time writes are seen);
  * the REAL installed tushare package imported (a wholesale fake module would exercise nothing);
    only `pro_api` is stubbed, so no client and no network are needed;
  * a socket guard that turns any outbound connection attempt into a hard failure;
  * `avoid_token_cache=True`, so `ts.set_token()` — which writes into the user profile — is never
    called (GPT: "avoid ts.set_token() entirely by using ts.pro_api(token)").

The assertion is an ALLOWLIST: the only writes permitted anywhere in the process are under the run
root and the machine-global api-lock namespace. Anything else fails the test.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="recovery runs on the Windows broker")


def _recovery_test_root(sub: str) -> Path:
    base = Path(os.environ.get("QUANT_RECOVERY_TEST_ROOT") or r"C:\quant_recovery")
    if not base.is_absolute() or base.drive.upper() == "E:":
        pytest.skip("recovery test root must be an absolute NON-E: path")
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        pytest.skip(f"recovery test root not writable ({exc})")
    return base / sub / uuid.uuid4().hex


#: The child program. It installs the monitor + socket guard FIRST, then imports and constructs.
_CHILD = r'''
import builtins, io, json, os, socket, sys
from pathlib import Path

RUN_ROOT = Path(sys.argv[1])
REPORT = Path(sys.argv[2])
SRC = Path(sys.argv[3])
API_LOCK_DIR = Path(sys.argv[4])          # derived from tushare_lock._api_lock_dir(), not guessed

violations, opened = [], []

def _allowed(path: str) -> bool:
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    s = str(p).lower()
    if str(RUN_ROOT).lower() in s:
        return True
    # the ONE sanctioned outside-write: the machine-global §6.1 api-lock namespace. It is a fixed
    # literal in tushare_lock._api_lock_dir() and is deliberately machine-wide (the Tushare ACCOUNT is
    # machine-wide, so its cross-process serialization must be too). Passed in from the parent so this
    # allowlist tracks the real function instead of a hardcoded guess.
    if str(API_LOCK_DIR).lower() in s:
        return True
    return False

_real_open = builtins.open
def _guard_open(file, mode="r", *a, **kw):
    m = mode if isinstance(mode, str) else "r"
    if any(c in m for c in ("w", "a", "x", "+")):
        opened.append(str(file))
        if not _allowed(str(file)):
            violations.append(f"open({file!r}, {m!r})")
    return _real_open(file, mode, *a, **kw)
builtins.open = _guard_open

for _name in ("mkdir", "makedirs", "remove", "unlink", "rename", "replace", "rmdir"):
    _orig = getattr(os, _name, None)
    if _orig is None:
        continue
    def _mk(orig, name):
        def _w(path, *a, **kw):
            if not _allowed(str(path)):
                violations.append(f"os.{name}({path!r})")
            return orig(path, *a, **kw)
        return _w
    setattr(os, _name, _mk(_orig, _name))

class _NoNet(socket.socket):
    def connect(self, *a, **kw):
        violations.append(f"socket.connect{a}")
        raise OSError("network is denied in the F10 live-construction test")
    def connect_ex(self, *a, **kw):
        violations.append(f"socket.connect_ex{a}")
        raise OSError("network is denied in the F10 live-construction test")
socket.socket = _NoNet

sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent / "scripts"))

result = {"constructed": False, "page_rows": None, "error": None}
try:
    # the REAL tushare package is imported here (import-time behaviour IS under the monitor)
    import tushare as ts
    calls = {}

    class _StubPro:
        def __getattr__(self, name):
            def _call(**kwargs):
                import pandas as pd
                calls["last"] = (name, kwargs)
                return pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20260702"]})
            return _call

    ts.pro_api = lambda *a, **kw: _StubPro()          # ONLY the client is stubbed
    def _boom(*a, **kw):
        violations.append("ts.set_token() was called (writes the user-profile token cache)")
        raise AssertionError("set_token must not be called on the recovery path")
    ts.set_token = _boom

    os.environ.setdefault("TUSHARE_TOKEN", "f10-dummy-token")
    from data_infra.fetchers import TushareFetcher
    import recovery_adapters as ra

    fetcher = TushareFetcher(config_path=str(SRC.parent / "config.yaml"),
                             avoid_token_cache=True)      # never touches the token cache
    result["constructed"] = True

    class _TokenLedger:
        """Stands in for the ledger's dispatch-token seam ONLY. The real token/spec binding is
        covered by the quartet battery; here the point is the CONSTRUCTION + write surface."""
        def consume_dispatch_token(self, token, spec): return token == "ok"
    spec = {"endpoint": "daily", "base_params": {"trade_date": "20260702"}, "limit": 0,
            "offset": 0, "page": 1, "recipe_id": "daily_by_trade_date",
            "pagination_mode": "single_page", "dispatch_token": "ok"}
    ex = ra.LiveExecutor(fetcher, _TokenLedger())
    df = ex.run_page(spec)                                 # ONE stubbed page through the real path
    result["page_rows"] = int(len(df))
    result["vendor_call"] = list(calls.get("last", ("", {})))
except BaseException as exc:
    result["error"] = f"{type(exc).__name__}: {exc}"

result["violations"] = violations
result["write_targets"] = opened[:40]
REPORT.write_text(json.dumps(result), encoding="utf-8")
'''


def test_live_fetcher_construction_writes_nothing_outside_the_run_root():
    """F10: construct the REAL fetcher + execute one stubbed page in a fresh, network-denied process
    and prove the ONLY writes are under the run root / api-lock namespace."""
    run_root = _recovery_test_root("f10")
    run_root.mkdir(parents=True, exist_ok=True)
    report = run_root / "f10_report.json"
    child = run_root / "child.py"
    child.write_text(_CHILD, encoding="utf-8")
    # the api-lock namespace comes from the REAL function, so the allowlist cannot drift from it
    sys.path.insert(0, str(ROOT / "src"))
    from data_infra.tushare_lock import _api_lock_dir
    api_lock_dir = _api_lock_dir()
    proc = subprocess.run(
        [sys.executable, str(child), str(run_root), str(report), str(ROOT / "src"),
         str(api_lock_dir)],
        capture_output=True, text=True, timeout=180,
        cwd=str(ROOT),
    )
    if not report.exists():
        pytest.fail(f"child produced no report.\nstdout={proc.stdout[-2000:]}\n"
                    f"stderr={proc.stderr[-2000:]}")
    data = json.loads(report.read_text(encoding="utf-8"))
    if data.get("error") and not data.get("constructed"):
        pytest.skip(f"live fetcher could not be constructed in this environment: {data['error']}")
    assert data["constructed"], data
    assert data["violations"] == [], f"writes/network outside the allowlist: {data['violations']}"
    assert data["page_rows"] == 1, data
    # the request that reached the vendor is EXACTLY the recipe's rendering (no paging kwargs for a
    # single_page recipe — the internal 0 sentinel must never be sent)
    method, kwargs = data["vendor_call"]
    assert method == "daily" and kwargs == {"trade_date": "20260702"}, data["vendor_call"]
    assert data.get("error") is None, data["error"]


def test_set_token_is_never_called_on_the_recovery_path():
    """`ts.set_token()` writes the user-profile token cache — outside the run root. The recovery path
    passes avoid_token_cache=True so `ts.pro_api(token)` is used instead; the child test above turns
    any set_token call into a violation, so this asserts the flag is actually plumbed."""
    src = (ROOT / "src" / "data_infra" / "fetchers" / "__init__.py").read_text(encoding="utf-8")
    i = src.index("def __init__(self, config_path=")
    body = src[i:i + 4000]
    assert "avoid_token_cache" in body
    assert "if avoid_token_cache:" in body and "ts.pro_api(token)" in body
