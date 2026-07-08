"""B7/B4 + R2-B2 + R3-B1: forward attempts are APPEND-ONLY, ledger-counted
research events — a published cycle can never be re-decided; a `started`
(non-terminal, partial-spend) attempt can NEVER be bypassed, even explicitly;
the ledger is a START-GATE cross-checked against the attempt dirs (a deleted
dir with a ledger record refuses forever)."""
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


def _ledger(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / "attempts_ledger.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return p


def _empty_ledger(tmp_path: Path) -> Path:
    return tmp_path / "no_ledger.jsonl"          # nonexistent = empty


def _mk_sealed_terminal(fwd, cycles_root: Path, cycle: str, att_id: str,
                        status: str) -> tuple[Path, Path]:
    """A terminal attempt SEALED per R4-B1: terminal manifest + ledger hash."""
    d = _mk_attempt(cycles_root, cycle, att_id, status)
    (d / "some_artifact.json").write_text('{"x": 1}', encoding="utf-8")
    h = fwd.write_terminal_attempt_manifest(
        d, cycle=cycle, decision_id=att_id, terminal_status=status, reason="r")
    ledger = _ledger(cycles_root, [
        {"event": "attempt_started", "cycle": cycle, "decision_id": att_id},
        {"event": "attempt_failed", "cycle": cycle, "decision_id": att_id,
         "terminal_attempt_manifest_hash": h},
    ])
    return d, ledger


def test_fresh_cycle_allowed(fwd, tmp_path):
    fwd.ensure_attempt_allowed(tmp_path, "202608",
                               ledger_path=_empty_ledger(tmp_path))


def test_published_attempt_refuses_forever(fwd, tmp_path):
    _mk_attempt(tmp_path, "202608", "aaaa", "published")
    for na in (False, True):
        with pytest.raises(fwd.ForwardGateError, match="PUBLISHED"):
            fwd.ensure_attempt_allowed(tmp_path, "202608", new_attempt=na,
                                       ledger_path=_empty_ledger(tmp_path))


def test_started_attempt_cannot_be_bypassed_even_explicitly(fwd, tmp_path):
    # R3 Blocker-1: a partial LLM spend is NON-TERMINAL — --new-attempt must NOT work
    _mk_attempt(tmp_path, "202609", "bbbb", "started")
    for na in (False, True):
        with pytest.raises(fwd.ForwardGateError, match="NON-TERMINAL"):
            fwd.ensure_attempt_allowed(tmp_path, "202609", new_attempt=na,
                                       ledger_path=_empty_ledger(tmp_path))


def test_failed_attempt_blocks_silent_retry_but_allows_explicit_when_sealed(fwd, tmp_path):
    _, ledger = _mk_sealed_terminal(fwd, tmp_path, "202610", "cccc", "failed")
    with pytest.raises(fwd.ForwardGateError, match="new-attempt"):
        fwd.ensure_attempt_allowed(tmp_path, "202610", ledger_path=ledger)
    fwd.ensure_attempt_allowed(tmp_path, "202610", new_attempt=True,
                               ledger_path=ledger)


def test_abandoned_attempt_is_terminal_retryable_when_sealed(fwd, tmp_path):
    _, ledger = _mk_sealed_terminal(fwd, tmp_path, "202611", "dddd",
                                    "abandoned_due_to_crash")
    fwd.ensure_attempt_allowed(tmp_path, "202611", new_attempt=True,
                               ledger_path=ledger)


# ------------------------ R4 Blocker-1: terminal seals ----------------------

def test_unsealed_terminal_attempt_refuses_retry(fwd, tmp_path):
    _mk_attempt(tmp_path, "202614", "gggg", "failed")   # no seal, no ledger hash
    with pytest.raises(fwd.ForwardGateError, match="unsealed"):
        fwd.ensure_attempt_allowed(tmp_path, "202614", new_attempt=True,
                                   ledger_path=_empty_ledger(tmp_path))


def test_tampered_terminal_manifest_refuses_retry(fwd, tmp_path):
    d, _ = _mk_sealed_terminal(fwd, tmp_path, "202615", "hhhh", "failed")
    ledger = _ledger(tmp_path, [
        {"event": "attempt_failed", "cycle": "202615", "decision_id": "hhhh",
         "terminal_attempt_manifest_hash": "0" * 64},   # ledger says different
    ])
    with pytest.raises(fwd.ForwardGateError, match="does not match the"):
        fwd.ensure_attempt_allowed(tmp_path, "202615", new_attempt=True,
                                   ledger_path=ledger)


def test_modified_artifact_after_sealing_refuses_retry(fwd, tmp_path):
    d, ledger = _mk_sealed_terminal(fwd, tmp_path, "202616", "iiii", "failed")
    (d / "some_artifact.json").write_text('{"x": 2}', encoding="utf-8")  # tamper
    with pytest.raises(fwd.ForwardGateError, match="after sealing"):
        fwd.ensure_attempt_allowed(tmp_path, "202616", new_attempt=True,
                                   ledger_path=ledger)


def test_seal_roundtrip_hashes_whole_tree(fwd, tmp_path):
    d = _mk_attempt(tmp_path, "202617", "jjjj", "failed")
    sub = d / "names" / "000001_SZ"
    sub.mkdir(parents=True)
    (sub / "extract_response_raw.json").write_text('{"r": 1}', encoding="utf-8")
    h = fwd.write_terminal_attempt_manifest(
        d, cycle="202617", decision_id="jjjj", terminal_status="failed", reason="r")
    tm = json.loads((d / "terminal_attempt_manifest.json").read_text(encoding="utf-8"))
    assert "names/000001_SZ/extract_response_raw.json" in tm["artifact_hashes"]
    assert "attempt_manifest.json" in tm["artifact_hashes"]
    fwd.verify_terminal_attempt_seal(d, h)              # intact -> no raise


def test_ledger_record_with_missing_dir_refuses(fwd, tmp_path):
    # R3 Blocker-1: manual deletion of an attempt dir = evidence breach
    ledger = _ledger(tmp_path, [{"event": "attempt_started", "cycle": "202612",
                                 "decision_id": "eeee"}])
    with pytest.raises(fwd.ForwardGateError, match="evidence breach"):
        fwd.ensure_attempt_allowed(tmp_path, "202612", new_attempt=True,
                                   ledger_path=ledger)


def test_attempt_dir_without_manifest_refuses(fwd, tmp_path):
    d = tmp_path / "202613" / "attempt_ffff"
    d.mkdir(parents=True)                          # torn: no attempt_manifest.json
    with pytest.raises(fwd.ForwardGateError, match="torn attempt"):
        fwd.ensure_attempt_allowed(tmp_path, "202613",
                                   ledger_path=_empty_ledger(tmp_path))


def test_write_json_atomic_no_partial_file(fwd, tmp_path):
    p = tmp_path / "x.json"
    fwd.write_json_atomic(p, {"a": 1})
    fwd.write_json_atomic(p, {"a": 2})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 2}
    assert not list(tmp_path.glob("*.tmp"))


# ---------------------- R5 Blocker-1: published seal -------------------------

def _mk_published(fwd, cycles_root: Path, cycle: str, att_id: str):
    d = _mk_attempt(cycles_root, cycle, att_id, "published")
    (d / "decision.json").write_text('{"legs": {}}', encoding="utf-8")
    (d / "manifest.json").write_text('{"decision_id": "x"}', encoding="utf-8")
    h = fwd.write_published_attempt_seal(d, cycle=cycle, decision_id=att_id)
    return d, h


def test_published_seal_roundtrip_and_fill_record_excluded(fwd, tmp_path):
    d, h = _mk_published(fwd, tmp_path, "202620", "pppp")
    fwd.verify_published_attempt_seal(d, h)             # intact -> no raise
    # a later fill_record must NOT break the pre-fill seal
    (d / "fill_record.json").write_text('{"fills": {}}', encoding="utf-8")
    fwd.verify_published_attempt_seal(d, h)
    # attempt_manifest status flip is ledger-protected, not seal-protected
    (d / "attempt_manifest.json").write_text(
        json.dumps({"status": "published", "published_attempt_seal_hash": h}),
        encoding="utf-8")
    fwd.verify_published_attempt_seal(d, h)


def test_tampered_published_decision_refuses(fwd, tmp_path):
    d, h = _mk_published(fwd, tmp_path, "202621", "qqqq")
    (d / "decision.json").write_text('{"legs": {"ai_book": ["HACKED"]}}',
                                     encoding="utf-8")
    with pytest.raises(fwd.ForwardGateError, match="after sealing"):
        fwd.verify_published_attempt_seal(d, h)


def test_unsealed_or_ledger_missing_published_refuses(fwd, tmp_path):
    d = _mk_attempt(tmp_path, "202622", "rrrr", "published")
    (d / "decision.json").write_text("{}", encoding="utf-8")
    with pytest.raises(fwd.ForwardGateError, match="unsealed decision"):
        fwd.verify_published_attempt_seal(d, "0" * 64)
    h = fwd.write_published_attempt_seal(d, cycle="202622", decision_id="rrrr")
    with pytest.raises(fwd.ForwardGateError, match="unsealed publication"):
        fwd.verify_published_attempt_seal(d, None)      # ledger lacks the hash
    with pytest.raises(fwd.ForwardGateError, match="does not match"):
        fwd.verify_published_attempt_seal(d, "0" * 64)  # ledger disagrees
    fwd.verify_published_attempt_seal(d, h)


def test_decision_id_derivation_is_pinned(fwd):
    a = fwd.compute_decision_id("202608", "2026-08-03T20:45:00+08:00", "abcd1234", "deadbeef")
    b = fwd.compute_decision_id("202608", "2026-08-03T20:45:00+08:00", "abcd1234", "deadbeef")
    c = fwd.compute_decision_id("202608", "2026-08-03T20:45:01+08:00", "abcd1234", "deadbeef")
    assert a == b and a != c and len(a) == 16
