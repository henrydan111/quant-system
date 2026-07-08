# SCRIPT_STATUS: ACTIVE — one-shot M1 text_store hash-basis migration (impl-review #1)
"""Migrate data/text_store to the pinned SOURCE_HASH_COLUMNS basis (M1) IN PLACE.

Why not GPT's archive+re-pull: a re-pull would reset ``first_ingested_at`` to
today for every row, destroying the July PIT visibility stamps (a strict PIT
regression). The store preserves ALL raw source columns, so the new pinned-basis
hash is recomputable from the existing rows with stamps intact.

Per source: archive original -> recompute content_hash over the pinned basis ->
dedup on the new hash keeping the EARLIEST first_ingested_at (originals win,
C1) -> stamp adapter_contract_hash -> atomic write.

Usage: venv/Scripts/python.exe workspace/scripts/migrate_text_store_m1.py [--dry-run]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_infra.text_store import (  # noqa: E402
    SOURCE_HASH_COLUMNS, _atomic_write_parquet, _hash_row,
    adapter_contract_hash,
)

STORE = PROJECT_ROOT / "data" / "text_store"
ARCHIVE = PROJECT_ROOT / "data" / "text_store_pre_m1_archive"
OLD_STAMPS = {"source", "content_hash", "adapter_contract_hash", "source_published_at",
              "published_missing", "retrieved_at", "first_ingested_at",
              "decision_visible_at"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    targets = [STORE / s / f"text_{s}.parquet" for s in SOURCE_HASH_COLUMNS]
    print("files to be touched:")
    for t in targets:
        print(f"  {t} (exists={t.exists()})")
    if args.dry_run:
        print("[dry-run] no writes")

    for source in SOURCE_HASH_COLUMNS:
        path = STORE / source / f"text_{source}.parquet"
        if not path.exists():
            print(f"[skip] {source}: no store file")
            continue
        df = pd.read_parquet(path)
        if "adapter_contract_hash" in df.columns:
            print(f"[skip] {source}: already migrated")
            continue
        basis = SOURCE_HASH_COLUMNS[source]
        missing = [c for c in basis if c not in df.columns]
        if missing:
            raise SystemExit(f"{source}: pinned columns {missing} absent — abort")

        new_hash = [_hash_row(source, df.loc[i], basis) for i in df.index]
        out = df.assign(content_hash=new_hash,
                        adapter_contract_hash=adapter_contract_hash(source, basis))
        n_before = len(out)
        out = (out.sort_values("first_ingested_at")
                  .drop_duplicates(subset=["content_hash"], keep="first")
                  .reset_index(drop=True))
        print(f"[{source}] {n_before} rows -> {len(out)} after pinned-basis dedup "
              f"({n_before - len(out)} incidental-field duplicates collapsed); "
              f"adapter_contract_hash={adapter_contract_hash(source, basis)}")
        if args.dry_run:
            continue
        arch = ARCHIVE / source
        arch.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, arch / path.name)
        _atomic_write_parquet(out, path)
        print(f"[{source}] archived -> {arch / path.name}; store rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
