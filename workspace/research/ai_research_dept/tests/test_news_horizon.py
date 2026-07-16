# NF chain unit sub-block 1: c16_news_horizon_v1 deterministic contract core.
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ai_layer.scorecard import ScorecardViolation, validate_scorecard_record  # noqa: E402

from workspace.research.ai_research_dept.engine.news_evidence import (  # noqa: E402
    RegistryError, build_card_record, build_card_registry,
)
from workspace.research.ai_research_dept.engine.news_horizon import (  # noqa: E402
    GLOBAL_WEIGHTS, HORIZONS, assert_evidence_exclusive,
    compute_news_final_by_horizon, deterministic_zero_factor_record,
    evaluate_news_horizon, news_final_scalar, validate_factor_leg_output,
    validate_penalty_leg_output,
)

CUT = "2025-01-27T18:00:00"
_DIMS = frozenset({"event_materiality", "fundamental_link", "novelty",
                   "catalyst_timing", "tradeability_at_horizon"})


def _pos(rid, ec="NFD"):
    return build_card_record(rid, domain="news", evidence_class=ec,
                             allowed_uses={"factor_positive", "context_only"},
                             allowed_consumers={"news"}, allowed_dimensions=_DIMS)


def _reg():
    recs = [_pos(f"NFD0{i}") for i in range(1, 7)]
    recs.append(_pos("NFI01", ec="NFI"))               # ceiling-3 evidence
    recs.append(build_card_record("NFR01", domain="news", evidence_class="NFR",
                                  allowed_uses={"penalty", "bear"},
                                  allowed_consumers={"news", "bear"},
                                  allowed_dimensions={"manipulation_risk"}))
    recs.append(build_card_record("NFC01", domain="coordination",
                                  evidence_class="coordination_risk",
                                  allowed_uses={"penalty", "bear"},
                                  allowed_consumers={"news", "bear"},
                                  allowed_dimensions={"coordination_risk"}))
    return build_card_registry(CUT, recs)


def _factor(mat=5, fund=5, nov=5, trades=(5, 5, 5),
            cits=("NFD01", "NFD02", "NFD03", "NFD04", "NFD05", "NFD06")):
    return {"factor_scores": [
                {"name": "event_materiality", "score_0_5": mat,
                 "citations": [cits[0]]},
                {"name": "fundamental_link", "score_0_5": fund,
                 "citations": [cits[1]]},
                {"name": "novelty", "score_0_5": nov, "citations": [cits[2]]}],
            "horizon_factor_scores": [
                {"name": "tradeability_at_horizon", "horizon": h,
                 "score_0_5": t, "citations": [cits[3 + i]]}
                for i, (h, t) in enumerate(zip(HORIZONS, trades))],
            "horizon_theses": []}


def _penalty(entries=()):
    return {"penalty_scores": list(entries), "risk_flags": []}


# --------------------------------------------------- c16_v1 unchanged (M2″)

class TestLegacyRejectsHorizon:
    def test_c16_v1_rejects_horizon_fields(self):
        rec = {"factor_scores": [], "horizon_factor_scores": []}
        with pytest.raises(ScorecardViolation, match="unknown top-level"):
            validate_scorecard_record(rec, weights={"event_materiality": 6})

    def test_c16_v1_rejects_theses(self):
        rec = {"factor_scores": [], "horizon_theses": []}
        with pytest.raises(ScorecardViolation, match="unknown top-level"):
            validate_scorecard_record(rec, weights={"event_materiality": 6})


# --------------------------------------------------- pinned formula (M3‴)

class TestFormula:
    def test_max_scores_reach_exactly_100(self):
        f = validate_factor_leg_output(_factor(), _reg())
        p = validate_penalty_leg_output(_penalty(), _reg())
        finals = compute_news_final_by_horizon(f, p)
        assert finals == {h: 100.0 for h in HORIZONS}   # 6·5+5·5+5·5+4·5 = 100

    def test_penalty_multiplier_2x_global_per_horizon(self):
        f = validate_factor_leg_output(_factor(), _reg())
        p = validate_penalty_leg_output(_penalty([
            {"name": "manipulation_risk", "score_0_5": 2, "citations": ["NFR01"]}]),
            _reg())
        finals = compute_news_final_by_horizon(f, p)
        assert finals == {h: 96.0 for h in HORIZONS}    # 100 − 2·2, every horizon

    def test_horizon_differentiation(self):
        f = validate_factor_leg_output(_factor(trades=(5, 3, 0)), _reg())
        p = validate_penalty_leg_output(_penalty(), _reg())
        finals = compute_news_final_by_horizon(f, p)
        assert finals["next_open"] == 100.0
        assert finals["1-3d"] == 92.0                   # 80 + 4·3
        assert finals["5-20d"] == 80.0                  # trade contributes 0

    def test_single_rounding_full_precision_to_clamp(self):
        f = validate_factor_leg_output(_factor(mat=3, fund=3, nov=3,
                                               trades=(3, 3, 3)), _reg())
        p = validate_penalty_leg_output(_penalty([
            {"name": "manipulation_risk", "score_0_5": 1.234,
             "citations": ["NFR01"]}]), _reg())
        finals = compute_news_final_by_horizon(f, p)
        # raw 60 − 2·1.234 = 57.532 → one rounding → 57.5
        assert finals["next_open"] == 57.5

    def test_clamp_floor_zero(self):
        f = validate_factor_leg_output(_factor(mat=0, fund=0, nov=0,
                                               trades=(0, 0, 0)), _reg())
        p = validate_penalty_leg_output(_penalty([
            {"name": "manipulation_risk", "score_0_5": 5, "citations": ["NFR01"]}]),
            _reg())
        assert compute_news_final_by_horizon(f, p) == {h: 0.0 for h in HORIZONS}


# --------------------------------------------------- M2⁴ semantics

class TestM24:
    def test_missing_horizon_pair_schema_failure(self):
        rec = _factor()
        rec["horizon_factor_scores"] = rec["horizon_factor_scores"][:2]
        with pytest.raises(ScorecardViolation, match="覆盖不符"):
            validate_factor_leg_output(rec, _reg())

    def test_duplicate_horizon_pair_schema_failure(self):
        rec = _factor()
        rec["horizon_factor_scores"].append(dict(rec["horizon_factor_scores"][0]))
        with pytest.raises(ScorecardViolation, match="重复|exact-once"):
            validate_factor_leg_output(rec, _reg())

    def test_unregistered_horizon_schema_failure(self):
        rec = _factor()
        rec["horizon_factor_scores"][0]["horizon"] = "30-60d"
        with pytest.raises(ScorecardViolation, match="未注册"):
            validate_factor_leg_output(rec, _reg())

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "5", None, 6])
    def test_non_finite_or_invalid_score_schema_failure(self, bad):
        rec = _factor()
        rec["horizon_factor_scores"][0]["score_0_5"] = bad
        with pytest.raises(ScorecardViolation, match="score_0_5"):
            validate_factor_leg_output(rec, _reg())

    def test_empty_citations_is_no_score_not_failure(self):
        rec = _factor()
        rec["factor_scores"][0]["citations"] = []       # materiality ungrounded
        f = validate_factor_leg_output(rec, _reg())     # NOT a schema failure
        p = validate_penalty_leg_output(_penalty(), _reg())
        finals = compute_news_final_by_horizon(f, p)
        assert finals["next_open"] == 70.0              # 100 − 6·5 (NO-SCORE = 0)

    def test_unauthorized_citation_is_no_score(self):
        rec = _factor()
        rec["factor_scores"][0]["citations"] = ["NFR01"]   # penalty-only record
        f = validate_factor_leg_output(rec, _reg())
        assert f["global"]["event_materiality"] == (0.0, False)

    def test_unregistered_citation_is_no_score(self):
        rec = _factor()
        rec["factor_scores"][0]["citations"] = ["NFD99"]
        f = validate_factor_leg_output(rec, _reg())
        assert f["global"]["event_materiality"] == (0.0, False)


# --------------------------------------------------- ceiling recompute (BINDING #5)

class TestCeiling:
    def test_nfi_citation_caps_score_at_3(self):
        rec = _factor()
        rec["factor_scores"][0]["citations"] = ["NFI01"]   # ceiling-3 evidence
        f = validate_factor_leg_output(rec, _reg())
        assert f["global"]["event_materiality"] == (3.0, True)   # min(5, 3)

    def test_nfd_citation_allows_5(self):
        f = validate_factor_leg_output(_factor(), _reg())
        assert f["global"]["event_materiality"] == (5.0, True)


# --------------------------------------------------- evidence exclusivity (M2″)

class TestExclusivity:
    def test_same_id_in_two_factor_entries_hard_fails(self):
        rec = _factor(cits=("NFD01", "NFD01", "NFD03", "NFD04", "NFD05", "NFD06"))
        f = validate_factor_leg_output(rec, _reg())
        p = validate_penalty_leg_output(_penalty(), _reg())
        with pytest.raises(ScorecardViolation, match="独占"):
            assert_evidence_exclusive(f, p)

    def test_id_shared_across_factor_and_penalty_hard_fails(self):
        f = validate_factor_leg_output(_factor(), _reg())
        p = validate_penalty_leg_output(_penalty([
            {"name": "coordination_risk", "score_0_5": 1, "citations": ["NFD01"]}]),
            _reg())
        with pytest.raises(ScorecardViolation, match="独占"):
            assert_evidence_exclusive(f, p)


# --------------------------------------------------- leg isolation (M2‴)

class TestLegSchemas:
    def test_penalty_key_in_factor_leg_rejected(self):
        rec = _factor()
        rec["penalty_scores"] = []
        with pytest.raises(ScorecardViolation, match="penalty"):
            validate_factor_leg_output(rec, _reg())

    def test_factor_key_in_penalty_leg_rejected(self):
        with pytest.raises(ScorecardViolation, match="factor"):
            validate_penalty_leg_output({"penalty_scores": [], "factor_scores": []},
                                        _reg())

    def test_unregistered_penalty_dim_rejected(self):
        with pytest.raises(ScorecardViolation, match="未注册罚分维"):
            validate_penalty_leg_output(_penalty([
                {"name": "hype", "score_0_5": 1, "citations": ["NFR01"]}]), _reg())

    def test_ungrounded_penalty_contributes_zero(self):
        f = validate_factor_leg_output(_factor(), _reg())
        p = validate_penalty_leg_output(_penalty([
            {"name": "manipulation_risk", "score_0_5": 5, "citations": []}]), _reg())
        assert compute_news_final_by_horizon(f, p)["next_open"] == 100.0

    # re-review Major: penalty authorization is DIMENSION-AWARE — the three
    # sanctioned mappings are exclusive (NFR→manipulation only, NFC→coordination
    # only, D7 source_status→confidence_cap only); cross-dimension = NO-SCORE
    @pytest.mark.parametrize("cit,dim,grounded", [
        ("NFR01", "manipulation_risk", True),
        ("NFR01", "coordination_risk", False),
        ("NFR01", "confidence_cap", False),
        ("NFC01", "coordination_risk", True),
        ("NFC01", "manipulation_risk", False),
        ("NFC01", "confidence_cap", False),
    ])
    def test_penalty_dimension_mapping_matrix(self, cit, dim, grounded):
        p = validate_penalty_leg_output(_penalty([
            {"name": dim, "score_0_5": 3, "citations": [cit]}]), _reg())
        assert p["penalties"][dim][1] is grounded
        assert p["penalties"][dim][0] == (3.0 if grounded else 0.0)

    def test_d7_source_status_grounds_only_confidence_cap(self):
        # a D7 source_status child (dims={confidence_cap}) — full sanctioned matrix
        parent = _pos("NFD09")
        child = build_card_record(
            "NFD09.source_status", domain="news", evidence_class="NFD",
            allowed_uses={"penalty", "bear"}, allowed_consumers={"news", "bear"},
            allowed_dimensions={"confidence_cap"},
            record_schema_id="d7_child_v2",
            derivation=(("source_parent_content_hash", "a" * 64),
                        ("registry_parent_content_hash", parent.content_hash),
                        ("attribute_type", "source_status")))
        reg = build_card_registry(CUT, [parent, child])
        for dim, ok in (("confidence_cap", True), ("manipulation_risk", False),
                        ("coordination_risk", False)):
            p = validate_penalty_leg_output(_penalty([
                {"name": dim, "score_0_5": 2,
                 "citations": ["NFD09.source_status"]}]), reg)
            assert p["penalties"][dim][1] is ok


# --------------------------------------------------- theses (D2/D3)

class TestTheses:
    def _thesis(self, **over):
        t = {"horizon": "1-3d", "direction": "利好",
             "causal_chain": "订单落地→产能爬坡→收入确认",
             "priced_in_status": "部分消化(公告日涨 3%)",
             "alternative_explanation": "行业整体回暖的贝塔",
             "base_adverse_scenario": "交付延期则收入后移一季",
             "falsifiable_condition": "下季度产能利用率未提升",
             "strongest_counter": "客户集中度高,单一订单依赖"}
        t.update(over)
        return t

    def test_valid_thesis_passes(self):
        rec = _factor()
        rec["horizon_theses"] = [self._thesis()]
        validate_factor_leg_output(rec, _reg())

    def test_missing_strongest_counter_rejected(self):
        rec = _factor()
        bad = self._thesis()
        del bad["strongest_counter"]
        rec["horizon_theses"] = [bad]
        with pytest.raises(ScorecardViolation, match="论点键"):
            validate_factor_leg_output(rec, _reg())

    def test_empty_strongest_counter_rejected(self):
        rec = _factor()
        rec["horizon_theses"] = [self._thesis(strongest_counter="  ")]
        with pytest.raises(ScorecardViolation, match="最强反证|非空"):
            validate_factor_leg_output(rec, _reg())

    def test_thesis_citations_do_not_unlock_scores(self):
        # theses are non-scoring: they carry no citations field at all — a thesis
        # cannot smuggle one (exact key set)
        rec = _factor()
        rec["horizon_theses"] = [dict(self._thesis(), citations=["NFD01"])]
        with pytest.raises(ScorecardViolation, match="论点键"):
            validate_factor_leg_output(rec, _reg())


# --------------------------------------------------- modes + zero path

class TestModesAndZero:
    def test_primary_alias(self):
        out = evaluate_news_horizon(_factor(trades=(5, 3, 0)), _penalty(), _reg(),
                                    output_mode="primary_horizon",
                                    primary_decision_horizon="1-3d")
        assert out["news_final"] == 92.0                # alias of the pinned horizon

    def test_vector_only_no_scalar(self):
        out = evaluate_news_horizon(_factor(), _penalty(), _reg(),
                                    output_mode="vector_only",
                                    primary_decision_horizon=None)
        assert out["news_final"] is None

    def test_vector_only_with_pinned_horizon_refused(self):
        with pytest.raises(RegistryError, match="vector_only"):
            news_final_scalar({h: 0.0 for h in HORIZONS}, output_mode="vector_only",
                              primary_decision_horizon="1-3d")

    def test_primary_without_pinned_horizon_refused(self):
        with pytest.raises(RegistryError, match="冻结契约"):
            news_final_scalar({h: 0.0 for h in HORIZONS},
                              output_mode="primary_horizon",
                              primary_decision_horizon=None)

    def test_zero_evidence_deterministic_record(self):
        # BINDING #4: zero positive population -> all pairs present, zero scores,
        # no citations, validates WITHOUT an LLM, finals all zero
        out = evaluate_news_horizon(deterministic_zero_factor_record(), _penalty(),
                                    _reg(), output_mode="primary_horizon",
                                    primary_decision_horizon="next_open")
        assert out["news_final_by_horizon"] == {h: 0.0 for h in HORIZONS}
        assert out["news_final"] == 0.0

    def test_weights_pinned(self):
        assert GLOBAL_WEIGHTS == {"event_materiality": 6, "fundamental_link": 5,
                                  "novelty": 5}
        assert sum(GLOBAL_WEIGHTS.values()) * 5 + 4 * 5 == 100


# --------------------------------------------------- execution view (BINDING #1)

class TestExecutionView:
    def test_executors_receive_immutable_view(self, tmp_path):
        import pandas as pd
        from workspace.research.ai_research_dept.engine.news_cards import (
            assess_flash, build_attribute_bundle, render_news_flash_section,
        )
        from workspace.research.ai_research_dept.engine.news_decision import (
            ExecutionView, record_decision,
        )
        from workspace.research.ai_research_dept.engine.news_evidence import EvidenceRef
        from workspace.research.ai_research_dept.engine.news_ingest import (
            build_cluster_snapshots,
        )
        from workspace.research.ai_research_dept.engine.news_legs import (
            run_news_two_legs,
        )

        def _stamp(rows):
            df = pd.DataFrame(rows)
            df["source_published_at"] = pd.to_datetime(df["datetime"])
            df["first_ingested_at"] = df["source_published_at"] + pd.Timedelta(minutes=1)
            df["decision_visible_at"] = df["first_ingested_at"]
            df["object_id_hash"] = "obj:" + df["content"]
            df["content_hash"] = "ch:" + df["content"]
            df["ingest_class"] = "forward"
            return df

        cl = build_cluster_snapshots(
            _stamp([{"src": "sina", "datetime": "2025-01-27 10:00:00",
                     "content": "重大订单甲"}]), "2025-01-27 18:00:00")[0]
        typing = {"event_type": "订单合同", "verification_status": "官方证实",
                  "content_kind": "事实", "direction": "利好", "importance": 5,
                  "is_rumor": False}
        route = {"primary_route": "stock", "subject_codes": ["688981.SH"],
                 "industry_tags": [], "concept_tags": [], "content": "重大订单甲"}
        card, records, facts = render_news_flash_section(
            [assess_flash(cl, typing, route)], "2025-01-27 18:00:00")
        art = build_attribute_bundle(
            [{"base_record_id": "NFD01",
              "attributes": {"fact": "签订 12 亿订单"}}],
            facts, records, card=card, decision_id="d1",
            cutoff="2025-01-27 18:00:00")
        record_decision(tmp_path, "d1", art)
        got = []
        f_ast = {"facts": [EvidenceRef(rid) for rid, r in
                           sorted(art.final_registry.records.items())
                           if "factor_positive" in r.allowed_uses]}
        run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                          output_mode="primary_horizon",
                          factor_payload_ast=f_ast, penalty_payload_ast=None,
                          factor_leg_fn=lambda v: got.append(v),
                          penalty_leg_fn=lambda v: None)
        assert len(got) == 1 and isinstance(got[0], ExecutionView)
        assert not hasattr(got[0], "payload_ast")       # AST not exposed
        with pytest.raises(Exception):
            got[0].payload_text = "篡改"                 # frozen
