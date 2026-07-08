"""C16 tests: deterministic scorecard aggregation + LLM containment.

Post impl-review #2 Blocker-1 / #3 Major-3: ONE evidence rule for factors AND
penalties — an entry counts only with non-empty, dossier-grounded,
SUBSTANTIVE (>=8 chars, non-trivial) evidence_spans; an evidence-free penalty
can NEVER move the final (audit-only via risk_flags).
"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from ai_layer.scorecard import (  # noqa: E402
    ScorecardViolation,
    compute_scorecard_final,
    validate_scorecard_record,
)

WEIGHTS = {"event_materiality": 8, "fundamental_link": 6, "novelty": 6}
CTX = ("公司获得大额设备订单。海外产能落地推进中。管理层回复具体且可验证。"
       "控股股东存在减持计划。")
SPAN_ORDER = "公司获得大额设备订单"
SPAN_CAPACITY = "海外产能落地推进中"
SPAN_MGMT = "管理层回复具体且可验证"
SPAN_RISK = "控股股东存在减持计划"


def _rec(factors, penalties=(), extra=None):
    rec = {
        "factor_scores": [
            {"name": n, "score_0_5": s, "evidence_spans": ev}
            for n, s, ev in factors
        ],
        "penalty_scores": [
            {"name": n, "score_0_5": s, "evidence_spans": ev}
            for n, s, ev in penalties
        ],
    }
    if extra:
        rec.update(extra)
    return rec


def test_final_computed_by_code_clamped():
    rec = _rec([("event_materiality", 5, [SPAN_ORDER]),
                ("fundamental_link", 3, [SPAN_CAPACITY])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 58.0
    # grounded penalties clamp at 0 from below
    rec2 = _rec([("event_materiality", 1, [SPAN_ORDER])],
                penalties=[("rumor_like", 5, [SPAN_RISK]),
                           ("hype", 5, [SPAN_MGMT])])
    assert compute_scorecard_final(rec2, weights=WEIGHTS, evidence_context=CTX) == 0.0


def test_llm_emitted_final_or_action_rejected():
    for field in ({"final": 88.0}, {"action": "buy"}, {"target_rank": 3}):
        rec = _rec([("novelty", 4, [SPAN_ORDER])], extra=field)
        with pytest.raises(ScorecardViolation):
            validate_scorecard_record(rec, weights=WEIGHTS)


def test_missing_evidence_span_is_no_score_not_neutral():
    rec = _rec([("event_materiality", 5, []),
                ("fundamental_link", 2, [SPAN_CAPACITY])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 12.0


def test_out_of_range_score_is_no_score():
    rec = _rec([("event_materiality", 7, [SPAN_ORDER]),
                ("novelty", 3, [SPAN_ORDER])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 18.0


def test_unregistered_score_name_cannot_smuggle_influence():
    rec = _rec([("secret_alpha_signal", 5, [SPAN_ORDER]),
                ("novelty", 1, [SPAN_ORDER])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 6.0


def test_trivial_or_short_span_is_no_score():
    # R3 Major-3: a generic/near-empty quote cannot carry evidentiary weight
    for spans in (["公司"], ["订单"], ["公告"]):
        rec = _rec([("event_materiality", 5, spans)])
        assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 0.0


def test_evidence_free_penalty_cannot_move_final():
    # R2 Blocker-1: governance_flag=5 with NO evidence -> zero influence
    rec = {
        "factor_scores": [{"name": "novelty", "score_0_5": 3,
                           "evidence_spans": [SPAN_ORDER]}],
        "penalty_scores": [{"name": "governance_flag", "score_0_5": 5,
                            "evidence_spans": []}],
        "risk_flags": ["疑似治理问题(无逐字证据)"],
    }
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 18.0


def test_ungrounded_penalty_evidence_is_no_score():
    rec = {
        "factor_scores": [{"name": "novelty", "score_0_5": 3,
                           "evidence_spans": [SPAN_ORDER]}],
        "penalty_scores": [{"name": "governance_flag", "score_0_5": 5,
                            "evidence_spans": ["完全不存在于原文的编造句子"]}],
    }
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 18.0


def test_grounded_penalty_counts_uncapped_by_registration():
    rec = {
        "factor_scores": [{"name": "novelty", "score_0_5": 3,
                           "evidence_spans": [SPAN_ORDER]}],
        "penalty_scores": [{"name": "governance_flag", "score_0_5": 2,
                            "evidence_spans": [SPAN_RISK]}],
    }
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 14.0


def test_ungrounded_factor_evidence_is_no_score():
    rec = _rec([("event_materiality", 5, ["完全不存在于原文的编造句子"]),
                ("novelty", 2, [SPAN_ORDER])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 12.0
