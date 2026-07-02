# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 1 fundamentals/events catch-up (UNFREEZE_PLAN.md Phase 1.4-1.5)
"""ann_date-window bulk catch-up for announcement-anchored datasets.

Contract: workspace/research/calendar_unfreeze/endpoint_contracts.yaml.
Fetches by ANN_DATE WINDOW (never by report period — a period-based fetch would
miss gap-period restatement announcements for older periods; plan Phase 1.4).

Stages (all resume-safe via a per-key JSON state file; strictly serial):
  A  weekly ann_date chunks : income income_quarterly balancesheet cashflow
                              cashflow_quarterly indicators holder_number
  B  per-day ann_date       : forecast dividends
  C  ann_date chunks->merge : stk_holdertrade (year-file layout)
  D  per-symbol range       : cyq_perf (auto-detects last covered date)
  E  month chunks->merge    : report_rc (report_date query; refetch from 202602 overlap)
  F  monthly                : index_weights (202603..202606 x 7 indices)

Usage:
    venv/Scripts/python.exe workspace/scripts/catchup_fundamentals_range.py \
        --start 20260228 --end 20260630 [--stages ABCDEF] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from data_infra.fetchers import TushareFetcher  # noqa: E402
from data_infra.storage import StorageManager  # noqa: E402

LOG_PATH = os.path.join(PROJECT_ROOT, "logs", "catchup_fundamentals_unfreeze.log")
STATE_PATH = os.path.join(
    PROJECT_ROOT, "workspace", "outputs", "calendar_unfreeze", "catchup_fund_state.json"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("catchup_fund")


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


def weekly_chunks(start: str, end: str) -> list[tuple[str, str]]:
    chunks = []
    cur = datetime.strptime(start, "%Y%m%d")
    stop = datetime.strptime(end, "%Y%m%d")
    while cur <= stop:
        upper = min(cur + timedelta(days=6), stop)
        chunks.append((cur.strftime("%Y%m%d"), upper.strftime("%Y%m%d")))
        cur = upper + timedelta(days=1)
    return chunks


def calendar_days(start: str, end: str) -> list[str]:
    return [d.strftime("%Y%m%d") for d in pd.date_range(start, end, freq="D")]


def trading_days(start: str, end: str) -> list[str]:
    cal = pd.read_parquet(os.path.join(PROJECT_ROOT, "data", "reference", "trade_cal.parquet"))
    days = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= start) & (cal["cal_date"] <= end)]
    return sorted(days["cal_date"].astype(str).tolist())


class Runner:
    def __init__(self, start: str, end: str, dry: bool):
        self.start, self.end, self.dry = start, end, dry
        self.state = load_state()
        self.fetcher = TushareFetcher(
            config_path=os.path.join(PROJECT_ROOT, "config.yaml"), max_retries=5, base_sleep=1.5
        )
        self.storage = StorageManager()
        self.failed: list[str] = []

    def _run_key(self, key: str, fn) -> None:
        if self.state.get(key, {}).get("status") == "done":
            return
        if self.dry:
            logger.info("[dry-run] would run %s", key)
            return
        try:
            detail = fn() or {}
            self.state[key] = {"status": "done", "at": datetime.now().isoformat(timespec="seconds"), **detail}
        except Exception as exc:  # noqa: BLE001 — per-key isolation, rerun retries
            logger.error("FAILED %s: %s", key, exc)
            self.state[key] = {"status": "failed", "error": str(exc)}
            self.failed.append(key)
        save_state(self.state)

    # ---------- Stage A: weekly ann_date range chunks ----------
    STAGE_A = [
        ("income", lambda f, s, e: f.fetch_income_vip(report_type="1", start_date=s, end_date=e), "fundamental", "income"),
        ("income_quarterly", lambda f, s, e: f.fetch_income_quarterly_vip(start_date=s, end_date=e), "fundamental", "income_quarterly"),
        ("balancesheet", lambda f, s, e: f.fetch_balancesheet_vip(report_type="1", start_date=s, end_date=e), "fundamental", "balancesheet"),
        ("cashflow", lambda f, s, e: f.fetch_cashflow_vip(report_type="1", start_date=s, end_date=e), "fundamental", "cashflow"),
        ("cashflow_quarterly", lambda f, s, e: f.fetch_cashflow_quarterly_vip(start_date=s, end_date=e), "fundamental", "cashflow_quarterly"),
        ("indicators", lambda f, s, e: f.fetch_fina_indicator_vip(start_date=s, end_date=e), "fundamental", "indicators"),
        ("holder_number", lambda f, s, e: f.fetch_stk_holdernumber(start_date=s, end_date=e), "corporate", "holder_number"),
    ]

    def stage_a(self) -> None:
        for name, fetch, kind, cat in self.STAGE_A:
            for lo, hi in weekly_chunks(self.start, self.end):
                def work(name=name, fetch=fetch, kind=kind, cat=cat, lo=lo, hi=hi):
                    df = fetch(self.fetcher, lo, hi)
                    if df.empty:
                        logger.info("  %s %s..%s: 0 rows", name, lo, hi)
                        return {"rows": 0}
                    df = df.dropna(how="all", axis=1)
                    if kind == "fundamental":
                        self.storage.insert_fundamental_data(df, cat)
                    else:
                        self.storage.insert_corporate_data(df, cat)
                    logger.info("  %s %s..%s: %d rows", name, lo, hi, len(df))
                    return {"rows": int(len(df))}
                self._run_key(f"A:{name}:{lo}-{hi}", work)

    # ---------- Stage B: per-day ann_date ----------
    def stage_b(self) -> None:
        for day in calendar_days(self.start, self.end):
            def work_fc(day=day):
                df = self.fetcher.fetch_forecast(ann_date=day)
                if not df.empty:
                    self.storage.insert_fundamental_data(df.dropna(how="all", axis=1), "forecast")
                return {"rows": int(len(df))}
            self._run_key(f"B:forecast:{day}", work_fc)

            def work_div(day=day):
                df = self.fetcher.fetch_dividend(ann_date=day)
                if not df.empty:
                    self.storage.insert_corporate_data(df.dropna(how="all", axis=1), "dividends")
                return {"rows": int(len(df))}
            self._run_key(f"B:dividends:{day}", work_div)

    # ---------- Stage C: stk_holdertrade year-file merge ----------
    def stage_c(self) -> None:
        out_path = os.path.join(PROJECT_ROOT, "data", "corporate", "stk_holdertrade", "stk_holdertrade_2026.parquet")

        def work():
            frames = []
            for lo, hi in weekly_chunks(self.start, self.end):
                df = self.fetcher.fetch_stk_holdertrade(start_date=lo, end_date=hi)
                if not df.empty:
                    frames.append(df)
                logger.info("  stk_holdertrade %s..%s: %d rows", lo, hi, len(df))
            if not frames:
                return {"rows": 0}
            new = pd.concat(frames, ignore_index=True)
            old = pd.read_parquet(out_path) if os.path.exists(out_path) else pd.DataFrame()
            before = len(old)
            # The bootstrap year file stores date columns as datetime64; the live API
            # returns YYYYMMDD strings — normalize the NEW side to the OLD file's
            # datetime64 convention (downstream ledger readers keep their dtype
            # contract; mixed object columns fail the parquet write — 2026-07-02).
            for col in ("ann_date", "in_date", "close_date", "begin_date", "end_date"):
                if col in new.columns and col in old.columns and pd.api.types.is_datetime64_any_dtype(old[col]):
                    new[col] = pd.to_datetime(new[col].astype(str), format="%Y%m%d", errors="coerce")
            merged = pd.concat([old, new], ignore_index=True).drop_duplicates()
            tmp = out_path + ".tmp"
            merged.to_parquet(tmp, index=False)
            os.replace(tmp, out_path)
            logger.info("  stk_holdertrade_2026.parquet: %d -> %d rows", before, len(merged))
            return {"rows_before": before, "rows_after": int(len(merged))}
        self._run_key("C:stk_holdertrade", work)

    # ---------- Stage D: cyq_perf per-symbol ----------
    def stage_d(self) -> None:
        cyq_root = os.path.join(PROJECT_ROOT, "data", "market", "cyq_perf")
        existing = []
        for year_dir in ("2026",):
            p = os.path.join(cyq_root, year_dir)
            if os.path.isdir(p):
                existing += [f[9:17] for f in os.listdir(p) if f.startswith("cyq_perf_")]
        last_covered = max(existing) if existing else "20260227"
        t_days = [d for d in trading_days(self.start, self.end) if d > last_covered]
        if not t_days:
            logger.info("cyq_perf already covered through %s", last_covered)
            return
        lo, hi = t_days[0], t_days[-1]
        logger.info("cyq_perf gap: %s..%s (%d trading days), per-symbol fetch", lo, hi, len(t_days))

        basic = pd.read_parquet(os.path.join(PROJECT_ROOT, "data", "reference", "stock_basic.parquet"))
        live = basic[basic["list_status"] == "L"]["ts_code"]
        dead = basic[(basic["list_status"] == "D") & (basic["delist_date"].fillna("99999999") >= lo)]["ts_code"]
        symbols = sorted(set(live) | set(dead))
        logger.info("cyq_perf symbols: %d (L=%d, recent-D=%d)", len(symbols), len(live), len(dead))

        buffer_key = "D:cyq_buffer"
        buf_dir = os.path.join(PROJECT_ROOT, "workspace", "outputs", "calendar_unfreeze", "cyq_buffer")
        os.makedirs(buf_dir, exist_ok=True)
        for i, code in enumerate(symbols, 1):
            def work(code=code):
                df = self.fetcher.fetch_cyq_perf(ts_code=code, start_date=lo, end_date=hi)
                if not df.empty:
                    df.to_parquet(os.path.join(buf_dir, f"{code.replace('.', '_')}.parquet"), index=False)
                return {"rows": int(len(df))}
            self._run_key(f"D:cyq:{code}", work)
            if i % 250 == 0:
                logger.info("PROGRESS cyq %d/%d symbols", i, len(symbols))

        def repartition():
            files = [os.path.join(buf_dir, f) for f in os.listdir(buf_dir)]
            if not files:
                return {"dates": 0}
            allf = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
            n_dates = 0
            for td, grp in allf.groupby("trade_date"):
                if not (lo <= str(td) <= hi):
                    continue
                year_dir = os.path.join(cyq_root, str(td)[:4])
                os.makedirs(year_dir, exist_ok=True)
                out = os.path.join(year_dir, f"cyq_perf_{td}.parquet")
                grp.reset_index(drop=True).to_parquet(out, index=False)
                n_dates += 1
            logger.info("cyq_perf repartitioned: %d daily files (%s..%s)", n_dates, lo, hi)
            return {"dates": n_dates}
        self._run_key("D:cyq_repartition", repartition)

    # ---------- Stage E: report_rc month-chunked merge ----------
    def stage_e(self) -> None:
        out_path = os.path.join(PROJECT_ROOT, "data", "analyst", "report_rc", "report_rc_2026.parquet")

        def work():
            frames = []
            for mo in (2, 3, 4, 5, 6):
                s = f"2026{mo:02d}01"
                e = f"2026{mo:02d}31" if mo != 6 else "20260630"
                df = self.fetcher._fetch_paginated(self.fetcher.pro.report_rc, limit=3000,
                                                   start_date=s, end_date=e)
                if not df.empty:
                    frames.append(df)
                logger.info("  report_rc 2026%02d: %d rows", mo, len(df))
            if not frames:
                return {"rows": 0}
            new = pd.concat(frames, ignore_index=True)
            old = pd.read_parquet(out_path) if os.path.exists(out_path) else pd.DataFrame()
            before = len(old)
            merged = pd.concat([old, new], ignore_index=True).drop_duplicates()
            tmp = out_path + ".tmp"
            merged.to_parquet(tmp, index=False)
            os.replace(tmp, out_path)
            logger.info("  report_rc_2026.parquet: %d -> %d rows", before, len(merged))
            return {"rows_before": before, "rows_after": int(len(merged))}
        self._run_key("E:report_rc", work)

    # ---------- Stage F: index_weights ----------
    TRACKED_INDICES = ["000001.SH", "000300.SH", "000905.SH", "000852.SH",
                       "399001.SZ", "399006.SZ", "000688.SH"]

    def stage_f(self) -> None:
        for month in ("202603", "202604", "202605", "202606"):
            for idx in self.TRACKED_INDICES:
                def work(month=month, idx=idx):
                    last_day = {"202603": "20260331", "202604": "20260430",
                                "202605": "20260531", "202606": "20260630"}[month]
                    df = self.fetcher.fetch_index_weight(index_code=idx,
                                                         start_date=month + "01", end_date=last_day)
                    if not df.empty:
                        self.storage.insert_universe_data(df, "index_weights")
                    logger.info("  index_weights %s %s: %d rows", month, idx, len(df))
                    return {"rows": int(len(df))}
                self._run_key(f"F:weights:{month}:{idx}", work)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calendar-unfreeze fundamentals/events catch-up")
    parser.add_argument("--start", default="20260228")
    parser.add_argument("--end", default="20260630")
    parser.add_argument("--stages", default="ABCDEF")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runner = Runner(args.start, args.end, args.dry_run)
    started = time.time()
    for stage in args.stages.upper():
        logger.info("===== STAGE %s =====", stage)
        getattr(runner, f"stage_{stage.lower()}")()
    logger.info("FUND CATCHUP %s in %.0f min, %d failed keys%s",
                "DRY-RUN" if args.dry_run else "COMPLETE", (time.time() - started) / 60,
                len(runner.failed), f" -> {runner.failed[:20]}" if runner.failed else "")
    if runner.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
