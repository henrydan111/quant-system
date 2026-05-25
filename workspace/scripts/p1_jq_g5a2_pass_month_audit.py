"""P1 attribution: did JoinQuant actually enforce pass_months=[1,4]?

v8 sells everything in January and April. JQ's strategy file declares
pass_months=[1,4] AND no_trading_today_signal — but JQ's 2015 all-cash day
count is 0. This script audits whether JQ ACTUALLY went to cash on Jan + Apr
trading days, year by year.

Specifically inspects:
  - n_pos at EOD per day in January and April for each year
  - number of "open" (buy) trades per day in Jan + Apr (JQ pass_months → 0 buys)
  - n positions over time to detect whether JQ HOLDS positions through pass-months
    rather than selling them
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

JQ_DIR = Path(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12")


def main() -> int:
    daily = pd.read_csv(JQ_DIR / "g5_G5_A2_stocknum12_daily.csv", parse_dates=["time"])
    positions = pd.read_csv(JQ_DIR / "g5_G5_A2_stocknum12_positions.csv", parse_dates=["time"])
    trades = pd.read_csv(JQ_DIR / "g5_G5_A2_stocknum12_trades.csv", parse_dates=["time"])

    daily["date"] = daily["time"].dt.normalize()
    positions["date"] = positions["time"].dt.normalize()
    trades["date"] = trades["time"].dt.normalize()

    # Build n_pos per date
    n_pos_by_date = positions.groupby("date").size()

    # Build n_buy / n_sell per date
    n_buy_by_date = trades[trades["action"] == "open"].groupby("date").size()
    n_sell_by_date = trades[trades["action"] == "close"].groupby("date").size()

    # All trading dates from daily.csv
    all_dates = daily["date"].sort_values()
    df = pd.DataFrame({"date": all_dates}).set_index("date")
    df["n_pos_eod"] = n_pos_by_date
    df["n_pos_eod"] = df["n_pos_eod"].fillna(0).astype(int)
    df["n_buy"] = n_buy_by_date.reindex(df.index).fillna(0).astype(int)
    df["n_sell"] = n_sell_by_date.reindex(df.index).fillna(0).astype(int)
    df["year"] = df.index.year
    df["month"] = df.index.month

    print("=" * 90)
    print("JQ pass-month audit: Did JQ actually sell-all in January and April?")
    print("=" * 90)
    print()
    print(f"{'Year':<6} {'Month':>6} {'Trading_days':>13} {'AllCash_days':>13} "
          f"{'Mean_pos':>9} {'Total_buys':>11} {'Total_sells':>12}")
    print("-" * 90)
    for year in range(2014, 2027):
        for month in [1, 4]:
            slice_ = df[(df["year"] == year) & (df["month"] == month)]
            if slice_.empty:
                continue
            print(
                f"{year:<6d} {month:>6d} {len(slice_):>13d} "
                f"{(slice_['n_pos_eod'] == 0).sum():>13d} "
                f"{slice_['n_pos_eod'].mean():>9.1f} "
                f"{slice_['n_buy'].sum():>11d} "
                f"{slice_['n_sell'].sum():>12d}"
            )

    # Detailed view of 2015 Jan + April (the year with zero all-cash days)
    print()
    print("=" * 90)
    print("Detailed: JQ daily n_pos / trades in 2015-01 and 2015-04")
    print("=" * 90)
    for month in [1, 4]:
        s = df[(df["year"] == 2015) & (df["month"] == month)]
        print(f"\n--- 2015-{month:02d} ---")
        for date, row in s.iterrows():
            print(
                f"  {date.date()}  n_pos_eod={int(row['n_pos_eod']):>2d} "
                f"buy={int(row['n_buy']):>2d}  sell={int(row['n_sell']):>2d}"
            )

    # Detailed view of 2015 stoploss zone: 06-25 through 09-30
    print()
    print("=" * 90)
    print("Detailed: JQ daily n_pos / trades 2015-06-25 to 2015-09-30")
    print("=" * 90)
    s = df[(df.index >= "2015-06-25") & (df.index <= "2015-09-30")]
    for date, row in s.iterrows():
        marker = ""
        if date in [pd.Timestamp("2015-06-30"), pd.Timestamp("2015-07-16"),
                    pd.Timestamp("2015-07-28"), pd.Timestamp("2015-08-19"),
                    pd.Timestamp("2015-09-02"), pd.Timestamp("2015-09-15")]:
            marker = " <-- v8 stoploss fired"
        print(
            f"  {date.date()}  n_pos_eod={int(row['n_pos_eod']):>2d} "
            f"buy={int(row['n_buy']):>2d}  sell={int(row['n_sell']):>2d}{marker}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
