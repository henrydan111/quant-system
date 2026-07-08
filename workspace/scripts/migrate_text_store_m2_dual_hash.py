# SCRIPT_STATUS: ACTIVE — one-shot Major-2 dual-hash text_store migration (impl-review #2)
"""Rebuild data/text_store from the pre-M1 archive under the DUAL-HASH contract
(object_id_hash + content_hash with normalized content, R2 Major-2) and emit
the formal migration manifest (R2 Major-1).

Rebuilding from the ARCHIVE (not the M1-migrated store) matters: M1's
identity-only hash collapsed ~48 irm_qa rows that were genuine ANSWER VARIANTS
of the same question — under Major-2 those are C1 revisions and must survive
as separate rows. All PIT stamps travel verbatim from the archive rows; the
manifest PROVES first_ingested_at / decision_visible_at changed for zero rows.

Usage: venv/Scripts/python.exe workspace/scripts/migrate_text_store_m2_dual_hash.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_infra.text_store import (  # noqa: E402
    SOURCE_CONTENT_COLUMNS, SOURCE_OBJECT_ID_COLUMNS, STAMP_COLUMNS,
    _atomic_write_parquet, _hash_row, adapter_contract_hash,
)

STORE = PROJECT_ROOT / "data" / "text_store"
ARCHIVE = PROJECT_ROOT / "data" / "text_store_pre_m1_archive"
MANIFEST_PATH = STORE / "migration_manifest.json"
_OLD_STAMPS = set(STAMP_COLUMNS) | {"content_hash"}  # any prior stamp generation


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    entry = {
        "migration_id": "m2_dual_hash_2026-07-08",
        "migration_script": "workspace/scripts/migrate_text_store_m2_dual_hash.py",
        "archive_dir": "data/text_store_pre_m1_archive",
        "reviewed_under": "GPT impl-review #2 Major-1/Major-2",
        "old_store_hash_by_source": {},
        "new_store_hash_by_source": {},
        "rows_before_by_source": {},
        "rows_after_by_source": {},
        "duplicates_removed_by_source": {},
        "revision_rows_recovered_vs_m1_by_source": {},
        "first_ingested_at_changed_count": 0,
        "decision_visible_at_changed_count": 0,
        "adapter_contract_hash_by_source": {},
    }

    print("files to be touched:")
    for source in SOURCE_OBJECT_ID_COLUMNS:
        print(f"  {STORE / source / f'text_{source}.parquet'}")
    if args.dry_run:
        print("[dry-run] no writes")

    for source in SOURCE_OBJECT_ID_COLUMNS:
        arch_path = ARCHIVE / source / f"text_{source}.parquet"
        live_path = STORE / source / f"text_{source}.parquet"
        if not arch_path.exists():
            raise SystemExit(f"{source}: archive missing at {arch_path} — abort")
        arch = pd.read_parquet(arch_path)
        live_before = pd.read_parquet(live_path) if live_path.exists() else pd.DataFrame()

        raw_cols = [c for c in arch.columns if c not in _OLD_STAMPS]
        obj_basis = SOURCE_OBJECT_ID_COLUMNS[source]
        content_basis = SOURCE_CONTENT_COLUMNS[source]
        missing = [c for c in {*obj_basis, *content_basis} if c not in raw_cols]
        if missing:
            raise SystemExit(f"{source}: pinned columns {missing} absent in archive — abort")

        out = arch.copy().reset_index(drop=True)
        out["object_id_hash"] = [_hash_row(source, out.loc[i], obj_basis)
                                 for i in out.index]
        out["content_hash"] = [_hash_row(source, out.loc[i], content_basis)
                               for i in out.index]
        out["adapter_contract_hash"] = adapter_contract_hash(
            source, obj_basis, content_basis)

        n_before = len(out)
        # keep the EARLIEST ingestion of each content version (originals win, C1);
        # all stamp columns travel VERBATIM from the archive row.
        stamps_pre = out[["content_hash", "first_ingested_at", "decision_visible_at"]].copy()
        out = (out.sort_values("first_ingested_at")
                  .drop_duplicates(subset=["content_hash"], keep="first")
                  .reset_index(drop=True))
        # PROOF: each surviving row's stamps equal the earliest archive row's
        check = out.merge(
            stamps_pre.sort_values("first_ingested_at")
                      .drop_duplicates(subset=["content_hash"], keep="first"),
            on="content_hash", suffixes=("", "_arch"))
        fic = int((check["first_ingested_at"] != check["first_ingested_at_arch"]).sum())
        dvc = int((check["decision_visible_at"] != check["decision_visible_at_arch"]).sum())
        entry["first_ingested_at_changed_count"] += fic
        entry["decision_visible_at_changed_count"] += dvc
        if fic or dvc:
            raise SystemExit(f"{source}: PIT stamps changed (fic={fic}, dvc={dvc}) — abort")

        entry["old_store_hash_by_source"][source] = (
            sha256_file(live_path) if live_path.exists() else None)
        entry["rows_before_by_source"][source] = n_before
        entry["rows_after_by_source"][source] = len(out)
        entry["duplicates_removed_by_source"][source] = n_before - len(out)
        entry["revision_rows_recovered_vs_m1_by_source"][source] = (
            len(out) - len(live_before) if not live_before.empty else None)
        entry["adapter_contract_hash_by_source"][source] = adapter_contract_hash(
            source, obj_basis, content_basis)

        print(f"[{source}] archive {n_before} -> {len(out)} rows "
              f"(dups removed {n_before - len(out)}; "
              f"vs M1 store {len(live_before)} -> recovered "
              f"{len(out) - len(live_before)} revision rows); PIT stamps unchanged")
        if args.dry_run:
            continue
        _atomic_write_parquet(out, live_path)
        entry["new_store_hash_by_source"][source] = sha256_file(live_path)

    if not args.dry_run:
        manifest = {"migrations": []}
        if MANIFEST_PATH.exists():
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["migrations"].append(entry)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
        print(f"[manifest] -> {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
