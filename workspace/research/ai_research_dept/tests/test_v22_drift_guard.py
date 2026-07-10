# GPT 复审#2 B1 回归:不可变 manifest + artifact_fp 输入绑定 + 完整性感知复用
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.analyst_chain import (  # noqa: E402
    VersionCollisionError, archive_complete, ensure_immutable_manifest,
)


def test_manifest_immutable(tmp_path):
    m1 = {"chain_version": "chain_vT", "config_hash": "aaa", "prompts_sha16": "p1",
          "created_at": "2026-07-10T00:00:00"}
    out1 = ensure_immutable_manifest(tmp_path, m1)
    assert out1["manifest_fp"]
    # 同内容再入(created_at 不参与指纹)→ 返回原 manifest,不重写
    out2 = ensure_immutable_manifest(
        tmp_path, {**m1, "created_at": "2026-07-11T09:00:00"})
    assert out2["manifest_fp"] == out1["manifest_fp"]
    # 内容漂移(prompt 哈希变了)→ 硬失败:同版本禁止漂移
    with pytest.raises(VersionCollisionError, match="bump"):
        ensure_immutable_manifest(tmp_path, {**m1, "prompts_sha16": "p2"})
    # 磁盘上仍是首个 manifest
    on_disk = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk["manifest_fp"] == out1["manifest_fp"]


def _arch(seat_err=None, seat_final=50.0, bear_err=None):
    return {"seats": {"fund": {"final": seat_final, "error": seat_err},
                      "tech": {"final": 40.0, "error": None}},
            "bear": ({"error": bear_err} if bear_err else {"refutations": []})}


def test_archive_complete_semantics():
    assert archive_complete(_arch())
    assert not archive_complete(_arch(seat_err="ScorecardViolation: x"))
    assert not archive_complete(_arch(seat_final=None))
    assert not archive_complete(_arch(bear_err="ArkClientError: y"))    # 空空头不可固化
    assert not archive_complete({"seats": {}, "bear": {}})
