"""Min/max date-span probe for Wave-1/4 fundamental & event endpoints.

Single call per endpoint for a heavily-covered stock (Moutai), reporting the
span of the primary disclosure-date column + row count. Resolves whether the
surviving (deep-history) endpoints actually cover IS 2014-2020 / OOS 2021-2026,
and disambiguates sparse-event endpoints that a single-day probe under-counts.
"""
from __future__ import annotations
import json, logging, sys, time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.data_infra.fetchers import TushareFetcher  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("depth")
S = "600519.SH"

# (endpoint, kwargs, date_column candidates)
PROBES = [
    ("express",         {"ts_code": S}, ["ann_date", "end_date"]),
    ("fina_mainbz",     {"ts_code": S}, ["end_date"]),
    ("fina_audit",      {"ts_code": S}, ["ann_date", "end_date"]),
    ("disclosure_date", {"ts_code": S}, ["ann_date", "end_date"]),
    ("share_float",     {"ts_code": S}, ["ann_date", "float_date"]),
    ("pledge_stat",     {"ts_code": S}, ["end_date"]),
    ("stk_surv",        {"ts_code": S}, ["surv_date"]),
    ("top10_floatholders", {"ts_code": S}, ["end_date", "ann_date"]),
]


def main():
    pro = TushareFetcher(config_path=str(PROJECT_ROOT / "config.yaml")).pro
    res = {}
    for name, kw, datecols in PROBES:
        try:
            df = getattr(pro, name)(**kw)
            n = 0 if df is None else len(df)
            span = None
            if df is not None and n:
                for c in datecols:
                    if c in df.columns:
                        col = df[c].dropna().astype(str)
                        if len(col):
                            span = f"{c}: {col.min()} .. {col.max()}"
                            break
            res[name] = {"rows": n, "span": span}
            log.info("%-18s rows=%-5s %s", name, n, span)
        except Exception as e:  # noqa: BLE001
            res[name] = {"rows": "ERR", "span": str(e)[:80]}
            log.info("%-18s ERR %s", name, str(e)[:80])
        time.sleep(1.3)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = PROJECT_ROOT / "workspace" / "outputs" / f"tushare_depth_probe_{stamp}.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n==== DEPTH (Moutai full history) ====")
    for k, v in res.items():
        print(f"{k:18} rows={v['rows']:<6} {v['span']}")
    print("wrote", p)


if __name__ == "__main__":
    main()
