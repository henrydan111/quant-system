# SCRIPT_STATUS: ACTIVE — one-shot bootstrap coverage manifests (R3 Blocker-3)
"""Write per-source BOOTSTRAP pull manifests covering the pre-manifest-era
initial text ingestion, so `check_text_coverage_history` can verify the 30-day
dossier window across the manifest-era boundary.

Method (recorded in each manifest): the covered window is derived from the
store's own SOURCE observation dates (min..max of the source's nominal date
column). These rows are forward-eligible only from their true
``first_ingested_at`` (the C1 gate enforces that independently); the bootstrap
manifest claims SOURCE-AVAILABILITY coverage only.

One manifest per source (own window + own status) — a source is never granted
coverage from another source's window.

Usage: venv/Scripts/python.exe workspace/scripts/write_text_bootstrap_manifest.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

STORE = PROJECT_ROOT / "data" / "text_store"
OUT_DIR = PROJECT_ROOT / "logs" / "text_pull"

#: nominal source-date column per source (observation date, NOT visibility)
DATE_COL = {
    "anns_d": "ann_date",
    "irm_qa_sh": "pub_time",
    "irm_qa_sz": "pub_time",
    "research_report": "trade_date",
}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="Asia/Shanghai")
    for source, col in DATE_COL.items():
        path = STORE / source / f"text_{source}.parquet"
        if not path.exists():
            print(f"[skip] {source}: no store")
            continue
        df = pd.read_parquet(path, columns=[col])
        dates = pd.to_datetime(df[col].astype(str).str[:10].str.replace("-", "")
                               .str[:8], format="%Y%m%d", errors="coerce").dropna()
        if dates.empty:
            print(f"[skip] {source}: no parseable dates")
            continue
        start, end = dates.min().date(), dates.max().date()
        manifest = {
            "run_ts": now.isoformat(),
            "timezone": "Asia/Shanghai",
            "bootstrap": True,
            "method": ("window derived from store nominal source dates "
                       f"(column {col}); source-availability coverage only; "
                       "visibility remains gated by first_ingested_at (C1)"),
            "window": {"start": str(start), "end": str(end)},
            "lookback_days": None,
            "counts": {source: int(len(df))},
            "source_status": {source: "ok_nonzero_rows"},
            "failures": [],
            "ok": True,
        }
        out = OUT_DIR / f"pull_manifest_00000000_bootstrap_{source}.json"
        out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        print(f"[{source}] bootstrap window {start}..{end} rows={len(df)} -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
