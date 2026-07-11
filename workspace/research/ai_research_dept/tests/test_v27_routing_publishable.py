# GPT 复审#7 回归:B1 冻结 routing 实际执行 / B2 嵌套权重+NaN 封死 /
# B3 共享合格判定 verify_publishable_archive / B4 marker status 文本对照重算
import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import ai_layer.ark_client as ark  # noqa: E402
import workspace.research.ai_research_dept.engine.llm_config as L  # noqa: E402
from workspace.research.ai_research_dept.engine.analyst_chain import (  # noqa: E402
    COMPOSITE_W, SEAT_WEIGHTS, ChainContract, VersionCollisionError,
    archive_complete, build_manifest, ensure_immutable_manifest,
    read_prompt_bundle,
)
from workspace.research.ai_research_dept.engine.integrity import (  # noqa: E402
    sha256_json, verify_archive_semantics, verify_publishable_archive,
    verify_scoring_contract,
)
from workspace.research.ai_research_dept.platform.server import (  # noqa: E402
    validate_full_month_status,
)

NAN = float("nan")


def _frames():
    return (pd.DataFrame({"pv_pack_version": ["pv_v0.2"]}),
            pd.DataFrame({"retrieval_profile_snapshot_id": ["snap1"]}),
            pd.DataFrame({"regime_card_version": ["regime_v0.4"]}))


def _load_contract(tmp_path):
    pv, retr, regime = _frames()
    ensure_immutable_manifest(tmp_path, build_manifest(
        pv, retr, regime, read_prompt_bundle(), ["20250127"], ["688981.SH"]))
    return ChainContract.load(tmp_path)


# ------------------------------------------------------------- B1 routing

class _FakeReply:
    def __init__(self, model):
        self.model, self.text, self.raw, self.usage = model, "{}", {}, {}


class TestFrozenRoutingExecuted:
    def test_call_with_config_ignores_task_llm(self, tmp_path, monkeypatch):
        """GPT 复现封死:加载契约后篡改 TASK_LLM,执行参数必须保持冻结值。"""
        contract = _load_contract(tmp_path)
        frozen_model = contract.routing["scoring"]["model"]
        captured = {}

        def fake_chat(messages, *, model, thinking, temperature, max_tokens):
            captured.update(model=model, thinking=thinking,
                            temperature=temperature, max_tokens=max_tokens)
            return _FakeReply(model)

        monkeypatch.setattr(ark, "chat", fake_chat)
        monkeypatch.setitem(L.TASK_LLM, "dimension_scoring",
                            {"model": "tampered-model", "thinking": False,
                             "temperature": 0.9, "max_tokens": 1,
                             "fallback": None})
        r = L.call_with_config([{"role": "user", "content": "x"}],
                               contract.routing["scoring"])
        assert captured["model"] == frozen_model != "tampered-model"
        assert captured["temperature"] == contract.routing["scoring"]["temperature"]
        assert r.model == frozen_model
        # 对照:旧的 L.call(task) 门确实会读被篡改的全局(证明修复是必要的)
        L.call("dimension_scoring", [{"role": "user", "content": "x"}])
        assert captured["model"] == "tampered-model"

    def test_call_with_config_requires_exec_keys(self):
        with pytest.raises(KeyError, match="缺执行字段"):
            L.call_with_config([], {"model": "m"})

    def test_contract_carries_llm_config_hash(self, tmp_path):
        contract = _load_contract(tmp_path)
        assert contract.llm_config_hash == L.llm_config_hash()

    def test_load_rejects_broken_routing(self, tmp_path):
        pv, retr, regime = _frames()
        m = build_manifest(pv, retr, regime, read_prompt_bundle(),
                           ["20250127"], ["688981.SH"])
        m["routing"] = {"scoring": {"model": "m"}, "bear": m["routing"]["bear"]}
        ensure_immutable_manifest(tmp_path, m)
        with pytest.raises(VersionCollisionError, match="routing"):
            ChainContract.load(tmp_path)

    def test_load_rejects_missing_llm_config_hash(self, tmp_path):
        pv, retr, regime = _frames()
        m = build_manifest(pv, retr, regime, read_prompt_bundle(),
                           ["20250127"], ["688981.SH"])
        m["llm_config_hash"] = ""
        ensure_immutable_manifest(tmp_path, m)
        with pytest.raises(VersionCollisionError, match="llm_config_hash"):
            ChainContract.load(tmp_path)


# ------------------------------------------------------------- B2 嵌套权重

_GOOD = {"seat_weights": {"fund": {"a": 20.0}, "tech": {"b": 30.0}},
         "composite_weights": {"fund": 0.5, "tech": 0.5},
         "bear_discount_strength": 4, "divergence_gap": 40}


class TestNestedWeightValidation:
    def test_valid_passes(self):
        assert verify_scoring_contract(_GOOD) == []
        assert verify_scoring_contract({
            "seat_weights": SEAT_WEIGHTS, "composite_weights": COMPOSITE_W,
            "bear_discount_strength": 4, "divergence_gap": 40}) == []

    def test_nan_composite_weight_rejected(self):
        """GPT 复现:composite_weights["fund"]=NaN 曾让复核 fail-open。"""
        bad = {**_GOOD, "composite_weights": {"fund": NAN, "tech": 0.5}}
        assert any("composite_weights" in p for p in verify_scoring_contract(bad))

    @pytest.mark.parametrize("sw,label", [
        ({"fund": {}, "tech": {"b": 30.0}}, "seat_weights[fund]"),
        ({"fund": "x", "tech": {"b": 30.0}}, "seat_weights[fund]"),
        ({"fund": {"a": NAN}, "tech": {"b": 30.0}}, "seat_weights[fund]"),
        ({"fund": {"a": -1}, "tech": {"b": 30.0}}, "seat_weights[fund]"),
        ({"fund": {"a": 101}, "tech": {"b": 30.0}}, "seat_weights[fund]"),
        ({"fund": {"a": True}, "tech": {"b": 30.0}}, "seat_weights[fund]"),
    ])
    def test_bad_seat_dims_rejected(self, sw, label):
        problems = verify_scoring_contract({**_GOOD, "seat_weights": sw,
                                            "composite_weights":
                                            {"fund": 0.5, "tech": 0.5}})
        assert problems and label in problems[0]

    @pytest.mark.parametrize("cw", [
        {"fund": 0.6, "tech": 0.6},          # 合计 1.2
        {"fund": 0.5, "tech": 0.4},          # 合计 0.9
        {"fund": 1.5, "tech": -0.5},         # 域外
    ])
    def test_composite_sum_must_be_one(self, cw):
        assert verify_scoring_contract({**_GOOD, "composite_weights": cw})

    def test_semantics_second_defense_nan_recompute(self):
        """第二道防线:即便 NaN 权重漏进语义层,重算值非有限数也必须点名。"""
        a = {"seats": {"fund": {"final": 50.0, "error": None}},
             "records": {"fund": {"factor_scores": []}},
             "bear": {"refutations": [], "kill_switches": ["k"],
                      "schema_valid": True, "parse_mode": "strict"},
             "judge": {"finals": {"fund": 50.0}, "composite": 99.0,
                       "composite_adj": 50.0}}
        problems = verify_archive_semantics(a, {"fund": {"a": 20.0}},
                                            {"fund": NAN})
        assert any("composite" in p for p in problems)


# ------------------------------------------------------------- B3 共享合格判定

def _publishable_arch(**mut):
    a = {"seats": {s: {"final": 50.0, "error": None} for s in SEAT_WEIGHTS},
         "records": {s: {"factor_scores": []} for s in SEAT_WEIGHTS},
         "bear": {"refutations": [], "kill_switches": ["k"], "blind_spots": [],
                  "schema_valid": True, "parse_mode": "strict"},
         "judge": {"finals": {s: 50.0 for s in SEAT_WEIGHTS},
                   "composite": 50.0, "composite_adj": 50.0}}
    for k, v in mut.items():
        a[k] = v
    return a


class TestSharedPublishablePredicate:
    def test_clean_passes_both(self):
        a = _publishable_arch()
        assert verify_publishable_archive(a, SEAT_WEIGHTS, COMPOSITE_W) == []
        assert archive_complete(a) is True

    def test_bear_schema_invalid_named(self):
        """GPT 复现:bear.schema_valid=False 曾在平台侧 sealed_ok、
        引擎侧 incomplete——同一档案两种判定。"""
        a = _publishable_arch()
        a["bear"]["schema_valid"] = False
        problems = verify_publishable_archive(a, SEAT_WEIGHTS, COMPOSITE_W)
        assert any("schema_valid" in p for p in problems)
        assert archive_complete(a) is False

    def test_seat_error_named(self):
        a = _publishable_arch()
        a["seats"]["tech"]["error"] = "boom"
        assert any("seats[tech]" in p for p in
                   verify_publishable_archive(a, SEAT_WEIGHTS, COMPOSITE_W))
        assert archive_complete(a) is False

    def test_bear_error_and_parse_mode_named(self):
        a = _publishable_arch()
        a["bear"]["error"] = "x"
        assert verify_publishable_archive(a, SEAT_WEIGHTS, COMPOSITE_W)
        b = _publishable_arch()
        b["bear"]["parse_mode"] = None
        assert any("parse_mode" in p for p in
                   verify_publishable_archive(b, SEAT_WEIGHTS, COMPOSITE_W))

    def test_engine_platform_verdict_equivalence(self):
        """引擎 bool 与共享谓词逐例等价(同一把尺的机械断言)。"""
        cases = [_publishable_arch()]
        for mut in ({"bear": {}},):
            cases.append(_publishable_arch(**mut))
        c = _publishable_arch(); c["bear"]["schema_valid"] = False; cases.append(c)
        d = _publishable_arch(); d["seats"]["fund"]["error"] = "e"; cases.append(d)
        e = _publishable_arch(); e["judge"]["composite"] = 99.9; cases.append(e)
        for a in cases:
            assert archive_complete(a) == (
                not verify_publishable_archive(a, SEAT_WEIGHTS, COMPOSITE_W))


# ------------------------------------------------------------- B4 status 文本

def _js_manifest():
    days, codes = ["20250127"], ["000001.SZ", "000002.SZ"]
    return {"job_spec": {"scope_kind": "full_month", "days": days,
                         "codes": codes, "expected": 2,
                         "job_set_sha256": sha256_json(
                             {"days": days, "codes": codes})}}


def _marker(m, varch, status_text):
    seals = sorted([[d, c.replace(".", "_"), a["archive_sha256"]]
                    for (c, d), a in varch.items()])
    return {"scope_kind": "full_month",
            "job_set_sha256": m["job_spec"]["job_set_sha256"],
            "expected": 2, "complete": len(seals),
            "archive_set_sha256": sha256_json(seals), "status": status_text}


class TestMarkerStatusText:
    def test_partial_forged_as_complete_rejected(self):
        """GPT 复现:真实 1/2 档案,只把 status 文本改成 complete 曾通过。"""
        m = _js_manifest()
        varch = {("000001.SZ", "20250127"): {"archive_sha256": "s1"}}
        forged = _marker(m, varch, "complete")
        ok, problems = validate_full_month_status(forged, m, varch)
        assert not ok and any("status=complete" in p for p in problems)

    def test_complete_downgraded_to_partial_rejected(self):
        m, varch = _js_manifest(), {
            ("000001.SZ", "20250127"): {"archive_sha256": "s1"},
            ("000002.SZ", "20250127"): {"archive_sha256": "s2"}}
        ok, problems = validate_full_month_status(
            _marker(m, varch, "partial"), m, varch)
        assert not ok and any("status=partial" in p for p in problems)

    def test_missing_or_illegal_status_rejected(self):
        m, varch = _js_manifest(), {
            ("000001.SZ", "20250127"): {"archive_sha256": "s1"},
            ("000002.SZ", "20250127"): {"archive_sha256": "s2"}}
        marker = _marker(m, varch, "complete")
        del marker["status"]
        assert not validate_full_month_status(marker, m, varch)[0]
        assert not validate_full_month_status(
            _marker(m, varch, "DONE!!"), m, varch)[0]

    def test_genuine_complete_and_partial_accepted(self):
        m = _js_manifest()
        full = {("000001.SZ", "20250127"): {"archive_sha256": "s1"},
                ("000002.SZ", "20250127"): {"archive_sha256": "s2"}}
        assert validate_full_month_status(_marker(m, full, "complete"),
                                          m, full)[0]
        part = {("000001.SZ", "20250127"): {"archive_sha256": "s1"}}
        assert validate_full_month_status(_marker(m, part, "partial"),
                                          m, part)[0]
