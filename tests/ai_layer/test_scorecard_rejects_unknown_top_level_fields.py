"""B7/B1 + R2 Blocker-1: unknown top-level and entry fields HARD-FAIL — an
unmodeled field is a smuggling channel; internal markers (`_invalid_evidence`)
are never accepted from the wire (evidence validity is computed, not trusted)."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from ai_layer.scorecard import ScorecardViolation, validate_scorecard_record  # noqa: E402

W = {"novelty": 6}


def test_unknown_top_level_field_rejected():
    rec = {"factor_scores": [{"name": "novelty", "score_0_5": 3, "evidence_spans": ["a"]}],
           "recommended_weight": 0.5}
    with pytest.raises(ScorecardViolation, match="unknown top-level"):
        validate_scorecard_record(rec, weights=W)


def test_unknown_entry_field_rejected():
    rec = {"factor_scores": [{"name": "novelty", "score_0_5": 3,
                              "evidence_spans": ["a"], "suggested_rank": 1}]}
    with pytest.raises(ScorecardViolation, match="unknown factor_scores entry"):
        validate_scorecard_record(rec, weights=W)


def test_llm_supplied_internal_marker_rejected():
    # R2 Blocker-1: `_invalid_evidence` is not a wire field — reject
    rec = {"penalty_scores": [{"name": "rumor_like", "score_0_5": 5,
                               "evidence_spans": ["a"], "_invalid_evidence": False}]}
    with pytest.raises(ScorecardViolation, match="unknown penalty_scores entry"):
        validate_scorecard_record(rec, weights=W)


def test_allowed_shape_passes():
    rec = {"factor_scores": [{"name": "novelty", "score_0_5": 3, "evidence_spans": ["a"]}],
           "penalty_scores": [], "risk_flags": [], "what_could_weaken": ["x"]}
    validate_scorecard_record(rec, weights=W)
