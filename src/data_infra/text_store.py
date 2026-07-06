"""C1 · PIT text store (CONTRACTS.md C1, gates Phase 2A).

Append-only, hash-versioned store for external text (research reports, exchange
Q&A, announcements, news). Every row is stamped at ingestion:

- ``source_published_at`` — the VERIFIED publication timestamp parsed from the
  source's own timestamp column (NaT when the source offers only a nominal
  date such as ``trade_date``/``ann_date`` — nominal dates are NEVER visibility);
- ``retrieved_at`` / ``first_ingested_at`` — our clocks; a re-ingest of
  identical content NEVER backdates or overwrites ``first_ingested_at``;
- ``decision_visible_at = max(source_published_at, first_ingested_at)`` —
  information is actionable only once it is BOTH published AND in our system
  (the R5-B1 ``max``-not-``earliest`` rule); missing/nominal publication falls
  back to ``first_ingested_at`` with ``published_missing=True`` (fixture-only
  for historical replay);
- ``content_hash`` — sha256 over source + all raw fields; a silent vendor
  REVISION becomes a NEW row (new hash), the original row is frozen forever.

The loader gate (``load_text``) admits a row at decision time ``T`` only when
``decision_visible_at <= T`` — so a historical backfill ingested today can never
fake visibility in the past (the reason historical text alpha is largely
non-validatable; the clean path is forward accumulation).

Enforced by: tests/pit/test_text_visible_time_gate.py ·
tests/pit/test_text_backfill_rejection.py · tests/pit/test_text_revision_hash_freeze.py.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE_DIR = _PROJECT_ROOT / "data" / "text_store"

#: stamp columns added by ingest_rows; the loader FAILS CLOSED when absent.
STAMP_COLUMNS = (
    "source",
    "content_hash",
    "source_published_at",
    "retrieved_at",
    "first_ingested_at",
    "decision_visible_at",
    "published_missing",
)


class TextStoreError(Exception):
    """Fail-closed error for the PIT text store."""


def _store_path(source: str, store_dir: str | os.PathLike | None) -> Path:
    base = Path(store_dir) if store_dir is not None else DEFAULT_STORE_DIR
    return base / source / f"text_{source}.parquet"


def _hash_row(source: str, row: pd.Series) -> str:
    payload = source + "|" + "|".join(f"{k}={row[k]}" for k in sorted(row.index))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ingest_rows(
    source: str,
    raw: pd.DataFrame,
    *,
    published_col: str | None,
    retrieved_at: pd.Timestamp,
    store_dir: str | os.PathLike | None = None,
) -> pd.DataFrame:
    """Stamp and append raw text rows (idempotent on content_hash).

    Args:
        source: source id (e.g. ``research_report``); one store file per source.
        raw: source-native columns, one row per text object.
        published_col: name of the column carrying a VERIFIED publication
            timestamp; ``None`` when the source has only nominal dates
            (fail-closed: visibility falls back to ingestion).
        retrieved_at: the actual fetch time for this batch.
        store_dir: override for tests; defaults to ``data/text_store``.

    Returns:
        The stamped rows for THIS batch (both newly appended and pre-existing
        duplicates, with their authoritative stamps).
    """
    if raw.empty:
        return raw.copy()
    retrieved_at = pd.Timestamp(retrieved_at)

    stamped = raw.copy().reset_index(drop=True)
    stamped["source"] = source
    stamped["content_hash"] = [
        _hash_row(source, stamped.loc[i, list(raw.columns)]) for i in stamped.index
    ]
    if published_col is not None:
        if published_col not in stamped.columns:
            raise TextStoreError(f"published_col '{published_col}' not in raw columns")
        pub = pd.to_datetime(stamped[published_col], errors="coerce")
    else:
        pub = pd.Series(pd.NaT, index=stamped.index)
    stamped["source_published_at"] = pub
    stamped["published_missing"] = pub.isna()
    stamped["retrieved_at"] = retrieved_at
    stamped["first_ingested_at"] = retrieved_at
    # R5-B1: max, not earliest; missing publication -> ingestion (fail-closed)
    stamped["decision_visible_at"] = (
        stamped[["source_published_at", "first_ingested_at"]].max(axis=1)
    )

    path = _store_path(source, store_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_parquet(path)
        known = set(existing["content_hash"])
        new_rows = stamped[~stamped["content_hash"].isin(known)]
        if not new_rows.empty:
            combined = pd.concat([existing, new_rows], ignore_index=True)
            combined.to_parquet(path, index=False)
        else:
            combined = existing
        # return authoritative stamps for THIS batch's hashes (originals win)
        return combined[combined["content_hash"].isin(set(stamped["content_hash"]))].copy()
    stamped.to_parquet(path, index=False)
    return stamped


def load_text(
    source: str,
    decision_time: str | pd.Timestamp,
    *,
    store_dir: str | os.PathLike | None = None,
) -> pd.DataFrame:
    """PIT loader: rows with ``decision_visible_at <= decision_time`` only.

    Fails closed when the store file lacks the stamp columns (a parquet written
    outside ``ingest_rows`` is refused, never guessed at).
    """
    path = _store_path(source, store_dir)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    missing = [c for c in STAMP_COLUMNS if c not in df.columns]
    if missing:
        raise TextStoreError(
            f"{path} is missing PIT stamp columns {missing} — refusing to load "
            f"(rows must be written through ingest_rows)"
        )
    t = pd.Timestamp(decision_time)
    return df[df["decision_visible_at"] <= t].copy()
