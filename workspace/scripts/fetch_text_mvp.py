# SCRIPT_STATUS: ACTIVE — Phase-2A MVP text ingestion shakedown + pool-density telemetry
"""Fetch the 4 ts_code-bearing text sources into the C1 text store + measure density.

Sources (per data_dictionary.md; sequential, NEVER parallel — §6.1):
  anns_d          (published_col=rec_time)   公告标题+PDF URL
  irm_qa_sh/_sz   (published_col=pub_time)   互动易问答全文
  research_report (published_col=None ⚠ nominal trade_date -> visible=ingestion)

C1 semantics: THIS backfill window is fixture-only (visible from ingestion time);
the clean forward panel accrues from today onward. Purpose here = pipeline
shakedown + the pre-registered density telemetry (user hypothesis premise:
"pool text is denser than broad").

Writes ONLY under data/text_store/ (new directory; no existing data touched).
Outputs telemetry -> workspace/outputs/text_mvp/density_telemetry.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from data_infra.fetchers import TushareFetcher  # noqa: E402
from data_infra.text_store import ingest_rows, load_text  # noqa: E402
from data_infra.golden_stock_universe import load_golden_stock_events  # noqa: E402

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "text_mvp"
CAPS = {"anns_d": 2000, "research_report": 1000, "irm_qa_sh": 3000, "irm_qa_sz": 3000}


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-06-01")
    ap.add_argument("--end", default="2026-07-06")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)

    print(f"[plan] window {start}..{end}; writes ONLY data/text_store/{{source}}/ "
          f"(+ telemetry under workspace/outputs/text_mvp/)", flush=True)
    if args.dry_run:
        n = sum(1 for _ in daterange(start, end))
        print(f"[dry-run] would make ~{n * 2} per-day calls (anns_d, research_report) "
              f"+ ~{n * 2} per-day range calls (irm_qa_sh/sz); no API touched.", flush=True)
        return 0

    f = TushareFetcher()
    counts = {s: 0 for s in CAPS}
    truncated: dict[str, list[str]] = {s: [] for s in CAPS}
    errors: dict[str, str] = {}

    for d in daterange(start, end):
        ymd = d.strftime("%Y%m%d")
        now = pd.Timestamp.now()
        for source, call, pub_col in (
            ("anns_d", lambda: f.fetch_anns_d(ymd), "rec_time"),
            ("research_report", lambda: f.fetch_research_report(ymd), None),
            ("irm_qa_sh", lambda: f.fetch_irm_qa_sh(ymd, ymd), "pub_time"),
            ("irm_qa_sz", lambda: f.fetch_irm_qa_sz(ymd, ymd), "pub_time"),
        ):
            if source in errors:
                continue  # permission/API failure earlier — skip source, keep going
            try:
                df = call()
            except Exception as e:  # noqa: BLE001 — log & continue per source
                errors[source] = f"{type(e).__name__}: {e}"
                print(f"[ERROR] {source} @{ymd}: {errors[source]} — skipping source", flush=True)
                continue
            if df is None or df.empty:
                continue
            if len(df) >= CAPS[source]:
                truncated[source].append(ymd)
            ingest_rows(source, df, published_col=pub_col, retrieved_at=now)
            counts[source] += len(df)
        if d.day % 7 == 0:
            print(f"[progress] through {ymd}: {counts}", flush=True)
        time.sleep(0.3)  # extra politeness between days (§6.1)

    print(f"[done] rows ingested: {counts}", flush=True)
    for s, days in truncated.items():
        if days:
            print(f"[WARN] {s} hit per-call cap on {len(days)} day(s): {days[:5]}...", flush=True)

    # ---- density telemetry (deterministic, no LLM) ----
    events = load_golden_stock_events()
    pool = set()
    for m in ("202605", "202606"):
        pool |= set(events.loc[events["month"] == m, "ts_code"])
    print(f"[telemetry] pool (202605+202606 union) = {len(pool)} names", flush=True)

    sb = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet",
                         columns=["ts_code", "list_status"])
    n_listed = int((sb["list_status"] == "L").sum())

    telem: dict = {"window": f"{start}..{end}", "pool_size": len(pool),
                   "n_listed_broad": n_listed, "sources": {}, "errors": errors}
    now = pd.Timestamp.now() + pd.Timedelta(days=1)
    for source in CAPS:
        rows = load_text(source, now)
        if rows.empty or "ts_code" not in rows.columns:
            telem["sources"][source] = {"rows": 0}
            continue
        per_name = rows.groupby("ts_code").size()
        pool_counts = per_name[per_name.index.isin(pool)]
        telem["sources"][source] = {
            "rows": int(len(rows)),
            "names_covered": int(per_name.size),
            "pool_names_covered": int(pool_counts.size),
            "pool_coverage_pct": round(pool_counts.size / max(len(pool), 1), 3),
            "broad_coverage_pct": round(per_name.size / n_listed, 3),
            "texts_per_covered_pool_name": round(float(pool_counts.mean()), 2) if len(pool_counts) else 0,
            "texts_per_covered_broad_name": round(float(per_name.mean()), 2),
            "pool_share_of_rows": round(float(rows["ts_code"].isin(pool).mean()), 3),
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "density_telemetry.json").write_text(
        json.dumps(telem, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(telem, indent=2, ensure_ascii=False), flush=True)
    print(f"wrote -> {OUT_DIR / 'density_telemetry.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
