"""C16 tests: deterministic scorecard aggregation + LLM containment (B1-hardened).

Post impl-review B1: unknown top-level/entry fields HARD-FAIL; every non-empty
evidence span must be GROUNDED (literal substring of the visible context) or
the entry becomes NO-SCORE — for factor scores AND penalties.
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
            {"name": n, "score_0_5": s, **({"evidence_spans": ev[0]} if ev else {})}
            for n, s, *ev in penalties
        ],
    }
    if extra:
        rec.update(extra)
    return rec


def test_final_computed_by_code_clamped():
    rec = _rec([("event_materiality", 5, ["span1"]), ("fundamental_link", 3, ["span2"])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 58.0
    rec2 = _rec([("event_materiality", 1, ["s"])],
                penalties=[("rumor_like", 5), ("hype", 5)])
    assert compute_scorecard_final(rec2, weights=WEIGHTS, evidence_context=CTX) == 0.0


def test_llm_emitted_final_or_action_rejected():
    for field in ({"final": 88.0}, {"action": "buy"}, {"target_rank": 3}):
        rec = _rec([("novelty", 4, ["s"])], extra=field)
        with pytest.raises(ScorecardViolation):
            validate_scorecard_record(rec, weights=WEIGHTS, evidence_context=CTX)


def test_missing_evidence_span_is_no_score_not_neutral():
    rec = _rec([("event_materiality", 5, []), ("fundamental_link", 2, ["span"])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 12.0


def test_out_of_range_score_is_no_score():
    rec = _rec([("event_materiality", 7, ["s"]), ("novelty", 3, ["s"])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 18.0


def test_unregistered_score_name_cannot_smuggle_influence():
    rec = _rec([("secret_alpha_signal", 5, ["s"]), ("novelty", 1, ["s"])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 6.0


def test_ungrounded_evidence_is_no_score_for_factors_and_penalties():
    # hallucinated span (not in CTX) -> factor NO-SCORE
    rec = _rec([("event_materiality", 5, ["编造的证据句"]), ("novelty", 2, ["span1"])])
    assert compute_scorecard_final(rec, weights=WEIGHTS, evidence_context=CTX) == 12.0
    # penalty with ungrounded evidence -> penalty NO-SCORE (would otherwise subtract 10)
    rec2 = {
        "factor_scores": [{"name": "novelty", "score_0_5": 3, "evidence_spans": ["span1"]}],
        "penalty_scores": [{"name": "governance_flag", "score_0_5": 5,
                            "evidence_spans": ["不存在的原文"]}],
    }
    assert compute_scorecard_final(rec2, weights=WEIGHTS, evidence_context=CTX) == 18.0
    # penalty WITHOUT evidence_spans still counts (risk direction, uncapped)
    rec3 = {
        "factor_scores": [{"name": "novelty", "score_0_5": 3, "evidence_spans": ["span1"]}],
        "penalty_scores": [{"name": "governance_flag", "score_0_5": 2}],
    }
    assert compute_scorecard_final(rec3, weights=WEIGHTS, evidence_context=CTX) == 14.0
