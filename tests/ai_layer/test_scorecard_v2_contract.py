# GPT REVISE Blocker-2 回归:scorecard 严格校验契约(chain_v2.1)
"""重名双计、注册维恰一次、分数域、证伪 schema —— 全部 fail-closed。

重名拒收是无条件的(对所有消费者都是 C16 漏洞);其余严格项 opt-in,
冻结的 MVP 前向产品(默认参数)行为不变。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ai_layer.scorecard import (  # noqa: E402
    ScorecardViolation, compute_scorecard_final, validate_scorecard_record,
)

W = {"a": 10.0, "b": 10.0}
CTX = "- [F01]某字段: 1.2|行业分位35%(468家)|10年分位33%\n- [F02]另一字段: 5.0|行业分位90%|10年分位80%"
SPAN1 = "[F01]某字段: 1.2|行业分位35%(468家)|10年分位33%"
SPAN2 = "[F02]另一字段: 5.0|行业分位90%|10年分位80%"


def _rec(factors, penalties=None, wcw=None):
    r = {"factor_scores": factors, "penalty_scores": penalties or [],
         "risk_flags": []}
    if wcw is not None:
        r["what_could_weaken"] = wcw
    return r


class TestDuplicateRejectionUnconditional:
    def test_duplicate_factor_names_rejected(self):
        rec = _rec([{"name": "a", "score_0_5": 5, "evidence_spans": [SPAN1]},
                    {"name": "a", "score_0_5": 5, "evidence_spans": [SPAN2]}])
        with pytest.raises(ScorecardViolation, match="double-count"):
            validate_scorecard_record(rec, weights=W)

    def test_duplicate_penalty_names_rejected(self):
        rec = _rec([{"name": "a", "score_0_5": 5, "evidence_spans": [SPAN1]}],
                   penalties=[{"name": "p", "score_0_5": 1, "evidence_spans": [SPAN2]},
                              {"name": "p", "score_0_5": 1, "evidence_spans": [SPAN2]}])
        with pytest.raises(ScorecardViolation, match="double-count"):
            validate_scorecard_record(rec, weights=W)

    def test_gpt_reproduction_exploit_closed(self):
        """GPT 复现:单条 grounded x=5,w=10 得 50;两条相同曾得 100 —— 现在整卡拒收。"""
        one = _rec([{"name": "a", "score_0_5": 5, "evidence_spans": [SPAN1]}])
        assert compute_scorecard_final(one, weights=W, evidence_context=CTX) == 50.0
        two = _rec([{"name": "a", "score_0_5": 5, "evidence_spans": [SPAN1]},
                    {"name": "a", "score_0_5": 5, "evidence_spans": [SPAN1]}])
        with pytest.raises(ScorecardViolation):
            compute_scorecard_final(two, weights=W, evidence_context=CTX)


class TestStrictOptIn:
    def test_missing_registered_dim_rejected(self):
        rec = _rec([{"name": "a", "score_0_5": 3, "evidence_spans": []}])
        with pytest.raises(ScorecardViolation, match="exactly once"):
            validate_scorecard_record(rec, weights=W, require_registered_exact=True)

    def test_unregistered_extra_dim_rejected(self):
        rec = _rec([{"name": "a", "score_0_5": 3, "evidence_spans": []},
                    {"name": "b", "score_0_5": 3, "evidence_spans": []},
                    {"name": "ghost", "score_0_5": 5, "evidence_spans": []}])
        with pytest.raises(ScorecardViolation, match="exactly once"):
            validate_scorecard_record(rec, weights=W, require_registered_exact=True)

    def test_no_data_dim_with_empty_evidence_ok(self):
        rec = _rec([{"name": "a", "score_0_5": 3, "evidence_spans": [SPAN1]},
                    {"name": "b", "score_0_5": 0, "evidence_spans": []}])
        validate_scorecard_record(rec, weights=W, require_registered_exact=True)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, 6, "5", True])
    def test_score_domain_hard_fail(self, bad):
        rec = _rec([{"name": "a", "score_0_5": bad, "evidence_spans": []},
                    {"name": "b", "score_0_5": 3, "evidence_spans": []}])
        with pytest.raises(ScorecardViolation, match="finite number"):
            validate_scorecard_record(rec, weights=W, require_registered_exact=True)

    def test_default_params_keep_legacy_behavior(self):
        """MVP 冻结产品路径:默认参数下,缺维/域外分不 raise(compute 端 NO-SCORE 兜底)。"""
        rec = _rec([{"name": "a", "score_0_5": 9, "evidence_spans": [SPAN1]}])
        validate_scorecard_record(rec, weights=W)   # 不 raise
        assert compute_scorecard_final(rec, weights=W, evidence_context=CTX) == 0.0


class TestFalsifierSchema:
    def test_valid(self):
        rec = _rec([{"name": "a", "score_0_5": 3, "evidence_spans": []},
                    {"name": "b", "score_0_5": 3, "evidence_spans": []}],
                   wcw=[{"condition": "现金流恶化", "observable_in": "fund"},
                        {"condition": "行业需求走弱", "observable_in": "news|fund"}])
        validate_scorecard_record(rec, weights=W, require_registered_exact=True,
                                  falsifier_schema=True)

    @pytest.mark.parametrize("bad", [
        [{"condition": "x", "observable_in": "elsewhere"}],
        [{"condition": "x"}],
        [{"condition": "x", "observable_in": "fund", "extra": 1}],
        ["自由文本"],
        [{"condition": "", "observable_in": "fund"}],
        [{"condition": "y" * 61, "observable_in": "fund"}],
    ])
    def test_invalid(self, bad):
        rec = _rec([{"name": "a", "score_0_5": 3, "evidence_spans": []},
                    {"name": "b", "score_0_5": 3, "evidence_spans": []}], wcw=bad)
        with pytest.raises(ScorecardViolation):
            validate_scorecard_record(rec, weights=W, require_registered_exact=True,
                                      falsifier_schema=True)

    def test_schema_off_accepts_legacy_strings(self):
        rec = _rec([{"name": "a", "score_0_5": 3, "evidence_spans": []}],
                   wcw=["自由文本证伪条件"])
        validate_scorecard_record(rec, weights=W)   # 不 raise(MVP 兼容)
