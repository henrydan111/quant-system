# NF wave review B1 + M5: history_bulk physical isolation + within-batch dedup.
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from data_infra.text_store import ingest_rows, load_text  # noqa: E402


def _news_rows(contents, dt="2020-03-01 10:00:00"):
    return pd.DataFrame([{"src": "sina", "datetime": dt, "content": c, "title": None,
                          "channels": ""} for c in contents])


def test_history_bulk_isolated_from_forward(tmp_path):
    # a 2020 flash BULK-ingested today (retrieved_at 2025) must NOT reach a forward
    # decision, even though its decision_visible_at (= max(pub, ingest)) <= cutoff.
    ingest_rows("news", _news_rows(["2020年的旧闻"]),
                published_col="datetime",
                retrieved_at=pd.Timestamp("2025-01-27 17:00:00"),
                store_dir=tmp_path, ingest_class="history_bulk")
    fwd = load_text("news", "2025-01-27 18:00:00", store_dir=tmp_path,
                    ingest_class="forward")
    assert fwd.empty                      # forward panel never sees bulk history

    bulk = load_text("news", "2025-01-27 18:00:00", store_dir=tmp_path,
                     ingest_class="history_bulk")
    assert len(bulk) == 1                 # it IS in the (NON_EVIDENTIARY) bulk panel


def test_forward_panel_visible_to_forward_loader(tmp_path):
    ingest_rows("news", _news_rows(["盘后快讯"], dt="2025-01-27 16:00:00"),
                published_col="datetime",
                retrieved_at=pd.Timestamp("2025-01-27 16:05:00"),
                store_dir=tmp_path, ingest_class="forward")
    fwd = load_text("news", "2025-01-27 18:00:00", store_dir=tmp_path,
                    ingest_class="forward")
    assert len(fwd) == 1


def test_within_batch_dedup(tmp_path):
    # M5: two identical flashes in ONE pull must persist as ONE row
    out = ingest_rows("news", _news_rows(["重复正文", "重复正文", "另一条"]),
                      published_col="datetime",
                      retrieved_at=pd.Timestamp("2025-01-27 16:05:00"),
                      store_dir=tmp_path, ingest_class="forward")
    stored = load_text("news", "2025-01-27 18:00:00", store_dir=tmp_path,
                       ingest_class="forward")
    assert stored["content_hash"].is_unique
    assert len(stored) == 2               # deduped 3 -> 2


def test_shared_hash_matches_fetcher(tmp_path):
    # M5: the fetcher's content hash helper must equal the store's stamped hash
    from data_infra.text_store import content_hash_for
    rows = _news_rows(["某条快讯正文"], dt="2025-01-27 16:00:00")
    out = ingest_rows("news", rows, published_col="datetime",
                      retrieved_at=pd.Timestamp("2025-01-27 16:05:00"),
                      store_dir=tmp_path, ingest_class="forward")
    fetch_hash = content_hash_for("news", rows.iloc[0], list(rows.columns))
    assert fetch_hash == out.iloc[0]["content_hash"]


def test_news_flat_path_ingest_rejected(tmp_path):
    # review B1: news without ingest_class MUST hard-fail (no flat-path bypass)
    import pytest
    from data_infra.text_store import TextStoreError
    with pytest.raises(TextStoreError, match="ingest_class"):
        ingest_rows("news", _news_rows(["x"]), published_col="datetime",
                    retrieved_at=pd.Timestamp("2025-01-27 16:00:00"),
                    store_dir=tmp_path)                # no ingest_class


def test_news_flat_path_load_rejected(tmp_path):
    import pytest
    from data_infra.text_store import TextStoreError
    with pytest.raises(TextStoreError, match="ingest_class"):
        load_text("news", "2025-01-27 18:00:00", store_dir=tmp_path)


def test_dedicated_forward_wrappers(tmp_path):
    from data_infra.text_store import ingest_forward_news, load_forward_news
    ingest_forward_news(_news_rows(["盘后"], dt="2025-01-27 16:00:00"),
                        retrieved_at=pd.Timestamp("2025-01-27 16:05:00"),
                        store_dir=tmp_path)
    assert len(load_forward_news("2025-01-27 18:00:00", store_dir=tmp_path)) == 1


def test_none_nan_missing_field_same_hash(tmp_path):
    # review M5: a row with title=None and title=NaN (same missing field) must
    # dedup to one (identical content_hash), not two
    r1 = pd.DataFrame([{"src": "sina", "datetime": "2025-01-27 16:00:00",
                        "content": "同正文", "title": None, "channels": ""}])
    r2 = pd.DataFrame([{"src": "sina", "datetime": "2025-01-27 16:00:00",
                        "content": "同正文", "title": float("nan"), "channels": ""}])
    from data_infra.text_store import content_hash_for
    h1 = content_hash_for("news", r1.iloc[0], list(r1.columns))
    h2 = content_hash_for("news", r2.iloc[0], list(r2.columns))
    assert h1 == h2                                   # None and NaN hash identically


def test_delimiter_injection_distinct_hash(tmp_path):
    # review B1: two DISTINCT news rows that collided under the flat key=value|
    # join (title="x|content=y",content="z" vs title="x",content="y|content=z")
    # must now hash DIFFERENTLY (structured JSON encoding, injection-proof) — else
    # they silently dedup to one row (data loss).
    from data_infra.text_store import content_hash_for
    cols = ["src", "datetime", "title", "content", "channels"]
    a = pd.Series({"src": "sina", "datetime": "2025-01-27 16:00:00",
                   "title": "x|content=y", "content": "z", "channels": ""})
    b = pd.Series({"src": "sina", "datetime": "2025-01-27 16:00:00",
                   "title": "x", "content": "y|content=z", "channels": ""})
    assert content_hash_for("news", a, cols) != content_hash_for("news", b, cols)


def test_news_missing_ingest_class_column_load_rejected(tmp_path):
    # review B3: a news partition that has lost its ingest_class column must fail
    # closed (an unstamped partition could leak history into a forward decision)
    import pytest
    from data_infra.text_store import TextStoreError, _store_path
    ingest_rows("news", _news_rows(["盘后"], dt="2025-01-27 16:00:00"),
                published_col="datetime",
                retrieved_at=pd.Timestamp("2025-01-27 16:05:00"),
                store_dir=tmp_path, ingest_class="forward")
    p = _store_path("news", tmp_path, "forward")
    pd.read_parquet(p).drop(columns=["ingest_class"]).to_parquet(p, index=False)
    with pytest.raises(TextStoreError, match="ingest_class"):
        load_text("news", "2025-01-27 18:00:00", store_dir=tmp_path,
                  ingest_class="forward")


def test_store_lock_released_and_serial_appends(tmp_path):
    # review B3: the transaction lock is cleaned up and a second ingest still
    # appends (lock re-acquired), never blocks
    from data_infra.text_store import _store_path
    ingest_rows("news", _news_rows(["一"], dt="2025-01-27 16:00:00"),
                published_col="datetime", retrieved_at=pd.Timestamp("2025-01-27 16:05:00"),
                store_dir=tmp_path, ingest_class="forward")
    p = _store_path("news", tmp_path, "forward")
    assert not (p.parent / (p.name + ".lock")).exists()   # lock dir cleaned up
    ingest_rows("news", _news_rows(["二"], dt="2025-01-27 16:01:00"),
                published_col="datetime", retrieved_at=pd.Timestamp("2025-01-27 16:06:00"),
                store_dir=tmp_path, ingest_class="forward")
    assert len(load_text("news", "2025-01-27 18:00:00", store_dir=tmp_path,
                         ingest_class="forward")) == 2
