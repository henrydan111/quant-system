# GPT 复审#5 回归:B1 契约防伪造 / B2 平台自声明降级封死 / B3 完成范围绑定 +
# Major-1 缺输入必抛 / Major-2 _safe_error / Major-3 共享语义校验
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.analyst_chain import (  # noqa: E402
    CHAIN_VERSION, COMPOSITE_W, SEAT_WEIGHTS, ChainContract,
    MissingInputError, VersionCollisionError, _safe_error, archive_complete,
    build_manifest, ensure_immutable_manifest, read_prompt_bundle,
    verify_contract_matches_manifest, verify_existing_archive,
)
from workspace.research.ai_research_dept.engine.integrity import (  # noqa: E402
    REQUIRED_SEAL_FIELDS, REQUIRED_SEAL_FIELDS_SCHEMA1, archive_seal,
    input_artifact_fp, required_seal_fields, sha256_json, verify_archive_body,
    verify_archive_semantics,
)


def _frames():
    pv = pd.DataFrame({"pv_pack_version": ["pv_v0.2"]})
    retr = pd.DataFrame({"retrieval_profile_snapshot_id": ["snap1"]})
    regime = pd.DataFrame({"regime_card_version": ["regime_v0.4"]})
    return pv, retr, regime


def _manifest(days=("20250127",), codes=("688981.SH",)):
    pv, retr, regime = _frames()
    return build_manifest(pv, retr, regime, read_prompt_bundle(),
                          list(days), list(codes))


# ------------------------------------------------------------- B1 契约防伪造

class TestContractForgeryClosed:
    def test_load_roundtrip(self, tmp_path):
        ensure_immutable_manifest(tmp_path, _manifest())
        c = ChainContract.load(tmp_path)
        assert c.manifest_fp and len(c.manifest_sha256) == 64
        verify_contract_matches_manifest(c, tmp_path)   # 自身对盘复核通过

    def test_forged_contract_rejected_at_run_boundary(self, tmp_path):
        """伪造构造器 + 真 manifest 指纹:直接实例化 ChainContract 改评分参数,
        run_stock 端 verify_contract_matches_manifest 必须识破。"""
        ensure_immutable_manifest(tmp_path, _manifest())
        real = ChainContract.load(tmp_path)
        evil_scoring = {k: v for k, v in dict(real.scoring).items()}
        evil_scoring["bear_discount_strength"] = 999    # 让空头折减永不触发
        forged = ChainContract(manifest_fp=real.manifest_fp,
                               manifest_sha256=real.manifest_sha256,
                               effective_prompts=real.effective_prompts,
                               scoring=evil_scoring, routing=real.routing)
        with pytest.raises(VersionCollisionError, match="伪造"):
            verify_contract_matches_manifest(forged, tmp_path)

    def test_contract_scoring_is_read_only(self, tmp_path):
        ensure_immutable_manifest(tmp_path, _manifest())
        c = ChainContract.load(tmp_path)
        with pytest.raises(TypeError):
            c.scoring["seat_weights"]["fund"]["盈利质量"] = 99.0
        with pytest.raises(TypeError):
            c.effective_prompts["fund_analyst_v2.txt"] = "EVIL"

    def test_load_rejects_downgraded_manifest(self, tmp_path):
        """sealed_required=False / schema=1 的 manifest 不可作 v2.5 执行契约。"""
        m = _manifest()
        for mutate in ({"sealed_required": False}, {"integrity_schema": 1}):
            bad = {**m, **mutate}
            vdir = tmp_path / str(sorted(mutate))
            vdir.mkdir()
            ensure_immutable_manifest(vdir, bad)
            with pytest.raises(VersionCollisionError, match="契约构造被拒"):
                ChainContract.load(vdir)

    def test_load_rejects_prompt_hash_mismatch(self, tmp_path):
        m = _manifest()
        m["effective_prompts"] = dict(m["effective_prompts"])
        first = next(iter(m["effective_prompts"]))
        m["effective_prompts"][first] = m["effective_prompts"][first] + "\nEVIL"
        ensure_immutable_manifest(tmp_path, m)          # 正文自洽(指纹重算)
        with pytest.raises(VersionCollisionError, match="prompt 哈希"):
            ChainContract.load(tmp_path)

    def test_archive_missing_executed_contract_rejected(self):
        cards = {"fund_card": "F", "pv_card": "T", "news_card": "N"}
        a = {"ts_code": "688981.SH", "date": "20250127",
             "chain_version": CHAIN_VERSION, "manifest_fp": "mfp1",
             "artifact_fp": input_artifact_fp(cards, "M", "mfp1"),
             "cards": cards, "market_context": "M"}
        a["archive_sha256"] = archive_seal(a)
        with pytest.raises(VersionCollisionError, match="executed_contract_sha256"):
            verify_existing_archive(a, "mfp1", a["artifact_fp"],
                                    "688981.SH", "20250127", "sha_of_manifest")

    def test_archive_wrong_executed_contract_rejected(self):
        cards = {"fund_card": "F", "pv_card": "T", "news_card": "N"}
        a = {"ts_code": "688981.SH", "date": "20250127",
             "chain_version": CHAIN_VERSION, "manifest_fp": "mfp1",
             "artifact_fp": input_artifact_fp(cards, "M", "mfp1"),
             "executed_contract_sha256": "OTHER_CONTRACT",
             "cards": cards, "market_context": "M"}
        a["archive_sha256"] = archive_seal(a)
        with pytest.raises(VersionCollisionError, match="执行契约"):
            verify_existing_archive(a, "mfp1", a["artifact_fp"],
                                    "688981.SH", "20250127", "sha_of_manifest")


# --------------------------------------------------- B2 封印 schema 分级(平台)

class TestSealSchemaTiers:
    def test_schema_tiers(self):
        assert "executed_contract_sha256" not in required_seal_fields(1)
        assert "executed_contract_sha256" in required_seal_fields(2)
        assert required_seal_fields(1) == REQUIRED_SEAL_FIELDS_SCHEMA1
        assert required_seal_fields(2) == REQUIRED_SEAL_FIELDS

    def test_schema1_sealed_archive_still_verifies(self):
        """v2.4 真封印档案(无 executed_contract)在 schema=1 下仍通过,
        在 schema=2(现行)下被拒——新字段不追溯、也不放行新档案。"""
        cards = {"fund_card": "F", "pv_card": "T", "news_card": "N"}
        a = {"ts_code": "688981.SH", "date": "20250127",
             "chain_version": "chain_v2.4", "manifest_fp": "mfp1",
             "artifact_fp": input_artifact_fp(cards, "M", "mfp1"),
             "cards": cards, "market_context": "M"}
        a["archive_sha256"] = archive_seal(a)
        assert verify_archive_body(a, require_sealed=True, seal_schema=1) == []
        assert verify_archive_body(a, require_sealed=True, seal_schema=2)


# ------------------------------------------------------- B3 完成范围绑定

class TestJobSpecScope:
    def test_manifest_binds_full_month_scope(self):
        m = _manifest(days=("20250127", "20250128"), codes=("A.SH", "B.SZ"))
        js = m["job_spec"]
        assert js["scope_kind"] == "full_month"
        assert js["expected"] == 4
        assert js["job_set_sha256"] == sha256_json(
            {"days": ["20250127", "20250128"], "codes": ["A.SH", "B.SZ"]})

    def test_smoke_scope_never_matches_job_spec(self):
        """烟测(子集 日/股)的范围摘要 ≠ manifest job_spec——
        full_month_status.json 的写入条件机械不成立。"""
        m = _manifest(days=("20250127", "20250128"), codes=("A.SH", "B.SZ"))
        smoke = sha256_json({"days": ["20250127"], "codes": ["A.SH"]})
        assert smoke != m["job_spec"]["job_set_sha256"]


# ----------------------------------------------- Major-1/2 缺输入 + 错误总函数

class TestTotalErrorHandling:
    def test_missing_input_is_typed_error(self):
        assert issubclass(MissingInputError, RuntimeError)

    def test_safe_error_huge_int(self):
        msg = _safe_error(RuntimeError(10**10000))
        assert isinstance(msg, str) and msg.startswith("RuntimeError")

    def test_safe_error_normal(self):
        assert _safe_error(ValueError("boom")) == "ValueError: boom"


# ------------------------------------------------- Major-3 共享语义校验

def _sem_arch():
    return {"seats": {s: {"final": 50.0, "error": None} for s in SEAT_WEIGHTS},
            "records": {s: {"factor_scores": []} for s in SEAT_WEIGHTS},
            "bear": {"refutations": [], "kill_switches": ["k"],
                     "blind_spots": [], "schema_valid": True,
                     "parse_mode": "strict"},
            "judge": {"finals": {s: 50.0 for s in SEAT_WEIGHTS},
                      "composite": 50.0, "composite_adj": 50.0}}


class TestArchiveSemantics:
    def test_clean_passes(self):
        assert verify_archive_semantics(_sem_arch(), SEAT_WEIGHTS, COMPOSITE_W) == []
        assert archive_complete(_sem_arch())

    def test_empty_records_entry_flagged(self):
        """GPT 复现:records 条目缺 factor_scores 曾静默通过。"""
        a = _sem_arch()
        a["records"]["fund"] = {}
        assert verify_archive_semantics(a, SEAT_WEIGHTS, COMPOSITE_W)
        assert not archive_complete(a)

    def test_string_kill_switches_flagged(self):
        """GPT 复现:kill_switches="k"(字符串,可迭代)曾冒充非空列表。"""
        a = _sem_arch()
        a["bear"]["kill_switches"] = "k"
        assert verify_archive_semantics(a, SEAT_WEIGHTS, COMPOSITE_W)
        assert not archive_complete(a)
        b = _sem_arch()
        b["bear"]["kill_switches"] = [1, 2]
        assert not archive_complete(b)

    def test_judge_seat_mismatch_flagged(self):
        """GPT 复现:judge.finals 与 seats.final 不一致曾静默通过。"""
        a = _sem_arch()
        a["judge"]["finals"]["fund"] = 99.0
        assert verify_archive_semantics(a, SEAT_WEIGHTS, COMPOSITE_W)
        assert not archive_complete(a)

    def test_forged_composite_flagged(self):
        a = _sem_arch()
        a["judge"]["composite"] = 88.8       # 与契约权重重算 50.0 不符
        assert any("composite" in p for p in
                   verify_archive_semantics(a, SEAT_WEIGHTS, COMPOSITE_W))
        assert not archive_complete(a)

    def test_bear_refutations_non_dict_flagged(self):
        a = _sem_arch()
        a["bear"]["refutations"] = ["not a dict"]
        assert verify_archive_semantics(a, SEAT_WEIGHTS, COMPOSITE_W)

    def test_composite_adj_range(self):
        a = _sem_arch()
        a["judge"]["composite_adj"] = float("nan")
        assert verify_archive_semantics(a, SEAT_WEIGHTS, COMPOSITE_W)


# --------------------------------------------------- 平台分级(读 server 常量)

def test_platform_render_version_matches_chain():
    sys.path.insert(0, str(ROOT))
    from workspace.research.ai_research_dept.platform import server
    assert server.RENDER_VERSION == CHAIN_VERSION
    assert CHAIN_VERSION not in server.LEGACY_CHAINS
    assert "chain_v2.4" not in server.LEGACY_CHAINS   # v2.4 已封印,非 legacy
