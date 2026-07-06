"""C1 test_stub: decision_visible_at = max(published, first_ingested), fail-closed.

Contract (CONTRACTS.md C1): information is actionable only once it is BOTH
published AND in our system. Nominal dates (trade_date/ann_date/...) are NEVER
visibility. Missing/nominal-only publication timestamp -> visible falls back to
first ingestion and the row is flagged (fixture-only for historical replay).
"""
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data_infra.text_store import TextStoreError, ingest_rows, load_text  # noqa: E402


def _raw(**kw):
    base = {"ts_code": "000001.SZ", "title": "公告A", "trade_date": "20260701"}
    base.update(kw)
    return pd.DataFrame([base])


def test_visible_is_max_of_published_and_ingested(tmp_path: Path):
    # published 09:30, ingested 10:15 -> visible 10:15 (NOT earliest)
    raw = _raw(pub_time="2026-07-01 09:30:00")
    ingest_rows("src_a", raw, published_col="pub_time",
                retrieved_at=pd.Timestamp("2026-07-01 10:15:00"), store_dir=tmp_path)
    assert load_text("src_a", "2026-07-01 09:45:00", store_dir=tmp_path).empty
    got = load_text("src_a", "2026-07-01 10:15:00", store_dir=tmp_path)
    assert len(got) == 1
    assert got["decision_visible_at"].iloc[0] == pd.Timestamp("2026-07-01 10:15:00")


def test_published_after_retrieval_gates_on_published(tmp_path: Path):
    # vendor stamps publication LATER than our fetch (clock/backdating) -> max rules
    raw = _raw(pub_time="2026-07-01 11:00:00")
    ingest_rows("src_b", raw, published_col="pub_time",
                retrieved_at=pd.Timestamp("2026-07-01 10:00:00"), store_dir=tmp_path)
    assert load_text("src_b", "2026-07-01 10:30:00", store_dir=tmp_path).empty
    assert len(load_text("src_b", "2026-07-01 11:00:00", store_dir=tmp_path)) == 1


def test_missing_published_falls_back_to_ingestion_and_flags(tmp_path: Path):
    raw = _raw()  # no pub_time at all (research_report-style: trade_date is NOMINAL)
    out = ingest_rows("src_c", raw, published_col=None,
                      retrieved_at=pd.Timestamp("2026-07-02 08:00:00"), store_dir=tmp_path)
    assert bool(out["published_missing"].iloc[0]) is True
    assert out["decision_visible_at"].iloc[0] == pd.Timestamp("2026-07-02 08:00:00")
    # the NOMINAL trade_date (20260701) must NOT make it visible on 07-01
    assert load_text("src_c", "2026-07-01 23:59:59", store_dir=tmp_path).empty


def test_loader_fails_closed_on_missing_stamp_columns(tmp_path: Path):
    # a parquet written outside ingest_rows (no stamps) must be REFUSED, not guessed
    src_dir = tmp_path / "src_d"
    src_dir.mkdir(parents=True)
    _raw().to_parquet(src_dir / "text_src_d.parquet", index=False)
    with pytest.raises(TextStoreError):
        load_text("src_d", "2026-07-05", store_dir=tmp_path)
