# NF integration P4a: ledger + archive chain binding — the five frozen obligations
# + the round-1 P1 fold (evidence-at-the-door: a self-consistent AssemblyProvenance
# is a CLAIM; the first-write door PROVES it by re-running P3b from the P2/P3a
# artifacts + source rows and comparing hashes).
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import test_news_archive as ta  # noqa: E402 — reuse contract/call_fn fixtures

from workspace.research.ai_research_dept.engine.news_archive import (  # noqa: E402
    _archive_path, load_and_verify_decision_archive,
    recover_and_seal_success_archive, seal_decision_archive,
)
from workspace.research.ai_research_dept.engine.news_decision import (  # noqa: E402
    lookup_decision, record_decision,
)
from workspace.research.ai_research_dept.engine.news_evidence import (  # noqa: E402
    RegistryError,
)
from workspace.research.ai_research_dept.engine.news_executors import (  # noqa: E402
    execute_news_decision,
)
from workspace.research.ai_research_dept.engine.news_flash_assemble import (  # noqa: E402
    AssemblyProvenance, verify_assembly_provenance,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash  # noqa: E402
from workspace.research.ai_research_dept.tests.assembly_fixtures import (  # noqa: E402
    asm_for, chain_artifact, evidence_for, rec,
)


def _dirs(tmp_path):
    return dict(ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
                contract=ta._contract())


def _executed(tmp_path, decision_id="d1"):
    art = chain_artifact(decision_id, variant="full")
    rec(tmp_path / "ledger", decision_id, art)
    bundle = execute_news_decision(
        art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
        decision_id=decision_id, contract=ta._contract(), call_fn=ta._call_fn())
    return art, asm_for(art), bundle


def _forged_asm(art, **over):
    """A hash-SELF-CONSISTENT assembly via the PUBLIC constructor (the GPT probe:
    no source edits, no disk tampering, no monkey-patching) claiming whatever
    `over` says — the real artifact_hash with forged provenance fields."""
    real = asm_for(art)
    kw = dict(artifact_hash=art.artifact_hash, ts_code=real.ts_code,
              decision_id=real.decision_id, cutoff_iso=real.cutoff_iso,
              ingest_class=real.ingest_class,
              consumed_assessed_flash_sha256=real.consumed_assessed_flash_sha256,
              consumed_d7_split_sha256=real.consumed_d7_split_sha256,
              selected_fact_occurrence_ids=real.selected_fact_occurrence_ids,
              n_splits_used=real.n_splits_used)
    kw.update(over)
    return AssemblyProvenance(**kw)


# ------------------------------------------------ obligation (a): REQUIRED, no default

def test_record_without_evidence_is_a_typeerror(tmp_path):
    art = chain_artifact("d1", variant="full")
    with pytest.raises(TypeError):
        record_decision(tmp_path / "ledger", "d1", art)
    with pytest.raises(TypeError):
        record_decision(tmp_path / "ledger", "d1", art, assembly=asm_for(art))


def test_seal_without_assembly_is_a_typeerror(tmp_path):
    art, asm, bundle = _executed(tmp_path)
    with pytest.raises(TypeError, match="assembly"):
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")


def test_record_with_none_assembly_refused(tmp_path):
    art = chain_artifact("d1", variant="full")
    ev = evidence_for(art)
    ev["assembly"] = None
    with pytest.raises(RegistryError, match="AssemblyProvenance"):
        record_decision(tmp_path / "ledger", "d1", art, **ev)


# ------------------------------------------------ round-1 P1: the reviewer's probe,
# ------------------------------------------------ pinned as regression

def test_gpt_probe_forged_provenance_refused_and_writes_nothing(tmp_path):
    # the exact reproduced attack: ordinary public-constructor assembly, hash
    # self-consistent, REAL artifact_hash — claiming a different stock, a 1999
    # cutoff and arbitrary P2/P3a references. Pre-fold it completed
    # record -> execute -> seal -> load. Now: refused at first write, and NO
    # ledger row / file may exist afterwards.
    art = chain_artifact("d1", variant="full")
    forged = _forged_asm(art, ts_code="000001.SZ",
                         cutoff_iso="1999-01-01T00:00:00",
                         consumed_assessed_flash_sha256="1" * 64,
                         consumed_d7_split_sha256="2" * 64)
    ev = evidence_for(art)
    ev["assembly"] = forged
    with pytest.raises(RegistryError, match="重推导|不符|does not match"):
        record_decision(tmp_path / "ledger", "d1", art, **ev)
    assert not (tmp_path / "ledger" / "decision_ledger.jsonl").exists()


@pytest.mark.parametrize("over", [
    {"ts_code": "000001.SZ"},                          # a stock the P2 never routed
    {"cutoff_iso": "1999-01-01T00:00:00"},             # a cutoff the chain never had
    {"ingest_class": "backtest"},                      # a class the chain never had
    {"consumed_assessed_flash_sha256": "1" * 64},      # an arbitrary P2 reference
    {"consumed_d7_split_sha256": "2" * 64},            # an arbitrary P3a reference
    {"n_splits_used": 0},                              # a split count the chain refutes
])
def test_every_forged_field_refused_at_first_write(tmp_path, over):
    art = chain_artifact("d1", variant="full")
    ev = evidence_for(art)
    ev["assembly"] = _forged_asm(art, **over)
    with pytest.raises(RegistryError):
        record_decision(tmp_path / "ledger", "d1", art, **ev)
    assert not (tmp_path / "ledger" / "decision_ledger.jsonl").exists()


def test_hand_built_artifact_cannot_be_recorded(tmp_path):
    # the residual face field-level checking would miss: a HAND-BUILT artifact
    # (invented split text, fabricated provenance stamps — never near text_store)
    # paired with REAL chain evidence and an assembly claiming ITS hash.
    # Re-derivation rebuilds the genuine artifact from the evidence; the hash
    # mismatch refuses, and nothing is written.
    import pandas as pd
    from workspace.research.ai_research_dept.engine.news_cards import (
        assess_flash, build_attribute_bundle, render_news_flash_section,
    )
    from workspace.research.ai_research_dept.engine.news_ingest import (
        build_cluster_snapshots,
    )
    rows = pd.DataFrame([{"src": "sina", "datetime": "2025-01-27 10:00:00",
                          "content": "中芯国际虚构 100 亿大单"}])
    rows["source_published_at"] = pd.to_datetime(rows["datetime"])
    rows["first_ingested_at"] = rows["source_published_at"] + pd.Timedelta(minutes=1)
    rows["decision_visible_at"] = rows["first_ingested_at"]
    rows["object_id_hash"] = "obj:" + rows["content"]
    rows["content_hash"] = "ch:" + rows["content"]      # fabricated provenance
    rows["ingest_class"] = "forward"
    cl = build_cluster_snapshots(rows, ta.CUT)[0]
    typing = {"event_type": "订单合同", "verification_status": "官方证实",
              "content_kind": "事实", "direction": "利好", "importance": 5,
              "is_rumor": False}
    route = {"primary_route": "stock", "subject_codes": ["688981.SH"],
             "industry_tags": [], "concept_tags": [],
             "content": "中芯国际虚构 100 亿大单"}
    card, records, facts = render_news_flash_section(
        [assess_flash(cl, typing, route)], ta.CUT)
    forged_art = build_attribute_bundle(
        [{"base_record_id": "NFD01", "attributes": {"fact": "虚构 100 亿大单"}}],
        facts, records, card=card, decision_id="d1", cutoff=ta.CUT)
    art = chain_artifact("d1", variant="full")           # the REAL chain's evidence
    ev = evidence_for(art)
    ev["assembly"] = _forged_asm(art, artifact_hash=forged_art.artifact_hash)
    with pytest.raises(RegistryError, match="重推导"):
        record_decision(tmp_path / "ledger", "d1", forged_art, **ev)
    assert not (tmp_path / "ledger" / "decision_ledger.jsonl").exists()


def test_evidence_from_another_chain_refused(tmp_path):
    # artifact from chain A, evidence from chain B: identity check or hash
    # mismatch refuses (the two genuine chains cannot be cross-wired)
    art_a = chain_artifact("d1", variant="full")
    art_b = chain_artifact("d1", variant="basic")
    ev_b = evidence_for(art_b)
    ev = dict(ev_b)
    ev["assembly"] = asm_for(art_a)
    with pytest.raises(RegistryError):
        record_decision(tmp_path / "ledger", "d1", art_a, **ev)
    assert not (tmp_path / "ledger" / "decision_ledger.jsonl").exists()


# ------------------------------------------------ obligation (c): the ledger pins

def test_ledger_entry_pins_hash_and_embeds_payload(tmp_path):
    art = chain_artifact("d1", variant="full")
    asm = asm_for(art)
    entry = rec(tmp_path / "ledger", "d1", art)
    assert entry["assembly_hash"] == asm.assembly_hash
    assert entry["assembly"] == asm.payload
    assert lookup_decision(tmp_path / "ledger", "d1")["assembly_hash"] \
        == asm.assembly_hash


def test_record_idempotent_with_same_evidence(tmp_path):
    art = chain_artifact("d1", variant="full")
    e1 = rec(tmp_path / "ledger", "d1", art)
    e2 = rec(tmp_path / "ledger", "d1", art)
    assert e1 == e2


def test_seal_refuses_a_chain_other_than_the_recorded_one(tmp_path):
    # recorded under chain A (variant full); an attacker tries to SEAL claiming a
    # different-but-real assembly (the basic chain's, rebound by forging is
    # impossible — so use a self-consistent forged claim): the ledger byte-compare
    # refuses before anything is written
    art, asm, bundle = _executed(tmp_path)
    other_chain = _forged_asm(art, consumed_assessed_flash_sha256="c" * 64)
    with pytest.raises(RegistryError, match="链 A 入账不得以链 B"):
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch", assembly=other_chain)


# ------------------------------------------------ obligation (d): archive v2 round-trip

def test_archive_round_trip_proves_the_chain(tmp_path):
    art, asm, bundle = _executed(tmp_path)
    archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                    archive_dir=tmp_path / "arch", assembly=asm)
    assert archive["archive_schema"] == "news_decision_archive_v2"
    assert archive["assembly"] == asm.payload
    loaded = load_and_verify_decision_archive(
        "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
    recovered = verify_assembly_provenance(loaded["assembly"])
    assert recovered.ts_code == asm.ts_code == "688981.SH"
    assert recovered.consumed_assessed_flash_sha256 \
        == asm.consumed_assessed_flash_sha256
    assert recovered.selected_fact_occurrence_ids == asm.selected_fact_occurrence_ids
    assert recovered.assembly_hash == asm.assembly_hash


def test_v1_shaped_archive_must_not_verify(tmp_path):
    # obligation (e): strip `assembly`, RE-SEAL the remaining payload (a validly
    # sealed v1 SHAPE, not merely a broken hash) -> strict key set refuses
    art, asm, bundle = _executed(tmp_path)
    archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                    archive_dir=tmp_path / "arch", assembly=asm)
    v1 = {k: v for k, v in archive.items()
          if k not in ("assembly", "archive_sha256")}
    v1["archive_schema"] = "news_decision_archive_v1"
    v1 = {**v1, "archive_sha256": seal_hash(v1)}
    path = _archive_path(tmp_path / "arch", "d1", archive["execution_id"])
    path.write_text(json.dumps(v1, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RegistryError, match="键集"):
        load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")


def test_tampered_archived_assembly_refused(tmp_path):
    # flip ts_code inside the archived assembly, re-seal the ARCHIVE (outer hash
    # valid) -> the inner recompute still refuses
    art, asm, bundle = _executed(tmp_path)
    archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                    archive_dir=tmp_path / "arch", assembly=asm)
    forged = json.loads(json.dumps(archive, ensure_ascii=False))
    forged["assembly"]["ts_code"] = "000001.SZ"          # stale inner hash
    body = {k: v for k, v in forged.items() if k != "archive_sha256"}
    forged["archive_sha256"] = seal_hash(body)
    path = _archive_path(tmp_path / "arch", "d1", archive["execution_id"])
    path.write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RegistryError, match="装配身份"):
        load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")


def test_consistent_but_different_archived_assembly_refused_by_ledger(tmp_path):
    # a SELF-CONSISTENT different chain claim substituted into the archive and
    # re-sealed: inner recompute passes, artifact binding passes, but the LEDGER
    # cross-check (chain pinned at the proven first write) refuses
    art, asm, bundle = _executed(tmp_path)
    archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                    archive_dir=tmp_path / "arch", assembly=asm)
    other = _forged_asm(art, consumed_assessed_flash_sha256="c" * 64)
    forged = json.loads(json.dumps(archive, ensure_ascii=False))
    forged["assembly"] = other.payload
    body = {k: v for k, v in forged.items() if k != "archive_sha256"}
    forged["archive_sha256"] = seal_hash(body)
    path = _archive_path(tmp_path / "arch", "d1", archive["execution_id"])
    path.write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RegistryError, match="链 A 入账不得以链 B"):
        load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")


# ------------------------------------------------ ledger row self-consistency

def test_forged_ledger_assembly_pair_refused(tmp_path):
    # ledger rewrite keeping the row individually re-sealed but with a decoupled
    # assembly/assembly_hash pair -> _read_chain refuses
    art = chain_artifact("d1", variant="full")
    rec(tmp_path / "ledger", "d1", art)
    p = tmp_path / "ledger" / "decision_ledger.jsonl"
    row = json.loads(p.read_text(encoding="utf-8"))
    row["assembly_hash"] = "f" * 64                       # decouple the pair
    body = {k: v for k, v in row.items() if k != "entry_hash"}
    row["entry_hash"] = seal_hash(body)                   # row re-sealed
    p.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="不自洽"):
        lookup_decision(tmp_path / "ledger", "d1")


# ------------------------------------------------ recovery: pure-disk chain identity

def test_recovery_recovers_the_assembly_from_the_ledger(tmp_path):
    # crash between commit and seal: recovery must produce a v2 archive carrying
    # the ledger's PROVEN assembly, from pure disk state, with no new argument
    art, asm, bundle = _executed(tmp_path)                # committed, not sealed
    archive = recover_and_seal_success_archive(
        "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
    assert archive["archive_schema"] == "news_decision_archive_v2"
    assert archive["assembly"] == asm.payload
    loaded = load_and_verify_decision_archive(
        "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
    assert loaded["assembly"] == asm.payload
