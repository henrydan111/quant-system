# NF integration P2: market-wide cluster+route+assess — declared-invariant tests.
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data_infra.text_store import ingest_rows  # noqa: E402
from workspace.research.ai_research_dept.engine.news_flash_assess import (  # noqa: E402
    AssessedFlashConflictError, assess_day_flashes, load_assessed_flash_artifact,
    write_assessed_flash_artifact,
)
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    type_day_flashes,
)

CUT = "2025-01-27 18:00:00"
IND = frozenset({"白酒"})
CON = frozenset({"消费"})


def _news_rows(contents, dt="2025-01-27 16:00:00"):
    return pd.DataFrame([{"src": "sina", "datetime": dt, "content": c, "title": None,
                          "channels": ""} for c in contents])


def _ingest(tmp_path, contents, *, dt="2025-01-27 16:00:00", ingest_class="forward",
            retrieved_at="2025-01-27 17:00:00"):
    ingest_rows("news", _news_rows(contents, dt), published_col="datetime",
                retrieved_at=pd.Timestamp(retrieved_at),
                store_dir=tmp_path, ingest_class=ingest_class)


def _stock_basic():
    return pd.DataFrame([
        {"ts_code": "600519.SH", "name": "贵州茅台", "list_date": "20010827",
         "delist_date": None},
        {"ts_code": "300750.SZ", "name": "宁德时代", "list_date": "20180611",
         "delist_date": None},
        {"ts_code": "301999.SZ", "name": "未来上市", "list_date": "20260101",  # after cutoff
         "delist_date": None},
    ])


_NC_COLS = ["ts_code", "name", "start_date", "end_date", "ann_date", "change_reason"]


def _namechange(rows=None):
    # default: clean, announced, unique as-of names for the two resolvable stocks (under
    # fail-closed-omit, a stock without a clean namechange entry gets NO name alias).
    if rows is None:
        rows = [
            {"ts_code": "600519.SH", "name": "贵州茅台", "start_date": "20010827",
             "end_date": None, "ann_date": "20010827", "change_reason": "上市"},
            {"ts_code": "300750.SZ", "name": "宁德时代", "start_date": "20180611",
             "end_date": None, "ann_date": "20180611", "change_reason": "上市"},
        ]
    return pd.DataFrame(rows, columns=_NC_COLS)


class _Reply:
    def __init__(self, text):
        self.text = text


def _stub_typer(**overrides):
    def fn(msgs):
        payload = json.loads(msgs[1]["content"])
        base = {"event_type": "订单合同", "verification_status": "官方证实",
                "content_kind": "事实", "direction": "利好", "importance": 5,
                "is_rumor": False, **overrides}
        return _Reply(json.dumps({"results": [
            {"idx": it["idx"], **base} for it in payload["items"]]}, ensure_ascii=False))
    return fn


def _p1(tmp_path):
    return type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                            store_dir=tmp_path)


def _assess(tmp_path, typed, *, stock_basic=None, namechange=None, **kw):
    return assess_day_flashes(CUT, ingest_class="forward", typed_artifact=typed,
                              stock_basic=stock_basic if stock_basic is not None else _stock_basic(),
                              namechange=namechange if namechange is not None else _namechange(),
                              industry_terms=IND, concept_terms=CON, store_dir=tmp_path, **kw)


# --------------------------------------------------- happy path + routing

def test_assess_routes_and_types(tmp_path):
    _ingest(tmp_path, ["贵州茅台签订 12 亿大单", "央行今日开展逆回购"])
    art = _assess(tmp_path, _p1(tmp_path))
    assert art["artifact_schema"] == "nf_assessed_flash_v1" and art["n_flashes"] == 2
    by_route = {a["route"]["primary_route"] for a in art["assessed"]}
    assert by_route == {"stock", "macro"}
    stock = next(a for a in art["assessed"] if a["route"]["primary_route"] == "stock")
    assert "600519.SH" in stock["route"]["subject_codes"]
    assert stock["evidence_class"] in ("NFD", "NFI")     # verify-not-trust recompute


# --------------------------------------------------- P0: as-of registry (P2 builds it)

def test_p0_stock_listed_after_cutoff_never_routes_to_stock(tmp_path):
    # GPT-P2 P0: P2 builds the alias registry AS-OF the canonical cutoff, so 未来上市
    # (301999, list_date 2026-01-01 > cutoff) is not in the universe and cannot resolve —
    # no future-listed stock can leak in, no matter what stock_basic contains.
    _ingest(tmp_path, ["未来上市公司发布重大公告"])
    art = _assess(tmp_path, _p1(tmp_path))
    a = art["assessed"][0]
    assert "301999.SZ" not in a["route"]["subject_codes"]
    assert a["route"]["primary_route"] != "stock"
    assert art["routing_reference"]["as_of_cutoff_iso"] == "2025-01-27T18:00:00"


# --------------------------------------------------- P1-#2: dict artifact must be verified

def test_p1_dict_artifact_seal_is_verified(tmp_path):
    # GPT-P2 P1-#2: a hand-built dict with a bogus self-claimed SHA must be REFUSED, not
    # trusted (the old code only verified path inputs).
    _ingest(tmp_path, ["贵州茅台大单"])
    forged = {"artifact_schema": "nf_typed_flash_v1", "cutoff_iso": "2025-01-27T18:00:00",
              "ingest_class": "forward", "evidence_class": "x/NON_EVIDENTIARY",
              "population_hash": "0" * 64, "n_flashes": 0, "typed": [],
              "artifact_sha256": "not-verified-by-p2"}
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        _assess(tmp_path, forged)


# --------------------------------------------------- P1-#3: population equality (not just rep)

def test_p1_population_must_equal_raw(tmp_path):
    # GPT-P2 P1-#3: dropping ANY flash from the P1 artifact (not just a cluster
    # representative) must fail — the raw content-hash set must equal the P1-typed set.
    _ingest(tmp_path, ["贵州茅台大单", "宁德时代扩产"])
    p1 = _p1(tmp_path)
    p1_short = dict(p1)
    p1_short["typed"] = p1["typed"][:1]
    p1_short["n_flashes"] = 1
    # re-seal so it passes P1's own verify but is a genuine population subset
    from workspace.research.ai_research_dept.engine.news_seal import seal_hash
    p1_short["population_hash"] = seal_hash(sorted(x["content_hash"] for x in p1_short["typed"]))
    body = {k: v for k, v in p1_short.items() if k != "artifact_sha256"}
    p1_short["artifact_sha256"] = seal_hash(body)
    with pytest.raises(ValueError, match="population"):
        _assess(tmp_path, p1_short)


# --------------------------------------------------- union routing (representative-member fix)

def test_union_routes_all_members_not_just_representative(tmp_path):
    # GPT-P2: the cluster key is the first 120 canonical chars, so two flashes with the
    # same long prefix but different tails (mentioning different stocks) cluster together.
    # Routing must UNION all members' mentions, not just members[0]'s.
    prefix = "详情" * 70                             # 140 chars — first 120 shared by both
    _ingest(tmp_path, [prefix + "贵州茅台", prefix + "宁德时代"])
    art = _assess(tmp_path, _p1(tmp_path))
    assert art["n_flashes"] == 1                     # one cluster (shared prefix)
    codes = set(art["assessed"][0]["route"]["subject_codes"])
    assert codes == {"600519.SH", "300750.SZ"}       # BOTH members' stocks, unioned


# --------------------------------------------------- binding / provenance

def test_consumed_p1_sha_and_routing_reference_bound(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单"])
    p1 = _p1(tmp_path)
    art = _assess(tmp_path, p1)
    assert art["consumed_typed_flash_sha256"] == p1["artifact_sha256"]
    rr = art["routing_reference"]
    assert set(rr) == {"as_of_cutoff_iso", "alias_registry_version", "alias_registry_hash",
                       "as_of_names_hash", "industry_terms_hash", "concept_terms_hash"}


def test_wrong_p1_identity_refused(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单"])
    p1 = _p1(tmp_path)
    from workspace.research.ai_research_dept.engine.news_seal import seal_hash
    p1_bad = dict(p1)
    p1_bad["cutoff_iso"] = "2025-01-27T09:30:00"
    body = {k: v for k, v in p1_bad.items() if k != "artifact_sha256"}
    p1_bad["artifact_sha256"] = seal_hash(body)       # re-seal so only IDENTITY differs
    with pytest.raises(ValueError, match="identity mismatch"):
        _assess(tmp_path, p1_bad)


# --------------------------------------------------- macro flagged / coordination unevaluated

def test_macro_flagged_not_news_render_eligible(tmp_path):
    _ingest(tmp_path, ["央行今日开展逆回购", "贵州茅台大单"])
    art = _assess(tmp_path, _p1(tmp_path))
    macro = next(a for a in art["assessed"] if a["route"]["primary_route"] == "macro")
    stock = next(a for a in art["assessed"] if a["route"]["primary_route"] == "stock")
    assert macro["news_render_eligible"] is False
    assert stock["news_render_eligible"] is True
    assert all(a["coordination_evaluated"] is False for a in art["assessed"])   # unassessed


# --------------------------------------------------- determinism + persistence

def test_deterministic_and_round_trip(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单", "宁德时代扩产"])
    p1 = _p1(tmp_path)
    a1 = _assess(tmp_path, p1)
    a2 = _assess(tmp_path, p1)
    assert a1["artifact_sha256"] == a2["artifact_sha256"]
    path = write_assessed_flash_artifact(a1, tmp_path / "out")
    assert load_assessed_flash_artifact(path)["artifact_sha256"] == a1["artifact_sha256"]


def test_tampered_artifact_refused(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单"])
    art = _assess(tmp_path, _p1(tmp_path))
    path = write_assessed_flash_artifact(art, tmp_path / "out")
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["assessed"][0]["route"]["subject_codes"] = ["000001.SZ"]   # tamper
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        load_assessed_flash_artifact(path)


def test_write_once_refuses_different_content(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单"])
    p1 = _p1(tmp_path)
    a1 = _assess(tmp_path, p1)
    write_assessed_flash_artifact(a1, tmp_path / "out")
    write_assessed_flash_artifact(a1, tmp_path / "out")            # idempotent
    a2 = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1,
                            stock_basic=_stock_basic(), namechange=_namechange(),
                            industry_terms=IND, concept_terms=frozenset({"消费", "大消费"}),
                            store_dir=tmp_path)
    if a2["artifact_sha256"] != a1["artifact_sha256"]:
        with pytest.raises(AssessedFlashConflictError, match="write-once"):
            write_assessed_flash_artifact(a2, tmp_path / "out")


# --------------------------------------------------- GPT-P2 re-review#1: as-of names + typing wash

def test_p0_post_cutoff_rename_does_not_resolve(tmp_path):
    # GPT-P2 P0: 000558.SZ was '莱茵体育' at the 2025-01-27 cutoff; it renamed to
    # '天府文旅' effective 2025-02-14. P2 resolves the AS-OF name (莱茵体育), so news
    # mentioning the FUTURE name '天府文旅' does NOT resolve at this cutoff.
    sb = pd.DataFrame([{"ts_code": "000558.SZ", "name": "天府文旅",   # current name
                        "list_date": "19970116", "delist_date": None}])
    nc = _namechange([
        {"ts_code": "000558.SZ", "name": "莱茵体育", "start_date": "20140101",
         "end_date": "20250213", "ann_date": "20140101", "change_reason": "更名"},
        {"ts_code": "000558.SZ", "name": "天府文旅", "start_date": "20250214",
         "end_date": None, "ann_date": "20250214", "change_reason": "更名"},
    ])
    _ingest(tmp_path, ["莱茵体育发布重大公告", "天府文旅发布重大公告"])
    art = _assess(tmp_path, _p1(tmp_path), stock_basic=sb, namechange=nc)
    assert art["n_flashes"] == 2                       # two distinct-content clusters
    stock_flash = next(a for a in art["assessed"] if a["route"]["primary_route"] == "stock")
    non_stock = next(a for a in art["assessed"] if a["route"]["primary_route"] != "stock")
    assert "000558.SZ" in stock_flash["route"]["subject_codes"]      # 莱茵体育 (as-of) resolved
    assert "000558.SZ" not in non_stock["route"]["subject_codes"]    # 天府文旅 (future) did NOT


def test_p1_conflicting_member_typings_refused(tmp_path):
    # GPT-P2 P1: two flashes share a >120-char prefix (one cluster) but P1 typed them
    # differently (official-bullish vs rumor-bearish). Reusing one typing would launder
    # evidence class across facts -> the cluster is refused (fail-closed).
    prefix = "详情" * 70
    _ingest(tmp_path, [prefix + "甲", prefix + "乙"])

    def mixed_typer(msgs):
        payload = json.loads(msgs[1]["content"])
        out = []
        for it in payload["items"]:
            if "甲" in it["content"]:
                t = {"event_type": "订单合同", "verification_status": "官方证实",
                     "content_kind": "事实", "direction": "利好", "importance": 5,
                     "is_rumor": False}
            else:
                t = {"event_type": "传闻未证实", "verification_status": "传闻",
                     "content_kind": "评论", "direction": "利空", "importance": 3,
                     "is_rumor": True}
            out.append({"idx": it["idx"], **t})
        return _Reply(json.dumps({"results": out}, ensure_ascii=False))
    p1 = type_day_flashes(CUT, ingest_class="forward", call_fn=mixed_typer, store_dir=tmp_path)
    with pytest.raises(ValueError, match="conflicting typings"):
        _assess(tmp_path, p1)


def test_p0_name_in_effect_but_unannounced_does_not_resolve(tmp_path):
    # GPT-P2 re-review#2: ann_date is the PIT visibility anchor. A name in effect at cut
    # (start_date <= cut) but announced AFTER cut (ann_date > cut) must NOT resolve.
    sb = pd.DataFrame([{"ts_code": "000001.SZ", "name": "刚改的名",
                        "list_date": "19910403", "delist_date": None}])
    nc = _namechange([
        {"ts_code": "000001.SZ", "name": "刚改的名", "start_date": "20250101",
         "end_date": None, "ann_date": "20250201", "change_reason": "更名"},  # ann > cut
    ])
    _ingest(tmp_path, ["刚改的名发布重大公告"])
    art = _assess(tmp_path, _p1(tmp_path), stock_basic=sb, namechange=nc)
    assert "000001.SZ" not in {c for a in art["assessed"]
                               for c in a["route"]["subject_codes"]}


def test_p1_importance_is_max_over_members(tmp_path):
    # GPT-P2 re-review#2: after the identity gate, importance is the MAX over members
    # (a low-importance representative must not drop the D7 importance>=4 split gate).
    prefix = "详情" * 70
    _ingest(tmp_path, [prefix + "甲", prefix + "乙"])

    def imp_typer(msgs):
        payload = json.loads(msgs[1]["content"])
        out = []
        for it in payload["items"]:
            imp = 1 if "甲" in it["content"] else 5      # same identity, different importance
            out.append({"idx": it["idx"], "event_type": "订单合同",
                        "verification_status": "官方证实", "content_kind": "事实",
                        "direction": "利好", "importance": imp, "is_rumor": False})
        return _Reply(json.dumps({"results": out}, ensure_ascii=False))
    p1 = type_day_flashes(CUT, ingest_class="forward", call_fn=imp_typer, store_dir=tmp_path)
    art = _assess(tmp_path, p1)
    assert art["n_flashes"] == 1
    assert art["assessed"][0]["typing"]["importance"] == 5   # max(1, 5), not the rep's


def test_p0_missing_delist_date_column_fail_closed(tmp_path):
    # GPT-P2 re-review#2: under a cutoff the delist_date COLUMN must exist (empty cell =
    # not delisted); a missing column was silently treated as 'not delisted'.
    sb = pd.DataFrame([{"ts_code": "600519.SH", "name": "贵州茅台",
                        "list_date": "20010827"}])          # no delist_date column
    _ingest(tmp_path, ["贵州茅台大单"])
    with pytest.raises(ValueError, match="delist_date"):
        _assess(tmp_path, _p1(tmp_path), stock_basic=sb)


def test_p0_unparseable_list_date_fail_closed(tmp_path):
    # GPT-P2 P0: a listed stock whose list_date can't be PIT-judged is refused, not
    # admitted (the old code coerced it to NaT and admitted it).
    sb = pd.DataFrame([{"ts_code": "600519.SH", "name": "贵州茅台",
                        "list_date": None, "delist_date": None}])
    _ingest(tmp_path, ["贵州茅台大单"])
    with pytest.raises(ValueError, match="list_date"):
        _assess(tmp_path, _p1(tmp_path), stock_basic=sb)


# --------------------------------------------------- NON_EVIDENTIARY / empty

def test_empty_day_empty_artifact(tmp_path):
    _ingest(tmp_path, ["cutoff 之后"], dt="2025-01-28 10:00:00")
    p1 = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                          store_dir=tmp_path)
    art = _assess(tmp_path, p1)
    assert art["n_flashes"] == 0 and art["evidence_class"].endswith("NON_EVIDENTIARY")
