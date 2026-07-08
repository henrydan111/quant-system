"""C16 tests: deterministic scorecard aggregation + LLM containment.

Post impl-review #2 Blocker-1: ONE evidence rule for factors AND penalties —
an entry counts only with non-empty, dossier-grounded evidence_spans; an
evidence-free penalty can NEVER move the final (audit-only via risk_flags).
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
CTX = "span1 span2 span s 公司获得大额订单 存在减持"


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
    rec = _rec([("event_materiality", 5, ["span1"]), ("fundamental_link", 3, ["span2"])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 58.0
    # grounded penalties clamp at 0 from below
    rec2 = _rec([("event_materiality", 1, ["s"])],
                penalties=[("rumor_like", 5, ["span1"]), ("hype", 5, ["span2"])])
    assert compute_scorecard_final(rec2, weights=WEIGHTS, evidence_context=CTX) == 0.0


def test_llm_emitted_final_or_action_rejected():
    for field in ({"final": 88.0}, {"action": "buy"}, {"target_rank": 3}):
        rec = _rec([("novelty", 4, ["s"])], extra=field)
        with pytest.raises(ScorecardViolation):
            validate_scorecard_record(rec, weights=WEIGHTS)


def test_missing_evidence_span_is_no_score_not_neutral():
    rec = _rec([("event_materiality", 5, []), ("fundamental_link", 2, ["span"])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 12.0


def test_out_of_range_score_is_no_score():
    rec = _rec([("event_materiality", 7, ["s"]), ("novelty", 3, ["s"])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 18.0


def test_unregistered_score_name_cannot_smuggle_influence():
    rec = _rec([("secret_alpha_signal", 5, ["s"]), ("novelty", 1, ["s"])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 6.0


def test_evidence_free_penalty_cannot_move_final():
    # R2 Blocker-1: governance_flag=5 with NO evidence -> zero influence
    rec = {
        "factor_scores": [{"name": "novelty", "score_0_5": 3, "evidence_spans": ["span1"]}],
        "penalty_scores": [{"name": "governance_flag", "score_0_5": 5,
                            "evidence_spans": []}],
        "risk_flags": ["疑似治理问题(无逐字证据)"],
    }
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 18.0


def test_ungrounded_penalty_evidence_is_no_score():
    rec = {
        "factor_scores": [{"name": "novelty", "score_0_5": 3, "evidence_spans": ["span1"]}],
        "penalty_scores": [{"name": "governance_flag", "score_0_5": 5,
                            "evidence_spans": ["不存在的原文"]}],
    }
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 18.0


def test_grounded_penalty_counts_uncapped_by_registration():
    rec = {
        "factor_scores": [{"name": "novelty", "score_0_5": 3, "evidence_spans": ["span1"]}],
        "penalty_scores": [{"name": "governance_flag", "score_0_5": 2,
                            "evidence_spans": ["存在减持"]}],
    }
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 14.0


def test_ungrounded_factor_evidence_is_no_score():
    rec = _rec([("event_materiality", 5, ["编造的证据句"]), ("novelty", 2, ["span1"])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 12.0
