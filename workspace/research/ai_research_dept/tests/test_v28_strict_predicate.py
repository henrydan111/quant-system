# GPT 复审#8 回归:Blocker 合格判定严格化(真值性 fail-open 封死)/
# Major 共享 verify_llm_route 值类型校验(thinking="False" 语义反转封死)
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import workspace.research.ai_research_dept.engine.llm_config as L  # noqa: E402
from workspace.research.ai_research_dept.engine.analyst_chain import (  # noqa: E402
    COMPOSITE_W, SEAT_WEIGHTS, ChainContract, VersionCollisionError,
    archive_complete, build_manifest, ensure_immutable_manifest,
    read_prompt_bundle,
)
from workspace.research.ai_research_dept.engine.integrity import (  # noqa: E402
    verify_llm_route, verify_publishable_archive,
)

NAN = float("nan")


def _arch(**mut):
    a = {"seats": {s: {"final": 50.0, "error": None} for s in SEAT_WEIGHTS},
         "records": {s: {"factor_scores": []} for s in SEAT_WEIGHTS},
         "bear": {"refutations": [], "kill_switches": ["k"], "blind_spots": [],
                  "schema_valid": True, "parse_mode": "strict"},
         "judge": {"finals": {s: 50.0 for s in SEAT_WEIGHTS},
                   "composite": 50.0, "composite_adj": 50.0}}
    for k, v in mut.items():
        a[k] = v
    return a


# --------------------------------------------- Blocker 严格判定(真值性封死)

class TestStrictPublishablePredicate:
    def test_clean_passes(self):
        assert verify_publishable_archive(_arch(), SEAT_WEIGHTS, COMPOSITE_W) == []
        assert archive_complete(_arch()) is True

    @pytest.mark.parametrize("sv", [NAN, 1, "false", "true", [1], 0, None],
                             ids=["nan", "int1", "str-false", "str-true",
                                  "list", "int0", "none"])
    def test_schema_valid_must_be_literal_true(self, sv):
        """GPT 复现:schema_valid=NaN(重封印后)曾 sealed_ok+archive_complete=True
        +平台 loaded;1/"false" 同理——只有字面 True 算通过。"""
        a = _arch()
        a["bear"]["schema_valid"] = sv
        problems = verify_publishable_archive(a, SEAT_WEIGHTS, COMPOSITE_W)
        assert any("schema_valid" in p for p in problems)
        assert archive_complete(a) is False

    @pytest.mark.parametrize("err", [[], {}, 0, "", False],
                             ids=["list", "dict", "zero", "empty-str", "false"])
    def test_falsey_nonnull_seat_error_flagged(self, err):
        """falsey 非空错误值([]/{}/0/"")曾被真值性当"无错误"。"""
        a = _arch()
        a["seats"]["fund"]["error"] = err
        problems = verify_publishable_archive(a, SEAT_WEIGHTS, COMPOSITE_W)
        assert any("seats[fund]" in p for p in problems)
        assert archive_complete(a) is False

    @pytest.mark.parametrize("err", [[], {}, 0, ""],
                             ids=["list", "dict", "zero", "empty-str"])
    def test_falsey_nonnull_bear_error_flagged(self, err):
        a = _arch()
        a["bear"]["error"] = err
        assert any("bear 带执行错误" in p for p in
                   verify_publishable_archive(a, SEAT_WEIGHTS, COMPOSITE_W))
        assert archive_complete(a) is False

    def test_literal_none_error_is_clean(self):
        """兼容:存量 v2.4-v2.7 档案 error 均为字面 None——必须继续通过。"""
        a = _arch()
        assert a["seats"]["fund"]["error"] is None
        assert verify_publishable_archive(a, SEAT_WEIGHTS, COMPOSITE_W) == []


# --------------------------------------------- Major 共享路由值类型校验

_GOOD_ROUTE = {"model": "doubao-seed-2.0-pro", "thinking": True,
               "temperature": 0.1, "max_tokens": 4000,
               "fallback": "deepseek-v4-pro"}


class TestRouteValueValidation:
    def test_valid_route_passes(self):
        assert verify_llm_route(_GOOD_ROUTE) == []
        assert verify_llm_route({**_GOOD_ROUTE, "thinking": None,
                                 "fallback": None}) == []

    def test_string_thinking_rejected(self):
        """GPT 复现:thinking="False" 是 truthy 字符串——曾静默反转 thinking 语义。"""
        problems = verify_llm_route({**_GOOD_ROUTE, "thinking": "False"})
        assert problems and "thinking" in problems[0]

    @pytest.mark.parametrize("mut,label", [
        ({"model": ""}, "model"),
        ({"model": None}, "model"),
        ({"model": 123}, "model"),
        ({"thinking": 1}, "thinking"),
        ({"thinking": "true"}, "thinking"),
        ({"temperature": NAN}, "temperature"),
        ({"temperature": True}, "temperature"),
        ({"temperature": 3.0}, "temperature"),
        ({"temperature": "0.1"}, "temperature"),
        ({"max_tokens": 0}, "max_tokens"),
        ({"max_tokens": -5}, "max_tokens"),
        ({"max_tokens": True}, "max_tokens"),
        ({"max_tokens": "4000"}, "max_tokens"),
        ({"max_tokens": 4000.0}, "max_tokens"),
        ({"fallback": ""}, "fallback"),
        ({"fallback": 123}, "fallback"),
    ])
    def test_bad_values_rejected(self, mut, label):
        problems = verify_llm_route({**_GOOD_ROUTE, **mut})
        assert problems and label in problems[0]

    def test_missing_keys_and_non_mapping(self):
        assert verify_llm_route({"model": "m"})
        assert verify_llm_route(None)
        assert verify_llm_route("route")

    def test_call_with_config_rejects_bad_values(self, monkeypatch):
        import ai_layer.ark_client as ark
        monkeypatch.setattr(ark, "chat",
                            lambda *a, **k: (_ for _ in ()).throw(
                                AssertionError("不应到达 chat")))
        with pytest.raises(ValueError, match="thinking"):
            L.call_with_config([], {**_GOOD_ROUTE, "thinking": "False"})

    def test_contract_load_rejects_string_thinking(self, tmp_path):
        """GPT 复现:thinking="False" 的自洽 manifest 曾通过 ChainContract.load。"""
        pv = pd.DataFrame({"pv_pack_version": ["pv_v0.2"]})
        retr = pd.DataFrame({"retrieval_profile_snapshot_id": ["s"]})
        regime = pd.DataFrame({"regime_card_version": ["regime_v0.4"]})
        m = build_manifest(pv, retr, regime, read_prompt_bundle(),
                           ["20250127"], ["688981.SH"])
        m["routing"] = json.loads(json.dumps(m["routing"]))
        m["routing"]["scoring"]["thinking"] = "False"
        ensure_immutable_manifest(tmp_path, m)          # 正文自洽
        with pytest.raises(VersionCollisionError, match="thinking"):
            ChainContract.load(tmp_path)
