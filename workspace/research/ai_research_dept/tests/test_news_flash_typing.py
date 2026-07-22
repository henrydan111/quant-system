# NF integration P1: market-wide news-flash typing driver — declared-invariant tests.
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data_infra.text_store import ingest_rows  # noqa: E402
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    load_typed_flash_artifact, type_day_flashes, write_typed_flash_artifact,
)

CUT = "2025-01-27 18:00:00"


def _news_rows(contents, dt="2025-01-27 16:00:00"):
    return pd.DataFrame([{"src": "sina", "datetime": dt, "content": c, "title": None,
                          "channels": ""} for c in contents])


def _ingest(tmp_path, contents, *, dt="2025-01-27 16:00:00", ingest_class="forward",
            retrieved_at="2025-01-27 17:00:00"):
    ingest_rows("news", _news_rows(contents, dt), published_col="datetime",
                retrieved_at=pd.Timestamp(retrieved_at),
                store_dir=tmp_path, ingest_class=ingest_class)


class _Reply:
    def __init__(self, text):
        self.text = text


def _stub_typer(**overrides):
    """A deterministic stub call_fn: types every item as a plain fact, echoing the
    request idx set so type_batch's exact-idx contract is satisfied."""
    def fn(msgs):
        payload = json.loads(msgs[1]["content"])
        base = {"event_type": "订单合同", "verification_status": "官方证实",
                "content_kind": "事实", "direction": "利好", "importance": 5,
                "is_rumor": False, **overrides}
        return _Reply(json.dumps({"results": [
            {"idx": it["idx"], **base} for it in payload["items"]]}, ensure_ascii=False))
    return fn


# --------------------------------------------------- happy path

def test_types_visible_flashes(tmp_path):
    _ingest(tmp_path, ["签订 12 亿大单", "另一条快讯"])
    art = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                           store_dir=tmp_path)
    assert art["artifact_schema"] == "nf_typed_flash_v1"
    assert art["n_flashes"] == 2
    assert all(set(t["typing"]) == {"event_type", "verification_status",
                                    "content_kind", "direction", "importance",
                                    "is_rumor"} for t in art["typed"])
    assert all(t["typing"]["event_type"] == "订单合同" for t in art["typed"])


# --------------------------------------------------- invariant 1: PIT (mechanical)

def test_cutoff_excludes_future_visible_flashes(tmp_path):
    # a flash visible AFTER the cutoff must never be typed — load_text's PIT gate.
    _ingest(tmp_path, ["cutoff 前"], dt="2025-01-27 16:00:00")
    _ingest(tmp_path, ["cutoff 后"], dt="2025-01-28 10:00:00")
    art = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                           store_dir=tmp_path)
    previews = [t["content_preview"] for t in art["typed"]]
    assert previews == ["cutoff 前"]
    # every typed row's carried visibility is <= cutoff
    assert all(pd.Timestamp(t["decision_visible_at"]) <= pd.Timestamp(CUT)
               for t in art["typed"])


def test_every_typed_row_is_cutoff_bound_after_type(tmp_path):
    # defence-in-depth mechanical assertion over the whole artifact
    _ingest(tmp_path, ["a", "b", "c"])
    art = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                           store_dir=tmp_path)
    cut = pd.Timestamp(CUT)
    assert art["typed"] and all(
        pd.Timestamp(t["decision_visible_at"]) <= cut for t in art["typed"])


# --------------------------------------------------- invariant 2: ingest_class isolation

def test_forward_run_never_sees_history_bulk(tmp_path):
    # ingest one forward + one history_bulk flash; each run sees only its own panel
    _ingest(tmp_path, ["2020 旧闻"], dt="2020-03-01 10:00:00", ingest_class="history_bulk")
    _ingest(tmp_path, ["盘后 forward 快讯"], dt="2025-01-27 16:00:00", ingest_class="forward")
    fwd = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                           store_dir=tmp_path)
    assert fwd["n_flashes"] == 1 and fwd["typed"][0]["content_preview"] == "盘后 forward 快讯"
    bulk = type_day_flashes(CUT, ingest_class="history_bulk", call_fn=_stub_typer(),
                            store_dir=tmp_path)
    assert bulk["n_flashes"] == 1 and bulk["typed"][0]["content_preview"] == "2020 旧闻"
    assert bulk["ingest_class"] == "history_bulk"


def test_bad_ingest_class_refused(tmp_path):
    with pytest.raises(ValueError, match="ingest_class"):
        type_day_flashes(CUT, ingest_class="live", call_fn=_stub_typer(),
                         store_dir=tmp_path)


# --------------------------------------------------- invariant 3: typed once per content

def test_each_distinct_content_typed_exactly_once(tmp_path):
    # the store guarantees content_hash uniqueness (dedups on ingest); P1 types each
    # distinct store row exactly once — #LLM items == #distinct content_hashes.
    _ingest(tmp_path, ["快讯一", "快讯二", "快讯三"])
    calls = {"n": 0}
    base = _stub_typer()

    def counting(msgs):
        calls["n"] += len(json.loads(msgs[1]["content"])["items"])
        return base(msgs)
    art = type_day_flashes(CUT, ingest_class="forward", call_fn=counting,
                           store_dir=tmp_path)
    assert art["n_flashes"] == 3
    assert calls["n"] == 3                  # each distinct content typed exactly once


def test_distinct_flashes_dedups_shared_content_hash(tmp_path):
    # P1's defensive dedup: two rows sharing a content_hash collapse to one, keeping
    # the EARLIEST visibility as representative (belt-and-suspenders vs the store).
    from workspace.research.ai_research_dept.engine.news_flash_typing import (
        _distinct_flashes,
    )
    df = pd.DataFrame([
        {"content_hash": "a" * 64, "object_id_hash": "o1", "src": "sina",
         "content": "晚到的副本", "decision_visible_at": "2025-01-27 16:00:00"},
        {"content_hash": "a" * 64, "object_id_hash": "o0", "src": "sina",
         "content": "早到的副本", "decision_visible_at": "2025-01-27 09:00:00"},
        {"content_hash": "b" * 64, "object_id_hash": "o2", "src": "em",
         "content": "另一条", "decision_visible_at": "2025-01-27 10:00:00"},
    ])
    out = _distinct_flashes(df, pd.Timestamp(CUT))
    assert [f["content_hash"] for f in out] == ["a" * 64, "b" * 64]   # sorted, deduped
    a = next(f for f in out if f["content_hash"] == "a" * 64)
    assert a["decision_visible_at"].startswith("2025-01-27T09:00:00")   # earliest kept


# --------------------------------------------------- invariant 4: deterministic/idempotent

def test_deterministic_artifact_hash(tmp_path):
    _ingest(tmp_path, ["z 最后", "a 最先", "m 中间"])
    a1 = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                          store_dir=tmp_path)
    a2 = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                          store_dir=tmp_path)
    assert a1["artifact_sha256"] == a2["artifact_sha256"]
    # output sorted by content_hash (position-independent join)
    hashes = [t["content_hash"] for t in a1["typed"]]
    assert hashes == sorted(hashes)


# --------------------------------------------------- invariant 5: fail-closed persistence

def test_write_load_round_trip(tmp_path):
    _ingest(tmp_path, ["落盘再读"])
    art = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                           store_dir=tmp_path)
    path = write_typed_flash_artifact(art, tmp_path / "out")
    loaded = load_typed_flash_artifact(path)
    assert loaded["artifact_sha256"] == art["artifact_sha256"]


def test_tampered_artifact_refused(tmp_path):
    _ingest(tmp_path, ["原始"])
    art = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                           store_dir=tmp_path)
    path = write_typed_flash_artifact(art, tmp_path / "out")
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["typed"][0]["typing"]["importance"] = 0     # tamper, keep old hash
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        load_typed_flash_artifact(path)


def test_population_hash_detects_added_flash(tmp_path):
    _ingest(tmp_path, ["一"])
    art = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                           store_dir=tmp_path)
    path = write_typed_flash_artifact(art, tmp_path / "out")
    obj = json.loads(path.read_text(encoding="utf-8"))
    # append a forged typed row AND fix artifact_sha256, but not population_hash
    obj["typed"].append({**obj["typed"][0], "content_hash": "f" * 64})
    from workspace.research.ai_research_dept.engine.news_seal import seal_hash
    body = {k: v for k, v in obj.items() if k != "artifact_sha256"}
    obj["artifact_sha256"] = seal_hash(body)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="population_hash mismatch"):
        load_typed_flash_artifact(path)


# --------------------------------------------------- invariant 6: NON_EVIDENTIARY / empty

def test_existing_forward_panel_empty_before_cutoff(tmp_path):
    # GPT-P1 Blocker-1: an EXISTING forward panel with no rows before cutoff is a real
    # empty artifact (not 'source unavailable') and must not call the typer. The panel
    # exists (a flash visible AFTER cutoff), so load_text(require_exists=True) passes.
    _ingest(tmp_path, ["cutoff 之后才可见"], dt="2025-01-28 10:00:00")
    called = {"n": 0}

    def boom(msgs):
        called["n"] += 1
        raise AssertionError("must not call the typer on an empty population")
    art = type_day_flashes(CUT, ingest_class="forward", call_fn=boom,
                           store_dir=tmp_path)
    assert art["n_flashes"] == 0 and called["n"] == 0
    assert art["evidence_class"].endswith("NON_EVIDENTIARY")


def test_missing_forward_store_raises(tmp_path):
    # GPT-P1 Blocker-1: a MISSING forward store is 'data unavailable', a hard error —
    # never a legitimate zero-news NON_EVIDENTIARY result.
    from data_infra.text_store import TextStoreError
    called = {"n": 0}

    def boom(msgs):
        called["n"] += 1
        return _stub_typer()(msgs)
    with pytest.raises(TextStoreError, match="required text store missing"):
        type_day_flashes(CUT, ingest_class="forward", call_fn=boom, store_dir=tmp_path)
    assert called["n"] == 0


def test_missing_history_bulk_store_tolerated(tmp_path):
    # history_bulk replay of a never-backfilled day is legitimately empty (opt-in
    # require_exists stays off by default for the replay panel).
    art = type_day_flashes(CUT, ingest_class="history_bulk", call_fn=_stub_typer(),
                           store_dir=tmp_path)
    assert art["n_flashes"] == 0


def test_different_cutoffs_same_day_distinct_files(tmp_path):
    # GPT-P1 Blocker-2: 09:30 and 18:00 on the same day must not collide.
    _ingest(tmp_path, ["盘前快讯"], dt="2025-01-27 09:00:00",
            retrieved_at="2025-01-27 09:00:00")
    _ingest(tmp_path, ["盘后快讯"], dt="2025-01-27 16:00:00",
            retrieved_at="2025-01-27 16:00:00")
    a_am = type_day_flashes("2025-01-27 09:30:00", ingest_class="forward",
                            call_fn=_stub_typer(), store_dir=tmp_path)
    a_pm = type_day_flashes("2025-01-27 18:00:00", ingest_class="forward",
                            call_fn=_stub_typer(), store_dir=tmp_path)
    p_am = write_typed_flash_artifact(a_am, tmp_path / "out")
    p_pm = write_typed_flash_artifact(a_pm, tmp_path / "out")
    assert p_am != p_pm and p_am.exists() and p_pm.exists()
    assert a_am["n_flashes"] == 1 and a_pm["n_flashes"] == 2   # am sees only 盘前


def test_subsecond_cutoffs_do_not_collide(tmp_path):
    # GPT-P1 re-review#2: two sub-second cutoffs must map to DISTINCT artifact paths
    # (second-only stamping collapsed them onto one identity and spuriously conflicted).
    _ingest(tmp_path, ["盘前"], dt="2025-01-27 09:00:00", retrieved_at="2025-01-27 09:00:00")
    a1 = type_day_flashes("2025-01-27 09:30:00.100000", ingest_class="forward",
                          call_fn=_stub_typer(), store_dir=tmp_path)
    a2 = type_day_flashes("2025-01-27 09:30:00.900000", ingest_class="forward",
                          call_fn=_stub_typer(), store_dir=tmp_path)
    p1 = write_typed_flash_artifact(a1, tmp_path / "out")
    p2 = write_typed_flash_artifact(a2, tmp_path / "out")
    assert p1 != p2 and p1.exists() and p2.exists()


def test_tz_offset_cutoff_canonicalized_to_shanghai_identity(tmp_path):
    # GPT-P1 re-review#2: a tz-aware cutoff is canonicalized to Shanghai-naive, so
    # 18:00+08:00 (== 18:00 Shanghai) and 18:00+09:00 (== 17:00 Shanghai) are DISTINCT
    # identities, and 18:00+08:00 equals the naive "18:00" identity.
    _ingest(tmp_path, ["盘后"], dt="2025-01-27 16:00:00")
    a_08 = type_day_flashes("2025-01-27 18:00:00+08:00", ingest_class="forward",
                            call_fn=_stub_typer(), store_dir=tmp_path)
    a_09 = type_day_flashes("2025-01-27 18:00:00+09:00", ingest_class="forward",
                            call_fn=_stub_typer(), store_dir=tmp_path)
    a_naive = type_day_flashes("2025-01-27 18:00:00", ingest_class="forward",
                               call_fn=_stub_typer(), store_dir=tmp_path)
    assert a_08["cutoff_iso"] == a_naive["cutoff_iso"] == "2025-01-27T18:00:00"
    assert a_09["cutoff_iso"] == "2025-01-27T17:00:00"      # +09:00 -> 17:00 Shanghai
    p08 = write_typed_flash_artifact(a_08, tmp_path / "out")
    p09 = write_typed_flash_artifact(a_09, tmp_path / "out")
    assert p08 != p09
    # 18:00+08:00 and naive 18:00 are the SAME identity -> idempotent, no conflict
    assert write_typed_flash_artifact(a_naive, tmp_path / "out") == p08


def test_write_once_refuses_different_content(tmp_path):
    # GPT-P1 Blocker-2: a re-typing with a DIFFERENT valid classification must not
    # overwrite a possibly-consumed artifact; an identical re-write is idempotent.
    from workspace.research.ai_research_dept.engine.news_flash_typing import (
        TypedFlashConflictError,
    )
    _ingest(tmp_path, ["同一条快讯"])
    a1 = type_day_flashes(CUT, ingest_class="forward", call_fn=_stub_typer(),
                          store_dir=tmp_path)
    write_typed_flash_artifact(a1, tmp_path / "out")
    # idempotent: identical artifact re-writes fine
    write_typed_flash_artifact(a1, tmp_path / "out")
    # different valid typing (importance 5 -> 3) for the SAME (class, cutoff)
    a2 = type_day_flashes(CUT, ingest_class="forward",
                          call_fn=_stub_typer(importance=3), store_dir=tmp_path)
    assert a2["artifact_sha256"] != a1["artifact_sha256"]
    with pytest.raises(TypedFlashConflictError, match="write-once"):
        write_typed_flash_artifact(a2, tmp_path / "out")
