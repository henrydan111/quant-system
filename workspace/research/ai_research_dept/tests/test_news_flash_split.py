# NF integration P3a: market-wide D7 attribute splitting (v1 deterministic) — invariant tests.
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data_infra.text_store import ingest_rows, load_text  # noqa: E402
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
    rows = load_text("news", pd.Timestamp(CUT), store_dir=tmp_path, ingest_class="forward")
    return p2, rows


def _split(p2, rows):
    return split_day_flashes(CUT, ingest_class="forward", assessed_artifact=p2,
                             source_rows=rows)


# --------------------------------------------------- happy path

def test_splits_importance_ge_4_positive_facts(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    art = _split(p2, rows)
    assert art["artifact_schema"] == "nf_d7_split_v3" and art["n_splits"] == 1
    assert art["fact_mode"] == "deterministic_whole_source_v2"
    s = art["splits"][0]
    assert s["fact_occurrence_id"] == p2["assessed"][0]["cluster"]["fact_occurrence_id"]
    assert s["attributes"]["fact"] == "贵州茅台签订 12 亿元大单"     # the WHOLE source
    assert "economic_linkage" not in s["attributes"]              # deferred in v1
    assert s["evidence_class"] in ("NFD", "NFI", "NFA")


# --------------------------------------------------- invariant 5: nothing is truncated

def test_neighbouring_sentence_qualifier_preserved(tmp_path):
    # GPT-P3a re-review#3: sentence expansion still dropped a qualifier living in the
    # PREVIOUS sentence. v1 emits the whole source, so it cannot be de-contextualized.
    src = "公司否认该报道。贵州茅台签订 12 亿元大单。"
    p2, rows = _pipeline(tmp_path, [src])
    art = _split(p2, rows)
    assert art["splits"][0]["attributes"]["fact"] == src
    assert "公司否认该报道" in art["splits"][0]["attributes"]["fact"]


def test_same_sentence_negation_preserved(tmp_path):
    src = "It is false that 贵州茅台 signed a $12bn contract."
    p2, rows = _pipeline(tmp_path, [src])
    assert _split(p2, rows)["splits"][0]["attributes"]["fact"] == src


def test_newline_separated_headline_body_preserved(tmp_path):
    # a headline/body newline used to end the "sentence" and drop the body (or the headline)
    src = "澄清公告\n此前关于贵州茅台签订 12 亿元大单的报道不实。"
    p2, rows = _pipeline(tmp_path, [src])
    fact = _split(p2, rows)["splits"][0]["attributes"]["fact"]
    assert "澄清公告" in fact and "不实" in fact


@pytest.mark.parametrize("ch, name", [
    ("\n", "LF"), ("\r", "CR"), ("\t", "TAB"), ("", "NEL"),
    ("‍", "ZWJ"), ("‌", "ZWNJ"), ("​", "ZWSP"),
    (" ", "LS"), (" ", "PS"), ("﻿", "BOM"), ("­", "SHY"),
])
def test_sanitizer_deleted_char_never_fuses_words(tmp_path, ch, name):
    # GPT-P3a re-review#5 (P2): the frozen sanitizer DELETES Cc/Cf, so any such character
    # between two words fused them ("doesnot" -> "doesnot") and could silently
    # destroy a negation the whole-source contract exists to preserve.
    p2, rows = _pipeline(tmp_path, [f"贵州茅台 does{ch}not have a contract."])
    fact = _split(p2, rows)["splits"][0]["attributes"]["fact"]
    assert "doesnot" not in fact, f"{name} fused the words"
    assert "does not" in fact


def test_every_sanitizer_deleted_codepoint_is_a_boundary():
    # STRUCTURAL guard (not a sample): enumerate every codepoint the frozen sanitizer
    # deletes and assert the pre-pass turns it into a boundary. Enumerating separators is
    # what kept failing (CR/LF -> then NEL/Tab/ZWJ); this mirrors the sanitizer's own
    # predicate, so a codepoint we never thought of cannot fuse tokens either.
    import unicodedata as ud
    from workspace.research.ai_research_dept.engine.cards import sanitize_text
    from workspace.research.ai_research_dept.engine.news_flash_split import (
        _space_out_deleted_controls,
    )
    fused = []
    for cp in range(0x110000):
        ch = chr(cp)
        if ud.category(ch) not in ("Cc", "Cf"):
            continue
        out = sanitize_text(_space_out_deleted_controls(f"does{ch}not"))
        if "doesnot" in out:
            fused.append(hex(cp))
    assert not fused, f"{len(fused)} sanitizer-deleted codepoints still fuse words: {fused[:8]}"


def test_newline_becomes_a_space_not_a_fused_word(tmp_path):
    # GPT-P3a re-review#4 (P2): the frozen sanitizer DELETES control chars, so a raw
    # newline fused the words across it ("does\nnot" -> "doesnot"), destroying a word
    # boundary. Line separators are replaced by a space BEFORE sanitizing.
    p2, rows = _pipeline(tmp_path, ["贵州茅台 does\nnot have a contract."])
    fact = _split(p2, rows)["splits"][0]["attributes"]["fact"]
    assert "does not" in fact and "doesnot" not in fact


# --------------------------------------------------- GPT-P3a re-review#4 P1: read-boundary contract

def test_spoofed_extraction_mode_refused(tmp_path):
    # a properly re-sealed artifact claiming an LLM extraction mode is refused
    # (the superseded-version matrix below covers the schema/derivation dimension)
    from workspace.research.ai_research_dept.engine.news_flash_split import (
        verify_split_artifact,
    )
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    spoofed = json.loads(json.dumps(_split(p2, rows), ensure_ascii=False))
    spoofed["fact_mode"] = "llm_span_v0"
    body = {k: v for k, v in spoofed.items() if k != "artifact_sha256"}
    spoofed["artifact_sha256"] = seal_hash(body)
    with pytest.raises(ValueError, match="fact_mode"):
        verify_split_artifact(spoofed)


def test_artifact_path_tracks_schema_version(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    path = write_split_artifact(_split(p2, rows), tmp_path / "out")
    assert path.name.startswith("nf_d7_split_v3_")


@pytest.mark.parametrize("schema, mode", [
    ("nf_d7_split_v1", None),                              # LLM era, no fact_mode
    ("nf_d7_split_v2", "deterministic_whole_source_v1"),   # pre-boundary-fix (word-fused)
    ("nf_d7_split_v3", "deterministic_whole_source_v1"),   # right shape, stale derivation
])
def test_superseded_artifact_versions_refused(tmp_path, schema, mode):
    # GPT-P3a re-review#6: the Cc/Cf boundary fix CHANGED the derived fact text for the
    # same input, so the version had to move with it. A validly-sealed artifact from ANY
    # older schema/derivation must be refused - otherwise a stale word-fused fact reaches
    # P3b while a corrected regeneration collides with write-once at the same path.
    from workspace.research.ai_research_dept.engine.news_flash_split import (
        verify_split_artifact,
    )
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    old = json.loads(json.dumps(_split(p2, rows), ensure_ascii=False))
    old["artifact_schema"] = schema
    if mode is None:
        old.pop("fact_mode", None)
    else:
        old["fact_mode"] = mode
    body = {k: v for k, v in old.items() if k != "artifact_sha256"}
    old["artifact_sha256"] = seal_hash(body)               # PROPERLY sealed, still refused
    with pytest.raises(ValueError, match="nf_d7_split_v3|fact_mode"):
        verify_split_artifact(old)


def test_v3_path_does_not_collide_with_a_stale_v2_file(tmp_path):
    # a leftover v2 file on disk must not block the corrected v3 write
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    art = _split(p2, rows)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    stale = out / f"nf_d7_split_v2_forward_{pd.Timestamp(CUT).strftime('%Y%m%dT%H%M%S%f')}.json"
    stale.write_text(json.dumps({"artifact_schema": "nf_d7_split_v2"}, ensure_ascii=False),
                     encoding="utf-8")
    path = write_split_artifact(art, out)                  # no write-once conflict
    assert path != stale and path.exists() and stale.exists()


def test_abbreviation_does_not_truncate(tmp_path):
    # "U.S." used to look like a sentence boundary and could strip a leading qualifier
    src = "The report is false. 贵州茅台 has no U.S. contract."
    p2, rows = _pipeline(tmp_path, [src])
    assert "The report is false" in _split(p2, rows)["splits"][0]["attributes"]["fact"]


# --------------------------------------------------- invariant 6: no LLM at all

def test_split_takes_no_llm_callable(tmp_path):
    # v1 is deterministic: the API accepts no call_fn, so no extraction can be injected
    import inspect
    from workspace.research.ai_research_dept.engine import news_flash_split as mod
    params = set(inspect.signature(mod.split_day_flashes).parameters)
    assert "call_fn" not in params and "batch" not in params
    assert not hasattr(mod, "_extract_batch")


def test_deterministic_and_round_trip(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单", "贵州茅台再签 5 亿元订单"])
    a1, a2 = _split(p2, rows), _split(p2, rows)
    assert a1["artifact_sha256"] == a2["artifact_sha256"]
    path = write_split_artifact(a1, tmp_path / "out")
    assert load_split_artifact(path)["artifact_sha256"] == a1["artifact_sha256"]


# --------------------------------------------------- invariant 3: derived population

def test_below_floor_importance_not_split(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台小事件"], importance=3)
    assert _split(p2, rows)["n_splits"] == 0


def test_non_positive_class_not_split(tmp_path):
    p2, rows = _pipeline(tmp_path, ["市场传闻贵州茅台将重组"],
                         typer_over={"verification_status": "传闻", "is_rumor": True,
                                     "content_kind": "评论", "event_type": "传闻未证实"})
    assert _split(p2, rows)["n_splits"] == 0


# --------------------------------------------------- invariant 1: source bound to P2

def test_substituted_text_under_p2_hash_refused(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    forged = rows.copy()
    forged.loc[:, "content"] = "贵州茅台明年将签订 50 亿元大单(未来正文)"
    with pytest.raises(ValueError, match="未绑定|重算校验"):
        _split(p2, forged)


def test_rows_must_be_dataframe_and_cover_population(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    with pytest.raises(ValueError, match="DataFrame"):
        _split(p2, {"whatever": "text"})
    with pytest.raises(ValueError, match="无来源行|未绑定|重算校验"):
        _split(p2, rows.iloc[0:0])


# --------------------------------------------------- invariant 2: P2 binding

def test_wrong_p2_identity_refused(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    bad = dict(p2)
    bad["cutoff_iso"] = "2025-01-27T09:30:00"
    body = {k: v for k, v in bad.items() if k != "artifact_sha256"}
    bad["artifact_sha256"] = seal_hash(body)
    with pytest.raises(ValueError, match="identity mismatch"):
        _split(bad, rows)


def test_forged_p2_dict_refused(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        _split({**p2, "artifact_sha256": "not-verified"}, rows)


def test_consumed_p2_sha_bound(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    assert _split(p2, rows)["consumed_assessed_flash_sha256"] == p2["artifact_sha256"]


# --------------------------------------------------- invariant 4: derived source_status

def test_source_status_tracks_verification_status(tmp_path):
    p2, rows = _pipeline(tmp_path, ["署名媒体报道贵州茅台大单"],
                         typer_over={"verification_status": "署名媒体"})
    assert "署名媒体" in _split(p2, rows)["splits"][0]["attributes"]["source_status"]


def test_official_source_status(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    assert _split(p2, rows)["splits"][0]["attributes"]["source_status"] == \
        "来源状态:公司/官方公告证实"


# --------------------------------------------------- persistence / empty

def test_tampered_artifact_refused(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    art = _split(p2, rows)
    path = write_split_artifact(art, tmp_path / "out")
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["splits"][0]["attributes"]["fact"] = "被篡改的事实"
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        load_split_artifact(path)


def test_write_once_refuses_different_content(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台签订 12 亿元大单"])
    a1 = _split(p2, rows)
    write_split_artifact(a1, tmp_path / "out")
    write_split_artifact(a1, tmp_path / "out")                 # idempotent
    tampered = json.loads(json.dumps(a1, ensure_ascii=False))
    tampered["splits"][0]["attributes"]["fact"] = "另一种正文"
    body = {k: v for k, v in tampered.items() if k != "artifact_sha256"}
    tampered["artifact_sha256"] = seal_hash(body)
    with pytest.raises(SplitConflictError, match="write-once"):
        write_split_artifact(tampered, tmp_path / "out")


def test_empty_population(tmp_path):
    p2, rows = _pipeline(tmp_path, ["贵州茅台小事件"], importance=2)
    art = _split(p2, rows)
    assert art["n_splits"] == 0 and art["evidence_class"].endswith("NON_EVIDENTIARY")
