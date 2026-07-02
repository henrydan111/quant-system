# SCRIPT_STATUS: ACTIVE — one-off: cyq_perf backfill for 2026-07-01 (calendar-unfreeze target_end move 0630->0701)
"""Per-symbol cyq_perf fetch for the single day 2026-07-01, repartitioned into
the per-date raw layout (data/market/cyq_perf/2026/cyq_perf_20260701.parquet).
Resume-safe via a buffer dir; strictly serial single fetcher."""
from __future__ import annotations

import logging
import os
import sys
import time

import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
from data_infra.fetchers import TushareFetcher  # noqa: E402

DAY = "20260701"
BUF = os.path.join(PROJECT_ROOT, "workspace", "outputs", "calendar_unfreeze", "cyq_buffer_0701")
OUT = os.path.join(PROJECT_ROOT, "data", "market", "cyq_perf", "2026", f"cyq_perf_{DAY}.parquet")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("cyq0701")


def main() -> None:
    os.makedirs(BUF, exist_ok=True)
    basic = pd.read_parquet(os.path.join(PROJECT_ROOT, "data", "reference", "stock_basic.parquet"))
    live = basic[basic["list_status"] == "L"]["ts_code"]
    dead = basic[(basic["list_status"] == "D") & (basic["delist_date"].fillna("99999999") >= DAY)]["ts_code"]
    symbols = sorted(set(live) | set(dead))
    done = {f[:-8].replace("_", ".") for f in os.listdir(BUF)}  # 000001_SZ.parquet -> 000001.SZ
    pending = [s for s in symbols if s not in done]
    log.info("cyq %s: %d symbols total, %d pending", DAY, len(symbols), len(pending))

    fetcher = TushareFetcher(config_path=os.path.join(PROJECT_ROOT, "config.yaml"), max_retries=5, base_sleep=1.5)
    started = time.time()
    for i, code in enumerate(pending, 1):
        try:
            df = fetcher.fetch_cyq_perf(ts_code=code, start_date=DAY, end_date=DAY)
            if not df.empty:
                df.to_parquet(os.path.join(BUF, f"{code.replace('.', '_')}.parquet"), index=False)
            else:  # marker so resume skips confirmed-empty symbols
                pd.DataFrame().to_parquet(os.path.join(BUF, f"{code.replace('.', '_')}.parquet"), index=False)
        except Exception as exc:  # noqa: BLE001 — per-symbol isolation; rerun retries
            log.error("FAILED %s: %s", code, exc)
        if i % 250 == 0:
            eta = (time.time() - started) / i * (len(pending) - i) / 60
            log.info("PROGRESS %d/%d eta_min=%.0f", i, len(pending), eta)

    frames = []
    for f in os.listdir(BUF):
        d = pd.read_parquet(os.path.join(BUF, f))
        if not d.empty:
            frames.append(d)
    allf = pd.concat(frames, ignore_index=True)
    allf = allf[allf["trade_date"].astype(str) == DAY].reset_index(drop=True)
    tmp = OUT + ".tmp"
    allf.to_parquet(tmp, index=False)
    os.replace(tmp, OUT)
    log.info("CYQ0701 COMPLETE: %d rows -> %s", len(allf), OUT)


if __name__ == "__main__":
    main()
