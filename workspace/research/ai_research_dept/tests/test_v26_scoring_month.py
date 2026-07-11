# GPT 复审#6 回归:B1 评分契约 fail-open 封死 / B2 full_month_status 验证后才暴露 /
# Major schema-1 仅限 chain_v2.4
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import workspace.research.ai_research_dept.engine.analyst_chain as ac  # noqa: E402
from workspace.research.ai_research_dept.engine.analyst_chain import (  # noqa: E402
    ChainContract, VersionCollisionError, archive_complete, build_manifest,
    ensure_immutable_manifest, judge, read_prompt_bundle,
)
from workspace.research.ai_research_dept.engine.integrity import (  # noqa: E402
    REQUIRED_SCORING_KEYS, sha256_json, verify_scoring_contract,
)


def _frames():
    return (pd.DataFrame({"pv_pack_version": ["pv_v0.2"]}),
            pd.DataFrame({"retrieval_profile_snapshot_id": ["snap1"]}),
            pd.DataFrame({"regime_card_version": ["regime_v0.4"]}))


def _manifest():
    pv, retr, regime = _frames()
    return build_manifest(pv, retr, regime, read_prompt_bundle(),
                          ["20250127"], ["688981.SH"])


_GOOD_SCORING = {"seat_weights": {"fund": {"a": 20.0}},
                 "composite_weights": {"fund": 1.0},
                 "bear_discount_strength": 4, "divergence_gap": 40}


# --------------------------------------------------- B1 评分契约完备性

class TestScoringContractCompleteness:
    def test_valid_passes(self):
        assert verify_scoring_contract(_GOOD_SCORING) == []

    @pytest.mark.parametrize("missing", sorted(REQUIRED_SCORING_KEYS))
    def test_each_missing_key_flagged(self, missing):
        sc = {k: v for k, v in _GOOD_SCORING.items() if k != missing}
        problems = verify_scoring_contract(sc)
        assert problems and missing in problems[0]

    @pytest.mark.parametrize("mut,label", [
        ({"seat_weights": {}}, "seat_weights"),
        ({"seat_weights": "x"}, "seat_weights"),
        ({"composite_weights": {"other": 1.0}}, "composite_weights"),
        ({"bear_discount_strength": 999}, "bear_discount_strength"),
        ({"bear_discount_strength": float("nan")}, "bear_discount_strength"),
        ({"bear_discount_strength": True}, "bear_discount_strength"),
        ({"divergence_gap": -1}, "divergence_gap"),
        ({"divergence_gap": "40"}, "divergence_gap"),
    ])
    def test_bad_values_flagged(self, mut, label):
        problems = verify_scoring_contract({**_GOOD_SCORING, **mut})
        assert problems and label in problems[0]

    def test_non_dict_flagged(self):
        assert verify_scoring_contract(None)
        assert verify_scoring_contract([])

    def test_contract_load_rejects_incomplete_scoring(self, tmp_path):
        """GPT 复现:缺 bear_discount_strength/divergence_gap 的自洽 manifest
        曾通过 ChainContract.load,judge 回退到可变全局。"""
        m = _manifest()
        m["scoring_contract"] = {k: v for k, v in m["scoring_contract"].items()
                                 if k not in ("bear_discount_strength",
                                              "divergence_gap")}
        ensure_immutable_manifest(tmp_path, m)          # 正文自洽
        with pytest.raises(VersionCollisionError, match="scoring_contract 缺字段"):
            ChainContract.load(tmp_path)


def _seat_results():
    return {"fund": {"final": 100.0,
                     "record": {"factor_scores": [
                         {"name": "a", "score_0_5": 5, "evidence_spans": ["x"]}],
                         "penalty_scores": []}}}


def _strong_bear():
    return {"refutations": [{"target_seat": "fund", "target_dim": "a",
                             "strength_0_5": 4}]}


class TestJudgeNoFallback:
    def test_incomplete_contract_raises_not_falls_back(self):
        """持契约时直接索引:缺键 = KeyError,绝不静默用模块全局。"""
        sc = {"seat_weights": {"fund": {"a": 20.0}},
              "composite_weights": {"fund": 1.0}}
        with pytest.raises(KeyError):
            judge(_seat_results(), _strong_bear(), sc)

    def test_globals_mutation_inert_with_contract(self, monkeypatch):
        """GPT 复现封死:契约在手时改全局 BEAR_DISCOUNT_STRENGTH/DIVERGENCE_GAP
        不再改变裁决(曾把 adj 15→30)。"""
        baseline = judge(_seat_results(), _strong_bear(), dict(_GOOD_SCORING))
        monkeypatch.setattr(ac, "BEAR_DISCOUNT_STRENGTH", 999)
        monkeypatch.setattr(ac, "DIVERGENCE_GAP", 0)
        mutated = judge(_seat_results(), _strong_bear(), dict(_GOOD_SCORING))
        assert mutated == baseline
        assert mutated["adj_finals"]["fund"] == 50.0   # 折减仍按契约阈值 4 生效

    def test_archive_complete_malformed_scoring_fail_closed(self):
        a = {"seats": {}, "records": {}, "bear": {}, "judge": {}}
        assert archive_complete(a, {"seat_weights": None}) is False
        assert archive_complete(a, {}) is False


# --------------------------------------------------- B2 月度标记验证

from workspace.research.ai_research_dept.platform.server import (  # noqa: E402
    SCHEMA1_CHAINS, validate_full_month_status,
)


def _job_spec_manifest():
    js_days, js_codes = ["20250127"], ["000001.SZ", "000002.SZ"]
    return {"job_spec": {"scope_kind": "full_month", "days": js_days,
                         "codes": js_codes, "expected": 2,
                         "job_set_sha256": sha256_json(
                             {"days": js_days, "codes": js_codes})}}


def _varch():
    return {("000001.SZ", "20250127"): {"archive_sha256": "s1"},
            ("000002.SZ", "20250127"): {"archive_sha256": "s2"}}


def _genuine_status(m, varch):
    seals = sorted([[d, c.replace(".", "_"), a["archive_sha256"]]
                    for (c, d), a in varch.items()])
    return {"scope_kind": "full_month",
            "job_set_sha256": m["job_spec"]["job_set_sha256"],
            "expected": 2, "complete": len(seals),
            "archive_set_sha256": sha256_json(seals)}


class TestFullMonthStatusValidation:
    def test_genuine_marker_accepted(self):
        m, varch = _job_spec_manifest(), _varch()
        ok, problems = validate_full_month_status(_genuine_status(m, varch), m, varch)
        assert ok and not problems

    def test_forged_claim_rejected(self):
        """GPT 复现:伪造 2384/2384 marker(错 job 哈希+错档案集哈希)曾原样暴露。"""
        m, varch = _job_spec_manifest(), {("000001.SZ", "20250127"):
                                          {"archive_sha256": "s1"}}
        forged = {"scope_kind": "full_month", "job_set_sha256": "WRONG",
                  "expected": 2384, "complete": 2384,
                  "archive_set_sha256": "FORGED"}
        ok, problems = validate_full_month_status(forged, m, varch)
        assert not ok and len(problems) >= 3

    def test_post_hoc_archive_deletion_detected(self):
        """完成后删档:complete 计数与磁盘不符 + 封印集哈希不符。"""
        m, varch = _job_spec_manifest(), _varch()
        status = _genuine_status(m, varch)
        del varch[("000002.SZ", "20250127")]
        ok, problems = validate_full_month_status(status, m, varch)
        assert not ok and any("complete" in p for p in problems)

    def test_archive_swap_detected(self):
        """同数量换档案内容:封印集哈希不符。"""
        m, varch = _job_spec_manifest(), _varch()
        status = _genuine_status(m, varch)
        varch[("000002.SZ", "20250127")] = {"archive_sha256": "EVIL"}
        ok, problems = validate_full_month_status(status, m, varch)
        assert not ok and any("archive_set_sha256" in p for p in problems)

    def test_missing_job_spec_rejected(self):
        ok, _ = validate_full_month_status({"scope_kind": "full_month"}, {}, {})
        assert not ok

    def test_smoke_scoped_marker_rejected(self):
        m, varch = _job_spec_manifest(), _varch()
        status = {**_genuine_status(m, varch), "scope_kind": "smoke"}
        ok, problems = validate_full_month_status(status, m, varch)
        assert not ok and any("scope_kind" in p for p in problems)


# --------------------------------------------------- Major schema-1 限定

def test_schema1_allowlist_is_v24_only():
    assert SCHEMA1_CHAINS == frozenset({"chain_v2.4"})
