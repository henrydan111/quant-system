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
- ``content_hash`` — sha256 over source + a PINNED per-source column basis
  (``SOURCE_HASH_COLUMNS``, impl-review M1); a silent vendor REVISION becomes
  a NEW row (new hash), the original row is frozen forever. Pinning makes the
  hash reproducible across adapter/schema drift (a vendor adding an incidental
  column must not re-mint every hash); each row records the
  ``adapter_contract_hash`` of the basis it was hashed under. Unknown/test
  sources fall back to hashing ALL raw columns (conservative: never hides a
  revision).

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
import tempfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE_DIR = _PROJECT_ROOT / "data" / "text_store"

#: stamp columns added by ingest_rows; the loader FAILS CLOSED when absent.
STAMP_COLUMNS = (
    "source",
    "content_hash",
    "adapter_contract_hash",
    "source_published_at",
    "retrieved_at",
    "first_ingested_at",
    "decision_visible_at",
    "published_missing",
)

#: impl-review M1 — the PINNED identity/content basis for content_hash, per
#: production source. Changing a basis = a new adapter contract (new
#: ``adapter_contract_hash``) and REQUIRES a store migration, never an in-place
#: re-mint. Column names verified against the live store schemas 2026-07-08.
#: irm_qa deliberately EXCLUDES the answer text ``a``: vendor re-formatting of
#: an answer must not mint spurious rows; a real answer revision arrives with a
#: new ``pub_time`` and thus a new hash.
SOURCE_HASH_COLUMNS: dict[str, list[str]] = {
    "anns_d": ["ann_date", "ts_code", "title", "url"],
    "irm_qa_sh": ["ts_code", "pub_time", "q"],
    "irm_qa_sz": ["ts_code", "pub_time", "q"],
    "research_report": ["ts_code", "title", "inst_csname", "trade_date"],
}


def adapter_contract_hash(source: str, columns: list[str] | None = None) -> str:
    """Short hash naming the (source, hash-basis) contract a row was minted under."""
    basis = columns if columns is not None else SOURCE_HASH_COLUMNS.get(source)
    payload = source + "|" + ("|".join(basis) if basis else "<ALL_RAW_COLUMNS>")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _atomic_write_parquet(df: pd.DataFrame, path: Path) -> None:
    """impl-review M2: same-dir tempfile + os.replace — a crashed writer can
    never leave a torn store file behind."""
    fd, tmp = tempfile.mkstemp(suffix=".parquet.tmp", dir=path.parent)
    os.close(fd)
    try:
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class TextStoreError(Exception):
    """Fail-closed error for the PIT text store."""


def _store_path(source: str, store_dir: str | os.PathLike | None) -> Path:
    base = Path(store_dir) if store_dir is not None else DEFAULT_STORE_DIR
    return base / source / f"text_{source}.parquet"


def _hash_basis(source: str, raw_columns: list[str]) -> list[str]:
    """Resolve the pinned hash basis; fail CLOSED if a pinned column is absent."""
    pinned = SOURCE_HASH_COLUMNS.get(source)
    if pinned is None:
        return sorted(raw_columns)          # unknown source: ALL raw columns
    missing = [c for c in pinned if c not in raw_columns]
    if missing:
        raise TextStoreError(
            f"source '{source}' raw batch is missing pinned hash columns "
            f"{missing} (SOURCE_HASH_COLUMNS contract, M1) — refusing to ingest"
        )
    return pinned


def _hash_row(source: str, row: pd.Series, basis: list[str]) -> str:
    payload = source + "|" + "|".join(f"{k}={row[k]}" for k in basis)
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
    basis = _hash_basis(source, list(raw.columns))
    stamped["content_hash"] = [
        _hash_row(source, stamped.loc[i, list(raw.columns)], basis)
        for i in stamped.index
    ]
    stamped["adapter_contract_hash"] = adapter_contract_hash(
        source, basis if source in SOURCE_HASH_COLUMNS else None)
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
            _atomic_write_parquet(combined, path)
        else:
            combined = existing
        # return authoritative stamps for THIS batch's hashes (originals win)
        return combined[combined["content_hash"].isin(set(stamped["content_hash"]))].copy()
    _atomic_write_parquet(stamped, path)
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
