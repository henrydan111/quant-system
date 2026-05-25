"""P1 attribution test: does treating suspended stocks as close/open=1.0
explain why JQ did NOT fire market_stoploss on the v8 stoploss-firing dates?

JoinQuant's get_price() on a suspended stock returns last-close for both
open and close, making close/open = 1.0. In contrast, v8's code drops rows
with open==0 or close/open=NaN. If 股灾 days had hundreds of suspended
002/003 names (panic halts), the JoinQuant effective mean is pulled UP
toward 1.0 — potentially above the 0.94 threshold.

This script computes mean(close/open) with TWO conventions on the prev_date
of each v8 stoploss date:
  - drop_nan: drop suspended/halted rows (the v8 convention)
  - fill_1: count suspended rows as ratio = 1.0 (the JoinQuant convention)

A row is treated as suspended if vol == 0 (the local Qlib convention) — and
get_price would return last_close for those, so close/open = 1.0 in JQ.

If mean_fill_1 > 0.94 on 4 of the 6 dates but mean_drop_nan ≤ 0.94 on those
dates, then suspended-handling is the mechanism explaining JQ's non-firing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(r"E:/量化系统")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_prev_trade_date(d: pd.Timestamp, cal: pd.DataFrame) -> pd.Timestamp | None:
    pri = cal[cal["cal_date"] < d]
    if pri.empty:
        return None
    return pd.Timestamp(pri.iloc[-1]["cal_date"])


def build_universe(
    sb: pd.DataFrame,
    d: pd.Timestamp,
    survivor_cutoff: pd.Timestamp | None,
    st_df: pd.DataFrame,
) -> set[str]:
    list_cutoff = d - pd.Timedelta(days=375)
    elig = sb[
        (sb["list_date"] <= list_cutoff)
        & ((sb["delist_date"].isna()) | (sb["delist_date"] > d))
    ]
    if survivor_cutoff is not None:
        elig = elig[
            elig["delist_date"].isna() | (elig["delist_date"] >= survivor_cutoff)
        ]
    st_today = st_df[
        (st_df["start"].notna())
        & (st_df["start"] <= d)
        & ((st_df["end"].isna()) | (st_df["end"] > d))
    ]
    return set(elig["ts_code"]) - set(st_today["ts_code"])


def main() -> int:
    sb = pd.read_parquet(PROJECT_ROOT / "data/reference/stock_basic.parquet")
    sb["list_date"] = pd.to_datetime(sb["list_date"], format="%Y%m%d", errors="coerce")
    sb["delist_date"] = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")
    sb = sb[sb["ts_code"].str.startswith("002") | sb["ts_code"].str.startswith("003")]

    cal = pd.read_parquet(PROJECT_ROOT / "data/reference/trade_cal.parquet")
    cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
    cal = cal[cal["is_open"] == 1].sort_values("cal_date").reset_index(drop=True)

    st_rows = []
    for line in (PROJECT_ROOT / "data/qlib_data/instruments/st_stocks.txt").read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        st_rows.append({
            "qlib_code": parts[0],
            "start": pd.to_datetime(parts[1], format="%Y-%m-%d", errors="coerce"),
            "end": pd.to_datetime(parts[2], format="%Y-%m-%d", errors="coerce"),
        })
    st_df = pd.DataFrame(st_rows)
    st_df["ts_code"] = st_df["qlib_code"].str.replace("_", ".").str.upper()

    import qlib
    from qlib.data import D
    qlib.init(provider_uri=str(PROJECT_ROOT / "data/qlib_data"), kernels=1)

    V8_STOPLOSS_DATES = [
        pd.Timestamp("2015-06-30"),
        pd.Timestamp("2015-07-16"),
        pd.Timestamp("2015-07-28"),
        pd.Timestamp("2015-08-19"),
        pd.Timestamp("2015-09-02"),
        pd.Timestamp("2015-09-15"),
    ]
    SURVIVOR_2026 = pd.Timestamp("2026-05-15")
    THRESH = 0.94

    all_codes = sorted({c.replace(".", "_") for c in sb["ts_code"]})
    df = D.features(all_codes, ["$open", "$close", "$vol"],
                    start_time="2015-05-01", end_time="2015-10-15", freq="day")
    df.columns = ["open", "close", "vol"]
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["datetime"]).dt.normalize()
    df["ts_code"] = df["instrument"].str.upper().str.replace("_", ".")

    print("=" * 120)
    print("Testing suspended-stock handling: does counting vol==0 names as ratio=1.0 lift the JQ mean above 0.94?")
    print("=" * 120)
    print(f"{'fire_date':<12} {'prev_date':<12} "
          f"{'n_trading':>10} {'n_susp':>9} "
          f"{'mean_drop':>11} {'mean_fill1':>12} "
          f"{'fire_drop?':>12} {'fire_fill1?':>13}")
    print("-" * 120)

    rows = []
    for fire_date in V8_STOPLOSS_DATES:
        prev_date = get_prev_trade_date(fire_date, cal)
        if prev_date is None:
            continue

        uni = build_universe(sb, prev_date, SURVIVOR_2026, st_df)
        # Note: we need EVERY universe member, not just those returned by D.features
        # If a stock is suspended for the entire window or wasn't yet listed,
        # D.features may omit the row entirely (NaN-only). For the JQ convention
        # the suspended/halted stock would have close/open=1.0 (last_close repeated).
        slice_ = df[df["date"] == prev_date].copy()
        slice_ = slice_[slice_["ts_code"].isin(uni)]
        # In our local Qlib data, suspended-stock rows show as NaN for open/close/vol
        valid = slice_[(slice_["open"] > 0) & slice_["close"].notna() & slice_["vol"].notna() & (slice_["vol"] > 0)]
        # All universe members minus those with valid trading data = effectively suspended/halted
        # under JQ's get_price convention they would contribute ratio=1.0
        n_total_universe = len(uni)
        n_trading_present = len(valid)
        n_missing = n_total_universe - n_trading_present
        susp_count = n_missing  # treat all missing rows as suspended-at-prev-close (JQ behavior)

        if len(valid) < 50:
            print(f"{fire_date.date()!s:<12} {prev_date.date()!s:<12}  not enough valid rows ({len(valid)})")
            continue

        # mean_drop = v8 convention: only the trading universe
        ratio_valid = (valid["close"] / valid["open"]).mean()
        n_trading = n_trading_present
        n_susp = susp_count
        # mean_fill1 = JQ convention: count suspended at 1.0
        n_total = n_trading + n_susp
        ratio_fill = (ratio_valid * n_trading + 1.0 * n_susp) / max(n_total, 1)

        fire_drop = "FIRE" if ratio_valid <= THRESH else "no"
        fire_fill = "FIRE" if ratio_fill <= THRESH else "no"

        print(
            f"{fire_date.date()!s:<12} {prev_date.date()!s:<12} "
            f"{n_trading:>10d} {n_susp:>9d} "
            f"{ratio_valid:>11.4f} {ratio_fill:>12.4f} "
            f"{fire_drop:>12} {fire_fill:>13}"
        )
        rows.append({
            "fire_date": fire_date.date(),
            "prev_date": prev_date.date(),
            "n_trading": n_trading,
            "n_susp": n_susp,
            "mean_drop_nan": ratio_valid,
            "mean_fill1": ratio_fill,
            "fire_drop": fire_drop,
            "fire_fill1": fire_fill,
        })

    print()
    print("=" * 120)
    # Compare to the actual JQ stoploss firings observed
    obs_jq_fired = {
        "2015-06-30": False,  # JQ did NOT fire on 06-30 (fired 06-29 instead)
        "2015-07-16": False,
        "2015-07-28": False,
        "2015-08-19": True,
        "2015-09-02": False,
        "2015-09-15": True,
    }
    print(f"{'fire_date':<12} {'JQ_actual_fired':>16} {'fill1_predicts':>16} {'reconciled?':>12}")
    print("-" * 80)
    for r in rows:
        actual = obs_jq_fired[str(r["fire_date"])]
        predicted = (r["fire_fill1"] == "FIRE")
        reconciled = (actual == predicted)
        print(f"{r['fire_date']!s:<12} {actual!s:>16} {predicted!s:>16} {reconciled!s:>12}")

    df_out = pd.DataFrame(rows)
    out_path = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v8_100k_capital_run/suspended_pull_up.csv"
    df_out.to_csv(out_path, index=False)
    print(f"\nWrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
