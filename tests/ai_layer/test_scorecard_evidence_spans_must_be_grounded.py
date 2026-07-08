"""B7/B1: a non-empty evidence span must literally appear (whitespace-normalized)
in the visible dossier/spans context, else the entry is NO-SCORE — a
hallucinated span can never unlock points."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from ai_layer.scorecard import compute_scorecard_final, validate_scorecard_record  # noqa: E402

W = {"event_materiality": 6}
CTX = "公司公告:获得某客户 2.3 亿元设备订单,预计 2026Q4 交付。"


def test_grounded_span_counts():
    rec = {"factor_scores": [{"name": "event_materiality", "score_0_5": 4,
                              "evidence_spans": ["获得某客户 2.3 亿元设备订单"]}]}
    assert compute_scorecard_final(rec, weights=W, evidence_context=CTX) == 24.0


def test_hallucinated_span_is_no_score():
    rec = {"factor_scores": [{"name": "event_materiality", "score_0_5": 5,
                              "evidence_spans": ["签署 50 亿元战略合同"]}]}
    assert compute_scorecard_final(rec, weights=W, evidence_context=CTX) == 0.0


def test_whitespace_normalization_tolerated():
    rec = {"factor_scores": [{"name": "event_materiality", "score_0_5": 3,
                              "evidence_spans": ["获得某客户   2.3 亿元设备订单"]}]}
    assert compute_scorecard_final(rec, weights=W, evidence_context=CTX) == 18.0


def test_overlong_span_rejected():
    rec = {"factor_scores": [{"name": "event_materiality", "score_0_5": 5,
                              "evidence_spans": [CTX * 10]}]}
    validate_scorecard_record(rec, weights=W, evidence_context=CTX * 10)
    assert rec["factor_scores"][0].get("_invalid_evidence") is True
