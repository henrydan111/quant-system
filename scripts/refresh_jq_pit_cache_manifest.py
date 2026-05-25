"""Regenerate ``data/external/jq_pit_cache/manifest.json`` from the on-disk
coverage. Run this after any cache refresh so consumers can verify coverage
before consuming data.

Produces a manifest like:

  {
    "schema_version": 1,
    "last_refresh_utc": "2026-05-22T15:30:00Z",
    "refresh_method": "manual_export_via_jq_research_notebook",
    "indices_tracked": ["399101.XSHE", "000300.XSHG", "000852.XSHG"],
    "coverage": {
      "index_members": {
        "399101.XSHE": {"start": "2014-01-07", "end": "2026-02-24",
                        "n_snapshots": 597, "year_files": [...]}
      },
      "valuation": {"start": null, "end": null, "month_files": []},
      "flags":     {"start": null, "end": null, "month_files": []}
    }
  }
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CACHE = Path(__file__).resolve().parents[1] / "data" / "external" / "jq_pit_cache"


def _scan_index_members() -> dict:
    out = {}
    root = CACHE / "index_members"
    if not root.exists():
        return out
    for idx_dir in sorted(root.iterdir()):
        if not idx_dir.is_dir():
            continue
        files = sorted(idx_dir.glob("*.parquet"))
        if not files:
            continue
        all_dates = []
        for f in files:
            df = pd.read_parquet(f, columns=["date"])
            all_dates.extend(pd.to_datetime(df["date"]).tolist())
        if not all_dates:
            continue
        ser = pd.Series(all_dates).drop_duplicates().sort_values()
        out[idx_dir.name] = {
            "start": ser.iloc[0].date().isoformat(),
            "end": ser.iloc[-1].date().isoformat(),
            "n_snapshots": int(len(ser)),
            "year_files": [f.name for f in files],
        }
    return out


def _scan_monthly(subdir: str) -> dict:
    root = CACHE / subdir
    if not root.exists():
        return {"start": None, "end": None, "month_files": []}
    files = sorted(root.glob("*.parquet"))
    if not files:
        return {"start": None, "end": None, "month_files": []}
    all_dates = []
    for f in files:
        df = pd.read_parquet(f, columns=["date"])
        all_dates.extend(pd.to_datetime(df["date"]).tolist())
    if not all_dates:
        return {"start": None, "end": None, "month_files": [f.name for f in files]}
    ser = pd.Series(all_dates).drop_duplicates().sort_values()
    return {
        "start": ser.iloc[0].date().isoformat(),
        "end": ser.iloc[-1].date().isoformat(),
        "n_days": int(len(ser)),
        "month_files": [f.name for f in files],
    }


def main() -> int:
    index_members = _scan_index_members()
    valuation = _scan_monthly("valuation")
    flags = _scan_monthly("flags")

    manifest = {
        "schema_version": 1,
        "last_refresh_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "refresh_method": "manual_export_via_jq_research_notebook",
        "indices_tracked": sorted(index_members.keys()),
        "coverage": {
            "index_members": index_members,
            "valuation": valuation,
            "flags": flags,
        },
        "source_notebook": "workspace/scripts/templates/jq_pit_cache_refresh.py",
        "notes": (
            "PIT cache for JoinQuant-deployment parity. Read via "
            "src.data_infra.jq_pit_cache.JoinQuantPITLoader. Refresh "
            "weekly via the JoinQuant research notebook template. See "
            "data/external/jq_pit_cache/README.md."
        ),
    }

    out_path = CACHE / "manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"  Indices: {sorted(index_members.keys())}")
    for idx, info in index_members.items():
        print(f"    {idx}: {info['start']} → {info['end']}  ({info['n_snapshots']} snapshots)")
    print(f"  Valuation: {valuation['start']} → {valuation['end']}  ({valuation.get('n_days', 0)} days)")
    print(f"  Flags:     {flags['start']} → {flags['end']}  ({flags.get('n_days', 0)} days)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
