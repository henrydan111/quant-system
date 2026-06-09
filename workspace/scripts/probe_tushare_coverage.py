"""History-depth probe for the flagship expansion endpoints (read-only, sequential).

The access probe proved callability on ONE date. This answers the next question:
does each flagship endpoint actually cover the research window (IS 2014-2020 /
OOS 2021-2026)? Probes representative dates/years and reports row counts so we
state verified coverage in the cross-review rather than assume it.

Strictly sequential, single calls, base_sleep respected. Touches no data/.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.data_infra.fetchers import TushareFetcher  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cov")
OUT = PROJECT_ROOT / "workspace" / "outputs"

# representative trading days (verified open days near year-start)
YEAR_DATES = {
    "2010": "20100104", "2012": "20120104", "2014": "20140102",
    "2016": "20160104", "2018": "20180102", "2020": "20200102",
    "2022": "20220104", "2024": "20240102", "2025": "20250102",
}
HEAVY_STOCK = "600519.SH"  # Moutai — maximal analyst coverage


def call(pro, name, **kw):
    fn = getattr(pro, name)
    for attempt in range(2):
        try:
            df = fn(**kw)
            return 0 if df is None else len(df)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "每分钟" in msg or "frequent" in msg.lower() or "每天" in msg:
                if attempt == 0:
                    time.sleep(20); continue
            return f"ERR:{msg[:60]}"
    return "ERR:exhausted"


def per_date(pro, name, **extra):
    out = {}
    for y, d in YEAR_DATES.items():
        out[y] = call(pro, name, trade_date=d, **extra)
        log.info("%-16s %s -> %s", name, y, out[y])
        time.sleep(1.3)
    return out


def per_year_range(pro, name, **base):
    """For per-stock endpoints that take start_date/end_date by ann/report date."""
    out = {}
    for y in YEAR_DATES:
        out[y] = call(pro, name, start_date=f"{y}0101", end_date=f"{y}1231", **base)
        log.info("%-16s %s -> %s", name, y, out[y])
        time.sleep(1.3)
    return out


def main():
    pro = TushareFetcher(config_path=str(PROJECT_ROOT / "config.yaml")).pro
    res = {}

    log.info("== report_rc (analyst, per-stock by report_date range, %s) ==", HEAVY_STOCK)
    res["report_rc"] = per_year_range(pro, "report_rc", ts_code=HEAVY_STOCK)

    log.info("== limit_list_d (打板 board, per-date) ==")
    res["limit_list_d"] = per_date(pro, "limit_list_d")

    log.info("== moneyflow_dc (2nd flow vendor, per-date) ==")
    res["moneyflow_dc"] = per_date(pro, "moneyflow_dc")

    log.info("== dc_member (东财 concept membership, per-date) ==")
    res["dc_member"] = per_date(pro, "dc_member")

    log.info("== stk_surv (institutional surveys, per-date) ==")
    res["stk_surv"] = per_date(pro, "stk_surv")

    log.info("== hm_detail (游资, per-date) ==")
    res["hm_detail"] = per_date(pro, "hm_detail")

    log.info("== repurchase (buybacks, per-year by ann_date) ==")
    res["repurchase"] = per_year_range(pro, "repurchase")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = OUT / f"tushare_coverage_probe_{stamp}.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n==== COVERAGE (row counts by year) ====")
    for ep, d in res.items():
        print(f"{ep:16} " + "  ".join(f"{y}:{v}" for y, v in d.items()))
    print("\nwrote", p)


if __name__ == "__main__":
    main()
