"""P1 attribution: did JoinQuant's market_stoploss fire on the same 6 dates as v8?

v8 went to all-cash via market_stoploss on these dates (from prior analysis):
    2015-06-30, 2015-07-16, 2015-07-28, 2015-08-19, 2015-09-02, 2015-09-15

This script extracts JQ's positions.csv and trades.csv and answers:
  Q1. On each of the 6 dates, how many positions did JQ hold at end-of-day?
  Q2. On each of the 6 dates, how many SELL trades did JQ execute?
  Q3. What were JQ's daily strategy returns on each of the 6 dates?
  Q4. What were JQ's NAV trajectories from D-1 through D+5 around each date?

If JQ position count drops to 0 on these dates → JQ also fired market_stoploss → not a divergence
If JQ position count stays at 12 (or similar) on these dates → JQ did NOT fire market_stoploss → divergence located

This is a pure read of pre-existing JQ artifacts — no backtesting, no new model assumption.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

JQ_DIR = Path(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12")

V8_STOPLOSS_DATES = [
    pd.Timestamp("2015-06-30"),
    pd.Timestamp("2015-07-16"),
    pd.Timestamp("2015-07-28"),
    pd.Timestamp("2015-08-19"),
    pd.Timestamp("2015-09-02"),
    pd.Timestamp("2015-09-15"),
]


def main() -> int:
    # --- Load JQ artifacts ---
    daily = pd.read_csv(JQ_DIR / "g5_G5_A2_stocknum12_daily.csv", parse_dates=["time"])
    positions = pd.read_csv(JQ_DIR / "g5_G5_A2_stocknum12_positions.csv", parse_dates=["time"])
    trades = pd.read_csv(JQ_DIR / "g5_G5_A2_stocknum12_trades.csv", parse_dates=["time"])

    daily["date"] = daily["time"].dt.normalize()
    positions["date"] = positions["time"].dt.normalize()
    trades["date"] = trades["time"].dt.normalize()

    print("=" * 80)
    print("JQ vs v8 market_stoploss firing comparison")
    print("=" * 80)
    print()

    # --- Q1 + Q2 + Q3: per-date answers ---
    print(f"{'Date':<12} {'JQ_pos_count':>12} {'JQ_sells':>10} {'JQ_buys':>10} "
          f"{'JQ_ret':>10} {'JQ_nav':>10}")
    print("-" * 80)
    for d in V8_STOPLOSS_DATES:
        pos_d = positions[positions["date"] == d]
        n_pos = len(pos_d)

        td = trades[trades["date"] == d]
        n_sell = (td["action"] == "close").sum()
        n_buy = (td["action"] == "open").sum()

        dr = daily[daily["date"] == d]
        ret = dr["daily_strategy_return"].iloc[0] if len(dr) else float("nan")
        nav = dr["nav"].iloc[0] if len(dr) else float("nan")
        print(
            f"{d.date()!s:<12} {n_pos:>12} {n_sell:>10} {n_buy:>10} "
            f"{ret:>10.4f} {nav:>10.4f}"
        )

    # --- Q4: NAV trajectory window around each date ---
    print()
    print("=" * 80)
    print("JQ NAV/return window: D-2 through D+5 around each v8 stoploss date")
    print("=" * 80)
    for d in V8_STOPLOSS_DATES:
        # Find trading days within ±5 calendar days
        window = daily[(daily["date"] >= d - pd.Timedelta(days=5))
                       & (daily["date"] <= d + pd.Timedelta(days=10))]
        if window.empty:
            continue
        print(f"\n--- Window around {d.date()} (v8 stoploss fire) ---")
        for _, row in window.iterrows():
            marker = " <-- v8 stoploss" if row["date"] == d else ""
            print(
                f"  {row['date'].date()}  ret={row['daily_strategy_return']:+.4f}  "
                f"nav={row['nav']:.4f}  drawdown={row['drawdown']:+.4f}{marker}"
            )

    # --- Summary table ---
    print()
    print("=" * 80)
    print("Summary: Did JQ go to all-cash on the v8 stoploss dates?")
    print("=" * 80)
    print()
    summary_rows = []
    for d in V8_STOPLOSS_DATES:
        pos_d = positions[positions["date"] == d]
        n_pos = len(pos_d)
        td = trades[trades["date"] == d]
        n_sell_today = (td["action"] == "close").sum()
        # Mass-sell event = N sells far in excess of usual rebalance (12 stocks total)
        all_cash = (n_pos == 0)
        mass_sell = (n_sell_today >= 8)  # JQ holds 12; a stoploss would close most/all
        summary_rows.append({
            "date": d.date(),
            "jq_n_pos_eod": n_pos,
            "jq_n_sell": n_sell_today,
            "jq_all_cash": all_cash,
            "jq_mass_sell": mass_sell,
        })
    summary_df = pd.DataFrame(summary_rows)
    print(summary_df.to_string(index=False))

    # --- Yearly position-zero days for the whole 2015 ---
    print()
    print("=" * 80)
    print("How many days did JQ go to ALL-CASH (n_pos==0) in 2015 vs 2014/2016?")
    print("=" * 80)
    for year in [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]:
        pos_y = positions[positions["date"].dt.year == year]
        days_y = pos_y["date"].nunique()
        days_with_positions = pos_y.groupby("date").size().shape[0]
        # Count days where someone held a position
        date_pos_count = pos_y.groupby("date").size()
        # Use daily.csv to get trading-day count
        daily_y = daily[daily["date"].dt.year == year]
        n_trading_days = len(daily_y)
        n_invested_days = len(date_pos_count)
        n_all_cash_days = n_trading_days - n_invested_days
        print(
            f"  {year}: trading_days={n_trading_days:3d} invested_days={n_invested_days:3d} "
            f"all_cash_days={n_all_cash_days:3d}"
        )

    # --- 2015 detailed: list every JQ all-cash day ---
    print()
    print("=" * 80)
    print("Every JQ all-cash day in 2015 (a date with no positions row)")
    print("=" * 80)
    pos_2015_dates = set(positions[positions["date"].dt.year == 2015]["date"].dt.normalize())
    daily_2015_dates = set(daily[daily["date"].dt.year == 2015]["date"].dt.normalize())
    cash_dates_2015 = sorted(daily_2015_dates - pos_2015_dates)
    print(f"Count: {len(cash_dates_2015)}")
    for d in cash_dates_2015:
        ret = daily[daily["date"] == d]["daily_strategy_return"].iloc[0]
        print(f"  {d.date()}  ret={ret:+.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
