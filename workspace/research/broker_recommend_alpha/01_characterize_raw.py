"""Characterize the raw broker_recommend (券商金股) ingest before building the signal.

Verifies the 72-month backfill landed correctly and surfaces the data-quality
facts the signal design must handle: ts_code format, per-month broker zigzag,
conviction distribution, duplicates/nulls, stock coverage.

Read-only over data/analyst/broker_recommend/; writes a combined parquet +
a per-month summary to workspace/outputs/broker_recommend_alpha/.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "analyst" / "broker_recommend"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "broker_recommend_alpha"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    files = sorted(RAW_DIR.glob("broker_recommend_*.parquet"))
    if not files:
        print(f"NO FILES under {RAW_DIR}")
        return 1

    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df["month"] = df["month"].astype(str)

    print(f"files={len(files)}  total_rows={len(df)}  cols={list(df.columns)}")
    print(f"month range: {df['month'].min()} .. {df['month'].max()}  (n_months={df['month'].nunique()})")
    print(f"distinct ts_code (ever): {df['ts_code'].nunique()}")
    print(f"distinct broker (ever) : {df['broker'].nunique()}")
    print(f"ts_code samples: {sorted(df['ts_code'].dropna().unique())[:5]}")
    print(f"nulls: ts_code={df['ts_code'].isna().sum()} broker={df['broker'].isna().sum()} name={df['name'].isna().sum()}")

    # Duplicates: same broker picking same stock twice in a month?
    dup = df.duplicated(subset=["month", "broker", "ts_code"]).sum()
    print(f"dup (month,broker,ts_code) rows: {dup}")

    # Conviction: per (month, ts_code) distinct brokers
    conv = (
        df.groupby(["month", "ts_code"])["broker"]
        .nunique()
        .rename("n_brokers")
        .reset_index()
    )
    print(f"\nconviction (n_brokers per stock-month): "
          f"mean={conv['n_brokers'].mean():.2f} max={conv['n_brokers'].max()} "
          f"p99={conv['n_brokers'].quantile(0.99):.0f}")
    print("conviction value counts (how many stock-months at each broker-count):")
    print(conv["n_brokers"].value_counts().sort_index().to_string())

    # Per-month summary — the zigzag
    per_month = (
        df.groupby("month")
        .agg(n_rows=("ts_code", "size"),
             n_brokers=("broker", "nunique"),
             n_codes=("ts_code", "nunique"))
        .reset_index()
    )
    per_month["max_conviction"] = per_month["month"].map(
        conv.groupby("month")["n_brokers"].max()
    )
    print(f"\nper-month brokers: min={per_month['n_brokers'].min()} "
          f"median={per_month['n_brokers'].median():.0f} max={per_month['n_brokers'].max()}")
    print("\nfull per-month table:")
    print(per_month.to_string(index=False))

    # Persist combined + summary for downstream steps
    df.to_parquet(OUT_DIR / "raw_combined.parquet", index=False)
    conv.to_parquet(OUT_DIR / "conviction_by_stock_month.parquet", index=False)
    per_month.to_csv(OUT_DIR / "per_month_summary.csv", index=False)
    print(f"\nwrote -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
