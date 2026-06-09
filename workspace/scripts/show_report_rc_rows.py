"""Show actual report_rc rows: report_date next to create_time, old era vs new era."""
import os
import pandas as pd

D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "data", "analyst", "report_rc")
pd.set_option("display.width", 160)

for yr in (2015, 2023):
    df = pd.read_parquet(os.path.join(D, f"report_rc_{yr}.parquet"))
    df = df.sort_values("report_date")
    print(f"\n===== report_date year {yr}: 5 sample rows =====")
    print(df[["ts_code", "report_date", "create_time", "org_name"]].head(5).to_string(index=False))
    # gap between when it was written and when it arrived, in days
    rd = pd.to_datetime(df["report_date"], format="%Y%m%d", errors="coerce")
    ct = pd.to_datetime(df["create_time"], errors="coerce")
    gap_days = (ct - rd).dt.days
    print(f"  median (arrived - written) gap: {gap_days.median():.0f} days   "
          f"min {gap_days.min():.0f} / max {gap_days.max():.0f}")
