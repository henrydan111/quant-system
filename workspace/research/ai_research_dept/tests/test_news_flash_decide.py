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
)
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
