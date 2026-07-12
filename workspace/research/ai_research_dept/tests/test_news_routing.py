# NF wave §7 step 3-routing/4 (review B3 hardened): alias registry + router + scoring_owner.
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_routing import (  # noqa: E402
    ScoringOwnershipError, SystemicExposureSnapshot, build_alias_registry,
    route_cluster, scoring_owner,
)

CUTOFF = "2025-01-27 18:00:00"


def _basic():
    return pd.DataFrame([
        {"name": "中芯国际", "ts_code": "688981.SH"},
        {"name": "平安银行", "ts_code": "000001.SZ"},
        {"name": "贵州茅台", "ts_code": "600519.SH"},
        {"name": "国泰", "ts_code": "601211.SH"},
        {"name": "国泰", "ts_code": "020001.SZ"},   # duplicate -> ambiguous
    ])


def _reg(valid_from="2025-01-01", valid_to=None):
    return build_alias_registry(_basic(), version="alias_v1", valid_from=valid_from,
                                valid_to=valid_to, hk_seed={"00981.HK": "688981.SH"},
                                adr_seed={"BABA": "988888.SH"})


IND = frozenset({"半导体", "白酒", "银行"})
CON = frozenset({"国产替代", "光刻机"})


def _exposure(targets, valid_from="2025-01-01", valid_to=None):
    return SystemicExposureSnapshot(mapping_id="m1", version="v1", content_hash="h",
                                    valid_from=valid_from, valid_to=valid_to,
                                    targets=frozenset(targets))


class TestAliasRegistry:
    def test_version_hash_and_deep_readonly(self):
        r = _reg()
        assert r.version == "alias_v1" and len(r.content_hash) == 16
        with pytest.raises(TypeError):
            r.exact["EVIL"] = "000000.SZ"       # deep read-only (review B3)

    def test_bare_a_code_requires_universe(self):
        r = _reg()
        codes, _ = r.resolve_codes("传闻 600519 涨停", CUTOFF)
        assert "600519.SH" in codes             # in universe
        # a code NOT in the universe must not fabricate a mapping
        codes2, _ = r.resolve_codes("传闻 612345 涨停", CUTOFF)
        assert "612345.SH" not in codes2

    def test_empty_registry_no_fabrication(self):
        empty = build_alias_registry(pd.DataFrame({"name": [], "ts_code": []}),
                                     version="v", valid_from="2025-01-01")
        codes, _ = empty.resolve_codes("612345 大涨", CUTOFF)
        assert codes == []                       # review B3 reproduction closed

    def test_hk_code_mapped_and_mention_preserved(self):
        codes, mentions = _reg().resolve_codes("中芯国际(00981.HK)港股跌7%", CUTOFF)
        assert "688981.SH" in codes
        assert any(m["mentioned"] == "00981.HK" and m["mapped"] == "688981.SH"
                   for m in mentions)

    def test_adr_alias_resolved(self):
        codes, _ = _reg().resolve_codes("BABA美股盘前上涨", CUTOFF)
        assert "988888.SH" in codes             # ASCII ADR now resolves (review B3)

    def test_ambiguous_name_fail_closed(self):
        codes, _ = _reg().resolve_codes("国泰发布公告", CUTOFF)
        assert "601211.SH" not in codes and "020001.SZ" not in codes

    def test_short_unique_name_not_substring_linked(self):
        basic = pd.DataFrame([{"name": "美的", "ts_code": "000333.SZ"}])
        r = build_alias_registry(basic, version="v", valid_from="2025-01-01")
        codes, _ = r.resolve_codes("这是一个完美的季度", CUTOFF)
        assert "000333.SZ" not in codes

    def test_registry_not_effective_before_valid_from(self):
        r = _reg(valid_from="2025-02-01")       # not yet effective at CUTOFF (01-27)
        codes, mentions = r.resolve_codes("中芯国际公告", CUTOFF)
        assert codes == []
        assert mentions[0]["alias_type"] == "registry_not_effective"

    def test_valid_to_in_hash(self):
        a = build_alias_registry(_basic(), version="v", valid_from="2025-01-01",
                                 valid_to="2025-06-30")
        b = build_alias_registry(_basic(), version="v", valid_from="2025-01-01",
                                 valid_to="2025-12-31")
        assert a.content_hash != b.content_hash  # valid_to bound into the hash

    def test_row_order_independent_hash(self):
        a = build_alias_registry(_basic(), version="v", valid_from="2025-01-01")
        b = build_alias_registry(_basic().iloc[::-1].reset_index(drop=True),
                                 version="v", valid_from="2025-01-01")
        assert a.content_hash == b.content_hash  # canonical sort -> deterministic


class TestRouter:
    def test_stock_primary_but_industry_tags_retained(self):
        # review B3: a mixed flash keeps its industry portion, not dropped
        r = route_cluster("贵州茅台领涨白酒板块", _reg(), CUTOFF, IND, CON)
        assert r["primary_route"] == "stock" and "600519.SH" in r["subject_codes"]
        assert "白酒" in r["industry_tags"]       # NOT dropped

    def test_industry_concept_route(self):
        r = route_cluster("半导体板块午后走强,国产替代加速", _reg(), CUTOFF, IND, CON)
        assert r["primary_route"] == "industry_concept"
        assert "半导体" in r["industry_tags"] and "国产替代" in r["concept_tags"]

    def test_macro_route(self):
        r = route_cluster("央行今日开展1000亿元逆回购操作", _reg(), CUTOFF, IND, CON)
        assert r["primary_route"] == "macro" and not r["subject_codes"]


class TestScoringOwner:
    def test_subject_named_is_news(self):
        assert scoring_owner("c1", "688981.SH", CUTOFF, subject_codes=["688981.SH"],
                             systemic_exposure=_exposure(set())) == "news"

    def test_systemic_peer_is_macro(self):
        assert scoring_owner("c1", "002049.SZ", CUTOFF, subject_codes=["688981.SH"],
                             systemic_exposure=_exposure({"002049.SZ"})) == "macro"

    def test_systemic_ignored_when_snapshot_not_effective(self):
        # exposure not effective at cutoff -> peer is not macro-owned
        exp = _exposure({"002049.SZ"}, valid_from="2025-02-01")
        assert scoring_owner("c1", "002049.SZ", CUTOFF, subject_codes=["688981.SH"],
                             systemic_exposure=exp) == "context"

    def test_unrelated_is_context(self):
        assert scoring_owner("c1", "600519.SH", CUTOFF, subject_codes=["688981.SH"],
                             systemic_exposure=_exposure(set())) == "context"

    def test_subject_and_peer_hard_fails(self):
        with pytest.raises(ScoringOwnershipError):
            scoring_owner("c1", "688981.SH", CUTOFF, subject_codes=["688981.SH"],
                          systemic_exposure=_exposure({"688981.SH"}))

    def test_arbitrary_set_rejected(self):
        with pytest.raises(ScoringOwnershipError, match="密封"):
            scoring_owner("c1", "688981.SH", CUTOFF, subject_codes=[],
                          systemic_exposure={"688981.SH"})   # raw set, not sealed
