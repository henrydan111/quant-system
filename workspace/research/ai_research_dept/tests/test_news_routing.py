# NF wave §7 step 3-routing/4: alias registry + 3-way router + scoring_owner (deterministic).
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_routing import (  # noqa: E402
    ScoringOwnershipError, build_alias_registry, route_cluster, scoring_owner,
)


def _basic():
    return pd.DataFrame([
        {"name": "中芯国际", "ts_code": "688981.SH"},
        {"name": "平安银行", "ts_code": "000001.SZ"},
        {"name": "贵州茅台", "ts_code": "600519.SH"},
        # duplicate name -> ambiguous -> must NOT link
        {"name": "国泰", "ts_code": "601211.SH"},
        {"name": "国泰", "ts_code": "020001.SZ"},
    ])


def _reg():
    return build_alias_registry(_basic(), version="alias_v1",
                                valid_from="2025-01-01",
                                hk_seed={"00981.HK": "688981.SH"})


IND = frozenset({"半导体", "白酒", "银行"})
CON = frozenset({"国产替代", "光刻机"})


# --------------------------------------------------- alias registry (M4)

class TestAliasRegistry:
    def test_version_and_hash_sealed(self):
        r = _reg()
        assert r.version == "alias_v1" and len(r.content_hash) == 16

    def test_bare_a_code_linked(self):
        codes, _ = _reg().resolve_codes("传闻 600519 涨停")
        assert "600519.SH" in codes

    def test_hk_code_mapped_via_seed(self):
        codes, mentions = _reg().resolve_codes("中芯国际(00981.HK)港股跌7%")
        assert "688981.SH" in codes
        # card preserves the original mention -> mapping
        assert any(m["mentioned"] == "00981.HK" and m["mapped"] == "688981.SH"
                   for m in mentions)

    def test_exact_name_linked(self):
        codes, _ = _reg().resolve_codes("贵州茅台发布一季报")
        assert "600519.SH" in codes

    def test_ambiguous_name_fail_closed(self):
        # "国泰" maps to two codes -> ambiguous -> NOT linked
        codes, _ = _reg().resolve_codes("国泰发布公告")
        assert "601211.SH" not in codes and "020001.SZ" not in codes

    def test_ambiguous_name_not_in_exact(self):
        r = _reg()
        assert "国泰" in r.ambiguous and "国泰" not in r.exact

    def test_short_unique_name_not_substring_linked(self):
        # a unique but SHORT (<4 char) name must NOT link by substring (precision:
        # "美的" would false-match "完美的季报"); only >=4-char names link by name
        basic = pd.DataFrame([{"name": "美的", "ts_code": "000333.SZ"}])
        r = build_alias_registry(basic, version="v", valid_from="2025-01-01")
        codes, _ = r.resolve_codes("这是一个完美的季度")
        assert "000333.SZ" not in codes           # no false substring link

    def test_long_name_still_links(self):
        codes, _ = _reg().resolve_codes("中芯国际公告")   # 4 chars -> links
        assert "688981.SH" in codes


# --------------------------------------------------- 3-way router

class TestRouter:
    def test_stock_route(self):
        r = route_cluster("中芯国际一季度产能利用率85%", _reg(), IND, CON)
        assert r["route"] == "stock" and "688981.SH" in r["subject_codes"]

    def test_industry_concept_route(self):
        r = route_cluster("半导体板块午后走强,国产替代加速", _reg(), IND, CON)
        assert r["route"] == "industry_concept"
        assert "半导体" in r["industry_tags"] and "国产替代" in r["concept_tags"]

    def test_macro_route(self):
        r = route_cluster("央行今日开展1000亿元逆回购操作", _reg(), IND, CON)
        assert r["route"] == "macro" and not r["subject_codes"]

    def test_stock_takes_priority_over_industry(self):
        # mentions both a linkable stock AND an industry term -> stock wins
        r = route_cluster("贵州茅台领涨白酒板块", _reg(), IND, CON)
        assert r["route"] == "stock" and "600519.SH" in r["subject_codes"]


# --------------------------------------------------- scoring_owner (M3)

class TestScoringOwner:
    def test_subject_named_is_news(self):
        assert scoring_owner("c1", "688981.SH", subject_codes=["688981.SH"],
                             systemic_exposure_targets=set()) == "news"

    def test_systemic_peer_is_macro(self):
        # SMIC export-control headline: direct for SMIC (news), systemic for a peer (macro)
        assert scoring_owner("c1", "002049.SZ", subject_codes=["688981.SH"],
                             systemic_exposure_targets={"002049.SZ"}) == "macro"

    def test_unrelated_is_context(self):
        assert scoring_owner("c1", "600519.SH", subject_codes=["688981.SH"],
                             systemic_exposure_targets=set()) == "context"

    def test_subject_and_peer_hard_fails(self):
        with pytest.raises(ScoringOwnershipError):
            scoring_owner("c1", "688981.SH", subject_codes=["688981.SH"],
                          systemic_exposure_targets={"688981.SH"})
