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
    # M01-M16 是冻结保留 ID(re-review Major-3)——mint 必须与权威表逐字一致
    return build_card_record(rid, domain="macro", evidence_class="market_state_fact",
                             allowed_uses={"factor_positive", "context_only"},
                             allowed_consumers={"macro"},
                             allowed_dimensions={"risk_appetite_environment_fit"})


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
            build_card_record("X", domain="news", evidence_class="HYPE",
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


class TestHierarchicalIdScan:
    # re-review Major-2: one token resolves to exactly ONE record (longest-first)
    def test_d7_child_does_not_double_resolve_parent(self):
        from workspace.research.ai_research_dept.engine.news_evidence import scan_payload_ids
        parent = _nfd("NFD01")
        child = build_card_record("NFD01.economic_linkage", domain="news",
                                  evidence_class="NFD",
                                  allowed_uses={"factor_positive"},
                                  allowed_consumers={"news"},
                                  allowed_dimensions={"fundamental_link"})
        reg = build_card_registry(CUT, [parent, child])
        # the child token alone must resolve ONLY the child, never also the parent
        assert scan_payload_ids("引用 NFD01.economic_linkage 支撑", reg) \
            == {"NFD01.economic_linkage"}
        # both tokens present -> both found
        assert scan_payload_ids("NFD01 与 NFD01.economic_linkage", reg) \
            == {"NFD01", "NFD01.economic_linkage"}
        # parent followed by a period (sentence end) is still the parent
        assert scan_payload_ids("see NFD01.", reg) == {"NFD01"}


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
        payload = {"news_card": {"facts": [{"id": "NFD01", "text": "签订大额订单"}]}}
        got = assert_factor_payload(payload, self._reg(), consumer_seat="news",
                                    target_dimension="event_materiality")
        assert got == {"NFD01"}

    def test_attention_id_in_factor_payload_hard_fails(self):
        # N00 (attention_only) smuggled into a nested/aliased factor field -> HARD FAIL
        payload = {"news_card": {"context_note": "参见 N00 热度"}}
        with pytest.raises(PayloadGateError, match="N00"):
            assert_factor_payload(payload, self._reg(), consumer_seat="news",
                                  target_dimension="event_materiality")

    def test_coordination_id_in_factor_payload_hard_fails(self):
        payload = {"facts": ["NFC01 协同转载"]}
        with pytest.raises(PayloadGateError, match="NFC01"):
            assert_factor_payload(payload, self._reg(), consumer_seat="news",
                                  target_dimension="event_materiality")

    def test_wrong_seat_for_registered_id_hard_fails(self):
        # NFD01 is authorized for news, not fund -> a fund factor payload citing it fails
        payload = {"fund_card": {"note": "NFD01"}}
        with pytest.raises(PayloadGateError, match="NFD01"):
            assert_factor_payload(payload, self._reg(), consumer_seat="fund",
                                  target_dimension="event_materiality")

    def test_word_boundary_no_false_prefix_match(self):
        reg = build_card_registry(CUT, [_macro("M01"),
                                        build_card_record("M16", domain="macro",
                                                          evidence_class="market_state_fact",
                                                          allowed_uses={"context_only"},
                                                          allowed_consumers={"macro"})])
        # a payload mentioning M16 (context_only) must flag M16, NOT falsely match M01
        with pytest.raises(PayloadGateError, match="M16"):
            assert_factor_payload({"macro_card": "环境 M16 综合"}, reg,
                                  consumer_seat="macro",
                                  target_dimension="risk_appetite_environment_fit")
        # and a clean M01 payload passes without M16 false-positive
        assert assert_factor_payload({"macro_card": "M01 风险偏好"}, reg,
                                     consumer_seat="macro",
                                     target_dimension="risk_appetite_environment_fit") == {"M01"}

    def test_build_from_registry_allowlist(self):
        reg = self._reg()
        ids = build_factor_payload_ids(reg, consumer_seat="news",
                                       target_dimension="event_materiality")
        assert ids == ["NFD01"]              # only the factor_positive-authorized id
