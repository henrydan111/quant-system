# GPT 复审#1/#2 回归:机械围栏 + 空头 typed 校验 + 版本一致性 + 漂移防护
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.validators import (  # noqa: E402
    _news_requires_cap, enforce_v2_evidence, line_map, span_line_id,
    validate_bear_record,
)

CARD = "\n".join([
    "【基本面三锚定事实表】(说明行,无 ID)",
    "- [F01]ROE(加权)%: 1.9|行业分位35%(468家)|10年分位33%",
    "- [F04]⚑经营现金流/营收: 0.29|行业分位94%(470家)|10年分位22%",
    "- [FD1]披露动态: 检索窗口内无业绩预告/快报(本行只可支撑 earnings_inflection)",
])
NEWS_CARD = "\n".join([
    "【检索装配单】",
    "- [N00]检索窗口全景: 直接事件 3 条,间接事件 25 条(检索返回集)",
    "- [ND01][3日前|★★]研报点评|某研报标题|中性",
    "- [NDA1][直接聚合|当日~9日前]互动易-产能: 另有4条(中性4)",
    "- [NI01][概念|当日|★★★★]业绩预告|688519.SH 业绩预告:扭亏 134.8%~147.9%|显著利好|相关度0.49",
    "- [NI02][关联|2日前|★★★]重组/并购|某关联公司重组|轻微利好|相关度0.35",
    "- [NIA1][概念聚合|当日~5日前]业绩预告: 返回集内另有22条(严重利空11/显著利好11)——聚合行属间接证据,封顶3分",
])
F01 = "- [F01]ROE(加权)%: 1.9|行业分位35%(468家)|10年分位33%"
F04 = "- [F04]⚑经营现金流/营收: 0.29|行业分位94%(470家)|10年分位22%"
SEAT_W = {"fund": {"profitability_quality": 6, "earnings_inflection": 4},
          "news": {"event_materiality": 6, "novelty": 5}}
FALS = {"fund-0": {"seat": "fund", "observable_in": "fund"}}


def test_line_map_and_exact_matching():
    lm = line_map(CARD)
    assert set(lm) == {"F01", "F04", "FD1"}
    assert span_line_id(F01, lm) == "F01"
    assert span_line_id(F01.lstrip("- "), lm) == "F01"          # 可省行首'- '
    assert span_line_id("[F01]ROE(加权)%: 1.9", lm) is None       # 截取片段拒收
    assert span_line_id("ROE 很好", lm) is None                   # 无 ID 拒收
    assert span_line_id("[F99]" + F01[7:], lm) is None            # 假 ID 拒收
    assert span_line_id(["not", "a", "str"], lm) is None          # 非字符串拒收


def test_exclusivity_two_pass_order_independent():
    """复审#2 Major-1:被争用的行 ID 在所有条目中一律作废——与条目顺序无关。"""
    def rec(order):
        fs = [{"name": "profitability_quality", "evidence_spans": [F01], "score_0_5": 4},
              {"name": "earnings_inflection", "evidence_spans": [F01], "score_0_5": 4}]
        return {"factor_scores": fs if order else fs[::-1], "penalty_scores": []}
    for order in (True, False):
        r = enforce_v2_evidence(rec(order), CARD, "fund")
        assert all(e["evidence_spans"] == [] for e in r["factor_scores"]), \
            "争用 ID 必须两边皆废"
        assert r["_fence_stats"]["contested_ids"] == ["F01"]
        assert r["_fence_stats"]["dropped_exclusive"] == 2


def test_uncontested_evidence_survives():
    rec = {"factor_scores": [
        {"name": "profitability_quality", "evidence_spans": [F01], "score_0_5": 4},
        {"name": "earnings_inflection", "evidence_spans": [F04], "score_0_5": 4}],
        "penalty_scores": []}
    enforce_v2_evidence(rec, CARD, "fund")
    assert rec["factor_scores"][0]["evidence_spans"] == [F01]
    assert rec["factor_scores"][1]["evidence_spans"] == [F04]


def test_disclosure_fence():
    fd = "- [FD1]披露动态: 检索窗口内无业绩预告/快报(本行只可支撑 earnings_inflection)"
    rec = {"factor_scores": [
        {"name": "profitability_quality", "evidence_spans": [fd], "score_0_5": 5}],
        "penalty_scores": []}
    enforce_v2_evidence(rec, CARD, "fund")
    assert rec["factor_scores"][0]["evidence_spans"] == []
    assert rec["_fence_stats"]["dropped_disclosure_fence"] == 1


class TestNewsCapByIdClass:
    """复审#2 B4:钳位按注册 ID 类,非渲染词(NDA 直接聚合曾以 5 分漏网)。"""

    @pytest.mark.parametrize("lid,expect", [
        ("N00", True), ("NI01", True), ("NI12", True), ("NIA1", True),
        ("NDA1", True), ("ND01", False), ("ND12", False), ("NX01", False)])
    def test_predicate(self, lid, expect):
        assert _news_requires_cap(lid) is expect

    @pytest.mark.parametrize("span", [
        "- [NDA1][直接聚合|当日~9日前]互动易-产能: 另有4条(中性4)",
        "- [NI02][关联|2日前|★★★]重组/并购|某关联公司重组|轻微利好|相关度0.35",
        "- [NIA1][概念聚合|当日~5日前]业绩预告: 返回集内另有22条(严重利空11/显著利好11)——聚合行属间接证据,封顶3分",
        "- [N00]检索窗口全景: 直接事件 3 条,间接事件 25 条(检索返回集)"])
    def test_clamped_to_3(self, span):
        rec = {"factor_scores": [
            {"name": "event_materiality", "evidence_spans": [span], "score_0_5": 5}],
            "penalty_scores": []}
        enforce_v2_evidence(rec, NEWS_CARD, "news")
        assert rec["factor_scores"][0]["score_0_5"] == 3

    def test_direct_detail_not_clamped(self):
        nd = "- [ND01][3日前|★★]研报点评|某研报标题|中性"
        rec = {"factor_scores": [
            {"name": "event_materiality", "evidence_spans": [nd], "score_0_5": 5}],
            "penalty_scores": []}
        enforce_v2_evidence(rec, NEWS_CARD, "news")
        assert rec["factor_scores"][0]["score_0_5"] == 5


class TestBearPerEntryRobustness:
    """复审#2 B3:单条畸形绝不清空整只空头(list 值曾触发 TypeError)。"""

    def _base(self, **kw):
        d = {"target_seat": "fund", "target_dim": "profitability_quality",
             "claim": "x", "counter_quote": F04, "strength_0_5": 4, "reason": "y"}
        d.update(kw)
        return d

    def test_malformed_values_dropped_individually(self):
        rec = {"refutations": [
            self._base(target_seat=["fund"]),          # list 席位 → pairing drop
            self._base(target_dim={"a": 1}),           # dict 维度 → pairing drop
            self._base(strength_0_5="4"),              # 字符串强度 → strength drop
            self._base(strength_0_5=True),             # bool 强度 → strength drop
            self._base(strength_0_5=float("nan")),     # NaN → strength drop
            self._base(strength_0_5=999),              # 域外 → strength drop
            self._base(falsifier_id=["fund-0"], strength_0_5=5),  # list fid → 降4仍保留
            self._base(),                              # 合法条 → 保留
        ], "kill_switches": "不是列表", "blind_spots": {"x": 1}}
        out = validate_bear_record(rec, CARD, SEAT_W, FALS)
        assert len(out["refutations"]) == 2            # 合法条 + list-fid 降级条
        assert all(r["strength_0_5"] == 4 for r in out["refutations"])
        assert out["kill_switches"] == [] and out["blind_spots"] == []
        d = out["validation_dropped"]
        assert d["pairing"] == 2 and d["strength"] == 4
        assert d["falsifier_downgraded"] == 1

    def test_quote_substring_and_pairing_rejected(self):
        rec = {"refutations": [
            self._base(counter_quote="经营现金流/营收: 0.29"),
            self._base(target_seat="ghost"),
            self._base(target_dim="not_a_dim")]}
        out = validate_bear_record(rec, CARD, SEAT_W, FALS)
        assert out["refutations"] == []
        assert out["validation_dropped"]["quote"] == 1
        assert out["validation_dropped"]["pairing"] == 2

    def test_falsifier_fast_path_requires_seat_binding(self):
        ok = self._base(strength_0_5=5, falsifier_id="fund-0")
        out = validate_bear_record({"refutations": [dict(ok)]}, CARD, SEAT_W, FALS)
        assert out["refutations"][0]["strength_0_5"] == 5
        # 席位不绑定(news 席引用 fund 的证伪)→ 降 4
        cross = self._base(strength_0_5=5, falsifier_id="fund-0",
                           target_seat="news", target_dim="novelty",
                           counter_quote="- [ND01][3日前|★★]研报点评|某研报标题|中性")
        out = validate_bear_record({"refutations": [cross]}, NEWS_CARD, SEAT_W, FALS)
        assert out["refutations"][0]["strength_0_5"] == 4

    def test_falsifier_fast_path_requires_domain_match(self):
        """复审#3 minor:observable_in=fund 的证伪引用 M 行(market 域)不再保 5。"""
        card_m = CARD + "\n- [M01]指数: 上证-0.1% 沪深300-0.4%"
        ref = self._base(strength_0_5=5, falsifier_id="fund-0",
                         counter_quote="- [M01]指数: 上证-0.1% 沪深300-0.4%")
        out = validate_bear_record({"refutations": [ref]}, card_m, SEAT_W, FALS)
        assert out["refutations"][0]["strength_0_5"] == 4

    def test_overflow_strength_dropped_individually(self):
        """复审#3 Major:10**10000 是 Real 但 float() 溢出——单条 drop,兄弟保留。"""
        rec = {"refutations": [self._base(strength_0_5=10**10000), self._base()],
               "kill_switches": ["k"], "blind_spots": []}
        out = validate_bear_record(rec, CARD, SEAT_W, FALS)
        assert len(out["refutations"]) == 1
        assert out["validation_dropped"]["strength"] == 1
        assert out["schema_valid"] is True

    def test_schema_valid_flag(self):
        """复审#3 B3:顶层容器损坏必须标记 schema_valid=False(不得伪装空但正常)。"""
        out = validate_bear_record({"refutations": {"not": "a list"},
                                    "kill_switches": ["k"], "blind_spots": []},
                                   CARD, SEAT_W, FALS)
        assert out["schema_valid"] is False and out["refutations"] == []
        out2 = validate_bear_record({"refutations": [], "kill_switches": "str",
                                     "blind_spots": []}, CARD, SEAT_W, FALS)
        assert out2["schema_valid"] is False


def test_platform_render_version_matches_chain():
    chain_src = (ROOT / "workspace/research/ai_research_dept/engine/analyst_chain.py"
                 ).read_text(encoding="utf-8")
    server_src = (ROOT / "workspace/research/ai_research_dept/platform/server.py"
                  ).read_text(encoding="utf-8")
    import re
    cv = re.search(r'CHAIN_VERSION = "([^"]+)"', chain_src).group(1)
    rv = re.search(r'RENDER_VERSION = "([^"]+)"', server_src).group(1)
    assert cv == rv, f"chain={cv} platform={rv}"


def test_archive_version_isolation_layout():
    chain_dir = ROOT / "workspace/outputs/ai_research_dept/analyst_chain"
    if not chain_dir.exists():
        return
    for child in chain_dir.iterdir():
        if child.is_dir():
            assert child.name.startswith("chain_v"), f"裸目录违规: {child}"
            assert (child / "manifest.json").exists(), f"缺 manifest: {child}"
            mf = json.loads((child / "manifest.json").read_text(encoding="utf-8"))
            assert mf.get("chain_version") == child.name


def test_raw_path_traversal_rejected():
    """复审#2 Major-2:day=../chain_v1.0/... 跨版本注入必须被拒。"""
    from workspace.research.ai_research_dept.platform.server import safe_raw_dir
    base = ROOT / "workspace/outputs/ai_research_dept/analyst_chain"
    chains = {"chain_v1.0", "chain_v2.2"}
    assert safe_raw_dir(base, chains, "chain_v2.2",
                        "../chain_v1.0/20250127", "688981.SH") is None
    assert safe_raw_dir(base, chains, "chain_vX", "20250127", "688981.SH") is None
    assert safe_raw_dir(base, chains, "chain_v2.2", "20250127", "..\\..\\etc") is None
    ok = safe_raw_dir(base, chains, "chain_v2.2", "20250127", "688981.SH")
    assert ok is not None and "chain_v2.2" in str(ok)
