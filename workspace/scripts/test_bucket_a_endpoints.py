"""Preliminary schema/null/mode test for Bucket A endpoints (pre-download gate).

For each Bucket A endpoint, pull a representative slice IN ITS INTENDED BULK MODE
and report: query mode that returns all-market data, row count, pagination-cap
hit, column list, dtypes, and per-column null %. This validates the data pulls in
the desired format and tells the downloader whether bulk-by-period/date works or
per-stock iteration is required.

Read-only, strictly sequential. Writes only a JSON report to workspace/outputs/.
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
log = logging.getLogger("bucketA_test")

# Representative bulk-mode probes. Each entry: (label, mode_note, callable(pro)->df)
PERIOD = "20231231"
PERIOD_Q = "20230930"
FRIDAY = "20231229"   # a pledge weekly report date


def probes(pro):
    return [
        ("report_rc", "report_date range (1 month), paginated",
         lambda: pro.report_rc(start_date="20240401", end_date="20240430", limit=5000, offset=0)),
        ("express_vip", "all-stock by period",
         lambda: pro.express_vip(period=PERIOD)),
        ("express", "by period (non-vip)",
         lambda: pro.express(period=PERIOD)),
        ("disclosure_date", "all-stock by end_date(period)",
         lambda: pro.disclosure_date(end_date=PERIOD)),
        ("fina_audit", "all-stock by period (annual)",
         lambda: pro.fina_audit(period=PERIOD)),
        ("fina_mainbz_vip", "all-stock by period",
         lambda: pro.fina_mainbz_vip(period=PERIOD)),
        ("repurchase", "by ann_date range (1 quarter)",
         lambda: pro.repurchase(start_date="20240101", end_date="20240331", limit=2000, offset=0)),
        ("pledge_stat_byweek", "all-stock by end_date (weekly Friday)",
         lambda: pro.pledge_stat(end_date=FRIDAY)),
        ("pledge_stat_bystock", "single-stock fallback",
         lambda: pro.pledge_stat(ts_code="000001.SZ")),
        ("top10_floatholders_byperiod", "all-stock by period (no ts_code)",
         lambda: pro.top10_floatholders(period=PERIOD)),
        ("top10_floatholders_bystock", "single-stock fallback",
         lambda: pro.top10_floatholders(ts_code="000001.SZ", period=PERIOD)),
    ]


def summarize(df: pd.DataFrame, limit_for_cap=None):
    n = len(df)
    nulls = (df.isna().mean() * 100).round(1).to_dict()
    dtypes = {c: str(t) for c, t in df.dtypes.items()}
    cap_hit = (limit_for_cap is not None and n == limit_for_cap)
    return {
        "rows": int(n), "ncols": int(df.shape[1]),
        "cap_hit": bool(cap_hit),
        "columns": list(df.columns),
        "dtypes": dtypes,
        "null_pct": {k: float(v) for k, v in nulls.items()},
        "all_market": bool(df["ts_code"].nunique() > 1) if "ts_code" in df.columns else None,
        "unique_stocks": int(df["ts_code"].nunique()) if "ts_code" in df.columns else None,
    }


def main():
    pro = TushareFetcher(config_path=str(PROJECT_ROOT / "config.yaml")).pro
    out = {}
    for label, mode, fn in probes(pro):
        try:
            df = fn()
            if df is None:
                out[label] = {"mode": mode, "status": "NONE"}
            else:
                cap = 5000 if "report_rc" in label else (2000 if "repurchase" in label else None)
                s = summarize(df, cap)
                s["mode"] = mode
                s["status"] = "OK" if len(df) else "EMPTY"
                out[label] = s
            log.info("%-30s %-40s rows=%s stocks=%s cap=%s", label, mode,
                     out[label].get("rows"), out[label].get("unique_stocks"),
                     out[label].get("cap_hit"))
        except Exception as e:  # noqa: BLE001
            out[label] = {"mode": mode, "status": "ERR", "error": str(e)[:120]}
            log.info("%-30s ERR %s", label, str(e)[:120])
        time.sleep(1.4)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = PROJECT_ROOT / "workspace" / "outputs" / f"bucket_a_pretest_{stamp}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n==== BUCKET A PRELIMINARY TEST ====")
    for label, r in out.items():
        if r.get("status") != "OK":
            print(f"\n{label:30} [{r['status']}] {r.get('error','')}  ({r['mode']})")
            continue
        print(f"\n{label:30} rows={r['rows']} stocks={r['unique_stocks']} "
              f"cap_hit={r['cap_hit']} cols={r['ncols']}  ({r['mode']})")
        # show columns with high null% as the data-quality flag
        high_null = {k: v for k, v in r["null_pct"].items() if v >= 50}
        print(f"   cols: {', '.join(r['columns'])}")
        if high_null:
            print(f"   >=50% NULL: {high_null}")
    print("\nwrote", p)


if __name__ == "__main__":
    main()
