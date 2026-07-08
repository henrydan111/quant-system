"""B7/B4 + R2 Blocker-2: forward attempts are APPEND-ONLY, ledger-counted
research events — a published cycle can never be re-decided; a failed attempt
blocks silent retries (explicit --new-attempt only); attempt state files are
written atomically."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

SCRIPT = (PROJECT_ROOT / "workspace" / "research" / "mvp_pool_book"
          / "run_forward_cycle.py")


@pytest.fixture(scope="module")
def fwd():
    spec = importlib.util.spec_from_file_location("run_forward_cycle_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk_attempt(cycles_root: Path, cycle: str, att_id: str, status: str):
    d = cycles_root / cycle / f"attempt_{att_id}"
    d.mkdir(parents=True)
    (d / "attempt_manifest.json").write_text(
        json.dumps({"status": status}), encoding="utf-8")
    return d


def test_fresh_cycle_allowed(fwd, tmp_path):
    fwd.ensure_attempt_allowed(tmp_path, "202608")   # no raise


def test_published_attempt_refuses_forever(fwd, tmp_path):
    _mk_attempt(tmp_path, "202608", "aaaa", "published")
    with pytest.raises(fwd.ForwardGateError, match="PUBLISHED"):
        fwd.ensure_attempt_allowed(tmp_path, "202608")
    # even an explicit new attempt cannot re-decide a published cycle
    with pytest.raises(fwd.ForwardGateError, match="PUBLISHED"):
        fwd.ensure_attempt_allowed(tmp_path, "202608", new_attempt=True)


def test_failed_attempt_blocks_silent_retry_but_allows_explicit(fwd, tmp_path):
    _mk_attempt(tmp_path, "202609", "bbbb", "failed")
    with pytest.raises(fwd.ForwardGateError, match="new-attempt"):
        fwd.ensure_attempt_allowed(tmp_path, "202609")
    fwd.ensure_attempt_allowed(tmp_path, "202609", new_attempt=True)   # explicit OK


def test_started_attempt_also_blocks_silent_retry(fwd, tmp_path):
    # a crashed-before-terminal attempt is still a spend — no silent rerun
    _mk_attempt(tmp_path, "202610", "cccc", "started")
    with pytest.raises(fwd.ForwardGateError, match="new-attempt"):
        fwd.ensure_attempt_allowed(tmp_path, "202610")


def test_write_json_atomic_no_partial_file(fwd, tmp_path):
    p = tmp_path / "x.json"
    fwd.write_json_atomic(p, {"a": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}
    fwd.write_json_atomic(p, {"a": 2})               # atomic overwrite
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 2}
    assert not list(tmp_path.glob("*.tmp"))          # no leftovers


def test_decision_id_derivation_is_pinned(fwd):
    a = fwd.compute_decision_id("202608", "2026-08-03T20:45:00+08:00", "abcd1234", "deadbeef")
    b = fwd.compute_decision_id("202608", "2026-08-03T20:45:00+08:00", "abcd1234", "deadbeef")
    c = fwd.compute_decision_id("202608", "2026-08-03T20:45:01+08:00", "abcd1234", "deadbeef")
    assert a == b and a != c and len(a) == 16
