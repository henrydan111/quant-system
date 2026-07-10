# GPT REVISE Blocker-1/3/4 回归:机械围栏 + 空头 typed 校验 + 版本一致性
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.validators import (  # noqa: E402
    enforce_v2_evidence, line_map, span_line_id, validate_bear_record,
)

CARD = "\n".join([
    "【基本面三锚定事实表】(说明行,无 ID)",
    "- [F01]ROE(加权)%: 1.9|行业分位35%(468家)|10年分位33%",
    "- [F04]⚑经营现金流/营收: 0.29|行业分位94%(470家)|10年分位22%",
    "- [FD1]披露动态: 检索窗口内无业绩预告/快报(本行只可支撑 earnings_inflection)",
])
NEWS_CARD = "\n".join([
    "【检索装配单】",
    "- [ND01][3日前|★★]研报点评|某研报标题|中性",
    "- [NI01][概念|当日|★★★★]业绩预告|688519.SH 业绩预告:扭亏 134.8%~147.9%|显著利好|相关度0.49",
    "- [NIA1][概念聚合]业绩预告: 返回集内另有22条(严重利空11/显著利好11)——聚合行属间接证据,封顶3分",
])
F01 = "- [F01]ROE(加权)%: 1.9|行业分位35%(468家)|10年分位33%"
F04 = "- [F04]⚑经营现金流/营收: 0.29|行业分位94%(470家)|10年分位22%"
SEAT_W = {"fund": {"profitability_quality": 6, "earnings_inflection": 4},
          "news": {"event_materiality": 6, "novelty": 5}}


def test_line_map_and_exact_matching():
    lm = line_map(CARD)
    assert set(lm) == {"F01", "F04", "FD1"}
    assert span_line_id(F01, lm) == "F01"
    assert span_line_id(F01.lstrip("- "), lm) == "F01"          # 可省行首'- '
    assert span_line_id("[F01]ROE(加权)%: 1.9", lm) is None       # 截取片段拒收
    assert span_line_id("ROE 很好", lm) is None                   # 无 ID 拒收
    assert span_line_id("[F99]" + F01[7:], lm) is None            # 假 ID 拒收


def test_exclusivity_by_line_id():
    rec = {"factor_scores": [
        {"name": "profitability_quality", "evidence_spans": [F01], "score_0_5": 4},
        {"name": "earnings_inflection", "evidence_spans": [F01], "score_0_5": 4}],
        "penalty_scores": []}
    enforce_v2_evidence(rec, CARD, "fund")
    assert rec["factor_scores"][0]["evidence_spans"] == [F01]
    assert rec["factor_scores"][1]["evidence_spans"] == []      # 复用被剔除


def test_disclosure_fence():
    fd = "- [FD1]披露动态: 检索窗口内无业绩预告/快报(本行只可支撑 earnings_inflection)"
    rec = {"factor_scores": [
        {"name": "profitability_quality", "evidence_spans": [fd], "score_0_5": 5}],
        "penalty_scores": []}
    enforce_v2_evidence(rec, CARD, "fund")
    assert rec["factor_scores"][0]["evidence_spans"] == []
    assert rec["_fence_stats"]["dropped_disclosure_fence"] == 1


def test_news_indirect_clamp():
    ni = ("- [NI01][概念|当日|★★★★]业绩预告|688519.SH 业绩预告:扭亏 134.8%~147.9%"
          "|显著利好|相关度0.49")
    rec = {"factor_scores": [
        {"name": "event_materiality", "evidence_spans": [ni], "score_0_5": 5}],
        "penalty_scores": []}
    enforce_v2_evidence(rec, NEWS_CARD, "news")
    assert rec["factor_scores"][0]["score_0_5"] == 3            # 确定性钳位
    assert rec["_fence_stats"]["indirect_clamped"] == ["event_materiality"]


def test_bear_strength_999_and_substring_rejected():
    rec = {"refutations": [
        {"target_seat": "fund", "target_dim": "profitability_quality",
         "claim": "x", "counter_quote": F04, "strength_0_5": 999, "reason": "y"},
        {"target_seat": "fund", "target_dim": "profitability_quality",
         "claim": "x", "counter_quote": "经营现金流/营收: 0.29", "strength_0_5": 4,
         "reason": "y"},
        {"target_seat": "ghost", "target_dim": "profitability_quality",
         "claim": "x", "counter_quote": F04, "strength_0_5": 4, "reason": "y"},
        {"target_seat": "fund", "target_dim": "not_a_dim",
         "claim": "x", "counter_quote": F04, "strength_0_5": 4, "reason": "y"}],
        "kill_switches": ["k"], "blind_spots": []}
    out = validate_bear_record(rec, CARD, SEAT_W, set())
    assert out["refutations"] == []                             # 999/子串/配对全拒
    assert out["validation_dropped"]["strength"] == 1
    assert out["validation_dropped"]["quote"] == 1
    assert out["validation_dropped"]["pairing"] == 2


def test_bear_falsifier_fast_path():
    ref = {"target_seat": "fund", "target_dim": "profitability_quality",
           "claim": "x", "counter_quote": F04, "strength_0_5": 5, "reason": "证伪条件命中"}
    # 无有效 falsifier_id → 降级 4
    out = validate_bear_record({"refutations": [dict(ref)]}, CARD, SEAT_W, {"fund-0"})
    assert out["refutations"][0]["strength_0_5"] == 4
    # 有效 falsifier_id → 保 5
    out = validate_bear_record(
        {"refutations": [dict(ref, falsifier_id="fund-0")]}, CARD, SEAT_W, {"fund-0"})
    assert out["refutations"][0]["strength_0_5"] == 5
    assert out["refutations"][0]["falsifier_id"] == "fund-0"


def test_platform_render_version_matches_chain():
    """平台 RENDER_VERSION 必须与链 CHAIN_VERSION 一致(平台禁 import 编排模块,
    一致性由本测试而非运行时 import 保证)。"""
    chain_src = (ROOT / "workspace/research/ai_research_dept/engine/analyst_chain.py"
                 ).read_text(encoding="utf-8")
    server_src = (ROOT / "workspace/research/ai_research_dept/platform/server.py"
                  ).read_text(encoding="utf-8")
    import re
    cv = re.search(r'CHAIN_VERSION = "([^"]+)"', chain_src).group(1)
    rv = re.search(r'RENDER_VERSION = "([^"]+)"', server_src).group(1)
    assert cv == rv, f"chain={cv} platform={rv}"


def test_archive_version_isolation_layout():
    """档案必须住版本目录且带 manifest(Blocker-1);裸日期目录=违规布局。"""
    chain_dir = ROOT / "workspace/outputs/ai_research_dept/analyst_chain"
    if not chain_dir.exists():
        return
    for child in chain_dir.iterdir():
        if child.is_dir():
            assert child.name.startswith("chain_v"), f"裸目录违规: {child}"
            assert (child / "manifest.json").exists(), f"缺 manifest: {child}"
            mf = json.loads((child / "manifest.json").read_text(encoding="utf-8"))
            assert mf.get("chain_version") == child.name
