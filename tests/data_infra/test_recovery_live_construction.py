# -*- coding: utf-8 -*-
"""F10 — the live-construction write-surface proof (adapter design v4 §6).

The synthetic pre-fetch battery can never prove this: by design it NEVER constructs the fetcher, so it
cannot exercise import-time behaviour, `.env` loading, logging handlers, real Tushare client
construction, or the user-profile token cache. Those are the ONE residual write surface of the
recovery, so they get their own test — in a FRESH SUBPROCESS.

History of what this test got wrong, because the pattern matters more than the fixes:

  round 1 (GPT fan-out review P0-2) — it hooked only `builtins.open`, which `Path.write_text` bypasses;
    it stubbed `ts.pro_api` so the REAL client was never constructed; and it entered the machine-global
    §6.1 API lock (1800s wait cap) and blocked past the subprocess timeout on a busy machine.
  round 2 (my own self-review) — the monitor was armed only AFTER the imports, forfeiting the
    import-time writes that are explicitly in its scope.
  round 3 (GPT fan-out re-review #2) — THREE false-negative vectors, all reproduced before fixing:
    (a) `_allowed` tested `str(RUN_ROOT) in str(path)`, a SUBSTRING — so a sibling directory sharing
        the run root's name as a prefix (`<run_root>_escape\\...`) was treated as inside it. This is the
        same "proxy standing in for the fact" defect class the review found in the identity keys;
        containment is now `Path.is_relative_to`, which is the fact itself;
    (b) the bytecode allowlist matched `__pycache__` BY SHAPE anywhere on disk, so an external
        `__pycache__\\escaped.txt` was exempt — and the main test never asserted the exemption count was
        zero, so the escape hatch was unobserved. There is now NO exemption: the child runs with
        PYTHONDONTWRITEBYTECODE=1, which removes the only legitimate outside write, so every outside
        write is a violation;
    (c) a construction failure produced `pytest.skip`. An authorization gate must never go green
        because it could not prove anything — "unable to demonstrate" is a FAILURE here, not a pass.

The assertion is an ALLOWLIST: with bytecode writing disabled and the API lock isolated into the run
root, there is no legitimate write outside the run root at all, so the expected count is exactly zero.

`sys.addaudithook` covers Python-level and C-level `open`, the `os.*` mutation events, sockets, and
process spawning. It is NOT an OS sandbox: a direct `CreateFileW` via ctypes, a write through an
already-established memory mapping, or a write performed inside a spawned child would not be caught by
it. A static scan of the construction path finds none of those, and process spawning is now flagged, so
this is a documented limit of the instrument rather than a known hole in the subject.
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

# Armed from the FIRST line, not after the imports: F10 exists partly to catch IMPORT-time writes
# (logging handlers, .env loading), so skipping the import phase would forfeit the thing being proven.
# The parent sets PYTHONDONTWRITEBYTECODE=1, so there is NO legitimate write outside the run root and
# therefore NO exemption of any kind — an exemption nobody counts is an unobserved escape hatch.


def _allowed(path) -> bool:
    """True iff `path` is genuinely INSIDE the run root.

    Containment, not a substring test: `<run_root>_escape\escaped.txt` contains the run root's string
    but is a sibling directory, and the substring form called it inside (reproduced)."""
    try:
        p = Path(str(path)).resolve()
    except (OSError, ValueError):
        return False
    try:
        return p.is_relative_to(RUN_ROOT)
    except ValueError:
        return False


_WRITE_MODES = ("w", "a", "x", "+")

#: Process spawning: an audit hook does not follow a child, so spawning one is BY DEFINITION an
#: unobservable write surface.
_PROCESS = ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.startfile")

#: DEFAULT-DENY. The previous version enumerated the MUTATING events, so every event it forgot was
#: silently allowed — `Path.touch()` on an existing file fires only `os.utime`, which the list missed
#: (reproduced). Enumerating mutations is unbounded and fails open; enumerating the handful of
#: NON-writing events is bounded and fails closed. Any `os.*`/`shutil.*` event not listed here — today's
#: or a future Python's — is treated as a mutation. Derived by enumerating every os/shutil event that
#: actually fires with an outside path during a real construction run; these four were the whole set,
#: and none of them writes (putenv/unsetenv pass a variable NAME, not a path).
_NON_WRITE_OS_EVENTS = frozenset({
    "os.listdir", "os.scandir", "os.stat", "os.lstat", "os.access", "os.chdir", "os.fwalk",
    "os.getxattr", "os.listxattr", "os.readlink", "os.add_dll_directory",
    "os.putenv", "os.unsetenv",
})


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
                violations.append(f"open({path!r}, mode={m!r}, flags={flags})")
        elif event in ("socket.connect", "socket.getaddrinfo"):
            violations.append(f"{event} — NETWORK attempted")
        elif event in _PROCESS:
            violations.append(f"{event}({args[0]!r}) — SPAWNED a process (write surface not observable)")
        elif event.startswith(("os.", "shutil.")) and event not in _NON_WRITE_OS_EVENTS:
            for a in args[:2]:
                if isinstance(a, (str, bytes, os.PathLike)) and not _allowed(a):
                    violations.append(f"{event}({a!r})")
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

# The parent launches this child with `-S`, so site initialisation has NOT run yet. Python's startup
# (`.pth` handlers, `sitecustomize`) otherwise executes BEFORE this file's first line — a window the
# hook could never see. Reproduced: a `sitecustomize` injected via PYTHONPATH wrote outside the run
# root and F10 reported violations=[]. Running site.main() HERE puts the real startup sequence under
# the hook instead of before it; the environment is still the real one, just observed.
import site
site.main()

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
        # red-team control: the monitor MUST catch this. The probe path is chosen by the parent so the
        # same mode covers a plain outside path, a run-root-prefix sibling, and an external __pycache__.
        probe = Path(os.environ["F10_EXTERNAL_PROBE"])
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("escaped", encoding="utf-8")
    elif MODE == "redteam_touch":
        # the parent PRE-CREATED this file outside the run root. touch() on an existing file fires
        # ONLY os.utime — no `open`, no `os.rename` — which the enumerated mutation list missed.
        Path(os.environ["F10_EXTERNAL_PROBE"]).touch()

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
result["dont_write_bytecode"] = bool(sys.dont_write_bytecode)
REPORT.write_text(json.dumps(result), encoding="utf-8")
'''


#: an mtime far enough in the past that a touch() must move it regardless of filesystem resolution
_OLD_MTIME_NS = 1_000_000_000 * 1_000_000_000


def _run_child(mode: str = "live", probe_from_root=None, startup_inject: bool = False):
    """Run the child in a fresh interpreter. `probe_from_root(run_root) -> Path` picks the red-team
    target, so one mode covers every escape shape. `startup_inject` plants a `sitecustomize` on
    PYTHONPATH that writes the probe during interpreter startup."""
    run_root = _recovery_test_root(f"f10_{mode}")
    run_root.mkdir(parents=True, exist_ok=True)
    report = run_root / "report.json"
    child = run_root / "child.py"
    child.write_text(_CHILD, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"        # removes the only legitimate outside write
    probe = None
    if probe_from_root is not None:
        probe = probe_from_root(run_root)
        env["F10_EXTERNAL_PROBE"] = str(probe)
        probe.parent.mkdir(parents=True, exist_ok=True)
        if mode == "redteam_touch":             # must PRE-EXIST: touch() on a new file also fires open
            probe.write_text("pre-existing", encoding="utf-8")
            os.utime(probe, ns=(_OLD_MTIME_NS, _OLD_MTIME_NS))
    if startup_inject:
        inj = run_root.parent / f"inj_{run_root.name}"
        inj.mkdir(parents=True, exist_ok=True)
        (inj / "sitecustomize.py").write_text(
            "from pathlib import Path\n"
            f"Path(r'{probe}').write_text('escaped at startup', encoding='utf-8')\n",
            encoding="utf-8")
        env["PYTHONPATH"] = str(inj) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        # -S: site initialisation is deferred so the child can install the audit hook FIRST and then
        # run site.main() UNDER it. Without this, .pth handlers and sitecustomize execute before the
        # hook exists and their writes are invisible (reproduced).
        [sys.executable, "-S", str(child), str(run_root), str(report), str(ROOT / "src"), mode],
        capture_output=True, text=True, timeout=300, cwd=str(ROOT), env=env)
    if not report.exists():
        pytest.fail(f"child produced no report.\nstdout={proc.stdout[-2000:]}\n"
                    f"stderr={proc.stderr[-2000:]}")
    return run_root, json.loads(report.read_text(encoding="utf-8")), probe


def test_live_fetcher_construction_writes_nothing_outside_the_run_root():
    """F10: construct the REAL fetcher + real DataApi and execute one page in a fresh, network-denied
    process, and prove the ONLY writes are under the run root."""
    _, data, _ = _run_child("live")
    # A construction failure is a FAILURE, never a skip: this test is a §13 authorization precondition,
    # and a gate that goes green because it could not prove anything is worse than no gate at all.
    assert data.get("error") is None, f"live construction failed: {data['error']}"
    assert data["constructed"], data
    assert data["real_client"], "the REAL Tushare client was not constructed"
    assert data["dont_write_bytecode"], "child must run with PYTHONDONTWRITEBYTECODE=1"
    assert data["violations"] == [], f"writes/network outside the run root: {data['violations']}"
    assert data["page_rows"] == 1, data
    # the request that reached the client is EXACTLY the recipe's rendering — no paging kwargs, so
    # the internal single_page 0 sentinel never becomes a vendor argument
    method, kwargs = data["vendor_call"]
    assert method == "daily" and kwargs == {"trade_date": "20260702"}, data["vendor_call"]


@pytest.mark.parametrize("name,derive", [
    # a plain outside path
    ("plain", lambda r: r.parent / "f10_external_probe" / "escaped.txt"),
    # GPT fan-out re-review #2: a SIBLING whose name has the run root as a string prefix. The old
    # substring containment test called this "inside the run root" and reported no violation.
    ("run_root_prefix_sibling", lambda r: Path(str(r) + "_escape") / "escaped.txt"),
    # GPT fan-out re-review #2: the bytecode allowlist matched __pycache__ ANYWHERE, so this was
    # exempted and merely counted — and nothing asserted the count was zero.
    ("external_pycache", lambda r: r.parent / "__pycache__" / "escaped.txt"),
])
def test_the_monitor_actually_catches_an_external_write(name, derive):
    """RED TEAM. A monitor is only evidence if it demonstrably catches what it claims to catch; each
    of these three shapes produced a FALSE 'no violations' at some point in this test's history."""
    _, data, probe = _run_child("redteam", derive)
    assert probe.exists(), f"[{name}] the probe write did not actually happen — test is vacuous"
    assert data["violations"], f"[{name}] the write monitor MISSED a real external write to {probe}"
    assert any("escaped.txt" in v for v in data["violations"]), (name, data["violations"])


def test_the_monitor_catches_a_touch_of_a_preexisting_external_file():
    """RED TEAM (fan-out re-review #3). `Path.touch()` on an EXISTING file fires only `os.utime` — no
    `open`, no rename — so the enumerated mutation list missed it entirely. The list is now default-deny,
    which catches this and every other mutation event nobody thought to enumerate."""
    _, data, probe = _run_child("redteam_touch", lambda r: r.parent / "f10_touch_probe" / "existing.txt")
    assert probe.exists(), "the pre-existing probe file vanished — test is vacuous"
    assert probe.stat().st_mtime_ns != _OLD_MTIME_NS, "touch() did not actually change mtime"
    assert data["violations"], f"the monitor MISSED a touch() of the external file {probe}"
    assert any("utime" in v for v in data["violations"]), data["violations"]


def test_the_monitor_catches_a_write_during_interpreter_startup():
    """RED TEAM (fan-out re-review #3). `.pth` handlers and `sitecustomize` run BEFORE the child's first
    line, so a write there was invisible. The child now starts under `-S` and calls `site.main()` after
    installing the hook, putting the real startup sequence under observation instead of ahead of it."""
    _, data, probe = _run_child("live", lambda r: r.parent / "f10_startup_probe" / "startup_escaped.txt",
                                startup_inject=True)
    assert probe.exists(), "the startup write did not actually happen — test is vacuous"
    assert data["violations"], f"the monitor MISSED a startup-time write to {probe}"
    assert any("startup_escaped" in v for v in data["violations"]), data["violations"]
    # and the real construction still happened under -S + site.main()
    assert data["constructed"] and data["real_client"] == "DataApi", data


def test_set_token_is_never_called_on_the_recovery_path():
    """`ts.set_token()` writes the user-profile token cache — outside the run root. The recovery path
    passes avoid_token_cache=True so `ts.pro_api(token)` is used instead."""
    src = (ROOT / "src" / "data_infra" / "fetchers" / "__init__.py").read_text(encoding="utf-8")
    i = src.index("def __init__(self, config_path=")
    body = src[i:i + 4000]
    assert "avoid_token_cache" in body
    assert "if avoid_token_cache:" in body and "ts.pro_api(token)" in body
