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
from workspace.research.ai_research_dept.engine.news_routing import (  # noqa: E402
    build_alias_registry,
)

CUT = "2025-01-27 18:00:00"
IND = frozenset({"白酒"})
CON = frozenset({"消费"})


def _news_rows(contents, dt="2025-01-27 16:00:00"):
    return pd.DataFrame([{"src": "sina", "datetime": dt, "content": c, "title": None,
                          "channels": ""} for c in contents])


def _ingest(tmp_path, contents, *, dt="2025-01-27 16:00:00", ingest_class="forward"):
    ingest_rows("news", _news_rows(contents, dt), published_col="datetime",
                retrieved_at=pd.Timestamp("2025-01-27 17:00:00"),
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


def _reg(cutoff=CUT):
    return build_alias_registry(_stock_basic(), version="t", valid_from="2000-01-01",
                                cutoff=cutoff)


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


# --------------------------------------------------- happy path + routing

def test_assess_routes_and_types(tmp_path):
    _ingest(tmp_path, ["贵州茅台签订 12 亿大单", "央行今日开展逆回购"])
    art = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=_p1(tmp_path),
                             registry=_reg(), industry_terms=IND, concept_terms=CON,
                             store_dir=tmp_path)
    assert art["artifact_schema"] == "nf_assessed_flash_v1" and art["n_flashes"] == 2
    by_route = {a["route"]["primary_route"] for a in art["assessed"]}
    assert by_route == {"stock", "macro"}
    stock = next(a for a in art["assessed"] if a["route"]["primary_route"] == "stock")
    assert "600519.SH" in stock["route"]["subject_codes"]
    assert stock["evidence_class"] in ("NFD", "NFI")     # verify-not-trust recompute


# --------------------------------------------------- invariant 2: P1 binding

def test_wrong_p1_identity_refused(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单"])
    p1 = _p1(tmp_path)
    p1_bad = {**p1, "cutoff_iso": "2025-01-27T09:30:00"}   # different cutoff identity
    with pytest.raises(ValueError, match="identity mismatch"):
        assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1_bad,
                           registry=_reg(), industry_terms=IND, concept_terms=CON,
                           store_dir=tmp_path)


def test_missing_p1_typing_is_hard_error(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单", "宁德时代扩产"])
    p1 = _p1(tmp_path)
    p1_short = {**p1, "typed": p1["typed"][:1]}            # drop one flash's typing
    with pytest.raises(ValueError, match="no P1 typing"):
        assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1_short,
                           registry=_reg(), industry_terms=IND, concept_terms=CON,
                           store_dir=tmp_path)


def test_consumed_p1_sha_is_bound(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单"])
    p1 = _p1(tmp_path)
    art = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1,
                             registry=_reg(), industry_terms=IND, concept_terms=CON,
                             store_dir=tmp_path)
    assert art["consumed_typed_flash_sha256"] == p1["artifact_sha256"]
    assert art["alias_registry_hash"] == _reg().content_hash


# --------------------------------------------------- invariant 1: PIT routing

def test_alias_listed_after_cutoff_does_not_route_to_stock(tmp_path):
    # 未来上市 (301999) lists 2026-01-01 > cutoff → not in the as-of registry → the
    # flash mentioning it routes by industry/concept or macro, never stock.
    _ingest(tmp_path, ["未来上市公司发布重大公告"])
    art = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=_p1(tmp_path),
                             registry=_reg(), industry_terms=IND, concept_terms=CON,
                             store_dir=tmp_path)
    a = art["assessed"][0]
    assert "301999.SZ" not in a["route"]["subject_codes"]
    assert a["route"]["primary_route"] != "stock"


# --------------------------------------------------- invariant 5: macro flagged

def test_macro_flagged_not_news_render_eligible(tmp_path):
    _ingest(tmp_path, ["央行今日开展逆回购", "贵州茅台大单"])
    art = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=_p1(tmp_path),
                             registry=_reg(), industry_terms=IND, concept_terms=CON,
                             store_dir=tmp_path)
    macro = next(a for a in art["assessed"] if a["route"]["primary_route"] == "macro")
    stock = next(a for a in art["assessed"] if a["route"]["primary_route"] == "stock")
    assert macro["news_render_eligible"] is False
    assert stock["news_render_eligible"] is True


# --------------------------------------------------- invariant 3/6: deterministic + persistence

def test_deterministic_and_round_trip(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单", "宁德时代扩产"])
    p1 = _p1(tmp_path)
    a1 = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1,
                            registry=_reg(), industry_terms=IND, concept_terms=CON,
                            store_dir=tmp_path)
    a2 = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1,
                            registry=_reg(), industry_terms=IND, concept_terms=CON,
                            store_dir=tmp_path)
    assert a1["artifact_sha256"] == a2["artifact_sha256"]
    path = write_assessed_flash_artifact(a1, tmp_path / "out")
    assert load_assessed_flash_artifact(path)["artifact_sha256"] == a1["artifact_sha256"]


def test_tampered_artifact_refused(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单"])
    art = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=_p1(tmp_path),
                             registry=_reg(), industry_terms=IND, concept_terms=CON,
                             store_dir=tmp_path)
    path = write_assessed_flash_artifact(art, tmp_path / "out")
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["assessed"][0]["route"]["subject_codes"] = ["000001.SZ"]   # tamper
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        load_assessed_flash_artifact(path)


def test_write_once_refuses_different_content(tmp_path):
    _ingest(tmp_path, ["贵州茅台大单"])
    p1 = _p1(tmp_path)
    a1 = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1,
                            registry=_reg(), industry_terms=IND, concept_terms=CON,
                            store_dir=tmp_path)
    write_assessed_flash_artifact(a1, tmp_path / "out")
    write_assessed_flash_artifact(a1, tmp_path / "out")            # idempotent
    # different concept terms -> different routing tags -> different artifact
    a2 = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1,
                            registry=_reg(), industry_terms=IND,
                            concept_terms=frozenset({"消费", "大消费"}), store_dir=tmp_path)
    if a2["artifact_sha256"] != a1["artifact_sha256"]:
        with pytest.raises(AssessedFlashConflictError, match="write-once"):
            write_assessed_flash_artifact(a2, tmp_path / "out")


# --------------------------------------------------- invariant 7: NON_EVIDENTIARY / empty

def test_empty_day_empty_artifact(tmp_path):
    # existing forward panel, nothing before cutoff -> empty P1 -> empty P2
    _ingest(tmp_path, ["cutoff 之后"], dt="2025-01-28 10:00:00")
    p1 = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                          store_dir=tmp_path)
    art = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1,
                             registry=_reg(), industry_terms=IND, concept_terms=CON,
                             store_dir=tmp_path)
    assert art["n_flashes"] == 0 and art["evidence_class"].endswith("NON_EVIDENTIARY")
