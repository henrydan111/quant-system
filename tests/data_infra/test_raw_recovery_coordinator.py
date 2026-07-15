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
    shutil.rmtree(base, ignore_errors=True)


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


def test_broken_junction_refused(crun):
    # GPT re-review #3 B3: a BROKEN junction (target missing) — Path.exists() returns False and would
    # SKIP it; os.lstat sees the reparse point and refuses.
    import _winapi
    rp = rrc.RecoveryPaths("brokjunc")
    rp.create_root()
    tgt = rp.root / "tmp_target"
    tgt.mkdir()
    junc = rp.root / "bjunc"
    _winapi.CreateJunction(str(tgt), str(junc))
    tgt.rmdir()  # now the junction is BROKEN (target gone)
    assert junc.exists() is False  # broken -> exists() lies (would SKIP the reparse scan)
    with pytest.raises(RuntimeError, match="reparse point"):
        rp.assert_write(junc / "escaped.txt")


def test_resume_clean_ok_and_tamper_refused(crun):
    rp, led = rrc.open_run("resumerun", new=True)
    # a clean resume re-opens the same run
    rp2, led2 = rrc.open_run("resumerun", new=False)
    assert rp2.run_id == "resumerun"
    # tampering ANY committed row now breaks the hash chain -> resume refuses (stronger than the old
    # run_created-field check; the chain head is anchored outside the jsonl)
    lines = rp.ledger_path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0]); row["baseline_manifest_sha256"] = "0" * 64
    lines[0] = json.dumps(row)
    rp.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="integrity failed|run_created"):
        rrc.open_run("resumerun", new=False)


def _good_contract(tmp_doc: Path) -> dict:
    return {"doc_path": str(tmp_doc.relative_to(rrc.E_ROOT)), "doc_sha256": rrc.sha256_file(tmp_doc),
            "required_fields": ["ts_code", "trade_date", "close"], "natural_key": ["ts_code", "trade_date"],
            "pagination": "single page per trade_date", "rate_limit": "500/min@15000pts",
            "cadence": "daily ~16:00 CST", "pit_anchors": "trade_date session-open-knowable",
            "empty_policy": "dense_refuse", "reviewed_by": "henry",
            "reviewed_at": datetime.now(timezone.utc).isoformat()}


def test_contract_gate_rejects_placeholders_and_bad_docs(tmp_path, monkeypatch):
    # run entirely under tmp_path (no writes into the live E: mirror — GPT re-review #3 minor)
    fake_root = tmp_path
    fake_mirror = fake_root / "Tushare数据接口" / "content"
    fake_mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", fake_mirror)

    def _good(doc):
        return {"doc_path": str(doc.relative_to(fake_root)), "doc_sha256": rrc.sha256_file(doc),
                "required_fields": ["ts_code", "trade_date", "close"], "natural_key": ["ts_code", "trade_date"],
                "pagination": "single page per trade_date", "rate_limit": "500/min@15000pts",
                "cadence": "daily ~16:00 CST", "pit_anchors": "trade_date session-open-knowable",
                "empty_policy": "dense_refuse", "reviewed_by": "henry",
                "reviewed_at": datetime.now(timezone.utc).isoformat()}

    # (a) "x"-stuffed contract (GPT's exact probe) — scalar AND list-element placeholders — refuses
    xstuffed = {k: "x" for k in rrc.CONTRACT_REQUIRED}
    xstuffed["required_fields"] = ["x", "x"]
    xstuffed["natural_key"] = ["x"]
    errs = rrc.contract_errors("daily", xstuffed)
    assert errs and any("placeholder" in e for e in errs)
    # (b) a real doc under the mirror passes
    doc = fake_mirror / "292_report_rc.md"
    doc.write_text("# daily interface doc", encoding="utf-8")
    assert rrc.contract_errors("daily", _good(doc)) == []
    # (c) wrong hash / path-escape / future timestamp all refuse
    assert any("mismatch" in e for e in rrc.contract_errors("daily", dict(_good(doc), doc_sha256="0" * 64)))
    assert any("escapes" in e for e in rrc.contract_errors("daily", dict(_good(doc), doc_path="CLAUDE.md")))
    fut = dict(_good(doc), reviewed_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat())
    assert any("future" in e for e in rrc.contract_errors("daily", fut))


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


def test_spaced_call_rate_limit_backoff_finite(tmp_path, monkeypatch):
    # GPT re-review #3 minor: an inf rate_limit_backoff must NOT persist inf as next-allowed. Drive a
    # rate-limit exception with a non-finite backoff and assert a FINITE cooldown lands.
    from data_infra import tushare_lock
    lockdir = tmp_path / "locks"
    lockdir.mkdir()
    monkeypatch.setattr(tushare_lock, "_api_lock_dir", lambda: lockdir)

    def _boom():
        raise RuntimeError("每分钟最多访问该接口 limit reached")  # matches _is_rate_limit

    for bad in (float("inf"), float("nan"), None):
        with pytest.raises(RuntimeError):
            tushare_lock.spaced_call(_boom, 1.5, rate_limit_backoff=bad)
        import math
        v = float(tushare_lock._next_allowed_path().read_text())
        assert math.isfinite(v), f"rate-limit backoff {bad!r} persisted non-finite next-allowed"
        tushare_lock._next_allowed_path().unlink()
