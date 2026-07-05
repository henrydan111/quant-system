# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 1 catch-up driver (UNFREEZE_PLAN.md Phase 1.3)
"""Serial per-trading-day raw-layer catch-up for the calendar unfreeze.

Covers ONLY the trade_date-partitioned datasets (market daily + index daily +
Phase-3 daily sets + suspend_d). Reference data (trade_cal/stock_basic) is
deliberately NOT refreshed here (hoisted out per plan Phase 1.3 — refresh once
before running this). Fundamentals / ann_date-anchored families are handled by
the separate ann_date-window bulk step (plan Phase 1.4), NOT here.

Resume-safe: writes per-date status to a JSON state file; completed dates are
skipped on re-run; failed dates are retried on re-run.

Usage:
    venv/Scripts/python.exe workspace/scripts/catchup_daily_range.py \
        --start 20260302 --end 20260630 [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from data_infra.pipeline.update_daily_data import DailyDataUpdater  # noqa: E402

LOG_PATH = os.path.join(PROJECT_ROOT, "logs", "catchup_daily_unfreeze.log")
STATE_PATH = os.path.join(
    PROJECT_ROOT, "workspace", "outputs", "calendar_unfreeze", "catchup_state.json"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("catchup")


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_PATH)


def trading_days(start: str, end: str) -> list[str]:
    cal = pd.read_parquet(os.path.join(PROJECT_ROOT, "data", "reference", "trade_cal.parquet"))
    days = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= start) & (cal["cal_date"] <= end)]
    return sorted(days["cal_date"].astype(str).tolist())


def run_one_day(updater: DailyDataUpdater, date: str) -> dict:
    detail: dict = {}

    market_symbols = updater.update_market_data(date)
    if not market_symbols:
        raise RuntimeError(f"market data empty for trading day {date}")
    detail["market_rows"] = len(market_symbols)

    updater.update_index_data(date)
    detail["index"] = "ok"

    _, phase3_sets = updater.update_phase3_daily_market(date)
    detail["phase3"] = sorted(phase3_sets)

    # suspend_d is not wired into the daily updater (bootstrap-only historically); fetch per
    # trade_date here so the suspension proxy stays exact over the gap. Write the per-date file
    # DIRECTLY (overwrite) rather than via insert_market_data's merge: suspend_d(date) is a complete
    # same-date snapshot, so a re-fetch REPLACES it, and this preserves suspend_timing (the merge
    # would duplicate rows + drop timing on a schema change). suspend_timing is load-bearing for the
    # monthly-bump full-day-vs-intraday completeness proof (GPT B1-b).
    df_susp = updater.fetcher.fetch_suspend_d(trade_date=date)
    susp_dir = os.path.join(PROJECT_ROOT, "data", "market", "suspend_d", date[:4])
    os.makedirs(susp_dir, exist_ok=True)
    susp_path = os.path.join(susp_dir, f"suspend_d_{date}.parquet")
    keep = [c for c in ("ts_code", "trade_date", "suspend_type", "suspend_timing") if c in df_susp.columns]
    out = df_susp[keep] if (not df_susp.empty and keep) else pd.DataFrame(
        columns=["ts_code", "trade_date", "suspend_type", "suspend_timing"])
    tmp = susp_path + ".tmp"
    out.to_parquet(tmp, index=False)
    os.replace(tmp, susp_path)
    detail["suspend_rows"] = int(len(df_susp))
    detail["suspend_timing_present"] = "suspend_timing" in keep

    return detail


def main() -> None:
    parser = argparse.ArgumentParser(description="Calendar-unfreeze daily catch-up driver")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    days = trading_days(args.start, args.end)
    state = load_state()
    pending = [d for d in days if state.get(d, {}).get("status") != "done"]

    logger.info(
        "Catch-up window %s..%s: %d trading days total, %d already done, %d pending",
        args.start, args.end, len(days), len(days) - len(pending), len(pending),
    )
    if args.dry_run:
        logger.info("[dry-run] pending dates: %s", ", ".join(pending) or "(none)")
        return

    updater = DailyDataUpdater(config_path=os.path.join(PROJECT_ROOT, "config.yaml"))

    started = time.time()
    failed: list[str] = []
    for idx, date in enumerate(pending, 1):
        day_started = time.time()
        try:
            detail = run_one_day(updater, date)
            state[date] = {"status": "done", "at": datetime.now().isoformat(timespec="seconds"), **detail}
        except Exception as exc:  # noqa: BLE001 — per-day isolation, rerun retries
            logger.error("FAILED %s: %s", date, exc)
            state[date] = {"status": "failed", "error": str(exc), "at": datetime.now().isoformat(timespec="seconds")}
            failed.append(date)
        save_state(state)

        elapsed = time.time() - started
        eta_min = (elapsed / idx) * (len(pending) - idx) / 60
        logger.info(
            "PROGRESS %d/%d %s status=%s day_secs=%.0f eta_min=%.0f",
            idx, len(pending), date, state[date]["status"], time.time() - day_started, eta_min,
        )

    done = sum(1 for d in days if state.get(d, {}).get("status") == "done")
    logger.info("CATCHUP COMPLETE: %d/%d done, %d failed%s",
                done, len(days), len(failed), f" -> {failed}" if failed else "")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
