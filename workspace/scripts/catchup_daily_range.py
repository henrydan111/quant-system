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


def _suspend_d_path(date: str) -> str:
    return os.path.join(PROJECT_ROOT, "data", "market", "suspend_d", date[:4], f"suspend_d_{date}.parquet")


def write_suspend_d(updater: DailyDataUpdater, date: str) -> dict:
    """Delegate to the canonical DailyDataUpdater.write_suspend_d (atomic overwrite, timing-
    preserving) so the daily-raw job and the monthly-bump catch-up share ONE suspend_d writer — the
    suspend_timing it preserves is load-bearing for the completeness proof (GPT B1-b)."""
    return updater.write_suspend_d(date)


def suspend_d_needs_refetch(date: str) -> bool:
    """True if suspend_d(date) is absent, unreadable, missing required columns, or has S rows but no
    suspend_timing column (a legacy no-timing file the monthly gate fails closed on). An empty file
    (no suspensions) is fine. Lets a done-day get a targeted timing-schema refresh (GPT m1)."""
    path = _suspend_d_path(date)
    if not os.path.exists(path):
        return True
    try:
        df = pd.read_parquet(path)
    except Exception:  # noqa: BLE001 — unreadable -> re-fetch
        return True
    if not {"ts_code", "trade_date", "suspend_type"} <= set(df.columns):
        return True
    if len(df) == 0:
        return False
    stype = df["suspend_type"].astype(str).str.upper()
    return bool((stype == "S").any()) and "suspend_timing" not in df.columns


def run_one_day(updater: DailyDataUpdater, date: str) -> dict:
    detail: dict = {}

    market_symbols = updater.update_market_data(date)
    if not market_symbols:
        raise RuntimeError(f"market data empty for trading day {date}")
    detail["market_rows"] = len(market_symbols)

    updater.update_index_data(date)
    detail["index"] = "ok"

    # update_phase3_daily_market now writes suspend_d (with timing) itself (Phase 5-C/C2), so it is
    # NOT re-fetched here — a second call would double the Tushare hit per session (GPT m1).
    _, phase3_sets = updater.update_phase3_daily_market(date)
    detail["phase3"] = sorted(phase3_sets)
    if "suspend_d" not in phase3_sets:  # write failed -> RAISE so the day is marked failed + retried
        raise RuntimeError(f"suspend_d write failed for {date}: {getattr(updater, '_suspend_error', '?')}")
    detail["suspend_d"] = True

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
    # GPT m1: a day marked `done` under the OLD daily path may have a legacy no-timing suspend_d the
    # monthly gate fails closed on. Give those a TARGETED suspend_d-only timing refresh (not a full
    # re-fetch of market/index/phase3), so the gate becomes self-healing without manual state edits.
    suspend_refresh = [d for d in days
                       if state.get(d, {}).get("status") == "done" and suspend_d_needs_refetch(d)]

    logger.info(
        "Catch-up window %s..%s: %d trading days total, %d already done, %d pending, %d suspend_d refresh",
        args.start, args.end, len(days), len(days) - len(pending), len(pending), len(suspend_refresh),
    )
    if args.dry_run:
        logger.info("[dry-run] pending dates: %s", ", ".join(pending) or "(none)")
        logger.info("[dry-run] suspend_d timing-refresh dates: %s", ", ".join(suspend_refresh) or "(none)")
        return

    updater = DailyDataUpdater(config_path=os.path.join(PROJECT_ROOT, "config.yaml"))

    # cross-process Tushare-account lock (CLAUDE.md §6.1) so the monthly catch-up serializes with the
    # daily raw job / any manual fetch (GPT 5-C M4).
    from data_infra.pipeline.daily_ops import account_lock

    started = time.time()
    failed: list[str] = []
    with account_lock(os.path.join(PROJECT_ROOT, "logs")):
        for date in suspend_refresh:
            try:
                detail = write_suspend_d(updater, date)
                state.setdefault(date, {}).update({"suspend_d_schema": "timing_required_v1", **detail})
                logger.info("suspend_d timing-refresh %s: rows=%d timing=%s",
                            date, detail["suspend_rows"], detail["suspend_timing_present"])
            except Exception as exc:  # noqa: BLE001 — a refresh failure IS a failure (GPT M2)
                logger.error("suspend_d refresh FAILED %s: %s", date, exc)
                failed.append(f"suspend_refresh:{date}")
            save_state(state)

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
