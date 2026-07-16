"""Page-receipt ledger (GPT recovery re-review #4 B2): coordinator-owned receipts, contiguous-page +
terminal proof, null-key/dup rejection, chain tamper detection, distinct-empty canary. Runs under C:."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
# NOTE: register each dynamically-loaded module in sys.modules BEFORE exec — a frozen dataclass under
# `from __future__ import annotations` resolves its annotations via sys.modules[cls.__module__], which is
# None mid-exec otherwise. Without this the suite only collected when another test happened to import
# the coordinator first (GPT re-review #5 MINOR: the batteries were not independent).
_c = importlib.util.spec_from_file_location("rrc", ROOT / "scripts" / "raw_recovery_coordinator.py")
rrc = importlib.util.module_from_spec(_c); sys.modules["rrc"] = rrc; _c.loader.exec_module(rrc)
_l = importlib.util.spec_from_file_location("rl", ROOT / "scripts" / "recovery_ledger.py")
rl = importlib.util.module_from_spec(_l); sys.modules["rl"] = rl; _l.loader.exec_module(rl)

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="needs the Windows no-follow broker")


@pytest.fixture()
def led(monkeypatch):
    base = Path(r"C:\quant_recovery") / "ledgertest" / uuid.uuid4().hex
    monkeypatch.setattr(rrc, "RECOVERY_ROOT", base)
    rp = rrc.RecoveryPaths("led")
    rp.create_root()
    ledger = rl.PageReceiptLedger(rp, coordinator_commit="deadbeef", adapter_bundle_hash="abc123")
    yield rp, ledger
    shutil.rmtree(base, ignore_errors=True)


def _plan_row(endpoint, part, out, *, empty="dense_refuse", limit=2, dedup=None, base_dups=False,
              nk=("ts_code", "trade_date")):
    params = {"trade_date": part}
    return {"request_id": rl.request_id(endpoint, params, part), "endpoint": endpoint, "dataset": endpoint,
            "params": params, "partition": part, "empty_policy": empty, "receipt_output": out,
            "natural_key": list(nk), "content_dedup_key": list(dedup or nk), "page_limit": limit,
            "baseline_dups": base_dups, "contract_sha256": "c" * 64, "doc_sha256": "d" * 64}


def _df(codes, date="20260702"):
    return pd.DataFrame({"ts_code": list(codes), "trade_date": [date] * len(codes), "v": range(len(codes))})


def test_shared_receipt_output_refused(led):
    _, L = led
    r1 = _plan_row("daily", "20260702", "market/daily/2026/daily_20260702.parquet")
    r2 = _plan_row("daily", "20260703", "market/daily/2026/daily_20260702.parquet")  # SAME output
    with pytest.raises(rl.LedgerError, match="share receipt_output"):
        L.freeze_plan([r1, r2])


def test_contiguous_and_terminal_happy_path(led):
    rp, L = led
    row = _plan_row("daily", "20260702", "market/daily/2026/daily_20260702.parquet", limit=2)
    L.freeze_plan([row])
    rid = row["request_id"]
    L.record_page(rid, 1, _df(["A.SZ", "B.SZ"]))                       # full page (==limit)
    L.record_page(rid, 2, _df(["C.SZ"]), terminal_claim="last_partial")  # short -> terminal
    ev = L.verify_request(rid)
    assert ev["pre_dedup_rows"] == 3 and ev["post_dedup_rows"] == 3 and ev["excess_dup_rows"] == 0
    assert len(ev["ordered_page_hashes"]) == 2
    assert (rp.staging_data / row["receipt_output"]).is_file()


def test_non_contiguous_pages_refused(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/a.parquet")
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, _df(["A.SZ", "B.SZ"]))
    L.record_page(rid, 3, _df(["C.SZ"]), terminal_claim="last_partial")  # gap: no page 2
    with pytest.raises(rl.LedgerError, match="contiguous"):
        L.verify_request(rid)


def test_exact_limit_last_page_needs_empty_terminal(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/b.parquet", limit=2)
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, _df(["A.SZ", "B.SZ"]), terminal_claim="last_partial")  # rows==limit but claims terminal
    with pytest.raises(rl.LedgerError, match="trailing empty page"):
        L.verify_request(rid)
    # a trailing empty page fixes it
    L.record_page(rid, 2, _df([]), terminal_claim="empty_terminal")
    assert L.verify_request(rid)["post_dedup_rows"] == 2


def test_null_natural_key_rejected(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/c.parquet", limit=3)
    L.freeze_plan([row]); rid = row["request_id"]
    bad = pd.DataFrame({"ts_code": ["A.SZ", None], "trade_date": ["20260702", "20260702"], "v": [1, 2]})
    L.record_page(rid, 1, bad, terminal_claim="last_partial")
    with pytest.raises(rl.LedgerError, match="null natural key"):
        L.verify_request(rid)


def test_unexpected_duplicates_rejected_unless_baseline(led):
    rp, L = led
    dup = _df(["A.SZ", "A.SZ"])  # duplicate (ts_code,trade_date)
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3, base_dups=False)
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, dup, terminal_claim="last_partial")
    with pytest.raises(rl.LedgerError, match="unexpected duplicate"):
        L.verify_request(rid)
    # a dataset that legitimately holds dups (event data) with baseline_dups=True passes
    monked = _plan_row("top_inst", "20260702", "o/e.parquet", limit=3, base_dups=True)
    L2 = rl.PageReceiptLedger(rp, coordinator_commit="deadbeef", adapter_bundle_hash="abc123")
    # a fresh run for the second plan (one plan per run)
    import uuid as _u
    base2 = rp.root.parent / _u.uuid4().hex
    rrc.RECOVERY_ROOT = rp.root.parent
    rp2 = rrc.RecoveryPaths(_u.uuid4().hex[:16]); rp2.create_root()
    L3 = rl.PageReceiptLedger(rp2, coordinator_commit="deadbeef", adapter_bundle_hash="abc123")
    L3.freeze_plan([monked]); rid2 = monked["request_id"]
    L3.record_page(rid2, 1, dup.rename(columns={}), terminal_claim="last_partial")
    ev = L3.verify_request(rid2)
    assert ev["excess_dup_rows"] == 1  # recorded, allowed
    shutil.rmtree(rp2.root, ignore_errors=True)


def test_chain_tamper_detected(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/f.parquet")
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, _df(["A.SZ"]), terminal_claim="last_partial")
    # edit a committed jsonl line -> the hash chain replay must fail
    lines = L.ledger_path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0]); rec["event"] = "tampered"; lines[0] = json.dumps(rec)
    L.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(rl.LedgerError, match="hash-chain break"):
        L.verify_request(rid)


def test_truncated_tail_detected(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/g.parquet")
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, _df(["A.SZ"]), terminal_claim="last_partial")
    lines = L.ledger_path.read_text(encoding="utf-8").splitlines()
    L.ledger_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")  # drop the last line
    with pytest.raises(rl.LedgerError, match="head does not match|hash-chain"):
        L.verify_request(rid)


def test_confirm_empty_needs_distinct_receipts_and_verified_canary(led):
    _, L = led
    empt = _plan_row("moneyflow", "20260702", "o/mf1.parquet", empty="sparse_canary")
    can = _plan_row("moneyflow", "20260703", "o/mf2.parquet", empty="sparse_canary")
    L.freeze_plan([empt, can]); ride, ridc = empt["request_id"], can["request_id"]
    # two BYTE-IDENTICAL empty receipts do not count as distinct
    L.record_page(ride, 1, _df([]), terminal_claim="empty_terminal")
    L.record_page(ride, 1, _df([]), terminal_claim="empty_terminal")
    with pytest.raises(rl.LedgerError, match="DISTINCT empty"):
        L.confirm_empty(ride, canary_request_id=ridc)
    # verify the same-endpoint nonempty canary, then confirm_empty is admissible (distinct receipts via
    # different page content on two pages)
    L.record_page(ridc, 1, _df(["X.SZ", "Y.SZ"]))
    L.record_page(ridc, 2, _df(["Z.SZ"]), terminal_claim="last_partial")
    L.verify_request(ridc)
    L.record_page(ride, 2, _df([], "20260702"), terminal_claim="empty_terminal")  # page 2 empty (distinct sha via page col? no)
    # force two DISTINCT empty receipts by an empty page with a different column shape
    empt2 = pd.DataFrame({"ts_code": [], "trade_date": [], "v": [], "extra": []})
    L.record_page(ride, 2, empt2, terminal_claim="empty_terminal")
    L.confirm_empty(ride, canary_request_id=ridc)
    ok, pending = L.consolidation_allowed("moneyflow")
    assert ok and not pending
