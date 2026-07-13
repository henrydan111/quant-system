"""Recovery coordinator v3 battery (GPT recovery re-review #2: B1 containment probes, B3 ledger
transitions, B4 contract-gate negatives, non-finite throttle minor). Everything network-free; test
runs live under C:\\quant_recovery\\runs_test\\<uuid> (C: is the sanctioned recovery area; E: must
never be written by the coordinator)."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("rrc", ROOT / "scripts" / "raw_recovery_coordinator.py")
rrc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rrc)


@pytest.fixture()
def crun(monkeypatch):
    """Isolated RECOVERY_ROOT on C: (the sanctioned recovery drive), cleaned up after."""
    base = Path(r"C:\quant_recovery") / "runs_test" / uuid.uuid4().hex
    monkeypatch.setattr(rrc, "RECOVERY_ROOT", base)
    yield base
    shutil.rmtree(base.parent if base.parent.name == uuid.uuid4().hex else base, ignore_errors=True)


# ── B1: run-id + containment probes (GPT's exact escapes) ────────────────────────────────────────
def test_run_id_traversal_and_special_forms_refused(crun):
    for bad in (r"..\escape", r"..\..\Users\henry\recovery_escape", "..", "a/b", "a\\b",
                "C:abs", r"\\server\share", "con:stream", ".hidden", "a" * 65, ""):
        with pytest.raises(SystemExit, match="REFUSED"):
            rrc.RecoveryPaths(bad)


def test_assert_write_lexical_containment(crun):
    rp = rrc.RecoveryPaths("okrun")
    rp.create_root()
    # inside: ok
    p = rp.assert_write(rp.reports / "x.json")
    assert str(p).startswith(str(rp.root))
    # lexical .. escape refused BEFORE any resolve
    with pytest.raises(RuntimeError, match="outside run root"):
        rp.assert_write(rp.root / ".." / "sibling" / "f.txt")
    # sibling-prefix dir (quant_recovery_evil-style) refused
    with pytest.raises(RuntimeError, match="outside run root"):
        rp.assert_write(Path(str(rp.root) + "_evil") / "f.txt")
    # E: and UNC refused
    with pytest.raises(RuntimeError):
        rp.assert_write(Path(r"E:\量化系统\data\x.parquet"))
    with pytest.raises(RuntimeError, match="outside run root"):
        rp.assert_write(Path(r"\\srv\share\f"))


@pytest.mark.skipif(not hasattr(Path("."), "is_junction"), reason="needs Path.is_junction (3.12+)")
def test_reparse_point_in_ancestry_refused(crun):
    import _winapi
    rp = rrc.RecoveryPaths("jrun")
    rp.create_root()
    target = rp.root / "realdir"
    target.mkdir()
    junc = rp.root / "junc"
    _winapi.CreateJunction(str(target), str(junc))  # junction INSIDE the run root
    with pytest.raises(RuntimeError, match="reparse point"):
        rp.assert_write(junc / "f.txt")


def test_resume_requires_valid_run_created_record(crun):
    rp, led = rrc.open_run("resumerun", new=True)
    # tamper: rewrite run_created with a wrong baseline hash
    lines = rp.ledger_path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["baseline_manifest_sha256"] = "0" * 64
    rp.ledger_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="run_created"):
        rrc.open_run("resumerun", new=False)


# ── B3: ledger transitions / verification / consolidation ───────────────────────────────────────
def _fresh(crun, name="ledrun"):
    rp, led = rrc.open_run(name, new=True)
    rid = rrc.request_id("daily", {"trade_date": "20260702"}, "20260702")
    rid2 = rrc.request_id("moneyflow", {"trade_date": "20260702"}, "20260702")
    led.freeze_plan([
        {"request_id": rid, "endpoint": "daily", "dataset": "daily", "params": {"trade_date": "20260702"},
         "partition": "20260702", "empty_policy": "dense_refuse"},
        {"request_id": rid2, "endpoint": "moneyflow", "dataset": "moneyflow",
         "params": {"trade_date": "20260702"}, "partition": "20260702", "empty_policy": "sparse_canary"},
    ])
    return rp, led, rid, rid2


def test_plan_freeze_is_once_and_hash_checked(crun):
    rp, led, rid, _ = _fresh(crun)
    with pytest.raises(RuntimeError, match="already frozen"):
        led.freeze_plan([])
    # tamper the plan file -> hash mismatch refuses everything
    plan = json.loads(rp.plan_path.read_text(encoding="utf-8"))
    plan["rows"][0]["params"] = {"trade_date": "20990101"}
    rp.plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        led.record_attempt(rid, "daily", {}, 1, "success", "t")


def test_unplanned_request_refused(crun):
    _, led, *_ = _fresh(crun, "ledrun2")
    with pytest.raises(RuntimeError, match="not in the frozen plan"):
        led.record_attempt("deadbeef" * 3, "daily", {}, 1, "success", "t")


def test_verified_requires_real_contained_hashed_output(crun):
    rp, led, rid, _ = _fresh(crun, "ledrun3")
    led.record_attempt(rid, "daily", {"trade_date": "20260702"}, 1, "success", "t")
    # no file -> refuse
    with pytest.raises(RuntimeError, match="verified"):
        led.record_verdict(rid, "verified", output_path=str(rp.staging_data / "missing.parquet"),
                           output_sha256="0" * 64, schema_fingerprint="f", key_stats={})
    # real contained file with matching hash -> accepted
    out = rp.staging_data / "market" / "daily" / "2026" / "daily_20260702.parquet"
    out.parent.mkdir(parents=True)
    out.write_bytes(b"DATA")
    led.record_verdict(rid, "verified", output_path=str(out), output_sha256=rrc.sha256_file(out),
                       schema_fingerprint="cols:v1", key_stats={"null_keys": 0, "dup_groups": 0})
    # terminal: further transitions refused
    with pytest.raises(RuntimeError, match="already terminal|invalid transition"):
        led.record_attempt(rid, "daily", {}, 2, "success", "t")


def test_dense_empty_refused_sparse_needs_canary_and_repeat(crun):
    rp, led, rid, rid2 = _fresh(crun, "ledrun4")
    led.record_attempt(rid, "daily", {}, 1, "success", "t")
    with pytest.raises(RuntimeError, match="NEVER"):
        led.record_verdict(rid, "confirmed_empty")            # dense dataset -> never empty
    led.record_attempt(rid2, "moneyflow", {}, 1, "success", "t")
    with pytest.raises(RuntimeError, match="canary"):
        led.record_verdict(rid2, "confirmed_empty")           # sparse without canary/repeat -> refuse
    led.record_verdict(rid2, "confirmed_empty", canary_request_id=rid, repeat_confirmed=True)


def test_torn_ledger_tail_fails_closed(crun):
    rp, led, rid, _ = _fresh(crun, "ledrun5")
    with open(rp.ledger_path, "a", encoding="utf-8") as fh:
        fh.write('{"kind": "attempt", "request_id": "x", TRUNCAT')
    with pytest.raises(RuntimeError, match="torn|malformed"):
        led.record_attempt(rid, "daily", {}, 1, "success", "t")


def test_consolidation_gate_requires_all_terminal(crun):
    rp, led, rid, rid2 = _fresh(crun, "ledrun6")
    ok, pending = led.consolidation_allowed("daily")
    assert ok is False and rid in pending
    led.record_attempt(rid, "daily", {}, 1, "success", "t")
    out = rp.staging_data / "d.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"D")
    led.record_verdict(rid, "verified", output_path=str(out), output_sha256=rrc.sha256_file(out),
                       schema_fingerprint="f", key_stats={})
    ok, pending = led.consolidation_allowed("daily")
    assert ok is True and not pending


# ── B4: contract gate negatives ──────────────────────────────────────────────────────────────────
def _good_contract(tmp_doc: Path) -> dict:
    return {"doc_path": str(tmp_doc.relative_to(rrc.E_ROOT)), "doc_sha256": rrc.sha256_file(tmp_doc),
            "required_fields": ["ts_code", "trade_date", "close"], "natural_key": ["ts_code", "trade_date"],
            "pagination": "single page per trade_date", "rate_limit": "500/min@15000pts",
            "cadence": "daily ~16:00 CST", "pit_anchors": "trade_date session-open-knowable",
            "empty_policy": "dense_refuse", "reviewed_by": "henry",
            "reviewed_at": datetime.now(timezone.utc).isoformat()}


def test_contract_gate_rejects_placeholders_and_bad_docs(tmp_path):
    # placeholders ("x") must NOT satisfy the gate (GPT B4's exact probe)
    errs = rrc.contract_errors("daily", {k: "x" for k in rrc.CONTRACT_REQUIRED})
    assert errs and any("placeholder" in e for e in errs)
    # a real doc under the mirror passes...
    doc = rrc.DOC_MIRROR / "_test_contract_doc.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# daily interface doc", encoding="utf-8")
    try:
        good = _good_contract(doc)
        assert rrc.contract_errors("daily", good) == []
        # ...wrong hash refuses
        bad = dict(good, doc_sha256="0" * 64)
        assert any("mismatch" in e for e in rrc.contract_errors("daily", bad))
        # ...path escaping the mirror refuses
        esc = dict(good, doc_path="CLAUDE.md")
        assert any("escapes" in e for e in rrc.contract_errors("daily", esc))
        # ...future review timestamp refuses
        fut = dict(good, reviewed_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat())
        assert any("future" in e for e in rrc.contract_errors("daily", fut))
    finally:
        doc.unlink(missing_ok=True)


def test_endpoint_matrix_unique_owner_per_output():
    seen = {}
    for row in rrc.ENDPOINT_MATRIX:
        key = (row["endpoint"], tuple(row["outputs"]))
        assert seen.setdefault(key, row["owner"]) == row["owner"], f"duplicate owner for {key}"
    # indicators has exactly ONE owner (GPT B2)
    ind = [r for r in rrc.ENDPOINT_MATRIX if "fina_indicator" in r["endpoint"]]
    assert len(ind) == 1 and ind[0]["owner"] == "A07"


# ── minor: non-finite throttle input ─────────────────────────────────────────────────────────────
def test_spaced_call_rejects_non_finite_base_sleep(tmp_path, monkeypatch):
    import time as _time
    from data_infra import tushare_lock
    lockdir = tmp_path / "locks"
    lockdir.mkdir()
    monkeypatch.setattr(tushare_lock, "_api_lock_dir", lambda: lockdir)
    for bad in (float("nan"), float("inf"), float("-inf"), -5, 0, None):
        t0 = _time.time()
        tushare_lock.spaced_call(lambda: "ok", bad)
        nxt = float(tushare_lock._next_allowed_path().read_text())
        assert nxt - t0 >= tushare_lock.MIN_BASE_SLEEP - 0.05, f"cooldown not floored for {bad!r}"
        tushare_lock._next_allowed_path().unlink()  # isolate iterations (no cross-wait)
