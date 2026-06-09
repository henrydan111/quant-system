"""All-market report_rc coverage probe (GPT cross-review Finding 1).

The Moutai-only depth probe proved history EXISTS; it did not prove coverage is
broad, retains delisted names (survivorship), or is stable across the universe.
This probes the full A-share universe by report_date year:
  - breadth: unique covered stocks / total listed that year
  - survivorship: are stocks that have SINCE delisted present in old years?
  - cap-bucket coverage: % covered within total_mv quintiles
  - pagination behavior: effective per-call cap + total rows

Read-only, strictly sequential. Uses local stock_basic + live daily_basic
(one date/yr) for the size buckets; no data/ writes.
"""
from __future__ import annotations
import json, logging, sys, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.data_infra.fetchers import TushareFetcher  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rc_univ")

YEARS = ["2014", "2018", "2022", "2024"]
FIRST_TD = {"2014": "20140102", "2018": "20180102", "2022": "20220104", "2024": "20240102"}
PAGE = 5000          # observed hard per-call cap is 5000
MAX_PAGES = 30       # per-chunk safety bound
SLEEP = 1.3
MONTHS = [f"{m:02d}" for m in range(1, 13)]
_MONTH_END = {"01": "31", "02": "28", "03": "31", "04": "30", "05": "31", "06": "30",
              "07": "31", "08": "31", "09": "30", "10": "31", "11": "30", "12": "31"}


def _paginate_window(pro, start, end):
    """Offset-paginate one date window with a dedup-stop (detects ignored offset)."""
    frames, offset, seen, offset_works = [], 0, set(), False
    for _ in range(MAX_PAGES):
        df = pro.report_rc(start_date=start, end_date=end, limit=PAGE, offset=offset)
        n = 0 if df is None else len(df)
        if not n:
            break
        # row identity to detect an ignored-offset duplicate page
        key = pd.util.hash_pandas_object(df, index=False)
        new = df.loc[~pd.Series(key.values, index=df.index).isin(seen)]
        if new.empty:
            break  # offset ignored or no new rows
        if offset > 0:
            offset_works = True
        seen.update(key.values.tolist())
        frames.append(new)
        offset += n
        time.sleep(SLEEP)
        if n < PAGE:
            break
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return out, offset_works


def paginate_year(pro, year):
    """Month-chunk the year so no single window exceeds the 5000 cap unnoticed."""
    parts, any_offset = [], False
    capped_months = []
    for mo in MONTHS:
        s, e = f"{year}{mo}01", f"{year}{mo}{_MONTH_END[mo]}"
        dfm, ow = _paginate_window(pro, s, e)
        any_offset = any_offset or ow
        if len(dfm) >= PAGE and not ow:
            capped_months.append(mo)  # month hit cap but offset didn't advance -> under-count
        if len(dfm):
            parts.append(dfm)
    out = pd.concat(parts, ignore_index=True).drop_duplicates() if parts else pd.DataFrame()
    return out, {"offset_works": any_offset, "capped_under_months": capped_months}


def main():
    fetcher = TushareFetcher(config_path=str(PROJECT_ROOT / "config.yaml"))
    pro = fetcher.pro

    sb = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet")
    delisted = set(sb.loc[sb["delist_date"].notna(), "ts_code"]) if "delist_date" in sb else set()
    log.info("stock_basic: %d rows, %d ever-delisted", len(sb), len(delisted))

    res = {}
    for y in YEARS:
        df, pmeta = paginate_year(pro, y)
        rows = len(df)
        codes = set(df["ts_code"].unique()) if rows else set()
        n_delisted = len(codes & delisted)

        # size buckets from live daily_basic on the year's first trading day
        buckets = {}
        try:
            db = pro.daily_basic(trade_date=FIRST_TD[y], fields="ts_code,total_mv")
            time.sleep(SLEEP)
            db = db[db["total_mv"].notna()].copy()
            db["q"] = pd.qcut(db["total_mv"].rank(method="first"), 5,
                              labels=["Q1_small", "Q2", "Q3", "Q4", "Q5_large"])
            for q, grp in db.groupby("q", observed=True):
                u = set(grp["ts_code"])
                buckets[str(q)] = {
                    "listed": len(u),
                    "covered": len(u & codes),
                    "pct": round(100 * len(u & codes) / max(1, len(u)), 1),
                }
            listed_that_day = len(db)
        except Exception as e:  # noqa: BLE001
            buckets = {"ERR": str(e)[:80]}
            listed_that_day = None

        res[y] = {
            "rows": rows, "unique_stocks": len(codes),
            "offset_works": pmeta["offset_works"],
            "capped_under_months": pmeta["capped_under_months"],
            "listed_on_first_td": listed_that_day,
            "breadth_pct": (round(100 * len(codes) / listed_that_day, 1)
                            if listed_that_day else None),
            "covered_delisted_stocks": n_delisted,
            "size_buckets": buckets,
        }
        log.info("year %s: rows=%d unique=%d breadth=%s%% delisted_present=%d offset_works=%s under=%s",
                 y, rows, len(codes), res[y]["breadth_pct"], n_delisted,
                 pmeta["offset_works"], pmeta["capped_under_months"])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = PROJECT_ROOT / "workspace" / "outputs" / f"report_rc_universe_{stamp}.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n==== report_rc ALL-MARKET COVERAGE (month-chunked) ====")
    for y, d in res.items():
        print(f"{y}: rows={d['rows']:>6} unique={d['unique_stocks']:>4} "
              f"breadth={d['breadth_pct']}%  delisted_present={d['covered_delisted_stocks']} "
              f"offset_works={d['offset_works']} capped_months={d['capped_under_months']}")
        for q, b in d["size_buckets"].items():
            if isinstance(b, dict) and "pct" in b:
                print(f"      {q:9} {b['covered']}/{b['listed']} = {b['pct']}%")
    print("wrote", p)


if __name__ == "__main__":
    main()
