# -*- coding: utf-8 -*-
"""Pre-fetch test matrix for the adapter quartet (design v4 acceptance §6).

Drives the FULL claimed-fetch machinery — atomic claim, executor invocation, prepare, response scope,
ledger-derived terminals, empty lifecycle, consolidation with typed conservation — under a
SyntheticExecutor (no Tushare import on this path). The battery sits below the contract layer (fake
contracts + the sanctioned per-instance seams), except the plan-scale test which freezes the REAL
signed A01 plan through the coordinator's full validation door. Runs under C:."""
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
    # Adapter drift must refuse a live fetch — but at the AUTHORIZATION, not by making the run
    # unopenable. This assertion used to read "hash-chain break", because the bundle hash was baked
    # into the chain genesis and any drift broke the replay at line 1. That coupling also meant a
    # DIFFERENT coordinator_commit (repo-wide git HEAD) bricked an in-flight run: three unrelated
    # commits from a parallel session did exactly that during the first live fetch. The genesis is now
    # a persisted per-run constant, so the run stays readable and the refusal comes from the check that
    # actually means what it says — and can be cleared by re-authorizing.
    L2 = rl.PageReceiptLedger(rp, coordinator_commit="deadbeef", adapter_bundle_hash="0" * 64)
    L2._revalidate_contract = L._revalidate_contract
    with pytest.raises(rl.LedgerError, match="DIFFERENT adapter bundle"):
        L2.claim_next_fetch(row["request_id"], "live_authorized")
    # and the point of the change: the run is still OPENABLE under the drifted identity, so a code fix
    # mid-recovery is recoverable by re-authorizing rather than by abandoning the run
    assert len(L2._load()) > 0
    assert L2._plan()[row["request_id"]]["endpoint"] == "daily"


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
    """A natural key demanding a coordinator-derived column with NO registered producer must REFUSE
    (silently omitting it would fail verification later with a misleading error). report_rc used to
    be this case; its producer is registered as of fan-out batch 2, so the invariant is pinned here
    with an endpoint that legitimately has no digest producer."""
    rp, L = rig
    req = {"trade_date": "20260702"}
    row = _prow("moneyflow", "20260702", "req/mf/20260702.parquet", params=req,
                empty="sparse_canary",
                nk=("ts_code", "trade_date", "row_payload_digest"))   # no producer for moneyflow
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    ex = _syn([(("moneyflow", req, 0), _df(["A.SZ"]))])
    claim = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    with pytest.raises(rl.LedgerError, match="no .* producer is registered"):
        L.fetch_claimed_page(row["request_id"], claim, ex)

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
    """Design v4 F1 lint: EXACTLY ONE wire call — no retry loop, no _safe_api_call, no pagination.
    Reads the SOURCE FILE (GPT impl-review minor: importing the fetcher module imports tushare, which
    made 'no Tushare import' false for the battery; the text is the fact being linted anyway)."""
    src = (ROOT / "src" / "data_infra" / "fetchers" / "__init__.py").read_text(encoding="utf-8")
    i = src.index("def fetch_page_once")
    j = src.index("\n    def ", i)                     # up to the next method
    body = src[i:j].split('"""')[-1]                   # strip the docstring
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


# ── GPT implementation-review fold: regression per finding ───────────────────────────────────────
def test_forged_claim_with_nonexistent_lease_refused(rig):
    """B1 (reproduced by GPT): a hand-built Claim with any lease id/offset was accepted and could
    verify a skipped page. The claim must bind to its DURABLE open lease."""
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet", limit=2)
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    ex = _syn([(("daily", {"trade_date": "20260702"}, 999999), _df(["Z.SZ"]))])
    forged = rl.Claim("FETCH", page=1, offset=999999, lease_id="f" * 32,
                      opened_at="2026-07-19T00:00:00+00:00")
    with pytest.raises(rl.LedgerError, match="does not exist in the ledger"):
        L.fetch_claimed_page(row["request_id"], forged, ex)
    assert not ex.calls                                # the executor was NEVER invoked


def test_altered_claim_offset_refused_without_killing_the_lease(rig):
    """B1: a claim whose page/offset differ from the durable lease is refused — and the refusal does
    NOT close the real lease (a forger cannot kill an in-flight fetch)."""
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet", limit=2)
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    real = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    assert real.kind == "FETCH"
    ex = _syn([(("daily", {"trade_date": "20260702"}, 0), _df(["A.SZ", "B.SZ"]))])
    import dataclasses
    altered = dataclasses.replace(real, offset=999999)
    with pytest.raises(rl.LedgerError, match="altered claim refused"):
        L.fetch_claimed_page(row["request_id"], altered, ex)
    # the REAL lease is intact: presenting the true claim still works
    res = L.fetch_claimed_page(row["request_id"], real, ex)
    assert res.row_count == 2


def test_legacy_fetch_page_is_default_off_and_mode_refused(rig):
    """B2 + re-review #2 (reproduced by GPT): 'refuse after mode declaration' alone was bypassable by
    fetching FIRST and declaring live_authorized after. The door is now DEFAULT-OFF (pre-mode fetching
    impossible in production), and a declared mode refuses even WITH the battery capability."""
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    invoked = []

    def _cb():
        invoked.append(1)
        return _df(["A.SZ"])
    # 1) BEFORE any mode declaration: the door is off by default (closes the fetch-then-declare hole)
    with pytest.raises(rl.LedgerError, match="legacy fetch_page is DISABLED"):
        L.fetch_page(row["request_id"], 1, _cb)
    # 2) even with the battery capability, a DECLARED run mode refuses
    L._legacy_fetch_enabled = True
    L.declare_run_mode("live_authorized")
    with pytest.raises(rl.LedgerError, match="legacy fetch_page is REFUSED"):
        L.fetch_page(row["request_id"], 1, _cb)
    assert not invoked                             # the callback NEVER ran, either way
    assert not [r for r in L._load() if r.get("kind") == "lease_open"]   # and no lease opened


def test_consolidation_refuses_a_drifted_bundle_and_repeats(rig, monkeypatch):
    """B3 (reproduced by GPT): the bundle was checked at run_family only, and consolidation could
    overwrite outputs on a second call. Both refuse now."""
    rp, L = rig
    m = "202601"
    rows = [_prow("broker_recommend", m, f"requests/A16/broker_recommend/{m}.parquet",
                  params={"month": m}, empty="sparse_canary",
                  nk=("month", "broker", "ts_code"), dataset="analyst/broker_recommend")]
    fixtures = [(("broker_recommend", {"month": m}, 0), pd.DataFrame(
        {"month": [m], "broker": ["ZX"], "ts_code": ["000001.SZ"]}))]
    L._freeze_plan_unvalidated(rows)
    L.declare_run_mode("synthetic_nonpromotable")
    spec = ra.FamilySpec("A16", "analyst/broker_recommend", ("broker_recommend",), "month",
                         ra.QUARTET["A16"].consolidation)
    assert len(ra.run_family(spec, L, _syn(fixtures))["verified"]) == 1
    # a drifted bundle refuses consolidation
    monkeypatch.setattr(ra, "compute_bundle_hash", lambda: "f" * 64)
    with pytest.raises(RuntimeError, match="bundle drifted"):
        ra.consolidate_family(spec, L)
    monkeypatch.undo()
    # the honest bundle consolidates ONCE; a repeat refuses (no overwrite of chained outputs)
    ra.consolidate_family(spec, L)
    with pytest.raises(RuntimeError, match="exactly once per run"):
        ra.consolidate_family(spec, L)


def test_post_claim_contract_refusal_closes_the_lease(rig):
    """MAJOR (reproduced by GPT): a contract-revalidation failure AFTER the claim escaped without
    closing the lease — every later claim was IN_FLIGHT forever. The refusal now records
    lease_failed, and the next claim is a RETRY."""
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    claim = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    _LIVE_CONTRACTS["daily"]["natural_key"] = ["ts_code", "trade_date", "EDITED"]   # contract drifts
    ex = _syn([(("daily", {"trade_date": "20260702"}, 0), _df(["A.SZ"]))])
    with pytest.raises(rl.LedgerError, match="CHANGED since the plan froze"):
        L.fetch_claimed_page(row["request_id"], claim, ex)
    nxt = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    assert nxt.kind == "RETRY_PAGE"                    # NOT IN_FLIGHT forever


def test_orphaned_lease_abandon_and_resume(rig):
    """MAJOR: a crash between lease-open and close left IN_FLIGHT forever. The EXPLICIT operator
    crash-resume transition converts the orphan and the claim re-issues the cursor."""
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")       # lease opened, then "crash"
    assert L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable").kind == "IN_FLIGHT"
    with pytest.raises(rl.LedgerError, match="auditable reason"):
        L.abandon_orphan_leases(row["request_id"], reason="  ")
    assert L.abandon_orphan_leases(row["request_id"], reason="crash-resume test") == 1
    nxt = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    assert (nxt.kind, nxt.page) == ("RETRY_PAGE", 1)
    ex = _syn([(("daily", {"trade_date": "20260702"}, 0), _df(["A.SZ"]))])
    L.fetch_claimed_page(row["request_id"], nxt, ex)
    assert L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable").kind == "VERIFY"


# ── GPT impl re-review #2 fold: concurrency/atomicity regressions ────────────────────────────────
def test_valid_claim_replay_cannot_reach_the_vendor_twice(rig):
    """re-review #2 (reproduced by GPT): two presenters of the SAME valid Claim both passed validation
    before the executor call — two real wire calls. The dispatch marker + the run-execution lock make
    a claim one-shot: a concurrent presenter refuses at the lock; a later presenter refuses on the
    dispatch/consumed state. Executor invocations == 1, always."""
    rp, L = rig
    L._exec_lock_timeout = 0.3                       # a concurrent presenter fails FAST in the test
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    claim = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    calls = []

    class _ReentrantExecutor:
        mode = "synthetic_nonpromotable"

        def run_page(self, spec):
            calls.append(1)
            # a CONCURRENT presenter of the SAME claim, while the first call is mid-flight:
            with pytest.raises(rl.LedgerError, match="run-execution lock BUSY"):
                L.fetch_claimed_page(row["request_id"], claim, self)
            return _df(["A.SZ"])
    res = L.fetch_claimed_page(row["request_id"], claim, _ReentrantExecutor())
    assert res.row_count == 1 and len(calls) == 1    # exactly ONE wire call ever happened
    # a SEQUENTIAL replay of the same claim (lease now consumed) also refuses
    with pytest.raises(rl.LedgerError, match="already consumed"):
        L.fetch_claimed_page(row["request_id"], claim, _ReentrantExecutor())
    assert len(calls) == 1


def test_abandon_refused_while_a_worker_holds_the_execution_lock(rig):
    """re-review #2: the reason string is audit, the LOCK is the mutual exclusion — abandoning while
    any worker is inside its dispatch->close span refuses at the lock."""
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    with L.execution_guard():                        # a live worker's span
        with pytest.raises(rl.LedgerError, match="run-execution lock BUSY"):
            L.abandon_orphan_leases(row["request_id"], reason="operator mid-flight — must refuse")


def test_abandoned_lease_can_never_close(rig):
    """re-review #2 (reproduced by GPT): after abandon + a successful retry, the ZOMBIE worker's close
    of the old lease still succeeded — two page-1 attempts. An abandoned lease now refuses at close
    AND at claim-binding."""
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    stale = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")   # worker A's claim
    assert L.abandon_orphan_leases(row["request_id"], reason="crash-resume") == 1
    ex = _syn([(("daily", {"trade_date": "20260702"}, 0), _df(["A.SZ"]))])
    # worker B retries and succeeds
    nxt = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    assert nxt.kind == "RETRY_PAGE"
    L.fetch_claimed_page(row["request_id"], nxt, ex)
    # zombie A returns: its claim refuses at binding (consumed), and a DIRECT close of the abandoned
    # lease refuses at the second guard
    with pytest.raises(rl.LedgerError, match="already consumed"):
        L.fetch_claimed_page(row["request_id"], stale, ex)
    with pytest.raises(rl.LedgerError, match="ABANDONED/FAILED"):
        L._close_lease_record(row["request_id"], stale.page, stale.lease_id, stale.opened_at,
                              _df(["Z.SZ"]), "single_page_contract")
    # exactly ONE page-1 attempt exists
    assert len([r for r in L._load() if r.get("kind") == "attempt"]) == 1


def test_direct_live_executor_call_is_not_a_thing(rig):
    """re-review #2 (reproduced by GPT): LiveExecutor.run_page was directly callable, reaching
    fetch_page_once with no ledger, run mode, or authorization. It now demands the one-shot
    dispatch token the ledger mints inside fetch_claimed_page."""
    rp, L = rig

    class _FetcherSpy:
        def __init__(self):
            self.calls = []

        def fetch_page_once(self, method, **kw):
            self.calls.append((method, kw))
            return _df(["A.SZ"])
    spy = _FetcherSpy()
    ex = ra.LiveExecutor(spy, L)
    spec = {"endpoint": "daily", "base_params": {"trade_date": "20260702"}, "limit": 0, "offset": 0,
            "page": 1, "recipe_id": "daily_by_trade_date", "pagination_mode": "single_page"}
    with pytest.raises(RuntimeError, match="no valid one-shot dispatch token"):
        ex.run_page(spec)                            # no token
    with pytest.raises(RuntimeError, match="no valid one-shot dispatch token"):
        ex.run_page(dict(spec, dispatch_token="guessed"))   # a guessed token
    assert not spy.calls                             # the vendor door NEVER opened


def test_any_post_claim_exception_closes_the_lease(rig):
    """re-review #2 (reproduced by GPT): a NON-LedgerError failure inside the close (e.g. Arrow
    serialization) escaped the per-site handlers and left the lease IN_FLIGHT forever. The total
    safety net closes it; the next claim is a RETRY."""
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    # a response pyarrow cannot serialize (a function object in a column) — passes scope, dies at
    # the serialization step inside the ledger, NOT in a per-site LedgerError handler
    bad = pd.DataFrame({"ts_code": ["A.SZ"], "trade_date": ["20260702"], "poison": [len]})
    ex = _syn([(("daily", {"trade_date": "20260702"}, 0), bad)])
    claim = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    with pytest.raises(Exception):
        L.fetch_claimed_page(row["request_id"], claim, ex)
    nxt = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    assert nxt.kind == "RETRY_PAGE"                  # closed as lease_failed, NOT IN_FLIGHT forever


def test_consolidation_serializes_on_the_execution_lock(rig):
    """re-review #2: the singleton check and the final event are now inside the SAME execution-lock
    span — a second consolidator serializes at the lock and then refuses on the event it sees."""
    rp, L = rig
    L._exec_lock_timeout = 0.3
    m = "202601"
    rows = [_prow("broker_recommend", m, f"requests/A16/broker_recommend/{m}.parquet",
                  params={"month": m}, empty="sparse_canary",
                  nk=("month", "broker", "ts_code"), dataset="analyst/broker_recommend")]
    fixtures = [(("broker_recommend", {"month": m}, 0), pd.DataFrame(
        {"month": [m], "broker": ["ZX"], "ts_code": ["000001.SZ"]}))]
    L._freeze_plan_unvalidated(rows)
    L.declare_run_mode("synthetic_nonpromotable")
    spec = ra.FamilySpec("A16", "analyst/broker_recommend", ("broker_recommend",), "month",
                         ra.QUARTET["A16"].consolidation)
    assert len(ra.run_family(spec, L, _syn(fixtures))["verified"]) == 1
    # while another worker holds the execution lock, consolidation refuses (no TOCTOU window)
    with L.execution_guard():
        with pytest.raises(rl.LedgerError, match="run-execution lock BUSY"):
            ra.consolidate_family(spec, L)
    ra.consolidate_family(spec, L)                   # the lock free -> consolidates exactly once
    with pytest.raises(RuntimeError, match="exactly once per run"):
        ra.consolidate_family(spec, L)


# ── GPT impl re-review #3 fold: token-binds-spec + lock-through-no-follow ─────────────────────────
class _FetcherSpy:
    def __init__(self):
        self.calls = []

    def fetch_page_once(self, method, **kw):
        self.calls.append((method, kw))
        return _df(["A.SZ"])


def _authorize_live(L, row, scope):
    from datetime import datetime, timedelta, timezone
    L.declare_run_mode("live_authorized")
    fut = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    L.record_fetch_authorization(actor="henry", expires_at=fut, endpoint_scope=scope)


def test_honest_live_executor_reaches_the_vendor_once(rig):
    """Positive control: the token-binds-spec check does not break the normal LiveExecutor path."""
    rp, L = rig
    # a real signed daily contract so the live contract re-bind passes
    _LIVE_CONTRACTS["daily"] = rrc.load_signed_contracts()["daily"]
    c = _LIVE_CONTRACTS["daily"]
    row = _prow("daily", "20260702", "req/daily/20260702.parquet",
                nk=tuple(c["natural_key"]))
    row["contract_sha256"] = rrc.canonical_contract_sha256(c)
    row["recipe_id"] = "daily_by_trade_date"
    L._revalidate_contract = lambda r: None            # below-contract: skip the doc revalidation
    L._assert_response_fields = lambda ep, cols: None
    L._freeze_plan_unvalidated([row])
    _authorize_live(L, row, ["daily"])
    spy = _FetcherSpy()
    ex = ra.LiveExecutor(spy, L)
    claim = L.claim_next_fetch(row["request_id"], "live_authorized")
    L.fetch_claimed_page(row["request_id"], claim, ex)
    assert spy.calls == [("daily", {"trade_date": "20260702"})]   # exactly the dispatched request


def test_valid_token_cannot_swap_the_request_out_of_scope(rig):
    """P0 (reproduced by GPT): a wrapping executor kept a valid `daily` dispatch token but swapped the
    spec to broker_recommend — the ledger recorded `daily` while the vendor got broker_recommend,
    escaping the §13 endpoint scope. The token is now BOUND to the frozen spec."""
    rp, L = rig
    _LIVE_CONTRACTS["daily"] = rrc.load_signed_contracts()["daily"]
    c = _LIVE_CONTRACTS["daily"]
    row = _prow("daily", "20260702", "req/daily/20260702.parquet", nk=tuple(c["natural_key"]))
    row["contract_sha256"] = rrc.canonical_contract_sha256(c)
    row["recipe_id"] = "daily_by_trade_date"
    L._revalidate_contract = lambda r: None
    L._assert_response_fields = lambda ep, cols: None
    L._freeze_plan_unvalidated([row])
    _authorize_live(L, row, ["daily"])                 # ONLY daily is authorized
    spy = _FetcherSpy()
    inner = ra.LiveExecutor(spy, L)

    class _SwapExecutor:
        mode = "live_authorized"

        def run_page(self, spec):
            swapped = dict(spec, endpoint="broker_recommend",
                           recipe_id="broker_recommend_by_month",
                           base_params={"month": "202601"}, pagination_mode="single_page", limit=0)
            return inner.run_page(swapped)             # keeps the VALID dispatch_token
    claim = L.claim_next_fetch(row["request_id"], "live_authorized")
    with pytest.raises(rl.LedgerError, match="dispatch token spec MISMATCH"):
        L.fetch_claimed_page(row["request_id"], claim, _SwapExecutor())
    assert spy.calls == []                             # broker_recommend NEVER reached the vendor
    # and the lease closed as failed, not IN_FLIGHT
    assert L.claim_next_fetch(row["request_id"], "live_authorized").kind == "RETRY_PAGE"


def test_execution_guard_refuses_a_junctioned_ledger_dir_without_touching_external(rig, tmp_path):
    """P0 (reproduced by GPT): execution_guard built a FileLock on the RAW path before any no-follow
    check, so a junction at <run>/ledger created (and on release DELETED) a lock file OUTSIDE the run
    root. The lock path now goes through rp.assert_write -> broker.validate_ancestry."""
    import subprocess
    rp, L = rig
    external = _recovery_test_root("external_target")
    external.mkdir(parents=True, exist_ok=True)
    sentinel = external / "run_execution.lock"
    sentinel.write_bytes(b"pre-existing external file")
    ledger_dir = rp.root / "ledger"
    assert not ledger_dir.exists()                     # rig has not written the ledger yet
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(ledger_dir), str(external)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"mklink unavailable: {r.stderr}")
    try:
        with pytest.raises(RuntimeError, match="REFUSED|reparse|junction"):
            with L.execution_guard():
                pass
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(ledger_dir)], capture_output=True, text=True)
    # the external file was NEITHER created-then-deleted NOR modified by the guard
    assert sentinel.exists() and sentinel.read_bytes() == b"pre-existing external file"


# ── GPT impl re-review #4 fold: the validate-then-swap TOCTOU is closed by handle-relative locking ─
def test_lock_closes_the_validate_then_swap_toctou(rig):
    """P0 (reproduced by GPT): assert_write validated the honest path, THEN FileLock(str(path))
    re-opened it by pathname — a junction swapped into <run>/ledger in that window was followed. The
    handle-bound broker lock is immune: the parent chain is opened RELATIVE to held handles, so a
    junction swapped in AFTER validation opens as the reparse point and is refused. Here we ARM the
    swap in the instant after validate_ancestry returns and prove the lock still refuses without
    touching the external target."""
    import subprocess
    rp, L = rig
    external = _recovery_test_root("toctou_target")
    external.mkdir(parents=True, exist_ok=True)
    sentinel = external / "run_execution.lock"
    sentinel.write_bytes(b"external pre-existing lock")
    ledger_dir = rp.root / "ledger"
    assert not ledger_dir.exists()                 # rig has not written the ledger yet

    broker = rp.broker()
    orig_validate = broker.validate_ancestry
    armed = {"done": False}

    def _validate_then_swap(target):
        result = orig_validate(target)             # validation SUCCEEDS on the honest path
        if not armed["done"]:                      # ...then the attacker wins the race, ONCE
            r = subprocess.run(["cmd", "/c", "mklink", "/J", str(ledger_dir), str(external)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                pytest.skip(f"mklink unavailable: {r.stderr}")
            armed["done"] = True
        return result
    broker.validate_ancestry = _validate_then_swap
    try:
        # execution_guard validates (swap fires), then opens the handle chain -> the junctioned
        # `ledger` component opens as a reparse point and is REFUSED
        with pytest.raises(rl.LedgerError, match="reparse|BUSY|refus"):
            with L.execution_guard():
                pass
    finally:
        broker.validate_ancestry = orig_validate
        subprocess.run(["cmd", "/c", "rmdir", str(ledger_dir)], capture_output=True, text=True)
    # the external target was NEVER opened, created, or deleted through the swap
    assert sentinel.exists() and sentinel.read_bytes() == b"external pre-existing lock"


def test_handle_lock_provides_real_cross_object_mutual_exclusion(rig):
    """The handle-bound lock still mutually excludes (a second holder of the same run lock refuses),
    proving the swap fix did not weaken the lock itself."""
    rp, L = rig
    with L.execution_guard():
        with pytest.raises(rl.LedgerError, match="BUSY"):
            with L.execution_guard(timeout=0.2):
                pass
    # released -> re-acquirable
    with L.execution_guard():
        pass


def test_handle_lock_file_is_not_deleted_on_release(rig):
    """The old FileLock deleted its lock file on release (which is how it removed an external file
    under a junction). The handle lock leaves a persistent zero-byte lock file in the run root."""
    rp, L = rig
    with L.execution_guard():
        pass
    lock_file = rp.root / "ledger" / "run_execution.lock"
    assert lock_file.is_file()                     # persists; a later acquire reuses it


# ── GPT impl re-review #5 fold: the lock leaf must not be deletable while held ────────────────────
def _child_unlink(path) -> str:
    """Try to delete `path` from a SEPARATE PROCESS; return SUCCEEDED / FAILED:<err>."""
    import subprocess
    code = ("import os,sys\n"
            "try:\n"
            "    os.unlink(sys.argv[1])\n"
            "    print('SUCCEEDED')\n"
            "except OSError as e:\n"
            "    print('FAILED:' + type(e).__name__)\n")
    r = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True)
    return r.stdout.strip()


def _child_replace(path) -> str:
    """Try to os.replace() another file OVER `path` from a separate process."""
    import subprocess
    code = ("import os,sys\n"
            "tmp = sys.argv[1] + '.usurper'\n"
            "open(tmp,'wb').write(b'x')\n"
            "try:\n"
            "    os.replace(tmp, sys.argv[1])\n"
            "    print('SUCCEEDED')\n"
            "except OSError as e:\n"
            "    print('FAILED:' + type(e).__name__)\n"
            "finally:\n"
            "    os.path.exists(tmp) and os.unlink(tmp)\n")
    r = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True)
    return r.stdout.strip()


def test_held_lock_file_cannot_be_unlinked_or_replaced_crossprocess(rig):
    """P0 (reproduced by GPT): the lock leaf was opened with FILE_SHARE_DELETE, so another process
    could unlink run_execution.lock while it was HELD — a new file then appeared at the same pathname
    and a SECOND execution_guard acquired, destroying mutual exclusion for the dispatch->call->close
    span (and for abandon/consolidation, which share the guard). The leaf now omits FILE_SHARE_DELETE."""
    rp, L = rig
    lock_path = rp.root / "ledger" / "run_execution.lock"
    with L.execution_guard():
        assert lock_path.is_file()
        # a SEPARATE PROCESS must not be able to delete or usurp the held lock file
        assert _child_unlink(lock_path).startswith("FAILED"), "held lock file was DELETED cross-process"
        assert _child_replace(lock_path).startswith("FAILED"), "held lock file was REPLACED cross-process"
        # and the identity cannot be switched out from under us: a second holder stays BUSY
        with pytest.raises(rl.LedgerError, match="BUSY"):
            with L.execution_guard(timeout=0.2):
                pass
    # after release the file still exists (never deleted) and is re-acquirable
    assert lock_path.is_file()
    with L.execution_guard(timeout=5.0):
        pass


def test_held_ledger_lock_file_cannot_be_unlinked_crossprocess(rig):
    """The same protection on the unified RecoveryPaths._lock leaf (the hot per-append lock)."""
    rp, L = rig
    lock_path = Path(str(rp.ledger_path) + ".lock")
    with rp._lock():
        assert lock_path.is_file()
        assert _child_unlink(lock_path).startswith("FAILED"), "held ledger lock was DELETED cross-process"
    assert lock_path.is_file()


def test_write_leaf_is_immovable_while_open_and_free_after_close(rig):
    """GPT impl re-review #8: the previous version of this test asserted that a child process COULD
    delete the file while the write handle was open, and called that a 'delete-sharing control' — it
    was in fact a direct demonstration of the escape window (the held object could be renamed out of
    the root mid-write). The correct invariant: while the write is IN FLIGHT the leaf cannot be
    deleted or renamed; once the handles close, ordinary replace/delete works again, so staged-output
    cleanup is not permanently sacrificed."""
    rp, L = rig
    target = rp.staging_data / "share_probe" / "x.bin"
    rp.broker().mkdirs(target.parent)
    with rp.broker().open_for_write(target, "wb") as fh:
        fh.write(b"payload")
        fh.flush()
        assert _child_unlink(target).startswith("FAILED"), \
            "the in-flight write leaf was DELETED cross-process"
        assert _child_replace(target).startswith("FAILED"), \
            "the in-flight write leaf was RENAMED/REPLACED cross-process"
    # after close: normal filesystem semantics return
    assert target.read_bytes() == b"payload"
    assert _child_unlink(target).startswith("SUCCEEDED"), \
        "staged outputs must remain deletable once no handle is held"
    assert not target.exists()

def _child_parent_swap(ledger_dir) -> str:
    """From a SEPARATE PROCESS: rename <run>/ledger aside and recreate a fresh dir at that pathname —
    the identity-switch GPT exploited in the parent-open -> leaf-open window."""
    import subprocess
    code = ("import os,sys\n"
            "d = sys.argv[1]\n"
            "try:\n"
            "    os.rename(d, d + '_moved')\n"
            "    os.mkdir(d)\n"
            "    print('SWAP_SUCCEEDED')\n"
            "except OSError as e:\n"
            "    print('SWAP_FAILED:' + type(e).__name__)\n")
    r = subprocess.run([sys.executable, "-c", code, str(ledger_dir)], capture_output=True, text=True)
    return r.stdout.strip()


def test_parent_dir_cannot_be_swapped_in_the_parent_open_to_leaf_open_window(rig):
    """P0 (reproduced by GPT): _root_handle/_dir_handle_chain opened directories WITH
    FILE_SHARE_DELETE, so in the instant between the `ledger` handle opening and the lock leaf being
    created, another process could rename `ledger` aside and mkdir a fresh one — holder A then locked
    under `ledger_moved` while holder B locked the NEW `<run>/ledger/run_execution.lock`. The whole
    lock chain (root + intermediates + leaf) now forbids delete-sharing. Here the swap is ARMED to
    fire in exactly that window."""
    rp, L = rig
    ledger_dir = rp.root / "ledger"
    rp.broker().mkdirs(ledger_dir)                 # the dir exists before the guard runs
    broker = rp.broker()
    orig_chain = broker._dir_handle_chain
    seen = {}

    def _chain_then_swap(rel_parts, *, create, share=None):
        h = orig_chain(rel_parts, create=create, share=share)
        if "swap" not in seen:                     # fire ONCE, in the parent-open -> leaf-open window
            seen["swap"] = _child_parent_swap(ledger_dir)
        return h
    broker._dir_handle_chain = _chain_then_swap
    try:
        with L.execution_guard():
            assert seen["swap"].startswith("SWAP_FAILED"), \
                f"the ledger dir was RENAMED while its handle was held: {seen['swap']}"
            # the lock lives at the real pathname (not under a moved tree) and excludes a 2nd holder
            assert (ledger_dir / "run_execution.lock").is_file()
            assert not (rp.root / "ledger_moved").exists()
            with pytest.raises(rl.LedgerError, match="BUSY"):
                with L.execution_guard(timeout=0.2):
                    pass
    finally:
        broker._dir_handle_chain = orig_chain


def test_run_root_cannot_be_renamed_while_a_lock_is_held(rig):
    """The same protection one level up: the RUN ROOT is opened without delete-sharing for a lock, so
    it cannot be renamed out from under a held guard."""
    import subprocess
    rp, L = rig
    with L.execution_guard():
        code = ("import os,sys\n"
                "try:\n"
                "    os.rename(sys.argv[1], sys.argv[1] + '_moved')\n"
                "    print('SWAP_SUCCEEDED')\n"
                "except OSError as e:\n"
                "    print('SWAP_FAILED:' + type(e).__name__)\n")
        r = subprocess.run([sys.executable, "-c", code, str(rp.root)], capture_output=True, text=True)
        assert r.stdout.strip().startswith("SWAP_FAILED"), "run root was renamed while a lock was held"


def test_ledger_lock_parent_chain_is_also_delete_protected(rig):
    """The unified RecoveryPaths._lock leaf shares the hardened chain."""
    rp, L = rig
    ledger_dir = rp.root / "ledger"
    rp.broker().mkdirs(ledger_dir)
    with rp._lock():
        assert _child_parent_swap(ledger_dir).startswith("SWAP_FAILED")


# ── GPT impl re-review #7 fold: ancestor-of-root bootstrap + post-write path re-walk ──────────────
def _mk_junction(link: Path, target: Path) -> bool:
    import subprocess
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                       capture_output=True, text=True)
    return r.returncode == 0


def _ancestor_swap_rig(tag: str):
    """Build <base>/<parent>/run with an EXTERNAL twin, so <parent> can be swapped for a junction.
    Returns (parent_dir, run_root, external_parent, external_run)."""
    base = _recovery_test_root(tag)
    parent = base / "recovery_root"
    run = parent / "run1"
    run.mkdir(parents=True)
    external_parent = base / "external_root"
    external_run = external_parent / "run1"
    external_run.mkdir(parents=True)
    return parent, run, external_parent, external_run


def test_ancestor_of_root_swapped_after_construction_is_refused(rig):
    """P0-1 (reproduced by GPT): the broker opened the run root with CreateFileW(str(root)), which
    resolves the WHOLE pathname — so an ANCESTOR of the run root (RECOVERY_ROOT) swapped for a junction
    redirected every 'validated' write outside. The root is now walked from the VOLUME ANCHOR,
    component-by-component, handle-relative + no-follow, and its object identity is re-checked."""
    import subprocess
    parent, run, external_parent, external_run = _ancestor_swap_rig("anc_post")
    broker = rrc.NoFollowWriteBroker(run)                  # constructed on the HONEST tree
    sentinel = external_run / "escaped.bin"
    # swap the ANCESTOR: rename <parent> aside, junction it to the external twin
    subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(parent) + "_moved"],
                   capture_output=True, text=True)
    os.rename(parent, str(parent) + "_moved")
    if not _mk_junction(parent, external_parent):
        os.rename(str(parent) + "_moved", parent)
        pytest.skip("mklink unavailable")
    try:
        # every write surface must refuse: the pathname now resolves to a DIFFERENT directory object
        with pytest.raises(Exception):
            with broker.open_for_write(run / "escaped.bin", "wb") as fh:
                fh.write(b"escaped-through-root-bootstrap")
        with pytest.raises(Exception):
            with broker.file_lock(run / "x.lock"):
                pass
        assert not sentinel.exists(), "a write escaped to the external tree through the swapped ancestor"
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(parent)], capture_output=True, text=True)
        os.rename(str(parent) + "_moved", parent)


def test_ancestor_junction_present_before_broker_construction_is_refused():
    """P0-1, the harder half (GPT): if the ancestor swap happens BEFORE the broker is constructed, it
    would cache the EXTERNAL directory's identity as legitimate — so an id comparison alone can never
    catch it. The volume-anchored walk refuses the junctioned ancestor at CONSTRUCTION time."""
    import subprocess
    parent, run, external_parent, external_run = _ancestor_swap_rig("anc_pre")
    os.rename(parent, str(parent) + "_moved")
    if not _mk_junction(parent, external_parent):
        os.rename(str(parent) + "_moved", parent)
        pytest.skip("mklink unavailable")
    try:
        # the run pathname "exists" (via the junction) but its ancestry contains a reparse point
        with pytest.raises(Exception, match="reparse|REFUSED"):
            rrc.NoFollowWriteBroker(run)
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(parent)], capture_output=True, text=True)
        os.rename(str(parent) + "_moved", parent)


def test_write_json_rename_cannot_escape_via_a_post_write_parent_swap(rig):
    """P0-2 (reproduced by GPT): write_json wrote the temp file safely, then os.replace(tmp, path)
    RE-WALKED both pathnames — a parent swapped in that window atomically placed the JSON OUTSIDE the
    run root (`crossproc_post_write_parent_swap=SWAP_SUCCEEDED` / `external_json_created=True`). The
    rename is now handle-relative (NtSetInformationFile with a held RootDirectory), so the swap still
    SUCCEEDS but the rename REFUSES and nothing lands outside."""
    import subprocess
    rp, L = rig
    external = _recovery_test_root("json_escape_target")
    external.mkdir(parents=True, exist_ok=True)
    reports = rp.reports
    rp.broker().mkdirs(reports)
    tmp, final = reports / "p.json.tmp", reports / "p.json"
    with rp.broker().open_for_write(tmp, "w") as fh:      # temp written safely
        fh.write("{}")
    # the EXACT window: temp on disk, rename not yet issued -> swap the parent for a junction
    os.rename(reports, str(reports) + "_moved")
    if not _mk_junction(reports, external):
        os.rename(str(reports) + "_moved", reports)
        pytest.skip("mklink unavailable")
    try:
        with pytest.raises(Exception, match="reparse|REFUSED"):
            rp.broker().replace_into(tmp, final)
        assert not (external / "p.json").exists(), "the JSON escaped the run root via the rename"
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(reports)], capture_output=True, text=True)
        os.rename(str(reports) + "_moved", reports)


def test_replace_into_refuses_cross_parent_rename(rig):
    """replace_into is single-parent by construction (both names resolve under ONE held handle)."""
    rp, L = rig
    rp.broker().mkdirs(rp.staging_data / "a")
    rp.broker().mkdirs(rp.staging_data / "b")
    src = rp.staging_data / "a" / "x.tmp"
    with rp.broker().open_for_write(src, "wb") as fh:
        fh.write(b"x")
    with pytest.raises(Exception, match="one parent"):
        rp.broker().replace_into(src, rp.staging_data / "b" / "x.bin")


def test_write_json_still_works_and_is_atomic(rig):
    """Positive control: the handle-relative rename preserves write_json's normal behaviour."""
    rp, L = rig
    target = rp.reports / "ok.json"
    rp.write_json(target, {"hello": "world"})
    import json as _json
    assert _json.loads(target.read_text(encoding="utf-8")) == {"hello": "world"}
    assert not list(target.parent.glob("*.tmp"))       # the temp file was renamed away, not left behind


# ── GPT impl re-review #8 fold: create_root + write-chain object-move windows ─────────────────────
def test_create_root_cannot_escape_through_a_swapped_ancestor():
    """P0 (reproduced by GPT: `external_run_created=True`): create_root did
    Path.mkdir(parents=True) AFTER the lexical ancestor check, so a junction swapped into an ancestor
    in that window created the run root INSIDE the external target. Creation now walks from the volume
    anchor, handle-relative."""
    import subprocess
    base = _recovery_test_root("create_escape")
    parent = base / "recovery_root"
    parent.mkdir(parents=True)
    external = base / "external_root"
    external.mkdir(parents=True)
    os.rename(parent, str(parent) + "_moved")
    if not _mk_junction(parent, external):
        os.rename(str(parent) + "_moved", parent)
        pytest.skip("mklink unavailable")
    try:
        with pytest.raises(Exception, match="reparse|REFUSED"):
            rrc.create_dir_tree_no_follow(parent / "run1")
        assert not (external / "run1").exists(), "the run root was created in the EXTERNAL tree"
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(parent)], capture_output=True, text=True)
        os.rename(str(parent) + "_moved", parent)


def test_anchored_create_builds_parents_and_refuses_an_existing_leaf():
    """Positive control: the anchored creator behaves like mkdir(parents=True, exist_ok=False)."""
    base = _recovery_test_root("create_ok")
    target = base / "a" / "b" / "run1"
    rrc.create_dir_tree_no_follow(target)
    assert target.is_dir() and (base / "a" / "b").is_dir()
    with pytest.raises(Exception):
        rrc.create_dir_tree_no_follow(target)


def test_run_root_cannot_be_moved_during_an_active_write(rig):
    """P0 (reproduced by GPT): the non-lock write chain used default delete-sharing, so the held ROOT
    (or an intermediate dir) could be RENAMED out of the run root mid-operation and the bytes landed in
    the moved external tree. The write chain now forbids delete-sharing for the DURATION."""
    import subprocess
    rp, L = rig
    target = rp.staging_data / "movetest" / "x.bin"
    rp.broker().mkdirs(target.parent)
    with rp.broker().open_for_write(target, "wb") as fh:
        fh.write(b"a")
        fh.flush()
        assert _child_parent_swap(target.parent).startswith("SWAP_FAILED")
        code = ("import os,sys\n"
                "try:\n"
                "    os.rename(sys.argv[1], sys.argv[1] + '_moved'); print('SWAP_SUCCEEDED')\n"
                "except OSError as e:\n"
                "    print('SWAP_FAILED:' + type(e).__name__)\n")
        r = subprocess.run([sys.executable, "-c", code, str(rp.root)], capture_output=True, text=True)
        assert r.stdout.strip().startswith("SWAP_FAILED"), "the run root moved during an active write"
    assert target.read_bytes() == b"a"


def test_replace_into_completes_inside_the_root_and_parent_is_free_between_ops(rig):
    """The rename chain forbids delete-sharing DURING the operation; between operations the tree is
    ordinary (movable/removable), which is the intended trade-off."""
    rp, L = rig
    d = rp.staging_data / "renametest"
    rp.broker().mkdirs(d)
    tmp, final = d / "x.tmp", d / "x.bin"
    with rp.broker().open_for_write(tmp, "wb") as fh:
        fh.write(b"payload")
    rp.broker().replace_into(tmp, final)
    assert final.read_bytes() == b"payload" and not tmp.exists()


# ── fan-out batch 1: the 22 newly-bound families ─────────────────────────────────────────────────
def test_every_fanned_out_family_builds_a_valid_plan_from_signed_contracts():
    """Every bound family must build a plan from the SIGNED contracts with unique request_ids AND
    unique receipt_outputs (the freeze refuses either collision), and its recipe must agree with the
    signed pagination mode."""
    contracts = rrc.load_signed_contracts()
    total = 0
    for owner, spec in sorted(ra.ALL_FAMILIES.items()):
        rows = ra.build_plan_rows(spec, contracts)
        assert rows, f"{owner}: empty plan"
        ids = {r["request_id"] for r in rows}
        outs = {r["receipt_output"] for r in rows}
        assert len(ids) == len(rows), f"{owner}: duplicate request_id"
        assert len(outs) == len(rows), f"{owner}: two requests share a receipt_output"
        for r in rows:
            assert r["recipe_id"] == ra.ENDPOINT_RECIPE[r["endpoint"]]
            assert r["response_scope"]["checks"], f"{owner}: an unscoped request was planned"
        total += len(rows)
    assert len(ra.ALL_FAMILIES) == 29      # quartet + batch 1 + batch 2
    assert total > 90_000, f"expected the full recovery scale, got {total}"


def test_period_report_type_uses_a_composite_partition(rig):
    """The direct-quarter VIP families send (period, report_type). Under a single partition key both
    requests would collapse to the same partition -> the same receipt_output -> freeze refusal."""
    contracts = rrc.load_signed_contracts()
    rows = ra.build_plan_rows(ra.ALL_FAMILIES["A04a"], contracts)
    parts = {r["partition"] for r in rows}
    assert len(parts) == len(rows)                     # every (period, type) is its own partition
    assert any(p.endswith("_2") for p in parts) and any(p.endswith("_3") for p in parts)


def test_multi_family_run_level_freeze(monkeypatch):
    """freeze_run_plan is ONCE per run across MANY families (design v4 F6). Freeze several small
    families together through the coordinator's full validation door — no fetching."""
    base = _recovery_test_root("multifam")
    monkeypatch.setattr(rrc, "RECOVERY_ROOT", base)
    rp = rrc.RecoveryPaths("mf")
    rp.create_root()
    ledger = rl.PageReceiptLedger(rp, coordinator_commit="deadbeef",
                                  adapter_bundle_hash=ra.compute_bundle_hash())
    contracts = rrc.load_signed_contracts()
    specs = [ra.ALL_FAMILIES[o] for o in ("A02", "A15a", "A15c", "A15g", "A16")]
    sha = ra.freeze_run_plan(ledger, specs, contracts)
    assert len(sha) == 64
    plan = ledger._plan()
    assert len(plan) == sum(len(ra.build_plan_rows(s, contracts)) for s in specs)
    assert {r["dataset"] for r in plan.values()} == {s.output_family for s in specs}
    shutil.rmtree(base, ignore_errors=True)


def test_every_bound_endpoint_has_a_response_scope_rule():
    """A bound endpoint with no declared scope rule would plan UNSCOPED requests."""
    for ep in ra.ENDPOINT_RECIPE:
        assert ep in ra._SCOPE_RULES, f"{ep}: bound to a recipe but has no response-scope rule"
    with pytest.raises(RuntimeError, match="no declared response-scope rule"):
        ra.response_scope_of("not_an_endpoint", {"trade_date": "20260702"})


def test_scope_rules_map_request_keys_to_the_right_response_columns():
    """The rule table is the fix for the old heuristic: a `period` request scopes the response's
    `end_date`, a year range scopes `ann_date`, a month range scopes `report_date`."""
    assert ra.response_scope_of("fina_mainbz", {"period": "20231231"})["checks"] == \
        [["end_date", "eq", "20231231"]]
    assert ra.response_scope_of("income_vip", {"period": "20231231", "report_type": "2"})["checks"] == \
        [["end_date", "eq", "20231231"], ["report_type", "eq", "2"]]
    assert ra.response_scope_of("repurchase", {"start_date": "20230101", "end_date": "20231231"})["checks"] == \
        [["ann_date", "date_in_range", ["20230101", "20231231"]]]
    assert ra.response_scope_of("report_rc", {"start_date": "20230101", "end_date": "20230131"})["checks"] == \
        [["report_date", "date_in_range", ["20230101", "20230131"]]]


def test_deferred_families_are_declared_with_reasons():
    """The families NOT bound in this batch are declared explicitly with why — never silently absent."""
    # after batch 2 only the UNSIGNED family remains deferred
    assert set(ra.DEFERRED_FAMILIES) == {"A07"}
    for owner, reason in ra.DEFERRED_FAMILIES.items():
        assert owner not in ra.ALL_FAMILIES
        assert len(reason) > 40
    # A10a is not "missing": it is produced as a SECOND LAYOUT of the A10 fetch, declared as such
    assert set(ra.CONSOLIDATED_AS_SECOND_LAYOUT) == {"A10a"}
    assert "market/suspension" in [c.label for c in ra.ALL_FAMILIES["A10"].consolidations]


# ── E2E under the synthetic executor: one representative per NEWLY-COVERED shape ──────────────────
def _run_family_e2e(rp, L, spec, rows, fixtures):
    L._freeze_plan_unvalidated(rows)
    L.declare_run_mode("synthetic_nonpromotable")
    summary = ra.run_family(spec, L, _syn(fixtures))
    assert not summary["failed"], summary["failed"]
    return summary, ra.consolidate_family(spec, L)


def test_e2e_per_period_family(rig):
    """NEW shape: a `period` request whose ROWS carry end_date (fina_mainbz)."""
    rp, L = rig
    spec = ra.ALL_FAMILIES["A15c"]
    rows, fixtures = [], []
    for period in ("20230630", "20231231"):
        req = {"period": period}
        rows.append(_prow("fina_mainbz", period, f"requests/A15c/fina_mainbz/{period}.parquet",
                          params=req, empty="sparse_canary", limit=10000,
                          nk=("ts_code", "end_date", "bz_item", "bz_code"),
                          dataset="fundamentals/fina_mainbz",
                          scope=ra.response_scope_of("fina_mainbz", req)))
        fixtures.append((("fina_mainbz", req, 0), pd.DataFrame(
            {"ts_code": ["000001.SZ"], "end_date": [period], "bz_item": ["主营"],
             "bz_code": ["P"], "bz_sales": [1.0]})))
    _, res = _run_family_e2e(rp, L, spec, rows, fixtures)
    assert sorted(o["partition"] for o in res["outputs"]) == ["20230630", "20231231"]


def test_e2e_period_report_type_family(rig):
    """NEW shape: (period, report_type) requests merging into ONE per-period output."""
    rp, L = rig
    spec = ra.ALL_FAMILIES["A04a"]
    rows, fixtures = [], []
    for rt in ("2", "3"):
        req = {"period": "20231231", "report_type": rt}
        part = f"20231231_{rt}"
        rows.append(_prow("income_vip", part, f"requests/A04a/income_vip/{part}.parquet",
                          params=req, empty="sparse_canary", limit=10000,
                          nk=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
                          dataset="fundamentals/income_quarterly",
                          scope=ra.response_scope_of("income_vip", req)))
        fixtures.append((("income_vip", req, 0), pd.DataFrame(
            {"ts_code": ["000001.SZ"], "end_date": ["20231231"], "report_type": [rt],
             "f_ann_date": ["20240101"], "update_flag": ["0"], "revenue": [float(rt)]})))
    _, res = _run_family_e2e(rp, L, spec, rows, fixtures)
    # both report_types land in ONE per-period file (grp=income_q_period)
    assert [o["partition"] for o in res["outputs"]] == ["20231231"]
    assert res["outputs"][0]["rows"] == 2


def test_e2e_per_code_range_family(rig):
    """NEW shape: per-index-code RANGE request, output partitioned per CODE (grp=index_per_code)."""
    rp, L = rig
    spec = ra.ALL_FAMILIES["A02"]
    req = {"ts_code": "000300.SH", "start_date": "20260101", "end_date": "20260131"}
    rows = [_prow("index_daily", "000300.SH", "requests/A02/index_daily/000300SH.parquet",
                  params=req, empty="dense_refuse",
                  nk=("ts_code", "trade_date"), dataset="market/index",
                  scope=ra.response_scope_of("index_daily", req))]
    fixtures = [(("index_daily", req, 0), pd.DataFrame(
        {"ts_code": ["000300.SH"] * 2, "trade_date": ["20260105", "20260106"], "close": [1.0, 2.0]}))]
    _, res = _run_family_e2e(rp, L, spec, rows, fixtures)
    assert [o["partition"] for o in res["outputs"]] == ["000300.SH"]


def test_e2e_per_stock_to_per_date_repartition(rig):
    """NEW shape: per-stock RANGE requests repartitioned to per-DATE outputs (cyq_perf)."""
    rp, L = rig
    spec = ra.ALL_FAMILIES["A13"]
    rows, fixtures = [], []
    for ts in ("000001.SZ", "600000.SH"):
        req = {"ts_code": ts, "start_date": "20260101", "end_date": "20260131"}
        rows.append(_prow("cyq_perf", ts, f"requests/A13/cyq_perf/{ts}.parquet",
                          params=req, empty="sparse_canary",
                          nk=("ts_code", "trade_date"), dataset="market/cyq_perf",
                          scope=ra.response_scope_of("cyq_perf", req)))
        fixtures.append((("cyq_perf", req, 0), pd.DataFrame(
            {"ts_code": [ts] * 2, "trade_date": ["20260105", "20260106"],
             "winner_rate": [0.5, 0.6]})))
    _, res = _run_family_e2e(rp, L, spec, rows, fixtures)
    parts = {o["partition"]: o["rows"] for o in res["outputs"]}
    assert parts == {"20260105": 2, "20260106": 2}      # 2 stocks x 2 dates -> per-date files


def test_e2e_quarter_stamp_family(rig):
    """NEW shape: the quarter stamp is sent AS end_date and IS the output partition."""
    rp, L = rig
    spec = ra.ALL_FAMILIES["A15b"]
    req = {"end_date": "20231231"}
    rows = [_prow("disclosure_date", "20231231", "requests/A15b/disclosure_date/20231231.parquet",
                  params=req, empty="sparse_canary", limit=3000,
                  nk=("ts_code", "end_date", "ann_date"), dataset="fundamentals/disclosure_date",
                  scope=ra.response_scope_of("disclosure_date", req))]
    fixtures = [(("disclosure_date", req, 0), pd.DataFrame(
        {"ts_code": ["000001.SZ"], "end_date": ["20231231"], "ann_date": ["20240315"],
         "actual_date": ["20240315"]}))]
    _, res = _run_family_e2e(rp, L, spec, rows, fixtures)
    assert [o["partition"] for o in res["outputs"]] == ["20231231"]


def test_scope_refuses_a_wrong_period_response(rig):
    """The per-period scope is enforced like every other: a response for ANOTHER period refuses."""
    rp, L = rig
    req = {"period": "20231231"}
    row = _prow("fina_mainbz", "20231231", "requests/A15c/fina_mainbz/20231231.parquet",
                params=req, empty="sparse_canary", limit=10000,
                nk=("ts_code", "end_date", "bz_item", "bz_code"),
                dataset="fundamentals/fina_mainbz",
                scope=ra.response_scope_of("fina_mainbz", req))
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    ex = _syn([(("fina_mainbz", req, 0), pd.DataFrame(
        {"ts_code": ["000001.SZ"], "end_date": ["20230630"], "bz_item": ["主营"],
         "bz_code": ["P"], "bz_sales": [1.0]}))])       # WRONG period
    claim = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    with pytest.raises(rl.LedgerError, match="outside the requested scope"):
        L.fetch_claimed_page(row["request_id"], claim, ex)


# ── fan-out batch 2: year transform, multi-consolidation, report_rc digest ───────────────────────
def test_year_partition_transform_is_declarative_and_validated():
    c = ra.ConsolidationSpec("r", "ann_date", "x/{partition}.parquet", "multiset_identity",
                             "omit_output", partition_transform="year")
    assert c.partition_of_value("20231231") == "2023"
    with pytest.raises(RuntimeError, match="YYYY-prefixed"):
        c.partition_of_value("")
    bad = ra.ConsolidationSpec("r", "ann_date", "x", "multiset_identity", "omit_output",
                               partition_transform="decade")
    with pytest.raises(RuntimeError, match="unknown partition_transform"):
        bad.partition_of_value("20231231")


def test_e2e_monthly_requests_fold_into_yearly_files(rig):
    """A14 report_rc: 12 MONTHLY range requests -> ONE file per YEAR (grp=report_rc_yearly) — a
    genuine many-to-one repartition, and the first family to exercise the year transform E2E. Also
    exercises the newly-registered report_rc_payload_digest producer."""
    rp, L = rig
    spec = ra.ALL_FAMILIES["A14"]
    rows, fixtures = [], []
    for m, last in (("202301", "31"), ("202302", "28")):
        req = {"start_date": f"{m}01", "end_date": f"{m}{last}"}
        rows.append(_prow("report_rc", m, f"requests/A14/report_rc/{m}.parquet", params=req,
                          empty="dense_refuse", limit=3000,
                          nk=("ts_code", "report_date", "org_name", "author_name", "quarter"),
                          dataset="analyst/report_rc",
                          scope=ra.response_scope_of("report_rc", req)))
        fixtures.append((("report_rc", req, 0), pd.DataFrame(
            {"ts_code": ["000001.SZ"], "report_date": [f"{m}15"], "org_name": ["ZX"],
             "author_name": ["A"], "quarter": ["2023Q1"], "eps": [1.0], "np": [2.0],
             "op_rt": [3.0], "rating": ["buy"]})))
    L._freeze_plan_unvalidated(rows)
    L.declare_run_mode("synthetic_nonpromotable")
    summary = ra.run_family(spec, L, _syn(fixtures))
    assert not summary["failed"] and len(summary["verified"]) == 2
    res = ra.consolidate_family(spec, L)
    # both months folded into ONE 2023 file
    assert [o["partition"] for o in res["outputs"]] == ["2023"]
    assert res["outputs"][0]["rows"] == 2
    out = pd.read_parquet(rp.staging_data / res["outputs"][0]["path"])
    assert "report_rc_payload_digest" in out.columns and out["report_rc_payload_digest"].notna().all()


def test_report_rc_digest_reuses_the_production_definition(rig):
    """The recovery digest MUST be the production one (pit_backend), else the recovery identity could
    drift from the serving identity and collapse a genuine revision."""
    import importlib
    sys.path.insert(0, str(ROOT / "src"))
    prod = importlib.import_module("data_infra.pit_backend").report_rc_payload_digest
    df = pd.DataFrame({"ts_code": ["A.SZ", "A.SZ"], "eps": [1.0, 1.5], "np": [2.0, 2.0],
                       "op_rt": [3.0, 3.0], "rating": ["buy", "buy"]})
    prepared = rl._PREPARE_REGISTRY["report_rc"](df)
    assert list(prepared["report_rc_payload_digest"]) == list(prod(df).astype(str))
    # a payload change IS a distinct revision identity
    assert prepared["report_rc_payload_digest"].nunique() == 2


def test_e2e_one_fetch_two_layouts(rig):
    """A10: suspend_d is fetched ONCE and consolidated TWICE (per-date store + yearly suspension
    files). Planning them as two families would mint an IDENTICAL request_id per session."""
    rp, L = rig
    spec = ra.ALL_FAMILIES["A10"]
    assert len(spec.consolidations) == 2
    rows, fixtures = [], []
    for d in ("20230105", "20240110"):
        req = {"trade_date": d}
        rows.append(_prow("suspend_d", d, f"requests/A10/suspend_d/{d}.parquet", params=req,
                          empty="sparse_canary",
                          nk=("ts_code", "trade_date", "suspend_type"),
                          dataset="market/suspend_d",
                          scope=ra.response_scope_of("suspend_d", req)))
        fixtures.append((("suspend_d", req, 0), pd.DataFrame(
            {"ts_code": ["000001.SZ"], "trade_date": [d], "suspend_type": ["S"]})))
    L._freeze_plan_unvalidated(rows)
    L.declare_run_mode("synthetic_nonpromotable")
    summary = ra.run_family(spec, L, _syn(fixtures))
    assert not summary["failed"] and len(summary["verified"]) == 2
    res = ra.consolidate_family(spec, L)
    by_label = {r["label"]: r for r in res["layouts"]}
    assert set(by_label) == {"market/suspend_d", "market/suspension"}
    # per-date layout: one file per session; yearly layout: one file per YEAR
    assert sorted(o["partition"] for o in by_label["market/suspend_d"]["outputs"]) == \
        ["20230105", "20240110"]
    assert sorted(o["partition"] for o in by_label["market/suspension"]["outputs"]) == ["2023", "2024"]
    # BOTH layouts conserve the same input rows
    assert sum(o["rows"] for o in by_label["market/suspend_d"]["outputs"]) == 2
    assert sum(o["rows"] for o in by_label["market/suspension"]["outputs"]) == 2


def test_every_matrix_family_is_bound_deferred_or_a_second_layout():
    """No matrix family may be silently unaccounted for: each is either executable, explicitly
    deferred with a reason, or declared as another family's second consolidation layout."""
    owners = {r.owner for r in rrc.ENDPOINT_MATRIX}
    accounted = set(ra.ALL_FAMILIES) | set(ra.DEFERRED_FAMILIES) | set(ra.CONSOLIDATED_AS_SECOND_LAYOUT)
    # A10 is the merged fetch owner for the matrix's A10a/A10b rows
    accounted |= {"A10a", "A10b"}
    missing = owners - accounted
    assert not missing, f"matrix families unaccounted for: {sorted(missing)}"


# ── §13 authorize-fetch CLI (design v4 F2 + GPT impl re-review #2) ────────────────────────────────
def test_authorize_fetch_writes_the_event_and_binds_plan_and_bundle(rig):
    """The CLI-level authorization is a SEPARATE, explicit action that writes the hash-chained
    fetch_authorized event; it binds the FROZEN plan + adapter bundle so re-authorization is required
    if either changes."""
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("live_authorized")
    rc = rrc.cmd_authorize_fetch(rp, L, actor="henry", hours=1.0, endpoints=["daily"])
    assert rc == 0
    evs = [r for r in L._load()
           if r.get("kind") == "lifecycle" and r.get("event") == "fetch_authorized"]
    assert len(evs) == 1
    ev = evs[0]
    assert ev["actor"] == "henry" and ev["endpoint_scope"] == ["daily"]
    assert ev["bundle_sha256"] == L.adapter_bundle_hash
    frozen = [r for r in L._load() if r.get("event") == "plan_frozen"][0]
    assert ev["plan_sha256"] == frozen["plan_sha256"]
    assert ev["os_sid"] and ev["os_username"]            # EVIDENCE, not the boundary
    # ...and the authorization now actually admits a claim
    assert L.claim_next_fetch(row["request_id"], "live_authorized").kind == "FETCH"


def test_authorize_fetch_refuses_bad_inputs(rig):
    rp, L = rig
    L._freeze_plan_unvalidated([_prow("daily", "20260702", "req/daily/20260702.parquet")])
    assert rrc.cmd_authorize_fetch(rp, L, actor="henry", hours=1.0, endpoints=[""]) == 2
    assert rrc.cmd_authorize_fetch(rp, L, actor="henry", hours=0, endpoints=["daily"]) == 2
    assert rrc.cmd_authorize_fetch(rp, L, actor="henry", hours=48, endpoints=["daily"]) == 2
    assert not [r for r in L._load() if r.get("event") == "fetch_authorized"]


def test_authorize_fetch_requires_a_frozen_plan(rig):
    """Authorizing a run with no frozen plan is meaningless — there is nothing to bind to."""
    rp, L = rig
    assert rrc.cmd_authorize_fetch(rp, L, actor="henry", hours=1.0, endpoints=["*"]) == 3
    assert not [r for r in L._load() if r.get("event") == "fetch_authorized"]


def test_fetch_command_cannot_mint_its_own_authorization():
    """The fetch command must have NO path that writes the authorization event (GPT impl re-review
    #2: authorization must be a separate user-triggered action)."""
    import inspect
    src = inspect.getsource(rrc.cmd_fetch)
    body = src.split('"""')[-1]          # strip the docstring: it NAMES the thing it must not call
    assert "record_fetch_authorization" not in body
    assert "cmd_authorize_fetch" not in body


def test_fetch_refuses_and_builds_no_fetcher_on_a_synthetic_run(rig, monkeypatch):
    """`cmd_fetch` used to be unconditionally `return 3`; now that it is wired, the property that
    replaces that is: a run whose IMMUTABLE mode is synthetic refuses BEFORE constructing a fetcher.
    No fetcher, no possible vendor call — the run-mode check is the door, and it is ahead of the
    import."""
    rp, L = rig
    L.declare_run_mode("synthetic_nonpromotable")
    built = []
    import data_infra.fetchers as _f
    monkeypatch.setattr(_f, "TushareFetcher",
                        lambda *a, **kw: built.append(1) or (_ for _ in ()).throw(
                            AssertionError("a synthetic run must NEVER construct a fetcher")))
    assert rrc.cmd_fetch(rp, L) == 3
    assert not built


def test_fetch_refuses_without_a_frozen_plan(rig, monkeypatch):
    """A live-declared run with nothing frozen has no requests to bind an authorization to."""
    rp, L = rig
    L.declare_run_mode("live_authorized")
    import data_infra.fetchers as _f
    monkeypatch.setattr(_f, "TushareFetcher",
                        lambda *a, **kw: (_ for _ in ()).throw(
                            AssertionError("must refuse before constructing a fetcher")))
    assert rrc.cmd_fetch(rp, L) == 3


# ── GPT fan-out review P0-1: the payload digest must be a CONTRACT constraint ─────────────────────
def _real_plan_row(owner):
    """Take a REAL plan row straight from the production builder over the REAL signed contracts —
    the regression GPT asked for. Returns (row, request, contracts). The row is the plan's own first
    partition, so the test can never drift onto a request the real population does not contain."""
    contracts = rrc.load_signed_contracts()
    rows = ra.build_plan_rows(ra.ALL_FAMILIES[owner], contracts)
    row = sorted(rows, key=lambda r: r["partition"])[0]
    return row, dict(row["params"]), contracts


def _install_real_contract(L, endpoint, contracts):
    """Point the below-contract seams at the REAL signed contract for this endpoint."""
    _LIVE_CONTRACTS[endpoint] = contracts[endpoint]
    L._revalidate_contract = lambda row: None
    L._assert_response_fields = lambda ep, cols: None


def test_signed_natural_key_must_cover_the_derived_identity_columns():
    """The exemption GPT found: assert_plan_matches_contracts subtracted derived_fields_for(ep) from
    the vendor key, so a signed natural_key WITHOUT the payload digest passed and the digest was never
    a contract constraint. Stripping it from a REAL plan row must now refuse."""
    contracts = rrc.load_signed_contracts()
    rows = ra.build_plan_rows(ra.ALL_FAMILIES["A11a"], contracts)[:1]
    stripped_c = dict(contracts)
    stripped_c["top_list"] = dict(contracts["top_list"],
                                  natural_key=["ts_code", "trade_date", "reason"])  # digest removed
    rows[0] = dict(rows[0], natural_key=["ts_code", "trade_date", "reason"],
                   contract_sha256=rrc.canonical_contract_sha256(stripped_c["top_list"]))
    with pytest.raises(RuntimeError, match="does NOT cover the matrix vendor key"):
        rrc.assert_plan_matches_contracts(rows, stripped_c)

def test_report_rc_same_core_different_payload_are_both_kept(rig):
    """Two analyst revisions sharing (ts_code, report_date, org, author, quarter) but with DIFFERENT
    payloads are distinct records. Before the fix the signed key lacked the digest, so they collided
    under the natural key and verify_request REFUSED — halting a real recovery."""
    rp, L = rig
    row, req, contracts = _real_plan_row("A14")
    _install_real_contract(L, "report_rc", contracts)
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    page = pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ"],
        "report_date": [req["start_date"], req["start_date"]],
        "org_name": ["ZX", "ZX"], "author_name": ["A", "A"],
        "quarter": ["2023Q1", "2023Q1"],
        "eps": [1.0, 1.5],                      # DIFFERENT payload -> different digest
        "np": [2.0, 2.0], "op_rt": [3.0, 3.0], "rating": ["buy", "buy"]})
    ex = _syn([(("report_rc", req, 0), page)])
    claim = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    L.fetch_claimed_page(row["request_id"], claim, ex)
    ev = L.verify_request(row["request_id"])
    assert ev["pre_dedup_rows"] == 2 and ev["post_dedup_rows"] == 2, ev


def test_report_rc_same_payload_different_quarter_are_both_kept(rig):
    """`quarter` was missing from the CONTENT-DEDUP key while present in the vendor key: two rows with
    an identical payload for DIFFERENT quarters (FY1 vs FY2) collapsed, exceeded max_content_dups=0
    and REFUSED. Both must survive."""
    rp, L = rig
    row, req, contracts = _real_plan_row("A14")
    _install_real_contract(L, "report_rc", contracts)
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    page = pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ"],
        "report_date": [req["start_date"], req["start_date"]],
        "org_name": ["ZX", "ZX"], "author_name": ["A", "A"],
        "quarter": ["2023Q1", "2023Q2"],        # SAME payload, DIFFERENT quarter
        "eps": [1.0, 1.0], "np": [2.0, 2.0], "op_rt": [3.0, 3.0], "rating": ["buy", "buy"]})
    ex = _syn([(("report_rc", req, 0), page)])
    claim = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    L.fetch_claimed_page(row["request_id"], claim, ex)
    ev = L.verify_request(row["request_id"])
    assert ev["pre_dedup_rows"] == 2 and ev["post_dedup_rows"] == 2, ev
    assert ev["excess_dup_rows"] == 0, ev


def test_event_family_same_core_different_payload_are_both_kept(rig):
    """The same invariant for the event families: two top_list rows sharing
    (ts_code, trade_date, reason) but differing elsewhere are distinct vendor records, separated ONLY
    by row_payload_digest — which the signed key now carries."""
    rp, L = rig
    row, req, contracts = _real_plan_row("A11a")
    _install_real_contract(L, "top_list", contracts)
    L._freeze_plan_unvalidated([row])
    L.declare_run_mode("synthetic_nonpromotable")
    page = pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ"],
        "trade_date": [req["trade_date"], req["trade_date"]],
        "reason": ["日涨幅偏离值达7%", "日涨幅偏离值达7%"],
        "net_amount": [1.0, 2.0]})              # distinct rows -> distinct digest
    ex = _syn([(("top_list", req, 0), page)])
    claim = L.claim_next_fetch(row["request_id"], "synthetic_nonpromotable")
    L.fetch_claimed_page(row["request_id"], claim, ex)
    ev = L.verify_request(row["request_id"])
    assert ev["pre_dedup_rows"] == 2 and ev["post_dedup_rows"] == 2, ev


def test_every_matrix_identity_column_is_in_its_signed_natural_key():
    """Sweep the WHOLE surface, not just the four GPT named: no family may rely on the removed
    exemption."""
    cs = rrc.load_signed_contracts()
    for r in rrc.ENDPOINT_MATRIX:
        for ep in r.source_endpoints:
            c = cs.get(ep)
            if not c:
                continue                        # unsigned (A07) — held at BLOCKED(contract)
            gap = set(r.vendor_record_key) - set(c["natural_key"])
            assert not gap, f"{ep}: signed natural_key misses identity column(s) {sorted(gap)}"


def test_content_dedup_key_is_never_coarser_than_the_vendor_key():
    """report_rc's dedup key dropped `quarter` while the vendor key kept it. A dedup key coarser than
    the vendor key collapses genuinely distinct records."""
    for r in rrc.ENDPOINT_MATRIX:
        if not r.content_dedup_key:
            continue
        dropped = set(r.vendor_record_key) - set(r.content_dedup_key)
        assert not dropped, (f"{r.owner}: content_dedup_key drops vendor-key column(s) "
                             f"{sorted(dropped)} — distinct records would collapse")


# ── the planner and the freeze door must derive the SAME partition label ─────────────────────────
def test_every_family_plans_the_label_the_freeze_door_derives():
    """The structural guard for the class that broke the whole-set freeze.

    `FamilySpec.partition_of` and `_request_population_key`'s honesty check each derived the partition
    label. They disagreed for 3 of the 29 families — the VIP statement pair (planned on
    (period, report_type), checked on `period` alone) and A14/A15e (planned on the raw `start_date`,
    signed as a month / a year) — and EVERY per-family test still passed, because each side was
    self-consistent. Only the whole-set freeze refused.

    `partition_of` now delegates to the coordinator's deriver, so this asserts the property directly
    rather than re-listing which families are composite."""
    contracts = rrc.load_signed_contracts()
    by_family = {r.output_family: r for r in rrc.ENDPOINT_MATRIX}
    checked = 0
    for owner in sorted(ra.ALL_FAMILIES):
        spec = ra.ALL_FAMILIES[owner]
        row = by_family[spec.output_family]
        for pr in ra.build_plan_rows(spec, contracts):
            # raises if the planned label is not what the freeze door derives from the same request
            rrc._request_population_key(pr, row)
            checked += 1
    assert checked > 100_000, f"only {checked} plan rows checked — the plan did not build"


def test_the_ledger_binds_the_REAL_adapter_bundle_hash():
    """`open_run` carried the placeholder "adapters_unbuilt" long after the adapters existed. That was
    load-bearing twice over: the §13 authorization binds `bundle_sha256` (so an adapter edit would not
    have invalidated a standing authorization), and `run_family`'s live drift check compares
    `compute_bundle_hash()` against it (so every live run would have refused as "drifted")."""
    import inspect
    src = inspect.getsource(rrc.open_run)
    # the ASSIGNMENT, not the word — the comment above it names the placeholder deliberately
    assert 'adapter_bundle_hash="adapters_unbuilt"' not in src
    assert "adapter_bundle_hash=_ra.compute_bundle_hash()" in src
    # and the value a real run binds is the real content hash
    rp, led = rrc.open_run("bundle_probe_" + uuid.uuid4().hex[:8], new=True)
    assert led.adapter_bundle_hash == ra.compute_bundle_hash()
    assert len(led.adapter_bundle_hash) == 64


# ── defects the FIRST LIVE FETCH exposed (measured, not reviewed) ─────────────────────────────────
def test_genesis_survives_unrelated_repo_commits(rig):
    """The one that actually bricked a live run. `_genesis()` used to be RE-DERIVED from
    `coordinator_commit` (repo-wide `git rev-parse HEAD`), so three commits from a PARALLEL session —
    touching nothing in the recovery — made recover01 unopenable: `hash-chain break at line 1`, with a
    350-row chain that was perfectly intact under its original anchor.

    A recovery that runs for days across multiple authorization segments cannot require that nobody
    commits to the repo. The anchor is now minted once and persisted."""
    rp, L = rig
    L.event("probe_one")
    original = L._genesis()
    assert L.genesis_path.exists(), "the genesis anchor was not persisted"

    # a later process, same run dir, DIFFERENT repo commit and different adapter bundle
    L2 = rl.PageReceiptLedger(rp, coordinator_commit="a-totally-different-head",
                              adapter_bundle_hash="f" * 64)
    assert L2._genesis() == original, "the anchor moved when unrelated identity inputs changed"
    assert len(L2._load()) >= 1, "the run must still open and replay"
    L2.event("probe_two")                       # and still be appendable
    assert len(L2._load()) >= 2


def test_genesis_anchor_refuses_a_ledger_from_another_run(rig):
    """Persisting the anchor must not weaken it into 'any ledger goes'."""
    rp, L = rig
    L.event("probe")
    anchor = json.loads(L.genesis_path.read_text(encoding="utf-8"))
    anchor["run"] = "some_other_run"
    L.genesis_path.write_text(json.dumps(anchor), encoding="utf-8")
    L2 = rl.PageReceiptLedger(rp, coordinator_commit="x", adapter_bundle_hash="y" * 64)
    with pytest.raises(rl.LedgerError, match="another run"):
        L2._load()


def test_plan_verification_is_cached_but_stat_guarded(rig):
    """The 102 MB frozen plan was re-read, re-parsed, re-canonicalised and re-hashed ~4x per request —
    the largest slice of the 6.4 s/request non-vendor overhead. Caching must not cost tamper-evidence."""
    rp, L = rig
    row = _prow("daily", "20260702", "req/daily/20260702.parquet")
    L._freeze_plan_unvalidated([row])
    assert L._plan()[row["request_id"]]["endpoint"] == "daily"
    assert L._plan_cache is not None
    doc = json.loads(L.plan_path.read_text(encoding="utf-8"))
    doc["rows"][0]["endpoint"] = "moneyflow"
    L.plan_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(rl.LedgerError, match="self-hash mismatch|was rewritten"):
        L._plan()


def test_chain_cache_never_masks_a_tamper(rig):
    """The chain cache is advanced only by `_append` (the sole writer, under the lock). An earlier
    version inferred 'grew => was appended to', which the tamper test caught at once: rewriting line 1
    also grows the file, so a real corruption took the incremental path."""
    rp, L = rig
    for i in range(3):
        L.event("probe_%d" % i)
    assert len(L._load()) == 3
    lines = L.ledger_path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["event"] = "tampered"
    lines[0] = json.dumps(rec)                        # a rewrite that GROWS the file
    L.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    L._chain_cache = None                             # a fresh process
    with pytest.raises(rl.LedgerError, match="hash-chain break|torn/malformed"):
        L._load()


def test_run_family_reports_per_request_progress():
    """A 13,479-request family printed nothing for its entire runtime — an operator could not tell
    running from hung (§10 requires visible completed/total/ETA)."""
    import inspect
    assert "on_request" in inspect.signature(ra.run_family).parameters
    assert "on_request(i, len(rids)" in inspect.getsource(ra.run_family)
    cmd = inspect.getsource(rrc.cmd_fetch)
    assert "flush=True" in cmd, "operator output must not sit in a block buffer"
    assert "on_request=_tick" in cmd
