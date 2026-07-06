"""C1 test_stub: historical backfill can NEVER fake historical visibility.

Contract (CONTRACTS.md C1 + R7-B4): a row published long ago but ingested today
has decision_visible_at = today; it is fixture-only for any decision before its
ingestion. This is the reason "historical text alpha is largely non-validatable"
— the clean path is forward accumulation.
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data_infra.text_store import ingest_rows, load_text  # noqa: E402


def test_backfilled_old_publication_not_visible_historically(tmp_path: Path):
    raw = pd.DataFrame([{
        "ts_code": "600000.SH",
        "title": "一年前的研报",
        "pub_time": "2025-01-10 09:00:00",   # published long ago
    }])
    ingest_rows("rr", raw, published_col="pub_time",
                retrieved_at=pd.Timestamp("2026-07-06 20:00:00"),  # backfilled NOW
                store_dir=tmp_path)

    # NOT visible at any historical decision time after publication
    assert load_text("rr", "2025-02-01", store_dir=tmp_path).empty
    assert load_text("rr", "2026-07-06 19:00:00", store_dir=tmp_path).empty
    # visible only from ingestion onward
    got = load_text("rr", "2026-07-06 20:00:00", store_dir=tmp_path)
    assert len(got) == 1
    assert got["decision_visible_at"].iloc[0] == pd.Timestamp("2026-07-06 20:00:00")


def test_reingest_does_not_backdate_first_ingested(tmp_path: Path):
    raw = pd.DataFrame([{"ts_code": "600000.SH", "title": "T",
                         "pub_time": "2026-07-01 09:00:00"}])
    ingest_rows("rr2", raw, published_col="pub_time",
                retrieved_at=pd.Timestamp("2026-07-01 10:00:00"), store_dir=tmp_path)
    # identical content re-fetched later must keep the ORIGINAL first_ingested_at
    ingest_rows("rr2", raw, published_col="pub_time",
                retrieved_at=pd.Timestamp("2026-07-03 10:00:00"), store_dir=tmp_path)
    got = load_text("rr2", "2026-07-02", store_dir=tmp_path)
    assert len(got) == 1  # deduped, not duplicated
    assert got["first_ingested_at"].iloc[0] == pd.Timestamp("2026-07-01 10:00:00")
