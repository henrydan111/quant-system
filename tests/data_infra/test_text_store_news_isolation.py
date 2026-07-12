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
