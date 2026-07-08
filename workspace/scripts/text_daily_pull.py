# SCRIPT_STATUS: ACTIVE — Phase-2A daily forward text pull (scheduled task)
"""Daily incremental pull of the 4 ts_code-bearing text sources into the C1 store.

Design:
  - LOOKBACK = 4 calendar days each run: catches late replies/revisions and a
    missed run (machine off). Idempotent — content_hash dedup in text_store
    means overlapping pulls are free; a revision becomes a NEW row (C1).
  - anns_d uses offset pagination (busy days exceed 2000/call).
  - Sequential calls only (§6.1). Logs to logs/text_daily_pull.log (rotating).

Scheduled as Windows task `QuantTextDailyPull` (daily 20:30) — the forward
clean panel accrues through this job; without it, only fixtures exist.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import date, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from data_infra.fetchers import TushareFetcher  # noqa: E402
from data_infra.text_store import ingest_rows  # noqa: E402

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
handler = RotatingFileHandler(LOG_DIR / "text_daily_pull.log",
                              maxBytes=2_000_000, backupCount=3, encoding="utf-8")
logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()],
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("text_daily_pull")

LOOKBACK_DAYS = 4


def main() -> int:
    f = TushareFetcher()
    end = date.today()
    start = end - timedelta(days=LOOKBACK_DAYS - 1)
    log.info("daily pull window %s..%s", start, end)

    counts: dict[str, int] = {}
    failures: list[str] = []
    d = start
    while d <= end:
        ymd = d.strftime("%Y%m%d")
        now = pd.Timestamp.now()
        for source, call, pub_col in (
            ("anns_d", lambda: f.fetch_anns_d_paged(ymd), "rec_time"),
            ("research_report", lambda: f.fetch_research_report(ymd), None),
            ("irm_qa_sh", lambda: f.fetch_irm_qa_sh(ymd, ymd), "pub_time"),
            ("irm_qa_sz", lambda: f.fetch_irm_qa_sz(ymd, ymd), "pub_time"),
        ):
            try:
                df = call()
            except Exception as e:  # noqa: BLE001
                failures.append(f"{source}@{ymd}: {type(e).__name__}: {e}")
                log.error("%s @%s failed: %s", source, ymd, e)
                continue
            if df is None or df.empty:
                continue
            ingest_rows(source, df, published_col=pub_col, retrieved_at=now)
            counts[source] = counts.get(source, 0) + len(df)
        d += timedelta(days=1)
        time.sleep(0.3)

    log.info("done: %s%s", counts, f" | FAILURES: {failures}" if failures else "")
    return 1 if failures and not counts else 0


if __name__ == "__main__":
    raise SystemExit(main())
