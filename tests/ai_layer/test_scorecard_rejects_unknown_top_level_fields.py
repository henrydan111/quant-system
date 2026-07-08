"""B7/B1: unknown top-level and entry fields HARD-FAIL (ignore-not-reject ruled
insufficient — an unmodeled field is a smuggling channel, not noise)."""
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
        validate_scorecard_record(rec, weights=W, evidence_context="a")


def test_unknown_entry_field_rejected():
    rec = {"factor_scores": [{"name": "novelty", "score_0_5": 3,
                              "evidence_spans": ["a"], "suggested_rank": 1}]}
    with pytest.raises(ScorecardViolation, match="unknown factor_scores entry"):
        validate_scorecard_record(rec, weights=W, evidence_context="a")


def test_allowed_shape_passes():
    rec = {"factor_scores": [{"name": "novelty", "score_0_5": 3, "evidence_spans": ["a"]}],
           "penalty_scores": [], "risk_flags": [], "what_could_weaken": ["x"]}
    validate_scorecard_record(rec, weights=W, evidence_context="a")
