"""report_rc PIT backfill canary (cross-review Q-D1a).

`report_rc` exposes only `report_date` (analyst publication date) — no separate
"row-entered-DB" timestamp. The PIT-breaking failure mode: a report dated T is
ingested into Tushare only AFTER T, so anchoring on report_date would let a
backtest "see" a report before it was actually retrievable. A single snapshot
cannot detect this; it needs two snapshots separated in wall-clock time.

This script:
  * `snapshot` (default): pull report_rc for the trailing window, content-hash
    every row, write a versioned snapshot under data/external/report_rc_canary/,
    and record an ingestion-lag observation (today - max(report_date)).
  * `diff OLD NEW`: compare two snapshots and report the three smoking guns —
      (1) BACKFILLED rows: appear only in NEW but carry a report_date <= OLD's
          max report_date (i.e. an old-dated row that was not retrievable at the
          OLD snapshot time)  <-- the decisive PIT-violation signal
      (2) report_date DRIFT: same logical report, different report_date
      (3) payload RESTATEMENT: same row identity, changed eps/np/tp/rating/...

Re-run `snapshot` periodically (>= weekly); then `diff` the newest two. Strictly
sequential, read-only against Tushare; writes only canary snapshots.

Usage:
    venv/Scripts/python.exe scripts/report_rc_backfill_canary.py snapshot
    venv/Scripts/python.exe scripts/report_rc_backfill_canary.py snapshot --lookback-days 120
    venv/Scripts/python.exe scripts/report_rc_backfill_canary.py diff <old.parquet> <new.parquet>
"""
from __future__ import annotations
import argparse, hashlib, json, logging, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.data_infra.fetchers import TushareFetcher  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rc_canary")

STORE = PROJECT_ROOT / "data" / "external" / "report_rc_canary"
PAGE = 5000  # hard per-call cap
ID_COLS = ["ts_code", "report_date", "org_name", "author_name", "quarter", "report_title"]
LK_COLS = ["ts_code", "org_name", "author_name", "quarter", "report_title"]  # logical key sans date
PAYLOAD = ["op_rt", "op_pr", "tp", "np", "eps", "pe", "rd", "roe", "ev_ebitda",
           "rating", "max_price", "min_price"]


def _hash_row(vals) -> str:
    return hashlib.sha1("|".join("" if v is None else str(v) for v in vals).encode()).hexdigest()[:16]


def _paginate(pro, start, end):
    """Month-chunk + offset pagination with dedup-stop (the 5000-cap-safe path)."""
    months, cur = [], datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    while cur <= end_dt:
        nxt = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        months.append((cur.strftime("%Y%m%d"), min(nxt - timedelta(days=1), end_dt).strftime("%Y%m%d")))
        cur = nxt
    frames, seen = [], set()
    for s, e in months:
        offset = 0
        while True:
            df = pro.report_rc(start_date=s, end_date=e, limit=PAGE, offset=offset)
            n = 0 if df is None else len(df)
            if not n:
                break
            keys = pd.util.hash_pandas_object(df, index=False).values
            mask = ~pd.Series(keys).isin(seen).values
            new = df[mask]
            if new.empty:
                break
            seen.update(keys[mask].tolist())
            frames.append(new)
            offset += n
            time.sleep(1.3)
            if n < PAGE:
                break
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _add_hashes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ID_COLS + PAYLOAD:
        if c not in df.columns:
            df[c] = None
    df["row_id"] = [_hash_row(v) for v in df[ID_COLS].itertuples(index=False, name=None)]
    df["payload_hash"] = [_hash_row(v) for v in df[PAYLOAD].itertuples(index=False, name=None)]
    df["lk"] = [_hash_row(v) for v in df[LK_COLS].itertuples(index=False, name=None)]
    return df


def cmd_snapshot(args):
    STORE.mkdir(parents=True, exist_ok=True)
    today = datetime.now()
    start = (today - timedelta(days=args.lookback_days)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    log.info("snapshot window %s .. %s", start, end)
    pro = TushareFetcher(config_path=str(PROJECT_ROOT / "config.yaml")).pro
    df = _add_hashes(_paginate(pro, start, end))
    if df.empty:
        log.error("empty pull — aborting"); return 1

    rd_max = str(df["report_date"].max())
    rd_min = str(df["report_date"].min())
    lag = (today - datetime.strptime(rd_max, "%Y%m%d")).days
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = STORE / f"snapshot_{stamp}.parquet"
    df.to_parquet(out, index=False)

    man_path = STORE / "manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {"snapshots": []}
    man["snapshots"].append({
        "stamp": stamp, "file": out.name, "window_start": start, "window_end": end,
        "rows": int(len(df)), "unique_stocks": int(df["ts_code"].nunique()),
        "report_date_min": rd_min, "report_date_max": rd_max,
        "ingestion_lag_days_at_snapshot": int(lag),
    })
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nSNAPSHOT {stamp}")
    print(f"  rows={len(df)}  unique_stocks={df['ts_code'].nunique()}")
    print(f"  report_date span {rd_min} .. {rd_max}")
    print(f"  INGESTION-LAG observation: today={end}, freshest report_date={rd_max} -> {lag} days")
    print(f"  wrote {out}")
    if len(man["snapshots"]) >= 2:
        prev = man["snapshots"][-2]["file"]
        print(f"\n  >> ready to diff: scripts/report_rc_backfill_canary.py diff "
              f"data/external/report_rc_canary/{prev} data/external/report_rc_canary/{out.name}")
    else:
        print("\n  (baseline captured — re-run >=1 week later, then `diff` the two snapshots)")
    return 0


def _run_diff(old_path, new_path):
    old = pd.read_parquet(old_path)
    new = pd.read_parquet(new_path)
    old_rd_max = str(old["report_date"].max())

    old_ids, new_ids = set(old["row_id"]), set(new["row_id"])
    # (1) BACKFILL: in NEW, not in OLD, with report_date <= OLD's max (old-dated, late-arriving)
    new_only = new[~new["row_id"].isin(old_ids)]
    backfilled = new_only[new_only["report_date"].astype(str) <= old_rd_max]
    # (2) report_date DRIFT: same logical key, different report_date
    om = old.groupby("lk")["report_date"].agg(lambda s: set(map(str, s)))
    nm = new.groupby("lk")["report_date"].agg(lambda s: set(map(str, s)))
    drift = [lk for lk in om.index.intersection(nm.index) if not nm[lk].issuperset(om[lk])]
    # (3) payload RESTATEMENT: same row_id, changed payload_hash
    j = old[["row_id", "payload_hash"]].merge(
        new[["row_id", "payload_hash"]], on="row_id", suffixes=("_old", "_new"))
    restated = j[j["payload_hash_old"] != j["payload_hash_new"]]
    disappeared = old[~old["row_id"].isin(new_ids)]

    print(f"\nDIFF  old={Path(old_path).name}  new={Path(new_path).name}")
    print(f"  old rows={len(old)} (report_date<= {old_rd_max})   new rows={len(new)}")
    print(f"  (1) BACKFILLED old-dated rows (PIT smoking gun): {len(backfilled)}")
    if len(backfilled):
        print(backfilled[["ts_code", "report_date", "org_name", "quarter"]].head(10).to_string(index=False))
    print(f"  (2) report_date DRIFT (logical reports w/ changed date): {len(drift)}")
    print(f"  (3) payload RESTATEMENT (same row, changed values): {len(restated)}")
    print(f"  (info) rows in OLD now absent from NEW: {len(disappeared)}")
    verdict = "PIT-CLEAN (anchor on report_date is safe)" if (len(backfilled) == 0 and len(drift) == 0) \
        else "PIT-RISK DETECTED — report_date is NOT a safe visibility anchor; add ingestion-lag buffer"
    print(f"\n  VERDICT: {verdict}")
    return 0


def cmd_diff(args):
    return _run_diff(args.old, args.new)


def _two_newest():
    man_path = STORE / "manifest.json"
    if not man_path.exists():
        return None
    snaps = json.loads(man_path.read_text(encoding="utf-8")).get("snapshots", [])
    if len(snaps) < 2:
        return None
    return STORE / snaps[-2]["file"], STORE / snaps[-1]["file"]


def cmd_recheck(args):
    """Unattended weekly path: snapshot, then auto-diff the two newest snapshots."""
    rc = cmd_snapshot(args)
    if rc:
        return rc
    pair = _two_newest()
    if pair is None:
        print("\n(only one snapshot exists — re-run `recheck` next week to get the first diff)")
        return 0
    return _run_diff(pair[0], pair[1])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("snapshot"); sp.add_argument("--lookback-days", type=int, default=120)
    dp = sub.add_parser("diff"); dp.add_argument("old"); dp.add_argument("new")
    rp = sub.add_parser("recheck"); rp.add_argument("--lookback-days", type=int, default=120)
    args = ap.parse_args()
    dispatch = {"snapshot": cmd_snapshot, "diff": cmd_diff, "recheck": cmd_recheck}
    sys.exit(dispatch[args.cmd](args))


if __name__ == "__main__":
    main()
