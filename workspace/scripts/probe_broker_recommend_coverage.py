"""Coverage probe for Tushare broker_recommend (券商月度金股, doc_id=267).

Read-only feasibility diagnostic for the Option-A "券商金股 mother signal"
validation. Answers ONE question before any ingestion: how far back does
broker_recommend history go, and how big is each monthly list?

Safety (CLAUDE.md §6.1):
  - STRICTLY SEQUENTIAL. One call at a time. Never parallel.
  - Read-only: writes a small JSON summary to workspace/outputs/, touches no
    data/ partition.
  - Interface doc (267_券商月度金股.md) was read before running this.
  - Endpoint schema: input month(YYYYMM); output month/broker/ts_code/name.
    Cadence: current month updated within 1-3 days. 6000积分 (account has 15000).

Usage:
    venv/Scripts/python.exe workspace/scripts/probe_broker_recommend_coverage.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_infra.fetchers import TushareFetcher  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("probe_broker_recommend")

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _probe_months() -> list[str]:
    """Jan + Jul of each year 2013..2026, plus the most recent months."""
    months: list[str] = []
    for year in range(2013, 2027):
        months.append(f"{year}01")
        months.append(f"{year}07")
    # densify the recent edge
    months += ["202602", "202603", "202604", "202605", "202606"]
    return sorted(set(months))


def main() -> int:
    fetcher = TushareFetcher(base_sleep=1.5, max_retries=2)
    results: list[dict] = []
    earliest_nonempty: str | None = None

    for month in _probe_months():
        try:
            df = fetcher._safe_api_call(fetcher.pro.broker_recommend, month=month)
        except Exception as e:  # definitive denial or repeated failure
            logger.warning("month=%s -> ERROR %s", month, e)
            results.append({"month": month, "error": str(e)[:200]})
            continue

        if df is None or df.empty:
            logger.info("month=%s -> EMPTY", month)
            results.append({"month": month, "rows": 0})
            continue

        n_rows = len(df)
        n_brokers = int(df["broker"].nunique()) if "broker" in df.columns else None
        n_codes = int(df["ts_code"].nunique()) if "ts_code" in df.columns else None
        cols = list(df.columns)
        results.append(
            {
                "month": month,
                "rows": n_rows,
                "n_brokers": n_brokers,
                "n_codes": n_codes,
                "columns": cols,
            }
        )
        if earliest_nonempty is None:
            earliest_nonempty = month
        logger.info(
            "month=%s -> rows=%d brokers=%s codes=%s cols=%s",
            month, n_rows, n_brokers, n_codes, cols,
        )

    summary = {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": "broker_recommend",
        "doc_id": 267,
        "earliest_nonempty_probed": earliest_nonempty,
        "n_months_probed": len(results),
        "n_months_with_data": sum(1 for r in results if r.get("rows", 0) > 0),
        "results": results,
    }
    out_path = OUT_DIR / "broker_recommend_coverage_probe.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== broker_recommend coverage probe =====")
    print(f"earliest non-empty (of probed months): {earliest_nonempty}")
    print(f"months with data: {summary['n_months_with_data']} / {len(results)}")
    print(f"{'month':>8} | {'rows':>5} | {'brokers':>7} | {'codes':>5}")
    for r in results:
        if r.get("rows", 0) > 0:
            print(f"{r['month']:>8} | {r['rows']:>5} | {str(r.get('n_brokers')):>7} | {str(r.get('n_codes')):>5}")
    print(f"\nfull report -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
