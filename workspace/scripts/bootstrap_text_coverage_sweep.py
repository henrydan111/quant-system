# SCRIPT_STATUS: ACTIVE — one-shot DAY-LEVEL bootstrap coverage sweep (R4 Blocker-3)
"""Real per-day, per-source Tushare sweep establishing DAY-LEVEL source
availability for the pre-daily-task era — replaces the retired min..max
row-derived bootstrap (too coarse for the formal coverage gate: a zero-row day
inside a range was marked covered without proof the source was queried).

For every (day, source): actually query the API, record
``ok_zero_rows / ok_nonzero_rows / failed`` per day, ingest any rows
(idempotent content-hash dedup; visibility of NEW rows = today's
first_ingested_at — C1 holds independently). Each source gets a bootstrap
manifest with ``coverage_by_day`` + the query log + its hash; the coverage
gate credits ONLY day-level bootstrap manifests.

Sequential calls only (§6.1). Usage:
  venv/Scripts/python.exe workspace/scripts/bootstrap_text_coverage_sweep.py [--start 20260628]
"""
from __future__ import annotations

import argparse
import hashlib
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
from data_infra.text_store import ingest_rows  # noqa: E402

OUT_DIR = PROJECT_ROOT / "logs" / "text_pull"
CN_TZ = "Asia/Shanghai"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20260628")
    args = ap.parse_args()

    f = TushareFetcher()
    now = pd.Timestamp.now(tz=CN_TZ)
    start = date(int(args.start[:4]), int(args.start[4:6]), int(args.start[6:8]))
    end = now.date()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sources = {
        "anns_d": (lambda ymd: f.fetch_anns_d_paged(ymd), "rec_time"),
        "research_report": (lambda ymd: f.fetch_research_report(ymd), None),
        "irm_qa_sh": (lambda ymd: f.fetch_irm_qa_sh(ymd, ymd), "pub_time"),
        "irm_qa_sz": (lambda ymd: f.fetch_irm_qa_sz(ymd, ymd), "pub_time"),
    }
    coverage = {s: {} for s in sources}
    query_log = {s: [] for s in sources}

    d = start
    while d <= end:
        ymd = d.strftime("%Y%m%d")
        iso = d.isoformat()
        for source, (call, pub_col) in sources.items():
            t0 = time.time()
            try:
                df = call(ymd)
            except Exception as e:  # noqa: BLE001
                coverage[source][iso] = "failed"
                query_log[source].append({"day": iso, "status": "failed",
                                          "error": f"{type(e).__name__}: {e}"[:200]})
                print(f"[{source}] {iso} FAILED: {e}", flush=True)
                continue
            n = 0 if df is None else len(df)
            truncated = bool(getattr(df, "attrs", {}).get("truncated")) if df is not None else False
            if truncated:
                coverage[source][iso] = "failed"
                query_log[source].append({"day": iso, "status": "failed",
                                          "error": "truncated (max_pages hit)"})
                print(f"[{source}] {iso} TRUNCATED -> failed", flush=True)
                continue
            if n > 0:
                ingest_rows(source, df, published_col=pub_col,
                            retrieved_at=pd.Timestamp.now(tz=CN_TZ))
            coverage[source][iso] = "ok_nonzero_rows" if n > 0 else "ok_zero_rows"
            query_log[source].append({"day": iso, "status": coverage[source][iso],
                                      "rows": n, "latency_s": round(time.time() - t0, 2)})
            print(f"[{source}] {iso} {coverage[source][iso]} rows={n}", flush=True)
        d += timedelta(days=1)
        time.sleep(0.3)

    for source in sources:
        log_payload = json.dumps(query_log[source], ensure_ascii=False, sort_keys=True)
        manifest = {
            "run_ts": now.isoformat(),
            "timezone": CN_TZ,
            "bootstrap": True,
            "source": source,
            "method": "explicit YYYYMMDD daily sweep (real per-day API queries)",
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "coverage_by_day": coverage[source],
            "query_log": query_log[source],
            "query_log_hash": hashlib.sha256(log_payload.encode("utf-8")).hexdigest(),
            "visibility_note": "rows remain gated by first_ingested_at (C1)",
            "failures": [f"{source}@{d_}" for d_, st in coverage[source].items()
                         if st == "failed"],
            # day-level granularity supersedes the manifest-level flag: the
            # coverage gate credits each ok_ day individually; failed days
            # simply earn no credit (recorded above for audit)
            "ok": True,
        }
        out = OUT_DIR / f"pull_manifest_00000000_bootstrap_{source}.json"
        out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        n_ok = sum(1 for v in coverage[source].values() if v.startswith("ok_"))
        print(f"[{source}] day-level bootstrap: {n_ok}/{len(coverage[source])} days ok "
              f"-> {out.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
