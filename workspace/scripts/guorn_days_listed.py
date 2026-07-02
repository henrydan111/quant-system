"""T1 local reproduction — 上市天数 (days since listing) at a signal date, from
data/reference/stock_basic.parquet (list_date, YYYYMMDD). Emits a code(6-digit)+value parquet for
guorn_factor_parity.py --local-series. Produces BOTH calendar-day and trading-day variants (果仁's caliber
is unverified until the 果仁 export exists — test both). NON-FORMAL parity tooling.

  python workspace/scripts/guorn_days_listed.py --date 2025-12-31
    -> workspace/outputs/guorn_derived/days_listed_cal_20251231.parquet   (calendar days)
       workspace/outputs/guorn_derived/days_listed_trd_20251231.parquet   (trading days)
"""
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="选股日期 YYYY-MM-DD")
    ap.add_argument("--outdir", default=str(ROOT / "workspace" / "outputs" / "guorn_derived"))
    a = ap.parse_args()
    d = pd.Timestamp(a.date)
    tag = a.date.replace("-", "")
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    sb = pd.read_parquet(ROOT / "data" / "reference" / "stock_basic.parquet")
    sb = sb[["ts_code", "list_date", "list_status", "delist_date"]].copy()
    sb["code"] = sb["ts_code"].str.split(".").str[0]
    sb["ld"] = pd.to_datetime(sb["list_date"].astype(str), format="%Y%m%d", errors="coerce")
    sb = sb.dropna(subset=["ld"])
    sb = sb[sb["ld"] <= d]  # listed on/before the signal date

    # calendar days since listing — INCLUSIVE of the listing day (果仁 caliber: a stock listed on the signal
    # date is 上市天数=1, not 0). Proven against the 2025-12-31 排除ST排除科创 export: elapsed-days = 果仁−1 for
    # ALL 4412 names (std=0), so +1 lands value-exact. The trading-day branch below is already inclusive.
    sb["cal"] = (d - sb["ld"]).dt.days + 1

    # trading days since listing (from the provider calendar, inclusive of both ends <= d)
    cal_days = pd.to_datetime([l.strip() for l in open(ROOT / "data" / "qlib_data" / "calendars" / "day.txt")])
    cal_le_d = cal_days[cal_days <= d].sort_values()
    pos = cal_le_d.searchsorted(sb["ld"].values, side="left")  # index of first trading day >= ld
    sb["trd"] = len(cal_le_d) - pos  # trading days from ld..d inclusive

    for kind, col in (("cal", "cal"), ("trd", "trd")):
        out = outdir / f"days_listed_{kind}_{tag}.parquet"
        sb.rename(columns={col: "value"})[["code", "value"]].to_parquet(out, index=False)
        print(f"[{kind}] wrote {len(sb)} codes -> {out}")
    print("\ncalendar-day 上市天数 describe:")
    print(sb["cal"].describe().to_string())
    print("\ntrading-day 上市天数 describe:")
    print(sb["trd"].describe().to_string())
    print("\nsample (600519 / 000001 / a recent IPO):")
    print(sb[sb["code"].isin(["600519", "000001"])][["code", "ld", "cal", "trd"]].to_string(index=False))


if __name__ == "__main__":
    main()
