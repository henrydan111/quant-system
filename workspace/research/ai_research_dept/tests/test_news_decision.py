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
    # P4a P1 fold: recordable artifacts must come from the REAL chain (the
    # first-write door proves the assembly by re-derivation from P2/P3a evidence)
    from workspace.research.ai_research_dept.tests.assembly_fixtures import (
        chain_artifact,
    )
    return chain_artifact(decision_id, variant="basic")


# --------------------------------------------------- ledger (BINDING #1)

def _rec(ledger_dir, decision_id, art):
    # P4a P1 fold: record with FULL re-derivation evidence (chain-built artifacts
    # register their evidence in assembly_fixtures)
    from workspace.research.ai_research_dept.tests.assembly_fixtures import rec
    return rec(ledger_dir, decision_id, art)


class TestDecisionLedger:
    def test_first_write_and_lookup(self, tmp_path):
        art = _artifact()
        entry = _rec(tmp_path, "d1", art)
        assert entry["bundle_hash"] == art.bundle.bundle_hash
        assert lookup_decision(tmp_path, "d1")["artifact_hash"] == art.artifact_hash

    def test_idempotent_identical_recompute(self, tmp_path):
        art = _artifact()
        e1 = _rec(tmp_path, "d1", art)
        e2 = _rec(tmp_path, "d1", art)      # byte-identical recompute
        assert e1 == e2

    def test_second_different_hash_refused(self, tmp_path):
        from workspace.research.ai_research_dept.tests.assembly_fixtures import (
            chain_artifact,
        )
        _rec(tmp_path, "d1", _artifact())
        # a different GENUINE world line for the SAME decision (different chain —
        # under the P4a evidence door a hand-built world can no longer be recorded)
        other = chain_artifact("d1", variant="full")
        with pytest.raises(RegistryError, match="首写胜出"):
            _rec(tmp_path, "d1", other)

    def test_ledger_owns_expected_id(self, tmp_path):
        # artifact minted for d1 cannot be recorded under the authoritative d2
        with pytest.raises(RegistryError, match="权威"):
            _rec(tmp_path, "d2", _artifact(decision_id="d1"))

    def test_empty_decision_id_refused(self, tmp_path):
        with pytest.raises(RegistryError, match="decision_id"):
            _rec(tmp_path, "  ", _artifact())

    def test_lock_released_and_second_decision_appends(self, tmp_path):
        _rec(tmp_path, "d1", _artifact("d1"))
        assert not (tmp_path / "decision_ledger.jsonl.lock").exists()
        _rec(tmp_path, "d2", _artifact("d2"))
        assert lookup_decision(tmp_path, "d2")["seq"] == 1

    def test_tampered_ledger_duplicate_line_fail_closed(self, tmp_path):
        _rec(tmp_path, "d1", _artifact())
        p = tmp_path / "decision_ledger.jsonl"
        line = p.read_text(encoding="utf-8")
        p.write_text(line + line, encoding="utf-8")    # hand-append duplicate id
        with pytest.raises(RegistryError, match="物理序|重复"):
            lookup_decision(tmp_path, "d1")

    @pytest.mark.parametrize("fld", ["bundle_hash", "artifact_hash",
                                     "final_registry_hash", "source_card_hash",
                                     "cutoff_iso", "seq", "prev_hash"])
    def test_every_field_mutation_fail_closed(self, tmp_path, fld):
        # re-review M1: mutating ANY ledger field breaks the per-row hash/chain
        import json as _json
        _rec(tmp_path, "d1", _artifact())
        p = tmp_path / "decision_ledger.jsonl"
        entry = _json.loads(p.read_text(encoding="utf-8"))
        entry[fld] = 0 if fld == "seq" and entry[fld] != 0 else \
            ("x" * 64 if isinstance(entry[fld], str) else entry[fld] + 1)
        p.write_text(_json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
        with pytest.raises(RegistryError):
            lookup_decision(tmp_path, "d1")

    def test_alternate_world_row_replacement_rejected_for_original(self, tmp_path):
        # re-review M1: an attacker recomputing a self-consistent chain with the
        # OTHER world's row cannot satisfy require_recorded for the original
        # artifact (full-field comparison). Wholesale-replacement detection for
        # the substituted world itself needs the external head anchor (archive
        # unit integration, documented).
        from workspace.research.ai_research_dept.tests.assembly_fixtures import (
            chain_artifact,
        )
        art_a = _artifact("d1")
        _rec(tmp_path, "d1", art_a)
        # world B: same decision id, a different GENUINE chain
        art_b = chain_artifact("d1", variant="full")
        # attacker rewrites the ledger with a self-consistent B row
        p = tmp_path / "decision_ledger.jsonl"
        p.unlink()
        _rec(tmp_path, "d1", art_b)
        with pytest.raises(RegistryError, match="不符"):
            require_recorded(tmp_path, "d1", art_a)


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
        with pytest.raises(RegistryError, match="键须恰 str"):
            serialize_payload_ast({1: "x"})

    def test_identity_bytes_preserved_exactly(self):
        # BINDING #5: no strip/fold/casefold — whitespace survives byte-exact
        s = serialize_payload_ast({"note": "  CLAIM:x  \tRaW"})
        assert '"  CLAIM:x  \\tRaW"' in s

    def test_deterministic_bytes(self):
        ast = {"b": [EvidenceRef("NFD01")], "a": 1}
        assert serialize_payload_ast(ast) == serialize_payload_ast(ast)

    # re-review M2: EXACT types — subclasses of str/dict/EvidenceRef all refuse
    def test_str_subclass_rejected(self):
        class S(str):
            pass
        with pytest.raises(RegistryError, match="闭集外"):
            serialize_payload_ast({"x": S("正文")})

    def test_dict_subclass_rejected(self):
        class D(dict):
            pass
        with pytest.raises(RegistryError, match="闭集外"):
            serialize_payload_ast(D(a=1))

    def test_evidence_ref_subclass_rejected(self):
        class R(EvidenceRef):
            pass
        with pytest.raises(RegistryError, match="闭集外"):
            serialize_payload_ast({"r": R("NFD01")})


# --------------------------------------------------- choke point (BINDING #1+#3+#4)

class TestSealedPayloadChokePoint:
    def _ready(self, tmp_path):
        art = _artifact()
        _rec(tmp_path, "d1", art)
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
                          use=sp.use, target_dimension=sp.target_dimension,
                          payload_text=sp.payload_text + "篡改",
                          registry_hash=sp.registry_hash,
                          artifact_hash=sp.artifact_hash, bundle_hash=sp.bundle_hash,
                          ledger_entry_hash=sp.ledger_entry_hash,
                          expected_ids=sp.expected_ids,
                          ref_occurrences=sp.ref_occurrences,
                          authorized_ids=sp.authorized_ids,
                          payload_ast=sp.payload_ast, payload_hash=sp.payload_hash)

    def test_blank_hash_automint_removed(self, tmp_path):
        # re-review B2: blank payload_hash must reject (no public auto-mint)
        art = self._ready(tmp_path)
        with pytest.raises(RegistryError, match="内部工厂"):
            SealedPayload(decision_id="d1", consumer_seat="news",
                          use="factor_positive", target_dimension=None,
                          payload_text="{}", registry_hash="a" * 64,
                          artifact_hash="b" * 64, bundle_hash="c" * 64,
                          ledger_entry_hash="d" * 64, expected_ids=(),
                          ref_occurrences=(), authorized_ids=(), payload_ast={})

    def test_fresh_self_mint_stopped_at_executor_boundary(self, tmp_path):
        # re-review B2 named probe: a FRESH self-consistent mint (attacker computes
        # the seal himself) for an UNRECORDED decision constructs as an object but
        # is refused by the executor-boundary verifier
        from workspace.research.ai_research_dept.engine.news_decision import (
            verify_payload_for_execution,
        )
        from workspace.research.ai_research_dept.engine.news_seal import seal_hash
        art = _artifact(decision_id="d9")               # d9 NOT recorded
        fields = {"decision_id": "d9", "seat": "news", "use": "factor_positive",
                  "dimension": None, "payload_text": "{}",
                  "registry_hash": art.final_registry.registry_hash,
                  "artifact_hash": art.artifact_hash,
                  "bundle_hash": art.bundle.bundle_hash,
                  "ledger_entry_hash": "e" * 64, "expected_ids": [],
                  "ref_occurrences": [], "authorized_ids": []}
        forged = SealedPayload(
            decision_id="d9", consumer_seat="news", use="factor_positive",
            target_dimension=None, payload_text="{}",
            registry_hash=art.final_registry.registry_hash,
            artifact_hash=art.artifact_hash, bundle_hash=art.bundle.bundle_hash,
            ledger_entry_hash="e" * 64, expected_ids=(), ref_occurrences=(),
            authorized_ids=(), payload_ast={}, payload_hash=seal_hash(fields))
        with pytest.raises(RegistryError, match="未入账"):
            verify_payload_for_execution(
                forged, art, ledger_dir=tmp_path, expected_decision_id="d9",
                expected_consumer_seat="news", expected_use="factor_positive",
                expected_target_dimension=None)


class TestRoleReplay:
    # re-review#2(seat) B1: the boundary must verify the CALLER'S expected
    # context, never trust the object's sealed role/mode
    def _ready(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_decision import (
            leg_expected_ids,
        )
        from workspace.research.ai_research_dept.tests.assembly_fixtures import (
            chain_artifact,
        )
        # "full" chain: NFD01 split (fact/source_status children) + NFR01 rumor
        art = chain_artifact("d1", variant="full")
        _rec(tmp_path, "d1", art)
        pen_ids = leg_expected_ids(art.final_registry, use="penalty",
                                   consumer_seat="news")
        pen = build_sealed_payload({"risks": [EvidenceRef(r) for r in pen_ids]},
                                   art, ledger_dir=tmp_path, decision_id="d1",
                                   consumer_seat="news", use="penalty")
        return art, pen

    def test_penalty_payload_replayed_into_factor_slot_refused(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_decision import (
            verify_payload_for_execution,
        )
        art, pen = self._ready(tmp_path)
        with pytest.raises(RegistryError, match="重放进错槽"):
            verify_payload_for_execution(
                pen, art, ledger_dir=tmp_path, expected_decision_id="d1",
                expected_consumer_seat="news", expected_use="factor_positive",
                expected_target_dimension=None)

    def test_wrong_seat_or_dimension_replay_refused(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_decision import (
            verify_payload_for_execution,
        )
        art, pen = self._ready(tmp_path)
        with pytest.raises(RegistryError, match="重放进错槽"):
            verify_payload_for_execution(
                pen, art, ledger_dir=tmp_path, expected_decision_id="d1",
                expected_consumer_seat="bear", expected_use="penalty",
                expected_target_dimension=None)
        with pytest.raises(RegistryError, match="重放进错槽"):
            verify_payload_for_execution(
                pen, art, ledger_dir=tmp_path, expected_decision_id="d1",
                expected_consumer_seat="news", expected_use="penalty",
                expected_target_dimension="coordination_risk")

    def test_subclass_expected_context_refused(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_decision import (
            verify_payload_for_execution,
        )
        art, pen = self._ready(tmp_path)

        class S(str):
            pass
        with pytest.raises(RegistryError, match="子类拒"):
            verify_payload_for_execution(
                pen, art, ledger_dir=tmp_path, expected_decision_id=S("d1"),
                expected_consumer_seat="news", expected_use="penalty",
                expected_target_dimension=None)


class TestProvenanceMultiplicity:
    # re-review#2(seat) B2: a typed reference cannot shield bare same-id copies
    def _ready(self, tmp_path):
        art = _artifact()
        _rec(tmp_path, "d1", art)
        from workspace.research.ai_research_dept.engine.news_decision import (
            leg_expected_ids,
        )
        ids = leg_expected_ids(art.final_registry, use="factor_positive",
                               consumer_seat="news")
        return art, ids

    def test_typed_plus_bare_copy_refused(self, tmp_path):
        art, ids = self._ready(tmp_path)
        ast = {"facts": [EvidenceRef(r) for r in ids],
               "note": f"[{ids[0]}]"}                   # bare same-id copy
        with pytest.raises(RegistryError, match="重数|出处"):
            build_sealed_payload(ast, art, ledger_dir=tmp_path, decision_id="d1",
                                 consumer_seat="news", use="factor_positive")

    def test_typed_plus_two_bare_copies_refused(self, tmp_path):
        art, ids = self._ready(tmp_path)
        ast = {"facts": [EvidenceRef(r) for r in ids],
               "a": f"[{ids[0]}]", "b": f"参见 [{ids[0]}]"}
        with pytest.raises(RegistryError, match="重数|出处"):
            build_sealed_payload(ast, art, ledger_dir=tmp_path, decision_id="d1",
                                 consumer_seat="news", use="factor_positive")

    def test_bare_copy_in_dict_key_refused(self, tmp_path):
        art, ids = self._ready(tmp_path)
        ast = {"facts": [EvidenceRef(r) for r in ids],
               f"[{ids[0]}]": "键里的裸副本"}
        with pytest.raises(RegistryError, match="重数|出处"):
            build_sealed_payload(ast, art, ledger_dir=tmp_path, decision_id="d1",
                                 consumer_seat="news", use="factor_positive")


class TestLegCompleteness:
    # re-review B1: expected populations enforced exactly-once before executors
    def _ready(self, tmp_path):
        art = _artifact()
        _rec(tmp_path, "d1", art)
        return art

    def _leg_expected(self, art):
        from workspace.research.ai_research_dept.engine.news_decision import (
            leg_expected_ids,
        )
        return leg_expected_ids(art.final_registry, use="factor_positive",
                                consumer_seat="news")

    def _build(self, tmp_path, art, ast):
        return build_sealed_payload(ast, art, ledger_dir=tmp_path,
                                    decision_id="d1", consumer_seat="news",
                                    use="factor_positive")

    def test_complete_population_passes(self, tmp_path):
        art = self._ready(tmp_path)
        ast = {"facts": [EvidenceRef(rid) for rid in self._leg_expected(art)]}
        sp = self._build(tmp_path, art, ast)
        assert sp.expected_ids == self._leg_expected(art)
        assert sorted(sp.ref_occurrences) == list(sp.expected_ids)

    def test_empty_payload_refused(self, tmp_path):
        art = self._ready(tmp_path)
        with pytest.raises(RegistryError, match="完整性"):
            self._build(tmp_path, art, {"facts": []})

    def test_subset_refused(self, tmp_path):
        art = self._ready(tmp_path)
        ids = self._leg_expected(art)
        ast = {"facts": [EvidenceRef(ids[0])]}          # one-record subset
        with pytest.raises(RegistryError, match="完整性"):
            self._build(tmp_path, art, ast)

    def test_duplicate_refused(self, tmp_path):
        art = self._ready(tmp_path)
        ids = self._leg_expected(art)
        ast = {"facts": [EvidenceRef(r) for r in ids] + [EvidenceRef(ids[0])]}
        with pytest.raises(RegistryError, match="完整性"):
            self._build(tmp_path, art, ast)

    def test_plain_string_ref_lookalike_refused(self, tmp_path):
        # re-review M2: [ID] syntax is EvidenceRef-exclusive — an ordinary string
        # carrying an authorized-looking token fails the provenance proof
        art = self._ready(tmp_path)
        ids = self._leg_expected(art)
        ast = {"facts": [EvidenceRef(r) for r in ids[1:]] + [f"[{ids[0]}]"]}
        with pytest.raises(RegistryError, match="出处"):
            self._build(tmp_path, art, ast)
