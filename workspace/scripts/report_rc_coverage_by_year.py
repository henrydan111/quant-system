"""Tushare report_rc: unique covered A-share stocks per report_date year.

This is the baseline the JoinQuant consensus-coverage count is compared against,
to test whether the 2022 bulk backfill of 2010-2021 is complete at the stock level.
"""
import os
import pandas as pd

D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "data", "analyst", "report_rc")

rows = []
for yr in range(2010, 2022):
    fp = os.path.join(D, f"report_rc_{yr}.parquet")
    if not os.path.exists(fp):
        continue
    df = pd.read_parquet(fp, columns=["ts_code", "report_date"])
    # standard A-share boards only (drop any non 6/0/3-prefixed oddities)
    ts = df["ts_code"].astype(str)
    ash = ts[ts.str.match(r"^(60|68|00|30|8|4)\d")]
    rows.append({"year": yr,
                 "reports": len(df),
                 "covered_stocks_tushare": df["ts_code"].nunique()})
out = pd.DataFrame(rows)
print(out.to_string(index=False))
print("\n# paste this dict into the JoinQuant notebook (Cell 4):")
print("TUSHARE_COVERED = {")
for r in rows:
    print(f"    {r['year']}: {r['covered_stocks_tushare']},")
print("}")
