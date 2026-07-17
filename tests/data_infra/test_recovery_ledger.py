"""Page-receipt ledger (GPT recovery re-review #4 B2): coordinator-owned receipts, contiguous-page +
terminal proof, null-key/dup rejection, chain tamper detection, distinct-empty canary. Runs under C:."""
from __future__ import annotations

import importlib.util
import json
import os
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


def _recovery_test_root(sub: str) -> Path:
    """A writable NON-E: root for the recovery batteries.

    NOT pytest tmp_path and NOT tempfile.mkdtemp(): this repo points tmp_path *and* TEMP at
    E:\\量化系统\\workspace\\outputs\\pytest_runtime_tmp, and the coordinator REFUSES every E: write by
    design — that refusal is the invariant under test, so running these there would test nothing.
    Default is the sanctioned C:\\quant_recovery area; set QUANT_RECOVERY_TEST_ROOT to any writable
    non-E: path if that drive is unavailable (GPT re-review #8: a sandboxed reviewer could not write it,
    so the full battery could not serve as passing evidence)."""
    base = Path(os.environ.get("QUANT_RECOVERY_TEST_ROOT") or r"C:\quant_recovery")
    # GPT re-review #10 MINOR: VALIDATE the root BEFORE creating or writing anything — the previous
    # order mkdir'd/wrote a relative or E: override before rejecting it.
    if not base.is_absolute():
        pytest.skip(f"QUANT_RECOVERY_TEST_ROOT {base} must be ABSOLUTE")
    if base.drive.upper() == "E:":
        pytest.skip(f"recovery test root must be NON-E: (E: is refused by the coordinator by design); "
                    f"got {base}")
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / f".writeprobe_{uuid.uuid4().hex}"
        probe.write_bytes(b"x")
        probe.unlink()
    except OSError as exc:
        pytest.skip(f"recovery test root {base} is not writable ({exc}); set QUANT_RECOVERY_TEST_ROOT to "
                    f"a writable NON-E: path (E: is refused by the coordinator by design)")
    return base / sub / uuid.uuid4().hex


@pytest.fixture()
def led(monkeypatch):
    base = _recovery_test_root("ledgertest")
    monkeypatch.setattr(rrc, "RECOVERY_ROOT", base)
    rp = rrc.RecoveryPaths("led")
    rp.create_root()
    ledger = rl.PageReceiptLedger(rp, coordinator_commit="deadbeef", adapter_bundle_hash="abc123")
    _LIVE_CONTRACTS.clear()
    for ep in ("daily", "moneyflow", "top_inst", "income", "stock_basic"):
        _LIVE_CONTRACTS[ep] = _fake_contract(ep)
    # PRIVATE per-instance seam (GPT re-review #10 BLOCKER: tests replace this method, never a public
    # attribute production reads). The battery is below the full contract layer, so it re-checks the
    # fake live contracts by hash rather than running the real doc validator.
    def _seam(row):
        c = _LIVE_CONTRACTS.get(row["endpoint"])
        if not c:
            raise rl.LedgerError(f"{row['endpoint']}: NO live contract at fetch time")
        if rrc.canonical_contract_sha256(c) != row["contract_sha256"]:
            raise rl.LedgerError(f"{row['endpoint']}: the signed contract CHANGED since the plan froze")
    ledger._revalidate_contract = _seam
    # Same per-instance seam for the response-field check: this battery is below the full contract
    # layer, so it validates against the fixture's fake contracts (which carry no required_fields =>
    # a no-op) rather than the LIVE YAML. Without this the battery depended on the live `daily`
    # contract being UNsigned — signing it (2026-07-17) made the real check fire on the fake responses.
    def _resp_seam(endpoint, columns):
        try:
            rrc.assert_response_has_required_fields(endpoint, columns, contracts=_LIVE_CONTRACTS)
        except RuntimeError as exc:
            raise rl.LedgerError(str(exc))
    ledger._assert_response_fields = _resp_seam
    yield rp, ledger
    shutil.rmtree(base, ignore_errors=True)


def _fake_contract(endpoint: str) -> dict:
    """A stand-in signed contract. The ledger battery is deliberately below the contract layer, but
    fetch_page re-verifies its plan row against the LIVE contract (GPT re-review #9), so the fixture
    must supply one and the plan rows must cite its canonical hash."""
    return {"endpoint": endpoint, "empty_policy": "dense_refuse", "natural_key": ["ts_code", "trade_date"]}


_LIVE_CONTRACTS: dict = {}


def _plan_row(endpoint, part, out, *, empty="dense_refuse", limit=2, dedup=None, max_dups=0,
              nk=("ts_code", "trade_date"), mode=None):
    params = {"trade_date": part}
    return {"request_id": rl.request_id(endpoint, params, part), "endpoint": endpoint, "dataset": endpoint,
            "params": params, "partition": part, "empty_policy": empty, "receipt_output": out,
            "natural_key": list(nk), "content_dedup_key": list(dedup or nk), "page_limit": limit,
            "pagination_mode": mode or ("offset_paged" if limit else "single_page"),
            "max_content_dups": max_dups,
            "contract_sha256": rrc.canonical_contract_sha256(_fake_contract(endpoint)),
            "doc_sha256": "d" * 64}


def json_rows(L):
    return [json.loads(x) for x in L.ledger_path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _df(codes, date="20260702"):
    return pd.DataFrame({"ts_code": list(codes), "trade_date": [date] * len(codes), "v": range(len(codes))})


def test_shared_receipt_output_refused(led):
    _, L = led
    r1 = _plan_row("daily", "20260702", "market/daily/2026/daily_20260702.parquet")
    r2 = _plan_row("daily", "20260703", "market/daily/2026/daily_20260702.parquet")  # SAME output
    with pytest.raises(rl.LedgerError, match="share receipt_output"):
        L._freeze_plan_unvalidated([r1, r2])


def test_contiguous_and_terminal_happy_path(led):
    rp, L = led
    row = _plan_row("daily", "20260702", "market/daily/2026/daily_20260702.parquet", limit=2)
    L._freeze_plan_unvalidated([row])
    rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ", "B.SZ"]))                       # full page (==limit)
    L.fetch_page(rid, 2, lambda: _df(["C.SZ"]), terminal_claim="last_partial")  # short -> terminal
    ev = L.verify_request(rid)
    assert ev["pre_dedup_rows"] == 3 and ev["post_dedup_rows"] == 3 and ev["excess_dup_rows"] == 0
    assert len(ev["ordered_page_hashes"]) == 2
    assert (rp.staging_data / row["receipt_output"]).is_file()


def test_non_contiguous_pages_refused(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/a.parquet")
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ", "B.SZ"]))
    L.fetch_page(rid, 3, lambda: _df(["C.SZ"]), terminal_claim="last_partial")  # gap: no page 2
    with pytest.raises(rl.LedgerError, match="contiguous"):
        L.verify_request(rid)


def test_exact_limit_last_page_needs_empty_terminal(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/b.parquet", limit=2)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ", "B.SZ"]), terminal_claim="last_partial")  # rows==limit but claims terminal
    with pytest.raises(rl.LedgerError, match="trailing empty page"):
        L.verify_request(rid)
    # a trailing empty page fixes it
    L.fetch_page(rid, 2, lambda: _df([]), terminal_claim="empty_terminal")
    assert L.verify_request(rid)["post_dedup_rows"] == 2


def test_null_natural_key_rejected(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/c.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    bad = pd.DataFrame({"ts_code": ["A.SZ", None], "trade_date": ["20260702", "20260702"], "v": [1, 2]})
    L.fetch_page(rid, 1, lambda: bad, terminal_claim="last_partial")
    with pytest.raises(rl.LedgerError, match="null natural key"):
        L.verify_request(rid)


def test_duplicate_under_natural_key_always_refused(led):
    """GPT re-review #5 F2: `baseline_dups=True` used to allow UNLIMITED excess and then silently drop
    it, so a duplicated page could mask a MISSING page. A repeat under the vendor's natural key is now
    always a refusal — there is no free pass."""
    rp, L = led
    dup = _df(["A.SZ", "A.SZ"])  # duplicate (ts_code,trade_date) = the natural key
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3, max_dups=0)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: dup, terminal_claim="last_partial")
    with pytest.raises(rl.LedgerError, match="duplicate rows under the NATURAL key"):
        L.verify_request(rid)


def test_natural_key_dups_refused_even_with_a_dup_budget(led):
    """The declared max_content_dups budget applies ONLY to restatement collapse under the coarser
    content-dedup key — it can never excuse a repeated vendor row (the page-duplication hole)."""
    rp, L = led
    dup = _df(["A.SZ", "A.SZ"])
    row = _plan_row("top_inst", "20260702", "o/e.parquet", limit=3, max_dups=99)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: dup, terminal_claim="last_partial")
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
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: df, terminal_claim="last_partial")
    with pytest.raises(rl.LedgerError, match="exceeds the declared max_content_dups"):
        L.verify_request(rid)


def test_receipt_replaced_after_recording_is_caught(led):
    """GPT re-review #5 F2 (reproduced): a receipt REPLACED after recording still verified and its
    substituted row landed in the staged output. Verification now RE-COMPUTES each receipt's hash."""
    rp, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ"]), terminal_claim="last_partial")
    # find the receipt on disk and substitute its content
    import json as _j
    rec = None
    for ln in rp.ledger_path.read_text(encoding="utf-8").splitlines():
        r = _j.loads(ln)
        if r.get("kind") == "attempt" and r.get("receipt"):
            rec = rp.root / r["receipt"]
    assert rec and rec.is_file()
    _df(["EVIL.SZ"]).to_parquet(rec, index=False)   # swap the receipt's bytes
    with pytest.raises(rl.LedgerError, match="BYTES on disk do not match|does not match the recorded hash"):
        L.verify_request(rid)


def test_full_final_page_cannot_certify_via_a_generic_terminal(led):
    """GPT re-review #5 F2 (reproduced): a FULL final page marked `contract_terminal` verified,
    skipping the trailing-empty confirmation. The generic escape is GONE and every terminal now
    carries a machine-checked invariant."""
    rp, L = led
    assert "contract_terminal" not in rl._TERMINALS
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=2)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ", "B.SZ"]), terminal_claim="contract_terminal")  # FULL page
    with pytest.raises(rl.LedgerError, match="valid terminal_claim"):
        L.verify_request(rid)


def test_single_page_contract_terminal_is_proof_checked(led):
    """The only contract-declared terminal is `single_page_contract`, and it is PROVEN: page_limit==0
    and exactly one page. Claiming it under offset paging refuses."""
    rp, L = led
    row = _plan_row("stock_basic", "20260702", "o/s.parquet", limit=0)  # -> single_page mode
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ"]), terminal_claim="single_page_contract")
    ev = L.verify_request(rid)
    assert ev["post_dedup_rows"] == 1


def test_single_page_contract_claim_refused_under_offset_paging(led):
    """Claiming the single-page contract terminal on a PAGED request refuses — the terminal is bound
    to the declared pagination mode, not to the adapter's say-so."""
    rp, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=2, mode="offset_paged")
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ"]), terminal_claim="single_page_contract")
    with pytest.raises(rl.LedgerError, match="single_page_contract invalid under offset_paged"):
        L.verify_request(rid)


def test_chain_tamper_detected(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/f.parquet")
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ"]), terminal_claim="last_partial")
    # edit a committed jsonl line -> the hash chain replay must fail
    lines = L.ledger_path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0]); rec["event"] = "tampered"; lines[0] = json.dumps(rec)
    L.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(rl.LedgerError, match="hash-chain break"):
        L.verify_request(rid)


def test_truncated_tail_detected(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/g.parquet")
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ"]), terminal_claim="last_partial")
    lines = L.ledger_path.read_text(encoding="utf-8").splitlines()
    L.ledger_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")  # drop the last line
    with pytest.raises(rl.LedgerError, match="head does not match|hash-chain"):
        L.verify_request(rid)


def test_confirm_empty_requires_two_completed_call_leases(led):
    """GPT re-review #7 B1 (reproduced): attempt_uid/recorded_at were minted at RECORD time, so ONE
    empty response recorded twice certified as two independent attempts — and the old test did exactly
    that. Independence must evidence a real CALL: the ledger opens a lease BEFORE it invokes the
    callable and closes it after, so two empty confirmations require two completed call leases with
    disjoint windows."""
    _, L = led
    empt = _plan_row("moneyflow", "20260702", "o/mf1.parquet", empty="sparse_canary")
    can = _plan_row("moneyflow", "20260703", "o/mf2.parquet", empty="sparse_canary")
    L._freeze_plan_unvalidated([empt, can]); ride, ridc = empt["request_id"], can["request_id"]
    # ONE completed call lease is never enough
    L.fetch_page(ride, 1, lambda: _df([]), terminal_claim="empty_terminal")
    with pytest.raises(rl.LedgerError, match="COMPLETED CALL LEASES"):
        L.confirm_empty(ride, canary_request_id=ridc)
    # a SECOND real call (byte-identical empty response — no schema games) is a valid re-attempt...
    L.fetch_page(ride, 1, lambda: _df([]), terminal_claim="empty_terminal")
    # ...but without a verified NONEMPTY same-endpoint canary it still refuses
    with pytest.raises(rl.LedgerError, match="canary"):
        L.confirm_empty(ride, canary_request_id=ridc)
    L.fetch_page(ridc, 1, lambda: _df(["X.SZ", "Y.SZ"]))
    L.fetch_page(ridc, 2, lambda: _df(["Z.SZ"]), terminal_claim="last_partial")
    L.verify_request(ridc)
    L.confirm_empty(ride, canary_request_id=ridc)
    ok, pending = L.consolidation_allowed("moneyflow")
    assert ok and not pending


def test_the_ledger_makes_the_call_itself(led):
    """The adapter supplies a CALLABLE, never data it claims to have fetched. The ledger must invoke
    it exactly once per lease, and a lease must not be reusable."""
    _, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    calls = {"n": 0}

    def one_call():
        calls["n"] += 1
        return _df(["A.SZ"])

    n = L.fetch_page(rid, 1, one_call, terminal_claim="last_partial")
    assert calls["n"] == 1 and n == 1, "the ledger must invoke the callable exactly once"
    rows = json_rows(L)
    opens = [r for r in rows if r.get("kind") == "lease_open"]
    atts = [r for r in rows if r.get("kind") == "attempt"]
    assert len(opens) == 1 and len(atts) == 1
    # the lease was OPENED BEFORE the response was recorded — that ordering is the whole proof
    assert opens[0]["seq"] < atts[0]["seq"]
    assert atts[0]["lease_id"] == opens[0]["lease_id"]
    assert atts[0]["opened_at"] == opens[0]["opened_at"] and atts[0]["closed_at"]


def test_failed_call_leaves_a_failed_lease_and_no_attempt(led):
    """A call that raises must leave durable evidence of the attempt and NO recorded page."""
    _, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]

    def boom():
        raise RuntimeError("vendor 500")

    with pytest.raises(RuntimeError, match="vendor 500"):
        L.fetch_page(rid, 1, boom)
    rows = json_rows(L)
    assert [r for r in rows if r.get("kind") == "lease_open"], "no lease evidence for the failed call"
    assert [r for r in rows if r.get("kind") == "lease_failed"], "failure not journalled"
    assert not [r for r in rows if r.get("kind") == "attempt"], "a failed call recorded a page"
    with pytest.raises(rl.LedgerError, match="no page receipts|contiguous"):
        L.verify_request(rid)


def test_adapter_supplied_raw_fetch_ts_refused(led):
    """First-seen is coordinator-owned: a response that pre-stamps raw_fetch_ts is refused, and the
    caller-controlled fetch_ts parameter is gone."""
    _, L = led
    import inspect
    assert "fetch_ts" not in inspect.signature(rl.PageReceiptLedger.fetch_page).parameters
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    spiked = _df(["A.SZ"]).assign(raw_fetch_ts="2020-01-01T00:00:00Z")   # backdated by the adapter
    with pytest.raises(rl.LedgerError, match="pre-supplied raw_fetch_ts"):
        L.fetch_page(rid, 1, lambda: spiked, terminal_claim="last_partial")


def test_non_dataframe_response_refused(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    with pytest.raises(rl.LedgerError, match="not a DataFrame"):
        L.fetch_page(rid, 1, lambda: {"rows": []})
    assert [r for r in json_rows(L) if r.get("kind") == "lease_failed"]


def test_confirm_empty_reuses_the_mode_specific_terminal_proof(led):
    """GPT re-review #7 B1: confirm_empty did not reuse verify_request's typed proof, so an
    offset_paged empty request could be confirmed on a single_page_contract claim."""
    _, L = led
    empt = _plan_row("moneyflow", "20260702", "o/mf1.parquet", empty="sparse_canary",
                     limit=2, mode="offset_paged")
    can = _plan_row("moneyflow", "20260703", "o/mf2.parquet", empty="sparse_canary")
    L._freeze_plan_unvalidated([empt, can]); ride, ridc = empt["request_id"], can["request_id"]
    L.fetch_page(ride, 1, lambda: _df([]), terminal_claim="single_page_contract")
    L.fetch_page(ride, 1, lambda: _df([]), terminal_claim="single_page_contract")
    with pytest.raises(rl.LedgerError, match="single_page_contract invalid under offset_paged"):
        L.confirm_empty(ride, canary_request_id=ridc)

def test_sparse_zero_rows_can_never_be_verified(led):
    """GPT re-review #6 F2 BLOCKER (reproduced): a SPARSE zero-row result fell through to `verified`,
    and consolidation_allowed() accepts `verified` — so a partition that returned nothing because the
    FETCH failed was indistinguishable from one the vendor genuinely has no data for. Missing data
    could certify as complete. verify_request must never certify an empty result."""
    _, L = led
    row = _plan_row("top_inst", "20260702", "o/ti.parquet", empty="sparse_canary", limit=2)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df([]), terminal_claim="empty_terminal")
    with pytest.raises(rl.LedgerError, match="can NEVER"):
        L.verify_request(rid)
    ok, pending = L.consolidation_allowed("top_inst")
    assert not ok and pending == [rid], "an unconfirmed sparse empty must BLOCK consolidation"


def test_receipt_paths_are_attempt_unique_and_immutable(led):
    """GPT re-review #6 F2: receipts used to reuse page_{n}.parquet, so a retry REWROTE the earlier
    attempt's bytes. Each attempt now owns an attempt_uid-suffixed receipt."""
    _, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ"]), terminal_claim="last_partial")
    L.fetch_page(rid, 1, lambda: _df(["A.SZ", "B.SZ"]), terminal_claim="last_partial")  # retry of page 1
    recs = [r["receipt"] for r in json_rows(L) if r.get("kind") == "attempt"]
    assert len(recs) == 2 and len(set(recs)) == 2, "retry reused the earlier attempt's receipt path"
    for r in recs:
        assert (L.rp.root / r).is_file()  # BOTH attempts' bytes survive


def test_raw_fetch_ts_is_injected_by_the_coordinator(led):
    """GPT re-review #6 F4: `raw_fetch_ts` was a DECLARED derivation with no producer — record_page
    never injected it. The coordinator owns first-seen; an adapter never supplies it."""
    _, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ"]), terminal_claim="last_partial")
    rec = [r for r in json_rows(L) if r.get("kind") == "attempt"][0]
    fr = pd.read_parquet(L.rp.root / rec["receipt"])
    assert "raw_fetch_ts" in fr.columns and fr["raw_fetch_ts"].notna().all()
    assert rec.get("attempt_uid") and rec.get("recorded_at")


def test_row_payload_digest_producer_is_executable_and_lossless(led):
    """GPT re-review #6 F3: `row_payload_digest` was PROSE — the matrix keyed the event families on a
    column nothing computed. The producer must exist and be lossless (any field change -> new digest)."""
    _, L = led
    a = pd.DataFrame([{"ts_code": "A.SZ", "trade_date": "20260702", "exalter": "X", "buy": 1.0}])
    b = pd.DataFrame([{"ts_code": "A.SZ", "trade_date": "20260702", "exalter": "X", "buy": 2.0}])  # buy differs
    da = rl.PageReceiptLedger.add_row_payload_digest(a)
    db = rl.PageReceiptLedger.add_row_payload_digest(b)
    assert "row_payload_digest" in da.columns
    assert da["row_payload_digest"][0] != db["row_payload_digest"][0], "digest is NOT lossless"
    # identical rows -> identical digest (deterministic); coordinator-derived cols are excluded
    again = rl.PageReceiptLedger.add_row_payload_digest(a.assign(raw_fetch_ts="2026-07-16T00:00:00Z"))
    assert again["row_payload_digest"][0] == da["row_payload_digest"][0], \
        "digest must ignore coordinator-derived columns"


def test_row_payload_digest_is_typed_and_lossless(led):
    """GPT re-review #7 M1 (reproduced): iterrows()+repr coerced int64 to float when another column was
    floating, so int64(1) and float64(1.0) produced the SAME digest — the key was not lossless, which
    is its entire purpose. Column-wise typed encoding fixes the whole class."""
    import numpy as np
    D = rl.PageReceiptLedger.add_row_payload_digest
    dig = lambda d: D(d)["row_payload_digest"][0]
    # GPT's exact case
    a = pd.DataFrame({"a": pd.Series([1], dtype="int64"), "b": pd.Series([2.5], dtype="float64")})
    b = pd.DataFrame({"a": pd.Series([1.0], dtype="float64"), "b": pd.Series([2.5], dtype="float64")})
    assert dig(a) != dig(b), "int64(1) and float64(1.0) still collide"
    # negative zero, type confusion, field-boundary aliasing
    assert dig(pd.DataFrame({"v": pd.Series([0.0])})) != dig(pd.DataFrame({"v": pd.Series([-0.0])}))
    assert dig(pd.DataFrame({"v": [1]})) != dig(pd.DataFrame({"v": ["1"]}))
    assert dig(pd.DataFrame({"x": ["a"], "y": ["bc"]})) != dig(pd.DataFrame({"x": ["ab"], "y": ["c"]}))
    # NaN/None are stable tokens, not payload-dependent
    assert dig(pd.DataFrame({"v": [float("nan")]})) == dig(pd.DataFrame({"v": [float("nan")]}))
    # determinism for identical typed input
    assert dig(a) == dig(a.copy())


def test_corrupted_staged_output_blocks_consolidation(led):
    """GPT re-review #7 B2 (reproduced): the verdict recorded only an in-memory logical hash and
    consolidation_allowed() trusted terminal STATE alone, so replacing the staged output with a valid
    but DIFFERENT parquet after verification still allowed consolidation and staged the corrupt value.
    A verdict is a statement about the bytes that existed at verify time — never about today's."""
    rp, L = led
    row = _plan_row("daily", "20260702", "market/daily/2026/daily_20260702.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ"]), terminal_claim="last_partial")
    ev = L.verify_request(rid)
    assert ev["output_bytes_sha256"] and ev["output_size"] > 0 and ev["output_path"]
    ok, pending = L.consolidation_allowed("daily")
    assert ok and not pending
    # ---- replace the staged output with a VALID but different parquet ----
    out = rp.staging_data / row["receipt_output"]
    pd.DataFrame({"ts_code": ["EVIL.SZ"], "trade_date": ["20260702"], "v": [999]}).to_parquet(out, index=False)
    with pytest.raises(rl.LedgerError, match="CHANGED since verification"):
        L.consolidation_allowed("daily")
    with pytest.raises(rl.LedgerError, match="CHANGED since verification"):
        L.assert_staged_outputs_intact("daily")


def test_deleted_staged_output_blocks_consolidation(led):
    rp, L = led
    row = _plan_row("daily", "20260702", "market/daily/2026/daily_20260702.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ"]), terminal_claim="last_partial")
    L.verify_request(rid)
    (rp.staging_data / row["receipt_output"]).unlink()
    with pytest.raises(rl.LedgerError, match="is GONE since verification"):
        L.consolidation_allowed("daily")


def test_missing_sentinels_do_not_collide(led):
    """GPT re-review #8 MAJOR (reproduced): None, pd.NA and pd.NaT all encoded to ONE `NULL` token, so
    event rows differing only in WHICH missing-sentinel they carry merged."""
    c = rl._canon_scalar
    enc = [c(None), c(pd.NA), c(pd.NaT), c(float("nan"))]
    assert len(set(enc)) == 4, f"missing sentinels collide: {enc}"
    D = rl.PageReceiptLedger.add_row_payload_digest
    a = pd.DataFrame({"k": ["A"], "v": pd.Series([None], dtype="object")})
    b = pd.DataFrame({"k": ["A"], "v": pd.Series([pd.NA], dtype="object")})
    assert D(a)["row_payload_digest"][0] != D(b)["row_payload_digest"][0], \
        "object-column None and pd.NA still produce one digest"


def test_decimal_and_datetime_are_exactly_encoded(led):
    import datetime
    import decimal
    c = rl._canon_scalar
    assert c(decimal.Decimal("1.10")) != c(decimal.Decimal("1.1"))   # scale is part of the value
    assert c(decimal.Decimal("1.5")) != c(1.5)                       # Decimal is not a float
    aware = datetime.datetime(2026, 7, 16, tzinfo=datetime.timezone.utc)
    naive = datetime.datetime(2026, 7, 16)
    assert c(aware) != c(naive)                                      # tz-aware != naive
    assert c(datetime.date(2026, 7, 16)) != c(datetime.datetime(2026, 7, 16))


def test_unknown_object_type_refuses_instead_of_repr(led):
    """A repr fallback makes the key depend on an unstable __repr__ and can alias distinct values."""
    class Weird:
        def __repr__(self):
            return "<same>"
    with pytest.raises(rl.LedgerError, match="no canonical encoding"):
        rl._canon_scalar(Weird())


# ── GPT re-review #9 BLOCKER-1: the contract binding must hold at FETCH time, not just at freeze ──
def test_editing_the_contract_after_freeze_stops_fetching(led):
    """GPT re-review #9 (reproduced): the contract hash was checked once, at freeze — editing the signed
    contract afterwards still allowed fetch_page. A frozen hash proves what WAS signed, never what is
    signed NOW."""
    _, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    L.fetch_page(rid, 1, lambda: _df(["A.SZ"]))                    # binding intact -> fetch allowed
    _LIVE_CONTRACTS["daily"] = dict(_fake_contract("daily"), empty_policy="sparse_canary")  # edited
    with pytest.raises(rl.LedgerError, match="CHANGED since the plan froze"):
        L.fetch_page(rid, 2, lambda: _df(["B.SZ"]), terminal_claim="last_partial")


def test_deleted_contract_after_freeze_stops_fetching(led):
    _, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    del _LIVE_CONTRACTS["daily"]
    with pytest.raises(rl.LedgerError, match="NO live contract"):
        L.fetch_page(rid, 1, lambda: _df(["A.SZ"]))


def test_endpoint_absent_from_live_contracts_cannot_fetch(led):
    """GPT re-review #10 BLOCKER: fetch-time re-binding reads the LIVE contracts internally — there is
    no injectable loader. An endpoint gone from the live set (signed when the plan froze, absent now)
    fails closed."""
    _, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=3)
    L._freeze_plan_unvalidated([row]); rid = row["request_id"]
    del _LIVE_CONTRACTS["daily"]
    with pytest.raises(rl.LedgerError, match="NO live contract"):
        L.fetch_page(rid, 1, lambda: _df(["A.SZ"]))


def test_decimal_special_values_do_not_collide(led):
    """GPT re-review #9 MAJOR: the special-value branch returned only the exponent tag, dropping sign
    and digits — Infinity == -Infinity and NaN123 == NaN456 at the digest layer."""
    import decimal
    D, c = decimal.Decimal, rl._canon_scalar
    assert c(D("Infinity")) != c(D("-Infinity"))
    assert c(D("NaN123")) != c(D("NaN456"))
    assert c(D("NaN")) != c(D("sNaN"))
    assert c(D("Infinity")) != c(float("inf"))          # Decimal inf is not float inf


def test_receipt_output_cannot_escape_staging_data(led):
    """GPT re-review #10 MAJOR (reproduced): receipt_output was joined onto staging_data and only
    uniqueness-checked, so ../reports/escaped.parquet normalized to <run>/reports (outside staging_data
    but inside the run root) and freeze accepted it."""
    _, L = led
    for bad in ("../reports/escaped.parquet", "../../evil.parquet", "a/../../b.parquet",
                r"C:\abs.parquet", "/abs.parquet", r"\srv\share\x.parquet", ""):
        row = _plan_row("daily", "20260702", bad)
        with pytest.raises(rl.LedgerError, match="receipt_output|traversal|OUTSIDE|RELATIVE|non-empty"):
            L._freeze_plan_unvalidated([row])
    # a normal nested relative path still passes
    ok = _plan_row("daily", "20260702", "market/daily/2026/daily_20260702.parquet")
    L._freeze_plan_unvalidated([ok])


def test_digest_is_semantic_not_physical(led):
    """GPT re-review #10 MINOR: the digest is SEMANTIC — equal values collapse across carrier type
    (int(1) == np.int64(1)); it distinguishes genuinely different values. Documented, not a defect."""
    import numpy as np
    c = rl._canon_scalar
    assert c(1) == c(np.int64(1))                 # same NUMBER, different carrier -> same digest
    assert c(1) != c(1.0) and c(1) != c("1")      # genuinely different values stay distinct
    assert len({c(None), c(pd.NA), c(pd.NaT), c(float("nan"))}) == 4   # every sentinel distinct


def test_rewritten_plan_json_refused(led):
    """GPT re-review #10 BLOCKER (reproduced): _plan checked only the plan's embedded self-hash, so a
    rewritten request_plan.json with a recomputed hash was accepted despite disagreeing with the
    hash-chained plan_frozen event."""
    import json as _j
    rp, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=2)
    L._freeze_plan_unvalidated([row])
    L._plan()   # attested, matches -> ok
    # rewrite the payload with a DIFFERENT plan and a freshly-recomputed self-hash
    evil = _plan_row("moneyflow", "20260703", "o/evil.parquet", limit=2)
    L.plan_path.write_text(_j.dumps({"sha256": rl._h(rl._canon([evil])),
                                   "coordinator_commit": "x", "adapter_bundle_hash": "y",
                                   "rows": [evil]}), encoding="utf-8")
    with pytest.raises(rl.LedgerError, match="the plan was rewritten|hash-chained plan_frozen"):
        L._plan()


def test_orphan_plan_after_crash_refused_then_healed(led):
    """GPT re-review #10 BLOCKER (reproduced): a crash between writing plan.json and appending the
    plan_frozen event left an orphan plan that _plan still accepted. Now the AUTHORITY is appended
    first; a payload lost by the crash refuses until a same-plan resume HEALS it."""
    rp, L = led
    row = _plan_row("daily", "20260702", "o/d.parquet", limit=2)
    L._freeze_plan_unvalidated([row])
    # simulate the crash-lost payload: the event survives, the file does not
    L.plan_path.unlink()
    with pytest.raises(rl.LedgerError, match="request_plan.json is MISSING"):
        L._plan()
    # re-freezing the SAME plan heals the payload and appends NO second event
    L._freeze_plan_unvalidated([row])
    assert L.plan_path.exists()
    assert len([r for r in L._load() if r.get("event") == "plan_frozen"]) == 1
    assert list(L._plan()) == [row["request_id"]]


def test_refreezing_a_different_plan_refused(led):
    _, L = led
    a = _plan_row("daily", "20260702", "o/a.parquet", limit=2)
    L._freeze_plan_unvalidated([a])
    b = _plan_row("moneyflow", "20260703", "o/b.parquet", limit=2)
    with pytest.raises(rl.LedgerError, match="already frozen for this run"):
        L._freeze_plan_unvalidated([b])
    # re-freezing the SAME plan is idempotent (no second event)
    L._freeze_plan_unvalidated([a])
    assert len([r for r in L._load() if r.get("event") == "plan_frozen"]) == 1


def test_no_plan_frozen_event_refused(led):
    _, L = led
    with pytest.raises(rl.LedgerError, match="not attested|no plan_frozen"):
        L._plan()
