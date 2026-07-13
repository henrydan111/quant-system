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
- **dual hashes (impl-review #2 Major-2)**: ``object_id_hash`` names the text
  OBJECT (identity columns); ``content_hash`` covers identity + content
  columns (whitespace-normalized). Same object, changed content = a NEW
  revision row appended (old row + its ``first_ingested_at`` frozen forever —
  the C1 revision rule); identical content re-ingested = dedup no-op. For
  irm_qa the answer text ``a`` IS content (an in-place answer edit is a
  revision), while format noise is absorbed by normalization;
- ``adapter_contract_hash`` — names the (source, object-basis, content-basis)
  contract a row was minted under; changing a basis = a new contract and a
  store migration, never an in-place re-mint.

**Timezone contract (impl-review #2 Blocker-5)**: ALL timestamps stored here
are Asia/Shanghai WALL TIME (naive storage, CN semantics). tz-aware inputs are
converted to CN then stripped; naive inputs are assumed to already be CN wall
time. ``load_text`` normalizes ``decision_time`` the same way.

The loader gate (``load_text``) admits a row at decision time ``T`` only when
``decision_visible_at <= T`` — so a historical backfill ingested today can never
fake visibility in the past. Formal/forward callers pass ``require_exists=True``
so a missing store file is a hard error, never silent no-text (R2 Blocker-6).

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

CN_TZ = "Asia/Shanghai"

#: stamp columns added by ingest_rows; the loader FAILS CLOSED when absent.
STAMP_COLUMNS = (
    "source",
    "object_id_hash",
    "content_hash",
    "adapter_contract_hash",
    "source_published_at",
    "retrieved_at",
    "first_ingested_at",
    "decision_visible_at",
    "published_missing",
)

#: impl-review #2 Major-2 — object identity vs content bases, per production
#: source. Column names verified against the live store schemas 2026-07-08.
SOURCE_OBJECT_ID_COLUMNS: dict[str, list[str]] = {
    "anns_d": ["ann_date", "ts_code", "url"],
    "irm_qa_sh": ["ts_code", "pub_time", "q"],
    "irm_qa_sz": ["ts_code", "pub_time", "q"],
    "research_report": ["ts_code", "title", "inst_csname", "trade_date"],
    # 政策三源(v1.5-D;宏观级,无 ts_code)
    "npr": ["pubtime", "title", "puborg"],
    "monetary_policy": ["pub_date", "title"],
    "cctv_news": ["date", "title"],
    # 新闻快讯(NF wave, doc 143):src 我方注入。per-source 去重身份 = src+datetime+
    # **content**——sina 等源 title 常为 None、正文在 content,故身份用 content(可靠载荷)
    # 而非 title(实测会 null 碰撞);跨源聚簇在 news_ingest 下游
    "news": ["src", "datetime", "content"],
}
SOURCE_CONTENT_COLUMNS: dict[str, list[str]] = {
    "anns_d": ["ann_date", "ts_code", "title", "url"],
    "irm_qa_sh": ["ts_code", "pub_time", "q", "a"],
    "irm_qa_sz": ["ts_code", "pub_time", "q", "a"],
    "research_report": ["ts_code", "title", "inst_csname", "trade_date"],
    "npr": ["pubtime", "title", "puborg", "ptype"],
    "monetary_policy": ["pub_date", "title", "url"],
    "cctv_news": ["date", "title", "content"],
    "news": ["src", "datetime", "title", "content", "channels"],
}


class TextStoreError(Exception):
    """Fail-closed error for the PIT text store."""


#: canonical missing sentinel (review M5): None / NaN / pd.NA / NaT hash identically
NULL_SENTINEL = "\x00NULL\x00"


def _norm_value(v) -> str:
    """Canonical value encoding for hashing (review M5): ALL missing forms
    (None/NaN/pd.NA/NaT) collapse to ONE sentinel so the same missing vendor
    field never hashes two ways; timestamps → CN-naive ISO; else
    whitespace-normalized text. One encoder, shared by fetcher and store."""
    try:
        if v is None or bool(pd.isna(v)):
            return NULL_SENTINEL
    except (TypeError, ValueError):
        pass
    if isinstance(v, pd.Timestamp) or hasattr(v, "to_pydatetime"):
        t = pd.Timestamp(v)
        if t.tzinfo is not None:
            t = t.tz_convert(CN_TZ).tz_localize(None)
        return "T:" + t.isoformat()
    return " ".join(str(v).split())


def to_cn_naive(ts) -> pd.Timestamp:
    """Normalize any timestamp to Asia/Shanghai WALL TIME (naive, CN semantics)."""
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert(CN_TZ).tz_localize(None)
    return t


def adapter_contract_hash(source: str, object_cols: list[str] | None,
                          content_cols: list[str] | None) -> str:
    """Short hash naming the (source, object-basis, content-basis) contract."""
    payload = (source + "|obj:" + ("|".join(object_cols) if object_cols else "<ALL>")
               + "|content:" + ("|".join(content_cols) if content_cols else "<ALL>"))
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


#: ingest classes with PHYSICAL separation (B1, NF wave): forward accrues the
#  clean PIT panel; history_bulk is bulk-backfilled history that is invisible to
#  the forward loader (a bulk row ingested today would otherwise satisfy a
#  decision_visible_at<=cutoff filter and pollute current flow). Sources not
#  passing ingest_class use the flat legacy path (unchanged).
INGEST_CLASSES = ("forward", "history_bulk")
#: sources that MUST declare a physical ingest_class (review B1: no flat-path bypass)
CLASS_REQUIRED_SOURCES = frozenset({"news"})


def _store_path(source: str, store_dir: str | os.PathLike | None,
                ingest_class: str | None = None) -> Path:
    base = Path(store_dir) if store_dir is not None else DEFAULT_STORE_DIR
    if ingest_class is not None:
        if ingest_class not in INGEST_CLASSES:
            raise TextStoreError(f"unknown ingest_class {ingest_class!r}")
        return base / source / ingest_class / f"text_{source}.parquet"
    return base / source / f"text_{source}.parquet"


def object_id_hash_for(source: str, row, raw_columns: list[str]) -> str:
    """Canonical object-id hash (M5: ONE implementation shared by fetcher + store)."""
    obj_basis, _ = _resolve_bases(source, list(raw_columns))
    return _hash_row(source, row, obj_basis)


def content_hash_for(source: str, row, raw_columns: list[str]) -> str:
    """Canonical content hash (M5: identical normalization on both layers so a
    fetcher-side dedup and a store-side dedup are bit-identical)."""
    _, content_basis = _resolve_bases(source, list(raw_columns))
    return _hash_row(source, row, content_basis)


def _resolve_bases(source: str, raw_columns: list[str]) -> tuple[list[str], list[str]]:
    """Resolve (object basis, content basis); fail CLOSED on missing pinned cols."""
    obj = SOURCE_OBJECT_ID_COLUMNS.get(source)
    content = SOURCE_CONTENT_COLUMNS.get(source)
    if obj is None or content is None:
        cols = sorted(raw_columns)              # unknown source: ALL raw columns
        return cols, cols
    missing = [c for c in {*obj, *content} if c not in raw_columns]
    if missing:
        raise TextStoreError(
            f"source '{source}' raw batch is missing pinned hash columns "
            f"{missing} (SOURCE_*_COLUMNS contract, M1/Major-2) — refusing to ingest"
        )
    return obj, content


def _hash_row(source: str, row: pd.Series, basis: list[str]) -> str:
    payload = source + "|" + "|".join(f"{k}={_norm_value(row[k])}" for k in basis)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ingest_rows(
    source: str,
    raw: pd.DataFrame,
    *,
    published_col: str | None,
    retrieved_at: pd.Timestamp,
    store_dir: str | os.PathLike | None = None,
    ingest_class: str | None = None,
) -> pd.DataFrame:
    """Stamp and append raw text rows (idempotent on content_hash).

    Args:
        source: source id (e.g. ``research_report``); one store file per source.
        raw: source-native columns, one row per text object.
        published_col: name of the column carrying a VERIFIED publication
            timestamp; ``None`` when the source has only nominal dates
            (fail-closed: visibility falls back to ingestion).
        retrieved_at: the actual fetch time for this batch (any tz; normalized
            to CN wall time).
        store_dir: override for tests; defaults to ``data/text_store``.

    Returns:
        The stamped rows for THIS batch (both newly appended and pre-existing
        duplicates, with their authoritative stamps).
    """
    # review B1: news MUST declare a physical ingest_class (before the empty
    # return) so a flat-path bypass is impossible; pre-NF sources unchanged.
    if source in CLASS_REQUIRED_SOURCES and ingest_class is None:
        raise TextStoreError(
            f"source {source!r} requires ingest_class ∈ {INGEST_CLASSES} "
            f"(physical isolation, review B1) — flat-path ingest refused")
    if raw.empty:
        return raw.copy()
    retrieved_at = to_cn_naive(retrieved_at)

    stamped = raw.copy().reset_index(drop=True)
    stamped["source"] = source
    obj_basis, content_basis = _resolve_bases(source, list(raw.columns))
    stamped["object_id_hash"] = [
        _hash_row(source, stamped.loc[i, list(raw.columns)], obj_basis)
        for i in stamped.index
    ]
    stamped["content_hash"] = [
        _hash_row(source, stamped.loc[i, list(raw.columns)], content_basis)
        for i in stamped.index
    ]
    known_source = source in SOURCE_OBJECT_ID_COLUMNS
    stamped["adapter_contract_hash"] = adapter_contract_hash(
        source, obj_basis if known_source else None,
        content_basis if known_source else None)
    if published_col is not None:
        if published_col not in stamped.columns:
            raise TextStoreError(f"published_col '{published_col}' not in raw columns")
        pub = pd.to_datetime(stamped[published_col], errors="coerce")
        if getattr(pub.dt, "tz", None) is not None:
            pub = pub.dt.tz_convert(CN_TZ).dt.tz_localize(None)
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
    if ingest_class is not None:
        stamped["ingest_class"] = ingest_class
    # M5: dedup WITHIN the incoming batch on content_hash (first occurrence wins)
    # before touching storage — two identical flashes in one pull must not both
    # persist (a probe showed two rows with the same content_hash surviving).
    stamped = stamped[~stamped["content_hash"].duplicated()].reset_index(drop=True)

    path = _store_path(source, store_dir, ingest_class)
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
        if not combined["content_hash"].is_unique:      # permanent check (review M5)
            raise TextStoreError(f"{path}: content_hash not unique after append")
        # return authoritative stamps for THIS batch's hashes (originals win)
        return combined[combined["content_hash"].isin(set(stamped["content_hash"]))].copy()
    _atomic_write_parquet(stamped, path)
    return stamped


def load_text(
    source: str,
    decision_time: str | pd.Timestamp,
    *,
    store_dir: str | os.PathLike | None = None,
    require_exists: bool = False,
    ingest_class: str | None = None,
) -> pd.DataFrame:
    """PIT loader: rows with ``decision_visible_at <= decision_time`` only.

    Fails closed when the store file lacks the stamp columns (a parquet written
    outside ``ingest_rows`` is refused, never guessed at). Formal/forward
    callers MUST pass ``require_exists=True`` — a missing required source is a
    hard error, not silent no-text (R2 Blocker-6).

    ``ingest_class`` (B1): the FORWARD loader passes ``ingest_class='forward'``
    so it reads ONLY the physically-separated forward panel; bulk history is
    never reachable from a forward decision. Omitting it reads the flat legacy
    path (unchanged for pre-NF sources).
    """
    if source in CLASS_REQUIRED_SOURCES and ingest_class is None:
        raise TextStoreError(
            f"source {source!r} requires ingest_class to load (review B1) — "
            f"a flat-path read would bypass forward/history_bulk isolation")
    path = _store_path(source, store_dir, ingest_class)
    if not path.exists():
        if require_exists:
            raise TextStoreError(
                f"required text store missing: {source} ({path}) — refusing to "
                f"treat a missing source as no-text (fail-closed)")
        return pd.DataFrame()
    df = pd.read_parquet(path)
    missing = [c for c in STAMP_COLUMNS if c not in df.columns]
    if missing:
        raise TextStoreError(
            f"{path} is missing PIT stamp columns {missing} — refusing to load "
            f"(rows must be written through ingest_rows)"
        )
    # review B1: every loaded row's stamped ingest_class must match the requested
    # partition (a row's provenance can't disagree with its physical location)
    if ingest_class is not None and "ingest_class" in df.columns:
        bad = df["ingest_class"] != ingest_class
        if bad.any():
            raise TextStoreError(
                f"{path}: {int(bad.sum())} rows have ingest_class != {ingest_class!r} "
                f"(partition/metadata mismatch)")
    t = to_cn_naive(decision_time)
    return df[df["decision_visible_at"] <= t].copy()


# ---- dedicated news entry points (review B1: production decisions use forward) ----

def ingest_forward_news(raw, *, retrieved_at, store_dir=None):
    """Forward-panel news ingest — the ONLY path a live decision's raw text takes."""
    return ingest_rows("news", raw, published_col="datetime",
                       retrieved_at=retrieved_at, store_dir=store_dir,
                       ingest_class="forward")


def ingest_history_news(raw, *, retrieved_at, store_dir=None):
    """History-bulk news ingest — physically separated; NON_EVIDENTIARY replay only."""
    return ingest_rows("news", raw, published_col="datetime",
                       retrieved_at=retrieved_at, store_dir=store_dir,
                       ingest_class="history_bulk")


def load_forward_news(decision_time, *, store_dir=None, require_exists=False):
    """Forward-panel news load — a live decision can NEVER see bulk history."""
    return load_text("news", decision_time, store_dir=store_dir,
                     require_exists=require_exists, ingest_class="forward")
