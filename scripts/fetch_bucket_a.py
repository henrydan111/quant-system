"""Bucket A historical bootstrap — Tushare 15000积分 data expansion.

Downloads the 8 deep-history "Bucket A" endpoints into the raw Parquet cache.
Modes/partitioning were verified by workspace/scripts/test_bucket_a_endpoints.py:

  report_rc          analyst forecasts   report_date range, month-chunked+paginated
                       -> data/analyst/report_rc/report_rc_{YYYY}.parquet
  express            preliminary earns   express_vip by quarterly period
                       -> data/fundamentals/express/express_{period}.parquet
  disclosure_date    report calendar     by quarterly end_date (all-market)
                       -> data/fundamentals/disclosure_date/disclosure_date_{period}.parquet
  fina_mainbz        segment revenue     fina_mainbz_vip by period, paginated (cap 10000)
                       -> data/fundamentals/fina_mainbz/fina_mainbz_{period}.parquet
  repurchase         buybacks            by ann_date year range, paginated (cap 2000+)
                       -> data/corporate/repurchase/repurchase_{YYYY}.parquet
  pledge_stat        share pledge        by weekly Friday end_date, paginated (HARD cap 3000)
                       -> data/corporate/pledge_stat/pledge_stat_{YYYY}.parquet
  top10_floatholders float ownership     by period, paginated (cap 6000)
                       -> data/corporate/top10_floatholders/top10_floatholders_{period}.parquet
  fina_audit         audit opinions      PER-STOCK (ts_code required), checkpointed
                       -> data/fundamentals/fina_audit/fina_audit.parquet

Safety: strictly sequential; every API call goes through TushareFetcher._safe_api_call
(rate-limit backoff + base_sleep). Idempotent — skips existing partition files unless
--force; fina_audit resumes from already-fetched ts_codes. --dry-run logs the files that
would be written and exits.

Usage:
    venv/Scripts/python.exe scripts/fetch_bucket_a.py --dry-run
    venv/Scripts/python.exe scripts/fetch_bucket_a.py                       # all 8
    venv/Scripts/python.exe scripts/fetch_bucket_a.py --endpoints report_rc express
    venv/Scripts/python.exe scripts/fetch_bucket_a.py --endpoints fina_audit
"""
from __future__ import annotations
import argparse, logging, sys, time
from datetime import datetime
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.data_infra.fetchers import TushareFetcher  # noqa: E402

DATA = PROJECT_ROOT / "data"
LOGS = PROJECT_ROOT / "logs"
STOCK_BASIC = DATA / "reference" / "stock_basic.parquet"

LOGS.mkdir(exist_ok=True)
_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler(LOGS / f"fetch_bucket_a_{_stamp}.log", encoding="utf-8")],
)
log = logging.getLogger("bucket_a")

ALL_ENDPOINTS = ["report_rc", "express", "disclosure_date", "fina_mainbz",
                 "repurchase", "pledge_stat", "top10_floatholders", "fina_audit"]
PAGE_LIMIT = 10000  # requested page size; server caps below this on capped endpoints


def quarter_ends(y0, y1):
    out = []
    for y in range(y0, y1 + 1):
        for md in ("0331", "0630", "0930", "1231"):
            out.append(f"{y}{md}")
    return out


def _paginate(fetcher, api_fn, **kw):
    """Cap-aware offset pagination: detect page size from page 1, stop on a short page."""
    frames, offset, first_n = [], 0, None
    while True:
        df = fetcher._safe_api_call(api_fn, limit=PAGE_LIMIT, offset=offset, **kw)
        n = 0 if df is None else len(df)
        if n == 0:
            break
        frames.append(df)
        if first_n is None:
            first_n = n
        offset += n
        if n < first_n:
            break
        if offset > 3_000_000:
            log.warning("pagination safety cap at offset=%d kw=%s — TRUNCATED", offset, kw)
            break
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ----------------------------------------------------------------------------- #
def _write(df, path, dry):
    if df is None or df.empty:
        return 0
    if dry:
        log.info("  [dry-run] would write %d rows -> %s", len(df), path.relative_to(PROJECT_ROOT))
        return len(df)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    log.info("  wrote %d rows -> %s", len(df), path.relative_to(PROJECT_ROOT))
    return len(df)


# Full report_rc schema + create_time (the vendor update timestamp — NOT in the
# default field set; required for the PIT availability anchor, see field_status).
REPORT_RC_FIELDS = ("ts_code,name,report_date,report_title,report_type,classify,org_name,"
                    "author_name,quarter,op_rt,op_pr,tp,np,eps,pe,rd,roe,ev_ebitda,rating,"
                    "max_price,min_price,create_time")


def fetch_report_rc(fetcher, force, dry):
    out_dir = DATA / "analyst" / "report_rc"
    for year in range(2010, 2027):
        f = out_dir / f"report_rc_{year}.parquet"
        if f.exists() and not force:
            log.info("report_rc %d: exists, skip", year); continue
        parts = []
        for mo in range(1, 13):
            s = f"{year}{mo:02d}01"
            e = (pd.Timestamp(f"{year}-{mo:02d}-01") + pd.offsets.MonthEnd(1)).strftime("%Y%m%d")
            dfm = _paginate(fetcher, fetcher.pro.report_rc, start_date=s, end_date=e,
                            fields=REPORT_RC_FIELDS)
            if len(dfm):
                parts.append(dfm)
            log.info("report_rc %s: +%d rows (cum %d)", f"{year}{mo:02d}", len(dfm),
                     sum(len(p) for p in parts))
        df = pd.concat(parts, ignore_index=True).drop_duplicates() if parts else pd.DataFrame()
        _write(df, f, dry)


def _fetch_by_period(fetcher, force, dry, *, api_attr, kwarg, out_dir, prefix, y0, y1, paginate):
    api = getattr(fetcher.pro, api_attr)
    for period in quarter_ends(y0, y1):
        f = out_dir / f"{prefix}_{period}.parquet"
        if f.exists() and not force:
            continue
        kw = {kwarg: period}
        df = _paginate(fetcher, api, **kw) if paginate else fetcher._safe_api_call(api, **kw)
        if df is not None and len(df):
            _write(df, f, dry)
        log.info("%s %s: %d rows", prefix, period, 0 if df is None else len(df))


def fetch_express(fetcher, force, dry):
    _fetch_by_period(fetcher, force, dry, api_attr="express_vip", kwarg="period",
                     out_dir=DATA / "fundamentals" / "express", prefix="express",
                     y0=2008, y1=2026, paginate=False)


def fetch_disclosure_date(fetcher, force, dry):
    _fetch_by_period(fetcher, force, dry, api_attr="disclosure_date", kwarg="end_date",
                     out_dir=DATA / "fundamentals" / "disclosure_date", prefix="disclosure_date",
                     y0=2008, y1=2026, paginate=False)


def fetch_fina_mainbz(fetcher, force, dry):
    _fetch_by_period(fetcher, force, dry, api_attr="fina_mainbz_vip", kwarg="period",
                     out_dir=DATA / "fundamentals" / "fina_mainbz", prefix="fina_mainbz",
                     y0=2010, y1=2026, paginate=True)


def fetch_top10_floatholders(fetcher, force, dry):
    _fetch_by_period(fetcher, force, dry, api_attr="top10_floatholders", kwarg="period",
                     out_dir=DATA / "corporate" / "top10_floatholders", prefix="top10_floatholders",
                     y0=2007, y1=2026, paginate=True)


def fetch_repurchase(fetcher, force, dry):
    out_dir = DATA / "corporate" / "repurchase"
    for year in range(2010, 2027):
        f = out_dir / f"repurchase_{year}.parquet"
        if f.exists() and not force:
            continue
        df = _paginate(fetcher, fetcher.pro.repurchase,
                       start_date=f"{year}0101", end_date=f"{year}1231")
        if len(df):
            _write(df, f, dry)
        log.info("repurchase %d: %d rows", year, len(df))


def fetch_pledge_stat(fetcher, force, dry):
    out_dir = DATA / "corporate" / "pledge_stat"
    for year in range(2014, 2027):
        f = out_dir / f"pledge_stat_{year}.parquet"
        if f.exists() and not force:
            log.info("pledge_stat %d: exists, skip", year); continue
        fridays = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="W-FRI").strftime("%Y%m%d")
        parts = []
        for fri in fridays:
            dfw = _paginate(fetcher, fetcher.pro.pledge_stat, end_date=fri)
            if len(dfw):
                parts.append(dfw)
        df = pd.concat(parts, ignore_index=True).drop_duplicates() if parts else pd.DataFrame()
        _write(df, f, dry)
        log.info("pledge_stat %d: %d rows from %d weeks", year, len(df), len(parts))


def fetch_fina_audit(fetcher, force, dry):
    out_dir = DATA / "fundamentals" / "fina_audit"
    f = out_dir / "fina_audit.parquet"
    sb = pd.read_parquet(STOCK_BASIC)
    codes = sorted(sb["ts_code"].dropna().astype(str).tolist())
    done, frames = set(), []
    if f.exists() and not force:
        prev = pd.read_parquet(f)
        frames.append(prev)
        done = set(prev["ts_code"].unique())
        log.info("fina_audit: resuming, %d/%d stocks already done", len(done), len(codes))
    if dry:
        log.info("  [dry-run] would fetch fina_audit for %d remaining stocks -> %s",
                 len(codes) - len(done), f.relative_to(PROJECT_ROOT))
        return
    todo = [c for c in codes if c not in done]
    for i, ts in enumerate(todo):
        df = fetcher._safe_api_call(fetcher.pro.fina_audit, ts_code=ts)
        if df is not None and len(df):
            frames.append(df)
        if i % 200 == 0:
            log.info("fina_audit: %d/%d (%s) cum_rows=%d", i, len(todo), ts,
                     sum(len(x) for x in frames))
        if i and i % 500 == 0:  # checkpoint
            out_dir.mkdir(parents=True, exist_ok=True)
            pd.concat(frames, ignore_index=True).drop_duplicates().to_parquet(f, index=False)
            log.info("fina_audit: checkpoint at %d stocks", i)
    if frames:
        out_dir.mkdir(parents=True, exist_ok=True)
        final = pd.concat(frames, ignore_index=True).drop_duplicates()
        final.to_parquet(f, index=False)
        log.info("fina_audit: DONE %d rows / %d stocks", len(final), final["ts_code"].nunique())


DISPATCH = {
    "report_rc": fetch_report_rc, "express": fetch_express,
    "disclosure_date": fetch_disclosure_date, "fina_mainbz": fetch_fina_mainbz,
    "repurchase": fetch_repurchase, "pledge_stat": fetch_pledge_stat,
    "top10_floatholders": fetch_top10_floatholders, "fina_audit": fetch_fina_audit,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoints", nargs="+", choices=ALL_ENDPOINTS, default=ALL_ENDPOINTS)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    log.info("=== Bucket A download: %s (force=%s dry_run=%s) ===",
             args.endpoints, args.force, args.dry_run)
    fetcher = TushareFetcher(config_path=str(PROJECT_ROOT / "config.yaml"))
    for ep in args.endpoints:
        log.info("---- %s ----", ep)
        t0 = time.time()
        DISPATCH[ep](fetcher, args.force, args.dry_run)
        log.info("---- %s done in %.1f min ----", ep, (time.time() - t0) / 60)
    log.info("=== Bucket A download complete ===")


if __name__ == "__main__":
    main()
