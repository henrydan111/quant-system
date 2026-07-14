# NF §7 step 5+6 core: sealed per-card metadata registry + ceiling arithmetic + ternary gate.
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_evidence import (  # noqa: E402
    CardRecord, PayloadGateError, RegistryError, SealedCardRegistry, assert_factor_payload,
    authorize, build_card_record, build_card_registry, build_factor_payload_ids,
    dimension_ceiling,
)
from workspace.research.ai_research_dept.engine.news_seal import SealError  # noqa: E402

CUT = "2025-01-27T18:00:00"


def _nfd(rid="NFD01", dim="event_materiality"):
    return build_card_record(rid, domain="news", evidence_class="NFD",
                             allowed_uses={"factor_positive", "context_only"},
                             allowed_consumers={"news"}, allowed_dimensions={dim})


def _nfi(rid="NFI01", dim="event_materiality"):
    return build_card_record(rid, domain="news", evidence_class="NFI",
                             allowed_uses={"factor_positive"}, allowed_consumers={"news"},
                             allowed_dimensions={dim})


def _attention(rid="N00"):
    return build_card_record(rid, domain="attention", evidence_class="attention_only",
                             allowed_uses={"context_only", "bear"},
                             allowed_consumers={"bear", "chief", "display"})


def _coordination(rid="NFC01"):
    return build_card_record(rid, domain="coordination", evidence_class="coordination_risk",
                             allowed_uses={"penalty", "bear"}, allowed_consumers={"news", "bear"},
                             allowed_dimensions={"coordination_risk"})


def _macro(rid="M01"):
    # M01-M16 是冻结保留 ID(re-review Major-3/#3 B1)——须经类型化 m_line_v1 且逐字一致
    return build_card_record(rid, domain="macro", evidence_class="market_state_fact",
                             allowed_uses={"factor_positive", "context_only"},
                             allowed_consumers={"macro"},
                             allowed_dimensions={"risk_appetite_environment_fit"},
                             record_schema_id="m_line_v1")


# --------------------------------------------------- record invariants

class TestCardRecord:
    def test_valid_factor_record_seals(self):
        r = _nfd()
        assert len(r.content_hash) == 64 and r.positive_ceiling == 5

    def test_attention_cannot_be_factor_positive(self):
        with pytest.raises(RegistryError, match="factor_positive"):
            build_card_record("N00", domain="attention", evidence_class="attention_only",
                              allowed_uses={"factor_positive"}, allowed_consumers={"news"},
                              allowed_dimensions={"event_materiality"})

    def test_rumor_cannot_be_factor_positive(self):
        with pytest.raises(RegistryError):
            build_card_record("NFR01", domain="news", evidence_class="NFR",
                              allowed_uses={"factor_positive"}, allowed_consumers={"news"},
                              allowed_dimensions={"event_materiality"})

    def test_coordination_only_penalty_bear(self):
        with pytest.raises(RegistryError, match="越界"):
            build_card_record("NFC01", domain="coordination", evidence_class="coordination_risk",
                              allowed_uses={"context_only"}, allowed_consumers={"news"})

    def test_research_summary_only_display(self):
        r = build_card_record("RS01", domain="research", evidence_class="research_summary",
                              allowed_uses={"display_only"}, allowed_consumers={"display", "chief"})
        assert r.positive_ceiling == 0
        with pytest.raises(RegistryError):
            build_card_record("RS02", domain="research", evidence_class="research_summary",
                              allowed_uses={"factor_positive"}, allowed_consumers={"news"},
                              allowed_dimensions={"event_materiality"})

    def test_factor_requires_dimensions(self):
        with pytest.raises(RegistryError, match="allowed_dimensions"):
            build_card_record("NFD9", domain="news", evidence_class="NFD",
                              allowed_uses={"factor_positive"}, allowed_consumers={"news"},
                              allowed_dimensions=())

    def test_unknown_evidence_class(self):
        with pytest.raises(RegistryError, match="未知 evidence_class"):
            build_card_record("XX01", domain="news", evidence_class="HYPE",
                              allowed_uses={"context_only"}, allowed_consumers={"news"})

    # re-review#2 M2 + re-review#3 M2: ID grammar (fullmatch — trailing
    # newline/CR/NUL are "visually duplicate identities") + domain enum
    @pytest.mark.parametrize("bad_id", ["", ".", "nfd01", "N", "NFD01.hype",
                                        "NFD01.fact.fact", "A" * 20,
                                        "NFD01\n", "MP01\n", "NFD01\r", "NFD01\x00"])
    def test_id_grammar_rejected(self, bad_id):
        with pytest.raises(RegistryError, match="不合语法"):
            build_card_record(bad_id, domain="news", evidence_class="NFD",
                              allowed_uses={"context_only"}, allowed_consumers={"news"})

    def test_unregistered_domain_rejected(self):
        with pytest.raises(RegistryError, match="domain"):
            build_card_record("NFD01", domain="hype", evidence_class="NFD",
                              allowed_uses={"context_only"}, allowed_consumers={"news"})

    def test_forged_content_hash_rejected(self):
        r = _nfd()
        with pytest.raises(SealError):
            CardRecord(record_id=r.record_id, domain=r.domain, evidence_class=r.evidence_class,
                       allowed_uses=r.allowed_uses, allowed_consumers=r.allowed_consumers,
                       allowed_dimensions=r.allowed_dimensions, content_hash="0" * 64)


class TestReservedMLine:
    # re-review Major-3: the factory itself refuses a reserved M-id minted with
    # ANY metadata deviating from the frozen authoritative table
    def test_m16_with_factor_positive_rejected(self):
        with pytest.raises(RegistryError, match="保留 ID"):
            build_card_record("M16", domain="macro", evidence_class="market_state_fact",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"macro"},
                              allowed_dimensions={"policy_alignment"})

    def test_m01_with_wrong_dimension_rejected(self):
        with pytest.raises(RegistryError, match="保留 ID"):
            build_card_record("M01", domain="macro", evidence_class="market_state_fact",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"macro"},
                              allowed_dimensions={"liquidity_flows_transmission"})

    def test_m04_with_extra_consumer_rejected(self):
        with pytest.raises(RegistryError, match="保留 ID"):
            build_card_record("M04", domain="macro", evidence_class="market_limit_state",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"macro", "news"},
                              allowed_dimensions={"risk_appetite_environment_fit",
                                                  "liquidity_flows_transmission"})

    def test_canonical_mint_accepted(self):
        assert _macro("M01").record_id == "M01"        # 逐字规范 → 可铸

    def test_m_line_domain_is_part_of_frozen_identity(self):
        # re-review#2 M2: canonical M01 metadata but domain="news" must be refused
        with pytest.raises(RegistryError, match="保留 ID"):
            build_card_record("M01", domain="news", evidence_class="market_state_fact",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"macro"},
                              allowed_dimensions={"risk_appetite_environment_fit"})

    def test_mp_prefix_reserved_at_kernel(self):
        # re-review#2 M2: a direct kernel mint of MP01 as a positive news/NFD
        # record bypassed the taxonomy factory — now refused at the kernel
        with pytest.raises(RegistryError, match="MP 保留命名空间"):
            build_card_record("MP01", domain="news", evidence_class="NFD",
                              allowed_uses={"factor_positive"},
                              allowed_consumers={"news"},
                              allowed_dimensions={"event_materiality"})

    def test_mf_prefix_reserved_at_kernel(self):
        with pytest.raises(RegistryError, match="MF 保留命名空间"):
            build_card_record("MF01", domain="news", evidence_class="NFD",
                              allowed_uses={"factor_positive"},
                              allowed_consumers={"news"},
                              allowed_dimensions={"event_materiality"})

    def test_mfr_variant_reserved_at_kernel(self):
        with pytest.raises(RegistryError, match="MF"):
            build_card_record("MFR01", domain="news", evidence_class="NFR",
                              allowed_uses={"penalty", "bear"},
                              allowed_consumers={"news", "bear"},
                              allowed_dimensions={"manipulation_risk"})


def _d7_child(parent, attr="economic_linkage", evidence_class=None,
              registry_parent_content_hash=None):
    # re-review#4 B1: d7_child_v2 seals BOTH source and registry parent hashes
    from workspace.research.ai_research_dept.engine.news_evidence import ATTRIBUTE_DIMENSIONS
    rph = registry_parent_content_hash or parent.content_hash
    return build_card_record(
        f"{parent.record_id}.{attr}", domain="news",
        evidence_class=evidence_class or parent.evidence_class,
        allowed_uses={"factor_positive", "context_only"}, allowed_consumers={"news"},
        allowed_dimensions=ATTRIBUTE_DIMENSIONS[attr],
        record_schema_id="d7_child_v2",
        derivation=(("source_parent_content_hash", parent.content_hash),
                    ("registry_parent_content_hash", rph),
                    ("attribute_type", attr)))


class TestHierarchicalIdScan:
    # re-review#4 B2: references have a SYNTAX ([ID]); a token resolves atomically
    def test_d7_child_does_not_double_resolve_parent(self):
        from workspace.research.ai_research_dept.engine.news_evidence import scan_payload_ids
        parent = _nfd("NFD01")
        child = _d7_child(parent)
        reg = build_card_registry(CUT, [parent, child])
        # the child bracket alone resolves ONLY the child, never also the parent
        assert scan_payload_ids("引用 [NFD01.economic_linkage] 支撑", reg) \
            == {"NFD01.economic_linkage"}
        # both bracketed tokens present -> both found
        assert scan_payload_ids("[NFD01] 与 [NFD01.economic_linkage]", reg) \
            == {"NFD01", "NFD01.economic_linkage"}
        # a bracketed parent is the parent
        assert scan_payload_ids("see [NFD01].", reg) == {"NFD01"}
        # BARE (unbracketed) ids are NOT references — content can't forge one
        assert scan_payload_ids("产能 H1 2025 展望", reg) == set()


class TestTypedSchemaLocks:
    # re-review#3 B1: "correctly shaped" generic mints of protected records refused
    def test_mf_external_shock_needs_derived_macro_type(self):
        # your probe: MF01/MFD minted directly into external_shock_transmission
        # WITHOUT macro_type=external_shock — refused (dim must be DERIVED)
        with pytest.raises(RegistryError, match="派生|mf_v1"):
            build_card_record("MF01", domain="macro", evidence_class="MFD",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"macro"},
                              allowed_dimensions={"external_shock_transmission"},
                              record_schema_id="mf_v1",
                              derivation=(("derivation_version", "mf_dim_v1"),
                                          ("macro_type", "地缘外围")))

    def test_mf_generic_schema_refused(self):
        with pytest.raises(RegistryError, match="mf_v1"):
            build_card_record("MF01", domain="macro", evidence_class="MFD",
                              allowed_uses={"context_only"}, allowed_consumers={"macro"},
                              record_schema_id="generic_v1")

    def test_d7_child_generic_mint_refused(self):
        # your probe: NFI01.fact minted with class NFD via the generic path
        with pytest.raises(RegistryError, match="d7_child_v2"):
            build_card_record("NFI01.fact", domain="news", evidence_class="NFD",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"news"},
                              allowed_dimensions={"event_materiality"})

    def test_d7_child_class_laundering_caught_at_registry(self):
        # typed child claiming NFD alongside its NFI parent -> registry refuses
        parent = _nfi("NFI01")
        child = _d7_child(parent, attr="fact", evidence_class="NFD")
        with pytest.raises(RegistryError, match="洗类"):
            build_card_registry(CUT, [parent, child])

    # re-review#4 B1: D7 child cannot bind the wrong parent or widen the seat
    def test_d7_child_wrong_parent_hash_refused(self):
        # NFD01.fact sealing NFD02's hash -> registry refuses (registry_parent
        # hash != the ID-prefix parent's actual hash)
        p1, p2 = _nfd("NFD01"), _nfd("NFD02")
        child = _d7_child(p1, attr="fact", registry_parent_content_hash=p2.content_hash)
        with pytest.raises(RegistryError, match="错父"):
            build_card_registry(CUT, [p1, p2, child])

    def test_d7_child_cross_seat_widening_refused(self):
        # domain=macro / consumer=macro child -> kernel refuses at construction
        from workspace.research.ai_research_dept.engine.news_evidence import ATTRIBUTE_DIMENSIONS
        with pytest.raises(RegistryError, match="domain 须恰为 news"):
            build_card_record("NFD01.fact", domain="macro", evidence_class="NFD",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"macro"},
                              allowed_dimensions=ATTRIBUTE_DIMENSIONS["fact"],
                              record_schema_id="d7_child_v2",
                              derivation=(("source_parent_content_hash", "a" * 64),
                                          ("registry_parent_content_hash", "b" * 64),
                                          ("attribute_type", "fact")))

    def test_d7_child_wrong_consumer_refused(self):
        from workspace.research.ai_research_dept.engine.news_evidence import ATTRIBUTE_DIMENSIONS
        with pytest.raises(RegistryError, match="consumers 须恰"):
            build_card_record("NFD01.fact", domain="news", evidence_class="NFD",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"news", "bear"},   # fact must be {news}
                              allowed_dimensions=ATTRIBUTE_DIMENSIONS["fact"],
                              record_schema_id="d7_child_v2",
                              derivation=(("source_parent_content_hash", "a" * 64),
                                          ("registry_parent_content_hash", "b" * 64),
                                          ("attribute_type", "fact")))

    # re-review#4 Major: derivation tuples are mechanically singular
    def test_duplicate_derivation_key_refused(self):
        with pytest.raises(RegistryError, match="重复"):
            build_card_record("MF01", domain="macro", evidence_class="MFD",
                              allowed_uses={"context_only"}, allowed_consumers={"macro"},
                              record_schema_id="mf_v1",
                              derivation=(("derivation_version", "mf_dim_v1"),
                                          ("macro_type", "货币政策"),
                                          ("macro_type", "地缘外围")))

    def test_surplus_derivation_key_refused(self):
        with pytest.raises(RegistryError, match="恰为"):
            build_card_record("MF01", domain="macro", evidence_class="MFD",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"macro"},
                              allowed_dimensions={"policy_alignment"},
                              record_schema_id="mf_v1",
                              derivation=(("derivation_version", "mf_dim_v1"),
                                          ("macro_type", "货币政策"),
                                          ("provenance", "FORGED")))

    def test_m_line_nonempty_derivation_refused(self):
        with pytest.raises(RegistryError, match="恰为"):
            build_card_record("M01", domain="macro", evidence_class="market_state_fact",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"macro"},
                              allowed_dimensions={"risk_appetite_environment_fit"},
                              record_schema_id="m_line_v1",
                              derivation=(("provenance", "x"),))

    def test_d7_orphan_child_refused_at_registry(self):
        parent = _nfd("NFD01")
        child = _d7_child(parent, attr="fact")
        with pytest.raises(RegistryError, match="孤儿"):
            build_card_registry(CUT, [child])          # parent absent

    @pytest.mark.parametrize("rid", ["M17", "MS01", "M01.fact", "MKT01"])
    def test_complete_m_namespace_reserved(self, rid):
        # your probe: M17 / future MS01 / M01.fact minted as positive news/NFD
        with pytest.raises(RegistryError, match="保留"):
            build_card_record(rid, domain="news", evidence_class="NFD",
                              allowed_uses={"factor_positive"},
                              allowed_consumers={"news"},
                              allowed_dimensions={"event_materiality"})

    def test_generic_schema_on_unprotected_only(self):
        # schema<->namespace bidirectional: a typed schema on a plain id refused
        # (m_line_v1 has empty derivation so it passes the derivation check and
        # reaches the namespace<->schema binding)
        with pytest.raises(RegistryError, match="generic_v1"):
            build_card_record("NFD01", domain="news", evidence_class="NFD",
                              allowed_uses={"context_only"}, allowed_consumers={"news"},
                              record_schema_id="m_line_v1")

    def test_direct_dataclass_construction_also_locked(self):
        # enforcement lives in __post_init__ — direct construction can't bypass
        with pytest.raises(RegistryError, match="保留"):
            CardRecord(record_id="M17", domain="news", evidence_class="NFD",
                       allowed_uses=frozenset({"factor_positive"}),
                       allowed_consumers=frozenset({"news"}),
                       allowed_dimensions=frozenset({"event_materiality"}))


class TestRequireSealedRegistry:
    # re-review#3 B2: duck-typed registry lookalikes refused at EVERY consumer
    def _fake(self):
        real = build_card_registry(CUT, [_nfd("NFD01")])

        class _Fake:
            registry_hash = real.registry_hash
            records = dict(real.records)
        return _Fake()

    def test_scan_refuses_fake(self):
        from workspace.research.ai_research_dept.engine.news_evidence import scan_payload_ids
        with pytest.raises(RegistryError, match="SealedCardRegistry"):
            scan_payload_ids("NFD01", self._fake())

    def test_assert_factor_payload_refuses_fake(self):
        with pytest.raises(RegistryError, match="SealedCardRegistry"):
            assert_factor_payload("NFD01", self._fake(), consumer_seat="news",
                                  target_dimension="event_materiality")

    def test_build_factor_payload_ids_refuses_fake(self):
        with pytest.raises(RegistryError, match="SealedCardRegistry"):
            build_factor_payload_ids(self._fake(), consumer_seat="news",
                                     target_dimension="event_materiality")

    def test_dimension_ceiling_refuses_fake(self):
        with pytest.raises(RegistryError, match="SealedCardRegistry"):
            dimension_ceiling(["NFD01"], self._fake(), consumer_seat="news",
                              target_dimension="event_materiality")


# --------------------------------------------------- sealed registry

class TestRegistry:
    def test_hash_and_order_independent(self):
        a = build_card_registry(CUT, [_nfd(), _attention(), _macro()])
        b = build_card_registry(CUT, [_macro(), _attention(), _nfd()])
        assert len(a.registry_hash) == 64 and a.registry_hash == b.registry_hash

    def test_duplicate_id_rejected(self):
        with pytest.raises(RegistryError, match="重复 record_id"):
            build_card_registry(CUT, [_nfd(), _nfd()])

    def test_deep_readonly(self):
        reg = build_card_registry(CUT, [_nfd()])
        with pytest.raises(TypeError):
            reg.records["EVIL"] = _nfd("EVIL")

    def test_forged_registry_hash_rejected(self):
        reg = build_card_registry(CUT, [_nfd()])
        with pytest.raises(SealError):
            SealedCardRegistry(cutoff_iso=CUT, records=reg.records, registry_hash="0" * 64)


# --------------------------------------------------- ternary authorization

class TestAuthorize:
    def test_factor_positive_full_triple(self):
        r = _nfd()
        assert authorize(r, use="factor_positive", consumer_seat="news",
                         target_dimension="event_materiality") is True

    def test_wrong_seat_denied(self):
        assert authorize(_nfd(), use="factor_positive", consumer_seat="macro",
                         target_dimension="event_materiality") is False

    def test_wrong_dimension_denied(self):
        assert authorize(_nfd(), use="factor_positive", consumer_seat="news",
                         target_dimension="novelty") is False

    def test_factor_positive_without_dimension_denied(self):
        assert authorize(_nfd(), use="factor_positive", consumer_seat="news") is False

    def test_metadata_not_id_prefix(self):
        # an attention record authorizes bear but NEVER factor_positive — decided by
        # metadata, not the id string
        att = _attention()
        assert authorize(att, use="bear", consumer_seat="bear") is True
        assert authorize(att, use="factor_positive", consumer_seat="bear",
                         target_dimension="event_materiality") is False


# --------------------------------------------------- ceiling arithmetic

class TestCeiling:
    def test_strongest_class_wins(self):
        reg = build_card_registry(CUT, [_nfi("NFI01"), _nfd("NFD01")])
        assert dimension_ceiling(["NFI01", "NFD01"], reg, consumer_seat="news",
                                 target_dimension="event_materiality") == 5

    def test_indirect_and_aggregate_cap_3(self):
        reg = build_card_registry(CUT, [_nfi("NFI01")])
        assert dimension_ceiling(["NFI01"], reg, consumer_seat="news",
                                 target_dimension="event_materiality") == 3

    def test_only_attention_or_unregistered_is_zero(self):
        reg = build_card_registry(CUT, [_attention("N00")])
        assert dimension_ceiling(["N00", "UNREG99"], reg, consumer_seat="news",
                                 target_dimension="event_materiality") == 0

    def test_wrong_dimension_does_not_lift(self):
        reg = build_card_registry(CUT, [_nfd("NFD01", dim="event_materiality")])
        # cited toward a dimension the record isn't scoped to -> no ceiling
        assert dimension_ceiling(["NFD01"], reg, consumer_seat="news",
                                 target_dimension="novelty") == 0


# --------------------------------------------------- the load-bearing factor-payload gate

class TestFactorPayloadGate:
    def _reg(self):
        return build_card_registry(CUT, [_nfd("NFD01"), _attention("N00"),
                                         _coordination("NFC01")])

    def test_clean_factor_payload_passes(self):
        payload = {"news_card": {"facts": [{"id": "[NFD01]", "text": "签订大额订单"}]}}
        got = assert_factor_payload(payload, self._reg(), consumer_seat="news",
                                    target_dimension="event_materiality")
        assert got == {"NFD01"}

    def test_attention_id_in_factor_payload_hard_fails(self):
        # N00 (attention_only) smuggled into a nested/aliased factor field -> HARD FAIL
        payload = {"news_card": {"context_note": "参见 [N00] 热度"}}
        with pytest.raises(PayloadGateError, match="N00"):
            assert_factor_payload(payload, self._reg(), consumer_seat="news",
                                  target_dimension="event_materiality")

    def test_coordination_id_in_factor_payload_hard_fails(self):
        payload = {"facts": ["[NFC01] 协同转载"]}
        with pytest.raises(PayloadGateError, match="NFC01"):
            assert_factor_payload(payload, self._reg(), consumer_seat="news",
                                  target_dimension="event_materiality")

    def test_wrong_seat_for_registered_id_hard_fails(self):
        # NFD01 is authorized for news, not fund -> a fund factor payload citing it fails
        payload = {"fund_card": {"note": "[NFD01]"}}
        with pytest.raises(PayloadGateError, match="NFD01"):
            assert_factor_payload(payload, self._reg(), consumer_seat="fund",
                                  target_dimension="event_materiality")

    def test_unregistered_id_hard_fails(self):
        # re-review#4 B2: a FABRICATED [NFD99] must hard-fail, not return empty
        with pytest.raises(PayloadGateError, match="未注册"):
            assert_factor_payload({"news_card": "[NFD99] 伪造事实"}, self._reg(),
                                  consumer_seat="news",
                                  target_dimension="event_materiality")

    def test_unregistered_d7_child_not_read_as_parent(self):
        # re-review#4 B2: [NFD01.fact] with only NFD01 registered must NOT be
        # misread as the authorized parent — it is an unknown id -> hard fail
        with pytest.raises(PayloadGateError, match="未注册"):
            assert_factor_payload({"news_card": {"note": "[NFD01.fact]"}}, self._reg(),
                                  consumer_seat="news",
                                  target_dimension="event_materiality")

    def test_word_boundary_no_false_prefix_match(self):
        reg = build_card_registry(CUT, [_macro("M01"),
                                        build_card_record("M16", domain="macro",
                                                          evidence_class="market_state_fact",
                                                          allowed_uses={"context_only"},
                                                          allowed_consumers={"macro"},
                                                          record_schema_id="m_line_v1")])
        # a payload mentioning [M16] (context_only) must flag M16, NOT falsely match M01
        with pytest.raises(PayloadGateError, match="M16"):
            assert_factor_payload({"macro_card": "环境 [M16] 综合"}, reg,
                                  consumer_seat="macro",
                                  target_dimension="risk_appetite_environment_fit")
        # and a clean [M01] payload passes without M16 false-positive
        assert assert_factor_payload({"macro_card": "[M01] 风险偏好"}, reg,
                                     consumer_seat="macro",
                                     target_dimension="risk_appetite_environment_fit") == {"M01"}

    def test_metadata_bracket_not_a_reference(self):
        # the render metadata bracket [age|stars|NFD] contains pipes -> not a
        # reference; its bare class label NFD is never extracted (no false unknown)
        reg = self._reg()
        got = assert_factor_payload("- [NFD01][2.0h|★★★|NFD]订单|正文", reg,
                                    consumer_seat="news",
                                    target_dimension="event_materiality")
        assert got == {"NFD01"}

    def test_build_from_registry_allowlist(self):
        reg = self._reg()
        ids = build_factor_payload_ids(reg, consumer_seat="news",
                                       target_dimension="event_materiality")
        assert ids == ["NFD01"]              # only the factor_positive-authorized id
