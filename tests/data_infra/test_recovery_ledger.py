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


def _plan_row(endpoint, part, out, *, empty="dense_refuse", limit=2, dedup=None, max_dups=0,
              nk=("ts_code", "trade_date"), mode=None):
    params = {"trade_date": part}
    return {"request_id": rl.request_id(endpoint, params, part), "endpoint": endpoint, "dataset": endpoint,
            "params": params, "partition": part, "empty_policy": empty, "receipt_output": out,
            "natural_key": list(nk), "content_dedup_key": list(dedup or nk), "page_limit": limit,
            "pagination_mode": mode or ("offset_paged" if limit else "single_page"),
            "max_content_dups": max_dups, "contract_sha256": "c" * 64, "doc_sha256": "d" * 64}


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


def test_duplicate_under_natural_key_always_refused(led):
    """GPT re-review #5 F2: `baseline_dups=True` used to allow UNLIMITED excess and then silently drop
    it, so a duplicated page could mask a MISSING page. A repeat under the vendor's natural key is now
    always a refusal — there is no free pass."""
    rp, L = led
    dup = _df(["A.SZ", "A.SZ"])  # duplicate (ts_code,trade_date) = the natural key
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3, max_dups=0)
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, dup, terminal_claim="last_partial")
    with pytest.raises(rl.LedgerError, match="duplicate rows under the NATURAL key"):
        L.verify_request(rid)


def test_natural_key_dups_refused_even_with_a_dup_budget(led):
    """The declared max_content_dups budget applies ONLY to restatement collapse under the coarser
    content-dedup key — it can never excuse a repeated vendor row (the page-duplication hole)."""
    rp, L = led
    dup = _df(["A.SZ", "A.SZ"])
    row = _plan_row("top_inst", "20260702", "o/e.parquet", limit=3, max_dups=99)
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, dup, terminal_claim="last_partial")
    with pytest.raises(rl.LedgerError, match="duplicate rows under the NATURAL key"):
        L.verify_request(rid)


def test_content_dedup_excess_bounded_by_declared_budget(led):
    """Genuine restatement collapse: rows DISTINCT under the natural key but colliding under the
    coarser content-dedup key are allowed only up to the plan's declared bound."""
    rp, L = led
    import pandas as pd
    # distinct natural keys (ts_code,ann_date); both collapse to one under (ts_code,end_date)
    df = pd.DataFrame([{"ts_code": "A.SZ", "ann_date": "20260701", "end_date": "20260630", "v": 1},
                       {"ts_code": "A.SZ", "ann_date": "20260702", "end_date": "20260630", "v": 2}])
    row = _plan_row("income", "20260702", "o/i.parquet", limit=3, max_dups=0,
                    nk=("ts_code", "ann_date"), dedup=("ts_code", "end_date"))
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, df, terminal_claim="last_partial")
    with pytest.raises(rl.LedgerError, match="exceeds the declared max_content_dups"):
        L.verify_request(rid)


def test_receipt_replaced_after_recording_is_caught(led):
    """GPT re-review #5 F2 (reproduced): a receipt REPLACED after recording still verified and its
    substituted row landed in the staged output. Verification now RE-COMPUTES each receipt's hash."""
    rp, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, _df(["A.SZ"]), terminal_claim="last_partial")
    # find the receipt on disk and substitute its content
    import json as _j
    rec = None
    for ln in rp.ledger_path.read_text(encoding="utf-8").splitlines():
        r = _j.loads(ln)
        if r.get("kind") == "attempt" and r.get("receipt"):
            rec = rp.root / r["receipt"]
    assert rec and rec.is_file()
    _df(["EVIL.SZ"]).to_parquet(rec, index=False)   # swap the receipt's bytes
    with pytest.raises(rl.LedgerError, match="does not match the recorded hash"):
        L.verify_request(rid)


def test_full_final_page_cannot_certify_via_a_generic_terminal(led):
    """GPT re-review #5 F2 (reproduced): a FULL final page marked `contract_terminal` verified,
    skipping the trailing-empty confirmation. The generic escape is GONE and every terminal now
    carries a machine-checked invariant."""
    rp, L = led
    assert "contract_terminal" not in rl._TERMINALS
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=2)
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, _df(["A.SZ", "B.SZ"]), terminal_claim="contract_terminal")  # FULL page
    with pytest.raises(rl.LedgerError, match="valid terminal_claim"):
        L.verify_request(rid)


def test_single_page_contract_terminal_is_proof_checked(led):
    """The only contract-declared terminal is `single_page_contract`, and it is PROVEN: page_limit==0
    and exactly one page. Claiming it under offset paging refuses."""
    rp, L = led
    row = _plan_row("stock_basic", "20260702", "o/s.parquet", limit=0)  # -> single_page mode
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, _df(["A.SZ"]), terminal_claim="single_page_contract")
    ev = L.verify_request(rid)
    assert ev["post_dedup_rows"] == 1


def test_single_page_contract_claim_refused_under_offset_paging(led):
    """Claiming the single-page contract terminal on a PAGED request refuses — the terminal is bound
    to the declared pagination mode, not to the adapter's say-so."""
    rp, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=2, mode="offset_paged")
    L.freeze_plan([row]); rid = row["request_id"]
    L.record_page(rid, 1, _df(["A.SZ"]), terminal_claim="single_page_contract")
    with pytest.raises(rl.LedgerError, match="single_page_contract invalid under offset_paged"):
        L.verify_request(rid)


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
