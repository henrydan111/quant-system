# NF integration P4a: ledger + archive chain binding — the five frozen obligations.
# (a) assembly REQUIRED, no default; (b) verify-then-bind order; (c) ledger pins
# assembly_hash + embeds the payload; (d) archive schema v2 + read-back recompute;
# (e) the refusal matrix below, incl. "a v1-shaped archive must not verify".
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_archive import (  # noqa: E402
    _archive_path, load_and_verify_decision_archive,
    recover_and_seal_success_archive, seal_decision_archive,
)
from workspace.research.ai_research_dept.engine.news_cards import (  # noqa: E402
    assess_flash, build_attribute_bundle, render_news_flash_section,
)
from workspace.research.ai_research_dept.engine.news_decision import (  # noqa: E402
    lookup_decision, record_decision,
)
from workspace.research.ai_research_dept.engine.news_evidence import (  # noqa: E402
    RegistryError,
)
from workspace.research.ai_research_dept.engine.news_executors import (  # noqa: E402
    NewsScoringContract, execute_news_decision,
)
from workspace.research.ai_research_dept.engine.news_flash_assemble import (  # noqa: E402
    verify_assembly_provenance,
)
from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    build_cluster_snapshots,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash  # noqa: E402
from workspace.research.ai_research_dept.tests.assembly_fixtures import (  # noqa: E402
    asm_for,
)

import pandas as pd  # noqa: E402

CUT = "2025-01-27 18:00:00"


def _stamp(rows, ingest_class="forward"):
    df = pd.DataFrame(rows)
    df["source_published_at"] = pd.to_datetime(df["datetime"])
    df["first_ingested_at"] = pd.to_datetime(df["datetime"]) + pd.Timedelta(minutes=1)
    df["decision_visible_at"] = df[["source_published_at",
                                    "first_ingested_at"]].max(axis=1)
    df["object_id_hash"] = df.apply(
        lambda r: "obj:" + str(r["src"]) + "|" + str(r["datetime"]) + "|"
        + str(r["content"]), axis=1)
    df["content_hash"] = df["content"].map(lambda c: "ch:" + str(c))
    df["ingest_class"] = ingest_class
    return df


def _assessed(content, *, importance=5, dt="2025-01-27 10:00:00"):
    cluster = build_cluster_snapshots(
        _stamp([{"src": "sina", "datetime": dt, "content": content}]), CUT)[0]
    typing = {"event_type": "订单合同", "verification_status": "官方证实",
              "content_kind": "事实", "direction": "利好",
              "importance": importance, "is_rumor": False}
    route = {"primary_route": "stock", "subject_codes": ["688981.SH"],
             "industry_tags": [], "concept_tags": [], "content": content}
    return assess_flash(cluster, typing, route)


def _artifact(decision_id="d1"):
    card, records, facts = render_news_flash_section(
        [_assessed("重大订单甲", importance=5)], CUT)
    split = {"base_record_id": "NFD01",
             "attributes": {"fact": "签订 12 亿订单", "economic_linkage": "年营收 15%"}}
    return build_attribute_bundle([split], facts, records, card=card,
                                  decision_id=decision_id, cutoff=CUT)


class _Reply:
    def __init__(self, text):
        self.text = text


def _call_fn():
    factor = {"factor_scores": [
                  {"name": "event_materiality", "score_0_5": 5,
                   "citations": ["NFD01.fact"]},
                  {"name": "fundamental_link", "score_0_5": 5,
                   "citations": ["NFD01.economic_linkage"]},
                  {"name": "novelty", "score_0_5": 5, "citations": ["NFD01"]}],
              "horizon_factor_scores": [
                  {"name": "tradeability_at_horizon", "horizon": h,
                   "score_0_5": 0, "citations": []}
                  for h in ("next_open", "1-3d", "5-20d")],
              "horizon_theses": []}
    penalty = {"penalty_scores": [
                   {"name": "manipulation_risk", "score_0_5": 0, "citations": []},
                   {"name": "confidence_cap", "score_0_5": 0, "citations": []}],
               "risk_flags": []}

    def fn(msgs):
        if "因子分析" in msgs[0]["content"]:
            return _Reply(json.dumps(factor, ensure_ascii=False))
        return _Reply(json.dumps(penalty, ensure_ascii=False))
    return fn


def _contract():
    return NewsScoringContract(schema_id="c16_news_horizon_v1",
                               output_mode="primary_horizon",
                               primary_decision_horizon="1-3d")


def _dirs(tmp_path):
    return dict(ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
                contract=_contract())


def _executed(tmp_path, decision_id="d1"):
    art = _artifact(decision_id)
    asm = asm_for(art)
    record_decision(tmp_path / "ledger", decision_id, art, assembly=asm)
    bundle = execute_news_decision(
        art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
        decision_id=decision_id, contract=_contract(), call_fn=_call_fn())
    return art, asm, bundle


# ------------------------------------------------ obligation (a): REQUIRED, no default

def test_record_without_assembly_is_a_typeerror(tmp_path):
    art = _artifact()
    with pytest.raises(TypeError, match="assembly"):
        record_decision(tmp_path / "ledger", "d1", art)


def test_seal_without_assembly_is_a_typeerror(tmp_path):
    art, asm, bundle = _executed(tmp_path)
    with pytest.raises(TypeError, match="assembly"):
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")


def test_record_with_none_assembly_refused(tmp_path):
    art = _artifact()
    with pytest.raises(RegistryError, match="AssemblyProvenance"):
        record_decision(tmp_path / "ledger", "d1", art, assembly=None)


# ------------------------------------------------ obligation (b)+(c): bind + pin

def test_record_refuses_assembly_for_a_different_artifact(tmp_path):
    art = _artifact("d1")
    other = _artifact("d2")
    with pytest.raises(RegistryError, match="不成对"):
        record_decision(tmp_path / "ledger", "d1", art, assembly=asm_for(other))


def test_ledger_entry_pins_hash_and_embeds_payload(tmp_path):
    art = _artifact()
    asm = asm_for(art)
    entry = record_decision(tmp_path / "ledger", "d1", art, assembly=asm)
    assert entry["assembly_hash"] == asm.assembly_hash
    assert entry["assembly"] == asm.payload
    assert lookup_decision(tmp_path / "ledger", "d1")["assembly_hash"] \
        == asm.assembly_hash


def test_record_idempotent_with_same_assembly(tmp_path):
    art = _artifact()
    asm = asm_for(art)
    e1 = record_decision(tmp_path / "ledger", "d1", art, assembly=asm)
    e2 = record_decision(tmp_path / "ledger", "d1", art, assembly=asm)
    assert e1 == e2


def test_same_artifact_second_chain_refused(tmp_path):
    # first-write-wins now pins WHICH upstream chain owns the decision id
    art = _artifact()
    record_decision(tmp_path / "ledger", "d1", art, assembly=asm_for(art))
    other_chain = asm_for(art, assessed_sha="c" * 64)     # same artifact, chain B
    with pytest.raises(RegistryError, match="第二条上游链|钉死链"):
        record_decision(tmp_path / "ledger", "d1", art, assembly=other_chain)


def test_seal_refuses_a_chain_other_than_the_recorded_one(tmp_path):
    art, asm, bundle = _executed(tmp_path)
    other_chain = asm_for(art, assessed_sha="c" * 64)     # valid, but not recorded
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
    assert recovered.ts_code == "688981.SH"
    assert recovered.consumed_assessed_flash_sha256 == "a" * 64
    assert recovered.selected_fact_occurrence_ids == asm.selected_fact_occurrence_ids
    assert recovered.assembly_hash == asm.assembly_hash


def test_v1_shaped_archive_must_not_verify(tmp_path):
    # obligation (e)'s round-trip half: strip `assembly`, RE-SEAL the remaining
    # payload (a validly-sealed v1 SHAPE, not merely a broken hash) -> the strict
    # key set refuses it structurally
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
    # valid) -> the inner recompute (verify_assembly_provenance) still refuses
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
    # replace the archived assembly with a SELF-CONSISTENT different chain and
    # re-seal the archive -> inner recompute passes, artifact binding passes,
    # but the LEDGER cross-check (chain pinned at record) refuses
    art, asm, bundle = _executed(tmp_path)
    archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                    archive_dir=tmp_path / "arch", assembly=asm)
    other_chain = asm_for(art, assessed_sha="c" * 64)
    forged = json.loads(json.dumps(archive, ensure_ascii=False))
    forged["assembly"] = other_chain.payload
    body = {k: v for k, v in forged.items() if k != "archive_sha256"}
    forged["archive_sha256"] = seal_hash(body)
    path = _archive_path(tmp_path / "arch", "d1", archive["execution_id"])
    path.write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RegistryError, match="链 A 入账不得以链 B"):
        load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")


# ------------------------------------------------ ledger row self-consistency

def test_forged_ledger_assembly_pair_refused(tmp_path):
    # whole-ledger rewrite keeping every row individually re-sealed, but with an
    # assembly/assembly_hash pair that does not cohere -> _read_chain refuses
    art = _artifact()
    record_decision(tmp_path / "ledger", "d1", art, assembly=asm_for(art))
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
    # crash between commit and seal: no archive exists; recovery must produce a
    # v2 archive carrying the LEDGER's assembly, from pure disk state, with no
    # assembly argument of its own
    art, asm, bundle = _executed(tmp_path)                # committed, not sealed
    archive = recover_and_seal_success_archive(
        "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
    assert archive["archive_schema"] == "news_decision_archive_v2"
    assert archive["assembly"] == asm.payload
    loaded = load_and_verify_decision_archive(
        "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
    assert loaded["assembly"] == asm.payload
