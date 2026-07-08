"""C16 test_stub (RED first): deterministic scorecard aggregation + LLM containment.

Contract (CONTRACTS.md C16): the LLM emits ONLY 0-5 dimension scores + evidence
spans; deterministic code computes final = clamp(Σ w·score − Σ 2·penalty, 0, 100).
The LLM never emits the final number or an action; a record carrying one is
REJECTED. Invalid/unsupported scores become NO-SCORE (0 points, conservative),
never neutral-positive. Only PRE-REGISTERED score names count (an invented
score name cannot smuggle influence).
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
PENALTY_WEIGHT = 2.0


def _rec(factors, penalties=(), extra=None):
    rec = {
        "ts_code": "000001.SZ",
        "factor_scores": [
            {"name": n, "score_0_5": s, "evidence_spans": ev}
            for n, s, ev in factors
        ],
        "penalty_scores": [{"name": n, "score_0_5": s} for n, s in penalties],
    }
    if extra:
        rec.update(extra)
    return rec


def test_final_computed_by_code_clamped():
    rec = _rec([("event_materiality", 5, ["span1"]), ("fundamental_link", 3, ["span2"])])
    validate_scorecard_record(rec, weights=WEIGHTS)
    # 5*8 + 3*6 = 58, no penalties
    assert compute_scorecard_final(rec, weights=WEIGHTS) == 58.0
    # penalties subtract at 2x, clamped at 0
    rec2 = _rec([("event_materiality", 1, ["s"])], penalties=[("rumor_like", 5), ("hype", 5)])
    assert compute_scorecard_final(rec2, weights=WEIGHTS) == 0.0  # 8 - 20 -> clamp 0


def test_llm_emitted_final_or_action_rejected():
    for field in ({"final": 88.0}, {"action": "buy"}, {"target_rank": 3}):
        rec = _rec([("novelty", 4, ["s"])], extra=field)
        with pytest.raises(ScorecardViolation):
            validate_scorecard_record(rec, weights=WEIGHTS)


def test_missing_evidence_span_is_no_score_not_neutral():
    rec = _rec([("event_materiality", 5, []),          # no evidence -> NO-SCORE
                ("fundamental_link", 2, ["span"])])
    validate_scorecard_record(rec, weights=WEIGHTS)
    # only fundamental_link counts: 2*6 = 12 (event_materiality contributes 0)
    assert compute_scorecard_final(rec, weights=WEIGHTS) == 12.0


def test_out_of_range_score_is_no_score():
    rec = _rec([("event_materiality", 7, ["s"]),       # invalid range
                ("novelty", 3, ["s"])])
    validate_scorecard_record(rec, weights=WEIGHTS)
    assert compute_scorecard_final(rec, weights=WEIGHTS) == 18.0  # only novelty 3*6


def test_unregistered_score_name_cannot_smuggle_influence():
    rec = _rec([("secret_alpha_signal", 5, ["s"]),     # NOT in pre-registered weights
                ("novelty", 1, ["s"])])
    validate_scorecard_record(rec, weights=WEIGHTS)
    assert compute_scorecard_final(rec, weights=WEIGHTS) == 6.0   # only novelty
