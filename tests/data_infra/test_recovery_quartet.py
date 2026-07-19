# -*- coding: utf-8 -*-
"""Pre-fetch test matrix for the adapter quartet (design v4 acceptance §6).

Drives the FULL claimed-fetch machinery — atomic claim, executor invocation, prepare, response scope,
ledger-derived terminals, empty lifecycle, consolidation with typed conservation — under a
SyntheticExecutor (no Tushare import on this path). The battery sits below the contract layer (fake
contracts + the sanctioned per-instance seams), except the plan-scale test which freezes the REAL
signed A01 plan through the coordinator's full validation door. Runs under C:."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import uuid
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
_c = importlib.util.spec_from_file_location("rrc", ROOT / "scripts" / "raw_recovery_coordinator.py")
rrc = importlib.util.module_from_spec(_c); sys.modules["rrc"] = rrc; _c.loader.exec_module(rrc)
_l = importlib.util.spec_from_file_location("rl", ROOT / "scripts" / "recovery_ledger.py")
rl = importlib.util.module_from_spec(_l); sys.modules["rl"] = rl; _l.loader.exec_module(rl)
# recovery_adapters imports the coordinator/ledger by their CANONICAL names — register the SAME module
# objects under those names so all three share one instance (seams + monkeypatched roots hold).
sys.modules["raw_recovery_coordinator"] = rrc
sys.modules["recovery_ledger"] = rl
_a = importlib.util.spec_from_file_location("recovery_adapters", ROOT / "scripts" / "recovery_adapters.py")
ra = importlib.util.module_from_spec(_a); sys.modules["recovery_adapters"] = ra; _a.loader.exec_module(ra)

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="needs the Windows no-follow broker")


def _recovery_test_root(sub: str) -> Path:
    base = Path(os.environ.get("QUANT_RECOVERY_TEST_ROOT") or r"C:\quant_recovery")
    if not base.is_absolute():
        pytest.skip(f"QUANT_RECOVERY_TEST_ROOT {base} must be ABSOLUTE")
    if base.drive.upper() == "E:":
        pytest.skip("recovery test root must be NON-E: (E: writes are refused by design)")
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / f".writeprobe_{uuid.uuid4().hex}"
        probe.write_bytes(b"x")
        probe.unlink()
    except OSError as exc:
        pytest.skip(f"recovery test root {base} is not writable ({exc})")
    return base / sub / uuid.uuid4().hex


_LIVE_CONTRACTS: dict = {}


def _fake_contract(endpoint: str, *, empty="dense_refuse", nk=("ts_code", "trade_date")) -> dict:
    return {"endpoint": endpoint, "empty_policy": empty, "natural_key": list(nk)}


@pytest.fixture()
def rig(monkeypatch):
    base = _recovery_test_root("quartet")
    monkeypatch.setattr(rrc, "RECOVERY_ROOT", base)
    rp = rrc.RecoveryPaths("qt")
    rp.create_root()
    ledger = rl.PageReceiptLedger(rp, coordinator_commit="deadbeef",
                                  adapter_bundle_hash=ra.compute_bundle_hash())

    def _seam(row):
        c = _LIVE_CONTRACTS.get(row["endpoint"])
        if not c:
            raise rl.LedgerError(f"{row['endpoint']}: NO live contract at fetch time")
        if rrc.canonical_contract_sha256(c) != row["contract_sha256"]:
            raise rl.LedgerError(f"{row['endpoint']}: the signed contract CHANGED since the plan froze")
    ledger._revalidate_contract = _seam

    def _resp_seam(endpoint, columns):
        try:
            rrc.assert_response_has_required_fields(endpoint, columns, contracts=_LIVE_CONTRACTS)
        except RuntimeError as exc:
            raise rl.LedgerError(str(exc))
    ledger._assert_response_fields = _resp_seam
    _LIVE_CONTRACTS.clear()
    yield rp, ledger
    shutil.rmtree(base, ignore_errors=True)


def _prow(ep, part, out, *, params=None, empty="dense_refuse", limit=0, mode=None,
          nk=("ts_code", "trade_date"), dedup=None, max_dups=0, dataset=None, scope=None):
    """A plan row in the grown v4 schema. contract_sha256 binds the fixture contract so the
    _revalidate seam passes; response_scope defaults to eq-on-the-partition column."""
    params = params if params is not None else {"trade_date": part}
    c = _LIVE_CONTRACTS.setdefault(ep, _fake_contract(ep, empty=empty, nk=nk))
    if scope is None:
        key = next(iter(params))
        scope = {"rule_id": f"eq_{key}", "checks": [[key, "eq", str(params[key])]]}
    return {"request_id": rl.request_id(ep, params, part), "endpoint": ep,
            "dataset": dataset or ep, "params": params, "partition": part,
            "empty_policy": empty, "receipt_output": out, "natural_key": list(nk),
            "content_dedup_key": list(dedup or nk), "page_limit": limit,
            "pagination_mode": mode or ("offset_paged" if limit else "single_page"),
            "max_content_dups": max_dups,
            "contract_sha256": rrc.canonical_contract_sha256(c), "doc_sha256": "d" * 64,
            "recipe_id": f"test_recipe_{ep}", "response_scope": scope}


def _df(codes, date="20260702", **extra):
    d = {"ts_code": list(codes), "trade_date": [date] * len(codes), "v": list(range(len(codes)))}
    for k, vals in extra.items():
        d[k] = vals
    return pd.DataFrame(d)


def _syn(fixtures):
    """fixtures: a LIST of ((endpoint, params_dict, offset), df) pairs (params dicts are unhashable,
    so the canonical-key conversion happens here)."""
    return ra.SyntheticExecutor({(ep, ra._params_key(p), off): df for (ep, p, off), df in fixtures})


def _drive(ledger, rid, executor):
    """The run_family inner loop for one request (kept in-test so assertions can interleave)."""
    while True:
        claim = ledger.claim_next_fetch(rid, executor.mode)
        if claim.kind in ("FETCH", "RETRY_PAGE", "RETRY_EMPTY_CONFIRM"):
            ledger.fetch_claimed_page(rid, claim, executor)
            continue
        return claim


# ── run-mode + §13 gates (F2) ────────────────────────────────────────────────────────────────────
def test_undeclared_run_mode_refuses(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    with pytest.raises(rl.LedgerError, match="run mode undeclared"):
        L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")


def test_mismatched_executor_mode_refuses_pre_lease(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    with pytest.raises(rl.LedgerError, match="executor mode .* != run mode"):
        L.claim_next_fetch(row["request_id"], "live_authorized")
    # the refusal happened BEFORE any lease: no lease_open trace exists
    assert not [r for r in L._load() if r.get("kind") == "lease_open"]
    # and the run mode is immutable
    with pytest.raises(rl.LedgerError, match="immutable"):
        L.declare_run_mode("live_authorized")


class _StubLiveExecutor:
    """live-MODE executor with canned pages — exercises the live gates WITHOUT tushare."""
    mode = "live_authorized"

    def __init__(self, df):
        self._df = df

    def run_page(self, spec):
        return self._df.copy()


def test_live_requires_the_fetch_authorized_event(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("live_authorized")
    ex = _StubLiveExecutor(_df(["A.SZ"]))
    with pytest.raises(rl.LedgerError, match="authorization missing"):
        L.claim_next_fetch(row["request_id"], ex.mode)
    # an EXPIRED authorization refuses
    from datetime import datetime, timedelta, timezone
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    L.record_fetch_authorization(actor="henry", expires_at=past, endpoint_scope=["daily"])
    with pytest.raises(rl.LedgerError, match="EXPIRED"):
        L.claim_next_fetch(row["request_id"], ex.mode)
    # a valid one admits the fetch; out-of-scope still refuses per endpoint
    fut = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    L.record_fetch_authorization(actor="henry", expires_at=fut, endpoint_scope=["daily"])
    claim = L.claim_next_fetch(row["request_id"], ex.mode)
    assert claim.kind == "FETCH"
    L.fetch_claimed_page(row["request_id"], claim, ex)
    assert _drive(L, row["request_id"], ex).kind == "VERIFY"


def test_authorization_binds_the_adapter_bundle(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("live_authorized")
    from datetime import datetime, timedelta, timezone
    fut = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    L.record_fetch_authorization(actor="henry", expires_at=fut, endpoint_scope=["*"])
    # a ledger bound to a DIFFERENT bundle cannot even LOAD the run: the bundle hash is part of the
    # chain GENESIS, so drift refuses at replay — STRICTLY stronger than the event-level check (which
    # still exists for an authorization recorded under an older bundle within the same genesis).
    L2 = rl.PageReceiptLedger(rp, coordinator_commit="deadbeef", adapter_bundle_hash="0" * 64)
    L2._revalidate_contract = L._revalidate_contract
    with pytest.raises(rl.LedgerError, match="hash-chain break"):
        L2.claim_next_fetch(row["request_id"], "live_authorized")


def test_promotion_refuses_a_synthetic_run(rig):
    rp, L = rig
    L._freeze_plan_unvalidated([_prow("daily", "20260702", "req/daily/20260702.parquet")])
    L.declare_run_mode("synthetic_nonpromotable")
    with pytest.raises(rl.LedgerError, match="NOT promotable"):
        L.assert_run_promotable()


# ── claim/cursor mechanics (F3) ──────────────────────────────────────────────────────────────────
def test_single_page_happy_path(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    ex = _syn([(("daily", {"trade_date": "20260702"}, 0), _df(["A.SZ", "B.SZ"]))])
    claim = L.claim_next_fetch(row["request_id"], ex.mode)
    assert (claim.kind, claim.page, claim.offset) == ("FETCH", 1, 0)
    res = L.fetch_claimed_page(row["request_id"], claim, ex)
    assert (res.row_count, res.terminal_kind) == (2, "single_page_contract")
    assert L.claim_next_fetch(row["request_id"], ex.mode).kind == "VERIFY"
    ev = L.verify_request(row["request_id"])
    assert ev["post_dedup_rows"] == 2
    assert L.claim_next_fetch(row["request_id"], ex.mode).kind == "SKIP_TERMINAL"


def test_offset_exact_limit_multipage_with_trailing_empty(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet", limit=2)
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    p = {"trade_date": "20260702"}
    ex = _syn([(("daily", p, 0), _df(["A.SZ", "B.SZ"])),
               (("daily", p, 2), _df(["C.SZ", "D.SZ"])),
               (("daily", p, 4), _df([]))])         # trailing empty proves the exact-limit end
    offsets = []
    while True:
        claim = L.claim_next_fetch(row["request_id"], ex.mode)
        if claim.kind != "FETCH":
            break
        offsets.append((claim.page, claim.offset))
        L.fetch_claimed_page(row["request_id"], claim, ex)
    assert offsets == [(1, 0), (2, 2), (3, 4)]
    assert claim.kind == "VERIFY"
    assert L.verify_request(row["request_id"])["post_dedup_rows"] == 4


def test_offset_last_partial_terminal(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet", limit=2)
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    p = {"trade_date": "20260702"}
    ex = _syn([(("daily", p, 0), _df(["A.SZ", "B.SZ"])), (("daily", p, 2), _df(["C.SZ"]))])
    while (c := L.claim_next_fetch(row["request_id"], ex.mode)).kind == "FETCH":
        res = L.fetch_claimed_page(row["request_id"], c, ex)
    assert res.terminal_kind == "last_partial"
    assert L.verify_request(row["request_id"])["post_dedup_rows"] == 3


def test_page_exceeding_the_signed_limit_refuses(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet", limit=2)
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    ex = _syn([(("daily", {"trade_date": "20260702"}, 0), _df(["A.SZ", "B.SZ", "C.SZ"]))])  # 3 > 2
    claim = L.claim_next_fetch(row["request_id"], ex.mode)
    with pytest.raises(rl.LedgerError, match="EXCEEDS the signed page_limit"):
        L.fetch_claimed_page(row["request_id"], claim, ex)
    # the failure is recorded; the next claim is a RETRY of the same page under a NEW lease
    nxt = L.claim_next_fetch(row["request_id"], ex.mode)
    assert (nxt.kind, nxt.page) == ("RETRY_PAGE", 1)


def test_concurrent_claim_sees_in_flight(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    first = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    assert first.kind == "FETCH"
    assert L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable").kind == "IN_FLIGHT"


def test_crash_resume_continues_at_the_next_offset(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet", limit=2)
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    p = {"trade_date": "20260702"}
    ex = _syn([(("daily", p, 0), _df(["A.SZ", "B.SZ"])), (("daily", p, 2), _df(["C.SZ"]))])
    L.fetch_claimed_page(row["request_id"], L.claim_next_fetch(row["request_id"], ex.mode), ex)
    # "crash": a FRESH ledger instance over the same run root resumes mid-request
    L2 = rl.PageReceiptLedger(rp, coordinator_commit="deadbeef",
                              adapter_bundle_hash=ra.compute_bundle_hash())
    L2._revalidate_contract = L._revalidate_contract
    L2._assert_response_fields = L._assert_response_fields
    claim = L2.claim_next_fetch(row["request_id"], ex.mode)
    assert (claim.kind, claim.page, claim.offset) == ("FETCH", 2, 2)
    L2.fetch_claimed_page(row["request_id"], claim, ex)
    assert L2.claim_next_fetch(row["request_id"], ex.mode).kind == "VERIFY"


# ── empties (F4) ─────────────────────────────────────────────────────────────────────────────────
def test_dense_empty_refuses_at_verify(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet", empty="dense_refuse")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    ex = _syn([(("daily", {"trade_date": "20260702"}, 0), _df([]))])   # columned EMPTY (real vendor shape)
    claim = _drive(L, row["request_id"], ex)
    assert claim.kind == "VERIFY"                     # dense-empty surfaces as a LOUD verify refusal
    with pytest.raises(rl.LedgerError, match="dense dataset verified with 0 rows"):
        L.verify_request(row["request_id"])


def test_sparse_empty_lifecycle_second_lease_then_canary(rig):
    rp, L = rig
    r_empty = _prow("moneyflow", "20260702", "req/mf/20260702.parquet", empty="sparse_canary")
    r_full = _prow("moneyflow", "20260703", "req/mf/20260703.parquet", empty="sparse_canary",
                   params={"trade_date": "20260703"})
    L._freeze_plan_unvalidated([r_empty, r_full])
    L.declare_run_mode("synthetic_nonpromotable")
    ex = _syn([(("moneyflow", {"trade_date": "20260703"}, 0), _df(["A.SZ"], date="20260703"))])
    # 1st empty attempt
    c1 = L.claim_next_fetch(r_empty["request_id"], ex.mode)
    assert c1.kind == "FETCH"
    L.fetch_claimed_page(r_empty["request_id"], c1, ex)
    # the lifecycle demands a SECOND independent empty lease — never VERIFY
    c2 = L.claim_next_fetch(r_empty["request_id"], ex.mode)
    assert c2.kind == "RETRY_EMPTY_CONFIRM" and c2.lease_id
    L.fetch_claimed_page(r_empty["request_id"], c2, ex)
    # two empties recorded, but no canary verified yet -> WAIT (VERIFY is never offered)
    assert L.claim_next_fetch(r_empty["request_id"], ex.mode).kind == "WAIT_FOR_CANARY"
    # verify the nonempty sibling -> deterministic canary appears
    assert _drive(L, r_full["request_id"], ex).kind == "VERIFY"
    L.verify_request(r_full["request_id"])
    c3 = L.claim_next_fetch(r_empty["request_id"], ex.mode)
    assert (c3.kind, c3.canary_request_id) == ("CONFIRM_EMPTY", r_full["request_id"])
    L.confirm_empty(r_empty["request_id"], canary_request_id=c3.canary_request_id)
    assert L.claim_next_fetch(r_empty["request_id"], ex.mode).kind == "SKIP_TERMINAL"


# ── response scope (F5) ──────────────────────────────────────────────────────────────────────────
def test_wrong_date_response_refuses(rig):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    ex = _syn([(("daily", {"trade_date": "20260702"}, 0), _df(["A.SZ"], date="20260703"))])  # WRONG date
    claim = L.claim_next_fetch(row["request_id"], ex.mode)
    with pytest.raises(rl.LedgerError, match="outside the requested scope"):
        L.fetch_claimed_page(row["request_id"], claim, ex)
    assert [r for r in L._load() if r.get("kind") == "lease_failed"]


def test_wrong_stock_response_refuses(rig):
    rp, L = rig
    row = _prow("income", "000001.SZ", "req/income/000001SZ.parquet",
                params={"ts_code": "000001.SZ"}, empty="sparse_canary", limit=2,
                nk=("ts_code", "end_date"))
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    wrong = pd.DataFrame({"ts_code": ["600000.SH"], "end_date": ["20231231"], "v": [1]})
    ex = _syn([(("income", {"ts_code": "000001.SZ"}, 0), wrong)])
    claim = L.claim_next_fetch(row["request_id"], ex.mode)
    with pytest.raises(rl.LedgerError, match="outside the requested scope"):
        L.fetch_claimed_page(row["request_id"], claim, ex)


# ── prepare_raw_page (F8) ────────────────────────────────────────────────────────────────────────
def test_top_list_pages_gain_the_row_payload_digest(rig):
    rp, L = rig
    row = _prow("top_list", "20260702", "req/top_list/20260702.parquet", empty="sparse_canary",
                nk=("ts_code", "trade_date", "reason"),
                dedup=("ts_code", "trade_date", "reason", "row_payload_digest"))
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    page = _df(["A.SZ", "B.SZ"], reason=["涨幅偏离", "换手率"])
    ex = _syn([(("top_list", {"trade_date": "20260702"}, 0), page)])
    L.fetch_claimed_page(row["request_id"], L.claim_next_fetch(row["request_id"], ex.mode), ex)
    ev = L.verify_request(row["request_id"])
    out = pd.read_parquet(rp.staging_data / ev["output_path"])
    assert "row_payload_digest" in out.columns and out["row_payload_digest"].nunique() == 2


def test_unregistered_derived_key_refuses_fail_closed(rig):
    rp, L = rig
    # report_rc's digest producer is deliberately unregistered until fan-out: refusing beats omitting
    row = _prow("report_rc", "202601", "req/rc/202601.parquet", empty="sparse_canary",
                params={"start_date": "20260101", "end_date": "20260131"},
                nk=("ts_code", "report_date", "report_rc_payload_digest"),
                scope={"rule_id": "report_date_in_range",
                       "checks": [["report_date", "date_in_range", ["20260101", "20260131"]]]},
                limit=3000)
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    page = pd.DataFrame({"ts_code": ["A.SZ"], "report_date": ["20260115"], "v": [1]})
    ex = _syn([(("report_rc", {"start_date": "20260101", "end_date": "20260131"}, 0), page)])
    claim = L.claim_next_fetch(row["request_id"], ex.mode)
    with pytest.raises(rl.LedgerError, match="no .* producer is registered"):
        L.fetch_claimed_page(row["request_id"], claim, ex)


# ── the canonical A01 merger (F9) ────────────────────────────────────────────────────────────────
def _legs(date="20260702"):
    daily = pd.DataFrame({"ts_code": ["A.SZ", "B.SZ"], "trade_date": [date] * 2,
                          "close": [10.0, 20.0], "vol": [1.0, 2.0], "raw_fetch_ts": ["t"] * 2})
    basic = pd.DataFrame({"ts_code": ["A.SZ", "B.SZ"], "trade_date": [date] * 2,
                          "close": [10.0, 20.0], "pe": [12.0, 8.0], "raw_fetch_ts": ["t"] * 2})
    adj = pd.DataFrame({"ts_code": ["A.SZ", "B.SZ"], "trade_date": [date] * 2,
                        "adj_factor": [1.1, 2.2], "raw_fetch_ts": ["t"] * 2})
    return daily, basic, adj


def test_merge_daily_legs_happy_and_aux_close_dropped():
    daily, basic, adj = _legs()
    m = ra.merge_daily_legs(daily, basic, adj, "20260702")
    assert len(m) == 2 and "adj_factor" in m.columns and "pe" in m.columns
    assert list(m.columns).count("close") == 1        # daily's close is canonical; aux close dropped
    assert not any(c.endswith(("_x", "_y")) for c in m.columns)


def test_merge_daily_legs_missing_adj_coverage_refuses():
    daily, basic, adj = _legs()
    adj = adj[adj["ts_code"] != "B.SZ"]               # B.SZ priced but no adj row
    with pytest.raises(RuntimeError, match="lack a positive adj_factor"):
        ra.merge_daily_legs(daily, basic, adj, "20260702")


def test_merge_daily_legs_duplicate_aux_key_refuses():
    daily, basic, adj = _legs()
    basic = pd.concat([basic, basic.iloc[[0]]], ignore_index=True)   # duplicate A.SZ in the aux leg
    with pytest.raises(Exception):                    # pandas one_to_one MergeError
        ra.merge_daily_legs(daily, basic, adj, "20260702")


def test_merge_daily_legs_wrong_date_leg_refuses():
    daily, basic, adj = _legs()
    adj.loc[0, "trade_date"] = "20260703"
    with pytest.raises(RuntimeError, match="ANOTHER date"):
        ra.merge_daily_legs(daily, basic, adj, "20260702")


# ── conservation (F7) ────────────────────────────────────────────────────────────────────────────
def test_digest_multiset_catches_drop_plus_duplicate():
    df = pd.DataFrame({"ts_code": ["A.SZ", "B.SZ", "C.SZ"], "end_date": ["20231231"] * 3,
                       "v": [1.0, 2.0, 3.0]})
    tampered = pd.concat([df.iloc[[0, 1, 1]]], ignore_index=True)    # drop C, duplicate B: SAME count
    assert len(tampered) == len(df)
    assert ra._digest_multiset(df) != ra._digest_multiset(tampered)  # count equality cannot pass this


# ── full-family E2E under the synthetic executor ─────────────────────────────────────────────────
def test_a01_family_end_to_end_synthetic(rig):
    rp, L = rig
    dates = ["20260702", "20260703"]
    rows, fixtures = [], []
    for d in dates:
        daily, basic, adj = _legs(d)
        for ep, df in (("daily", daily), ("daily_basic", basic), ("adj_factor", adj)):
            rows.append(_prow(ep, d, f"requests/A01/{ep}/{d}.parquet",
                              params={"trade_date": d}, dataset="market/daily"))
            fixtures.append(((ep, {"trade_date": d}, 0), df.drop(columns=["raw_fetch_ts"])))
    L._freeze_plan_unvalidated(rows)
    L.declare_run_mode("synthetic_nonpromotable")
    ex = _syn(fixtures)
    spec = ra.QUARTET["A01"]
    summary = ra.run_family(spec, L, ex)
    assert len(summary["verified"]) == 6 and not summary["failed"]
    result = ra.consolidate_family(spec, L)
    assert len(result["outputs"]) == 2
    for o in result["outputs"]:
        m = pd.read_parquet(rp.staging_data / o["path"])
        assert len(m) == 2 and "adj_factor" in m.columns and "pe" in m.columns
    assert any(r.get("event") == "family_consolidated" for r in L._load())
    with pytest.raises(rl.LedgerError, match="NOT promotable"):
        L.assert_run_promotable()


def test_income_repartition_end_to_end_multiset(rig):
    rp, L = rig
    stocks = {"000001.SZ": ["20230630", "20231231"], "600000.SH": ["20231231"]}
    rows, fixtures = [], []
    for ts, periods in stocks.items():
        rows.append(_prow("income", ts, f"requests/A03a/income/{ts}.parquet",
                          params={"ts_code": ts}, empty="sparse_canary", limit=2000,
                          nk=("ts_code", "end_date"), dataset="fundamentals/income"))
        fixtures.append((("income", {"ts_code": ts}, 0), pd.DataFrame(
            {"ts_code": [ts] * len(periods), "end_date": periods,
             "revenue": [float(i + 1) for i in range(len(periods))]})))
    L._freeze_plan_unvalidated(rows)
    L.declare_run_mode("synthetic_nonpromotable")
    spec = ra.FamilySpec("A03a", "fundamentals/income", ("income",), "ts_code",
                         ra.QUARTET["A03a"].consolidation)
    summary = ra.run_family(spec, L, _syn(fixtures))
    assert len(summary["verified"]) == 2 and not summary["failed"]
    result = ra.consolidate_family(spec, L)
    # per-stock inputs REPARTITIONED per end_date: 20230630 (1 row) + 20231231 (2 rows)
    parts = {o["partition"]: o["rows"] for o in result["outputs"]}
    assert parts == {"20230630": 1, "20231231": 2}


def test_top_list_confirmed_empty_date_omits_its_output(rig):
    rp, L = rig
    r_full = _prow("top_list", "20260702", "requests/A11a/top_list/20260702.parquet",
                   empty="sparse_canary", nk=("ts_code", "trade_date", "reason"),
                   dedup=("ts_code", "trade_date", "reason", "row_payload_digest"),
                   dataset="market/top_list")
    r_empty = _prow("top_list", "20260703", "requests/A11a/top_list/20260703.parquet",
                    params={"trade_date": "20260703"}, empty="sparse_canary",
                    nk=("ts_code", "trade_date", "reason"),
                    dedup=("ts_code", "trade_date", "reason", "row_payload_digest"),
                    dataset="market/top_list")
    L._freeze_plan_unvalidated([r_full, r_empty])
    L.declare_run_mode("synthetic_nonpromotable")
    fixtures = [(("top_list", {"trade_date": "20260702"}, 0), _df(["A.SZ"], reason=["涨幅偏离"]))]
    spec = ra.FamilySpec("A11a", "market/top_list", ("top_list",), "trade_date",
                         ra.QUARTET["A11a"].consolidation)
    summary = ra.run_family(spec, L, _syn(fixtures))
    assert len(summary["verified"]) == 1 and len(summary["confirmed_empty"]) == 1
    result = ra.consolidate_family(spec, L)
    assert [o["partition"] for o in result["outputs"]] == ["20260702"]   # the empty date has NO file


def test_broker_recommend_monthly_layout(rig):
    rp, L = rig
    rows, fixtures = [], []
    for m in ("202601", "202602"):
        rows.append(_prow("broker_recommend", m, f"requests/A16/broker_recommend/{m}.parquet",
                          params={"month": m}, empty="sparse_canary",
                          nk=("month", "broker", "ts_code"), dataset="analyst/broker_recommend"))
        fixtures.append((("broker_recommend", {"month": m}, 0), pd.DataFrame(
            {"month": [m], "broker": ["中信"], "ts_code": ["000001.SZ"]})))
    L._freeze_plan_unvalidated(rows)
    L.declare_run_mode("synthetic_nonpromotable")
    spec = ra.FamilySpec("A16", "analyst/broker_recommend", ("broker_recommend",), "month",
                         ra.QUARTET["A16"].consolidation)
    summary = ra.run_family(spec, L, _syn(fixtures))
    assert len(summary["verified"]) == 2
    result = ra.consolidate_family(spec, L)
    assert sorted(o["path"] for o in result["outputs"]) == [
        "consolidated/analyst/broker_recommend/broker_recommend_202601.parquet",
        "consolidated/analyst/broker_recommend/broker_recommend_202602.parquet"]


# ── bundle + lint pins ───────────────────────────────────────────────────────────────────────────
def test_live_run_refuses_a_drifted_bundle(rig, monkeypatch):
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("live_authorized")
    monkeypatch.setattr(ra, "compute_bundle_hash", lambda: "f" * 64)   # a dirty relevant file
    with pytest.raises(RuntimeError, match="bundle drifted"):
        ra.run_family(ra.QUARTET["A01"], L, _StubLiveExecutor(_df(["A.SZ"])))


def test_fetch_page_once_shape_lint():
    """Design v4 F1 lint: EXACTLY ONE wire call — no retry loop, no _safe_api_call, no pagination."""
    import inspect
    sys.path.insert(0, str(ROOT / "src"))
    import data_infra.fetchers as F
    src = inspect.getsource(F.TushareFetcher.fetch_page_once)
    body = src.split('"""')[-1]                        # strip the docstring
    for banned in ("for ", "while ", "_safe_api_call", "_fetch_paginated"):
        assert banned not in body, f"fetch_page_once must not contain {banned!r}"


def test_recipe_disjointness_is_enforced():
    bad = ra.CallRecipe("bad", "daily", (("trade_date", "limit"),), (), ("limit", "offset"))
    with pytest.raises(RuntimeError, match="disjointness"):
        ra.validate_recipe(bad)


# ── the REAL A01 plan at full scale through the coordinator's validation door ────────────────────
def test_real_a01_plan_scale_freeze(monkeypatch):
    """Builds the REAL A01 plan from the SIGNED contracts (3 legs x 4493 sessions = 13,479 requests)
    and freezes it through freeze_request_plan — full contract/population/merge-coverage validation,
    NO fetching. Proves the production path composes end-to-end at scale."""
    base = _recovery_test_root("planscale")
    monkeypatch.setattr(rrc, "RECOVERY_ROOT", base)
    rp = rrc.RecoveryPaths("scale")
    rp.create_root()
    ledger = rl.PageReceiptLedger(rp, coordinator_commit="deadbeef",
                                  adapter_bundle_hash=ra.compute_bundle_hash())
    contracts = rrc.load_signed_contracts()
    rows = ra.build_plan_rows(ra.QUARTET["A01"], contracts)
    assert len(rows) == 3 * 4493
    sha = ra.freeze_run_plan(ledger, [ra.QUARTET["A01"]], contracts)
    assert len(sha) == 64
    plan = ledger._plan()
    assert len(plan) == 13479
    shutil.rmtree(base, ignore_errors=True)
