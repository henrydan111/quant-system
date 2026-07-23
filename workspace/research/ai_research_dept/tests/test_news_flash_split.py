# NF integration P3a: market-wide D7 attribute splitting — declared-invariant tests.
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
    assess_day_flashes,
)
from workspace.research.ai_research_dept.engine.news_flash_split import (  # noqa: E402
    SplitConflictError, load_split_artifact, split_day_flashes, write_split_artifact,
)
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    type_day_flashes,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash  # noqa: E402

CUT = "2025-01-27 18:00:00"
IND = frozenset({"白酒"})
CON = frozenset({"消费"})
_CAL = pd.DatetimeIndex(pd.bdate_range("2025-01-02", "2025-03-31"))
_NC_COLS = ["ts_code", "name", "start_date", "end_date", "ann_date", "change_reason"]


def _stock_basic():
    return pd.DataFrame([{"ts_code": "600519.SH", "name": "贵州茅台",
                          "list_date": "20010827", "delist_date": None}])


def _namechange():
    return pd.DataFrame([{"ts_code": "600519.SH", "name": "贵州茅台",
                          "start_date": "20010827", "end_date": None,
                          "ann_date": "20010827", "change_reason": "上市"}],
                        columns=_NC_COLS)


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


def _splitter(span=None, **over):
    """Default: echo a verbatim prefix of the supplied content (a valid grounded span)."""
    def fn(msgs):
        payload = json.loads(msgs[1]["content"])
        out = []
        for it in payload["items"]:
            s = span if span is not None else it["content"][:12]
            out.append({"idx": it["idx"], "fact_span": s, **over})
        return _Reply(json.dumps({"results": out}, ensure_ascii=False))
    return fn


def _pipeline(tmp_path, contents_list, *, importance=5, typer_over=None):
    """P1 -> P2 -> the (assessed artifact, raw source rows) P3a consumes."""
    _ingest(tmp_path, contents_list)
    p1 = type_day_flashes(CUT, ingest_class="forward",
                          call_fn=_typer(importance, **(typer_over or {})),
                          store_dir=tmp_path)
    p2 = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1,
                            stock_basic=_stock_basic(), namechange=_namechange(),
                            open_calendar=_CAL, industry_terms=IND, concept_terms=CON,
                            store_dir=tmp_path)
    from data_infra.text_store import load_text
    rows = load_text("news", pd.Timestamp(CUT), store_dir=tmp_path, ingest_class="forward")
    return p2, rows


def _split(tmp_path, p2, rows, **kw):
    return split_day_flashes(CUT, ingest_class="forward", assessed_artifact=p2,
                             source_rows=rows, call_fn=kw.pop("call_fn", _splitter()), **kw)


# --------------------------------------------------- happy path

def test_splits_importance_ge_4_positive_facts(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    art = _split(tmp_path, p2, rows, call_fn=_splitter(span="签订 12 亿元大单"))
    assert art["artifact_schema"] == "nf_d7_split_v1" and art["n_splits"] == 1
    s = art["splits"][0]
    assert s["fact_occurrence_id"] == p2["assessed"][0]["cluster"]["fact_occurrence_id"]
    # the span is expanded to its enclosing sentence (here: the whole one-sentence source)
    assert s["attributes"]["fact"] == "贵州茅台签订 12 亿元大单"
    assert "economic_linkage" not in s["attributes"]            # deferred in v1
    assert s["evidence_class"] in ("NFD", "NFI", "NFA")


# --------------------------------------------------- GPT-P3a P0: source bound to P2

def test_p0_substituted_text_under_p2_hash_refused(tmp_path):
    # The reviewer's probe: point P2's content_hash at a DIFFERENT (future) text. Because
    # content_hash is recomputed from the row, the edited row no longer matches and the
    # population member has no verified source -> hard error (previously the future text
    # was accepted while the artifact still claimed the P2 SHA).
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    forged = rows.copy()
    forged.loc[:, "content"] = "贵州茅台明年将签订 50 亿元大单(未来正文)"
    with pytest.raises(ValueError, match="未绑定|重算校验"):
        _split(tmp_path, p2, forged)


def test_p0_rows_must_be_dataframe_and_cover_population(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    with pytest.raises(ValueError, match="DataFrame"):
        _split(tmp_path, p2, {"whatever": "text"})
    with pytest.raises(ValueError, match="无来源行|未绑定|重算校验"):
        _split(tmp_path, p2, rows.iloc[0:0])       # empty rows, non-empty population


# --------------------------------------------------- GPT-P3a P1: span grounding

@pytest.mark.parametrize("ungrounded", [
    "预计增厚年营收 15%",            # invented number/claim, not in the source
    "茅台签了个大单",                # paraphrase
    "",                              # empty
])
def test_p1_ungrounded_span_refused(tmp_path, ungrounded):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    with pytest.raises(ValueError, match="fact_span"):
        _split(tmp_path, p2, rows, call_fn=_splitter(span=ungrounded))


def test_p1_span_must_be_str(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    with pytest.raises(ValueError, match="fact_span"):
        _split(tmp_path, p2, rows, call_fn=_splitter(span=5))


def test_p1_negation_context_cannot_be_truncated(tmp_path):
    # GPT-P3a re-review#2 (P1), the reviewer's probe: the span IS verbatim, but cutting it
    # away from "It is false that" would invert the meaning and flow into
    # factor_positive/event_materiality. The deterministic sentence expansion keeps it.
    # (the subject name must be present so the flash routes to a stock and becomes a
    # POSITIVE class — a nameless English flash routes to macro and is never split)
    src = "It is false that 贵州茅台 signed a $12bn contract."
    p2, rows = _pipeline(tmp_path, [src])
    art = _split(tmp_path, p2, rows,
                 call_fn=_splitter(span="贵州茅台 signed a $12bn contract"))
    fact = art["splits"][0]["attributes"]["fact"]
    assert fact == src                       # full sentence, negation intact
    assert "It is false that" in fact


def test_p1_attribution_context_preserved_cn(tmp_path):
    # the Chinese equivalent: "有传闻称" must not be truncated off
    src = "有传闻称贵州茅台签订 12 亿元大单。"
    p2, rows = _pipeline(tmp_path, [src])
    art = _split(tmp_path, p2, rows, call_fn=_splitter(span="贵州茅台签订 12 亿元大单"))
    assert "有传闻称" in art["splits"][0]["attributes"]["fact"]


def test_p1_expansion_is_the_sentence_not_the_whole_source(tmp_path):
    # a multi-sentence source expands to the ENCLOSING sentence only
    p2, rows = _pipeline(tmp_path, ["公司发布澄清公告。贵州茅台签订 12 亿元大单。后续待跟踪。"])
    art = _split(tmp_path, p2, rows, call_fn=_splitter(span="贵州茅台签订 12 亿元大单"))
    fact = art["splits"][0]["attributes"]["fact"]
    assert fact == "贵州茅台签订 12 亿元大单。"
    assert "澄清公告" not in fact and "后续待跟踪" not in fact


def test_p1_decimal_is_not_a_sentence_boundary(tmp_path):
    # an ASCII '.' between digits is a decimal, not a terminator
    p2, rows = _pipeline(tmp_path, ["贵州茅台 revenue grew 12.5 percent this year."])
    art = _split(tmp_path, p2, rows, call_fn=_splitter(span="grew 12.5 percent"))
    assert art["splits"][0]["attributes"]["fact"] == \
        "贵州茅台 revenue grew 12.5 percent this year."


def test_p1_verbatim_span_accepted_and_expanded(tmp_path):
    # a valid partial span is accepted, and the emitted fact is its enclosing sentence
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    art = _split(tmp_path, p2, rows, call_fn=_splitter(span="贵州茅台签订"))
    assert art["splits"][0]["attributes"]["fact"] == "贵州茅台签订 12 亿元大单"


# --------------------------------------------------- invariant 3: derived population

def test_below_floor_importance_not_split(tmp_path):
    # importance 3 < D7 floor 4 -> no split required, no LLM call
    p2, contents = _pipeline(tmp_path, ["贵州茅台小事件"], importance=3)
    called = {"n": 0}

    def boom(msgs):
        called["n"] += 1
        raise AssertionError("must not call the splitter below the D7 floor")
    art = _split(tmp_path, p2, contents, call_fn=boom)
    assert art["n_splits"] == 0 and called["n"] == 0


def test_non_positive_class_not_split(tmp_path):
    # a rumor flash is NFR (not a positive class) -> never split even at importance 5
    p2, contents = _pipeline(tmp_path, ["市场传闻贵州茅台将重组"],
                             typer_over={"verification_status": "传闻", "is_rumor": True,
                                         "content_kind": "评论",
                                         "event_type": "传闻未证实"})
    art = _split(tmp_path, p2, contents)
    assert art["n_splits"] == 0


# --------------------------------------------------- invariant 2: P2 binding

def test_wrong_p2_identity_refused(tmp_path):
    p2, contents = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    bad = dict(p2)
    bad["cutoff_iso"] = "2025-01-27T09:30:00"
    body = {k: v for k, v in bad.items() if k != "artifact_sha256"}
    bad["artifact_sha256"] = seal_hash(body)      # re-seal so only IDENTITY differs
    with pytest.raises(ValueError, match="identity mismatch"):
        _split(tmp_path, bad, contents)


def test_forged_p2_dict_refused(tmp_path):
    p2, contents = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    forged = {**p2, "artifact_sha256": "not-verified"}
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        _split(tmp_path, forged, contents)


def test_consumed_p2_sha_bound(tmp_path):
    p2, contents = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    art = _split(tmp_path, p2, contents)
    assert art["consumed_assessed_flash_sha256"] == p2["artifact_sha256"]


# --------------------------------------------------- invariant 4: derived source_status

def test_source_status_is_derived_not_model_authored(tmp_path):
    # the splitter tries to inject its own source_status; the derived one wins
    p2, contents = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    art = _split(tmp_path, p2, contents,
                 call_fn=_splitter(source_status="来源状态:我说它是官方的"))
    ss = art["splits"][0]["attributes"]["source_status"]
    assert ss == "来源状态:公司/官方公告证实"       # from verification_status, not the model


def test_source_status_tracks_verification_status(tmp_path):
    p2, contents = _pipeline(tmp_path, ["署名媒体报道贵州茅台大单"],
                             typer_over={"verification_status": "署名媒体"})
    art = _split(tmp_path, p2, contents)
    assert "署名媒体" in art["splits"][0]["attributes"]["source_status"]


# --------------------------------------------------- invariant 5: text validation

def test_whitespace_only_span_refused(tmp_path):
    # a span that IS in the source but carries no substantive characters still fails the
    # frozen predicate (grounding alone is not enough)
    p2, rows = _pipeline(tmp_path, ["贵州茅台 签订大单"])
    with pytest.raises(ValueError, match="fact"):
        _split(tmp_path, p2, rows, call_fn=_splitter(span=" "))


# --------------------------------------------------- invariant 6/7: determinism, seal, empty

def test_deterministic_and_round_trip(tmp_path):
    p2, contents = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单", "贵州茅台再签 5 亿单"])
    a1 = _split(tmp_path, p2, contents)
    a2 = _split(tmp_path, p2, contents)
    assert a1["artifact_sha256"] == a2["artifact_sha256"]
    path = write_split_artifact(a1, tmp_path / "out")
    assert load_split_artifact(path)["artifact_sha256"] == a1["artifact_sha256"]


def test_tampered_artifact_refused(tmp_path):
    p2, contents = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    art = _split(tmp_path, p2, contents)
    path = write_split_artifact(art, tmp_path / "out")
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["splits"][0]["attributes"]["fact"] = "被篡改的事实"
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        load_split_artifact(path)


def test_write_once_refuses_different_content(tmp_path):
    # two sentences -> spans in DIFFERENT sentences expand to different facts
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单。同日另公告回购计划。"])
    a1 = _split(tmp_path, p2, rows, call_fn=_splitter(span="贵州茅台签订 12 亿元大单"))
    write_split_artifact(a1, tmp_path / "out")
    write_split_artifact(a1, tmp_path / "out")                 # idempotent
    a2 = _split(tmp_path, p2, rows, call_fn=_splitter(span="回购计划"))
    assert a2["artifact_sha256"] != a1["artifact_sha256"]
    with pytest.raises(SplitConflictError, match="write-once"):
        write_split_artifact(a2, tmp_path / "out")


def test_empty_population_no_llm_call(tmp_path):
    p2, contents = _pipeline(tmp_path, ["贵州茅台小事件"], importance=2)
    called = {"n": 0}

    def boom(msgs):
        called["n"] += 1
        raise AssertionError("no LLM call on an empty population")
    art = _split(tmp_path, p2, contents, call_fn=boom)
    assert art["n_splits"] == 0 and called["n"] == 0
    assert art["evidence_class"].endswith("NON_EVIDENTIARY")
