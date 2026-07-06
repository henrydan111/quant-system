"""MVP guardrail test_stub (RED first): deterministic top-K EW selection with caps.

Per the 2026-07-06c directive (ROADMAP Phase-1 MVP): construction = top-K equal
weight from a score ranking, with deterministic guardrails standing in for the
full risk model: per-industry cap (<= ceil(K/3)), exclusion (veto) set, and
candidates-only membership. Selection must be fully deterministic (score desc,
tie-break by code) and fail-closed on nothing (fewer eligible than K -> return
fewer, never pad, never reach outside candidates).
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from portfolio_risk.rank_book_construction import select_top_k_equal_weight  # noqa: E402


def _scores(d):
    return pd.Series(d, dtype=float)


IND = {
    "A1": "银行", "A2": "银行", "A3": "银行", "A4": "银行",
    "B1": "白酒", "B2": "白酒",
    "C1": "半导体",
}


def test_topk_by_score_desc_deterministic():
    s = _scores({"A1": 0.9, "B1": 0.8, "C1": 0.7, "A2": 0.6})
    out = select_top_k_equal_weight(s, k=3, industry_of=IND, max_per_industry=3)
    assert out == ["A1", "B1", "C1"]


def test_industry_cap_skips_and_backfills():
    # top-4 by score are all 银行, cap=2 -> 3rd/4th bank skipped, next industries pulled in
    s = _scores({"A1": 0.9, "A2": 0.8, "A3": 0.7, "A4": 0.6, "B1": 0.5, "C1": 0.4})
    out = select_top_k_equal_weight(s, k=4, industry_of=IND, max_per_industry=2)
    assert out == ["A1", "A2", "B1", "C1"]


def test_unknown_industry_is_its_own_capped_bucket():
    s = _scores({"X1": 0.9, "X2": 0.8, "X3": 0.7, "B1": 0.6})
    out = select_top_k_equal_weight(s, k=3, industry_of={}, max_per_industry=2)
    # X* have no industry -> UNKNOWN bucket, capped at 2
    assert out == ["X1", "X2", "B1"]


def test_exclude_veto_removes_before_selection():
    s = _scores({"A1": 0.9, "B1": 0.8, "C1": 0.7})
    out = select_top_k_equal_weight(s, k=2, industry_of=IND, max_per_industry=2,
                                    exclude={"A1"})
    assert out == ["B1", "C1"]


def test_tie_break_by_code_and_nan_dropped():
    s = _scores({"B1": 0.5, "A1": 0.5, "C1": float("nan")})
    out = select_top_k_equal_weight(s, k=3, industry_of=IND, max_per_industry=3)
    # equal scores -> code order; NaN never selected
    assert out == ["A1", "B1"]


def test_fewer_eligible_than_k_returns_fewer_never_pads():
    s = _scores({"A1": 0.9, "A2": 0.8})
    out = select_top_k_equal_weight(s, k=5, industry_of=IND, max_per_industry=1)
    assert out == ["A1"]
