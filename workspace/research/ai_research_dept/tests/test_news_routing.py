# NF wave §7 routing/4 (FIX-FIRST full-seal): sealed alias/exposure/claim + PIT bounds.
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_routing import (  # noqa: E402
    AliasRegistry, ScoringOwnershipError, build_alias_registry, build_atomic_claim,
    build_systemic_exposure, route_cluster, scoring_owner,
)
from workspace.research.ai_research_dept.engine.news_seal import SealError  # noqa: E402

CUTOFF = "2025-01-27 18:00:00"


def _basic(with_dates=False):
    rows = [
        {"name": "中芯国际", "ts_code": "688981.SH"},
        {"name": "平安银行", "ts_code": "000001.SZ"},
        {"name": "贵州茅台", "ts_code": "600519.SH"},
        {"name": "国泰", "ts_code": "601211.SH"},
        {"name": "国泰", "ts_code": "020001.SZ"},
    ]
    if with_dates:
        for r in rows:
            r["list_date"] = "20100101"
            r["delist_date"] = None
    return pd.DataFrame(rows)


def _reg(**kw):
    return build_alias_registry(_basic(), version="alias_v1", valid_from="2025-01-01",
                                hk_seed={"00981.HK": "688981.SH"},
                                adr_seed={"BABA": "600519.SH"}, **kw)


IND = frozenset({"半导体", "白酒", "银行"})
CON = frozenset({"国产替代", "光刻机"})


def _exposure(targets, valid_from="2025-01-01", valid_to=None):
    return build_systemic_exposure("m1", "v1", valid_from, targets, valid_to=valid_to)


def _claim(subject_codes, cid="c1", fact="f1"):
    route = {"subject_codes": subject_codes, "industry_tags": [], "concept_tags": []}
    return build_atomic_claim(cid, fact, route, "reghash")


class TestAliasRegistrySealed:
    def test_hash_and_deep_readonly(self):
        r = _reg()
        assert len(r.content_hash) == 64
        with pytest.raises(TypeError):
            r.exact["EVIL"] = "000000.SZ"

    def test_forged_direct_construction_rejected(self):
        r = _reg()
        # tamper the payload (swap a mapping) but keep the old hash -> verify catches it
        from workspace.research.ai_research_dept.engine.news_seal import deep_ro
        with pytest.raises(SealError):
            AliasRegistry(version=r.version, content_hash=r.content_hash,
                          exact=deep_ro({"中芯国际": "000000.SZ"}),
                          ambiguous=r.ambiguous, a_universe=r.a_universe,
                          valid_from=r.valid_from, valid_to=r.valid_to)

    def test_row_order_independent_hash(self):
        a = build_alias_registry(_basic(), version="v", valid_from="2025-01-01")
        b = build_alias_registry(_basic().iloc[::-1].reset_index(drop=True),
                                 version="v", valid_from="2025-01-01")
        assert a.content_hash == b.content_hash

    def test_explicit_suffix_honored(self):
        # review B3: 000001.SH must NOT resolve as 000001.SZ
        basic = pd.DataFrame([{"name": "X", "ts_code": "000001.SH"},
                              {"name": "Y", "ts_code": "000001.SZ"}])
        r = build_alias_registry(basic, version="v", valid_from="2025-01-01")
        codes, _ = r.resolve_codes("传闻 000001.SH 涨停", CUTOFF)
        assert codes == ["000001.SH"]

    def test_bare_code_requires_universe(self):
        codes, _ = _reg().resolve_codes("传闻 612345 涨停", CUTOFF)
        assert "612345.SH" not in codes

    def test_empty_registry_no_fabrication(self):
        empty = build_alias_registry(pd.DataFrame({"name": [], "ts_code": []}),
                                     version="v", valid_from="2025-01-01")
        assert empty.resolve_codes("612345 大涨", CUTOFF)[0] == []

    def test_pit_listing_bounds(self):
        # review B3: a stock listed AFTER the cutoff must not be in the universe
        basic = pd.DataFrame([{"name": "新股", "ts_code": "301999.SZ",
                               "list_date": "20250601", "delist_date": None}])
        r = build_alias_registry(basic, version="v", valid_from="2025-01-01",
                                 cutoff="2025-01-27")
        assert "301999.SZ" not in r.a_universe
        assert r.resolve_codes("301999 上市", CUTOFF)[0] == []

    def test_pit_delisted_excluded(self):
        basic = pd.DataFrame([{"name": "退市", "ts_code": "600001.SH",
                               "list_date": "20000101", "delist_date": "20240101"}])
        r = build_alias_registry(basic, version="v", valid_from="2025-01-01",
                                 cutoff="2025-01-27")
        assert "600001.SH" not in r.a_universe

    def test_seed_target_must_be_in_universe(self):
        with pytest.raises(ValueError, match="宇宙"):
            build_alias_registry(_basic(), version="v", valid_from="2025-01-01",
                                 hk_seed={"00700.HK": "999999.SH"})

    def test_hk_mention_preserved(self):
        codes, mentions = _reg().resolve_codes("中芯国际(00981.HK)港股跌7%", CUTOFF)
        assert "688981.SH" in codes
        assert any(m["mentioned"] == "00981.HK" and m["mapped"] == "688981.SH"
                   for m in mentions)

    def test_adr_resolved(self):
        assert "600519.SH" in _reg().resolve_codes("BABA美股上涨", CUTOFF)[0]

    def test_ambiguous_fail_closed(self):
        assert _reg().resolve_codes("国泰发布公告", CUTOFF)[0] == []

    def test_not_effective_before_valid_from(self):
        r = build_alias_registry(_basic(), version="v", valid_from="2025-02-01")
        assert r.resolve_codes("中芯国际公告", CUTOFF)[0] == []


class TestRouter:
    def test_stock_primary_keeps_industry_tags(self):
        r = route_cluster("贵州茅台领涨白酒板块", _reg(), CUTOFF, IND, CON)
        assert r["primary_route"] == "stock" and "600519.SH" in r["subject_codes"]
        assert "白酒" in r["industry_tags"]

    def test_macro(self):
        r = route_cluster("央行今日开展逆回购", _reg(), CUTOFF, IND, CON)
        assert r["primary_route"] == "macro"


class TestAtomicClaimSealed:
    def test_seal_and_forge(self):
        c = _claim(["688981.SH"])
        assert len(c.content_hash) == 64
        from workspace.research.ai_research_dept.engine.news_routing import AtomicClaim
        with pytest.raises(SealError):
            AtomicClaim(claim_id="c1", fact_cluster_id="f1", subject_codes=("EVIL",),
                        industry_tags=(), concept_tags=(), alias_registry_hash="reghash",
                        content_hash=c.content_hash)


class TestScoringOwner:
    def test_subject_is_news(self):
        assert scoring_owner(_claim(["688981.SH"]), "688981.SH", CUTOFF,
                             systemic_exposure=_exposure(set())) == "news"

    def test_systemic_peer_is_macro(self):
        assert scoring_owner(_claim(["688981.SH"]), "002049.SZ", CUTOFF,
                             systemic_exposure=_exposure({"002049.SZ"})) == "macro"

    def test_exposure_not_effective(self):
        exp = _exposure({"002049.SZ"}, valid_from="2025-02-01")
        assert scoring_owner(_claim(["688981.SH"]), "002049.SZ", CUTOFF,
                             systemic_exposure=exp) == "context"

    def test_unrelated_context(self):
        assert scoring_owner(_claim(["688981.SH"]), "600519.SH", CUTOFF,
                             systemic_exposure=_exposure(set())) == "context"

    def test_subject_and_peer_hard_fails(self):
        with pytest.raises(ScoringOwnershipError):
            scoring_owner(_claim(["688981.SH"]), "688981.SH", CUTOFF,
                          systemic_exposure=_exposure({"688981.SH"}))

    def test_raw_claim_rejected(self):
        with pytest.raises(ScoringOwnershipError, match="AtomicClaim"):
            scoring_owner("c1", "688981.SH", CUTOFF, systemic_exposure=_exposure(set()))

    def test_raw_exposure_rejected(self):
        with pytest.raises(ScoringOwnershipError, match="SystemicExposure"):
            scoring_owner(_claim(["688981.SH"]), "688981.SH", CUTOFF,
                          systemic_exposure={"688981.SH"})

    def test_forged_exposure_rejected(self):
        exp = _exposure({"002049.SZ"})
        from workspace.research.ai_research_dept.engine.news_routing import SystemicExposureSnapshot
        with pytest.raises(SealError):
            SystemicExposureSnapshot(mapping_id=exp.mapping_id, version=exp.version,
                                     content_hash=exp.content_hash, valid_from=exp.valid_from,
                                     valid_to=exp.valid_to, targets=frozenset({"EVIL.SZ"}))
