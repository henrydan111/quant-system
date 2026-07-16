# NF seat wiring unit 1: decision ledger + sealed payload choke point.
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_cards import (  # noqa: E402
    assess_flash, build_attribute_bundle, render_news_flash_section,
)
from workspace.research.ai_research_dept.engine.news_decision import (  # noqa: E402
    SealedPayload, build_sealed_payload, factor_refs, lookup_decision,
    record_decision, require_recorded, serialize_payload_ast,
)
from workspace.research.ai_research_dept.engine.news_evidence import (  # noqa: E402
    EvidenceRef, PayloadGateError, RegistryError,
)
from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    build_cluster_snapshots,
)
from workspace.research.ai_research_dept.engine.news_seal import SealError  # noqa: E402

CUT = "2025-01-27 18:00:00"


def _stamp(rows, ingest_class="forward"):
    df = pd.DataFrame(rows)
    df["source_published_at"] = pd.to_datetime(df["datetime"])
    df["first_ingested_at"] = pd.to_datetime(df["datetime"]) + pd.Timedelta(minutes=1)
    df["decision_visible_at"] = df[["source_published_at", "first_ingested_at"]].max(axis=1)
    df["object_id_hash"] = df.apply(
        lambda r: "obj:" + str(r["src"]) + "|" + str(r["datetime"]) + "|" + str(r["content"]),
        axis=1)
    df["content_hash"] = df["content"].map(lambda c: "ch:" + str(c))
    df["ingest_class"] = ingest_class
    return df


def _cluster(content, dt="2025-01-27 10:00:00"):
    return build_cluster_snapshots(
        _stamp([{"src": "sina", "datetime": dt, "content": content}]), CUT)[0]


def _assessed(content, *, status="官方证实", importance=3, dt="2025-01-27 10:00:00"):
    typing = {"event_type": "订单合同", "verification_status": status,
              "content_kind": "事实", "direction": "利好",
              "importance": importance, "is_rumor": False}
    route = {"primary_route": "stock", "subject_codes": ["688981.SH"],
             "industry_tags": [], "concept_tags": [], "content": content}
    return assess_flash(_cluster(content, dt), typing, route)


def _artifact(decision_id="d1"):
    card, records, facts = render_news_flash_section(
        [_assessed("重大订单甲", importance=5),
         _assessed("小事件乙", importance=3, dt="2025-01-27 09:00:00")], CUT)
    split = {"base_record_id": "NFD01",
             "attributes": {"fact": "签订 12 亿订单", "economic_linkage": "年营收 15%"}}
    return build_attribute_bundle([split], facts, records, card=card,
                                  decision_id=decision_id, cutoff=CUT)


# --------------------------------------------------- ledger (BINDING #1)

class TestDecisionLedger:
    def test_first_write_and_lookup(self, tmp_path):
        art = _artifact()
        entry = record_decision(tmp_path, "d1", art)
        assert entry["bundle_hash"] == art.bundle.bundle_hash
        assert lookup_decision(tmp_path, "d1")["artifact_hash"] == art.artifact_hash

    def test_idempotent_identical_recompute(self, tmp_path):
        art = _artifact()
        e1 = record_decision(tmp_path, "d1", art)
        e2 = record_decision(tmp_path, "d1", art)      # byte-identical recompute
        assert e1 == e2

    def test_second_different_hash_refused(self, tmp_path):
        record_decision(tmp_path, "d1", _artifact())
        # a different world line for the SAME decision (different split text)
        card, records, facts = render_news_flash_section(
            [_assessed("重大订单甲", importance=5),
             _assessed("小事件乙", importance=3, dt="2025-01-27 09:00:00")], CUT)
        other = build_attribute_bundle(
            [{"base_record_id": "NFD01", "attributes": {"fact": "另一措辞"}}],
            facts, records, card=card, decision_id="d1", cutoff=CUT)
        with pytest.raises(RegistryError, match="首写胜出"):
            record_decision(tmp_path, "d1", other)

    def test_ledger_owns_expected_id(self, tmp_path):
        # artifact minted for d1 cannot be recorded under the authoritative d2
        with pytest.raises(RegistryError, match="权威"):
            record_decision(tmp_path, "d2", _artifact(decision_id="d1"))

    def test_empty_decision_id_refused(self, tmp_path):
        with pytest.raises(RegistryError, match="decision_id"):
            record_decision(tmp_path, "  ", _artifact())

    def test_lock_released_and_second_decision_appends(self, tmp_path):
        record_decision(tmp_path, "d1", _artifact("d1"))
        assert not (tmp_path / "decision_ledger.jsonl.lock").exists()
        record_decision(tmp_path, "d2", _artifact("d2"))
        assert lookup_decision(tmp_path, "d2")["seq"] == 1

    def test_tampered_ledger_duplicate_line_fail_closed(self, tmp_path):
        record_decision(tmp_path, "d1", _artifact())
        p = tmp_path / "decision_ledger.jsonl"
        line = p.read_text(encoding="utf-8")
        p.write_text(line + line, encoding="utf-8")    # hand-append duplicate id
        with pytest.raises(RegistryError, match="重复 decision_id"):
            lookup_decision(tmp_path, "d1")


# --------------------------------------------------- closed AST (BINDING #2/#5)

class TestClosedAst:
    def test_evidence_ref_encodes(self):
        assert serialize_payload_ast({"refs": [EvidenceRef("NFD01")]}) \
            == '{"refs": ["[NFD01]"]}'

    def test_set_rejected(self):
        with pytest.raises(RegistryError, match="闭集外"):
            serialize_payload_ast({"ids": {"NFD01"}})

    def test_custom_object_rejected_no_default_str(self):
        class Sneaky:
            def __str__(self):
                return "[NFD01]"
        with pytest.raises(RegistryError, match="闭集外"):
            serialize_payload_ast({"x": Sneaky()})

    def test_nan_inf_rejected(self):
        for bad in (float("nan"), float("inf")):
            with pytest.raises(RegistryError, match="非有限"):
                serialize_payload_ast({"v": bad})

    def test_non_str_key_rejected(self):
        with pytest.raises(RegistryError, match="键须 str"):
            serialize_payload_ast({1: "x"})

    def test_identity_bytes_preserved_exactly(self):
        # BINDING #5: no strip/fold/casefold — whitespace survives byte-exact
        s = serialize_payload_ast({"note": "  CLAIM:x  \tRaW"})
        assert '"  CLAIM:x  \\tRaW"' in s

    def test_deterministic_bytes(self):
        ast = {"b": [EvidenceRef("NFD01")], "a": 1}
        assert serialize_payload_ast(ast) == serialize_payload_ast(ast)


# --------------------------------------------------- choke point (BINDING #1+#3+#4)

class TestSealedPayloadChokePoint:
    def _ready(self, tmp_path):
        art = _artifact()
        record_decision(tmp_path, "d1", art)
        return art

    def test_happy_path(self, tmp_path):
        art = self._ready(tmp_path)
        refs = factor_refs(art, consumer_seat="news",
                           target_dimension="event_materiality")
        assert refs and all(isinstance(r, EvidenceRef) for r in refs)
        sp = build_sealed_payload({"facts": refs}, art, ledger_dir=tmp_path,
                                  decision_id="d1", consumer_seat="news",
                                  target_dimension="event_materiality")
        assert sp.registry_hash == art.final_registry.registry_hash
        assert set(sp.authorized_ids) == {r.record_id for r in refs}
        assert len(sp.payload_hash) == 64

    def test_unrecorded_decision_refused(self, tmp_path):
        art = _artifact()                              # NOT recorded
        with pytest.raises(RegistryError, match="未入账"):
            build_sealed_payload({"facts": []}, art, ledger_dir=tmp_path,
                                 decision_id="d1", consumer_seat="news",
                                 target_dimension="event_materiality")

    def test_ledger_mismatched_artifact_refused(self, tmp_path):
        self._ready(tmp_path)                          # d1 recorded (world line A)
        card, records, facts = render_news_flash_section(
            [_assessed("重大订单甲", importance=5),
             _assessed("小事件乙", importance=3, dt="2025-01-27 09:00:00")], CUT)
        other = build_attribute_bundle(
            [{"base_record_id": "NFD01", "attributes": {"fact": "另一措辞"}}],
            facts, records, card=card, decision_id="d1", cutoff=CUT)
        with pytest.raises(RegistryError, match="账本行不符"):
            require_recorded(tmp_path, "d1", other)

    def test_unauthorized_ref_hard_fails_on_final_bytes(self, tmp_path):
        art = self._ready(tmp_path)
        # the demoted NFD01 is context_only — an EvidenceRef to it must hard-fail
        with pytest.raises(PayloadGateError, match="NFD01"):
            build_sealed_payload({"facts": [EvidenceRef("NFD01")]}, art,
                                 ledger_dir=tmp_path, decision_id="d1",
                                 consumer_seat="news",
                                 target_dimension="event_materiality")

    def test_bare_known_id_in_string_field_refused(self, tmp_path):
        art = self._ready(tmp_path)
        with pytest.raises(PayloadGateError, match="裸/畸形"):
            build_sealed_payload({"note": "参考 NFD01.fact 行"}, art,
                                 ledger_dir=tmp_path, decision_id="d1",
                                 consumer_seat="news",
                                 target_dimension="event_materiality")

    def test_fabricated_ref_refused(self, tmp_path):
        art = self._ready(tmp_path)
        with pytest.raises(PayloadGateError, match="未注册"):
            build_sealed_payload({"facts": [EvidenceRef("NFD99")]}, art,
                                 ledger_dir=tmp_path, decision_id="d1",
                                 consumer_seat="news",
                                 target_dimension="event_materiality")

    def test_sealed_payload_forge_rejected(self, tmp_path):
        art = self._ready(tmp_path)
        refs = factor_refs(art, consumer_seat="news",
                           target_dimension="event_materiality")
        sp = build_sealed_payload({"facts": refs}, art, ledger_dir=tmp_path,
                                  decision_id="d1", consumer_seat="news",
                                  target_dimension="event_materiality")
        with pytest.raises(SealError):
            SealedPayload(decision_id=sp.decision_id, consumer_seat=sp.consumer_seat,
                          target_dimension=sp.target_dimension,
                          payload_text=sp.payload_text + "篡改",
                          registry_hash=sp.registry_hash,
                          authorized_ids=sp.authorized_ids,
                          payload_hash=sp.payload_hash)
