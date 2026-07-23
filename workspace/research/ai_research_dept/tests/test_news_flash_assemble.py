# NF integration P3b: per-stock D7 artifact assembly — declared-invariant tests.
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data_infra.text_store import ingest_rows, load_text  # noqa: E402
from workspace.research.ai_research_dept.engine.news_cards import (  # noqa: E402
    verify_d7_artifact,
)
from workspace.research.ai_research_dept.engine.news_flash_assemble import (  # noqa: E402
    NothingToDecide, assemble_stock_artifact,
)
from workspace.research.ai_research_dept.engine.news_flash_assess import (  # noqa: E402
    assess_day_flashes,
)
from workspace.research.ai_research_dept.engine.news_flash_split import (  # noqa: E402
    split_day_flashes,
)
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    type_day_flashes,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash  # noqa: E402

CUT = "2025-01-27 18:00:00"
MAOTAI, CATL = "600519.SH", "300750.SZ"
IND = frozenset({"白酒"})
CON = frozenset({"消费"})
_CAL = pd.DatetimeIndex(pd.bdate_range("2025-01-02", "2025-03-31"))
_NC_COLS = ["ts_code", "name", "start_date", "end_date", "ann_date", "change_reason"]


def _stock_basic():
    return pd.DataFrame([
        {"ts_code": MAOTAI, "name": "贵州茅台", "list_date": "20010827", "delist_date": None},
        {"ts_code": CATL, "name": "宁德时代", "list_date": "20180611", "delist_date": None},
    ])


def _namechange():
    return pd.DataFrame([
        {"ts_code": MAOTAI, "name": "贵州茅台", "start_date": "20010827", "end_date": None,
         "ann_date": "20010827", "change_reason": "上市"},
        {"ts_code": CATL, "name": "宁德时代", "start_date": "20180611", "end_date": None,
         "ann_date": "20180611", "change_reason": "上市"},
    ], columns=_NC_COLS)


def _ingest(tmp_path, contents):
    ingest_rows("news", pd.DataFrame([{"src": "sina", "datetime": "2025-01-27 16:00:00",
                                       "content": c, "title": None, "channels": ""}
                                      for c in contents]),
                published_col="datetime", retrieved_at=pd.Timestamp("2025-01-27 17:00:00"),
                store_dir=tmp_path, ingest_class="forward")


class _Reply:
    def __init__(self, text):
        self.text = text


def _typer(importance=5, **over):
    def fn(msgs):
        payload = json.loads(msgs[1]["content"])
        base = {"event_type": "订单合同", "verification_status": "官方证实",
                "content_kind": "事实", "direction": "利好", "importance": importance,
                "is_rumor": False, **over}
        return _Reply(json.dumps({"results": [{"idx": it["idx"], **base}
                                              for it in payload["items"]]},
                                 ensure_ascii=False))
    return fn


def _chain(tmp_path, contents, *, importance=5, typer_over=None):
    """P1 -> P2 -> P3a -> the inputs P3b consumes."""
    _ingest(tmp_path, contents)
    p1 = type_day_flashes(CUT, ingest_class="forward",
                          call_fn=_typer(importance, **(typer_over or {})),
                          store_dir=tmp_path)
    p2 = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1,
                            stock_basic=_stock_basic(), namechange=_namechange(),
                            open_calendar=_CAL, industry_terms=IND, concept_terms=CON,
                            store_dir=tmp_path)
    rows = load_text("news", pd.Timestamp(CUT), store_dir=tmp_path, ingest_class="forward")
    p3a = split_day_flashes(CUT, ingest_class="forward", assessed_artifact=p2,
                            source_rows=rows)
    return p2, p3a, rows


def _assemble(p2, p3a, rows, *, ts_code=MAOTAI, decision_id="d1"):
    return assemble_stock_artifact(CUT, ingest_class="forward", ts_code=ts_code,
                                   decision_id=decision_id, assessed_artifact=p2,
                                   split_artifact=p3a, source_rows=rows)


# --------------------------------------------------- happy path

def test_assembles_a_verified_d7_artifact(tmp_path):
    p2, p3a, rows = _chain(tmp_path, ["贵州茅台签订 12 亿元大单"])
    art, prov = _assemble(p2, p3a, rows)
    assert verify_d7_artifact(art) == art            # full lineage re-derivation passes
    assert art.bundle.decision_id == "d1"
    assert prov["ts_code"] == MAOTAI and prov["n_selected"] == 1
    assert prov["consumed_assessed_flash_sha256"] == p2["artifact_sha256"]
    assert prov["consumed_d7_split_sha256"] == p3a["artifact_sha256"]


# --------------------------------------------------- invariant 3: derived selection

def test_only_flashes_routing_to_this_stock_are_used(tmp_path):
    p2, p3a, rows = _chain(tmp_path, ["贵州茅台签订 12 亿元大单", "宁德时代扩产 20GWh"])
    art_m, prov_m = _assemble(p2, p3a, rows, ts_code=MAOTAI)
    art_c, prov_c = _assemble(p2, p3a, rows, ts_code=CATL, decision_id="d2")
    assert prov_m["n_selected"] == 1 and prov_c["n_selected"] == 1
    assert prov_m["selected_fact_occurrence_ids"] != prov_c["selected_fact_occurrence_ids"]
    assert art_m.artifact_hash != art_c.artifact_hash


def test_stock_with_no_routed_flash_yields_no_artifact(tmp_path):
    # invariant 7: an explicit NothingToDecide, never an empty-but-valid D7 artifact
    p2, p3a, rows = _chain(tmp_path, ["宁德时代扩产 20GWh"])
    with pytest.raises(NothingToDecide, match="无路由命中"):
        _assemble(p2, p3a, rows, ts_code=MAOTAI)


def test_macro_flash_is_not_selected(tmp_path):
    # P2 marks macro-routed flashes news_render_eligible=False; they never reach render
    p2, p3a, rows = _chain(tmp_path, ["央行今日开展逆回购", "贵州茅台签订 12 亿元大单"])
    _, prov = _assemble(p2, p3a, rows)
    assert prov["n_selected"] == 1


# --------------------------------------------------- invariant 1: chain binding

def test_split_artifact_from_a_different_run_refused(tmp_path):
    # two independent chains -> P3a's consumed-P2 SHA won't match the other chain's P2
    p2a, p3a_a, rows_a = _chain(tmp_path / "a", ["贵州茅台签订 12 亿元大单"])
    p2b, p3a_b, _ = _chain(tmp_path / "b", ["贵州茅台另一条重大公告"])
    with pytest.raises(ValueError, match="chain binding|DIFFERENT assessed"):
        assemble_stock_artifact(CUT, ingest_class="forward", ts_code=MAOTAI,
                                decision_id="d1", assessed_artifact=p2a,
                                split_artifact=p3a_b, source_rows=rows_a)


def test_identity_mismatch_refused(tmp_path):
    p2, p3a, rows = _chain(tmp_path, ["贵州茅台签订 12 亿元大单"])
    bad = dict(p2)
    bad["cutoff_iso"] = "2025-01-27T09:30:00"
    body = {k: v for k, v in bad.items() if k != "artifact_sha256"}
    bad["artifact_sha256"] = seal_hash(body)
    with pytest.raises(ValueError, match="does not match this run"):
        _assemble(bad, p3a, rows)


def test_forged_artifacts_refused(tmp_path):
    p2, p3a, rows = _chain(tmp_path, ["贵州茅台签订 12 亿元大单"])
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        _assemble({**p2, "artifact_sha256": "nope"}, p3a, rows)
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        _assemble(p2, {**p3a, "artifact_sha256": "nope"}, rows)


# --------------------------------------------------- invariant 2: source bound by recompute

def test_substituted_source_text_refused(tmp_path):
    p2, p3a, rows = _chain(tmp_path, ["贵州茅台签订 12 亿元大单"])
    forged = rows.copy()
    forged.loc[:, "content"] = "贵州茅台明年将签订 50 亿元大单(未来正文)"
    with pytest.raises(ValueError, match="未绑定|重算校验"):
        _assemble(p2, p3a, forged)


# --------------------------------------------------- invariant 4: exact split coverage

def test_missing_split_is_a_hard_error(tmp_path):
    p2, p3a, rows = _chain(tmp_path, ["贵州茅台签订 12 亿元大单"])
    stripped = json.loads(json.dumps(p3a, ensure_ascii=False))
    stripped["splits"] = []
    stripped["n_splits"] = 0
    stripped["population_hash"] = seal_hash([])
    body = {k: v for k, v in stripped.items() if k != "artifact_sha256"}
    stripped["artifact_sha256"] = seal_hash(body)      # validly re-sealed, but empty
    with pytest.raises(ValueError, match="无对应拆分|覆盖不全"):
        _assemble(p2, stripped, rows)


def test_below_floor_facts_need_no_split(tmp_path):
    # importance 3 -> no split required and none demanded
    p2, p3a, rows = _chain(tmp_path, ["贵州茅台签订 12 亿元大单"], importance=3)
    assert p3a["n_splits"] == 0
    art, prov = _assemble(p2, p3a, rows)
    assert prov["n_splits_used"] == 0
    assert verify_d7_artifact(art) == art


# --------------------------------------------------- invariant 6: decision_id discipline

@pytest.mark.parametrize("bad", ["", "   ", 5, None])
def test_bad_decision_id_refused(tmp_path, bad):
    p2, p3a, rows = _chain(tmp_path, ["贵州茅台签订 12 亿元大单"])
    with pytest.raises(ValueError, match="decision_id"):
        _assemble(p2, p3a, rows, decision_id=bad)


def test_bad_ts_code_refused(tmp_path):
    p2, p3a, rows = _chain(tmp_path, ["贵州茅台签订 12 亿元大单"])
    with pytest.raises(ValueError, match="ts_code"):
        _assemble(p2, p3a, rows, ts_code="")


# --------------------------------------------------- determinism

def test_deterministic_artifact_hash(tmp_path):
    p2, p3a, rows = _chain(tmp_path, ["贵州茅台签订 12 亿元大单"])
    a1, _ = _assemble(p2, p3a, rows)
    a2, _ = _assemble(p2, p3a, rows)
    assert a1.artifact_hash == a2.artifact_hash
