"""One-time migration: convert the existing
``Knowledge/zxz_399101_pit_membership_tuesdays.csv`` (the manual JoinQuant
export from the P1 G5_A2 investigation) into the new PIT cache layout at
``data/external/jq_pit_cache/index_members/399101.XSHE/{YYYY}.parquet``.

After migration, the JoinQuantPITLoader can serve 399101.XSHE membership
without referencing the workspace-local CSV.
"""

from pathlib import Path

import pandas as pd

P = Path(r"E:/量化系统")
SRC = P / "Knowledge/zxz_399101_pit_membership_tuesdays.csv"
DST_DIR = P / "data/external/jq_pit_cache/index_members/399101.XSHE"

df = pd.read_csv(SRC)
df["date"] = pd.to_datetime(df["date"]).dt.normalize()
# Convert JoinQuant codes to Tushare format
df["ts_code"] = (
    df["ts_code"]
    .str.replace(".XSHE", ".SZ", regex=False)
    .str.replace(".XSHG", ".SH", regex=False)
)
df = df[["date", "ts_code"]].sort_values(["date", "ts_code"]).reset_index(drop=True)

DST_DIR.mkdir(parents=True, exist_ok=True)
n_total = 0
for year, g in df.groupby(df["date"].dt.year):
    out = DST_DIR / f"{year}.parquet"
    g.reset_index(drop=True).to_parquet(out, index=False)
    n_total += len(g)
    print(f"  {out.relative_to(P)}: {len(g):>7,} rows ({g['date'].nunique()} snapshots)")

print(f"\nTotal: {n_total:,} rows over {df['date'].nunique()} Tuesday snapshots.")
print(f"Date range: {df['date'].min().date()} → {df['date'].max().date()}.")
