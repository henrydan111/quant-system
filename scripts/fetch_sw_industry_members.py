"""A2 — One-time bootstrap of Shenwan SW2021 historical stock-to-industry membership.

Plan ref: C:\\Users\\henry\\.claude\\plans\\vast-exploring-rabbit.md (v8)

Behavior
--------
- Loads the 31 L1 codes from data/universe/industry_sw2021/industry_sw2021.parquet
- For each L1: calls fetch_index_member_all(industry_code=..., is_new='Y')
  AND fetch_index_member_all(industry_code=..., is_new='N'), concatenates.
  (A0 verified that is_new=None returns only current members; both
  branches are required for full historical coverage.)
- 62 calls total at base_sleep=1.5 → ~93s of enforced sleep + API roundtrip.
  tqdm progress bar per CLAUDE.md §10.
- Writes data/universe/industry_sw2021_members/industry_sw2021_members.parquet
  via StorageManager.insert_universe_data (matches existing universe pattern).
- Mutation safety per CLAUDE.md §6.4:
    --dry-run: skip write, log target + row count
    --force: backup existing → .bak_YYYYMMDD_HHMMSS, write to .tmp,
             os.replace(tmp, target), record manifest.
    Idempotent dedup: if existing file has identical row-hash, skip write.
    unclassified_stocks.txt sidecar appends, never overwrites.

Usage
-----
    venv/Scripts/python.exe scripts/fetch_sw_industry_members.py
    venv/Scripts/python.exe scripts/fetch_sw_industry_members.py --dry-run
    venv/Scripts/python.exe scripts/fetch_sw_industry_members.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_infra.fetchers import TushareFetcher  # noqa: E402
from src.data_infra.storage import StorageManager  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

CATALOG_PATH = (
    PROJECT_ROOT
    / "data"
    / "universe"
    / "industry_sw2021"
    / "industry_sw2021.parquet"
)
TARGET_DIR = PROJECT_ROOT / "data" / "universe" / "industry_sw2021_members"
TARGET_FILE = TARGET_DIR / "industry_sw2021_members.parquet"
UNCLASSIFIED_LOG = TARGET_DIR / "unclassified_stocks.txt"
STOCK_BASIC_PATH = PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet"


def _row_hash(df: pd.DataFrame) -> str:
    """Stable hash of df contents for dedup comparison."""
    canonical = df.sort_values(list(df.columns)).reset_index(drop=True)
    return hashlib.sha256(
        canonical.to_csv(index=False).encode("utf-8")
    ).hexdigest()


def _load_l1_codes() -> list[tuple[str, str]]:
    catalog = pd.read_parquet(CATALOG_PATH)
    l1 = catalog[catalog["level"] == "L1"][["index_code", "industry_name"]]
    pairs = list(zip(l1["index_code"].tolist(), l1["industry_name"].tolist()))
    logger.info("Loaded %d L1 industries from catalog", len(pairs))
    return pairs


def _fetch_all_members(
    fetcher: TushareFetcher, l1_codes: list[tuple[str, str]]
) -> pd.DataFrame:
    """For each L1: fetch is_new='Y' + 'N', concat. Returns full membership."""
    frames: list[pd.DataFrame] = []
    iterator = tqdm(l1_codes, desc="SW2021 L1 members", unit="industry")
    for code, name in iterator:
        iterator.set_postfix_str(f"{code} {name}")
        for is_new_flag in ("Y", "N"):
            try:
                df = fetcher.fetch_index_member_all(
                    industry_code=code, is_new=is_new_flag
                )
            except Exception as e:
                logger.error(
                    "  %s (%s) is_new=%s FAILED: %s", code, name, is_new_flag, e
                )
                continue
            if df is not None and not df.empty:
                frames.append(df)
    if not frames:
        raise RuntimeError("No membership data fetched — investigate.")
    combined = pd.concat(frames, ignore_index=True)
    logger.info("Raw concatenated rows: %d", len(combined))
    combined = combined.drop_duplicates()
    logger.info("After de-dup: %d", len(combined))
    return combined


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Apply normalizations from plan A2: date parsing, sentinels, list_date fallback."""
    df = df.copy()

    # Parse date columns
    df["in_date"] = pd.to_datetime(df["in_date"], format="%Y%m%d", errors="coerce")
    df["out_date"] = pd.to_datetime(df["out_date"], format="%Y%m%d", errors="coerce")

    # Sentinel for null out_date — stock still in the industry
    sentinel = pd.Timestamp("2099-12-31")
    df["out_date"] = df["out_date"].fillna(sentinel)

    # Null in_date fallback to list_date
    null_in_mask = df["in_date"].isna()
    if null_in_mask.any():
        logger.warning(
            "%d rows with null in_date — falling back to stock list_date",
            int(null_in_mask.sum()),
        )
        sb = pd.read_parquet(STOCK_BASIC_PATH)
        sb["list_date"] = pd.to_datetime(
            sb["list_date"], format="%Y%m%d", errors="coerce"
        )
        list_map = sb.set_index("ts_code")["list_date"].to_dict()
        df.loc[null_in_mask, "in_date"] = df.loc[null_in_mask, "ts_code"].map(
            list_map
        )

    # Drop rows still null after fallback; log to sidecar
    still_null = df["in_date"].isna()
    if still_null.any():
        unclassified = df.loc[still_null, ["ts_code", "name", "l1_code"]].copy()
        TARGET_DIR.mkdir(parents=True, exist_ok=True)
        with open(UNCLASSIFIED_LOG, "a", encoding="utf-8") as fh:
            fh.write(f"\n# Bootstrap run {datetime.now().isoformat(timespec='seconds')}\n")
            for _, row in unclassified.iterrows():
                fh.write(
                    f"{row['ts_code']}\t{row['name']}\t{row['l1_code']}\n"
                )
        logger.warning(
            "%d rows dropped (no in_date and no list_date); appended to %s",
            int(still_null.sum()),
            UNCLASSIFIED_LOG,
        )
        df = df.loc[~still_null].copy()

    return df


def _summary(df: pd.DataFrame) -> None:
    """One-page console summary."""
    print()
    print("=" * 60)
    print("SW2021 MEMBERSHIP BOOTSTRAP SUMMARY")
    print("=" * 60)
    print(f"Total rows: {len(df):,}")
    print(f"Unique stocks: {df['ts_code'].nunique():,}")
    print(f"Unique L1 industries: {df['l1_code'].nunique()}")
    if "is_new" in df.columns:
        print(f"is_new mix: {df['is_new'].value_counts().to_dict()}")
    spans = (df["out_date"] - df["in_date"]).dt.days
    print(
        f"Membership length (days): "
        f"min={spans.min()}, median={spans.median():.0f}, max={spans.max()}"
    )
    print(f"in_date range: {df['in_date'].min().date()} → {df['in_date'].max().date()}")
    print(f"Pre-2008 in_date count: {int((df['in_date'] <= '2008-01-01').sum()):,}")
    print("=" * 60)


def _safe_write(df: pd.DataFrame, force: bool, dry_run: bool) -> None:
    """Apply mutation-safety controls per CLAUDE.md §6.4."""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    target = TARGET_FILE

    logger.info("Will write %d rows to %s", len(df), target)

    if dry_run:
        logger.info("[DRY-RUN] skipped actual write")
        return

    if target.exists() and not force:
        logger.info(
            "Target exists at %s and --force not set; skipping (use --force to overwrite)",
            target,
        )
        return

    if target.exists() and force:
        # Idempotent dedup: skip if identical
        existing = pd.read_parquet(target)
        new_hash = _row_hash(df)
        old_hash = _row_hash(existing)
        if new_hash == old_hash:
            logger.info("New data identical to existing (hash=%s); skipping write", new_hash[:12])
            return
        # Backup-then-replace per Codex review-7 N3
        backup = target.with_name(
            f"{target.name}.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        shutil.copy2(target, backup)
        logger.info("Backed up existing → %s (hash diff %s -> %s)", backup.name, old_hash[:12], new_hash[:12])

    if target.exists() and force:
        # Atomic write via temp + os.replace
        tmp = target.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        os.replace(tmp, target)
        logger.info("Atomic replace via temp complete: %s", target)
        # Manual manifest record (insert_universe_data was bypassed)
        try:
            storage = StorageManager()
            storage._record_ingest_manifest(
                "industry_sw2021_members", [str(target)], len(df)
            )
            logger.info("Recorded manifest for industry_sw2021_members")
        except Exception as e:
            logger.warning("Manifest record failed (non-fatal): %s", e)
    else:
        # First-time write — go through StorageManager normally
        storage = StorageManager()
        storage.insert_universe_data(df, "industry_sw2021_members")
        logger.info("Wrote via StorageManager.insert_universe_data → %s", target)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap SW2021 historical stock-to-industry membership"
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip the write")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing target with backup (uses copy2 + os.replace)",
    )
    args = parser.parse_args()

    if not CATALOG_PATH.exists():
        logger.error(
            "Catalog file missing: %s — run init_fundamentals_data.py first",
            CATALOG_PATH,
        )
        return 1

    if TARGET_FILE.exists() and not (args.force or args.dry_run):
        logger.info(
            "Target exists at %s; nothing to do (--force to refetch, --dry-run to preview)",
            TARGET_FILE,
        )
        return 0

    fetcher = TushareFetcher(
        config_path=str(PROJECT_ROOT / "config.yaml"), base_sleep=1.5
    )
    l1_codes = _load_l1_codes()

    t0 = time.time()
    raw = _fetch_all_members(fetcher, l1_codes)
    logger.info("Fetch complete in %.1fs", time.time() - t0)

    members_df = _normalize(raw)
    _summary(members_df)

    _safe_write(members_df, force=args.force, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
