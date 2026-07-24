# NF integration P4b: per-stock decision driver — declared-invariant tests.
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import test_news_archive as ta  # noqa: E402 — reuse contract/call_fn fixtures

from workspace.research.ai_research_dept.engine.news_archive import (  # noqa: E402
    load_and_verify_decision_archive,
)
from workspace.research.ai_research_dept.engine.news_decision import (  # noqa: E402
    lookup_decision, record_decision,
)
from workspace.research.ai_research_dept.engine.news_executors import (  # noqa: E402
    execute_news_decision,
)
from workspace.research.ai_research_dept.engine.news_flash_assemble import (  # noqa: E402
    NothingToDecide, verify_assembly_provenance,
)
from workspace.research.ai_research_dept.engine.news_flash_decide import (  # noqa: E402
    decide_stock, nf_decision_id,
)  # noqa: F401 — decide_stock also used via _decide
from workspace.research.ai_research_dept.tests.assembly_fixtures import (  # noqa: E402
    CUT, SMIC, chain_artifact, chain_store, evidence_for,
)

NF_ID = f"nf:forward:{SMIC}:2025-01-27T18:00:00"


def _dirs(tmp_path, root):
    return dict(ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
                archive_dir=tmp_path / "arch", store_dir=root, artifact_dir=root)


def _decide(tmp_path, *, variant="full", ts_code=SMIC, call_fn=None):
    root = chain_store(variant)
    return decide_stock(CUT, ingest_class="forward", ts_code=ts_code,
                        **_dirs(tmp_path, root), contract=ta._contract(),
                        call_fn=call_fn or ta._call_fn())


# --------------------------------------------------- invariant 1: identity

def test_decision_id_is_deterministic_and_canonical():
    assert nf_decision_id(CUT, ingest_class="forward", ts_code=SMIC) == NF_ID
    # str and Timestamp cutoffs canonicalize to the same id
    assert nf_decision_id(pd.Timestamp(CUT), ingest_class="forward",
                          ts_code=SMIC) == NF_ID


def test_bad_identity_inputs_refused():
    with pytest.raises(ValueError, match="ts_code"):
        nf_decision_id(CUT, ingest_class="forward", ts_code="")
    with pytest.raises(ValueError, match="ingest_class"):
        nf_decision_id(CUT, ingest_class="", ts_code=SMIC)


# --------------------------------------------------- happy path

def test_full_decision_round_trip(tmp_path):
    out = _decide(tmp_path)
    assert out["decision_id"] == NF_ID
    assert out["news_status"] == "success" and out["resumed"] is False
    assert set(out) == {"decision_id", "execution_id", "news_status",
                        "assembly_hash", "archive_sha256", "resumed"}
    # the sealed archive is the consumer door — it re-verifies the whole chain
    art = chain_artifact(NF_ID, variant="full")
    loaded = load_and_verify_decision_archive(
        NF_ID, art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
        contract=ta._contract(), archive_dir=tmp_path / "arch")
    assert loaded["archive_sha256"] == out["archive_sha256"]
    recovered = verify_assembly_provenance(loaded["assembly"])
    assert recovered.ts_code == SMIC
    assert recovered.assembly_hash == out["assembly_hash"]
    # the ledger row pinned the same chain
    assert lookup_decision(tmp_path / "ledger", NF_ID)["assembly_hash"] \
        == out["assembly_hash"]


# --------------------------------------------------- invariant 4: idempotent re-entry

def test_second_run_resumes_without_reexecuting(tmp_path):
    out1 = _decide(tmp_path)
    calls = []

    def counting_fn(msgs):
        calls.append(msgs)
        raise AssertionError("a resumed decision must never re-invoke the LLM")
    out2 = _decide(tmp_path, call_fn=counting_fn)
    assert calls == []                                   # invariant 4: no LLM
    assert out2["resumed"] is True
    assert out2["execution_id"] == out1["execution_id"]
    assert out2["archive_sha256"] == out1["archive_sha256"]


def test_crash_between_commit_and_seal_recovers(tmp_path):
    # commit exists, archive missing (process died) -> decide recovers from
    # pure disk state and seals the SAME execution
    root = chain_store("full")
    art = chain_artifact(NF_ID, variant="full")
    record_decision(tmp_path / "ledger", NF_ID, art, **evidence_for(art))
    bundle = execute_news_decision(
        art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
        decision_id=NF_ID, contract=ta._contract(), call_fn=ta._call_fn())
    assert bundle["outcome"].news_status == "success"    # committed, NOT sealed
    out = _decide(tmp_path)
    assert out["resumed"] is True
    assert out["execution_id"] == bundle["execution_id"]
    loaded = load_and_verify_decision_archive(
        NF_ID, art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
        contract=ta._contract(), archive_dir=tmp_path / "arch")
    assert loaded["execution_id"] == bundle["execution_id"]


def test_hard_failure_does_not_block_retry(tmp_path):
    def broken_fn(msgs):
        return ta._Reply("not json at all")
    out1 = _decide(tmp_path, call_fn=broken_fn)
    assert out1["news_status"] == "hard_failed" and out1["resumed"] is False
    # retry with a working LLM: fresh execution, success, sealed
    out2 = _decide(tmp_path)
    assert out2["news_status"] == "success" and out2["resumed"] is False
    assert out2["execution_id"] != out1["execution_id"]
    # both executions left independent audit archives
    for sha in (out1["archive_sha256"], out2["archive_sha256"]):
        assert len(sha) == 64
    assert out1["archive_sha256"] != out2["archive_sha256"]


def test_unsealed_hard_failed_commitment_is_backfilled_on_reentry(tmp_path):
    # P4b review P1 (the reviewer's probe): hard_failed COMMITTED, crash before
    # seal_decision_archive -> the old execution's independent audit archive was
    # lost forever (recovery only supported success). Re-entry must FIRST
    # backfill the missing hard_failed archive from pure disk state, then retry;
    # afterwards the old execution is verifiable BY EXECUTION.
    from workspace.research.ai_research_dept.engine.news_archive import (
        load_and_verify_execution_archive,
    )
    root = chain_store("full")
    art = chain_artifact(NF_ID, variant="full")
    record_decision(tmp_path / "ledger", NF_ID, art, **evidence_for(art))

    def broken_fn(msgs):
        return ta._Reply("not json at all")
    bundle = execute_news_decision(                      # committed, NOT sealed
        art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
        decision_id=NF_ID, contract=ta._contract(), call_fn=broken_fn)
    assert bundle["outcome"].news_status == "hard_failed"
    failed_exec = bundle["execution_id"]

    out = _decide(tmp_path)                              # re-entry with good LLM
    assert out["news_status"] == "success"
    assert out["execution_id"] != failed_exec
    # the old hard_failed execution's audit archive now EXISTS and verifies
    old = load_and_verify_execution_archive(
        NF_ID, failed_exec, art, ledger_dir=tmp_path / "ledger",
        prov_dir=tmp_path / "prov", contract=ta._contract(),
        archive_dir=tmp_path / "arch")
    assert old["outcome"]["news_status"] == "hard_failed"
    assert old["evaluation"] is None
    assert old["archive_schema"] == "news_decision_archive_v2"


def test_two_task_barrier_A_backfills_B_before_succeeding(tmp_path):
    # P4b re-review#2 P1 (the reviewer's cross-task probe): task B is mid-flow
    # (holds the per-decision lock), task A's decide_stock must BLOCK; B commits
    # hard_failed and crashes before seal (lock released, archive missing); A
    # then proceeds and MUST backfill B's archive before returning success.
    # Pre-fold, A's one-shot snapshot missed B's commitment and returned success
    # with B's audit archive permanently unsealed.
    import shutil
    import threading
    import time as _time
    from workspace.research.ai_research_dept.engine.news_archive import (
        load_and_verify_execution_archive,
    )
    from workspace.research.ai_research_dept.engine.news_flash_decide import (
        _decision_flow_lock_path,
    )
    art = chain_artifact(NF_ID, variant="full")
    lock = _decision_flow_lock_path(tmp_path / "ledger", NF_ID)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.mkdir()                                         # B holds the flow lock
    result: dict = {}

    def task_a():
        result["out"] = _decide(tmp_path)
    t = threading.Thread(target=task_a, daemon=True)
    t.start()
    _time.sleep(0.4)
    assert t.is_alive(), "task A must block on B's per-decision flow lock"
    # B's flow while holding the lock: record + hard_failed commit, crash pre-seal
    record_decision(tmp_path / "ledger", NF_ID, art, **evidence_for(art))

    def broken_fn(msgs):
        return ta._Reply("not json at all")
    b_bundle = execute_news_decision(
        art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
        decision_id=NF_ID, contract=ta._contract(), call_fn=broken_fn)
    shutil.rmtree(lock)                                  # B crashes; lock released
    t.join(timeout=60)
    assert not t.is_alive() and result["out"]["news_status"] == "success"
    # A backfilled B's hard_failed archive BEFORE returning success
    old = load_and_verify_execution_archive(
        NF_ID, b_bundle["execution_id"], art, ledger_dir=tmp_path / "ledger",
        prov_dir=tmp_path / "prov", contract=ta._contract(),
        archive_dir=tmp_path / "arch")
    assert old["outcome"]["news_status"] == "hard_failed"


def test_stale_flow_lock_fails_closed(tmp_path):
    # a crash-leftover lock dir blocks the next driver until timeout, then
    # fails closed (operator intervention; same semantics as the ledger lock)
    from workspace.research.ai_research_dept.engine.news_flash_decide import (
        _decision_flow_lock_path,
    )
    lock = _decision_flow_lock_path(tmp_path / "ledger", NF_ID)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.mkdir()
    root = chain_store("full")
    with pytest.raises(RuntimeError, match="决策流锁超时"):
        decide_stock(CUT, ingest_class="forward", ts_code=SMIC,
                     **_dirs(tmp_path, root), contract=ta._contract(),
                     call_fn=ta._call_fn(), lock_timeout=0.3)


def test_backfill_also_runs_when_success_already_exists(tmp_path):
    # even a decision that later SUCCEEDED must backfill an older unsealed
    # hard_failed execution on re-entry (the reviewer's explicit ask)
    from workspace.research.ai_research_dept.engine.news_archive import (
        load_and_verify_execution_archive,
    )
    art = chain_artifact(NF_ID, variant="full")
    record_decision(tmp_path / "ledger", NF_ID, art, **evidence_for(art))

    def broken_fn(msgs):
        return ta._Reply("not json at all")
    failed = execute_news_decision(                      # hard_failed, unsealed
        art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
        decision_id=NF_ID, contract=ta._contract(), call_fn=broken_fn)
    good = execute_news_decision(                        # success, ALSO unsealed
        art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
        decision_id=NF_ID, contract=ta._contract(), call_fn=ta._call_fn())
    out = _decide(tmp_path)                              # re-entry
    assert out["resumed"] is True
    assert out["execution_id"] == good["execution_id"]
    # BOTH unsealed executions were backfilled
    for eid, status in ((failed["execution_id"], "hard_failed"),
                        (good["execution_id"], "success")):
        loaded = load_and_verify_execution_archive(
            NF_ID, eid, art, ledger_dir=tmp_path / "ledger",
            prov_dir=tmp_path / "prov", contract=ta._contract(),
            archive_dir=tmp_path / "arch")
        assert loaded["outcome"]["news_status"] == status


# --------------------------------------------------- invariant 5: nothing to decide

def test_unrouted_stock_writes_nothing(tmp_path):
    with pytest.raises(NothingToDecide):
        _decide(tmp_path, ts_code="300750.SZ")           # never routed by the chain
    assert not (tmp_path / "ledger" / "decision_ledger.jsonl").exists()
    assert not (tmp_path / "arch").exists()
    assert not (tmp_path / "prov").exists()


# --------------------------------------------------- determinism of the identity slot

def test_same_slot_two_variants_first_write_wins(tmp_path):
    # the SAME (stock, cutoff) driven from a DIFFERENT committed chain refuses
    # at the ledger (first-write-wins pinned the full-variant chain)
    from workspace.research.ai_research_dept.engine.news_evidence import (
        RegistryError,
    )
    _decide(tmp_path, variant="full")
    with pytest.raises(RegistryError, match="首写胜出|世界线"):
        _decide(tmp_path, variant="basic")
