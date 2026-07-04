# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 1 fundamentals/events catch-up (UNFREEZE_PLAN.md Phase 1.4-1.5)
"""ann_date-window bulk catch-up for announcement-anchored datasets.

Contract: workspace/research/calendar_unfreeze/endpoint_contracts.yaml.
Fetches by ANN_DATE WINDOW (never by report period — a period-based fetch would
miss gap-period restatement announcements for older periods; plan Phase 1.4).

Stages (all resume-safe via a per-key JSON state file; strictly serial):
  A  weekly ann_date chunks : income income_quarterly balancesheet cashflow
                              cashflow_quarterly indicators holder_number
  B  per-day ann_date       : forecast dividends
  C  ann_date chunks->merge : stk_holdertrade (per-year file, ann_date-partitioned)
  D  per-symbol range       : cyq_perf (auto-detects last covered date)
  E  month chunks->merge    : report_rc (report_date query over [report-rc-start, report-rc-end],
                              per-year file; the monthly bump passes a pre-boundary TTL halo)
  F  monthly                : index_weights (months spanned by [start, end] x 7 indices)

Range-safety (Phase 5-B / GPT B3): this script is REUSED every monthly freeze-bump, so it must
be range- and year-safe. --state-suffix scopes the resume-state file (and the cyq buffer) per
bump so a new window is never skipped by a prior bump's "done" keys; range-scoped state keys and
per-year output files make a window crossing a year boundary (a report_rc halo reaches into the
prior year) correct. report_rc/index_weights month iteration derives from the window, not a
hardcoded 2026 span.

Usage:
    venv/Scripts/python.exe workspace/scripts/catchup_fundamentals_range.py \
        --start 20260228 --end 20260630 [--stages ABCDEF] [--dry-run] \
        [--report-rc-start YYYYMMDD] [--report-rc-end YYYYMMDD] [--state-suffix TAG]
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
OUT_DIR = os.path.join(PROJECT_ROOT, "workspace", "outputs", "calendar_unfreeze")


def state_path_for(suffix: str | None) -> str:
    """Resume-state file, scoped per bump by --state-suffix so a new window is never skipped by
    a prior bump's `done` keys. No suffix -> the original global file (the shipped Phase-1 run)."""
    name = "catchup_fund_state.json" if not suffix else f"catchup_fund_state_{suffix}.json"
    return os.path.join(OUT_DIR, name)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("catchup_fund")


def load_state(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


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


def months_spanned(start: str, end: str) -> list[str]:
    """['YYYYMM', ...] for every calendar month intersecting [start, end] (year-crossing safe)."""
    out, cur = [], datetime.strptime(start[:6] + "01", "%Y%m%d")
    stop = datetime.strptime(end, "%Y%m%d")
    while cur <= stop:
        out.append(cur.strftime("%Y%m"))
        y, m = cur.year, cur.month
        cur = datetime(y + (m // 12), (m % 12) + 1, 1)
    return out


def month_bounds(month: str, clip_start: str | None = None, clip_end: str | None = None) -> tuple[str, str]:
    """(lo, hi) YYYYMMDD for a 'YYYYMM'; optionally clipped to [clip_start, clip_end]."""
    y, m = int(month[:4]), int(month[4:6])
    full_lo = month + "01"
    full_hi = (datetime(y + (m // 12), (m % 12) + 1, 1) - timedelta(days=1)).strftime("%Y%m%d")
    lo = max(full_lo, clip_start) if clip_start else full_lo
    hi = min(full_hi, clip_end) if clip_end else full_hi
    return lo, hi


def trading_days(start: str, end: str) -> list[str]:
    cal = pd.read_parquet(os.path.join(PROJECT_ROOT, "data", "reference", "trade_cal.parquet"))
    days = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= start) & (cal["cal_date"] <= end)]
    return sorted(days["cal_date"].astype(str).tolist())


class Runner:
    def __init__(self, start: str, end: str, dry: bool, *, report_rc_start: str | None = None,
                 report_rc_end: str | None = None, state_suffix: str | None = None,
                 allow_empty_report_rc: bool = False):
        self.start, self.end, self.dry = start, end, dry
        # report_rc has its own window (the pre-boundary TTL halo); default to [start, end].
        self.report_rc_start = report_rc_start or start
        self.report_rc_end = report_rc_end or end
        self.suffix = state_suffix
        self.allow_empty_report_rc = allow_empty_report_rc
        self.state_path = state_path_for(state_suffix)
        self.state = load_state(self.state_path)
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
        save_state(self.state_path, self.state)

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

    # ---------- Stage C: stk_holdertrade per-year file merge ----------
    def stage_c(self) -> None:
        rc_dir = os.path.join(PROJECT_ROOT, "data", "corporate", "stk_holdertrade")

        def work():
            frames = []
            for lo, hi in weekly_chunks(self.start, self.end):
                df = self.fetcher.fetch_stk_holdertrade(start_date=lo, end_date=hi)
                if not df.empty:
                    frames.append(df)
                logger.info("  stk_holdertrade %s..%s: %d rows", lo, hi, len(df))
            if not frames:
                return {"rows": 0}
            new_all = pd.concat(frames, ignore_index=True)
            # partition new rows by ann_date year -> per-year file (year-crossing safe).
            yr = pd.to_datetime(new_all["ann_date"].astype(str), format="%Y%m%d", errors="coerce").dt.year
            before_t = after_t = 0
            for year, grp in new_all.groupby(yr):
                if pd.isna(year):
                    continue
                out_path = os.path.join(rc_dir, f"stk_holdertrade_{int(year)}.parquet")
                old = pd.read_parquet(out_path) if os.path.exists(out_path) else pd.DataFrame()
                before = len(old)
                grp = grp.copy()
                # The bootstrap year file stores date columns as datetime64; the live API
                # returns YYYYMMDD strings — normalize the NEW side to the OLD file's
                # datetime64 convention (mixed object columns fail the parquet write — 2026-07-02).
                for col in ("ann_date", "in_date", "close_date", "begin_date", "end_date"):
                    if col in grp.columns and col in old.columns and pd.api.types.is_datetime64_any_dtype(old[col]):
                        grp[col] = pd.to_datetime(grp[col].astype(str), format="%Y%m%d", errors="coerce")
                merged = pd.concat([old, grp], ignore_index=True).drop_duplicates()
                tmp = out_path + ".tmp"
                merged.to_parquet(tmp, index=False)
                os.replace(tmp, out_path)
                logger.info("  stk_holdertrade_%d.parquet: %d -> %d rows", int(year), before, len(merged))
                before_t += before
                after_t += len(merged)
            return {"rows_before": before_t, "rows_after": after_t}
        self._run_key(f"C:stk_holdertrade:{self.start}-{self.end}", work)

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

        # buffer dir scoped per bump (--state-suffix) so sequential bumps never mix partials.
        buf_name = "cyq_buffer" if not self.suffix else f"cyq_buffer_{self.suffix}"
        buf_dir = os.path.join(PROJECT_ROOT, "workspace", "outputs", "calendar_unfreeze", buf_name)
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

    # ---------- Stage E: report_rc month-chunked merge over the halo window ----------
    def stage_e(self) -> None:
        rc_start, rc_end = self.report_rc_start, self.report_rc_end

        def work():
            frames = []
            month_results = []
            # iterate the months spanned by [report_rc_start, report_rc_end] (the pre-boundary
            # TTL halo — reaches into the prior year on the first bump), clipping each end.
            for mo in months_spanned(rc_start, rc_end):
                s, e = month_bounds(mo, rc_start, rc_end)
                df = self.fetcher._fetch_paginated(self.fetcher.pro.report_rc, limit=3000,
                                                   start_date=s, end_date=e)
                month_results.append({"month": mo, "rows": int(len(df))})
                if not df.empty:
                    frames.append(df)
                logger.info("  report_rc %s..%s: %d rows", s, e, len(df))
            if not frames:
                # M2 fail-closed: an all-zero report_rc halo over a multi-month window is NOT
                # credible completeness (endpoint late/throttled/credential-or-schema-broken).
                # Only a verified-empty window may proceed, via the explicit manual/test flag.
                if self.allow_empty_report_rc:
                    logger.warning("report_rc halo %s..%s returned ZERO rows — ALLOWED by flag. months=%s",
                                   rc_start, rc_end, month_results)
                    return {"rows": 0, "month_results": month_results, "allowed_empty": True}
                raise RuntimeError(
                    f"report_rc halo replay returned ZERO rows over {rc_start}..{rc_end} — not "
                    f"credible for a monthly bump (endpoint late/throttled/broken). "
                    f"months={month_results}. Pass --allow-empty-report-rc only for a "
                    f"verified-empty window.")
            new = pd.concat(frames, ignore_index=True)
            # Phase 5 B2 (report_rc availability-boundary): stamp OUR first-ingestion time
            # so the PIT ledger can anchor a late-arriving fresh-window row (create_time
            # absent/backward) at its true first-seen floor + detect silent payload
            # revisions. First-seen semantics: dedupe on the vendor CONTENT (every column
            # except raw_fetch_ts — so a changed payload OR create_time is a distinct
            # revision keeping its own stamp) and keep the EARLIEST raw_fetch_ts. A
            # re-fetch of an already-seen content row never moves its stamp later.
            now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new["raw_fetch_ts"] = now_ts
            # partition by report_date year -> per-year file (a halo crossing a year boundary
            # writes report_rc_<prev>.parquet AND report_rc_<cur>.parquet correctly).
            yr = new["report_date"].astype(str).str[:4]
            before_t = after_t = 0
            for year, grp in new.groupby(yr):
                if not (isinstance(year, str) and year.isdigit() and len(year) == 4):
                    continue
                out_path = os.path.join(PROJECT_ROOT, "data", "analyst", "report_rc", f"report_rc_{year}.parquet")
                old = pd.read_parquet(out_path) if os.path.exists(out_path) else pd.DataFrame()
                before = len(old)
                combined = pd.concat([old, grp], ignore_index=True)
                content_cols = [c for c in combined.columns if c != "raw_fetch_ts"]
                # First-seen wins. A pre-instrumentation bootstrap row (year files <2026 have NO
                # raw_fetch_ts -> NaN after concat) was observed BEFORE we started stamping, i.e.
                # earliest possible -> NaN wins over a today re-fetch stamp; sort NaN FIRST,
                # keep="first" (two known stamps -> ascending -> earliest kept). Such a NaN row CAN
                # be fresh-affecting via TTL carry (its 120-open-day active interval reaches the
                # fresh window) — that is SAFE: the ledger quarantines a fresh-affecting row missing
                # BOTH create_time and raw_fetch_ts, and a CHANGED payload/create_time is a DISTINCT
                # content row keeping its own (today) stamp, not this identical-content branch.
                combined = (
                    combined.sort_values("raw_fetch_ts", kind="mergesort", na_position="first")
                    .drop_duplicates(subset=content_cols, keep="first")
                    .reset_index(drop=True)
                )
                tmp = out_path + ".tmp"
                combined.to_parquet(tmp, index=False)
                os.replace(tmp, out_path)
                logger.info("  report_rc_%s.parquet: %d -> %d rows (raw_fetch_ts stamped)", year, before, len(combined))
                before_t += before
                after_t += len(combined)
            return {"rows_before": before_t, "rows_after": after_t, "month_results": month_results}
        # range-scoped key: a new halo window is never masked by a prior bump's `done`.
        self._run_key(f"E:report_rc:{rc_start}-{rc_end}", work)

    # ---------- Stage F: index_weights ----------
    TRACKED_INDICES = ["000001.SH", "000300.SH", "000905.SH", "000852.SH",
                       "399001.SZ", "399006.SZ", "000688.SH"]

    def stage_f(self) -> None:
        # index_weights is a monthly snapshot -> fetch each FULL month spanned by [start, end]
        # (the key is already month-scoped, so re-running is idempotent per month/index).
        for month in months_spanned(self.start, self.end):
            lo, hi = month_bounds(month)  # full month bounds for the snapshot query
            for idx in self.TRACKED_INDICES:
                def work(month=month, idx=idx, lo=lo, hi=hi):
                    df = self.fetcher.fetch_index_weight(index_code=idx, start_date=lo, end_date=hi)
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
    parser.add_argument("--report-rc-start", default=None,
                        help="report_rc (Stage E) window start (YYYYMMDD); defaults to --start. "
                             "The monthly bump passes a pre-boundary TTL halo start.")
    parser.add_argument("--report-rc-end", default=None,
                        help="report_rc (Stage E) window end (YYYYMMDD); defaults to --end.")
    parser.add_argument("--state-suffix", default=None,
                        help="Scope the resume-state file + cyq buffer per bump so a new window "
                             "is not skipped by a prior bump's done keys.")
    parser.add_argument("--allow-empty-report-rc", action="store_true",
                        help="Permit an all-zero report_rc halo (Stage E) instead of failing "
                             "closed. Only for a VERIFIED-empty window — not the default path.")
    args = parser.parse_args()

    runner = Runner(args.start, args.end, args.dry_run, report_rc_start=args.report_rc_start,
                    report_rc_end=args.report_rc_end, state_suffix=args.state_suffix,
                    allow_empty_report_rc=args.allow_empty_report_rc)
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
