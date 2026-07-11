# GPT 复审#2 B1 + 复审#3 B1/B2/B3 回归:不可变 manifest(验证不信任)+ 封印 + 严格完整性
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.analyst_chain import (  # noqa: E402
    CHAIN_VERSION, SEAT_WEIGHTS, VersionCollisionError, _allocate_attempt,
    _valid_final, archive_complete, ensure_immutable_manifest,
    verify_existing_archive,
)
from workspace.research.ai_research_dept.engine.integrity import (  # noqa: E402
    REQUIRED_SEAL_FIELDS, archive_seal, input_artifact_fp,
    verify_archive_body, verify_manifest_body,
)


def test_manifest_immutable_and_verify_not_trust(tmp_path):
    m1 = {"chain_version": "chain_vT", "config_hash": "aaa", "prompts_sha16": "p1",
          "created_at": "2026-07-10T00:00:00"}
    out1 = ensure_immutable_manifest(tmp_path, m1)
    assert out1["manifest_fp"]
    # 同内容再入(created_at 不参与指纹)→ 返回原 manifest,不重写
    out2 = ensure_immutable_manifest(
        tmp_path, {**m1, "created_at": "2026-07-11T09:00:00"})
    assert out2["manifest_fp"] == out1["manifest_fp"]
    # 内容漂移 → 硬失败:同版本禁止漂移
    with pytest.raises(VersionCollisionError, match="bump"):
        ensure_immutable_manifest(tmp_path, {**m1, "prompts_sha16": "p2"})
    # 复审#3 B2:篡改磁盘正文、保留自称指纹 → 必须被识破(验证不信任)
    mf = tmp_path / "manifest.json"
    tampered = json.loads(mf.read_text(encoding="utf-8"))
    tampered["config_hash"] = "EVIL"
    mf.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(VersionCollisionError, match="篡改"):
        ensure_immutable_manifest(tmp_path, m1)
    assert verify_manifest_body(tampered)          # 独立校验函数同样识破


def _sealed_archive(manifest_fp="mfp1", **overrides):
    cards = {"fund_card": "F...", "pv_card": "T...", "news_card": "N..."}
    mc = "M..."
    a = {"ts_code": "688981.SH", "date": "20250127", "chain_version": CHAIN_VERSION,
         "manifest_fp": manifest_fp,
         "artifact_fp": input_artifact_fp(cards, mc, manifest_fp),
         "executed_contract_sha256": "ec1",        # v2.5 schema2 必需封印字段
         "cards": cards, "market_context": mc}
    a.update(overrides)
    a["archive_sha256"] = archive_seal(a)
    return a


class TestArchiveVerifyNotTrust:
    def test_clean_archive_passes(self):
        a = _sealed_archive()
        verify_existing_archive(a, "mfp1", a["artifact_fp"], "688981.SH", "20250127")

    def test_tampered_output_body_rejected(self):
        """复审#3 B2:改 judge.composite=99.9 保留旧指纹 → archive_sha256 封印识破。"""
        a = _sealed_archive()
        a["judge"] = {"composite": 99.9}           # 封印后篡改正文
        with pytest.raises(VersionCollisionError, match="封印"):
            verify_existing_archive(a, "mfp1", a["artifact_fp"], "688981.SH", "20250127")

    def test_tampered_cards_rejected(self):
        a = _sealed_archive()
        a["cards"] = {"fund_card": "EVIL", "pv_card": "T...", "news_card": "N..."}
        a["archive_sha256"] = archive_seal(a)   # 重封印
        with pytest.raises(VersionCollisionError, match="artifact_fp 不符"):
            verify_existing_archive(a, "mfp1", a["artifact_fp"], "688981.SH", "20250127")

    def test_input_drift_rejected(self):
        a = _sealed_archive()
        with pytest.raises(VersionCollisionError, match="漂移"):
            verify_existing_archive(a, "mfp1", "different_fp", "688981.SH", "20250127")

    def test_unsealed_legacy_rejected_for_reuse(self):
        a = _sealed_archive()
        del a["archive_sha256"]
        with pytest.raises(VersionCollisionError, match="封印"):
            verify_existing_archive(a, "mfp1", a["artifact_fp"], "688981.SH", "20250127")

    def test_verify_archive_body_structural(self):
        a = _sealed_archive()
        assert verify_archive_body(a, require_sealed=True,
                                   expect_chain=CHAIN_VERSION,
                                   expect_date="20250127",
                                   expect_stem="688981_SH") == []
        assert verify_archive_body(a, expect_chain="chain_v9.9")
        assert verify_archive_body(a, expect_date="20250101")
        assert verify_archive_body(a, expect_stem="000001_SZ")


class TestSealDowngradeClosed:
    """复审#4 B1 复现:删字段+重封印曾把 v2.3 档案降级成 legacy 绕过全部校验。"""

    @pytest.mark.parametrize("field", sorted(REQUIRED_SEAL_FIELDS - {"archive_sha256"}))
    def test_delete_field_and_reseal_rejected(self, field):
        a = _sealed_archive()
        del a[field]
        a["archive_sha256"] = archive_seal(a)      # 重封印(GPT 的攻击方式)
        problems = verify_archive_body(a, require_sealed=True)
        assert problems and "缺少必需封印字段" in problems[0]
        with pytest.raises(VersionCollisionError, match="缺少必需封印字段"):
            verify_existing_archive(a, "mfp1", a.get("artifact_fp", "x"),
                                    "688981.SH", "20250127")

    def test_delete_seal_itself_rejected(self):
        a = _sealed_archive()
        del a["archive_sha256"]
        problems = verify_archive_body(a, require_sealed=True)
        assert problems and "缺少必需封印字段" in problems[0]

    def test_sealed_required_manifest_without_fp_rejected(self):
        assert verify_manifest_body({"chain_version": "x", "sealed_required": True})


class TestTotalFunctions:
    @pytest.mark.parametrize("bad", [
        True, None, "50", float("nan"), float("inf"), -1, 101,
        pytest.param(10**10000, id="huge-int"), [50]])
    def test_valid_final_never_raises(self, bad):
        assert _valid_final(bad) is False

    def test_valid_final_accepts_range(self):
        assert _valid_final(0) and _valid_final(50.0) and _valid_final(100)

    def test_archive_complete_total(self):
        a = _full_arch()
        a["seats"]["fund"] = "not a dict"
        assert archive_complete(a) is False
        b = _full_arch()
        b["seats"]["fund"]["final"] = 10**10000
        assert archive_complete(b) is False


def test_allocate_attempt_sparse_numbering(tmp_path):
    """复审#4 Major-1 复现:目录 {0001,0003} 时曾再次分配 0003(计数式)。"""
    (tmp_path / "attempt_0001").mkdir(parents=True)
    (tmp_path / "attempt_0003").mkdir(parents=True)
    no, d = _allocate_attempt(tmp_path)
    assert no == 4 and d.name == "attempt_0004" and d.exists()
    no2, d2 = _allocate_attempt(tmp_path)
    assert no2 == 5 and d2.name == "attempt_0005"


def _full_arch(**mut):
    seats = {s: {"final": 50.0, "error": None} for s in SEAT_WEIGHTS}
    a = {"seats": seats,
         "records": {s: {"factor_scores": []} for s in SEAT_WEIGHTS},
         "bear": {"refutations": [], "kill_switches": ["k"], "blind_spots": [],
                  "schema_valid": True, "parse_mode": "strict"},
         # v2.5 语义校验:judge.finals 必须与 seats 一致,composite 必须可按契约
         # 权重重算(全席 50 → composite 50)
         "judge": {"finals": {s: 50.0 for s in SEAT_WEIGHTS},
                   "composite": 50.0, "composite_adj": 50.0}}
    for k, v in mut.items():
        a[k] = v
    return a


class TestArchiveCompleteStrict:
    def test_full_archive_complete(self):
        assert archive_complete(_full_arch())

    def test_missing_seat_incomplete(self):
        """复审#3 B3 复现:一个席位、没有 bear 曾被判完整。"""
        a = _full_arch()
        a["seats"] = {"fund": {"final": 50.0, "error": None}}
        assert not archive_complete(a)

    def test_empty_bear_dict_incomplete(self):
        assert not archive_complete(_full_arch(bear={}))

    def test_bear_schema_invalid_incomplete(self):
        a = _full_arch()
        a["bear"]["schema_valid"] = False
        assert not archive_complete(a)

    def test_bear_no_kill_switch_incomplete(self):
        a = _full_arch()
        a["bear"]["kill_switches"] = []
        assert not archive_complete(a)

    def test_bear_bad_parse_mode_incomplete(self):
        a = _full_arch()
        a["bear"]["parse_mode"] = None
        assert not archive_complete(a)

    def test_seat_error_or_bad_final_incomplete(self):
        a = _full_arch()
        a["seats"]["tech"]["error"] = "x"
        assert not archive_complete(a)
        b = _full_arch()
        b["seats"]["news"]["final"] = float("nan")
        assert not archive_complete(b)
        c = _full_arch()
        c["seats"]["fund"]["final"] = True          # bool 不是合法 final
        assert not archive_complete(c)

    def test_records_missing_incomplete(self):
        a = _full_arch()
        del a["records"]["tech"]
        assert not archive_complete(a)

    def test_judge_missing_seat_incomplete(self):
        a = _full_arch()
        a["judge"] = {"finals": {"fund": 50.0}}
        assert not archive_complete(a)
