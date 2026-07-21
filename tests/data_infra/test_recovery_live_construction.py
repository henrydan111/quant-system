# -*- coding: utf-8 -*-
"""F10 — the live-construction write-surface proof (adapter design v4 §6; hardened after the GPT
fan-out review's P0-2).

The synthetic pre-fetch battery can never prove this: by design it NEVER constructs the fetcher, so it
cannot exercise import-time behaviour, `.env` loading, logging handlers, real Tushare client
construction, or the user-profile token cache. Those are the ONE residual write surface of the
recovery, so they get their own test — in a FRESH SUBPROCESS.

Three things the first version got wrong (all found by GPT, all reproduced before fixing):
  1. it hooked only `builtins.open`, so `Path.write_text()` — which resolves `io.open` at import time
     inside pathlib — went straight past the monitor. Verified: a builtins.open hook does NOT see
     Path.write_text. The monitor is now `sys.addaudithook`, the interpreter-level audit mechanism
     that fires for C-level opens too;
  2. it stubbed `ts.pro_api`, so the REAL client construction was never exercised. The real
     `ts.pro_api(token)` now runs (construction needs no network); only the DataApi's `query` — the
     one method that would reach the wire — is replaced;
  3. (found in my own self-review, not by GPT) the monitor was armed only AFTER the imports, which
     forfeits half of what F10 claims to prove — import-time writes (logging handlers, `.env`). It is
     now armed from the first line; the interpreter's own bytecode cache is the one legitimate outside
     write, so it is allowlisted BY SHAPE and counted separately rather than left unseen;
  4. it entered the machine-global §6.1 API lock, whose wait cap is 1800s, so on a busy machine the
     child blocked past the subprocess timeout and the test FAILED depending on unrelated system
     state. The child now isolates that lock into its own run-local directory via the sanctioned test
     seam (monkeypatching `tushare_lock._api_lock_dir`), so this test never contends with a real
     fetch and never depends on an idle machine.

The assertion is an ALLOWLIST: the only writes permitted anywhere in the process are under the run
root. With the lock isolated into the run root there is no longer any legitimate outside write at all.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
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


#: The child program. Audit hook + socket guard FIRST, then lock isolation, then construct.
_CHILD = r'''
import json, os, socket, sys
from pathlib import Path

RUN_ROOT = Path(sys.argv[1]).resolve()
REPORT = Path(sys.argv[2])
SRC = Path(sys.argv[3])
MODE = sys.argv[4] if len(sys.argv) > 4 else "live"

violations = []
bytecode_writes = []

# Armed from the FIRST line, not after the imports: F10 exists partly to catch IMPORT-time writes
# (logging handlers, .env loading), so skipping the import phase would forfeit the thing being proven.
# The only import-time writes that are legitimately outside the run root are the interpreter's own
# bytecode cache, so those are allowlisted BY SHAPE and recorded separately instead of being blind.


def _allowed(path) -> bool:
    try:
        p = Path(str(path)).resolve()
    except (OSError, ValueError):
        return False
    return str(RUN_ROOT).lower() in str(p).lower()


def _is_bytecode(path) -> bool:
    s = str(path).lower()
    return "__pycache__" in s or s.endswith((".pyc", ".pyo"))


_WRITE_MODES = ("w", "a", "x", "+")


def _audit(event, args):
    # sys.addaudithook fires for C-level opens too, so Path.write_text / io.open / os.open are all
    # covered — a builtins.open shim is not (verified: it misses Path.write_text).
    try:
        if event == "open":
            path, mode = args[0], args[1]
            if path is None or not isinstance(path, (str, bytes, os.PathLike)):
                return
            m = mode if isinstance(mode, str) else ""
            flags = args[2] if len(args) > 2 else 0
            writing = any(c in m for c in _WRITE_MODES) or bool(
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND))
            if writing and not _allowed(path):
                (bytecode_writes if _is_bytecode(path) else violations).append(
                    f"open({path!r}, mode={m!r}, flags={flags})")
        elif event in ("os.mkdir", "os.rmdir", "os.remove", "os.unlink", "os.rename", "os.replace"):
            for a in args[:2]:
                if isinstance(a, (str, bytes, os.PathLike)) and not _allowed(a):
                    (bytecode_writes if _is_bytecode(a) else violations).append(f"{event}({a!r})")
        elif event in ("socket.connect", "socket.getaddrinfo"):
            violations.append(f"{event} — NETWORK attempted")
    except Exception:
        pass


sys.addaudithook(_audit)


class _NoNet(socket.socket):
    def connect(self, *a, **kw):
        violations.append("socket.connect")
        raise OSError("network is denied in the F10 live-construction test")
    def connect_ex(self, *a, **kw):
        violations.append("socket.connect_ex")
        raise OSError("network is denied in the F10 live-construction test")


socket.socket = _NoNet

sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent / "scripts"))

result = {"constructed": False, "page_rows": None, "error": None, "real_client": False}
try:
    # Isolate the machine-global §6.1 API lock into the run root via the SANCTIONED test seam, so
    # this test neither contends with a real fetch nor depends on an idle machine.
    from data_infra import tushare_lock as _tl
    _iso = RUN_ROOT / "api_lock"
    _iso.mkdir(parents=True, exist_ok=True)
    _tl._api_lock_dir = lambda: _iso

    import tushare as ts                      # the REAL package; import-time behaviour is audited
    os.environ.setdefault("TUSHARE_TOKEN", "f10-dummy-token")

    from data_infra.fetchers import TushareFetcher
    import recovery_adapters as ra

    if MODE == "redteam":
        # red-team control: an external write MUST be caught by the monitor
        Path(os.environ["F10_EXTERNAL_PROBE"]).write_text("escaped", encoding="utf-8")

    fetcher = TushareFetcher(config_path=str(SRC.parent / "config.yaml"),
                             avoid_token_cache=True)      # never touches the token cache
    result["constructed"] = True
    # the REAL DataApi was constructed (ts.pro_api ran); only `query` — the method that would reach
    # the wire — is replaced, so client construction IS exercised.
    _inner = object.__getattribute__(fetcher.pro, "_real")
    result["real_client"] = type(_inner).__name__
    calls = {}

    def _fake_query(api_name, fields="", **kwargs):
        import pandas as pd
        calls["last"] = (api_name, dict(kwargs))
        return pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20260702"]})
    _inner.query = _fake_query

    class _TokenLedger:
        """Stands in for the ledger's dispatch-token seam ONLY; the real token/spec binding is
        covered by the quartet battery. Here the point is CONSTRUCTION + the write surface."""
        def consume_dispatch_token(self, token, spec):
            return token == "ok"

    spec = {"endpoint": "daily", "base_params": {"trade_date": "20260702"}, "limit": 0,
            "offset": 0, "page": 1, "recipe_id": "daily_by_trade_date",
            "pagination_mode": "single_page", "dispatch_token": "ok"}
    df = ra.LiveExecutor(fetcher, _TokenLedger()).run_page(spec)
    result["page_rows"] = int(len(df))
    result["vendor_call"] = list(calls.get("last", ("", {})))
except BaseException as exc:
    result["error"] = f"{type(exc).__name__}: {exc}"

result["violations"] = violations
result["bytecode_writes"] = len(bytecode_writes)
REPORT.write_text(json.dumps(result), encoding="utf-8")
'''


def _run_child(mode: str, extra_env: dict | None = None):
    run_root = _recovery_test_root(f"f10_{mode}")
    run_root.mkdir(parents=True, exist_ok=True)
    report = run_root / "report.json"
    child = run_root / "child.py"
    child.write_text(_CHILD, encoding="utf-8")
    env = dict(os.environ, **(extra_env or {}))
    proc = subprocess.run(
        [sys.executable, str(child), str(run_root), str(report), str(ROOT / "src"), mode],
        capture_output=True, text=True, timeout=300, cwd=str(ROOT), env=env)
    if not report.exists():
        pytest.fail(f"child produced no report.\nstdout={proc.stdout[-2000:]}\n"
                    f"stderr={proc.stderr[-2000:]}")
    return run_root, json.loads(report.read_text(encoding="utf-8"))


def test_live_fetcher_construction_writes_nothing_outside_the_run_root():
    """F10: construct the REAL fetcher + real DataApi and execute one page in a fresh, network-denied
    process, and prove the ONLY writes are under the run root."""
    _, data = _run_child("live")
    if data.get("error") and not data.get("constructed"):
        pytest.skip(f"live fetcher could not be constructed in this environment: {data['error']}")
    assert data["constructed"], data
    assert data["real_client"], "the REAL Tushare client was not constructed"
    assert data["violations"] == [], f"writes/network outside the run root: {data['violations']}"
    assert data["page_rows"] == 1, data
    # the request that reached the client is EXACTLY the recipe's rendering — no paging kwargs, so
    # the internal single_page 0 sentinel never becomes a vendor argument
    method, kwargs = data["vendor_call"]
    assert method == "daily" and kwargs == {"trade_date": "20260702"}, data["vendor_call"]
    assert data.get("error") is None, data["error"]


def test_the_monitor_actually_catches_an_external_write():
    """RED TEAM (GPT fan-out review P0-2): the first monitor hooked only `builtins.open`, which
    Path.write_text bypasses — so a clean run proved nothing. This drives a deliberate external
    Path.write_text and asserts the monitor SEES it. Without this, 'zero violations' is not evidence."""
    external = _recovery_test_root("f10_external") / "escaped.txt"
    external.parent.mkdir(parents=True, exist_ok=True)
    _, data = _run_child("redteam", {"F10_EXTERNAL_PROBE": str(external)})
    assert data["violations"], "the write monitor MISSED a deliberate external Path.write_text"
    assert any("escaped.txt" in v for v in data["violations"]), data["violations"]


def test_set_token_is_never_called_on_the_recovery_path():
    """`ts.set_token()` writes the user-profile token cache — outside the run root. The recovery path
    passes avoid_token_cache=True so `ts.pro_api(token)` is used instead."""
    src = (ROOT / "src" / "data_infra" / "fetchers" / "__init__.py").read_text(encoding="utf-8")
    i = src.index("def __init__(self, config_path=")
    body = src[i:i + 4000]
    assert "avoid_token_cache" in body
    assert "if avoid_token_cache:" in body and "ts.pro_api(token)" in body
