"""B7/B1(+): a non-empty evidence span must literally appear (whitespace-
normalized) in the RAW dossier context, else the entry is NO-SCORE — a
hallucinated or overlong span can never unlock (or subtract) points."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from ai_layer.scorecard import compute_scorecard_final  # noqa: E402

W = {"event_materiality": 6}
CTX = "公司公告:获得某客户 2.3 亿元设备订单,预计 2026Q4 交付。"


def _one(score, spans):
    return {"factor_scores": [{"name": "event_materiality", "score_0_5": score,
                               "evidence_spans": spans}]}


def test_grounded_span_counts():
    assert compute_scorecard_final(_one(4, ["获得某客户 2.3 亿元设备订单"]),
                                   weights=W, evidence_context=CTX) == 24.0


def test_hallucinated_span_is_no_score():
    assert compute_scorecard_final(_one(5, ["签署 50 亿元战略合同"]),
                                   weights=W, evidence_context=CTX) == 0.0


def test_one_bad_span_poisons_the_entry():
    # mixed grounded + hallucinated -> entire entry NO-SCORE (all-spans rule)
    assert compute_scorecard_final(_one(5, ["获得某客户 2.3 亿元设备订单", "编造句"]),
                                   weights=W, evidence_context=CTX) == 0.0


def test_whitespace_normalization_tolerated():
    assert compute_scorecard_final(_one(3, ["获得某客户   2.3 亿元设备订单"]),
                                   weights=W, evidence_context=CTX) == 18.0


def test_overlong_span_is_no_score():
    big_ctx = CTX * 10
    assert compute_scorecard_final(_one(5, [big_ctx]),
                                   weights=W, evidence_context=big_ctx) == 0.0
