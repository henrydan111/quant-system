# NF §7 step 5: two-card flash renderer (evidence fence + leg slices + D7 + sealing).
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_cards import (  # noqa: E402
    AttributeRow, D7BaseFact, RenderedCard, _build_attribute_records, assess_flash,
    assign_evidence_class, build_attribute_bundle, is_legacy_attention_id,
    render_attention_context_card, render_news_flash_section, verify_bundle_registry,
)
from workspace.research.ai_research_dept.engine.news_evidence import (  # noqa: E402
    PayloadGateError, RegistryError, assert_factor_payload, authorize,
    build_card_registry,
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


def _typing(status="官方证实", kind="事实", rumor=False, importance=3,
            event_type="订单合同", direction="利好"):
    return {"event_type": event_type, "verification_status": status,
            "content_kind": kind, "direction": direction,
            "importance": importance, "is_rumor": rumor}


def _route(primary="stock", content=None):
    r = {"primary_route": primary, "subject_codes": ["688981.SH"],
         "industry_tags": [], "concept_tags": []}
    if content is not None:
        r["content"] = content
    return r


def _assessed(content, *, status="官方证实", kind="事实", rumor=False, importance=3,
              primary="stock", coordination=False, dt="2025-01-27 10:00:00"):
    return assess_flash(_cluster(content, dt), _typing(status=status, kind=kind,
                                                       rumor=rumor, importance=importance),
                        _route(primary, content=content),
                        coordination_fired=coordination)


# --------------------------------------------------- evidence fence (§2 step 5+7)

class TestEvidenceFence:
    @pytest.mark.parametrize("status,kind,rumor,route,expect", [
        ("官方证实", "事实", False, "stock", "NFD"),
        ("署名媒体", "事实", False, "stock", "NFI"),
        ("官方证实", "事实", False, "industry_concept", "NFA"),
        ("署名媒体", "事实", False, "industry_concept", "NFA"),
        ("官方证实", "事实", False, "macro", "MFD"),
        ("署名媒体", "事实", False, "macro", "MFI"),
        # rumor/manipulation -> R-class regardless of route
        ("官方证实", "事实", True, "stock", "NFR"),
        ("传闻", "事实", False, "stock", "NFR"),
        ("署名媒体", "推广", False, "stock", "NFR"),
        ("传闻", "事实", False, "macro", "MFR"),
        # informational-but-unscorable -> news_context (fail-closed, never positive)
        ("未证实", "事实", False, "stock", "news_context"),
        ("观点", "事实", False, "stock", "news_context"),
        ("官方证实", "行情", False, "stock", "news_context"),
        ("官方证实", "评论", False, "stock", "news_context"),
    ])
    def test_matrix(self, status, kind, rumor, route, expect):
        assert assign_evidence_class(
            {"verification_status": status, "content_kind": kind, "is_rumor": rumor},
            route) == expect

    def test_syndication_does_not_clear_rumor(self):
        # §2 step 4: the rumor flag is NOT cleared by reposting — the fence never
        # consults n_outlets, so a widely-syndicated rumor stays NFR
        assert assign_evidence_class(
            {"verification_status": "传闻", "content_kind": "事实", "is_rumor": True},
            "stock") == "NFR"

    # re-review Major-1: the fence is INDEPENDENTLY fail-closed (no type_batch help)
    def test_unknown_route_never_defaults_positive(self):
        with pytest.raises(RegistryError, match="primary_route"):
            assign_evidence_class(
                {"verification_status": "官方证实", "content_kind": "事实",
                 "is_rumor": False}, "stok")            # typo'd route

    def test_malformed_status_never_defaults_positive(self):
        with pytest.raises(RegistryError, match="verification_status"):
            assign_evidence_class(
                {"verification_status": "hacked", "content_kind": "事实",
                 "is_rumor": False}, "stock")

    def test_malformed_kind_rejected(self):
        with pytest.raises(RegistryError, match="content_kind"):
            assign_evidence_class(
                {"verification_status": "官方证实", "content_kind": "?",
                 "is_rumor": False}, "stock")

    def test_non_bool_rumor_rejected(self):
        with pytest.raises(RegistryError, match="is_rumor"):
            assign_evidence_class(
                {"verification_status": "官方证实", "content_kind": "事实",
                 "is_rumor": "false"}, "stock")

    def test_assess_flash_validates_display_fields(self):
        with pytest.raises(RegistryError, match="event_type"):
            assess_flash(_cluster("x"), _typing(event_type="EVIL"), _route("stock"))
        with pytest.raises(RegistryError, match="importance"):
            assess_flash(_cluster("x"), _typing(importance="5"), _route("stock"))


# --------------------------------------------------- positive section + leg slices

class TestFlashSection:
    def test_factor_slice_only_positive_classes(self):
        card, records, _ = render_news_flash_section([
            _assessed("中芯国际签订大额订单", status="官方证实"),
            _assessed("媒体报道产能爬坡", status="署名媒体", dt="2025-01-27 09:00:00"),
            _assessed("传闻公司将重组", status="传闻", rumor=True, dt="2025-01-27 08:00:00"),
            _assessed("盘面异动直线拉升", kind="行情", dt="2025-01-27 07:00:00"),
        ], CUT)
        assert "NFD01" in card.factor_payload_text
        assert "NFI01" in card.factor_payload_text
        # risk + context are physically in the restricted slice, not the factor slice
        assert "NFR" not in card.factor_payload_text
        assert "NFU" not in card.factor_payload_text
        assert "NFR01" in card.restricted_text and "NFU01" in card.restricted_text

    def test_factor_slice_passes_gate_risk_slice_fails(self):
        card, records, _ = render_news_flash_section([
            _assessed("签订订单", status="官方证实"),
            _assessed("传闻重组", status="传闻", rumor=True, dt="2025-01-27 08:00:00"),
        ], CUT)
        reg = build_card_registry(card.cutoff_iso, records)
        # the factor slice is safe for the factor leg
        assert assert_factor_payload(card.factor_payload_text, reg,
                                     consumer_seat="news",
                                     target_dimension="event_materiality") == {"NFD01"}
        # feeding the restricted slice to the factor leg hard-fails (metadata filter)
        with pytest.raises(PayloadGateError, match="NFR01"):
            assert_factor_payload(card.restricted_text, reg, consumer_seat="news",
                                  target_dimension="event_materiality")

    def test_no_aggregate_count_lines_in_factor_slice(self):
        # B1′: zero aggregate/count rows — no 全景/聚合/条 counting language
        card, _, _ = render_news_flash_section(
            [_assessed(f"事件{i}", importance=i % 5) for i in range(1, 6)], CUT)
        for banned in ("全景", "聚合", "另有"):
            assert banned not in card.factor_payload_text

    def test_dedup_by_fact_occurrence(self):
        # same wording (same fact id) assessed twice -> ONE row
        a1 = _assessed("重复事实文", status="官方证实")
        a2 = _assessed("重复事实文", status="官方证实")
        card, records, _ = render_news_flash_section([a1, a2], CUT)
        assert card.factor_payload_text.count("重复事实文") == 1

    def test_conflicting_fact_assessments_hard_fail(self):
        # re-review BLOCKER: NFD imp=5 + NFR imp=1 on the SAME fact must never let
        # importance pick the class (the rumor flag was silently erased before)
        good = _assessed("同一事实文", status="官方证实", importance=5)
        rumor = _assessed("同一事实文", status="传闻", rumor=True, importance=1)
        with pytest.raises(RegistryError, match="冲突评定"):
            render_news_flash_section([good, rumor], CUT)

    def test_conflicting_direction_hard_fails(self):
        # identity covers direction too — same fact typed 利好 and 利空 = conflict
        a1 = _assessed("同事实方向冲突", status="官方证实")
        a2 = assess_flash(_cluster("同事实方向冲突"),
                          _typing(status="官方证实", direction="利空"),
                          _route("stock", content="同事实方向冲突"))
        with pytest.raises(RegistryError, match="冲突评定"):
            render_news_flash_section([a1, a2], CUT)

    def test_coordination_ored_across_group(self):
        # re-review BLOCKER: metadata-identical duplicates, coordination on the
        # LOW-importance one -> merged row + NFC still emitted (OR, never erased)
        plain = _assessed("同事实协同", status="官方证实", importance=5)
        flagged = _assessed("同事实协同", status="官方证实", importance=1,
                            coordination=True)
        card, records, _ = render_news_flash_section([plain, flagged], CUT)
        assert card.factor_payload_text.count("同事实协同") == 1
        assert "NFC01" in card.restricted_text          # the safety flag survives
        # merged importance = max(5, 1) -> 5 stars on the fact line
        assert "★★★★★" in card.factor_payload_text

    def test_deterministic_order_and_numbering(self):
        items = [_assessed("低重要", importance=1, dt="2025-01-27 09:00:00"),
                 _assessed("高重要", importance=5, dt="2025-01-27 08:00:00"),
                 _assessed("中重要", importance=3, dt="2025-01-27 10:00:00")]
        c1, _, _ = render_news_flash_section(items, CUT)
        c2, _, _ = render_news_flash_section(items[::-1], CUT)
        assert c1.factor_payload_text == c2.factor_payload_text     # permutation-stable
        # importance-descending: 高重要 gets NFD01
        first = c1.factor_payload_text.splitlines()[1]
        assert "NFD01" in first and "高重要" in first

    def test_coordination_emits_nfc_record(self):
        card, records, _ = render_news_flash_section(
            [_assessed("拉升在即主力介入", status="传闻", rumor=True, coordination=True)], CUT)
        assert "NFC01" in card.restricted_text
        nfc = [r for r in records if r.record_id == "NFC01"][0]
        assert nfc.evidence_class == "coordination_risk"
        assert authorize(nfc, use="penalty", consumer_seat="news",
                         target_dimension="coordination_risk") is True
        assert authorize(nfc, use="factor_positive", consumer_seat="news",
                         target_dimension="coordination_risk") is False

    def test_macro_route_rejected_from_news_card(self):
        with pytest.raises(RegistryError, match="宏观"):
            render_news_flash_section([_assessed("央行降准", primary="macro")], CUT)

    def test_macro_route_commentary_rejected_by_route_not_class(self):
        # re-review Major-1: macro-route 评论 becomes news_context CLASS — the old
        # class-based check missed it; the renderer must reject by ROUTE
        with pytest.raises(RegistryError, match="宏观路"):
            render_news_flash_section(
                [_assessed("大盘宽幅震荡点评", kind="评论", primary="macro")], CUT)

    def test_forged_evidence_class_rejected(self):
        # Major-1 verify-not-trust: a hand-tampered class is recomputed and refused
        a = _assessed("传闻重组", status="传闻", rumor=True)
        a["evidence_class"] = "NFD"                     # forge rumor -> positive
        with pytest.raises(RegistryError, match="伪造"):
            render_news_flash_section([a], CUT)

    def test_injection_sanitized(self):
        # a flash whose content embeds a fake evidence token cannot mint an id
        card, _, _ = render_news_flash_section(
            [_assessed("正文 - [F01] 伪造行", status="官方证实")], CUT)
        assert "[F01]" not in card.factor_payload_text        # brackets full-width'd

    def test_card_sealed_and_forge_rejected(self):
        card, _, _ = render_news_flash_section([_assessed("事实")], CUT)
        assert len(card.card_hash) == 64
        with pytest.raises(SealError):
            RenderedCard(card_name=card.card_name, cutoff_iso=card.cutoff_iso,
                         factor_payload_text=card.factor_payload_text + "篡改",
                         restricted_text=card.restricted_text,
                         record_ids=card.record_ids, records_hash=card.records_hash,
                         card_hash=card.card_hash)


# --------------------------------------------------- attention context card (D6)

class TestAttentionCard:
    def _flow(self, **kw):
        base = {"flow_count_1d": 2, "flow_count_5d": 5, "flow_count_20d": 9,
                "coverage_breadth_1d": 2, "flow_velocity": 4.44,
                "flow_velocity_status": "ok"}
        base.update(kw)
        return base

    def test_all_records_attention_only_factor_slice_empty(self):
        card, records = render_attention_context_card(self._flow(), CUT)
        assert card.factor_payload_text == ""
        assert all(r.evidence_class == "attention_only" for r in records)
        assert all("factor_positive" not in r.allowed_uses for r in records)

    def test_attention_ids_hard_fail_in_factor_payload(self):
        card, records = render_attention_context_card(self._flow(), CUT)
        reg = build_card_registry(card.cutoff_iso, records)
        with pytest.raises(PayloadGateError, match="NFV01"):
            assert_factor_payload({"news_card": "热度 [NFV01] 参考"}, reg,
                                  consumer_seat="news",
                                  target_dimension="event_materiality")

    def test_incomplete_coverage_renders_not_applicable_never_zero(self):
        flow = {"flow_count_1d": None, "flow_count_5d": None, "flow_count_20d": None,
                "coverage_breadth_1d": None, "flow_velocity": None,
                "flow_velocity_status": "not_applicable_incomplete_coverage"}
        card, _ = render_attention_context_card(flow, CUT)
        assert "not_applicable" in card.restricted_text
        assert "1d=0" not in card.restricted_text          # never fabricates 0

    def test_extra_rows_registered_attention_only(self):
        card, records = render_attention_context_card(
            self._flow(), CUT, extra_rows=(("N00", "检索全景: 直接 3 条,间接 5 条"),))
        assert "N00" in card.restricted_text
        n00 = [r for r in records if r.record_id == "N00"][0]
        assert n00.evidence_class == "attention_only"

    def test_duplicate_extra_row_id_rejected(self):
        # re-review Major-2: extra_rows colliding with NFV01 must not seal
        with pytest.raises(RegistryError, match="重复 record_id"):
            render_attention_context_card(
                self._flow(), CUT, extra_rows=(("NFV01", "撞号行"),))


# --------------------------------------------------- D7 attribute rows

class TestD7Attributes:
    def _attrs(self):
        return {"fact": "签订 12 亿元订单", "economic_linkage": "对应年营收 15%",
                "timing": "下季度交付", "source_status": "公司公告官方证实"}

    def test_scoped_dimensions(self):
        rows = _build_attribute_records("NFD01", claim_id="c1", fact_cluster_id="f1",
                                       evidence_class="NFD", importance=5,
                                       source_parent_content_hash="a" * 64,
                                       registry_parent_content_hash="b" * 64, attributes=self._attrs())
        by_attr = {r.attribute_type: (r, rec) for r, rec in rows}
        _, fact_rec = by_attr["fact"]
        # fact row authorizes ONLY event_materiality
        assert authorize(fact_rec, use="factor_positive", consumer_seat="news",
                         target_dimension="event_materiality") is True
        assert authorize(fact_rec, use="factor_positive", consumer_seat="news",
                         target_dimension="fundamental_link") is False
        _, link_rec = by_attr["economic_linkage"]
        assert authorize(link_rec, use="factor_positive", consumer_seat="news",
                         target_dimension="fundamental_link") is True

    def test_source_status_never_positive(self):
        rows = _build_attribute_records("NFD01", claim_id="c1", fact_cluster_id="f1",
                                       evidence_class="NFD", importance=4,
                                       source_parent_content_hash="a" * 64,
                                       registry_parent_content_hash="b" * 64, attributes={"source_status": "官方证实"})
        _, rec = rows[0]
        assert "factor_positive" not in rec.allowed_uses
        assert authorize(rec, use="penalty", consumer_seat="news",
                         target_dimension="confidence_cap") is True

    def test_small_event_not_split(self):
        with pytest.raises(RegistryError, match="importance"):
            _build_attribute_records("NFD01", claim_id="c1", fact_cluster_id="f1",
                                    evidence_class="NFD", importance=3,
                                    source_parent_content_hash="a" * 64,
                                       registry_parent_content_hash="b" * 64, attributes={"fact": "小事件"})

    def test_unknown_attribute_rejected(self):
        with pytest.raises(RegistryError, match="未注册 attribute_type"):
            _build_attribute_records("NFD01", claim_id="c1", fact_cluster_id="f1",
                                    evidence_class="NFD", importance=5,
                                    source_parent_content_hash="a" * 64,
                                       registry_parent_content_hash="b" * 64, attributes={"hype": "x"})

    def test_rumor_class_not_splittable(self):
        with pytest.raises(RegistryError, match="正向类"):
            _build_attribute_records("NFR01", claim_id="c1", fact_cluster_id="f1",
                                    evidence_class="NFR", importance=5,
                                    source_parent_content_hash="a" * 64,
                                       registry_parent_content_hash="b" * 64, attributes={"fact": "x"})

    def test_row_sealed_and_forged_rejected(self):
        rows = _build_attribute_records("NFD01", claim_id="c1", fact_cluster_id="f1",
                                       evidence_class="NFD", importance=5,
                                       source_parent_content_hash="a" * 64,
                                       registry_parent_content_hash="b" * 64, attributes={"fact": "x"})
        row, _ = rows[0]
        assert len(row.row_hash) == 64
        with pytest.raises(SealError):
            AttributeRow(row_id=row.row_id, claim_id="EVIL", fact_cluster_id="f1",
                         evidence_group_id=row.evidence_group_id,
                         attribute_type="fact", text=row.text, row_hash=row.row_hash)


# --------------------------------------------------- D7 batch bundle (Major-4)

class TestAttributeBundle:
    def _rendered(self):
        # 重大订单甲 imp=5 (NFD01), 署名乙 imp=4 (NFI01), 小事件丙 imp=3 (NFD02)
        return render_news_flash_section(
            [_assessed("重大订单甲", status="官方证实", importance=5),
             _assessed("媒体乙报道", status="署名媒体", importance=4,
                       dt="2025-01-27 09:00:00"),
             _assessed("小事件丙", status="官方证实", importance=3,
                       dt="2025-01-27 08:00:00")], CUT)

    def _split(self, base_id):
        # re-review#2 B1: a split carries ONLY the base reference + attributes
        return {"base_record_id": base_id,
                "attributes": {"fact": "签订 12 亿订单", "economic_linkage": "年营收 15%"}}

    def test_base_demoted_attributes_positive(self):
        card, records, facts = self._rendered()
        art = build_attribute_bundle(
            [self._split("NFD01")], facts, records, card=card,
            decision_id="d1", cutoff=CUT)
        bundle, rows, final_reg = art.bundle, art.rows, art.final_registry
        by_id = dict(final_reg.records)
        # the split event's broad base row can no longer score positively...
        assert authorize(by_id["NFD01"], use="factor_positive", consumer_seat="news",
                         target_dimension="event_materiality") is False
        # ...its scoped attribute rows can (each only toward its own dimension)
        assert authorize(by_id["NFD01.fact"], use="factor_positive",
                         consumer_seat="news",
                         target_dimension="event_materiality") is True
        # untouched sibling stays positive
        assert authorize(by_id["NFD02"], use="factor_positive", consumer_seat="news",
                         target_dimension="event_materiality") is True
        # downstream consumption point: registry must match the sealed bundle
        verify_bundle_registry(bundle, final_reg)

    def test_caller_supplied_class_or_importance_rejected(self):
        # re-review#2 B1: the laundering probe — extra authority keys are refused
        card, records, facts = self._rendered()
        forged = {"base_record_id": "NFI01", "evidence_class": "NFD",
                  "attributes": {"fact": "x"}}
        with pytest.raises(RegistryError, match="只许"):
            build_attribute_bundle([forged], facts, records, card=card,
                                   decision_id="d1", cutoff=CUT)

    def test_class_and_floor_derived_from_sealed_base(self):
        # NFI01 splits as NFI (children ceiling 3, not 5); imp-3 NFD02 fails the floor
        card, records, facts = self._rendered()
        art = build_attribute_bundle(
            [self._split("NFI01")], facts, records, card=card,
            decision_id="d1", cutoff=CUT)
        bundle, final_reg = art.bundle, art.final_registry
        child = dict(final_reg.records)["NFI01.fact"]
        assert child.evidence_class == "NFI" and child.positive_ceiling == 3
        with pytest.raises(RegistryError, match="importance"):
            build_attribute_bundle([self._split("NFD02")], facts, records,
                                   card=card, decision_id="d1", cutoff=CUT)

    def test_self_minted_descriptor_rejected(self):
        # a self-consistent D7BaseFact NOT minted by the renderer (importance
        # upgraded to 5), swapped into the population, fails the EXACT-population
        # equality check (re-review#3 M1: not membership-only)
        card, records, facts = self._rendered()
        base = [r for r in records if r.record_id == "NFD02"][0]
        forged = D7BaseFact(base_record_id="NFD02", base_content_hash=base.content_hash,
                            claim_id="CLAIM:forged", fact_cluster_id="f",
                            evidence_class="NFD", importance=5)
        swapped = [f for f in facts if f.base_record_id != "NFD02"] + [forged]
        with pytest.raises(RegistryError, match="不精确相等"):
            build_attribute_bundle([self._split("NFD02")], swapped, records,
                                   card=card, decision_id="d1", cutoff=CUT)

    def test_subset_population_rejected(self):
        # re-review#3 M1: exact population equality — a SUBSET of the card's base
        # facts is refused even though every member is genuine
        card, records, facts = self._rendered()
        with pytest.raises(RegistryError, match="不精确相等"):
            build_attribute_bundle([self._split("NFD01")], facts[:1], records,
                                   card=card, decision_id="d1", cutoff=CUT)

    def test_cross_card_binding_rejected(self):
        # re-review#3 M1: a bundle can only bind ITS OWN card — records/facts from
        # a different render (importance differs -> different card identity) refuse
        card_a, records_a, facts_a = self._rendered()
        card_b, records_b, facts_b = render_news_flash_section(
            [_assessed("重大订单甲", status="官方证实", importance=4)], CUT)
        with pytest.raises(RegistryError, match="不符|不精确相等"):
            build_attribute_bundle([self._split("NFD01")], facts_b, records_b,
                                   card=card_a, decision_id="d1", cutoff=CUT)
        # and the two cards' bundle identities differ (source_card_hash sealed)
        assert card_a.card_hash != card_b.card_hash

    def test_decision_id_not_coerced(self):
        # re-review#3 M1: decision_id=1 must be refused, not str()-coerced
        card, records, facts = self._rendered()
        for bad in (1, None, "", "  "):
            with pytest.raises(RegistryError, match="decision_id"):
                build_attribute_bundle([self._split("NFD01")], facts, records,
                                       card=card, decision_id=bad, cutoff=CUT)

    def test_empty_attributes_rejected(self):
        # re-review#3 m1: an empty split must not demote evidence with no child
        card, records, facts = self._rendered()
        with pytest.raises(RegistryError, match="fact"):
            build_attribute_bundle([{"base_record_id": "NFD01", "attributes": {}}],
                                   facts, records, card=card,
                                   decision_id="d1", cutoff=CUT)

    def test_missing_fact_attribute_rejected(self):
        # re-review#3 m1: demoting a broad base requires the fact attribute
        card, records, facts = self._rendered()
        with pytest.raises(RegistryError, match="fact"):
            build_attribute_bundle(
                [{"base_record_id": "NFD01", "attributes": {"timing": "下季度"}}],
                facts, records, card=card, decision_id="d1", cutoff=CUT)

    def test_final_registry_reverifies_d7_parent_binding(self):
        # re-review#4 B1: the bundle's final registry passes require_sealed_registry
        # (D7 children bind the DEMOTED parent, whose hash the child sealed)
        from workspace.research.ai_research_dept.engine.news_evidence import (
            require_sealed_registry,
        )
        card, records, facts = self._rendered()
        art = build_attribute_bundle(
            [self._split("NFD01")], facts, records, card=card,
            decision_id="d1", cutoff=CUT)
        final_reg = art.final_registry
        require_sealed_registry(final_reg)                 # D7 relationships hold
        # the demoted parent and its children coexist; parent is context_only
        by_id = dict(final_reg.records)
        assert authorize(by_id["NFD01"], use="factor_positive", consumer_seat="news",
                         target_dimension="event_materiality") is False
        assert authorize(by_id["NFD01.fact"], use="factor_positive",
                         consumer_seat="news",
                         target_dimension="event_materiality") is True

    def test_duck_typed_registry_rejected(self):
        # re-review#3 B2: an unsealed lookalike exposing .registry_hash is refused
        card, records, facts = self._rendered()
        bundle = build_attribute_bundle(
            [self._split("NFD01")], facts, records, card=card,
            decision_id="d1", cutoff=CUT).bundle
        presplit = {r.record_id: r for r in records}       # pre-split positives!

        class _Fake:
            registry_hash = bundle.final_registry_hash
            records = presplit
        with pytest.raises(RegistryError, match="SealedCardRegistry"):
            verify_bundle_registry(bundle, _Fake())

    def test_duplicate_base_split_rejected(self):
        card, records, facts = self._rendered()
        with pytest.raises(RegistryError, match="全局重复拆分"):
            build_attribute_bundle([self._split("NFD01"), self._split("NFD01")],
                                   facts, records, card=card,
                                   decision_id="d1", cutoff=CUT)

    def test_unknown_base_rejected(self):
        card, records, facts = self._rendered()
        with pytest.raises(RegistryError, match="无密封 D7BaseFact"):
            build_attribute_bundle([self._split("NFD99")], facts, records,
                                   card=card, decision_id="d1", cutoff=CUT)

    def test_bundle_seal_binds_authorization(self):
        # re-review#2 B1: bundles differing only in child content (class/attrs)
        # must have different bundle hashes (child content_hash is sealed)
        card, records, facts = self._rendered()
        b1 = build_attribute_bundle([self._split("NFD01")], facts, records,
                                    card=card, decision_id="d1", cutoff=CUT).bundle
        b2 = build_attribute_bundle([self._split("NFI01")], facts, records,
                                    card=card, decision_id="d1", cutoff=CUT).bundle
        assert b1.bundle_hash != b2.bundle_hash
        assert len(b1.bundle_hash) == 64 and b1.child_record_hashes

    def test_forged_bundle_rejected(self):
        from workspace.research.ai_research_dept.engine.news_cards import AttributeBundle
        card, records, facts = self._rendered()
        b = build_attribute_bundle([self._split("NFD01")], facts, records,
                                   card=card, decision_id="d1", cutoff=CUT).bundle
        with pytest.raises(SealError):
            AttributeBundle(decision_id="EVIL", cutoff_iso=b.cutoff_iso,
                            source_card_hash=b.source_card_hash,
                            base_fact_hashes=b.base_fact_hashes,
                            source_registry_hash=b.source_registry_hash,
                            claim_ids=b.claim_ids, row_hashes=b.row_hashes,
                            child_record_hashes=b.child_record_hashes,
                            demoted_record_hashes=b.demoted_record_hashes,
                            final_registry_hash=b.final_registry_hash,
                            bundle_hash=b.bundle_hash)

    def test_mismatched_registry_refused_downstream(self):
        card, records, facts = self._rendered()
        bundle = build_attribute_bundle([self._split("NFD01")], facts, records,
                                        card=card, decision_id="d1", cutoff=CUT).bundle
        other = build_card_registry(bundle.cutoff_iso, records)   # pre-split registry
        with pytest.raises(RegistryError, match="不符"):
            verify_bundle_registry(bundle, other)


# --------------------------------------------------- D7 artifact boundary (rr#5 B1)

class TestD7Artifact:
    def _rendered(self):
        return render_news_flash_section(
            [_assessed("重大订单甲", status="官方证实", importance=5),
             _assessed("媒体乙报道", status="署名媒体", importance=4,
                       dt="2025-01-27 09:00:00")], CUT)

    def _split(self, base_id):
        return {"base_record_id": base_id,
                "attributes": {"fact": "签订 12 亿订单", "economic_linkage": "年营收 15%"}}

    def _artifact(self):
        card, records, facts = self._rendered()
        art = build_attribute_bundle([self._split("NFD01")], facts, records,
                                     card=card, decision_id="d1", cutoff=CUT)
        return card, records, facts, art

    def test_factory_artifact_verifies(self):
        from workspace.research.ai_research_dept.engine.news_cards import verify_d7_artifact
        _, _, _, art = self._artifact()
        assert verify_d7_artifact(art) is art
        assert len(art.artifact_hash) == 64

    def test_wrong_source_correct_registry_rejected(self):
        # re-review#5 B1 named probe: wrong source-parent hash + CORRECT registry-
        # parent hash passed require_sealed_registry before; the artifact boundary
        # must reject it via full source-lineage re-derivation
        from workspace.research.ai_research_dept.engine.news_cards import (
            AttributeBundle, D7DecisionArtifact, verify_d7_artifact,
        )
        from workspace.research.ai_research_dept.engine.news_evidence import (
            ATTRIBUTE_DIMENSIONS, build_card_record, build_card_registry as bcr,
        )
        card, records, facts, art = self._artifact()
        fin = art.final_registry
        demoted = fin.records["NFD01"]
        # forge children: WRONG source hash, CORRECT registry (demoted) hash
        forged_children = []
        for attr in ("fact", "economic_linkage"):
            forged_children.append(build_card_record(
                f"NFD01.{attr}", domain="news", evidence_class="NFD",
                allowed_uses={"factor_positive", "context_only"},
                allowed_consumers={"news"},
                allowed_dimensions=ATTRIBUTE_DIMENSIONS[attr],
                record_schema_id="d7_child_v2",
                derivation=(("source_parent_content_hash", "c" * 64),   # WRONG
                            ("registry_parent_content_hash", demoted.content_hash),
                            ("attribute_type", attr))))
        others = [r for rid, r in fin.records.items() if "." not in rid]
        forged_fin = bcr(art.bundle.cutoff_iso, others + forged_children)  # passes registry checks
        forged_bundle = AttributeBundle(
            decision_id="d1", cutoff_iso=art.bundle.cutoff_iso,
            source_card_hash=card.card_hash,
            base_fact_hashes=art.bundle.base_fact_hashes,
            source_registry_hash=art.bundle.source_registry_hash,
            claim_ids=art.bundle.claim_ids, row_hashes=art.bundle.row_hashes,
            child_record_hashes=tuple(sorted(c.content_hash for c in forged_children)),
            demoted_record_hashes=art.bundle.demoted_record_hashes,
            final_registry_hash=forged_fin.registry_hash)               # self-sealed
        forged_art = D7DecisionArtifact(
            card=card, base_facts=art.base_facts, source_registry=art.source_registry,
            rows=art.rows, bundle=forged_bundle, final_registry=forged_fin)
        with pytest.raises(RegistryError, match="source 血缘"):
            verify_d7_artifact(forged_art)

    def test_self_sealed_false_lineage_bundle_rejected(self):
        # re-review#5 B1 named probe: an internally-valid AttributeBundle with
        # INVENTED source identities must not pass the artifact boundary
        from workspace.research.ai_research_dept.engine.news_cards import (
            AttributeBundle, D7DecisionArtifact, verify_d7_artifact,
        )
        card, records, facts, art = self._artifact()
        fake_bundle = AttributeBundle(
            decision_id="d1", cutoff_iso=art.bundle.cutoff_iso,
            source_card_hash="f" * 64,                                  # invented
            base_fact_hashes=art.bundle.base_fact_hashes,
            source_registry_hash="e" * 64,                              # invented
            claim_ids=art.bundle.claim_ids, row_hashes=art.bundle.row_hashes,
            child_record_hashes=art.bundle.child_record_hashes,
            demoted_record_hashes=art.bundle.demoted_record_hashes,
            final_registry_hash=art.final_registry.registry_hash)       # self-sealed ok
        fake_art = D7DecisionArtifact(
            card=card, base_facts=art.base_facts, source_registry=art.source_registry,
            rows=art.rows, bundle=fake_bundle, final_registry=art.final_registry)
        with pytest.raises(RegistryError, match="绑定不符"):
            verify_d7_artifact(fake_art)
        # and the old narrow gate is documented as NOT the lineage boundary:
        # the fake bundle still matches its registry there (final-hash only)
        verify_bundle_registry(fake_bundle, art.final_registry)

    def test_artifact_forge_rejected(self):
        from workspace.research.ai_research_dept.engine.news_cards import D7DecisionArtifact
        _, _, _, art = self._artifact()
        with pytest.raises(SealError):
            D7DecisionArtifact(card=art.card, base_facts=art.base_facts,
                               source_registry=art.source_registry, rows=(),
                               bundle=art.bundle, final_registry=art.final_registry,
                               artifact_hash=art.artifact_hash)   # rows dropped, old hash


# --------------------------------------------------- renderer full revalidation (M3)

class TestRendererRevalidation:
    def test_post_assess_mutation_rejected(self):
        # re-review#2 M3: mutating typing AFTER assess_flash must be refused at
        # the renderer boundary (previously int("5")/5.0 coercions let it through)
        for field_name, bad in (("event_type", "EVIL"), ("direction", "涨停"),
                                ("importance", "5"), ("importance", 5.0),
                                ("importance", True)):
            a = _assessed("被篡改事实")
            a["typing"][field_name] = bad
            with pytest.raises(RegistryError):
                render_news_flash_section([a], CUT)


# --------------------------------------------------- macro precedence (Major-5)

class TestMacroPrecedence:
    def test_prompt_pins_external_shock_precedence(self):
        # re-review Major-5: discrete external shocks take precedence over
        # 地缘外围/商品汇率/货币政策 — pinned in the typing prompt verbatim
        from workspace.research.ai_research_dept.engine.news_ingest import (
            _MACRO_TYPE_APPENDIX,
        )
        assert "归类优先级" in _MACRO_TYPE_APPENDIX
        assert "一律归 external_shock" in _MACRO_TYPE_APPENDIX
        assert "优先于 地缘外围/商品汇率/货币政策" in _MACRO_TYPE_APPENDIX

    def test_derivation_doc_states_precedence(self):
        import workspace.research.ai_research_dept.engine.news_taxonomy as tax
        assert "离散外部冲击" in (tax.__doc__ or "")


# --------------------------------------------------- B1′ legacy classification

class TestLegacyClassification:
    @pytest.mark.parametrize("rid,expect", [
        ("N00", True), ("NDA1", True), ("NDA12", True), ("NIA3", True),
        ("ND01", False), ("NI07", False), ("NX01", False), ("F01", False),
    ])
    def test_is_legacy_attention(self, rid, expect):
        assert is_legacy_attention_id(rid) is expect
