# NF §7 step 6 registry data: M01-M16 frozen taxonomy + MF derivation (M1⁴/M1‴).
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_evidence import (  # noqa: E402
    RegistryError, authorize, build_card_registry, dimension_ceiling,
)
from workspace.research.ai_research_dept.engine.news_taxonomy import (  # noqa: E402
    M_LINE_TAXONOMY, MACRO_TYPE_DIMENSION, build_m_line_records, build_mf_record,
    build_policy_row_record,
)

CUT = "2025-01-27T18:00:00"


def _by_id():
    return {r.record_id: r for r in build_m_line_records()}


class TestMLineTable:
    def test_exactly_m01_to_m16(self):
        assert sorted(M_LINE_TAXONOMY) == [f"M{i:02d}" for i in range(1, 17)]

    def test_frozen_class_assignments(self):
        # M1‴ authoritative class table, pinned id-by-id
        cls = {rid: ec for rid, (ec, _) in M_LINE_TAXONOMY.items()}
        assert all(cls[r] == "market_breadth_state" for r in ("M03", "M09", "M15"))
        assert all(cls[r] == "market_limit_state" for r in ("M04", "M10"))
        assert cls["M14"] == "market_leadership_state"
        assert all(cls[r] == "market_state_fact"
                   for r in ("M01", "M02", "M05", "M06", "M07", "M08",
                             "M11", "M12", "M13", "M16"))

    def test_m16_never_positive(self):
        m16 = _by_id()["M16"]
        assert "factor_positive" not in m16.allowed_uses
        assert authorize(m16, use="context_only", consumer_seat="macro") is True

    def test_m04_dual_dimension_m01_single(self):
        recs = _by_id()
        assert authorize(recs["M04"], use="factor_positive", consumer_seat="macro",
                         target_dimension="liquidity_flows_transmission") is True
        assert authorize(recs["M04"], use="factor_positive", consumer_seat="macro",
                         target_dimension="risk_appetite_environment_fit") is True
        assert authorize(recs["M01"], use="factor_positive", consumer_seat="macro",
                         target_dimension="liquidity_flows_transmission") is False

    def test_fund_news_seats_never_receive_m_rows(self):
        # M1‴: fund/news 席不收 M 行;technical 需单独契约(未预授)
        for rec in build_m_line_records():
            for seat in ("fund", "news", "technical"):
                assert authorize(rec, use="factor_positive", consumer_seat=seat,
                                 target_dimension="risk_appetite_environment_fit") is False

    def test_external_shock_not_groundable_by_m_lines(self):
        # M1⁴: M01/M02/M06-08/M12 do NOT independently ground external_shock
        reg = build_card_registry(CUT, build_m_line_records())
        assert dimension_ceiling(list(M_LINE_TAXONOMY), reg, consumer_seat="macro",
                                 target_dimension="external_shock_transmission") == 0

    def test_policy_alignment_only_atomic_rows_not_m16(self):
        reg = build_card_registry(CUT, build_m_line_records()
                                  + [build_policy_row_record("MP01")])
        # M16 alone grounds nothing for policy
        assert dimension_ceiling(["M16"], reg, consumer_seat="macro",
                                 target_dimension="policy_alignment") == 0
        # the atomic policy row does
        assert dimension_ceiling(["MP01"], reg, consumer_seat="macro",
                                 target_dimension="policy_alignment") == 5


class TestMFDerivation:
    def test_every_macro_type_registered(self):
        from workspace.research.ai_research_dept.engine.news_ingest import MACRO_TYPES
        assert set(MACRO_TYPE_DIMENSION) == set(MACRO_TYPES)

    def test_external_shock_sole_entry(self):
        # the ONLY macro_type deriving external_shock_transmission
        entries = [t for t, d in MACRO_TYPE_DIMENSION.items()
                   if d == "external_shock_transmission"]
        assert entries == ["external_shock"]

    def test_mfd_with_type_positive_exactly_one_dim(self):
        r = build_mf_record("MF01", "MFD", macro_type="大盘资金面")
        assert authorize(r, use="factor_positive", consumer_seat="macro",
                         target_dimension="liquidity_flows_transmission") is True
        assert len(r.allowed_dimensions) == 1

    def test_geo_and_commodity_do_not_ground_external_shock(self):
        for mt in ("地缘外围", "商品汇率"):
            r = build_mf_record("MF01", "MFD", macro_type=mt)
            assert authorize(r, use="factor_positive", consumer_seat="macro",
                             target_dimension="external_shock_transmission") is False

    def test_missing_macro_type_context_only(self):
        r = build_mf_record("MF01", "MFA", macro_type=None)
        assert "factor_positive" not in r.allowed_uses

    def test_unregistered_macro_type_context_only(self):
        r = build_mf_record("MF01", "MFD", macro_type="花边新闻")
        assert "factor_positive" not in r.allowed_uses

    def test_mfr_penalty_bear_only(self):
        r = build_mf_record("MFR01", "MFR")
        assert r.allowed_uses == frozenset({"penalty", "bear"})
        assert authorize(r, use="factor_positive", consumer_seat="macro",
                         target_dimension="risk_appetite_environment_fit") is False

    def test_unknown_class_rejected(self):
        with pytest.raises(RegistryError, match="MF 记录类"):
            build_mf_record("MF01", "NFD", macro_type="货币政策")


class TestReservedNamespaces:
    # re-review Major-3: policy/MF factories can NEVER borrow a reserved M-line id
    def test_policy_factory_rejects_reserved_m16(self):
        with pytest.raises(RegistryError, match="越界"):
            build_policy_row_record("M16")

    def test_policy_factory_rejects_arbitrary_id(self):
        with pytest.raises(RegistryError, match="越界"):
            build_policy_row_record("POLICY1")

    def test_policy_namespace_accepted(self):
        assert build_policy_row_record("MP01").record_id == "MP01"

    def test_mf_factory_rejects_reserved_m03(self):
        with pytest.raises(RegistryError, match="越界"):
            build_mf_record("M03", "MFD", macro_type="货币政策")

    def test_mf_factory_rejects_short_id(self):
        with pytest.raises(RegistryError, match="越界"):
            build_mf_record("MFR1", "MFR")              # needs 2+ digits

    def test_kernel_factory_rejects_deviant_reserved_mint(self):
        # even bypassing the taxonomy factories, the KERNEL factory refuses a
        # reserved id with non-canonical metadata (the original probe:
        # a factor-positive M16 policy record)
        from workspace.research.ai_research_dept.engine.news_evidence import (
            build_card_record,
        )
        with pytest.raises(RegistryError, match="保留 ID"):
            build_card_record("M16", domain="macro", evidence_class="market_state_fact",
                              allowed_uses={"factor_positive", "context_only"},
                              allowed_consumers={"macro"},
                              allowed_dimensions={"policy_alignment"})
