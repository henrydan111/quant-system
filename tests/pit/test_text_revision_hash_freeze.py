"""C1 test_stub: content-hash version freeze — revisions are NEW rows, append-only.

Contract (CONTRACTS.md C1): a loader at decision time T may only see content
versions whose hash already existed at T; a later revision never rewrites or
hides the original. Includes the contract-mandated case: a row whose nominal
trade_date <= decision_date but ingested_at > decision_date is EXCLUDED.
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data_infra.text_store import ingest_rows, load_text  # noqa: E402


def test_revision_creates_new_row_original_frozen(tmp_path: Path):
    v1 = pd.DataFrame([{"ts_code": "000002.SZ", "title": "盈利预告",
                        "content": "净利 1.0亿", "pub_time": "2026-07-01 09:00:00"}])
    ingest_rows("ann", v1, published_col="pub_time",
                retrieved_at=pd.Timestamp("2026-07-01 09:30:00"), store_dir=tmp_path)
    # vendor silently REVISES the content; we fetch it two days later
    v2 = v1.assign(content="净利 0.6亿(更正)")
    ingest_rows("ann", v2, published_col="pub_time",
                retrieved_at=pd.Timestamp("2026-07-03 09:30:00"), store_dir=tmp_path)

    at_0702 = load_text("ann", "2026-07-02", store_dir=tmp_path)
    assert len(at_0702) == 1 and at_0702["content"].iloc[0] == "净利 1.0亿"

    at_0704 = load_text("ann", "2026-07-04", store_dir=tmp_path)
    assert len(at_0704) == 2  # both versions known by now, original untouched
    assert set(at_0704["content"]) == {"净利 1.0亿", "净利 0.6亿(更正)"}
    assert at_0704["content_hash"].nunique() == 2


def test_nominal_date_before_decision_but_ingested_after_is_excluded(tmp_path: Path):
    # THE contract-mandated fixture: trade_date <= decision_date, ingested AFTER
    raw = pd.DataFrame([{"ts_code": "000002.SZ", "title": "研报",
                         "trade_date": "20260620"}])  # nominal only
    ingest_rows("rr3", raw, published_col=None,
                retrieved_at=pd.Timestamp("2026-07-05 08:00:00"), store_dir=tmp_path)
    # decision at 06-25: trade_date says "already published" — ingestion says NO
    assert load_text("rr3", "2026-06-25", store_dir=tmp_path).empty
    assert len(load_text("rr3", "2026-07-05 08:00:00", store_dir=tmp_path)) == 1
