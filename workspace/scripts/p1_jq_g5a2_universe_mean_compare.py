"""P1 attribution: compute the actual mean(close/open) for two candidate universes
on the 6 v8 stoploss-firing dates, to determine whether the v8/JQ universe
mismatch is sufficient to explain JQ NOT firing stoploss on those days.

For each of the 6 dates D in {2015-06-30, 2015-07-16, 2015-07-28, 2015-08-19,
2015-09-02, 2015-09-15} the stoploss check looks at the PREVIOUS trading day's
close/open ratio. We compute mean(close/open) on prev_date over:

  Universe V8a = v8 actual universe (002/003 alive at 2024-01-01, 375d list,
                 no ST) — what the v8 code uses
  Universe V8b = same as V8a but WITHOUT survivor filter — what JQ would do
                 if its get_index_stocks honored PIT membership
  Universe JQa = 002/003 alive at 2026-05-15 (proxy for JQ's frozen
                 get_index_stocks('399101.XSHE') current membership)
  Universe JQb = 002/003 alive at "today" (= same as JQa for a finished
                 backtest) — sanity check

If mean(close/open) > 0.94 in JQa but ≤ 0.94 in V8a on the disputed dates,
then mechanism B is fully explanatory. If both are ≤ 0.94, mechanism B is not
the explanation (must be mechanism A or another factor).
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
    """Build the universe of 002/003 stocks on date d under different filters."""
    list_cutoff = d - pd.Timedelta(days=375)
    elig = sb[
        (sb["list_date"] <= list_cutoff)
        & ((sb["delist_date"].isna()) | (sb["delist_date"] > d))
    ]
    if survivor_cutoff is not None:
        elig = elig[
            elig["delist_date"].isna() | (elig["delist_date"] >= survivor_cutoff)
        ]
    # ST exclusion
    st_today = st_df[
        (st_df["start"].notna())
        & (st_df["start"] <= d)
        & ((st_df["end"].isna()) | (st_df["end"] > d))
    ]
    return set(elig["ts_code"]) - set(st_today["ts_code"])


def main() -> int:
    # --- Load reference data ---
    sb = pd.read_parquet(PROJECT_ROOT / "data/reference/stock_basic.parquet")
    sb["list_date"] = pd.to_datetime(sb["list_date"], format="%Y%m%d", errors="coerce")
    sb["delist_date"] = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")
    # Filter to 002/003 only (mainboard SMB)
    sb = sb[sb["ts_code"].str.startswith("002") | sb["ts_code"].str.startswith("003")]

    cal = pd.read_parquet(PROJECT_ROOT / "data/reference/trade_cal.parquet")
    cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
    cal = cal[cal["is_open"] == 1].sort_values("cal_date").reset_index(drop=True)

    # Load ST ranges
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

    # --- Init qlib + load OHLC on the 6 dates' previous trading days ---
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
    SURVIVOR_2024 = pd.Timestamp("2024-01-01")
    SURVIVOR_2026 = pd.Timestamp("2026-05-15")
    THRESH = 0.94

    print("=" * 110)
    print("Mean(close/open) on prev_date for 6 v8-stoploss dates, across 4 candidate universes")
    print("=" * 110)
    print(f"Threshold = {THRESH}; lower mean → stoploss FIRES; higher mean → no fire")
    print()
    print(f"{'fire_date':<12} {'prev_date':<12} "
          f"{'V8a_2024surv':>14} {'V8b_no_surv':>13} "
          f"{'JQa_2026surv':>14} {'fired?_V8a':>11} {'fired?_JQa':>11}")
    print("-" * 110)

    all_codes = sorted({c.replace(".", "_") for c in sb["ts_code"]})
    # Pull a wide window — May 1 to Oct 1, 2015 — covers all prev_dates and dates.
    feat_start = "2015-05-01"
    feat_end = "2015-10-15"
    df = D.features(all_codes, ["$open", "$close"],
                    start_time=feat_start, end_time=feat_end, freq="day")
    df.columns = ["open", "close"]
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["datetime"]).dt.normalize()
    df["ts_code"] = df["instrument"].str.upper().str.replace("_", ".")

    summary_rows = []
    for fire_date in V8_STOPLOSS_DATES:
        prev_date = get_prev_trade_date(fire_date, cal)
        if prev_date is None:
            continue

        # OHLC on prev_date
        slice_ = df[df["date"] == prev_date]
        slice_ = slice_[slice_["open"] > 0].dropna(subset=["close", "open"])

        # Universes on prev_date
        v8a = build_universe(sb, prev_date, SURVIVOR_2024, st_df)
        v8b = build_universe(sb, prev_date, None, st_df)
        jqa = build_universe(sb, prev_date, SURVIVOR_2026, st_df)

        def mean_for(uni: set) -> tuple[float, int]:
            sub = slice_[slice_["ts_code"].isin(uni)]
            if len(sub) < 50:
                return float("nan"), len(sub)
            return float((sub["close"] / sub["open"]).mean()), len(sub)

        m_v8a, n_v8a = mean_for(v8a)
        m_v8b, n_v8b = mean_for(v8b)
        m_jqa, n_jqa = mean_for(jqa)

        fired_v8a = "FIRE" if m_v8a <= THRESH else "no"
        fired_jqa = "FIRE" if m_jqa <= THRESH else "no"

        print(
            f"{fire_date.date()!s:<12} {prev_date.date()!s:<12} "
            f"{m_v8a:>10.4f}({n_v8a:>3d}) {m_v8b:>9.4f}({n_v8b:>3d}) "
            f"{m_jqa:>10.4f}({n_jqa:>3d}) {fired_v8a:>11} {fired_jqa:>11}"
        )

        summary_rows.append({
            "fire_date": fire_date.date(),
            "prev_date": prev_date.date(),
            "mean_close_open_v8a": m_v8a,
            "n_v8a": n_v8a,
            "mean_close_open_jqa": m_jqa,
            "n_jqa": n_jqa,
            "v8a_fires": fired_v8a,
            "jqa_fires": fired_jqa,
        })

    print()
    print("=" * 110)
    print("Reconciliation: did v8 v.s. JQ actually agree on these stoploss dates?")
    print("=" * 110)
    # Save the summary
    summary_df = pd.DataFrame(summary_rows)
    out_path = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v8_100k_capital_run/universe_mean_compare.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(out_path, index=False)
    print(f"Wrote: {out_path}")
    print(summary_df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
