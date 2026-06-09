"""One-off: verify the report_rc vendor-backfill PIT finding from the RAW download.

Checks, per report_date-year file under data/analyst/report_rc/:
  - whether a create_time column exists (the actual row-ingestion timestamp)
  - the span of create_time
  - the fraction of rows whose create_time falls on the 2022-05-02/03 bulk-backfill days

A report_date back to 2010 with create_time pinned to 2022-05 is the vendor-backfill
lookahead signature: dated old, but not actually retrievable until 2022-05.
"""
from __future__ import annotations
import os
import pandas as pd

D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "data", "analyst", "report_rc")

f2015 = os.path.join(D, "report_rc_2015.parquet")
cols = list(pd.read_parquet(f2015).columns)
print("COLUMNS (2015 file):", cols)
print("has create_time:", "create_time" in cols)
print()

for yr in range(2010, 2027):
    fp = os.path.join(D, f"report_rc_{yr}.parquet")
    if not os.path.exists(fp):
        continue
    df = pd.read_parquet(fp)
    line = f"report_date year={yr}: rows={len(df):>7}"
    if "create_time" in df.columns:
        ct = pd.to_datetime(df["create_time"], errors="coerce")
        ctd = ct.dt.normalize()
        backfill = ctd.isin([pd.Timestamp("2022-05-02"), pd.Timestamp("2022-05-03")]).mean()
        line += (f" | create_time {ct.min()} .. {ct.max()}"
                 f" | %on 2022-05-02/03 = {backfill * 100:5.1f}%"
                 f" | %create_time year==report year = "
                 f"{(ct.dt.year == yr).mean() * 100:5.1f}%")
    else:
        line += " | NO create_time column"
    print(line)
